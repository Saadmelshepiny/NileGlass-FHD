#!/usr/bin/env python3
"""3.0: looks, title font, sizes per part, seasons, font library.  argv: PYROOT"""
import os, re, sys, tempfile, time
PY = sys.argv[1]
sys.path.insert(0, os.path.join(PY, "Components"))
sys.path.insert(0, PY)
import NileGlassStyle as S
import NileGlassFonts as F
SK = os.path.join(PY, "../../../share/enigma2/NileGlass_FHD")
FD = os.path.join(PY, "../../../share/fonts")
fails = []


def check(name, ok, extra=""):
	print(("PASS " if ok else "FAIL ") + name, "" if ok else extra)
	if not ok:
		fails.append(name)


base = S.readStyle("/none")
for look in S.LOOKS:
	x = S.buildXml(dict(base, look=look), SK)
	check("look %s builds" % look, not S._xmlProblems(x, SK, FD) and S.LOOKS[look][0] in x)
x = S.buildXml(dict(base, title_font="cairo"), SK)
check("titles in another font", 'filename="NileGlass-Cairo-Bold.ttf" name="Medium"' in x and 'filename="NileGlass-Regular.ttf" name="Regular"' in x)
x = S.buildXml(dict(base, list_size=120), SK)
setup = re.search(r'<screen name="Setup".*?</screen>', x, re.S).group(0)
orig = re.search(r'<screen name="Setup".*?</screen>', open(os.path.join(SK, "layouts/menus_popup.xml"), encoding="utf-8").read(), re.S).group(0)
h0 = int(re.search(r'itemHeight="(\d+)"', orig).group(1))
check("lists: bigger text, taller rows", ('itemHeight="%d"' % round(h0 * 1.2)) in setup, (h0, re.findall(r'itemHeight="\d+"', setup)))
x = S.buildXml(dict(base, card_size=110, epg_size=90, desc_size=120), SK)
check("cards scaled", re.search(r'<screen name="NG_Dash_system_100"', x) is not None)
check("no problem with every size", not S._xmlProblems(x, SK, FD))
t = lambda d: time.mktime(time.strptime(d, "%Y-%m-%d"))
check("Ramadan: gold", S.seasonal(dict(base, season=True), t("2027-02-20"))["accent"] == "gold")
check("Eid: green", S.seasonal(dict(base, season=True), t("2027-03-10"))["accent"] == "green")
check("season off: own look", S.seasonal(dict(base, season=False), t("2027-02-20"))["accent"] == base["accent"])
check("no season: own look", S.seasonal(dict(base, season=True), t("2026-11-20")) == dict(base, season=True))
# font library
d = tempfile.mkdtemp()
check("not downloaded: not offered", F.installed(d) == [] and F.fontSet("harmattan", d) is None)
good = b"\x00\x01\x00\x00" + b"x" * 20000
calls = []
def get(url, timeout=0, maxBytes=0):
	calls.append(url)
	if "raw.githubusercontent" in url:
		raise IOError("blocked")
	return good
ok, why = F.download("harmattan", d, get)
check("download (mirror used when GitHub fails)", ok and len(calls) == 4 and F.fontSet("harmattan", d)["Medium"][0] == "NileGlass-Dl-harmattan-Bold.ttf", (ok, why, calls))
check("offered after download", ("harmattan", "Harmattan") in F.installed(d))
ok, why = F.download("lalezar", d, lambda url, timeout=0, maxBytes=0: b"<html>not found</html>" * 1000)
check("a web page is not a font: nothing kept", not ok and F.fontSet("lalezar", d) is None and not os.path.exists(F.files("lalezar", d)[0]))
check("one-weight fonts: bold = regular", F.download("changa", d, lambda url, timeout=0, maxBytes=0: good)[0] and F.fontSet("changa", d)["Medium"][0] == "NileGlass-Dl-changa-Regular.ttf")
print("ALL OK" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
