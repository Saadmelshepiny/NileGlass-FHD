# -*- coding: utf-8 -*-
# NileGlass FHD - "Tonight" screen: films and matches of tonight on your
# channels, from the file of the Saad EPG plugin.
#
#   OK / green : zap to the channel     red    : record (timer)
#   yellow     : films <-> matches      blue   : favourites only / all
#   left/right : page                   menu   : choose another channel of the same item
#
# Speed: the data is already in memory (Components.NileGlassCore.tonight),
# posters and picons are found and read from disk in a worker thread; the UI
# thread only shows files that are already in the page cache.

import os
import threading
import time

from enigma import eEPGCache, eServiceCenter, eServiceReference

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Tools.LoadPixmap import LoadPixmap

from Components.NileGlassCore import tonight, posters, callInUiThread, log
from Components.Converter.NGTonight import channelName, itemName

PICON_DIRS = ("/usr/share/enigma2/picon", "/media/hdd/picon", "/media/usb/picon", "/media/mmc/picon", "/picon", "/data/picon")


def findPicon(ch):
	"""Picon file of a channel (worker thread only - the disk may sleep)."""
	names = []
	if ch.get("picon"):
		names.append(ch["picon"])
	parts = ch["sref"].rstrip(":").split(":")[:10]
	if len(parts) >= 10:
		names.append("_".join(parts))
		if parts[2] != "1":  # many picon sets only have the type-1 name
			names.append("_".join(parts[:2] + ["1"] + parts[3:]))
	for d in PICON_DIRS:
		if not os.path.isdir(d):
			continue
		for n in names:
			p = os.path.join(d, n + ".png")
			if os.path.isfile(p):
				return p
	return ""


def warm(path):
	try:
		with open(path, "rb") as f:
			f.read()
		return path
	except Exception:
		return ""


def findBouquet(ref):
	"""The TV bouquet that holds `ref`, so the channel list follows the zap."""
	sc = eServiceCenter.getInstance()
	want = ref.toCompareString() if hasattr(ref, "toCompareString") else ref.toString()
	root = eServiceReference('1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.tv" ORDER BY bouquet')
	bouquets = sc.list(root)
	for b in (bouquets.getContent("R", True) if bouquets else None) or []:
		if not (b.flags & eServiceReference.isDirectory):
			continue
		lst = sc.list(b)
		for r in (lst.getContent("R", True) if lst else None) or []:
			if (r.toCompareString() if hasattr(r, "toCompareString") else r.toString()) == want:
				return b
	return None


class NileGlassTonight(Screen):
	def __init__(self, session, kind="film"):
		Screen.__init__(self, session)
		self.kind = kind if kind in ("film", "match") else "film"
		self.favOnly = False
		self.items = []
		self.picons = {}      # key -> pixmap (loaded on the UI thread from a warmed file)
		self.piconPaths = {}  # key -> path or ""
		self.shownPoster = None
		self.wantPoster = None
		self.diskBusy = False
		self["list"] = List([])
		self["poster"] = Pixmap()
		self["picon"] = Pixmap()
		for name in ("title", "info", "when", "channel", "desc", "badge", "versus", "status", "empty", "tab_films", "tab_matches"):
			self[name] = Label("")
		self["tab_films_line"] = Label("")
		self["tab_matches_line"] = Label("")
		self["key_red"] = StaticText("تسجيل")
		self["key_green"] = StaticText("تحويل")
		self["key_yellow"] = StaticText("")
		self["key_blue"] = StaticText("")
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "MenuActions"], {
			"ok": self.zap, "cancel": self.close,
			"red": self.record, "green": self.zap, "yellow": self.toggleKind, "blue": self.toggleFav,
			"up": self.up, "down": self.down, "left": self.pageUp, "right": self.pageDown,
			"menu": self.chooseChannel,
		}, -1)
		self["list"].onSelectionChanged.append(self.selectionChanged)
		self.onLayoutFinish.append(self.fill)
		self.onClose.append(self.cleanup)
		tonight.addListener(self.fill)
		tonight.refresh(force=True)
		self.setTitle("الليلة على قنواتك")

	def cleanup(self):
		tonight.removeListener(self.fill)
		if posters is not None:
			posters.cancel(self.gotTmdbPoster)

	# ---------------------------------------------------------------- list
	def up(self):
		self["list"].up()

	def down(self):
		self["list"].down()

	def pageUp(self):
		self["list"].pageUp()

	def pageDown(self):
		self["list"].pageDown()

	def toggleKind(self):
		self.kind = "match" if self.kind == "film" else "film"
		self.fill()

	def toggleFav(self):
		self.favOnly = not self.favOnly
		self.fill()

	def fill(self):
		now = time.time()
		films = tonight.items("film", now)
		matches = tonight.items("match", now)
		if self.favOnly:
			films = [x for x in films if x["fav"]]
			matches = [x for x in matches if x["fav"]]
		self.items = films if self.kind == "film" else matches
		self["tab_films"].setText("أفلام الليلة  (%d)" % len(films))
		self["tab_matches"].setText("الماتشات  (%d)" % len(matches))
		self["tab_films_line"].setVisible(self.kind == "film")
		self["tab_matches_line"].setVisible(self.kind == "match")
		self["key_yellow"].setText("الماتشات" if self.kind == "film" else "الأفلام")
		self["key_blue"].setText("الكل" if self.favOnly else "المفضلة فقط")
		rows = [self.row(x, now) for x in self.items]
		self["list"].setList(rows)
		st = tonight.status()
		if not st["found"]:
			self["empty"].setText("ملف «الليلة» مش موجود.\nشغّل بلوجين Saad EPG مرة\n(أدوات متقدمة ← ملف \"الليلة\" للسكين).")
		elif not rows:
			self["empty"].setText("مفيش %s في الفترة دي%s." % ("أفلام" if self.kind == "film" else "ماتشات", " على المفضلة" if self.favOnly else ""))
		else:
			self["empty"].setText("")
		gen = st.get("generated")
		self["status"].setText(("آخر تحديث للدليل  " + time.strftime("%H:%M", time.localtime(gen)) if gen else "") +
			("   تنبيه: " + st["error"] if st.get("error") and st["error"] != "no file" else ""))
		self.loadPicons()
		self.selectionChanged()

	def row(self, x, now):
		start = time.strftime("%H:%M", time.localtime(x["start"]))
		ch = x["channels"][0] if x["channels"] else None
		chName = channelName(ch) if ch else ""
		more = len(x["channels"]) - 1
		if x["kind"] == "film":
			bits = [chName + (("  +%d" % more) if more > 0 else "")]
			if x.get("year"):
				bits.append(str(x["year"]))
			if x.get("rating"):
				try:
					bits.append("%.1f/10" % float(x["rating"]))
				except (TypeError, ValueError):
					pass
			if x.get("cat") and x["cat"].lower() not in ("movie", "film", "فيلم", "أفلام", "افلام"):
				bits.append(x["cat"])
			line2 = "  •  ".join(filter(None, bits))
		else:
			line2 = "  •  ".join(filter(None, [chName + (("  +%d" % more) if more > 0 else ""), x.get("comp")]))
		badge = ""
		if x["start"] <= now:
			badge = "مباشر" if x["kind"] == "match" else "الآن"
		elif x["fav"]:
			badge = "مفضلة"
		key = ch["key"] if ch else ""
		return (start, itemName(x), line2, badge, self.picons.get(key), x)

	# ---------------------------------------------------------------- details
	def current(self):
		cur = self["list"].getCurrent()
		return cur[5] if cur else None

	def selectionChanged(self):
		x = self.current()
		if not x:
			for n in ("title", "info", "when", "channel", "desc", "badge", "versus"):
				self[n].setText("")
			self["poster"].hide()
			self["picon"].hide()
			return
		now = time.time()
		t1 = time.strftime("%H:%M", time.localtime(x["start"]))
		t2 = time.strftime("%H:%M", time.localtime(x["stop"]))
		left = int((x["start"] - now) // 60)
		when = "%s - %s" % (t1, t2)
		if left > 0:
			when += "\nبعد %s" % ("%d دقيقة" % left if left < 60 else "%d:%02d ساعة" % (left // 60, left % 60))
		else:
			when += "\nباقي %d دقيقة" % max(0, int((x["stop"] - now) // 60))
		self["when"].setText(when)
		self["title"].setText(itemName(x) if x["kind"] == "film" else (x.get("comp") or x.get("title") or ""))
		names = [channelName(c) for c in x["channels"]]
		self["channel"].setText(names[0] + (("\nوعلى: " + "، ".join(names[1:4])) if len(names) > 1 else "") if names else "")
		if x["kind"] == "film":
			info = []
			if x.get("en") and x["en"] != x["title"]:
				info.append(x["en"])
			if x.get("year"):
				info.append(str(x["year"]))
			if x.get("rating"):
				try:
					info.append("التقييم %.1f/10" % float(x["rating"]))
				except (TypeError, ValueError):
					pass
			self["info"].setText("  •  ".join(info))
			self["versus"].setText("")
			self["desc"].setText(x.get("desc") or x.get("short") or "")
		else:
			self["info"].setText(("النتيجة  " + x["score"]) if x.get("score") else ("العرض الأول" if x.get("first") else "إعادة"))
			self["versus"].setText("%s\n×\n%s" % (x.get("home") or "", x.get("away") or "") if x.get("home") else (x.get("title") or ""))
			self["desc"].setText(x.get("title") or "")
			self["poster"].hide()
		self["badge"].setText(self["list"].getCurrent()[3])
		ch = x["channels"][0] if x["channels"] else None
		pm = self.picons.get(ch["key"]) if ch else None
		if pm is not None and self["picon"].instance:
			self["picon"].instance.setPixmap(pm)
			self["picon"].show()
		else:
			self["picon"].hide()
		if x["kind"] == "film":
			self.showPoster(x)

	# ---------------------------------------------------------------- posters
	def showPoster(self, x):
		self.wantPoster = x["id"]
		self["poster"].hide()
		path = x.get("poster") or ""
		threading.Thread(target=self._posterThread, args=(x, path), name="NileGlass-tonight-img", daemon=True).start()

	def _posterThread(self, x, path):
		ok = path and path.startswith("/") and os.path.isfile(path) and warm(path)
		callInUiThread(self._posterReady, x, path if ok else "")

	def _posterReady(self, x, path):
		if self.wantPoster != x["id"] or not self["poster"].instance:
			return
		if path:
			self["poster"].instance.setPixmapFromFile(path)
			self["poster"].show()
		elif posters is not None:  # not on disk: ask the skin's TMDB service
			posters.cancel(self.gotTmdbPoster)
			self.tmdbFor = x["id"]
			if not posters.request(x.get("en") or x["title"], self.gotTmdbPoster):
				posters.request(x["title"], self.gotTmdbPoster)

	def gotTmdbPoster(self, title, path):
		if path and getattr(self, "tmdbFor", None) == self.wantPoster and self["poster"].instance:
			self["poster"].instance.setPixmapFromFile(path)
			self["poster"].show()

	# ---------------------------------------------------------------- picons
	def loadPicons(self):
		todo = {}
		for x in self.items:
			for c in x["channels"][:1]:
				if c["key"] not in self.piconPaths:
					todo[c["key"]] = c
		if todo and not self.diskBusy:
			self.diskBusy = True
			threading.Thread(target=self._piconThread, args=(list(todo.items()),), name="NileGlass-tonight-picon", daemon=True).start()

	def _piconThread(self, todo):
		found = {}
		for key, ch in todo:
			try:
				p = findPicon(ch)
				found[key] = warm(p) if p else ""
			except Exception:
				found[key] = ""
		callInUiThread(self._piconsReady, found)

	def _piconsReady(self, found):
		self.diskBusy = False
		self.piconPaths.update(found)
		changed = False
		for key, p in found.items():
			if p:
				try:
					self.picons[key] = LoadPixmap(p, cached=True)
					changed = True
				except Exception:
					pass
		if changed:
			idx = self["list"].getIndex()
			now = time.time()
			self["list"].updateList([self.row(x, now) for x in self.items])
			if idx is not None:
				self["list"].setIndex(idx)
			self.selectionChanged()
		self.loadPicons()  # items added meanwhile

	# ---------------------------------------------------------------- actions
	def chooseChannel(self):
		x = self.current()
		if not x or len(x["channels"]) < 2:
			return
		self.session.openWithCallback(lambda ch: ch and self.zapTo(ch[1]), ChoiceBox, title=itemName(x),
			list=[(channelName(c), c) for c in x["channels"]])

	def zap(self):
		x = self.current()
		if x and x["channels"]:
			self.zapTo(x["channels"][0])

	def zapTo(self, ch):
		ref = eServiceReference(ch["sref"])
		try:
			from Screens.InfoBar import InfoBar
			ib = InfoBar.instance
			bouquet = findBouquet(ref) if ib else None
			if ib and bouquet is not None:
				ib.zapToService(ref, bouquet=bouquet)
			else:
				self.session.nav.playService(ref)
		except Exception as err:
			log("tonight zap:", err)
			self.session.nav.playService(ref)
		self.close()

	def record(self):
		x = self.current()
		if not x or not x["channels"]:
			return
		ch = x["channels"][0]
		if x["stop"] < time.time():
			return
		try:
			from ServiceReference import ServiceReference
			from Screens.TimerEntry import addTimerFromEvent, checkForConflicts, TimerEntry
			from RecordTimer import RecordTimerEntry
			from Components.UsageConfig import preferredTimerPath
			from Components.config import config
			service = ServiceReference(ch["sref"])
			event = None
			try:  # the real EPG event gives the right name, id and times
				event = eEPGCache.getInstance().lookupEventTime(eServiceReference(ch["sref"]), int(x["start"]) + 120)
			except Exception:
				event = None
			if event is not None and abs(event.getBeginTime() - x["start"]) < 1800:
				addTimerFromEvent(self.session, self.timerAdded, event, service)
				return
			before = config.recording.margin_before.value * 60
			after = config.recording.margin_after.value * 60
			timer = RecordTimerEntry(service, int(x["start"]) - before, int(x["stop"]) + after, itemName(x), x.get("short") or x.get("comp") or "", None,
				checkOldTimers=True, dirname=preferredTimerPath())
			self.session.openWithCallback(lambda answer: checkForConflicts(self.session, self.timerAdded, answer[1]) if answer[0] else None, TimerEntry, timer)
		except Exception as err:
			log("tonight record:", err)
			self.session.open(MessageBox, "تعذّر إضافة التسجيل:\n%s" % err, MessageBox.TYPE_ERROR, timeout=8)

	def timerAdded(self, timer):
		self.session.open(MessageBox, "تمت إضافة التسجيل:\n%s" % timer.name, MessageBox.TYPE_INFO, timeout=4)
