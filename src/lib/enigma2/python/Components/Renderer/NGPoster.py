# -*- coding: utf-8 -*-
# NileGlass FHD - event poster renderer.
#
# Usage in skin.xml (any source that offers an EPG event works:
# session.Event_Now, session.Event_Next, ServiceEvent, Event, Service ...):
#
#   <widget source="session.Event_Now" render="NGPoster" position="50,540" size="170,255"
#           zPosition="5" borderWidth="1" borderColor="#60ffffff" />
#
# Optional attributes:
#   delay="250"     debounce in ms while the user scrolls through lists
#   prefetch="1"    download only, never display (e.g. for session.Event_Next)
#   kind="backdrop" show the wide TMDB backdrop instead of the poster
#   eventIndex="2"  with session.CurrentService / ServiceEvent: poster of the
#                   2nd coming programme (taken from the in-memory EPG cache)
#   fallback="NileGlass_FHD/ui/noposter.png"  shown instead of hiding
#
# The widget hides itself when no poster is available, so the layout stays
# clean.  Disk and network work is done by Components.NileGlassCore in
# background threads - this file only runs cheap code on the UI thread.

import os
from time import time

from enigma import eEPGCache, eServiceReference, ePixmap, eTimer, BT_SCALE, BT_KEEP_ASPECT_RATIO, BT_HALIGN_CENTER, BT_VALIGN_CENTER

from Components.Renderer.Renderer import Renderer
from Components.NileGlassCore import posters
from Tools.Directories import SCOPE_CURRENT_SKIN, resolveFilename


class NGPoster(Renderer):
	GUI_WIDGET = ePixmap

	def __init__(self):
		Renderer.__init__(self)
		self.delay = 250
		self.prefetch = False
		self.kind = "poster"
		self.eventIndex = 0
		self.fallback = None
		self.wantedName = None     # raw event name we want to show
		self.wantedTitle = None    # cleaned title we asked the service for
		self.shownPath = None
		self.timer = eTimer()
		self.timer.callback.append(self.lookup)

	def applySkin(self, desktop, parent):
		attribs = []
		for attrib, value in self.skinAttributes:
			if attrib == "delay":
				try:
					self.delay = max(0, int(value))
				except ValueError:
					pass
			elif attrib == "kind":
				self.kind = "backdrop" if value == "backdrop" else "poster"
			elif attrib == "eventIndex":
				try:
					self.eventIndex = max(0, int(value))
				except ValueError:
					pass
			elif attrib == "fallback":
				path = resolveFilename(SCOPE_CURRENT_SKIN, value)
				self.fallback = path if path and os.path.isfile(path) else None
			elif attrib == "prefetch":
				self.prefetch = value.lower() in ("1", "true", "yes")
			else:
				attribs.append((attrib, value))
		self.skinAttributes = attribs
		rc = Renderer.applySkin(self, desktop, parent)
		self.wantedName = None
		self.changed((self.CHANGED_DEFAULT,))
		return rc

	def postWidgetCreate(self, instance):
		instance.setPixmapScale(BT_SCALE | BT_KEEP_ASPECT_RATIO | BT_HALIGN_CENTER | BT_VALIGN_CENTER)
		instance.hide()

	def preWidgetRemove(self, instance):
		self.timer.stop()
		posters.cancel(self.onPoster)
		self.wantedName = None

	def upcomingName(self):
		src = self.source
		ref = getattr(src, "serviceref", None)
		if ref is None:
			ref = getattr(src, "service", None)
		if not isinstance(ref, eServiceReference) or not ref.valid():
			return ""
		try:
			events = eEPGCache.getInstance().lookupEvent(["BT", (ref.toString(), 0, -1, 24 * 60)]) or []
		except Exception:
			return ""
		if events and events[0][0] <= time():
			events = events[1:]
		i = self.eventIndex - 1
		return (events[i][1] or "") if 0 <= i < len(events) else ""

	def eventName(self):
		src = self.source
		if self.eventIndex:
			return self.upcomingName()
		try:
			if hasattr(src, "event"):
				event = src.event
				return event and event.getEventName() or ""
			# Sources without EPG (media player / recordings / IPTV): use the
			# title of what is playing.
			service = getattr(src, "service", None)
			info = service and hasattr(service, "info") and service.info()
			return info and info.getName() or ""
		except Exception:
			return ""

	def changed(self, what):
		if not self.instance:
			return
		if what[0] == self.CHANGED_CLEAR:
			self.timer.stop()
			self.wantedName = None
			self.hidePoster()
			return
		name = self.eventName()
		if name == self.wantedName:
			return
		self.wantedName = name
		self.timer.stop()
		if not name:
			self.hidePoster()
			return
		if self.delay:
			self.timer.start(self.delay, True)
		else:
			self.lookup()

	def lookup(self):
		if self.suspended:  # screen hidden: do the work when it is shown
			self.pendingLookup = True
			return
		self.pendingLookup = False
		if not self.instance or not self.wantedName:
			return
		posters.cancel(self.onPoster)
		title = posters.request(self.wantedName, None if self.prefetch else self.onPoster, prefetch=self.prefetch, kind=self.kind)
		self.wantedTitle = title
		if not title:
			self.hidePoster()

	def onPoster(self, title, path):
		# Runs on the UI thread (scheduled by NileGlassCore).
		if not self.instance or title != self.wantedTitle:
			return
		if not path:
			if self.fallback and not self.prefetch:
				path = self.fallback
			else:
				self.hidePoster()
				return
		if path != self.shownPath:
			self.instance.setPixmapFromFile(path)
			self.shownPath = path
		self.instance.show()

	def hidePoster(self):
		self.wantedTitle = None
		if not self.instance:
			return
		if self.fallback and not self.prefetch and self.wantedName:
			if self.shownPath != self.fallback:
				self.instance.setPixmapFromFile(self.fallback)
				self.shownPath = self.fallback
			self.instance.show()
		else:
			self.instance.hide()

	def onShow(self):
		Renderer.onShow(self)
		if getattr(self, "pendingLookup", False):
			self.lookup()
