#!/usr/bin/env python3
"""Card layouts (the menu look) for three screens of skin.xml:
  SecondInfoBar   smaller panel at the left + the next 4 events as cards with their EPG
  ChannelSelection 16 channel rows + a big card for the running event + 4 event cards
  DeliteBluePanel  emu panel at the left + cards with the decoding details
Replaces those <screen> blocks in place.  argv: SKINDIR"""
import glob, os, re, sys
from PIL import Image

SK = sys.argv[1]
CS = "session.CurrentService"
FE = "session.FrontendStatus"
NOW = "session.Event_Now"


def W(src, render, x, y, w, h, extra="", conv=(), font=None, fg="fg", bg="bg", halign="left", valign="center", wrap=False):
	a = '<widget source="%s" render="%s" position="%d,%d" size="%d,%d"' % (src, render, x, y, w, h)
	if font:
		a += ' font="%s" foregroundColor="%s" backgroundColor="%s" transparent="1" halign="%s" valign="%s"%s' % (font, fg, bg, halign, valign, "" if wrap else ' noWrap="1"')
	a += (" " + extra if extra else "")
	c = "".join('<convert type="%s">%s</convert>' % cv for cv in conv)
	return "\t\t" + a + (">%s</widget>" % c if c else "/>")


def N(name, x, y, w, h, font, fg="fg", bg="bg", halign="left", valign="center", wrap=False, extra=""):
	return '\t\t<widget name="%s" position="%d,%d" size="%d,%d" font="%s" foregroundColor="%s" backgroundColor="%s" transparent="1" halign="%s" valign="%s"%s%s/>' % (
		name, x, y, w, h, font, fg, bg, halign, valign, "" if wrap else ' noWrap="1"', (" " + extra if extra else ""))


def T(text, x, y, w, h, font, fg="fgDim", bg="bg", halign="left"):
	return '\t\t<eLabel text="%s" position="%d,%d" size="%d,%d" font="%s" foregroundColor="%s" backgroundColor="%s" transparent="1" halign="%s" valign="center" noWrap="1"/>' % (text, x, y, w, h, font, fg, bg, halign)


def card(x, y, w, h, color="bgCard", r=18, z=-9):
	return '\t\t<eLabel position="%d,%d" size="%d,%d" backgroundColor="%s" cornerRadius="%d" zPosition="%d"/>' % (x, y, w, h, color, r, z)


def line(x, y, w, h=1):
	return '\t\t<eLabel position="%d,%d" size="%d,%d" backgroundColor="line" zPosition="-8"/>' % (x, y, w, h)


def key(color, x, y, w=200, objtype=None):
	o = ['\t\t<ePixmap pixmap="NileGlass_FHD/buttons/%s_k200.png" position="%d,%d" size="%d,38" alphatest="blend" conditional="key_%s"/>' % (color, x, y, w, color)]
	common = 'position="%d,%d" size="%d,38" font="Medium;22" foregroundColor="white" backgroundColor="black" transparent="1" halign="center" valign="center" noWrap="1" zPosition="1"' % (x, y, w)
	if objtype in (None, "name"):
		o.append('\t\t<widget name="key_%s" %s%s/>' % (color, common, "" if objtype else ' objectTypes="key_%s,Button,Label"' % color))
	if objtype is None:
		o.append('\t\t<widget source="key_%s" render="Label" %s objectTypes="key_%s,StaticText"/>' % (color, common, color))
	return o


def eventCard(src, i, x, y, w, h, bg, thumb=(134, 200), descLines=4, titleFont="Medium;28", descFont="Regular;22"):
	"""one upcoming event: poster thumb, time, title, description"""
	tw, th = thumb
	tx = x + 16 + tw + 16
	ww = w - (tx - x) - 16
	return [card(x, y, w, h, bg),
		'\t\t<widget source="%s" render="NGPoster" kind="thumb" eventIndex="%d" position="%d,%d" size="%d,%d" delay="400" picon="1" fallback="NileGlass_FHD/ui/noposter.png" borderWidth="1" borderColor="posterBorder" zPosition="2"/>' % (src, i + 1, x + 16, y + (h - th) // 2, tw, th),
		'\t\t<widget source="%s" render="NGEventList" items="1" start="%d" fields="time" position="%d,%d" size="%d,30" font="Regular;22" foregroundColor="gold" backgroundColor="%s" transparent="1" halign="left" valign="center" noWrap="1"/>' % (src, i, tx, y + 12, ww, bg),
		'\t\t<widget source="%s" render="NGEventList" items="1" start="%d" fields="title" position="%d,%d" size="%d,38" font="%s" foregroundColor="fg" backgroundColor="%s" transparent="1" halign="left" valign="center" noWrap="1"/>' % (src, i, tx, y + 42, ww, titleFont, bg),
		'\t\t<widget source="%s" render="NGEventList" items="1" start="%d" fields="desc" position="%d,%d" size="%d,%d" font="%s" foregroundColor="fgDim" backgroundColor="%s" transparent="1" halign="left" valign="top"/>' % (src, i, tx, y + 84, ww, h - 96, descFont, bg)]


# ------------------------------------------------------------------ SecondInfoBar
def sib():
	PX, PY, PW, PH = 40, 40, 1180, 1000
	o = ['\t<screen name="SecondInfoBar" position="0,0" size="1920,1080" backgroundColor="transparent" flags="wfNoBorder">',
		'\t\t<!-- left: channel and the running programme; right: the next four programmes as cards -->',
		card(PX, PY, PW, PH, "bg", 24, -10),
		'\t\t<ePixmap pixmap="NileGlass_FHD/ui/picon_bg.png" position="62,58" size="182,110" alphatest="blend" scale="1"/>',
		W(CS, "Picon", 63, 59, 180, 108, 'alphatest="blend" zPosition="1"', [("ServiceName", "Reference")]),
		W(CS, "ChannelNumber", 264, 56, 110, 56, "", (), "Regular;40", "accent"),
		N("channel", 370, 56, 620, 56, "Medium;40"),
		W(CS, "Label", 264, 118, 250, 34, "", [("ServiceName", "Provider")], "Regular;24", "gold"),
		W(CS, "Label", 520, 118, 150, 34, "", [("ServiceOrbitalPosition", "Short")], "Regular;24", "fgDim"),
		W("global.CurrentTime", "Label", 990, 52, 206, 64, "", [("ClockToText", "Format:%H:%M")], "Regular;56", "fg", halign="right"),
		W("global.CurrentTime", "Label", 680, 118, 516, 34, "", [("ClockToText", "Format:%A %d %B"), ("NGHijri", "Append")], "Regular;22", "gold", halign="right"),
		line(62, 176, PW - 44),
		# running programme
		W(NOW, "NGPoster", 62, 192, 240, 360, 'delay="0" fallback="NileGlass_FHD/ui/noposter.png" borderWidth="2" borderColor="posterBorder" zPosition="2"'),
		W(NOW, "Label", 324, 186, 872, 56, "", [("EventName", "Name")], "Medium;38", "accent"),
		W(NOW, "NGEventInfo", 324, 246, 872, 196, 'mode="card" fields="year,genres,director,country,cast,runtime" labelColor="#9aa3ae" delay="0"', (), "Regular;26", "fg", valign="top", wrap=True),
		W(NOW, "NGStars", 324, 450, 200, 36, 'backgroundPixmap="NileGlass_FHD/ui/stars_bg.png" pixmap="NileGlass_FHD/ui/stars.png" transparent="1" zPosition="1"'),
		W(NOW, "NGEventInfo", 536, 448, 300, 40, 'fields="rating" delay="0"', (), "Medium;26", "gold"),
		W(NOW, "Label", 324, 500, 96, 40, "", [("EventTime", "StartTime"), ("ClockToText", "Format:%H:%M")], "Regular;28", "green"),
		'\t\t<eLabel position="424,515" size="672,10" backgroundColor="bgBar" cornerRadius="5"/>',
		W(NOW, "Progress", 424, 515, 672, 10, 'pixmap="NileGlass_FHD/ui/progress_heat.png" transparent="1" zPosition="1"', [("EventTime", "Progress")]),
		W(NOW, "Label", 1100, 500, 96, 40, "", [("EventTime", "EndTime"), ("ClockToText", "Format:%H:%M")], "Regular;28", "red", halign="right"),
		N("epg_description", 62, 566, PW - 44, 168, "Regular;27", "#d6dbe1", valign="top", wrap=True),
		line(62, 744, PW - 44),
		# signal and picture
		W(CS, "Label", 62, 756, 700, 34, "", [("PliExtraInfo", "TransponderInfo")], "Regular;24", "fgDim"),
		W(CS, "FixedLabel", 62, 752, 300, 72, 'text="IPTV"', [("NGStream", "Only")], "Medium;52", "accent"),
		W(CS, "Label", 780, 756, 416, 34, "", [("NGCodec", "Resolution")], "Regular;24", "fg", halign="right"),
	]
	for i, (lab, conv) in enumerate((("SNR", "SNR"), ("AGC", "AGC"))):
		y = 798 + i * 40
		o += [W(FE, "FixedLabel", 62, y, 70, 32, 'text="%s"' % lab, [("NGStream", "")], "Regular;24", "fgDim"),
			'\t\t<ePixmap pixmap="NileGlass_FHD/ui/signal_wide_bg.png" position="140,%d" size="360,16" alphatest="blend"/>' % (y + 8),
			W(FE, "Progress", 140, y + 8, 360, 16, 'pixmap="NileGlass_FHD/ui/signal_wide.png" transparent="1" zPosition="1"', [("FrontendInfo", conv), ("NGStream", "")]),
			W(FE, "Label", 510, y, 95, 32, "", [("FrontendInfo", conv), ("NGStream", "")], "Regular;24", "green", halign="right")]
	o += [W(CS, "Label", 780, 798, 416, 32, "", [("NGCodec", "Codecs")], "Regular;24", "orange", halign="right"),
		W(CS, "Label", 780, 838, 416, 32, "", [("NGBitrate", "Compact")], "Regular;22", "accent", halign="right"),
		W(CS, "Label", 62, 880, 700, 30, "", [("PliExtraInfo", "CryptoBar"), ("NGStream", "")], "Regular;24", "fg"),
		W(CS, "Label", 62, 912, 560, 30, "", [("PliExtraInfo", "CryptoNameCaid")], "Regular;22", "fgDim"),
		W(CS, "FixedLabel", 1000, 880, 60, 30, 'text="SID"', [("NGStream", "")], "Regular;22", "accent"),
		W(CS, "Label", 1060, 880, 136, 30, "", [("ServiceInfo", "Sid"), ("NGStream", "")], "Regular;22", "fg", halign="right"),
		line(62, 958, PW - 44)]
	o += key("green", 730, 980, 200, "name") + key("blue", 996, 980, 200, "name")
	# right: coming programmes
	RX, RW = 1240, 640
	o += [card(RX, PY, RW, 70, "bg", 20, -10),
		T("البرامج القادمة", RX + 20, PY + 4, 300, 62, "ArabicBold;28", "accent"),
		W(CS, "Label", RX + 300, PY + 4, RW - 320, 62, "", [("NGTonight", "Soon")], "Regular;22", "gold", halign="right")]
	for i in range(4):
		o += eventCard(CS, i, RX, PY + 84 + i * 232, RW, 220, "bg")
	o.append('\t</screen>')
	return "\n".join(o)


# ------------------------------------------------------------------ ChannelSelection
def channels(old):
	listEl = re.search(r'<widget name="list".*?/>', old, re.S).group(0)
	listEl = re.sub(r'size="[^"]*" itemHeight="\d+" serviceItemHeight="\d+" selectionPixmap="[^"]*"',
		'size="960,800" itemHeight="50" serviceItemHeight="50" selectionPixmap="NileGlass_FHD/ui/sel_channel50.png"', listEl, count=1)
	listEl = listEl.replace('serviceNumberFont="Regular;26" serviceNameFont="Regular;28" serviceInfoFont="Regular;23" serviceRemainingInfoFont="Regular;21"',
		'serviceNumberFont="Regular;25" serviceNameFont="Regular;27" serviceInfoFont="Regular;22" serviceRemainingInfoFont="Regular;20"')
	assert "sel_channel50" in listEl and 'size="960,800"' in listEl
	SE = "ServiceEvent"
	X, Y, CW = 1046, 140, 814
	LC = CW - 236            # text column beside the poster
	o = ['\t<screen name="ChannelSelection" position="0,0" size="1920,1080" backgroundColor="transparent" flags="wfNoBorder">',
		'\t\t<panel name="NG_Frame"/>', "\t\t" + listEl,
		'\t\t<!-- selected channel: running programme card (poster, times, full description), then four upcoming programme cards -->',
		card(X, Y, CW, 440),
		W(SE, "NGPoster", X + CW - 196, Y + 16, 180, 270, 'delay="300" picon="1" fallback="NileGlass_FHD/ui/noposter.png" borderWidth="2" borderColor="posterBorder" zPosition="3"'),
		W(SE, "Label", X + 20, Y + 12, LC, 36, "", [("ServiceName", "Name")], "Medium;26", "fgDim", "bgCard"),
		W(SE, "Label", X + 20, Y + 50, LC, 76, "", [("EventName", "Name")], "Medium;30", "accent", "bgCard", valign="top", wrap=True),
		W(SE, "Label", X + 20, Y + 132, 110, 32, "", [("EventTime", "StartTime"), ("ClockToText", "Format:%H:%M")], "Regular;26", "fg", "bgCard"),
		W(SE, "Label", X + 20 + LC - 110, Y + 132, 110, 32, "", [("EventTime", "EndTime"), ("ClockToText", "Format:%H:%M")], "Regular;26", "fg", "bgCard", halign="right"),
		'\t\t<eLabel position="%d,%d" size="%d,8" backgroundColor="bgBar" cornerRadius="4" zPosition="-7"/>' % (X + 20, Y + 170, LC),
		W(SE, "Progress", X + 20, Y + 170, LC, 8, 'pixmap="NileGlass_FHD/ui/progress_sib.png" transparent="1" zPosition="1"', [("EventTime", "Progress")]),
		W(SE, "Label", X + 20, Y + 184, 260, 32, "", [("EventTime", "Remaining"), ("RemainingToText", "InMinutes")], "Regular;24", "fgDim", "bgCard"),
		W(SE, "NGEventInfo", X + 20, Y + 220, LC, 32, 'fields="year,genres"', (), "Regular;24", "gold", "bgCard"),
		W(SE, "NGStars", X + 20, Y + 254, 200, 32, 'backgroundPixmap="NileGlass_FHD/ui/stars_bg.png" pixmap="NileGlass_FHD/ui/stars.png" transparent="1" zPosition="1"'),
		W(SE, "Label", X + 20, Y + 298, CW - 40, 132, "", [("EventName", "FullDescription"), ("NGTranslate", "")], "Regular;23", "#d6dbe1", "bgCard", valign="top", wrap=True),
	]
	hw = (CW - 12) // 2
	for i in range(4):
		cx = X + (i % 2) * (hw + 12)
		cy = Y + 452 + (i // 2) * 183
		o += eventCard(SE, i, cx, cy, hw, 171, "bgCard", thumb=(104, 156), titleFont="Medium;22", descFont="Regular;19")
	o.append('\t</screen>')
	return "\n".join(o)


# ------------------------------------------------------------------ DeliteBluePanel
def blue(old):
	P = "bg"
	LW, LH = 800, 880
	o = ['\t<screen name="DeliteBluePanel" position="40,center" size="1840,%d" backgroundColor="transparent" flags="wfNoBorder" title="OpenBh Blue Panel">' % LH,
		'\t\t<!-- left: softcams and the channel; right: decoding cards -->',
		card(0, 0, LW, LH, P, 24, -10),
		'\t\t<ePixmap pixmap="NileGlass_FHD/ui/ng_logo.png" position="22,24" size="40,40" alphatest="blend" zPosition="1"/>',
		'\t\t<widget source="Title" render="Label" position="74,16" size="540,56" font="Medium;32" foregroundColor="accent" backgroundColor="%s" transparent="1" halign="left" valign="center" noWrap="1"/>' % P,
		W("global.CurrentTime", "Label", LW - 180, 16, 156, 56, "", [("ClockToText", "Format:%H:%M")], "Regular;40", "fg", P, halign="right"),
		line(24, 84, LW - 48),
		N("lab1", 32, 98, 736, 40, "Regular;26", "fgDim", P),
		'\t\t<widget name="list" position="32,142" size="736,58" itemHeight="58" font="Medium;32" foregroundColor="fg" backgroundColor="bgCard" foregroundColorSelected="white" backgroundColorSelected="bgSel" scrollbarMode="showNever"/>',
		N("lab2", 32, 208, 736, 36, "Regular;24", "fgDim", P),
		N("lab3", 32, 246, 736, 48, "Medium;32", "accent", P),
		N("activecam", 32, 246, 736, 48, "Medium;32", "accent", P),
		line(24, 306, LW - 48)]
	for i in range(4):
		o.append(N("Ilab%d" % (i + 1), 32, 318 + i * 44, 736, 42, "Regular;27", "fg", P))
	o += [line(24, 504, LW - 48),
		'\t\t<ePixmap pixmap="NileGlass_FHD/ui/picon_bg.png" position="32,522" size="222,134" alphatest="blend"/>',
		W(CS, "Picon", 33, 523, 220, 132, 'alphatest="blend" zPosition="1"', [("ServiceName", "Reference")]),
		W(CS, "Label", 274, 520, 500, 46, "", [("ServiceName", "Name")], "Medium;32", "fg", P),
		W(CS, "Label", 274, 570, 500, 40, "", [("PliExtraInfo", "TransponderInfo")], "Regular;24", "fgDim", P),
		W(CS, "Label", 274, 614, 500, 40, "", [("PliExtraInfo", "PIDInfo")], "Regular;22", "fgDim", P),
		W(CS, "Label", 32, 672, 736, 36, "", [("NGCodec", "Full")], "Regular;24", "gold", P),
		line(24, LH - 154, LW - 48)]
	# four colour keys in two rows (long names)
	for i, c in enumerate(("red", "green", "yellow", "blue")):
		x, y = 32 + (i % 2) * 376, LH - 136 + (i // 2) * 56
		o += ['\t\t<ePixmap pixmap="NileGlass_FHD/buttons/%s_k300.png" position="%d,%d" size="360,44" alphatest="blend" scale="1"/>' % (c, x, y),
			'\t\t<widget name="key_%s" position="%d,%d" size="360,44" font="Medium;26" foregroundColor="white" backgroundColor="black" transparent="1" halign="center" valign="center" noWrap="1" zPosition="1"/>' % (c, x, y)]
	# cards
	X, CW = LW + 20, 1840 - LW - 20
	sw = (CW - 2 * 14) // 3
	for i, (t, conv, col, sub) in enumerate((("الحالة", "State", "gold", "حالة فك التشفير"), ("وقت ECM", "Time", "accent", "سرعة الرد"), ("Hops", "Hops", "fg", "عدد القفزات"))):
		x = X + i * (sw + 14)
		o += [card(x, 0, sw, 110, P, 18), T(t, x + 18, 8, sw - 36, 28, "Regular;20", "fgDim", P),
			W(CS, "Label", x + 18, 38, sw - 36, 44, "", [("NGEcm", conv)], "Medium;30", col, P),
			T(sub, x + 18, 80, sw - 36, 24, "Regular;17", "fgMute", P)]
	y = 124
	rows = (("الإيمو", "Cam"), ("الشفرة", "Caid"), ("الريدر", "Reader"), ("السيرفر", "From"), ("البروتوكول", "Protocol"),
		("ECM PID", "Pid"), ("Provider", "Prov"), ("ChID", "Chid"))
	h = 56 + len(rows) * 36 + 10
	o += [card(X, y, CW, h, P, 18), T("تفاصيل فك التشفير", X + 22, y + 10, 400, 36, "ArabicBold;26", "accent", P)]
	for i, (lab, conv) in enumerate(rows):
		yy = y + 56 + i * 36
		o += [T(lab, X + 22, yy, 200, 34, "Regular;22", "fgDim", P), W(CS, "Label", X + 230, yy, CW - 252, 34, "", [("NGEcm", conv)], "Regular;24", "fg", P)]
	y += h + 12
	o += [card(X, y, CW, 112, P, 18), T("أنظمة التشفير في القناة", X + 22, y + 8, 400, 30, "Regular;20", "fgDim", P),
		W(CS, "Label", X + 22, y + 40, CW - 44, 34, "", [("PliExtraInfo", "CryptoBar")], "Regular;26", "fgDim", P),
		W(CS, "Label", X + 22, y + 74, CW - 44, 32, "", [("NGEcm", "Caids")], "Regular;22", "gold", P)]
	y += 124
	o += [card(X, y, CW, LH - y, P, 18), T("ecm.info", X + 22, y + 8, 400, 30, "Medium;22", "fgDim", P),
		'\t\t<widget name="Ecmtext" position="%d,%d" size="%d,%d" font="Regular;20" foregroundColor="fgDim" backgroundColor="%s" transparent="1" halign="left"/>' % (X + 22, y + 40, CW - 44, LH - y - 50, P),
		'\t</screen>']
	return "\n".join(o)


path = os.path.join(SK, "skin.xml")
text = open(path, encoding="utf-8").read()


def replace(name, new):
	global text
	m = re.search(r'\t<screen name="%s"[^>]*>.*?</screen>' % name, text, re.S)
	text = text[:m.start()] + new + text[m.end():]


cs_old = re.search(r'<screen name="ChannelSelection".*?</screen>', text, re.S).group(0)
replace("SecondInfoBar", sib())
replace("ChannelSelection", channels(cs_old))
replace("DeliteBluePanel", blue(None))
open(path, "w", encoding="utf-8").write(text)

# 50 px channel selection bar (every accent colour): the 56 px one, shorter
for src in glob.glob(os.path.join(SK, "ui", "sel_channel56.png")) + glob.glob(os.path.join(SK, "variants", "accent", "*", "ui", "sel_channel56.png")):
	im = Image.open(src).convert("RGBA")
	w = im.width
	top, bot = im.crop((0, 0, w, 25)), im.crop((0, 31, w, 56))
	new = Image.new("RGBA", (w, 50))
	new.paste(top, (0, 0)); new.paste(bot, (0, 25))
	new.save(src.replace("sel_channel56", "sel_channel50"), optimize=True)
print("card screens ok")
