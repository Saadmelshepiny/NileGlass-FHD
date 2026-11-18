#!/usr/bin/env python3
"""Test of the Tonight service, NGTonight converter and the Tonight screen
with stubbed enigma2 modules.  argv: PYROOT sample_tonight.json"""
import json
import os
import queue
import shutil
import sys
import tempfile
import threading
import time
import types

os.environ["TZ"] = "Africa/Cairo"
time.tzset()
PYROOT, SAMPLE = sys.argv[1], sys.argv[2]
TMP = tempfile.mkdtemp(prefix="ngtonight")
ui = queue.Queue()
tw = types.ModuleType("twisted"); ti = types.ModuleType("twisted.internet")
ti.reactor = types.SimpleNamespace(callFromThread=lambda f, *a: ui.put((f, a))); tw.internet = ti
sys.modules.update({"twisted": tw, "twisted.internet": ti})


def pump(t=2.0, until=None):
	end = time.time() + t
	while time.time() < end:
		try:
			f, a = ui.get(timeout=0.03)
			f(*a)
		except queue.Empty:
			pass
		if until and until():
			return True
	return False


def mod(name, **kw):
	m = types.ModuleType(name); m.__dict__.update(kw); sys.modules[name] = m; return m


class Widget:
	def __init__(self, text=""):
		self.text, self.visible = text, True
		self.instance = types.SimpleNamespace(setPixmapFromFile=lambda p: setattr(self, "file", p), setPixmap=lambda p: setattr(self, "pm", p))

	def setText(self, t): self.text = t
	def getText(self): return self.text
	def show(self): self.visible = True
	def hide(self): self.visible = False
	def setVisible(self, v): self.visible = bool(v)


class ListSrc:
	def __init__(self, lst): self.list, self.idx, self.onSelectionChanged = lst, 0, []
	def setList(self, l): self.list = l; self.idx = 0; [f() for f in self.onSelectionChanged]
	updateList = setList
	def getCurrent(self): return self.list[self.idx] if self.list else None
	def getIndex(self): return self.idx
	def setIndex(self, i): self.idx = i
	def up(self): self.idx = max(0, self.idx - 1); [f() for f in self.onSelectionChanged]
	def down(self): self.idx = min(len(self.list) - 1, self.idx + 1); [f() for f in self.onSelectionChanged]
	pageUp, pageDown = up, down


class Screen(dict):
	def __init__(self, session): self.session = session; self.onLayoutFinish, self.onClose = [], []
	def setTitle(self, t): self.title = t
	def close(self, *a): self.closed = True; [f() for f in self.onClose]


class Converter:
	def __init__(self, arg): pass


class Poll:
	def __init__(self): pass


zapped = []


class Ref:
	isDirectory, isMarker = 1, 2

	def __init__(self, s="", flags=0): self.s, self.flags = s, flags
	def toString(self): return self.s
	def toCompareString(self): return self.s


mod("enigma", eEPGCache=types.SimpleNamespace(getInstance=lambda: types.SimpleNamespace(lookupEventTime=lambda r, t: None)),
	eServiceCenter=types.SimpleNamespace(getInstance=lambda: types.SimpleNamespace(list=lambda r: None)), eServiceReference=Ref)
mod("Components"); mod("Components.Converter"); mod("Components.Sources"); mod("Screens"); mod("Tools")
mod("Components.ActionMap", ActionMap=lambda *a, **k: None)
mod("Components.Label", Label=Widget)
mod("Components.Pixmap", Pixmap=Widget)
mod("Components.Sources.List", List=ListSrc)
mod("Components.Sources.StaticText", StaticText=Widget)
mod("Components.Converter.Converter", Converter=Converter)
mod("Components.Converter.Poll", Poll=Poll)
mod("Components.Converter.NGPoll", NGPoll=Poll)
mod("Components.Element", cached=lambda f: f)
mod("Screens.ChoiceBox", ChoiceBox=object); mod("Screens.MessageBox", MessageBox=types.SimpleNamespace(TYPE_ERROR=3, TYPE_INFO=1))
mod("Screens.Screen", Screen=Screen)
mod("Tools.LoadPixmap", LoadPixmap=lambda p, cached=False: "PM:" + p)
mod("ServiceReference", ServiceReference=lambda s: types.SimpleNamespace(getServiceName=lambda: {"1:0:19:65:3E8:7E:C00000:0:0:0:": "MBC 2\x86"}.get(s, "")))
mod("NavigationInstance", instance=types.SimpleNamespace(getCurrentlyPlayingServiceReference=lambda: Ref("1:0:19:65:3E8:7E:C00000:0:0:0:")))

src = open(os.path.join(PYROOT, "Components/NileGlassCore.py"), encoding="utf-8").read()
conf = os.path.join(TMP, "nileglass.conf")
tfile = os.path.join(TMP, "tonight.json")
open(conf, "w").write("[tmdb]\napi_key =\n[tonight]\nfile = %s\n" % tfile)
src = src.replace('CONF_FILE = "/etc/enigma2/nileglass.conf"', "CONF_FILE = %r" % conf)
core = mod("Components.NileGlassCore"); core.__file__ = "x"
exec(compile(src, "NileGlassCore.py", "exec"), core.__dict__)

ok = True


def check(c, msg):
	global ok
	print(("PASS " if c else "FAIL ") + msg)
	ok = ok and c


# sample shifted so that "now" is the generation time of the file
data = json.load(open(SAMPLE, encoding="utf-8"))
shift = int(time.time()) - data["generated"]
for x in data["films"] + data["matches"]:
	x["start"] += shift; x["stop"] += shift
data["generated"] += shift
# a poster file on "disk" and a match in the near future on the playing channel
os.makedirs(os.path.join(TMP, "posters"))
pp = os.path.join(TMP, "posters", "p.jpg"); open(pp, "wb").write(b"\xff\xd8x" + b"\x01" * 2048 + b"\xff\xd9")
for f in data["films"]:
	if f["poster"]:
		f["poster"] = pp
data["films"].append({"id": "fx", "title": "فتاتي الجديد", "start": int(time.time()) + 1800, "stop": int(time.time()) + 7000, "channels": [{"sref": "1:0:19:65:3E8:7E:C00000:0:0:0:", "name": "x"}], "fav": False})
open(tfile + ".tmp", "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False)); os.replace(tfile + ".tmp", tfile)

T = core.tonight
check(T.status()["found"] is False, "nothing loaded before first refresh")
T.refresh(force=True)
end = time.time() + 3
while time.time() < end and not T.films:
	time.sleep(0.02)
st = T.status()
check(st["found"] and st["films"] > 30 and st["matches"] == 40, "file read in background: %r" % st)
check(not any(f["title"] in ("Arabic Movie", "Movie") for f in T.films), "generic titles dropped")
keys = [(f["title"], f["start"] // 300) for f in T.films]
check(len(keys) == len(set(keys)) and any(len(f["channels"]) > 1 for f in T.films), "no duplicate films; multi-channel films kept together")
check(not any("LIVE" in (m["comp"] + m["title"]) for m in T.matches), "' - LIVE' removed")
check(threading.current_thread() is threading.main_thread(), "test runs on main thread")

# unchanged file is not parsed again
T.films[0]["_mark"] = 1
T.refresh(force=True); time.sleep(0.3)
check(T.films[0].get("_mark") == 1, "unchanged file not re-read")

# converter
spec = __import__("importlib.util").util.spec_from_file_location("Components.Converter.NGTonight", os.path.join(PYROOT, "Components/Converter/NGTonight.py"))
cm = __import__("importlib.util").util.module_from_spec(spec); sys.modules["Components.Converter.NGTonight"] = cm; spec.loader.exec_module(cm)
soon = cm.NGTonight("Soon").text
svc = cm.NGTonight("Service").text
print("     soon:", soon); print("     service:", svc)
check(soon.startswith(("بعد قليل", "الآن")), "Soon text")
check(svc.startswith("الليلة") and "فتاتي الجديد" in svc and "MBC 2" in svc and "\x86" not in svc, "Service text uses the receiver's channel name")

# screen
spec = __import__("importlib.util").util.spec_from_file_location("tonightscreen", os.path.join(PYROOT, "Plugins/Extensions/NileGlassSetup/tonight.py"))
sm = __import__("importlib.util").util.module_from_spec(spec); spec.loader.exec_module(sm)
sm.PICON_DIRS = (os.path.join(TMP, "picon"),)
os.makedirs(sm.PICON_DIRS[0]); open(os.path.join(sm.PICON_DIRS[0], "1_0_19_65_3E8_7E_C00000_0_0_0.png"), "wb").write(b"png")
played = []
session = types.SimpleNamespace(nav=types.SimpleNamespace(playService=lambda r: played.append(r.s)), open=lambda *a, **k: None, openWithCallback=lambda *a, **k: None)
s = sm.NileGlassTonight(session)
for f in s.onLayoutFinish:
	f()
rows = s["list"].list
check(len(rows) == len(T.items("film")) and s["tab_films_line"].visible and not s["tab_matches_line"].visible, "films tab filled (%d rows)" % len(rows))
check("أفلام الليلة" in s["tab_films"].text and "الماتشات" in s["tab_matches"].text, "tab titles: %s | %s" % (s["tab_films"].text, s["tab_matches"].text))
idx = next(i for i, r in enumerate(rows) if r[5]["poster"])
s["list"].setIndex(idx); s.selectionChanged()
pump(until=lambda: getattr(s["poster"], "file", None))
check(getattr(s["poster"], "file", "") == pp and s["poster"].visible, "poster from the plugin's disk path")
pump(1.0, until=lambda: any(r[4] for r in s["list"].list))
check(any(r[4] for r in s["list"].list), "picon loaded in the list")
print("     row:", s["list"].list[idx][:4])
s.toggleKind()
check(s["tab_matches_line"].visible and s["list"].list and s["list"].list[0][5]["kind"] == "match", "yellow switches to matches")
print("     match:", s["list"].list[0][:4], "|", s["versus"].text.replace("\n", " "), "|", s["info"].text)
s.toggleFav()
check(s["key_blue"].text == "الكل", "blue: favourites only")
s.toggleFav(); s.toggleKind()
s.zap()
check(played and played[0] == s["list"].getCurrent()[5]["channels"][0]["sref"] and getattr(s, "closed", False), "OK zaps to the channel")

# file removed -> empty state
os.remove(tfile)
T.refresh(force=True)
pump(1.0, until=lambda: not T.films)
check(not T.films and T.status()["found"] is False, "missing file clears the data")
s2 = sm.NileGlassTonight(session)
for f in s2.onLayoutFinish:
	f()
check("مش موجود" in s2["empty"].text, "empty-state message")

shutil.rmtree(TMP, ignore_errors=True)
print("ALL OK" if ok else "SOME TESTS FAILED")
