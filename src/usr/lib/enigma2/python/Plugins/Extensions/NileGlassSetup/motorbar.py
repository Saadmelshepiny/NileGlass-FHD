# -*- coding: utf-8 -*-
# NileGlass FHD - "the dish is moving" banner for motorised tuners.
#
# The image shows its Dish banner only when the receiver reports the rotor as
# moving, which FBC tuners with USALS often never do.  Here the banner simply
# follows the satellite: when a channel starts on a motorised tuner (one
# with a rotor satellite list, here tuner A) and its orbital position is not
# where that tuner was last, the banner shows
#     Tuner A   7.0W  ->  13.0E      00:14
# counting down an estimate (degrees x the turning speed from the tuner
# setup) and closes as soon as the channel is tuned (PMT found), or after the
# estimate plus a margin.  When the image's own banner is on screen, this one
# stays hidden.  Nothing is changed in the tuner or image settings.

import json
import os

from enigma import eTimer, iPlayableService, iServiceInformation

from Components.Label import Label
from Screens.Screen import Screen

STATE = "/etc/enigma2/nileglass_rotor.json"
INVALID = 0xFFFF
MARGIN = 15   # seconds after the estimate before giving up


def orbText(pos):
	if pos is None or pos == INVALID:
		return "؟"
	if pos > 1800:
		pos = 3600 - pos
		return "%d.%dW" % (pos // 10, pos % 10)
	return "%d.%dE" % (pos // 10, pos % 10)


def degrees(a, b):
	d = abs(a - b)
	return min(d, 3600 - d) / 10.0


def mmss(sec):
	sec = max(0, int(sec))
	return "%02d:%02d" % (sec // 60, sec % 60)


def rotorTuners():
	out = set()
	try:
		from Components.NimManager import nimmanager
		for slot in nimmanager.nim_slots:
			try:
				if nimmanager.getRotorSatListForNim(slot.slot, only_first=True):
					out.add(slot.slot)
			except Exception:
				pass
	except Exception:
		pass
	return out


def turningSpeed(tuner, orbpos, pol):
	"""Seconds per degree from the tuner setup (simple or advanced)."""
	vertical = pol in (1, 3)
	try:
		from Components.config import config
		nim = config.Nims[tuner]
		mode = nim.configMode.value
		if mode == "simple":
			return (nim.turningspeedV if vertical else nim.turningspeedH).float
		if mode == "advanced":
			sat = nim.advanced.sat[orbpos]
			lnb = nim.advanced.lnb[int(sat.lnb.value)]
			return (lnb.turningspeedV if vertical else lnb.turningspeedH).float
	except Exception:
		pass
	return 1.7 if vertical else 2.3


class NileGlassMotor(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = "NileGlassMotor"
		self["title"] = Label("")
		self["from"] = Label("")
		self["to"] = Label("")
		self["time"] = Label("")
		self["info"] = Label("")


class MotorWatch:
	def __init__(self, session):
		self.session = session
		self.dialog = session.instantiateDialog(NileGlassMotor)
		self.rotors = rotorTuners()
		self.last = self.load()
		self.pending = 0
		self.left = 0
		self.checkTimer = eTimer()
		self.checkTimer.callback.append(self.check)
		self.tick = eTimer()
		self.tick.callback.append(self.step)
		session.nav.event.append(self.event)

	# ---- remembered position per tuner
	def load(self):
		try:
			with open(STATE) as f:
				return {int(k): v for k, v in json.load(f).items()}
		except Exception:
			try:
				from Components.config import config
				pos = config.misc.lastrotorposition.value
				return {t: pos for t in self.rotors} if pos != INVALID else {}
			except Exception:
				return {}

	def save(self):
		try:
			with open(STATE + ".tmp", "w") as f:
				json.dump({str(k): v for k, v in self.last.items()}, f)
			os.replace(STATE + ".tmp", STATE)
		except Exception:
			pass

	# ---- service events
	def event(self, ev):
		if ev == iPlayableService.evStart:
			self.pending = 8                  # tuner number may need a moment
			self.checkTimer.start(250, True)
		elif ev == iPlayableService.evEnd:
			self.checkTimer.stop()

	def current(self):
		service = self.session.nav.getCurrentService()
		info = service and service.info()
		data = info and info.getInfoObject(iServiceInformation.sTransponderData)
		if not data or data == -1 or "DVB-S" not in str(data.get("tuner_type", "")):
			return None
		fe = service.frontendInfo()
		fdata = fe and fe.getFrontendData()
		tuner = fdata and fdata.get("tuner_number")
		return tuner, data.get("orbital_position", INVALID), data.get("polarization", 0)

	def check(self):
		try:
			cur = self.current()
		except Exception:
			cur = None
		if cur is None or cur[0] is None:
			self.pending -= 1
			if self.pending > 0:
				self.checkTimer.start(250, True)
			return
		tuner, orbpos, pol = cur
		if tuner not in self.rotors or orbpos == INVALID:
			return
		old = self.last.get(tuner)
		self.last[tuner] = orbpos
		self.save()
		if old is None or old == orbpos:
			return
		deg = degrees(old, orbpos)
		self.total = int(round(deg * turningSpeed(tuner, orbpos, pol))) + 2
		self.left = self.total
		self.giveUp = self.total + MARGIN
		d = self.dialog
		d["title"].setText("الطبق بيتحرك  ·  تيونر %s" % chr(65 + tuner))
		d["from"].setText(orbText(old))
		d["to"].setText(orbText(orbpos))
		d["info"].setText("%.1f°  ·  حوالي %d ثانية" % (deg, self.total))
		d["time"].setText(mmss(self.left))
		if not self.imageDishShown():
			d.show()
		self.tick.start(1000, False)

	def imageDishShown(self):
		try:
			from Screens.InfoBar import InfoBar
			dish = InfoBar.instance and getattr(InfoBar.instance, "dishDialog", None)
			return bool(dish and dish.shown)
		except Exception:
			return False

	def tuned(self):
		try:
			service = self.session.nav.getCurrentService()
			info = service and service.info()
			pmt = info and info.getInfo(iServiceInformation.sPMTPID)
			return pmt is not None and pmt >= 0
		except Exception:
			return False

	def step(self):
		self.left -= 1
		self.giveUp -= 1
		if self.tuned() or self.giveUp <= 0:
			self.stop()
			return
		self.dialog["time"].setText(mmss(self.left) if self.left > 0 else "...")
		if self.imageDishShown():
			self.dialog.hide()
		elif not self.dialog.shown:
			self.dialog.show()

	def stop(self):
		self.tick.stop()
		self.dialog.hide()


watcher = None


def install(session):
	global watcher
	if watcher is None:
		try:
			watcher = MotorWatch(session)
		except Exception as err:
			print("[NileGlass] motor banner:", err)
