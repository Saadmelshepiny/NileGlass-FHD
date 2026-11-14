# -*- coding: utf-8 -*-
# NileGlass FHD - where a channel is sent, for the channel under the cursor
# (it does not have to be playing), read from the channel list itself.
#
#   <convert type="NGServiceTp">Line</convert>    ->  "11938 H 27500 5/6 · DVB-S2 8PSK · 13.0°E Hotbird"
#   <convert type="NGServiceTp">Details</convert> ->  "Provider · HD · SID 1005 · TS 20700 · ON 366"
#   Tuning / Orbital / Provider / Type / Ids : the single parts
# IPTV channels: the stream's address instead of the transponder.

from enigma import eServiceCenter, eServiceReference, iServiceInformation

from Components.Converter.Converter import Converter
from Components.Element import cached

POL = {0: "H", 1: "V", 2: "L", 3: "R"}
FEC = {0: "Auto", 1: "1/2", 2: "2/3", 3: "3/4", 4: "5/6", 5: "7/8", 6: "8/9", 7: "3/5", 8: "4/5", 9: "9/10", 10: "6/7"}
MOD = {1: "QPSK", 2: "8PSK", 3: "QAM16", 4: "16APSK", 5: "32APSK"}
TYPES = {1: "SD", 2: "Radio", 10: "Radio", 0x11: "HD", 0x16: "SD", 0x19: "HD", 0x1F: "UHD", 0x20: "UHD", 0x86: "HD"}
SEP = "  ·  "


def orbital(pos):
	try:
		pos = int(pos)
	except (TypeError, ValueError):
		return ""
	if pos <= 0 or pos >= 3600:
		return ""
	text = "%.1f°W" % ((3600 - pos) / 10.0) if pos > 1800 else "%.1f°E" % (pos / 10.0)
	try:
		from Components.NimManager import nimmanager
		name = nimmanager.getSatName(pos)
		if name:
			name = name.split("(")[0].replace(text.replace("°", ""), "").strip(" -")
			for t in (text[:-1] + "E", text[:-1] + "W"):
				name = name.replace(t.replace("°", ""), "").strip()
			if name and len(name) <= 24:
				text += " " + name
	except Exception:
		pass
	return text


def tuning(tp):
	try:
		ttype = tp.get("tuner_type", "")
		freq = int(tp.get("frequency") or 0)
		if ttype == "DVB-S":
			parts = ["%d %s %d %s" % (freq // 1000, POL.get(tp.get("polarization"), "?"), int(tp.get("symbol_rate") or 0) // 1000,
				FEC.get(tp.get("fec_inner"), "")), ("DVB-S2" if tp.get("system") == 1 else "DVB-S") + (" " + MOD[tp.get("modulation")] if tp.get("modulation") in MOD else "")]
			return SEP.join(p.strip() for p in parts)
		if ttype in ("DVB-C", "DVB-T", "ATSC"):
			mhz = freq / 1000.0 if freq > 100000 else freq
			mhz = mhz / 1000.0 if mhz > 10000 else mhz
			return "%s  %.1f MHz" % (ttype, mhz)
	except Exception:
		pass
	return ""


class NGServiceTp(Converter):
	def __init__(self, arg):
		Converter.__init__(self, arg)
		self.mode = (arg or "Line").strip()

	def ref(self):
		src = self.source
		ref = getattr(src, "service", None)
		if isinstance(ref, eServiceReference):
			return ref
		ref = getattr(src, "serviceref", None)
		return ref if isinstance(ref, eServiceReference) else None

	@cached
	def getText(self):
		ref = self.ref()
		if ref is None or ref.flags & eServiceReference.isDirectory or ref.flags & eServiceReference.isMarker:
			return ""
		try:
			info = eServiceCenter.getInstance().info(ref)
		except Exception:
			info = None
		path = ref.getPath() or ""
		stream = "://" in path or "%3a//" in ref.toString().lower()
		m = self.mode
		try:
			if m in ("Line", "Tuning", "Orbital"):
				if stream:
					host = path.split("://", 1)[-1].split("/", 1)[0].split("@")[-1] if "://" in path else ""
					return ("IPTV" + (SEP + host if host else "")) if m != "Orbital" else ""
				tp = info and info.getInfoObject(ref, iServiceInformation.sTransponderData)
				if not tp:
					return ""
				t, o = tuning(tp), orbital(tp.get("orbital_position"))
				return {"Tuning": t, "Orbital": o}.get(m, SEP.join(p for p in (t, o) if p))
			parts = []
			if m in ("Details", "Provider"):
				prov = info.getInfoString(ref, iServiceInformation.sProvider) if info else ""
				if m == "Provider":
					return prov or ""
				if prov:
					parts.append(prov)
			if m in ("Details", "Type"):
				kind = "IPTV" if stream else TYPES.get(ref.getData(0), "")
				if m == "Type":
					return kind
				if kind:
					parts.append(kind)
			if m in ("Details", "Ids") and not stream:
				sid, tsid, onid = ref.getUnsignedData(1), ref.getUnsignedData(2), ref.getUnsignedData(3)
				ids = SEP.join(p for p in (sid and "SID %d" % sid, tsid and "TS %d" % tsid, onid and "ON %d" % onid) if p)
				if m == "Ids":
					return ids
				if ids:
					parts.append(ids)
			return SEP.join(parts)
		except Exception:
			return ""

	text = property(getText)
