#!/usr/bin/env python3
"""Render approximate screenshots of skin.xml screens with sample data.

This is NOT enigma2 - it is a small PIL emulation used to check the layout
(positions, sizes, colours, z-order, fonts, transparency) before installing.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT, BG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
SKIN = os.environ.get("NG_SKIN_DIR") or os.path.join(ROOT, "usr/share/enigma2/NileGlass_FHD")
FONTS = os.path.join(ROOT, "usr/share/fonts")
skin = ET.parse(os.path.join(SKIN, "skin.xml")).getroot()
screens = {s.get("name"): s for s in skin.findall("screen")}
colors = {c.get("name"): c.get("value") for c in skin.find("colors")}
FONTMAP = {"Regular": "NileGlass-Regular.ttf", "Medium": "NileGlass-Medium.ttf", "Light": "NileGlass-Light.ttf",
	"ArabicBold": "NileGlass-ArabicBold.ttf", "Console": "NileGlass-Regular.ttf"}
ARABIC = re.compile(r"[\u0600-\u06ff\ufb50-\ufeff]")
STYLE = {}
if os.environ.get("NG_STYLE_XML"):
	_st = ET.parse(os.environ["NG_STYLE_XML"]).getroot()
	colors.update({c.get("name"): c.get("value") for c in _st.find("colors")})
	STYLE = {f.get("name"): (f.get("filename"), int(f.get("scale"))) for f in _st.find("fonts")}
	for _sc in _st.findall("screen"):
		screens[_sc.get("name")] = _sc


def col(v, default=(255, 255, 255, 255)):
	if not v:
		return default
	v = colors.get(v, v)
	v = v.lstrip("#")
	if len(v) == 6:
		v = "00" + v
	a, r, g, b = (int(v[i:i + 2], 16) for i in (0, 2, 4, 6))
	return (r, g, b, 255 - a)


_fc = {}


def font(spec, arabic=False):
	name, size = spec.split(";")
	size = int(size)
	if STYLE:
		fname, scale = STYLE.get("Replacement" if arabic and name != "ArabicBold" else name, STYLE["Regular"])
		key = (fname, size * scale // 100)
		if key not in _fc:
			_fc[key] = ImageFont.truetype(os.path.join(FONTS, fname), key[1], layout_engine=ImageFont.Layout.RAQM)
		return _fc[key]
	f = "NileGlass-ArabicBold.ttf" if name == "ArabicBold" else ("NileGlass-Arabic.ttf" if arabic else FONTMAP.get(name, "NileGlass-Regular.ttf"))
	if arabic and name != "ArabicBold":
		size = int(size * 1.08)
	key = (f, size)
	if key not in _fc:
		_fc[key] = ImageFont.truetype(os.path.join(FONTS, f), size, layout_engine=ImageFont.Layout.RAQM)
	return _fc[key]


def expand(el):
	out = []
	for c in el:
		if c.tag == "panel" and c.get("name") is None and c.get("position"):
			import copy as _copy
			ox, oy = (int(v) for v in c.get("position").split(","))
			for e in expand(c):
				e = _copy.deepcopy(e)
				if e.get("position") and "," in e.get("position") and e.get("position").replace(",", "").replace("-", "").isdigit():
					x, y = (int(v) for v in e.get("position").split(","))
					e.set("position", "%d,%d" % (x + ox, y + oy))
				out.append(e)
		elif c.tag == "panel":
			out.extend(expand(screens[c.get("name")]))
		else:
			out.append(c)
	return out


def xy(s):
	return tuple(int(x) for x in s.split(","))


def pix(path):
	return Image.open(os.path.join(SKIN, path.replace("NileGlass_FHD/", ""))).convert("RGBA")


COLOR_RE = re.compile(r"\\c([0-9a-fA-F]{8})")


def drawText(canvas, el, text, pos=None, size=None):
	if text is None or text == "":
		return
	x, y = pos or xy(el.get("position"))
	w, h = size or xy(el.get("size"))
	lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
	d = ImageDraw.Draw(lay)
	fg = col(el.get("foregroundColor"), (238, 241, 244, 255))
	spec = el.get("font", "Regular;28")
	halign = el.get("halign")
	valign = el.get("valign", "top")
	lines = text.split("\n")
	lh = int(int(spec.split(";")[1]) * 1.25)
	if valign == "center":
		ty = (h - lh * len(lines)) // 2
	else:
		ty = 0
	for line in lines:
		segs = []
		cur = fg
		pos2 = 0
		for m in COLOR_RE.finditer(line):
			segs.append((line[pos2:m.start()], cur))
			c = m.group(1)
			cur = (int(c[2:4], 16), int(c[4:6], 16), int(c[6:8], 16), 255)
			pos2 = m.end()
		segs.append((line[pos2:], cur))
		plain = "".join(s for s, _ in segs)
		isAr = bool(ARABIC.search(plain))
		f = font(spec, isAr)
		tw = d.textlength(plain, font=f)
		al = halign or ("right" if isAr else "left")
		tx = {"left": 0, "center": (w - tw) / 2, "right": w - tw}.get(al, 0)
		if len(segs) > 1 and not isAr:
			for s, c in segs:
				d.text((tx, ty), s, font=f, fill=c)
				tx += d.textlength(s, font=f)
		else:
			shadow = el.get("shadowColor")
			if shadow:
				d.text((tx + 2, ty + 2), plain, font=f, fill=(0, 0, 0, 200))
			d.text((tx, ty), plain, font=f, fill=segs[-1][1] if len(segs) > 1 else fg)
		ty += lh
	canvas.alpha_composite(lay, (x, y))


def drawRect(canvas, el, color):
	x, y = xy(el.get("position"))
	w, h = xy(el.get("size"))
	r = int((el.get("cornerRadius") or "0").split(";")[0])
	if r:
		m = Image.new("L", (w * 4, h * 4), 0)
		ImageDraw.Draw(m).rounded_rectangle([0, 0, w * 4 - 1, h * 4 - 1], r * 4, fill=255)
		im = Image.new("RGBA", (w, h), color)
		im.putalpha(ImageChops.multiply(im.getchannel("A"), m.resize((w, h), Image.LANCZOS)))
		canvas.alpha_composite(im, (x, y))
		if el.get("widgetBorderWidth"):
			ln = Image.new("RGBA", (w * 4, h * 4), (0, 0, 0, 0))
			ImageDraw.Draw(ln).rounded_rectangle([1, 1, w * 4 - 2, h * 4 - 2], r * 4, outline=col(colors.get(el.get("widgetBorderColor"), "#002c3e50")), width=4)
			canvas.alpha_composite(ln.resize((w, h), Image.LANCZOS), (x, y))
		return
	canvas.alpha_composite(Image.new("RGBA", (w, h), color), (x, y))
	if el.get("widgetBorderWidth"):
		ImageDraw.Draw(canvas).rectangle([x, y, x + w - 1, y + h - 1], outline=col(colors.get(el.get("widgetBorderColor"), "#002c3e50")))


def drawPix(canvas, el, img, scale=False):
	x, y = xy(el.get("position"))
	w, h = xy(el.get("size"))
	if scale or img.size != (w, h):
		img = img.copy()
		img.thumbnail((w, h), Image.LANCZOS) if scale else None
		if not scale:
			img = img.crop((0, 0, w, h))
	ox = x + (w - img.width) // 2 if scale else x
	oy = y + (h - img.height) // 2 if scale else y
	canvas.alpha_composite(img, (ox, oy))
	bw = int(el.get("borderWidth", "0"))
	if bw and scale:
		d = ImageDraw.Draw(canvas)
		d.rectangle([ox - bw, oy - bw, ox + img.width + bw - 1, oy + img.height + bw - 1], outline=col(el.get("borderColor")), width=bw)


class Sample:
	def __init__(self, data):
		self.data = data

	def text(self, el):
		src = el.get("source") or el.get("name")
		convs = [(c.get("type"), (c.text or "").strip()) for c in el.findall("convert")]
		key = src + "|" + ("|".join("%s:%s" % c for c in convs) if convs else ("@" + el.get("render") if el.get("render") else ""))
		for k, v in self.data.items():
			if k == key:
				return v
		for k, v in self.data.items():  # loose: match by converter only
			if "|" in k and k.split("|", 1)[1] == key.split("|", 1)[1] and k.split("|", 1)[0] == "*":
				return v
		return None


def render(name, data, bgimg, extra=None, outname=None):
	full = bgimg.copy()
	scr = screens[name]
	sw, sh = xy(scr.get("size", "1920,1080"))
	pos = scr.get("position", "0,0")
	ox = (1920 - sw) // 2 if pos.startswith("center") else int(pos.split(",")[0])
	oy = (1080 - sh) // 2 if pos.endswith("center") else int(pos.split(",")[1])
	canvas = Image.new("RGBA", (sw, sh), (0, 0, 0, 0)) if (ox or oy or (sw, sh) != (1920, 1080)) else full
	_sbg = scr.get("backgroundColor")
	if _sbg and _sbg != "transparent" and not _sbg.startswith("#ff"):
		drawRect(canvas, ET.Element("x", {"position": "0,0", "size": "%d,%d" % (sw, sh), "cornerRadius": scr.get("cornerRadius", "0")}), col(_sbg))
	elements = expand(screens[name])
	elements = sorted(enumerate(elements), key=lambda e: (int(e[1].get("zPosition", "0")), e[0]))
	S = Sample(data)
	for _, el in elements:
		tag = el.tag
		_z = int(el.get("zPosition", "0") or 0)
		if _z >= 10 and data.get("__dash") and _z // 10 != data["__dash"]:
			continue
		if el.get("objectTypes"):
			key, *types = el.get("objectTypes").split(",")
			if data.get("__static__" + key) is not None and ("StaticText" in types) != data["__static__" + key]:
				continue
			if ("__has__" + key) in data and not data["__has__" + key]:
				continue
		if el.get("conditional") and not data.get("__has__" + el.get("conditional"), True):
			continue
		_ngs = [(c.text or "").strip() for c in el.findall("convert") if c.get("type") == "NGStream"]
		if _ngs and (_ngs[0] == "Only") != bool(data.get("__stream")):
			continue
		if tag == "ePixmap":
			_im = pix(el.get("pixmap"))
			if el.get("scale") == "1" and el.get("size"):
				_im = _im.resize(xy(el.get("size")), Image.LANCZOS)
			drawPix(canvas, el, _im)
		elif tag == "eLabel":
			bg = el.get("backgroundColor")
			if el.get("text"):
				if bg and el.get("transparent") != "1":
					drawRect(canvas, el, col(bg))
				drawText(canvas, el, el.get("text"))
			elif bg:
				drawRect(canvas, el, col(bg))
		elif tag == "widget":
			render_ = el.get("render")
			src = el.get("source") or ""
			wname = el.get("name")
			if extra and wname in extra:
				extra[wname](canvas, el)
				continue
			if extra and src in extra and render_ in ("Listbox",):
				extra[src](canvas, el)
				continue
			if render_ == "FixedLabel":
				if el.get("backgroundColor") and el.get("transparent") != "1":
					drawRect(canvas, el, col(el.get("backgroundColor")))
				if not el.get("text"):
					continue
				_cs = [(c.text or "").strip() for c in el.findall("convert") if c.get("type") == "ConditionalShowHide"]
				_on = bool(data.get("__online", True))
				if not _cs or _on != (_cs[0] == "Invert"):
					drawText(canvas, el, el.get("text"))
				continue
			if render_ == "Pixmap":
				if el.get("source") in ("session.CurrentService",) and el.get("pixmap") and not el.findall("convert"):
					drawPix(canvas, el, pix(el.get("pixmap")))
				elif S.text(el) == "1":
					drawPix(canvas, el, pix(el.get("pixmap")))
			elif render_ == "Picon":
				if data.get("__picon"):
					_pw, _ph = xy(el.get("size"))
					drawPix(canvas, el, data["__picon"].resize((_pw, _ph), Image.LANCZOS) if _pw > 300 else data["__picon"], scale=True)
			elif render_ == "NGPoster":
				if el.get("kind") == "backdrop":
					if data.get("__backdrop"):
						bw, bh = xy(el.get("size"))
						drawPix(canvas, el, data["__backdrop"].resize((bw, bh), Image.LANCZOS), scale=True)
				elif el.get("eventIndex"):
					i = int(el.get("eventIndex"))
					names = ["نشرة الأخبار", "رسالة إلى الوالي", "عائلتي تربح", "", "الكنز", "صاحبة السعادة", "", "Inception"]
					t = names[(i - 1) % len(names)]
					img = samplePoster(t, i) if t and t != "نشرة الأخبار" else pix("ui/noposter.png")
					drawPix(canvas, el, img, scale=True)
				elif el.get("prefetch") != "1" and data.get("__poster"):
					drawPix(canvas, el, data["__poster"], scale=True)
			elif render_ == "NGEventInfo" and el.get("mode") == "card":
				lc = "\\c00" + colors.get(el.get("labelColor"), el.get("labelColor", "#9aa3ae")).lstrip("#")[-6:]
				vc = "\\c00eef1f4"
				rows = [("السنة", "2019"), ("النوع", "حرب، دراما، أكشن"), ("المخرج", "شريف عرفة"), ("البلد", "مصر"), ("الأبطال", "أحمد عز، هند صبري، إياد نصار"), ("المدة", "135 دقيقة")]
				el2 = ET.Element("x", dict(el.attrib)); el2.set("halign", "right")
				drawText(canvas, el2, "\n".join("%s%s:  %s%s" % (lc, a, vc, b) for a, b in rows))
			elif render_ == "NGEventInfo" and el.get("fields") == "rating":
				drawText(canvas, el, "★ 7.4")
			elif render_ == "NGEventInfo":
				drawText(canvas, el, ("فيلم  •  " if "type" in el.get("fields", "") else "") + "2019  •  حرب، دراما  •  ★ 7.4".replace("  •  ★ 7.4", "" if "rating" not in el.get("fields", "year,genres,rating") else "  •  ★ 7.4"))
			elif render_ == "NGStars":
				x, y = xy(el.get("position")); w, h = xy(el.get("size"))
				canvas.alpha_composite(pix(el.get("pixmap")).crop((0, 0, int(w * 0.74), h)), (x, y))
			elif render_ == "NGSwatch":
				v = S.text(el)
				if v:
					x, y = xy(el.get("position")); w, h = xy(el.get("size"))
					ImageDraw.Draw(canvas).rounded_rectangle([x, y, x + w - 1, y + h - 1], 8, fill=col(v), outline=(90, 110, 130, 255))
			elif render_ == "NGWeatherIcon":
				drawPix(canvas, el, pix("weather/partly_night.png").resize(xy(el.get("size")), Image.LANCZOS))
			elif render_ == "Progress":
				v = S.text(el)
				if v:
					x, y = xy(el.get("position")); w, h = xy(el.get("size"))
					p = el.get("pixmap")
					fill = pix(p).resize((w, h)) if p else Image.new("RGBA", (w, h), col(el.get("foregroundColor")))
					cw = int(w * float(re.sub(r"[^0-9.]", "", v) or 0) / 100)
					if cw > 0:
						canvas.alpha_composite(fill.crop((0, 0, cw, h)), (x, y))
			elif render_ == "NGRing":
				drawPix(canvas, el, pix("ui/ring_08.png"))
			elif render_ == "Pig":
				x, y = xy(el.get("position")); w, h = xy(el.get("size"))
				canvas.alpha_composite(bgimg.resize((w, h), Image.LANCZOS), (x, y))
			elif render_ == "NGEventList" and el.get("fields"):
				i = int(el.get("start", "0"))
				ev = [("23:45 - 01:00", "رسالة إلى الوالي", "فيلم كوميدي. والي يعود من الماضي إلى القاهرة الحديثة ويواجه مواقف طريفة."),
					("01:00 - 02:00", "عائلتي تربح", "برنامج مسابقات عائلي تتنافس فيه أسرتان على جوائز مالية."),
					("02:00 - 03:30", "الكنز", "دراما تاريخية عن رحلة البحث عن كنز فرعوني مفقود عبر أجيال."),
					("03:30 - 05:00", "Inception", "A thief who steals corporate secrets through dream-sharing technology.")][i % 4]
				drawText(canvas, el, {"time": ev[0], "title": ev[1], "desc": ev[2]}[el.get("fields")])
			elif render_ == "NGEventList" and el.get("start") is not None:
				i = int(el.get("start"))
				rows = ["18:55  نشرة الأخبار", "19:30  رسالة إلى الوالي", "20:01  عائلتي تربح", "21:00  برنامج حواري", "22:00  الكنز", "23:30  صاحبة السعادة", "00:30  موجز", "01:00  Inception"]
				sep = "\n" if el.get("timeBreak") == "1" else "  "
				drawText(canvas, el, "\\c00f2c94c" + rows[i].replace("  ", sep + "\\c00d6dbe1", 1))
			elif render_ in ("Label", "ChannelNumber", "NGEventList") or (wname and not render_):
				drawText(canvas, el, S.text(el))
	if canvas is not full:
		full.alpha_composite(canvas, (ox, oy))
	full.convert("RGB").save(os.path.join(OUT, (outname or name) + ".png"), optimize=True)
	print("rendered", name)


# ------------------------------------------------------------------ sample data
def samplePoster(title, seed=0):
	w, h = 400, 600
	img = Image.new("RGBA", (w, h))
	px = img.load()
	pal = [(30, 40, 70), (90, 30, 40), (30, 80, 60), (70, 50, 100), (100, 70, 20), (20, 70, 100), (80, 80, 80), (60, 30, 80), (40, 60, 30)][seed % 9]
	for yy in range(h):
		for xx in range(w):
			t = yy / h
			px[xx, yy] = (int(pal[0] + 120 * t), int(pal[1] + 30 * t), int(max(0, pal[2] - 40 * t)), 255)
	d = ImageDraw.Draw(img)
	d.ellipse([60, 120, 340, 400], fill=(230, 150, 60, 255))
	d.rectangle([0, 360, w, h], fill=(20, 18, 30, 255))
	for i in range(8):
		d.polygon([(i * 60 - 20, 360), (i * 60 + 30, 250 + (i % 3) * 30), (i * 60 + 80, 360)], fill=(14, 12, 22, 255))
	f = font("ArabicBold;72", True)
	tw = d.textlength(title, font=f)
	d.text(((w - tw) / 2, 430), title, font=f, fill=(255, 255, 255, 255))
	f2 = font("Regular;22")
	d.text((120, 540), "SAMPLE POSTER", font=f2, fill=(200, 200, 200, 255))
	return img


def samplePicon(text):
	img = Image.new("RGBA", (220, 132), (0, 0, 0, 0))
	d = ImageDraw.Draw(img)
	f = font("Medium;46")
	tw = d.textlength(text, font=f)
	d.text(((220 - tw) / 2, 28), text, font=f, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
	f = font("Regular;24")
	d.text((70, 86), "MASR HD", font=f, fill=(240, 200, 60, 255))
	return img


def sampleBackdrop():
	w, h = 780, 439
	img = Image.new("RGBA", (w, h))
	px = img.load()
	for yy in range(h):
		for xx in range(w):
			t = yy / h
			px[xx, yy] = (int(200 - 120 * t), int(120 - 60 * t), int(60 + 10 * t), 255)
	d = ImageDraw.Draw(img)
	d.polygon([(0, 300), (160, 200), (330, 280), (520, 170), (780, 290), (780, 439), (0, 439)], fill=(50, 40, 40, 255))
	d.polygon([(0, 360), (250, 300), (500, 370), (780, 330), (780, 439), (0, 439)], fill=(25, 20, 22, 255))
	d.text((20, 400), "SAMPLE BACKDROP", font=font("Regular;20"), fill=(220, 220, 220, 255))
	return img


bg = Image.open(BG).convert("RGBA")
# use the clean upper part of the reference frame as "live TV"
bg = bg.crop((0, 0, 1920, 790)).resize((1920, 1080), Image.LANCZOS)

common = {
	"__picon": samplePicon("MBC"), "__poster": samplePoster("الممر"), "__backdrop": sampleBackdrop(),
	"session.CurrentService|ServiceName:Provider": "MBC",
	"session.CurrentService|ServiceName:Name": "MBC MASR HD",
	"session.CurrentService|@ChannelNumber": "101",
	"session.CurrentService|ServiceInfo:HasTelext|ConditionalShowHide:": "1",
	"session.CurrentService|ServiceInfo:SubtitlesAvailable|ConditionalShowHide:": "1",
	"session.CurrentService|ServiceInfo:IsWidescreen|ConditionalShowHide:": "1",
	"session.CurrentService|ServiceInfo:IsHD|ConditionalShowHide:": "1",
	"global.CurrentTime|NGWeather:temp": "22°C",
	"global.CurrentTime|NGWeather:desc": "غائم جزئيًا",
	"global.CurrentTime|NGWeather:city": "القاهرة",
	"global.CurrentTime|ClockToText:Format:%d %b %Y": "10 نوفمبر 2026",
	"global.CurrentTime|ClockToText:Format:%H:%M": "23:58",
	"global.CurrentTime|ClockToText:Format:%A %d %B": "الثلاثاء 10 نوفمبر",
	"global.CurrentTime|ClockToText:Format:%A %d %B %Y": "الثلاثاء 10 نوفمبر 2026",
	"session.FrontendInfo|FrontendInfo:STRING,4": "\\c00d6dbe1A \\c002f9cffB \\c00d6dbe1C \\c00d6dbe1D",
	"session.CurrentService|PliExtraInfo:TunerSystem": "DVB-S2",
	"session.Event_Now|EventTime:StartTime|ClockToText:Format:%H:%M": "22:30",
	"session.Event_Now|EventName:Name": "فيلم: الممر",
	"session.Event_Now|EventTime:Remaining|RemainingToText:InMinutes": "+52 min",
	"session.Event_Now|EventTime:Progress": "41",
	"session.Event_Now|EventName:Genre": "Movie / Drama",
	"session.Event_Next|EventTime:StartTime|ClockToText:Format:%H:%M": "00:50",
	"session.Event_Next|EventName:Name": "نشرة الأخبار",
	"session.Event_Next|EventTime:Duration|ClockToText:InMinutes": "30 min",
	"session.CurrentService|PliExtraInfo:ResolutionString": "1920x1080i",
	"session.CurrentService|PliExtraInfo:CryptoNameCaid": "FTA",
	"session.CurrentService|ServiceInfo:Sid": "2969",
	"session.CurrentService|PliExtraInfo:VideoCodec": "MPEG4-H.264",
	"session.FrontendStatus|FrontendInfo:SNR": "78",
	"session.FrontendStatus|FrontendInfo:AGC": "91",
	"session.CurrentService|PliExtraInfo:CryptoBar": "\\c00555555BI \\c00555555S \\c00555555V \\c00555555I \\c00555555N \\c00f2c94cCW \\c00555555ND \\c00555555CO \\c00555555DC",
	"session.CurrentService|PliExtraInfo:TransponderInfo": "11938 H 27500 5/6",
	"session.CurrentService|ServiceOrbitalPosition:Short": "7.0W",
	"session.FrontendStatus|FrontendInfo:SNRdB": "13.2 dB",
	"session.CurrentService|PliExtraInfo:PIDInfo": "V:4001 A:4002 PCR:4001 PMT:0100",
	"session.CurrentService|NGSysInfo:BoxName": "Vu+ Ultimo4K",
	"session.CurrentService|NGSysInfo:StorageWarn": "الفلاش 93%",
	"session.CurrentService|NGSubs:Ok": "ترجمة عربي",
	"session.CurrentService|NGSysInfo:Image": "OpenBh 5.6",
	"session.CurrentService|NGSysInfo:CpuLoad": "34%",
	"session.CurrentService|NGSysInfo:CpuTemp": "67°C",
	"session.CurrentService|NGSysInfo:RamPercent": "48%",
	"session.CurrentService|NGSysInfo:RamUsed": "980 MB / 2.0 GB",
	"session.CurrentService|NGSysInfo:FlashPercent": "22%",
	"session.CurrentService|NGSysInfo:FlashFree": "2.9 GB",
	"session.CurrentService|NGSysInfo:IP": "192.168.1.20",
	"session.CurrentService|NGSysInfo:Uptime": "11m",
	"session.CurrentService|NGSysInfo:HddFree": "612 GB / 931 GB",
	"session.CurrentService|NGCodec:Resolution": "1080i25",
	"session.CurrentService|NGCodec:Codecs": "H.264 · AC3",
	"session.CurrentService|NGCodec:Full": "1080p24 · HEVC · DD+",
	"session.CurrentService|NGPlayEnd:": "ينتهي 00:47",
	"global.CurrentTime|NGHijri:": "29 جمادى الأولى 1448 هـ",
	"global.CurrentTime|ClockToText:Format:%A %d %B %Y|NGHijri:Append": "الثلاثاء 10 نوفمبر 2026 · 29 جمادى الأولى",
}
# progress values: converter returns percent for the preview
for k in list(common):
	if k.endswith("NGSysInfo:CpuLoad") or k.endswith("NGSysInfo:RamPercent") or k.endswith("NGSysInfo:FlashPercent"):
		pass
progress = {"session.FrontendStatus|FrontendInfo:SNR": "78", "session.FrontendStatus|FrontendInfo:AGC": "91"}


class PercentSample(dict):
	pass


def withLabels(d):
	"""Labels of SNR/AGC show '78 %' while Progress uses the number."""
	return d


# Labels for SNR/AGC need '%'; emulate by a second key lookup in render via text post-fix
_orig = drawText


def drawText(canvas, el, text, pos=None, size=None):  # noqa: F811
	if text in ("78", "91") and el.get("render") == "Label":
		text += " %"
	if text and text.endswith("%") and el.get("render") == "Label" and "NGSysInfo" in "".join(c.get("type") for c in el.findall("convert")):
		pass
	_orig(canvas, el, text, pos, size)


def pct(v):
	return v.rstrip("%")


# progress widgets read numeric values
for k in ("session.CurrentService|NGSysInfo:CpuLoad", "session.CurrentService|NGSysInfo:RamPercent", "session.CurrentService|NGSysInfo:FlashPercent"):
	pass

ONLY = set(filter(None, os.environ.get("NG_SCREENS", "").split(",")))
_render = render


def render(name, data, bgimg, extra=None, outname=None):  # noqa: F811
	if not ONLY or name in ONLY:
		_render(name, data, bgimg, extra, outname)


# ---- InfoBar
if os.environ.get("NG_NEUTRAL"):
	common = dict(common)
	common.update({"__picon": samplePicon("TV 1"), "session.CurrentService|ServiceName:Provider": "Provider",
		"session.CurrentService|ServiceName:Name": "Channel 1 HD"})
	render("InfoBar", common, bg)
	sys.exit(0)
render("InfoBar", common, bg)

# ---- SecondInfoBar
sib = dict(common)
sib.update({
	"session.CurrentService|ServiceName:Provider": "MBC", "session.Event_Now|EventTime:EndTime|ClockToText:Format:%H:%M": "00:50",
	"channel|": "MBC MASR HD",
	"epg_description|": "دراما حربية تدور أحداثها بعد نكسة 1967، حول ضابط في سلاح الصاعقة يقود مجموعة من الجنود في مهمة خاصة خلف خطوط العدو.\n\nإخراج: شريف عرفة",
	"key_red|": "", "key_green|": "Green Panel", "key_yellow|": "", "key_blue|": "Blue Panel",
})
sib["session.CurrentService|@NGEventList"] = "\\c002f9cff00:50  \\c00d6dbe1نشرة الأخبار\n\\c002f9cff01:20  \\c00d6dbe1Inception\n\\c002f9cff03:50  \\c00d6dbe1برنامج صاحبة السعادة\n\\c002f9cff05:00  \\c00d6dbe1صباح الخير يا مصر"


def sysProgress(d):
	d = dict(d)
	return d


render("SecondInfoBar", sib, bg)


# ---- ChannelSelection
def channelList(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	ih = int(el.get("itemHeight"))
	rows = [("100", "ON E HD", "برنامج حواري", 40), ("101", "MBC MASR HD", "فيلم: الممر", 62), ("102", "CBC HD", "مسلسل الاختيار ح 12", 85),
		("103", "DMC HD", "صاحبة السعادة", 20), ("104", "Al Hayah", "مسلسل", 55), ("105", "Nile Sport", "ملخص الدوري", 70),
		("106", "Rotana Cinema", "فيلم عربي", 90), ("107", "Al Jazeera", "نشرة الأخبار", 35), ("108", "Sky News Arabia", "موجز", 15),
		("109", "BBC Arabic", "تقرير خاص", 60), ("110", "Spacetoon", "رسوم متحركة", 45)]
	sel = pix("ui/sel_channel.png")
	d = ImageDraw.Draw(canvas)
	for i, (num, name, ev, p) in enumerate(rows[: h // ih]):
		ry = y + i * ih
		if i == 1:
			canvas.alpha_composite(sel, (x, ry))
		e = ET.Element("x", {"font": "Regular;30", "foregroundColor": "white" if i == 1 else "fgDim", "valign": "center", "halign": "right"})
		drawText(canvas, e, num, (x + 10, ry), (70, ih))
		pc = samplePicon(name.split()[0][:4]).resize((100, 60), Image.LANCZOS)
		canvas.alpha_composite(pc, (x + 96, ry + 6))
		e = ET.Element("x", {"font": "Regular;32", "foregroundColor": "white", "valign": "center"})
		drawText(canvas, e, name, (x + 214, ry), (330, ih))
		bx = x + 556
		d.rectangle([bx, ry + 32, bx + 60, ry + 40], outline=(80, 86, 96, 255))
		d.rectangle([bx + 1, ry + 33, bx + int(59 * p / 100), ry + 39], fill=(255, 255, 255, 255) if i == 1 else (47, 156, 255, 255))
		e = ET.Element("x", {"font": "Regular;26", "foregroundColor": "#d6dbe1" if i == 1 else "fgDim", "valign": "center"})
		drawText(canvas, e, ev, (bx + 76, ry), (w - (bx + 76 - x) - 16, ih))


cs = dict(common)
cs.update({
	"ServiceEvent|ServiceName:Name": "MBC MASR HD",
	"ServiceEvent|NGWatch:Text": "الأكثر مشاهدة #2 · 5 س 20 د",
	"ServiceEvent|NGServiceTp:Line": "11862 H 27500 5/6  ·  DVB-S2 8PSK  ·  7.0°W Nilesat", "ServiceEvent|NGServiceTp:Details": "MBC  ·  HD  ·  SID 1005  ·  TS 20700  ·  ON 366",
	"ServiceEvent|EventTime:StartTime|ClockToText:Format:%H:%M": "22:30",
	"ServiceEvent|EventTime:EndTime|ClockToText:Format:%H:%M": "00:50",
	"ServiceEvent|EventTime:Progress": "62",
	"ServiceEvent|EventTime:Remaining|RemainingToText:InMinutes": "+52 min",
	"ServiceEvent|EventName:Name": "فيلم: الممر",
	"ServiceEvent|EventName:FullDescription": sib["epg_description|"],
	"ServiceEvent|@NGEventList": sib["session.CurrentService|@NGEventList"],
	"Title|@Label": "المفضلة (TV)",
	"key_red|": "الكل", "key_green|": "الأقمار", "key_yellow|": "المزودين", "key_blue|": "المفضلة",
	"__static__key_red": False, "__static__key_green": False, "__static__key_yellow": False, "__static__key_blue": False,
})
render("ChannelSelection", cs, bg, {"list": channelList})


# ---- Menu
def menuList(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	items = [("setup", "الإعدادات"), ("blackhole_extra", "تطبيقات OpenBh"), ("plugin_selection", "الإضافات"), ("timermenu", "المؤقتات"),
		("backupscreen", "النسخ الاحتياطي ومدير الصور"), ("information", "المعلومات"), ("shutdown", "الإيقاف وإعادة التشغيل")]
	selName = (el.get("selectionPixmap") or "NileGlass_FHD/ui/sel_menu.png").split("NileGlass_FHD/")[-1]
	sel = pix(selName)
	ih, isz = (58, 40) if "sel_pn" in selName else (66, 48)
	for i, (key, label) in enumerate(items):
		ry = y + i * ih
		if i == 0:
			canvas.alpha_composite(sel.crop((0, 0, w, ih)), (x, ry))
		canvas.alpha_composite(pix("menu/%s.png" % key).resize((isz, isz), Image.LANCZOS), (x + 16, ry + (ih - isz) // 2))
		e = ET.Element("x", {"font": "Regular;30", "foregroundColor": "white", "valign": "center", "halign": "right"})
		drawText(canvas, e, label, (x + 70, ry), (w - 90, ih))


mn = dict(common)
mn.update({"Title|@Label": "القائمة الرئيسية", "description|@Label": "معلومات عن الجهاز والصورة والشبكة", "key_blue": "", "__has__key_red": False, "__has__key_green": False, "__has__key_yellow": False, "__has__key_blue": False})
mn.update({"session.CurrentService|NGSysInfo:CpuTemp": "64°C", "session.CurrentService|NGSysInfo:LoadAvg": "0.42", "session.CurrentService|NGSysInfo:Fan": "N/A",
	"session.CurrentService|NGSysInfo:Uptime": "1h 42m", "session.CurrentService|NGSysInfo:RamPercent": "40%", "session.CurrentService|NGSysInfo:RamMB": "600 / 1536 MB",
	"session.CurrentService|NGSysInfo:FlashFree": "2.6 GB", "session.CurrentService|NGSysInfo:FlashPercent": "38", "session.CurrentService|NGSysInfo:HddFreeOnly": "612 GB",
	"session.CurrentService|NGSysInfo:HddPercent": "34", "session.CurrentService|NGSysInfo:UsbFree": "—", "session.CurrentService|NGSysInfo:UsbPercent": "0",
	"session.CurrentService|NGSysInfo:Online": "متصل", "session.CurrentService|NGSysInfo:IP": "192.168.1.20", "session.CurrentService|NGSysInfo:NetType": "Wi-Fi · wlan0",
	"session.CurrentService|NGSysInfo:NetDown": "213 kbit/s", "session.CurrentService|NGSysInfo:NetUp": "14 kbit/s", "session.CurrentService|NGSysInfo:Image": "OpenBh 6.0",
	"session.CurrentService|NGSysInfo:BoxName": "Vu+ Ultimo4K",
	"session.CurrentService|NGSysInfo:StorageWarn": "الفلاش 93%",
	"session.CurrentService|NGSubs:Ok": "ترجمة عربي", "session.CurrentService|NGSysInfo:SkinVersion": "v2.8.0"})
S_ = "session.CurrentService|"
mn.update({S_ + "NGSysInfo:OnlineYes": "متصل", S_ + "NGSysInfo:Gateway": "192.168.1.1", S_ + "NGSysInfo:Netmask": "255.255.255.0",
	S_ + "NGSysInfo:Dns": "192.168.1.1  ·  8.8.8.8", S_ + "NGSysInfo:Mac": "00:1D:EC:0A:12:7F", S_ + "NGSysInfo:LinkSpeed": "100 Mb/s",
	S_ + "NGSysInfo:RxTotal": "3.4 GB", S_ + "NGSysInfo:TxTotal": "412 MB", S_ + "NGSysInfo:Rotor": "7.0°W", S_ + "NGSysInfo:TunerCount": "8",
	S_ + "NGSysInfo:TunerName": "Vuplus DVB-S NIM(45308X FBC)", S_ + "NGSysInfo:TunerTypes": "DVB-S2X", S_ + "ServiceOrbitalPosition:Short": "7.0W",
	S_ + "PliExtraInfo:TunerSystem": "DVB-S2", S_ + "PliExtraInfo:TransponderInfo": "11938 H 27500 5/6",
	"session.FrontendStatus|FrontendInfo:SNR": "78", "session.FrontendStatus|FrontendInfo:AGC": "91", "session.FrontendStatus|FrontendInfo:SNRdB": "11.2 dB",
	S_ + "NGCodec:Video": "H.264", S_ + "NGCodec:Audio": "AC3", S_ + "NGCodec:Fps": "25 fps", S_ + "NGCodec:Full": "1080i25 · H.264 · AC3",
	S_ + "NGSysInfo:VideoOut": "2160p50", S_ + "NGSysInfo:HdmiColour": "YCbCr422  ·  12bit", S_ + "NGSysInfo:Aspect": "16:9",
	S_ + "NGSysInfo:Volume": "55%", S_ + "NGSysInfo:Ac3": "تحويل ستيريو", S_ + "NGSysInfo:SkinVersion": "v2.8.2"})
for _g, _n in ((4, "Menu"), (1, "Menu_net"), (2, "Menu_tuner"), (3, "Menu_av")):
	_d = dict(mn); _d["__dash"] = _g
	render("Menu", _d, bg, {"menu": menuList}, outname=_n)


# ---- Green panel
def greenList(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	rows = [("Saad Auto Subssupport", "Automatic Arabic subtitles v2.5.6"), ("Saad AutoBiss", "Saad AutoBiss v4.7 - Feeds, Radar, Auto Biss, AutoRoll, Web control"),
		("Saad Panel", "التحكم في Enigma2"), ("Saad Radio", "تشغيل الراديو في الخلفية مع صورة القناة"), ("Saad EPG", "دليل برامج القنوات العربية والأوروبية من الإنترنت"),
		("Saad LiveOnSat", "مباريات اليوم: القنوات والترددات والنتائج المباشرة"), ("Saad Quran Hub - القرآن الكريم", "Quran reciters and radios"), ("Weather & News", "Visual Crossing / Open-Meteo - الطقس")]
	sel = pix("ui/sel_panel.png")
	for i, (n, dsc) in enumerate(rows[: h // 90]):
		ry = y + i * 90
		if i == 0:
			canvas.alpha_composite(sel, (x, ry))
		ic = Image.new("RGBA", (150, 60), (0, 0, 0, 0)); d = ImageDraw.Draw(ic)
		d.rounded_rectangle([0, 0, 149, 59], radius=8, fill=(30, 110, 200, 255) if i % 2 else (40, 150, 80, 255))
		d.text((12, 14), n.split()[0][:8], font=font("Medium;26"), fill=(255, 255, 255, 255))
		canvas.alpha_composite(ic, (x + 28, ry + 15))
		e = ET.Element("x", {"font": "Medium;36", "foregroundColor": "white", "valign": "center", "halign": "left"})
		drawText(canvas, e, n, (x + 214, ry + 4), (1280, 48))
		e = ET.Element("x", {"font": "Regular;27", "foregroundColor": "#ffffff" if i == 0 else "#aab3be", "valign": "center", "halign": "left"})
		drawText(canvas, e, dsc, (x + 214, ry + 50), (1280, 36))


PLUGIN_SAMPLE = {
	"list|NGPluginInfo:Version": "2.8.3", "list|NGPluginInfo:Last": "من 3 ساعة", "list|NGPluginInfo:Runs": "27",
	"list|NGPluginInfo:Name": "Saad Auto Subssupport", "list|NGPluginInfo:Description": "Automatic Arabic subtitles v2.8.3 - ترجمة عربية تلقائية للأفلام والمسلسلات من أكثر من مصدر",
	"list|NGPluginInfo:Package": "enigma2-plugin-extensions-saadautosub", "list|NGPluginInfo:Maker": "Saad",
	"list|NGPluginInfo:Installed": "12/11/2026", "list|NGPluginInfo:Size": "3.4 MB", "list|NGPluginInfo:Kind": "إضافة · مفتوح المصدر",
	"list|NGPluginInfo:Feed": "أحدث إصدار", "list|NGPluginInfo:Folder": "Extensions/SaadAutoSub",
	"list|NGPluginInfo:Background": "نعم، بيشتغل مع الجهاز", "list|NGPluginInfo:Places": "قائمة الإضافات · الملحقات (الأزرق) · قائمة القنوات",
}
gp = dict(common)
gp.update(PLUGIN_SAMPLE)
gp.update({"Title|@Label": "OpenBh Green Panel", "key_red|": "Panel Setup", "key_green|": "Fast Plug", "key_yellow|": "إضافات", "key_blue|": "سكريبتات"})
render("DeliteGreenPanel", gp, bg, {"list": greenList})


# ---- Settings (Setup screen with the NileGlass items)
def setupList(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	rows = [("— المظهر —", None), ("   لون التمييز", "أزرق"), ("   شفافية الخلفية", "20% (الافتراضي)"), ("   الخط", "Ubuntu + Tajawal"), ("   حجم الخط", "عادي"),
		("— البوسترات —", None), ("   عرض بوسترات البرامج", "نعم"), ("   مفتاح TMDB", ""), ("   لغة البحث", "العربية"),
		("— الطقس —", None), ("   عرض الطقس", "نعم"), ("   المدينة", "الإسكندرية")]
	sel = pix("ui/sel_wide.png")
	for i, (lab, val) in enumerate(rows[: h // 54]):
		ry = y + i * 54
		if i == 1:
			canvas.alpha_composite(sel.crop((0, 0, w, 54)), (x, ry))
		e = ET.Element("x", {"font": "Regular;30", "foregroundColor": "accent" if val is None else "white", "valign": "center", "halign": "left"})
		drawText(canvas, e, lab.strip() if val is None else lab, (x + 16, ry), (900, 54))
		if val is not None:
			e = ET.Element("x", {"font": "Regular;30", "foregroundColor": "white", "valign": "center", "halign": "right"})
			drawText(canvas, e, val, (x + w // 2, ry), (w // 2 - 20, 54))


st = dict(common)
st.update({"Title|@Label": "إعدادات سكين NileGlass", "description|": "لون شريط التحديد وأشرطة التقدم والعناوين.", "key_red|@Label": "إلغاء", "key_green|@Label": "حفظ", "key_blue|@Label": "مسح البوسترات",
	"__static__key_red": True, "__static__key_green": True, "__static__key_blue": True, "__has__key_yellow": False})
st = dict(st); st.update({k: v for k, v in mn.items() if k.startswith(("session.", "global."))}); st["__dash"] = 3
render("Setup", st, bg, {"config": setupList})


ev = dict(common)
ev.update({"Title|@Label": "معلومات البرنامج", "Event|EventName:Name": "فيلم: الممر", "channel|": "MBC MASR HD", "datetime|": "الثلاثاء 10 نوفمبر  22:30", "duration|": "135 دقيقة",
	"FullDescription|": "دراما حربية تدور أحداثها بعد نكسة 1967، حول ضابط في سلاح الصاعقة يقود مجموعة من الجنود في مهمة خاصة خلف خطوط العدو.\n\nإخراج: شريف عرفة\nبطولة: أحمد عز، هند صبري، إياد نصار",
	"key_red|": "", "key_green|": "إضافة مؤقت", "key_yellow|": "دليل القناة", "key_blue|": "الدليل المتعدد", "__static__key_green": False, "__static__key_yellow": False, "__static__key_blue": False, "__has__key_red": False})
for _i, _n in enumerate(("أحمد عز", "هند صبري", "إياد نصار", "محمد فراج", "أحمد رزق")):
	ev["cast_n%d|" % _i] = _n
ev["cast_title|"] = "الأبطال"


def castPhoto(i):
	def f(c, e):
		x, y = xy(e.get("position")); w, h = xy(e.get("size"))
		im = Image.new("RGBA", (w, h), (40 + 25 * i, 50 + 10 * i, 70, 255)); d = ImageDraw.Draw(im)
		d.ellipse([w // 2 - 22, 24, w // 2 + 22, 68], fill=(200, 190, 180, 255)); d.rectangle([w // 2 - 34, 78, w // 2 + 34, h], fill=(90, 100, 120, 255))
		c.alpha_composite(im, (x, y))
	return f


render("EventView", ev, bg, {"cast_p%d" % i: castPhoto(i) for i in range(5)})
ip = dict(common)
ip.update({"__stream": True, "session.CurrentService|ServiceName:Name": "Days Old Radio (راديو ديز أولد)", "session.Event_Now|EventName:Name": "Days Old Radio",
	"session.CurrentService|NGStreamInfo:Net": "162 kb/s", "session.CurrentService|NGStreamInfo:Volume": "55%",
	"session.CurrentService|NGStreamInfo:Audio": "MP3 · 128 kb/s · Stereo", "session.CurrentService|NGStreamInfo:Quality": "جودة جيدة",
	"session.CurrentService|NGStream:Only": "1", "session.CurrentService|PliExtraInfo:TransponderInfo": "stream.zeno.fm",
	"session.CurrentService|NGCodec:Resolution": "", "session.CurrentService|NGCodec:Codecs": "MP3", "global.CurrentTime|NGDate:{A} {d} {B}": "الأربعاء 11 نوفمبر"})
render("InfoBar", ip, bg, outname="InfoBarIPTV")
mp = dict(common)
mp.update({"session.CurrentService|ServiceName:Name": "The Dark Knight (2008)", "session.CurrentService|ServicePosition:Gauge": "38",
	"session.CurrentService|ServicePosition:Position": "0:58:12", "session.CurrentService|ServicePosition:Remaining": "-1:34:00", "session.CurrentService|ServicePosition:Length": "2:32:12"})
render("MoviePlayer", mp, bg)


# ---- NileGlass settings with preview
def ngSetupList(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	rows = [("— المظهر —", None), ("   شكل الإنفوبار", "كامل (الإشارة والتفاصيل)"), ("   لون التمييز", "أزرق"), ("   شفافية الخلفية", "20% (الافتراضي)"), ("   الخط", "IBM Plex Arabic"),
		("   حجم الخط", "عادي"), ("   عناوين عريضة", "نعم"), ("   لون النص", "كريمي"), ("   حجم خط الإنفوبار", "كبير"), ("   إطار حول كتابة الإنفوبار", "نعم"),
		("   اتجاه الكتابة", "تلقائي (حسب لغة الجهاز)"), ("   ترجمة القوائم غير المترجمة", "نعم")]
	sel = pix("ui/sel_list.png")
	for i, (lab, val) in enumerate(rows[: h // 54]):
		ry = y + i * 54
		if i == 4:
			canvas.alpha_composite(sel.crop((0, 0, min(w, sel.width), 54)), (x, ry))
		e = ET.Element("x", {"font": "Regular;30", "foregroundColor": "accent" if val is None else "white", "valign": "center", "halign": "left"})
		drawText(canvas, e, lab.strip() if val is None else lab, (x + 16, ry), (640, 54))
		if val is not None:
			e = ET.Element("x", {"font": "Regular;30", "foregroundColor": "white", "valign": "center", "halign": "right"})
			drawText(canvas, e, val, (x + 600, ry), (w - 620, 54))


def pvGlass(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	canvas.alpha_composite(pix("variants/glass/20/ui/ib_top_right.png").crop((0, 0, w, h)), (x, y))


def pvAccent(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	canvas.alpha_composite(pix("variants/accent/blue/ui/sel_menu.png").crop((0, 0, w, min(h, 66))), (x, y))


ns = dict(common)
ns.update({"Title|@Label": "إعدادات سكين NileGlass", "preview_title|": "معاينة", "preview_font|": "نموذج للخط  123  Font sample",
	"pv_ib_time|": "22:30", "pv_ib_title|": "فيلم السهرة", "pv_head|": "القائمة الرئيسية  Menu", "pv_row|": "الإعدادات  Settings", "pv_row2|": "المؤقتات  Timers",
	"pv_desc|": "دراما حربية تدور أحداثها بعد 1967 عن ضابط يقود مهمة خاصة. Drama 0123456789",
	"description|": "لون شريط التحديد وأشرطة التقدم والعناوين.", "key_red|@Label": "إلغاء", "key_green|@Label": "حفظ", "key_yellow|@Label": "اختبار", "key_blue|@Label": "أدوات",
	"__static__key_red": True, "__static__key_green": True, "__static__key_yellow": True, "__static__key_blue": True})
render("NileGlassSetup", ns, bg, {"config": ngSetupList, "preview_glass": pvGlass, "preview_accent": pvAccent})


# ---- Tonight (films / matches from the Saad EPG plugin)
TONIGHT_ROWS = [("20:00", "عفريت ترانزيت", "Rotana Cinema  +2", "ROTANA", "الآن"), ("21:00", "الكابتن فيليبس", "MBC 2  •  2013  •  7.5/10", "MBC2", "مفضلة"),
	("21:00", "فتاتي", "MBC 4  +2  •  1991  •  7.4/10", "MBC4", ""), ("21:30", "أسوار القمر", "Rotana Cinema Masr  •  2015  •  5.5/10", "ROT", ""),
	("22:00", "Deadfall", "OSN Movies  •  2012  •  6.0/10  •  أكشن", "OSN", ""), ("22:15", "أيامنا الحلوة", "Rotana Classic", "CLAS", ""),
	("23:00", "الرجل يحب مرتين", "Cima", "CIMA", ""), ("23:45", "المهمة المستحيلة", "MBC Max  •  2025  •  7.2/10", "MAX", "")]


def tonightList(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	ih = 92
	sel = pix("ui/sel_channel.png")
	for i, (t, title, l2, pic, badge) in enumerate(TONIGHT_ROWS[: h // ih]):
		ry = y + i * ih
		if i == 1:
			canvas.alpha_composite(sel.resize((w, ih)), (x, ry))
		drawText(canvas, ET.Element("x", {"font": "Medium;34", "foregroundColor": "white", "valign": "center"}), t, (x + 14, ry), (106, ih))
		canvas.alpha_composite(samplePicon(pic or title[:4]).resize((100, 60), Image.LANCZOS), (x + 124, ry + 16))
		drawText(canvas, ET.Element("x", {"font": "Medium;32", "foregroundColor": "white", "valign": "center", "halign": "left"}), title, (x + 240, ry + 6), (700, 46))
		drawText(canvas, ET.Element("x", {"font": "Regular;26", "foregroundColor": "#ffffff" if i == 1 else "#aab3be", "valign": "center", "halign": "left"}), l2, (x + 240, ry + 50), (830, 36))
		if badge:
			drawText(canvas, ET.Element("x", {"font": "Regular;26", "foregroundColor": "#ffc850", "valign": "center", "halign": "right"}), badge, (x + 940, ry + 8), (140, 42))


tn = dict(common)
tn.update({"Title|@Label": "الليلة على قنواتك", "tab_films|": "أفلام الليلة  (41)", "tab_matches|": "الماتشات  (40)",
	"badge|": "مفضلة", "channel|": "MBC 2\nوعلى: MBC 2 HD، MBC Max", "when|": "21:00 - 23:25\nبعد 1:05 ساعة",
	"title|": "الكابتن فيليبس", "info|": "Captain Phillips  •  2013  •  التقييم 7.5/10",
	"desc|": "قصة حقيقية عن القبطان ريتشارد فيليبس وسفينة الشحن الأمريكية التي استولى عليها قراصنة صوماليون عام 2009، في أول اختطاف لسفينة أمريكية منذ قرنين.",
	"status|": "آخر تحديث للدليل  14:52", "empty|": "", "versus|": "",
	"key_red|@Label": "تسجيل", "key_green|@Label": "تحويل", "key_yellow|@Label": "الماتشات", "key_blue|@Label": "المفضلة فقط",
	"__static__key_red": True, "__static__key_green": True, "__static__key_yellow": True, "__static__key_blue": True})


def tnPoster(canvas, el):
	drawPix(canvas, el, samplePoster("الكابتن فيليبس", 3), scale=True)


def tnPicon(canvas, el):
	drawPix(canvas, el, samplePicon("MBC2"), scale=True)


def tnLine(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	canvas.alpha_composite(Image.new("RGBA", (w, h), col("accent")), (x, y))


render("NileGlassTonight", tn, bg, {"list": tonightList, "poster": tnPoster, "picon": tnPicon, "tab_films_line": tnLine, "tab_matches_line": lambda c, e: None, "versus": lambda c, e: None})


# ---- OpenBh popups (1.7)
def rowsList(rows, icons=None, ih=64, font="Regular;32", sel=0):
	def f(canvas, el):
		x, y = xy(el.get("position")); w, h = xy(el.get("size"))
		for i, r in enumerate(rows[: h // ih]):
			ry = y + i * ih
			if i == sel:
				canvas.alpha_composite(Image.new("RGBA", (w, ih), col("bgSel")), (x, ry))
			tx = x + 20
			if icons:
				canvas.alpha_composite(pix("icons/%s.png" % icons[i]).resize((48, 48), Image.LANCZOS), (x + 18, ry + (ih - 48) // 2))
				tx = x + 88
			drawText(canvas, ET.Element("x", {"font": font, "foregroundColor": "white" if i == sel else "fg", "valign": "center", "halign": "left"}), r, (tx, ry), (w - (tx - x) - 16, ih))
	return f


pop = dict(common)
ext_rows = ["OpenBh Speed Up", "إدارة الأجهزة", "Quick Option settings", "الإعدادات العامة", "إعدادات شريط المعلومات", "ضبط وضع شاشة العرض", "معالج تهيئة الفلاش ممورى",
	"لوحة تحكم مشاركة الملفات", "إعدادات تبادل الملفات", "OpenVPN", "UPnP Minidlna", "Inadyn", "نسخ احتياطي للإعدادات"]
ext_icons = ["fast_plugin_setup", "dev_hdd", "plugin_list_setup", "nabsettings", "infopanel_osd", "infopanel_osd", "infopanel_space", "infopanel_samba", "swapsettings",
	"inadynsettings", "nabuploads", "inadynsettings", "mountwizard"]
d = dict(pop); d.update({"Title|@Label": "OpenBh Extra Settings"})
render("DeliteSettings", d, bg, {"list": rowsList(ext_rows, ext_icons)})
d = dict(pop); d.update({"Title|@Label": "OpenBh Script Panel", "statuslab|": "This script will delete all crash-logs and debug-logs from /home/root, /media/hdd and /media/usb to free space on the receiver.", "key_green|": "تنفيذ"})
render("DeliteScript", d, bg, {"list": rowsList(["Delete_all_Crashlogs", "Ifconfig", "Netstat", "Uptime"], ih=56, font="Regular;30")})
d = dict(pop); d.update({"Title|@Label": "OpenBh E2 Addons Manager"})
render("DeliteAddons", d, bg, {"list": rowsList(["Addons and Feeds Manager", "OpenBh online update", "Manual Install OpenBh packages", "تثبيت يدوي لحزم الملفات المحمية", "لوحة إلغاء تثبيت الإضافات", "التحكم الأبوي على الإضافات"],
	["addons_manager", "nabuploads", "nabpackpanel", "ipkpackpanel", "uninstpanel", "nabsettings"])})


def bpCam(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	canvas.alpha_composite(Image.new("RGBA", (w, h), col("bgCard")), (x, y))
	drawText(canvas, ET.Element("x", {"font": "Medium;34", "foregroundColor": "white", "valign": "center", "halign": "center"}), "<  OSCam-emu 11880  >", (x, y), (w, h))


d = dict(pop)
d.update({"Title|@Label": "OpenBh Blue Panel", "lab1|": "3  CAMs Installed", "lab2|": "Press OK to start the selected cam", "lab3|": "", "activecam|": "Active: OSCam-emu 11880",
	"Ilab1|": "Name: beIN SPORTS 1 HD", "Ilab2|": "Provider: beIN", "Ilab3|": "Aspect Ratio: 16:9", "Ilab4|": "Videosize: 1920x1080",
	"session.CurrentService|ServiceName:Name": "beIN SPORTS 1 HD", "session.CurrentService|PliExtraInfo:TransponderInfo": "11013 H 27500 3/4  7.0W",
	"session.CurrentService|PliExtraInfo:PIDInfo": "V 0x0100  A 0x0101  SID 0x0FA1",
	"session.CurrentService|PliExtraInfo:CryptoBar": "\\c007f7f7fBI  S  \\c0000ff00V  \\c007f7f7fI  N  CW  ND  CO  DC",
	"session.CurrentService|NGEcm:State": "تم فك التشفير", "session.CurrentService|NGEcm:Cam": "OSCam-emu 11880", "session.CurrentService|NGEcm:Caid": "0x0500  Viaccess",
	"session.CurrentService|NGEcm:Source": "emulator", "session.CurrentService|NGEcm:Protocol": "emu", "session.CurrentService|NGEcm:Hops": "0", "session.CurrentService|NGEcm:Time": "312 ms",
	"Ecmtext|": "Caid: 0x0500\nPid: 0x0B2C\nProv: 0x030B00\nReader: emulator\nFrom: local\nProtocol: emu\nHops: 0\nEcm Time: 0.312",
	"key_red|": "Autocam", "key_green|": "Cam Info", "key_yellow|": "System Info", "key_blue|": "Extra Settings", "__picon": samplePicon("beIN")})
render("DeliteBluePanel", d, bg, {"list": bpCam})
d = dict(pop); d.update({"VolumeText|": "45"})
render("Volume", d, bg)
d = dict(pop); d.update({"From|": "من:", "Goto|": "إلى:", "Tuner|": "الموالف:", "posFrom|": "7.0W", "posGoto|": "13.0E", "tunerName|": "Tuner A", "turnTime|": "00:12", "turnSpeed|": "1.5°/s"})
render("Dish", d, bg, {"Dishpixmap": lambda c, e: drawPix(c, e, pix("ui/dish.png"))})


# ---- 1.8: infobar, audio tracks
ib = dict(common)
ib.update({"session.CurrentService|ServiceInfo:AudioCodec": "AC3 5.1", "session.FrontendStatus|FrontendInfo:SNRdB": "13.4 dB",
	"global.CurrentTime|ClockToText:Format:%a %d %b": "الثلاثاء 10 نوفمبر"})
render("InfoBar", ib, bg, outname="InfoBar18")


def audioConfig(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	rows = [("To Subtitle Selection", ""), ("AC3 / AC3+ Downmix", "ترميز الصوت الرقمي المزدوج"), ("AAC / AAC+ Downmix", "ترميز الصوت الرقمي المزدوج"),
		("DTS / DTS-HD Transcoding", "Dolby Digital"), ("Dolby TrueHD Transcoding", "Dolby Digital"), ("Enable Bluetooth Audio", "لا يعمل")]
	for i, (a, b) in enumerate(rows):
		ry = y + i * 58
		drawText(canvas, ET.Element("x", {"font": "Regular;30", "foregroundColor": "fg", "valign": "center", "halign": "left"}), a, (x + 10, ry), (560, 58))
		drawText(canvas, ET.Element("x", {"font": "Regular;30", "foregroundColor": "fg", "valign": "center", "halign": "right"}), b, (x + 560, ry), (w - 580, 58))


def audioStreams(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	rows = [("1", "MPEG1 Layer II", "الإنجليزية", True), ("2", "MPEG1 Layer II", "التركية", False), ("3", "MPEG1 Layer II", "الروسية", False), ("4", "MPEG1 Layer II", "الإيطالية", False),
		("5", "AC3", "التشيكية", False), ("6", "MPEG1 Layer II", "المجرية", False), ("7", "MPEG1 Layer II", "البولندية", False)]
	for i, (n, c, lang, sel) in enumerate(rows):
		ry = y + i * 60
		if i == 0:
			canvas.alpha_composite(Image.new("RGBA", (w, 60), col("bgSel")), (x, ry))
		drawText(canvas, ET.Element("x", {"font": "Regular;32", "foregroundColor": "white", "valign": "center", "halign": "center"}), n, (x + 14, ry), (56, 60))
		drawText(canvas, ET.Element("x", {"font": "Regular;26", "foregroundColor": "#ffffff" if i == 0 else "#9aa3ae", "valign": "center", "halign": "left"}), c, (x + 84, ry), (300, 60))
		drawText(canvas, ET.Element("x", {"font": "Regular;32", "foregroundColor": "white", "valign": "center", "halign": "left"}), lang, (x + 400, ry), (540, 60))
		if sel:
			canvas.alpha_composite(pix("selections/selectioncross.png"), (x + 980, ry + 14))


au = dict(common)
au.update({"Title|@Label": "Select Audio Track", "session.CurrentService|ServiceName:Name": "Love Nature 4K", "session.Event_Now|EventName:Name": "عالم الحيوان",
	"session.CurrentService|ServiceInfo:AudioCodec": "MPEG1 Layer II  Stereo", "session.CurrentService|PliExtraInfo:ResolutionString": "3840x2160p50", "__has__key_blue": False})
render("AudioSelection", au, bg, {"config": audioConfig, "streams": audioStreams})


# ---- 2.0: weather
wd = dict(common)
wd.update({"Title|@Label": "الطقس", "city|": "الإسكندرية", "now_temp|": "21°C", "now_desc|": "صافٍ غالبًا", "now_extra|": "العظمى / الصغرى  24°C / 17°C  •  الرطوبة  60%  •  الرياح  14 km/h", "updated|": "آخر تحديث  18:30"})
days = [("اليوم", "24°C / 17°C", "صافٍ غالبًا", "clear_day"), ("الأربعاء", "23°C / 16°C", "غائم جزئيًا", "partly_day"), ("الخميس", "22°C / 16°C", "أمطار خفيفة\nمطر 40%", "rain"),
	("الجمعة", "21°C / 15°C", "غائم", "cloudy"), ("السبت", "23°C / 16°C", "صافٍ", "clear_day")]
ex = {"now_icon": lambda c, e: drawPix(c, e, pix("weather/clear_day.png"), scale=True)}
for i, (dn, t, ds, ic) in enumerate(days):
	wd.update({"day%d|" % i: dn, "temp%d|" % i: t, "desc%d|" % i: ds})
	ex["icon%d" % i] = (lambda name: (lambda c, e: drawPix(c, e, pix("weather/%s.png" % name), scale=True)))(ic)
render("NileGlassWeather", wd, bg, ex)


# ---- 2.2: film page
fd = dict(common)
fd.update({"title|": "الكابتن فيليبس", "original|": "Captain Phillips", "facts|": "2013   •   134 دقيقة   •   دراما، إثارة", "ratings|": "TMDB  7.5/10     IMDb  7.8/10",
	"story|": "قصة حقيقية عن القبطان ريتشارد فيليبس وسفينة الشحن الأمريكية التي استولى عليها قراصنة صوماليون عام 2009، في أول اختطاف لسفينة أمريكية منذ قرنين. يتحول الصراع إلى مواجهة نفسية بين القبطان وقائد القراصنة.",
	"crew|": "إخراج: بول جرينجراس\nالبلد: الولايات المتحدة\nالجوائز: 6 ترشيحات أوسكار", "showings_title|": "مواعيد العرض على قنواتك (3)"})
names = ["توم هانكس\nريتشارد فيليبس", "برخاد عبدي\nموسى", "باركاد عبد الرحمن\nبلال", "فيصل أحمد\nنجيي", "مهاد علي\nإلمي", "مايكل شانون\nشين"]
fex = {"backdrop": lambda c, e: drawPix(c, e, bg.resize((1920, 1080)), scale=True), "poster": lambda c, e: drawPix(c, e, samplePoster("الكابتن فيليبس", 3), scale=True)}
for i, n in enumerate(names):
	fd["castname%d|" % i] = n
	fex["cast%d" % i] = (lambda k: (lambda c, e: drawPix(c, e, samplePoster(" ", k), scale=True)))(i)


def showRows(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	for i, (a, b) in enumerate([("الثلاثاء 10/11  21:00", "MBC 2"), ("الخميس 12/11  23:30", "MBC Max"), ("السبت 14/11  17:00", "MBC 2")]):
		ry = y + i * 44
		if i == 0:
			canvas.alpha_composite(Image.new("RGBA", (w, 44), col("bgSel")), (x, ry))
		drawText(canvas, ET.Element("x", {"font": "Regular;26", "foregroundColor": "#f2c94c", "valign": "center", "halign": "left"}), a, (x + 14, ry), (250, 44))
		drawText(canvas, ET.Element("x", {"font": "Regular;26", "foregroundColor": "white", "valign": "center", "halign": "left"}), b, (x + 270, ry), (316, 44))


fex["showings"] = showRows
render("NileGlassFilm", fd, bg, fex)


# ---- satfinder
sfd = dict(common)
sfd.update({"Title|@Label": "مكتشف الإشارة", "Frontend|FrontendInfo:SNR": "75 %", "Frontend|FrontendInfo:AGC": "55 %", "Frontend|FrontendInfo:SNRdB": "8.9 dB",
	"Frontend|FrontendInfo:BER": "0", "Frontend|FrontendInfo:LOCK": "1", "pos|": "7.3W", "onid|": "1918", "tsid|": "53700", "description|": "اختار الموالف والقمر والتردد، وحرّك الطبق لحد ما الإشارة تبقى أعلى حاجة.",
	"key_red|": "إلغاء", "key_green|": "بحث", "key_yellow|": "قائمة القنوات", "__static__key_red": True, "__static__key_green": True, "__static__key_yellow": True, "__has__key_blue": False})


def sfConfig(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	rows = [("الموالف", "B: Vuplus DVB-S NIM(45308X FBC)"), ("قمر صناعي", "7.0W Nilesat 201/301 & Eutelsat 7 West A"), ("توليف", "باقة معرفة مسبقًا"), ("التردد", "12418 H 30000 3/4")]
	for i, (a, b) in enumerate(rows):
		ry = y + i * 54
		if i == 0:
			canvas.alpha_composite(Image.new("RGBA", (w, 54), col("bgSel")), (x, ry))
		drawText(canvas, ET.Element("x", {"font": "Regular;30", "foregroundColor": "white", "valign": "center", "halign": "left"}), a, (x + 14, ry), (300, 54))
		drawText(canvas, ET.Element("x", {"font": "Regular;30", "foregroundColor": "white", "valign": "center", "halign": "right"}), b, (x + 300, ry), (w - 320, 54))


render("Satfinder", sfd, bg, {"config": sfConfig})


# ---- 2.4 popups
def barAt(pct, img="ui/signal_xl.png"):
	def f(c, e):
		x, y = xy(e.get("position")); w, h = xy(e.get("size"))
		p = pix(img).resize((w, h))
		c.alpha_composite(p.crop((0, 0, int(w * pct), h)), (x, y))
	return f


psd = dict(common)
psd.update({"Title|@Label": "ضبط الماتور", "SNR|": "SNR:", "AGC|": "AGC:", "BER|": "BER:", "Lock|": "Lock:", "snr_percentage|": "82 %", "agc_percentage|": "71 %", "ber_value|": "0",
	"snr_db|": "11.4 dB", "lock_state|": "Locked", "Frequency|": "Frequency:", "Symbolrate|": "Symbolrate:", "FEC|": "FEC:", "frequency_value|": "11747", "symbolrate_value|": "27500", "fec_value|": "3/4",
	"status_bar|": "Moving east ...", "rotorstatus|": "Positioner: 7.0W  (stored position 3)", "key_info|": "INFO", "key_menu|": "MENU", "__static__key_info": True, "__static__key_menu": True,
	"__has__key_red": False, "__has__key_green": False, "__has__key_yellow": False, "__has__key_blue": False})


def psList(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	rows = [("Tuner", "A"), ("Satellite", "7.0W Nilesat"), ("Frequency", "11747 H"), ("Move east", ""), ("Move west", ""), ("Step east", "1"), ("Step west", "1"), ("Store position", "3"), ("Goto position", "3"), ("Goto 0", ""), ("Limits", "")]
	for i, (a, b) in enumerate(rows):
		ry = y + i * 50
		if i == 3:
			canvas.alpha_composite(Image.new("RGBA", (w, 50), col("bgSel")), (x, ry))
		drawText(canvas, ET.Element("x", {"font": "Regular;28", "foregroundColor": "white", "valign": "center", "halign": "left"}), a, (x + 14, ry), (400, 50))
		drawText(canvas, ET.Element("x", {"font": "Regular;28", "foregroundColor": "white", "valign": "center", "halign": "right"}), b, (x + 400, ry), (w - 420, 50))


render("PositionerSetup", psd, bg, {"list": psList, "snr_bar": barAt(0.82), "agc_bar": barAt(0.71), "ber_bar": barAt(0.02),
	"lock_on": lambda c, e: drawPix(c, e, pix("icons/lock_on.png"))})
render("NileGlassCamBar", dict(common, **{"cam|": "oscam", "info|": "3 إيموهات مثبتة  ·  الشغال: oscam", "state|": "إعادة التشغيل بزر OK",
	"session.CurrentService|NGEcm:State": "تم فك التشفير", "session.CurrentService|NGEcm:Caid": "0x1884  Nagra", "session.CurrentService|NGEcm:Source": "127.0.0.1:12000",
	"session.CurrentService|NGEcm:Protocol": "cccam", "session.CurrentService|NGEcm:Hops": "1", "session.CurrentService|NGEcm:Time": "182 ms",
	"session.CurrentService|PliExtraInfo:CryptoNameCaid": "Nagravision:1884", "session.CurrentService|PliExtraInfo:CryptoBar": "B I N S T V BI BU CO CW ND PV VM"}), bg, {"left": lambda c, e: drawPix(c, e, pix("icons/arrow_left.png")), "right": lambda c, e: drawPix(c, e, pix("icons/arrow_right.png"))})
brd = dict(common)
for w, vals in (("video", ("5634", "1379", "11532", "5513")), ("audio", ("190", "151", "229", "190"))):
	for f, v in zip(("cur", "min", "max", "avg"), vals):
		brd["session.CurrentService|NGBitrate:%s.%s" % (w, f)] = v
render("NileGlassBitrate", brd, bg)
render("PVRState", dict(common, **{"state|": "إيقاف مؤقت", "speed|": "", "eventname|": "Batman v Superman"}), bg, {"statusicon": lambda c, e: drawPix(c, e, pix("icons/pvr_1.png"))})
render("Nab_DoStartCam", dict(common, **{"lab1|": "جاري تشغيل\noscam ...", "Title|@Label": "الإيمو"}), bg, {"connect": lambda c, e: drawPix(c, e, pix("icons/camstart_1.png"))})


rdd = dict(common)
rdd.update({"Title|@Label": "سطور وريدرات الإيمو", "file|": "OSCAM  ·  /etc/tuxbox/config/oscam/oscam.server",
	"details|": "label = server1\nprotocol = cccam\ndevice = s1.example.com,12000\nuser = ali\npassword = ****\ngroup = 1\ncccversion = 2.3.2",
	"hint|": "4 ريدرات   ·   INFO: إظهار الباسورد   ·   MENU: النسخ الاحتياطية",
	"key_red|": "حذف", "key_green|": "إيقاف / تشغيل", "key_yellow|": "تعديل", "key_blue|": "إضافة",
	"__static__key_red": True, "__static__key_green": True, "__static__key_yellow": True, "__static__key_blue": True})


def rdList(canvas, el):
	x, y = xy(el.get("position")); w, h = xy(el.get("size"))
	rows = [("server1", "cccam", "s1.example.com:12000", "ali", "متصل"), ("local_card", "internal", "/dev/sci0", "", "موقوف"),
		("server3", "newcamd", "s3.example.com:15000", "bob", "مقطوع"), ("my", "cccam", "my.server.net:23000", "user1", "بيتصل ...")]
	for i, r in enumerate(rows):
		ry = y + i * 52
		if i == 0:
			canvas.alpha_composite(Image.new("RGBA", (w, 52), col("bgSel")), (x, ry))
		for (cx, cw, f, c, al), t in zip(((14, 400, "Medium;30", "white", "left"), (420, 200, "Regular;26", "#f0c419", "left"), (630, 560, "Regular;26", "white", "left"), (1200, 300, "Regular;26", "#9aa3ae", "left"), (1510, 236, "Regular;26", "#3cc85a", "right")), r):
			drawText(canvas, ET.Element("x", {"font": f, "foregroundColor": "white" if i == 0 else c, "valign": "center", "halign": al}), t, (x + cx, ry), (cw, 52))


render("NileGlassReaders", rdd, bg, {"list": rdList})


MORE_SAMPLE = {
	"session.CurrentService|NGContext:Local": "10:49:27",
	"session.CurrentService|NGContext:Utc": "08:49:27",
	"session.CurrentService|NGContext:Offset": "UTC+2",
	"session.CurrentService|NGContext:Zone": "Africa/Cairo",
	"session.CurrentService|NGContext:Dst": "من غير توقيت صيفي",
	"session.CurrentService|NGContext:Sync": "NTP · pool.ntp.org",
	"session.CurrentService|NGContext:City1": "مكة  11:49",
	"session.CurrentService|NGContext:City2": "دبي  12:49",
	"session.CurrentService|NGContext:City3": "لندن  08:49",
	"session.CurrentService|NGContext:City4": "نيويورك  03:49",
	"session.CurrentService|NGContext:Python": "3.14.0",
	"session.CurrentService|NGContext:Kernel": "4.1.20",
	"session.CurrentService|NGContext:Image": "OpenBh 6.0.012 (Release)",
	"session.CurrentService|NGContext:Model": "Vu+ Ultimo4K",
	"session.CurrentService|NGContext:Flashed": "02/11/2026",
	"session.CurrentService|NGContext:Enigma": "2026-11-01",
	"session.CurrentService|NGContext:Updates": "12 حزمة ليها تحديث",
	"session.CurrentService|NGContext:FeedAge": "من 3 ساعة",
	"session.CurrentService|NGContext:EmuRunning": "oscam",
	"session.CurrentService|NGContext:EmuVersion": "11880-emu",
	"session.CurrentService|NGContext:EmuUptime": "2 س 05 د",
	"session.CurrentService|NGContext:EmuInstalled": "oscam · ncam · oscam_emu",
	"session.CurrentService|NGContext:EmuCount": "3",
	"session.CurrentService|NGContext:BtCount": "1",
	"session.CurrentService|NGContext:BtPaired": "2",
	"session.CurrentService|NGContext:BtAdapter": "hci0 جاهز",
	"session.CurrentService|NGContext:BtConnected": "Vu+ BT Remote",
	"session.CurrentService|NGContext:Ssid": "Saad_5G",
	"session.CurrentService|NGContext:NetRate": "433 Mbit/s",
	"session.CurrentService|NGContext:Signal": "-52 dBm · 82%",
	"ctx|NGHostInfo:Total": "14",
	"ctx|NGHostInfo:Changed": "3",
	"ctx|NGHostInfo:OwnerVersion": "1.6.1",
	"ctx|NGHostInfo:Owner": "ServiceApp",
	"ctx|NGHostInfo:Item": "مشغل IPTV (4097)",
	"ctx|NGHostInfo:Value": "exteplayer3",
	"ctx|NGHostInfo:Default": "gstplayer",
	"ctx|NGHostInfo:Kind": "اختيار من قائمة",
	"ctx|NGHostInfo:Choices": "gstplayer · exteplayer3 · ffplayer",
	"skins|NGSkinInfo:Resolution": "1920x1080",
	"skins|NGSkinInfo:Size": "38 MB",
	"skins|NGSkinInfo:Screens": "241",
	"skins|NGSkinInfo:Name": "NileGlass_FHD",
	"skins|NGSkinInfo:Author": "Saad",
	"skins|NGSkinInfo:Version": "2.8.17",
	"skins|NGSkinInfo:Fonts": "NileGlass-Regular · NileGlass-Medium · Tajawal",
	"skins|NGSkinInfo:Color1": "#0f1722",
	"skins|NGSkinInfo:Color2": "#e8eef4",
	"skins|NGSkinInfo:Color3": "#2f9cff",
	"skins|NGSkinInfo:Color4": "#1a2535",
	"skins|NGSkinInfo:Color5": "#f2c94c",
	"skins|NGSkinInfo:Color6": "#3cc85a",
	"global.CurrentTime|NGHijri:": "4 جمادى الآخرة 1448 هـ",
	"global.CurrentTime|ClockToText:Format:%A %d %B %Y": "الأحد 15 نوفمبر 2026",
	"session.CurrentService|NGEcm:State": "تم فك التشفير", "session.CurrentService|NGEcm:Caid": "0x0500 Viaccess", "session.CurrentService|NGEcm:Reader": "server1", "session.CurrentService|NGEcm:From": "s1.example.com", "session.CurrentService|NGEcm:Time": "312 ms", "session.CurrentService|NGEcm:Protocol": "cccam",

	"session.CurrentService|NGTimerInfo:NextIn": "بعد 2 س 10 د", "session.CurrentService|NGTimerInfo:Count": "5", "session.CurrentService|NGTimerInfo:Conflicts": "مفيش",
	"session.CurrentService|NGTimerInfo:NextName": "الدوري الإسباني: ريال مدريد × برشلونة", "session.CurrentService|NGTimerInfo:NextWhen": "النهارده 22:00",
	"session.CurrentService|NGTimerInfo:NextChannel": "beIN SPORTS 1 HD", "session.CurrentService|NGTimerInfo:NextLength": "120 دقيقة",
	"session.CurrentService|NGTimerInfo:Recording": "", "session.CurrentService|NGTimerInfo:Path": "/media/hdd/movie",
	"session.CurrentService|NGTimerInfo:FreeSpace": "212 GB فاضي", "session.CurrentService|NGTimerInfo:FreeHours": "تكفي حوالي 66 ساعة HD", "session.CurrentService|NGTimerInfo:UsedPercent": "58",
	"ng_sel|NGPluginInfo:PkgSize": "1.9 MB", "ng_sel|NGPluginInfo:PkgState": "جديدة", "ng_sel|NGPluginInfo:Free": "812 MB",
	"ng_sel|NGPluginInfo:PkgName": "enigma2-plugin-extensions-e2iplayer", "ng_sel|NGPluginInfo:PkgDescription": "مشغل محتوى من مواقع كتير على الإنترنت",
	"ng_sel|NGPluginInfo:PkgVersion": "2026.11.02", "ng_sel|NGPluginInfo:Section": "extra", "ng_sel|NGPluginInfo:After": "يفضل حوالي 806 MB",
	"ng_sel|NGPluginInfo:Depends": "هتنزل معاها 2: python3-pycurl, rtmpdump", "ng_sel|NGPluginInfo:PkgMaker": "SSS",
	"Service|MovieInfo:RecordServiceName": "MBC 2", "Service|ServiceName:Name": "فيلم: الممر", "Service|NGMovieInfo:Recorded": "14/11/2026  22:30",
	"Service|NGMovieInfo:Length": "1:52:10", "Service|NGMovieInfo:Size": "3.84 GB", "Service|NGMovieInfo:Quality": "HD تقريبًا · 4.6 Mbit/s",
	"Service|NGMovieInfo:Watched": "وقفت عند 45:10 من 1:52:10", "Service|NGMovieInfo:WatchedPct": "40", "Service|NGMovieInfo:Left": "فاضل 67 د",
	"Service|EventName:FullDescription": "ضابط مصري يقود مجموعة من الجنود في مهمة خلف خطوط العدو خلال حرب الاستنزاف، فيلم حربي مأخوذ عن أحداث حقيقية.",
}

# ---- any other screens, with placeholder rows (NG_EXTRA=Name1,Name2)
for _n in filter(None, os.environ.get("NG_EXTRA", "").split(",")):
	if _n not in screens:
		continue
	_rows = rowsList(["A: Vuplus DVB-S NIM(45308X FBC)", "B: Vuplus DVB-S NIM(45308X FBC)", "C: FBC virtual 1", "D: FBC virtual 2", "E: FBC virtual 3"], ih=60, font="Regular;28")
	_ex = {}
	for _el in expand(screens[_n]):
		if _el.tag == "widget" and (_el.get("render") == "Listbox" or _el.get("name") in ("list", "config", "choosen", "hddlist", "languages", "timerlist", "mainmenu")):
			_ex[_el.get("source") or _el.get("name")] = _rows
	_d = dict(common)
	_d.update(MORE_SAMPLE)
	_d.update({"Title|@Label": _n, "key_red|@Label": "إلغاء", "key_green|@Label": "حفظ", "key_red|": "إلغاء", "key_green|": "حفظ",
		"description|": "وصف العنصر المختار يظهر هنا.", "introduction|": "اضغط OK لتعديل الإعدادات.", "status|": "جاري التحديث…"})
	_render(_n, _d, bg, _ex)
