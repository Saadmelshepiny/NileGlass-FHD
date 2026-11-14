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
#   sport="show"    keep looking for a poster during matches / sport (by
#                   default sport events get no film poster: TMDB has none
#                   and would guess a wrong film; setting "smart_sport")
#
# The widget hides itself when no poster is available, so the layout stays
# clean.  Disk and network work is done by Components.NileGlassCore in
# background threads - this file only runs cheap code on the UI thread.

import os
from time import time

from enigma import eEPGCache, eServiceCenter, eServiceReference, ePixmap, eTimer, BT_SCALE, BT_KEEP_ASPECT_RATIO, BT_HALIGN_CENTER, BT_VALIGN_CENTER

from Components.Renderer.Renderer import Renderer
from Components.NileGlassCore import posters, isSportEvent, isSportTitle, isNewsEvent, upcomingEvents
from Tools.Directories import SCOPE_CURRENT_SKIN, resolveFilename

# Decoded pictures of the last posters shown, shared by all poster widgets:
# moving back and forth in a list shows them again without decoding the
# JPEG on the UI thread every time.  The "no poster" picture is decoded once.
_PIX_MAX = 24
_pix = {}


def _pixmap(path):
	try:
		mtime = os.path.getmtime(path)
	except OSError:
		return None
	hit = _pix.pop(path, None)
	if hit and hit[0] == mtime:
		_pix[path] = hit            # most recent last
		return hit[1]
	try:
		from Tools.LoadPixmap import LoadPixmap
		pm = LoadPixmap(path, cached=False)
	except Exception:
		pm = None
	if pm is not None:
		_pix[path] = (mtime, pm)
		while len(_pix) > _PIX_MAX:
			_pix.pop(next(iter(_pix)))
	return pm


class NGPoster(Renderer):
	GUI_WIDGET = ePixmap

	def __init__(self):
		Renderer.__init__(self)
		self.delay = 250
		self.prefetch = False
		self.kind = "poster"
		self.eventIndex = 0
		self.fallback = None
		self.piconFallback = False   # no poster: the channel's picon instead of the empty frame
		self.sportAware = True
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
				self.kind = value if value in ("backdrop", "thumb") else "poster"
			elif attrib == "eventIndex":
				try:
					self.eventIndex = max(0, int(value))
				except ValueError:
					pass
			elif attrib == "picon":
				self.piconFallback = value.lower() in ("1", "true", "yes")
			elif attrib == "fallback":
				path = resolveFilename(SCOPE_CURRENT_SKIN, value)
				self.fallback = path if path and os.path.isfile(path) else None
			elif attrib == "sport":
				self.sportAware = value.lower() != "show"
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
		events = upcomingEvents(ref.toString())
		if events and events[0][0] <= time():
			events = events[1:]
		i = self.eventIndex - 1
		return (events[i][2] or "") if 0 <= i < len(events) else ""

	def channelName(self):
		try:
			src = self.source
			ref = getattr(src, "serviceref", None) or getattr(src, "service", None)
			if not isinstance(ref, eServiceReference):
				import NavigationInstance
				ref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()
			info = ref and eServiceCenter.getInstance().info(ref)
			return info and info.getName(ref) or ""
		except Exception:
			return ""

	def eventName(self):
		src = self.source
		sport = self.sportAware and posters.skipSport
		if self.eventIndex:
			name = self.upcomingName()
			return "" if sport and isSportTitle(name) else name
		try:
			if hasattr(src, "event"):
				event = src.event
				if event and (sport or posters.skipSport):
					ch = self.channelName()
					if (sport and isSportEvent(event, ch)) or isNewsEvent(event, ch):
						return ""
				return event and event.getEventName() or ""
			# Sources without EPG (media player / recordings / IPTV): use the
			# title of what is playing.
			service = getattr(src, "service", None)
			info = service and hasattr(service, "info") and service.info()
			return info and info.getName() or ""
		except Exception:
			return ""

	def serviceRef(self):
		try:
			src = self.source
			ref = getattr(src, "serviceref", None) or getattr(src, "service", None)
			if not isinstance(ref, eServiceReference):
				import NavigationInstance
				ref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()
			return ref
		except Exception:
			return None

	def piconPath(self):
		if not self.piconFallback:
			return None
		try:
			from Components.Renderer.Picon import getPiconName
			ref = self.serviceRef()
			return getPiconName(ref.toString()) if ref else None
		except Exception:
			return None

	def offHere(self):
		"""posters of the channel list turned off in the settings (faster browsing)"""
		if self.source.__class__.__name__ != "ServiceEvent":
			return False
		try:
			from Components.NileGlassCore import confBool
			return not confBool("extras", "cl_posters", True)
		except Exception:
			return False

	def changed(self, what):
		if not self.instance:
			return
		if self.offHere():
			self.timer.stop()
			self.instance.hide()
			return
		if what[0] == self.CHANGED_CLEAR:
			self.timer.stop()
			self.wantedName = None
			self.hidePoster()
			return
		if self.eventIndex and self.delay:
			# "coming up" posters: no EPG work while the list is still moving;
			# the name is looked up once the selection rests
			self.timer.stop()
			self.timer.start(self.delay, True)
			self.deferName = True
			return
		self.deferName = False
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
		if getattr(self, "deferName", False):
			self.deferName = False
			name = self.eventName()
			if name == self.wantedName and self.shownPath:
				return
			self.wantedName = name
			if not name:
				self.hidePoster()
				return
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
			if (self.fallback or self.piconFallback) and not self.prefetch:
				path = self.piconPath() or self.fallback
			if not path:
				self.hidePoster()
				return
		if path != self.shownPath:
			self.setPicture(path)
		self.instance.show()

	def setPicture(self, path):
		pm = _pixmap(path)
		if pm is not None:
			self.instance.setPixmap(pm)
		else:
			self.instance.setPixmapFromFile(path)
		self.shownPath = path

	def hidePoster(self):
		self.wantedTitle = None
		if not self.instance:
			return
		fb = (self.piconPath() or (self.fallback if self.wantedName else None)) if not self.prefetch else None
		if fb:
			if self.shownPath != fb:
				self.setPicture(fb)
			self.instance.show()
		else:
			self.instance.hide()

	def onShow(self):
		Renderer.onShow(self)
		if getattr(self, "pendingLookup", False):
			self.lookup()
