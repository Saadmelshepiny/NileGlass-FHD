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
# ---- settings screen beside the cards
H = load("NGHostInfo", "Components/Converter/NGHostInfo.py")


class Sel:
	def __init__(self, choices, value, default):
		self.choices = types.SimpleNamespace(choices=choices)
		self.value, self.default = value, default
		self.description = dict(choices)


class YesNo:
	value, default = True, True


cfg = types.SimpleNamespace(list=[("IPTV player", Sel([("gst", "gstplayer"), ("ext", "exteplayer3")], "ext", "gst")), ("Autostart", YesNo())], onSelectionChanged=[])
cfg.getCurrent = lambda: cfg.list[0]
class ServiceAppSettings(dict): pass
ServiceAppSettings.__module__ = "Plugins.SystemPlugins.ServiceApp.plugin"
host = ServiceAppSettings(config=cfg)
src = types.SimpleNamespace(host=host)
h = lambda typ: (lambda x: (setattr(x, "source", src), x.getText())[1])(H.NGHostInfo(typ))
check("option under the cursor", h("Item") == "IPTV player" and h("Value") == "exteplayer3", (h("Item"), h("Value")))
check("default", h("Default") == "gstplayer")
check("choices", h("Choices") == "gstplayer · exteplayer3")
check("count and changed", h("Total") == "2" and h("Changed") == "1")
check("plugin of the screen", h("Owner") == "ServiceApp" and H.owner(host)[1].endswith("SystemPlugins/ServiceApp"))
cfg.getCurrent = lambda: cfg.list[1]
check("yes/no option", h("Value") == "نعم" and h("Choices") == "نعم · لأ" and h("Default") == "نعم  (زي ما هو)", (h("Value"), h("Choices"), h("Default")))
check("follows the cursor", len(cfg.onSelectionChanged) >= 1)

# ---- context values
C = load("NGContext", "Components/Converter/NGContext.py")
cv = lambda typ: (lambda x: x.getText())(C.NGContext(typ))
check("utc time", len(cv("Utc")) == 8 and cv("Offset").startswith("UTC"))
check("python version", cv("Python") == "%d.%d.%d" % sys.version_info[:3])
check("other cities", cv("City1").startswith("مكة"), cv("City1"))
check("sync source text", "القمر" in cv("Sync") or "NTP" in cv("Sync"))
C.EMU_DIRS = (d,)
open(os.path.join(d, "oscam"), "w").write("#!/bin/sh\n"); os.chmod(os.path.join(d, "oscam"), 0o755)
open(os.path.join(d, "ncam.sh"), "w").write("x")
check("emus installed", cv("EmuInstalled") == "oscam" and cv("EmuCount") == "1", cv("EmuInstalled"))
C.btAdapter = lambda: None
check("no bluetooth", cv("BtAdapter") == "مفيش بلوتوث على الجهاز" and cv("BtCount") == "—")

# ---- skin under the cursor
K = load("NGSkinInfo", "Components/Converter/NGSkinInfo.py")
sk = os.path.join(d, "MySkin"); os.makedirs(sk)
open(os.path.join(sk, "skin.xml"), "w").write('<?xml version="1.0"?>\n<!-- My Skin by Ahmed, version 1.4 -->\n<skin><colors><color name="background" value="#00102030"/><color name="foreground" value="#ffffff"/><color name="x1" value="#123456"/></colors><fonts><font filename="Roboto-Bold.ttf" name="Regular"/></fonts><screen name="A"/><screen name="B"/></skin>')
K.ROOT = d
ks = types.SimpleNamespace(getCurrent=lambda: ("MYSKIN", "MySkin", "", "MySkin", "skin.xml", "1920x1080", "2 MB", ""), onSelectionChanged=[])
k = lambda typ: (lambda x: (setattr(x, "source", ks), x.getText())[1])(K.NGSkinInfo(typ))
check("skin facts", k("Name") == "MySkin" and k("Screens") == "2" and k("Fonts") == "Roboto-Bold", (k("Screens"), k("Fonts")))
check("skin header", k("Author").startswith("Ahmed") and k("Version") == "1.4", (k("Author"), k("Version")))
check("skin colours", k("Color1") == "#102030" and k("Color2") == "#ffffff" and k("Color3") == "#123456" and k("Color4") == "", (k("Color1"), k("Color2"), k("Color3")))
# ---- subtitle state from the subtitle plugin
SB = load("NGSubs", "Components/Converter/NGSubs.py")
SB.FILE = os.path.join(d, "subs.json")
cur = "1:0:19:3E9:3F8:FFFF:E080000:0:0:0:"
SB.playingRef = lambda: cur
def put(**kw):
	import json as _j
	time.sleep(0.01)
	open(SB.FILE, "w").write(_j.dumps(dict({"lang": "ar", "source": "dl.subdl.com", "offset": 0.0, "ref": cur, "title": "X", "updated": 1}, **kw)))
	os.utime(SB.FILE, (time.time() + len(str(kw)), time.time() + len(str(kw)) + put.n)); put.n += 1
put.n = 1
show = lambda: {k: SB.NGSubs(k).getText() for k in ("Ok", "Busy", "None", "Bad") if SB.NGSubs(k).getText()}
put(state="searching")
check("searching", show() == {"Busy": "بيدوّر ترجمة"}, show())
put(state="on", sync="adjusting")
check("adjusting", show() == {"Busy": "بتتظبط…"}, show())
put(state="on", sync="exact")
check("on and in sync", show() == {"Ok": "ترجمة عربي"}, show())
put(state="on", sync="exact", offset=1.5, ref=cur)
check("recording with a manual offset", show() == {"Ok": "ترجمة +1.5ث"}, show())
put(state="on", sync="exact", source="live")
check("live", show() == {"Ok": "ترجمة مباشرة"}, show())
put(state="none")
check("nothing found", show() == {"None": "مفيش ترجمة"}, show())
put(state="idle", ref="")
check("idle: nothing shown", show() == {})
put(state="on", sync="exact", ref="1:0:19:1:1:1:E080000:0:0:0:")
check("another channel: nothing shown", show() == {})
os.remove(SB.FILE)
check("no file: nothing", show() == {})
print("ALL OK" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
