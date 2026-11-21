#!/usr/bin/env python3
"""Find list templates whose text boxes overlap or are too short for Arabic
(an Arabic line needs about 1.3 x the font size).  argv: skin.xml [ratio]"""
import re, sys
import xml.etree.ElementTree as ET
RATIO = float(sys.argv[2]) if len(sys.argv) > 2 else 1.25
root = ET.parse(sys.argv[1]).getroot()
bad = []
for scr in root.iter("screen"):
	name = scr.get("name")
	for conv in scr.iter("convert"):
		if conv.get("type") != "TemplatedMultiContent":
			continue
		t = conv.text or ""
		t = re.sub(r"#[^\n]*", "", t)
		fonts = [int(x) for x in re.findall(r'gFont\(\s*"[^"]+"\s*,\s*(\d+)\s*\)', t)]
		for tm in re.finditer(r'"(\w+)"\s*:\s*\(\s*(\d+)\s*,\s*\[(.*?)\]\s*,', t, re.S) or []:
			pass
		# every template (one or several modes): text entries
		ents = []
		for m in re.finditer(r"MultiContentEntryText\(", t):
			depth, i = 1, m.end()
			while i < len(t) and depth:
				depth += {"(": 1, ")": -1}.get(t[i], 0)
				i += 1
			a = t[m.end():i - 1]
			p = re.search(r"pos\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", a); s = re.search(r"size\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", a)
			f = re.search(r"font\s*=\s*(\d+)", a)
			if not (p and s and f):
				continue
			fi = int(f.group(1))
			if fi >= len(fonts):
				continue
			ents.append((int(p.group(1)), int(p.group(2)), int(s.group(1)), int(s.group(2)), fonts[fi], m.start()))
		for x, y, w, h, fs, _ in ents:
			if h < fs * RATIO and h > 0:
				bad.append("%s: text box %dx%d at %d,%d too short for font %d" % (name, w, h, x, y, fs))
		for i, a in enumerate(ents):
			for b in ents[i + 1:]:
				if a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]:
					if (a[0], a[1]) != (b[0], b[1]):
						bad.append("%s: text boxes overlap %s / %s" % (name, a[:4], b[:4]))
print("\n".join(sorted(set(bad))) or "text fit ok")
print(len(set(bad)), "problems")
