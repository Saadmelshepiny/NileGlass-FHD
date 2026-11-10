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

from enigma import addFont, eEPGCache, eLabel, eServiceCenter, eServiceReference, eTimer, gFont, gRGB

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
omdb_key = {omdb_key}

[posters]
cache_dir = {cache_dir}
max_files = {max_files}
quality = {quality}
prefetch = {prefetch}
prefetch_hour = {prefetch_hour}
epg_titles = {epg_titles}
epg_titles_url = {epg_titles_url}
neighbours = {neighbours}
smart_sport = {smart_sport}

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
infobar_size = {infobar_size}
text_color = {text_color}
bold_titles = {bold_titles}
outline = {outline}
direction = {direction}
translate = {translate}
channels = {channels}
sib = {sib}
menu_backdrop = {menu_backdrop}
opaque_screens = {opaque_screens}
text_finish = {text_finish}
ok_upcoming = {ok_upcoming}
lite = {lite}
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
			fontsets = Style.fontChoices()
			if style["font"] not in [k for k, v in fontsets]:
				fontsets.append((style["font"], style["font"].replace("skin:", "")))
		else:
			style = {"accent": "blue", "transparency": 20, "font": "ubuntu", "font_size": 100, "infobar": "full", "infobar_size": 100, "text_color": "white",
				"bold_titles": True, "outline": False, "direction": "auto", "translate": True}
			accents, fontsets = [("blue", "blue")], [("ubuntu", "Ubuntu")]
		self.infobar = NoSave(ConfigSelection(default=style.get("infobar", "full"), choices=[("full", T("Full (signal + details)", "كامل (الإشارة والتفاصيل)")), ("compact", T("Compact", "مختصر"))]))
		self.accent = NoSave(ConfigSelection(default=style["accent"], choices=accents))
		self.transparency = NoSave(ConfigSelection(default=str(style["transparency"]), choices=[
			("0", T("0% (solid - nothing behind)", "0% (معتم تمامًا - بدون أي خيالات)")), ("10", T("10% (almost solid)", "10% (شبه معتم)")), ("20", T("20% (default)", "20% (الافتراضي)")),
			("30", "30%"), ("40", "40%"), ("50", T("50% (very clear)", "50% (شفاف جدًا)"))]))
		self.font = NoSave(ConfigSelection(default=style["font"], choices=fontsets))
		sizes = [("80", T("Very small", "صغير جدًا")), ("90", T("Small", "صغير")), ("100", T("Normal", "عادي")), ("110", T("Large", "كبير")), ("120", T("Very large", "كبير جدًا")), ("130", T("Huge", "ضخم"))]
		self.fontSize = NoSave(ConfigSelection(default=str(style["font_size"]) if str(style["font_size"]) in dict(sizes) else "100", choices=sizes))
		self.infobarSize = NoSave(ConfigSelection(default=str(style.get("infobar_size", 100)) if str(style.get("infobar_size", 100)) in ("90", "100", "110", "120") else "100", choices=sizes[1:5]))
		colors = [(k, (Style.TEXT_COLOR_NAMES_AR[k] if AR else k.capitalize())) for k in Style.TEXT_COLORS] if Style else [("white", "white")]
		self.textColor = NoSave(ConfigSelection(default=style.get("text_color", "white"), choices=colors))
		self.boldTitles = NoSave(ConfigYesNo(default=bool(style.get("bold_titles", True))))
		self.outline = NoSave(ConfigYesNo(default=bool(style.get("outline", False))))
		self.direction = NoSave(ConfigSelection(default=style.get("direction", "auto"), choices=[
			("auto", T("Automatic (by menu language)", "تلقائي (حسب لغة الجهاز)")), ("rtl", T("Always right", "يمين دائمًا")), ("ltr", T("Always left", "شمال دائمًا"))]))
		self.translate = NoSave(ConfigYesNo(default=bool(style.get("translate", True))))
		self.preset = NoSave(ConfigSelection(default="none", choices=[("none", T("— keep my choices —", "— خليها زي ما هي —"))] +
			([(k, Style.PRESET_NAMES_AR[k] if AR else k.capitalize()) for k in Style.PRESETS] if Style else [])))
		self.channels = NoSave(ConfigSelection(default=style.get("channels", "posters"), choices=[
			("posters", T("Description + posters", "وصف + بوسترات")), ("simple", T("Wide list", "قائمة عريضة"))]))
		self.sib = NoSave(ConfigSelection(default=style.get("sib", "cinema"), choices=[
			("cinema", T("Cinema (posters row)", "سينما (صف بوسترات)")), ("classic", T("Classic (programme list)", "كلاسيك (قائمة برامج)"))]))
		self.menuBackdrop = NoSave(ConfigYesNo(default=bool(style.get("menu_backdrop", True))))
		self.lite = NoSave(ConfigYesNo(default=bool(style.get("lite", False))))
		self.okUpcoming = NoSave(ConfigYesNo(default=bool(style.get("ok_upcoming", True))))
		self.opaque = NoSave(ConfigYesNo(default=bool(style.get("opaque_screens", False))))
		self.finish = NoSave(ConfigSelection(default=style.get("text_finish", "normal"), choices=[
			("normal", T("Normal", "عادي")), ("glossy", T("Glossy (bright + shadow)", "لامع (أوضح + ظل)")), ("matte", T("Matte (soft)", "مطفي (هادي)"))]))
		self.omdbKey = NoSave(ConfigText(default=confGet("tmdb", "omdb_key", ""), fixed_size=False, visible_width=30))
		# the image's own settings, shown here for convenience
		try:
			self.ibTimeout = config.usage.infobar_timeout
			self.sibTimeout = config.usage.show_second_infobar
		except AttributeError:
			self.ibTimeout = self.sibTimeout = None
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
		self.neighbours = NoSave(ConfigYesNo(default=confBool("posters", "neighbours", True)))
		self.smartSport = NoSave(ConfigYesNo(default=confBool("posters", "smart_sport", True)))
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
		self["pv_ib_time"] = Label("22:30")
		self["pv_ib_title"] = Label(T("Tonight's film", "فيلم السهرة"))
		self["pv_head"] = Label(T("Main menu  القائمة", "القائمة الرئيسية  Menu"))
		self["pv_row"] = Label(T("Settings  الإعدادات", "الإعدادات  Settings"))
		self["pv_row2"] = Label(T("Timers  المؤقتات", "المؤقتات  Timers"))
		self["pv_desc"] = Label(T("A war drama set after 1967, about an officer who leads a special mission. 0123456789",
			"دراما حربية تدور أحداثها بعد 1967 عن ضابط يقود مهمة خاصة. Drama 0123456789"))
		self.previewKey = None
		self.diagRunning = False
		self.onLayoutFinish.append(self.updatePreview)
		from Components.ActionMap import ActionMap
		self["ngHelp"] = ActionMap(["InfoActions"], {"info": self.optionHelp}, -2)
		self["ngSections"] = ActionMap(["ChannelSelectBaseActions"], {"nextBouquet": lambda: self.jumpSection(1), "prevBouquet": lambda: self.jumpSection(-1)}, -2)
		self.setTitle(T("NileGlass FHD settings", "إعدادات سكين NileGlass"))

	def optionHelp(self):
		cur = self["config"].getCurrent()
		if cur and len(cur) > 2 and cur[2]:
			self.session.open(MessageBox, "%s\n\n%s\n\n%s" % (cur[0].strip(), cur[2], T("The preview on the right shows look changes before saving.", "المعاينة على اليمين بتوريك تغييرات الشكل قبل الحفظ.")), MessageBox.TYPE_INFO)

	def jumpSection(self, step):
		"""CH+/CH-: jump to the next / previous section of the settings."""
		lst = self["config"].list
		heads = [n for n, x in enumerate(lst) if len(x) < 2]
		cur = self["config"].getCurrentIndex()
		targets = [n for n in heads if (n > cur if step > 0 else n < cur - 1)]
		if targets:
			n = targets[0] if step > 0 else targets[-1]
			self["config"].setCurrentIndex(min(n + 1, len(lst) - 1))

	def changedEntry(self):
		if Style and self["config"].getCurrent() and len(self["config"].getCurrent()) > 1 and self["config"].getCurrent()[1] is self.preset and self.preset.value in Style.PRESETS:
			accent, transp, font, color = Style.PRESETS[self.preset.value]
			self.accent.value, self.transparency.value, self.textColor.value = accent, str(transp), color
			if font in [k for k, v in self.font.choices.choices]:
				self.font.value = font
		Setup.changedEntry(self)

	def createSetup(self):
		i = "   "
		items = [
			(T("— Look —", "— المظهر —"),),
			(i + T("Lite mode (fastest)", "الوضع الخفيف (أقصى سرعة)"), self.lite, T("Turns off the heavy parts: poster rows, pictures behind menus, text shadows.", "يقفل الحاجات التقيلة: صفوف البوسترات، الصور ورا القوائم، ظل الخط.")),
			(i + T("Ready-made style", "ستايل جاهز"), self.preset, T("Sets colour, transparency, font and text colour in one go.", "يغيّر اللون والشفافية والخط ولون النص مرة واحدة.")),
			(i + T("Channel list", "شكل قائمة القنوات"), self.channels, ""),
			(i + T("Second infobar", "شكل الإنفوبار الثاني"), self.sib, ""),
			(i + T("Event picture behind menus", "صورة البرنامج ورا القوائم"), self.menuBackdrop, T("The backdrop of the running programme behind the main menu and settings.", "خلفية البرنامج الشغال ورا القائمة الرئيسية والإعدادات.")),
			(i + T("Infobar", "شكل الإنفوبار"), self.infobar, T("Full shows signal and service details, compact only the programmes.", "الكامل يعرض الإشارة وتفاصيل القناة، والمختصر البرامج فقط.")),
			(i + T("Accent colour", "لون التمييز"), self.accent, T("Colour of selection bars, progress bars and highlights.", "لون شريط التحديد وأشرطة التقدم والعناوين.")),
			(i + T("Solid menus (no TV behind)", "قوائم معتمة تمامًا (بدون صورة القناة)"), self.opaque, T("Menus and plugin screens get a solid background; the infobar stays glassy.", "القوائم وشاشات الإضافات خلفيتها معتمة تمامًا، والإنفوبار يفضل شفاف.")),
			(i + T("Background transparency", "شفافية الخلفية"), self.transparency, T("How much of the picture shows through the bars and panels.", "مدى ظهور الصورة من خلف الإنفوبار والقوائم.")),
			(i + T("Font", "الخط"), self.font, T("Font used for all text.", "الخط المستخدم في كل النصوص.")),
			(i + T("Text size", "حجم الخط"), self.fontSize, T("Size of all text.", "حجم كل النصوص في السكين.")),
			(i + T("Bold titles", "عناوين عريضة"), self.boldTitles, T("Titles and channel names in the bold version of the font.", "العناوين وأسماء القنوات بالخط العريض.")),
			(i + T("Text finish", "شكل الخط (لامع / مطفي)"), self.finish, T("Glossy makes text brighter with a soft shadow, matte makes it calmer.", "اللامع أوضح وبظل خفيف، والمطفي أهدى للعين.")),
			(i + T("Text colour", "لون النص"), self.textColor, T("Colour of the normal text everywhere.", "لون الكتابة العادية في كل الشاشات.")),
			(i + T("Infobar text size", "حجم خط الإنفوبار"), self.infobarSize, T("Extra size step for the infobar only.", "حجم إضافي لكتابة الإنفوبار فقط.")),
			(i + T("Outline infobar text", "إطار حول كتابة الإنفوبار"), self.outline, T("A thin dark outline makes the infobar text readable over bright pictures.", "إطار أسود رفيع يوضّح الكتابة فوق الصور الفاتحة.")),
			(i + T("Text direction", "اتجاه الكتابة"), self.direction, T("Puts Arabic, English and mixed text of lists and menus on one side.", "يخلي الكتابة العربي والإنجليزي والمخلوطة في القوائم على ناحية واحدة.")),
			(i + T("Translate untranslated menus", "ترجمة القوائم غير المترجمة"), self.translate, T("Arabic for OpenBh menu items the image leaves in English (GUI restart).", "ترجمة عربية لعناصر قوائم OpenBh اللي الصورة سايباها إنجليزي (بعد إعادة التشغيل).")),
			(T("— Posters —", "— البوسترات —"),),
			(i + T("Show event posters", "عرض بوسترات البرامج"), self.posters, T("Posters, year, genre and rating of films and programmes.", "البوستر والسنة والنوع والتقييم للأفلام والبرامج.")),
		]
		if self.posters.value:
			items += [
				(i + T("TMDB API key", "مفتاح TMDB"), self.apiKey, T("Free key from themoviedb.org (Settings > API). Press OK to type it.", "مفتاح مجاني من موقع themoviedb.org (الإعدادات > API). اضغط OK للكتابة.")),
				(i + T("Search language", "لغة البحث"), self.language, ""),
				(i + T("OMDb key (IMDb rating)", "مفتاح OMDb (تقييم IMDb)"), self.omdbKey, T("Optional free key from omdbapi.com for IMDb ratings and awards.", "اختياري: مفتاح مجاني من omdbapi.com لتقييم IMDb والجوايز.")),
				(i + T("Use English titles from SaadEPG", "استخدام الأسماء الإنجليزية من SaadEPG"), self.epgTitles, T("When TMDB does not know the Arabic title, search with the English title from your SaadEPG guide (about 0.8 MB once a day).", "لو TMDB مش عارف الاسم العربي، يبحث بالاسم الإنجليزي من دليل SaadEPG (حوالي 0.8 ميجا مرة يوميًا).")),
				(i + T("Poster quality", "جودة البوستر"), self.quality, T("High looks sharper but needs more internet and disk space.", "العالية أوضح لكنها تستهلك إنترنت ومساحة أكثر.")),
				(i + T("Poster cache", "مكان حفظ البوسترات"), self.cacheDir, T("A hard disk or USB stick is recommended.", "يُفضّل الهارد أو فلاشة USB.")),
				(i + T("Maximum posters kept", "أقصى عدد بوسترات"), self.maxFiles, T("Older posters are removed automatically.", "يُحذف الأقدم تلقائيًا.")),
				(i + T("Prepare neighbouring channels", "تجهيز القنوات المجاورة"), self.neighbours, T("In the channel list, posters of the 2 channels above and below are downloaded in the background, so they show instantly when you move.", "في قائمة القنوات بيحمّل في الخلفية بوسترات قناتين فوق وقناتين تحت، فتظهر فورًا لما تتحرك عليهم.")),
				(i + T("Smart sport mode", "وضع الرياضة الذكي"), self.smartSport, T("No film poster during matches and sport programmes (TMDB has none and would show a wrong film). The infobar stays clear of the score.", "مفيش بوستر أفلام وقت الماتشات والبرامج الرياضية (TMDB معندوش ليها وكان هيجيب فيلم غلط)، والشريط ميغطيش النتيجة.")),
				(i + T("Daily download of the bouquets", "تحميل يومي لبوسترات الباقات"), self.prefetch, T("Downloads posters of the coming programmes once a day, so they appear instantly.", "يحمّل بوسترات البرامج القادمة مرة يوميًا فتظهر فورًا وقت التقليب.")),
			]
			if self.prefetch.value:
				items.append((i + T("Download time", "وقت التحميل"), self.prefetchHour, T("Best at night while the receiver is idle.", "يُفضّل بالليل والجهاز غير مستخدم.")))
		if self.ibTimeout is not None:
			items += [
				(T("— Infobar —", "— الإنفوبار —"),),
				(i + T("Infobar stays for", "مدة بقاء الإنفوبار"), self.ibTimeout, T("'No timeout' keeps it on screen until you press EXIT.", "«بدون مهلة» يخليه ظاهر لحد ما تضغط EXIT.")),
				(i + T("OK on the second infobar: coming up", "OK في الإنفوبار الثاني يفتح البرامج القادمة"), self.okUpcoming, T("Browse the next programmes with big posters and read their EPG (left/right).", "تتنقل بين البرامج الجاية ببوسترات كبيرة وتقرأ تفاصيلها (يمين/شمال).")),
				(i + T("Second infobar (OK twice)", "الإنفوبار الثاني (OK مرتين)"), self.sibTimeout, T("How long the second infobar stays, or what OK opens instead.", "مدة بقاء الإنفوبار الثاني، أو اللي يفتح بدله.")),
			]
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
		key = (self.accent.value, self.transparency.value, self.font.value, self.fontSize.value, self.infobarSize.value, self.textColor.value, self.finish.value,
			self.boldTitles.value, self.outline.value, self.direction.value)
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
			fontSet = Style.fontSet(self.font.value, copy=False)
			size = int(self.fontSize.value)
			ib = int(self.infobarSize.value)

			def alias(kind, extra=100):
				fname, rel = fontSet[kind if (kind != "Medium" or self.boldTitles.value) else "Regular"]
				name = "NGPv_%s_%s_%d_%d" % (self.font.value, kind, size, extra)
				addFont(fname if fname.startswith("/") else os.path.join(FONT_DIR, fname), name, int(rel * size * extra / 10000), False, 0)
				return name
			regular, medium = alias("Regular"), alias("Medium")
			ibRegular, ibMedium = alias("Regular", ib), alias("Medium", ib)
			fg, dim = (int(Style._finish(x, {"text_finish": self.finish.value}), 16) for x in Style.TEXT_COLORS[self.textColor.value])
			accent = int(Style.ACCENTS[self.accent.value][0], 16)
			rtl = Style.isRtl({"direction": self.direction.value}, config.osd.language.value)
			for name, font, pt, color, align in (
					("preview_font", regular, 32, fg, None), ("pv_head", medium, 36, fg, rtl), ("pv_row", regular, 32, 0xffffff, rtl),
					("pv_row2", regular, 32, fg, rtl), ("pv_desc", regular, 26, dim, rtl), ("pv_ib_time", ibRegular, 30, fg, None),
					("pv_ib_title", ibMedium, 32, accent, None)):
				inst = self[name].instance
				if not inst:
					continue
				inst.setFont(gFont(font, pt))
				inst.setForegroundColor(gRGB(color))
				if align is not None:
					inst.setHAlign(eLabel.alignRight if align else eLabel.alignLeft)
				if name.startswith("pv_ib"):
					try:
						inst.setBorderWidth(2 if self.outline.value else 0)
						inst.setBorderColor(gRGB(0))
					except Exception:
						pass
				self[name].setText(self[name].getText())  # repaint
		except Exception as err:
			print("[NileGlass] preview:", err)

	# ----------------------------------------------------------------- save
	def settingsValues(self):
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
			"neighbours": 1 if self.neighbours.value else 0,
			"smart_sport": 1 if self.smartSport.value else 0,
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
			"infobar_size": self.infobarSize.value,
			"text_color": self.textColor.value,
			"bold_titles": 1 if self.boldTitles.value else 0,
			"outline": 1 if self.outline.value else 0,
			"direction": self.direction.value,
			"translate": 1 if self.translate.value else 0,
			"channels": self.channels.value,
			"sib": self.sib.value,
			"menu_backdrop": 1 if self.menuBackdrop.value else 0,
			"opaque_screens": 1 if self.opaque.value else 0,
			"text_finish": self.finish.value,
			"ok_upcoming": 1 if self.okUpcoming.value else 0,
			"lite": 1 if self.lite.value else 0,
			"omdb_key": self.omdbKey.value.strip(),
		}

	def keySave(self):
		# the image's own infobar timeouts: applied at once
		for item in (self.ibTimeout, self.sibTimeout):
			if item is not None and item.isChanged():
				item.save()
		try:
			from Components.config import configfile
			configfile.save()
		except Exception:
			pass
		lookOld = Style.readStyle() if Style else {}
		try:
			tmp = CONF_FILE + ".tmp"
			with open(tmp, "w", encoding="utf-8") as f:
				f.write(TEMPLATE.format(**self.settingsValues()))
			os.replace(tmp, CONF_FILE)
			lookNew = Style.readStyle() if Style else {}
			lookChanged = any(lookOld.get(k) != lookNew.get(k) for k in lookNew if k not in ("translate", "ok_upcoming"))
			global OK_UPCOMING
			OK_UPCOMING = bool(lookNew.get("ok_upcoming", True)) or (lookOld.get("translate") and not lookNew.get("translate"))
			if Style and lookChanged:
				print("[NileGlass] style applied:", Style.apply())
		except Exception as err:
			self.session.open(MessageBox, T("Could not save settings:", "تعذّر حفظ الإعدادات:") + "\n%s" % err, MessageBox.TYPE_ERROR)
			return
		needRestart = lookChanged
		try:
			from Components.NileGlassCore import reloadSettings
			needRestart = reloadSettings() or needRestart
		except Exception as err:
			print("[NileGlass] reload:", err)
			needRestart = True
		if lookNew.get("translate"):
			installTranslations()
		if needRestart:
			self.askRestart(T("Settings saved.\nThe new look needs a GUI restart. Restart now?", "تم حفظ الإعدادات.\nالشكل الجديد محتاج إعادة تشغيل الواجهة. إعادة التشغيل الآن؟"))
		else:  # posters, weather, updates ... are already active
			self.session.open(MessageBox, T("Settings saved and applied.", "تم حفظ الإعدادات وتطبيقها."), MessageBox.TYPE_INFO, timeout=3)
			self.close()

	def askRestart(self, text):
		self.session.openWithCallback(self.restartAnswer, MessageBox, text, MessageBox.TYPE_YESNO)

	def restartAnswer(self, answer):
		if answer:
			self.session.open(TryQuitMainloop, 3)
			self.close()

	def keyCancel(self):
		for item in (self.ibTimeout, self.sibTimeout):
			if item is not None:
				item.cancel()  # undo unsaved changes of the image's own settings
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
			(T("Go back to the previous version", "الرجوع للنسخة السابقة"), "rollback"),
			(T("Run the first-start wizard again", "تشغيل معالج البداية مرة تانية"), "wizard"),
		]
		self.session.openWithCallback(self.toolChosen, ChoiceBox, title=T("Tools", "أدوات"), list=items)

	def toolChosen(self, choice):
		if not choice:
			return
		action = choice[1]
		if action == "update":
			checkForUpdate(self.session, quiet=False)
		elif action == "rollback":
			checkForUpdate(self.session, quiet=False, previous=True)
		elif action == "wizard":
			startWizard(self.session)
		elif action == "prefetch":
			n = posters.prefetch(collectBouquetTitles()) if posters else 0
			self.session.open(MessageBox, T("%d programmes queued. Posters are downloaded in the background.", "تمت إضافة %d برنامج. البوسترات تُحمّل في الخلفية.") % n, MessageBox.TYPE_INFO, timeout=6)
		elif action == "backup":
			dst = backupPath()
			try:
				os.makedirs(os.path.dirname(dst), exist_ok=True)
				with open(dst, "w", encoding="utf-8") as f:
					f.write(TEMPLATE.format(**self.settingsValues()))
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
def checkForUpdate(session, quiet=False, previous=False):
	"""quiet=True: only a small popup when something new exists (daily check)."""
	if updater is None:
		return

	def gotInfo(info, error):
		if error or not info:
			if not quiet:
				session.open(MessageBox, T("Could not check for updates:", "تعذّر التحقق من التحديثات:") + "\n%s" % error, MessageBox.TYPE_ERROR, timeout=10)
			return
		if previous:
			prev = info.get("previous") or {}
			if not prev.get("ipk"):
				session.open(MessageBox, T("No previous version is available.", "مفيش نسخة سابقة متاحة."), MessageBox.TYPE_INFO, timeout=6)
				return
			session.openWithCallback(lambda yes: yes and startDownload(prev), MessageBox,
				T("Install the previous version %s (installed %s)?", "تثبيت النسخة السابقة %s (المثبت %s)؟") % (prev.get("version"), updater.installedVersion()), MessageBox.TYPE_YESNO)
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
		session.open(Console, title=T("Installing NileGlass update", "تثبيت تحديث NileGlass"), cmdlist=[updater.installCommand(path)],
			finishedCallback=installed, closeOnSuccess=True)

	def installed(*args):
		if not os.path.isfile(updater.DONE_MARK):
			session.open(MessageBox, T("The update could not be installed. See the console text.", "تعذّر تثبيت التحديث. راجع النص في شاشة التثبيت."), MessageBox.TYPE_ERROR)
			return
		try:
			os.remove(updater.DONE_MARK)
		except OSError:
			pass
		session.open(MessageBox, T("Update installed. The GUI restarts now ...", "تم تثبيت التحديث. جارٍ إعادة تشغيل الواجهة ..."), MessageBox.TYPE_INFO, timeout=3)
		restartTimer.callback.append(lambda: session.open(TryQuitMainloop, 3))
		restartTimer.start(3000, True)

	restartTimer = eTimer()

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


# ---------------------------------------------------------------- translations
# Arabic for OpenBh strings the image leaves untranslated. Added as a gettext
# *fallback*, so it is only asked for texts the image's own catalogue lacks.
_trCatalog = None


def installTranslations():
	global _trCatalog
	try:
		if not (Style and Style.readStyle().get("translate", True)):
			return
		if not config.osd.language.value.lower().startswith("ar"):
			return
		import gettext
		import json
		from Components.Language import language
		if _trCatalog is None:
			with open(os.path.join(SKIN_DIR, "translations", "ar.json"), "r", encoding="utf-8") as f:
				table = json.load(f)

			class NGCatalog(gettext.NullTranslations):
				def gettext(self, message):
					if message in table:
						return table[message]
					return self._fallback.gettext(message) if self._fallback else message
			_trCatalog = NGCatalog()
			language.addCallback(installTranslations)  # a new catalogue after a language change
		cat = getattr(language, "catalog", None)
		if cat is None:
			return
		node = cat
		while getattr(node, "_fallback", None) is not None:  # already in the chain?
			if node._fallback is _trCatalog:
				return
			node = node._fallback
		cat.add_fallback(_trCatalog)
		print("[NileGlass] Arabic menu translations added")
	except Exception as err:
		print("[NileGlass] translations:", err)


OK_UPCOMING = True


def patchSecondInfoBar():
	"""OK while the second infobar is shown opens the 'coming up' browser."""
	global OK_UPCOMING
	try:
		from Screens import InfoBarGenerics as IBG
		cls = IBG.InfoBarShowHide
		if getattr(cls, "_ngPatched", False):
			return
		OK_UPCOMING = bool(Style.readStyle().get("ok_upcoming", True)) if Style else True
		original = cls.toggleShow

		def toggleShow(self):
			try:
				sib = getattr(self, "secondInfoBarScreen", None)
				if OK_UPCOMING and sib is not None and sib.shown and IBG.isStandardInfoBar(self):
					sib.hide()
					self.secondInfoBarWasShown = False
					from .upcoming import NileGlassUpcoming
					self.session.open(NileGlassUpcoming)
					return
			except Exception as err:
				print("[NileGlass] coming up:", err)
			return original(self)
		cls.toggleShow = toggleShow
		cls._ngPatched = True
	except Exception as err:
		print("[NileGlass] patch second infobar:", err)


def openFilm(session, **kwargs):
	"""Film page of the programme running now."""
	try:
		from enigma import eEPGCache
		ref = session.nav.getCurrentlyPlayingServiceReference()
		ev = eEPGCache.getInstance().lookupEventTime(ref, -1) if ref else None
		from .film import NileGlassFilm
		session.open(NileGlassFilm, ev.getEventName() if ev else "", ref)
	except Exception as err:
		print("[NileGlass] film page:", err)


def openUpcoming(session, **kwargs):
	from .upcoming import NileGlassUpcoming
	session.open(NileGlassUpcoming)


def sessionstart(reason, session=None, **kwargs):
	global nightly
	if reason == 0 and nightly is None:
		try:
			if config.skin.primary_skin.value.startswith("NileGlass_FHD/"):
				nightly = NightlyPrefetch(session)
				if tonight is not None:
					tonight.refresh(force=True)
				installTranslations()
				patchSecondInfoBar()
				try:
					from .neighbours import install as installNeighbours
					installNeighbours()
				except Exception as err:
					print("[NileGlass] neighbours:", err)
				try:
					from .startup import startupChecks
					startupChecks(session)
				except Exception as err:
					print("[NileGlass] startup checks:", err)
		except Exception as err:
			print("[NileGlass] sessionstart:", err)


def main(session, **kwargs):
	session.open(NileGlassSetup)


def startWizard(session):
	from .startup import startWizard as run
	run(session)


def openWeather(session, **kwargs):
	try:
		from .weatherscreen import NileGlassWeather
		session.open(NileGlassWeather)
	except Exception as err:
		print("[NileGlass] weather:", err)
		session.open(MessageBox, str(err), MessageBox.TYPE_ERROR, timeout=8)


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
		PluginDescriptor(name=T("Weather (5 days)", "الطقس (5 أيام)"), where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=openWeather),
		PluginDescriptor(name=T("Coming up (posters)", "البرامج القادمة (بوسترات)"), where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=openUpcoming),
		PluginDescriptor(name=T("Film page (now)", "صفحة الفيلم (الشغال دلوقتي)"), where=PluginDescriptor.WHERE_EXTENSIONSMENU, fnc=openFilm),
		PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=sessionstart),
	]
