# -*- coding: utf-8 -*-
# NileGlass FHD - the skin doctor: looks at everything that makes the box slow
# or unstable, says what it found in plain words, and offers a fix for what
# the skin itself can fix.  It only reads; a fix runs only when you say yes.
#
# Also: settings snapshots (automatic before every update, the last 10 kept)
# and the check after an update (a short note if something is wrong).

import glob
import os
import shutil
import time

OK, WARN, BAD = "ok", "warn", "bad"
SNAP_DIR = "/etc/enigma2/NileGlass_FHD/snapshots"
CONF = "/etc/enigma2/nileglass.conf"
KEEP_SNAPS = 10


# ---------------------------------------------------------------- settings snapshots
def snapshot(reason="manual"):
	"""copy of the settings file; -> path or None"""
	if not os.path.isfile(CONF):
		return None
	try:
		os.makedirs(SNAP_DIR, exist_ok=True)
		try:
			from .updater import installedVersion
			v = installedVersion()
		except Exception:
			v = "?"
		dst = os.path.join(SNAP_DIR, "%s_v%s_%s.conf" % (time.strftime("%Y%m%d-%H%M%S"), v, reason))
		shutil.copyfile(CONF, dst)
		for old in snapshots()[KEEP_SNAPS:]:
			try:
				os.remove(old[0])
			except OSError:
				pass
		return dst
	except Exception as err:
		print("[NileGlass] snapshot:", err)
		return None


def snapshots():
	"""[(path, text)] newest first"""
	out = []
	for p in sorted(glob.glob(os.path.join(SNAP_DIR, "*.conf")), reverse=True):
		name = os.path.basename(p)[:-5]
		parts = name.split("_", 2)
		try:
			when = time.strftime("%d/%m %H:%M", time.strptime(parts[0], "%Y%m%d-%H%M%S"))
		except Exception:
			when = parts[0]
		why = {"update": "قبل التحديث", "manual": "يدوي", "doctor": "قبل إصلاح"}.get(parts[2] if len(parts) > 2 else "", parts[2] if len(parts) > 2 else "")
		out.append((p, "%s   %s   %s" % (when, parts[1] if len(parts) > 1 else "", why)))
	return out


# ---------------------------------------------------------------- the checks
def _free(path):
	try:
		s = os.statvfs(path)
		return s.f_blocks * s.f_frsize, s.f_bavail * s.f_frsize
	except Exception:
		return 0, 0


def _size(path, limit=20000):
	total, n = 0, 0
	for root, dirs, files in os.walk(path):
		for f in files:
			n += 1
			if n > limit:
				return total, True
			try:
				total += os.path.getsize(os.path.join(root, f))
			except OSError:
				pass
	return total, False


def mb(n):
	return "%d MB" % (n // 1048576) if n < 10 * 1073741824 else "%.1f GB" % (n / 1073741824.0)


def checks():
	"""-> [(state, title, detail, fix id or None)]"""
	out = []
	add = lambda *a: out.append(a)
	# 1. the style file
	try:
		from Components import NileGlassStyle as Style
		with open(Style.USER_XML, encoding="utf-8") as f:
			problems = Style._xmlProblems(f.read())
		if problems:
			add(BAD, "ملف الشكل فيه مشكلة", "; ".join(problems)[:200], "restyle")
		else:
			add(OK, "ملف الشكل سليم", "الخطوط والألوان كلها موجودة", None)
		if any("font" in x.lower() for x in problems):
			add(BAD, "الخط المختار ناقص ملفات", "", "font")
	except FileNotFoundError:
		add(WARN, "مفيش ملف شكل", "الإعدادات لسه متحفظتش", "restyle")
	except Exception as err:
		add(WARN, "تعذّر فحص ملف الشكل", str(err)[:120], None)
	# 2. space
	total, free = _free("/")
	if total:
		pct = 100 * (total - free) // total
		add(BAD if pct >= 95 else WARN if pct >= 85 else OK, "مساحة الفلاش", "مستخدم %d%% - فاضي %s" % (pct, mb(free)), "flashcache" if pct >= 85 else None)
	for m in ("/media/hdd", "/media/usb"):
		total, free = _free(m)
		if total and os.path.ismount(m):
			pct = 100 * (total - free) // total
			add(BAD if pct >= 97 else WARN if pct >= 90 else OK, "مساحة %s" % m, "مستخدم %d%% - فاضي %s" % (pct, mb(free)), None)
	# 3. posters cache
	try:
		from Components.NileGlassCore import posters
		d = posters.cacheDir if posters else None
		if d and os.path.isdir(os.path.dirname(d)):
			size, more = _size(os.path.dirname(d))
			onFlash = not d.startswith(("/media/", "/mnt/"))
			add(WARN if (onFlash and size > 150 * 1048576) else OK, "كاش البوسترات", "%s%s في %s" % (mb(size), "+" if more else "", os.path.dirname(d)), "trimcache" if onFlash and size > 150 * 1048576 else None)
	except Exception:
		pass
	# 4. picons
	picons = [p for p in ("/usr/share/enigma2/picon", "/media/hdd/picon", "/media/usb/picon", "/picon", "/media/mmc/picon") if os.path.isdir(p) and glob.glob(os.path.join(p, "*.png"))[:1]]
	add(OK if picons else WARN, "لوجوهات القنوات", picons[0] if picons else "مفيش فولدر picon - اللوجوهات مش هتظهر", None)
	# 5. EPG data
	epg = None
	try:
		from Components.config import config
		epg = config.misc.epgcache_filename.value
	except Exception:
		pass
	epg = epg or "/media/hdd/epg.dat"
	if os.path.isfile(epg):
		age = (time.time() - os.path.getmtime(epg)) / 86400
		add(WARN if age > 3 else OK, "بيانات الدليل (EPG)", "آخر حفظ من %d يوم" % age if age >= 1 else "متحدّثة", None)
	# 6. crashes
	try:
		from .crashguard import load
		recent = [c for c in load()["list"] if time.time() - c.get("time", 0) < 7 * 86400]
		if recent:
			by = {}
			for c in recent:
				by[c["blame"]] = by.get(c["blame"], 0) + 1
			add(BAD if by.get("NileGlass", 0) >= 2 else WARN, "الواجهة وقعت آخر أسبوع", "، ".join("%s ×%d" % (k, v) for k, v in sorted(by.items(), key=lambda kv: -kv[1])), "safemode" if by.get("NileGlass", 0) >= 2 else None)
		else:
			add(OK, "مفيش كراش آخر أسبوع", "", None)
	except Exception:
		pass
	# 7. who slows the box (speed report)
	try:
		from .perfwatch import LOG
		text = ""
		for p in (LOG + ".old", LOG):
			if os.path.isfile(p):
				text += open(p, encoding="utf-8", errors="ignore").read()
		who = {}
		for line in text.splitlines():
			parts = line.split()
			if len(parts) > 4 and parts[1] == "stall" and parts[4] != "-":
				top = parts[4].split(",")[0].rpartition(":")[0]
				if top:
					who[top] = who.get(top, 0) + 1
		if who:
			worst = sorted(who.items(), key=lambda kv: -kv[1])[:3]
			bg = [(k, v) for k, v in worst if k != "GUI"]
			add(WARN if sum(v for k, v in worst) >= 5 else OK, "مين بيوقّف الجهاز", "، ".join("%s ×%d" % (("الشاشات نفسها" if k == "GUI" else k), v) for k, v in worst), "lite" if not bg else None)
	except Exception:
		pass
	# 8. memory and background work
	try:
		import threading
		rss = int([l for l in open("/proc/self/status").read().splitlines() if l.startswith("VmRSS")][0].split()[1]) // 1024
		n = threading.active_count() - 1
		add(WARN if rss > 400 or n > 40 else OK, "الذاكرة والشغل في الخلفية", "ذاكرة الواجهة %d MB - شغل خلفي %d" % (rss, n), None)
	except Exception:
		pass
	# 9. settings snapshots
	snaps = snapshots()
	add(OK if snaps else WARN, "نسخ الإعدادات", ("آخر نسخة: %s" % snaps[0][1]) if snaps else "مفيش نسخة لسه", "snapshot")
	return out


LABEL = {OK: "تمام", WARN: "تنبيه", BAD: "مشكلة"}


def summary(items):
	bad = sum(1 for i in items if i[0] == BAD)
	warn = sum(1 for i in items if i[0] == WARN)
	return bad, warn


# ---------------------------------------------------------------- the fixes (asked first, in the screen)
FIXES = {
	"restyle": "يكتب ملف الشكل من جديد من إعداداتك",
	"font": "يرجّع الخط الافتراضي",
	"flashcache": "يمسح كاش السكين اللي على الفلاش (بوسترات وخلفيات)",
	"trimcache": "يمسح كاش البوسترات اللي على الفلاش",
	"safemode": "الوضع الآمن: الوضع الخفيف + الخط الافتراضي",
	"lite": "يشغّل الوضع الخفيف (أقصى سرعة)",
	"snapshot": "ياخد نسخة من الإعدادات دلوقتي",
}


def fix(fid, setConf=None):
	"""-> text of what was done; needs a GUI restart when it changed the look"""
	from Components import NileGlassStyle as Style
	if fid not in ("snapshot",):
		snapshot("doctor")
	if fid == "restyle":
		Style.apply()
		return "اتكتب من جديد - هيبان بعد إعادة تشغيل الواجهة"
	if fid in ("font", "safemode", "lite") and setConf:
		values = {"font": "ubuntu"} if fid == "font" else {"lite": 1} if fid == "lite" else {"lite": 1, "font": "ubuntu"}
		setConf({"style": values})
		Style.apply()
		return "اتعمل - هيبان بعد إعادة تشغيل الواجهة (ترجّعه من الإعدادات)"
	if fid in ("flashcache", "trimcache"):
		from Components.NileGlassCore import posters
		base = os.path.dirname(posters.cacheDir) if posters and posters.cacheDir else None
		if not base or base.startswith(("/media/", "/mnt/")):
			return "الكاش مش على الفلاش"
		n = 0
		for sub in ("poster", "backdrop", "thumb"):
			for p in glob.glob(os.path.join(base, sub, "*.jpg")):
				try:
					os.remove(p)
					n += 1
				except OSError:
					pass
		try:
			posters.index.clear()
		except Exception:
			pass
		return "اتمسح %d صورة" % n
	if fid == "snapshot":
		p = snapshot("manual")
		return "اتحفظت: %s" % p if p else "تعذّر الحفظ"
	return ""


def afterUpdate(session, delay=60000):
	"""first start of a new version: the doctor looks once, quietly; a note only when something is wrong"""
	try:
		from enigma import eTimer
		from .updater import installedVersion
	except Exception:
		return
	mark = "/etc/enigma2/NileGlass_FHD/doctor_version"
	try:
		seen = open(mark).read().strip()
	except Exception:
		seen = ""
	v = installedVersion()
	if seen == v:
		return

	def run():
		try:
			os.makedirs(os.path.dirname(mark), exist_ok=True)
			with open(mark, "w") as f:
				f.write(v)
			items = checks()
			bad = [i for i in items if i[0] == BAD]
			if bad:
				from Tools import Notifications
				from Screens.MessageBox import MessageBox
				Notifications.AddPopup("طبيب السكين لقى %d مشكلة بعد التحديث:\n%s\n\nافتحه من إعدادات السكين ← الأزرق ← طبيب السكين." % (len(bad), "\n".join("- %s: %s" % (b[1], b[2]) for b in bad[:3])),
					MessageBox.TYPE_WARNING, 20, "NileGlassDoctor")
		except Exception as err:
			print("[NileGlass] doctor:", err)
	t = eTimer()
	t.callback.append(run)
	t.start(delay, True)
	afterUpdate._t = t
