# -*- coding: utf-8 -*-
#
# NileGlass FHD skin - shared background services.
#
#   * PosterService  : finds / downloads event posters (TMDB) off the UI thread
#   * WeatherService : current weather from Open-Meteo (no API key needed)
#   * TonightService : films / matches of tonight from the Saad EPG plugin
#                      (/etc/enigma2/saadepg/tonight.json)
#   * EpgTitleMap    : Arabic -> English titles from the SaadEPG guide, used
#                      when TMDB does not know the Arabic EPG title
#
# Design rules (speed + stability):
#   - The enigma2 UI thread never touches the network and never touches a
#     possibly sleeping hard disk.  All file-system work for posters happens
#     in a worker thread; the UI only receives a ready file path.
#   - Exactly two worker threads for posters (local I/O + network) and one for
#     weather.  Queues are bounded, duplicate requests are merged.
#   - Results are handed back to the UI thread through twisted's
#     reactor.callFromThread, which is the thread-safe way in enigma2.
#   - Every network call has a short timeout and every error is caught; a
#     failure only means "no poster", never a crash.
#
# Settings live in /etc/enigma2/nileglass.conf (created on first start).

import gzip
import hashlib
import json
import os
import queue
import re
import ssl
import threading
import time
import unicodedata
from collections import deque
from configparser import ConfigParser
from urllib.parse import quote, urlencode
from urllib.error import URLError
from urllib.request import Request, urlopen

CONF_FILE = "/etc/enigma2/nileglass.conf"
USER_AGENT = "Mozilla/5.0 (Enigma2; NileGlass skin)"

DEFAULT_CONF = """# NileGlass FHD skin settings
# Restart the GUI after changing this file.

[tmdb]
# Free key from https://www.themoviedb.org/settings/api
# Either the short "API Key (v3 auth)" or the long "API Read Access Token" works.
api_key =
# Language used for the TMDB search (ar, en, fr, de, tr ...)
language = ar
# Set to 0 to switch off poster downloading completely
enabled = 1
# Optional free OMDb key (https://www.omdbapi.com/apikey.aspx) for IMDb ratings
omdb_key =

[posters]
# Where downloaded posters are kept. "auto" = first writable /media/hdd,
# /media/usb, /media/mmc ... and /tmp as last resort (RAM, cleared on reboot).
cache_dir = auto
# Maximum number of posters kept in the cache
max_files = 600
# Poster quality: w342 (fast) or w500 (sharper, bigger files)
quality = w342
# Download posters of the coming programmes of all bouquets once a day
prefetch = 1
# Hour of the daily download (0-23), done while nothing else is downloading
prefetch_hour = 4
# Use the English titles of the SaadEPG guide when the Arabic title is not
# found on TMDB (downloaded once a day, about 0.8 MB)
epg_titles = 1
epg_titles_url = https://raw.githubusercontent.com/Saadmelshepiny/saadepg-data/epg
# Download the posters of the channels around the selected one in the
# channel list, so they are ready when you move to them
neighbours = 1
# Translate programme descriptions (not titles) to Arabic
translate_epg = 1
# No film posters for matches / sport (TMDB has none and would guess wrong)
smart_sport = 1

[weather]
# City from the built-in list (alexandria, cairo, giza, riyadh, dubai ...),
# or "custom" to use the name / coordinates below.
city_id = alexandria
city = Alexandria
latitude =
longitude =
# C or F
units = C
# Set to 0 to switch weather off
enabled = 1

[tonight]
# File written by the Saad EPG plugin (films and matches of tonight)
file = /etc/enigma2/saadepg/tonight.json

[update]
# Check GitHub once a day for a new version of the skin (1/0)
auto = 1

[style]
# full or compact infobar
infobar = full
# blue, gold, green, red, purple, orange, cyan
accent = blue
# background transparency in percent: 10, 20, 30, 40, 50
transparency = 20
# ubuntu, tajawal, almarai, cairo, kufi
font = ubuntu
# text size in percent: 90, 100, 110, 120
font_size = 100
"""

# Built-in weather cities: id -> (Arabic name, English name, latitude, longitude)
CITIES = {
	"alexandria": ("الإسكندرية", "Alexandria", 31.2001, 29.9187),
	"cairo": ("القاهرة", "Cairo", 30.0444, 31.2357),
	"giza": ("الجيزة", "Giza", 30.0131, 31.2089),
	"port_said": ("بورسعيد", "Port Said", 31.2653, 32.3019),
	"suez": ("السويس", "Suez", 29.9668, 32.5498),
	"ismailia": ("الإسماعيلية", "Ismailia", 30.5965, 32.2715),
	"damietta": ("دمياط", "Damietta", 31.4165, 31.8133),
	"mansoura": ("المنصورة", "Mansoura", 31.0409, 31.3785),
	"tanta": ("طنطا", "Tanta", 30.7865, 31.0004),
	"zagazig": ("الزقازيق", "Zagazig", 30.5877, 31.5020),
	"damanhur": ("دمنهور", "Damanhur", 31.0341, 30.4682),
	"kafr_el_sheikh": ("كفر الشيخ", "Kafr El Sheikh", 31.1107, 30.9388),
	"shibin_el_kom": ("شبين الكوم", "Shibin El Kom", 30.5503, 31.0106),
	"banha": ("بنها", "Banha", 30.4660, 31.1848),
	"marsa_matruh": ("مرسى مطروح", "Marsa Matruh", 31.3543, 27.2373),
	"el_alamein": ("العلمين", "El Alamein", 30.8335, 28.9545),
	"arish": ("العريش", "Arish", 31.1316, 33.7984),
	"sharm_el_sheikh": ("شرم الشيخ", "Sharm El Sheikh", 27.9158, 34.3300),
	"hurghada": ("الغردقة", "Hurghada", 27.2579, 33.8116),
	"fayoum": ("الفيوم", "Fayoum", 29.3084, 30.8428),
	"beni_suef": ("بني سويف", "Beni Suef", 29.0661, 31.0994),
	"minya": ("المنيا", "Minya", 28.1099, 30.7503),
	"asyut": ("أسيوط", "Asyut", 27.1783, 31.1859),
	"sohag": ("سوهاج", "Sohag", 26.5591, 31.6957),
	"qena": ("قنا", "Qena", 26.1551, 32.7160),
	"luxor": ("الأقصر", "Luxor", 25.6872, 32.6396),
	"aswan": ("أسوان", "Aswan", 24.0889, 32.8998),
	"riyadh": ("الرياض", "Riyadh", 24.7136, 46.6753),
	"jeddah": ("جدة", "Jeddah", 21.4858, 39.1925),
	"mecca": ("مكة المكرمة", "Mecca", 21.3891, 39.8579),
	"medina": ("المدينة المنورة", "Medina", 24.5247, 39.5692),
	"dammam": ("الدمام", "Dammam", 26.4207, 50.0888),
	"dubai": ("دبي", "Dubai", 25.2048, 55.2708),
	"abu_dhabi": ("أبوظبي", "Abu Dhabi", 24.4539, 54.3773),
	"sharjah": ("الشارقة", "Sharjah", 25.3463, 55.4209),
	"kuwait": ("الكويت", "Kuwait City", 29.3759, 47.9774),
	"doha": ("الدوحة", "Doha", 25.2854, 51.5310),
	"manama": ("المنامة", "Manama", 26.2285, 50.5860),
	"muscat": ("مسقط", "Muscat", 23.5880, 58.3829),
	"amman": ("عمّان", "Amman", 31.9454, 35.9284),
	"jerusalem": ("القدس", "Jerusalem", 31.7683, 35.2137),
	"gaza": ("غزة", "Gaza", 31.5017, 34.4668),
	"beirut": ("بيروت", "Beirut", 33.8938, 35.5018),
	"damascus": ("دمشق", "Damascus", 33.5138, 36.2765),
	"baghdad": ("بغداد", "Baghdad", 33.3152, 44.3661),
	"sanaa": ("صنعاء", "Sanaa", 15.3694, 44.1910),
	"khartoum": ("الخرطوم", "Khartoum", 15.5007, 32.5599),
	"tripoli": ("طرابلس", "Tripoli", 32.8872, 13.1913),
	"benghazi": ("بنغازي", "Benghazi", 32.1167, 20.0667),
	"tunis": ("تونس", "Tunis", 36.8065, 10.1815),
	"algiers": ("الجزائر", "Algiers", 36.7538, 3.0588),
	"rabat": ("الرباط", "Rabat", 34.0209, -6.8416),
	"casablanca": ("الدار البيضاء", "Casablanca", 33.5731, -7.5898),
	"nouakchott": ("نواكشوط", "Nouakchott", 18.0735, -15.9582),
	"istanbul": ("إسطنبول", "Istanbul", 41.0082, 28.9784),
	"london": ("لندن", "London", 51.5074, -0.1278),
	"paris": ("باريس", "Paris", 48.8566, 2.3522),
	"berlin": ("برلين", "Berlin", 52.5200, 13.4050),
	"new_york": ("نيويورك", "New York", 40.7128, -74.0060),
}

# Folders where other popular plugins keep posters.  Matching files there are
# reused so nothing is downloaded twice.
FOREIGN_DIRS = (
	"xtraEvent/poster",
	"poster",
	"posters",
	"AglarePosterX/poster",
	"NileGlass/poster",
)
MOUNTS = ("/media/hdd", "/media/usb", "/media/mmc", "/media/usb2", "/media/sdcard")

# Titles that never have a meaningful poster.  Saves pointless requests.
# SKIP_EXACT: the whole cleaned title equals the word.
# SKIP_PREFIX: the cleaned title starts with the word/phrase.
SKIP_EXACT = (
	"news", "nachrichten", "weather", "live", "bulletin", "headlines", "football", "soccer",
	"highlights", "teleshopping", "ads", "promo", "tba", "no epg", "no information",
	"to be announced", "match",
)
SKIP_PREFIX = (
	"breaking news", "news at", "world news", "live:",
	"اخبار", "أخبار", "الأخبار", "الاخبار", "نشرة", "موجز", "الطقس", "مباشر", "بث مباشر",
	"اذان", "أذان", "الأذان", "قرآن", "القرآن", "تلاوة", "صلاة", "خطبة", "دعاء",
	"مباراة", "الدوري", "كأس", "تيليشوبينج", "اعلان", "إعلان", "فاصل", "لا توجد معلومات",
)

PREFIXES = (
	"فيلم", "الفيلم", "فلم", "مسلسل", "المسلسل", "برنامج", "البرنامج", "سهرة", "عرض أول", "عرض اول",
	"film", "movie", "series", "serie", "série", "the movie", "documentary", "وثائقي",
)


RECENT_ERRORS = deque(maxlen=20)  # shown by the diagnostics screen


def log(*args):
	msg = " ".join(str(a) for a in args)
	print("[NileGlass]", msg)
	if "error" in msg.lower() or "fail" in msg.lower():
		RECENT_ERRORS.append(time.strftime("%H:%M:%S ") + msg[:160])


# ------------------------------------------------------------------ config
def loadConfig():
	cp = ConfigParser()
	try:
		if not os.path.isfile(CONF_FILE):
			with open(CONF_FILE, "w", encoding="utf-8") as f:
				f.write(DEFAULT_CONF)
		cp.read(CONF_FILE, encoding="utf-8")
	except Exception as err:
		log("config error:", err)
	defaults = ConfigParser()
	defaults.read_string(DEFAULT_CONF)
	for section in defaults.sections():
		if not cp.has_section(section):
			cp.add_section(section)
		for key, value in defaults.items(section):
			if not cp.has_option(section, key):
				cp.set(section, key, value)
	return cp


CONFIG = loadConfig()


def confGet(section, key, default=""):
	try:
		value = CONFIG.get(section, key).strip()
		return value if value != "" else default
	except Exception:
		return default


def confBool(section, key, default=True):
	return confGet(section, key, "1" if default else "0").lower() in ("1", "true", "yes", "on")


def liteMode():
	"""Lite mode (one switch in the settings): no poster downloads, no
	translation, no weather - the saved settings of each stay as they are and
	come back when lite mode is switched off."""
	return confBool("style", "lite", False)


# ------------------------------------------------------------------ helpers
def callInUiThread(fnc, *args):
	"""Run fnc(*args) on the enigma2 main loop."""
	try:
		from twisted.internet import reactor
		reactor.callFromThread(fnc, *args)
	except Exception as err:
		log("callFromThread failed:", err)


_sslContext = None


# ---------------------------------------------------------------- circuit breaker
# A server that failed 3 times in a row is left alone for 10 minutes: no
# waiting on timeouts while the internet or that service is down.
_breaker = {}
BREAK_AFTER = 3
BREAK_FOR = 600


def _host(url):
	try:
		return url.split("/")[2].lower()
	except IndexError:
		return url


def hostBlocked(url):
	b = _breaker.get(_host(url))
	return bool(b and b[1] > time.time())


def httpGet(url, headers=None, timeout=8, maxBytes=3 * 1024 * 1024):
	"""Small, safe HTTP GET returning bytes (or raises)."""
	host = _host(url)
	b = _breaker.get(host)
	if b and b[1] > time.time():
		raise IOError("%s paused after errors (circuit breaker)" % host)
	try:
		data = _httpGet(url, headers, timeout, maxBytes)
	except Exception as err:
		code = getattr(err, "code", None)
		if code is None or code >= 500 or code == 429:  # network / server trouble, not "not found"
			fails = (b[0] if b else 0) + 1
			_breaker[host] = (fails, time.time() + BREAK_FOR if fails >= BREAK_AFTER else 0)
			if fails >= BREAK_AFTER:
				log("%s: %d errors, paused for %d min" % (host, fails, BREAK_FOR // 60))
		raise
	_breaker.pop(host, None)
	return data


def _httpGet(url, headers=None, timeout=8, maxBytes=3 * 1024 * 1024):
	global _sslContext
	hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
	if headers:
		hdrs.update(headers)
	req = Request(url, headers=hdrs)
	try:
		try:
			resp = urlopen(req, timeout=timeout, context=_sslContext)
		except URLError as err:  # urllib wraps TLS errors
			if isinstance(getattr(err, "reason", None), ssl.SSLError):
				raise err.reason
			raise
	except ssl.SSLError as err:
		# Some images ship without an up-to-date CA bundle. The data fetched
		# here is public (posters, weather), so fall back to an unverified
		# context instead of losing the feature.
		if _sslContext is None and "CERTIFICATE_VERIFY_FAILED" in str(err):
			log("TLS verification unavailable on this image, using unverified context for public data")
			_sslContext = ssl._create_unverified_context()
			resp = urlopen(req, timeout=timeout, context=_sslContext)
		else:
			raise
	with resp:
		data = resp.read(maxBytes + 1)
	if len(data) > maxBytes:
		raise ValueError("response too large")
	return data


def isLocalMount(path):
	"""True when path lives on a local block device (not nfs/cifs/autofs)."""
	try:
		best, fstype = "", ""
		with open("/proc/mounts", "r") as f:
			for line in f:
				parts = line.split()
				if len(parts) > 2 and path.startswith(parts[1]) and len(parts[1]) > len(best):
					best, fstype = parts[1], parts[2]
		return best not in ("", "/") and fstype not in ("nfs", "nfs4", "cifs", "smbfs", "autofs", "fuse.sshfs", "tmpfs")
	except Exception:
		return False


_reBrackets = re.compile(r"[\(\[\{].*?[\)\]\}]")
_reEpisode = re.compile(
	r"(?:\b(?:s\d{1,2}\s*e\d{1,3}|ep\.?\s*\d+|episode\s*\d+|season\s*\d+|part\s*\d+|folge\s*\d+|staffel\s*\d+)\b"
	r"|(?<!\S)(?:الحلقة|حلقة|ح|ج|الجزء|جزء|الموسم|موسم)\s*[\d٠-٩]+)",
	re.IGNORECASE)
_reYear = re.compile(r"\b(19|20)\d{2}\b")
_reJunk = re.compile(r"\b(?:hd|fhd|uhd|4k|premiere|rpt|repeat|إعادة|اعادة|جديد|حصريا|حصري)\b", re.IGNORECASE)
_reSpaces = re.compile(r"\s+")
_reUnsafe = re.compile(r"[\\/:*?\"<>|]+")


def _reArabicOnly(text):
	return bool(re.search("[\u0600-\u06ff]", text or ""))


def cleanTitle(name):
	"""Turn an EPG event name into a searchable title. '' means: no poster."""
	if not name:
		return ""
	t = unicodedata.normalize("NFKC", name)
	t = t.replace("‏", "").replace("‎", "")
	t = _reBrackets.sub(" ", t)
	t = _reEpisode.sub(" ", t)
	t = _reYear.sub(" ", t)
	t = _reJunk.sub(" ", t)
	# "مسلسل : الاختيار" / "Film: Inception" -> keep the part after the category word
	for sep in (":", " - ", " – ", "|"):
		if sep in t:
			head, tail = t.split(sep, 1)
			if head.strip().lower() in PREFIXES and tail.strip():
				t = tail
			elif len(head.strip()) >= 2:
				# a short subtitle is often part of the real title ("Mission: Impossible",
				# "Moja wina: Londyn"); keep it - the search falls back to the head alone
				words = tail.split()
				if sep == ":" and 0 < len(words) <= 4 and not _reArabicOnly(tail):
					t = "%s: %s" % (head.strip(), tail.strip())
				else:
					t = head
			break
	t = _reSpaces.sub(" ", t).strip(" -–.,:!؟?\"'")
	low = t.lower()
	for p in PREFIXES:
		if low.startswith(p + " ") and len(t) > len(p) + 2:
			t = t[len(p) + 1:].strip()
			low = t.lower()
			break
	if len(t) < 2:
		return ""
	if low in SKIP_EXACT:
		return ""
	for w in SKIP_PREFIX:
		if low == w or low.startswith(w + " "):
			return ""
	return t


def fileNameFor(title):
	"""File name used in the cache (compatible with xtraEvent style names)."""
	safe = _reUnsafe.sub(" ", title).strip()
	if len(safe.encode("utf-8")) > 150:
		safe = hashlib.md5(title.encode("utf-8")).hexdigest()
	return safe + ".jpg"


# ------------------------------------------------------------------ posters
GENRES_AR = {
	28: "أكشن", 12: "مغامرات", 16: "رسوم متحركة", 35: "كوميدي", 80: "جريمة", 99: "وثائقي", 18: "دراما",
	10751: "عائلي", 14: "فانتازيا", 36: "تاريخي", 27: "رعب", 10402: "موسيقى", 9648: "غموض", 10749: "رومانسي",
	878: "خيال علمي", 10770: "فيلم تلفزيوني", 53: "إثارة", 10752: "حرب", 37: "غرب أمريكي", 10759: "أكشن ومغامرات",
	10762: "أطفال", 10763: "أخبار", 10764: "واقع", 10765: "خيال علمي وفانتازيا", 10766: "دراما يومية",
	10767: "حواري", 10768: "حرب وسياسة",
}
GENRES_EN = {
	28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime", 99: "Documentary", 18: "Drama",
	10751: "Family", 14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music", 9648: "Mystery", 10749: "Romance",
	878: "Sci-Fi", 10770: "TV Movie", 53: "Thriller", 10752: "War", 37: "Western", 10759: "Action & Adventure",
	10762: "Kids", 10763: "News", 10764: "Reality", 10765: "Sci-Fi & Fantasy", 10766: "Soap", 10767: "Talk",
	10768: "War & Politics",
}
_reYearHint = re.compile(r"\b(19[3-9]\d|20[0-4]\d)\b")
_reArabic = re.compile(r"[؀-ۿ]")


def formatInfo(meta, fields=("year", "genres", "rating"), arabic=True, sep="  •  "):
	"""Turn stored TMDB metadata into one display line (UI thread, cheap)."""
	if not meta:
		return ""
	out = []
	for f in fields:
		if f == "year" and meta.get("year"):
			out.append(str(meta["year"]))
		elif f == "genres" and meta.get("genreNames"):          # TVmaze: genre names, not TMDB ids
			out.append(", ".join(meta["genreNames"][:3]))
		elif f == "genres" and meta.get("genres"):
			names = GENRES_AR if arabic else GENRES_EN
			g = [names[i] for i in meta["genres"] if i in names][:3]
			if g:
				out.append("، ".join(g) if arabic else ", ".join(g))
		elif f == "rating" and meta.get("rating"):
			out.append("%.1f/10" % meta["rating"])
		elif f == "type" and meta.get("type"):
			out.append(({"movie": "فيلم", "tv": "مسلسل"} if arabic else {"movie": "Movie", "tv": "Series"}).get(meta["type"], ""))
		elif f == "overview" and meta.get("overview"):
			out.append(meta["overview"])
		elif f in ("director", "country") and (meta.get("details") or {}).get(f):
			out.append(meta["details"][f])
		elif f == "cast" and (meta.get("details") or {}).get("cast"):
			out.append(("، " if arabic else ", ").join(meta["details"]["cast"][:3]))
		elif f == "imdb" and (meta.get("details") or {}).get("imdb"):
			out.append("IMDb %s" % meta["details"]["imdb"])
		elif f == "awards" and (meta.get("details") or {}).get("awards"):
			out.append(meta["details"]["awards"])
		elif f == "runtime" and (meta.get("details") or {}).get("runtime"):
			out.append(("%d دقيقة" if arabic else "%d min") % meta["details"]["runtime"])
	return sep.join(x for x in out if x)


CARD_LABELS = {
	"year": ("السنة", "Year"), "genres": ("النوع", "Genre"), "director": ("المخرج", "Director"),
	"country": ("البلد", "Country"), "cast": ("الأبطال", "Cast"), "runtime": ("المدة", "Runtime"), "type": ("التصنيف", "Type"),
	"imdb": ("التقييم", "Rating"), "awards": ("الجوائز", "Awards"),
}


def formatCard(meta, fields=("year", "genres", "director", "country", "cast"), arabic=True, labelColor="", valueColor=""):
	"""Multi-line 'label: value' block like a film card."""
	if not meta:
		return ""
	lines = []
	for f in fields:
		v = formatInfo(meta, (f,), arabic)
		if v:
			label = CARD_LABELS.get(f, (f, f))[0 if arabic else 1]
			lines.append("%s%s:  %s%s" % (labelColor, label, valueColor, v))
	return "\n".join(lines)


# -- sport detection (context-aware posters) --------------------------------
_reSport = re.compile(r"(?:\bvs\.?\b|\bv\b(?=\s+\S)|\s[x\u00d7\u2013-]\s.*\s(?:live|\u0645\u0628\u0627\u0634\u0631)|\u0636\u062f\s|"
	r"\b(?:league|liga|premier|champions|cup|serie a|bundesliga|laliga|uefa|fifa|caf|nba|nfl|ufc|wwe|grand prix|formula 1|f1|"
	r"motogp|tennis|atp|wta|football|soccer|derby|highlights)\b|"
	r"\u0645\u0628\u0627\u0631\u0627\u0629|\u0627\u0644\u062f\u0648\u0631\u064a|\u062f\u0648\u0631\u064a\s|\u0643\u0623\u0633|"
	r"\u0628\u0637\u0648\u0644\u0629|\u0627\u0633\u062a\u0648\u062f\u064a\u0648 \u062a\u062d\u0644\u064a\u0644\u064a|\u0645\u0644\u062e\u0635|\u0623\u0647\u062f\u0627\u0641|\u0631\u064a\u0627\u0636\u0629)", re.I)


# "Team A - Team B": two short sides and at least one side looks like a club
_reVersus = re.compile(r"^\s*([^-\u2013:|]{2,32}?)\s+(?:-|\u2013|\u2014|x|\u00d7|v|vs\.?)\s+([^-\u2013:|]{2,32}?)\s*(?:\(.*\))?\s*$", re.I)
_CLUB_WORDS = (
	"united", "city", "fc", "cf", "afc", "sc", "real", "atletico", "athletic", "sporting", "inter", "milan", "juventus",
	"arsenal", "chelsea", "liverpool", "tottenham", "everton", "villa", "newcastle", "brighton", "wolves", "fulham",
	"brentford", "palace", "forest", "west ham", "leeds", "barcelona", "madrid", "sevilla", "valencia", "betis",
	"bayern", "dortmund", "leverkusen", "leipzig", "psg", "paris", "marseille", "lyon", "monaco", "napoli", "roma",
	"lazio", "atalanta", "ajax", "psv", "porto", "benfica", "celtic", "rangers", "galatasaray", "fenerbahce",
	"al ahly", "zamalek", "pyramids", "hilal", "nassr", "ittihad", "wydad", "raja", "esperance",
	"\u0627\u0644\u0623\u0647\u0644\u064a", "\u0627\u0644\u0632\u0645\u0627\u0644\u0643", "\u0628\u064a\u0631\u0627\u0645\u064a\u062f\u0632",
	"\u0627\u0644\u0647\u0644\u0627\u0644", "\u0627\u0644\u0646\u0635\u0631", "\u0627\u0644\u0627\u062a\u062d\u0627\u062f",
	"\u0627\u0644\u0645\u0635\u0631\u064a", "\u0627\u0644\u0625\u0633\u0645\u0627\u0639\u064a\u0644\u064a",
	"\u0628\u0631\u0634\u0644\u0648\u0646\u0629", "\u0631\u064a\u0627\u0644 \u0645\u062f\u0631\u064a\u062f",
	"\u0644\u064a\u0641\u0631\u0628\u0648\u0644", "\u0645\u0627\u0646\u0634\u0633\u062a\u0631", "\u062a\u0634\u064a\u0644\u0633\u064a",
	"\u0623\u0631\u0633\u0646\u0627\u0644", "\u064a\u0648\u0641\u0646\u062a\u0648\u0633", "\u0628\u0627\u064a\u0631\u0646",
	"\u0645\u0646\u062a\u062e\u0628")
_reClub = re.compile(r"(?:^|[\s.'])(?:%s)(?:$|[\s.'])" % "|".join(re.escape(w) for w in _CLUB_WORDS), re.I)


def isSportTitle(name):
	"""True for an event name that looks like a match / sport programme."""
	if not name:
		return False
	if _reSport.search(name):
		return True
	m = _reVersus.match(name)
	if not m or _reNotTeam.search(m.group(1)) or _reNotTeam.search(m.group(2)):
		return False
	return bool(_reClub.search(m.group(1)) or _reClub.search(m.group(2)))


# words that never appear in a team name but often in film titles
_reNotTeam = re.compile(r"\b(?:the|and|of|part|chapter|movie|season|episode|ep|vol|returns)\b|\b(?:\d+|[ivx]+)$|\u0627\u0644\u062c\u0632\u0621|\u0627\u0644\u062d\u0644\u0642\u0629|\u0627\u0644\u0645\u0648\u0633\u0645", re.I)


def isSportEvent(event, channelName=""):
	"""Sport detection from the DVB genre (content nibble 4 = sports), the
	event name and description and the channel name. Cheap: no I/O."""
	if not event:
		return False
	try:
		genre = event.getGenreData()
		if genre and genre.getLevel1() == 4:
			return True
	except Exception:
		pass
	try:
		for g in event.getGenreDataList() or ():
			if g and g[0] == 4:
				return True
	except Exception:
		pass
	try:
		name = event.getEventName() or ""
	except Exception:
		name = ""
	if isSportTitle(name):
		return True
	try:  # "Premier League", "Live football" ... in the short description
		desc = (event.getShortDescription() or "")[:160]
		if desc and desc.strip() != name.strip() and _reSport.search(desc) and not _reFilmHint.search(desc):
			return True
	except Exception:
		pass
	ch = (channelName or "").lower()
	return bool(ch) and any(k in ch for k in ("sport", "\u0631\u064a\u0627\u0636", "ssc", "on time", "alkass", "\u0627\u0644\u0643\u0623\u0633"))


_NEWS_CHANNELS = ("news", "jazeera", "\u0627\u0644\u062c\u0632\u064a\u0631\u0629", "arabiya", "\u0627\u0644\u0639\u0631\u0628\u064a\u0629", "hadath",
	"\u0627\u0644\u062d\u062f\u062b", "\u0623\u062e\u0628\u0627\u0631", "\u0627\u0644\u0625\u062e\u0628\u0627\u0631\u064a\u0629", "france 24", "cnn", "bbc", "rt arabic", "rt ", "trt", "asharq", "\u0627\u0644\u0634\u0631\u0642",
	"alghad", "\u0627\u0644\u063a\u062f", "al araby", "\u0627\u0644\u0639\u0631\u0628\u064a", "dw", "euronews", "cgtn", "i24", "mayadeen", "\u0627\u0644\u0645\u064a\u0627\u062f\u064a\u0646", "qahera")
_NOT_NEWS = ("doc", "\u0648\u062b\u0627\u0626\u0642", "kids", "\u0623\u0637\u0641\u0627\u0644", "sport", "\u0631\u064a\u0627\u0636", "drama", "\u062f\u0631\u0627\u0645\u0627", "cinema", "\u0633\u064a\u0646\u0645\u0627", "movies", "\u0623\u0641\u0644\u0627\u0645", "mubasher", "\u0645\u0628\u0627\u0634\u0631")


def playingChannelName(source=None):
	"""Name of the channel of a ServiceEvent source, else the playing one."""
	try:
		from enigma import eServiceCenter, eServiceReference
		ref = getattr(source, "serviceref", None) or getattr(source, "service", None)
		if not isinstance(ref, eServiceReference):
			import NavigationInstance
			ref = NavigationInstance.instance.getCurrentlyPlayingServiceReference()
		info = ref and eServiceCenter.getInstance().info(ref)
		return info and info.getName(ref) or ""
	except Exception:
		return ""


def noFilmEvent(event, source=None):
	"""Sport or news: no film poster / rating / details for it."""
	if not event or not posters.skipSport:
		return False
	ch = playingChannelName(source)
	return isSportEvent(event, ch) or isNewsEvent(event, ch)


def isNewsEvent(event, channelName=""):
	"""News / talk programmes: DVB genre 0x2 or a news channel. They have
	no film poster, and a word of their title often matches a film by
	chance - so no poster is looked up for them."""
	try:
		genre = event.getGenreData() if event else None
		if genre and genre.getLevel1() == 2:
			return True
	except Exception:
		pass
	ch = (channelName or "").lower()
	if not ch or any(k in ch for k in _NOT_NEWS):
		return False
	return any(k in ch for k in _NEWS_CHANNELS)


_reFilmHint = re.compile(r"\b(?:film|movie|documentary|drama|series)\b|\u0641\u064a\u0644\u0645|\u0648\u062b\u0627\u0626\u0642\u064a|\u0645\u0633\u0644\u0633\u0644", re.I)


# -- shared EPG lookup for the "coming up" widgets ----------------------------
# The channel list shows 4 upcoming posters + 4 titles per channel; each of
# them used to ask the EPG cache for 24 hours of events on every key press.
# They now share one answer per channel and minute.
_upcoming = {}


def upcomingEvents(refstr):
	"""[(begin, duration, title)] of the next 24 h on a channel, cached."""
	key = (refstr, int(time.time() // 60))
	hit = _upcoming.get(key)
	if hit is not None:
		return hit
	try:
		from enigma import eEPGCache
		events = eEPGCache.getInstance().lookupEvent(["BDT", (refstr, 0, -1, 24 * 60)]) or []
	except Exception:
		events = []
	if len(_upcoming) > 48:
		_upcoming.clear()
	_upcoming[key] = events
	return events


_details = {}


def upcomingDetails(refstr):
	"""[(begin, duration, title, short description, extended description)] of the next 24 h, cached."""
	key = (refstr, int(time.time() // 60))
	hit = _details.get(key)
	if hit is not None:
		return hit
	try:
		from enigma import eEPGCache
		events = eEPGCache.getInstance().lookupEvent(["BDTSE", (refstr, 0, -1, 24 * 60)]) or []
	except Exception:
		events = []
	if len(_details) > 48:
		_details.clear()
	_details[key] = events
	return events


class PosterService:
	"""Posters, backdrops and TMDB metadata for EPG events.

	kinds: "poster" -> path, "backdrop" -> path, "meta" -> dict
	One TMDB search per title gives poster + metadata; a backdrop is only
	downloaded when a screen actually shows one."""
	NEGATIVE_TTL = 12 * 3600      # don't ask TMDB again for an unknown title for 12h
	NEGATIVE_VERSION = 2          # bumped when the search gets better
	REINDEX_EVERY = 15 * 60       # rescan foreign poster folders every 15 min
	KINDS = ("poster", "backdrop", "meta", "details", "thumb")

	def __init__(self):
		self.enabled = confBool("tmdb", "enabled", True) and not liteMode()
		self.apiKey = confGet("tmdb", "api_key", "")
		self.language = confGet("tmdb", "language", "ar")
		try:
			self.maxFiles = max(50, int(confGet("posters", "max_files", "600")))
		except ValueError:
			self.maxFiles = 600
		self.quality = "w500" if confGet("posters", "quality", "w342") == "w500" else "w342"
		self.prefetchQueue = deque(maxlen=600)
		self.skipSport = confBool("posters", "smart_sport", True)
		self.stats = {"downloads": 0, "notfound": 0, "errors": 0, "prefetched": 0, "epg": 0}
		self.cacheDir = None     # .../NileGlass/poster
		self.backdropDir = None  # .../NileGlass/backdrop
		self.metaDir = None      # .../NileGlass/meta
		self.index = {}          # lower-case file name -> full path (posters)
		self.metaMemo = {}       # title -> dict (small in-memory cache)
		self.negative = {}       # title -> timestamp of failed lookup
		self.lastIndex = 0
		self.lastNegativeSave = 0
		self.lock = threading.Lock()
		self.ioQueue = queue.Queue(maxsize=96)
		self.netQueue = queue.Queue(maxsize=32)
		self.netPending = {}     # title -> set of extra needs ("backdrop", "details")
		self.callbacks = {}      # (kind, title) -> list of callbacks
		self.started = False

	# -- public API (UI thread) --------------------------------------------
	def request(self, eventName, callback, prefetch=False, kind="poster"):
		"""Ask for the poster / backdrop / metadata of an EPG event.
		callback(title, value) is called later on the UI thread.
		Returns the cleaned title ('' = nothing to look up)."""
		title = cleanTitle(eventName)
		if not title or kind not in self.KINDS:
			return ""
		m = _reYearHint.search(eventName or "")
		year = int(m.group(1)) if m else None
		if kind == "meta" and title in self.metaMemo and callback is not None:
			callInUiThread(callback, title, self.metaMemo[title])
			return title
		self._start()
		with self.lock:
			if callback is not None:
				self.callbacks.setdefault((kind, title), []).append(callback)
		try:
			self.ioQueue.put_nowait((kind, title, year))
		except queue.Full:
			if callback is not None:
				self.cancel(callback)
			return ""
		return title

	def cancel(self, callback):
		with self.lock:
			for key in list(self.callbacks):
				cbs = [c for c in self.callbacks[key] if c != callback]
				if cbs:
					self.callbacks[key] = cbs
				else:
					del self.callbacks[key]

	def prefetch(self, eventNames, urgent=False):
		"""Queue posters for later, used by the daily bouquet download.
		Handled only when nothing else is waiting. urgent=True puts them at
		the head of the queue (channels next to the selected one).
		Returns the number queued."""
		n = 0
		seen = set()
		titles = []
		for name in eventNames:
			if self.skipSport and isSportTitle(name):
				continue
			title = cleanTitle(name)
			if title and title not in seen:
				seen.add(title)
				titles.append(title)
		if urgent:
			for title in reversed(titles):
				try:
					self.prefetchQueue.remove(title)
				except ValueError:
					pass
				self.prefetchQueue.appendleft(title)
		else:
			self.prefetchQueue.extend(titles)
		n = len(titles)
		if n:
			self._start()
			try:
				self.ioQueue.put_nowait(("_wake", "", None))
			except queue.Full:
				pass
		return n

	def status(self):
		"""Snapshot for the diagnostics screen (worker-thread safe)."""
		def count(d, ext):
			try:
				return len([x for x in os.listdir(d) if x.endswith(ext)])
			except Exception:
				return 0
		free = None
		try:
			st = os.statvfs(self.cacheDir)
			free = st.f_bavail * st.f_frsize
		except Exception:
			pass
		return {"cache": self.cacheDir, "posters": count(self.cacheDir, ".jpg") if self.cacheDir else 0,
			"backdrops": count(self.backdropDir, ".jpg") if self.backdropDir else 0,
			"free": free, "pending": len(self.prefetchQueue), "stats": dict(self.stats)}

	def testKey(self):
		"""Blocking check of the TMDB key - call from a thread only."""
		if not self.apiKey:
			return False, "no key"
		try:
			self._tmdb("configuration", {})
			return True, "ok"
		except Exception as err:
			return False, str(err)[:120]

	# -- internals -----------------------------------------------------------
	def _start(self):
		if self.started:
			return
		self.started = True
		for target, name in ((self._ioLoop, "NileGlass-poster-io"), (self._netLoop, "NileGlass-poster-net")):
			threading.Thread(target=target, name=name, daemon=True).start()

	def _deliver(self, kind, title, value):
		with self.lock:
			cbs = self.callbacks.pop((kind, title), [])
		for cb in cbs:
			callInUiThread(cb, title, value)

	def _chooseCacheDir(self):
		wanted = confGet("posters", "cache_dir", "auto")
		candidates = []
		if wanted and wanted != "auto":
			candidates.append(wanted)
		for m in MOUNTS:
			if os.path.isdir(m) and isLocalMount(m):
				candidates.append(os.path.join(m, "NileGlass", "poster"))
		candidates.append("/tmp/NileGlass/poster")
		for c in candidates:
			try:
				os.makedirs(c, exist_ok=True)
				test = os.path.join(c, ".w")
				with open(test, "w") as f:
					f.write("1")
				os.remove(test)
				if c.startswith("/tmp"):
					self.maxFiles = min(self.maxFiles, 120)  # RAM disk: keep it small
				base = os.path.dirname(c.rstrip("/"))
				self.backdropDir = os.path.join(base, "backdrop")
				self.thumbDir = os.path.join(base, "thumb")
				self.peopleDir = os.path.join(base, "people")
				os.makedirs(self.thumbDir, exist_ok=True)
				os.makedirs(self.peopleDir, exist_ok=True)
				self.metaDir = os.path.join(base, "meta")
				os.makedirs(self.backdropDir, exist_ok=True)
				os.makedirs(self.metaDir, exist_ok=True)
				log("poster cache:", c)
				threading.Thread(target=self._dropLooseMatches, args=(base,), daemon=True).start()
				return c
			except Exception:
				continue
		return None

	def _dropLooseMatches(self, base):
		"""Once: forget cached matches made by the old, looser title rule
		(a word of the title inside a longer film name). They are looked up
		again with the stricter rule."""
		mark = os.path.join(base, ".match2")
		if os.path.exists(mark):
			return
		dropped = 0
		try:
			for f in os.listdir(self.metaDir):
				if not f.endswith(".json"):
					continue
				stem = f[:-5]
				try:
					with open(os.path.join(self.metaDir, f), encoding="utf-8") as fh:
						meta = json.load(fh)
				except Exception:
					continue
				want = self._norm(stem)
				name = self._norm(meta.get("name") or "")
				if not want or not name or want == name:
					continue
				short, long_ = sorted((want, name), key=len)
				if short in long_ and len(short) < 0.6 * len(long_):
					for d, ext in ((self.metaDir, ".json"), (self.cacheDir, ".jpg"), (self.thumbDir, ".jpg"), (self.backdropDir, ".jpg")):
						try:
							os.remove(os.path.join(d, stem + ext))
						except Exception:
							pass
					dropped += 1
			open(mark, "w").write("%d\n" % dropped)
			log("dropped %d loose poster matches" % dropped)
		except Exception as err:
			log("drop loose matches:", err)

	def _reindex(self):
		index = {}
		dirs = []
		for m in MOUNTS:
			if os.path.isdir(m) and isLocalMount(m):
				for sub in FOREIGN_DIRS:
					dirs.append(os.path.join(m, sub))
		if self.cacheDir:
			dirs.append(self.cacheDir)  # last = highest priority
		for d in dirs:
			try:
				for name in os.listdir(d):
					if name.lower().endswith(".jpg"):
						index[name.lower()] = os.path.join(d, name)
			except Exception:
				pass
		self.index = index
		self.lastIndex = time.time()
		self._loadNegative()

	def _negativeFile(self):
		return self.cacheDir and os.path.join(self.cacheDir, ".notfound.json")

	def _loadNegative(self):
		try:
			with open(self._negativeFile(), "r", encoding="utf-8") as f:
				data = json.load(f)
			now = time.time()
			if data.pop("_v", 0) != self.NEGATIVE_VERSION:      # older search: give every title a new try
				data = {}
			self.negative = {k: v for k, v in data.items() if isinstance(v, (int, float)) and now - v < self.NEGATIVE_TTL}
		except Exception:
			pass

	def _saveNegative(self):
		try:
			if len(self.negative) > 3000:
				self.negative = dict(sorted(self.negative.items(), key=lambda kv: kv[1])[-2000:])
			tmp = self._negativeFile() + ".tmp"
			with open(tmp, "w", encoding="utf-8") as f:
				json.dump(dict(self.negative, _v=self.NEGATIVE_VERSION), f, ensure_ascii=False)
			os.replace(tmp, self._negativeFile())
		except Exception:
			pass

	# local lookups (worker threads only)
	def _posterPath(self, title):
		return self.index.get(fileNameFor(title).lower())

	def _backdropPath(self, title):
		if not self.backdropDir:
			return None
		p = os.path.join(self.backdropDir, fileNameFor(title))
		return p if os.path.isfile(p) else None

	def _metaPath(self, title):
		return self.metaDir and os.path.join(self.metaDir, fileNameFor(title)[:-4] + ".json")

	def _loadMeta(self, title):
		if title in self.metaMemo:
			return self.metaMemo[title]
		p = self._metaPath(title)
		if p and os.path.isfile(p):
			try:
				with open(p, "r", encoding="utf-8") as f:
					meta = json.load(f)
				self._memo(title, meta)
				return meta
			except Exception:
				pass
		return None

	def _memo(self, title, meta):
		if len(self.metaMemo) > 300:
			self.metaMemo.clear()
		self.metaMemo[title] = meta

	@staticmethod
	def _warm(path):
		try:
			with open(path, "rb") as f:  # wake the disk + fill the page cache
				data = f.read()
			# empty or cut files (other plugins, full disk ...) are never shown
			if len(data) < 1024 or not (data[:2] == b"\xff\xd8" or data[:4] == b"\x89PNG"):
				return None
			try:
				os.utime(path, None)   # LRU for the cache cleaner
			except OSError:
				pass
			return path
		except Exception:
			return None

	def _thumbPath(self, title):
		d = getattr(self, "thumbDir", None)
		p = d and os.path.join(d, fileNameFor(title))
		return p if p and os.path.isfile(p) else None

	def _local(self, kind, title):
		if kind == "thumb":  # small poster for lists: 4x faster to decode
			p = self._thumbPath(title)
			if p:
				return True, self._warm(p)
			meta = self._loadMeta(title)
			if meta is not None and not meta.get("poster"):
				return True, None
			return False, None
		"""(found, value). found=False means a download could help."""
		if kind == "poster":
			p = self._posterPath(title)
			return (True, self._warm(p)) if p else (False, None)
		if kind == "meta":
			meta = self._loadMeta(title)
			return (True, meta) if meta is not None else (False, None)
		if kind == "details":
			meta = self._loadMeta(title)
			return (True, meta) if meta is not None and "details" in meta else (False, meta)
		p = self._backdropPath(title)
		if p:
			return True, self._warm(p)
		meta = self._loadMeta(title)
		if meta is not None and not meta.get("backdrop"):
			return True, None  # known title without a backdrop
		return False, None

	def _ioLoop(self):
		try:
			self.cacheDir = self._chooseCacheDir()
			self._reindex()
			epgTitles.lookup("")  # start loading the SaadEPG title list early
		except Exception as err:
			log("poster init error:", err)
		while True:
			try:
				kind, title, year = self.ioQueue.get(timeout=2 if self.prefetchQueue else None)
			except queue.Empty:
				self._prefetchOne()
				continue
			if kind == "_wake":
				continue
			try:
				if time.time() - self.lastIndex > self.REINDEX_EVERY:
					self._reindex()
				found, value = self._local(kind, title)
				if found:
					self._deliver(kind, title, value)
					continue
				if not self._canDownload(title):
					self._deliver(kind, title, value if kind == "details" else None)
					continue
				need = {kind} & {"backdrop", "details", "thumb"}
				with self.lock:
					if title in self.netPending:
						self.netPending[title] |= need
						continue
					self.netPending[title] = set(need)
				try:
					self.netQueue.put_nowait((title, year))
				except queue.Full:
					with self.lock:
						self.netPending.pop(title, None)
					self._deliver(kind, title, None)
			except Exception as err:
				log("poster io error:", err)
				self._deliver(kind, title, None)

	def _prefetchOne(self):
		"""One queued prefetch title, only while the queues are idle."""
		if not self.prefetchQueue or not self.netQueue.empty():
			return
		title = self.prefetchQueue.popleft()
		if self._posterPath(title) or not self._canDownload(title):
			return
		with self.lock:
			if title in self.netPending:
				return
			self.netPending[title] = set()
		try:
			self.netQueue.put_nowait((title, None))
			self.stats["prefetched"] += 1
		except queue.Full:
			with self.lock:
				self.netPending.pop(title, None)

	def _canDownload(self, title):
		if not (self.enabled and self.apiKey and self.cacheDir):
			return False
		ts = self.negative.get(title)
		return not (ts and time.time() - ts < self.NEGATIVE_TTL)

	def _netLoop(self):
		downloads = 0
		while True:
			title, year = self.netQueue.get()
			try:
				meta = self._loadMeta(title)
				if meta is None:
					meta = self._search(title, year)
					if meta is None:
						self.stats["notfound"] += 1
						self.negative[title] = time.time()
						if time.time() - self.lastNegativeSave > 60:
							self.lastNegativeSave = time.time()
							self._saveNegative()
					else:
						downloads += 1
						self.stats["downloads"] += 1
				if meta and meta.get("poster") and not self._posterPath(title):  # e.g. removed by the cache cleaner
					pp = self._saveImage(self.imageUrl(meta, "poster", self.quality), os.path.join(self.cacheDir, fileNameFor(title)), 1024 * 1024)
					if pp:
						self.index[os.path.basename(pp).lower()] = pp
				with self.lock:
					needs = set(self.netPending.get(title) or ())
				if meta and "details" in needs and "details" not in meta:
					meta = self._details(title, meta)
				if meta and "thumb" in needs and meta.get("poster") and not self._thumbPath(title):
					self._saveImage(meta.get("thumbUrl") or self.imageUrl(meta, "poster", "w185"), os.path.join(self.thumbDir, fileNameFor(title)), 300 * 1024)
				if meta and "backdrop" in needs and meta.get("backdrop") and not self._backdropPath(title):
					self._saveImage(self.imageUrl(meta, "backdrop", "w1280"), os.path.join(self.backdropDir, fileNameFor(title)), 3 * 1024 * 1024)
				if downloads and downloads % 25 == 0:
					self._trimCache()
			except Exception as err:
				self.stats["errors"] += 1
				log("poster download error for %r: %s" % (title, err))
			finally:
				with self.lock:
					self.netPending.pop(title, None)
			p = self._posterPath(title)
			meta = self._loadMeta(title)
			self._deliver("poster", title, p)
			self._deliver("meta", title, meta)
			self._deliver("details", title, meta)
			self._deliver("backdrop", title, self._backdropPath(title))
			self._deliver("thumb", title, self._thumbPath(title))
			if self.prefetchQueue:
				time.sleep(0.3)  # be gentle with TMDB during bulk downloads

	def _tmdb(self, endpoint, params):
		headers = {"Accept": "application/json"}
		params = dict(params)
		if len(self.apiKey) > 40:  # v4 read access token
			headers["Authorization"] = "Bearer " + self.apiKey
		else:
			params["api_key"] = self.apiKey
		url = "https://api.themoviedb.org/3/%s?%s" % (endpoint, urlencode(params))
		return json.loads(httpGet(url, headers=headers, timeout=7).decode("utf-8"))

	@staticmethod
	def _norm(s):
		s = unicodedata.normalize("NFKC", s or "").lower()
		s = re.sub("[ً-ٟـ]", "", s)  # Arabic diacritics + tatweel
		s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
		return re.sub(r"[^\w]+", "", s)

	def _score(self, want, names):
		score = 0
		for n in names:
			nn = self._norm(n)
			if nn == want:
				score = max(score, 100)
			elif want and (want in nn or nn in want) and min(len(nn), len(want)) >= 3 \
					and min(len(nn), len(want)) >= 0.6 * max(len(nn), len(want)):
				# part of a title only counts when it is most of it:
				# "المنتصف" must not match "...: إمبراطورية المنتصف"
				score = max(score, 60)
		return score

	@staticmethod
	def _year(r):
		d = r.get("release_date") or r.get("first_air_date") or ""
		return int(d[:4]) if d[:4].isdigit() else None

	def _pick(self, title, results, year=None):
		want = self._norm(title)
		best, bestScore = None, -1
		for r in results:
			if r.get("media_type") not in (None, "movie", "tv") or not r.get("poster_path"):
				continue
			names = [r.get(k) for k in ("title", "name", "original_title", "original_name") if r.get(k)]
			score = self._score(want, names)
			if score and year and self._year(r) == year:
				score += 25
			score += min(20, int(r.get("popularity") or 0) // 5)
			if score > bestScore:
				best, bestScore = r, score
		# Only accept a real name match - a wrong poster is worse than none.
		return best if bestScore >= 60 else None

	def _pickByTranslations(self, title, results, year=None):
		"""Arabic EPG titles often differ from TMDB's main title. Check the
		translated / alternative titles of the two best candidates."""
		want = self._norm(title)
		for r in [r for r in results if r.get("media_type") in ("movie", "tv") and r.get("poster_path")][:3]:
			try:
				extra = "translations,alternative_titles"
				d = self._tmdb("%s/%d" % (r["media_type"], r["id"]), {"append_to_response": extra})
			except Exception:
				continue
			names = []
			for t in (d.get("translations") or {}).get("translations") or []:
				data = t.get("data") or {}
				names += [data.get("title"), data.get("name")]
			alt = d.get("alternative_titles") or {}
			for t in (alt.get("titles") or alt.get("results") or []):
				names.append(t.get("title"))
			if self._score(want, [n for n in names if n]) >= 100:
				return r
		return None

	def _search(self, title, year=None):
		meta = self._searchTmdb(title, year)
		if meta is None and ": " in title:                     # "Moja wina: Londyn" -> "Moja wina"
			meta = self._searchTmdb(title.split(": ", 1)[0], year, saveAs=title)
		if meta is None and not _reArabic.search(title):        # series TMDB does not know: TVmaze (free, no key)
			meta = self._searchTvmaze(title, year)
		return meta

	def _searchTvmaze(self, title, year=None):
		try:
			res = json.loads(httpGet("https://api.tvmaze.com/search/shows?" + urlencode({"q": title}), timeout=7).decode("utf-8")) or []
		except Exception:
			return None
		want = self._norm(title)
		best, bestScore = None, -1
		for r in res[:6]:
			show = r.get("show") or {}
			img = show.get("image") or {}
			if not img.get("original"):
				continue
			score = self._score(want, [show.get("name") or ""])
			prem = (show.get("premiered") or "")[:4]
			if score and year and prem.isdigit() and int(prem) == year:
				score += 25
			if score > bestScore:
				best, bestScore = show, score
		if not best or bestScore < 100:      # TVmaze has no translations: only an exact name counts
			return None
		img = best.get("image") or {}
		summary = re.sub(r"<[^>]+>", "", best.get("summary") or "").strip()
		meta = {"id": best.get("id"), "type": "tv", "source": "tvmaze", "name": best.get("name") or "",
			"year": int(best["premiered"][:4]) if (best.get("premiered") or "")[:4].isdigit() else None,
			"rating": float((best.get("rating") or {}).get("average") or 0), "genres": [], "genreNames": best.get("genres") or [],
			"overview": summary, "poster": img.get("original") or "", "thumbUrl": img.get("medium") or "", "backdrop": ""}
		self.stats["tvmaze"] = self.stats.get("tvmaze", 0) + 1
		return self._store(title, meta)

	def _store(self, title, meta):
		if not self._posterPath(title) and meta.get("poster"):
			p = self._saveImage(self.imageUrl(meta, "poster", self.quality), os.path.join(self.cacheDir, fileNameFor(title)), 1024 * 1024)
			if p:
				self.index[os.path.basename(p).lower()] = p
		tmp = self._metaPath(title) + ".tmp"
		with open(tmp, "w", encoding="utf-8") as f:
			json.dump(meta, f, ensure_ascii=False)
		os.replace(tmp, self._metaPath(title))
		self._memo(title, meta)
		return meta

	def _searchTmdb(self, title, year=None, saveAs=None):
		saveAs = saveAs or title
		params = {"query": title, "language": self.language, "include_adult": "false", "page": 1}
		results = self._tmdb("search/multi", params).get("results") or []
		hit = self._pick(title, results, year)
		resultsEn = []
		if not hit and self.language != "en":
			params["language"] = "en"
			resultsEn = self._tmdb("search/multi", params).get("results") or []
			hit = self._pick(title, resultsEn, year)
			if hit:  # keep the local-language overview / title when available
				hit = next((r for r in results if r.get("id") == hit.get("id")), hit)
		if not hit and _reArabic.search(title):
			en = epgTitles.lookup(title)
			if en:  # English title from the SaadEPG guide
				params.update(query=en, language="en")
				resultsEn2 = self._tmdb("search/multi", params).get("results") or []
				hit = self._pick(en, resultsEn2, year)
				if hit and self.language != "en":  # Arabic overview / title when TMDB has one
					try:
						loc = self._tmdb("%s/%d" % (hit.get("media_type") or "movie", hit["id"]), {"language": self.language})
						if loc.get("overview"):
							hit = dict(hit, overview=loc["overview"])
						if loc.get("title") or loc.get("name"):
							hit = dict(hit, title=loc.get("title") or loc.get("name"), name=loc.get("title") or loc.get("name"))
					except Exception:
						pass
				if hit:
					self.stats["epg"] = self.stats.get("epg", 0) + 1
		if not hit and (results or resultsEn):
			# the EPG title is in another language (Arabic, Polish, German ...): TMDB found the
			# film by one of its translated / alternative titles - check those of the best candidates
			hit = self._pickByTranslations(title, results or resultsEn, year)
			if hit:
				self.stats["translated"] = self.stats.get("translated", 0) + 1
		if not hit:
			return None
		meta = {
			"id": hit.get("id"),
			"type": hit.get("media_type") or "movie",
			"name": hit.get("title") or hit.get("name") or "",
			"year": self._year(hit),
			"rating": round(float(hit.get("vote_average") or 0), 1) if (hit.get("vote_count") or 0) >= 5 else 0,
			"genres": hit.get("genre_ids") or [],
			"overview": (hit.get("overview") or "").strip(),
			"poster": hit.get("poster_path") or "",
			"backdrop": hit.get("backdrop_path") or "",
		}
		return self._store(saveAs, meta)

	def _details(self, title, meta):
		"""Director / writer, country, main cast, runtime (one extra request,
		only for screens that show them)."""
		if meta.get("source") == "tvmaze":        # not a TMDB id
			return meta
		try:
			d = self._tmdb("%s/%d" % (meta.get("type") or "movie", int(meta["id"])), {"language": self.language, "append_to_response": "credits,external_ids"})
		except Exception as err:
			log("details error for %r: %s" % (title, err))
			return meta
		credits = d.get("credits") or {}
		directors = [c.get("name") for c in credits.get("crew") or [] if c.get("job") == "Director"]
		if not directors:
			directors = [c.get("name") for c in d.get("created_by") or []]
		cast = [c.get("name") for c in (credits.get("cast") or [])[:4] if c.get("name")]
		people = [(c.get("name"), c.get("character") or "", c.get("profile_path") or "") for c in (credits.get("cast") or [])[:6] if c.get("name")]
		countries = [c.get("name") for c in d.get("production_countries") or [] if c.get("name")]
		if not countries:
			countries = d.get("origin_country") or []
		runtime = d.get("runtime") or ((d.get("episode_run_time") or [0]) or [0])[0]
		meta = dict(meta)
		meta["details"] = {"director": "، ".join([x for x in directors if x][:2]), "cast": cast, "country": "، ".join(countries[:2]),
			"runtime": runtime or 0, "seasons": d.get("number_of_seasons") or 0, "people": people,
			"original": d.get("original_title") or d.get("original_name") or ""}
		imdbId = (d.get("external_ids") or {}).get("imdb_id") or d.get("imdb_id")
		omdbKey = confGet("tmdb", "omdb_key", "")
		if imdbId and omdbKey:  # IMDb rating + awards from OMDb (free key)
			try:
				o = json.loads(httpGet("https://www.omdbapi.com/?" + urlencode({"i": imdbId, "apikey": omdbKey}), timeout=7).decode("utf-8"))
				if o.get("imdbRating") and o["imdbRating"] != "N/A":
					meta["details"]["imdb"] = o["imdbRating"]
				if o.get("Awards") and o["Awards"] != "N/A":
					meta["details"]["awards"] = o["Awards"][:80]
			except Exception as err:
				log("omdb:", err)
		if not meta.get("overview") and d.get("overview"):
			meta["overview"] = d["overview"].strip()
		try:
			tmp = self._metaPath(title) + ".tmp"
			with open(tmp, "w", encoding="utf-8") as f:
				json.dump(meta, f, ensure_ascii=False)
			os.replace(tmp, self._metaPath(title))
		except Exception:
			pass
		self._memo(title, meta)
		return meta

	@staticmethod
	def imageUrl(meta, key, size):
		"""poster / backdrop url: TMDB path, or a full url from another source (TVmaze)"""
		v = meta.get(key) or ""
		if v.startswith("http"):
			return v
		return "https://image.tmdb.org/t/p/%s" % size + quote(v)

	@staticmethod
	def _saveImage(url, path, maxBytes):
		img = httpGet(url, timeout=10, maxBytes=maxBytes)
		# only complete JPEG/PNG files reach the screen (a broken image can crash the GUI)
		if len(img) < 1024 or not (img.startswith(b"\xff\xd8") and img.rstrip(b"\x00").endswith(b"\xff\xd9") or img.startswith(b"\x89PNG") and b"IEND" in img[-32:]):
			return None
		tmp = path + ".part"
		with open(tmp, "wb") as f:
			f.write(img)
		os.replace(tmp, path)
		return path

	def _trimDir(self, d, limit, ext):
		try:
			files = [os.path.join(d, n) for n in os.listdir(d) if n.endswith(ext)]
			if len(files) <= limit:
				return
			files.sort(key=lambda p: os.path.getmtime(p))
			for p in files[:len(files) - limit]:
				try:
					os.remove(p)
					self.index.pop(os.path.basename(p).lower(), None)
				except Exception:
					pass
		except Exception as err:
			log("cache trim error:", err)

	def personImage(self, profilePath):
		"""Blocking (worker threads only): local file of an actor photo."""
		if not profilePath or not getattr(self, "peopleDir", None):
			return None
		p = os.path.join(self.peopleDir, profilePath.strip("/").replace("/", "_"))
		if os.path.isfile(p):
			return p
		return self._saveImage("https://image.tmdb.org/t/p/w185" + quote(profilePath), p, 300 * 1024)

	def _trimCache(self):
		if getattr(self, "thumbDir", None):
			self._trimDir(self.thumbDir, self.maxFiles, ".jpg")
			self._trimDir(self.peopleDir, 300, ".jpg")
		self._trimDir(self.cacheDir, self.maxFiles, ".jpg")
		self._trimDir(self.backdropDir, max(30, self.maxFiles // 3), ".jpg")
		self._trimDir(self.metaDir, self.maxFiles * 3, ".json")


class EpgTitleMap:
	"""Arabic EPG title -> English title, from the user's SaadEPG data
	(films.json.gz + tr_ar.json.gz).  Loaded and refreshed in its own thread;
	lookup() never blocks and simply returns None until the map is ready."""
	REFRESH = 24 * 3600
	FILES = ("films.json.gz", "tr_ar.json.gz")
	_reNoise = re.compile(r"\bseg\s*\d+\b|\bpt\s*\d+\b|\bs\d+\s*ep\s*\d+\b|\bep\s*\d+\b", re.IGNORECASE)

	def __init__(self):
		self.enabled = confBool("posters", "epg_titles", True)
		self.base = (confGet("posters", "epg_titles_url", "") or "").strip().rstrip("/")
		self.map = {}
		self.updated = 0
		self.error = ""
		self.busy = False
		self.lock = threading.Lock()
		self.file = None

	@staticmethod
	def key(title):
		return PosterService._norm(cleanTitle(title))

	def lookup(self, title):
		"""English title for an Arabic EPG title, or None. Any thread."""
		if not self.enabled:
			return None
		self._kick()
		return self.map.get(self.key(title)) if self.map else None

	def status(self):
		return {"enabled": self.enabled, "titles": len(self.map), "updated": self.updated, "error": self.error}

	def _kick(self):
		if not self.base or self.busy or (self.map and time.time() - self.updated < self.REFRESH):
			return
		with self.lock:
			if self.busy:
				return
			self.busy = True
		threading.Thread(target=self._run, name="NileGlass-epgmap", daemon=True).start()

	def _run(self):
		try:
			if not self.map:
				self._loadDisk()
			if time.time() - self.updated >= self.REFRESH:
				self._download()
		except Exception as err:
			self.error = str(err)[:100]
			log("epg titles:", err)
		finally:
			if not self.updated:
				self.updated = time.time() - self.REFRESH + 3600  # retry in an hour
			self.busy = False

	def _path(self):
		if self.file is None:
			d = posters.metaDir and os.path.dirname(posters.metaDir.rstrip("/"))
			self.file = os.path.join(d or "/tmp/NileGlass", "epg_titles.json")
		return self.file

	def _loadDisk(self):
		try:
			with open(self._path(), "r", encoding="utf-8") as f:
				data = json.load(f)
			self.map = data.get("map") or {}
			self.updated = float(data.get("updated") or 0)
		except Exception:
			pass

	def _cleanEn(self, en):
		en = self._reNoise.split(en)[0]
		en = cleanTitle(en.split(" - ")[0])
		return en if 2 <= len(en) <= 60 and not _reArabic.search(en) else ""

	def build(self, films, trAr):
		"""films: list of dicts (title, en); trAr: {english: arabic}."""
		new = {}
		for en, ar in (trAr or {}).items():
			if isinstance(en, str) and isinstance(ar, str) and len(en) <= 80 and _reArabic.search(ar):
				k, e = self.key(ar), self._cleanEn(en)
				if k and e and len(k) >= 3 and k != self.key(e):
					new.setdefault(k, e)
		for f in films or []:  # the film list is the most precise source: it wins
			ar, en = f.get("title") or "", f.get("en") or ""
			k, e = self.key(ar), self._cleanEn(en)
			if k and e:
				new[k] = e
		return new

	def _get(self, name):
		raw = httpGet("%s/%s" % (self.base, name), timeout=20, maxBytes=6 * 1024 * 1024)
		if raw[:2] == b"\x1f\x8b":
			raw = gzip.decompress(raw)
		return json.loads(raw.decode("utf-8"))

	def _download(self):
		films = self._get(self.FILES[0])
		films = films.get("films") if isinstance(films, dict) else films
		trAr = self._get(self.FILES[1])
		new = self.build(films if isinstance(films, list) else [], trAr if isinstance(trAr, dict) else {})
		if not new:
			raise ValueError("empty title list")
		self.map = new
		self.updated = time.time()
		self.error = ""
		try:
			tmp = self._path() + ".tmp"
			os.makedirs(os.path.dirname(tmp), exist_ok=True)
			with open(tmp, "w", encoding="utf-8") as f:
				json.dump({"updated": self.updated, "map": new}, f, ensure_ascii=False, separators=(",", ":"))
			os.replace(tmp, self._path())
		except Exception as err:
			log("epg titles save:", err)
		log("epg titles: %d" % len(new))


# ------------------------------------------------------------------ tonight
GENERIC_TITLES = {"movie", "film", "arabic movie", "arabic film", "foreign movie", "english movie", "فيلم", "افلام",
	"فيلم عربي", "فيلم اجنبي", "افلام عربي", "افلام اجنبي", "سهره", "سهرة"}
_reLive = re.compile(r"\s*[-–|]\s*(?:live|مباشر|بث مباشر)\s*$", re.IGNORECASE)


def serviceKey(sref):
	"""Comparable key of a service reference: SID:TSID:ONID:NAMESPACE."""
	parts = (sref or "").split(":")
	if len(parts) < 7:
		return ""
	return ":".join((p.strip().upper().lstrip("0") or "0") for p in parts[3:7])


def _plainNorm(s):
	return PosterService._norm(s or "")


_GENERIC = set()


def normalizeTonight(data, now=None):
	"""Clean the Saad EPG 'tonight' data: drop generic titles and finished
	items, merge the same film / match found on several channels, prefer the
	Arabic names, strip ' - LIVE'.  Returns (films, matches) sorted by start."""
	now = now or time.time()
	if not _GENERIC:
		_GENERIC.update(_plainNorm(t) for t in GENERIC_TITLES)

	def channels(item):
		out = []
		for c in item.get("channels") or []:
			if isinstance(c, dict) and c.get("sref"):
				out.append({"sref": c["sref"], "name": (c.get("name") or "").strip(), "picon": c.get("picon") or "", "key": serviceKey(c["sref"])})
		return out

	def num(v, default=0):
		try:
			return int(v)
		except (TypeError, ValueError):
			return default

	films, index = [], {}
	for f in (data.get("films") or [])[:200]:
		if not isinstance(f, dict):
			continue
		title = _reLive.sub("", (f.get("title") or "").strip())
		start, stop = num(f.get("start")), num(f.get("stop"))
		if not title or _plainNorm(title) in _GENERIC or not start or (stop and stop < now):
			continue
		keys = [(_plainNorm(title), start // 300)]
		if num(f.get("tmdb_id")):
			keys.insert(0, (("tmdb", num(f.get("tmdb_id"))), start // 300))
		chans = channels(f)
		old = next((index[k] for k in keys if k in index), None)
		if old is not None:
			for k in keys:
				index.setdefault(k, old)
			if not old["tmdb_id"] and num(f.get("tmdb_id")):  # the TMDB entry has the better data
				old.update(tmdb_id=num(f.get("tmdb_id")), en=(f.get("en") or "").strip(), year=num(f.get("year"), None), rating=f.get("rating"),
					poster=f.get("poster") or old["poster"], poster_url=f.get("poster_url") or old["poster_url"])
			seen = {c["key"] for c in old["channels"]}
			old["channels"] += [c for c in chans if c["key"] not in seen]
			old["fav"] = old["fav"] or bool(f.get("fav"))
			if _reArabic.search(title) and not _reArabic.search(old["title"]):
				old["title"] = title
			continue
		item = {"kind": "film", "id": str(f.get("id") or ""), "title": title, "en": (f.get("en") or "").strip(),
			"year": num(f.get("year"), None), "tmdb_id": num(f.get("tmdb_id")), "rating": f.get("rating"),
			"start": start, "stop": stop or start + 7200, "cat": (f.get("cat") or "").strip(),
			"short": (f.get("short") or "").strip(), "desc": (f.get("desc") or f.get("short") or "").strip(),
			"poster": f.get("poster") or "", "poster_url": f.get("poster_url") or "",
			"channels": chans, "fav": bool(f.get("fav"))}
		for k in keys:
			index[k] = item
		films.append(item)

	matches, index = [], {}
	for m in (data.get("matches") or [])[:200]:
		if not isinstance(m, dict):
			continue
		start, stop = num(m.get("start")), num(m.get("stop"))
		if not start or (stop and stop < now):
			continue
		home, away = (m.get("home") or "").strip(), (m.get("away") or "").strip()
		title = _reLive.sub("", (m.get("title") or "").strip())
		comp = _reLive.sub("", (m.get("comp") or "").strip())
		teams = frozenset(filter(None, (_plainNorm(m.get("home_en") or home), _plainNorm(m.get("away_en") or away))))
		key = (start // 300, teams or _plainNorm(title))
		chans = channels(m)
		if key in index:
			old = index[key]
			seen = {c["key"] for c in old["channels"]}
			old["channels"] += [c for c in chans if c["key"] not in seen]
			old["fav"] = old["fav"] or bool(m.get("fav"))
			if (_reArabic.search(home) or _reArabic.search(title)) and not (_reArabic.search(old["home"]) or _reArabic.search(old["title"])):
				old.update(title=title, home=home, away=away, comp=comp or old["comp"])
			continue
		item = {"kind": "match", "id": str(m.get("id") or ""), "title": title, "comp": comp, "home": home, "away": away,
			"start": start, "stop": stop or start + 7200, "score": m.get("score") or "", "first": bool(m.get("first")),
			"live": bool(m.get("live_broadcast")), "channels": chans, "fav": bool(m.get("fav")),
			"home_logo": m.get("home_logo") or "", "away_logo": m.get("away_logo") or "", "comp_logo": m.get("comp_logo") or ""}
		index[key] = item
		matches.append(item)
	films.sort(key=lambda x: (x["start"], not x["fav"]))
	matches.sort(key=lambda x: (x["start"], not x["fav"]))
	return films, matches


class TonightService:
	"""Reads the tonight file of the Saad EPG plugin in a background thread,
	only when it changed (checked at most once a minute)."""
	CHECK_EVERY = 60

	def __init__(self):
		self.path = confGet("tonight", "file", "/etc/enigma2/saadepg/tonight.json") or "/etc/enigma2/saadepg/tonight.json"
		self.films, self.matches, self.info = [], [], {}
		self.mtime = 0
		self.checked = 0
		self.error = ""
		self.busy = False
		self.lock = threading.Lock()
		self.listeners = []

	def refresh(self, force=False):
		"""Start a background check (never blocks)."""
		if self.busy or (not force and time.time() - self.checked < self.CHECK_EVERY):
			return
		with self.lock:
			if self.busy:
				return
			self.busy = True
		threading.Thread(target=self._run, name="NileGlass-tonight", daemon=True).start()

	def items(self, kind="film", now=None):
		self.refresh()
		now = now or time.time()
		return [x for x in (self.films if kind == "film" else self.matches) if x["stop"] > now]

	def soon(self, within=5400, now=None):
		"""Next film or match starting within `within` seconds; favourites first."""
		now = now or time.time()
		cand = [x for x in self.items("film", now) + self.items("match", now) if now - 120 <= x["start"] <= now + within]
		cand.sort(key=lambda x: (not x["fav"], x["start"]))
		return cand[0] if cand else None

	def forService(self, sref, now=None):
		key = serviceKey(sref)
		if not key:
			return []
		now = now or time.time()
		return [x for x in self.items("film", now) + self.items("match", now) if any(c["key"] == key for c in x["channels"])]

	def status(self):
		return {"file": self.path, "found": self.mtime > 0, "films": len(self.films), "matches": len(self.matches),
			"generated": self.info.get("generated") or 0, "state": self.info.get("status") or "", "error": self.error or self.info.get("error") or ""}

	def addListener(self, cb):
		if cb not in self.listeners:
			self.listeners.append(cb)

	def removeListener(self, cb):
		if cb in self.listeners:
			self.listeners.remove(cb)

	def _run(self):
		changed = False
		try:
			try:
				mtime = os.stat(self.path).st_mtime
			except OSError:
				mtime = 0
				if self.mtime:
					self.films, self.matches, self.info, changed = [], [], {}, True
				self.error = "no file"
			if mtime and mtime != self.mtime:
				with open(self.path, "r", encoding="utf-8") as f:
					data = json.load(f)
				if not isinstance(data, dict):
					raise ValueError("bad file")
				films, matches = normalizeTonight(data)
				self.films, self.matches = films, matches
				self.info = {k: data.get(k) for k in ("schema", "generated", "status", "error", "updated", "cloud")}
				self.error = ""
				changed = True
			self.mtime = mtime
		except Exception as err:
			self.error = str(err)[:100]
			log("tonight:", err)
		finally:
			self.checked = time.time()
			self.busy = False
		if changed:
			for cb in list(self.listeners):
				callInUiThread(cb)


# ------------------------------------------------------------------ weather
WMO_AR = {
	0: "صافٍ", 1: "صافٍ غالبًا", 2: "غائم جزئيًا", 3: "غائم",
	45: "ضباب", 48: "ضباب", 51: "رذاذ خفيف", 53: "رذاذ", 55: "رذاذ كثيف",
	56: "رذاذ متجمد", 57: "رذاذ متجمد", 61: "مطر خفيف", 63: "مطر", 65: "مطر غزير",
	66: "مطر متجمد", 67: "مطر متجمد", 71: "ثلج خفيف", 73: "ثلج", 75: "ثلج كثيف", 77: "حبيبات ثلج",
	80: "زخات مطر", 81: "زخات مطر", 82: "زخات غزيرة", 85: "زخات ثلج", 86: "زخات ثلج",
	95: "عاصفة رعدية", 96: "عاصفة رعدية", 99: "عاصفة رعدية",
}


def wmoIcon(code, isDay):
	if code is None:
		return "na"
	if code in (0, 1):
		return "clear_day" if isDay else "clear_night"
	if code == 2:
		return "partly_day" if isDay else "partly_night"
	if code == 3:
		return "cloudy"
	if code in (45, 48):
		return "fog"
	if code in (71, 73, 75, 77, 85, 86):
		return "snow"
	if code in (95, 96, 99):
		return "thunder"
	return "rain"


class WeatherService:
	UPDATE_EVERY = 30 * 60
	RETRY_AFTER = 5 * 60

	def __init__(self):
		self.enabled = confBool("weather", "enabled", True) and not liteMode()
		self.units = confGet("weather", "units", "C").upper()[:1]
		self.state = {}
		self.started = False
		self.wake = threading.Event()
		self.relocate = False

	def reload(self):
		"""New city / units / on-off from the settings: refresh now, no restart."""
		self.enabled = confBool("weather", "enabled", True) and not liteMode()
		self.units = confGet("weather", "units", "C").upper()[:1]
		if not self.enabled:
			self.state = {}
			return
		self.relocate = True
		self.wake.set()
		self._start()

	def get(self, key, default=""):
		self._start()
		return self.state.get(key, default)

	def _start(self):
		if self.started or not self.enabled:
			return
		self.started = True
		threading.Thread(target=self._loop, name="NileGlass-weather", daemon=True).start()

	def _cacheFile(self):
		return "/tmp/nileglass_weather.json"

	def _location(self):
		cid = confGet("weather", "city_id", "alexandria")
		if cid in CITIES:
			ar, en, lat, lon = CITIES[cid]
			return lat, lon, ar
		lat, lon = confGet("weather", "latitude"), confGet("weather", "longitude")
		city = confGet("weather", "city", "Alexandria")
		if lat and lon:
			return float(lat), float(lon), city
		url = "https://geocoding-api.open-meteo.com/v1/search?" + urlencode({"name": city, "count": 1, "language": "ar"})
		data = json.loads(httpGet(url, timeout=8).decode("utf-8"))
		res = (data.get("results") or [None])[0]
		if not res:
			raise ValueError("city not found: %s" % city)
		return res["latitude"], res["longitude"], res.get("name") or city

	def _loop(self):
		try:  # show the last known values immediately after a GUI restart
			with open(self._cacheFile(), "r", encoding="utf-8") as f:
				self.state = json.load(f)
		except Exception:
			pass
		location = None
		while True:
			delay = self.UPDATE_EVERY
			try:
				if self.relocate:
					self.relocate = False
					location = None
				if not self.enabled:
					raise ValueError("switched off")
				if location is None:
					location = self._location()
				lat, lon, city = location
				params = {"latitude": lat, "longitude": lon, "timezone": "auto",
					"current": "temperature_2m,weather_code,is_day,relative_humidity_2m,wind_speed_10m",
					"daily": "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max", "forecast_days": 5}
				if self.units == "F":
					params["temperature_unit"] = "fahrenheit"
				data = json.loads(httpGet("https://api.open-meteo.com/v1/forecast?" + urlencode(params), timeout=8).decode("utf-8"))
				cur = data.get("current") or {}
				daily = data.get("daily") or {}
				code = cur.get("weather_code")
				unit = "°F" if self.units == "F" else "°C"

				def fmt(v):
					return ("%d%s" % (round(v), unit)) if isinstance(v, (int, float)) else ""
				tmax = (daily.get("temperature_2m_max") or [None])[0]
				tmin = (daily.get("temperature_2m_min") or [None])[0]
				state = {
					"temp": fmt(cur.get("temperature_2m")),
					"city": city,
					"desc": WMO_AR.get(code, ""),
					"icon": wmoIcon(code, cur.get("is_day", 1)),
					"hilo": ("%s / %s" % (fmt(tmax), fmt(tmin))) if tmax is not None else "",
					"humidity": ("%d%%" % cur["relative_humidity_2m"]) if isinstance(cur.get("relative_humidity_2m"), (int, float)) else "",
					"wind": ("%d km/h" % round(cur["wind_speed_10m"])) if isinstance(cur.get("wind_speed_10m"), (int, float)) else "",
					"updated": int(time.time()),
					"days": [{"date": d, "icon": wmoIcon(c, 1), "desc": WMO_AR.get(c, ""), "max": fmt(hi), "min": fmt(lo), "rain": ("%d%%" % r) if isinstance(r, (int, float)) else ""}
						for d, c, hi, lo, r in zip(daily.get("time") or [], daily.get("weather_code") or [], daily.get("temperature_2m_max") or [],
							daily.get("temperature_2m_min") or [], daily.get("precipitation_probability_max") or [None] * 5)],
				}
				self.state = state
				try:
					with open(self._cacheFile(), "w", encoding="utf-8") as f:
						json.dump(state, f, ensure_ascii=False)
				except Exception:
					pass
			except Exception as err:
				if self.enabled:
					log("weather error:", err)
				delay = self.RETRY_AFTER
			self.wake.wait(delay)
			self.wake.clear()


def reloadSettings():
	"""Re-read nileglass.conf and apply what can change while running
	(posters, weather, EPG titles, tonight file). Returns True when a GUI
	restart is still needed (poster folder changed)."""
	global CONFIG
	oldCache = confGet("posters", "cache_dir", "auto")
	CONFIG = loadConfig()
	p = posters
	p.enabled = confBool("tmdb", "enabled", True) and not liteMode()
	p.apiKey = confGet("tmdb", "api_key", "")
	p.language = confGet("tmdb", "language", "ar")
	p.quality = "w500" if confGet("posters", "quality", "w342") == "w500" else "w342"
	try:
		p.maxFiles = max(50, int(confGet("posters", "max_files", "600")))
	except ValueError:
		pass
	p.negative = {}  # a new key or language may find what failed before
	epgTitles.enabled = confBool("posters", "epg_titles", True)
	p.skipSport = confBool("posters", "smart_sport", True)
	tonight.path = confGet("tonight", "file", tonight.path) or tonight.path
	tonight.mtime = 0
	tonight.refresh(force=True)
	weather.reload()
	return confGet("posters", "cache_dir", "auto") != oldCache


posters = PosterService()


# ---------------------------------------------------------------- translation
class Translator:
	"""Programme descriptions -> Arabic (titles are never translated).

	Free Google translate endpoint, one background thread, answers kept in
	memory and on disk (same text = no new request). Text that is already
	mostly Arabic, or very short, is left as it is."""

	URL = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=ar&dt=t&q="
	MEM = 400
	MAX_CHARS = 1800

	def __init__(self):
		self.mem = {}
		self.waiting = {}
		self.queue = queue.Queue()
		self.thread = None
		self.lock = threading.Lock()

	@property
	def enabled(self):
		return confBool("posters", "translate_epg", True) and not liteMode()

	@staticmethod
	def needs(text):
		if not text or len(text.strip()) < 12:
			return False
		letters = [c for c in text if c.isalpha()]
		if not letters:
			return False
		arabic = sum(1 for c in letters if "\u0600" <= c <= "\u06ff")
		return arabic < 0.3 * len(letters)

	@staticmethod
	def key(text):
		return hashlib.md5(text.encode("utf-8")).hexdigest()

	def folder(self):
		base = posters.metaDir and os.path.dirname(posters.metaDir.rstrip("/"))
		d = os.path.join(base or "/tmp/NileGlass", "translate")
		try:
			os.makedirs(d, exist_ok=True)
		except OSError:
			return None
		return d

	def cached(self, text):
		"""Translation if known (memory or disk), else None. Cheap."""
		if not self.needs(text):
			return text
		k = self.key(text)
		hit = self.mem.get(k)
		if hit is not None:
			return hit
		d = posters.metaDir and self.folder()
		if d:
			try:
				with open(os.path.join(d, k + ".txt"), encoding="utf-8") as f:
					hit = f.read()
				self._remember(k, hit)
				return hit
			except OSError:
				pass
		return None

	def _remember(self, k, value):
		if len(self.mem) >= self.MEM:
			self.mem.pop(next(iter(self.mem)))
		self.mem[k] = value

	def request(self, text, callback):
		"""Ask for a translation; callback(original, translated) on the UI thread."""
		if not self.enabled or not self.needs(text):
			return
		k = self.key(text)
		with self.lock:
			first = k not in self.waiting
			self.waiting.setdefault(k, []).append(callback)
		if first:
			self.queue.put((k, text))
			if self.thread is None or not self.thread.is_alive():
				self.thread = threading.Thread(target=self._loop, daemon=True)
				self.thread.start()

	def _loop(self):
		while True:
			try:
				k, text = self.queue.get(timeout=60)
			except queue.Empty:
				return
			result = None
			try:
				data = json.loads(httpGet(self.URL + quote(text[:self.MAX_CHARS]), timeout=6).decode("utf-8"))
				result = "".join(part[0] for part in data[0] if part and part[0]).strip() or None
			except Exception as err:
				log("translate:", err)
			if result:
				self._remember(k, result)
				d = self.folder()
				if d:
					try:
						with open(os.path.join(d, k + ".tmp"), "w", encoding="utf-8") as f:
							f.write(result)
						os.replace(os.path.join(d, k + ".tmp"), os.path.join(d, k + ".txt"))
					except OSError:
						pass
			with self.lock:
				callbacks = self.waiting.pop(k, [])
			if result:
				for cb in callbacks:
					callInUiThread(cb, text, result)


translator = Translator()
epgTitles = EpgTitleMap()
tonight = TonightService()
weather = WeatherService()
