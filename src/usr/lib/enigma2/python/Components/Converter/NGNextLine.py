# -*- coding: utf-8 -*-
# NileGlass FHD - one line for the next programme, empty when there is none.
#   <widget source="session.Event_Next" ...><convert type="NGNextLine"/></widget>
#   ->  "التالي   21:00   نشرة الأخبار"

import time

from Components.Converter.Converter import Converter
from Components.Element import cached


class NGNextLine(Converter):
	def __init__(self, arg):
		Converter.__init__(self, arg)
		self.label = (arg or "").strip() or "التالي"

	@cached
	def getText(self):
		try:
			ev = self.source.event
			name = ev and (ev.getEventName() or "").strip()
			if not name:
				return ""
			begin = ev.getBeginTime()
			when = time.strftime("%H:%M", time.localtime(begin)) if begin else ""
			return "   ".join(p for p in (self.label, when, name) if p)
		except Exception:
			return ""

	text = property(getText)
