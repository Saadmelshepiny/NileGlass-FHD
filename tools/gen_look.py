#!/usr/bin/env python3
"""Graphics of the optional "carbon" look (style option look = carbon):
near-black panels with a thin outline, selection bars as a glowing outline in
the accent colour, progress bars as a gradient, ring gauges with tick marks.
Only pictures and colours - nothing extra is drawn at run time.
Writes variants/look/carbon/{accent/<name>,glass/<level>,ui} and keeps the
classic rings in variants/look/classic/ui (to switch back).  argv: SKINDIR"""
import glob, importlib.util, math, os, shutil, sys
from PIL import Image, ImageChops, ImageDraw, ImageFilter
SK = sys.argv[1]
S = 4
spec = importlib.util.spec_from_file_location("st", os.path.join(SK, "../../../lib/enigma2/python/Components/NileGlassStyle.py"))
st = importlib.util.module_from_spec(spec); spec.loader.exec_module(st)
OUT = os.path.join(SK, "variants", "look", "carbon")
FILL = (8, 13, 20)
EDGE = (64, 90, 114)


def rgb(h):
	return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def save(im, *parts):
	dst = os.path.join(OUT, *parts)
	os.makedirs(os.path.dirname(dst), exist_ok=True)
	im.save(dst, optimize=True)


def selection(w, h, acc):
	"""A glowing bar in the accent colour at the left edge and a faint fill
	fading to the right.  Lists draw these pictures cut to their own width
	and row height (and narrower when a scrollbar shows), so nothing of the
	design sits on the right or bottom edge."""
	W, H = w * S, h * S
	r = min(8, h // 5) * S
	mask = Image.new("L", (W + r * 2, H), 0)
	ImageDraw.Draw(mask).rounded_rectangle([0, 0, W + r * 2, H - 1], r, fill=255)
	mask = mask.crop((0, 0, W, H))
	ramp = Image.linear_gradient("L").rotate(90, expand=True).resize((W, H))      # 0 left .. 255 right
	fillA = ramp.point(lambda v: 84 - v * 60 // 255)
	barW = 4 * S
	line = Image.new("L", (W, H), 0)
	ImageDraw.Draw(line).rectangle([0, 0, barW, H], fill=255)
	glow = line.filter(ImageFilter.GaussianBlur(S * 7)).point(lambda v: min(255, v * 2))
	a = ImageChops.lighter(ImageChops.lighter(fillA, glow.point(lambda v: v * 170 // 255)), line)
	a = ImageChops.multiply(a, mask)
	im = Image.new("RGBA", (W, H), acc + (0,))
	im.putalpha(a)
	out = im.resize((w, h), Image.LANCZOS)
	# the bar itself a little lighter than the accent
	px = out.load()
	lite = tuple(min(255, int(c + (255 - c) * 0.35)) for c in acc)
	for y in range(h):
		for x in range(3):
			px[x, y] = lite + (px[x, y][3],)
	return out


def bar(w, h, dark, acc, light):
	"""dark accent -> accent -> light, a thin highlight on top"""
	im = Image.new("RGBA", (w, h))
	px = im.load()
	for x in range(w):
		t = x / float(max(1, w - 1))
		if t < 0.7:
			k = t / 0.7
			c = tuple(int(dark[i] + (acc[i] - dark[i]) * k) for i in range(3))
		else:
			k = (t - 0.7) / 0.3
			c = tuple(int(acc[i] + (light[i] - acc[i]) * k) for i in range(3))
		for y in range(h):
			s = 1.12 if y < max(1, h // 3) else 1.0
			px[x, y] = tuple(min(255, int(v * s)) for v in c) + (255,)
	if h >= 6:      # rounded left end only (the right end is cut by the progress value)
		m = Image.new("L", (w * S, h * S), 0)
		ImageDraw.Draw(m).rounded_rectangle([0, 0, w * S + h * S, h * S - 1], h * S // 2, fill=255)
		im.putalpha(m.resize((w, h), Image.LANCZOS))
	return im


def panel(src, level):
	"""the infobar backgrounds: same shape, near-black, thin outline"""
	base = Image.open(src).convert("RGBA")
	a = base.getchannel("A")
	solid = a.point(lambda v: 255 if v > 8 else 0)
	inner = solid.filter(ImageFilter.MinFilter(3))
	edge = ImageChops.subtract(solid, inner)
	alpha = int(round(255 * (1 - 0.55 * level / 100.0)))
	shape = a.point(lambda v: min(255, v * 255 // max(1, max(a.getextrema()))))
	out = Image.new("RGBA", base.size, FILL + (0,))
	out.putalpha(shape.point(lambda v: v * alpha // 255))
	line = Image.new("RGBA", base.size, EDGE + (0,))
	line.putalpha(edge.point(lambda v: v * 230 // 255))
	return Image.alpha_composite(out, line)


def ring(i, acc):
	n = 130 * S
	im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
	d = ImageDraw.Draw(im)
	c = n / 2.0
	for k in range(48):
		a = math.radians(k * 7.5)
		r1, r2 = (57 if k % 4 else 54) * S, 61 * S
		d.line([(c + r1 * math.cos(a), c + r1 * math.sin(a)), (c + r2 * math.cos(a), c + r2 * math.sin(a))], fill=(96, 128, 152, 150 if k % 4 else 220), width=S)
	w = 8 * S
	box = [c - 50 * S, c - 50 * S, c + 50 * S, c + 50 * S]
	d.arc(box, 0, 360, fill=(30, 44, 58, 255), width=w)
	if i:
		g = Image.new("RGBA", (n, n), (0, 0, 0, 0))
		ImageDraw.Draw(g).arc(box, -90, -90 + 360 * i / 20.0, fill=acc + (150,), width=w)
		im = Image.alpha_composite(im, g.filter(ImageFilter.GaussianBlur(S * 3)))
		ImageDraw.Draw(im).arc(box, -90, -90 + 360 * i / 20.0, fill=acc + (255,), width=w)
	return im.resize((130, 130), Image.LANCZOS)


shutil.rmtree(os.path.join(SK, "variants", "look"), ignore_errors=True)
count = 0
for name, (accent, dark, light) in st.ACCENTS.items():
	acc, dk, lt = rgb(accent), rgb(dark), rgb(light)
	src = os.path.join(SK, "variants", "accent", name)
	for f in sorted(glob.glob(os.path.join(src, "ui", "*.png")) + glob.glob(os.path.join(src, "epg", "*.png"))):
		base = os.path.basename(f)
		sub = os.path.basename(os.path.dirname(f))
		w, h = Image.open(f).size
		if base.startswith("sel_") or sub == "epg":
			im = selection(w, h, acc)
		elif base.startswith(("progress", "signal", "volume")):
			im = bar(w, h, dk, acc, lt)
		else:
			continue
		save(im, "accent", name, sub, base)
		count += 1
for lv in (10, 20, 30, 40, 50):
	for f in sorted(glob.glob(os.path.join(SK, "variants", "glass", str(lv), "ui", "*.png"))):
		save(panel(f, lv), "glass", str(lv), "ui", os.path.basename(f))
		count += 1
classic = os.path.join(SK, "variants", "look", "classic", "ui")
os.makedirs(classic, exist_ok=True)
for i in range(21):
	shutil.copyfile(os.path.join(SK, "ui", "ring_%02d.png" % i), os.path.join(classic, "ring_%02d.png" % i))
	save(ring(i, (53, 182, 230)), "ui", "ring_%02d.png" % i)
	count += 1
print("carbon look: %d pictures" % count)
