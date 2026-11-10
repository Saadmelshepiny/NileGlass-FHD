# -*- coding: utf-8 -*-
# NileGlass FHD - weather text converter (Open-Meteo, no API key).
#
#   <widget source="global.CurrentTime" render="Label" ...>
#       <convert type="NGWeather">temp</convert>
#   </widget>
#
# Types: temp, city, desc, hilo, humidity, wind, icon
# The data is fetched by a background thread (Components.NileGlassCore);
# this converter only reads the last known values, so it never blocks.

from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached
from Components.NileGlassCore import weather


class NGWeather(Poll, Converter):
	TYPES = ("temp", "city", "desc", "hilo", "humidity", "wind", "icon")

	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)
		self.type = type.strip().lower() if type and type.strip().lower() in self.TYPES else "temp"
		self.poll_interval = 60 * 1000
		self.poll_enabled = True

	@cached
	def getText(self):
		return weather.get(self.type, "")

	text = property(getText)
