# -*- coding: utf-8 -*-
# NileGlass FHD - "Coming up": browse the next programmes of the channel you
# are watching with big posters and read their full EPG.
#   left/right : previous / next programme      red : record (timer)
#   OK / exit  : close
# EPG comes from enigma2's in-memory cache; posters and film data come from
# the skin's background service, so moving through the row never blocks.

import time

from enigma import eEPGCache

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen

from Components.NileGlassCore import posters, formatCard, formatInfo, cleanTitle, log

SLOTS = 6


class NileGlassUpcoming(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.events = []
		self.index = 0
		self.first = 0
		self.meta = {}
		for i in range(SLOTS):
			self["poster%d" % i] = Pixmap()
			self["time%d" % i] = Label("")
			self["sel%d" % i] = Label("")
		for n in ("title", "when", "info", "card", "desc", "channel", "count"):
			self[n] = Label("")
		self["key_red"] = StaticText("تسجيل")
		self["key_yellow"] = StaticText("")
		self["key_blue"] = StaticText("")
		self["key_green"] = StaticText("صفحة الفيلم")
		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "ColorActions", "InfoActions"], {
			"ok": self.film, "green": self.film, "info": self.film, "cancel": self.close, "left": self.left, "right": self.right,
			"up": self.left, "down": self.right, "red": self.record}, -1)
		self.onLayoutFinish.append(self.load)
		self.onClose.append(self.cleanup)
		self.setTitle("البرامج القادمة")

	def cleanup(self):
		if posters is not None:
			posters.cancel(self.gotPoster)
			posters.cancel(self.gotMeta)

	def load(self):
		ref = self.session.nav.getCurrentlyPlayingServiceReference()
		self.ref = ref
		try:
			from ServiceReference import ServiceReference
			self["channel"].setText(ServiceReference(ref).getServiceName().replace("\x86", "").replace("\x87", "") if ref else "")
		except Exception:
			pass
		try:
			evs = eEPGCache.getInstance().lookupEvent(["IBDTSE", (ref.toString(), 0, -1, 24 * 60)]) or [] if ref else []
		except Exception as err:
			log("upcoming:", err)
			evs = []
		now = time.time()
		self.events = [e for e in evs if e and e[1] and e[3] and e[1] + (e[2] or 0) > now][:30]
		if self.events and self.events[0][1] <= now and len(self.events) > 1:
			self.index = 1  # start with the next programme
		self.refresh()

	# ---------------------------------------------------------------- moving
	def left(self):
		if self.index > 0:
			self.index -= 1
			self.refresh()

	def right(self):
		if self.index < len(self.events) - 1:
			self.index += 1
			self.refresh()

	def refresh(self):
		if not self.events:
			self["title"].setText("لا يوجد دليل برامج لهذه القناة")
			return
		if self.index < self.first:
			self.first = self.index
		elif self.index >= self.first + SLOTS:
			self.first = self.index - SLOTS + 1
		for i in range(SLOTS):
			n = self.first + i
			self["sel%d" % i].setVisible(n == self.index)
			if n < len(self.events):
				ev = self.events[n]
				self["time%d" % i].setText(time.strftime("%H:%M", time.localtime(ev[1])))
				self.askPoster(i, ev[3])
			else:
				self["time%d" % i].setText("")
				self["poster%d" % i].hide()
		self["count"].setText("%d / %d" % (self.index + 1, len(self.events)))
		self.showDetails()

	def askPoster(self, slot, name):
		self["poster%d" % slot].hide()
		title = cleanTitle(name)
		self["poster%d" % slot].wanted = title
		if posters is not None and title:
			posters.request(name, self.gotPoster)

	def gotPoster(self, title, path):
		if not path:
			return
		for i in range(SLOTS):
			w = self["poster%d" % i]
			if getattr(w, "wanted", None) == title and w.instance:
				w.instance.setPixmapFromFile(path)
				w.show()

	def showDetails(self):
		ev = self.events[self.index]
		begin, dur, name, short, ext = ev[1], ev[2] or 0, ev[3] or "", ev[4] or "", ev[5] or ""
		left = int((begin - time.time()) // 60)
		when = "%s - %s   •   %d دقيقة" % (time.strftime("%H:%M", time.localtime(begin)), time.strftime("%H:%M", time.localtime(begin + dur)), dur // 60)
		if left > 0:
			when += "   •   بعد %s" % ("%d دقيقة" % left if left < 60 else "%d:%02d ساعة" % (left // 60, left % 60))
		self["title"].setText(name)
		self["when"].setText(when)
		self["desc"].setText("\n".join(x for x in (short, ext) if x and x != name))
		self["info"].setText("")
		self["card"].setText("")
		self.wantedMeta = cleanTitle(name)
		if posters is not None and self.wantedMeta:
			posters.request(name, self.gotMeta, kind="details")

	def gotMeta(self, title, meta):
		if title != self.wantedMeta or not meta:
			return
		self["info"].setText(formatInfo(meta, ("year", "genres", "rating")))
		self["card"].setText(formatCard(meta, ("director", "cast", "country", "runtime", "imdb"), True, "\\c009aa3ae", "\\c00eef1f4"))

	def film(self):
		if self.events:
			from .film import NileGlassFilm
			ev = self.events[self.index]
			self.session.open(NileGlassFilm, ev[3], self.ref, ev[1])

	# ---------------------------------------------------------------- record
	def record(self):
		if not self.events or self.ref is None:
			return
		try:
			from ServiceReference import ServiceReference
			from Screens.TimerEntry import addTimerFromEvent
			event = eEPGCache.getInstance().lookupEventId(self.ref, self.events[self.index][0])
			if event is not None:
				addTimerFromEvent(self.session, None, event, ServiceReference(self.ref))
		except Exception as err:
			log("upcoming record:", err)
