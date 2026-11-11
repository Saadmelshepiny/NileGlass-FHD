# -*- coding: utf-8 -*-
# NileGlass FHD - full film page: backdrop, poster, ratings, story, cast with
# photos and every showing of the film on your channels this week.
#   up/down : choose a showing     OK / green : zap     red : record
# All pictures and data are fetched in background threads.

import os
import threading
import time

from enigma import eEPGCache, eServiceReference

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen

from Components.Converter.NGDate import formatDate
from Components.NileGlassCore import posters, formatInfo, cleanTitle, callInUiThread, log, GENRES_AR

CAST = 6


def channelName(ref):
	try:
		from ServiceReference import ServiceReference
		return ServiceReference(ref).getServiceName().replace("\x86", "").replace("\x87", "")
	except Exception:
		return ""


class NileGlassFilm(Screen):
	def __init__(self, session, name, ref=None, begin=None):
		Screen.__init__(self, session)
		self.name = name or ""
		self.title_ = cleanTitle(self.name) or self.name
		for n in ("title", "original", "facts", "ratings", "story", "crew", "showings_title"):
			self[n] = Label("")
		self["backdrop"] = Pixmap()
		self["poster"] = Pixmap()
		for i in range(CAST):
			self["cast%d" % i] = Pixmap()
			self["castname%d" % i] = Label("")
		self["showings"] = List([])
		self["key_red"] = StaticText("تسجيل")
		self["key_green"] = StaticText("تحويل")
		self["key_yellow"] = StaticText("")
		self["key_blue"] = StaticText("")
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions"], {
			"ok": self.zap, "green": self.zap, "red": self.record, "cancel": self.close,
			"up": lambda: self["showings"].up(), "down": lambda: self["showings"].down()}, -1)
		self.onLayoutFinish.append(self.load)
		self.onClose.append(self.cleanup)
		self.setTitle("صفحة الفيلم")

	def cleanup(self):
		for cb in (self.gotMeta, self.gotPoster, self.gotBackdrop):
			posters.cancel(cb)

	def load(self):
		self["title"].setText(self.title_)
		self["backdrop"].hide()
		self["poster"].hide()
		for i in range(CAST):
			self["cast%d" % i].hide()
		posters.request(self.name, self.gotPoster)
		posters.request(self.name, self.gotBackdrop, kind="backdrop")
		posters.request(self.name, self.gotMeta, kind="details")
		self.findShowings()

	# ---------------------------------------------------------------- data
	def gotPoster(self, title, path):
		if path and self["poster"].instance:
			self["poster"].instance.setPixmapFromFile(path)
			self["poster"].show()

	def gotBackdrop(self, title, path):
		if path and self["backdrop"].instance:
			self["backdrop"].instance.setPixmapFromFile(path)
			self["backdrop"].show()

	def gotMeta(self, title, meta):
		if not meta:
			self["story"].setText("لا توجد تفاصيل لهذا البرنامج على TMDB.")
			return
		d = meta.get("details") or {}
		self["title"].setText(meta.get("name") or self.title_)
		self["original"].setText(d.get("original", "") if d.get("original") != meta.get("name") else "")
		facts = []
		if meta.get("year"):
			facts.append(str(meta["year"]))
		if d.get("runtime"):
			facts.append("%d دقيقة" % d["runtime"])
		g = [GENRES_AR[i] for i in meta.get("genres") or [] if i in GENRES_AR][:3]
		if g:
			facts.append("، ".join(g))
		self["facts"].setText("   •   ".join(facts))
		rt = []
		if meta.get("rating"):
			rt.append("TMDB  %.1f/10" % meta["rating"])
		if d.get("imdb"):
			rt.append("IMDb  %s/10" % d["imdb"])
		self["ratings"].setText("     ".join(rt))
		self["story"].setText(meta.get("overview") or "")
		crew = []
		if d.get("director"):
			crew.append("إخراج: " + d["director"])
		if d.get("country"):
			crew.append("البلد: " + d["country"])
		if d.get("awards"):
			crew.append("الجوائز: " + d["awards"])
		self["crew"].setText("\n".join(crew))
		people = (d.get("people") or [])[:CAST]
		for i, p in enumerate(people):
			self["castname%d" % i].setText(p[0] + (("\n" + p[1]) if p[1] else ""))
		threading.Thread(target=self._photos, args=(people,), name="NileGlass-film", daemon=True).start()

	def _photos(self, people):
		for i, p in enumerate(people):
			try:
				path = posters.personImage(p[2]) if len(p) > 2 else None
			except Exception as err:
				log("actor photo:", err)
				path = None
			if path:
				callInUiThread(self._photo, i, path)

	def _photo(self, i, path):
		w = self["cast%d" % i]
		if w.instance:
			w.instance.setPixmapFromFile(path)
			w.show()

	def findShowings(self):
		rows = []
		try:
			res = eEPGCache.getInstance().search(("RIBDT", 60, eEPGCache.EXAKT_TITLE_SEARCH, self.name, eEPGCache.NO_CASE_CHECK)) or []
		except Exception as err:
			log("film search:", err)
			res = []
		now = time.time()
		seen = set()
		for ref, eid, begin, dur, title in sorted(res, key=lambda x: x[2]):
			if begin + (dur or 0) < now or (ref, begin) in seen:
				continue
			seen.add((ref, begin))
			ch = channelName(eServiceReference(ref))
			if not ch:
				continue
			day = formatDate("{A} {d}/{m}", begin)
			live = "  الآن" if begin <= now else ""
			rows.append(("%s  %s%s" % (day, time.strftime("%H:%M", time.localtime(begin)), live), ch, ref, eid, begin))
		self["showings"].setList(rows[:40])
		self["showings_title"].setText("مواعيد العرض على قنواتك (%d)" % len(rows) if rows else "لا توجد مواعيد عرض قادمة في الدليل")

	# ---------------------------------------------------------------- actions
	def current(self):
		return self["showings"].getCurrent()

	def zap(self):
		cur = self.current()
		if not cur:
			return self.close()
		try:
			from .tonight import findBouquet
			from Screens.InfoBar import InfoBar
			ref = eServiceReference(cur[2])
			b = findBouquet(ref)
			if InfoBar.instance and b is not None:
				InfoBar.instance.zapToService(ref, bouquet=b)
			else:
				self.session.nav.playService(ref)
		except Exception as err:
			log("film zap:", err)
		self.close()

	def record(self):
		cur = self.current()
		if not cur:
			return
		try:
			from ServiceReference import ServiceReference
			from Screens.TimerEntry import addTimerFromEvent
			event = eEPGCache.getInstance().lookupEventId(eServiceReference(cur[2]), cur[3])
			if event is not None:
				addTimerFromEvent(self.session, None, event, ServiceReference(cur[2]))
		except Exception as err:
			log("film record:", err)
