#!/usr/bin/env python3
"""One clock for the NileGlass converters (Converter/NGPoll.py): converters with
the same interval share a timer, hidden ones are not polled, gone ones are
forgotten, the timer stops when nobody is left.  argv: PYROOT"""
import gc, importlib.util, os, sys, types
fails = []


def check(name, ok, extra=""):
	print(("PASS " if ok else "FAIL ") + name, "" if ok else extra)
	if not ok:
		fails.append(name)


class Timer:
	all = []
	def __init__(self): self.callback, self.running, self.ms = [], False, None; Timer.all.append(self)
	def start(self, ms, single=False): self.running, self.ms = True, ms
	def stop(self): self.running = False
	def fire(self):
		for c in self.callback: c()


sys.modules["enigma"] = types.SimpleNamespace(eTimer=Timer)
spec = importlib.util.spec_from_file_location("NGPoll", os.path.join(sys.argv[1], "Components/Converter/NGPoll.py"))
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)


class Conv(P.NGPoll):
	CHANGED_POLL = 4
	def __init__(self, ms):
		P.NGPoll.__init__(self)
		self.got = 0
		self.poll_interval = ms
		self.poll_enabled = True
	def changed(self, what): self.got += 1


a, b, c = Conv(1000), Conv(1000), Conv(5000)
check("same interval: one timer", len(Timer.all) == 2 and P.stats() == {1000: 2, 5000: 1}, P.stats())
t1 = [t for t in Timer.all if t.ms == 1000][0]
t1.fire()
check("one tick polls both", a.got == 1 and b.got == 1 and c.got == 0)
a.doSuspend(True)
t1.fire()
check("hidden: not polled", a.got == 1 and b.got == 2)
a.doSuspend(False)
check("shown again: polled at once and back on the clock", a.got == 2 and P.stats()[1000] == 2)
a.poll_interval = 5000
check("interval changed: moves to the other clock", P.stats() == {1000: 1, 5000: 2}, P.stats())
b.destroy()
check("last one gone: the timer stops", not t1.running and 1000 not in P.stats())
del c; gc.collect()
check("converters dropped without destroy are forgotten", P.stats() == {5000: 1}, P.stats())
b2 = Conv(1000)
check("timer starts again", t1.running and len(Timer.all) == 2)
# ---- prewarm: the skin's converters and renderers loaded while idle
import xml.etree.ElementTree as ET
el = ET.fromstring('<screen><widget render="NGPosterX" source="x"><convert type="NGFakeConv">A</convert></widget><widget name="y"/></screen>')
sys.modules["skin"] = types.SimpleNamespace(domScreens={"A": (el, "/x/")})
spec = importlib.util.spec_from_file_location("prewarm", os.path.join(sys.argv[1], "Plugins/Extensions/NileGlassSetup/prewarm.py"))
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)
check("modules from the skin", W.skinModules() == ["Components.Converter.NGFakeConv", "Components.Renderer.NGPosterX"], W.skinModules())
busy = [True]
core = types.ModuleType("Components.NileGlassCore"); core.userActive = lambda w=1.2: busy[0]
sys.modules["Components"] = types.ModuleType("Components"); sys.modules["Components.NileGlassCore"] = core
sys.modules.pop("json", None)
W._todo[:] = ["json", "no.such.module"]
W._timer = Timer()
W._step()
check("keys being pressed: nothing loaded, try later", W._todo == ["json", "no.such.module"] and W._timer.ms == 1500)
busy[0] = False
W._step(); W._step()
check("idle: loaded one per step, missing ones skipped", "json" in sys.modules and W._todo == [] and W.done == ["json"], (W._todo, W.done))
print("ALL OK" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
