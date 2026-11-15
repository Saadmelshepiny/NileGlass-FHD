# -*- coding: utf-8 -*-
# NileGlass FHD - small additions to image screens for the cards beside them:
#   * package list (Plugins > download / remove): "ng_sel", the package under the cursor
# Installed once at GUI start; a screen that fails here still opens as usual.


def _addSelection(cls, listName="list", name="ng_sel"):
	if getattr(cls, "_ngSel", False):
		return
	orig = cls.__init__

	def __init__(self, *args, **kwargs):
		orig(self, *args, **kwargs)
		try:
			from Components.Sources.NGSelection import NGSelection
			if name not in self:
				self[name] = NGSelection(self[listName])
		except Exception as err:
			print("[NileGlass] screen hook:", err)
	cls.__init__ = __init__
	cls._ngSel = True


def install():
	try:
		from Screens.PluginBrowser import PluginDownloadBrowser
		_addSelection(PluginDownloadBrowser)
	except Exception as err:
		print("[NileGlass] screen hook:", err)
