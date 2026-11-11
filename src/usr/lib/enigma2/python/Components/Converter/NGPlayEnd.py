# -*- coding: utf-8 -*-
# NileGlass FHD - clock time at which the playing film / recording ends.
#
#   <convert type="NGPlayEnd"/>        ->  "ينتهي 23:45"
#   <convert type="NGPlayEnd">Time</convert>  ->  "23:45"
# now + (length - position), refreshed every few seconds while on screen
# (so pausing or seeking moves the end time); nothing for live TV.

import time

from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached

PTS = 90000.0


class NGPlayEnd(Poll, Converter):
	def __init__(self, arg):
		Poll.__init__(self)
		Converter.__init__(self, arg)
		self.bare = (arg or "").strip() == "Time"
		self.poll_interval = 5000
		self.poll_enabled = True

	@cached
	def getText(self):
		try:
			service = self.source.service
			seek = service and service.seek()
			if not seek:
				return ""
			length = seek.getLength()
			pos = seek.getPlayPosition()
			if length[0] or pos[0] or length[1] <= 0:
				return ""
			left = max(0, (length[1] - pos[1]) / PTS)
			end = time.strftime("%H:%M", time.localtime(time.time() + left))
			return end if self.bare else "ينتهي " + end
		except Exception:
			return ""

	text = property(getText)
