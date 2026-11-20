#!/usr/bin/env python3
"""Writes the OpenBh panel / popup screens, Blue Panel, Volume and Dish into
skin.xml between <!-- NG_POPUPS_BEGIN --> and <!-- NG_POPUPS_END -->.
Screens with the same name elsewhere in skin.xml are removed first."""
import re
import sys

SKIN = sys.argv[1]
s = open(SKIN, encoding="utf-8").read()

LISTATTR = 'backgroundColor="bg" foregroundColor="fg" foregroundColorSelected="white" backgroundColorSelected="bgSel" scrollbarMode="showOnDemand" scrollbarWidth="6" scrollbarSliderForegroundColor="accent" transparent="1"'
PILL = {2: ("k260", 260), 3: ("k260", 260), 4: ("k200", 200)}


def frame(w, h, buttons=()):
	out = [
		'<eLabel position="0,0" size="%d,%d" backgroundColor="bg" zPosition="-10"/>' % (w, h),
		'<eLabel position="0,0" size="%d,3" backgroundColor="lineAccent" zPosition="-9"/>' % w,
		'<widget source="Title" render="Label" position="36,12" size="%d,64" font="Medium;38" foregroundColor="accent" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>' % (w - 300),
		'<widget source="global.CurrentTime" render="Label" position="%d,12" size="220,64" font="Regular;40" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="right" valign="center" noWrap="1"><convert type="ClockToText">Format:%%H:%%M</convert></widget>' % (w - 256),
		'<eLabel position="0,88" size="%d,1" backgroundColor="line"/>' % w,
	]
	if buttons:
		out.append('<eLabel position="0,%d" size="%d,1" backgroundColor="line"/>' % (h - 84, w))
		img, bw = PILL[max(2, len(buttons))]
		gap = (w - len(buttons) * bw) // (len(buttons) + 1)
		for i, b in enumerate(buttons):
			x = gap + i * (bw + gap)
			out.append('<ePixmap pixmap="NileGlass_FHD/buttons/%s_%s.png" position="%d,%d" size="%d,50" alphatest="blend"/>' % (b, img, x, h - 67, bw))
			out.append('<widget name="key_%s" position="%d,%d" size="%d,50" font="Medium;28" foregroundColor="white" backgroundColor="black" transparent="1" halign="center" valign="center" noWrap="1" zPosition="1"/>' % (b, x, h - 67, bw))
	return out


def iconList(x, y, w, rows, ih=64, font=32):
	return ('<widget source="list" render="Listbox" position="%d,%d" size="%d,%d" backgroundColor="bg" foregroundColor="fg" foregroundColorSelected="white" backgroundColorSelected="bgSel" scrollbarMode="showOnDemand" scrollbarWidth="6" scrollbarSliderForegroundColor="accent" transparent="1">'
		'<convert type="TemplatedMultiContent">{"template": ['
		'MultiContentEntryPixmapAlphaBlend(pos=(18, %d), size=(48, 48), png=1, flags=BT_SCALE|BT_KEEP_ASPECT_RATIO|BT_HALIGN_CENTER|BT_VALIGN_CENTER), '
		'MultiContentEntryText(pos=(88, 0), size=(%d, %d), font=0, flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER, text=0)], '
		'"fonts": [gFont("Regular", %d)], "itemHeight": %d}</convert></widget>') % (x, y, w, rows * ih, (ih - 48) // 2, w - 110, ih, font, ih)


def stringList(x, y, w, rows, ih=56, font=30):
	return ('<widget source="list" render="Listbox" position="%d,%d" size="%d,%d" font="Regular;%d" itemHeight="%d" backgroundColor="bg" foregroundColor="fg" foregroundColorSelected="white" backgroundColorSelected="bgSel" scrollbarMode="showOnDemand" scrollbarWidth="6" scrollbarSliderForegroundColor="accent" transparent="1"><convert type="StringList"/></widget>') % (x, y, w, rows * ih, font, ih)


def configList(x, y, w, rows, ih=56):
	return ('<widget name="config" position="%d,%d" size="%d,%d" itemHeight="%d" font="Regular;30" secondfont="Regular;30" foregroundColor="fg" backgroundColor="bg" foregroundColorSelected="white" backgroundColorSelected="bgSel" scrollbarMode="showOnDemand" scrollbarWidth="6" scrollbarSliderForegroundColor="accent" transparent="1"/>') % (x, y, w, rows * ih, ih)


def text(name, x, y, w, h, font="Regular;28", fg="fg", extra=""):
	return '<widget name="%s" position="%d,%d" size="%d,%d" font="%s" foregroundColor="%s" backgroundColor="bg" transparent="1" halign="left" %s/>' % (name, x, y, w, h, font, fg, extra)


def card(x, y, w, h):
	return '<eLabel position="%d,%d" size="%d,%d" backgroundColor="bgCard" zPosition="-5"/>' % (x, y, w, h)


# titles of the embedded OpenBh skins (a skin.xml screen replaces them, title included)
TITLES = {}
if len(sys.argv) > 2:
	import glob
	for f in glob.glob(sys.argv[2] + "/lib/python/Screens/*.py"):
		t = open(f, encoding="utf-8", errors="replace").read()
		for m in re.finditer(r"\nclass (\w+)\(.*?skin = \"\"\"\s*<screen[^>]*title=\"([^\"]+)\"", t, re.S):
			TITLES.setdefault(m.group(1), m.group(2))


def screen(name, w, h, body, buttons=(), title=None):
	title = title or TITLES.get(name)
	attrs = ' title="%s"' % title if title else ""
	lines = ['\t<screen name="%s" position="center,center" size="%d,%d" backgroundColor="transparent" flags="wfNoBorder"%s>' % (name, w, h, attrs)]
	lines += ["\t\t" + x for x in frame(w, h, buttons) + body]
	lines.append("\t</screen>")
	return "\n".join(lines)


screens = []
# ---- icon menus (OpenBh Addons Manager, Downloads, Green Panel setup, Extra Settings)
for n in ("DeliteAddons", "Nab_downArea", "BhSetupGreen"):
	screens.append(screen(n, 960, 720, [iconList(30, 104, 900, 9)]))
screens.append(screen("DeliteSettings", 1000, 980, [iconList(30, 104, 940, 13)]))
screens.append(screen("DeliteSetupFp", 960, 820, [stringList(30, 104, 900, 11)], ("red",)))
# ---- package lists
for n in ("Nab_downCat", "Nab_downPanel", "Nab_uninstPanel"):
	screens.append(screen(n, 1240, 880, [stringList(30, 104, 1180, 13)]))
screens.append(screen("Nab_downPanelIPK", 1240, 880, [stringList(30, 104, 1180, 11), card(30, 732, 1180, 120),
	text("warntext", 50, 742, 1140, 100, "Regular;28", "gold", 'valign="center"')]))
# ---- script panel: full description of the selected script
screens.append(screen("DeliteScript", 1240, 900, [stringList(30, 104, 1180, 10), card(30, 676, 1180, 120),
	text("statuslab", 50, 684, 1140, 104, "Regular;28", "gold", 'valign="center"')], ("green",)))
# ---- text pages
screens.append(screen("Nab_ShowDownFile", 1240, 880, [text("infotext", 40, 104, 1160, 670, "Regular;28")], ("green", "yellow")))
for n in ("Nab_Stats", "NabEnsetInfo", "DeliteInaLog", "DeliteVpnLog"):
	screens.append(screen(n, 1240, 880, [text("infotext", 40, 104, 1160, 750, "Regular;28")]))
screens.append(screen("NabProcInfo", 1240, 880, [text("pibartit", 40, 100, 1160, 44, "Medium;28", "accent"), text("infotext", 40, 150, 1160, 700, "Regular;26")]))
screens.append(screen("BhBackupSettings", 1240, 620, [text("infotext", 40, 104, 1160, 420, "Regular;28")], ("red",)))
# ---- config screens
screens.append(screen("BhGreenPluginsSetup", 1240, 880, [configList(40, 104, 1160, 12)], ("red", "green", "blue")))
screens.append(screen("BhSpeedUp", 1240, 960, [text("lab1", 40, 100, 1160, 90, "Regular;26", "fgDim"), configList(40, 196, 1160, 11)], ("red", "green")))
screens.append(screen("DeliteSetupAutocam2", 1240, 700, [configList(40, 104, 1160, 8)], ("green",)))
screens.append(screen("addonsParentalConfig", 1240, 700, [configList(40, 104, 1160, 8)], ("red", "green")))
screens.append(screen("DeliteInaSetup", 1240, 700, [configList(40, 104, 1160, 8)], ("green",)))
screens.append(screen("DeliteAutocamMan2", 1240, 880, [card(30, 100, 1180, 60), text("defaultcam", 50, 100, 1140, 60, "Medium;30", "gold", 'valign="center"'),
	stringList(30, 176, 1180, 11)], ("red", "green")))
screens.append(screen("BhNetBrowser", 1240, 880, [stringList(30, 104, 1180, 12)], ("red", "green")))

# ---- Blue Panel: emu + live decoding info
blue = [
	text("lab1", 40, 104, 720, 44, "Regular;30", "fgDim", 'valign="center"'),
	'<widget name="list" position="40,156" size="720,60" itemHeight="58" font="Medium;34" foregroundColor="fg" backgroundColor="bgCard" foregroundColorSelected="white" backgroundColorSelected="bgSel" scrollbarMode="showNever"/>',
	text("lab2", 40, 226, 720, 40, "Regular;26", "fgDim", 'valign="center"'),
	text("lab3", 40, 276, 720, 50, "Medium;34", "accent", 'valign="center"'),
	text("activecam", 40, 276, 720, 50, "Medium;34", "accent", 'valign="center"'),
	'<eLabel position="40,340" size="720,1" backgroundColor="line"/>',
	text("Ilab1", 40, 352, 720, 44, "Regular;28", "fg", 'valign="center" noWrap="1"'),
	text("Ilab2", 40, 398, 720, 44, "Regular;28", "fg", 'valign="center" noWrap="1"'),
	text("Ilab3", 40, 444, 720, 44, "Regular;28", "fg", 'valign="center" noWrap="1"'),
	text("Ilab4", 40, 490, 720, 44, "Regular;28", "fg", 'valign="center" noWrap="1"'),
	'<ePixmap pixmap="NileGlass_FHD/ui/picon_bg.png" position="40,560" size="222,134" alphatest="blend"/>',
	'<widget source="session.CurrentService" render="Picon" position="41,561" size="220,132" alphatest="blend" zPosition="1"><convert type="ServiceName">Reference</convert></widget>',
	'<widget source="session.CurrentService" render="Label" position="290,560" size="470,50" font="Medium;32" foregroundColor="fg" backgroundColor="bg" transparent="1" noWrap="1"><convert type="ServiceName">Name</convert></widget>',
	'<widget source="session.CurrentService" render="Label" position="290,612" size="470,40" font="Regular;26" foregroundColor="fgDim" backgroundColor="bg" transparent="1" noWrap="1"><convert type="PliExtraInfo">TransponderInfo</convert></widget>',
	'<widget source="session.CurrentService" render="Label" position="290,654" size="470,40" font="Regular;26" foregroundColor="fgDim" backgroundColor="bg" transparent="1" noWrap="1"><convert type="PliExtraInfo">PIDInfo</convert></widget>',
	'<eLabel position="790,104" size="1,750" backgroundColor="line"/>',
	card(820, 104, 740, 750),
	'<eLabel text="فك التشفير" position="844,114" size="700,44" font="ArabicBold;30" foregroundColor="accent" backgroundColor="bgCard" transparent="1"/>',
	'<widget source="session.CurrentService" render="Label" position="844,162" size="700,44" font="Regular;30" foregroundColor="fgDim" backgroundColor="bgCard" transparent="1" noWrap="1"><convert type="PliExtraInfo">CryptoBar</convert></widget>',
	'<widget source="session.CurrentService" render="Label" position="844,212" size="700,48" font="Medium;32" foregroundColor="gold" backgroundColor="bgCard" transparent="1" noWrap="1"><convert type="NGEcm">State</convert></widget>',
]
y = 270
for label, typ in (("الإيمو", "Cam"), ("الشفرة", "Caid"), ("المصدر", "Source"), ("البروتوكول", "Protocol"), ("Hops", "Hops"), ("وقت ECM", "Time")):
	blue.append('<eLabel text="%s" position="844,%d" size="200,40" font="Regular;26" foregroundColor="fgDim" backgroundColor="bgCard" transparent="1" halign="left" valign="center"/>' % (label, y))
	blue.append('<widget source="session.CurrentService" render="Label" position="1050,%d" size="494,40" font="Regular;28" foregroundColor="fg" backgroundColor="bgCard" transparent="1" halign="left" valign="center" noWrap="1"><convert type="NGEcm">%s</convert></widget>' % (y, typ))
	y += 44
blue += [
	'<eLabel position="844,%d" size="700,1" backgroundColor="line"/>' % (y + 6),
	'<widget name="Ecmtext" position="844,%d" size="700,%d" font="Regular;22" foregroundColor="fgDim" backgroundColor="bgCard" transparent="1" halign="left"/>' % (y + 16, 840 - y - 16),
]
screens.append(screen("DeliteBluePanel", 1600, 960, blue, ("red", "green", "yellow", "blue"), "OpenBh Blue Panel"))

# ---- Volume with percent
screens.append('''	<screen name="Volume" position="1250,56" size="630,104" backgroundColor="transparent" flags="wfNoBorder">
		<eLabel position="0,0" size="630,104" backgroundColor="bg" zPosition="-10"/>
		<eLabel position="0,0" size="630,3" backgroundColor="lineAccent" zPosition="-9"/>
		<ePixmap pixmap="NileGlass_FHD/ui/speaker.png" position="22,24" size="56,56" alphatest="blend"/>
		<eLabel position="96,46" size="360,14" backgroundColor="bgBar" zPosition="-9"/>
		<widget name="Volume" position="96,46" size="360,14" pixmap="NileGlass_FHD/ui/volume.png" transparent="1" zPosition="1"/>
		<widget source="session.CurrentService" render="VolumeText" position="460,20" size="106,64" font="Medium;44" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="right" valign="center" noWrap="1" zPosition="2"/>
		<eLabel text="%" position="568,30" size="44,50" font="Regular;32" foregroundColor="accent" backgroundColor="bg" transparent="1" halign="left" valign="center"/>
	</screen>''')

# ---- Dish: banner at the top while the motor turns
screens.append('''	<screen name="Dish" position="center,30" size="960,150" backgroundColor="transparent" flags="wfNoBorder">
		<eLabel position="0,0" size="960,150" backgroundColor="bg" zPosition="-10"/>
		<eLabel position="0,0" size="960,3" backgroundColor="lineAccent" zPosition="-9"/>
		<widget name="Dishpixmap" pixmap="NileGlass_FHD/ui/dish.png" position="24,27" size="96,96" alphatest="blend" zPosition="1"/>
		<eLabel text="الطبق يتحرك" position="140,12" size="420,50" font="Medium;36" foregroundColor="accent" backgroundColor="bg" transparent="1" halign="left" valign="center"/>
		<widget name="From" position="140,66" size="110,40" font="Regular;26" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="left" valign="center"/>
		<widget name="posFrom" position="250,66" size="200,40" font="Medium;30" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="left" valign="center"/>
		<widget name="Goto" position="460,66" size="110,40" font="Regular;26" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="left" valign="center"/>
		<widget name="posGoto" position="570,66" size="200,40" font="Medium;30" foregroundColor="gold" backgroundColor="bg" transparent="1" halign="left" valign="center"/>
		<widget name="Tuner" position="140,106" size="110,36" font="Regular;24" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="left" valign="center"/>
		<widget name="tunerName" position="250,106" size="300,36" font="Regular;26" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="left" valign="center"/>
		<widget name="turnTime" position="780,20" size="160,70" font="Medium;54" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="right" valign="center"/>
		<widget name="turnSpeed" position="700,96" size="240,40" font="Regular;24" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="right" valign="center"/>
	</screen>''')

# ---- audio / subtitle choice: compact, settings on top with room, tracks below, no live picture
_au = ['\t<screen name="AudioSelection" position="center,center" size="1240,968" backgroundColor="transparent" flags="wfNoBorder">']
_au += ["\t\t" + x for x in frame(1240, 968)]
_au += ['\t\t<widget source="global.CurrentTime" render="Label" position="700,12" size="270,64" font="Regular;26" foregroundColor="gold" backgroundColor="bg" transparent="1" halign="right" valign="center" noWrap="1"><convert type="ClockToText">Format:%A %d %B</convert></widget>',
	'\t\t<!-- settings: the first four follow the colour keys -->',
	'\t\t<widget name="config" position="84,100" size="1126,504" itemHeight="56" font="Regular;30" secondfont="Regular;30" %s/>' % LISTATTR]
for i, c in enumerate(("red", "green", "yellow", "blue")):
	_au.append('\t\t<widget source="key_%s" render="Pixmap" pixmap="NileGlass_FHD/buttons/%s.png" position="40,%d" size="30,30" alphatest="blend" zPosition="2"><convert type="ConditionalShowHide"/></widget>' % (c, c, 113 + i * 56))
_au += ['\t\t<eLabel position="30,616" size="1180,1" backgroundColor="line"/>',
	'\t\t<widget source="session.CurrentService" render="Label" position="40,624" size="620,40" font="Medium;26" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"><convert type="ServiceName">Name</convert></widget>',
	'\t\t<widget source="session.CurrentService" render="Label" position="680,624" size="520,40" font="Regular;24" foregroundColor="gold" backgroundColor="bg" transparent="1" halign="right" valign="center" noWrap="1"><convert type="ServiceInfo">AudioCodec</convert></widget>',
	'\t\t<!-- audio / subtitle tracks -->',
	'\t\t<widget source="streams" render="Listbox" position="30,670" size="1180,224" %s>' % LISTATTR,
	'\t\t\t<convert type="TemplatedMultiContent">',
	'\t\t\t\t{"template": [',
	'\t\t\t\t\tMultiContentEntryText(pos=(10, 0), size=(56, 56), font=0, flags=RT_HALIGN_CENTER|RT_VALIGN_CENTER, text=2),',
	'\t\t\t\t\tMultiContentEntryText(pos=(80, 0), size=(300, 56), font=1, flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER, text=3, color="#9aa3ae", color_sel="#ffffff"),',
	'\t\t\t\t\tMultiContentEntryText(pos=(400, 0), size=(700, 56), font=0, flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER, text=4),',
	'\t\t\t\t\tMultiContentEntryPixmapAlphaBlend(pos=(1124, 12), size=(32, 32), png=6, flags=BT_SCALE|BT_KEEP_ASPECT_RATIO)',
	'\t\t\t\t],',
	'\t\t\t\t"fonts": [gFont("Regular", 30), gFont("Regular", 24)],',
	'\t\t\t\t"itemHeight": 56',
	'\t\t\t\t}',
	'\t\t\t</convert>',
	'\t\t</widget>',
	'\t\t<eLabel position="30,906" size="1180,1" backgroundColor="line"/>',
	'\t\t<eLabel text="OK  اختيار المسار       MENU  اللغة التلقائية للصوت والترجمة" position="30,916" size="1180,40" font="Regular;22" foregroundColor="fgMute" backgroundColor="bg" transparent="1" halign="center" valign="center"/>',
	'\t</screen>']
screens.append("\n".join(_au))

# ---- more OpenBh screens in the frame of the skin (1.9/2.0)
def full(name, body, title=None):
	t = ' title="%s"' % title if title else ""
	return '\t<screen name="%s" position="0,0" size="1920,1080" backgroundColor="transparent" flags="wfNoBorder"%s>\n\t\t<panel name="NG_Frame"/>\n' % (name, t) + "".join("\t\t" + b + "\n" for b in body) + "\t</screen>"


def pbtn(w, h, keys):
	"""Colour keys of a centred popup; Button/Label and StaticText alike."""
	out = ['<eLabel position="0,%d" size="%d,1" backgroundColor="line"/>' % (h - 84, w)]
	img, bw = PILL[max(2, len(keys))]
	gap = (w - len(keys) * bw) // (len(keys) + 1)
	for i, b in enumerate(keys):
		x = gap + i * (bw + gap)
		out.append('<ePixmap pixmap="NileGlass_FHD/buttons/%s_%s.png" position="%d,%d" size="%d,38" alphatest="blend" conditional="key_%s"/>' % (b, img, x, h - 61, bw, b))
		attrs = 'position="%d,%d" size="%d,38" font="Medium;24" foregroundColor="white" backgroundColor="black" transparent="1" halign="center" valign="center" noWrap="1" zPosition="1"' % (x, h - 61, bw)
		out.append('<widget name="key_%s" %s objectTypes="key_%s,Button,Label"/>' % (b, attrs, b))
		out.append('<widget source="key_%s" render="Label" %s objectTypes="key_%s,StaticText"/>' % (b, attrs, b))
	return out


def popup(name, w, h, body, keys=(), title=None, pos="center,center"):
	"""Centred popup in the skin's frame (title from the screen, clock)."""
	t = ' title="%s"' % title if title else ""
	lines = ['\t<screen name="%s" position="%s" size="%d,%d" backgroundColor="transparent" flags="wfNoBorder"%s>' % (name, pos, w, h, t)]
	fr = frame(w, h)
	if keys:
		fr += pbtn(w, h, keys)
	lines += ["\t\t" + x for x in fr + body]
	lines.append("\t</screen>")
	return "\n".join(lines)


def lab(name, x, y, w, h, font="Regular;28", fg="fg", bg="bg", extra='halign="left" valign="center"'):
	return '<widget name="%s" position="%d,%d" size="%d,%d" font="%s" foregroundColor="%s" backgroundColor="%s" transparent="1" %s/>' % (name, x, y, w, h, font, fg, bg, extra)


def src(name, x, y, w, h, font="Regular;28", fg="fg", bg="bg", extra='halign="left" valign="center"'):
	return '<widget source="%s" render="Label" position="%d,%d" size="%d,%d" font="%s" foregroundColor="%s" backgroundColor="%s" transparent="1" %s/>' % (name, x, y, w, h, font, fg, bg, extra)


def compact(name, body, keys=("red", "green", "yellow", "blue"), k=0.82, title=None):
	"""A full-screen design (content at 80,146 .. 1840,940) as a centred,
	smaller popup: positions and sizes x k, fonts x 0.9, list rows kept whole."""
	import re as _re
	W = round(1760 * k) + 60
	H = 104 + round(794 * k) + 10 + 84

	def pos(m):
		x, y = int(m.group(1)), int(m.group(2))
		return 'position="%d,%d"' % (round((x - 80) * k) + 30, round((y - 146) * k) + 104)

	def font(m):
		return 'font="%s;%d"' % (m.group(1), max(18, round(int(m.group(2)) * 0.9)))

	out = []
	for line in body:
		ih = _re.search(r'itemHeight="(\d+)"', line)
		size = _re.search(r'size="(\d+),(\d+)"', line)
		if ih and size:
			rows = max(1, round(int(size.group(2)) / int(ih.group(1))))
			nih = round(int(ih.group(1)) * 0.86)
			line = line.replace(ih.group(0), 'itemHeight="%d"' % nih)
			line = line.replace(size.group(0), 'size="%d,%d"' % (round(int(size.group(1)) * k), rows * nih))
		elif size:
			line = line.replace(size.group(0), 'size="%d,%d"' % (round(int(size.group(1)) * k), max(1, round(int(size.group(2)) * k))))
		line = _re.sub(r'position="(\d+),(\d+)"', pos, line, count=1)
		line = _re.sub(r'(?<!second)font="(\w+);(\d+)"', font, line)
		line = _re.sub(r'secondfont="(\w+);(\d+)"', lambda m: 'secondfont="%s;%d"' % (m.group(1), max(18, round(int(m.group(2)) * 0.9))), line)
		line = line.replace("ui/signal_xl", "ui/signal_l")
		out.append(line)
	return popup(name, W, H, out, keys, title)


screens.append(full("TimerEditList", ['<widget name="timerlist" position="60,146" size="1800,700" itemHeight="100" %s/>' % LISTATTR,
	'<eLabel position="60,860" size="1800,1" backgroundColor="line"/>',
	'<widget name="description" position="60,868" size="1800,84" font="Regular;26" foregroundColor="fgDim" backgroundColor="bg" transparent="1"/>']))
screens.append(full("PowerTimerEditList", ['<widget name="timerlist" position="60,146" size="1800,700" itemHeight="100" %s/>' % LISTATTR,
	'<eLabel position="60,860" size="1800,1" backgroundColor="line"/>',
	'<widget name="description" position="60,868" size="1800,84" font="Regular;26" foregroundColor="fgDim" backgroundColor="bg" transparent="1"/>']))
screens.append(full("PluginDownloadBrowser", ['<widget name="text" position="60,146" size="1800,50" font="Regular;30" foregroundColor="gold" backgroundColor="bg" transparent="1"/>',
	'<widget name="list" position="60,206" size="1800,740" itemHeight="100" %s/>' % LISTATTR]))
screens.append(screen("ChannelContextMenu", 1100, 860, ['<widget name="menu" position="30,104" size="1040,728" itemHeight="56" %s/>' % LISTATTR]))
screens.append(screen("MovieContextMenu", 1100, 860, ['<widget name="config" position="30,104" size="1040,560" itemHeight="56" %s/>' % LISTATTR,
	'<eLabel position="30,676" size="1040,1" backgroundColor="line"/>',
	'<widget source="description" render="Label" position="30,684" size="1040,80" font="Regular;26" foregroundColor="fgDim" backgroundColor="bg" transparent="1"/>',
	'<widget name="footnote" position="30,766" size="1040,30" font="Regular;22" foregroundColor="gold" backgroundColor="bg" transparent="1"/>']))
screens.append(screen("InputBox", 1240, 380, ['<widget name="text" position="40,104" size="1160,100" font="Regular;30" foregroundColor="fg" backgroundColor="bg" transparent="1" valign="center"/>',
	card(40, 214, 1160, 70), '<widget name="input" position="60,214" size="1120,70" font="Medium;38" foregroundColor="white" backgroundColor="bgCard" transparent="1" valign="center"/>']))
screens.append(full("HelpMenu", ['<widget name="list" position="60,146" size="1800,800" itemHeight="56" %s/>' % LISTATTR]))

wx = [card(60, 146, 1800, 280),
	'<widget name="now_icon" position="90,176" size="200,200" alphatest="blend" scale="1" zPosition="1"/>',
	'<widget name="now_temp" position="320,170" size="420,130" font="Medium;110" foregroundColor="fg" backgroundColor="bgCard" transparent="1" halign="left" valign="center" noWrap="1"/>',
	'<widget name="now_desc" position="320,300" size="900,56" font="Regular;38" foregroundColor="accent" backgroundColor="bgCard" transparent="1" halign="left" valign="center" noWrap="1"/>',
	'<widget name="now_extra" position="320,360" size="1500,44" font="Regular;28" foregroundColor="fgDim" backgroundColor="bgCard" transparent="1" halign="left" valign="center" noWrap="1"/>',
	'<widget name="city" position="1100,170" size="720,80" font="Medium;54" foregroundColor="gold" backgroundColor="bgCard" transparent="1" halign="right" valign="center" noWrap="1"/>',
	'<widget name="updated" position="1100,250" size="720,40" font="Regular;24" foregroundColor="fgMute" backgroundColor="bgCard" transparent="1" halign="right" valign="center" noWrap="1"/>']
for i in range(5):
	x = 60 + i * 364
	wx += [card(x, 446, 344, 490),
		'<widget name="day%d" position="%d,462" size="344,50" font="Medium;34" foregroundColor="accent" backgroundColor="bgCard" transparent="1" halign="center" valign="center" noWrap="1"/>' % (i, x),
		'<widget name="icon%d" position="%d,526" size="150,150" alphatest="blend" scale="1" zPosition="1"/>' % (i, x + 97),
		'<widget name="temp%d" position="%d,690" size="344,60" font="Medium;40" foregroundColor="fg" backgroundColor="bgCard" transparent="1" halign="center" valign="center" noWrap="1"/>' % (i, x),
		'<widget name="desc%d" position="%d,760" size="324,160" font="Regular;28" foregroundColor="fgDim" backgroundColor="bgCard" transparent="1" halign="center" valign="top"/>' % (i, x + 10)]
screens.append(full("NileGlassWeather", wx))

up = ['<widget name="channel" position="80,140" size="1000,46" font="Medium;30" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>',
	'<widget name="count" position="1440,140" size="400,46" font="Regular;28" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="right" valign="center" noWrap="1"/>']
for i in range(6):
	x = 140 + i * 278
	up += ['<widget name="sel%d" position="%d,190" size="262,431" backgroundColor="accent" zPosition="0"/>' % (i, x - 6),
		'<ePixmap pixmap="NileGlass_FHD/ui/noposter.png" position="%d,196" size="250,375" scale="1" zPosition="1"/>' % x,
		'<widget name="poster%d" position="%d,196" size="250,375" scale="1" zPosition="2"/>' % (i, x),
		'<widget name="time%d" position="%d,576" size="250,40" font="Medium;30" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="center" valign="center" noWrap="1" zPosition="3"/>' % (i, x)]
up += ['<eLabel position="80,632" size="1760,1" backgroundColor="line"/>',
	'<widget name="title" position="80,640" size="1100,56" font="Medium;40" foregroundColor="accent" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>',
	'<widget name="when" position="80,698" size="1100,40" font="Regular;28" foregroundColor="gold" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>',
	'<widget name="info" position="80,740" size="1100,38" font="Regular;27" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>',
	'<widget name="desc" position="80,782" size="1100,166" font="Regular;28" foregroundColor="#d6dbe1" backgroundColor="bg" transparent="1" halign="left"/>',
	card(1210, 644, 630, 304),
	'<widget name="card" position="1230,656" size="590,280" font="Regular;27" foregroundColor="fg" backgroundColor="bgCard" transparent="1" halign="left"/>']
screens.append(full("NileGlassUpcoming", up))

fp = ['\t<screen name="NileGlassFilm" position="0,0" size="1920,1080" backgroundColor="transparent" flags="wfNoBorder">',
	'\t\t<eLabel position="0,0" size="1920,1080" backgroundColor="#00060709" zPosition="-30"/>',
	'\t\t<widget name="backdrop" position="0,0" size="1920,1080" scale="1" zPosition="-20"/>',
	'\t\t<eLabel position="0,0" size="1920,1080" backgroundColor="#38060709" zPosition="-15"/>',
	'\t\t<eLabel position="0,0" size="1920,3" backgroundColor="lineAccent" zPosition="-9"/>',
	'\t\t<eLabel position="76,76" size="368,548" backgroundColor="posterBorder" zPosition="1"/>',
	'\t\t<ePixmap pixmap="NileGlass_FHD/ui/noposter.png" position="80,80" size="360,540" scale="1" zPosition="2"/>',
	'\t\t<widget name="poster" position="80,80" size="360,540" scale="1" zPosition="3"/>',
	'\t\t<widget name="title" position="480,76" size="1360,70" font="Medium;54" foregroundColor="accent" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>',
	'\t\t<widget name="original" position="480,148" size="1360,40" font="Regular;30" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>',
	'\t\t<widget name="facts" position="480,192" size="1360,42" font="Regular;30" foregroundColor="gold" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>',
	'\t\t<widget name="ratings" position="480,238" size="1360,46" font="Medium;34" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>',
	'\t\t<widget name="story" position="480,296" size="1360,206" font="Regular;29" foregroundColor="#e6e9ec" backgroundColor="bg" transparent="1" halign="left"/>',
	'\t\t<widget name="crew" position="480,512" size="1360,110" font="Regular;26" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="left"/>',
	'\t\t<eLabel text="الأبطال" position="80,640" size="400,40" font="ArabicBold;28" foregroundColor="accent" backgroundColor="bg" transparent="1" halign="left"/>']
for i in range(6):
	x = 80 + i * 186
	fp += ['\t\t<eLabel position="%d,686" size="140,210" backgroundColor="bgCard" zPosition="0"/>' % x,
		'\t\t<widget name="cast%d" position="%d,686" size="140,210" scale="1" zPosition="1"/>' % (i, x),
		'\t\t<widget name="castname%d" position="%d,900" size="176,80" font="Regular;21" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="center" valign="top"/>' % (i, x - 18)]
fp += ['\t\t<widget name="showings_title" position="1240,640" size="600,40" font="ArabicBold;28" foregroundColor="accent" backgroundColor="bg" transparent="1" halign="left"/>',
	'\t\t<eLabel position="1236,684" size="608,316" backgroundColor="bgCard" zPosition="-1"/>',
	'\t\t<widget source="showings" render="Listbox" position="1240,688" size="600,308" backgroundColor="bgCard" foregroundColor="fg" foregroundColorSelected="white" backgroundColorSelected="bgSel" scrollbarMode="showOnDemand" scrollbarWidth="6" scrollbarSliderForegroundColor="accent" transparent="1"><convert type="TemplatedMultiContent">{"template": [MultiContentEntryText(pos=(14, 0), size=(250, 44), font=0, flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER, text=0, color="#f2c94c", color_sel="#ffffff"), MultiContentEntryText(pos=(270, 0), size=(316, 44), font=0, flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER, text=1)], "fonts": [gFont("Regular", 26)], "itemHeight": 44}</convert></widget>',
	'\t\t<eLabel text="أعلى/أسفل: اختيار الميعاد     OK: تحويل     الأحمر: تسجيل" position="80,1010" size="1760,40" font="Regular;24" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="left" valign="center"/>',
	'\t</screen>']
screens.append("\n".join(fp))

def fe(conv, x, y, w, h, font, fg, extra=""):
	return '<widget source="Frontend" render="Label" position="%d,%d" size="%d,%d" font="%s" foregroundColor="%s" backgroundColor="bgCard" transparent="1" valign="center" noWrap="1" %s><convert type="FrontendInfo">%s</convert></widget>' % (x, y, w, h, font, fg, extra, conv)


sf = ['<widget name="config" position="80,146" size="1020,540" itemHeight="54" font="Regular;30" secondfont="Regular;30" %s/>' % LISTATTR,
	'<eLabel position="80,700" size="1020,1" backgroundColor="line"/>',
	'<widget name="description" position="80,708" size="1020,90" font="Regular;26" foregroundColor="fgDim" backgroundColor="bg" transparent="1"/>',
	'<widget name="introduction" position="80,800" size="1020,60" font="Regular;26" foregroundColor="gold" backgroundColor="bg" transparent="1"/>',
	card(1130, 146, 710, 794),
	'<eLabel text="قوة الإشارة" position="1160,160" size="650,44" font="ArabicBold;30" foregroundColor="accent" backgroundColor="bgCard" transparent="1" halign="left"/>']
for i, (lbl, conv) in enumerate((("SNR", "SNR"), ("AGC", "AGC"))):
	y = 220 + i * 130
	sf += ['<eLabel text="%s" position="1160,%d" size="120,44" font="Medium;32" foregroundColor="fg" backgroundColor="bgCard" transparent="1" halign="left" valign="center"/>' % (lbl, y),
		fe(conv, 1640, y, 180, 44, "Medium;38", "green", 'halign="right"'),
		'<ePixmap pixmap="NileGlass_FHD/ui/signal_xl_bg.png" position="1160,%d" size="660,24" alphatest="blend"/>' % (y + 56),
		'<widget source="Frontend" render="Progress" position="1160,%d" size="660,24" pixmap="NileGlass_FHD/ui/signal_xl.png" transparent="1" zPosition="1"><convert type="FrontendInfo">%s</convert></widget>' % (y + 56, conv)]
sf += ['<eLabel text="SNR dB" position="1160,480" size="240,44" font="Regular;28" foregroundColor="fgDim" backgroundColor="bgCard" transparent="1" halign="left" valign="center"/>',
	fe("SNRdB", 1400, 480, 420, 44, "Medium;34", "fg", 'halign="right"'),
	'<eLabel text="BER" position="1160,532" size="240,44" font="Regular;28" foregroundColor="fgDim" backgroundColor="bgCard" transparent="1" halign="left" valign="center"/>',
	fe("BER", 1400, 532, 420, 44, "Medium;34", "fg", 'halign="right"'),
	'<eLabel text="القفل" position="1160,584" size="240,44" font="Regular;28" foregroundColor="fgDim" backgroundColor="bgCard" transparent="1" halign="left" valign="center"/>',
	'<widget source="Frontend" render="Pixmap" pixmap="NileGlass_FHD/selections/selectioncross.png" position="1788,590" size="32,32" alphatest="blend" zPosition="1"><convert type="FrontendInfo">LOCK</convert><convert type="ConditionalShowHide"/></widget>',
	'<eLabel position="1160,644" size="660,1" backgroundColor="line"/>']
for i, (lbl, srcname) in enumerate((("القمر", "pos"), ("ONID", "onid"), ("TSID", "tsid"))):
	y = 660 + i * 50
	sf += ['<eLabel text="%s" position="1160,%d" size="240,44" font="Regular;28" foregroundColor="fgDim" backgroundColor="bgCard" transparent="1" halign="left" valign="center" objectTypes="%s,StaticText"/>' % (lbl, y, srcname),
		'<widget source="%s" render="Label" position="1400,%d" size="420,44" font="Medium;30" foregroundColor="fg" backgroundColor="bgCard" transparent="1" halign="right" valign="center" noWrap="1" objectTypes="%s,StaticText"/>' % (srcname, y, srcname)]
screens.append(compact("Satfinder", sf))
# ---- manual / automatic scan settings: compact like the satfinder
_scan = [configList(80, 146, 1760, 12, 54).replace('font="Regular;30" secondfont="Regular;30"', 'font="Regular;30" secondfont="Regular;30"'),
	'<eLabel position="80,806" size="1760,1" backgroundColor="line"/>',
	'<widget name="description" position="80,816" size="1760,96" font="Regular;26" foregroundColor="fgDim" backgroundColor="bg" transparent="1"/>',
	'<widget name="introduction" position="80,912" size="1760,30" font="Regular;24" foregroundColor="gold" backgroundColor="bg" transparent="1" noWrap="1"/>']
screens.append(compact("ScanSetup", _scan))
screens.append(compact("ScanSimple", [x for x in _scan if "introduction" not in x and "description" not in x]))
# ---- dish moving banner (NileGlassSetup/motorbar.py)
screens.append('''	<screen name="NileGlassMotor" position="center,48" size="820,150" backgroundColor="transparent" flags="wfNoBorder" zPosition="5">
		<eLabel position="0,0" size="820,150" backgroundColor="bg" zPosition="-10"/>
		<eLabel position="0,0" size="820,3" backgroundColor="lineAccent" zPosition="-9"/>
		<widget name="title" position="24,10" size="560,40" font="Medium;28" foregroundColor="gold" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>
		<widget name="time" position="596,8" size="200,48" font="Medium;40" foregroundColor="accent" backgroundColor="bg" transparent="1" halign="right" valign="center" noWrap="1"/>
		<widget name="from" position="24,58" size="300,56" font="Medium;44" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="center" valign="center" noWrap="1"/>
		<ePixmap pixmap="NileGlass_FHD/icons/arrow_right.png" position="390,62" size="40,48" alphatest="blend"/>
		<widget name="to" position="496,58" size="300,56" font="Medium;44" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="center" valign="center" noWrap="1"/>
		<widget name="info" position="24,114" size="772,30" font="Regular;22" foregroundColor="fgMute" backgroundColor="bg" transparent="1" halign="center" valign="center" noWrap="1"/>
	</screen>''')
# ---- edit one reader (NileGlassSetup/readers.py)
screens.append(compact("NileGlassReaderEdit", [configList(80, 146, 1760, 11, 54),
	'<eLabel position="80,760" size="1760,1" backgroundColor="line"/>',
	'<widget name="description" position="80,770" size="1760,60" font="Regular;26" foregroundColor="gold" backgroundColor="bg" transparent="1"/>',
	'<widget name="footnote" position="80,840" size="1760,40" font="Regular;24" foregroundColor="fgDim" backgroundColor="bg" transparent="1" noWrap="1"/>'], ("red", "green")))
# ---- softcam bar (NileGlassSetup/cambar.py): emu + decoding details
def _ecm(conv, x, y, w, font="Regular;26", fg="fg", extra='halign="left"'):
	return '\t\t<widget source="session.CurrentService" render="Label" position="%d,%d" size="%d,38" font="%s" foregroundColor="%s" backgroundColor="bg" transparent="1" valign="center" noWrap="1" %s><convert type="%s</convert></widget>' % (x, y, w, font, fg, extra, conv)


def _cap(text, x, y, w=150):
	return '\t\t<eLabel text="%s" position="%d,%d" size="%d,38" font="Regular;24" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="left" valign="center"/>' % (text, x, y, w)


_cb = ['\t<screen name="NileGlassCamBar" position="center,40" size="1100,420" backgroundColor="transparent" flags="wfNoBorder">',
	'\t\t<eLabel position="0,0" size="1100,420" backgroundColor="bg" zPosition="-10"/>',
	'\t\t<eLabel position="0,0" size="1100,3" backgroundColor="lineAccent" zPosition="-9"/>',
	'\t\t<eLabel text="الإيمو" position="30,14" size="300,40" font="Medium;28" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="left" valign="center"/>',
	'\t\t<widget name="state" position="560,14" size="510,40" font="Regular;26" foregroundColor="green" backgroundColor="bg" transparent="1" halign="right" valign="center" noWrap="1"/>',
	'\t\t<widget name="left" pixmap="NileGlass_FHD/icons/arrow_left.png" position="40,62" size="40,48" alphatest="blend"/>',
	'\t\t<widget name="cam" position="100,56" size="900,60" font="Medium;46" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="center" valign="center" noWrap="1"/>',
	'\t\t<widget name="right" pixmap="NileGlass_FHD/icons/arrow_right.png" position="1020,62" size="40,48" alphatest="blend"/>',
	'\t\t<widget name="info" position="30,118" size="1040,34" font="Regular;24" foregroundColor="gold" backgroundColor="bg" transparent="1" halign="center" valign="center" noWrap="1"/>',
	'\t\t<eLabel position="30,162" size="1040,1" backgroundColor="line" zPosition="-9"/>',
	_cap("الحالة", 30, 172),
	_ecm('NGEcm">State', 180, 172, 890, "Medium;28", "accent"),
	_cap("النظام", 30, 214),
	_ecm('NGEcm">Caid', 180, 214, 360),
	_cap("المصدر", 560, 214, 130),
	_ecm('NGEcm">Source', 690, 214, 380),
	_cap("البروتوكول", 30, 256),
	_ecm('NGEcm">Protocol', 180, 256, 360),
	_cap("Hops", 560, 256, 130),
	_ecm('NGEcm">Hops', 690, 256, 120),
	_cap("ECM", 830, 256, 80),
	_ecm('NGEcm">Time', 910, 256, 160),
	_cap("الكارت", 30, 298),
	_ecm('PliExtraInfo">CryptoNameCaid', 180, 298, 890, "Regular;26", "#c8ced6"),
	_cap("الأنظمة", 30, 340),
	_ecm('PliExtraInfo">CryptoBar', 180, 340, 890, "Regular;26", "fg"),
	'\t\t<eLabel text="يمين / شمال: الإيمو التالي     OK: تشغيل / إعادة تشغيل     MENU: مركز الإيمو     EXIT: خروج" position="30,382" size="1040,30" font="Regular;20" foregroundColor="fgMute" backgroundColor="bg" transparent="1" halign="center" valign="center"/>',
	'\t</screen>']
screens.append("\n".join(_cb))

# ---- emu readers / lines (NileGlassSetup/readers.py)
RD_COLS = (("#", 60, "center"), ("الاسم", 320, "left"), ("السيرفر / الكارت", 370, "left"), ("البورت", 110, "center"), ("البروتوكول", 170, "left"),
	("اليوزر", 200, "left"), ("الباسورد", 160, "left"), ("الحالة", 240, "right"))


def tableHead(cols, x0, y, h=34):
	out, x = [], x0 + 14
	for title, w, al in cols:
		out.append('<eLabel text="%s" position="%d,%d" size="%d,%d" font="Regular;24" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="%s" valign="center"/>' % (title, x, y, w, h, al))
		x += w + 8
	return out


def tableRow(cols, texts, ih=52):
	"""TemplatedMultiContent entries: texts = [(index, font, colour or None)] matching cols"""
	out, x = [], 14
	for (title, w, al), (idx, font, color) in zip(cols, texts):
		flag = {"left": "RT_HALIGN_LEFT", "center": "RT_HALIGN_CENTER", "right": "RT_HALIGN_RIGHT"}[al]
		c = ""
		if color == "dyn":
			c = ', color=MultiContentTemplateColor(%d), color_sel="#ffffff"' % idx[1]
			idx = idx[0]
		elif color:
			c = ', color="%s", color_sel="#ffffff"' % color
		out.append('MultiContentEntryText(pos=(%d, 0), size=(%d, %d), font=%d, flags=%s|RT_VALIGN_CENTER, text=%d%s)' % (x, w, ih, font, flag, idx, c))
		x += w + 8
	return ", ".join(out)


rd = ['<widget name="file" position="80,138" size="1760,36" font="Regular;24" foregroundColor="gold" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>'] + tableHead(RD_COLS, 80, 180) + [
	'<eLabel position="80,218" size="1760,1" backgroundColor="line"/>',
	'<widget source="list" render="Listbox" position="80,226" size="1760,416" %s>' % LISTATTR +
	'<convert type="TemplatedMultiContent">{"template": [' +
	tableRow(RD_COLS, [(7, 1, "#9aa3ae"), (0, 0, None), (2, 1, None), (8, 1, None), (1, 1, "#f0c419"), (3, 1, "#9aa3ae"), (9, 1, "#9aa3ae"), ((4, 6), 1, "dyn")]) +
	'], "fonts": [gFont("Medium", 28), gFont("Regular", 26)], "itemHeight": 52}</convert></widget>',
	'<eLabel position="80,652" size="1760,1" backgroundColor="line"/>',
	card(80, 662, 1760, 236),
	'<widget name="details" position="100,670" size="1720,222" font="Regular;24" foregroundColor="#c8ced6" backgroundColor="bgCard" transparent="1" halign="left" valign="top"/>',
	'<widget name="hint" position="80,906" size="1760,40" font="Regular;22" foregroundColor="fgMute" backgroundColor="bg" transparent="1" halign="center" valign="center" noWrap="1"/>']
screens.append(full("NileGlassReaders", rd))

# ---- the emu center (NileGlassSetup/camcenter.py)
_cc = [lab("info", 80, 138, 1760, 40, "Regular;26", "gold", extra='halign="left" valign="center" noWrap="1"'),
	'<eLabel position="80,186" size="1760,1" backgroundColor="line"/>',
	'<widget source="list" render="Listbox" position="80,200" size="1760,728" %s>' % LISTATTR +
	'<convert type="TemplatedMultiContent">{"template": ['
	'MultiContentEntryText(pos=(24, 6), size=(1700, 48), font=0, flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER, text=0), '
	'MultiContentEntryText(pos=(24, 54), size=(1700, 36), font=1, flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER, text=1, color="#9aa3ae", color_sel="#ffffff")], '
	'"fonts": [gFont("Medium", 32), gFont("Regular", 24)], "itemHeight": 104}</convert></widget>']
screens.append(full("NileGlassCamCenter", _cc))

ST_COLS = (("الاسم", 360, "left"), ("النوع", 130, "left"), ("الهوست", 360, "left"), ("البورت", 110, "center"), ("البروتوكول", 200, "left"),
	("ECM", 140, "center"), ("الحالة", 300, "right"))
_st = [lab("summary", 80, 138, 1760, 36, "Regular;24", "gold", extra='halign="left" valign="center" noWrap="1"')] + tableHead(ST_COLS, 80, 180) + [
	'<eLabel position="80,218" size="1760,1" backgroundColor="line"/>',
	'<widget source="list" render="Listbox" position="80,226" size="1760,676" %s>' % LISTATTR +
	'<convert type="TemplatedMultiContent">{"template": [' +
	tableRow(ST_COLS, [(0, 0, None), (1, 1, "#9aa3ae"), (2, 1, None), (3, 1, None), (4, 1, "#f0c419"), (5, 1, None), ((6, 7), 1, "dyn")]) +
	'], "fonts": [gFont("Medium", 28), gFont("Regular", 26)], "itemHeight": 52}</convert></widget>',
	'<eLabel position="80,906" size="1760,1" backgroundColor="line"/>',
	lab("hint", 80, 910, 1760, 36, "Regular;22", "fgMute", extra='halign="center" valign="center" noWrap="1"')]
screens.append(full("NileGlassCamStatus", _st))

_ci = ['<widget source="list" render="Listbox" position="80,150" size="1760,750" %s>' % LISTATTR +
	'<convert type="TemplatedMultiContent">{"template": ['
	'MultiContentEntryText(pos=(24, 0), size=(560, 56), font=1, flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER, text=0, color="#9aa3ae", color_sel="#ffffff"), '
	'MultiContentEntryText(pos=(600, 0), size=(1130, 56), font=0, flags=RT_HALIGN_LEFT|RT_VALIGN_CENTER, text=1)], '
	'"fonts": [gFont("Medium", 28), gFont("Regular", 26)], "itemHeight": 56}</convert></widget>']
screens.append(full("NileGlassCamInfo", _ci))

_ct = [lab("file", 80, 138, 1760, 36, "Regular;24", "gold", extra='halign="left" valign="center" noWrap="1"'),
	'<eLabel position="80,180" size="1760,1" backgroundColor="line"/>',
	card(80, 192, 1760, 706),
	'<widget name="text" position="100,200" size="1720,690" font="Regular;24" foregroundColor="#c8ced6" backgroundColor="bgCard" transparent="1" halign="left" scrollbarMode="showOnDemand" scrollbarWidth="6" scrollbarSliderForegroundColor="accent"/>',
	lab("hint", 80, 906, 1760, 36, "Regular;22", "fgMute", extra='halign="center" valign="center" noWrap="1"')]
screens.append(full("NileGlassCamText", _ct))


# ---- bitrate viewer (NileGlassSetup/cambar.py)
_br = []
for i, (title, which) in enumerate((("فيديو", "video"), ("صوت", "audio"))):
	y = 116 + i * 132
	_br.append('\t\t<eLabel text="%s" position="30,%d" size="160,44" font="Medium;30" foregroundColor="accent" backgroundColor="bg" transparent="1" halign="left" valign="center"/>' % (title, y))
	for j, (capt, field) in enumerate((("الحالي", "cur"), ("الأقل", "min"), ("الأعلى", "max"), ("المتوسط", "avg"))):
		x = 200 + j * 180
		_br.append('\t\t<eLabel text="%s" position="%d,%d" size="170,34" font="Regular;24" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="center" valign="center"/>' % (capt, x, y))
		_br.append('\t\t<widget source="session.CurrentService" render="Label" position="%d,%d" size="170,52" font="Medium;%d" foregroundColor="%s" backgroundColor="bg" transparent="1" halign="center" valign="center" noWrap="1"><convert type="NGBitrate">%s.%s</convert></widget>' % (x, y + 38, 40 if field == "cur" else 32, "fg" if field == "cur" else "#c8ced6", which, field))
screens.append('\t<screen name="NileGlassBitrate" position="center,center" size="960,420" backgroundColor="transparent" flags="wfNoBorder">\n'
	'\t\t<eLabel position="0,0" size="960,420" backgroundColor="bg" zPosition="-10"/>\n\t\t<eLabel position="0,0" size="960,3" backgroundColor="lineAccent" zPosition="-9"/>\n'
	'\t\t<eLabel text="معدل البت (kb/s)" position="30,20" size="560,56" font="Medium;36" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="left" valign="center"/>\n'
	'\t\t<widget source="session.CurrentService" render="Label" position="590,20" size="340,56" font="Regular;26" foregroundColor="gold" backgroundColor="bg" transparent="1" halign="right" valign="center" noWrap="1"><convert type="ServiceName">Name</convert></widget>\n'
	'\t\t<eLabel position="30,90" size="900,1" backgroundColor="line" zPosition="-9"/>\n' + "\n".join(_br) + '\n'
	'\t\t<eLabel text="بيتحدث كل ثانية  ·  OK / EXIT للإغلاق" position="30,376" size="900,32" font="Regular;22" foregroundColor="fgMute" backgroundColor="bg" transparent="1" halign="center" valign="center"/>\n'
	'\t</screen>')

# ======================================================================
# 2.4: the secondary popups that still fell back to the image's look
# ======================================================================
# ---- motor (PositionerSetup) and its helper screens
ps = ['<widget name="list" position="80,146" size="1020,650" itemHeight="50" font="Regular;28" secondfont="Regular;28" %s/>' % LISTATTR,
	'<eLabel position="80,808" size="1020,1" backgroundColor="line"/>',
	lab("status_bar", 80, 816, 1020, 60, "Regular;26", "gold"),
	lab("rotorstatus", 80, 878, 1020, 60, "Medium;28", "accent"),
	card(1130, 146, 710, 794),
	'<eLabel text="الإشارة" position="1160,160" size="420,44" font="ArabicBold;30" foregroundColor="accent" backgroundColor="bgCard" transparent="1" halign="left"/>',
	'<ePixmap pixmap="NileGlass_FHD/icons/lock_off.png" position="1756,154" size="64,64" alphatest="blend"/>',
	'<widget name="lock_on" pixmap="NileGlass_FHD/icons/lock_on.png" position="1756,154" size="64,64" alphatest="blend" zPosition="1"/>',
	'<widget name="lock_off" position="0,0" size="1,1" transparent="1"/>',
	lab("Lock", 1600, 160, 150, 44, "Regular;24", "fgDim", "bgCard", 'halign="right" valign="center"'),
	lab("lock_state", 1160, 210, 660, 40, "Medium;28", "fg", "bgCard", 'halign="left" valign="center"')]
for i, (l, bar, val) in enumerate((("SNR", "snr_bar", "snr_percentage"), ("AGC", "agc_bar", "agc_percentage"), ("BER", "ber_bar", "ber_value"))):
	y = 268 + i * 116
	ps += [lab(l, 1160, y, 200, 44, "Medium;32", "fg", "bgCard"),
		lab(val, 1600, y, 220, 44, "Medium;36", "green", "bgCard", 'halign="right" valign="center"'),
		'<ePixmap pixmap="NileGlass_FHD/ui/signal_xl_bg.png" position="1160,%d" size="660,24" alphatest="blend"/>' % (y + 54),
		'<widget name="%s" position="1160,%d" size="660,24" pixmap="NileGlass_FHD/ui/signal_xl.png" transparent="1" zPosition="1"/>' % (bar, y + 54)]
ps += ['<eLabel text="SNR dB" position="1160,616" size="300,44" font="Regular;28" foregroundColor="fgDim" backgroundColor="bgCard" transparent="1" halign="left" valign="center"/>',
	lab("snr_db", 1460, 616, 360, 44, "Medium;32", "fg", "bgCard", 'halign="right" valign="center"'),
	'<eLabel position="1160,676" size="660,1" backgroundColor="line"/>']
for i, (l, v) in enumerate((("Frequency", "frequency_value"), ("Symbolrate", "symbolrate_value"), ("FEC", "fec_value"))):
	y = 692 + i * 56
	ps += [lab(l, 1160, y, 300, 44, "Regular;28", "fgDim", "bgCard"),
		lab(v, 1460, y, 360, 44, "Medium;30", "fg", "bgCard", 'halign="right" valign="center"')]
ps += [src("key_info", 1160, 880, 300, 40, "Regular;24", "fgMute", "bgCard"), src("key_menu", 1520, 880, 300, 40, "Regular;24", "fgMute", "bgCard", 'halign="right" valign="center"')]
screens.append(compact("PositionerSetup", ps))
screens.append(popup("TunerScreen", 1240, 820, [configList(40, 104, 1160, 9),
	lab("introduction", 40, 620, 1160, 100, "Regular;26", "gold", extra='halign="left" valign="top"')], ("red", "green")))
screens.append(popup("RotorNimSelection", 1000, 500, ['<widget name="nimlist" position="30,104" size="940,370" itemHeight="62" font="Regular;30" %s/>' % LISTATTR]))
screens.append(full("PositionerSetupLog", ['<widget name="list" position="80,146" size="1760,790" font="Regular;26" foregroundColor="fg" backgroundColor="bg" transparent="1"/>']))

# ---- Blue Panel: "starting the cam" animation
screens.append(popup("Nab_DoStartCam", 760, 230, [
	'<widget name="connect" position="40,116" size="64,64" pixmaps="NileGlass_FHD/icons/camstart_0.png,NileGlass_FHD/icons/camstart_1.png,NileGlass_FHD/icons/camstart_2.png,NileGlass_FHD/icons/camstart_3.png" alphatest="blend"/>',
	lab("lab1", 130, 100, 600, 100, "Regular;30", "fg", extra='halign="left" valign="center"')], title="الإيمو"))

# ---- PVR / timeshift state (pause, fast forward ...)
pvr = ",".join("NileGlass_FHD/icons/pvr_%d.png" % i for i in range(7))
for name, extra in (("PVRState", []), ("TimeshiftState", ['<widget name="PTSSeekBack" position="0,0" size="1,1" transparent="1"/>', '<widget name="PTSSeekPointer" position="0,0" size="1,1" transparent="1"/>'])):
	screens.append('\t<screen name="%s" position="60,50" size="620,104" backgroundColor="transparent" flags="wfNoBorder">\n' % name +
		'\t\t<eLabel position="0,0" size="620,104" backgroundColor="bg" zPosition="-10"/>\n\t\t<eLabel position="0,0" size="620,3" backgroundColor="lineAccent" zPosition="-9"/>\n'
		'\t\t<widget name="statusicon" position="20,20" size="64,64" pixmaps="%s" alphatest="blend"/>\n' % pvr +
		'\t\t' + lab("state", 100, 10, 300, 48, "Medium;34", "fg") + '\n'
		'\t\t' + lab("speed", 420, 10, 180, 48, "Medium;34", "accent", extra='halign="right" valign="center"') + '\n'
		'\t\t' + lab("eventname", 100, 58, 500, 36, "Regular;24", "fgDim", extra='halign="left" valign="center" noWrap="1"') + '\n' +
		"".join("\t\t" + e + "\n" for e in extra) + '\t</screen>')

# ---- small overlays
screens.append('\t<screen name="VideoMode" position="1250,56" size="630,90" backgroundColor="transparent" flags="wfNoBorder">\n'
	'\t\t<eLabel position="0,0" size="630,90" backgroundColor="bg" zPosition="-10"/>\n\t\t<eLabel position="0,0" size="630,3" backgroundColor="lineAccent" zPosition="-9"/>\n'
	'\t\t' + lab("videomode", 24, 14, 582, 64, "Medium;34", "fg", extra='halign="center" valign="center"') + '\n\t</screen>')
screens.append('\t<screen name="UnhandledKey" position="1820,40" size="64,64" backgroundColor="transparent" flags="wfNoBorder">\n'
	'\t\t<widget name="UnhandledKeyPixmap" pixmap="NileGlass_FHD/icons/unhandled_key.png" position="0,0" size="64,64" alphatest="blend"/>\n\t</screen>')
screens.append('\t<screen name="SubservicesQuickzap" position="1250,56" size="630,90" backgroundColor="transparent" flags="wfNoBorder">\n'
	'\t\t<eLabel position="0,0" size="630,90" backgroundColor="bg" zPosition="-10"/>\n\t\t<eLabel position="0,0" size="630,3" backgroundColor="lineAccent" zPosition="-9"/>\n'
	'\t\t' + lab("CurrentSubserviceNumber", 24, 14, 582, 64, "Medium;34", "fg", extra='halign="center" valign="center"') + '\n\t</screen>')
screens.append(popup("MinuteInput", 600, 230, [lab("minutes", 40, 110, 520, 80, "Medium;54", "accent", extra='halign="center" valign="center"')], title="دقائق"))

# ---- text screens
screens.append(full("TextBox", ['<widget name="text" position="80,146" size="1760,790" font="Regular;28" foregroundColor="fg" backgroundColor="bg" transparent="1"/>']))
screens.append(full("Console", ['<widget name="text" position="80,146" size="1760,790" font="Regular;26" foregroundColor="fg" backgroundColor="bg" transparent="1"/>']))

# ---- scanning
W, Hs = 1500, 800
sc = ['\t<screen name="ServiceScan" position="center,center" size="%d,%d" backgroundColor="transparent" flags="wfNoBorder">' % (W, Hs),
	'\t\t<eLabel position="0,0" size="%d,%d" backgroundColor="bg" zPosition="-10"/>' % (W, Hs),
	'\t\t<eLabel position="0,0" size="%d,3" backgroundColor="lineAccent" zPosition="-9"/>' % W,
	'\t\t<eLabel position="0,88" size="%d,1" backgroundColor="line" zPosition="-9"/>' % W,
	'\t\t' + lab("Title", 36, 12, 1100, 64, "Medium;36", "accent", extra='halign="left" valign="center" noWrap="1"'),
	'\t\t<widget source="global.CurrentTime" render="Label" position="%d,12" size="220,64" font="Regular;40" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="right" valign="center" noWrap="1"><convert type="ClockToText">Format:%%H:%%M</convert></widget>' % (W - 256),
	'\t\t<eLabel position="36,112" size="%d,12" backgroundColor="bgBar"/>' % (W - 72),
	'\t\t<widget name="scan_progress" position="36,112" size="%d,12" pixmap="NileGlass_FHD/ui/progress.png" transparent="1" zPosition="1"/>' % (W - 72),
	'\t\t' + lab("scan_state", 36, 136, W - 72, 46, "Medium;30", "accent"),
	'\t\t' + lab("transponder", 36, 184, 820, 40, "Regular;26", "gold", extra='halign="left" valign="center" noWrap="1"'),
	'\t\t' + lab("network", 870, 184, W - 906, 40, "Regular;26", "fgDim", extra='halign="right" valign="center" noWrap="1"'),
	'\t\t' + lab("pass", 36, 226, W - 72, 36, "Regular;24", "fgDim", extra='halign="left" valign="center" noWrap="1"'),
	'\t\t<eLabel position="36,270" size="%d,1" backgroundColor="line"/>' % (W - 72),
	'\t\t<widget name="servicelist" position="36,280" size="%d,416" itemHeight="52" font="Regular;28" %s/>' % (W - 72, LISTATTR),
	'\t\t<eLabel position="0,%d" size="%d,1" backgroundColor="line" zPosition="-9"/>' % (Hs - 84, W)]
for i, c in enumerate(("red", "green")):
	x = 36 + i * 370
	sc += ['\t\t<ePixmap pixmap="NileGlass_FHD/buttons/%s_k260.png" position="%d,%d" size="260,38" alphatest="blend" conditional="key_%s"/>' % (c, x, Hs - 61, c),
		'\t\t<widget name="key_%s" position="%d,%d" size="260,38" font="Medium;24" foregroundColor="white" backgroundColor="black" transparent="1" halign="center" valign="center" noWrap="1" zPosition="1"/>' % (c, x, Hs - 61)]
sc.append('\t</screen>')
screens.append("\n".join(sc))
screens.append(popup("AutoDiseqc", 1240, 760, [configList(40, 104, 1160, 6),
	src("statusbar", 40, 450, 1160, 100, "Regular;28", "gold", extra='halign="left" valign="top"'),
	src("tunerstatusbar", 40, 556, 1160, 100, "Regular;26", "fgDim", extra='halign="left" valign="top"')], ("red",)))

# ---- CI / CAM module menus
screens.append(popup("CiSelection", 1240, 640, ['<widget name="entries" position="30,104" size="1180,336" itemHeight="56" font="Regular;30" secondfont="Regular;30" %s/>' % LISTATTR,
	lab("text", 40, 452, 1160, 80, "Regular;28", "gold")], ("red",)))
screens.append(popup("MMIDialog", 1240, 860, [lab("title", 40, 100, 1160, 44, "Medium;30", "accent"),
	lab("subtitle", 40, 148, 1160, 40, "Regular;26", "fgDim"),
	'<widget name="entries" position="30,196" size="1180,504" itemHeight="56" font="Regular;30" secondfont="Regular;30" %s/>' % LISTATTR,
	lab("bottom", 40, 710, 1160, 50, "Regular;26", "gold"),
	src("key_menu", 40, 780, 300, 50, "Regular;24", "fgMute")]))

# ---- background jobs
screens.append(popup("JobView", 1240, 560, [src("job_name", 40, 110, 1160, 50, "Medium;32", "fg"),
	src("job_task", 40, 170, 1160, 44, "Regular;28", "fgDim"),
	'<eLabel position="40,236" size="1160,14" backgroundColor="bgBar"/>',
	'<widget source="job_progress" render="Progress" position="40,236" size="1160,14" pixmap="NileGlass_FHD/ui/progress.png" transparent="1" zPosition="1"/>',
	'<widget source="job_progress" render="Label" position="40,262" size="1160,44" font="Medium;30" foregroundColor="accent" backgroundColor="bg" transparent="1" halign="right" valign="center"><convert type="ProgressToText"/></widget>',
	src("job_status", 40, 312, 1160, 60, "Regular;28", "gold"),
	configList(40, 380, 1160, 1, 56)], ("red", "green", "blue")))

# ---- bouquet chooser, service info, folder chooser
screens.append(popup("BouquetSelector", 1000, 820, ['<widget name="menu" position="30,104" size="940,672" itemHeight="56" font="Regular;30" %s/>' % LISTATTR]))
si = ['<widget name="infolist" position="80,146" size="1760,800" itemHeight="50" font="Regular;28" %s/>' % LISTATTR,
	'<eLabel position="40,958" size="1840,1" backgroundColor="line" zPosition="-9"/>']
for i, c in enumerate(("red", "green", "yellow", "blue")):
	x = (80, 566, 1053, 1540)[i]
	si += ['<ePixmap pixmap="NileGlass_FHD/buttons/%s_k300.png" position="%d,980" size="300,38" alphatest="blend"/>' % (c, x),
		'<widget name="%s" position="%d,980" size="300,38" font="Medium;24" foregroundColor="white" backgroundColor="black" transparent="1" halign="center" valign="center" noWrap="1" zPosition="1"/>' % (c, x)]
screens.append('\t<screen name="ServiceInfo" position="0,0" size="1920,1080" backgroundColor="transparent" flags="wfNoBorder">\n'
	'\t\t<eLabel position="40,40" size="1840,1000" backgroundColor="bg" zPosition="-10"/>\n\t\t<eLabel position="40,40" size="1840,2" backgroundColor="lineAccent" zPosition="-9"/>\n\t\t<eLabel position="40,128" size="1840,1" backgroundColor="line" zPosition="-9"/>\n'
	'\t\t<widget source="Title" render="Label" position="80,52" size="1160,66" font="Medium;38" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>\n'
	'\t\t<widget source="global.CurrentTime" render="Label" position="1660,52" size="190,66" font="Regular;48" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="right" valign="center" noWrap="1"><convert type="ClockToText">Format:%H:%M</convert></widget>\n' +
	"".join("\t\t" + b + "\n" for b in si) + '\t</screen>')
screens.append('\t<screen name="ServiceInfoSimple" position="0,0" size="1920,1080" backgroundColor="transparent" flags="wfNoBorder">\n\t\t<panel name="ServiceInfo"/>\n\t</screen>')
lb = [lab("text", 80, 146, 1760, 44, "Medium;30", "accent"),
	lab("target", 80, 194, 1760, 40, "Regular;26", "gold", extra='halign="left" valign="center" noWrap="1"'),
	'<widget name="filelist" position="80,244" size="1100,700" itemHeight="50" font="Regular;28" %s/>' % LISTATTR,
	'<eLabel position="1200,244" size="1,700" backgroundColor="line"/>',
	lab("textbook", 1220, 244, 620, 44, "Medium;28", "fgDim"),
	'<widget name="booklist" position="1220,296" size="620,650" itemHeight="50" font="Regular;26" %s/>' % LISTATTR,
	src("key_menu", 1660, 146, 180, 44, "Regular;24", "fgMute", extra='halign="right" valign="center"')]
for c in ("red", "green", "yellow", "blue"):
	lb.append('<widget name="%s" position="0,0" size="1,1" transparent="1"/>' % c)
screens.append(full("LocationBox", lb))

# ---- OScam / NCam info (OpenBh built-in). The rows are drawn by the image's
# code (fonts x1.5 on FHD), the skin gives them the frame and a wide list.
screens.append(full("OscamInfoMenu", ['<widget name="mainmenu" position="80,150" size="1760,780" %s/>' % LISTATTR]))
screens.append(full("oscECMInfo", ['<widget name="output" position="80,150" size="1760,780" %s/>' % LISTATTR]))
screens.append(full("oscInfo", ['<widget name="output" position="80,150" size="1760,790" %s/>' % LISTATTR]))
names = [re.search(r'<screen name="([^"]+)"', x).group(1) for x in screens]
# drop old versions of these screens (outside the generated block)
s = re.sub(r"\n?[ \t]*<!-- NG_POPUPS_BEGIN.*?NG_POPUPS_END -->\n?", "\n", s, flags=re.S)
for n in names:
	s = re.sub(r'\n\t<screen name="%s"[ >].*?\n\t</screen>' % re.escape(n), "", s, flags=re.S)
block = "\n\t<!-- NG_POPUPS_BEGIN (generated by tools/gen_popups.py) -->\n" + "\n".join(screens) + "\n\t<!-- NG_POPUPS_END -->\n"
s = s.rstrip()
assert s.endswith("</skin>")
s = s[:-len("</skin>")].rstrip() + "\n" + block + "\n</skin>\n"
open(SKIN, "w", encoding="utf-8").write(s)
print("screens:", len(names))
