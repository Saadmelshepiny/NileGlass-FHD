# -*- coding: utf-8 -*-
# NileGlass FHD - date with full Arabic names.
#
# The image's short names (%a / %b) come out as single letters in Arabic
# ("ر 11 نوف"), so short dates use this instead:
#   <convert type="NGDate">{d} {B}</convert>             ->  "11 نوفمبر"
#   <convert type="NGDate">{A} {d} {B}  {H}:{M}</convert> ->  "الأربعاء 11 نوفمبر  23:34"
# {A} day  {d} day of month  {B} month  {m} month number  {Y} year  {H} {M} time
# Works on global.CurrentTime and after EventTime (StartTime / EndTime).

import time

from Components.Converter.Converter import Converter
from Components.Element import cached

DAYS = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")
MONTHS = ("يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر")


def formatDate(fmt, t):
	lt = time.localtime(t)
	return fmt.replace("{A}", DAYS[lt.tm_wday]).replace("{B}", MONTHS[lt.tm_mon - 1]).replace(
		"{d}", str(lt.tm_mday)).replace("{m}", str(lt.tm_mon)).replace("{Y}", str(lt.tm_year)).replace(
		"{H}", "%02d" % lt.tm_hour).replace("{M}", "%02d" % lt.tm_min)


class NGDate(Converter):
	def __init__(self, arg):
		Converter.__init__(self, arg)
		self.fmt = (arg or "{A} {d} {B}").strip()

	@cached
	def getText(self):
		try:
			t = self.source.time
			if t is None:
				return ""
			if isinstance(t, tuple):
				t = t[0]
			return formatDate(self.fmt, t)
		except Exception:
			return ""

	text = property(getText)
