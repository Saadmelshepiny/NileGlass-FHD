# -*- coding: utf-8 -*-
# NileGlass FHD - TMDB rating as stars.
#
#   <ePixmap pixmap="NileGlass_FHD/ui/stars_bg.png" position="x,y" size="200,36" alphatest="blend"/>
#   <widget source="session.Event_Now" render="NGStars" pixmap="NileGlass_FHD/ui/stars.png"
#           position="x,y" size="200,36" transparent="1" zPosition="1"/>
#
# Uses the cached TMDB metadata (rating 0-10 -> 0-100 %). Hidden when unknown.

from enigma import eSlider, eTimer

from Components.Renderer.Renderer import Renderer
from Components.NileGlassCore import posters


class NGStars(Renderer):
	GUI_WIDGET = eSlider

	def __init__(self):
		Renderer.__init__(self)
		self.wantedName = None
		self.wantedTitle = None
		self.timer = eTimer()
		self.timer.callback.append(self.lookup)

	def postWidgetCreate(self, instance):
		instance.setRange(0, 100)
		instance.setValue(0)
		instance.hide()

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
		if not self.instance:
			return
		name = "" if what[0] == self.CHANGED_CLEAR else self.eventName()
		if name == self.wantedName:
			return
		self.wantedName = name
		self.timer.stop()
		self.instance.hide()
		if name:
			self.timer.start(300, True)

	def lookup(self):
		if self.suspended:  # screen hidden: do the work when it is shown
			self.pendingLookup = True
			return
		self.pendingLookup = False
		if self.wantedName:
			posters.cancel(self.onMeta)
			self.wantedTitle = posters.request(self.wantedName, self.onMeta, kind="meta")

	def onMeta(self, title, meta):
		if not self.instance or title != self.wantedTitle:
			return
		rating = (meta or {}).get("rating") or 0
		if rating > 0:
			self.instance.setValue(int(round(rating * 10)))
			self.instance.show()
		else:
			self.instance.hide()

	def onShow(self):
		Renderer.onShow(self)
		if getattr(self, "pendingLookup", False):
			self.lookup()
