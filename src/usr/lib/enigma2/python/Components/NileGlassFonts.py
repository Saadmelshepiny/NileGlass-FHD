# -*- coding: utf-8 -*-
# NileGlass FHD - the font library: more Arabic fonts, downloaded only when you
# pick one (the package stays small).  All are free fonts (SIL Open Font
# License) from the Google Fonts collection on GitHub (jsDelivr as a mirror).
# A downloaded font is checked (a real font file) before it can be chosen;
# a failed download changes nothing.

import os

FONTS_DIR = "/usr/share/fonts"
SOURCES = ("https://raw.githubusercontent.com/google/fonts/main/ofl/", "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/")

# key: (shown name, size scale, regular file, bold file or None)  - files under ofl/
CATALOG = {
	"harmattan": ("Harmattan", 108, "harmattan/Harmattan-Regular.ttf", "harmattan/Harmattan-Bold.ttf"),
	"lateef": ("Lateef", 122, "lateef/Lateef-Regular.ttf", "lateef/Lateef-Bold.ttf"),
	"scheherazade": ("Scheherazade New", 104, "scheherazadenew/ScheherazadeNew-Regular.ttf", "scheherazadenew/ScheherazadeNew-Bold.ttf"),
	"mirza": ("Mirza", 112, "mirza/Mirza-Regular.ttf", "mirza/Mirza-Bold.ttf"),
	"ruqaa": ("Aref Ruqaa", 104, "arefruqaa/ArefRuqaa-Regular.ttf", "arefruqaa/ArefRuqaa-Bold.ttf"),
	"lalezar": ("Lalezar (عناوين)", 96, "lalezar/Lalezar-Regular.ttf", None),
	"rakkas": ("Rakkas (عناوين)", 98, "rakkas/Rakkas-Regular.ttf", None),
	"changa": ("Changa", 96, "changa/Changa%5Bwght%5D.ttf", None),
	"readex": ("Readex Pro", 94, "readexpro/ReadexPro%5BHEXP%2Cwght%5D.ttf", None),
	"rubik": ("Rubik", 96, "rubik/Rubik%5Bwght%5D.ttf", None),
	"naskh": ("Noto Naskh Arabic", 100, "notonaskharabic/NotoNaskhArabic%5Bwght%5D.ttf", None),
	"reemkufi": ("Reem Kufi", 98, "reemkufi/ReemKufi%5Bwght%5D.ttf", None),
	"alexandria": ("Alexandria", 92, "alexandria/Alexandria%5Bwght%5D.ttf", None),
	"baloo": ("Baloo Bhaijaan 2", 98, "baloobhaijaan2/BalooBhaijaan2%5Bwght%5D.ttf", None),
	"lemonada": ("Lemonada", 90, "lemonada/Lemonada%5Bwght%5D.ttf", None),
}


def files(key, fontsDir=FONTS_DIR):
	base = "NileGlass-Dl-%s" % key
	return os.path.join(fontsDir, base + "-Regular.ttf"), os.path.join(fontsDir, base + "-Bold.ttf")


def isFont(path):
	try:
		if os.path.getsize(path) < 15000:
			return False
		with open(path, "rb") as f:
			head = f.read(4)
		return head in (b"\x00\x01\x00\x00", b"true", b"OTTO", b"ttcf")
	except Exception:
		return False


def fontSet(key, fontsDir=FONTS_DIR):
	"""the skin's font aliases for a downloaded font, or None when not (fully) there"""
	if key not in CATALOG:
		return None
	name, rel, _r, bold = CATALOG[key]
	reg, b = files(key, fontsDir)
	if not isFont(reg):
		return None
	regular = os.path.basename(reg)
	strong = os.path.basename(b) if bold and isFont(b) else regular
	return {"Regular": (regular, rel), "Medium": (strong, rel), "Light": (regular, rel), "ArabicBold": (strong, rel), "Replacement": (regular, rel)}


def installed(fontsDir=FONTS_DIR):
	return [(k, CATALOG[k][0]) for k in CATALOG if fontSet(k, fontsDir)]


def download(key, fontsDir=FONTS_DIR, get=None):
	"""-> (True, '') or (False, reason).  Runs in a background thread."""
	if key not in CATALOG:
		return False, "unknown font"
	if get is None:
		from Components.NileGlassCore import httpGet as get
	name, rel, regular, bold = CATALOG[key]
	want = [(regular, files(key, fontsDir)[0])] + ([(bold, files(key, fontsDir)[1])] if bold else [])
	for src, dst in want:
		ok, last = False, ""
		for base in SOURCES:
			try:
				data = get(base + src, timeout=20, maxBytes=6 * 1024 * 1024)
			except Exception as err:
				last = str(err)
				continue
			tmp = dst + ".part"
			try:
				with open(tmp, "wb") as f:
					f.write(data)
				if not isFont(tmp):
					os.remove(tmp)
					last = "not a font file"
					continue
				os.replace(tmp, dst)
				ok = True
				break
			except Exception as err:
				last = str(err)
		if not ok:
			return False, last or "download failed"
	return True, ""


def remove(key, fontsDir=FONTS_DIR):
	for p in files(key, fontsDir):
		try:
			os.remove(p)
		except OSError:
			pass
