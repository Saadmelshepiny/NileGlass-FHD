# -*- coding: utf-8 -*-
# NileGlass FHD - the settings screen beside the cards: the option under the
# cursor (its value, default and choices), how many options differ from the
# defaults, and which plugin the screen belongs to (with its version).
#   <widget source="ctx" render="Label"><convert type="NGHostInfo">Value</convert></widget>
#   Item, Value, Default, Choices, Kind, Total, Changed, Owner, OwnerVersion, OwnerPackage, OwnerInstalled

from Components.Converter.Converter import Converter
from Components.Element import cached

PLUGIN_ROOT = "/usr/lib/enigma2/python/Plugins/"


def entry(host):
	try:
		cur = host["config"].getCurrent()
		return cur if cur and len(cur) > 1 and hasattr(cur[1], "value") else None
	except Exception:
		return None


def valueText(elem, value=None):
	if value is None:
		value = elem.value
	try:
		desc = getattr(elem, "description", None)
		if isinstance(desc, dict) and value in desc:
			return str(desc[value])
		choices = getattr(getattr(elem, "choices", None), "choices", None)
		if choices:
			for c in choices:
				if (c[0] if isinstance(c, (tuple, list)) else c) == value:
					return str(c[1] if isinstance(c, (tuple, list)) and len(c) > 1 else c)
	except Exception:
		pass
	if isinstance(value, bool):
		return "نعم" if value else "لأ"
	if isinstance(value, (list, tuple)):
		return ".".join(str(v) for v in value) if all(isinstance(v, int) for v in value) else ", ".join(str(v) for v in value)
	return str(value)


def choicesText(elem):
	try:
		choices = getattr(getattr(elem, "choices", None), "choices", None)
		if choices:
			return [str(c[1] if isinstance(c, (tuple, list)) and len(c) > 1 else c) for c in choices]
	except Exception:
		pass
	if isinstance(getattr(elem, "value", None), bool):
		return ["نعم", "لأ"]
	lim = getattr(elem, "limits", None)
	if lim:
		try:
			return ["من %s لحد %s" % (lim[0][0], lim[0][1])]
		except Exception:
			pass
	return []


def kindText(elem):
	n = elem.__class__.__name__
	return {"ConfigYesNo": "نعم / لأ", "ConfigBoolean": "نعم / لأ", "ConfigOnOff": "شغال / مقفول", "ConfigEnableDisable": "مفعّل / مقفول", "ConfigText": "كتابة", "ConfigPassword": "كلمة سر",
		"ConfigIP": "عنوان IP", "ConfigInteger": "رقم", "ConfigNumber": "رقم", "ConfigClock": "ساعة", "ConfigSlider": "شريط", "ConfigSelectionNumber": "رقم من قائمة",
		"ConfigDirectory": "مجلد", "ConfigSelection": "اختيار من قائمة", "ConfigSet": "أكتر من اختيار"}.get(n, n.replace("Config", ""))


def owner(host):
	"""(name, folder) of the plugin the screen comes from, or (None, None)"""
	mod = getattr(host.__class__, "__module__", "") or ""
	parts = mod.split(".")
	if len(parts) >= 3 and parts[0] == "Plugins":
		return parts[2], PLUGIN_ROOT + parts[1] + "/" + parts[2]
	return None, None


class NGHostInfo(Converter):
	def __init__(self, arg):
		Converter.__init__(self, arg)
		self.type = (arg or "Item").strip()
		self.hooked = None

	def hook(self, host):
		if host is not self.hooked:
			self.hooked = host
			try:
				cb = self.selChanged
				lst = host["config"].onSelectionChanged
				if cb not in lst:
					lst.append(cb)
			except Exception:
				pass

	def selChanged(self):
		self.downstream_elements.changed((self.CHANGED_ALL, 0))

	@cached
	def getText(self):
		host = getattr(self.source, "host", None)
		if host is None:
			return ""
		self.hook(host)
		t = self.type
		try:
			if t in ("Item", "Value", "Default", "Choices", "Kind"):
				e = entry(host)
				if e is None:
					return ""
				label, elem = str(e[0]).strip(), e[1]
				if t == "Item":
					return label
				if t == "Value":
					return valueText(elem)
				if t == "Default":
					d = getattr(elem, "default", None)
					if d is None:
						return "—"
					return valueText(elem, d) + ("  (زي ما هو)" if d == elem.value else "")
				if t == "Kind":
					return kindText(elem)
				ch = choicesText(elem)
				return " · ".join(ch[:14]) + (" …" if len(ch) > 14 else "") if ch else "تكتبها بنفسك"
			if t in ("Total", "Changed"):
				items = [x for x in (host["config"].list or []) if len(x) > 1 and hasattr(x[1], "value")]
				if t == "Total":
					return str(len(items))
				n = sum(1 for x in items if getattr(x[1], "default", x[1].value) != x[1].value)
				return str(n)
			if t.startswith("Owner"):
				name, folder = owner(host)
				if t == "Owner":
					return name or "OpenBh"
				if not folder:
					from Components.Converter.NGContext import systemInfo
					if t == "OwnerVersion":
						v, b = systemInfo("imageversion") or systemInfo("imgversion") or "", systemInfo("imagebuild") or ""
						return "%s.%s" % (v, b) if b else str(v)
					return ""
				from Components import NileGlassPlugins as P
				P.prepare([folder])

				class D:
					path = folder
					description = ""
				D.name = name
				info = P.info(D)
				return {"OwnerVersion": (info.get("version", "") or "").split("+")[0][:12], "OwnerPackage": info.get("package", ""), "OwnerInstalled": info.get("installed", "")}.get(t, "")
		except Exception as err:
			print("[NileGlass] NGHostInfo %s:" % t, err)
		return ""

	text = property(getText)
