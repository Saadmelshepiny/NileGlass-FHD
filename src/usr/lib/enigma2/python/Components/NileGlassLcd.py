# -*- coding: utf-8 -*-
# NileGlass FHD - the front display skin (800x480 colour LCD of the Ultimo4K),
# written from the [lcd] settings of nileglass.conf: layout, picon size,
# sizes and colours of the channel name, programme name, progress bar and clock.
# Pure Python (no enigma imports): used by the settings screen, by the package
# install script (after an update the user's choices are written again) and by
# tools/gen_lcd.py (the default file in the package).
# The display skin is read when the GUI starts, so a change needs a GUI restart.

import os
from configparser import ConfigParser

CONF_FILE = "/etc/enigma2/nileglass.conf"
OUT = "/usr/share/enigma2/display/NileGlass_LCD/skin_display.xml"

COLORS = {
	"white": ("#ffffff", "White", "أبيض"),
	"amber": ("#ffc83d", "Amber", "كهرماني"),
	"yellow": ("#fff04d", "Yellow", "أصفر"),
	"orange": ("#ff9a3c", "Orange", "برتقالي"),
	"green": ("#5ee07a", "Green", "أخضر"),
	"cyan": ("#4fe0ff", "Cyan", "سماوي"),
	"blue": ("#5aa8ff", "Light blue", "أزرق فاتح"),
	"red": ("#ff5c5c", "Red", "أحمر"),
	"grey": ("#c8ced6", "Silver", "فضي"),
}
SIZES = {"small": ("Small", "صغير"), "normal": ("Normal", "عادي"), "large": ("Large", "كبير"), "xlarge": ("Extra large", "كبير جدًا")}
LAYOUTS = {
	"standard": ("Logo + clock on top", "اللوجو والساعة فوق"),
	"picon": ("Big logo", "لوجو كبير"),
	"clock": ("Big clock (no logo)", "ساعة كبيرة (بدون لوجو)"),
	"text": ("Big text (no logo)", "كتابة كبيرة (بدون لوجو)"),
}
DEFAULTS = {"layout": "standard", "picon": "normal", "channel_size": "normal", "channel_color": "white",
	"event_size": "normal", "event_color": "amber", "bar_color": "event", "clock_color": "white", "dates": "1"}
CHANNEL_FONT = {"small": 42, "normal": 50, "large": 58, "xlarge": 66}
EVENT_FONT = {"small": 38, "normal": 44, "large": 52, "xlarge": 60}
PICON = {"small": (210, 126), "normal": (250, 150), "large": (300, 180), "xlarge": (340, 204)}
DIM, BAR, LINE, ACC = "#9aa3ae", "#1d2633", "#2a3646", "#2f9cff"
L, R = 40, 760          # the edges of the panel sit under the bezel: 40 px kept free at each side


def read(path=CONF_FILE):
	cp = ConfigParser()
	try:
		cp.read(path, encoding="utf-8")
	except Exception:
		pass
	o = dict(DEFAULTS)
	if cp.has_section("lcd"):
		for k in DEFAULTS:
			v = cp.get("lcd", k, fallback="").strip()
			if v:
				o[k] = v
	if o["layout"] not in LAYOUTS:
		o["layout"] = "standard"
	for k in ("picon", "channel_size", "event_size"):
		if o[k] not in SIZES:
			o[k] = "normal"
	for k in ("channel_color", "event_color", "clock_color"):
		if o[k] not in COLORS:
			o[k] = DEFAULTS[k]
	if o["bar_color"] != "event" and o["bar_color"] not in COLORS:
		o["bar_color"] = "event"
	o["dates"] = "0" if str(o["dates"]).lower() in ("0", "false", "no", "off") else "1"
	return o


def _c(name):
	return COLORS[name][0]


def _w(src, render, x, y, w, h, extra, converts):
	return '\t\t<widget source="%s" render="%s" position="%d,%d" size="%d,%d" %s>\n\t\t\t%s\n\t\t</widget>' % (src, render, x, y, w, h, extra, converts)


def _label(src, x, y, w, h, font, color, halign, converts, wrap=False):
	return _w(src, "Label", x, y, w, h, 'font="%s" foregroundColor="%s" halign="%s" valign="center"%s' % (font, color, halign, "" if wrap else ' noWrap="1"'), converts)


def _clock(x, y, w, h, size, color, halign="right"):
	return _label("global.CurrentTime", x, y, w, h, "NGLcd;%d" % size, color, halign, '<convert type="ClockToText">Format:%H:%M</convert>')


def _dates(o, x, y, w, halign="right", big=30):
	if o["dates"] != "1":
		return []
	return [_label("global.CurrentTime", x, y, w, int(big * 1.2), "NGLcdLight;%d" % big, "#e6eaef", halign, '<convert type="NGDate">{A} {d} {B}</convert>'),
		_label("global.CurrentTime", x, y + int(big * 1.2), w, int(big * 1.0), "NGLcdLight;%d" % int(big * 0.83), DIM, halign, '<convert type="NGHijri"/>')]


def _rec(x, y, halign="left"):
	return '\t\t<widget source="session.RecordState" render="FixedLabel" text="REC" position="%d,%d" size="90,36" font="NGLcd;30" foregroundColor="#ff4040" halign="%s" valign="center" zPosition="3">\n\t\t\t<convert type="ConditionalShowHide"/>\n\t\t</widget>' % (x, y, halign)


def _picon(src, x, y, w, h):
	return _w(src, "LcdPicon", x, y, w, h, 'alphatest="blend" zPosition="2"', '<convert type="ServiceName">Reference</convert>')


def _bottom(o, src, top):
	"""channel name, programme name, progress bar, start / remaining / end - from 'top' down to the bottom"""
	ev, bar = _c(o["event_color"]), _c(o["event_color"] if o["bar_color"] == "event" else o["bar_color"])
	cf, ef = CHANNEL_FONT[o["channel_size"]], EVENT_FONT[o["event_size"]]
	if o["layout"] == "text":
		cf, ef = cf + 10, ef + 10
	timesY, barY = 412, 388
	ch = int(cf * 1.25)
	out = [_label(src["svc"], L, top, R - L, ch, "NGLcd;%d" % cf, _c(o["channel_color"]), "center", '<convert type="ServiceName">%s</convert>' % src["name"])]
	evTop = top + ch + 4
	out.append(_label(src["ev"], L, evTop, R - L, max(ef + 8, barY - 10 - evTop), "NGLcd;%d" % ef, ev, "center", '<convert type="EventName">Name</convert>', wrap=True))
	out += ['\t\t<eLabel position="%d,%d" size="%d,14" backgroundColor="%s" zPosition="1"/>' % (L, barY, R - L, BAR),
		_w(src["ev"], "Progress", L, barY, R - L, 14, 'foregroundColor="%s" backgroundColor="%s" zPosition="2"' % (bar, BAR), '<convert type="EventTime">Progress</convert>'),
		_label(src["ev"], L, timesY, 170, 54, "NGLcd;38", DIM, "left", '<convert type="EventTime">StartTime</convert><convert type="ClockToText">Format:%H:%M</convert>'),
		_label(src["ev"], L + 180, timesY, R - L - 360, 54, "NGLcd;38", "#ffffff", "center", '<convert type="EventTime">VFDRemaining</convert><convert type="RemainingToText">VFD</convert>'),
		_label(src["ev"], R - 170, timesY, 170, 54, "NGLcd;38", DIM, "right", '<convert type="EventTime">EndTime</convert><convert type="ClockToText">Format:%H:%M</convert>')]
	return out


def _maxTop(o):
	"""lowest line the top part may end on, so the channel and the programme name keep their room"""
	cf, ef = CHANNEL_FONT[o["channel_size"]], EVENT_FONT[o["event_size"]]
	return 388 - 10 - int(ef * 1.3) - 4 - int(cf * 1.25) - 8


def info(o, src):
	clock = _c(o["clock_color"])
	lay = o["layout"]
	out = ['\t\t<eLabel position="0,0" size="800,6" backgroundColor="%s" zPosition="1"/>' % ACC]
	if lay in ("standard", "picon"):
		if lay == "picon":
			ph = min(240, _maxTop(o) - 18 - 4)
			pw = ph * 5 // 3
			out.append(_picon(src["picon"], L, 18, pw, ph))
			out.append(_clock(L + pw + 16, 18, R - L - pw - 16, 90, 76, clock))
			out += _dates(o, L + pw + 16, 112, R - L - pw - 16, big=27)
			out.append(_rec(R - 90, 226, "right"))
			top = max(18 + ph, 160) + 4
		else:
			pw, ph = PICON[o["picon"]]
			if 26 + ph + 6 > _maxTop(o):      # big logo and big letters together: the logo gives way
				ph = max(110, _maxTop(o) - 32)
				pw = ph * 5 // 3
			out.append(_picon(src["picon"], L, 26, pw, ph))
			cx = L + pw + 20
			out.append(_clock(cx, 18, R - cx, 96, 88 if pw <= 300 else 76, clock))
			out += _dates(o, cx, 116, R - cx, big=30 if pw <= 300 else 26)
			out.append(_rec(R - 90, 116 if o["dates"] != "1" else 26 + ph - 36, "right"))
			top = max(26 + ph, 188) + 6
		out.append('\t\t<eLabel position="%d,%d" size="%d,2" backgroundColor="%s" zPosition="1"/>' % (L, top, R - L, LINE))
		out += _bottom(o, src, top + 8)
	elif lay == "clock":
		out.append(_clock(L, 10, R - L, 150, 140, clock, "center"))
		if o["dates"] == "1":
			out.append(_label("global.CurrentTime", L, 162, R - L, 38, "NGLcdLight;32", "#e6eaef", "center", '<convert type="NGDate">{A} {d} {B}</convert>'))
		out.append(_rec(L, 16))
		out.append('\t\t<eLabel position="%d,204" size="%d,2" backgroundColor="%s" zPosition="1"/>' % (L, R - L, LINE))
		out += _bottom(o, src, 210)
	else:  # text: channel and programme in large letters, small clock at the top
		out.append(_clock(R - 220, 14, 220, 64, 56, clock))
		if o["dates"] == "1":
			out.append(_label("global.CurrentTime", L, 14, R - L - 230, 64, "NGLcdLight;30", "#e6eaef", "left", '<convert type="NGDate">{A} {d} {B}</convert>'))
		out.append(_rec(L, 84))
		out.append('\t\t<eLabel position="%d,84" size="%d,2" backgroundColor="%s" zPosition="1"/>' % (L, R - L, LINE))
		out += _bottom(o, src, 100)
	return "\n".join(out)


def screen(name, body):
	return '\t<screen name="%s" position="fill" resolution="800,480" backgroundColor="#000000">\n%s\n\t</screen>\n' % (name, body)


def build(o=None):
	o = o or dict(DEFAULTS)
	ev, clock = _c(o["event_color"]), _c(o["clock_color"])
	bar = _c(o["event_color"] if o["bar_color"] == "event" else o["bar_color"])
	live = {"svc": "session.CurrentService", "ev": "session.Event_Now", "picon": "session.CurrentService", "name": "Name"}
	chan = {"svc": "parent.ServiceEvent", "ev": "parent.ServiceEvent", "picon": "parent.ServiceEvent", "name": "Name"}
	epg = {"svc": "parent.Service", "ev": "parent.Event", "picon": "parent.Service", "name": "Name"}
	out = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
		'<!-- NileGlass FHD - front display (800x480), written from the skin settings (Components/NileGlassLcd.py). Screens not defined here come from the image\'s default display skin. -->',
		'<skin>',
		'\t<include filename="/usr/share/enigma2/display/skin_default/skin_display_templates.xml"/>',
		'\t<fonts>',
		'\t\t<font filename="NileGlass-Medium.ttf" name="NGLcd" scale="100"/>',
		'\t\t<font filename="NileGlass-Regular.ttf" name="NGLcdLight" scale="100"/>',
		'\t</fonts>', '']
	out.append(screen("InfoBarSummary", info(o, live)))
	out.append(screen("ChannelSelectionSummary", info(o, chan)))
	out.append(screen("ChannelSelectionRadioSummary", info(o, chan)))
	for name in ("GraphicalEPGPIGSummary", "GraphicalEPGSummary", "EPGSelectionSummary", "EPGSelectionMultiSummary", "GraphicalInfoBarEPGSummary"):
		out.append(screen(name, info(o, epg)))
	out.append(screen("InfoBarMoviePlayerSummary", "\n".join([
		'\t\t<eLabel position="0,0" size="800,6" backgroundColor="%s" zPosition="1"/>' % ACC,
		_clock(L, 16, R - L, 100, 88, clock),
		_label("session.CurrentService", L, 40, 400, 56, "NGLcd;40", "#f2c94c", "left", '<convert type="NGPlayEnd"/>'),
		_label("session.CurrentService", L, 140, R - L, 200, "NGLcd;%d" % (EVENT_FONT[o["event_size"]] + 12), ev, "center", '<convert type="ServiceName">Name</convert>', wrap=True),
		'\t\t<eLabel position="%d,370" size="%d,14" backgroundColor="%s" zPosition="1"/>' % (L, R - L, BAR),
		_w("session.CurrentService", "Progress", L, 370, R - L, 14, 'foregroundColor="%s" backgroundColor="%s" zPosition="2"' % (bar, BAR), '<convert type="ServicePosition">Gauge</convert>'),
		_label("session.CurrentService", L, 396, 350, 64, "NGLcd;44", DIM, "left", '<convert type="ServicePosition">Position,ShowHours</convert>'),
		_label("session.CurrentService", 410, 396, 350, 64, "NGLcd;44", "#ffffff", "right", '<convert type="ServicePosition">Remaining,Negate,ShowHours</convert>')])))
	stand = [_clock(L, 60, R - L, 200, 180, clock if o["clock_color"] != "white" else "#c8ced6", "center")]
	if o["dates"] == "1":
		stand += [_label("global.CurrentTime", L, 290, R - L, 60, "NGLcdLight;46", "#f2c94c", "center", '<convert type="ClockToText">Format:%A %d %B</convert>'),
			_label("global.CurrentTime", L, 356, R - L, 52, "NGLcdLight;38", DIM, "center", '<convert type="NGHijri"/>')]
	stand.append('\t\t<widget source="session.RecordState" render="FixedLabel" text="REC" position="%d,416" size="%d,52" font="NGLcd;40" foregroundColor="#ff4040" halign="center" valign="center">\n\t\t\t<convert type="ConditionalShowHide"/>\n\t\t</widget>' % (L, R - L))
	out.append(screen("StandbySummary", "\n".join(stand)))
	out.append('</skin>\n')
	return "\n".join(out)


def write(o=None, path=OUT):
	"""write the display skin; True when the file changed (a GUI restart shows it)"""
	xml = build(o if o is not None else read())
	try:
		with open(path, encoding="utf-8") as f:
			if f.read() == xml:
				return False
	except Exception:
		pass
	if not os.path.isdir(os.path.dirname(path)):
		return False
	tmp = path + ".tmp"
	with open(tmp, "w", encoding="utf-8") as f:
		f.write(xml)
	os.replace(tmp, path)
	return True


if __name__ == "__main__":      # package install script: the user's front display choices again after an update
	try:
		print("[NileGlass] front display:", "written" if write() else "unchanged")
	except Exception as err:
		print("[NileGlass] front display:", err)
