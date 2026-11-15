# -*- coding: utf-8 -*-
# NileGlass FHD - the screen a card window stands beside (set by dashctx.py),
# so the cards can show that screen's own things (its settings, its plugin).

from Components.Sources.Source import Source


class NGHost(Source):
	def __init__(self):
		Source.__init__(self)
		self.host = None

	def setHost(self, host):
		self.host = host
		self.changed((self.CHANGED_ALL,))

	def getCurrent(self):
		return self.host

	current = property(getCurrent)
