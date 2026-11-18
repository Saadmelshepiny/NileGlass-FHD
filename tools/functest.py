#!/usr/bin/env python3
"""Functional test of the NileGlass Python parts with stubbed enigma2 modules.

Network is simulated (no real TMDB/Open-Meteo access).  Checks:
  * posters: local hit, download, negative cache, title mismatch rejection,
    callbacks arrive on the "UI thread" (our fake reactor), stale callbacks ignored
  * NGPoster renderer show/hide logic and debounce
  * NGEventList, NGSysInfo, NGWeather converters
"""
import json
import os
import queue
import shutil
import sys
import tempfile
import threading
import time
import types

PYROOT = sys.argv[1]  # build/root/usr/lib/enigma2/python
TMP = tempfile.mkdtemp(prefix="ngtest")

# ------------------------------------------------------------ stubs
uiQueue = queue.Queue()
reactor = types.SimpleNamespace(callFromThread=lambda f, *a: uiQueue.put((f, a)))
twisted = types.ModuleType("twisted"); internet = types.ModuleType("twisted.internet")
internet.reactor = reactor; twisted.internet = internet
sys.modules.update({"twisted": twisted, "twisted.internet": internet})


def pumpUI(timeout=3.0, until=None):
	end = time.time() + timeout
	while time.time() < end:
		try:
			f, a = uiQueue.get(timeout=0.05)
			f(*a)
		except queue.Empty:
			pass
		if until and until():
			return True
	return bool(until and until())


class eTimer:
	def __init__(self):
		self.callback = []
		self.active = False

	def start(self, ms, single=False):
		self.active = True
		self.ms = ms

	def stop(self):
		self.active = False

	def fire(self):
		self.active = False
		for c in self.callback:
			c()


class Widget:
	def __init__(self, parent=None):
		self.visible = True
		self.file = None
		self.text = ""

	def hide(self): self.visible = False
	def show(self): self.visible = True
	def setPixmapScale(self, f): pass
	def setPixmapFromFile(self, p): self.file = p
	def setPixmap(self, p): self.file = p
	def setText(self, t): self.text = t


class eServiceReference:
	isGroup = 4

	def __init__(self, s="1:0:19:B91:4B0:2:0:0:0:0:"):
		self.s = s
		self.flags = 0

	isDirectory, isMarker = 1, 2

	def valid(self): return True
	def toString(self): return self.s


class FakeEPG:
	@staticmethod
	def getInstance(): return FakeEPG()

	def lookupEvent(self, q):
		now = int(time.time())
		return [(now - 600, 3600, "فيلم السهرة"), (now + 3000, 1800, "نشرة الأخبار"), (now + 4800, 5400, "Inception")]


enigma = types.ModuleType("enigma")
enigma.eTimer = eTimer
enigma.ePixmap = Widget
enigma.eLabel = Widget
enigma.eServiceReference = eServiceReference
enigma.eEPGCache = FakeEPG
enigma.eServiceCenter = types.SimpleNamespace(getInstance=lambda: types.SimpleNamespace(info=lambda r: types.SimpleNamespace(getName=lambda ref: CHANNEL["name"])))
CHANNEL = {"name": "MBC 2"}
for n in ("BT_SCALE", "BT_KEEP_ASPECT_RATIO", "BT_HALIGN_CENTER", "BT_VALIGN_CENTER"):
	setattr(enigma, n, 1)
sys.modules["enigma"] = enigma


class Element:
	CHANGED_DEFAULT, CHANGED_ALL, CHANGED_CLEAR, CHANGED_SPECIFIC, CHANGED_POLL = 0, 1, 2, 3, 4

	def __init__(self):
		self.source = None
		self.skinAttributes = []


def cached(f):
	return f


class Renderer(Element):
	def __init__(self):
		Element.__init__(self)
		self.instance = None
		self.suspended = False

	def applySkin(self, desktop, parent):
		return True

	def create(self):
		self.instance = self.GUI_WIDGET(None)
		self.postWidgetCreate(self.instance)

	def postWidgetCreate(self, i): pass
	def onShow(self): self.suspended = False


class Converter(Element):
	def __init__(self, arg):
		Element.__init__(self)

	def changed(self, what): pass
	def destroy(self): pass


class Poll:
	def __init__(self):
		self.poll_interval = 1000
		self.poll_enabled = False


class VariableText:
	def __init__(self):
		self.text = ""


def mod(name, **kw):
	m = types.ModuleType(name)
	m.__dict__.update(kw)
	sys.modules[name] = m
	return m


mod("Components")
mod("Components.Element", Element=Element, cached=cached)
mod("Components.Renderer")
mod("Components.Renderer.Renderer", Renderer=Renderer)
mod("Components.Converter")
mod("Components.Converter.Converter", Converter=Converter)
mod("Components.Converter.Poll", Poll=Poll)
mod("Components.Converter.NGPoll", NGPoll=Poll)
mod("Components.VariableText", VariableText=VariableText)
mod("skin", parseColor=lambda v: types.SimpleNamespace(argb=lambda: int(v.lstrip("#"), 16)))
mod("Tools")
mod("Tools.Hex2strColor", Hex2strColor=lambda c: "\\c%08x" % c)
mod("Tools.Directories", SCOPE_CURRENT_SKIN=5, resolveFilename=lambda s, p: "/skin/" + p)
mod("Tools.LoadPixmap", LoadPixmap=lambda p, cached=False: p)
mod("Components.SystemInfo", getBoxDisplayName=lambda: ("Vu+", "Ultimo4K"), BoxInfo=types.SimpleNamespace(getItem=lambda k, d="": {"displaydistro": "OpenBh", "imgversion": "5.6"}.get(k, d)))

# ------------------------------------------------------------ load NileGlassCore with test config
import importlib.util  # noqa: E402

src = open(os.path.join(PYROOT, "Components/NileGlassCore.py"), encoding="utf-8").read()
conf = os.path.join(TMP, "nileglass.conf")
src = src.replace('CONF_FILE = "/etc/enigma2/nileglass.conf"', 'CONF_FILE = %r' % conf)
src = src.replace('MOUNTS = ("/media/hdd",', 'MOUNTS = (%r,' % os.path.join(TMP, "hdd"))
os.makedirs(os.path.join(TMP, "hdd/xtraEvent/poster"))
with open(os.path.join(TMP, "hdd/xtraEvent/poster/الممر.jpg"), "wb") as f:
	f.write(b"\xff\xd8localposter" + b"\x00" * 2048 + b"\xff\xd9")
open(conf, "w").write("[tmdb]\napi_key = TESTKEY123\n[posters]\ncache_dir = %s\n" % os.path.join(TMP, "cache"))
core = types.ModuleType("Components.NileGlassCore")
core.__file__ = "NileGlassCore.py"
sys.modules["Components.NileGlassCore"] = core
exec(compile(src, "NileGlassCore.py", "exec"), core.__dict__)
core.isLocalMount = lambda p: True  # tmp dir counts as local disk for the test

calls = []


def fakeHttp(url, headers=None, timeout=8, maxBytes=0):
	calls.append(url)
	threadName = threading.current_thread().name
	assert threadName.startswith("NileGlass"), "network on UI thread! %s" % threadName
	if "search/multi" in url and "The+Last+Hunt" in url:
		return json.dumps({"results": [{"media_type": "movie", "id": 555, "title": "The Last Hunt", "poster_path": "/lh.jpg", "popularity": 10, "release_date": "1956-02-29"}]}).encode()
	if "search/multi" in url:
		if "Inception" in url:
			return json.dumps({"results": [{"media_type": "movie", "id": 27205, "title": "Inception", "poster_path": "/inc.jpg", "backdrop_path": "/incb.jpg", "popularity": 80,
				"vote_average": 8.37, "vote_count": 30000, "genre_ids": [28, 878], "release_date": "2010-07-15", "overview": "قصة"}]}).encode()
		if "%D8%A7%D9%84%D9%83%D9%86%D8%B2" in url:  # الكنز
			return json.dumps({"results": [{"media_type": "movie", "id": 77, "title": "The Treasure", "poster_path": "/t.jpg", "popularity": 5, "release_date": "2017-08-30"}]}).encode()
		if "Wrong" in url:
			return json.dumps({"results": [{"media_type": "movie", "title": "Something else entirely", "poster_path": "/x.jpg"}]}).encode()
		return json.dumps({"results": []}).encode()
	if "/movie/27205?" in url:
		return json.dumps({"credits": {"crew": [{"job": "Director", "name": "Christopher Nolan"}], "cast": [{"name": "Leonardo DiCaprio"}, {"name": "Elliot Page"}, {"name": "Tom Hardy"}]},
			"production_countries": [{"name": "United States of America"}], "runtime": 148}).encode()
	if "/configuration?" in url:
		return b"{}"
	if "/movie/77?" in url:
		return json.dumps({"translations": {"translations": [{"data": {"title": "الكنز"}}]}, "alternative_titles": {"titles": []}}).encode()
	if url.endswith("/films.json.gz"):
		import gzip as _gz
		return _gz.compress(json.dumps({"films": [{"title": "الصيد الأخير", "en": "The Last Hunt"}, {"title": "بدون", "en": ""}]}).encode())
	if url.endswith("/tr_ar.json.gz"):
		return json.dumps({"Hollywood Weapons S3 EP4 - Seg1": "أسلحة هوليوود S3 EP4 - Seg1", "Tech Now": "التقنية الآن", "Same": "Same"}).encode()
	if "/movie/555?" in url:
		return json.dumps({"title": "الصيد الأخير", "overview": "وصف عربي"}).encode()
	if "image.tmdb.org" in url:
		time.sleep(0.2)
		return b"\xff\xd8downloaded" + b"\x01" * 2048 + b"\xff\xd9"
	if "open-meteo" in url and "geocoding" in url:
		return json.dumps({"results": [{"latitude": 30.04, "longitude": 31.24, "name": "القاهرة"}]}).encode()
	if "open-meteo" in url:
		return json.dumps({"current": {"temperature_2m": 22.4, "weather_code": 2, "is_day": 0, "relative_humidity_2m": 40, "wind_speed_10m": 11},
			"daily": {"temperature_2m_max": [27.0], "temperature_2m_min": [16.2]}}).encode()
	raise IOError("unexpected url " + url)


realHttpGet = core.httpGet
core.httpGet = fakeHttp
P = core.posters
results = {}


def cb(title, path):
	assert threading.current_thread() is threading.main_thread(), "callback not on UI thread"
	results[title] = path


ok = True


def check(cond, msg):
	global ok
	print(("PASS " if cond else "FAIL ") + msg)
	ok = ok and cond


# 1. local poster from another plugin's folder
P.request("فيلم: الممر", cb)
pumpUI(until=lambda: "الممر" in results)
check(results.get("الممر", "").endswith("xtraEvent/poster/الممر.jpg"), "reuses poster from xtraEvent folder")
check(not any("themoviedb" in c for c in calls), "no network for local poster")

# 2. download
P.request("Inception (2010)", cb)
pumpUI(until=lambda: "Inception" in results)
check(results.get("Inception") and os.path.isfile(results["Inception"]) and "cache" in results["Inception"], "downloads + caches new poster")
n = len(calls)
results.clear()
P.request("Inception", cb)
pumpUI(until=lambda: "Inception" in results)
check(len(calls) == n and results.get("Inception"), "second request served from cache")

# 3. wrong match rejected + negative cache
P.request("Wrong Title Here", cb)
pumpUI(until=lambda: "Wrong Title Here" in results)
check(results.get("Wrong Title Here", "x") is None, "non-matching TMDB result rejected")
n = len(calls)
results.pop("Wrong Title Here")
P.request("Wrong Title Here", cb)
pumpUI(until=lambda: "Wrong Title Here" in results)
check(len(calls) == n, "negative cache prevents repeated lookups")

# 3b. metadata + backdrop from the same search
n = len(calls)
meta = {}
P.request("Inception", lambda t, v: meta.update({"m": v}), kind="meta")
pumpUI(until=lambda: "m" in meta)
check(meta.get("m") and meta["m"]["year"] == 2010 and meta["m"]["rating"] == 8.4 and len(calls) == n, "metadata cached without extra requests: %s" % core.formatInfo(meta.get("m")))
P.request("Inception", lambda t, v: meta.update({"b": v}), kind="backdrop")
pumpUI(until=lambda: "b" in meta)
check(meta.get("b") and "backdrop" in meta["b"] and any("w1280" in c for c in calls), "backdrop downloaded on demand")
# 3b2. details (director, cast, country) only on demand
P.request("Inception", lambda t, v: meta.update({"d": v}), kind="details")
pumpUI(until=lambda: "d" in meta)
d = (meta.get("d") or {}).get("details") or {}
check(d.get("director") == "Christopher Nolan" and len(d.get("cast", [])) == 3 and d.get("runtime") == 148, "details: " + core.formatCard(meta.get("d")).replace("\n", " | "))
n = len(calls)
meta.pop("d")
P.request("Inception", lambda t, v: meta.update({"d": v}), kind="details")
pumpUI(until=lambda: "d" in meta)
check(len(calls) == n, "details cached")
# prefetch queue runs only when idle and never on the UI thread
before = P.stats["prefetched"]
P.prefetch(["Inception", "فيلم الكنز", "Some Unknown Film 1", "Some Unknown Film 2", "نشرة الأخبار"])
end = time.time() + 8
while time.time() < end and P.prefetchQueue:
	pumpUI(0.2)
check(not P.prefetchQueue and P.stats["prefetched"] >= before + 2, "prefetch processed in background: %s" % P.stats)
st = P.status()
check(st["posters"] >= 2 and st["cache"], "status: %d posters, %d backdrops" % (st["posters"], st["backdrops"]))
kt = {}
th = threading.Thread(target=lambda: kt.update(r=P.testKey()), name="NileGlass-diag"); th.start(); th.join()
check(kt["r"][0], "key test (from the diagnostics thread)")

# 3c. Arabic title found through TMDB translations
P.request("فيلم الكنز", cb)
pumpUI(until=lambda: "الكنز" in results)
check(results.get("الكنز"), "Arabic title matched via translations")

# 4. skipped titles
check(P.request("نشرة الأخبار", cb) == "", "news is skipped without any work")

# 5. renderer
spec = importlib.util.spec_from_file_location("Components.Renderer.NGPoster", os.path.join(PYROOT, "Components/Renderer/NGPoster.py"))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
r = m.NGPoster()
ev = {"name": "Inception"}
r.source = types.SimpleNamespace(event=types.SimpleNamespace(getEventName=lambda: ev["name"]))
r.skinAttributes = [("delay", "200")]
r.create(); r.applySkin(None, None)
check(r.timer.active, "debounce timer armed")
r.timer.fire()
pumpUI(until=lambda: r.instance.visible)
check(r.instance.visible and r.instance.file and r.instance.file.endswith(".jpg"), "renderer shows poster")
ev["name"] = "نشرة الأخبار"
r.changed((r.CHANGED_ALL,)); r.timer.fire()
check(not r.instance.visible, "renderer hides for news")
# stale callback: request Inception, change to something else before it arrives
ev["name"] = "Inception"; r.changed((r.CHANGED_ALL,)); r.timer.fire()
ev["name"] = "Unknown Film XYZ"; r.changed((r.CHANGED_ALL,)); r.timer.fire()
pumpUI(1.5)
check(not r.instance.visible, "stale poster not shown after switching event")

# context: no film poster for sport (genre 4, match names, sport channels)
class G:
	def __init__(self, l1): self.l1 = l1
	def getLevel1(self): return self.l1
sp = {"genre": None}
r.source = types.SimpleNamespace(event=types.SimpleNamespace(getEventName=lambda: ev["name"], getGenreData=lambda: sp["genre"]))
ev["name"] = "Inception"; r.changed((r.CHANGED_ALL,)); r.timer.fire()
pumpUI(until=lambda: r.instance.visible)
check(r.instance.visible, "film poster with genre data present")
ev["name"] = "Real Madrid vs Barcelona"; r.changed((r.CHANGED_ALL,))
check(not r.instance.visible and not r.timer.active, "match by name: no poster, no lookup")
ev["name"] = "Inception"; sp["genre"] = G(4); r.changed((r.CHANGED_ALL,))
check(not r.instance.visible, "DVB sport genre: no poster")
sp["genre"] = None; CHANNEL["name"] = "beIN SPORTS 1 HD"; r.wantedName = None; r.changed((r.CHANGED_ALL,))
check(not r.instance.visible, "sport channel: no poster")
CHANNEL["name"] = "MBC 2"; P.skipSport = False; r.wantedName = None; ev["name"] = "Real Madrid vs Barcelona"; r.changed((r.CHANGED_ALL,))
check(r.timer.active, "smart sport off: looks up as before")
P.skipSport = True; r.timer.stop()
check(core.isSportTitle("Manchester United - Aston Villa") and not core.isSportTitle("Sex and the City - Part 2") and core.isSportTitle("الأهلي × الزمالك - مباشر") and core.isSportTitle("الدوري المصري") and not core.isSportTitle("الممر") and not core.isSportTitle("Mission: Impossible"), "sport title detection (ar/en)")
check(not core.isSportEvent(types.SimpleNamespace(getGenreData=lambda: None, getEventName=lambda: "Inception"), "beIN MOVIES"), "beIN Movies is not sport")

# urgent prefetch goes to the head of the queue, sport skipped
P.prefetchQueue.clear()
P.prefetchQueue.extend(["Old 1", "Old 2"])
n = P.prefetch(["Next Film", "Barca vs Real", "Prev Film", "Old 2"], urgent=True)
check(n == 3 and list(P.prefetchQueue)[:3] == ["Next Film", "Prev Film", "Old 2"] and list(P.prefetchQueue).count("Old 2") == 1, "urgent prefetch order: %r" % list(P.prefetchQueue))
P.prefetchQueue.clear()

# circuit breaker: 3 network failures block the host for a while
import urllib.error
calls = []
real = core._httpGet
def failing(url, *a, **k):
	calls.append(url); raise urllib.error.URLError("timeout")
core._httpGet = failing
for i in range(5):
	try:
		realHttpGet("https://down.example.com/x%d" % i)
	except Exception:
		pass
check(len(calls) == 3 and core.hostBlocked("https://down.example.com/y"), "breaker opens after 3 failures (%d calls)" % len(calls))
check(not core.hostBlocked("https://api.themoviedb.org/3"), "other hosts unaffected")
core._httpGet = real
core._breaker.clear()

# neighbours: the 2 channels above and below are queued after the pause
spec = importlib.util.spec_from_file_location("ngneighbours", os.path.join(PYROOT, "Plugins/Extensions/NileGlassSetup/neighbours.py"))
nb = importlib.util.module_from_spec(spec); spec.loader.exec_module(nb)
refs = [eServiceReference("ch%d" % i) for i in range(8)]
refs[2].flags = eServiceReference.isMarker
class FakeList:
	def __init__(self): self.cb = []; self.idx = 4; self.calls = 0
	def connectSelChanged(self, f): self.cb.append(f)
	def getList(self): self.calls += 1; return refs
	def getCurrentIndex(self): return self.idx
csel = types.SimpleNamespace(servicelist=FakeList(), onShown=[], execing=True, getRoot=lambda: eServiceReference("bouquet"))
class NbEPG:
	@staticmethod
	def getInstance(): return NbEPG()
	def lookupEventTime(self, ref, t): return types.SimpleNamespace(getEventName=lambda: "Film " + ref.s)
nb.eEPGCache = NbEPG
nb.attach(csel)
P.prefetchQueue.clear()
csel.servicelist.cb[0]()
check(csel._ngNeighbours.timer.active and csel._ngNeighbours.timer.ms == 600, "neighbour prefetch debounced")
qsave = P.prefetchQueue
P.prefetchQueue = __import__("collections").deque(maxlen=600)
csel._ngNeighbours.timer.fire()
check(list(P.prefetchQueue) == ["ch5", "ch3", "ch6"], "neighbours queued, marker skipped: %r" % list(P.prefetchQueue))
csel.servicelist.idx = 5; csel.servicelist.cb[0](); csel._ngNeighbours.timer.fire()
check(csel.servicelist.calls == 1, "bouquet list read once per bouquet")
P.prefetchQueue = qsave

# media player source (no .event)
r2 = m.NGPoster()
r2.source = types.SimpleNamespace(service=types.SimpleNamespace(info=lambda: types.SimpleNamespace(getName=lambda: "Inception")))
r2.skinAttributes = [("delay", "0")]
r2.create(); r2.applySkin(None, None)
pumpUI(until=lambda: r2.instance.visible)
check(r2.instance.visible, "poster from playing file name (movie player)")

# "coming up" poster: no EPG work while the list moves, one shared lookup
epgCalls = {"n": 0}
_orig = FakeEPG.lookupEvent
def counting(self, q):
	epgCalls["n"] += 1
	return _orig(self, q)
FakeEPG.lookupEvent = counting
core._upcoming.clear()
thumbs = []
for i in (1, 2, 3, 4):
	t = m.NGPoster(); t.source = types.SimpleNamespace(service=eServiceReference())
	t.skinAttributes = [("eventIndex", str(i)), ("delay", "500"), ("kind", "thumb")]
	t.create(); t.applySkin(None, None); thumbs.append(t)
for _ in range(10):   # ten fast key presses
	for t in thumbs:
		t.changed((t.CHANGED_ALL,))
check(epgCalls["n"] == 0 and all(t.timer.active for t in thumbs), "fast scrolling: no EPG lookups (%d)" % epgCalls["n"])
for t in thumbs:
	t.timer.fire()
check(epgCalls["n"] == 1, "4 upcoming posters share one EPG lookup (%d)" % epgCalls["n"])
check(thumbs[1].wantedName == "Inception" and thumbs[0].wantedName == "نشرة الأخبار" and thumbs[2].wantedName == "", "right event per poster: %r" % [t.wantedName for t in thumbs])
FakeEPG.lookupEvent = _orig

# decoded posters are reused: back and forth in a list decodes each file once
decodes = []
sys.modules["Tools.LoadPixmap"].LoadPixmap = lambda p, cached=False: decodes.append(p) or ("PM", p)
m._pix.clear()
fb = os.path.join(TMP, "fb.png"); open(fb, "wb").write(b"x")
w1 = m.NGPoster(); w1.source = types.SimpleNamespace(event=None); w1.skinAttributes = []; w1.create(); w1.applySkin(None, None)
for _ in range(5):
	w1.shownPath = None; w1.setPicture(fb)
check(decodes.count(fb) == 1 and w1.instance.file == ("PM", fb), "same picture decoded once (%d)" % decodes.count(fb))
os.utime(fb, (time.time() + 5, time.time() + 5)); w1.shownPath = None; w1.setPicture(fb)
check(decodes.count(fb) == 2, "changed file decoded again")
sys.modules["Tools.LoadPixmap"].LoadPixmap = lambda p, cached=False: p
m._pix.clear()

# translation of descriptions (titles are never translated)
T_ = core.translator
check(not T_.needs("الممر فيلم حربي عن حرب أكتوبر") and T_.needs("Kobieta (Amy Adams) porzuca karierę artystki") and not T_.needs("Short"), "only non-Arabic, real texts are translated")
trCalls = []
def fakeTr(url, **k):
	trCalls.append(url)
	return json.dumps([[["امرأة (إيمي آدمز) تترك ", "Kobieta ...", None], ["مسيرتها الفنية.", "x", None]], None, "pl"]).encode()
core.httpGet = fakeTr
src_ = types.SimpleNamespace(text="Kobieta (Amy Adams) porzuca karierę artystki.")
spec = importlib.util.spec_from_file_location("Components.Converter.NGTranslate", os.path.join(PYROOT, "Components/Converter/NGTranslate.py"))
trm = importlib.util.module_from_spec(spec); sys.modules[spec.name] = trm; spec.loader.exec_module(trm)
c = trm.NGTranslate(""); c.source = src_
refreshed = []
trm.Converter.changed = lambda self, what: refreshed.append(what)
check(c.getText() == src_.text and c.timer.active and not trCalls, "original shown first, no request while the list moves")
src_.text = "Another programme text in English here."; c.getText()
c.timer.fire()   # text changed meanwhile? the newest one is asked
pumpUI(until=lambda: refreshed)
check(len(trCalls) == 1 and refreshed, "one request after the text settles, screen refreshed")
check(c.getText() == "امرأة (إيمي آدمز) تترك مسيرتها الفنية.", "translated text shown: %s" % c.getText())
trCalls.clear()
c2 = trm.NGTranslate(""); c2.source = types.SimpleNamespace(text=src_.text)
check(c2.getText().startswith("امرأة") and not c2.timer.active and not trCalls, "known translation shown at once, no new request")
T_.mem.clear()
check(T_.cached(src_.text).startswith("امرأة"), "translation kept on disk")
core.httpGet = fakeHttp

# 6. event list
spec = importlib.util.spec_from_file_location("NGEventList", os.path.join(PYROOT, "Components/Renderer/NGEventList.py"))
el = importlib.util.module_from_spec(spec); spec.loader.exec_module(el)
e = el.NGEventList(); e.skinAttributes = [("items", "5"), ("timeColor", "#2f9cff")]; e.applySkin(None, None)
e.source = types.SimpleNamespace(serviceref=eServiceReference())
e.changed((e.CHANGED_ALL,))
lines = e.text.split("\n")
check(len(lines) == 2 and "نشرة الأخبار" in lines[0] and "Inception" in lines[1], "event list skips running event: %r" % lines)

# 7. sysinfo
spec = importlib.util.spec_from_file_location("NGSysInfo", os.path.join(PYROOT, "Components/Converter/NGSysInfo.py"))
si = importlib.util.module_from_spec(spec); spec.loader.exec_module(si)
vals = {t: si.NGSysInfo(t).text for t in ("CpuLoad", "RamPercent", "RamUsed", "FlashFree", "Uptime", "IP", "BoxName", "Image", "CpuTemp")}
print("     sysinfo:", vals)
check(vals["BoxName"] == "Vu+ Ultimo4K" and vals["RamPercent"].endswith("%"), "sysinfo text values")
check(0 <= si.NGSysInfo("RamPercent").value <= 100, "sysinfo progress value")

# 8. weather
spec = importlib.util.spec_from_file_location("NGWeather", os.path.join(PYROOT, "Components/Converter/NGWeather.py"))
wm = importlib.util.module_from_spec(spec); spec.loader.exec_module(wm)
w = wm.NGWeather("temp")
w.text
end = time.time() + 3
while time.time() < end and not core.weather.state.get("temp"):
	time.sleep(0.05)
check(wm.NGWeather("temp").text == "22°C" and wm.NGWeather("icon").text == "partly_night", "weather: %s %s %s" % (core.weather.state.get("temp"), core.weather.state.get("desc"), core.weather.state.get("city")))

# 9. SaadEPG English titles
T9 = core.epgTitles
end = time.time() + 3
while time.time() < end and not T9.map:
	time.sleep(0.05)
check(T9.map.get(T9.key("الصيد الأخير")) == "The Last Hunt", "epg title map from films.json")
check(T9.map.get(T9.key("التقنية الآن")) == "Tech Now", "epg title map from tr_ar.json")
check(T9.lookup("أسلحة هوليوود S3 EP4 - Seg1") in (None, "Hollywood Weapons"), "episode noise stripped: %r" % T9.lookup("أسلحة هوليوود S3 EP4 - Seg1"))
check(os.path.isfile(T9._path()), "title map saved to disk")
results.clear()
P.request("فيلم: الصيد الأخير", cb, kind="meta")
pumpUI(until=lambda: "الصيد الأخير" in results)
mm = results.get("الصيد الأخير") or {}
check(mm.get("id") == 555 and mm.get("overview") == "وصف عربي" and mm.get("name") == "الصيد الأخير", "poster found through English EPG title: %r" % mm)
check(P.status()["stats"].get("epg") == 1, "epg match counted")

shutil.rmtree(TMP, ignore_errors=True)
print("ALL OK" if ok else "SOME TESTS FAILED")
sys.exit(0 if ok else 1)
