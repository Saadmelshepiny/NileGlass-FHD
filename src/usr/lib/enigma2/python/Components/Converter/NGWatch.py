# -*- coding: utf-8 -*-
# NileGlass FHD - how much you watched the channel under the cursor this week
# (Components/NileGlassWatch.py), for the channel list card.
#   <convert type="NGWatch">Text</convert>  -> "الأكثر مشاهدة #2 · 5 س 20 د الأسبوع ده"
#   <convert type="NGWatch">Top</convert>   -> boolean: one of your ten most watched

from Components.Converter.Converter import Converter
from Components.Element import cached

try:
	from Components import NileGlassWatch as Watch
except Exception:
	Watch = None


class NGWatch(Converter):
	def __init__(self, arg):
		Converter.__init__(self, arg)
		self.top = (arg or "").strip().lower() == "top"

	def ref(self):
		try:
			return self.source.getCurrentService()
		except Exception:
			try:
				return self.source.service
			except Exception:
				return None

	@cached
	def getText(self):
		if Watch is None:
			return ""
		try:
			return Watch.text(self.ref())
		except Exception:
			return ""

	text = property(getText)

	@cached
	def getBoolean(self):
		if Watch is None:
			return False
		try:
			k = Watch.key(self.ref())
			return bool(k) and k in Watch.ranking()[:Watch.TOP]
		except Exception:
			return False

	boolean = property(getBoolean)
