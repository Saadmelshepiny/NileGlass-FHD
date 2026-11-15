# -*- coding: utf-8 -*-
# NileGlass FHD - what the plugin screens show about the plugin under the
# cursor: version, package, install date, size, where it appears, whether it
# starts with the box, how often and when it was last opened, and whether the
# feed has another version.
#
# Everything slow (the package index, folder sizes) is read once in a
# background thread; the screen asks with info(descriptor) and gets what is
# known now, and is told (listeners) when more is known.  Opening a plugin is
# counted by a small wrapper around PluginDescriptor.__call__ (installUsage).

import glob
import gzip
import json
import os
import re
import threading
import time

OPKG_INFO = "/var/lib/opkg/info"
OPKG_STATUS = "/var/lib/opkg/status"
OPKG_LISTS = "/var/lib/opkg/lists"
PLUGIN_ROOT = "/usr/lib/enigma2/python/Plugins/"
USAGE_FILE = "/etc/enigma2/NileGlass_FHD/plugins_used.json"

_lock = threading.Lock()
_index = None          # plugin folder -> package name
_status = {}           # package -> {"Version": .., "Installed-Time": ..}
_feed = {}             # package -> version offered by the feeds
_feedFields = {}       # package -> all fields of the feed entry (size, depends ...)
_sizes = {}            # folder -> bytes
_loading = False
_loadedAt = 0
_listsSeen = None
_listeners = []
_usage = None
_usageDirty = False
_usageTimer = None

WHERE_NAMES = (   # (PluginDescriptor attribute, Arabic, English)
	("WHERE_PLUGINMENU", "قائمة الإضافات", "Plugins"),
	("WHERE_EXTENSIONSMENU", "الملحقات (الأزرق)", "Extensions"),
	("WHERE_MAINMENU", "القائمة الرئيسية", "Main menu"),
	("WHERE_MENU", "قوائم الإعدادات", "Setup menus"),
	("WHERE_CHANNEL_CONTEXT_MENU", "قائمة القنوات", "Channel list"),
	("WHERE_EVENTINFO", "دليل البرامج", "EPG"),
	("WHERE_MOVIELIST", "التسجيلات", "Recordings"),
	("WHERE_NETWORKSETUP", "إعدادات الشبكة", "Network setup"),
	("WHERE_SOFTWAREMANAGER", "مدير البرامج", "Software manager"),
)
BACKGROUND = ("WHERE_AUTOSTART", "WHERE_SESSIONSTART", "WHERE_NETWORKCONFIG_READ", "WHERE_RECORDTIMER", "WHERE_INFOBAR")


def _ar():
	try:
		from Components.NileGlassCore import confGet
		return confGet("style", "direction", "rtl") != "ltr"
	except Exception:
		return True


# ---------------------------------------------------------------- package data
def _folderOf(path):
	"""/usr/lib/enigma2/python/Plugins/Extensions/Foo/x.py -> .../Extensions/Foo"""
	if not path.startswith(PLUGIN_ROOT):
		return None
	parts = path[len(PLUGIN_ROOT):].split("/")
	if len(parts) < 2 or not parts[1]:
		return None
	return PLUGIN_ROOT + parts[0] + "/" + parts[1]


def _readIndex():
	index = {}
	for i, lst in enumerate(glob.glob(os.path.join(OPKG_INFO, "*.list"))):
		if i % 20 == 0:
			time.sleep(0.005)      # background work: the remote always goes first
		pkg = os.path.basename(lst)[:-5]
		try:
			with open(lst, encoding="utf-8", errors="ignore") as f:
				for line in f:
					if line.startswith(PLUGIN_ROOT):
						folder = _folderOf(line.split("\t")[0].strip())
						if folder and folder not in index:
							index[folder] = pkg
		except Exception:
			pass
	return index


def _readStanzas(text):
	out = {}
	for n, block in enumerate(text.split("\n\n")):
		if n % 300 == 299:
			time.sleep(0.003)
		fields = {}
		for line in block.split("\n"):
			if ":" in line and not line.startswith(" "):
				k, v = line.split(":", 1)
				fields[k.strip()] = v.strip()
		if fields.get("Package"):
			out[fields["Package"]] = fields
	return out


def _readFeeds():
	feed = {}
	fields_ = {}
	for path in glob.glob(os.path.join(OPKG_LISTS, "*")):
		try:
			with open(path, "rb") as f:
				raw = f.read()
			if raw[:2] == b"\x1f\x8b":
				raw = gzip.decompress(raw)
			time.sleep(0.01)
			for pkg, fields in _readStanzas(raw.decode("utf-8", "ignore")).items():
				if fields.get("Version"):
					feed[pkg] = fields["Version"]
					fields_[pkg] = {k: fields[k] for k in ("Version", "Size", "Installed-Size", "Depends", "Section", "Description", "Maintainer") if k in fields}
		except Exception:
			pass
	_feedFields.clear()
	_feedFields.update(fields_)
	return feed


def _folderSize(folder):
	total = 0
	for root, dirs, files in os.walk(folder):
		time.sleep(0.001)
		for fn in files:
			try:
				total += os.path.getsize(os.path.join(root, fn))
			except OSError:
				pass
	return total


def _load(folders):
	global _index, _status, _feed, _loading, _loadedAt, _listsSeen
	try:
		try:
			_listsSeen = os.path.getmtime(OPKG_LISTS)
		except Exception:
			_listsSeen = None
		index = _readIndex()
		try:
			with open(OPKG_STATUS, encoding="utf-8", errors="ignore") as f:
				status = _readStanzas(f.read())
		except Exception:
			status = {}
		feed = _readFeeds()
		with _lock:
			_index, _status, _feed = index, status, feed
			_loadedAt = time.time()
		_notify()
		for folder in folders:
			if folder not in _sizes:
				_sizes[folder] = _folderSize(folder)
		_notify()
	except Exception as err:
		print("[NileGlass] plugin info:", err)
	finally:
		_loading = False


def _notify():
	try:
		from Components.NileGlassCore import callInUiThread
	except Exception:
		callInUiThread = None
	for fnc in list(_listeners):
		try:
			if callInUiThread:
				callInUiThread(fnc)
			else:
				fnc()
		except Exception:
			pass


def prepare(folders=None):
	"""start reading the package data in the background (once per GUI start);
	folders None: the folders of every plugin"""
	global _loading, _index
	try:   # the feeds were updated (download browser): read again - at most every 5 minutes
		m = os.path.getmtime(OPKG_LISTS)
		if _index is not None and m != _listsSeen and time.time() - _loadedAt > 300:
			_index = None
	except Exception:
		pass
	if folders is None:
		folders = sorted(set(p.path for p in _allPlugins() if getattr(p, "path", None)))
	if _loading or (_index is not None and all(f in _sizes for f in folders)):
		return
	_loading = True
	t = threading.Thread(target=_load, args=(list(folders),), name="NGPluginInfo")
	t.daemon = True
	t.start()


def addListener(fnc):
	if fnc not in _listeners:
		_listeners.append(fnc)


def removeListener(fnc):
	if fnc in _listeners:
		_listeners.remove(fnc)


# ---------------------------------------------------------------- usage
def _loadUsage():
	global _usage
	if _usage is None:
		try:
			with open(USAGE_FILE, encoding="utf-8") as f:
				_usage = json.load(f)
		except Exception:
			_usage = {}
	return _usage


def _saveUsage():
	global _usageDirty
	if not _usageDirty:
		return
	_usageDirty = False
	try:
		os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
		tmp = USAGE_FILE + ".tmp"
		with open(tmp, "w", encoding="utf-8") as f:
			json.dump(_usage, f)
		os.replace(tmp, USAGE_FILE)
	except Exception as err:
		print("[NileGlass] plugin usage:", err)


def keyOf(desc):
	return getattr(desc, "path", None) or ("name:" + str(getattr(desc, "name", "")))


def countRun(desc, now=None):
	global _usageDirty, _usageTimer
	use = _loadUsage()
	k = keyOf(desc)
	n, _ = use.get(k, (0, 0))
	use[k] = (n + 1, int(now or time.time()))
	_usageDirty = True
	try:
		from enigma import eTimer
		if _usageTimer is None:
			_usageTimer = eTimer()
			_usageTimer.callback.append(_saveUsage)
		_usageTimer.start(4000, True)     # written a little later: never in the way of the plugin opening
	except Exception:
		_saveUsage()


def installUsage():
	"""count every opening of a plugin from a plugin list, the green panel, the blue button ..."""
	try:
		from Plugins.Plugin import PluginDescriptor
	except Exception:
		return
	if getattr(PluginDescriptor, "_ngCounted", False):
		return
	user = set(getattr(PluginDescriptor, w) for w in ("WHERE_PLUGINMENU", "WHERE_EXTENSIONSMENU", "WHERE_MAINMENU") if hasattr(PluginDescriptor, w))
	orig = PluginDescriptor.__call__

	def __call__(self, *args, **kwargs):
		try:
			if "session" in kwargs or (args and hasattr(args[0], "openWithCallback")):
				if user.intersection(self.where):
					countRun(self)
		except Exception:
			pass
		return orig(self, *args, **kwargs)
	PluginDescriptor.__call__ = __call__
	PluginDescriptor._ngCounted = True


# ---------------------------------------------------------------- the answer
def _ago(ts, ar):
	if not ts:
		return "لسه متفتحش" if ar else "never"
	d = int(time.time() - ts)
	if d < 60:
		return "دلوقتي" if ar else "just now"
	if d < 3600:
		return ("من %d دقيقة" if ar else "%d min ago") % (d // 60)
	if d < 86400:
		return ("من %d ساعة" if ar else "%d h ago") % (d // 3600)
	if d < 86400 * 30:
		return ("من %d يوم" if ar else "%d days ago") % (d // 86400)
	return time.strftime("%d/%m/%Y", time.localtime(ts))


def _size(n):
	if n is None:
		return "…"
	if n < 1024 * 1024:
		return "%d KB" % max(1, n // 1024)
	return "%.1f MB" % (n / 1048576.0)


VERSION_RE = re.compile(r"""(?:^|\b)(?:__version__|VERSION|PLUGIN_VERSION|version|Version)\s*[=:]\s*["']?v?(\d+(?:\.\d+){0,3}[\w\-.]*)""", re.M)
DESC_VERSION_RE = re.compile(r"\bv(?:er(?:sion)?)?\.?\s*(\d+(?:\.\d+){1,3})\b", re.I)


def _versionFromFiles(folder, desc):
	for name in ("version", "version.txt", "VERSION", "__init__.py", "plugin.py", "version.py"):
		path = os.path.join(folder, name)
		try:
			with open(path, encoding="utf-8", errors="ignore") as f:
				text = f.read(65536)
		except Exception:
			continue
		if name.lower().startswith("version") and not name.endswith(".py"):
			v = text.strip().split()[0] if text.strip() else ""
			if re.match(r"v?\d", v):
				return v.lstrip("v")
		m = VERSION_RE.search(text)
		if m:
			return m.group(1)
	m = DESC_VERSION_RE.search(getattr(desc, "description", "") or "")
	return m.group(1) if m else ""


def _shortVersion(v):
	v = v.split(":", 1)[-1]                       # epoch
	v = re.sub(r"\+git\d*\+?([0-9a-f]{7})[0-9a-f]*", r"+\1", v)
	return v[:22]


_cache = {}


def info(desc, plugins=None):
	"""-> dict of display texts for this plugin (what is known now)"""
	ar = _ar()
	folder = getattr(desc, "path", None) or ""
	key = (folder, getattr(desc, "name", ""), _index is not None, folder in _sizes)
	if key in _cache and _cache[key][0] > time.time() - 30:
		out = dict(_cache[key][1])
	else:
		out = {}
		pkg = (_index or {}).get(folder, "") if folder else ""
		st = _status.get(pkg, {}) if pkg else {}
		ctrl = {}
		if pkg:
			try:
				with open(os.path.join(OPKG_INFO, pkg + ".control"), encoding="utf-8", errors="ignore") as f:
					ctrl = list(_readStanzas(f.read()).values())[0] if f else {}
			except Exception:
				ctrl = {}
		version = st.get("Version") or ctrl.get("Version") or (_versionFromFiles(folder, desc) if folder else "")
		out["version"] = _shortVersion(version) if version else "—"
		out["package"] = pkg or ("مثبت يدوي (من غير حزمة)" if ar else "installed by hand (no package)") if _index is not None else "…"
		maint = (ctrl.get("Maintainer") or "").split("<")[0].strip()
		out["maker"] = maint[:40] if maint else "—"
		when = st.get("Installed-Time")
		try:
			when = int(when) if when else (int(os.path.getmtime(folder)) if folder else 0)
		except Exception:
			when = 0
		out["installed"] = time.strftime("%d/%m/%Y", time.localtime(when)) if when else "—"
		out["size"] = _size(_sizes.get(folder)) if folder else "—"
		feedV = _feed.get(pkg, "") if pkg else ""
		if not pkg:
			out["feed"] = "—"
		elif not feedV:
			out["feed"] = ("مش في الفيد" if ar else "not in the feeds") if _feed else ("حدّث الفيد لمعرفة الجديد" if ar else "update the feeds to see")
		elif version and feedV != version:
			out["feed"] = (("فيه إصدار تاني: %s" if ar else "other version: %s") % _shortVersion(feedV))
		else:
			out["feed"] = "أحدث إصدار" if ar else "up to date"
		kind = []
		if folder:
			sub = folder[len(PLUGIN_ROOT):].split("/")[0] if folder.startswith(PLUGIN_ROOT) else ""
			kind.append(("إضافة" if sub == "Extensions" else "نظام" if sub == "SystemPlugins" else sub) if ar else (sub or "?"))
			try:
				names = os.listdir(folder)
				py = any(n.endswith(".py") for n in names)
				pyc = any(n.endswith(".pyc") for n in names) or os.path.isdir(os.path.join(folder, "__pycache__"))
				so = any(n.endswith(".so") for n in names)
				if not py and pyc:
					kind.append("مقفول (pyc)" if ar else "compiled")
				elif py:
					kind.append("مفتوح المصدر" if ar else "source")
				if so:
					kind.append("فيه مكتبات" if ar else "native")
			except Exception:
				pass
		out["kind"] = " · ".join(kind) or "—"
		out["folder"] = folder.replace(PLUGIN_ROOT, "") or "—"
		_cache[key] = (time.time(), dict(out))
	# where it shows up / starts with the box (all descriptors of the same folder)
	places, background = [], False
	try:
		from Plugins.Plugin import PluginDescriptor
		allp = plugins if plugins is not None else _allPlugins()
		same = [p for p in allp if folder and getattr(p, "path", None) == folder] or [desc]
		wheres = set()
		for p in same:
			wheres.update(getattr(p, "where", []) or [])
		for attr, a, e in WHERE_NAMES:
			if hasattr(PluginDescriptor, attr) and getattr(PluginDescriptor, attr) in wheres:
				places.append(a if ar else e)
		background = any(hasattr(PluginDescriptor, w) and getattr(PluginDescriptor, w) in wheres for w in BACKGROUND)
	except Exception:
		pass
	out["places"] = " · ".join(places) or "—"
	out["background"] = ("نعم، بيشتغل مع الجهاز" if ar else "yes, starts with the box") if background else ("لأ، بس لما تفتحه" if ar else "no, only when opened")
	use = _loadUsage().get(keyOf(desc))
	n, last = use if use else (0, 0)
	out["runs"] = str(n) if n else "0"
	out["last"] = _ago(last, ar)
	out["name"] = getattr(desc, "name", "") or ""
	out["description"] = getattr(desc, "description", "") or ""
	return out


def _allPlugins():
	try:
		from Components.PluginComponent import plugins
		return plugins.pluginList
	except Exception:
		return []


# ---------------------------------------------------------------- packages not installed yet (download browser)
def _pkgName(desc):
	name = getattr(desc, "name", "") or ""
	for cand in (name, "enigma2-plugin-" + name, "enigma2-plugin-extensions-" + name, "enigma2-plugin-systemplugins-" + name):
		if cand in _feedFields or cand in _status:
			return cand
	return name


def _installed(pkg):
	st = _status.get(pkg, {})
	return "installed" in st.get("Status", "") or (st.get("Version") and "Status" not in st)


def _freeFlash():
	try:
		s = os.statvfs("/")
		return s.f_bavail * s.f_frsize
	except Exception:
		return 0


def pkgInfo(desc):
	"""what the cards beside the package list show for the package under the cursor"""
	ar = _ar()
	pkg = _pkgName(desc)
	f = _feedFields.get(pkg, {})
	out = {"name": pkg or "—", "description": f.get("Description") or getattr(desc, "description", "") or ""}
	out["pkgversion"] = _shortVersion(f["Version"]) if f.get("Version") else "—"
	size = int(f["Size"]) if f.get("Size", "").isdigit() else 0
	inst = int(f["Installed-Size"]) if f.get("Installed-Size", "").isdigit() else 0
	out["pkgsize"] = _size(size) if size else ("…" if _index is None else "—")
	if _installed(pkg):
		v = _status.get(pkg, {}).get("Version", "")
		out["pkgstate"] = ("متثبتة %s" % _shortVersion(v)) if ar else ("installed %s" % _shortVersion(v))
	else:
		out["pkgstate"] = "جديدة" if ar else "new"
	free = _freeFlash()
	out["free"] = _size(free) if free else "—"
	need = inst or size * 3          # unpacked, roughly
	if not size and not inst:
		out["after"] = "—"
	elif free and need >= free:
		out["after"] = "المساحة مش هتكفي" if ar else "not enough space"
	else:
		out["after"] = (("يفضل حوالي %s" if ar else "about %s left") % _size(free - need)) if free else "—"
	deps = [d.strip().split(" ")[0] for d in f.get("Depends", "").split(",") if d.strip()]
	missing = [d for d in deps if not _installed(d)]
	if not deps:
		out["depends"] = "مفيش" if ar else "none"
	elif not missing:
		out["depends"] = ("%d حزمة، كلها متثبتة" if ar else "%d, all installed") % len(deps)
	else:
		out["depends"] = (("هتنزل معاها %d: %s" if ar else "brings %d: %s") % (len(missing), ", ".join(m.replace("enigma2-plugin-", "")[:24] for m in missing[:3])))
	out["section"] = f.get("Section", "—") or "—"
	out["maker"] = (f.get("Maintainer") or "").split("<")[0].strip()[:40] or "—"
	return out
