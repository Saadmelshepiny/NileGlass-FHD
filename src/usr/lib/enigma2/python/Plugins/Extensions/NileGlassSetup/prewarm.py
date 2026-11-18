# -*- coding: utf-8 -*-
# NileGlass FHD - the first opening of a screen is the slow one: Python has to
# load its code and the code of every converter and renderer its skin uses.
# A while after the GUI starts, when the box is idle and no key is being
# pressed, those modules are loaded one by one (one every 150 ms), so the
# first EPG, settings, recordings or plugin list opens like the tenth.

import sys

try:
	from enigma import eTimer
except Exception:      # tests
	eTimer = None

SCREENS = ("Screens.EpgSelectionSingle", "Screens.EpgSelectionGrid", "Screens.EpgSelectionMulti", "Screens.EpgSelectionInfobarSingle",
	"Screens.EpgSelectionInfobarGrid", "Screens.EventView", "Screens.Setup", "Screens.PluginBrowser", "Screens.MovieSelection",
	"Screens.TimerEdit", "Screens.TimerEntry", "Screens.ChoiceBox", "Screens.MessageBox", "Screens.About", "Screens.ServiceInfo",
	"Screens.AudioSelection", "Screens.SkinSelector", "Screens.VirtualKeyBoard", "Screens.TextBox")
START_AFTER = 40000
STEP = 150

_todo = []
_timer = None
done = []


def skinModules():
	"""converters and renderers the skin uses, from the loaded skin"""
	names = set()
	try:
		from skin import domScreens
		for name, entry in list(domScreens.items()):
			el = entry[0] if isinstance(entry, tuple) else entry
			for w in el.iter("widget"):
				r = w.get("render")
				if r:
					names.add("Components.Renderer." + r)
				for c in w.iter("convert"):
					t = c.get("type")
					if t:
						names.add("Components.Converter." + t)
	except Exception as err:
		print("[NileGlass] prewarm:", err)
	return sorted(names)


def _busy():
	try:
		from Components.NileGlassCore import userActive
		if userActive(3.0):
			return True
	except Exception:
		pass
	return False


def _step():
	if not _todo:
		return
	if _busy():                          # someone is using the remote: later
		_timer.start(1500, True)
		return
	name = _todo.pop(0)
	if name not in sys.modules:
		try:
			__import__(name)
			done.append(name)
		except Exception:
			pass
	if _todo:
		_timer.start(STEP, True)


def start():
	global _timer
	if _timer is not None or eTimer is None:
		return

	def begin():
		_todo.extend(m for m in list(SCREENS) + skinModules() if m not in sys.modules)
		_step()
	_timer = eTimer()
	_timer.callback.append(_step)
	first = eTimer()
	first.callback.append(begin)
	first.start(START_AFTER, True)
	start._first = first     # keep it alive
