#!/usr/bin/env python3
"""What each OpenBh screen class offers to a skin, read from the source:
self["x"] = Type(...) in the class and its base classes (followed through
the whole source tree).  Used to keep converted screens honest."""
import os, re

SOURCE_TYPES = {"StaticText", "List", "Boolean", "Event", "ServiceEvent", "CurrentService", "Clock", "FrontendStatus",
	"Progress", "ServiceList", "CanvasSource", "HbbtvApplication", "RdsDecoder", "RecordState", "Sensor", "EventInfo",
	"FrontendInfo", "ServiceInfo", "VideoSize", "OrderedList", "TunerInfo"}
GUI_TYPES = {"Label", "Button", "Pixmap", "MultiPixmap", "MenuList", "ConfigList", "ScrollLabel", "ProgressBar", "Slider",
	"ChoiceList", "FileList", "MultiFileSelectList", "SelectionList", "PluginList", "MultiContentList", "TimerList",
	"InputBox", "Input", "HelpMenuList", "ServiceList", "EPGList", "EPGListGrid", "EPGListMulti", "EPGListSingle", "MovieList",
	"ConfigSelectionList", "NimList", "HarddiskList", "PowerTimerList", "VideoWindow", "PiGDummy", "Pig", "Sources", "BlinkingPixmapConditional",
	"PixmapConditional", "LabelConditional", "ActionMap", "HelpableActionMap", "NumberActionMap", "HelpableNumberActionMap"}
ACTIONS = {"ActionMap", "HelpableActionMap", "NumberActionMap", "HelpableNumberActionMap", "ButtonSetupActionMap", "HelpableButtonSetupActionMap"}

CLASS_RE = re.compile(r"^class (\w+)(?:\(([^)]*)\))?:", re.M)
ASSIGN_RE = re.compile(r'self\[["\'](\w+)["\']\]\s*=\s*([\w.]+)')
DYN_RE = re.compile(r'self\[\s*["\'](\w+)["\']\s*(?:\+|%)')
INST_RE = re.compile(r'self\[["\'](\w+)["\']\]\.instance')


class Index:
	def __init__(self, pyroot):
		self.classes = {}
		for root, _, files in os.walk(pyroot):
			for fn in files:
				if not fn.endswith(".py"):
					continue
				text = open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read()
				ms = list(CLASS_RE.finditer(text))
				for i, m in enumerate(ms):
					body = text[m.end():ms[i + 1].start() if i + 1 < len(ms) else len(text)]
					bases = [b.strip().split(".")[-1] for b in (m.group(2) or "").split(",") if b.strip()]
					self.classes.setdefault(m.group(1), (bases, body))

	def bases(self, cls, seen=None):
		seen = seen or set()
		if cls in seen or cls not in self.classes:
			return seen
		seen.add(cls)
		for b in self.classes[cls][0]:
			self.bases(b, seen)
		return seen

	def info(self, cls):
		"""-> (components {name: type or None}, dynamic prefixes, names used with .instance) or None"""
		if cls not in self.classes:
			return None
		comps, dyn, inst = {}, set(), set()
		for c in self.bases(cls):
			body = self.classes[c][1]
			for k, v in ASSIGN_RE.findall(body):
				t = v.split(".")[-1]
				comps.setdefault(k, None if v.startswith("self.") else t)
			dyn |= set(DYN_RE.findall(body))
			inst |= set(INST_RE.findall(body))
		comps = {k: v for k, v in comps.items() if v not in ACTIONS}
		return comps, dyn, inst

	def derivesFrom(self, cls, base):
		return base in self.bases(cls) - {cls}
