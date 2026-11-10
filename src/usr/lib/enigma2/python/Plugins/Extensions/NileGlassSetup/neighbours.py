# -*- coding: utf-8 -*-
# NileGlass FHD - prefetch of the channels around the selection.
#
# While the channel list is open, 600 ms after the selection stops moving the
# programmes now running on the 2 channels above and the 2 below are put at
# the head of the poster queue.  When the user moves there the poster is
# already on disk.  All the network work stays in NileGlassCore's threads;
# here only a few cheap EPG-cache lookups run on the UI thread.

from enigma import eEPGCache, eServiceReference, eTimer

from Components.NileGlassCore import posters, confBool

RANGE = 2          # channels on each side
DEBOUNCE = 600     # ms of no movement before prefetching
_SKIP = eServiceReference.isMarker | eServiceReference.isDirectory


class NeighbourPrefetch:
	def __init__(self, csel):
		self.csel = csel
		self.rootKey = None
		self.refs = []
		self.lastIndex = -1
		self.timer = eTimer()
		self.timer.callback.append(self.run)
		csel.servicelist.connectSelChanged(self.moved)
		csel.onShown.append(self.shown)

	def shown(self):
		self.rootKey = None   # bouquet may have been edited meanwhile
		self.moved()

	def moved(self):
		if getattr(self.csel, "execing", False) and posters.enabled and posters.apiKey and confBool("posters", "neighbours", True):
			self.timer.start(DEBOUNCE, True)

	def run(self):
		try:
			if not getattr(self.csel, "execing", False):
				return
			lst = self.csel.servicelist
			root = self.csel.getRoot()
			key = root and root.toString()
			if key != self.rootKey:
				self.refs = lst.getList() or []
				self.rootKey = key
				self.lastIndex = -1
			idx = lst.getCurrentIndex()
			if idx == self.lastIndex or not (0 <= idx < len(self.refs)):
				return
			self.lastIndex = idx
			epg = eEPGCache.getInstance()
			names = []
			for step in range(1, RANGE + 1):
				for i in (idx + step, idx - step):
					if 0 <= i < len(self.refs):
						ref = self.refs[i]
						if ref.flags & _SKIP:
							continue
						ev = epg.lookupEventTime(ref, -1)
						name = ev and ev.getEventName()
						if name:
							names.append(name)
			if names:
				posters.prefetch(names, urgent=True)
		except Exception as err:
			print("[NileGlass] neighbours:", err)


def attach(csel):
	if csel is not None and not hasattr(csel, "_ngNeighbours"):
		csel._ngNeighbours = NeighbourPrefetch(csel)


def install():
	"""Hook every ChannelSelection (also the one created before us).
	Always installed: the setting is checked on every move, so turning it
	on or off needs no restart."""
	try:
		from Screens.ChannelSelection import ChannelSelection
		if not getattr(ChannelSelection, "_ngNbPatched", False):
			original = ChannelSelection.__init__

			def __init__(self, *args, **kwargs):
				original(self, *args, **kwargs)
				try:
					attach(self)
				except Exception as err:
					print("[NileGlass] neighbours attach:", err)
			ChannelSelection.__init__ = __init__
			ChannelSelection._ngNbPatched = True
		try:
			from Screens.InfoBar import InfoBar
			ib = InfoBar.instance
			attach(ib and getattr(ib, "servicelist", None))
		except Exception:
			pass
	except Exception as err:
		print("[NileGlass] neighbours install:", err)
