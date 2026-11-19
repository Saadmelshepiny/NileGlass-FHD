# -*- coding: utf-8 -*-
# NileGlass FHD - how fast does the box answer the remote, and how much of
# that is the skin?
#
#  key   every key press is timed from the moment it arrives until enigma2 is
#        idle again; slow ones (> KEY_SLOW ms) are logged with the screen the
#        key was pressed on and the screen that is open afterwards.
#  skin  the time spent drawing a screen with the skin (Screen.applySkin) is
#        measured separately; slow ones (> SKIN_SLOW ms) are logged.  So a
#        slow opening can be told apart: plugin work, or skin drawing.
#  stall a light heartbeat (every 250 ms) notices when the box did nothing at
#        all for a while - then keys wait, or seem lost.
# The log is /tmp/nileglass_perf.log.

import os
import time

from enigma import eActionMap, eTimer

LOG = "/tmp/nileglass_perf.log"
KEY_SLOW = 150      # ms
SKIN_SLOW = 40      # ms
MAX_LOG = 200000    # bytes


def write(line):
	try:
		if os.path.exists(LOG) and os.path.getsize(LOG) > MAX_LOG:
			os.replace(LOG, LOG + ".old")
		with open(LOG, "a") as f:
			f.write("%s %s\n" % (time.strftime("%H:%M:%S"), line))
	except Exception:
		pass


def screenName(screen):
	if screen is None:
		return "?"
	sn = getattr(screen, "skinName", None)
	if isinstance(sn, (list, tuple)):
		sn = sn[0] if sn else None
	cls = screen.__class__.__name__
	return cls if not sn or sn == cls else "%s/%s" % (cls, sn)


try:
	from Components.NileGlassCore import keyPressed
except Exception:
	keyPressed = None

STALL = 300         # ms: the box did nothing else for this long (no key, no drawing)
TICK = 250
try:
	HZ = os.sysconf("SC_CLK_TCK")
except Exception:
	HZ = 100


SAMPLER = "NileGlass-PerfSampler"


def threadTicks():
	"""CPU time used so far by every Python thread, by name (the GUI itself is "GUI").
	Reads one /proc file per thread: never call it on the GUI thread (every read
	gives the interpreter away and the GUI waits to get it back) - the sampler
	thread below does it once a second."""
	import threading
	out = {}
	for t in threading.enumerate():
		if t.name == SAMPLER:
			continue
		tid = getattr(t, "native_id", None)
		if not tid:
			continue
		try:
			with open("/proc/self/task/%d/stat" % tid) as f:
				parts = f.read().rsplit(")", 1)[1].split()
			ticks = int(parts[11]) + int(parts[12])
		except Exception:
			continue
		name = "GUI" if t is threading.main_thread() else threadGroup(t.name)
		out[name] = out.get(name, 0) + ticks
	return out


def threadGroup(name):
	"""PoolThread-twisted.internet.reactor-3 -> PoolThread-twisted; Thread-12 (fetch) -> Thread"""
	import re
	name = re.sub(r"\s*\(.*\)$", "", name or "?")
	name = re.sub(r"[-_ ]?\d+$", "", name)
	return name.replace(".internet.reactor", "").replace(" ", "_")[:24] or "?"


class Sampler:
	"""background thread: processor time per thread, once a second, last 10 s kept"""
	def __init__(self):
		import collections
		import threading
		self.samples = collections.deque(maxlen=12)       # (monotonic time, {name: ticks})
		self.stop = False
		th = threading.Thread(target=self.run, name=SAMPLER)
		th.daemon = True
		th.start()

	def run(self):
		while not self.stop:
			try:
				self.samples.append((time.monotonic(), threadTicks()))
			except Exception:
				pass
			time.sleep(1.0)

	def used(self, since):
		"""processor time per thread from the last sample before 'since' to the newest"""
		s = list(self.samples)
		if len(s) < 2:
			return []
		base = s[0]
		for sample in s:
			if sample[0] <= since:
				base = sample
		new = s[-1]
		if new is base:
			return []
		return sorted(((new[1][n] - base[1].get(n, new[1][n]), n) for n in new[1]), reverse=True)


class PerfWatch:
	def __init__(self, session):
		self.session = session
		self.t0 = None
		self.screen = ""
		self.timer = eTimer()
		self.timer.callback.append(self.done)
		eActionMap.getInstance().bindAction("", -0x7FFFFFFF, self.key)
		# heartbeat: a timer that should fire every TICK ms; when it comes late the
		# box was busy (a screen, a plugin, a background job) and keys had to wait
		self.beat = eTimer()
		self.beat.callback.append(self.heartbeat)
		self.last = time.monotonic()
		self.sampler = Sampler()
		self.stalls = []                   # (start, late, screen): named once the sampler has seen past them
		self.beat.start(TICK, False)

	def heartbeat(self):
		now = time.monotonic()
		late = int((now - self.last) * 1000) - TICK
		self.last = now
		if late >= STALL:
			self.stalls.append((now - (late + TICK) / 1000.0, now, late, screenName(getattr(self.session, "current_dialog", None))))
		# a stall is written a little later, when the sampler has a reading from after it:
		# who used the processor while the box did not answer - the GUI itself or a background thread?
		while self.stalls:
			start, end, ms, screen = self.stalls[0]
			latest = self.sampler.samples[-1][0] if self.sampler.samples else 0
			if latest < end and now - end < 4:
				break
			self.stalls.pop(0)
			try:
				used = self.sampler.used(start)
			except Exception:
				used = []
			top = ",".join("%s:%d" % (n, d * 1000 // HZ) for d, n in used[:3] if d > 0)
			write("stall %d %s %s" % (ms, screen, top or "-"))

	def key(self, key, flag):
		if flag in (0, 2) and keyPressed is not None:
			keyPressed()                         # background work waits a moment (NileGlassCore.waitQuiet)
		if key == 401 and flag == 3:             # blue held: is the long press reaching the box?
			write("bluelong %s" % screenName(getattr(self.session, "current_dialog", None)))
		if flag in (0, 2) and self.t0 is None:   # make / repeat
			self.t0 = time.monotonic()
			self.screen = screenName(getattr(self.session, "current_dialog", None))
			self.timer.start(0, True)            # runs when the key is fully handled
		return 0                                 # never eat the key

	def done(self):
		if self.t0 is None:
			return
		ms = int((time.monotonic() - self.t0) * 1000)
		self.t0 = None
		if ms >= KEY_SLOW:
			now = screenName(getattr(self.session, "current_dialog", None))
			write("key %d %s %s" % (ms, self.screen, now))


def patchSkinTiming():
	from Screens.Screen import Screen
	if getattr(Screen, "_ngTimed", False):
		return
	original = Screen.applySkin

	def applySkin(self, *args, **kwargs):
		t0 = time.monotonic()
		try:
			return original(self, *args, **kwargs)
		finally:
			ms = int((time.monotonic() - t0) * 1000)
			if ms >= SKIN_SLOW:
				write("skin %d %s" % (ms, screenName(self)))
	Screen.applySkin = applySkin
	Screen._ngTimed = True


watcher = None


def install(session):
	global watcher
	if watcher is None:
		try:
			if os.path.exists(LOG):          # a fresh log for every start
				os.replace(LOG, LOG + ".old")
			watcher = PerfWatch(session)
			patchSkinTiming()
		except Exception as err:
			print("[NileGlass] perf watch:", err)


def report():
	"""Summary: slow key presses by the screen they opened, and skin drawing
	time per screen. Numbers first on every line so the text reads well in
	Arabic and English alike."""
	try:
		lines = open(LOG).read().splitlines()
	except Exception:
		return "مفيش حاجة بطيئة متسجلة لسه.\nاستخدم الجهاز شوية وافتح التقرير تاني."
	keys, skins, guards, fits, blues, exts, stalls, culprits = {}, {}, [], [], [], [], {}, {}
	for line in lines:
		p = line.split()
		try:
			if p[1] == "fit":
				fits.append("   " + " ".join(p[2:]))
				continue
			if p[1] == "bluelong":
				blues.append(p[2] if len(p) > 2 else "?")
				continue
			if p[1] == "extensions":
				exts.append(" ".join(p[2:]))
				continue
			if p[1] == "guard":
				guards.append("   %s  %s  (فوقها: %s)" % (p[0], p[3], p[4]))
				continue
			if p[1] == "stall":
				ms, name = int(p[2]), p[3]
				s = stalls.setdefault(name, [0, 0, 0])
				s[0] += 1
				s[1] += ms
				s[2] = max(s[2], ms)
				first = True
				for item in (p[4].split(",") if len(p) > 4 and p[4] != "-" else []):
					who, _, cpu = item.rpartition(":")
					if not who or not cpu.isdigit():
						continue
					c = culprits.setdefault(who, [0, 0])
					c[1] += int(cpu)
					if first:
						c[0] += 1          # the biggest user in this stall
						first = False
				continue
			if p[1] == "key":
				ms, frm, to = int(p[2]), p[3], p[4]
				name = to if to != frm else frm
				s = keys.setdefault(name, [0, 0, 0])
			elif p[1] == "skin":
				ms, name = int(p[2]), p[3]
				s = skins.setdefault(name, [0, 0, 0])
			else:
				continue
		except (IndexError, ValueError):
			continue
		s[0] += 1
		s[1] += ms
		s[2] = max(s[2], ms)

	def table(d):
		# Latin first on every row (screen name, then the numbers): no Arabic on
		# these lines, so the text direction can't shuffle them
		rows = sorted(d.items(), key=lambda kv: -kv[1][2])[:8]
		return ["   %-28s %5d ms   x%d" % (name[:28], worst, n) for name, (n, _t, worst) in rows]

	out = ["الضغطات البطيئة (أبطأ من %d ms) والشاشة اللي ظهرت بعدها:" % KEY_SLOW]
	out += table(keys) or ["   مفيش ضغطات بطيئة"]
	out += ["", "مرات الجهاز وقف فيها عن الاستجابة (أكتر من %d ms) والشاشة المفتوحة:" % STALL]
	if stalls:
		rows = sorted(stalls.items(), key=lambda kv: -kv[1][0])[:8]
		out += ["   %-28s %5d ms   x%d" % (name[:28], v[2], v[0]) for name, v in rows]
		if culprits:
			out += ["", "مين كان شاغل المعالج وقت الوقفات (GUI = الشاشة نفسها):"]
			out += ["   %-28s x%-4d %6d ms" % (who[:28], c[0], c[1]) for who, c in sorted(culprits.items(), key=lambda kv: (-kv[1][0], -kv[1][1]))[:8]]
	else:
		out += ["   مفيش، الجهاز كان بيرد على طول"]
	out += ["", "الذاكرة والشغل في الخلفية:"]
	try:
		rss = [l for l in open("/proc/self/status").read().splitlines() if l.startswith("VmRSS")][0].split()[1]
		out.append("   ذاكرة الواجهة: %d MB" % (int(rss) // 1024))
	except Exception:
		pass
	try:
		import threading
		groups = {}
		for t in threading.enumerate():
			if t is not threading.main_thread():
				g = threadGroup(t.name)
				groups[g] = groups.get(g, 0) + 1
		out.append("   شغل في الخلفية: %d" % (threading.active_count() - 1))
		out += ["   %-28s x%d" % (g[:28], n) for g, n in sorted(groups.items(), key=lambda kv: -kv[1])[:10]]
		from Components.Converter.NGPoll import stats
		s = stats()
		out.append("   قراءات دورية: %s" % ("، ".join("%d كل %g ث" % (n, i / 1000.0) for i, n in sorted(s.items())) or "مفيش"))
	except Exception:
		pass
	try:
		from .crashguard import load, text
		out += ["", "آخر مرات الواجهة وقعت فيها:"] + text(load(), 4)
	except Exception:
		pass
	out += ["", "وقت تجهيز الشاشات (أكتر من %d ms):" % SKIN_SLOW]
	out += table(skins) or ["   مفيش، كل الشاشات سريعة"]
	if guards:
		out += ["", "شاشات حاولت تقفل وهي مش ظاهرة (اتمنع القفل الغلط):"] + guards[-6:]
	if fits:
		out += ["", "طول القوائم:"] + fits[-4:]
	out += ["", "الضغطة الطويلة على الأزرق:"]
	out += ["   long press  x%d   (%s)" % (len(blues), blues[-1])] if blues else ["   الجهاز ما استلمش ولا ضغطة طويلة على الأزرق"]
	out += ["   extensions: %s" % e for e in exts[-3:]]
	out += ["", "لو الضغطة بطيئة والشاشة نفسها سريعة في التجهيز، البطء من البلج إن مش من السكين."]
	return "\n".join(out)
