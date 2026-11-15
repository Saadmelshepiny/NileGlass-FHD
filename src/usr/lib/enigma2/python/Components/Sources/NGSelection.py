# -*- coding: utf-8 -*-
# NileGlass FHD - the line under the cursor of a GUI list (MenuList, PluginList)
# as a source, so converters can show details of it in cards beside the list.

from Components.Sources.Source import Source


class NGSelection(Source):
	def __init__(self, gui):
		Source.__init__(self)
		self.gui = gui
		self.onSelectionChanged = []
		try:
			gui.onSelectionChanged.append(self.selectionChanged)
		except Exception:
			pass

	def selectionChanged(self):
		for f in self.onSelectionChanged:
			f()

	def getCurrent(self):
		try:
			return self.gui.getCurrent()
		except Exception:
			return None

	current = property(getCurrent)
