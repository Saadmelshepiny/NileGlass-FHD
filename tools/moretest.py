#!/usr/bin/env python3
"""Cards of their own per screen: watch time per channel, timers (next, conflicts,
room), recordings (.cuts position, size, quality), storage warning, packages
before install.  argv: PYROOT"""
import importlib.util, os, struct, sys, tempfile, time, types
PY = sys.argv[1]
fails = []


def check(name, ok, extra=""):
	print(("PASS " if ok else "FAIL ") + name, "" if ok else extra)
	if not ok:
		fails.append(name)


def load(name, rel):
	spec = importlib.util.spec_from_file_location(name, os.path.join(PY, rel))
	m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
	sys.modules[name] = m
	return m


class Converter:
	CHANGED_DEFAULT, CHANGED_ALL = 0, 2

	def __init__(self, arg):
		self.source = None

	def changed(self, what):
		pass


class Poll:
	def __init__(self):
		pass


for n in ("Components", "Components.Converter", "Components.Sources"):
	sys.modules[n] = types.ModuleType(n)
cm = types.ModuleType("Components.Converter.Converter"); cm.Converter = Converter; sys.modules["Components.Converter.Converter"] = cm
pm = types.ModuleType("Components.Converter.Poll"); pm.Poll = Poll; sys.modules["Components.Converter.Poll"] = pm
el = types.ModuleType("Components.Element"); el.cached = lambda f: f; sys.modules["Components.Element"] = el
core = types.ModuleType("Components.NileGlassCore"); core.confGet = lambda s, k, d="": d; core.callInUiThread = lambda f, *a: f(*a)
core.isLocalMount = lambda p: True
sys.modules["Components.NileGlassCore"] = core
d = tempfile.mkdtemp()

# ---- watch
W = load("Components.NileGlassWatch", "Components/NileGlassWatch.py")
sys.modules["Components"].NileGlassWatch = W
W.FILE = os.path.join(d, "watch.json")
mbc = "1:0:19:3E9:3F8:FFFF:E080000:0:0:0:"
cbc = "1:0:1:100:200:300:E080000:0:0:0:"
now = time.time()
for i in range(90):
	W.add(mbc, 60, crypted=False, now=now)
for i in range(30):
	W.add(cbc, 60, crypted=True, now=now)
W.add(cbc, 60, crypted=True, now=now)
check("channel key ignores the playing details", W.key(mbc) == "19:3E9:3F8:FFFF:E080000")
check("most watched", W.text(mbc, now).startswith("الأكثر مشاهدة #1") and "1 س 30 د" in W.text(mbc, now), W.text(mbc, now))
check("second", "#2" in W.text(cbc, now), W.text(cbc, now))
check("not watched: nothing", W.text("1:0:1:9:9:9:E080000:0:0:0:", now) == "")
check("scrambled channels opened today", W.cryptToday() == 1)
W.add(mbc, 60, now=now - 10 * 86400)
check("only 8 days kept", len(W.load()["days"]) <= 8)
W.save()
check("saved", os.path.isfile(W.FILE))

# ---- storage warning
S = load("NGSysInfo", "Components/Converter/NGSysInfo.py")
S.diskInfo = lambda p: (100, 5) if p == "/" else (100, 50)
check("flash almost full", S.storageWarning("/media/hdd") == "الفلاش 95%")
S.diskInfo = lambda p: (100, 60) if p == "/" else (100, 3)
check("disk almost full", S.storageWarning("/media/hdd") == "الهارد 97%")
S.diskInfo = lambda p: (100, 50)
check("all fine: nothing", S.storageWarning("/media/hdd") == "")

# ---- timers
T = load("NGTimerInfo", "Components/Converter/NGTimerInfo.py")


class Tm:
	def __init__(self, name, b, e, dis=False, jp=False):
		self.name, self.begin, self.end, self.disabled, self.justplay = name, b, e, dis, jp
		self.service_ref = types.SimpleNamespace(getServiceName=lambda: "MBC 2")


now = time.time()
rt = types.SimpleNamespace(timer_list=[Tm("Later", now + 7200, now + 9000), Tm("Off", now + 100, now + 200, dis=True), Tm("Zap", now + 50, now + 60, jp=True),
	Tm("Soon", now + 1500, now + 4200)])
T.recordTimer = lambda: rt
T.recordPath = lambda: d + "/"
T.space = lambda p: (1000e9, 320e9)
sys.modules["Components.TimerSanityCheck"] = types.SimpleNamespace(TimerSanityCheck=lambda lst, t: types.SimpleNamespace(check=lambda: t.name != "Later"))
c = lambda typ: (lambda x: (setattr(x, "source", None), x.getText())[1])(T.NGTimerInfo(typ))
check("next recording", c("NextName") == "Soon" and c("NextIn") == "بعد 25 د", (c("NextName"), c("NextIn")))
check("count skips off and zap timers", c("Count") == "2")
check("conflicts", c("Conflicts") == "1 متعارض", c("Conflicts"))
check("channel and length", c("NextChannel") == "MBC 2" and c("NextLength") == "45 دقيقة")
check("room", c("FreeSpace") == "320 GB فاضي" and c("FreeHours") == "تكفي حوالي 100 ساعة HD", (c("FreeSpace"), c("FreeHours")))
x = T.NGTimerInfo("UsedPercent")
check("used percent", x.getValue() == 68)
rt.timer_list = []
check("no timers", c("NextName") == "مفيش تسجيل جاي" and c("Conflicts") == "مفيش")

# ---- recordings
sys.modules["enigma"] = types.SimpleNamespace(eServiceCenter=None, iServiceInformation=None)
M = load("NGMovieInfo", "Components/Converter/NGMovieInfo.py")
ts = os.path.join(d, "film.ts")
open(ts, "wb").write(b"0" * 2000000)
open(ts + ".cuts", "wb").write(struct.pack(">QI", 90000 * 600, 0) + struct.pack(">QI", 90000 * 2710, 3))
open(ts + ".meta", "w").write("1:0:19:3E9:3F8:FFFF:E080000:0:0:0:\nFilm\n\n1731600000\n")
mv = M.NGMovieInfo("Watched")
mv.source = types.SimpleNamespace(getCurrentService=lambda: types.SimpleNamespace(getPath=lambda: ts))
mv.length = lambda ref: 5520
check("where playback stopped", mv.getText() == "وقفت عند 45:10 من 1:32:00", mv.getText())
mv.type = "Left"
check("time left", mv.getText() == "فاضل 46 د", mv.getText())
check("watched percent", mv.getValue() == 49)
mv.type = "Recorded"
check("recorded date from .meta", mv.getText() == time.strftime("%d/%m/%Y  %H:%M", time.localtime(1731600000)))
mv.type = "Quality"
check("quality from the bitrate", mv.getText().startswith("SD"), mv.getText())
mv.length = lambda ref: 1
check("bitrate high: 4K", mv.getText().startswith("4K"))
os.remove(ts + ".cuts")
mv.type = "Watched"
check("never watched", mv.getText() == "لسه متشافش")

# ---- packages
P = load("Components.NileGlassPlugins", "Components/NileGlassPlugins.py")
P._feedFields.update({"enigma2-plugin-extensions-foo": {"Version": "1.2", "Size": "2000000", "Depends": "python3-requests, enigma2", "Section": "extra", "Description": "Foo player"}})
P._status.update({"enigma2": {"Status": "install ok installed", "Version": "7"}})
P._index = {}
P._freeFlash = lambda: 100 * 1048576
r = P.pkgInfo(types.SimpleNamespace(name="extensions-foo", description=""))
check("package found by its short name", r["name"] == "enigma2-plugin-extensions-foo" and r["pkgversion"] == "1.2", r)
check("download size", r["pkgsize"] == "1.9 MB", r["pkgsize"])
check("new / free / after", r["pkgstate"] == "جديدة" and r["free"] == "100.0 MB" and r["after"].startswith("يفضل حوالي"), r)
check("missing dependencies named", r["depends"].startswith("هتنزل معاها 1") and "python3-requests" in r["depends"], r["depends"])
P._freeFlash = lambda: 1000
r = P.pkgInfo(types.SimpleNamespace(name="extensions-foo", description=""))
check("not enough space", r["after"] == "المساحة مش هتكفي")
print("ALL OK" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
