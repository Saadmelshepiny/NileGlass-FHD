#!/usr/bin/env python3
"""Crash guard: who caused a crash (skin / plugin / enigma2), new logs read once,
two skin crashes in the same version -> offer the previous version (once).  argv: PYROOT"""
import importlib.util, os, sys, tempfile, time, types
fails = []


def check(name, ok, extra=""):
	print(("PASS " if ok else "FAIL ") + name, "" if ok else extra)
	if not ok:
		fails.append(name)


spec = importlib.util.spec_from_file_location("crashguard", os.path.join(sys.argv[1], "Plugins/Extensions/NileGlassSetup/crashguard.py"))
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
HEAD = "OpenBh Enigma2 Crashlog\n\nCrashdate = x\n\nComponent = ePython\n\n"
SKIN = HEAD + """<   12.345> [Skin] ok
<   99.001> Traceback (most recent call last):
<   99.002>   File "/usr/lib/enigma2/python/Components/Renderer/Label.py", line 30, in changed
<   99.003>   File "/usr/lib/enigma2/python/Components/Converter/NGSysInfo.py", line 612, in getText
<   99.004>     return storageWarning(self._hddPath())
<   99.005> AttributeError: 'NGSysInfo' object has no attribute '_hddPath'
<   99.100> [ePyObject] (CallObject(<bound method ...>) failed)
"""
PLUG = HEAD + """Traceback (most recent call last):
  File "/usr/lib/enigma2/python/Screens/Screen.py", line 120, in execBegin
  File "/usr/lib/enigma2/python/Plugins/Extensions/SaadPanel/plugin.py", line 88, in __init__
  File "/usr/lib/enigma2/python/Components/ActionMap.py", line 40, in __init__
KeyError: 'foo'
"""
CORE = HEAD + """Traceback (most recent call last):
  File "/usr/lib/enigma2/python/Screens/InfoBarGenerics.py", line 2000, in zap
TypeError: bad thing
"""
p = C.parse(SKIN)
check("skin crash found", p["blame"] == "NileGlass" and p["error"].startswith("AttributeError") and p["where"].startswith("NGSysInfo.py:612"), p)
p = C.parse(PLUG)
check("plugin crash: the plugin, not enigma2 underneath", p["blame"] == "SaadPanel" and p["error"] == "KeyError: 'foo'", p)
p = C.parse(CORE)
check("enigma2's own", p["blame"] == "enigma2" and "InfoBarGenerics" in p["where"])
check("no traceback: C++", C.parse(HEAD + "segfault\n")["blame"] == "enigma2 (C++)")

d = tempfile.mkdtemp()
C.DIRS = (d,)
C.STATE = os.path.join(d, "state.json")
C.debugDirs = lambda: [d]
open(os.path.join(d, "Enigma2_crash_2026-11-18_10-00-00.log"), "w").write(PLUG)
st, new = C.scan(version="2.9.0")
check("new log read", len(new) == 1 and new[0]["blame"] == "SaadPanel")
st, new = C.scan(st, version="2.9.0")
check("read only once", new == [])
for i, txt in enumerate((SKIN, SKIN)):
	f = os.path.join(d, "Enigma2_crash_2026-11-18_11-0%d-00.log" % i)
	open(f, "w").write(txt)
	os.utime(f, (time.time() + 10 + i, time.time() + 10 + i))
st, new = C.scan(st, version="2.9.0")
check("two skin crashes in this version", len(C.skinCrashes(st, "2.9.0")) == 2 and len(C.skinCrashes(st, "2.8.20")) == 0)
C.save(st)
rows = C.text(C.load())
check("report lines", any("السكين" in r for r in rows) and any("SaadPanel" in r for r in rows), rows)
print("ALL OK" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
