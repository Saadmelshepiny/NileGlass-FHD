# -*- coding: utf-8 -*-
# NileGlass FHD - film / programme details from TMDB.
#
#   one line :  <widget source="session.Event_Now" render="NGEventInfo" fields="year,genres,rating" ... />
#   card     :  <widget source="session.Event_Now" render="NGEventInfo" mode="card"
#                       fields="year,genres,director,country,cast" labelColor="#9aa3ae" ... />
#   story    :  <widget ... render="NGEventInfo" fields="overview" />
#
# fields: year, genres, rating, type, overview, director, country, cast, runtime
# year/genres/rating/overview come with the poster search (no extra request);
# director/country/cast/runtime need one extra TMDB request, made only when a
# widget shows them. All cached on disk; the UI thread only formats text.

from enigma import eLabel, eTimer

from Components.Renderer.Renderer import Renderer
from Components.VariableText import VariableText
from Components.NileGlassCore import posters, formatInfo, formatCard, confGet
from skin import parseColor
from Tools.Hex2strColor import Hex2strColor

DETAIL_FIELDS = ("director", "country", "cast", "runtime", "imdb", "awards")


class NGEventInfo(Renderer, VariableText):
	GUI_WIDGET = eLabel

	def __init__(self):
		Renderer.__init__(self)
		VariableText.__init__(self)
		self.fields = ("year", "genres", "rating")
		self.mode = "line"
		self.delay = 300
		self.labelColor = ""
		self.valueColor = ""
		self.arabic = confGet("tmdb", "language", "ar") == "ar"
		self.wantedName = None
		self.wantedTitle = None
		self.timer = eTimer()
		self.timer.callback.append(self.lookup)

	def applySkin(self, desktop, parent):
		attribs = []
		for attrib, value in self.skinAttributes:
			if attrib == "fields":
				self.fields = tuple(f.strip() for f in value.split(",") if f.strip())
			elif attrib == "mode":
				self.mode = "card" if value == "card" else "line"
			elif attrib == "labelColor":
				self.labelColor = Hex2strColor(parseColor(value).argb())
			elif attrib == "delay":
				try:
					self.delay = max(0, int(value))
				except ValueError:
					pass
			else:
				if attrib == "foregroundColor":
					self.valueColor = Hex2strColor(parseColor(value).argb())
				attribs.append((attrib, value))
		self.skinAttributes = attribs
		return Renderer.applySkin(self, desktop, parent)

	def preWidgetRemove(self, instance):
		self.timer.stop()
		posters.cancel(self.onMeta)

	def eventName(self):
		src = self.source
		try:
			if hasattr(src, "event"):
				event = src.event
				return event and event.getEventName() or ""
			service = getattr(src, "service", None)
			info = service and hasattr(service, "info") and service.info()
			return info and info.getName() or ""
		except Exception:
			return ""

	def changed(self, what):
		if what[0] == self.CHANGED_CLEAR:
			self.timer.stop()
			self.wantedName = None
			self.text = ""
			return
		name = self.eventName()
		if name == self.wantedName:
			return
		self.wantedName = name
		self.text = ""
		self.timer.stop()
		if name:
			if self.delay:
				self.timer.start(self.delay, True)
			else:
				self.lookup()

	def lookup(self):
		if self.suspended:  # screen hidden: do the work when it is shown
			self.pendingLookup = True
			return
		self.pendingLookup = False
		if not self.wantedName:
			return
		posters.cancel(self.onMeta)
		kind = "details" if any(f in DETAIL_FIELDS for f in self.fields) else "meta"
		self.wantedTitle = posters.request(self.wantedName, self.onMeta, kind=kind)

	def onMeta(self, title, meta):
		if title != self.wantedTitle:
			return
		if not meta:
			self.text = ""
		elif self.mode == "card":
			self.text = formatCard(meta, self.fields, self.arabic, self.labelColor, self.valueColor)
		else:
			self.text = formatInfo(meta, self.fields, self.arabic)

	def onShow(self):
		Renderer.onShow(self)
		if getattr(self, "pendingLookup", False):
			self.lookup()
