#!/usr/bin/env python3
"""One look for every screen (the Obsidian-like menus): rounded navy panels,
rounded cards, separator lines kept inside the rounded edges, no straight
accent line along a rounded top, logo in the full-screen header.
Idempotent; edits the files in place, keeping their formatting.
argv: SKINDIR"""
import os, re, sys

SK = sys.argv[1]
FILES = [os.path.join(SK, "skin.xml")] + [os.path.join(SK, "layouts", f) for f in ("sib_classic.xml", "channels_simple.xml", "infobar_compact.xml")]
PANEL_COLORS = ("bg", "background")
NGFRAME = (40, 40, 1840, 1000)
SIB_RECT = (12, 6, 1896, 1068)         # second infobar: panel just inside the screen
LEAVE_FULL = ("GridEPG", "NileGlassFilm")
INSET = 24
COLORS = {"bg": "0f1722", "background": "0f1722", "bgDeep": "0b1119", "bgCard": "1a2535"}

ATTR = re.compile(r'(\w+)="([^"]*)"')


def attrs(tag):
	return dict(ATTR.findall(tag))


def setAttr(tag, name, value):
	if re.search(r'\s%s="[^"]*"' % name, tag):
		return re.sub(r'(\s%s=")[^"]*(")' % name, lambda m: m.group(1) + value + m.group(2), tag, count=1)
	return re.sub(r'\s*(/?>)$', lambda m: ' %s="%s"%s' % (name, value, m.group(1)), tag, count=1)


def rect(a):
	try:
		x, y = (int(v) for v in a["position"].split(","))
		w, h = (int(v) for v in a["size"].split(","))
		return x, y, w, h
	except Exception:
		return None


def radiusFor(h):
	return "24" if h >= 120 else "18" if h >= 70 else "12"


def restyleScreen(block):
	head = re.match(r'<screen[^>]*>', block).group(0)
	sa = attrs(head)
	name = sa.get("name", "")
	try:
		W, H = (int(v) for v in sa.get("size", "0,0").split(","))
	except ValueError:
		W = H = 0
	if sa.get("backgroundColor") in PANEL_COLORS and "cornerRadius" not in sa and W and W < 1920:
		block = block.replace(head, setAttr(head, "cornerRadius", "24"), 1)
	# the panel rectangle of this screen
	panelRect = None
	tags = re.findall(r'<eLabel\b[^>]*/>', block)
	best = 0
	for t in tags:
		a = attrs(t)
		r = rect(a)
		if r and a.get("backgroundColor") in PANEL_COLORS and "text" not in a and r[2] * r[3] > best and r[2] >= 200 and r[3] >= 60:
			best, panelRect, panelTag = r[2] * r[3], r, t
	if panelRect is None:
		if re.search(r'<panel name="NG_Frame"\s*/>', block):
			panelRect = NGFRAME
		elif sa.get("backgroundColor") in PANEL_COLORS and W:
			panelRect = (0, 0, W, H)
	if panelRect and best:
		new = panelTag
		if panelRect == (0, 0, 1920, 1080):
			if name in LEAVE_FULL:
				panelRect = None
			elif name == "SecondInfoBar":
				panelRect = SIB_RECT
				new = setAttr(setAttr(new, "position", "%d,%d" % SIB_RECT[:2]), "size", "%d,%d" % SIB_RECT[2:])
		if panelRect:
			new = setAttr(new, "cornerRadius", radiusFor(panelRect[3]))
		block = block.replace(panelTag, new, 1)
	out = []
	for t in re.findall(r'<eLabel\b[^>]*/>', block):
		a = attrs(t)
		r = rect(a)
		if not r or "text" in a:
			continue
		col = a.get("backgroundColor")
		if col == "bgCard" and r[2] >= 120 and r[3] >= 60 and "cornerRadius" not in a:
			out.append((t, setAttr(t, "cornerRadius", "16" if r[3] >= 100 else "12")))
		elif col in ("line", "lineAccent") and r[3] <= 2 and panelRect and r[2] > 300:
			px, py, pw, ph = panelRect
			if r[1] <= py + 2 and col == "lineAccent":
				out.append((t, ""))                      # straight accent along a rounded top
			elif r[0] <= px + 2 and r[0] + r[2] >= px + pw - 2:
				out.append((t, setAttr(setAttr(t, "position", "%d,%d" % (px + INSET, r[1])), "size", "%d,%d" % (pw - 2 * INSET, r[3]))))
	for old, new in out:
		if new:
			block = block.replace(old, new, 1)
		else:
			block = re.sub(r'\n?[ \t]*' + re.escape(old), "", block, count=1)
	if name == "NG_Frame" and "ng_logo.png" not in block:
		block = block.replace('<widget source="Title" render="Label" position="80,52" size="1160,66"',
			'<ePixmap pixmap="NileGlass_FHD/ui/ng_logo.png" position="66,65" size="40,40" alphatest="blend" zPosition="1"/>\n\t\t'
			'<widget source="Title" render="Label" position="120,52" size="1120,66"', 1)
	return block


def restyle(text):
	text = re.sub(r'<screen\b.*?</screen>', lambda m: restyleScreen(m.group(0)), text, flags=re.S)

	def color(m):
		name, alpha = m.group(1), m.group(2)
		return '<color name="%s" value="#%s%s"/>' % (name, alpha, COLORS[name])
	return re.sub(r'<color name="(%s)" value="#([0-9a-fA-F]{2})[0-9a-fA-F]{6}"/>' % "|".join(COLORS), color, text)


for f in FILES:
	if not os.path.isfile(f):
		continue
	src = open(f, encoding="utf-8").read()
	dst = restyle(src)
	if dst != src:
		open(f, "w", encoding="utf-8").write(dst)
	print("%-24s %s" % (os.path.basename(f), "changed" if dst != src else "unchanged"))
