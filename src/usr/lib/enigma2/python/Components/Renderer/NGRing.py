# -*- coding: utf-8 -*-
# NileGlass FHD - a ring gauge (0..100 %) drawn from 21 ready pictures.
#   <widget source="session.CurrentService" render="NGRing" position=".." size="130,130" alphatest="blend">
#       <convert type="NGSysInfo">RamPercent</convert>
#   </widget>
# Pictures: NileGlass_FHD/ui/ring_00.png .. ring_20.png (5 % steps).

from enigma import ePixmap

from Components.Renderer.Renderer import Renderer
from Tools.Directories import SCOPE_CURRENT_SKIN, resolveFilename
from Tools.LoadPixmap import LoadPixmap


class NGRing(Renderer):
	GUI_WIDGET = ePixmap

	def __init__(self):
		Renderer.__init__(self)
		self.step = None

	def postWidgetCreate(self, instance):
		self.changed((self.CHANGED_DEFAULT,))

	def changed(self, what):
		if not self.instance or self.source is None:
			return
		try:
			rng = getattr(self.source, "range", 100) or 100
			v = max(0.0, min(1.0, float(self.source.value or 0) / rng))
		except Exception:
			v = 0.0
		step = int(round(v * 20))
		if step != self.step:
			self.step = step
			pm = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "NileGlass_FHD/ui/ring_%02d.png" % step), cached=True)
			if pm:
				self.instance.setPixmap(pm)
