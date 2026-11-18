# -*- coding: utf-8 -*-
# NileGlass FHD - after the GUI comes back from a crash: which one was to blame?
#
# enigma2 writes Enigma2_crash_<date>.log with its last log lines.  After every
# start the new crash logs are read once: the last Python traceback in them
# says which code failed (this skin, a plugin by name, or enigma2 itself).
#   * a crash caused by a plugin: a short note on the screen (nothing else);
#   * two crashes caused by the skin since its last update: the skin offers to
#     go back to the previous version - only when you say yes.
# The list is kept in /etc/enigma2/NileGlass_FHD/crashes.json and shown in the
# speed report and in Tools > Last crashes.  Nothing is deleted or changed.

import glob
import json
import os
import re
import time

STATE = "/etc/enigma2/NileGlass_FHD/crashes.json"
DIRS = ("/home/root/logs", "/home/root", "/media/hdd/logs", "/media/hdd", "/media/usb/logs", "/media/usb", "/tmp")
KEEP = 20
SKIN_MARKS = ("/NileGlassSetup/", "/Components/NileGlass", "/Converter/NG", "/Renderer/NG", "/Sources/NG")

_reStamp = re.compile(r"^<\s*[\d.]+>\s*")
_reFile = re.compile(r'File "([^"]+)", line (\d+)(?:, in (\S+))?')
_reError = re.compile(r"^([A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt|Warning))(?::\s*(.*))?$")


def debugDirs():
	dirs = []
	try:
		from Components.config import config
		dirs.append(config.crash.debug_path.value.rstrip("/"))
	except Exception:
		pass
	return [d for d in dict.fromkeys(dirs + list(DIRS)) if d and os.path.isdir(d)]


def crashFiles():
	out = []
	for d in debugDirs():
		out += glob.glob(os.path.join(d, "Enigma2_crash*.log")) + glob.glob(os.path.join(d, "enigma2_crash*.log"))
	out = list(dict.fromkeys(os.path.realpath(p) for p in out))
	out.sort(key=lambda p: os.path.getmtime(p))
	return out


def blameOf(path):
	"""Plugins/Extensions/Foo/x.py -> 'Foo'; skin files -> 'NileGlass'; else None"""
	if any(m in path for m in SKIN_MARKS):
		return "NileGlass"
	m = re.search(r"/Plugins/(?:Extensions|SystemPlugins)/([^/]+)/", path)
	return m.group(1) if m else None


def parse(text):
	"""-> dict(blame, error, where, component)"""
	lines = [_reStamp.sub("", l.rstrip("\n")) for l in text.splitlines()]
	comp = ""
	for l in lines[:40]:
		if l.startswith("Component ="):
			comp = l.split("=", 1)[1].strip()
			break
	start = None
	for i in range(len(lines) - 1, -1, -1):
		if lines[i].strip().startswith("Traceback (most recent call last)"):
			start = i
			break
	if start is None:
		return {"blame": "enigma2 (C++)" if comp else "?", "error": comp or "", "where": "", "component": comp}
	frames, error = [], ""
	for l in lines[start + 1:start + 120]:
		s = l.strip()
		m = _reFile.search(s)
		if m:
			frames.append((m.group(1), int(m.group(2)), m.group(3) or ""))
			continue
		e = _reError.match(s)
		if e and frames:
			error = s[:160]
			break
	blame, where = None, ""
	for path, line, fn in reversed(frames):         # the innermost code that is not enigma2's own
		b = blameOf(path)
		if b:
			blame, where = b, "%s:%d %s" % (os.path.basename(path), line, fn)
			break
	if not blame:
		blame = "enigma2"
		if frames:
			path, line, fn = frames[-1]
			where = "%s:%d %s" % (os.path.basename(path), line, fn)
	return {"blame": blame, "error": error, "where": where, "component": comp}


def load():
	try:
		with open(STATE, encoding="utf-8") as f:
			d = json.load(f)
	except Exception:
		d = {}
	d.setdefault("seen", [])
	d.setdefault("list", [])
	d.setdefault("asked", [])
	return d


def save(d):
	try:
		os.makedirs(os.path.dirname(STATE), exist_ok=True)
		tmp = STATE + ".tmp"
		with open(tmp, "w", encoding="utf-8") as f:
			json.dump(d, f, ensure_ascii=False)
		os.replace(tmp, STATE)
	except Exception as err:
		print("[NileGlass] crash guard:", err)


def installedVersion():
	try:
		from .updater import installedVersion as v
		return v()
	except Exception:
		return "?"


def scan(state=None, version=None):
	"""read the crash logs not seen before; -> (state, new entries)"""
	d = state if state is not None else load()
	version = version or installedVersion()
	new = []
	for p in crashFiles()[-KEEP:]:
		key = "%s|%d" % (p, int(os.path.getmtime(p)))
		if key in d["seen"]:
			continue
		d["seen"].append(key)
		try:
			with open(p, encoding="utf-8", errors="ignore") as f:
				info = parse(f.read(400000))
		except Exception:
			continue
		info.update(file=p, time=int(os.path.getmtime(p)), version=version)
		new.append(info)
		d["list"].append(info)
	d["seen"] = d["seen"][-60:]
	d["list"] = d["list"][-KEEP:]
	return d, new


def skinCrashes(d, version):
	return [c for c in d["list"] if c.get("blame") == "NileGlass" and c.get("version") == version]


def text(d=None, limit=8):
	"""the crash part of the speed report / the Last crashes screen"""
	d = d or load()
	rows = []
	for c in reversed(d["list"][-limit:]):
		who = "السكين NileGlass" if c["blame"] == "NileGlass" else ("إضافة %s" % c["blame"] if c["blame"] not in ("enigma2", "enigma2 (C++)", "?") else "إنيجما نفسها")
		rows.append("   %s   %s   (v%s)" % (time.strftime("%d/%m %H:%M", time.localtime(c.get("time", 0))), who, c.get("version", "?")))
		if c.get("error"):
			rows.append("      %s" % c["error"])
		if c.get("where"):
			rows.append("      %s" % c["where"])
	return rows or ["   مفيش كراش متسجل"]


def check(session, delay=20000):
	"""a while after the start: read new crash logs, tell what was found"""
	try:
		from enigma import eTimer
	except Exception:
		return

	def run():
		try:
			d, new = scan()
			version = installedVersion()
			save(d)
			if not new:
				return
			last = new[-1]
			mine = skinCrashes(d, version)
			if len(mine) >= 2 and version not in d["asked"]:
				d["asked"].append(version)
				save(d)
				ask(session, version, len(mine), last)
				return
			who = last["blame"]
			if who not in ("NileGlass", "enigma2", "enigma2 (C++)", "?"):
				from Tools import Notifications
				from Screens.MessageBox import MessageBox
				Notifications.AddPopup("الواجهة وقعت آخر مرة بسبب إضافة: %s\n%s" % (who, last.get("error", "")), MessageBox.TYPE_INFO, 12, "NileGlassCrash")
		except Exception as err:
			print("[NileGlass] crash guard:", err)
	t = eTimer()
	t.callback.append(run)
	t.start(delay, True)
	check._timer = t


def ask(session, version, count, last):
	try:
		from .plugin import checkForUpdate
		reason = "الواجهة وقعت %d مرات بسبب السكين من وقت ما اتحدّث لنسخة %s.\n%s\n\n" % (count, version, last.get("error", ""))
		checkForUpdate(session, quiet=False, previous=True, reason=reason)
	except Exception as err:
		print("[NileGlass] crash guard ask:", err)
