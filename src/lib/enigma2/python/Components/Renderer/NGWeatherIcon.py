# -*- coding: utf-8 -*-
# NileGlass FHD - weather icon renderer.
#
#   <widget source="global.CurrentTime" render="NGWeatherIcon" position="..." size="64,64"
#           alphatest="blend" />
#
# Icons are taken from <skin>/weather/<name>.png. The pixmap is only reloaded
# when the condition actually changes, so it costs nothing per minute tick.

from enigma import ePixmap

from Components.Renderer.Renderer import Renderer
from Components.NileGlassCore import weather
from Tools.Directories import SCOPE_CURRENT_SKIN, resolveFilename
from Tools.LoadPixmap import LoadPixmap


class NGWeatherIcon(Renderer):
	GUI_WIDGET = ePixmap

	def __init__(self):
		Renderer.__init__(self)
		self.iconName = None

	def postWidgetCreate(self, instance):
		self.update()

	def changed(self, what):
		self.update()

	def update(self):
		if not self.instance:
			return
		name = weather.get("icon", "")
		if not name:
			self.instance.hide()
			return
		if name != self.iconName:
			pix = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "weather/%s.png" % name), cached=True)
			if pix:
				self.instance.setPixmap(pix)
				self.iconName = name
		self.instance.show()
