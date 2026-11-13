# -*- coding: utf-8 -*-
# NileGlass FHD - menus and settings panels as tall as what they show.
#
# With the "panel over the picture" look, the Menu and Setup screens are a
# panel at the left edge of the screen.  The skin gives them room for the
# longest list; here, once laid out (and again whenever a settings list
# changes), the list gets exactly the rows it has (up to a maximum, then it
# scrolls), everything below the list moves up with it and the panel takes
# the resulting height, centred vertically.  A two-row menu is a small panel,
# a 12-row menu fits on one page instead of spilling one row onto a second.
# Full-screen skins (the other look, other skins) are left alone.

from enigma import ePoint, eSize, getDesktop

LEFT = 40          # panel distance from the left edge
MARGIN = 30        # free space kept above and below the panel
MENU_MIN_ROWS = 9     # a 3-item menu still looks like a menu, not a strip
SETUP_MIN_ROWS = 8
FULL = 1800        # a window this wide is a full-screen skin: not touched


def _itemHeight(widget, default):
	for attrib, value in getattr(widget, "skinAttributes", None) or []:
		if attrib == "itemHeight":
			try:
				return int(value)
			except ValueError:
				pass
	return default


def _instances(screen):
	"""Every on-screen part of a screen: components, renderers, skin labels/pixmaps."""
	out = []
	for comp in list(screen.values()) + list(getattr(screen, "renderer", [])) + list(getattr(screen, "additionalWidgets", [])):
		inst = getattr(comp, "instance", None)
		if inst is not None and inst not in out:
			out.append(inst)
	return out


def _log(text):
	print("[NileGlass] fit:", text)
	try:
		from .perfwatch import write
		write("fit " + text)
	except Exception:
		pass


class _Fit:
	def __init__(self, screen, listWidget, rows, itemHeight, minRows=1):
		self.screen, self.listWidget, self.rows, self.itemHeight = screen, listWidget, rows, itemHeight
		self.minRows = minRows     # short lists still get a panel of a decent height

	def run(self):
		s = self.screen
		win = getattr(s, "instance", None)
		lst = getattr(self.listWidget(), "instance", None)
		name = s.__class__.__name__
		if win is None or lst is None:
			_log("%s skipped: %s" % (name, "no window" if win is None else "list not found"))
			return
		if win.size().width() >= FULL:
			return
		dw, dh = getDesktop(0).size().width(), getDesktop(0).size().height()
		ly, lh = lst.position().y(), lst.size().height()
		H0 = win.size().height()
		below = H0 - (ly + lh)                     # description / buttons under the list
		maxRows = max(1, (dh - 2 * MARGIN - ly - below) // self.itemHeight)
		rows = max(self.minRows, min(self.rows(), maxRows))
		newH = rows * self.itemHeight
		delta = newH - lh
		if not delta:
			win.move(ePoint(LEFT, max(MARGIN, (dh - H0) // 2)))
			return
		bottom = ly + lh
		for inst in _instances(s):
			if inst is lst or inst is win:
				continue
			p = inst.position()
			if p.y() >= bottom - 2:                # under the list: follows it
				inst.move(ePoint(p.x(), p.y() + delta))
			elif p.y() <= ly and p.y() + inst.size().height() >= bottom - 2:   # spans the panel (background, divider)
				inst.resize(eSize(inst.size().width(), inst.size().height() + delta))
		lst.resize(eSize(lst.size().width(), newH))
		H = H0 + delta
		win.resize(eSize(win.size().width(), H))
		win.move(ePoint(LEFT, max(MARGIN, (dh - H) // 2)))


def _menuList(screen):
	"""The Listbox renderer of the "menu" source; between them there is a
	converter (TemplatedMultiContent), so follow the chain of sources."""
	menu = screen.get("menu")
	for r in getattr(screen, "renderer", []):
		src, depth = getattr(r, "source", None), 0
		while src is not None and depth < 5:
			if src is menu:
				return r
			src, depth = getattr(src, "source", None), depth + 1
	return None


# other list screens of the image that NileGlass draws as a left panel:
# class name -> (list widget, row height, minimum rows)
OTHER = {
	"AdapterSetupConfiguration": ("menulist", 58, 9),
	"NetworkMountsMenu": ("menulist", 58, 9),
	"AdapterSetup": ("config", 54, 8),
}


def _otherFit(screen):
	name, ih, minRows = OTHER[screen.__class__.__name__]
	if name not in screen:
		return None

	def rows():
		items = getattr(screen, "mainmenu", None) if name == "menulist" else None
		if items is None:
			items = getattr(screen[name], "list", None)
		return len(items or [])
	return _Fit(screen, lambda: screen[name], rows, ih, minRows).run


def _patchApplySkin():
	"""Fit right after the screen is laid out (end of applySkin), whatever
	other plugins do with onLayoutFinish or close()."""
	from Screens.Screen import Screen
	if getattr(Screen, "_ngFitHook", False):
		return
	original = Screen.applySkin

	def applySkin(self, *args, **kwargs):
		result = original(self, *args, **kwargs)
		fit = getattr(self, "_ngFitNow", None)
		if fit is None and self.__class__.__name__ in OTHER:
			fit = _otherFit(self)
		if fit is not None:
			try:
				fit()
			except Exception as err:
				_log("%s failed: %s" % (self.__class__.__name__, err))
		return result
	Screen.applySkin = applySkin
	Screen._ngFitHook = True


def install():
	try:
		_patchApplySkin()
	except Exception as err:
		print("[NileGlass] fit hook:", err)
	try:
		from Screens.Menu import Menu
		if not getattr(Menu, "_ngFit", False):
			original = Menu.__init__

			def __init__(self, *args, **kwargs):
				original(self, *args, **kwargs)
				try:
					fit = _Fit(self, lambda: _menuList(self), lambda: len(self["menu"].list or []), 66, MENU_MIN_ROWS)
					self._ngFitNow = fit.run
				except Exception as err:
					print("[NileGlass] menu fit:", err)
			Menu.__init__ = __init__
			Menu._ngFit = True
	except Exception as err:
		print("[NileGlass] menu fit install:", err)
	try:
		from Screens.Setup import Setup
		if not getattr(Setup, "_ngFit", False):
			originalInit = Setup.__init__
			originalCreate = Setup.createSetup

			def __init__(self, *args, **kwargs):
				originalInit(self, *args, **kwargs)
				try:
					fit = _Fit(self, lambda: self["config"], lambda: len(self["config"].list or []), _itemHeight(self["config"], 54), SETUP_MIN_ROWS)
					self._ngFitNow = self._ngFitSetup = fit.run
				except Exception as err:
					print("[NileGlass] setup fit:", err)

			def createSetup(self, *args, **kwargs):
				result = originalCreate(self, *args, **kwargs)
				try:
					fit = getattr(self, "_ngFitSetup", None)
					if fit and getattr(self, "instance", None) is not None:
						fit()
				except Exception as err:
					print("[NileGlass] setup fit:", err)
				return result
			Setup.__init__ = __init__
			Setup.createSetup = createSetup
			Setup._ngFit = True
	except Exception as err:
		print("[NileGlass] setup fit install:", err)
