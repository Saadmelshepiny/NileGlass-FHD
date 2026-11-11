# -*- coding: utf-8 -*-
# NileGlass FHD - small softcam switcher bar.
#
#   <  OScam  >   LEFT / RIGHT: the next emu (OScam, NCam ...)
#                 OK: restart the running emu, or start the one chosen
#                 EXIT: close
# Below it: decoding details of the channel (state, CAID / system, reader,
# protocol, hops, ECM time, available systems) from /tmp/ecm.info.
# Emu configuration files are never touched.
#
# Works with both softcam systems of OpenBh:
#  - the Blue Panel one (/usr/camscript/Ncam_*.sh, /etc/BhCamConf and the
#    Blackhole socket) - what the Blue Panel itself does;
#  - the init.d one (/etc/init.d/softcam.*, Tools.camcontrol) as a fallback.
# All file and socket work is tiny and done once on OK; the bar never polls.

import os
import shutil
import socket

from enigma import eTimer

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Screens.Screen import Screen

CAMSCRIPT = "/usr/camscript"
BHCONF = "/etc/BhCamConf"
BHSOCK = "/tmp/Blackhole.socket"
AUTOCLOSE = 15000  # ms without a key press


class BlueCams:
	"""The Blue Panel's softcams (/usr/camscript)."""

	def __init__(self):
		self.names, self.scripts = [], {}
		for fil in sorted(os.listdir(CAMSCRIPT)):
			if not fil.startswith("Ncam_"):
				continue
			try:
				with open(os.path.join(CAMSCRIPT, fil)) as f:
					for line in f:
						line = line.strip()
						if line.startswith("CAMNAME="):
							name = line[8:].strip().strip('"')
							if name and name not in self.scripts:
								self.names.append(name)
								self.scripts[name] = os.path.join(CAMSCRIPT, fil)
							break
			except Exception:
				pass

	def current(self):
		script = "%s/Ncam_Ci.sh" % CAMSCRIPT
		try:
			with open(BHCONF) as f:
				for line in f:
					parts = line.strip().split("|")
					if parts[0] == "delcurrent" and len(parts) > 1:
						script = parts[1]
		except Exception:
			pass
		for name, path in self.scripts.items():
			if path == script:
				return name
		return None

	def start(self, name):
		new = self.scripts[name]
		old = self.scripts.get(self.current() or "", "%s/Ncam_Ci.sh" % CAMSCRIPT)
		lines = []
		try:
			with open(BHCONF) as f:
				lines = f.readlines()
		except Exception:
			pass
		out, seen = [], set()
		for line in lines:
			key = line.split("|")[0]
			if key in ("delcurrent", "deldefault"):
				line = "%s|%s\n" % (key, new)
				seen.add(key)
			out.append(line)
		for key in ("deldefault", "delcurrent"):
			if key not in seen:
				out.append("%s|%s\n" % (key, new))
		with open(BHCONF + ".tmp", "w") as f:
			f.writelines(out)
		os.rename(BHCONF + ".tmp", BHCONF)
		with open("/etc/CurrentBhCamName", "w") as f:
			f.write(name)
		shutil.copyfile(new, "/usr/bin/StartBhCam")
		os.chmod("/usr/bin/StartBhCam", 0o755)
		_bhSend(("STOP_CAMD," + old, "NEW_CAMD," + new))


def _bhSend(cmds):
	for cmd in cmds:
		s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		try:
			s.settimeout(2)
			s.connect(BHSOCK)
			s.send(cmd.encode("utf-8"))
		finally:
			s.close()


def _blueRestart(self, name):
	"""Same emu again: stop + start through the image's socket, no file written."""
	script = self.scripts[name]
	_bhSend(("STOP_CAMD," + script, "NEW_CAMD," + script))


BlueCams.restart = _blueRestart


class InitCams:
	"""/etc/init.d/softcam.* (Tools.camcontrol)."""

	def __init__(self):
		from Tools.camcontrol import CamControl
		self.cc = CamControl("softcam")
		self.names = [x for x in self.cc.getList() if x.lower() != "none"]

	def current(self):
		return self.cc.current()

	def start(self, name):
		self.cc.command("stop")
		self.cc.select(name)
		self.cc.command("start")

	def restart(self, name):
		self.cc.command("restart")


def camSystem():
	if os.path.isdir(CAMSCRIPT):
		try:
			cams = BlueCams()
			if cams.names:
				return cams
		except Exception as err:
			print("[NileGlass] cambar blue:", err)
	try:
		return InitCams()
	except Exception as err:
		print("[NileGlass] cambar init.d:", err)
	return None


def isEmu(name):
	return name and name.lower() not in ("ci", "common interface", "none")


def label(name):
	return {"Ci": "Common Interface"}.get(name, name)


class NileGlassCamBar(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = "NileGlassCamBar"
		self["cam"] = Label("")
		self["left"] = Pixmap()
		self["right"] = Pixmap()
		self["info"] = Label("")
		self["state"] = Label("")
		self.cams = camSystem()
		self.names = [x for x in (self.cams.names if self.cams else []) if isEmu(x)]
		self.running = self.cams.current() if self.cams else None
		self.index = self.names.index(self.running) if self.running in self.names else 0
		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions", "MenuActions"], {
			"menu": self.readers,
			"ok": self.apply,
			"cancel": self.close,
			"left": self.prev,
			"right": self.next,
		}, -2)
		self.closeTimer = eTimer()
		self.closeTimer.callback.append(self.autoClose)
		self.onClose.append(self.closeTimer.stop)
		self.onLayoutFinish.append(self.refresh)

	def autoClose(self):
		if self.session.current_dialog is self:
			self.close()

	def refresh(self):
		self.closeTimer.start(AUTOCLOSE, True)
		if not self.names:
			self["cam"].setText("لا يوجد إيمو")
			self["info"].setText("مفيش إيموهات مثبتة على الجهاز")
			self["state"].setText("")
			self["left"].hide()
			self["right"].hide()
			return
		if len(self.names) < 2:
			self["left"].hide()
			self["right"].hide()
		name = self.names[self.index]
		self["cam"].setText(label(name))
		n = len(self.names)
		self["info"].setText("%d %s  ·  %s: %s" % (n, "إيمو مثبت" if n == 1 else "إيموهات مثبتة", "الشغال", label(self.running) if self.running else "—"))
		self["state"].setText("إعادة التشغيل بزر OK" if name == self.running else "التشغيل بزر OK")

	def readers(self):
		# the bar closes with "readers" and whoever opened it opens the readers
		# screen once the bar is really gone (openCamBar); opening it here,
		# right after close(), is refused by enigma2 ("Modal open ...")
		self.closeTimer.stop()
		self.close("readers")

	def prev(self):
		if len(self.names) > 1:
			self.index = (self.index - 1) % len(self.names)
			self.refresh()

	def next(self):
		if len(self.names) > 1:
			self.index = (self.index + 1) % len(self.names)
			self.refresh()

	def apply(self):
		if not self.names:
			self.close()
			return
		name = self.names[self.index]
		again = name == self.running
		try:
			if again:
				self.cams.restart(name)
			else:
				self.cams.start(name)
		except Exception as err:
			print("[NileGlass] cambar:", err)
			self["state"].setText("فشلت العملية")
			return
		self.running = name
		self["state"].setText(("جاري إعادة تشغيل %s ..." if again else "جاري تشغيل %s ...") % label(name))
		self.closeTimer.start(3000, True)


class NileGlassBitrate(Screen):
	"""Bitrate viewer: video / audio, current, min, max, average."""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = "NileGlassBitrate"
		self["actions"] = ActionMap(["OkCancelActions"], {"ok": self.close, "cancel": self.close}, -2)
