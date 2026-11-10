# -*- coding: utf-8 -*-
# NileGlass FHD - weather for today and the next days (Open-Meteo, no key).
# Data comes from Components.NileGlassCore.weather (background thread).

import os
import time

from enigma import eTimer

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Screens.Screen import Screen

from Components.NileGlassCore import weather

SKIN_DIR = "/usr/share/enigma2/NileGlass_FHD"
DAYS_AR = ("الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")


class NileGlassWeather(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		for name in ("city", "now_temp", "now_desc", "now_extra", "updated"):
			self[name] = Label("")
		self["now_icon"] = Pixmap()
		for i in range(5):
			self["day%d" % i] = Label("")
			self["temp%d" % i] = Label("")
			self["desc%d" % i] = Label("")
			self["icon%d" % i] = Pixmap()
		self["actions"] = ActionMap(["OkCancelActions"], {"ok": self.close, "cancel": self.close}, -1)
		self.timer = eTimer()
		self.timer.callback.append(self.fill)
		self.onLayoutFinish.append(self.fill)
		self.onClose.append(self.timer.stop)
		self.setTitle("الطقس")

	def icon(self, widget, name):
		path = os.path.join(SKIN_DIR, "weather", "%s.png" % (name or "na"))
		if self[widget].instance and os.path.isfile(path):
			self[widget].instance.setPixmapFromFile(path)
			self[widget].show()

	def fill(self):
		st = weather.state if weather else {}
		if not st.get("updated"):
			weather.get("temp")  # starts the service if needed
			self["now_desc"].setText("جارٍ تحميل الطقس ...")
			self.timer.start(2000, True)
			return
		self["city"].setText(st.get("city", ""))
		self["now_temp"].setText(st.get("temp", ""))
		self["now_desc"].setText(st.get("desc", ""))
		self["now_extra"].setText("  •  ".join(x for x in (("العظمى / الصغرى  " + st["hilo"]) if st.get("hilo") else "",
			("الرطوبة  " + st["humidity"]) if st.get("humidity") else "", ("الرياح  " + st["wind"]) if st.get("wind") else "") if x))
		self["updated"].setText("آخر تحديث  " + time.strftime("%H:%M", time.localtime(st["updated"])))
		self.icon("now_icon", st.get("icon"))
		for i, d in enumerate((st.get("days") or [])[:5]):
			try:
				t = time.strptime(d["date"], "%Y-%m-%d")
				name = "اليوم" if i == 0 else DAYS_AR[t.tm_wday]
			except Exception:
				name = d.get("date", "")
			self["day%d" % i].setText(name)
			self["temp%d" % i].setText("%s / %s" % (d.get("max", ""), d.get("min", "")))
			self["desc%d" % i].setText(d.get("desc", "") + (("\nمطر %s" % d["rain"]) if d.get("rain") and d["rain"] != "0%" else ""))
			self.icon("icon%d" % i, d.get("icon"))
		self.timer.start(10 * 60 * 1000, True)
