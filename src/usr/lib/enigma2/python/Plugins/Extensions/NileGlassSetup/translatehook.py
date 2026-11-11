# -*- coding: utf-8 -*-
# NileGlass FHD - Arabic description in the event information screen (INFO).
# The image fills its description box directly (no converter), so the text
# is replaced here once the translation arrives. The title is left alone.

from Components.NileGlassCore import translator


class _Waiter:
	def __init__(self, screen, text):
		self.screen, self.text = screen, text

	def ready(self, original, translated):
		s = self.screen
		try:
			if s.instance and "FullDescription" in s and s["FullDescription"].getText() == original:
				s["FullDescription"].setText(translated)
		except Exception:
			pass


def install():
	try:
		from Screens.EventView import EventViewBase
	except Exception:
		return
	if getattr(EventViewBase, "_ngTranslate", False):
		return
	original = EventViewBase.setEvent

	def setEvent(self, event):
		original(self, event)
		try:
			if not translator.enabled:
				return
			text = self["FullDescription"].getText()
			hit = translator.cached(text)
			if hit is not None and hit != text:
				self["FullDescription"].setText(hit)
			elif hit is None:
				translator.request(text, _Waiter(self, text).ready)
		except Exception as err:
			print("[NileGlass] translate event view:", err)
	EventViewBase.setEvent = setEvent
	EventViewBase._ngTranslate = True
