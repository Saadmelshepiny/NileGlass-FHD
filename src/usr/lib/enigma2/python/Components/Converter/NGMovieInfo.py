# -*- coding: utf-8 -*-
# NileGlass FHD - the recording under the cursor in the movie list.
#
#   Length, Size, Recorded, Channel, Quality, Watched, Left, WatchedPct (value)
# "Watched" comes from the .cuts file (the place where playback stopped).

import os
import struct
import time

from Components.Converter.Converter import Converter
from Components.Element import cached

try:
	from enigma import eServiceCenter, iServiceInformation
except Exception:
	eServiceCenter = iServiceInformation = None


def clock(sec):
	sec = int(sec)
	h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
	return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def lastPosition(path):
	"""seconds where playback stopped (cut type 3 in the .cuts file), or 0"""
	try:
		with open(path + ".cuts", "rb") as f:
			data = f.read()
	except Exception:
		return 0
	last = 0
	for i in range(0, len(data) - 11, 12):
		pts, kind = struct.unpack(">QI", data[i:i + 12])
		if kind == 3:
			last = pts / 90000.0
	return last


def metaLines(path):
	try:
		with open(path + ".meta", encoding="utf-8", errors="ignore") as f:
			return f.read().split("\n")
	except Exception:
		return []


class NGMovieInfo(Converter):
	def __init__(self, arg):
		Converter.__init__(self, arg)
		self.type = (arg or "Length").strip()

	def ref(self):
		try:
			return self.source.getCurrentService()
		except Exception:
			return None

	def path(self, ref):
		try:
			p = ref.getPath()
			return p if p and os.path.isfile(p) else None
		except Exception:
			return None

	def length(self, ref):
		try:
			info = eServiceCenter.getInstance().info(ref)
			n = info.getLength(ref) if info else 0
			return n if n and n > 0 else 0
		except Exception:
			return 0

	@cached
	def getText(self):
		ref = self.ref()
		p = self.path(ref) if ref else None
		if not p:
			return ""
		t = self.type
		try:
			if t == "Length":
				n = self.length(ref)
				return clock(n) if n else ""
			if t == "Size":
				n = os.path.getsize(p)
				return "%.2f GB" % (n / 1e9) if n >= 1e9 else "%d MB" % (n // 1000000)
			if t == "Recorded":
				meta = metaLines(p)
				ts = int(meta[3]) if len(meta) > 3 and meta[3].strip().isdigit() else int(os.path.getmtime(p))
				return time.strftime("%d/%m/%Y  %H:%M", time.localtime(ts))
			if t == "Channel":
				meta = metaLines(p)
				if meta and meta[0].strip():
					try:
						from ServiceReference import ServiceReference
						name = ServiceReference(meta[0].strip()).getServiceName()
						if name:
							return name.replace("\xc2\x86", "").replace("\xc2\x87", "")
					except Exception:
						pass
				try:
					info = eServiceCenter.getInstance().info(ref)
					return info.getInfoString(ref, iServiceInformation.sServiceref) and "" or ""
				except Exception:
					return ""
			if t == "Quality":
				n = self.length(ref)
				if not n:
					return ""
				mbit = os.path.getsize(p) * 8 / 1e6 / n
				kind = "4K" if mbit >= 14 else "HD" if mbit >= 3.5 else "SD"
				return "%s تقريبًا · %.1f Mbit/s" % (kind, mbit)
			if t in ("Watched", "Left"):
				n, pos = self.length(ref), lastPosition(p)
				if t == "Watched":
					if pos < 10:
						return "لسه متشافش"
					if n and pos >= n - 60:
						return "اتشاف للآخر"
					return "وقفت عند %s%s" % (clock(pos), (" من %s" % clock(n)) if n else "")
				if n and 10 <= pos < n - 60:
					return "فاضل %d د" % max(1, int((n - pos) // 60))
				return ""
		except Exception as err:
			print("[NileGlass] NGMovieInfo:", err)
		return ""

	text = property(getText)

	@cached
	def getValue(self):
		ref = self.ref()
		p = self.path(ref) if ref else None
		if not p:
			return 0
		n, pos = self.length(ref), lastPosition(p)
		return int(min(100, 100 * pos / n)) if n else 0

	value = property(getValue)
	range = 100
