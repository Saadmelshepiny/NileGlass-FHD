# -*- coding: utf-8 -*-
# NileGlass FHD - the cards beside menus and settings follow the subject.
#
# Each card set (network, tuners & dish, picture & sound, system) is a small
# window of its own (skin screens NileGlassDash_<subject>), built once and
# kept: a menu or settings panel only carries a marker saying where the cards
# go.  A moment after the panel is on screen the set that fits the menu entry
# under the cursor (or the open settings screen) is put beside it.  So a menu
# opens as fast as a plain panel, the cards are never built twice, and only
# the visible set reads the box (hidden windows are suspended by enigma2).

GROUPS = {"net": 1, "tuner": 2, "av": 3, "system": 4, "time": 5, "image": 6, "emu": 7, "bt": 8, "option": 9}

NET = ("network", "net", "device_setup", "password_setup", "inadyn", "ftp", "samba", "telnet", "nfs", "vpn", "dlna",
	"ushare", "adapter", "nameserver", "wlan", "wifi", "streaming", "mount")
TUNER = ("scan", "tuner", "nim", "satfinder", "positioner", "blindscan", "fallback", "client_mode", "diseqc", "satconfig",
	"lnb", "cable", "terrestrial", "dish", "motor", "rotor", "sat_", "ci_", "cicam", "fcc")
AV = ("video", "audio", "autolanguage", "subtitle", "hdmi", "osd", "3d", "avsetup", "picture", "aspect", "volume", "ac3", "dts", "display")


BT = ("bluetooth", "bt_", "btsetup", "btdevice")
EMU = ("softcam", "oscam", "ncam", "emu", "camd", "autocam", "cam_", "camsetup", "camstart")
TIME = ("time", "clock", "timezone", "ntp")
IMAGE = ("softwareupdate", "software_update", "imageupdate", "update", "imagemanager", "flash", "upgrade", "feed")


def subject(*keys):
	for key in keys:
		k = (key or "").lower()
		if not k:
			continue
		if any(p in k for p in BT):
			return "bt"
		if k == "av" or k.startswith("av_") or any(p in k for p in AV):
			return "av"
		if any(p in k for p in TUNER):
			return "tuner"
		if any(p in k for p in EMU):
			return "emu"
		if any(p in k for p in NET):
			return "net"
		if any(p in k for p in TIME) and "timeshift" not in k and "timer" not in k:
			return "time"
		if any(p in k for p in IMAGE):
			return "image"
	return None


MARKER_Z = "-77"       # zPosition of the marker label in the skin (tools/gen_menus_popup.py)
DASH_W, DASH_H = 670, 464
SHOW_DELAY, HIDE_DELAY = 90, 160     # ms: after the panel shows / after it went away

_session = None
_dialogs = {}          # subject -> (dialog or None, skin element it was built from)
_want = None           # the screen that should have cards beside it now
_timer = None
_Dash = None
_warm = None


def enabled():
	try:
		from Components.NileGlassCore import confBool
		return confBool("extras", "dash", True) and not confBool("style", "lite", False)
	except Exception:
		return True


def setSession(session):
	"""Called once at start.  A while later, when the box is idle, the card
	windows are built one by one (hidden), so the first menu does not wait."""
	global _session, _warm
	_session = session
	try:
		from enigma import eTimer
		todo = ["system", "option", "net", "tuner", "av"]

		def step():
			try:
				if enabled() and todo:
					_dialog(todo.pop(0))
					if todo:
						_warm.start(1500, True)
			except Exception as err:
				print("[NileGlass] dash warm-up:", err)
		_warm = eTimer()
		_warm.callback.append(step)
		_warm.start(20000, True)
	except Exception as err:
		print("[NileGlass] dash warm-up:", err)


def menuSubject(screen):
	key = None
	try:
		cur = screen["menu"].getCurrent()
		key = cur[2] if cur and len(cur) > 2 else None
	except Exception:
		pass
	menuID = getattr(screen, "menuID", None)
	if menuID == "mainmenu" and key == "setup":
		return "system"
	return subject(key, menuID) or "system"


def setupSubject(screen):
	"""a settings screen: its subject, else the cards about its own options (and its plugin)"""
	return subject(getattr(screen, "setup", None), screen.__class__.__name__, getattr(screen.__class__, "__module__", ""),
		" ".join(screen.skinName) if isinstance(getattr(screen, "skinName", None), list) else getattr(screen, "skinName", "")) or "option"


def _marker(screen):
	for w in getattr(screen, "additionalWidgets", None) or []:
		for attrib, value in getattr(w, "skinAttributes", None) or []:
			if attrib == "zPosition" and str(value) == MARKER_Z:
				return w
	return None


def _skinElement(name):
	try:
		from skin import domScreens
		return domScreens.get("NileGlassDash_" + name)
	except Exception:
		return None


def _dialog(name):
	"""the window of a card set: built on first use, rebuilt after a skin reload"""
	global _Dash
	element = _skinElement(name)
	have = _dialogs.get(name)
	if have is not None and have[1] is element:
		return have[0]
	if have is not None and have[0] is not None:      # skin reloaded: the old window has the old look
		try:
			_session.deleteDialog(have[0])
		except Exception as err:
			print("[NileGlass] dash:", err)
	dialog = None
	if element is not None and _session is not None:
		try:
			if _Dash is None:
				from Screens.Screen import Screen

				class NileGlassDash(Screen):
					def __init__(self, session, subject):
						Screen.__init__(self, session)
						self.skinName = "NileGlassDash_" + subject
						try:
							from Components.Sources.NGHost import NGHost
							self["ctx"] = NGHost()      # the screen the cards stand beside
						except Exception as err:
							print("[NileGlass] dash ctx:", err)
				_Dash = NileGlassDash
			dialog = _session.instantiateDialog(_Dash, name)
			quiet(dialog)
		except Exception as err:
			print("[NileGlass] dash:", err)
			dialog = None
	_dialogs[name] = (dialog, element)
	return dialog


def quiet(dialog):
	"""A hidden card window does no work: enigma2 keeps feeding every widget of
	a hidden window (the clock every second, the channel on every change).
	Here a hidden widget only notes that something changed, and is brought up
	to date once, when its window is shown again."""
	def guard(r, orig):
		def changed(what):
			if r.suspended:
				r._ngStale = True
				return
			orig(what)
		return changed

	for r in list(getattr(dialog, "renderer", [])):
		try:
			r._ngChanged = r.changed
			r._ngStale = False
			r.changed = guard(r, r._ngChanged)
		except Exception:
			pass

	def catchUp():
		for r in list(getattr(dialog, "renderer", [])):
			if getattr(r, "_ngStale", False):
				r._ngStale = False
				try:
					r._ngChanged((r.CHANGED_ALL,))
				except Exception:
					pass
	dialog.onShow.append(catchUp)


def _alive(screen):
	return screen is not None and getattr(screen, "instance", None) is not None and getattr(screen, "shown", False) and getattr(screen, "already_shown", False)


def _tick():
	name = None
	try:
		host = _want
		if _alive(host) and enabled():
			try:
				name = host._ngDashSubject()
			except Exception:
				name = None
			if name not in GROUPS:
				name = "system"
			dialog = _dialog(name)
			marker = getattr(host._ngDashMarker, "instance", None)
			if dialog is None or marker is None:
				name = None
			else:
				from enigma import ePoint, getDesktop
				desk = getDesktop(0).size()
				at = host.instance.position()
				x = at.x() + marker.position().x()
				y = max(20, min(at.y() + marker.position().y(), desk.height() - 20 - DASH_H))
				if x + DASH_W > desk.width():
					name = None
				else:
					now = dialog.instance.position()
					if now.x() != x or now.y() != y:
						dialog.instance.move(ePoint(x, y))
					try:
						if dialog["ctx"].host is not host:
							dialog["ctx"].setHost(host)
					except Exception:
						pass
					dialog.show()
	except Exception as err:
		print("[NileGlass] dash:", err)
		name = None
	for key, (dialog, element) in list(_dialogs.items()):
		if key != name and dialog is not None:
			try:
				dialog.hide()
			except Exception:
				pass


def _start(ms):
	global _timer
	try:
		if _timer is None:
			from enigma import eTimer
			_timer = eTimer()
			_timer.callback.append(_tick)
		_timer.start(ms, True)
	except Exception as err:
		print("[NileGlass] dash:", err)


def request(screen):
	"""cards beside this screen, a moment from now (so the panel itself comes up first)"""
	global _want
	_want = screen
	_start(SHOW_DELAY)


def release(screen):
	global _want
	if _want is screen:
		_want = None
		_start(HIDE_DELAY)      # not at once: the next menu usually wants the same cards


def attach(screen):
	"""End of applySkin of any screen: if its skin has the cards marker (the
	Menu / Setup panels and every screen borrowing them), look after its cards."""
	if getattr(screen, "_ngDashMarker", None) is not None or _session is None:
		return
	marker = _marker(screen)
	if marker is None:
		return
	screen._ngDashMarker = marker
	if not hasattr(screen, "_ngDashSubject"):
		screen._ngDashSubject = lambda: setupSubject(screen)
	screen.onShow.append(lambda: request(screen))
	screen.onHide.append(lambda: release(screen))

	def closed():
		release(screen)
		screen._ngDashMarker = screen._ngDashSubject = None
	screen.onClose.append(closed)


def refresh(screen):
	"""the panel changed size or subject: put the cards where they belong"""
	if _want is screen:
		_start(SHOW_DELAY)


def attachMenu(screen):
	screen._ngDashSubject = lambda: menuSubject(screen)
	try:
		screen["menu"].onSelectionChanged.append(lambda: refresh(screen))
	except Exception:
		pass
