#!/usr/bin/env python3
"""Rounded corners on the list selection bars (all accent colours), like the
menu panel's selection.  Run after gen_variants.py.  argv: SKINDIR"""
import glob, os, sys
from PIL import Image, ImageChops, ImageDraw
SK = sys.argv[1]; S = 4; R = 10
files = [f for f in glob.glob(os.path.join(SK, "ui", "sel_*.png")) + glob.glob(os.path.join(SK, "variants", "accent", "*", "ui", "sel_*.png"))
	if not f.endswith("sel_pn.png")]
for f in files:
	im = Image.open(f).convert("RGBA"); w, h = im.size
	m = Image.new("L", (w * S, h * S), 0)
	ImageDraw.Draw(m).rounded_rectangle([0, 0, w * S - 1, h * S - 1], R * S, fill=255)
	m = m.resize((w, h), Image.LANCZOS)
	im.putalpha(ImageChops.multiply(im.getchannel("A"), m))
	im.save(f, optimize=True)
print("rounded", len(files), "selection bars")
