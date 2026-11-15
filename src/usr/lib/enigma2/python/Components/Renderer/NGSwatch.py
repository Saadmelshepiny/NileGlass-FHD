# -*- coding: utf-8 -*-
# NileGlass FHD - a colour sample: the box takes the colour its converter gives
# ("#rrggbb" or "#aarrggbb"); empty: hidden.

from enigma import eLabel, gRGB

from Components.Renderer.Renderer import Renderer


class NGSwatch(Renderer):
	GUI_WIDGET = eLabel

	def changed(self, what):
		if not self.instance:
			return
		text = (self.source.text or "").strip().lstrip("#")
		try:
			value = int(text, 16)
		except ValueError:
			self.instance.hide()
			return
		self.instance.setBackgroundColor(gRGB(value if len(text) > 6 else value))
		self.instance.setTransparent(0)
		self.instance.show()
		self.instance.invalidate()
