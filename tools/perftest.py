#!/usr/bin/env python3
"""perfwatch: key / skin timing and the report.  argv: PYROOT"""
import importlib.util, os, sys, tempfile, time, types
PY = sys.argv[1]
class Timer:
	def __init__(self): self.callback = []; self.active = False
	def start(self, ms, single=False): self.active = True
	def fire(self): self.active = False; [f() for f in self.callback]
bound = []
e = types.ModuleType("enigma"); e.eTimer = Timer
e.eActionMap = types.SimpleNamespace(getInstance=lambda: types.SimpleNamespace(bindAction=lambda ctx, prio, fn: bound.append(fn)))
sys.modules["enigma"] = e
class Screen:
	def applySkin(self): time.sleep(self.cost)
sys.modules["Screens"] = types.ModuleType("Screens"); ms_ = types.ModuleType("Screens.Screen"); ms_.Screen = Screen; sys.modules["Screens.Screen"] = ms_
spec = importlib.util.spec_from_file_location("pw", os.path.join(PY, "Plugins/Extensions/NileGlassSetup/perfwatch.py"))
pw = importlib.util.module_from_spec(spec); spec.loader.exec_module(pw)
pw.LOG = os.path.join(tempfile.mkdtemp(), "perf.log")
ok = True
def check(c, m):
	global ok; print(("PASS " if c else "FAIL ") + m); ok = ok and c
class Plugin(Screen):
	def __init__(self, cost, sn): self.cost, self.skinName = cost, sn
greenpanel = Plugin(0, ["DeliteGreenPanel"])
session = types.SimpleNamespace(current_dialog=greenpanel)
pw.install(session); pw.install(session)
check(len(bound) == 1, "one key hook")
check(bound[0]("KEY_OK", 0) == 0, "key is never eaten")
time.sleep(0.2)
opened = Plugin(0.06, ["CCcamInfoMain"]); session.current_dialog = opened
opened.applySkin()
pw.watcher.timer.fire()
fast = Plugin(0.001, ["Fast"]); fast.applySkin()
bound[0]("KEY_UP", 0); pw.watcher.timer.fire()   # fast key: not logged
log = open(pw.LOG).read()
print(log)
check("skin" in log and "CCcamInfoMain" in log and "Fast" not in log.split("skin")[-1], "slow skin drawing logged, fast not")
check("key " in log and "Plugin/DeliteGreenPanel Plugin/CCcamInfoMain" in log, "slow key logged with the screen it opened")
check(log.count("key ") == 1, "fast key not logged")
r = pw.report()
print(r)
_p = r.split("وقت تجهيز الشاشات")
check(len(_p) == 2 and "CCcamInfoMain" in _p[0] and "CCcamInfoMain" in _p[1], "report: both tables")

# stalls: who used the processor
open(pw.LOG, "a").write("10:00:00 stall 2000 InfoBar LiveOnSatDB:1800,GUI:120\n10:00:05 stall 900 MainHome LiveOnSatDB:700,PoolThread-twisted:150\n10:00:09 stall 700 MainHome GUI:650\n")
r = pw.report()
sec = r.split("مين كان شاغل المعالج")[1].split("\n\n")[0] if "مين كان شاغل المعالج" in r else ""
check("LiveOnSatDB                  x2" in sec and "GUI                          x1" in sec, "report: the busiest thread per stall\n" + sec)
check(pw.threadGroup("PoolThread-twisted.internet.reactor-3") == "PoolThread-twisted" and pw.threadGroup("Thread-12 (fetch)") == "Thread", "thread groups")
t = pw.threadTicks()
check("GUI" in t and t["GUI"] >= 0, "processor time per thread: %r" % t)

# the processor readings never run on the GUI thread
import threading as _th, time as _tm
calls = []
real = pw.threadTicks
pw.threadTicks = lambda: (calls.append(_th.current_thread() is _th.main_thread()), {"GUI": len(calls) * 10, "LiveOnSatDB": len(calls) * 90})[1]
s = pw.Sampler()
_tm.sleep(2.3)
s.stop = True
check(calls and not any(calls), "readings only in the sampler thread: %r" % calls)
used = s.used(_tm.monotonic() - 1.5)
check(used and used[0][1] == "LiveOnSatDB" and used[0][0] > used[1][0], "sampler: who used the processor %r" % used)
pw.threadTicks = real

# where the GUI code was during a stall: sampled from the sampler thread
fake = {"t": _tm.monotonic()}
s2 = pw.Sampler(lambda: fake["t"])
src = "def busy():\n\timport time\n\tt = time.monotonic()\n\twhile time.monotonic() - t < 1.2:\n\t\tsum(range(2000))\n"
ns = {}
exec(compile(src, "/usr/lib/enigma2/python/Plugins/Extensions/SlowPlug/plugin.py", "exec"), ns)
t0 = _tm.monotonic()
ns["busy"]()                       # the "GUI" (main thread) is stuck here, no heartbeat
t1 = _tm.monotonic()
s2.stop = True
w = s2.whereIn(t0, t1)
check(w.startswith("SlowPlug/plugin.py:"), "stall code: the plugin and line %r" % w)
check(s2.whereIn(t1 + 5, t1 + 6) == "-", "no samples outside a stall")
check(pw.codeWhere(None) == "C++", "no Python on the stack -> C++")
open(pw.LOG, "a").write("10:01:00 stall 2400 InfoBar GUI:2300 SlowPlug/plugin.py:5<Screen.py:300\n10:01:09 stall 800 InfoBar GUI:700 C++\n")
r = pw.report()
check("الواجهة كانت بتعمل إيه" in r and "SlowPlug/plugin.py:5<Screen.py:300" in r and "C++" in r, "report: the code during stalls")
print("ALL OK" if ok else "SOME TESTS FAILED")
