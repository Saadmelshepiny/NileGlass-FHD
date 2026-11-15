# -*- coding: utf-8 -*-
# NileGlass FHD - details of the plugin under the cursor in a plugin list
# (Plugins screen, OpenBh green panel), for the cards beside the list.
#
#   <widget source="list" render="Label"><convert type="NGPluginInfo">Version</convert></widget>
#   Version, Runs, Last, Name, Description, Package, Maker, Installed, Size,
#   Feed, Kind, Places, Background, Folder

from Components.Converter.Converter import Converter
from Components.Element import cached

try:
	from Components import NileGlassPlugins as Info
except Exception:
	Info = None

FIELDS = {"version", "runs", "last", "name", "description", "package", "maker", "installed", "size", "feed", "kind", "places", "background", "folder"}


def descriptorOf(entry):
	if entry is None:
		return None
	if hasattr(entry, "where") and hasattr(entry, "fnc"):
		return entry
	try:
		for x in entry:
			if hasattr(x, "where") and hasattr(x, "fnc"):
				return x
	except TypeError:
		pass
	return None


class NGPluginInfo(Converter):
	def __init__(self, arg):
		Converter.__init__(self, arg)
		self.field = (arg or "Name").strip().lower()
		if self.field not in FIELDS:
			self.field = "name"
		self.hooked = False

	def selChanged(self):
		self.downstream_elements.changed((self.CHANGED_ALL, 0))

	def more(self):
		if self.source is not None:
			Converter.changed(self, (self.CHANGED_ALL,))

	@cached
	def getText(self):
		if Info is None:
			return ""
		try:
			desc = descriptorOf(self.source.getCurrent())
		except Exception:
			desc = None
		if desc is None:
			return ""
		try:
			if self.field in ("package", "installed", "feed", "size", "maker", "version"):
				Info.prepare()
			return Info.info(desc).get(self.field, "")
		except Exception as err:
			print("[NileGlass] NGPluginInfo:", err)
			return ""

	text = property(getText)

	def changed(self, what):
		if what[0] == self.CHANGED_DEFAULT and not self.hooked and self.source is not None:
			self.hooked = True
			try:
				self.source.onSelectionChanged.append(self.selChanged)
			except Exception:
				pass
			if Info:
				Info.addListener(self.more)
		Converter.changed(self, what)

	def destroy(self):
		if Info:
			Info.removeListener(self.more)
		Converter.destroy(self)
