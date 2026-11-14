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
# Nothing runs between key presses; the log is /tmp/nileglass_perf.log.

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


class PerfWatch:
	def __init__(self, session):
		self.session = session
		self.t0 = None
		self.screen = ""
		self.timer = eTimer()
		self.timer.callback.append(self.done)
		eActionMap.getInstance().bindAction("", -0x7FFFFFFF, self.key)

	def key(self, key, flag):
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
	keys, skins, guards, fits, blues, exts = {}, {}, [], [], [], []
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
