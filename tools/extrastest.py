#!/usr/bin/env python3
"""2.6 extras: codec, play end, hijri, radio screen, cast.  argv: PYROOT"""
import importlib.util, os, sys, time, types
PY = sys.argv[1]
ok = True
def check(c, msg):
	global ok; print(("PASS " if c else "FAIL ") + msg); ok = ok and c
class Timer:
	def __init__(self): self.callback = []; self.active = False
	def start(self, ms, single=False): self.active = True
	def stop(self): self.active = False
	def isActive(self): return self.active
	def fire(self): [f() for f in self.callback]
class IPS: evStart, evEnd, evUpdatedInfo, evVideoSizeChanged = 1, 2, 3, 4
class ISI: sVideoType, sVideoHeight, sProgressive, sFrameRate, sTagBitrate, sTagNominalBitrate, sAudioBitrate, sTagChannelMode, sServiceref = 1, 2, 3, 4, 20, 21, 22, 23, 24
e = types.ModuleType("enigma"); e.eTimer = Timer; e.iPlayableService = IPS; e.iServiceInformation = ISI; sys.modules["enigma"] = e
for n in ("Components", "Components.Converter", "Screens", "Tools"): sys.modules[n] = types.ModuleType(n)
class Converter:
	CHANGED_SPECIFIC, CHANGED_ALL, CHANGED_CLEAR = 3, 2, 1
	def __init__(self, arg): pass
	def changed(self, what): pass
class Poll:
	def __init__(self): pass
m = types.ModuleType("Components.Converter.Converter"); m.Converter = Converter; sys.modules[m.__name__] = m
m = types.ModuleType("Components.Converter.Poll"); m.Poll = Poll; sys.modules[m.__name__] = m
m = types.ModuleType("Components.Converter.NGPoll"); m.NGPoll = Poll; sys.modules[m.__name__] = m
m = types.ModuleType("Components.Element"); m.cached = lambda f: f; sys.modules[m.__name__] = m
CONF = {("extras", "hijri"): "1", ("extras", "hijri_offset"): "0", ("extras", "radio"): "1", ("extras", "cast"): "1", ("style", "lite"): "0"}
core = types.ModuleType("Components.NileGlassCore")
core.confGet = lambda s, k, d="": CONF.get((s, k), d)
core.confBool = lambda s, k, d=True: CONF.get((s, k), "1" if d else "0") in ("1",)
core.liteMode = lambda: core.confBool("style", "lite", False)
sys.modules[core.__name__] = core
def load(rel, name):
	spec = importlib.util.spec_from_file_location(name, os.path.join(PY, rel)); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

# ---- codec
cod = load("Components/Converter/NGCodec.py", "NGCodec")
class Info:
	def __init__(self, v): self.v = v
	def getInfo(self, w): return self.v.get(w, -1)
class Track:
	def __init__(self, d): self.d = d
	def getDescription(self): return self.d
class Audio:
	def __init__(self, d): self.d = d
	def getNumberOfTracks(self): return 1
	def getCurrentTrack(self): return 0
	def getTrackInfo(self, i): return Track(self.d)
class Svc:
	def __init__(self, v, a): self.i = Info(v); self.a = a
	def info(self): return self.i
	def audioTracks(self): return Audio(self.a) if self.a else None
def text(mode, svc):
	c = cod.NGCodec(mode); c.source = types.SimpleNamespace(service=svc); return c.getText()
s1 = Svc({1: 7, 2: 1080, 3: 1, 4: 50000}, "Dolby Digital +")
check(text("Full", s1) == "1080p50 · HEVC · DD+", "full: " + text("Full", s1))
check(text("Resolution", Svc({2: 576, 3: 0, 4: 25000}, "")) == "576i25", "SD interlaced")
check(text("Codecs", Svc({1: 1}, "AAC")) == "H.264 · AAC", "codecs")
check(text("Full", Svc({}, None)) == "", "nothing known -> empty, no error")
check(text("Full", None) == "", "no service -> empty")

# ---- play end
pe = load("Components/Converter/NGPlayEnd.py", "NGPlayEnd")
seek = types.SimpleNamespace(getLength=lambda: (0, 90000 * 3600), getPlayPosition=lambda: (0, 90000 * 600))
c = pe.NGPlayEnd(""); c.source = types.SimpleNamespace(service=types.SimpleNamespace(seek=lambda: seek))
want = time.strftime("%H:%M", time.localtime(time.time() + 3000))
check(c.getText() == "ينتهي " + want, "film ends at now + remaining: " + c.getText())
c2 = pe.NGPlayEnd(""); c2.source = types.SimpleNamespace(service=types.SimpleNamespace(seek=lambda: None))
check(c2.getText() == "", "live TV: nothing")

# ---- hijri
hj = load("Components/Converter/NGHijri.py", "NGHijri")
check(hj.toHijri(2025, 3, 1) == (1446, 9, 1), "1 Ramadan 1446 = 1 Mar 2025")
check(hj.toHijri(2026, 3, 20) == (1447, 10, 1), "Eid al-Fitr 1447 = 20 Mar 2026")
h = hj.NGHijri("Append"); h.source = types.SimpleNamespace(text="الأربعاء 11 نوفمبر")
check(h.getText().startswith("الأربعاء 11 نوفمبر · ") and "هـ" not in h.getText(), "append: " + h.getText())
CONF[("extras", "hijri")] = "0"
check(h.getText() == "الأربعاء 11 نوفمبر", "hijri off: date only")
h2 = hj.NGHijri(""); h2.source = types.SimpleNamespace(time=None)
check(h2.getText() == "", "hijri off: standalone empty")
CONF[("extras", "hijri")] = "1"; CONF[("extras", "hijri_offset")] = "1"
y, m_, d = hj.toHijri(*time.localtime(time.time() + 86400)[:3])
check(h2.getText().startswith("%d " % d), "offset +1 day")
CONF[("extras", "hijri_offset")] = "0"

# ---- next line
nl = load("Components/Converter/NGNextLine.py", "NGNextLine")
c = nl.NGNextLine(""); c.source = types.SimpleNamespace(event=types.SimpleNamespace(getEventName=lambda: "نشرة", getBeginTime=lambda: 0))
check(c.getText() == "التالي   نشرة", "next line: " + c.getText())
c.source = types.SimpleNamespace(event=None)
check(c.getText() == "", "no next programme: empty (no lone label)")

# ---- date names
dt = load("Components/Converter/NGDate.py", "NGDate")
t0 = time.mktime((2026, 11, 11, 23, 34, 0, 0, 0, -1))
check(dt.formatDate("{A} {d} {B}", t0) == "الأربعاء 11 نوفمبر", "full Arabic day and month: " + dt.formatDate("{A} {d} {B}", t0))
c = dt.NGDate("{A} {H}:{M}"); c.source = types.SimpleNamespace(time=t0)
check(c.getText() == "الأربعاء 23:34", "day + time")

# ---- stream details
sys.modules["Components.Converter.NGCodec"] = cod
si = load("Components/Converter/NGStreamInfo.py", "NGStreamInfo")
class SInfo:
	def __init__(self, ref, v, sv): self.ref = ref; self.v = v; self.sv = sv
	def getInfo(self, w): return self.v.get(w, -1)
	def getInfoString(self, w): return self.ref if w == ISI.sServiceref else self.sv.get(w, "")
def sinfo(mode, ref, v=None, sv=None, audio="MPEG-1 Layer 3 (MP3)"):
	c = si.NGStreamInfo(mode)
	svc = Svc({}, audio); svc.i = SInfo(ref, v or {}, sv or {})
	c.source = types.SimpleNamespace(service=svc); return c
web = "4097:0:2:0:0:0:0:0:0:0:https%3a//stream.zeno.fm/abc:Radio"
check(sinfo("Audio", web, {ISI.sTagBitrate: 128000}, {ISI.sTagChannelMode: "stereo"}).getText() == "MP3 · 128 kb/s · Stereo", "audio line")
check(sinfo("Quality", web, {ISI.sTagBitrate: 128000}).getText() == "جودة جيدة", "quality word")
check(sinfo("Audio", "1:0:19:1:1:1:0:0:0:0:").getText() == "", "satellite channel: nothing")
dev = [1000000]
si._rxBytes = lambda: dev[0]
n = sinfo("Net", web); n.getText(); n.last = (n.last[0] - 2, n.last[1]); dev[0] += 500000
check(n.getText() == "2.0 Mb/s", "internet speed: " + n.getText())
vc = types.SimpleNamespace(getInstance=lambda: types.SimpleNamespace(isMuted=lambda: False, getVolume=lambda: 55))
sys.modules["enigma"].eDVBVolumecontrol = vc
check(sinfo("Volume", web).getText() == "55%", "volume")

# ---- cast
class Lab:
	def __init__(self, t=""): self.t = t
	def setText(self, t): self.t = t
class CPix:
	def __init__(self): self.vis = True; self.instance = types.SimpleNamespace(setPixmapFromFile=lambda p: None)
	def hide(self): self.vis = False
	def show(self): self.vis = True
m = types.ModuleType("Components.Label"); m.Label = Lab; sys.modules[m.__name__] = m
m = types.ModuleType("Components.Pixmap"); m.Pixmap = CPix; sys.modules[m.__name__] = m
reqs = []
core.posters = types.SimpleNamespace(request=lambda n, cb, kind="poster": reqs.append((n, cb, kind)), personImage=lambda p: "/tmp/" + p)
core.callInUiThread = lambda f, *a: f(*a)
core.log = lambda *a: None
core.noFilmEvent = lambda ev, src=None: ev.getEventName().startswith("Match")
class EVB(dict):
	def __init__(self, event, ref):
		self.instance = None; self.event = event
	def setEvent(self, event): self.event = event
m = types.ModuleType("Screens.EventView"); m.EventViewBase = EVB; sys.modules[m.__name__] = m
ch = load("Plugins/Extensions/NileGlassSetup/casthook.py", "casthook")
ch.install(); ch.install()
ev = lambda n: types.SimpleNamespace(getEventName=lambda: n)
v = EVB(None, None); v.instance = object()
check("cast_p4" in v and "cast_n0" in v and "cast_title" in v, "cast slots added to the INFO screen")
v.setEvent(ev("الممر"))
check(len(reqs) == 1 and reqs[0][2] == "details", "film: details asked once")
import threading
reqs[0][1]("الممر", {"details": {"people": [("أحمد عز", "x", "/a.jpg"), ("هند صبري", "", "")]}})
for t in threading.enumerate():
	if t.name == "NileGlass-cast": t.join(2)
check(v["cast_n0"].t == "أحمد عز" and v["cast_n1"].t == "هند صبري" and v["cast_n2"].t == "" and v["cast_title"].t == "الأبطال", "names shown")
v.setEvent(ev("Match: Ahly - Zamalek"))
check(len(reqs) == 1 and v["cast_n0"].t == "", "match: no cast, cleared")
reqs[0][1]("الممر", {"details": {"people": [("Late", "", "")]}})
check(v["cast_n0"].t == "", "late answer for an old programme is ignored")
CONF[("extras", "cast")] = "0"; v.setEvent(ev("فيلم آخر"))
check(len(reqs) == 1, "off in the settings: nothing asked")
print("ALL OK" if ok else "SOME TESTS FAILED")
