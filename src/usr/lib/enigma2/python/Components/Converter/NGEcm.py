# -*- coding: utf-8 -*-
# NileGlass FHD - decoding information from /tmp/ecm.info (any softcam / emu).
#
#   <widget source="session.CurrentService" render="Label" ...>
#       <convert type="NGEcm">Caid</convert>
#   </widget>
#
# Types:
#   State    "تم فك التشفير" / "بانتظار فك التشفير ..." / "قناة مفتوحة (FTA)"; shows the
#            change right after switching the emu (old ecm.info = waiting)
#   Caid     0x1830  Nagra
#   Source   reader / server / emulator
#   Protocol cccam, newcamd, emu ...
#   Hops     number of hops (0 = local)
#   Time     ECM time in ms
#   Line     everything in one line
#   Raw      the whole ecm.info file
#   Cam      name of the running softcam (from the image's settings)
#   Reader / From / Pid / Prov / Chid   those lines of ecm.info (reader name, server address, ECM PID ...)
#   Caids    every encryption system the channel is sent with ("Conax · Nagra · Viaccess")
#
# /tmp is a RAM disk, so reading the small file once a second costs nothing;
# it is only parsed again when it changed.

import os
import re
import time

from enigma import iServiceInformation

from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached

ECM_FILE = "/tmp/ecm.info"
SYSTEMS = (
	(0x0100, 0x01FF, "Seca"), (0x0500, 0x05FF, "Viaccess"), (0x0600, 0x06FF, "Irdeto"), (0x0900, 0x09FF, "NDS"),
	(0x0B00, 0x0BFF, "Conax"), (0x0D00, 0x0DFF, "CryptoWorks"), (0x0E00, 0x0EFF, "PowerVU"), (0x1010, 0x1010, "Tandberg"),
	(0x1700, 0x17FF, "Betacrypt"), (0x1800, 0x18FF, "Nagra"), (0x2600, 0x26FF, "BISS"), (0x2700, 0x2710, "DRE"),
	(0x4AE0, 0x4AE1, "DRE"), (0x4AEA, 0x4AEA, "Cryptoguard"), (0x4AEE, 0x4AEE, "Bulcrypt"), (0x5581, 0x5581, "Bulcrypt"),
	(0x4AFC, 0x4AFC, "Panaccess"), (0x4A02, 0x4A02, "Tongfang"), (0x5601, 0x5604, "Verimatrix"),
)

_cache = {"mtime": None, "info": {}, "raw": ""}


def systemName(caid):
	for lo, hi, name in SYSTEMS:
		if lo <= caid <= hi:
			return name
	return ""


def readEcm():
	"""(mtime, dict, raw text) of ecm.info; parsed only when it changed."""
	try:
		mtime = os.stat(ECM_FILE).st_mtime
	except OSError:
		_cache.update(mtime=None, info={}, raw="")
		return None, {}, ""
	if mtime != _cache["mtime"]:
		info, raw = {}, ""
		try:
			with open(ECM_FILE, "r", errors="replace") as f:
				raw = f.read(4096)
			for line in raw.splitlines():
				if ":" in line:
					k, v = line.split(":", 1)
					info[k.strip().lower()] = v.strip()
				elif line.lower().startswith("system") or line.startswith("="):  # oscam: "===== Nagra ECM on CaID 0x1830 ..."
					info["system"] = line.strip()
		except Exception:
			pass
		_cache.update(mtime=mtime, info=info, raw=raw)
	return _cache["mtime"], _cache["info"], _cache["raw"]


def currentCam():
	try:
		from Components.config import config
		for path in ("softcam.actCam", "softcam.actcam"):
			obj = config
			for part in path.split("."):
				obj = getattr(obj, part)
			if obj.value:
				return str(obj.value)
	except Exception:
		pass
	for p in ("/etc/CurrentBhCamName", "/etc/CurrentDelCamName", "/etc/active_emu.list", "/etc/clist.list"):
		try:
			with open(p) as f:
				name = f.read().strip().splitlines()[0]
			if name:
				return name
		except Exception:
			continue
	return ""


class NGEcm(Poll, Converter):
	TYPES = ("state", "caid", "source", "protocol", "hops", "time", "line", "raw", "cam", "reader", "from", "pid", "prov", "chid", "caids")

	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)
		t = (type or "").strip().lower()
		self.type = t if t in self.TYPES else "line"
		self.poll_interval = 1000
		self.poll_enabled = True
		self.zapTime = time.time()
		self.lastRef = None

	def _service(self):
		service = getattr(self.source, "service", None)
		return service and service.info()

	def _crypted(self, info):
		try:
			return bool(info.getInfo(iServiceInformation.sIsCrypted))
		except Exception:
			return False

	@cached
	def getText(self):
		if self.type == "cam":
			return currentCam()
		info = self._service()
		if not info:
			return ""
		try:
			ref = info.getInfoString(iServiceInformation.sServiceref)
		except Exception:
			ref = None
		if ref != self.lastRef:
			self.lastRef = ref
			self.zapTime = time.time()
		crypted = self._crypted(info)
		if self.type == "caids":
			return self._caids(info) if crypted else ""
		mtime, ecm, raw = readEcm()
		now = time.time()
		fresh = mtime is not None and mtime >= self.zapTime - 2 and now - mtime < 90  # emu restarted or stopped = stale
		if self.type == "state":
			if not crypted:
				return "قناة مفتوحة (FTA)"
			if not fresh:
				return "بانتظار فك التشفير ..."
			return "تم فك التشفير"
		if not crypted or not fresh:
			return ""
		if self.type == "raw":
			return raw.strip()
		if self.type == "caid":
			return self._caid(ecm)
		if self.type == "source":
			return self._source(ecm)
		if self.type == "protocol":
			return ecm.get("protocol", "")
		if self.type == "hops":
			return ecm.get("hops", "")
		if self.type == "time":
			return self._time(ecm)
		if self.type == "reader":
			return ecm.get("reader") or ecm.get("source") or ecm.get("using") or ""
		if self.type == "from":
			return ecm.get("from") or ecm.get("address") or ""
		if self.type in ("pid", "prov", "chid"):
			return ecm.get(self.type) or ecm.get(self.type + "id", "") or ""
		return "   ".join(x for x in (self._caid(ecm), self._source(ecm), ecm.get("protocol", ""),
			("hops " + ecm["hops"]) if ecm.get("hops") else "", self._time(ecm)) if x)

	text = property(getText)

	@staticmethod
	def _caids(info):
		try:
			caids = info.getInfoObject(iServiceInformation.sCAIDs) or []
		except Exception:
			return ""
		names = []
		for c in caids:
			n = systemName(c) or "0x%04X" % c
			if n not in names:
				names.append(n)
		return "  ·  ".join(names)

	@staticmethod
	def _caid(ecm):
		raw = ecm.get("caid") or ""
		if not raw and "system" in ecm:  # oscam/ncam: "===== Nagra ECM on CaID 0x1830 ..."
			raw = ecm["system"]
		try:
			c = int(raw.split()[0], 16) if raw else 0
		except ValueError:
			m = re.search(r"0x([0-9a-fA-F]{4})", raw)
			c = int(m.group(1), 16) if m else 0
		if not c:
			return ""
		name = systemName(c)
		return "0x%04X  %s" % (c, name) if name else "0x%04X" % c

	@staticmethod
	def _source(ecm):
		for k in ("reader", "from", "source", "address", "using"):
			v = ecm.get(k)
			if v:
				return v.replace("(", " (").strip()
		return ""

	@staticmethod
	def _time(ecm):
		t = (ecm.get("ecm time") or ecm.get("ecmtime") or "").replace("msec", "").replace("ms", "").strip()
		if not t:
			return ""
		try:
			v = float(t.split()[0])
			ms = v * 1000 if v < 20 else v  # "0.312" seconds or "312" ms
			return "%d ms" % ms
		except ValueError:
			return t
