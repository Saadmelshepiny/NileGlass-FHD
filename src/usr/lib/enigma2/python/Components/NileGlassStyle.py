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
	"icons": "classic"}
TEXT_FINISHES = ("normal", "glossy", "matte")
# infobar status icon sets (variants/icons/<name>)
ICON_STYLES = ("classic", "glass", "badge", "line", "neon", "minimal")
ICON_STYLE_NAMES_AR = {"classic": "كلاسيك (الأصلي)", "glass": "زجاجي لامع", "badge": "شارات بيضا", "line": "أيقونات خطية", "neon": "نيون", "minimal": "نص بسيط"}
LAYOUT_FILES = {("channels", "simple"): "channels_simple.xml", ("sib", "classic"): "sib_classic.xml", ("infobar", "compact"): "infobar_compact.xml"}
# ready-made looks: (accent, transparency, font, text colour)
PRESETS = {
	"classic": ("blue", 20, "ubuntu", "white"),
	"gold": ("gold", 30, "plex", "cream"),
	"cinema": ("red", 10, "notosans", "pure"),
	"sport": ("green", 20, "vazir", "white"),
	"night": ("purple", 10, "almarai", "grey"),
}
PRESET_NAMES_AR = {"classic": "كلاسيك أزرق", "gold": "ذهبي فاخر", "cinema": "سينما", "sport": "رياضة", "night": "ليلي هادي"}
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
	if style["font"] not in FONT_SETS and not style["font"].startswith("skin:"):
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
	for k in ("bold_titles", "outline", "translate", "menu_backdrop", "opaque_screens", "ok_upcoming", "lite"):
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
		changed = transformScreen(scr, ibFactor, outline, rtl, style.get("text_finish") == "glossy" and not lite)
		if lite or not style.get("menu_backdrop", True):
			changed = _dropMenuBackdrops(scr) or changed
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


def buildXml(style, skinDir=SKIN_DIR, language=None):
	accent, dark, line = ACCENTS[style["accent"]]
	t = style["transparency"]
	bgA = _alpha(t * 0.5)        # main panels  (20% -> 10% transparent)
	deepA = _alpha(t * 0.35)
	cardA = _alpha(min(60, t * 0.5 + 9))
	if style.get("opaque_screens") or not t:  # menus and plugin screens fully solid: no TV picture behind them
		bgA = cardA = "00"
	fonts = []
	fontSet = dict(fontSet_(style["font"]))
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
		<color name="background" value="#{bgA}0b0d10"/>
		<color name="bg" value="#{bgA}0b0d10"/>
		<color name="bgDeep" value="#{deepA}060709"/>
		<color name="bgCard" value="#{cardA}161a20"/>
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
""".format(accent=accent, dark=dark, line=line, bgA=bgA, deepA=deepA, cardA=cardA, fonts="\n".join(fonts),
		fg=_finish(TEXT_COLORS[style["text_color"]][0], style), fgDim=_finish(TEXT_COLORS[style["text_color"]][1], style), screens=_transformedScreens(style, skinDir, language))


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
	style = readStyle(confFile)
	copied = _copyTree(os.path.join(skinDir, "variants", "accent", style["accent"]), skinDir)
	copied += _copyTree(os.path.join(skinDir, "variants", "glass", str(style["transparency"] or 10)), skinDir)
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
