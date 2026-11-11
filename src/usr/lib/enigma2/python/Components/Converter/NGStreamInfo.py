# -*- coding: utf-8 -*-
# NileGlass FHD - details of an internet stream (web radio / IPTV).
#
#   <convert type="NGStreamInfo">Net</convert>      ->  "1.4 Mb/s"   (internet download now)
#   <convert type="NGStreamInfo">Volume</convert>   ->  "55%"  /  "صامت"
#   <convert type="NGStreamInfo">Audio</convert>    ->  "MP3 · 128 kb/s · Stereo"
#   <convert type="NGStreamInfo">Quality</convert>  ->  "جودة جيدة"
# (Arabic and Latin are kept in separate widgets so the text direction never
# shuffles the parts.)
# Empty for satellite channels, so it can sit where the signal panel is.
# Refreshed every 2 s, and only while the widget is on screen.

import os
import time

from enigma import iServiceInformation

from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached

S_TAG_BITRATE = getattr(iServiceInformation, "sTagBitrate", None)
S_TAG_NOMINAL = getattr(iServiceInformation, "sTagNominalBitrate", None)
S_AUDIO_RATE = getattr(iServiceInformation, "sAudioBitrate", None)
S_CHANNELS = getattr(iServiceInformation, "sTagChannelMode", None)
S_REF = getattr(iServiceInformation, "sServiceref", None)


def isStream(info):
	try:
		ref = info.getInfoString(S_REF) or ""
		return "://" in ref or "%3a//" in ref.lower()
	except Exception:
		return False


def _rxBytes():
	total = 0
	try:
		with open("/proc/net/dev") as f:
			for line in f.readlines()[2:]:
				name, data = line.split(":", 1)
				if name.strip() != "lo":
					total += int(data.split()[0])
	except Exception:
		return None
	return total


def rate(kbits):
	return "%.1f Mb/s" % (kbits / 1000.0) if kbits >= 1000 else "%d kb/s" % kbits


def _int(info, what):
	if what is None:
		return -1
	try:
		v = info.getInfo(what)
		return v if isinstance(v, int) else -1
	except Exception:
		return -1


class NGStreamInfo(Poll, Converter):
	def __init__(self, arg):
		Poll.__init__(self)
		Converter.__init__(self, arg)
		self.mode = (arg or "Net").strip()
		self.poll_interval = 2000
		self.poll_enabled = True
		self.last = None      # (time, rx bytes)

	def net(self):
		now, rx = time.monotonic(), _rxBytes()
		if rx is None:
			return ""
		last, self.last = self.last, (now, rx)
		if not last or now - last[0] < 0.5 or rx < last[1]:
			return ""
		kbits = (rx - last[1]) * 8 / 1000.0 / (now - last[0])
		return rate(int(kbits))

	@staticmethod
	def volume():
		try:
			from enigma import eDVBVolumecontrol
			v = eDVBVolumecontrol.getInstance()
			return "صامت" if v.isMuted() else "%d%%" % v.getVolume()
		except Exception:
			return ""

	@staticmethod
	def kbps(info):
		bps = max(_int(info, S_TAG_BITRATE), _int(info, S_TAG_NOMINAL))
		return bps // 1000 if bps > 1000 else _int(info, S_AUDIO_RATE)

	@classmethod
	def quality(cls, info):
		k = cls.kbps(info)
		if k <= 0:
			return ""
		return "جودة عالية" if k >= 256 else "جودة جيدة" if k >= 128 else "جودة عادية"

	@classmethod
	def audio(cls, service, info):
		parts = []
		try:
			from Components.Converter.NGCodec import audioCodec
			codec = audioCodec(service)
		except Exception:
			codec = ""
		if codec:
			parts.append(codec)
		kbps = cls.kbps(info)
		if kbps > 0:
			parts.append("%d kb/s" % kbps)
		try:
			mode = (info.getInfoString(S_CHANNELS) or "").lower() if S_CHANNELS is not None else ""
		except Exception:
			mode = ""
		if "mono" in mode:
			parts.append("Mono")
		elif "stereo" in mode or "dual" in mode:
			parts.append("Stereo")
		return " · ".join(parts)

	@cached
	def getText(self):
		try:
			service = self.source.service
			info = service and service.info()
			if not info or not isStream(info):
				self.last = None
				return ""
			if self.mode == "Volume":
				return self.volume()
			if self.mode == "Audio":
				return self.audio(service, info)
			if self.mode == "Quality":
				return self.quality(info)
			return self.net()
		except Exception:
			return ""

	text = property(getText)
