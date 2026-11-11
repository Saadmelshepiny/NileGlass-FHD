# -*- coding: utf-8 -*-
# NileGlass FHD - how fast does the box answer the remote?
#
# Every key press is timed from the moment it arrives until enigma2 is idle
# again (the key handled and the screen redrawn).  Only slow presses
# (> SLOW ms) are written to /tmp/nileglass_perf.log with the screen they
# happened on, so the slow screen can be found and fixed.  Nothing runs
# between key presses.

import time

from enigma import eActionMap, eTimer

LOG = "/tmp/nileglass_perf.log"
SLOW = 150          # ms
MAX_LOG = 200000    # bytes


class PerfWatch:
	def __init__(self, session):
		self.session = session
		self.t0 = None
		self.screen = ""
		self.timer = eTimer()
		self.timer.callback.append(self.done)
		eActionMap.getInstance().bindAction("", -0x7FFFFFFF, self.key)

	def screenName(self):
		d = getattr(self.session, "current_dialog", None)
		if d is None:
			return "?"
		sn = getattr(d, "skinName", None)
		if isinstance(sn, (list, tuple)):
			sn = sn[0] if sn else None
		return "%s%s" % (d.__class__.__name__, ("/" + sn) if sn and sn != d.__class__.__name__ else "")

	def key(self, key, flag):
		if flag in (0, 2) and self.t0 is None:   # make / repeat
			self.t0 = time.monotonic()
			self.screen = self.screenName()
			self.timer.start(0, True)            # runs when the key is fully handled
		return 0                                 # never eat the key

	def done(self):
		if self.t0 is None:
			return
		ms = int((time.monotonic() - self.t0) * 1000)
		self.t0 = None
		if ms < SLOW:
			return
		now = self.screenName()
		try:
			import os
			if os.path.exists(LOG) and os.path.getsize(LOG) > MAX_LOG:
				os.replace(LOG, LOG + ".old")
			with open(LOG, "a") as f:
				f.write("%s %5d ms  %s%s\n" % (time.strftime("%H:%M:%S"), ms, self.screen, ("  ->  " + now) if now != self.screen else ""))
		except Exception:
			pass


watcher = None


def install(session):
	global watcher
	if watcher is None:
		try:
			watcher = PerfWatch(session)
		except Exception as err:
			print("[NileGlass] perf watch:", err)


def report():
	"""Arabic summary of the slow key presses: per screen, count / average / worst."""
	try:
		lines = open(LOG).read().splitlines()
	except Exception:
		return "مفيش ضغطات بطيئة متسجلة (أبطأ من %d ms).\nاستخدم الجهاز شوية وبعدين افتح التقرير." % SLOW
	stats = {}
	for line in lines:
		parts = line.split()
		try:
			ms, screen = int(parts[1]), parts[3]
		except (IndexError, ValueError):
			continue
		s = stats.setdefault(screen, [0, 0, 0])
		s[0] += 1
		s[1] += ms
		s[2] = max(s[2], ms)
	if not stats:
		return "مفيش ضغطات بطيئة متسجلة."
	rows = sorted(stats.items(), key=lambda kv: -kv[1][1])[:12]
	out = ["الضغطات الأبطأ من %d ms (الملف: %s)" % (SLOW, LOG), ""]
	for screen, (n, total, worst) in rows:
		out.append("%s:  %d مرة  ·  متوسط %d ms  ·  أبطأ %d ms" % (screen, n, total // n, worst))
	return "\n".join(out)
