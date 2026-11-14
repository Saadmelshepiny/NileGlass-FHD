# -*- coding: utf-8 -*-
# NileGlass FHD - keep a broken plugin descriptor from crashing the image.
#
# Screens.ButtonSetup ("Button setup" in the user interface menu, and every
# long / short press of a programmable key) lists all plugins: it sorts them
# by name and looks into each function's code.  A plugin with no name, or
# whose function is not a plain Python function, makes that raise and the
# whole receiver restarts.  This replaces only that listing step with one that
# skips such a plugin (written to /tmp/nileglass_perf.log) instead.

def _log(text):
	print("[NileGlass] safety:", text)
	try:
		from .perfwatch import write
		write("safety " + text)
	except Exception:
		pass


def safeIterPlugins(pluginlist, twinPlugins, twinPaths, predicate=None):
	items = []
	for plugin in list(pluginlist or []):
		name = getattr(plugin, "name", None)
		if not isinstance(name, str) or not name:
			_log("plugin without a name skipped: %r" % (getattr(plugin, "path", None),))
			continue
		items.append(plugin)
	items.sort(key=lambda p: p.name)
	for plugin in items:
		try:
			fnc, path = plugin.fnc, plugin.path
			if not path:
				continue
			try:
				if fnc in twinPlugins:
					continue
			except TypeError:          # unhashable function object
				continue
			if predicate is not None:
				try:
					if not predicate(plugin):
						continue
				except Exception as err:
					_log("plugin %s skipped: %s" % (plugin.name, err))
					continue
			key = path[path.rfind("Plugins"):]
			twinPaths[key] = twinPaths.get(key, 0) + 1
			twinPlugins.add(fnc)
		except Exception as err:
			_log("plugin %s skipped: %s" % (getattr(plugin, "name", "?"), err))
			continue
		yield plugin, key, twinPaths[key]


def patchActionMap():
	"""enigma2 stops the whole receiver (eFatal "unbindAction with illegal
	python reference") when a key map is unbound with a function other than
	the one it was bound with.  That happens when a plugin replaces the
	.action of a key map while it is bound (the global key map is the usual
	one) and a screen then turns it off - "Button setup" does exactly that.
	Here every key map remembers what it bound and unbinds exactly that."""
	from Components.ActionMap import ActionMap
	if getattr(ActionMap, "_ngSafeBind", False):
		return

	def doBind(self):
		if not self.bound:
			fn = self.action
			done = []
			for context in self.contexts:
				self.p.bindAction(context, self.prio, fn)
				done.append((context, fn))
			self._ngBoundWith = done
			self.bound = True

	def doUnbind(self):
		if self.bound:
			done = getattr(self, "_ngBoundWith", None)
			if done is None:                       # bound before this patch
				done = [(c, self.action) for c in self.contexts]
			elif any(fn != self.action for _c, fn in done):
				_log("key map %s: action replaced while bound, unbinding the original" % self.__class__.__name__)
			for context, fn in done:
				self.p.unbindAction(context, fn)
			self._ngBoundWith = None
			self.bound = False
	ActionMap.doBind = doBind
	ActionMap.doUnbind = doUnbind
	ActionMap._ngSafeBind = True


def patchButtonSetup(bs):
	"""Button setup turns the global key map off while it waits for a key
	(globalActionMap.setEnabled(False)).  If another plugin has rebound or
	replaced that key map, unbinding it stops the receiver.  Here the global
	keys are silenced by emptying their action table instead - same effect,
	nothing is unbound - and restored when the screen closes."""
	cls = getattr(bs, "ButtonSetup", None)
	if cls is None or getattr(cls, "_ngSafeKeys", False):
		return
	from enigma import eActionMap

	def disableKeyMap(self):
		g = bs.globalActionMap
		if getattr(g, "_ngSaved", None) is None:
			g._ngSaved = g.actions
			g.actions = {}
		p = eActionMap.getInstance()
		for k in (0, 1, 4, 5):
			p.unbindNativeKey("ListboxActions", k)

	def enableKeyMap(self):
		g = bs.globalActionMap
		saved = getattr(g, "_ngSaved", None)
		if saved is not None:
			g.actions = saved
			g._ngSaved = None
		p = eActionMap.getInstance()
		p.bindKey("keymap.xml", "generic", 103, 5, "ListboxActions", "moveUp")
		p.bindKey("keymap.xml", "generic", 108, 5, "ListboxActions", "moveDown")
		p.bindKey("keymap.xml", "generic", 105, 5, "ListboxActions", "pageUp")
		p.bindKey("keymap.xml", "generic", 106, 5, "ListboxActions", "pageDown")
	cls.disableKeyMap = disableKeyMap
	cls.enableKeyMap = enableKeyMap
	cls._ngSafeKeys = True


def patchExtensions():
	"""Blue held = the extensions list.  Its opening is written to the speed
	report, and an error inside it is shown instead of doing nothing."""
	from Screens.InfoBarGenerics import InfoBarExtensions
	if getattr(InfoBarExtensions, "_ngLogged", False):
		return
	original = InfoBarExtensions.showExtensionSelection

	def showExtensionSelection(self, *args, **kwargs):
		try:
			from .perfwatch import write
			write("extensions open %d" % len(getattr(self, "extensionsList", []) or []))
		except Exception:
			pass
		try:
			return original(self, *args, **kwargs)
		except Exception as err:
			_log("extensions list failed: %s" % err)
			try:
				from .perfwatch import write
				write("extensions error %s" % str(err).replace(" ", "_")[:80])
				from Screens.MessageBox import MessageBox
				self.session.open(MessageBox, "قائمة الإضافات مفتحتش:\n%s" % err, MessageBox.TYPE_ERROR, timeout=10)
			except Exception:
				pass
	InfoBarExtensions.showExtensionSelection = showExtensionSelection
	InfoBarExtensions._ngLogged = True


def install():
	try:
		patchActionMap()
	except Exception as err:
		print("[NileGlass] safety keymap:", err)
	try:
		patchExtensions()
	except Exception as err:
		print("[NileGlass] safety extensions:", err)
	try:
		import Screens.ButtonSetup as bs
		if getattr(bs, "_ngSafe", False) or not hasattr(bs, "iterPlugins"):
			return
		bs.iterPlugins = safeIterPlugins
		bs._ngSafe = True
		patchButtonSetup(bs)
	except Exception as err:
		print("[NileGlass] safety install:", err)
