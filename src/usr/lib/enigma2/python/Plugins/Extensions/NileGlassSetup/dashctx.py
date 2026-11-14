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


def _pollers(comp):
	"""converters of a widget that read the box on a timer"""
	out, src, depth = [], getattr(comp, "source", None), 0
	while src is not None and depth < 5:
		if hasattr(src, "poll_enabled"):
			out.append(src)
		src, depth = getattr(src, "source", None), depth + 1
	return out


def enabled():
	try:
		from Components.NileGlassCore import confBool
		return confBool("extras", "dash", True)
	except Exception:
		return True


def show(screen, name):
	"""show the card set 'name', hide the others; hidden sets stop reading
	the box (only the visible cards poll).  Cards turned off in the settings:
	nothing shown, nothing read."""
	want = GROUPS.get(name, GROUPS["system"]) if enabled() else None
	parts = getattr(screen, "_ngDashParts", None)
	if parts is None:
		parts = []
		for comp in list(getattr(screen, "renderer", [])) + list(screen.values()):
			g = _group(comp)
			if g in GROUPS.values() and getattr(comp, "instance", None) is not None:
				parts.append((g, comp.instance, _pollers(comp)))
		screen._ngDashParts = parts
	if getattr(screen, "_ngDashNow", -1) == want:
		return
	screen._ngDashNow = want
	for g, inst, pollers in parts:
		on = g == want
		for p in pollers:
			try:
				if p.poll_enabled != on:
					p.poll_enabled = on
					if on:
						p.poll()          # fresh values right away
			except Exception:
				pass
		if on:
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


def autoAttach(screen):
	"""A screen that borrows the Setup / Menu skin (plugins, the readers editor):
	it has the card sets too, so show the one that fits and hide the rest."""
	groups = set()
	for comp in list(getattr(screen, "renderer", [])):
		g = _group(comp)
		if g in GROUPS.values():
			groups.add(g)
			if len(groups) >= 3:
				break
	if len(groups) < 3:
		return
	attachSetup(screen)
	screen._ngDashUpdate()
