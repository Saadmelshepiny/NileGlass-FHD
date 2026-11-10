# -*- coding: utf-8 -*-
# NileGlass FHD - list of upcoming EPG events for a service.
#
#   <widget source="session.CurrentService" render="NGEventList" position="..." size="..."
#           font="Regular;28" items="6" timeColor="#2f9cff" foregroundColor="#eef1f4" />
#   <widget source="ServiceEvent" render="NGEventList" ... />   (channel list)
#
# Attributes:
#   items="6"          number of lines
#   skipNow="1"        start with the next event (1) or with the running one (0)
#   start="0"          skip this many further events (e.g. start="2" items="1")
#   timeColor="..."    colour of the start time
#   showDuration="1"   append the duration in minutes
#   timeBreak="1"      time on its own line above the title (narrow captions)
#
# Data comes from enigma2's in-memory EPG cache (C++), so it is instant and
# needs no disk or network access.

from time import localtime, strftime, time

from enigma import eEPGCache, eLabel, eServiceReference

from Components.Renderer.Renderer import Renderer
from Components.VariableText import VariableText
from skin import parseColor
from Tools.Hex2strColor import Hex2strColor


class NGEventList(Renderer, VariableText):
	GUI_WIDGET = eLabel

	def __init__(self):
		Renderer.__init__(self)
		VariableText.__init__(self)
		self.epgcache = eEPGCache.getInstance()
		self.items = 6
		self.skipNow = True
		self.start = 0
		self.timeBreak = False
		self.showDuration = False
		self.timeColor = ""
		self.textColor = ""
		self.lastKey = None

	def applySkin(self, desktop, parent):
		attribs = []
		for attrib, value in self.skinAttributes:
			if attrib == "items":
				self.items = max(1, int(value))
			elif attrib == "timeBreak":
				self.timeBreak = value == "1"
			elif attrib == "start":
				self.start = max(0, int(value))
			elif attrib == "skipNow":
				self.skipNow = value.lower() in ("1", "true", "yes")
			elif attrib == "showDuration":
				self.showDuration = value.lower() in ("1", "true", "yes")
			elif attrib == "timeColor":
				self.timeColor = Hex2strColor(parseColor(value).argb())
			else:
				if attrib == "foregroundColor":
					self.textColor = Hex2strColor(parseColor(value).argb())
				attribs.append((attrib, value))
		self.skinAttributes = attribs
		return Renderer.applySkin(self, desktop, parent)

	def serviceRef(self):
		src = self.source
		ref = getattr(src, "serviceref", None)  # CurrentService
		if ref is None:
			ref = getattr(src, "service", None)  # ServiceEvent
		if isinstance(ref, eServiceReference) and ref.valid():
			if ref.flags & eServiceReference.isGroup:
				return None
			return ref
		return None

	def changed(self, what):
		if what[0] == self.CHANGED_CLEAR:
			self.text = ""
			self.lastKey = None
			return
		ref = self.serviceRef()
		if ref is None:
			self.text = ""
			self.lastKey = None
			return
		refstr = ref.toString()
		try:
			events = self.epgcache.lookupEvent(["BDT", (refstr, 0, -1, 24 * 60)]) or []
		except Exception:
			events = []
		if self.skipNow and events and events[0][0] <= time():  # first one is running now
			events = events[1:]
		lines = []
		for begin, duration, title in events[self.start:self.start + self.items]:
			if not title:
				continue
			line = "%s%s%s%s%s" % (self.timeColor, strftime("%H:%M", localtime(begin)), "\n" if self.timeBreak else "  ", self.textColor, title.strip())
			if self.showDuration and duration:
				line += "  (%d')" % (duration // 60)
			lines.append(line)
		text = "\n".join(lines)
		if text != self.lastKey:  # CurrentService fires many events per zap - only repaint on change
			self.lastKey = text
			self.text = text
