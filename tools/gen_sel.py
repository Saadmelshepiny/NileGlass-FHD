#!/usr/bin/env python3
"""Menu and settings selection bars in the accent colour (every accent), made
from that accent's list bar: same look as the other screens.  argv: SKINDIR"""
import glob, os, sys
from PIL import Image, ImageChops, ImageDraw
SK = sys.argv[1]
SIZES = {"sel_pn.png": (560, 58), "sel_set.png": (880, 54)}


def fit(src, w, h, end=40):
	sw, sh = src.size
	im = Image.new("RGBA", (w, sh))
	im.paste(src.crop((0, 0, w - end, sh)), (0, 0))
	im.paste(src.crop((sw - end, 0, sw, sh)), (w - end, 0))
	if sh != h:
		im = im.resize((w, h), Image.LANCZOS)
	m = Image.new("L", (w * 4, h * 4), 0)
	ImageDraw.Draw(m).rounded_rectangle([0, 0, w * 4 - 1, h * 4 - 1], 40, fill=255)
	im.putalpha(ImageChops.multiply(im.getchannel("A"), m.resize((w, h), Image.LANCZOS)))
	return im


for d in [os.path.join(SK, "ui")] + glob.glob(os.path.join(SK, "variants", "accent", "*", "ui")):
	src = os.path.join(d, "sel_list.png")
	if not os.path.isfile(src):
		continue
	base = Image.open(src).convert("RGBA")
	for name, (w, h) in SIZES.items():
		fit(base, w, h).save(os.path.join(d, name), optimize=True)
print("selection bars ok")
