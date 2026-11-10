# -*- coding: utf-8 -*-
# NileGlass FHD - show / hide widgets for internet streams (IPTV, web radio).
#
# Put it last in a widget's converter chain. It passes everything through
# unchanged (like ConditionalShowHide) and only decides visibility:
#
#   <convert type="FrontendInfo">SNR</convert><convert type="NGStream"/>
#       -> hidden while an internet stream is playing (no tuner, no signal)
#   <convert type="NGStream">Only</convert>
#       -> shown only while an internet stream is playing (the IPTV badge)
#
# A stream is a service whose reference carries a URL (4097/5001/5002 or
# 1:0:...:http%3a//...). Stream relay of satellite channels has no URL in
# the reference, so it keeps its signal panel.

import NavigationInstance

from Components.Converter.Converter import Converter


def isStreamRef(ref):
	try:
		s = ref.toString().lower() if ref else ""
	except Exception:
		return False
	return "://" in s or "%3a//" in s


def playingIsStream():
	try:
		return isStreamRef(NavigationInstance.instance.getCurrentlyPlayingServiceReference())
	except Exception:
		return False


class NGStream(Converter):
	def __init__(self, arg):
		Converter.__init__(self, arg)
		self.only = arg.strip().lower() in ("only", "invert", "stream")

	# transparent to everything the renderer asks for (text, value, range ...)
	def __getattr__(self, name):
		return getattr(self.source, name)

	def calcVisibility(self):
		return playingIsStream() == self.only

	def changed(self, what):
		vis = self.calcVisibility()
		for x in self.downstream_elements:
			x.visible = vis
		super(Converter, self).changed(what)

	def connectDownstream(self, downstream):
		Converter.connectDownstream(self, downstream)
		downstream.visible = self.calcVisibility()
