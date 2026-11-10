# -*- coding: utf-8 -*-
# NileGlass FHD - settings screen (Plugins menu) + nightly poster download.
#
#   * look: accent colour, transparency, font, text size, infobar layout (live preview)
#   * posters: TMDB key, language, cache, quality, nightly download of the bouquets
#   * weather: city list
#   * yellow = test (key, internet, cache, recent errors)
#   * blue   = tools (download posters now, backup / restore settings, clear cache)
# Everything is stored in /etc/enigma2/nileglass.conf.

import os
import shutil
import threading
import time

from enigma import addFont, eEPGCache, eServiceCenter, eServiceReference, eTimer, gFont

from Components.config import config, ConfigSelection, ConfigSelectionNumber, ConfigText, ConfigYesNo, NoSave
from Components.Label import Label
from Components.Pixmap import Pixmap
from Plugins.Plugin import PluginDescriptor
from Screens.ChoiceBox import ChoiceBox
from Screens.Console import Console
from Screens.MessageBox import MessageBox
from Screens.Setup import Setup
from Screens.Standby import TryQuitMainloop

try:
	from Components.NileGlassCore import CONF_FILE, MOUNTS, CITIES, RECENT_ERRORS, confGet, confBool, posters, weather, epgTitles, tonight, httpGet, callInUiThread, isLocalMount
except Exception:  # skin files missing - keep the plugin loadable
	CONF_FILE = "/etc/enigma2/nileglass.conf"
	MOUNTS = ("/media/hdd", "/media/usb", "/media/mmc")
	CITIES = {"alexandria": ("الإسكندرية", "Alexandria", 31.2001, 29.9187)}
	RECENT_ERRORS = []
	posters = weather = epgTitles = tonight = httpGet = None

	def confGet(section, key, default=""):
		return default

	def confBool(section, key, default=True):
		return default

	def callInUiThread(fnc, *args):
		fnc(*args)

	def isLocalMount(path):
		return False

try:
	from Components import NileGlassStyle as Style
except Exception:
	Style = None

try:
	from . import updater
except Exception:
	updater = None

SKIN_DIR = "/usr/share/enigma2/NileGlass_FHD"
FONT_DIR = "/usr/share/fonts"


def isArabic():
	try:
		return config.osd.language.value.lower().startswith("ar")
	except Exception:
		return True


AR = isArabic()


def T(en, ar):
	return ar if AR else en


LANGS = [("ar", "العربية"), ("en", "English"), ("fr", "Français"), ("de", "Deutsch"), ("tr", "Türkçe"), ("es", "Español"), ("it", "Italiano"), ("fa", "فارسی")]

TEMPLATE = """# NileGlass FHD skin settings (written by the NileGlass setup screen)
# Restart the GUI after changing this file.

[tmdb]
api_key = {api_key}
language = {language}
enabled = {tmdb_enabled}

[posters]
cache_dir = {cache_dir}
max_files = {max_files}
quality = {quality}
prefetch = {prefetch}
prefetch_hour = {prefetch_hour}
epg_titles = {epg_titles}
epg_titles_url = {epg_titles_url}

[weather]
city_id = {city_id}
city = {city}
latitude = {latitude}
longitude = {longitude}
units = {units}
enabled = {weather_enabled}

[update]
auto = {update_auto}

[style]
infobar = {infobar}
accent = {accent}
transparency = {transparency}
font = {font}
font_size = {font_size}
"""


def cacheChoices():
	choices = [("auto", T("Automatic", "تلقائي"))]
	for m in MOUNTS:
		if os.path.isdir(m):
			choices.append((os.path.join(m, "NileGlass", "poster"), m))
	choices.append(("/tmp/NileGlass/poster", "/tmp (RAM)"))
	current = confGet("posters", "cache_dir", "auto")
	if current not in [c[0] for c in choices]:
		choices.append((current, current))
	return choices, current


def cityChoices():
	choices = [(cid, (v[0] if AR else v[1])) for cid, v in CITIES.items()]
	choices.append(("custom", T("Other city (type the name)", "مدينة أخرى (اكتب الاسم)")))
	return choices


def backupPath():
	for m in MOUNTS:
		if os.path.isdir(m) and isLocalMount(m):
			return os.path.join(m, "NileGlass", "backup", "nileglass.conf")
	return "/etc/enigma2/nileglass.conf.bak"


def findBackup():
	for m in MOUNTS:
		p = os.path.join(m, "NileGlass", "backup", "nileglass.conf")
		if os.path.isfile(p):
			return p
	return "/etc/enigma2/nileglass.conf.bak" if os.path.isfile("/etc/enigma2/nileglass.conf.bak") else None


def collectBouquetTitles(hours=8, maxServices=400):
	"""Titles of the coming programmes of all TV bouquets (in-memory EPG, fast)."""
	refs = []
	sc = eServiceCenter.getInstance()
	root = eServiceReference('1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.tv" ORDER BY bouquet')
	bouquets = sc.list(root)
	for b in (bouquets.getContent("R", True) if bouquets else None) or []:
		if not (b.flags & eServiceReference.isDirectory):
			continue
		lst = sc.list(b)
		for r in (lst.getContent("R", True) if lst else None) or []:
			if r.flags & (eServiceReference.isMarker | eServiceReference.isDirectory):
				continue
			refs.append(r.toString())
		if len(refs) >= maxServices:
			break
	epg = eEPGCache.getInstance()
	titles = []
	for ref in list(dict.fromkeys(refs))[:maxServices]:
		try:
			titles += [e[0] for e in (epg.lookupEvent(["T", (ref, 0, -1, hours * 60)]) or []) if e and e[0]]
		except Exception:
			pass
	return titles


class NileGlassSetup(Setup):
	def __init__(self, session):
		# --- look
		if Style:
			style = Style.readStyle()
			accents = [(k, Style.ACCENT_NAMES_AR[k] if AR else k.capitalize()) for k in Style.ACCENTS]
			fontsets = [(k, v) for k, v in Style.FONT_NAMES.items()]
		else:
			style = {"accent": "blue", "transparency": 20, "font": "ubuntu", "font_size": 100, "infobar": "full"}
			accents, fontsets = [("blue", "blue")], [("ubuntu", "Ubuntu")]
		self.infobar = NoSave(ConfigSelection(default=style.get("infobar", "full"), choices=[("full", T("Full (signal + details)", "كامل (الإشارة والتفاصيل)")), ("compact", T("Compact", "مختصر"))]))
		self.accent = NoSave(ConfigSelection(default=style["accent"], choices=accents))
		self.transparency = NoSave(ConfigSelection(default=str(style["transparency"]), choices=[
			("10", T("10% (almost solid)", "10% (شبه معتم)")), ("20", T("20% (default)", "20% (الافتراضي)")),
			("30", "30%"), ("40", "40%"), ("50", T("50% (very clear)", "50% (شفاف جدًا)"))]))
		self.font = NoSave(ConfigSelection(default=style["font"], choices=fontsets))
		self.fontSize = NoSave(ConfigSelection(default=str(style["font_size"]) if str(style["font_size"]) in ("90", "100", "110", "120") else "100", choices=[
			("90", T("Small", "صغير")), ("100", T("Normal", "عادي")), ("110", T("Large", "كبير")), ("120", T("Very large", "كبير جدًا"))]))
		# --- posters
		self.posters = NoSave(ConfigYesNo(default=confBool("tmdb", "enabled", True)))
		self.apiKey = NoSave(ConfigText(default=confGet("tmdb", "api_key", ""), fixed_size=False, visible_width=48))
		lang = confGet("tmdb", "language", "ar")
		self.language = NoSave(ConfigSelection(default=lang, choices=LANGS if lang in dict(LANGS) else LANGS + [(lang, lang)]))
		choices, current = cacheChoices()
		self.cacheDir = NoSave(ConfigSelection(default=current, choices=choices))
		try:
			maxFiles = int(confGet("posters", "max_files", "600"))
		except ValueError:
			maxFiles = 600
		self.maxFiles = NoSave(ConfigSelectionNumber(min=100, max=3000, stepwidth=100, default=min(3000, max(100, maxFiles // 100 * 100)), wraparound=True))
		self.quality = NoSave(ConfigSelection(default="w500" if confGet("posters", "quality", "w342") == "w500" else "w342", choices=[
			("w342", T("Normal (fast)", "عادية (أسرع)")), ("w500", T("High (sharper)", "عالية (أوضح)"))]))
		self.prefetch = NoSave(ConfigYesNo(default=confBool("posters", "prefetch", True)))
		try:
			hour = int(confGet("posters", "prefetch_hour", "4"))
		except ValueError:
			hour = 4
		self.epgTitles = NoSave(ConfigYesNo(default=confBool("posters", "epg_titles", True)))
		self.prefetchHour = NoSave(ConfigSelection(default=str(hour % 24), choices=[(str(h), "%02d:00" % h) for h in range(24)]))
		# --- weather
		self.weather = NoSave(ConfigYesNo(default=confBool("weather", "enabled", True)))
		cid = confGet("weather", "city_id", "alexandria")
		self.cityId = NoSave(ConfigSelection(default=cid if cid in CITIES or cid == "custom" else "alexandria", choices=cityChoices()))
		self.city = NoSave(ConfigText(default=confGet("weather", "city", "Alexandria"), fixed_size=False, visible_width=30))
		self.units = NoSave(ConfigSelection(default=confGet("weather", "units", "C").upper()[:1] or "C", choices=[("C", "°C"), ("F", "°F")]))
		self.updateAuto = NoSave(ConfigYesNo(default=confBool("update", "auto", True)))
		self.latitude = confGet("weather", "latitude", "")
		self.longitude = confGet("weather", "longitude", "")
		Setup.__init__(self, session, setup=None,
			yellow_button={"function": self.diagnose, "text": T("Test", "اختبار"), "helptext": T("Check key, internet and cache", "فحص المفتاح والإنترنت والتخزين")},
			blue_button={"function": self.tools, "text": T("Tools", "أدوات"), "helptext": T("Download, backup, restore, clear", "تحميل، نسخ احتياطي، استرجاع، مسح")})
		self["key_red"].setText(T("Cancel", "إلغاء"))
		self["key_green"].setText(T("Save", "حفظ"))
		# live preview (shown by the NileGlassSetup screen of the skin)
		self["preview_accent"] = Pixmap()
		self["preview_glass"] = Pixmap()
		self["preview_font"] = Label(T("Font sample  123  نموذج للخط", "نموذج للخط  123  Font sample"))
		self["preview_title"] = Label(T("Preview", "معاينة"))
		self.previewKey = None
		self.diagRunning = False
		self.onLayoutFinish.append(self.updatePreview)
		self.setTitle(T("NileGlass FHD settings", "إعدادات سكين NileGlass"))

	def createSetup(self):
		i = "   "
		items = [
			(T("— Look —", "— المظهر —"),),
			(i + T("Infobar", "شكل الإنفوبار"), self.infobar, T("Full shows signal and service details, compact only the programmes.", "الكامل يعرض الإشارة وتفاصيل القناة، والمختصر البرامج فقط.")),
			(i + T("Accent colour", "لون التمييز"), self.accent, T("Colour of selection bars, progress bars and highlights.", "لون شريط التحديد وأشرطة التقدم والعناوين.")),
			(i + T("Background transparency", "شفافية الخلفية"), self.transparency, T("How much of the picture shows through the bars and panels.", "مدى ظهور الصورة من خلف الإنفوبار والقوائم.")),
			(i + T("Font", "الخط"), self.font, T("Font used for all text.", "الخط المستخدم في كل النصوص.")),
			(i + T("Text size", "حجم الخط"), self.fontSize, T("Size of all text.", "حجم كل النصوص في السكين.")),
			(T("— Posters —", "— البوسترات —"),),
			(i + T("Show event posters", "عرض بوسترات البرامج"), self.posters, T("Posters, year, genre and rating of films and programmes.", "البوستر والسنة والنوع والتقييم للأفلام والبرامج.")),
		]
		if self.posters.value:
			items += [
				(i + T("TMDB API key", "مفتاح TMDB"), self.apiKey, T("Free key from themoviedb.org (Settings > API). Press OK to type it.", "مفتاح مجاني من موقع themoviedb.org (الإعدادات > API). اضغط OK للكتابة.")),
				(i + T("Search language", "لغة البحث"), self.language, ""),
				(i + T("Use English titles from SaadEPG", "استخدام الأسماء الإنجليزية من SaadEPG"), self.epgTitles, T("When TMDB does not know the Arabic title, search with the English title from your SaadEPG guide (about 0.8 MB once a day).", "لو TMDB مش عارف الاسم العربي، يبحث بالاسم الإنجليزي من دليل SaadEPG (حوالي 0.8 ميجا مرة يوميًا).")),
				(i + T("Poster quality", "جودة البوستر"), self.quality, T("High looks sharper but needs more internet and disk space.", "العالية أوضح لكنها تستهلك إنترنت ومساحة أكثر.")),
				(i + T("Poster cache", "مكان حفظ البوسترات"), self.cacheDir, T("A hard disk or USB stick is recommended.", "يُفضّل الهارد أو فلاشة USB.")),
				(i + T("Maximum posters kept", "أقصى عدد بوسترات"), self.maxFiles, T("Older posters are removed automatically.", "يُحذف الأقدم تلقائيًا.")),
				(i + T("Daily download of the bouquets", "تحميل يومي لبوسترات الباقات"), self.prefetch, T("Downloads posters of the coming programmes once a day, so they appear instantly.", "يحمّل بوسترات البرامج القادمة مرة يوميًا فتظهر فورًا وقت التقليب.")),
			]
			if self.prefetch.value:
				items.append((i + T("Download time", "وقت التحميل"), self.prefetchHour, T("Best at night while the receiver is idle.", "يُفضّل بالليل والجهاز غير مستخدم.")))
		items += [
			(T("— Weather —", "— الطقس —"),),
			(i + T("Show weather", "عرض الطقس"), self.weather, ""),
		]
		if self.weather.value:
			items.append((i + T("City", "المدينة"), self.cityId, T("Press OK for the list of cities.", "اضغط OK لعرض قائمة المدن.")))
			if self.cityId.value == "custom":
				items.append((i + T("City name", "اسم المدينة"), self.city, T("Type the city name in English or Arabic.", "اكتب اسم المدينة بالعربي أو الإنجليزي.")))
			items.append((i + T("Units", "الوحدة"), self.units, ""))
		items += [
			(T("— Updates —", "— التحديثات —"),),
			(i + T("Check for updates daily", "التحقق من التحديثات يوميًا"), self.updateAuto, T("Installed version: %s. Updates come from GitHub; your settings are kept.", "النسخة المثبتة: %s. التحديثات من GitHub وإعداداتك لا تتغير.") % (updater.installedVersion() if updater else "?")),
		]
		self["config"].list = items
		self.updatePreview()

	# ----------------------------------------------------------------- preview
	def updatePreview(self):
		if not Style or "preview_accent" not in self:
			return
		key = (self.accent.value, self.transparency.value, self.font.value, self.fontSize.value)
		if key == self.previewKey or not self["preview_accent"].instance:
			return
		self.previewKey = key
		try:
			acc = os.path.join(SKIN_DIR, "variants", "accent", self.accent.value, "ui", "sel_menu.png")
			if os.path.isfile(acc):
				self["preview_accent"].instance.setPixmapFromFile(acc)
			glass = os.path.join(SKIN_DIR, "variants", "glass", self.transparency.value, "ui", "ib_top_right.png")
			if os.path.isfile(glass):
				self["preview_glass"].instance.setPixmapFromFile(glass)
			fname, rel = Style.FONT_SETS[self.font.value]["Regular"]
			alias = "NGPreview_%s_%s" % (self.font.value, self.fontSize.value)
			addFont(os.path.join(FONT_DIR, fname), alias, int(rel * int(self.fontSize.value) / 100), False, 0)
			self["preview_font"].instance.setFont(gFont(alias, 34))
			self["preview_font"].setText(self["preview_font"].getText())
		except Exception as err:
			print("[NileGlass] preview:", err)

	# ----------------------------------------------------------------- save
	def values(self):
		custom = self.cityId.value == "custom"
		cityText = self.city.value.strip() or "Alexandria"
		keepCoords = custom and cityText == confGet("weather", "city", "") and confGet("weather", "city_id", "") == "custom"
		return {
			"api_key": self.apiKey.value.strip(),
			"language": self.language.value,
			"tmdb_enabled": 1 if self.posters.value else 0,
			"cache_dir": self.cacheDir.value,
			"max_files": self.maxFiles.value,
			"quality": self.quality.value,
			"prefetch": 1 if self.prefetch.value else 0,
			"prefetch_hour": self.prefetchHour.value,
			"epg_titles": 1 if self.epgTitles.value else 0,
			"epg_titles_url": confGet("posters", "epg_titles_url", "https://raw.githubusercontent.com/Saadmelshepiny/saadepg-data/epg"),
			"city_id": self.cityId.value,
			"city": cityText if custom else CITIES.get(self.cityId.value, ("", cityText))[1],
			"latitude": self.latitude if keepCoords else "",
			"longitude": self.longitude if keepCoords else "",
			"units": self.units.value,
			"weather_enabled": 1 if self.weather.value else 0,
			"update_auto": 1 if self.updateAuto.value else 0,
			"infobar": self.infobar.value,
			"accent": self.accent.value,
			"transparency": self.transparency.value,
			"font": self.font.value,
			"font_size": self.fontSize.value,
		}

	def keySave(self):
		try:
			tmp = CONF_FILE + ".tmp"
			with open(tmp, "w", encoding="utf-8") as f:
				f.write(TEMPLATE.format(**self.values()))
			os.replace(tmp, CONF_FILE)
			if Style:
				print("[NileGlass] style applied:", Style.apply())
		except Exception as err:
			self.session.open(MessageBox, T("Could not save settings:", "تعذّر حفظ الإعدادات:") + "\n%s" % err, MessageBox.TYPE_ERROR)
			return
		try:
			os.remove("/tmp/nileglass_weather.json")  # fresh weather after restart
		except OSError:
			pass
		self.askRestart(T("Settings saved.\nRestart the GUI now to apply them?", "تم حفظ الإعدادات.\nإعادة تشغيل الواجهة الآن لتطبيقها؟"))

	def askRestart(self, text):
		self.session.openWithCallback(self.restartAnswer, MessageBox, text, MessageBox.TYPE_YESNO)

	def restartAnswer(self, answer):
		if answer:
			self.session.open(TryQuitMainloop, 3)
			self.close()

	def keyCancel(self):
		self.close()

	# ----------------------------------------------------------------- yellow: test
	def diagnose(self):
		if self.diagRunning or posters is None:
			return
		self.diagRunning = True
		self["footnote"].setText(T("Testing ...", "جارٍ الفحص ..."))
		self["footnote"].show()
		threading.Thread(target=self._diagThread, name="NileGlass-diag", daemon=True).start()

	def _diagThread(self):
		lines = []
		ok, bad = "[OK]", "[X]"
		try:
			httpGet("https://api.open-meteo.com/v1/forecast?latitude=30&longitude=31&current=temperature_2m", timeout=6)
			lines.append("%s  %s" % (ok, T("Internet: working", "الإنترنت: يعمل")))
		except Exception as err:
			lines.append("%s  %s %s" % (bad, T("Internet: no connection", "الإنترنت: لا يوجد اتصال"), str(err)[:60]))
		valid, reason = posters.testKey()
		lines.append("%s  %s" % (ok if valid else bad, T("TMDB key: valid", "مفتاح TMDB: صالح") if valid else T("TMDB key: not working (%s)", "مفتاح TMDB: لا يعمل (%s)") % reason))
		st = posters.status()
		free = st.get("free")
		lines.append("%s  %s %s" % (ok if st.get("cache") else bad, T("Poster folder:", "مكان البوسترات:"), st.get("cache") or T("not available", "غير متاح")))
		lines.append("     %s %d   %s %d   %s %s" % (T("posters", "بوسترات"), st["posters"], T("backdrops", "خلفيات"), st["backdrops"],
			T("free", "مساحة حرة"), ("%.1f GB" % (free / 1073741824.0)) if free else "?"))
		s = st["stats"]
		lines.append("     %s %d   %s %d   %s %d   %s %d" % (T("downloaded", "تم تحميل"), s["downloads"], T("not found", "غير موجود"), s["notfound"],
			T("errors", "أخطاء"), s["errors"], T("waiting", "في الانتظار"), st["pending"]))
		et = epgTitles.status() if epgTitles else {}
		if et.get("enabled"):
			good = et.get("titles", 0) > 0
			lines.append("%s  %s %d   %s %d" % (ok if good else bad, T("SaadEPG titles:", "أسماء SaadEPG:"), et.get("titles", 0),
				T("found by them", "بوسترات بفضلها"), s.get("epg", 0)) + ("" if good else "  " + (et.get("error") or T("loading ...", "جارٍ التحميل ..."))))
		tn = tonight.status() if tonight else {}
		if tn:
			if tn.get("found"):
				gen = tn.get("generated")
				lines.append("%s  %s %d   %s %d   %s %s" % (ok, T("Tonight file: films", "ملف الليلة: أفلام"), tn["films"], T("matches", "ماتشات"), tn["matches"],
					T("updated", "تحديث"), time.strftime("%H:%M", time.localtime(gen)) if gen else "?"))
			else:
				lines.append("%s  %s %s" % (bad, T("Tonight file not found:", "ملف الليلة غير موجود:"), tn.get("file")))
		w = weather.state if weather else {}
		if w.get("updated"):
			lines.append("%s  %s %s %s (%s)" % (ok, T("Weather:", "الطقس:"), w.get("city", ""), w.get("temp", ""), time.strftime("%H:%M", time.localtime(w["updated"]))))
		else:
			lines.append("%s  %s" % (bad, T("Weather: not loaded yet", "الطقس: لم يتم التحميل بعد")))
		errs = list(RECENT_ERRORS)[-5:]
		if errs:
			lines.append("")
			lines.append(T("Recent errors:", "آخر الأخطاء:"))
			lines += ["  " + e for e in errs]
		callInUiThread(self._diagDone, "\n".join(lines))

	def _diagDone(self, text):
		self.diagRunning = False
		try:
			self["footnote"].setText("")
			self.session.open(MessageBox, text, MessageBox.TYPE_INFO, title=T("NileGlass test", "فحص NileGlass"))
		except Exception as err:
			print("[NileGlass] diag:", err)

	# ----------------------------------------------------------------- blue: tools
	def tools(self):
		items = [
			(T("Check for updates", "التحقق من التحديثات"), "update"),
			(T("Download posters of the bouquets now", "تحميل بوسترات الباقات الآن"), "prefetch"),
			(T("Backup settings", "نسخة احتياطية للإعدادات"), "backup"),
			(T("Restore settings", "استرجاع الإعدادات"), "restore"),
			(T("Clear posters and details", "مسح البوسترات والتفاصيل"), "clear"),
		]
		self.session.openWithCallback(self.toolChosen, ChoiceBox, title=T("Tools", "أدوات"), list=items)

	def toolChosen(self, choice):
		if not choice:
			return
		action = choice[1]
		if action == "update":
			checkForUpdate(self.session, quiet=False)
		elif action == "prefetch":
			n = posters.prefetch(collectBouquetTitles()) if posters else 0
			self.session.open(MessageBox, T("%d programmes queued. Posters are downloaded in the background.", "تمت إضافة %d برنامج. البوسترات تُحمّل في الخلفية.") % n, MessageBox.TYPE_INFO, timeout=6)
		elif action == "backup":
			dst = backupPath()
			try:
				os.makedirs(os.path.dirname(dst), exist_ok=True)
				with open(dst, "w", encoding="utf-8") as f:
					f.write(TEMPLATE.format(**self.values()))
				self.session.open(MessageBox, T("Settings saved to:", "تم حفظ الإعدادات في:") + "\n" + dst, MessageBox.TYPE_INFO, timeout=8)
			except Exception as err:
				self.session.open(MessageBox, str(err), MessageBox.TYPE_ERROR)
		elif action == "restore":
			src = findBackup()
			if not src:
				self.session.open(MessageBox, T("No backup found.", "لا توجد نسخة احتياطية."), MessageBox.TYPE_INFO, timeout=6)
				return
			try:
				shutil.copyfile(src, CONF_FILE)
				if Style:
					Style.apply()
				self.askRestart(T("Settings restored from:\n%s\nRestart the GUI now?", "تم استرجاع الإعدادات من:\n%s\nإعادة تشغيل الواجهة الآن؟") % src)
			except Exception as err:
				self.session.open(MessageBox, str(err), MessageBox.TYPE_ERROR)
		elif action == "clear":
			self.clearCache()

	def clearCache(self):
		removed = 0
		for d in set([c[0] for c in cacheChoices()[0] if c[0] != "auto"]):
			if d.rstrip("/").endswith("NileGlass/poster"):
				base = os.path.dirname(d.rstrip("/"))
				for sub in ("poster", "backdrop", "meta"):
					sd = os.path.join(base, sub)
					if os.path.isdir(sd):
						removed += len([n for n in os.listdir(sd) if n.endswith((".jpg", ".json"))])
						shutil.rmtree(sd, ignore_errors=True)
		self.session.open(MessageBox, T("Cleared (%d files). Restart the GUI to start fresh.", "تم المسح (%d ملف). أعد تشغيل الواجهة للبدء من جديد.") % removed, MessageBox.TYPE_INFO, timeout=6)


# --------------------------------------------------------------------- updates
def checkForUpdate(session, quiet=False):
	"""quiet=True: only a small popup when something new exists (daily check)."""
	if updater is None:
		return

	def gotInfo(info, error):
		if error or not info:
			if not quiet:
				session.open(MessageBox, T("Could not check for updates:", "تعذّر التحقق من التحديثات:") + "\n%s" % error, MessageBox.TYPE_ERROR, timeout=10)
			return
		if not updater.isNewer(info["version"]):
			if not quiet:
				session.open(MessageBox, T("NileGlass is up to date (%s).", "سكين NileGlass محدّث (%s).") % updater.installedVersion(), MessageBox.TYPE_INFO, timeout=6)
			return
		if quiet:
			try:
				from Tools import Notifications
				Notifications.AddPopup(T("A new NileGlass version (%s) is available.\nPlugins > NileGlass FHD > Tools", "يوجد إصدار جديد من سكين NileGlass (%s).\nالإضافات > NileGlass FHD > أدوات") % info["version"], MessageBox.TYPE_INFO, 15, "NileGlassUpdate")
			except Exception as err:
				print("[NileGlass] update popup:", err)
			return
		notes = info.get("notes_ar" if AR else "notes_en") or ""
		text = T("New version %s is available (installed %s).", "يوجد إصدار جديد %s (المثبت %s).") % (info["version"], updater.installedVersion())
		if notes:
			text += "\n\n" + notes
		text += "\n\n" + T("Download and install now?", "تحميل وتثبيت الآن؟")
		session.openWithCallback(lambda yes: yes and startDownload(info), MessageBox, text, MessageBox.TYPE_YESNO)

	def startDownload(info):
		session.open(MessageBox, T("Downloading the update ...", "جارٍ تحميل التحديث ..."), MessageBox.TYPE_INFO, timeout=3)
		updater.downloadAsync(info, downloaded)

	def downloaded(path, error):
		if error or not path:
			session.open(MessageBox, T("Download failed:", "فشل التحميل:") + "\n%s" % error, MessageBox.TYPE_ERROR)
			return
		session.openWithCallback(installed, Console, title=T("Installing NileGlass update", "تثبيت تحديث NileGlass"), cmdlist=[updater.installCommand(path)], closeOnSuccess=True)

	def installed(*args):
		session.openWithCallback(lambda yes: yes and session.open(TryQuitMainloop, 3), MessageBox,
			T("Update installed. Restart the GUI now?", "تم تثبيت التحديث. إعادة تشغيل الواجهة الآن؟"), MessageBox.TYPE_YESNO)

	updater.checkAsync(gotInfo)


# --------------------------------------------------------------------- nightly download
class NightlyPrefetch:
	CHECK_EVERY = 10 * 60 * 1000

	def __init__(self, session=None):
		self.session = session
		self.lastDay = None
		self.lastUpdateDay = None
		self.timer = eTimer()
		self.timer.callback.append(self.check)
		self.timer.start(self.CHECK_EVERY, False)

	def check(self):
		try:
			today = time.localtime().tm_yday
			if self.session and confBool("update", "auto", True) and self.lastUpdateDay != today:
				self.lastUpdateDay = today
				checkForUpdate(self.session, quiet=True)
		except Exception as err:
			print("[NileGlass] update check error:", err)
		try:
			if posters is None or not (confBool("posters", "prefetch", True) and confBool("tmdb", "enabled", True) and confGet("tmdb", "api_key", "")):
				return
			try:
				hour = int(confGet("posters", "prefetch_hour", "4")) % 24
			except ValueError:
				hour = 4
			now = time.localtime()
			if now.tm_hour == hour and self.lastDay != now.tm_yday:
				self.lastDay = now.tm_yday
				n = posters.prefetch(collectBouquetTitles())
				print("[NileGlass] nightly poster download: %d programmes queued" % n)
		except Exception as err:
			print("[NileGlass] nightly download error:", err)


nightly = None


def sessionstart(reason, session=None, **kwargs):
	global nightly
	if reason == 0 and nightly is None:
		try:
			if config.skin.primary_skin.value.startswith("NileGlass_FHD/"):
				nightly = NightlyPrefetch(session)
				if tonight is not None:
					tonight.refresh(force=True)
		except Exception as err:
			print("[NileGlass] sessionstart:", err)


def main(session, **kwargs):
	session.open(NileGlassSetup)


def openTonight(session, **kwargs):
	try:
		from .tonight import NileGlassTonight
		session.open(NileGlassTonight)
	except Exception as err:
		print("[NileGlass] tonight:", err)
		session.open(MessageBox, str(err), MessageBox.TYPE_ERROR, timeout=8)


def Plugins(**kwargs):
	return [
		PluginDescriptor(name="NileGlass FHD", description=T("Skin settings: look, posters, weather", "إعدادات السكين: المظهر والبوسترات والطقس"), where=PluginDescriptor.WHERE_PLUGINMENU, icon="plugin.png", fnc=main),
		PluginDescriptor(name=T("Tonight: films and matches", "الليلة: أفلام وماتشات"), description=T("Films and matches of tonight on your channels (Saad EPG)", "أفلام وماتشات الليلة على قنواتك (Saad EPG)"), where=PluginDescriptor.WHERE_PLUGINMENU, icon="tonight.png", fnc=openTonight),
		PluginDescriptor(name=T("Tonight: films and matches", "الليلة: أفلام وماتشات"), where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=openTonight),
		PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=sessionstart),
	]
