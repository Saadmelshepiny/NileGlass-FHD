# -*- coding: utf-8 -*-
# NileGlass FHD - apply the look options (accent colour, transparency, font, text size).
#
# Pure Python, no enigma2 imports, so it can also run from the package
# post-install script:   python3 NileGlassStyle.py
#
# How it works (no cost at runtime):
#   * pre-rendered PNG variants are copied over the active skin pixmaps
#   * colour / font / parameter overrides are written to
#     /etc/enigma2/NileGlass_FHD/nileglass_style.xml, which enigma2 loads
#     automatically after skin.xml (later definitions win)
# A GUI restart applies everything.

import os
import re
import shutil
import xml.etree.ElementTree as ET
from configparser import ConfigParser

SKIN_DIR = "/usr/share/enigma2/NileGlass_FHD"
CONF_FILE = "/etc/enigma2/nileglass.conf"
USER_DIR = "/etc/enigma2/NileGlass_FHD"
USER_XML = os.path.join(USER_DIR, "nileglass_style.xml")

# name -> (accent, darker selection colour, line colour)
ACCENTS = {
	"blue": ("2f9cff", "1f5fa8", "78aadc"),
	"gold": ("e8b428", "8a6a12", "e8c878"),
	"green": ("34be64", "1d6e3a", "78d29a"),
	"red": ("e63c3c", "8c1c22", "f08a8a"),
	"purple": ("965ae6", "56308f", "b996f0"),
	"orange": ("f58228", "93480e", "f5b078"),
	"cyan": ("1ebed2", "0f6e7c", "78d6e4"),
}
ACCENT_NAMES_AR = {"blue": "أزرق", "gold": "ذهبي", "green": "أخضر", "red": "أحمر", "purple": "بنفسجي", "orange": "برتقالي", "cyan": "سماوي"}
TRANSPARENCY = (0, 10, 20, 30, 40, 50)  # 0 = solid, nothing of the picture behind menus
# font set -> {alias: (file, relative scale)}
FONT_SETS = {
	"ubuntu": {"Regular": ("NileGlass-Regular.ttf", 100), "Medium": ("NileGlass-Medium.ttf", 100), "Light": ("NileGlass-Light.ttf", 100),
		"ArabicBold": ("NileGlass-ArabicBold.ttf", 100), "Replacement": ("NileGlass-Arabic.ttf", 108)},
	"tajawal": {"Regular": ("NileGlass-Arabic.ttf", 104), "Medium": ("NileGlass-ArabicBold.ttf", 104), "Light": ("NileGlass-Arabic.ttf", 104),
		"ArabicBold": ("NileGlass-ArabicBold.ttf", 100), "Replacement": ("NileGlass-Arabic.ttf", 104)},
	"almarai": {"Regular": ("NileGlass-Almarai-Regular.ttf", 98), "Medium": ("NileGlass-Almarai-Bold.ttf", 98), "Light": ("NileGlass-Almarai-Light.ttf", 98),
		"ArabicBold": ("NileGlass-Almarai-Bold.ttf", 98), "Replacement": ("NileGlass-Almarai-Regular.ttf", 98)},
	"cairo": {"Regular": ("NileGlass-Cairo-Regular.ttf", 96), "Medium": ("NileGlass-Cairo-Bold.ttf", 96), "Light": ("NileGlass-Cairo-Light.ttf", 96),
		"ArabicBold": ("NileGlass-Cairo-Bold.ttf", 96), "Replacement": ("NileGlass-Cairo-Regular.ttf", 96)},
	"kufi": {"Regular": ("NileGlass-Kufi-Regular.ttf", 90), "Medium": ("NileGlass-Kufi-Bold.ttf", 90), "Light": ("NileGlass-Kufi-Light.ttf", 90),
		"ArabicBold": ("NileGlass-Kufi-Bold.ttf", 90), "Replacement": ("NileGlass-Kufi-Regular.ttf", 90)},
}
for _key, _file, _rel in (("plex", "IBMPlex", 96), ("notosans", "NotoSans", 94), ("vazir", "Vazir", 94), ("amiri", "Amiri", 104), ("messiri", "Messiri", 98)):
	FONT_SETS[_key] = {"Regular": ("NileGlass-%s-Regular.ttf" % _file, _rel), "Medium": ("NileGlass-%s-Bold.ttf" % _file, _rel),
		"Light": ("NileGlass-%s-%s.ttf" % (_file, "Light" if _file not in ("Amiri", "Messiri") else "Regular"), _rel),
		"ArabicBold": ("NileGlass-%s-Bold.ttf" % _file, _rel), "Replacement": ("NileGlass-%s-Regular.ttf" % _file, _rel)}
FONT_NAMES = {"ubuntu": "Ubuntu + Tajawal", "tajawal": "Tajawal", "almarai": "Almarai", "cairo": "Cairo", "kufi": "Noto Kufi",
	"plex": "IBM Plex Arabic", "notosans": "Noto Sans Arabic", "vazir": "Vazirmatn", "amiri": "Amiri", "messiri": "El Messiri"}
FONT_SIZES = (80, 90, 100, 110, 120, 130)
SKINS_DIR = "/usr/share/enigma2"
FONTS_DIR = "/usr/share/fonts"


# ---------------------------------------------------------------- fonts of another skin
# font = "skin:MX_HQ10" uses the fonts (files and scales) of that skin. The
# files are copied once to /usr/share/fonts/NileGlass-From-<skin>-*.ttf, so
# they keep working when the other skin is removed.
_fontScan = {}   # skin.xml path -> ((mtime, size), fonts)
_reFonts = re.compile(r"<fonts\b.*?</fonts>", re.S)


def _skinFonts(path, skinDir, fontsDir):
	"""Fonts of one skin.xml. Only the <fonts> block is parsed (the files
	are megabytes), and the answer is kept until the file changes."""
	try:
		st = os.stat(path)
	except OSError:
		return {}
	sig = (st.st_mtime, st.st_size)
	hit = _fontScan.get(path)
	if hit and hit[0] == sig:
		return hit[1]
	fonts = {}
	try:
		with open(path, "rb") as f:
			data = f.read().decode("utf-8", "replace")
		for block in _reFonts.findall(data):
			for f in ET.fromstring(block).findall("font"):
				fn, alias = f.get("filename"), f.get("name")
				if not fn or not alias:
					continue
				for cand in (fn, os.path.join(skinDir, fn), os.path.join(skinDir, "fonts", fn), os.path.join(fontsDir, fn)):
					if os.path.isfile(cand):
						sc = f.get("scale") or "100"
						fonts[alias] = (cand, int(sc) if sc.isdigit() else 100, bool(f.get("replacement")))
						break
	except Exception:
		fonts = {}
	_fontScan[path] = (sig, fonts)
	return fonts


def otherSkinFonts(skinsDir=SKINS_DIR, fontsDir=FONTS_DIR):
	"""{skin name: {alias: (absolute file, scale, replacement)}} of installed skins."""
	out = {}
	try:
		names = sorted(os.listdir(skinsDir))
	except OSError:
		return out
	for name in names:
		path = os.path.join(skinsDir, name, "skin.xml")
		if name.startswith("NileGlass") or not os.path.isfile(path):
			continue
		fonts = _skinFonts(path, os.path.join(skinsDir, name), fontsDir)
		if "Regular" in fonts:
			out[name] = fonts
	return out


def _copyFont(src, skin, alias, fontsDir=FONTS_DIR):
	dst = os.path.join(fontsDir, "NileGlass-From-%s-%s%s" % (re.sub(r"[^A-Za-z0-9_]", "_", skin), alias, os.path.splitext(src)[1] or ".ttf"))
	try:
		if not os.path.isfile(dst) or os.path.getsize(dst) != os.path.getsize(src):
			shutil.copyfile(src, dst + ".tmp")
			os.replace(dst + ".tmp", dst)
		return os.path.basename(dst)
	except Exception as err:
		print("[NileGlass] font copy failed:", err)
		return None


def fontSet(key, skinsDir=SKINS_DIR, fontsDir=FONTS_DIR, copy=True):
	"""Font set for a key: a built-in one, or "skin:<name>" built from that skin."""
	if key.startswith("dl:"):         # downloaded from the font library (NileGlassFonts.py)
		try:
			from Components.NileGlassFonts import fontSet as dlSet
			return dlSet(key[3:], fontsDir) or FONT_SETS["ubuntu"]
		except Exception:
			return FONT_SETS["ubuntu"]
	if not key.startswith("skin:"):
		return FONT_SETS.get(key) or FONT_SETS["ubuntu"]
	name = key[5:]
	fonts = otherSkinFonts(skinsDir, fontsDir).get(name)
	memo = os.path.join(fontsDir, "NileGlass-From-%s.json" % re.sub(r"[^A-Za-z0-9_]", "_", name))
	if not fonts:  # skin removed: use the copies made earlier
		try:
			import json
			with open(memo, "r") as f:
				saved = {k: tuple(v) for k, v in json.load(f).items()}
			if all(os.path.isfile(os.path.join(fontsDir, v[0])) for v in saved.values()) and "Regular" in saved:
				return saved
		except Exception:
			pass
		return FONT_SETS["ubuntu"]
	files = {}
	for alias in ("Regular", "Bold", "Medium", "Light", "Replacement", "Subtitlefont"):
		if alias in fonts:
			src, scale, _r = fonts[alias]
			fn = _copyFont(src, name, alias, fontsDir) if copy else src
			if fn:
				files[alias] = (fn, scale)
	if "Regular" not in files:
		return FONT_SETS["ubuntu"]
	reg = files["Regular"]
	rep_ = files.get("Replacement") or reg
	result = {"Regular": reg, "Medium": files.get("Medium") or files.get("Bold") or reg, "Light": files.get("Light") or reg,
		"ArabicBold": rep_, "Replacement": rep_}
	if "Subtitlefont" in files:  # used by subtitle plugins
		result["Subtitlefont"] = files["Subtitlefont"]
	if copy:
		try:
			import json
			with open(memo, "w") as f:
				json.dump(result, f)
		except Exception:
			pass
	return result


def fontChoices(skinsDir=SKINS_DIR):
	out = list(FONT_NAMES.items())
	try:
		from Components.NileGlassFonts import installed
		out += [("dl:" + k, name) for k, name in installed()]
	except Exception:
		pass
	for name in otherSkinFonts(skinsDir):
		out.append(("skin:" + name, "خط سكين %s" % name))
	return out
INFOBAR_SIZES = (90, 100, 110, 120)
# text colour -> (main text, dimmed text)
TEXT_COLORS = {"white": ("eef1f4", "9aa3ae"), "pure": ("ffffff", "b4bcc6"), "cream": ("f3ead8", "b5ab98"), "grey": ("c9ced6", "8d949e")}
TEXT_COLOR_NAMES_AR = {"white": "أبيض", "pure": "أبيض ناصع", "cream": "كريمي", "grey": "رمادي فاتح"}
DIRECTIONS = ("auto", "rtl", "ltr")
DEFAULTS = {"accent": "blue", "transparency": "20", "font": "ubuntu", "font_size": "100", "infobar": "full",
	"infobar_size": "100", "text_color": "white", "bold_titles": "1", "outline": "0", "direction": "auto", "translate": "1",
	"channels": "posters", "sib": "cinema", "menu_backdrop": "1", "opaque_screens": "0", "text_finish": "normal", "ok_upcoming": "1", "lite": "0",
	"icons": "classic", "ib_color": "graphite", "menus": "popup", "square_corners": "0", "look": "classic",
	"title_font": "same", "list_size": "100", "epg_size": "100", "desc_size": "100", "card_size": "100", "season": "0"}
AREA_SIZES = (80, 90, 100, 110, 120, 130)
AREA_KEYS = ("list_size", "epg_size", "desc_size", "card_size")
TEXT_FINISHES = ("normal", "glossy", "matte")
# infobar status icon sets (variants/icons/<name>)
ICON_STYLES = ("classic", "glass", "badge", "line", "neon", "minimal")
ICON_STYLE_NAMES_AR = {"classic": "كلاسيك (الأصلي)", "glass": "زجاجي لامع", "badge": "شارات بيضا", "line": "أيقونات خطية", "neon": "نيون", "minimal": "نص بسيط"}
# infobar background colours (variants/ibcolor/<name>/<transparency>/ui)
IB_COLORS = ("graphite", "black", "navy", "midnight", "royal", "petrol", "teal", "emerald", "olive",
	"purple", "plum", "burgundy", "red", "brown", "gold", "silver")
IB_COLOR_NAMES_AR = {"graphite": "رمادي غامق (الأصلي)", "black": "أسود", "navy": "كحلي", "midnight": "أزرق ليلي",
	"royal": "أزرق ملكي", "petrol": "بترولي", "teal": "تركواز غامق", "emerald": "زمردي", "olive": "زيتوني",
	"purple": "بنفسجي", "plum": "برقوقي", "burgundy": "عنابي", "red": "أحمر قاني", "brown": "بني",
	"gold": "ذهبي غامق", "silver": "فضي"}
# looks: panel colours (main, deep, card) and the outline of panels / cards (None: no outline)
LOOKS = {"classic": ("0f1722", "0b1119", "1a2535", None), "carbon": ("080d14", "060a10", "0b121b", "2c3e50"),
	"oled": ("000000", "000000", "0c0c0e", None), "sand": ("1c1610", "14100b", "2a2118", None), "emerald": ("0b1a16", "07120f", "142a24", None),
	"slate": ("17191d", "101215", "23272e", None), "royal": ("120f24", "0c0a19", "1e1a38", None)}
LOOK_NAMES_AR = {"classic": "كلاسيك (الأصلي)", "carbon": "كربون (داكن بحدود رفيعة)", "oled": "أسود كامل (OLED)", "sand": "رملي دافي",
	"emerald": "زمردي", "slate": "رمادي فحمي", "royal": "بنفسجي ملكي"}
LAYOUT_FILES = {("channels", "simple"): "channels_simple.xml", ("sib", "classic"): "sib_classic.xml", ("infobar", "compact"): "infobar_compact.xml", ("menus", "popup"): "menus_popup.xml"}
# ready-made looks: (accent, transparency, font, text colour)
PRESETS = {
	"classic": ("blue", 20, "ubuntu", "white"),
	"oled": ("cyan", 0, "plex", "pure"),
	"desert": ("gold", 20, "cairo", "cream"),
	"emerald": ("green", 20, "almarai", "white"),
	"gold": ("gold", 30, "plex", "cream"),
	"cinema": ("red", 10, "notosans", "pure"),
	"sport": ("green", 20, "vazir", "white"),
	"night": ("purple", 10, "almarai", "grey"),
}
PRESET_LOOKS = {"oled": "oled", "desert": "sand", "emerald": "emerald", "night": "royal"}
PRESET_NAMES_AR = {"oled": "أسود OLED", "desert": "صحراوي ذهبي", "emerald": "زمردي هادي", "classic": "كلاسيك أزرق", "gold": "ذهبي فاخر", "cinema": "سينما", "sport": "رياضة", "night": "ليلي هادي"}
INFOBAR_LAYOUTS = ("full", "compact")


def readStyle(confFile=CONF_FILE):
	cp = ConfigParser()
	try:
		cp.read(confFile, encoding="utf-8")
	except Exception:
		pass
	style = dict(DEFAULTS)
	if cp.has_section("style"):
		for k in DEFAULTS:
			v = cp.get("style", k, fallback="").strip()
			if v:
				style[k] = v
	if style["accent"] not in ACCENTS:
		style["accent"] = DEFAULTS["accent"]
	try:
		t = int(style["transparency"])
		style["transparency"] = min(TRANSPARENCY, key=lambda x: abs(x - t))
	except ValueError:
		style["transparency"] = 20
	if style["infobar"] not in INFOBAR_LAYOUTS:
		style["infobar"] = "full"
	if style["font"] not in FONT_SETS and not style["font"].startswith(("skin:", "dl:")):
		style["font"] = DEFAULTS["font"]
	try:
		style["font_size"] = max(80, min(130, int(style["font_size"])))
	except ValueError:
		style["font_size"] = 100
	try:
		style["infobar_size"] = max(80, min(130, int(style["infobar_size"])))
	except ValueError:
		style["infobar_size"] = 100
	if style["text_color"] not in TEXT_COLORS:
		style["text_color"] = "white"
	if style["look"] not in LOOKS:
		style["look"] = "classic"
	for k in AREA_KEYS:
		try:
			style[k] = max(80, min(130, int(style[k])))
		except (TypeError, ValueError):
			style[k] = 100
	if style["title_font"] != "same" and style["title_font"] not in FONT_SETS and not style["title_font"].startswith(("skin:", "dl:")):
		style["title_font"] = "same"
	if style["font"].startswith("dl:"):
		try:
			from Components.NileGlassFonts import fontSet as dlSet
			if not dlSet(style["font"][3:]):
				style["font"] = DEFAULTS["font"]
		except Exception:
			style["font"] = DEFAULTS["font"]
	if style["menus"] not in ("popup", "full"):
		style["menus"] = "popup"
	if style["ib_color"] not in IB_COLORS:
		style["ib_color"] = "graphite"
	if style["direction"] not in DIRECTIONS:
		style["direction"] = "auto"
	if style["channels"] not in ("posters", "simple"):
		style["channels"] = "posters"
	if style["sib"] not in ("cinema", "classic"):
		style["sib"] = "cinema"
	if style["text_finish"] not in TEXT_FINISHES:
		style["text_finish"] = "normal"
	if style["icons"] not in ICON_STYLES:
		style["icons"] = "classic"
	for k in ("bold_titles", "outline", "translate", "menu_backdrop", "opaque_screens", "ok_upcoming", "lite", "square_corners", "season"):
		style[k] = str(style[k]).strip().lower() in ("1", "yes", "true", "on")
	return style


def osdLanguage(settings="/etc/enigma2/settings"):
	try:
		with open(settings, "r", encoding="utf-8", errors="replace") as f:
			for line in f:
				if line.startswith("config.osd.language="):
					return line.split("=", 1)[1].strip()
	except Exception:
		pass
	return "ar_AE"  # NileGlass is made for Arabic users


def isRtl(style, language=None):
	if style.get("direction") == "rtl":
		return True
	if style.get("direction") == "ltr":
		return False
	return (language or osdLanguage()).lower().startswith(("ar", "fa", "he", "ur"))


def _copyTree(src, dst):
	if not os.path.isdir(src):
		return 0
	n = 0
	for root, dirs, files in os.walk(src):
		for f in files:
			s = os.path.join(root, f)
			d = os.path.join(dst, os.path.relpath(s, src))
			os.makedirs(os.path.dirname(d), exist_ok=True)
			shutil.copyfile(s, d + ".tmp")
			os.replace(d + ".tmp", d)
			n += 1
	return n


def _alpha(percent):
	return "%02x" % max(0, min(255, int(round(percent * 2.55))))


def _layoutScreens(style, skinDir):
	"""<screen> blocks of the chosen layout variants (they override skin.xml)."""
	if style.get("infobar") != "compact":
		return ""
	try:
		with open(os.path.join(skinDir, "layouts", "infobar_compact.xml"), "r", encoding="utf-8") as f:
			text = f.read()
		a, b = text.index("<screen"), text.rindex("</screen>") + len("</screen>")
		return "\t" + text[a:b] + "\n"
	except Exception:
		return ""


# ------------------------------------------------------------------ screen transforms
# Copies of skin screens with changed font sizes / text outline / text direction
# are written into the style file, where they replace the originals.
INFOBAR_SCREENS = ("InfoBar", "SecondInfoBar", "SecondInfoBarSimple", "MoviePlayer")
NO_DIRECTION = set(INFOBAR_SCREENS) | {"Volume", "Mute", "Dish", "NumberZap", "NumberZapPicon", "ChannelSelection", "SlimChannelSelection",
	"NG_Frame", "NG_Buttons", "NG_Frame_Small", "NileGlassTonight"}
TEXT_RENDERS = ("Label", "NGEventList", "NGEventInfo", "ChannelNumber", "FixedLabel", "VRunningText", "RunningText")
_reEntry = re.compile(r"(MultiContentEntry\w+)\(([^()]*(?:\([^()]*\)[^()]*)*)\)")
_rePos = re.compile(r"pos\s*=\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)")
_reSize = re.compile(r"size\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)")


def _scaleFont(value, factor):
	m = re.match(r"^\s*([^;]+);\s*(\d+)\s*$", value or "")
	if not m:
		return value
	return "%s;%d" % (m.group(1), max(10, int(round(int(m.group(2)) * factor))))


def _isTextWidget(el):
	if el.tag == "eLabel":
		return bool(el.get("text"))
	if el.tag != "widget":
		return False
	r = el.get("render")
	if r:
		return r in TEXT_RENDERS
	return bool(el.get("font")) and not el.get("itemHeight") and el.get("name") not in ("list", "config", "menu", "entries", "filelist")


def _flipTemplate(text, width, rtl):
	"""Text entries aligned to the reading side; icons moved to the side the
	reading starts from (geometry mirrored inside the list width)."""
	entries = [(m, m.group(1), m.group(2)) for m in _reEntry.finditer(text)]
	texts = [(_rePos.search(a), _reSize.search(a)) for m, k, a in entries if k == "MultiContentEntryText"]
	pixes = [(_rePos.search(a), _reSize.search(a)) for m, k, a in entries if k.startswith("MultiContentEntryPixmap")]
	mirror = False
	if texts and pixes and all(p and s for p, s in texts + pixes):
		tx = min(int(p.group(1)) for p, s in texts)
		px = min(int(p.group(1)) for p, s in pixes)
		mirror = (px < tx) if rtl else (px > tx)

	def fix(m):
		kind, args = m.group(1), m.group(2)
		if mirror:
			p, sz = _rePos.search(args), _reSize.search(args)
			if p and sz:
				x = width - int(p.group(1)) - int(sz.group(1))
				args = args[:p.start()] + "pos=(%d, %s)" % (max(0, x), p.group(2)) + args[p.end():]
		if kind == "MultiContentEntryText" and "RT_HALIGN_CENTER" not in args and "RT_HALIGN_BLOCK" not in args:
			want = "RT_HALIGN_RIGHT" if rtl else "RT_HALIGN_LEFT"
			args = re.sub(r"RT_HALIGN_(LEFT|RIGHT|BIDI)", want, args)
			if want not in args:
				if re.search(r"flags\s*=", args):
					args = re.sub(r"flags\s*=\s*", "flags=%s|" % want, args, count=1)
				else:
					args += ", flags=%s|RT_VALIGN_CENTER" % want
		elif kind.startswith("MultiContentEntryPixmap") and mirror:
			args = args.replace("BT_HALIGN_LEFT", "BT_HALIGN_X").replace("BT_HALIGN_RIGHT", "BT_HALIGN_LEFT").replace("BT_HALIGN_X", "BT_HALIGN_RIGHT")
		return "%s(%s)" % (kind, args)
	return _reEntry.sub(fix, text)


def _mix(hex6, target, amount):
	c = [int(hex6[i:i + 2], 16) for i in (0, 2, 4)]
	return "".join("%02x" % int(round(v + (target - v) * amount)) for v in c)


def transformScreen(scr, ibFactor=1.0, outline=False, rtl=None, shadow=False):
	"""Change a copied <screen> element in place. Returns True if anything changed."""
	changed = False
	name = scr.get("name", "")
	isInfobar = name in INFOBAR_SCREENS
	for el in scr.iter():
		if isInfobar:
			if ibFactor != 1.0 and el.get("font"):
				el.set("font", _scaleFont(el.get("font"), ibFactor))
				changed = True
			if outline and _isTextWidget(el) and not el.get("borderWidth"):
				el.set("borderWidth", "2")
				el.set("borderColor", "#000000")
				changed = True
		if shadow and _isTextWidget(el) and not el.get("shadowColor") and not el.get("borderWidth"):
			el.set("shadowColor", "#50000000")  # "glossy" text: a soft drop shadow gives depth
			el.set("shadowOffset", "2,2")
			changed = True
		if rtl is None or name in NO_DIRECTION:
			continue
		if el.tag == "convert" and el.get("type") == "TemplatedMultiContent" and el.text:
			parent = next((w for w in scr.iter("widget") if el in list(w)), None)
			try:
				width = int((parent.get("size") or "0,0").split(",")[0]) if parent is not None else 0
			except ValueError:
				width = 0
			if width:
				new = _flipTemplate(el.text, width, rtl)
				if new != el.text:
					el.text = new
					changed = True
		elif _isTextWidget(el):
			try:
				w = int((el.get("size") or "0,0").split(",")[0])
			except ValueError:
				w = 0
			cur = el.get("halign")
			if w >= 500 and cur in (None, "left", "right"):  # wide text areas only: label/value rows keep their layout
				want = "right" if rtl else "left"
				if cur != want:
					el.set("halign", want)
					changed = True
	return changed


def _layoutElements(style, skinDir):
	"""{screen name: element} of the layout variants chosen in the style."""
	out = {}
	for (key, value), fname in LAYOUT_FILES.items():
		if style.get(key) != value:
			continue
		try:
			root = ET.parse(os.path.join(skinDir, "layouts", fname)).getroot()
			scrs = [root] if root.tag == "screen" else root.findall("screen")
			for scr in scrs:
				out[scr.get("name")] = scr
		except Exception as err:
			print("[NileGlass] layout %s: %s" % (fname, err))
	return out


def _dropMenuBackdrops(scr):
	"""Remove the full-screen event backdrop (option 'menu_backdrop' off)."""
	changed = False
	for parent in list(scr.iter()):
		for el in list(parent):
			if el.tag == "widget" and el.get("render") == "NGPoster" and el.get("kind") == "backdrop" and el.get("size") == "1920,1080":
				parent.remove(el)
				changed = True
	return changed


def _dropCorners(scr):
	"""Square panels and cards: rounded corners are drawn in software on every
	repaint, so without them the screens come up faster."""
	changed = False
	for el in scr.iter():
		if el.attrib.pop("cornerRadius", None) is not None:
			changed = True
	return changed


PANEL_COLORS = ("bg", "background", "bgCard", "bgDeep")


def _outlinePanels(scr):
	"""Carbon look: the rounded panels and cards get a thin outline (drawn by
	the widget itself together with its background - no extra widget)."""
	changed = False
	for el in scr.iter():
		if not el.get("cornerRadius") or el.get("backgroundColor") not in PANEL_COLORS or el.get("text") or el.get("widgetBorderWidth"):
			continue
		if el.tag != "eLabel" and el.get("render") != "FixedLabel":
			continue
		try:
			w, h = (int(v) for v in el.get("size", "").split(","))
		except ValueError:
			continue
		if w >= 120 and h >= 44:
			el.set("widgetBorderWidth", "1")
			el.set("widgetBorderColor", "panelLine")
			changed = True
	return changed


_reEpgScreen = re.compile(r"epg|eventview|film|tonight|upcoming|similar", re.I)
_reGFont = re.compile(r'(gFont\(\s*"[^"]+"\s*,\s*)(\d+)(\s*\))')
_reItemH = re.compile(r'("itemHeight"\s*:\s*)(\d+)')
DESC_CONVERTERS = ("ExtendedDescription", "FullDescription", "ShortDescription", "Description")
LIST_NAMES = ("list", "config", "menu", "entries", "filelist", "menulist", "languages", "list_left", "list_right")


def _areaOf(scr):
	name = scr.get("name", "")
	if name.startswith(("NileGlassDash_", "NG_Dash_")):
		return "card"
	if _reEpgScreen.search(name):
		return "epg"
	return None


def _scaleAreas(scr, style):
	"""Text sizes per part of the skin: lists, EPG, descriptions, cards (beside
	the global size and the infobar size).  Lists grow their rows with the text."""
	f = dict((k, style.get(k, 100) / 100.0) for k in AREA_KEYS)
	if all(v == 1.0 for v in f.values()):
		return False
	changed = False
	area = _areaOf(scr)
	whole = f["card_size"] if area == "card" else f["epg_size"] if area == "epg" else 1.0
	for el in scr.iter("widget"):
		conv = " ".join("%s:%s" % (c.get("type"), (c.text or "").strip()) for c in el.findall("convert"))
		isList = el.get("itemHeight") or el.get("name") in LIST_NAMES or "TemplatedMultiContent" in conv
		factor = whole
		if isList and scr.get("name") not in INFOBAR_SCREENS:
			factor *= f["list_size"]
		elif any(d in conv for d in DESC_CONVERTERS) or el.get("name") in ("description", "epg_description", "FullDescription", "text") or el.get("render") in ("RunningText", "VRunningText"):
			factor *= f["desc_size"]
		if abs(factor - 1.0) < 0.01:
			continue
		if el.get("font"):
			el.set("font", _scaleFont(el.get("font"), factor))
			changed = True
		if isList:
			grow = max(1.0, factor)     # rows grow with bigger text, never shrink under their pictures
			if el.get("itemHeight"):
				el.set("itemHeight", str(int(round(int(el.get("itemHeight")) * grow))))
			for c in el.findall("convert"):
				if c.get("type") == "TemplatedMultiContent" and c.text:
					c.text = _reGFont.sub(lambda m: "%s%d%s" % (m.group(1), max(10, int(round(int(m.group(2)) * factor))), m.group(3)), c.text)
					c.text = _reItemH.sub(lambda m: "%s%d" % (m.group(1), int(round(int(m.group(2)) * grow))), c.text)
			changed = True
	if whole != 1.0:
		for el in scr.iter("eLabel"):
			if el.get("font"):
				el.set("font", _scaleFont(el.get("font"), whole))
				changed = True
	return changed


def _transformedScreens(style, skinDir, language=None):
	ibFactor = style.get("infobar_size", 100) / 100.0
	outline = bool(style.get("outline"))
	rtl = isRtl(style, language)
	try:
		root = ET.parse(os.path.join(skinDir, "skin.xml")).getroot()
	except Exception as err:
		print("[NileGlass] style: cannot read skin.xml:", err)
		return ""
	layouts = _layoutElements(style, skinDir)
	out = []
	done = set()
	for scr in root.findall("screen"):
		name = scr.get("name")
		replaced = name in layouts
		if replaced:
			scr = layouts[name]
		done.add(name)
		lite = bool(style.get("lite"))
		square = lite or bool(style.get("square_corners"))
		outlined = LOOKS[style.get("look", "classic")][3] is not None
		changed = transformScreen(scr, ibFactor, outline, rtl, style.get("text_finish") == "glossy" and not lite)
		changed = _scaleAreas(scr, style) or changed
		if lite or not style.get("menu_backdrop", True):
			changed = _dropMenuBackdrops(scr) or changed
		if outlined:
			changed = _outlinePanels(scr) or changed
		if square:
			changed = _dropCorners(scr) or changed
		if lite:  # lite mode: no rows of posters (the heaviest part while zapping)
			for parent in list(scr.iter()):
				for el in list(parent):
					if el.tag == "widget" and el.get("render") == "NGPoster" and el.get("eventIndex"):
						parent.remove(el)
						changed = True
		if changed or replaced:
			out.append("\t" + ET.tostring(scr, encoding="unicode").strip())
	for name, scr in layouts.items():  # layout screens that skin.xml does not have
		if name not in done:
			transformScreen(scr, ibFactor, outline, rtl, style.get("text_finish") == "glossy")
			_scaleAreas(scr, style)
			if LOOKS[style.get("look", "classic")][3] is not None:
				_outlinePanels(scr)
			if style.get("lite") or style.get("square_corners"):
				_dropCorners(scr)
			out.append("\t" + ET.tostring(scr, encoding="unicode").strip())
	return "\n".join(out) + ("\n" if out else "")


fontSet_ = fontSet


def _finish(hex6, style):
	f = style.get("text_finish", "normal")
	if f == "glossy":
		return _mix(hex6, 255, 0.45)  # brighter
	if f == "matte":
		return _mix(hex6, 0x70, 0.22)  # softer, less contrast
	return hex6


def _toHijri(y, m, d):
	"""Gregorian -> (year, month, day), civil Islamic calendar (same as Converter/NGHijri.py)"""
	a = int((m - 14) / 12)
	jd = (1461 * (y + 4800 + a)) // 4 + (367 * (m - 2 - 12 * a)) // 12 - (3 * ((y + 4900 + a) // 100)) // 4 + d - 32075
	l = jd - 1948440 + 10632
	n = (l - 1) // 10631
	l = l - 10631 * n + 354
	j = ((10985 - l) // 5316) * ((50 * l) // 17719) + (l // 5670) * ((43 * l) // 15238)
	l = l - ((30 - j) // 15) * ((17719 * j) // 50) - (j // 16) * ((15238 * j) // 43) + 29
	month = (24 * l) // 709
	day = l - (709 * month) // 24
	return 30 * n + j - 30, month, day


def season(now=None):
	"""'ramadan' / 'eid' by the Hijri date, else None"""
	import time as _t
	lt = _t.localtime(now)
	y, m, d = _toHijri(lt.tm_year, lt.tm_mon, lt.tm_mday)
	if m == 9:
		return "ramadan"
	if (m == 10 and d <= 3) or (m == 12 and 10 <= d <= 13):
		return "eid"
	return None


def seasonal(style, now=None):
	"""the style with the season's look, when the season option is on"""
	if not style.get("season"):
		return style
	s = season(now)
	if s == "ramadan":
		return dict(style, accent="gold", look="royal" if style.get("look") == "oled" else "sand")
	if s == "eid":
		return dict(style, accent="green", look="emerald")
	return style


def buildXml(style, skinDir=SKIN_DIR, language=None):
	style = seasonal(style)
	accent, dark, line = ACCENTS[style["accent"]]
	t = style["transparency"]
	bgA = _alpha(t * 0.5)        # main panels  (20% -> 10% transparent)
	deepA = _alpha(t * 0.35)
	cardA = _alpha(min(60, t * 0.5 + 9))
	if style.get("opaque_screens") or style.get("lite") or not t:  # menus and plugin screens fully solid: no TV picture behind them (lite mode: nothing to blend)
		bgA = cardA = "00"
	screens = _transformedScreens(style, skinDir, language)
	cBg, cDeep, cCard, cLine = LOOKS[style.get("look", "classic")]
	if cLine:      # lists without a selection picture: the same faint accent tint as the pictures of this look
		dark = "".join("%02x" % int(int(dark[i:i + 2], 16) * 0.5 + int(cBg[i:i + 2], 16) * 0.5) for i in (0, 2, 4))
	if cLine and cardA != "00":      # outlined cards: as solid as the panels, the outline sets them apart
		cardA = bgA
	fonts = []
	fontSet = dict(fontSet_(style["font"]))
	if style.get("title_font", "same") != "same":      # titles in another font than the text
		titles = fontSet_(style["title_font"])
		for alias in ("Medium", "ArabicBold"):
			if alias in titles:
				fontSet[alias] = titles[alias]
	if not style.get("bold_titles", True):
		fontSet["Medium"] = fontSet["Regular"]
	for alias, (fname, rel) in fontSet.items():
		scale = int(round(rel * style["font_size"] / 100.0))
		extra = ' replacement="1"' if alias == "Replacement" else ""
		fonts.append('\t\t<font filename="%s" name="%s" scale="%d"%s/>' % (fname, alias, scale, extra))
	return """<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated by the NileGlass FHD settings screen. Do not edit - use Plugins > NileGlass FHD. -->
<skin>
	<colors>
		<color name="accent" value="#{accent}"/>
		<color name="bgSel" value="#{dark}"/>
		<color name="bgSelNow" value="#{dark}"/>
		<color name="lineAccent" value="#58{line}"/>
		<color name="posterBorder" value="#50{line}"/>
		<color name="background" value="#{bgA}{cBg}"/>
		<color name="bg" value="#{bgA}{cBg}"/>
		<color name="bgDeep" value="#{deepA}{cDeep}"/>
		<color name="bgCard" value="#{cardA}{cCard}"/>
		<color name="panelLine" value="#00{cLine}"/>
		<color name="fg" value="#00{fg}"/>
		<color name="foreground" value="#00{fg}"/>
		<color name="fgDim" value="#00{fgDim}"/>
	</colors>
	<fonts>
{fonts}
	</fonts>
	<parameters>
		<parameter name="FrontendInfoColors" value="#00{accent},#00f2c94c,#00d6dbe1"/>
	</parameters>
{screens}</skin>
""".format(accent=accent, dark=dark, line=line, bgA=bgA, deepA=deepA, cardA=cardA, cBg=cBg, cDeep=cDeep, cCard=cCard, cLine=cLine or "28364a", fonts="\n".join(fonts),
		fg=_finish(TEXT_COLORS[style["text_color"]][0], style), fgDim=_finish(TEXT_COLORS[style["text_color"]][1], style), screens=screens)


def _xmlProblems(xml, skinDir=SKIN_DIR, fontsDir=FONTS_DIR):
	"""Things in a style file that would stop enigma2 from starting."""
	try:
		root = ET.fromstring(xml)
	except Exception as err:
		return ["xml: %s" % err]
	out = []
	for f in root.iter("font"):
		fn = f.get("filename") or ""
		if not any(os.path.isfile(p) for p in (fn, os.path.join(fontsDir, fn), os.path.join(skinDir, fn), os.path.join(skinDir, "fonts", fn))):
			out.append("font file missing: %s" % fn)
	return out


def safeXml(style, skinDir=SKIN_DIR, language=None):
	"""Safe mode: never write a style file that could keep the GUI from starting.
	Problems -> the same style with the default font, then the plain default."""
	xml = buildXml(style, skinDir, language)
	problems = _xmlProblems(xml, skinDir)
	if problems:
		print("[NileGlass] safe mode:", "; ".join(problems))
		style = dict(style, font="ubuntu")
		xml = buildXml(style, skinDir, language)
		if _xmlProblems(xml, skinDir):
			style = readStyle("/nonexistent")
			xml = buildXml(style, skinDir, language)
	return xml


def checkInstalled(userXml=USER_XML, skinDir=SKIN_DIR):
	"""At start-up: is the active style file still safe (fonts deleted ...)?
	Returns a problem text, '' when fine. The file is repaired for the next start."""
	try:
		with open(userXml, "r", encoding="utf-8") as f:
			problems = _xmlProblems(f.read(), skinDir)
	except OSError:
		return ""
	if problems:
		try:
			apply(skinDir=skinDir, userXml=userXml)
		except Exception as err:
			try:
				os.remove(userXml)  # last resort: the plain skin always starts
			except OSError:
				pass
			print("[NileGlass] safe mode removed the style file:", err)
		return "; ".join(problems)
	return ""


def apply(confFile=CONF_FILE, skinDir=SKIN_DIR, userXml=USER_XML):
	"""Apply the style from the config file. Returns a short report string."""
	style = seasonal(readStyle(confFile))
	copied = _copyTree(os.path.join(skinDir, "variants", "accent", style["accent"]), skinDir)
	copied += _copyTree(os.path.join(skinDir, "variants", "glass", str(style["transparency"] or 10)), skinDir)
	# the look's own pictures (selection bars, progress bars, infobar panels, rings); "classic" puts the rings back
	look = os.path.join(skinDir, "variants", "look", style["look"])
	if not os.path.isdir(look):      # looks that are only colours use the classic pictures
		look = os.path.join(skinDir, "variants", "look", "classic")
	copied += _copyTree(os.path.join(look, "accent", style["accent"]), skinDir)
	copied += _copyTree(os.path.join(look, "glass", str(style["transparency"] or 10)), skinDir)
	copied += _copyTree(os.path.join(look, "ui"), os.path.join(skinDir, "ui"))
	if style["ib_color"] != "graphite":
		copied += _copyTree(os.path.join(skinDir, "variants", "ibcolor", style["ib_color"], str(style["transparency"] or 10)), skinDir)
	icons = os.path.join(skinDir, "variants", "icons", style["icons"])
	if os.path.isdir(icons):
		copied += _copyTree(os.path.join(icons, "icons"), os.path.join(skinDir, "icons"))
	os.makedirs(os.path.dirname(userXml), exist_ok=True)
	xml = safeXml(style, skinDir)
	tmp = userXml + ".tmp"
	with open(tmp, "w", encoding="utf-8") as f:
		f.write(xml)
	os.replace(tmp, userXml)
	return "accent=%s transparency=%s font=%s size=%s infobar=%s/%s colour=%s rtl=%s (%d pixmaps)" % (style["accent"], style["transparency"], style["font"], style["font_size"],
		style["infobar"], style["infobar_size"], style["text_color"], isRtl(style), copied)


if __name__ == "__main__":
	try:
		print("[NileGlass] style applied:", apply())
	except Exception as err:
		print("[NileGlass] style not applied:", err)
