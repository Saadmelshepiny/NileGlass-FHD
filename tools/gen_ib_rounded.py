#!/usr/bin/env python3
"""Infobar backgrounds in the menu look: flat navy, rounded corners, a thin
light line between the top strip and the main bar.  Writes the default set
(ui/, 20 %) and every transparency level (variants/glass/<n>/ui); run
gen_ibcolors.py afterwards for the colour sets.  argv: SKINDIR"""
import os, sys
from PIL import Image, ImageDraw
SK = sys.argv[1]
S = 4
FILL = (15, 23, 34)                 # same navy as the menu panels
LINE = (255, 255, 255, 34)
LEVELS = (10, 20, 30, 40, 50)


def alpha(level):
	return int(round(255 * (1 - 0.6 * level / 100.0)))   # 20 % -> 224 (menus: 244)


def shape(w, h, r, corners, a, line=None):
	im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
	d = ImageDraw.Draw(im)
	d.rounded_rectangle([0, 0, w * S - 1, h * S - 1], r * S, fill=FILL + (a,), corners=corners)
	im = im.resize((w, h), Image.LANCZOS)
	if line:
		ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
		y, x0, x1 = line
		ImageDraw.Draw(ov).line([(x0, y), (x1, y)], fill=LINE)
		im = Image.alpha_composite(im, ov)
	return im


TOP = (True, True, False, False)        # tl, tr, br, bl
BOTTOM = (False, False, True, True)
ALL = (True, True, True, True)
FILES = {
	"ib_top_left.png": (1090, 54, 20, TOP, None),
	"ib_top_right.png": (775, 54, 20, TOP, None),
	"ib_main.png": (1890, 170, 24, BOTTOM, (0, 24, 1866)),
	"ib_main_compact.png": (1890, 120, 24, BOTTOM, (0, 24, 1866)),
	"sib_panel.png": (1890, 440, 24, ALL, None),
}
for lv in LEVELS:
	for name, (w, h, r, c, line) in FILES.items():
		im = shape(w, h, r, c, alpha(lv), line)
		dst = os.path.join(SK, "variants", "glass", str(lv), "ui", name)
		os.makedirs(os.path.dirname(dst), exist_ok=True)
		im.save(dst, optimize=True)
		if lv == 20:
			im.save(os.path.join(SK, "ui", name), optimize=True)

# picon plate: rounded card, no gloss
pl = Image.new("RGBA", (222 * S, 134 * S), (0, 0, 0, 0))
ImageDraw.Draw(pl).rounded_rectangle([0, 0, 222 * S - 1, 134 * S - 1], 14 * S, fill=(30, 42, 58, 255), outline=(52, 68, 90, 255), width=2 * S)
pl.resize((222, 134), Image.LANCZOS).save(os.path.join(SK, "ui", "picon_bg.png"), optimize=True)
Image.new("RGBA", (222, 134), (0, 0, 0, 0)).save(os.path.join(SK, "ui", "picon_gloss.png"), optimize=True)
print("rounded infobar backgrounds ok")
