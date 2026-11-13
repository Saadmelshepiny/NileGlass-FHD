# -*- coding: utf-8 -*-
# NileGlass FHD - the cards beside menus and settings follow the subject.
#
# The skin has one set of cards per subject beside the Menu / Setup panel,
# each set on its own zPosition decade (1x network, 2x tuners & dish,
# 3x picture & sound, 4x system).  Here the set that fits the menu entry under
# the cursor (or the open menu / settings screen) is shown, the others hidden.

GROUPS = {"net": 1, "tuner": 2, "av": 3, "system": 4}

NET = ("network", "net", "device_setup", "password_setup", "inadyn", "ftp", "samba", "telnet", "nfs", "vpn", "dlna",
	"ushare", "adapter", "nameserver", "wlan", "wifi", "streaming", "mount")
TUNER = ("scan", "tuner", "nim", "satfinder", "positioner", "blindscan", "fallback", "client_mode", "diseqc", "satconfig",
	"lnb", "cable", "terrestrial", "dish", "motor", "rotor", "sat_", "ci_", "cicam", "fcc")
AV = ("video", "audio", "autolanguage", "subtitle", "hdmi", "osd", "3d", "avsetup", "picture", "aspect", "volume", "ac3", "dts", "display")


def subject(*keys):
	for key in keys:
		k = (key or "").lower()
		if not k:
			continue
		if k == "av" or k.startswith("av_") or any(p in k for p in AV):
			return "av"
		if any(p in k for p in TUNER):
			return "tuner"
		if any(p in k for p in NET):
			return "net"
	return None


def _group(comp):
	for attrib, value in getattr(comp, "skinAttributes", None) or []:
		if attrib == "zPosition":
			try:
				z = int(value)
			except ValueError:
				return None
			return z // 10 if z >= 10 else None
	return None


def show(screen, name):
	"""show the card set 'name', hide the others"""
	want = GROUPS.get(name, GROUPS["system"])
	parts = getattr(screen, "_ngDashParts", None)
	if parts is None:
		parts = []
		for comp in list(getattr(screen, "renderer", [])) + list(screen.values()):
			g = _group(comp)
			if g in GROUPS.values() and getattr(comp, "instance", None) is not None:
				parts.append((g, comp.instance))
		screen._ngDashParts = parts
	if getattr(screen, "_ngDashNow", None) == want:
		return
	screen._ngDashNow = want
	for g, inst in parts:
		if g == want:
			inst.show()
		else:
			inst.hide()


def menuSubject(screen):
	key = None
	try:
		cur = screen["menu"].getCurrent()
		key = cur[2] if cur and len(cur) > 2 else None
	except Exception:
		pass
	menuID = getattr(screen, "menuID", None)
	if menuID == "mainmenu" and key == "setup":
		return "system"
	return subject(key, menuID) or "system"


def setupSubject(screen):
	return subject(getattr(screen, "setup", None), screen.__class__.__name__,
		" ".join(screen.skinName) if isinstance(getattr(screen, "skinName", None), list) else getattr(screen, "skinName", "")) or "system"


def attachMenu(screen):
	def update():
		try:
			show(screen, menuSubject(screen))
		except Exception as err:
			print("[NileGlass] dash:", err)
	screen._ngDashUpdate = update
	try:
		screen["menu"].onSelectionChanged.append(update)
	except Exception:
		pass


def attachSetup(screen):
	def update():
		try:
			show(screen, setupSubject(screen))
		except Exception as err:
			print("[NileGlass] dash:", err)
	screen._ngDashUpdate = update
