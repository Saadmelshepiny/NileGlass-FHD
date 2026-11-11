# -*- coding: utf-8 -*-
# NileGlass FHD - a proper screen while a radio station plays.
#
# Instead of the black (or still) picture: the station logo large, the
# programme now and next, a small moving level meter and a big clock.  The
# screen lies BELOW every other window (zPosition in the skin), so the
# infobar, the channel list and any menu still show on top of it.
# Shown for radio services (DVB radio and radio streams); hidden for TV, in
# standby, or when switched off in the settings ("Radio screen").
# The meter only runs while the screen is visible (and not in lite mode).

from enigma import eTimer, iPlayableService

from Components.Pixmap import Pixmap
from Screens.Screen import Screen

FRAMES = 6
STEP = 320        # ms per meter frame
RADIO_TYPES = (2, 10)


def enabled():
	try:
		from Components.NileGlassCore import confBool
		return confBool("extras", "radio", True)
	except Exception:
		return True


def lite():
	try:
		from Components.NileGlassCore import liteMode
		return liteMode()
	except Exception:
		return False


def isRadioRef(ref):
	try:
		if ref is None:
			return False
		if ref.getData(0) in RADIO_TYPES:
			return True
		s = ref.toString()
		return s.split(":")[2:3] in (["2"], ["A"], ["a"])
	except Exception:
		return False


class NileGlassRadio(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = "NileGlassRadio"
		self["eq"] = Pixmap()


class RadioWatch:
	def __init__(self, session):
		self.session = session
		self.dialog = session.instantiateDialog(NileGlassRadio)
		self.frame = 0
		self.pixmaps = None
		self.timer = eTimer()
		self.timer.callback.append(self.step)
		self.check = eTimer()
		self.check.callback.append(self.update)
		session.nav.event.append(self.event)
		try:
			from Components.config import config
			config.misc.standbyCounter.addNotifier(self.standby, initial_call=False)
		except Exception as err:
			print("[NileGlass] radio standby:", err)

	# ---- events
	def event(self, ev):
		if ev in (iPlayableService.evStart, iPlayableService.evEnd):
			self.check.start(150, True)

	def standby(self, *args):
		self.hide()
		try:
			from Screens.Standby import inStandby
			if inStandby and self.update not in inStandby.onClose:
				inStandby.onClose.append(self.update)
		except Exception:
			pass

	# ---- show / hide
	def update(self):
		try:
			from Screens.Standby import inStandby
		except Exception:
			inStandby = None
		try:
			ref = self.session.nav.getCurrentlyPlayingServiceReference()
		except Exception:
			ref = None
		if enabled() and not inStandby and isRadioRef(ref):
			self.show()
		else:
			self.hide()

	def show(self):
		try:
			if not self.dialog.shown:
				self.dialog.show()
			if lite():
				self.timer.stop()
			elif not self.timer.isActive():
				self.timer.start(STEP, False)
		except Exception as err:
			print("[NileGlass] radio screen:", err)

	def hide(self):
		self.timer.stop()
		try:
			if self.dialog.shown:
				self.dialog.hide()
		except Exception:
			pass

	# ---- level meter
	def step(self):
		try:
			if self.pixmaps is None:
				from Tools.Directories import resolveFilename, SCOPE_CURRENT_SKIN
				from Tools.LoadPixmap import LoadPixmap
				self.pixmaps = [LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "NileGlass_FHD/ui/eq%d.png" % i), cached=True) for i in range(FRAMES)]
			self.frame = (self.frame + 1) % FRAMES
			pm = self.pixmaps[self.frame]
			w = self.dialog["eq"]
			if pm is not None and w.instance:
				w.instance.setPixmap(pm)
		except Exception as err:
			print("[NileGlass] radio meter:", err)
			self.timer.stop()


watcher = None


def install(session):
	global watcher
	if watcher is None:
		try:
			watcher = RadioWatch(session)
		except Exception as err:
			print("[NileGlass] radio screen:", err)
