# -*- coding: utf-8 -*-
# NileGlass FHD - video / audio bitrate of the playing service.
#
# The service measures the rate itself (iServiceInformation.sVideoBitrate /
# sAudioBitrate, DVB and IPTV alike); this converter reads it once a second,
# only while a widget using it is on screen (suspended when the screen is
# hidden), and keeps min / max / average per channel.
# On an image without those counters it shows nothing - never an error.
#
#   <convert type="NGBitrate">Compact</convert>  ->  "V 5.6 Mb/s · A 190 kb/s"
#   Video / Audio                                ->  "5634 kb/s" / "190 kb/s"
#   VideoStats / AudioStats                      ->  "5634  (1379 - 11532, avg 5513)"
#   video.cur / video.min / video.max / video.avg (and audio.*) -> "5634"
#   Bool (with ConditionalShowHide)              ->  True when a rate is known

from enigma import eTimer, iServiceInformation

import NavigationInstance
from Components.Converter.Converter import Converter
from Components.Element import cached

S_VIDEO = getattr(iServiceInformation, "sVideoBitrate", None)
S_AUDIO = getattr(iServiceInformation, "sAudioBitrate", None)
MIN_VALID = (100, 8)    # kbit/s below this are gaps in the data, not the rate
SMOOTH = 5              # seconds averaged for the "current" value


class _Stats:
	def __init__(self):
		self.reset()

	def reset(self):
		self.hist = []
		self.cur = self.min = self.max = 0
		self.total = self.count = 0

	def add(self, val, idx):
		if val < MIN_VALID[idx]:
			return False
		self.hist.append(val)
		del self.hist[:-SMOOTH]
		self.cur = sum(self.hist) // len(self.hist)
		self.min = val if not self.min else min(self.min, val)
		self.max = max(self.max, val)
		self.total += val
		self.count += 1
		return True

	@property
	def avg(self):
		return self.total // self.count if self.count else 0


class _Engine:
	def __init__(self):
		self.users = []
		self.sref = None
		self.stats = (_Stats(), _Stats())
		self.timer = eTimer()
		self.timer.callback.append(self.poll)

	def attach(self, user):
		if user not in self.users:
			self.users.append(user)
		if S_VIDEO is not None and not self.timer.isActive():
			self.timer.start(1000, False)

	def detach(self, user):
		if user in self.users:
			self.users.remove(user)
		if not self.users:
			self.timer.stop()

	def poll(self):
		try:
			service = NavigationInstance.instance.getCurrentService()
			info = service and service.info()
			if not info:
				return
			sref = info.getInfoString(iServiceInformation.sServiceref)
			if sref != self.sref:
				self.sref = sref
				for s in self.stats:
					s.reset()
				self.notify()
			v = info.getInfo(S_VIDEO)
			a = info.getInfo(S_AUDIO)
			if self.stats[0].add(v, 0) | self.stats[1].add(a, 1):
				self.notify()
		except Exception as err:
			print("[NGBitrate]", err)
			self.timer.stop()

	def notify(self):
		for user in self.users[:]:
			user.refresh()


engine = _Engine()


def _rate(kbps):
	if kbps >= 1000:
		return "%.1f Mb/s" % (kbps / 1000.0)
	return "%d kb/s" % kbps


class NGBitrate(Converter):
	def __init__(self, arg):
		Converter.__init__(self, arg)
		self.kind = arg.strip().lower() or "compact"

	def refresh(self):
		Converter.changed(self, (self.CHANGED_POLL,))

	@cached
	def getText(self):
		v, a = engine.stats
		k = self.kind
		if k == "video":
			return "%d kb/s" % v.cur if v.cur else ""
		if k == "audio":
			return "%d kb/s" % a.cur if a.cur else ""
		if k in ("videostats", "audiostats"):
			s = v if k == "videostats" else a
			if not s.cur:
				return ""
			return "%d kb/s   (%d - %d, avg %d)" % (s.cur, s.min, s.max, s.avg)
		if "." in k:
			which, field = k.split(".", 1)
			st = v if which == "video" else a
			val = getattr(st, field, 0) if field in ("cur", "min", "max", "avg") else 0
			return "%d" % val if val else "-"
		parts = []
		if v.cur:
			parts.append("V " + _rate(v.cur))
		if a.cur:
			parts.append("A " + _rate(a.cur))
		return "  ·  ".join(parts)

	text = property(getText)

	@cached
	def getBoolean(self):
		v, a = engine.stats
		if self.kind.startswith("video"):
			return v.cur > 0
		if self.kind.startswith("audio"):
			return a.cur > 0
		return v.cur > 0 or a.cur > 0

	boolean = property(getBoolean)

	def changed(self, what):
		if what[0] == self.CHANGED_CLEAR:
			engine.detach(self)
		elif what[0] != self.CHANGED_POLL and not self.suspended:
			engine.attach(self)
		Converter.changed(self, what)

	def doSuspend(self, suspended):
		if suspended:
			engine.detach(self)
		else:
			engine.attach(self)

	def destroy(self):
		engine.detach(self)
		Converter.destroy(self)
