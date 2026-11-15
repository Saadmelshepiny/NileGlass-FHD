# -*- coding: utf-8 -*-
# NileGlass FHD - the skin under the cursor in the skin selector.
#   Name, Resolution, Size, Screens, Fonts, Author, Version, Color1..Color6, ColorName1..6
# The skin file is read once per skin (only colours, fonts and the header).

import os
import re

from Components.Converter.Converter import Converter
from Components.Element import cached

ROOT = "/usr/share/enigma2"
WANT = ("background", "bg", "foreground", "fg", "accent", "selection", "bgSel", "gold", "yellow", "red", "green", "blue")
_cache = {}


def skinFile(entry):
	# SkinSelector rows: (LABEL, label, default, dir, file, resolution, size, preview)
	try:
		d, f = entry[3], entry[4]
		for p in (os.path.join(ROOT, d, f), os.path.join(ROOT, "display", d, f), os.path.join(d, f)):
			if os.path.isfile(p):
				return p
	except Exception:
		pass
	return None


def parse(path):
	if path in _cache:
		return _cache[path]
	info = {"colors": [], "fonts": [], "screens": 0, "author": "", "version": ""}
	try:
		with open(path, encoding="utf-8", errors="ignore") as f:
			text = f.read(3 * 1024 * 1024)
		head = re.sub(r"<\?xml[^>]*\?>", "", text[:4000])
		m = re.search(r"(?:author|by|created by|skin by)[:\s]+([^\n<>,;|-]{2,40})", head, re.I)
		info["author"] = m.group(1).strip() if m else ""
		m = re.search(r"version[:\s=\"']+v?([\d][\w.\-]{0,15})", head, re.I)
		info["version"] = m.group(1) if m else ""
		colors = re.findall(r'<color\s+name="([^"]+)"\s+value="#?([0-9a-fA-F]{6,8})"', text)
		named = dict((n, v) for n, v in colors)
		picked = [n for n in WANT if n in named]
		for n, v in colors:
			if len(picked) >= 6:
				break
			if n not in picked:
				picked.append(n)
		info["colors"] = [(n, named[n][-6:]) for n in picked[:6]]
		fonts = re.findall(r'<font\s+[^>]*filename="([^"]+)"', text)
		info["fonts"] = list(dict.fromkeys(os.path.splitext(os.path.basename(x))[0] for x in fonts))
		info["screens"] = len(re.findall(r"<screen\b", text))
		owner = os.path.basename(os.path.dirname(path))
		for ctl in os.listdir("/var/lib/opkg/info") if os.path.isdir("/var/lib/opkg/info") else []:
			if ctl.endswith(".list") and owner.lower().replace("_", "-") in ctl.lower():
				c = ctl[:-5] + ".control"
				try:
					ct = open(os.path.join("/var/lib/opkg/info", c), encoding="utf-8", errors="ignore").read()
					v = re.search(r"^Version:\s*(\S+)", ct, re.M)
					a = re.search(r"^Maintainer:\s*([^<\n]+)", ct, re.M)
					info["version"] = info["version"] or (v.group(1).split("+")[0] if v else "")
					info["author"] = info["author"] or (a.group(1).strip() if a else "")
				except Exception:
					pass
				break
	except Exception as err:
		print("[NileGlass] skin info:", err)
	_cache[path] = info
	return info


class NGSkinInfo(Converter):
	def __init__(self, arg):
		Converter.__init__(self, arg)
		self.type = (arg or "Name").strip()
		self.hooked = False

	def changed(self, what):
		if what[0] == self.CHANGED_DEFAULT and not self.hooked and self.source is not None:
			self.hooked = True
			try:
				self.source.onSelectionChanged.append(lambda: self.downstream_elements.changed((self.CHANGED_ALL, 0)))
			except Exception:
				pass
		Converter.changed(self, what)

	@cached
	def getText(self):
		try:
			entry = self.source.getCurrent()
		except Exception:
			entry = None
		if not entry:
			return ""
		t = self.type
		try:
			if t == "Name":
				return str(entry[1])
			if t == "Resolution":
				return str(entry[5] or "")
			if t == "Size":
				return str(entry[6] or "")
			path = skinFile(entry)
			if not path:
				return ""
			info = parse(path)
			if t == "Screens":
				return str(info["screens"])
			if t == "Fonts":
				return " · ".join(info["fonts"][:4]) or "—"
			if t == "Author":
				return info["author"] or "—"
			if t == "Version":
				return info["version"] or "—"
			if t.startswith("ColorName") and t[9:].isdigit():
				i = int(t[9:]) - 1
				return info["colors"][i][0] if i < len(info["colors"]) else ""
			if t.startswith("Color") and t[5:].isdigit():
				i = int(t[5:]) - 1
				return "#" + info["colors"][i][1] if i < len(info["colors"]) else ""
		except Exception as err:
			print("[NileGlass] NGSkinInfo:", err)
		return ""

	text = property(getText)
