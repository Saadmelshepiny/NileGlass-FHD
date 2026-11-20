#!/usr/bin/env python3
"""Static checks of the NileGlass skin against the OpenBh source tree."""
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = sys.argv[1]          # build/root
BH = sys.argv[2]            # OpenBh enigma2 source
SKIN_DIR = os.path.join(ROOT, "usr/share/enigma2/NileGlass_FHD")
PY = os.path.join(BH, "lib/python")
errors, warnings = [], []

tree = ET.parse(os.environ.get("NG_SKIN_XML", os.path.join(SKIN_DIR, "skin.xml")))
skin = tree.getroot()
screens = {s.get("name"): s for s in skin.findall("screen")}
_names = [s.get("name") for s in skin.findall("screen")]
# enigma2 creates eLabels AFTER the widgets: an opaque full-size background
# eLabel at zPosition >= 0 covers every widget of the screen (blank screen)
for _s in skin.findall("screen"):
	if _s.find("widget") is None:
		continue
	for _e in _s.findall("eLabel"):
		if _e.get("backgroundColor") and not _e.get("text") and _e.get("size") == _s.get("size") and int(_e.get("zPosition", "0")) >= 0:
			errors.append("%s: background eLabel above the widgets (needs a negative zPosition)" % _s.get("name"))
for _n in sorted({n for n in _names if _names.count(n) > 1}):
	errors.append("screen defined more than once: %s" % _n)
colors = {c.get("name") for c in skin.find("colors")}
fonts = {f.get("name") for f in skin.find("fonts").findall("font")} | {a.get("name") for a in skin.find("fonts").findall("alias")}

# ---- converters / renderers available
conv = {f[:-3] for f in os.listdir(os.path.join(PY, "Components/Converter")) if f.endswith(".py")}
rend = {f[:-3] for f in os.listdir(os.path.join(PY, "Components/Renderer")) if f.endswith(".py")}
conv |= {f[:-3] for f in os.listdir(os.path.join(ROOT, "usr/lib/enigma2/python/Components/Converter"))}
rend |= {f[:-3] for f in os.listdir(os.path.join(ROOT, "usr/lib/enigma2/python/Components/Renderer"))}

# ---- components each screen class offers (from reading the OpenBh source)
KEYS_BUTTON = {"key_red", "key_green", "key_yellow", "key_blue"}
EPG_BASE = {"Service", "Event", "lab1", "key_red", "key_green", "key_yellow", "key_blue", "key_menu", "key_info", "key_play", "list", "bouquetlist", "number", "Title"}
COMMON = {"Title"}
SCREEN_COMPONENTS = {
	"InfoBar": {"key_red", "key_green", "key_yellow", "key_blue"},
	"SecondInfoBar": {"epg_description", "channel"} | KEYS_BUTTON,
	"ChannelSelection": {"list", "Service", "ServiceEvent", "Event", "key_menu", "key_info"} | KEYS_BUTTON,
	"SingleEPG": EPG_BASE,
	"MultiEPG": EPG_BASE | {"now_button", "next_button", "more_button", "now_button_sel", "next_button_sel", "more_button_sel", "now_text", "next_text", "more_text", "date", "key_text"},
	"GridEPG": EPG_BASE | {"timeline_text", "timeline_now", "primetime", "change_bouquet", "jump", "page", "key_text"} | {"timeline%d" % i for i in range(6)},
	"InfobarSingleEPG": EPG_BASE,
	"EventView": {"Service", "Event", "epg_eventname", "epg_description", "FullDescription", "summary_description", "datetime", "channel", "duration", "key_menu", "key_red", "key_green", "key_yellow", "key_blue", "red", "green", "yellow", "blue", "cast_title"} | {"cast_%s%d" % (k, i) for k in "pn" for i in range(5)},
	"InfoBarEventView": {"Service", "Event", "epg_eventname", "epg_description", "FullDescription", "datetime", "channel", "duration", "key_red"},
	"Menu": {"menu", "title", "description", "key_blue"},
	"Setup": {"config", "description", "footnote", "key_red", "key_green", "key_menu", "HelpWindow", "VKeyIcon"},
	"MessageBox": {"icon", "text", "Text", "selectedChoice", "list", "key_help"},
	"ChoiceBox": {"text", "list", "description", "key_menu", "key_previous", "key_next", "summary_list", "summary_selection"},
	"ExtensionsList": {"text", "list", "description", "key_menu", "key_previous", "key_next", "summary_list", "summary_selection"},
	"AboutOE": {"lab1", "lab2", "lab3", "AboutScrollLabel", "key_red", "key_green", "key_yellow", "key_blue", "key_menu"},
	"PluginBrowser": {"list", "entry", "desc", "key_red", "key_green", "key_yellow", "key_0", "key_previous", "key_next"},
	"PluginDownloadBrowser": {"list", "text", "key_red", "key_green", "key_blue", "ng_sel"},
	"MovieSelection": {"Service", "Event", "chosenletter", "waitingtext", "DescriptionBorder", "list", "key_red", "key_green", "key_yellow", "key_blue", "key_menu", "key_info", "key_0", "movie_off", "movie_sort", "freeDiskSpace", "TrashcanSize"},
	"NumberZap": {"number", "number_summary", "servicename", "servicename_summary", "Service"},
	"Volume": {"Volume", "VolumeText"},
	"Mute": set(),
	"MoviePlayer": set(),
	"DeliteGreenPanel": {"list"} | KEYS_BUTTON,
	"Satfinder": {"config", "description", "introduction", "Frontend", "key_red", "key_green", "key_yellow", "key_menu", "tsid", "onid", "pos", "HelpWindow", "VKeyIcon", "Title"},
	"NileGlassFilm": {"title", "original", "facts", "ratings", "story", "crew", "showings_title", "backdrop", "poster", "showings", "key_red", "key_green", "key_yellow", "key_blue", "Title"} | {"%s%d" % (k, i) for k in ("cast", "castname") for i in range(6)},
	"NileGlassUpcoming": {"channel", "count", "title", "when", "info", "desc", "card", "key_red", "key_green", "key_yellow", "key_blue", "Title"} | {"%s%d" % (k, i) for k in ("sel", "poster", "time") for i in range(6)},
	"NileGlassWeather": {"city", "now_temp", "now_desc", "now_extra", "updated", "now_icon", "Title"} | {"%s%d" % (k, i) for k in ("day", "temp", "desc", "icon") for i in range(5)},
	"NileGlassTonight": {"list", "poster", "picon", "title", "info", "when", "channel", "desc", "badge", "versus", "status", "empty", "tab_films", "tab_matches", "tab_films_line", "tab_matches_line", "key_red", "key_green", "key_yellow", "key_blue", "Title"},
	"NileGlassSetup": {"config", "description", "footnote", "key_red", "key_green", "key_yellow", "key_blue", "key_menu", "HelpWindow", "VKeyIcon", "preview_accent", "preview_glass", "preview_icons", "preview_font", "preview_title", "pv_ib_time", "pv_ib_title", "pv_head", "pv_row", "pv_row2", "pv_desc"},
	"NileGlassCamBar": {"cam", "left", "right", "info", "state", "Title"},
	"NileGlassBitrate": {"Title"},
	"RdsInfoDisplay": {"RadioText", "RtpText", "RassLogo", "Title"},
	"NetworkServiceSetup": {"lab1", "labactive", "lab2", "labstop", "labrun", "key_red", "key_green", "key_yellow", "key_blue", "status_summary", "autostartstatus_summary", "Title"},
	"NileGlassMotor": {"title", "from", "to", "time", "info", "Title"},
	"NileGlassReaderEdit": {"config", "description", "footnote", "key_red", "key_green", "key_yellow", "key_blue", "key_menu", "HelpWindow", "VKeyIcon", "Title"},
	"NileGlassReaders": {"list", "details", "file", "hint", "summary", "key_red", "key_green", "key_yellow", "key_blue", "Title"},
	"NileGlassCamCenter": {"list", "info", "key_red", "key_green", "key_yellow", "key_blue", "Title"},
	"NileGlassCamStatus": {"list", "summary", "hint", "key_red", "key_green", "key_yellow", "key_blue", "Title"},
	"NileGlassCamInfo": {"list", "hint", "Title"},
	"NileGlassCamText": {"text", "file", "hint", "key_red", "key_green", "key_yellow", "key_blue", "Title"},
	"TextBox": {"text", "key_red", "Title"},
	"ServiceInfo": {"infolist", "red", "green", "yellow", "blue", "key_red", "Title"},
	"DeliteBluePanel": {"lab1", "lab2", "lab3", "Ilab1", "Ilab2", "Ilab3", "Ilab4", "activecam", "Ecmtext", "list"} | KEYS_BUTTON,
}
ALIASES = {
	"SecondInfoBarSimple": "SecondInfoBar", "SlimChannelSelection": "ChannelSelection", "EPGSelection": "SingleEPG",
	"EPGSelectionMulti": "MultiEPG", "GraphicalEPG": "GridEPG", "GridEPGPIG": "GridEPG", "GraphicalEPGPIG": "GridEPG",
	"InfoBarGridEPG": "GridEPG", "GraphicalInfoBarEPG": "GridEPG", "QuickEPG": "InfobarSingleEPG",
	"EventViewSimple": "EventView", "MessageBoxSimple": "MessageBox", "NumberZapPicon": "NumberZap", "ServiceInfoSimple": "ServiceInfo",
}
# screens not listed above: read self["..."] of the class with that name in the OpenBh source
_classSrc = {}
for _root, _d, _files in os.walk(PY):
	for _f in _files:
		if _f.endswith(".py"):
			_t = open(os.path.join(_root, _f), encoding="utf-8", errors="replace").read()
			for _m in re.finditer(r"\nclass (\w+)\(.*?(?=\nclass |\Z)", _t, re.S):
				_classSrc.setdefault(_m.group(1), _m.group(0))
for n in screens:
	if n not in SCREEN_COMPONENTS and n in _classSrc and not n.startswith("NG"):
		SCREEN_COMPONENTS[n] = set(re.findall(r'self\["(\w+)"\]\s*=', _classSrc[n])) | {"Title"}
		for _m in re.finditer(r'self\[f"key_\{color\}"\]', _classSrc[n]):
			SCREEN_COMPONENTS[n] |= {"key_red", "key_green", "key_yellow", "key_blue"}
		if "ConfigListScreen" in _classSrc[n].lstrip().split("\n", 1)[0]:
			SCREEN_COMPONENTS[n] |= {"config", "HelpWindow", "VKeyIcon"}
		_static = set(re.findall(r'self\["(key_\w+)"\]\s*=\s*StaticText', _classSrc[n]))
		if _static:
			STATIC_KEYS_AUTO = globals().setdefault("STATIC_KEYS_AUTO", {})
			STATIC_KEYS_AUTO[n] = _static
for n in screens:
	if n.startswith("menu_"):
		ALIASES[n] = "Menu"
GLOBAL_SOURCES = ("session.", "global.")

# Which of the key_* are StaticText (source) vs Button/Label (name) per screen
STATIC_KEYS = {"Menu": {"key_blue"}, "Setup": {"key_red", "key_green", "key_menu"}, "NileGlassSetup": {"key_red", "key_green", "key_yellow", "key_blue", "key_menu"}, "NileGlassReaders": {"key_red", "key_green", "key_yellow", "key_blue"}, "NileGlassCamCenter": {"key_red", "key_green", "key_yellow", "key_blue"}, "NileGlassCamStatus": {"key_red", "key_green", "key_yellow", "key_blue"}, "NileGlassCamText": {"key_red", "key_green", "key_yellow", "key_blue"}, "ChoiceBox": {"key_menu"},
	"PluginBrowser": set(), "AboutOE": {"key_menu"}}
STATIC_KEYS.update(globals().get("STATIC_KEYS_AUTO", {}))
# screens converted by gen_converted.py: their component lists come from the source
DYN = {}
_cc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "converted_components.json")
if os.path.isfile(_cc):
	import json as _json
	for _n, _items in _json.load(open(_cc)).items():
		SCREEN_COMPONENTS[_n] = set(SCREEN_COMPONENTS.get(_n) or ()) | {i for i in _items if ":" not in i}
		STATIC_KEYS[_n] = set(STATIC_KEYS.get(_n) or ()) | {i[7:] for i in _items if i.startswith("static:")}
		DYN[_n] = tuple(i[4:] for i in _items if i.startswith("dyn:"))


def expand(elem, seen=()):
	out = []
	for child in elem:
		if child.tag == "panel" and child.get("name") is None:      # inline panel (own position): its children
			out.extend(expand(child, seen))
			continue
		if child.tag == "panel":
			name = child.get("name")
			if name not in screens:
				errors.append("panel '%s' not found" % name)
				continue
			if name in seen:
				errors.append("panel recursion %s" % name)
				continue
			out.extend(expand(screens[name], seen + (name,)))
		else:
			out.append(child)
	return out


def checkFile(attr, value, where):
	for v in value.split(","):
		v = v.strip()
		if v.startswith("NileGlass_FHD/"):
			if not os.path.isfile(os.path.join(SKIN_DIR, v[len("NileGlass_FHD/"):])):
				errors.append("%s: missing file %s" % (where, v))
		elif v:
			warnings.append("%s: %s='%s' not inside the skin" % (where, attr, v))


def checkColorFont(el, where):
	for a in ("foregroundColor", "backgroundColor", "borderColor", "foregroundColorSelected", "backgroundColorSelected", "shadowColor"):
		v = el.get(a)
		if v and not v.startswith("#") and v not in colors:
			errors.append("%s: unknown colour %s=%s" % (where, a, v))
	f = el.get("font")
	if f:
		name = f.split(";")[0]
		if name not in fonts:
			errors.append("%s: unknown font %s" % (where, f))


# global resources
for bs in skin.iter("pixmap"):
	checkFile("filename", bs.get("filename"), "windowstyle")
for mi in skin.iter("menuicon"):
	checkFile("image", mi.get("image"), "menuicons")
for f in skin.find("fonts").findall("font"):
	fn = f.get("filename")
	if not os.path.isfile(os.path.join(ROOT, "usr/share/fonts", fn)) and not os.path.isfile(os.path.join(BH, "data/fonts", fn)):
		errors.append("font file missing: %s" % fn)

checked = 0
for name, scr in screens.items():
	if name.startswith(("NG_", "NileGlassDash_")):
		continue
	base = ALIASES.get(name, name)
	comps = SCREEN_COMPONENTS.get(base)
	if comps is None:
		warnings.append("no component list for screen %s" % name)
		comps = set()
	static = STATIC_KEYS.get(base, set())
	for el in expand(scr):
		where = "%s/%s" % (name, el.get("name") or el.get("source") or el.tag)
		checked += 1
		for a in ("pixmap", "pixmaps", "selectionPixmap", "backgroundPixmap"):
			if el.get(a):
				checkFile(a, el.get(a), where)
		checkColorFont(el, where)
		if el.tag != "widget":
			continue
		cond = el.get("conditional")
		ot = el.get("objectTypes")
		if ot:
			key, *types = ot.split(",")
			if key not in comps:
				continue  # skipped by enigma2 at runtime
			isStatic = key in static
			if ("StaticText" in types) != isStatic:
				continue  # the other variant applies
		wname, wsource, render = el.get("name"), el.get("source"), el.get("render")
		if DYN.get(base) and (wname or wsource or "").startswith(DYN[base]):
			continue
		if wname and wname not in comps:
			errors.append("%s: widget name '%s' not offered by the screen" % (where, wname))
		if wname and wname in static:
			errors.append("%s: '%s' is a StaticText source, use source=" % (where, wname))
		if wsource and not wsource.startswith(GLOBAL_SOURCES) and wsource not in comps and wsource not in COMMON:
			errors.append("%s: source '%s' not offered by the screen" % (where, wsource))
		if wsource and not render:
			errors.append("%s: source without render" % where)
		if render and render not in rend and render not in ("Label", "Pixmap", "Progress", "Listbox", "Picon", "Pig", "FixedLabel"):
			errors.append("%s: renderer '%s' not found" % (where, render))
		for c in el.findall("convert"):
			if c.get("type") not in conv:
				errors.append("%s: converter '%s' not found" % (where, c.get("type")))

print("checked %d elements in %d screens" % (checked, len(screens)))
for w in sorted(set(warnings)):
	print("WARN ", w)
for e in errors:
	print("ERROR", e)
sys.exit(1 if errors else 0)
