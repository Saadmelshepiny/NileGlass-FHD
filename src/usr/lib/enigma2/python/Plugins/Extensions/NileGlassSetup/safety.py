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


def install():
	try:
		import Screens.ButtonSetup as bs
		if getattr(bs, "_ngSafe", False) or not hasattr(bs, "iterPlugins"):
			return
		bs.iterPlugins = safeIterPlugins
		bs._ngSafe = True
	except Exception as err:
		print("[NileGlass] safety install:", err)
