# -*- coding: utf-8 -*-
# NileGlass FHD - Hijri date.
#
#   on global.CurrentTime:
#     <convert type="NGHijri"/>                ->  "1 جمادى الآخرة 1448 هـ"
#   after a date converter (adds it to that text):
#     <convert type="ClockToText">Format:%A %d %B</convert><convert type="NGHijri">Append</convert>
#                                              ->  "الأربعاء 11 نوفمبر · 1 جمادى الآخرة"
# Arithmetic (civil) Hijri calendar; it can differ by a day from the sighting
# in your country, so the settings have a +/- day correction.  Turned off in
# the settings -> empty (Append: the original text only).

import time

from Components.Converter.Converter import Converter
from Components.Element import cached

MONTHS = ("محرم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى", "جمادى الآخرة",
	"رجب", "شعبان", "رمضان", "شوال", "ذو القعدة", "ذو الحجة")


def _settings():
	try:
		from Components.NileGlassCore import confBool, confGet
		if not confBool("extras", "hijri", True):
			return None
		return int(confGet("extras", "hijri_offset", "0") or 0)
	except Exception:
		return 0


def toHijri(y, m, d):
	"""Gregorian -> (year, month 1-12, day), civil Islamic calendar."""
	a = int((m - 14) / 12)
	jd = (1461 * (y + 4800 + a)) // 4 + (367 * (m - 2 - 12 * a)) // 12 - (3 * ((y + 4900 + a) // 100)) // 4 + d - 32075
	l = jd - 1948440 + 10632
	n = (l - 1) // 10631
	l = l - 10631 * n + 354
	j = ((10985 - l) // 5316) * ((50 * l) // 17719) + (l // 5670) * ((43 * l) // 15238)
	l = l - ((30 - j) // 15) * ((17719 * j) // 50) - (j // 16) * ((15238 * j) // 43) + 29
	month = (24 * l) // 709
	day = l - (709 * month) // 24
	year = 30 * n + j - 30
	return year, month, day


def hijriText(t=None, withYear=True):
	offset = _settings()
	if offset is None:
		return ""
	lt = time.localtime((t or time.time()) + offset * 86400)
	y, m, d = toHijri(lt.tm_year, lt.tm_mon, lt.tm_mday)
	if not 1 <= m <= 12:
		return ""
	return "%d %s %d هـ" % (d, MONTHS[m - 1], y) if withYear else "%d %s" % (d, MONTHS[m - 1])


class NGHijri(Converter):
	def __init__(self, arg):
		Converter.__init__(self, arg)
		self.mode = (arg or "").strip()

	@cached
	def getText(self):
		try:
			if self.mode == "Append":
				base = self.source.text or ""
				h = hijriText(withYear=False)
				return "%s · %s" % (base, h) if base and h else base
			return hijriText(getattr(self.source, "time", None), withYear=self.mode != "Short")
		except Exception:
			return ""

	text = property(getText)
