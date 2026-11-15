# -*- coding: utf-8 -*-
# NileGlass FHD - what you watch: once a minute the playing channel gets a
# minute (not in standby), per day, the last 8 days kept.  Also which
# scrambled channels were opened today (the readers screen counts them).
# Shown for the channel under the cursor in the channel list (NGWatch).

import json
import os
import time

FILE = "/etc/enigma2/NileGlass_FHD/watch.json"
KEEP_DAYS = 8
TOP = 10

_data = None
_dirty = 0
_timer = None
_session = None
_rankCache = (0, None)


def _today(now=None):
	return time.strftime("%Y-%m-%d", time.localtime(now or time.time()))


def load():
	global _data
	if _data is None:
		try:
			with open(FILE, encoding="utf-8") as f:
				_data = json.load(f)
		except Exception:
			_data = {}
		_data.setdefault("days", {})
		_data.setdefault("crypt", {})
	return _data


def save():
	global _dirty
	if not _dirty:
		return
	_dirty = 0
	try:
		os.makedirs(os.path.dirname(FILE), exist_ok=True)
		tmp = FILE + ".tmp"
		with open(tmp, "w", encoding="utf-8") as f:
			json.dump(_data, f)
		os.replace(tmp, FILE)
	except Exception as err:
		print("[NileGlass] watch:", err)


def key(ref):
	"""1:0:19:3E9:3F8:FFFF:E080000:0:0:0: -> the part that names the channel"""
	s = ref.toString() if hasattr(ref, "toString") else str(ref or "")
	parts = s.split(":")
	if len(parts) >= 10 and not s.startswith("1:0:0:0:0:0:0:0:0:0"):
		if parts[1] == "0" and parts[3] != "0":
			return ":".join(parts[2:7]).upper()
		if "%3a" in s.lower() or "http" in s.lower():          # IPTV: the stream address is the channel
			return s.split(":", 10)[-1][:120]
	return None


def add(ref, seconds=60, crypted=False, now=None):
	global _dirty
	k = key(ref)
	if not k:
		return
	d = load()
	day = _today(now)
	bucket = d["days"].setdefault(day, {})
	bucket[k] = bucket.get(k, 0) + seconds
	if crypted:
		lst = d["crypt"].setdefault(day, [])
		if k not in lst:
			lst.append(k)
	for old in sorted(d["days"])[:-KEEP_DAYS]:
		del d["days"][old]
	for old in [x for x in d["crypt"] if x != day]:
		del d["crypt"][old]
	_dirty += 1


def week(k, now=None):
	"""seconds watched in the last 7 days"""
	d = load()
	since = _today((now or time.time()) - 6 * 86400)
	return sum(v.get(k, 0) for day, v in d["days"].items() if day >= since)


def ranking(now=None):
	"""channel keys by time watched this week, most first (cached a minute)"""
	global _rankCache
	t = now or time.time()
	if _rankCache[1] is not None and t - _rankCache[0] < 60:
		return _rankCache[1]
	d = load()
	since = _today(t - 6 * 86400)
	tot = {}
	for day, v in d["days"].items():
		if day >= since:
			for k, s in v.items():
				tot[k] = tot.get(k, 0) + s
	r = [k for k, s in sorted(tot.items(), key=lambda x: -x[1]) if s >= 600]
	_rankCache = (t, r)
	return r


def cryptToday():
	return len(load()["crypt"].get(_today(), []))


def _dur(s):
	h, m = s // 3600, (s % 3600) // 60
	if h:
		return "%d س %d د" % (h, m) if m else "%d س" % h
	return "%d د" % max(1, m)


def text(ref, now=None):
	k = key(ref)
	if not k:
		return ""
	s = week(k, now)
	if s < 60:
		return ""
	r = ranking(now)
	if k in r[:TOP]:
		return "الأكثر مشاهدة #%d · %s" % (r.index(k) + 1, _dur(s))
	return "شفتها %s الأسبوع ده" % _dur(s)


def _tick():
	try:
		from Screens.Standby import inStandby
		if inStandby is None and _session is not None:
			ref = _session.nav.getCurrentlyPlayingServiceReference()
			crypted = False
			try:
				from enigma import iServiceInformation
				svc = _session.nav.getCurrentService()
				info = svc and svc.info()
				crypted = bool(info and info.getInfo(iServiceInformation.sIsCrypted) == 1)
			except Exception:
				pass
			if ref is not None:
				add(ref, 60, crypted)
		if _dirty >= 10:      # written every ten minutes of watching
			save()
	except Exception as err:
		print("[NileGlass] watch:", err)


def start(session):
	global _timer, _session
	_session = session
	if _timer is not None:
		return
	try:
		from enigma import eTimer
		_timer = eTimer()
		_timer.callback.append(_tick)
		_timer.start(60000, False)
	except Exception as err:
		print("[NileGlass] watch:", err)
