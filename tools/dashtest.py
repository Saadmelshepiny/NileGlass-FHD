#!/usr/bin/env python3
"""Cards beside the menus as windows of their own (dashctx.py): built once,
shown a moment after the panel, moved beside it, hidden when it goes, follow
the menu entry; lite mode / option off: nothing built.  argv: PYROOT"""
import importlib.util, os, sys, types
PY = sys.argv[1]
fails = []


def check(name, ok, extra=""):
	print(("PASS " if ok else "FAIL ") + name, extra if not ok else "")
	if not ok:
		fails.append(name)


class P:
	def __init__(self, x, y): self._x, self._y = x, y
	def x(self): return self._x
	def y(self): return self._y
	def width(self): return self._x
	def height(self): return self._y


class Inst:
	def __init__(self, x=0, y=0): self.p = P(x, y)
	def position(self): return self.p
	def move(self, p): self.p = p
	def size(self): return P(1920, 1080)


class Timer:
	all = []
	def __init__(self): self.callback, self.ms = [], None; Timer.all.append(self)
	def start(self, ms, single): self.ms = ms
	def fire(self):
		if self.ms is not None:
			self.ms = None
			for c in self.callback: c()


enigma = types.ModuleType("enigma")
enigma.eTimer, enigma.ePoint = Timer, P
enigma.getDesktop = lambda n: Inst()
sys.modules["enigma"] = enigma
skin = types.ModuleType("skin")
skin.domScreens = {"NileGlassDash_" + k: object() for k in ("net", "tuner", "av", "system", "option", "time", "image", "emu", "bt")}
sys.modules["skin"] = skin
conf = {("extras", "dash"): True, ("style", "lite"): False}
core = types.ModuleType("Components.NileGlassCore")
core.confBool = lambda s, k, d=True: conf.get((s, k), d)
sys.modules["Components"] = types.ModuleType("Components")
sys.modules["Components.NileGlassCore"] = core


class Screen(dict):
	def __init__(self, session=None):
		self.session, self.shown, self.already_shown, self.instance = session, True, False, Inst(40, 150)
		self.onShow, self.onHide, self.onClose, self.additionalWidgets = [], [], [], []
	def show(self):
		if self.shown and self.already_shown: return
		self.shown = self.already_shown = True
		for f in self.onShow: f()
	def hide(self):
		if not self.shown: return
		self.shown = False
		for f in self.onHide: f()


scr = types.ModuleType("Screens.Screen"); scr.Screen = Screen
sys.modules["Screens"] = types.ModuleType("Screens"); sys.modules["Screens.Screen"] = scr


class Session:
	built, deleted = [], []
	def instantiateDialog(self, cls, *a):
		d = cls(self, *a); d.shown = False; d.already_shown = False; d.instance = Inst(1240, 300); self.built.append(d.skinName); return d
	def deleteDialog(self, d): d.hide(); self.deleted.append(d.skinName)


spec = importlib.util.spec_from_file_location("dashctx", os.path.join(PY, "Plugins/Extensions/NileGlassSetup/dashctx.py"))
dc = importlib.util.module_from_spec(spec); spec.loader.exec_module(dc)


def host(x, marker=True):
	s = Screen()
	if marker:
		w = types.SimpleNamespace(skinAttributes=[("backgroundColor", "transparent"), ("zPosition", "-77")], instance=Inst(x, 0))
		s.additionalWidgets.append(w)
	return s


def tick():
	if dc._timer: dc._timer.fire()


def visible():
	return sorted(k for k, (d, e) in dc._dialogs.items() if d is not None and d.shown)


class MenuList:
	def __init__(self): self.onSelectionChanged, self.cur = [], ("Network", None, "network_setup")
	def getCurrent(self): return self.cur


session = Session()
plain = host(620)
dc.attach(plain)
check("no session yet: nothing attached", not plain.onShow)
dc.setSession(session)

menu = host(620)
menu["menu"] = MenuList(); menu.menuID = "setup"
dc.attachMenu(menu); dc.attach(menu)
check("opening the menu builds nothing", not session.built)
menu.show()
check("panel on screen first, cards not yet", not session.built and dc._timer.ms == dc.SHOW_DELAY)
tick()
check("then the network cards beside the panel", visible() == ["net"] and session.built == ["NileGlassDash_net"])
d = dc._dialogs["net"][0]
check("placed at the marker", (d.instance.position().x(), d.instance.position().y()) == (660, 150), (d.instance.position().x(), d.instance.position().y()))
menu["menu"].cur = ("Tuners", None, "nim_selection")
for f in menu["menu"].onSelectionChanged: f()
check("moving the cursor does not swap at once", visible() == ["net"])
tick()
check("cards follow the entry under the cursor", visible() == ["tuner"])

# a settings screen opens over the menu
setup = host(980); setup.setup = "video"
dc.attach(setup)
menu.hide(); setup.show()
check("cards stay during the change of screen", visible() == ["tuner"])
tick()
check("settings: picture & sound cards", visible() == ["av"])
d = dc._dialogs["av"][0]
check("beside the wider panel", d.instance.position().x() == 1020)
setup.hide()
for f in setup.onClose: f()
menu.already_shown = False; menu.show(); tick()
check("back in the menu: its cards again, nothing rebuilt", visible() == ["tuner"] and len(session.built) == 3, session.built)
menu.hide(); tick()
check("menu closed: no cards left", visible() == [])

# subjects of settings screens
S = lambda **kw: type("X", (), kw)()
check("time settings", dc.setupSubject(types.SimpleNamespace(setup="time", skinName="Setup")) == "time")
check("bluetooth plugin", dc.subject("BluetoothSetupScreen") == "bt")
check("emu", dc.subject("SoftcamSetup") == "emu" and dc.subject("cicam_setup") == "tuner")
check("update", dc.subject("softwareupdate") == "image")
check("timeshift is not time", dc.subject("timeshift") is None)
class ServiceAppSettings: pass
check("plugin settings: their own options", dc.setupSubject(ServiceAppSettings()) == "option")

# a screen without the marker
other = host(0, marker=False); dc.attach(other); other.show(); tick()
check("screens without the marker: untouched", visible() == [] and not other.onShow)

# too low on the screen: kept inside
low = host(620); low.instance = Inst(40, 900); dc.attach(low); low.show(); tick()
d = dc._dialogs["option"][0]
check("kept inside the screen (a settings screen: its own options)", d.instance.position().y() == 1080 - 20 - dc.DASH_H and visible() == ["option"])
low.hide(); tick()

# skin reloaded: rebuilt with the new look
n = len(session.built)
skin.domScreens["NileGlassDash_net"] = object()
menu["menu"].cur = ("Network", None, "network_setup"); menu.already_shown = False; menu.show(); tick()
check("skin reload: the old window is dropped, a new one built", session.deleted == ["NileGlassDash_net"] and len(session.built) == n + 1 and visible() == ["net"])
menu.hide(); tick()

# off / lite
conf[("style", "lite")] = True
menu.already_shown = False; menu.show(); tick()
check("lite mode: no cards", visible() == [])
menu.hide(); tick()
conf[("style", "lite")] = False; conf[("extras", "dash")] = False
menu.already_shown = False; menu.show(); tick()
check("cards off in the settings: none", visible() == [])
menu.hide(); tick(); conf[("extras", "dash")] = True

# idle warm-up after start: windows built hidden, one at a time
for k, (d, e) in list(dc._dialogs.items()):
	dc._dialogs.pop(k)
n = len(session.built)
check("warm-up waits for the box to settle", dc._warm.ms == 20000)
dc._warm.fire()
check("warm-up: one hidden window per step", len(session.built) == n + 1 and visible() == [] and dc._warm.ms == 1500)
for i in range(6): dc._warm.fire()
check("warm-up: all five, then it stops", len(session.built) == n + 5 and dc._warm.ms is None and visible() == [])

# skin without the card windows (another menu look)
skin.domScreens.clear()
n = len(session.built)
menu.already_shown = False; menu.show(); tick()
check("skin without card windows: nothing built, no error", len(session.built) == n and visible() == [])
# hidden card windows do no work, and catch up when shown
class R:
	CHANGED_ALL = 2
	def __init__(self): self.suspended, self.calls = True, []
	def changed(self, what): self.calls.append(what)
win = Screen(); r = R(); win.renderer = [r]
dc.quiet(win)
r.changed((1,)); r.changed((1,))
check("hidden: no work", r.calls == [])
win.shown = False; win.show()
check("shown: brought up to date once", r.calls == [(2,)], r.calls)
r.suspended = False; r.changed((1,))
check("visible: as usual", r.calls == [(2,), (1,)])
print("ALL OK" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
