# -*- coding: utf-8 -*-
# NileGlass FHD - a long text shown one line per row.
# enigma2 reorders a multi-line label as one block when Arabic and Latin are
# mixed, so lines and words got swapped (reports, crash list).  Here every line
# is its own row, so each one is drawn on its own and keeps its order.

from Components.ActionMap import ActionMap
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Screens.Screen import Screen


def rows(text, width=110):
	"""text -> [(line,)]: tabs to spaces, long lines cut into rows at a space"""
	out = []
	for line in (text or "").replace("\t", "    ").splitlines():
		line = line.rstrip()
		while len(line) > width:
			cut = line.rfind(" ", 0, width)
			cut = cut if cut > width // 2 else width
			out.append((line[:cut],))
			line = "      " + line[cut:].lstrip()
		out.append((line,))
	return out


class NileGlassLines(Screen):
	def __init__(self, session, text="", title=""):
		Screen.__init__(self, session)
		self.skinName = "NileGlassLines"
		self.setTitle(title)
		self["list"] = List(rows(text))
		self["key_red"] = StaticText("إغلاق")
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions"], {
			"ok": self.close, "cancel": self.close, "red": self.close,
			"up": self.up, "down": self.down,
			"left": self.pageUp, "right": self.pageDown,
		}, -1)

	def up(self):
		self["list"].up()

	def down(self):
		self["list"].down()

	def pageUp(self):
		self["list"].pageUp()

	def pageDown(self):
		self["list"].pageDown()
