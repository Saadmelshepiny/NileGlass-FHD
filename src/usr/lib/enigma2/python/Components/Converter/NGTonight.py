# -*- coding: utf-8 -*-
# NileGlass FHD - films / matches of tonight from the Saad EPG plugin.
#
#   <widget source="session.CurrentService" render="Label" ...>
#       <convert type="NGTonight">Soon</convert>
#   </widget>
#
# Types:
#   Soon     next film or match on your channels within 90 minutes
#            (favourite channels first), e.g. "بعد قليل  21:30  فتاتي  •  MBC 2"
#   Service  the next film / match of tonight on the channel you are watching
#
# The file is read by a background thread (Components.NileGlassCore.tonight);
# this converter only formats what is already in memory.

import time

from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached
from Components.NileGlassCore import tonight

try:
	from ServiceReference import ServiceReference
except Exception:  # tests
	ServiceReference = None


def channelName(ch):
	"""Name of the channel as it is called in the receiver's own list."""
	if ServiceReference is not None:
		try:
			name = ServiceReference(ch["sref"]).getServiceName()
			if name:
				return name.replace("\x86", "").replace("\x87", "")
		except Exception:
			pass
	return ch.get("name") or ""


def itemName(x):
	if x["kind"] == "match" and x.get("home") and x.get("away"):
		return "%s × %s" % (x["home"], x["away"])
	return x.get("title") or ""


def itemLine(x, prefix=""):
	t = time.strftime("%H:%M", time.localtime(x["start"]))
	ch = channelName(x["channels"][0]) if x.get("channels") else ""
	return "  ".join(filter(None, (prefix, t, itemName(x)))) + (("  •  " + ch) if ch else "")


class NGTonight(Poll, Converter):
	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)
		self.type = "service" if (type or "").strip().lower() == "service" else "soon"
		self.poll_interval = 60 * 1000
		self.poll_enabled = True

	def _currentRef(self):
		try:
			import NavigationInstance
			ref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()
			return ref.toString() if ref else ""
		except Exception:
			return ""

	@cached
	def getText(self):
		try:
			now = time.time()
			if self.type == "service":
				items = [x for x in tonight.forService(self._currentRef(), now) if x["start"] > now - 60]
				return itemLine(items[0], "الليلة") if items else ""
			x = tonight.soon(now=now)
			if not x:
				return ""
			return itemLine(x, "الآن" if x["start"] <= now else "بعد قليل")
		except Exception as err:
			print("[NGTonight]", err)
			return ""

	text = property(getText)
