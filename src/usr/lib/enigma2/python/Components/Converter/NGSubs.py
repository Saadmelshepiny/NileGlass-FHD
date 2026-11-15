# -*- coding: utf-8 -*-
# NileGlass FHD - subtitle state written by the subtitle plugin (Saad Auto
# Subssupport 2.8.5+) in /tmp/NileGlass/subs.json, shown in the infobar.
# Read only; the file is read again only when it changed.  Shown only when it
# is about the channel / recording playing now.
#   <convert type="NGSubs">Ok</convert>    text when subtitles are on and in sync
#   Busy: searching / still adjusting,  None: nothing found,  Bad: error
# {"state": "searching|on|none|off|error|idle", "sync": "exact|adjusting", "lang": "ar",
#  "source": "dl.subdl.com|hdd|mora|live", "offset": 0.0, "ref": "...", "title": "...", "updated": 0}

import json
import os

from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached

FILE = "/tmp/NileGlass/subs.json"
_cache = {"mtime": None, "data": None}


def state():
	try:
		m = os.stat(FILE).st_mtime
	except OSError:
		_cache.update(mtime=None, data=None)
		return None
	if m != _cache["mtime"]:
		try:
			with open(FILE, encoding="utf-8") as f:
				_cache["data"] = json.load(f)
		except Exception:
			_cache["data"] = None
		_cache["mtime"] = m
	return _cache["data"]


def norm(ref):
	return (ref or "").strip().rstrip(":").lower()


def playingRef():
	try:
		import NavigationInstance
		ref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()
		return ref.toString() if ref else ""
	except Exception:
		return ""


def classify(d, current):
	"""-> (class, text) or (None, "")"""
	if not d or d.get("state") in (None, "idle", "off"):
		return None, ""
	ref = norm(d.get("ref"))
	if not ref or ref != norm(current):
		return None, ""
	st = d.get("state")
	lang = (d.get("lang") or "ar").lower()
	label = "ترجمة عربي" if lang == "ar" else "ترجمة " + lang.upper()[:3]
	if st == "searching":
		return "busy", "بيدوّر ترجمة"
	if st == "on":
		if d.get("sync") == "adjusting":
			return "busy", "بتتظبط…"
		try:
			off = float(d.get("offset") or 0)
		except (TypeError, ValueError):
			off = 0
		if off:
			return "ok", "ترجمة %+.1fث" % off
		if d.get("source") == "live":
			return "ok", "ترجمة مباشرة"
		return "ok", label
	if st == "none":
		return "none", "مفيش ترجمة"
	if st == "error":
		return "bad", "خطأ ترجمة"
	return None, ""


class NGSubs(Poll, Converter):
	def __init__(self, arg):
		Converter.__init__(self, arg)
		Poll.__init__(self)
		self.want = (arg or "Ok").strip().lower()
		self.poll_interval = 2000
		self.poll_enabled = True

	@cached
	def getText(self):
		try:
			cls, text = classify(state(), playingRef())
		except Exception:
			return ""
		return text if cls == self.want else ""

	text = property(getText)

	@cached
	def getBoolean(self):
		return bool(self.getText())

	boolean = property(getBoolean)
