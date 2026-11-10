# -*- coding: utf-8 -*-
# NileGlass FHD - things done once after the GUI starts:
#   * safe mode: the active style file is checked (fonts removed ...) and repaired
#   * crash watch: a new enigma2 crash log that mentions NileGlass -> offer the lite mode
#   * first-start wizard: style, font, city and TMDB key in four quick steps

import glob
import os
import threading
from configparser import ConfigParser

from enigma import eTimer

from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox

CONF_FILE = "/etc/enigma2/nileglass.conf"
USER_DIR = "/etc/enigma2/NileGlass_FHD"
WIZARD_FLAG = os.path.join(USER_DIR, ".wizard_done")
CRASH_SEEN = os.path.join(USER_DIR, ".crash_seen")
CRASH_DIRS = ("/home/root/logs", "/media/hdd/logs", "/media/usb/logs", "/home/root", "/tmp")

try:
	from Components import NileGlassStyle as Style
except Exception:
	Style = None

_timer = None


def setConf(values, section="style"):
	cp = ConfigParser()
	cp.read(CONF_FILE, encoding="utf-8")
	for sec, items in values.items():
		if not cp.has_section(sec):
			cp.add_section(sec)
		for k, v in items.items():
			cp.set(sec, k, str(v))
	tmp = CONF_FILE + ".tmp"
	with open(tmp, "w", encoding="utf-8") as f:
		cp.write(f)
	os.replace(tmp, CONF_FILE)


def restartQuestion(session, text):
	from Screens.Standby import TryQuitMainloop
	session.openWithCallback(lambda yes: yes and session.open(TryQuitMainloop, 3), MessageBox, text, MessageBox.TYPE_YESNO)


# ---------------------------------------------------------------- crash watch
def newCrash():
	"""(file, line) of a crash log newer than the last check that mentions NileGlass."""
	try:
		with open(CRASH_SEEN) as f:
			seen = float(f.read().strip() or 0)
	except Exception:
		seen = 0
	newest, hit = seen, None
	for d in CRASH_DIRS:
		for p in glob.glob(os.path.join(d, "enigma2_crash*.log")):
			try:
				m = os.path.getmtime(p)
			except OSError:
				continue
			if m <= seen:
				continue
			newest = max(newest, m)
			try:
				with open(p, "r", errors="replace") as f:
					text = f.read()[-20000:]
			except Exception:
				continue
			if "NileGlass" in text or "/NG" in text:
				line = next((ln.strip() for ln in reversed(text.splitlines()) if "NileGlass" in ln or "/NG" in ln), "")
				hit = (p, line[:160])
	if newest > seen:
		try:
			os.makedirs(USER_DIR, exist_ok=True)
			with open(CRASH_SEEN, "w") as f:
				f.write(str(newest))
		except Exception:
			pass
	return hit


def offerLite(session, hit):
	text = ("الواجهة وقعت المرة اللي فاتت بسبب جزء من سكين NileGlass:\n%s\n\nنفعّل الوضع الخفيف ونرجّع الخط الافتراضي؟ (تقدر ترجّعهم من الإعدادات)" % hit[1])

	def answer(yes):
		if yes:
			setConf({"style": {"lite": 1, "font": "ubuntu"}})
			if Style:
				Style.apply()
			restartQuestion(session, "تم. إعادة تشغيل الواجهة الآن؟")
	session.openWithCallback(answer, MessageBox, text, MessageBox.TYPE_YESNO)


# ---------------------------------------------------------------- wizard
def startWizard(session):
	if not Style:
		return
	state = {}

	def step1():
		items = [(Style.PRESET_NAMES_AR[k], k) for k in Style.PRESETS]
		session.openWithCallback(step2, ChoiceBox, title="1/4  مرحبًا في NileGlass - اختار الستايل", list=items)

	def step2(choice):
		if not choice:
			return finish(False)
		state["preset"] = choice[1]
		items = [(v, k) for k, v in Style.fontChoices()]
		session.openWithCallback(step3, ChoiceBox, title="2/4  اختار الخط", list=items)

	def step3(choice):
		if choice:
			state["font"] = choice[1]
		from Components.NileGlassCore import CITIES
		items = [(v[0], k) for k, v in CITIES.items()]
		session.openWithCallback(step4, ChoiceBox, title="3/4  مدينة الطقس", list=items)

	def step4(choice):
		if choice:
			state["city"] = choice[1]
		session.open(MessageBox, "4/4  جارٍ اختبار مفتاح TMDB والإنترنت ...", MessageBox.TYPE_INFO, timeout=3)

		def test():
			try:
				from Components.NileGlassCore import posters, callInUiThread
				ok, reason = posters.testKey()
				callInUiThread(done, ok, reason)
			except Exception as err:
				done(False, str(err))
		threading.Thread(target=test, name="NileGlass-wizard", daemon=True).start()

	def done(ok, reason):
		accent, transp, font, color = Style.PRESETS[state["preset"]]
		values = {"style": {"accent": accent, "transparency": transp, "font": state.get("font", font), "text_color": color}}
		if state.get("city"):
			from Components.NileGlassCore import CITIES
			values["weather"] = {"city_id": state["city"], "city": CITIES[state["city"]][1]}
		setConf(values)
		Style.apply()
		finish(True)
		key = "مفتاح TMDB يعمل، والبوسترات هتظهر." if ok else "مفتاح TMDB لا يعمل (%s). تقدر تكتبه من الإعدادات." % reason
		restartQuestion(session, "تم ضبط السكين.\n%s\n\nإعادة تشغيل الواجهة الآن لتطبيق الشكل؟" % key)

	def finish(_ok):
		try:
			os.makedirs(USER_DIR, exist_ok=True)
			open(WIZARD_FLAG, "w").close()
		except Exception:
			pass
	step1()


# ---------------------------------------------------------------- start-up
def startupChecks(session):
	"""Called from the plugin's session start (NileGlass is the active skin)."""
	global _timer
	problem = ""
	if Style:
		try:
			problem = Style.checkInstalled()
		except Exception as err:
			print("[NileGlass] safe mode:", err)
	hit = None
	try:
		hit = newCrash()
	except Exception as err:
		print("[NileGlass] crash watch:", err)

	def later():
		try:
			if problem:
				session.open(MessageBox, "وضع الأمان: كان فيه مشكلة في شكل السكين (%s) واتصلحت. هتتطبق بعد إعادة التشغيل." % problem[:120], MessageBox.TYPE_WARNING, timeout=15)
			elif hit:
				offerLite(session, hit)
			elif not os.path.isfile(WIZARD_FLAG):
				startWizard(session)
		except Exception as err:
			print("[NileGlass] startup:", err)
	_timer = eTimer()
	_timer.callback.append(later)
	_timer.start(20000, True)  # after the infobar and the first zap
