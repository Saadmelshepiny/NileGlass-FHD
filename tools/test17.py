"""Tests for 1.7: translation fallback, ECM converter, style transforms."""
import gettext, json, os, sys, tempfile, time, types, importlib.util
PY = sys.argv[1]; SKIN = sys.argv[2]
ok = True
def check(c, m):
	global ok; print(("PASS " if c else "FAIL ") + m); ok = ok and c

# --- translation fallback (same logic as plugin.installTranslations)
table = json.load(open(os.path.join(SKIN, "translations/ar.json"), encoding="utf-8"))
class NGCatalog(gettext.NullTranslations):
	def gettext(self, m):
		return table[m] if m in table else (self._fallback.gettext(m) if self._fallback else m)
class Img(gettext.NullTranslations):  # the image catalogue: knows one string
	def gettext(self, m):
		if m == "Setup": return "الضبط"
		return self._fallback.gettext(m) if self._fallback else m
img = Img(); img.add_fallback(NGCatalog())
check(img.gettext("Setup") == "الضبط", "image translation wins")
check(img.gettext("OpenBh Apps") == "تطبيقات OpenBh", "missing string from NileGlass table")
check(img.gettext("Unknown thing") == "Unknown thing", "unknown text unchanged")
check(all("%s" not in k or k.count("%s") == v.count("%s") for k, v in table.items()), "format placeholders kept")

# --- ECM converter
mods = {}
def mod(n, **kw):
	m = types.ModuleType(n); m.__dict__.update(kw); sys.modules[n] = m; return m
mod("enigma", iServiceInformation=types.SimpleNamespace(sIsCrypted=1, sServiceref=2))
mod("Components"); mod("Components.Converter")
mod("Components.Converter.Converter", Converter=type("C", (), {"__init__": lambda s, a: None}))
mod("Components.Converter.Poll", Poll=type("P", (), {"__init__": lambda s: None}))
mod("Components.Converter.NGPoll", NGPoll=type("P", (), {"__init__": lambda s: None}))
mod("Components.Element", cached=lambda f: f)
spec = importlib.util.spec_from_file_location("NGEcm", os.path.join(PY, "Components/Converter/NGEcm.py"))
E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)
tmp = tempfile.mkdtemp(); E.ECM_FILE = os.path.join(tmp, "ecm.info")
crypted = [1]
info = types.SimpleNamespace(getInfo=lambda k: crypted[0], getInfoString=lambda k: "1:0:1:ABC")
conv = lambda t: (lambda c: (setattr(c, "source", types.SimpleNamespace(service=types.SimpleNamespace(info=lambda: info))), c)[1])(E.NGEcm(t))
st = conv("State")
check(st.text == "بانتظار فك التشفير ...", "waiting before ecm.info exists")
time.sleep(0.05)
open(E.ECM_FILE, "w").write("system: Viaccess\ncaid: 0x0500\npid: 0x0B2C\nreader: emulator\nfrom: local\nprotocol: emu\nhops: 0\necm time: 0.312\n")
check(st.text == "تم فك التشفير", "decoded after fresh ecm.info")
check(conv("Caid").text == "0x0500  Viaccess", "caid + system: %r" % conv("Caid").text)
check(conv("Time").text == "312 ms" and conv("Source").text == "emulator" and conv("Hops").text == "0", "time/source/hops")
open(E.ECM_FILE, "w").write("===== Nagra ECM on CaID 0x1830, pid 0x0710\nreader: card1\necm time: 845 msec\n")
check(conv("Caid").text == "0x1830  Nagra" and conv("Time").text == "845 ms", "oscam header format: %r %r" % (conv("Caid").text, conv("Time").text))
crypted[0] = 0
check(st.text == "قناة مفتوحة (FTA)" and conv("Caid").text == "", "FTA")

# --- style transforms
sys.path.insert(0, os.path.join(PY, "Components"))
import NileGlassStyle as S
import xml.etree.ElementTree as ET
st = S.readStyle("/nonexistent")
check(st["text_color"] == "white" and st["direction"] == "auto" and st["translate"] is True, "defaults")
check(S.isRtl({"direction": "auto"}, "ar_AE") and not S.isRtl({"direction": "auto"}, "en_GB") and S.isRtl({"direction": "rtl"}, "en_GB"), "direction rules")
for lang, rtl in (("ar_AE", True), ("en_GB", False)):
	st = dict(S.DEFAULTS); st.update(S.readStyle("/nonexistent")); st["infobar_size"] = 110; st["outline"] = True
	xml = S.buildXml(st, SKIN, language=lang)
	root = ET.fromstring(xml)
	scr = {s.get("name"): s for s in root.findall("screen")}
	menu = " ".join([c for c in scr["Menu"].iter("convert") if c.get("type") == "TemplatedMultiContent"][0].text.split())
	if rtl:
		check("RT_HALIGN_RIGHT" in menu and ("pos=(636, 9)" in menu or "pos=(616, 9)" in menu or "pos=(500, 9)" in menu), "Arabic: menu text right, icon stays right")
		ds = " ".join([c for c in scr["DeliteSettings"].iter("convert") if c.get("type") == "TemplatedMultiContent"][0].text.split())
		check("pos=(874, 8)" in ds and "RT_HALIGN_RIGHT" in ds, "Arabic: popup icon moved right")
	else:
		check("RT_HALIGN_LEFT" in menu and ("pos=(16, 9)" in menu or "pos=(20, 9)" in menu), "English: menu icon moved left: %s" % menu[:160])
	ib = scr["InfoBar"]
	fonts = [w.get("font") for w in ib.iter() if w.get("font")]
	check(any(f.endswith(";35") for f in fonts) and all(w.get("borderWidth") == "2" for w in ib.iter("widget") if w.get("render") == "Label"), "infobar sizes x1.1 + outline")
	check("NileGlassTonight" not in scr and "ChannelSelection" not in scr, "excluded screens untouched")
	check(root.find("colors/color[@name='fg']") is not None, "text colour written")
FD = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(PY)))), "share/fonts")
missing = sorted({f for fs in S.FONT_SETS.values() for f, r in fs.values() if not os.path.isfile(os.path.join(FD, f))})
check(not missing, "every font file of every font set exists %s" % missing)
print("ALL OK" if ok else "SOME TESTS FAILED")
