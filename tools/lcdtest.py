#!/usr/bin/env python3
"""Front display settings: the settings file template has every [lcd] key the
screen writes, the display skin builder gives valid XML for every choice and
keeps every widget inside 40..760 x 0..480, and the install script writes the
user's choices.  argv: PYROOT"""
import importlib.util, itertools, os, re, sys, tempfile, xml.etree.ElementTree as ET
PY = sys.argv[1]
spec = importlib.util.spec_from_file_location("lcd", os.path.join(PY, "Components/NileGlassLcd.py"))
lcd = importlib.util.module_from_spec(spec); spec.loader.exec_module(lcd)
fails = []


def check(name, ok, extra=""):
	print(("PASS " if ok else "FAIL ") + name, "" if ok else extra)
	if not ok:
		fails.append(name)


src = open(os.path.join(PY, "Plugins/Extensions/NileGlassSetup/plugin.py"), encoding="utf-8").read()
tpl = src[src.index('TEMPLATE = """'):]
tpl = tpl[:tpl.index('"""', 15)]
keys = set(re.findall(r"\{(\w+)\}", tpl))
check("template has every front display option", all("lcd_" + k in keys for k in lcd.DEFAULTS), sorted("lcd_" + k for k in lcd.DEFAULTS if "lcd_" + k not in keys))
bad = []
n = 0
for lay, pic, cs, es, dates in itertools.product(lcd.LAYOUTS, lcd.SIZES, lcd.SIZES, lcd.SIZES, ("0", "1")):
	o = dict(lcd.DEFAULTS, layout=lay, picon=pic, channel_size=cs, event_size=es, dates=dates)
	root = ET.fromstring(lcd.build(o))
	n += 1
	for s in root.findall("screen"):
		for w in s:
			x, y = map(int, w.get("position").split(",")); W, H = map(int, w.get("size").split(","))
			full = w.tag == "eLabel" and W == 800
			if W <= 0 or H <= 0 or y < 0 or y + H > 480 or (not full and (x < 40 or x + W > 760)):
				bad.append((lay, pic, cs, es, s.get("name"), w.get("position"), w.get("size")))
		if s.get("name") == "InfoBarSummary":
			ev = [w for w in s if any(c.get("type") == "EventName" for c in w.findall("convert"))][0]
			bar = [w for w in s if w.get("render") == "Progress"][0]
			ey, eh = int(ev.get("position").split(",")[1]), int(ev.get("size").split(",")[1])
			if ey + eh > int(bar.get("position").split(",")[1]):
				bad.append((lay, pic, cs, es, "programme over the bar"))
check("%d combinations: valid and inside the visible window" % n, not bad, bad[:5])
o = dict(lcd.DEFAULTS, event_color="green", channel_color="amber")
check("colours reach the skin", lcd.COLORS["green"][0] in lcd.build(o) and lcd.COLORS["amber"][0] in lcd.build(o))
d = tempfile.mkdtemp()
conf = os.path.join(d, "c.conf")
open(conf, "w").write("[lcd]\nlayout = clock\nevent_color = cyan\nchannel_size = huge\n")
r = lcd.read(conf)
check("settings read, bad values fall back", r["layout"] == "clock" and r["event_color"] == "cyan" and r["channel_size"] == "normal")
os.makedirs(os.path.join(d, "NileGlass_LCD"))
out = os.path.join(d, "NileGlass_LCD", "skin_display.xml")
check("written once", lcd.write(r, out) and not lcd.write(r, out))
check("no display folder: nothing written", not lcd.write(r, os.path.join(d, "none", "x.xml")))
default = open(os.path.join(PY, "../../../share/enigma2/display/NileGlass_LCD/skin_display.xml"), encoding="utf-8").read()
check("package file = default choices", default == lcd.build())
print("ALL OK" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
