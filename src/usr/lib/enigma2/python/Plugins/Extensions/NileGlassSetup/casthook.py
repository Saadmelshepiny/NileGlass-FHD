# -*- coding: utf-8 -*-
# NileGlass FHD - the main cast with photos in the event information screen
# (INFO).  Optional, off by default (setting "Cast in the INFO screen"): it
# costs one extra TMDB request per film and a few small photos.
#
# The screen gets five photo + name slots (cast_p0..4 / cast_n0..4); the skin
# places them, another skin simply has no such widgets.  Details and photos
# are fetched in the background and only shown if the same programme is
# still on screen.  Sport and news get no cast (no film behind them).

import threading

CAST = 5


def enabled():
	try:
		from Components.NileGlassCore import confBool, liteMode
		return confBool("extras", "cast", False) and not liteMode()
	except Exception:
		return False


class _Loader:
	def __init__(self, screen, name):
		self.screen, self.name = screen, name

	def alive(self):
		s = self.screen
		return getattr(s, "_ngCastName", None) == self.name and getattr(s, "instance", None) is not None

	def details(self, title, meta):
		if not self.alive():
			return
		people = ((meta or {}).get("details") or {}).get("people") or []
		people = [p for p in people if p and p[0]][:CAST]
		s = self.screen
		for i in range(CAST):
			n = s.get("cast_n%d" % i)
			if n is not None:
				n.setText(people[i][0] if i < len(people) else "")
		if "cast_title" in s:
			s["cast_title"].setText("الأبطال" if people else "")
		if people:
			threading.Thread(target=self._photos, args=(people,), name="NileGlass-cast", daemon=True).start()

	def _photos(self, people):
		from Components.NileGlassCore import posters, callInUiThread, log
		for i, p in enumerate(people):
			try:
				path = posters.personImage(p[2]) if len(p) > 2 and p[2] else None
			except Exception as err:
				log("cast photo:", err)
				path = None
			if path:
				callInUiThread(self._photo, i, path)

	def _photo(self, i, path):
		if not self.alive():
			return
		w = self.screen.get("cast_p%d" % i)
		try:
			if w is not None and w.instance:
				w.instance.setPixmapFromFile(path)
				w.show()
		except Exception:
			pass


def _clear(screen):
	for i in range(CAST):
		if "cast_p%d" % i in screen:
			screen["cast_p%d" % i].hide()
			screen["cast_n%d" % i].setText("")
	if "cast_title" in screen:
		screen["cast_title"].setText("")


def _load(screen, event):
	if "cast_p0" not in screen:
		return
	name = event.getEventName() if event else ""
	if name == getattr(screen, "_ngCastName", None):
		return
	screen._ngCastName = name
	_clear(screen)
	if not name or not enabled():
		return
	from Components.NileGlassCore import posters, noFilmEvent
	try:
		if noFilmEvent(event, screen.get("Service")):
			return
	except Exception:
		pass
	posters.request(name, _Loader(screen, name).details, kind="details")


def install():
	try:
		from Screens.EventView import EventViewBase
		from Components.Label import Label
		from Components.Pixmap import Pixmap
	except Exception:
		return
	if getattr(EventViewBase, "_ngCast", False):
		return
	originalInit = EventViewBase.__init__
	originalSet = EventViewBase.setEvent

	def __init__(self, *args, **kwargs):
		try:
			for i in range(CAST):
				self["cast_p%d" % i] = Pixmap()
				self["cast_n%d" % i] = Label("")
			self["cast_title"] = Label("")
		except Exception as err:
			print("[NileGlass] cast:", err)
		originalInit(self, *args, **kwargs)

	def setEvent(self, event, *args, **kwargs):
		result = originalSet(self, event, *args, **kwargs)
		try:
			_load(self, event)
		except Exception as err:
			print("[NileGlass] cast:", err)
		return result

	EventViewBase.__init__ = __init__
	EventViewBase.setEvent = setEvent
	EventViewBase._ngCast = True
