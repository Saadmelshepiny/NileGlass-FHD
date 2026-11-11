# -*- coding: utf-8 -*-
# NileGlass FHD - show a programme description in Arabic.
#
# Put it after the converter that gives the description:
#   <convert type="EventName">FullDescription</convert><convert type="NGTranslate"/>
# The original text shows at once; when the same text has stayed on screen
# for a moment (not while scrolling through a list) its Arabic translation
# is fetched in the background and replaces it.  Known translations show
# immediately.  Programme titles are never passed through this.

from enigma import eTimer

from Components.Converter.Converter import Converter
from Components.Element import cached
from Components.NileGlassCore import translator

SETTLE = 700   # ms the text must stay before it is sent for translation


class NGTranslate(Converter):
	def __init__(self, arg):
		Converter.__init__(self, arg)
		self.pending = None
		self.timer = eTimer()
		self.timer.callback.append(self.ask)

	def original(self):
		try:
			return self.source.text or ""
		except Exception:
			return ""

	@cached
	def getText(self):
		text = self.original()
		if not text or not translator.enabled:
			return text
		hit = translator.cached(text)
		if hit is not None:
			return hit
		if self.pending != text:
			self.pending = text
			self.timer.start(SETTLE, True)
		return text

	text = property(getText)

	def ask(self):
		if self.pending and self.pending == self.original():
			translator.request(self.pending, self.ready)

	def ready(self, original, translated):
		if original == self.original():
			Converter.changed(self, (self.CHANGED_ALL,))

	def changed(self, what):
		if what[0] == self.CHANGED_CLEAR:
			self.timer.stop()
			self.pending = None
		Converter.changed(self, what)

	def destroy(self):
		self.timer.stop()
		Converter.destroy(self)
