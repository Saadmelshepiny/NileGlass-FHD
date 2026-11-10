# -*- coding: utf-8 -*-
# NileGlass FHD - online update from GitHub.
#
# version.json in the repository:
#   {"version": "1.4.0", "ipk": "https://.../enigma2-plugin-skins-nileglass-fhd_1.4.0_all.ipk",
#    "sha256": "...", "notes_ar": "...", "notes_en": "..."}
#
# Network work runs in a thread, results come back on the UI thread.
# The package is checked (size, sha256, ipk format) before opkg sees it.
# Your settings and TMDB key in /etc/enigma2/nileglass.conf are kept.

import hashlib
import json
import os
import threading
import time

REPO = "Saadmelshepiny/NileGlass-FHD"
VERSION_URL = "https://raw.githubusercontent.com/%s/main/version.json" % REPO
VERSION_FILE = "/usr/share/enigma2/NileGlass_FHD/version.txt"
DOWNLOAD = "/tmp/nileglass_update.ipk"


def installedVersion():
	try:
		with open(VERSION_FILE, "r") as f:
			return f.read().strip()
	except Exception:
		return "0"


def _tuple(v):
	out = []
	for part in str(v).split("."):
		digits = "".join(c for c in part if c.isdigit())
		out.append(int(digits) if digits else 0)
	return tuple(out + [0] * (3 - len(out)))


def isNewer(remote, local=None):
	return _tuple(remote) > _tuple(local or installedVersion())


def _ui(fnc, *args):
	try:
		from twisted.internet import reactor
		reactor.callFromThread(fnc, *args)
	except Exception:
		fnc(*args)


def checkAsync(callback):
	"""callback(info_or_None, error_or_None) on the UI thread."""
	def run():
		try:
			from Components.NileGlassCore import httpGet
			# the query string bypasses the GitHub CDN cache (it can serve an old file for minutes)
			info = json.loads(httpGet("%s?t=%d" % (VERSION_URL, int(time.time())), timeout=8, maxBytes=64 * 1024).decode("utf-8"))
			if not info.get("version") or not str(info.get("ipk", "")).startswith("https://"):
				raise ValueError("bad version.json")
			_ui(callback, info, None)
		except Exception as err:
			_ui(callback, None, str(err)[:120])
	threading.Thread(target=run, name="NileGlass-update", daemon=True).start()


def downloadAsync(info, callback):
	"""callback(path_or_None, error_or_None) on the UI thread."""
	def run():
		try:
			from Components.NileGlassCore import httpGet
			data = httpGet(info["ipk"], timeout=60, maxBytes=40 * 1024 * 1024)
			if not data.startswith(b"!<arch>\n"):
				raise ValueError("not an ipk package")
			want = (info.get("sha256") or "").lower()
			if want and hashlib.sha256(data).hexdigest() != want:
				raise ValueError("checksum mismatch")
			with open(DOWNLOAD, "wb") as f:
				f.write(data)
			_ui(callback, DOWNLOAD, None)
		except Exception as err:
			_ui(callback, None, str(err)[:120])
	threading.Thread(target=run, name="NileGlass-update", daemon=True).start()


def installCommand(path):
	return "opkg install --force-reinstall %s && rm -f %s" % (path, path)
