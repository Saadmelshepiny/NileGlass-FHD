# -*- coding: utf-8 -*-
# NileGlass FHD - the timer list cards: the next recording, how many are
# planned, conflicts between them, and how many hours the free space holds.
#
#   NextIn, NextName, NextWhen, NextChannel, NextLength, Count, Conflicts,
#   Recording, FreeSpace, FreeHours, Path, UsedPercent (value 0..100)
# Read once a minute (and when the screen opens); the conflict check of the
# image (TimerSanityCheck) runs only when the list of timers changed.

import os
import time

from Components.Converter.Converter import Converter
from Components.Converter.NGPoll import NGPoll as Poll
from Components.Element import cached

GB_PER_HOUR = 3.2       # an HD recording, roughly (6 - 8 Mbit/s)
DAYS = ("الاتنين", "التلات", "الأربع", "الخميس", "الجمعة", "السبت", "الحد")

_conflictCache = (None, 0)


def recordTimer():
	try:
		import NavigationInstance
		return NavigationInstance.instance.RecordTimer
	except Exception:
		return None


def upcoming(rt, now=None):
	now = now or time.time()
	out = [t for t in (rt.timer_list if rt else []) if not t.disabled and not getattr(t, "justplay", False) and t.end > now]
	out.sort(key=lambda t: t.begin)
	return out


def conflicts(rt, timers):
	global _conflictCache
	sig = tuple((id(t), t.begin, t.end, str(getattr(t, "service_ref", ""))) for t in timers)
	if _conflictCache[0] == sig:
		return _conflictCache[1]
	n = 0
	try:
		from Components.TimerSanityCheck import TimerSanityCheck
		for t in timers[:40]:
			if getattr(t, "conflict_detection", True) and not TimerSanityCheck(rt.timer_list, t).check():
				n += 1
	except Exception as err:
		print("[NileGlass] timers:", err)
	_conflictCache = (sig, n)
	return n


def recordPath():
	try:
		from Components.config import config
		p = config.usage.default_path.value or "/media/hdd/movie/"
	except Exception:
		p = "/media/hdd/movie/"
	return p if os.path.isdir(p) else "/media/hdd/movie/" if os.path.isdir("/media/hdd/movie/") else None


def space(path):
	try:
		st = os.statvfs(path)
		return st.f_blocks * st.f_frsize, st.f_bavail * st.f_frsize
	except Exception:
		return 0, 0


def inText(seconds):
	if seconds <= 0:
		return "دلوقتي"
	m = int((seconds + 59) // 60)
	if m < 60:
		return "بعد %d د" % max(1, m)
	h, m = m // 60, m % 60
	if h < 24:
		return "بعد %d س %d د" % (h, m) if m else "بعد %d س" % h
	return "بعد %d يوم" % (h // 24)


def whenText(t):
	lt = time.localtime(t)
	today = time.localtime()
	if lt.tm_yday == today.tm_yday and lt.tm_year == today.tm_year:
		day = "النهارده"
	elif (t - time.time()) < 2 * 86400 and (lt.tm_yday - today.tm_yday) % 365 == 1:
		day = "بكرة"
	else:
		day = "%s %d/%d" % (DAYS[lt.tm_wday], lt.tm_mday, lt.tm_mon)
	return "%s %s" % (day, time.strftime("%H:%M", lt))


def channelName(t):
	try:
		return t.service_ref.getServiceName().replace("\xc2\x86", "").replace("\xc2\x87", "")
	except Exception:
		return ""


class NGTimerInfo(Poll, Converter):
	def __init__(self, arg):
		Converter.__init__(self, arg)
		Poll.__init__(self)
		self.type = (arg or "NextIn").strip()
		self.poll_interval = 60000
		self.poll_enabled = True

	@cached
	def getText(self):
		t = self.type
		try:
			rt = recordTimer()
			if t in ("FreeSpace", "FreeHours", "Path"):
				path = recordPath()
				if not path:
					return "مفيش مكان تسجيل" if t == "FreeSpace" else ""
				total, free = space(path)
				if t == "Path":
					return path.rstrip("/")
				if t == "FreeSpace":
					return "%.0f GB فاضي" % (free / 1e9) if free >= 1e10 else "%.1f GB فاضي" % (free / 1e9)
				return "تكفي حوالي %d ساعة HD" % int(free / 1e9 / GB_PER_HOUR)
			now = time.time()
			up = upcoming(rt, now)
			if t == "Count":
				return str(len(up))
			if t == "Conflicts":
				n = conflicts(rt, up) if up else 0
				return "مفيش" if n == 0 else "%d متعارض" % n
			if t == "Recording":
				rec = [x for x in up if x.begin <= now]
				return ("بيسجل دلوقتي: %s" % rec[0].name) if rec else ""
			nxt = [x for x in up if x.begin > now]
			if not nxt:
				return "مفيش تسجيل جاي" if t == "NextName" else "—" if t == "NextIn" else ""
			n = nxt[0]
			if t == "NextIn":
				return inText(n.begin - now)
			if t == "NextName":
				return n.name or channelName(n)
			if t == "NextWhen":
				return whenText(n.begin)
			if t == "NextChannel":
				return channelName(n)
			if t == "NextLength":
				return "%d دقيقة" % max(1, int((n.end - n.begin) // 60))
		except Exception as err:
			print("[NileGlass] NGTimerInfo:", err)
		return ""

	text = property(getText)

	@cached
	def getValue(self):
		if self.type == "UsedPercent":
			path = recordPath()
			total, free = space(path) if path else (0, 0)
			return int(round(100 * (total - free) / total)) if total else 0
		return 0

	value = property(getValue)
	range = 100

	@cached
	def getBoolean(self):
		return bool(self.getText()) and self.getText() not in ("مفيش", "—")

	boolean = property(getBoolean)
