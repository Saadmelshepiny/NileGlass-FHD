#!/usr/bin/env python3
"""One way of showing every screen: a rounded panel at the left edge and,
beside it, the card set (dashboard) that fits the screen's subject - the same
system as the menus and settings.

For every panel screen of skin.xml and layouts/menus_popup.xml:
  - centred panels move to the left edge ("40,center");
  - panels up to 1150 wide get the full card set beside them, panels up to
    1310 wide a slightly narrower one; wider ones (scan / tuning screens with
    their own signal display) only move left;
  - quick pop-ups (messages, number zap, context menus, input boxes, the dish
    and cam bars ...) stay as they are.
Also writes the extensions list (blue held) as its own screen.
Idempotent (screens already done carry an NG-DASH comment).  argv: SKINDIR"""
import importlib.util, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashlib import BUILDERS, DASH_W, DASH_H

SK = sys.argv[1]
GAP, RIGHT = 20, 1880
FULL_MAX, SCALED_MAX = 1150, 1310
SKIP = re.compile(r"^(MessageBox|MessageBoxSimple|NumberZap|NumberZapPicon|NumberZapExt|Dish|InputBox|MinuteInput|Nab_DoStartCam|"
	r"NileGlassMotor|NileGlassCamBar|NileGlassBitrate|ChannelContextMenu|MovieContextMenu|ChoiceBox|JobView|AudioSelection|"
	r"SubtitleSelection|PiPSetup|VirtualKeyBoard|Volume|Mute|PVRState|TimeshiftState|SimpleSummary|InfoBar|SecondInfoBar|"
	r"ChannelSelection|ChannelSelectionRadio|Menu|Setup|menu_.*|NileGlassFilm|NileGlassTonight|NileGlassUpcoming|DeliteBluePanel|"
	r"EventView.*|EPG.*|.*EPG.*|MovieSelection|MoviePlayer|TimerEntry|.*Summary|NG_.*|UserInterfacePositioner|OSDCalibration)$")

spec = importlib.util.spec_from_file_location("dashctx", os.path.join(SK, "../../../lib/enigma2/python/Plugins/Extensions/NileGlassSetup/dashctx.py"))
dashctx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashctx)
HINTS = (("system", ("Animation",)),
	("net", ("Network", "Net", "Adapter", "Inadyn", "Vpn", "Samba", "Nfs", "Ftp", "Telnet", "Mount", "Wlan", "OpenVpn", "Nameserver", "uShare", "MiniDLNA")),
	("tuner", ("Scan", "Satfinder", "Tuner", "Positioner", "Rotor", "Diseqc", "Nim", "CiSelection", "MMI", "Fallback", "ServiceInfo")),
	("av", ("Video", "Audio", "Hdmi", "Osd", "AV")))


def subjectOf(name):
	for subject, words in HINTS:
		if any(w in name for w in words):
			return subject
	return dashctx.subject(name) or "system"


def scaled(lines, x0, s):
	if s >= 0.999:
		return lines
	out = []
	for line in lines:
		ring = 'render="NGRing"' in line

		def pos(m):
			x, y = int(m.group(1)), int(m.group(2))
			return 'position="%d,%d"' % (x0 + round((x - x0) * s), y)

		def size(m):
			w, h = int(m.group(1)), int(m.group(2))
			return 'size="%d,%d"' % (w if ring else round(w * s), h)
		line = re.sub(r'position="(\d+),(\d+)"', pos, line, count=1)
		line = re.sub(r'size="(\d+),(\d+)"', size, line, count=1)
		out.append(line)
	return out


SCALES = (1.0, 0.85, 0.75)


def panelName(subject, s):
	return "NG_Dash_%s_%d" % (subject, round(s * 100))


def panels():
	out = [PBEGIN, "\t<!-- card sets beside the panels (tools/gen_dash.py): positions from the panel that includes them -->"]
	for subject, build in BUILDERS.items():
		for s in SCALES:
			out.append('\t<screen name="%s">' % panelName(subject, s))
			out += scaled(build(0), 0, s)
			out.append("\t</screen>")
	out.append("\t" + PEND)
	return "\n".join(out) + "\n"


PBEGIN, PEND = "<!-- NG-DASHPANELS BEGIN -->", "<!-- NG-DASHPANELS END -->"
EXT_W = 900
EXTENSIONS = '''	<screen name="ExtensionsList" position="40,center" size="%d,800" backgroundColor="transparent" flags="wfNoBorder">
		<!-- blue held: extensions, narrow panel (cards added below) -->
		<eLabel position="0,0" size="%d,800" backgroundColor="bg" cornerRadius="24" zPosition="-10"/>
		<ePixmap pixmap="NileGlass_FHD/ui/ng_logo.png" position="22,24" size="40,40" alphatest="blend" zPosition="1"/>
		<widget source="Title" render="Label" position="74,16" size="%d,56" font="Medium;30" foregroundColor="accent" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>
		<widget source="global.CurrentTime" render="Label" position="%d,16" size="156,56" font="Regular;38" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="right" valign="center" noWrap="1"><convert type="ClockToText">Format:%%H:%%M</convert></widget>
		<eLabel position="24,84" size="%d,1" backgroundColor="line" zPosition="-8"/>
		<widget name="text" position="30,92" size="%d,0" font="Regular;26" foregroundColor="gold" backgroundColor="bg" transparent="1"/>
		<widget name="list" position="30,100" size="%d,580" itemHeight="58" font="Regular;30" foregroundColor="fg" backgroundColor="bg" foregroundColorSelected="white" backgroundColorSelected="bgSel" selectionPixmap="NileGlass_FHD/ui/sel_set.png" scrollbarMode="showOnDemand" scrollbarWidth="4" scrollbarSliderForegroundColor="accent" transparent="1"/>
		<eLabel position="24,692" size="%d,1" backgroundColor="line" zPosition="-8"/>
		<widget name="description" position="30,700" size="%d,90" font="Regular;24" foregroundColor="fgDim" backgroundColor="bg" transparent="1"/>
	</screen>
''' % (EXT_W, EXT_W, EXT_W - 254, EXT_W - 180, EXT_W - 48, EXT_W - 60, EXT_W - 60, EXT_W - 48, EXT_W - 60)


def process(text, fileName):
	done = []

	def one(m):
		block = m.group(0)
		head = re.match(r"<screen\b[^>]*>", block).group(0)
		name = re.search(r'name="([^"]+)"', head).group(1)
		if "NG-DASH" in block or SKIP.match(name):
			return block
		pos = re.search(r'position="([^"]+)"', head)
		size = re.search(r'size="(\d+),(\d+)"', head)
		if not pos or not size:
			return block
		W, H = int(size.group(1)), int(size.group(2))
		p = pos.group(1)
		if W >= 1800 or H < 200 or not (p.startswith("center,center") or p.startswith("40,") or p == "center"):
			return block
		newHead = head.replace('position="%s"' % p, 'position="40,center"')
		body = block[len(head):]
		windowBg = re.search(r'backgroundColor="([^"]+)"', head)
		if windowBg and windowBg.group(1) != "transparent":
			# panel drawn by the window itself: draw it with a label instead, so the window can be wider
			newHead = re.sub(r'backgroundColor="[^"]+"', 'backgroundColor="transparent"', newHead)
			newHead = re.sub(r'\s*cornerRadius="[^"]*"', "", newHead)
			if "wfNoBorder" not in newHead:
				newHead = newHead[:-1] + ' flags="wfNoBorder">'
			body = '\n\t\t<eLabel position="0,0" size="%d,%d" backgroundColor="%s" cornerRadius="24" zPosition="-10"/>' % (W, H, windowBg.group(1)) + body
		if W <= SCALED_MAX:
			fit = (RIGHT - 40 - W - GAP) / float(DASH_W)
			s = max(q for q in SCALES if q <= fit + 1e-6) if fit < 1 else 1.0
			subject = subjectOf(name)
			x0 = W + GAP
			dw = round(DASH_W * s)
			newW = x0 + dw
			newH = max(H, DASH_H)
			newHead = re.sub(r'size="\d+,\d+"', 'size="%d,%d"' % (newW, newH), newHead, count=1)
			# the card set is one shared panel (written once below), placed beside this panel
			body = body.replace("</screen>", '\t\t<!-- NG-DASH %s cards -->\n\t\t<panel position="%d,0" size="%d,%d"><panel name="%s"/></panel>\n\t</screen>' % (
				subject, x0, dw, DASH_H, panelName(subject, s)))
			done.append("%s(%s%s)" % (name, subject, "" if s >= 0.999 else " %.2f" % s))
		else:
			body = body.replace("</screen>", "\t\t<!-- NG-DASH left only -->\n\t</screen>")
			done.append("%s(left)" % name)
		return newHead + body

	text = re.sub(r"<screen\b.*?</screen>", one, text, flags=re.S)
	print("%s: %d screens -> %s" % (fileName, len(done), ", ".join(done)))
	return text


path = os.path.join(SK, "skin.xml")
skin = open(path, encoding="utf-8").read()
if '<screen name="ExtensionsList"' not in skin:
	skin = skin.replace("</skin>", EXTENSIONS + "</skin>")
skin = re.sub(re.escape(PBEGIN) + ".*?" + re.escape(PEND) + "\n?", "", skin, flags=re.S)
skin = skin.replace("</skin>", "\t" + panels() + "</skin>")
open(path, "w", encoding="utf-8").write(process(skin, "skin.xml"))
lp = os.path.join(SK, "layouts", "menus_popup.xml")
lay = open(lp, encoding="utf-8").read()
open(lp, "w", encoding="utf-8").write(process(lay, "menus_popup.xml"))
