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
#   fields="time"      only "21:45 - 23:45" of the event; "title" only its name;
#   fields="desc"      only its description (short one, else the long one) - for event cards
#
# Data comes from enigma2's in-memory EPG cache (C++), so it is instant and
# needs no disk or network access.

from time import localtime, strftime, time

from enigma import eEPGCache, eLabel, eServiceReference

from Components.Renderer.Renderer import Renderer
from Components.NileGlassCore import upcomingDetails, upcomingEvents
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
		self.pending = True
		self.showDuration = False
		self.timeColor = ""
		self.textColor = ""
		self.lastKey = None
		self.fields = ""

	def applySkin(self, desktop, parent):
		attribs = []
		for attrib, value in self.skinAttributes:
			if attrib == "items":
				self.items = max(1, int(value))
			elif attrib == "timeBreak":
				self.timeBreak = value == "1"
			elif attrib == "fields":
				self.fields = value.strip().lower()
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
		if self.suspended:  # screen hidden (e.g. second infobar): no EPG work until it is shown
			self.pending = True
			return
		self.pending = False
		ref = self.serviceRef()
		if ref is None:
			self.text = ""
			self.lastKey = None
			return
		if self.fields in ("time", "title", "desc"):
			self.showFields(ref)
			return
		events = upcomingEvents(ref.toString())
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

	def showFields(self, ref):
		events = upcomingDetails(ref.toString())
		if self.skipNow and events and events[0][0] <= time():
			events = events[1:]
		lines = []
		for ev in events[self.start:self.start + self.items]:
			begin, duration, title = ev[0], ev[1] or 0, (ev[2] or "").strip()
			if self.fields == "time":
				lines.append("%s - %s" % (strftime("%H:%M", localtime(begin)), strftime("%H:%M", localtime(begin + duration))))
			elif self.fields == "title":
				lines.append(title)
			else:
				short = (ev[3] or "").strip() if len(ev) > 3 else ""
				ext = (ev[4] or "").strip() if len(ev) > 4 else ""
				desc = short if short and short != title else ext
				lines.append(desc.replace("\x8a", "\n"))
		text = "\n".join(lines)
		if text != self.lastKey:
			self.lastKey = text
			self.text = text

	def onShow(self):
		Renderer.onShow(self)
		if self.pending:
			self.changed((self.CHANGED_ALL,))
