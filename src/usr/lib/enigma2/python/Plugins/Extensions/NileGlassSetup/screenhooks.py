# -*- coding: utf-8 -*-
# NileGlass FHD - small additions to image screens for the cards beside them:
#   * package list (Plugins > download / remove): "ng_sel", the package under the cursor
#   * Blue Panel: left / right pick the next / previous emu (round), "ng_emupos" says
#     which one of how many; OK starts it as before (the image's own code)
# Installed once at GUI start; a screen that fails here still opens as usual.


def _addSelection(cls, listName="list", name="ng_sel"):
	if getattr(cls, "_ngSel", False):
		return
	orig = cls.__init__

	def __init__(self, *args, **kwargs):
		orig(self, *args, **kwargs)
		try:
			from Components.Sources.NGSelection import NGSelection
			if name not in self:
				self[name] = NGSelection(self[listName])
		except Exception as err:
			print("[NileGlass] screen hook:", err)
	cls.__init__ = __init__
	cls._ngSel = True


def emuMove(screen, step):
	"""Blue Panel: the next / previous installed emu in its list (round)"""
	lst = screen["list"]
	n = len(getattr(lst, "list", []) or [])
	if n < 2:
		return
	try:
		cur = lst.getSelectedIndex()
	except Exception:
		cur = 0
	lst.moveToIndex((cur + step) % n)
	emuPos(screen)


def emuPos(screen):
	try:
		lst = screen["list"]
		n = len(getattr(lst, "list", []) or [])
		if n:
			screen["ng_emupos"].setText("%d من %d   ·   يمين / شمال للتبديل" % (lst.getSelectedIndex() + 1, n) if n > 1 else "إيمو واحد مثبت")
		else:
			screen["ng_emupos"].setText("")
		# the image's list does not redraw when it is moved from here, so the
		# chosen name is shown in a label over it (OK still takes the list's own choice)
		name = lst.getCurrent() if n else ""
		name = name[0] if isinstance(name, tuple) else (name or "")
		active = screen["activecam"].getText() if "activecam" in screen else ""
		screen["ng_emuname"].setText(name + ("   (الشغال)" if name and name == active else ""))
	except Exception as err:
		print("[NileGlass] blue panel:", err)


def _addEmuSwitch(cls):
	if getattr(cls, "_ngEmu", False):
		return
	orig = cls.__init__

	def __init__(self, *args, **kwargs):
		orig(self, *args, **kwargs)
		try:
			from Components.ActionMap import ActionMap
			from Components.Label import Label
			self["ng_emupos"] = Label("")
			self["ng_emuname"] = Label("")
			self["ng_emuActions"] = ActionMap(["DirectionActions"], {
				"left": lambda: emuMove(self, -1),
				"right": lambda: emuMove(self, 1),
			}, -2)
			# onShow, never onLayoutFinish: enigma2 exec()s anything there that is
			# not a bound method, and the screen then does not open at all
			self.onShow.append(lambda: emuPos(self))
		except Exception as err:
			print("[NileGlass] blue panel hook:", err)
	cls.__init__ = __init__
	cls._ngEmu = True


def install():
	try:
		from Screens.BpBlue import DeliteBluePanel
		_addEmuSwitch(DeliteBluePanel)
	except Exception as err:
		print("[NileGlass] screen hook:", err)
	try:
		from Screens.PluginBrowser import PluginDownloadBrowser
		_addSelection(PluginDownloadBrowser)
	except Exception as err:
		print("[NileGlass] screen hook:", err)
