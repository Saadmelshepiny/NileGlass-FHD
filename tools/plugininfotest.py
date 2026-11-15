#!/usr/bin/env python3
"""Plugin cards: package index from opkg lists, version from status / files /
description, feed comparison, folder size, places and background start from
the descriptors, opening counted, converter finds the descriptor in list
entries of both plugin screens.  argv: PYROOT"""
import importlib.util, os, sys, tempfile, time, types
PY = sys.argv[1]
fails = []


def check(name, ok, extra=""):
	print(("PASS " if ok else "FAIL ") + name, "" if ok else extra)
	if not ok:
		fails.append(name)


class PD:
	WHERE_PLUGINMENU, WHERE_EXTENSIONSMENU, WHERE_MAINMENU, WHERE_MENU, WHERE_AUTOSTART, WHERE_SESSIONSTART = 0, 1, 2, 3, 4, 5

	def __init__(self, name, where, path, desc="", fnc=None):
		self.name, self.where, self.path, self.description = name, where, path, desc
		self.fnc = fnc or (lambda *a, **k: "ran")

	def __call__(self, *args, **kwargs):
		return self.fnc(*args, **kwargs)


plugmod = types.ModuleType("Plugins.Plugin"); plugmod.PluginDescriptor = PD
sys.modules["Plugins"] = types.ModuleType("Plugins"); sys.modules["Plugins.Plugin"] = plugmod
sys.modules["Components"] = types.ModuleType("Components")
core = types.ModuleType("Components.NileGlassCore"); core.confGet = lambda s, k, d="": d; core.callInUiThread = lambda f, *a: f(*a)
sys.modules["Components.NileGlassCore"] = core
spec = importlib.util.spec_from_file_location("NileGlassPlugins", os.path.join(PY, "Components/NileGlassPlugins.py"))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
sys.modules["Components.NileGlassPlugins"] = M
Components = sys.modules["Components"]; Components.NileGlassPlugins = M

d = tempfile.mkdtemp()
root = os.path.join(d, "Plugins") + "/"
info, lists = os.path.join(d, "info"), os.path.join(d, "lists")
os.makedirs(info); os.makedirs(lists)
M.PLUGIN_ROOT, M.OPKG_INFO, M.OPKG_STATUS, M.OPKG_LISTS, M.USAGE_FILE = root, info, os.path.join(d, "status"), lists, os.path.join(d, "used.json")
a = root + "Extensions/Alpha"; b = root + "Extensions/Beta"; c = root + "SystemPlugins/Gamma"
for f in (a, b, c):
	os.makedirs(f)
open(a + "/plugin.py", "w").write("x" * 5000)
open(b + "/plugin.pyc", "wb").write(b"0" * 3000)
open(b + "/__init__.py", "w").write('VERSION = "4.7.1"\n')
os.remove(b + "/__init__.py"); open(b + "/version.txt", "w").write("v4.7.1\n")
open(c + "/plugin.py", "w").write("# nothing\n")
open(info + "/enigma2-plugin-extensions-alpha.list", "w").write(a + "/plugin.py\n" + a + "/icon.png\n")
open(info + "/enigma2-plugin-extensions-alpha.control", "w").write("Package: enigma2-plugin-extensions-alpha\nVersion: 1:2.0+git123+abcdef0123-r0\nMaintainer: Saad <s@x>\n")
open(M.OPKG_STATUS, "w").write("Package: enigma2-plugin-extensions-alpha\nVersion: 1:2.0+git123+abcdef0123-r0\nStatus: install ok installed\nInstalled-Time: 1700000000\n\n")
open(lists + "/feed", "w").write("Package: enigma2-plugin-extensions-alpha\nVersion: 1:2.1-r0\n\nPackage: other\nVersion: 1\n")
pa = PD("Alpha", [PD.WHERE_PLUGINMENU], a)
pa2 = PD("Alpha ext", [PD.WHERE_EXTENSIONSMENU, PD.WHERE_SESSIONSTART], a)
pb = PD("Beta", [PD.WHERE_PLUGINMENU], b, "Beta v4.7")
pc = PD("Gamma", [PD.WHERE_PLUGINMENU], c, "Gamma tools v3.2")
allp = [pa, pa2, pb, pc]
M._allPlugins = lambda: allp

first = M.info(pa)
check("before the index: placeholders, no waiting", first["package"] == "…" and first["size"] == "…")
heard = []
M.addListener(lambda: heard.append(1))
M.prepare()
for _ in range(50):
	if not M._loading and M._index is not None and a in M._sizes:
		break
	time.sleep(0.05)
check("background read tells the screen", heard)
r = M.info(pa)
check("package and version from opkg", r["package"] == "enigma2-plugin-extensions-alpha" and r["version"].startswith("2.0+abcdef0"), r)
check("maker", r["maker"] == "Saad")
check("install date", r["installed"] == time.strftime("%d/%m/%Y", time.localtime(1700000000)))
check("feed has another version", "2.1-r0" in r["feed"], r["feed"])
check("size", r["size"] == "4 KB", r["size"])
check("places of all its entries", "قائمة الإضافات" in r["places"] and "الملحقات" in r["places"], r["places"])
check("starts with the box", r["background"].startswith("نعم"))
rb = M.info(pb)
check("no package: version from the folder", rb["version"] == "4.7.1" and "يدوي" in rb["package"] and rb["feed"] == "—", rb)
check("compiled only", "مقفول" in rb["kind"], rb["kind"])
check("only when opened", rb["background"].startswith("لأ"))
rc = M.info(pc)
check("version from the description", rc["version"] == "3.2" and rc["kind"].startswith("نظام"), rc)
check("never opened", rc["runs"] == "0" and "متفتحش" in rc["last"])

M.installUsage()
session = types.SimpleNamespace(openWithCallback=lambda *a: None)
check("opening still works", pc(session=session) == "ran")
pc(session=session)
PD("auto", [PD.WHERE_SESSIONSTART], c)(reason=0, session=session)
M._saveUsage()
rc = M.info(pc)
check("opening counted, start-up calls not", rc["runs"] == "2" and rc["last"] == "دلوقتي", rc)
check("usage saved", os.path.isfile(M.USAGE_FILE))

spec = importlib.util.spec_from_file_location("NGPluginInfo", os.path.join(PY, "Components/Converter/NGPluginInfo.py"))
conv = types.ModuleType("Components.Converter"); sys.modules["Components.Converter"] = conv
cm = types.ModuleType("Components.Converter.Converter")


class Converter:
	CHANGED_DEFAULT, CHANGED_ALL = 0, 2

	def __init__(self, arg):
		self.source = None

	def changed(self, what):
		pass

	def destroy(self):
		pass
cm.Converter = Converter
sys.modules["Components.Converter.Converter"] = cm
el = types.ModuleType("Components.Element"); el.cached = lambda f: f; sys.modules["Components.Element"] = el
N = importlib.util.module_from_spec(spec); spec.loader.exec_module(N)
check("descriptor in a plugin list entry", N.descriptorOf((pb, "Beta", "desc", None)) is pb)
check("descriptor in a green panel entry", N.descriptorOf(("Beta", "desc", None, pb, 3)) is pb)
check("nothing selected", N.descriptorOf(None) is None and N.descriptorOf(("a", "b")) is None)
cv = N.NGPluginInfo("Version")
cv.source = types.SimpleNamespace(getCurrent=lambda: ("Beta", "d", None, pb, 1), onSelectionChanged=[])
check("converter text", cv.getText() == "4.7.1")
cv.changed((0,))
check("follows the cursor", cv.source.onSelectionChanged == [cv.selChanged] or len(cv.source.onSelectionChanged) == 1)
print("ALL OK" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
