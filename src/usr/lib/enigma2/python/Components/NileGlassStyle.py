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
import shutil
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
TRANSPARENCY = (10, 20, 30, 40, 50)
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
FONT_NAMES = {"ubuntu": "Ubuntu + Tajawal", "tajawal": "Tajawal", "almarai": "Almarai", "cairo": "Cairo", "kufi": "Noto Kufi"}
FONT_SIZES = (90, 100, 110, 120)
DEFAULTS = {"accent": "blue", "transparency": "20", "font": "ubuntu", "font_size": "100", "infobar": "full"}
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
	if style["font"] not in FONT_SETS:
		style["font"] = DEFAULTS["font"]
	try:
		style["font_size"] = max(80, min(130, int(style["font_size"])))
	except ValueError:
		style["font_size"] = 100
	return style


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


def buildXml(style, skinDir=SKIN_DIR):
	accent, dark, line = ACCENTS[style["accent"]]
	t = style["transparency"]
	bgA = _alpha(t * 0.5)        # main panels  (20% -> 10% transparent)
	deepA = _alpha(t * 0.35)
	cardA = _alpha(min(60, t * 0.5 + 9))
	fonts = []
	for alias, (fname, rel) in FONT_SETS[style["font"]].items():
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
	</colors>
	<fonts>
{fonts}
	</fonts>
	<parameters>
		<parameter name="FrontendInfoColors" value="#00{accent},#00f2c94c,#00d6dbe1"/>
	</parameters>
{screens}</skin>
""".format(accent=accent, dark=dark, line=line, bgA=bgA, deepA=deepA, cardA=cardA, fonts="\n".join(fonts), screens=_layoutScreens(style, skinDir))


def apply(confFile=CONF_FILE, skinDir=SKIN_DIR, userXml=USER_XML):
	"""Apply the style from the config file. Returns a short report string."""
	style = readStyle(confFile)
	copied = _copyTree(os.path.join(skinDir, "variants", "accent", style["accent"]), skinDir)
	copied += _copyTree(os.path.join(skinDir, "variants", "glass", str(style["transparency"])), skinDir)
	os.makedirs(os.path.dirname(userXml), exist_ok=True)
	tmp = userXml + ".tmp"
	with open(tmp, "w", encoding="utf-8") as f:
		f.write(buildXml(style, skinDir))
	os.replace(tmp, userXml)
	return "accent=%s transparency=%s font=%s size=%s infobar=%s (%d pixmaps)" % (style["accent"], style["transparency"], style["font"], style["font_size"], style["infobar"], copied)


if __name__ == "__main__":
	try:
		print("[NileGlass] style applied:", apply())
	except Exception as err:
		print("[NileGlass] style not applied:", err)
