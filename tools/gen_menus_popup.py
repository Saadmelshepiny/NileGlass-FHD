#!/usr/bin/env python3
"""layouts/menus_popup.xml: menus as a rounded panel at the left with a system
dashboard beside it, settings as a rounded panel. argv: SKINDIR"""
import os, re, sys
SK = sys.argv[1]
PANEL = "bg"          # same panel colour (and transparency setting) as every other screen
UI = "NileGlass_FHD/ui/"

def lab(x, y, w, h, src, conv, font, color, halign="left", extra=""):
	c = "".join('<convert type="%s">%s</convert>' % cv for cv in conv)
	return '\t\t<widget source="%s" render="Label" position="%d,%d" size="%d,%d" font="%s" foregroundColor="%s" backgroundColor="%s" transparent="1" halign="%s" valign="center" noWrap="1"%s>%s</widget>' % (src, x, y, w, h, font, color, PANEL, halign, extra, c)

def text(x, y, w, h, t, font, color, halign="left"):
	return '\t\t<eLabel text="%s" position="%d,%d" size="%d,%d" font="%s" foregroundColor="%s" backgroundColor="%s" transparent="1" halign="%s" valign="center" noWrap="1"/>' % (t, x, y, w, h, font, color, PANEL, halign)

def pix(x, y, w, h, name, z=0):
	return '\t\t<ePixmap pixmap="%s%s" position="%d,%d" size="%d,%d" alphatest="blend" zPosition="%d"/>' % (UI, name, x, y, w, h, z)

def panel(w, top, bottom, tag=""):
	return ['\t\t<eLabel position="0,%d" size="%d,%d" backgroundColor="%s" cornerRadius="24" zPosition="-10"/>' % (top, w, bottom - top, PANEL)]

def header(w):
	return [pix(22, 22, 40, 40, "ng_logo.png", 1),
		'\t\t<widget source="Title" render="Label" position="74,16" size="%d,52" font="Medium;30" foregroundColor="accent" backgroundColor="%s" transparent="1" halign="left" valign="center" noWrap="1"/>' % (w - 250, PANEL),
		lab(w - 170, 16, 146, 52, "global.CurrentTime", [("ClockToText", "Format:%H:%M")], "Regular;38", "fg", "right"),
		'\t\t<eLabel position="22,82" size="%d,1" backgroundColor="line" zPosition="-8"/>' % (w - 44)]

import sys as _s, os as _o
_s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__)))
from dashlib import *  # noqa: F401,F403 (Dash, dashboard, SYS, FE ...)

TEMPLATE = '''			<convert type="TemplatedMultiContent">
				{"template": [
					MultiContentEntryPixmapAlphaBlend(pos=(500, 9), size=(40, 40), png=5, flags=BT_SCALE),
					MultiContentEntryText(pos=(16, 0), size=(470, 58), font=0, flags=RT_VALIGN_CENTER, text=0)
				],
				"fonts": [gFont("Regular", 30)],
				"itemHeight": 58
				}
			</convert>'''

# ---- Menu: panel 600 wide + dashboard; list 9 rows (fitted at run time)
W, LIST_Y, ROWS = 1290, 96, 9
LB = LIST_Y + ROWS * 58          # 618
PB = LB + 106                     # panel bottom 724
menu = panel(600, 0, PB) + header(600) + [
	'\t\t<widget source="menu" render="Listbox" position="20,%d" size="560,%d" selectionPixmap="%ssel_pn.png" scrollbarMode="showOnDemand" scrollbarWidth="4" scrollbarSliderForegroundColor="accent" backgroundColor="%s" foregroundColor="fg" foregroundColorSelected="white" transparent="1">\n%s\n\t\t</widget>' % (LIST_Y, ROWS * 58, UI, PANEL, TEMPLATE),
	'\t\t<eLabel position="22,%d" size="556,1" backgroundColor="line" zPosition="-8"/>' % (LB + 10),
	pix(24, LB + 30, 40, 40, "ng_logo.png", 1),
	text(76, LB + 22, 360, 32, "NileGlass FHD", "Medium;26", "fg"),
	lab(76, LB + 54, 180, 26, SYS, [("NGSysInfo", "Image")], "Regular;18", "fgDim"),
	lab(262, LB + 54, 200, 26, SYS, [("NGSysInfo", "BoxName")], "Regular;18", "fgMute"),
	lab(462, LB + 34, 114, 34, SYS, [("NGSysInfo", "SkinVersion")], "Medium;22", "gold", "right"),
	'\t\t<eLabel position="0,%d" size="600,52" backgroundColor="%s" cornerRadius="20" zPosition="-9"/>' % (PB + 14, PANEL),
	pix(22, PB + 25, 64, 30, "key_ok.png", 1), text(94, PB + 14, 90, 52, "فتح", "Regular;24", "fg"),
	pix(212, PB + 25, 64, 30, "key_exit.png", 1), text(284, PB + 14, 90, 52, "رجوع", "Regular;24", "fg"),
	pix(400, PB + 25, 64, 30, "key_menu.png", 1), text(472, PB + 14, 110, 52, "إغلاق", "Regular;24", "fg"),
] + dashboard(620)
H = PB + 66

# ---- Setup: panel 1280 wide
SW, SROWS = 960, 11
SLB = 96 + SROWS * 54
SPB = SLB + 220
setup = ['\t\t<eLabel position="0,0" size="%d,%d" backgroundColor="%s" cornerRadius="24" zPosition="-10"/>' % (SW, SPB, PANEL)] + header(SW) + [
	'\t\t<widget name="config" position="40,96" size="%d,%d" itemHeight="54" font="Regular;30" secondfont="Regular;28" selectionPixmap="%ssel_set.png" scrollbarMode="showOnDemand" scrollbarWidth="4" scrollbarSliderForegroundColor="accent" backgroundColor="%s" foregroundColor="fg" foregroundColorSelected="white" transparent="1" enableWrapAround="1"/>' % (SW - 80, SROWS * 54, UI, PANEL),
	'\t\t<eLabel position="22,%d" size="%d,1" backgroundColor="line" zPosition="-8"/>' % (SLB + 8, SW - 44),
	'\t\t<widget name="description" position="40,%d" size="%d,90" font="Regular;26" foregroundColor="fgDim" backgroundColor="%s" transparent="1"/>' % (SLB + 14, SW - 80, PANEL),
	'\t\t<widget name="footnote" position="40,%d" size="%d,34" font="Regular;22" foregroundColor="gold" backgroundColor="%s" transparent="1" noWrap="1"/>' % (SLB + 106, SW - 80, PANEL),
]
step = (SW - 80 - 200) // 3
for k, c in enumerate(("red", "green", "yellow", "blue")):
	x, y = 40 + k * step, SLB + 152
	setup += ['\t\t<ePixmap pixmap="NileGlass_FHD/buttons/%s_k200.png" position="%d,%d" size="200,38" alphatest="blend" conditional="key_%s"/>' % (c, x, y, c),
		'\t\t<widget name="key_%s" position="%d,%d" size="200,38" font="Medium;22" foregroundColor="white" backgroundColor="black" transparent="1" halign="center" valign="center" noWrap="1" zPosition="1" objectTypes="key_%s,Button,Label"/>' % (c, x, y, c),
		'\t\t<widget source="key_%s" render="Label" position="%d,%d" size="200,38" font="Medium;22" foregroundColor="white" backgroundColor="black" transparent="1" halign="center" valign="center" noWrap="1" zPosition="1" objectTypes="key_%s,StaticText"/>' % (c, x, y, c)]

setup += dashboard(SW + 20)
SWW = SW + 20 + 670
skin = open(os.path.join(SK, "skin.xml")).read()
menus = re.findall(r'<screen name="(menu_[^"]+)"[^>]*><panel name="Menu"/></screen>', skin)
out = ['<skin>', '\t<!-- Menus: rounded panel at the left + system dashboard; settings: rounded panel (style option "menus = popup") -->',
	'\t<screen name="Menu" position="40,center" size="%d,%d" backgroundColor="transparent" flags="wfNoBorder">' % (W, H)] + menu + ['\t</screen>',
	'\t<screen name="Setup" position="40,center" size="%d,%d" backgroundColor="transparent" flags="wfNoBorder">' % (SWW, SPB)] + setup + ['\t</screen>']
out += ['\t<screen name="%s" position="40,center" size="%d,%d" backgroundColor="transparent" flags="wfNoBorder"><panel name="Menu"/></screen>' % (n, W, H) for n in menus]


def keys(w, h):
	xs = [24 + i * ((w - 48 - 200) // 3) for i in range(4)]
	y = h - 56
	o = ['\t\t<eLabel position="24,%d" size="%d,1" backgroundColor="line" zPosition="-8"/>' % (h - 74, w - 48)]
	for k, x in zip(("red", "green", "yellow", "blue"), xs):
		c = 'position="%d,%d" size="200,38" font="Medium;22" foregroundColor="white" backgroundColor="black" transparent="1" halign="center" valign="center" noWrap="1" zPosition="1"' % (x, y)
		o += ['\t\t<ePixmap pixmap="NileGlass_FHD/buttons/%s_k200.png" position="%d,%d" size="200,38" alphatest="blend" conditional="key_%s"/>' % (k, x, y, k),
			'\t\t<widget name="key_%s" %s objectTypes="key_%s,Button,Label"/>' % (k, c, k),
			'\t\t<widget source="key_%s" render="Label" %s objectTypes="key_%s,StaticText"/>' % (k, c, k)]
	return o


def leftify(name, w, maxX=1880):
	"""a full-frame screen of skin.xml as a left panel: same widgets, moved and narrowed"""
	m = re.search(r'<screen name="%s"[^>]*>(.*?)</screen>' % name, skin, re.S)
	body = m.group(1)
	els = re.findall(r'(<(widget|eLabel|ePixmap)\b[^>]*?(?:/>|>.*?</widget>))', body, re.S)
	kept = []
	for xml, tag in els:
		a = dict(re.findall(r'(\w+)="([^"]*)"', xml.split(">", 1)[0]))
		src = a.get("source", "")
		if tag != "widget" or src.startswith(("session.", "global.")) or src == "Title" or (a.get("name") or src).startswith("key_"):
			continue
		x, y = (int(v) for v in a["position"].split(","))
		ww, hh = (int(v) for v in a["size"].split(","))
		if x >= maxX:
			continue
		kept.append([xml, x, y, ww, hh])
	bx, by = min(k[1] for k in kept), min(k[2] for k in kept)
	bh = max(k[2] + k[4] for k in kept) - by
	h = 100 + bh + 16 + 74
	o = ['\t<screen name="%s" position="40,center" size="%d,%d" backgroundColor="transparent" flags="wfNoBorder">' % (name, w, h),
		'\t\t<eLabel position="0,0" size="%d,%d" backgroundColor="bg" cornerRadius="24" zPosition="-10"/>' % (w, h),
		'\t\t<ePixmap pixmap="NileGlass_FHD/ui/ng_logo.png" position="22,24" size="40,40" alphatest="blend" zPosition="1"/>',
		'\t\t<widget source="Title" render="Label" position="74,16" size="%d,56" font="Medium;30" foregroundColor="accent" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>' % (w - 254),
		'\t\t<widget source="global.CurrentTime" render="Label" position="%d,16" size="156,56" font="Regular;38" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="right" valign="center" noWrap="1"><convert type="ClockToText">Format:%%H:%%M</convert></widget>' % (w - 180),
		'\t\t<eLabel position="24,84" size="%d,1" backgroundColor="line" zPosition="-8"/>' % (w - 48)]
	for xml, x, y, ww, hh in kept:
		nx, ny, nw = x - bx + 24, y - by + 100, min(ww, w - 48 - (x - bx))
		xml = re.sub(r'position="[^"]*"', 'position="%d,%d"' % (nx, ny), xml, count=1)
		xml = re.sub(r'size="[^"]*"', 'size="%d,%d"' % (nw, hh), xml, count=1)
		o.append("\t\t" + xml.strip())
	return o + keys(w, h) + ['\t</screen>']


for _n, _w, _mx in (("PluginBrowser", 1100, 1880), ("PluginDownloadBrowser", 1100, 1880), ("TimerEditList", 1300, 1880), ("PowerTimerEditList", 1300, 1880),
		("HelpMenu", 1100, 1880), ("AboutOE", 1250, 1300), ("TextBox", 1250, 1880), ("Console", 1250, 1880), ("OscamInfoMenu", 1100, 1880),
		("oscInfo", 1250, 1880), ("oscECMInfo", 1250, 1880), ("PositionerSetupLog", 1250, 1880)):
	out += leftify(_n, _w, _mx)
out.append('</skin>\n')
open(os.path.join(SK, "layouts", "menus_popup.xml"), "w").write("\n".join(out))
print("menus_popup.xml:", len(menus), "menu screens, menu panel", W, "x", H)
