#!/usr/bin/env python3
"""Rounded panel / card graphics for the menu dashboard look. argv: SKINDIR"""
import math, os, sys
from PIL import Image, ImageDraw, ImageFont
SK = sys.argv[1]; UI = os.path.join(SK, "ui"); S = 4
PANEL = (15, 23, 34, 244); CARD = (17, 26, 38, 240); EDGE = (40, 54, 72, 255)
ACC = (47, 196, 230, 255)

def rr(w, h, fill, r=22, edge=None, corners=(True, True, True, True)):
	im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
	d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], r * S, fill=fill, outline=edge, width=S if edge else 0, corners=corners)
	return im.resize((w, h), Image.LANCZOS)

def save(im, name): im.save(os.path.join(UI, name), optimize=True)

for w, tag in ((600, ""), (1280, "_w")):
	# top / bottom caps of a panel; the middle is a plain eLabel of the same colour
	full = rr(w, 96, PANEL, 22)
	save(full.crop((0, 0, w, 24)), "pn_top%s.png" % tag)
	save(full.crop((0, 72, w, 96)), "pn_bot%s.png" % tag)
save(rr(600, 52, PANEL, 18), "keybar.png")
save(rr(214, 96, CARD, 16), "card_s3.png")
save(rr(670, 220, CARD, 20), "card_l.png")
save(rr(670, 124, CARD, 20), "card_m.png")
for name, col in (("bar_gold", (242, 189, 60, 255)), ("bar_green", (46, 204, 113, 255)), ("bar_white", (215, 222, 230, 255))):
	save(rr(456, 8, col, 4), name + ".png")
save(rr(456, 8, (38, 49, 66, 255), 4), "bar_track.png")
# key caps
f = ImageFont.truetype(os.path.join(SK, "../../fonts/NileGlass-Medium.ttf"), 15)
for k in ("OK", "EXIT", "MENU"):
	im = rr(64, 30, (26, 36, 50, 255), 6, edge=(70, 86, 108, 255)); d = ImageDraw.Draw(im)
	tw = d.textlength(k, font=f); d.text(((64 - tw) / 2, 6), k, font=f, fill=(200, 208, 218, 255))
	save(im, "key_%s.png" % k.lower())
# RAM ring, 21 steps
for i in range(21):
	n = 130 * S; im = Image.new("RGBA", (n, n), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
	w = 12 * S; box = [w, w, n - w, n - w]
	d.arc(box, 0, 360, fill=(38, 49, 66, 255), width=w)
	if i:
		d.arc(box, -90, -90 + 360 * i / 20.0, fill=ACC, width=w)
	save(im.resize((130, 130), Image.LANCZOS), "ring_%02d.png" % i)
# small logo
im = Image.new("RGBA", (40 * S, 40 * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
c = 20 * S; R = 18 * S
pts = [(c + R * math.cos(math.radians(60 * k - 30)), c + R * math.sin(math.radians(60 * k - 30))) for k in range(6)]
d.polygon(pts, fill=(47, 196, 230, 255)); r2 = 9 * S
pts2 = [(c + r2 * math.cos(math.radians(60 * k - 30)), c + r2 * math.sin(math.radians(60 * k - 30))) for k in range(6)]
d.polygon(pts2, fill=(15, 23, 34, 255))
save(im.resize((40, 40), Image.LANCZOS), "ng_logo.png")
print("panel graphics ok")
