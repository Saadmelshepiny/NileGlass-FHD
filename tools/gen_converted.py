#!/usr/bin/env python3
"""Screens of the image that NileGlass does not draw itself fall back to the
image's emergency skin (picture-in-picture, centred, another look).  This
takes the widget set of every such screen from the image's own default skin
(MX_Slim-Line_NP, which knows every OpenBh screen and its list templates),
drops that skin's decoration (backgrounds, clock, channel name, icons, colour
key icons) and puts the content in a NileGlass left panel: rounded navy
panel at the left edge, logo + title + clock header, colour-key pills.
The result goes into skin.xml between the NG-CONVERTED markers.
argv: SLIM_SKIN_XML  NILEGLASS_SKIN_DIR"""
import copy, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from components import Index, SOURCE_TYPES, GUI_TYPES
import xml.etree.ElementTree as ET

SLIM, SK, BH = sys.argv[1], sys.argv[2], sys.argv[3]
INDEX = Index(os.path.join(BH, "lib/python"))
SKINNAMES = {}
for _c, (_b, _body) in INDEX.classes.items():
	for _n in re.findall(r'skinName[^\n]*?["\'](\w+)["\']', _body):
		SKINNAMES.setdefault(_n, _c)
SLIMDIR = os.path.dirname(SLIM)
SIZES = {"1302,782", "1300,720", "1300,700"}
SKIP = re.compile(r"Wizard|^__|Summary|^picshow$|^Pic_|^Screensaver$|^Standby|^Nab_debOut$")
KEYS = ("red", "green", "yellow", "blue")
OURS_COLORS = {"transparent", "background", "bg", "bgDeep", "bgCard", "bgBar", "bgSel", "foreground", "fg", "fgDim", "fgMute",
	"accent", "gold", "green", "orange", "red", "yellow", "blue", "white", "black", "grey", "line", "lineAccent"}
COLOR_MAP = {"button": "fg", "bgbutton": "bg", "bgbutton2": "bg", "transparent2": "transparent", "bgblue": "bgSel",
	"skyblue": "accent", "info": "fgDim", "un272727": "line"}
FUNCTIONAL_PIX = ("pixmap", "pixmaps", "pointer")   # images a widget needs to work: copied
STYLE_PIX = ("selectionPixmap", "backgroundPixmap", "scrollbarSliderPicture", "scrollbarbackgroundPicture")
LEGACY = "NileGlass_FHD/legacy/"
PANEL_MIN_W = 900
TOP, SIDE, KEYBAR = 100, 24, 74

root = ET.parse(SLIM).getroot()
slim = {s.get("name"): s for s in root.iter("screen")}
ourText = open(os.path.join(SK, "skin.xml"), encoding="utf-8").read()
BEGIN, END = "<!-- NG-CONVERTED BEGIN -->", "<!-- NG-CONVERTED END -->"
ourText = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", "", ourText, flags=re.S)
ours = set(re.findall(r'<screen name="([^"]+)"', ourText))
for f in os.listdir(os.path.join(SK, "layouts")):
	ours |= set(re.findall(r'<screen name="([^"]+)"', open(os.path.join(SK, "layouts", f), encoding="utf-8").read()))
copied = set()


def expand(el, depth=0):
	out = []
	for c in list(el):
		if c.tag == "panel" and depth < 4 and c.get("name") in slim:
			out += expand(slim[c.get("name")], depth + 1)
		else:
			out.append(c)
	return out


def num(pair):
	try:
		a, b = (int(v) for v in pair.split(","))
		return a, b
	except Exception:
		return None


def keyName(el):
	n = el.get("source") or el.get("name") or ""
	return n if n.startswith("key_") or n == "VKeyIcon" else None


def keep(el):
	if el.tag in ("ePixmap", "eLabel"):
		return el.tag == "eLabel" and bool(el.get("text"))
	if el.tag != "widget":
		return el.tag == "applet"
	src = el.get("source") or ""
	if src == "Title" or src.startswith(("global.", "session.")):
		return False
	if el.get("render") == "Pig" or el.get("addon") or keyName(el):
		return False
	return True


def legacy(path):
	src = os.path.join(SLIMDIR, path.split("/", 1)[1]) if path.startswith("MX_Slim-Line_NP/") else None
	if not src or not os.path.isfile(src):
		return None
	rel = path.split("/", 1)[1]
	dst = os.path.join(SK, "legacy", rel)
	if dst not in copied:
		os.makedirs(os.path.dirname(dst), exist_ok=True)
		shutil.copyfile(src, dst)
		copied.add(dst)
	return LEGACY + rel


def restyle(el):
	for k in list(el.attrib):
		v = el.get(k)
		if "Color" in k and v and not v.startswith("#"):
			if v in COLOR_MAP:
				el.set(k, COLOR_MAP[v])
			elif v not in OURS_COLORS:
				el.set(k, "bg" if k.startswith("background") else "fg")
		elif k in STYLE_PIX:
			del el.attrib[k]
		elif k in FUNCTIONAL_PIX and "MX_Slim-Line_NP/" in v:
			parts = []
			for p in v.split(","):
				name, sep, img = p.rpartition(":") if ":" in p else ("", "", p)
				new = legacy(img.strip())
				if new is None:
					parts = None
					break
				parts.append((name + sep) + new)
			if parts is None:
				del el.attrib[k]
			else:
				el.set(k, ",".join(parts))
		elif k == "font" and v.startswith("Bold;"):
			el.set(k, "Medium;" + v.split(";", 1)[1])
	if el.get("render") == "Listbox" or el.get("name") in ("list", "config", "menu", "filelist", "menulist", "languages"):
		el.attrib.setdefault("backgroundColorSelected", "bgSel")
		el.attrib.setdefault("foregroundColorSelected", "white")
	for c in el.iter():
		if c is not el and c.tag != "convert":
			restyle(c)


def keyBar(w, h):
	xs = [SIDE + i * ((w - 2 * SIDE - 200) // 3) for i in range(4)]
	y = h - KEYBAR + 18
	out = ['\t\t<eLabel position="%d,%d" size="%d,1" backgroundColor="line" zPosition="-8"/>' % (SIDE, h - KEYBAR, w - 2 * SIDE)]
	for k, x in zip(KEYS, xs):
		common = 'position="%d,%d" size="200,38" font="Medium;22" foregroundColor="white" backgroundColor="black" transparent="1" halign="center" valign="center" noWrap="1" zPosition="1"' % (x, y)
		out += ['\t\t<ePixmap pixmap="NileGlass_FHD/buttons/%s_k200.png" position="%d,%d" size="200,38" alphatest="blend" conditional="key_%s"/>' % (k, x, y, k),
			'\t\t<widget name="key_%s" %s objectTypes="key_%s,Button,Label"/>' % (k, common, k),
			'\t\t<widget source="key_%s" render="Label" %s objectTypes="key_%s,StaticText"/>' % (k, common, k)]
	return out


def classFor(name):
	if name in INDEX.classes:
		return name
	return SKINNAMES.get(name)


def fixRef(e, comps, dyn):
	"""keep a widget only if the screen offers it, the right way (name= GUI / source= sources)"""
	if e.tag != "widget":
		return True
	n, src = e.get("name"), e.get("source")
	key = n or src
	if key not in comps:
		return any(key.startswith(p) for p in dyn)
	t = comps[key]
	if n and t in SOURCE_TYPES:
		if t != "StaticText":
			return False
		del e.attrib["name"]
		e.set("source", n)
		e.set("render", "Label")
	elif src and t in GUI_TYPES:
		if t not in ("Label", "Button") or e.find("convert") is not None:
			return False
		del e.attrib["source"]
		e.attrib.pop("render", None)
		e.set("name", src)
	return True


INFO = {}


def convert(name, s):
	cls = classFor(name)
	if cls is None or INDEX.derivesFrom(cls, "Setup"):
		return None
	for b in INDEX.bases(cls):                      # the class asks for another skin name: this one is never used
		for lit in re.findall(r'self\.skinName\s*=\s*["\'](\w+)["\']\s*(?:#.*)?$', INDEX.classes[b][1], re.M):
			if lit != name:
				return None
	comps, dyn, inst = INDEX.info(cls)
	els = [copy.deepcopy(e) for e in expand(s)]
	kept = [e for e in els if keep(e) and fixRef(e, comps, dyn)]
	if not kept:
		return None
	boxes = []
	for e in kept:
		p, z = num(e.get("position", "")), num(e.get("size", ""))
		if p and z and z[0] > 0 and z[1] > 0:
			boxes.append((p[0], p[1], p[0] + z[0], p[1] + z[1]))
	if not boxes:
		return None
	bx, by = min(b[0] for b in boxes), min(b[1] for b in boxes)
	bw, bh = max(b[2] for b in boxes) - bx, max(b[3] for b in boxes) - by
	if bw > 1800 or bh > 880:
		return None
	w = max(PANEL_MIN_W, bw + 2 * SIDE)
	h = TOP + bh + 16 + KEYBAR
	attrs = 'name="%s" position="40,center" size="%d,%d" backgroundColor="transparent" flags="wfNoBorder"' % (name, w, h)
	if s.get("title"):
		attrs += ' title="%s"' % s.get("title").replace("&", "&amp;").replace('"', "&quot;")
	out = ['\t<screen %s>' % attrs,
		'\t\t<eLabel position="0,0" size="%d,%d" backgroundColor="bg" cornerRadius="24" zPosition="-10"/>' % (w, h),
		'\t\t<ePixmap pixmap="NileGlass_FHD/ui/ng_logo.png" position="22,24" size="40,40" alphatest="blend" zPosition="1"/>',
		'\t\t<widget source="Title" render="Label" position="74,16" size="%d,56" font="Medium;30" foregroundColor="accent" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>' % (w - 74 - 180),
		'\t\t<widget source="global.CurrentTime" render="Label" position="%d,16" size="156,56" font="Regular;38" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="right" valign="center" noWrap="1"><convert type="ClockToText">Format:%%H:%%M</convert></widget>' % (w - 180),
		'\t\t<eLabel position="%d,84" size="%d,1" backgroundColor="line" zPosition="-8"/>' % (SIDE, w - 2 * SIDE)]
	dx, dy = SIDE - bx, TOP - by
	for e in kept:
		p, z = num(e.get("position", "")), num(e.get("size", ""))
		if p and not (z == (0, 0)):
			e.set("position", "%d,%d" % (p[0] + dx, p[1] + dy))
		restyle(e)
		e.tail = None
		xml = ET.tostring(e, encoding="unicode").strip()
		out.append("\t\t" + xml)
	present = {e.get("name") or e.get("source") for e in kept if e.tag == "widget"}
	for n in sorted(inst - present):
		if n in comps and comps[n] not in SOURCE_TYPES:
			out.append('\t\t<widget name="%s" position="0,0" size="0,0" transparent="1"/>' % n)
	out += keyBar(w, h)
	out.append("\t</screen>")
	INFO[name] = sorted(comps) + ["dyn:" + p for p in sorted(dyn)] + ["static:" + k for k, t in comps.items() if t == "StaticText"]
	return "\n".join(out)


done, skipped = [], []
blocks = []
for name, s in slim.items():
	if name in ours or SKIP.search(name) or s.get("size") not in SIZES or s.get("id"):
		continue
	xml = convert(name, s)
	if xml:
		blocks.append(xml)
		done.append(name)
	else:
		skipped.append(name)
block = BEGIN + "\n\t<!-- generated by tools/gen_converted.py: image screens in the NileGlass left-panel look -->\n" + "\n\n".join(blocks) + "\n\t" + END + "\n"
ourText = ourText.replace("</skin>", "\t" + block + "</skin>")
open(os.path.join(SK, "skin.xml"), "w", encoding="utf-8").write(ourText)
print("converted %d screens, skipped %d: %s" % (len(done), len(skipped), ", ".join(skipped)))
print("legacy images copied:", len(copied))
json.dump(INFO, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "converted_components.json"), "w"), indent=0, sort_keys=True)
