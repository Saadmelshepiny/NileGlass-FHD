# -*- coding: utf-8 -*-
"""Card sets (dashboards) beside NileGlass panels: shared by gen_menus_popup.py
and gen_dash.py."""
PANEL = "bg"
UI = "NileGlass_FHD/ui/"
DASH_W, DASH_H = 670, 464


SYS = "session.CurrentService"
FE = "session.FrontendStatus"
# Dashboards beside the menu / settings panel: one set per subject, the right
# one is shown for the menu or setting in use (Plugins/.../dashctx.py).  Each
# set lives on its own zPosition decade: 1x network, 2x tuners, 3x picture &
# sound, 4x system (x1 card backgrounds, x2 contents).
GROUPS = {"net": 1, "tuner": 2, "av": 3, "system": 4, "plugins": 5, "timers": 6, "pkgs": 7, "time": 8, "image": 9, "emu": 10, "bt": 11, "option": 12, "skin": 13}


class Dash:
	def __init__(self, g):
		self.bz, self.fz = GROUPS[g] * 10 + 1, GROUPS[g] * 10 + 2
		self.out = []

	def pix(self, x, y, w, h, name, front=False):
		if name.startswith("card_"):          # card: a rounded panel-coloured label (hidden with its set)
			self.out.append('\t\t<widget source="%s" render="FixedLabel" text="" position="%d,%d" size="%d,%d" backgroundColor="%s" cornerRadius="18" zPosition="%d"/>' % (SYS, x, y, w, h, PANEL, self.bz))
			return
		self.out.append('\t\t<widget source="%s" render="Pixmap" pixmap="%s%s" position="%d,%d" size="%d,%d" alphatest="blend" zPosition="%d"/>' % (SYS, UI, name, x, y, w, h, self.fz if front else self.bz))

	def text(self, x, y, w, h, t, font, color, halign="left"):
		self.out.append('\t\t<widget source="%s" render="FixedLabel" text="%s" position="%d,%d" size="%d,%d" font="%s" foregroundColor="%s" backgroundColor="%s" transparent="1" halign="%s" valign="center" noWrap="1" zPosition="%d"/>' % (SYS, t, x, y, w, h, font, color, PANEL, halign, self.fz))

	def line(self, x, y, w, h):
		self.out.append('\t\t<widget source="%s" render="FixedLabel" text="" position="%d,%d" size="%d,%d" backgroundColor="line" zPosition="%d"/>' % (SYS, x, y, w, h, self.fz))

	def lab(self, x, y, w, h, conv, font, color, halign="left", src=SYS, z=None):
		c = "".join('<convert type="%s">%s</convert>' % cv for cv in conv)
		self.out.append('\t\t<widget source="%s" render="Label" position="%d,%d" size="%d,%d" font="%s" foregroundColor="%s" backgroundColor="%s" transparent="1" halign="%s" valign="center" noWrap="1" zPosition="%d">%s</widget>' % (src, x, y, w, h, font, color, PANEL, halign, z or self.fz, c))

	def progress(self, x, y, w, conv, img, src=SYS):
		self.pix(x, y, w, 8, "bar_track.png")
		c = "".join('<convert type="%s">%s</convert>' % cv for cv in conv)
		self.out.append('\t\t<widget source="%s" render="Progress" position="%d,%d" size="%d,8" pixmap="%s%s" transparent="1" zPosition="%d">%s</widget>' % (src, x, y, w, UI, img, self.fz, c))

	def small(self, x, title, conv, color, sub, src=SYS):
		self.pix(x, 0, 214, 96, "card_s3.png")
		self.text(x + 16, 8, 182, 24, title, "Regular;18", "fgDim")
		for cv, col in (conv if isinstance(conv, list) else [(conv, color)]):
			self.lab(x + 16, 32, 186, 40, [cv] if isinstance(cv, tuple) else [("NGSysInfo", cv)], "Medium;30", col, src=src if isinstance(cv, tuple) else SYS)
		self.text(x + 16, 68, 186, 22, sub, "Regular;16", "fgMute")

	def rows(self, x0, y, rows, lw=170):
		for i, (label, conv, src) in enumerate(rows):
			yy = y + i * 34
			self.text(x0 + 22, yy, lw, 30, label, "Regular;20", "fgDim")
			self.lab(x0 + 22 + lw, yy, 626 - lw, 30, conv, "Regular;22", "fg", src=src)


def dashSystem(x0):
	d = Dash("system")
	for i, (t, conv, col, sub) in enumerate((("الحرارة", "CpuTemp", "gold", "حساس اللوحة"), ("المعالج", "LoadAvg", "accent", "الحمل · دقيقة"),
			("وقت التشغيل", "Uptime", "fg", "منذ الإقلاع"))):
		d.small(x0 + i * 228, t, conv, col, sub)
	y = 108
	d.pix(x0, y, 670, 220, "card_l.png")
	d.text(x0 + 22, y + 10, 200, 28, "النظام", "Regular;20", "fgDim")
	d.out.append('\t\t<widget source="%s" render="NGRing" position="%d,%d" size="130,130" alphatest="blend" zPosition="%d"><convert type="NGSysInfo">RamPercent</convert></widget>' % (SYS, x0 + 22, y + 42, d.fz))
	d.lab(x0 + 22, y + 82, 130, 36, [("NGSysInfo", "RamPercent")], "Medium;30", "fg", "center", z=d.fz + 1)
	d.text(x0 + 22, y + 116, 130, 22, "الذاكرة", "Regular;16", "fgDim", "center")
	d.lab(x0 + 2, y + 180, 170, 28, [("NGSysInfo", "RamMB")], "Regular;18", "fgDim", "center")
	for i, (name, free, pct, img) in enumerate((("الفلاش", "FlashFree", "FlashPercent", "bar_gold.png"), ("الهارد", "HddFreeOnly", "HddPercent", "bar_green.png"),
			("USB", "UsbFree", "UsbPercent", "bar_white.png"))):
		x, yy = x0 + 190, y + 42 + i * 60
		d.text(x, yy, 120, 30, name, "Medium;22", "fg")
		d.lab(x + 236, yy, 220, 30, [("NGSysInfo", free)], "Regular;20", "fgDim", "right")
		d.progress(x, yy + 36, 456, [("NGSysInfo", pct)], img)
	y = 340
	d.pix(x0, y, 670, 124, "card_m.png")
	d.text(x0 + 22, y + 10, 160, 26, "الشبكة", "Regular;20", "fgDim")
	d.lab(x0 + 200, y + 10, 150, 26, [("NGSysInfo", "OnlineYes")], "Medium;20", "green", "right")
	d.lab(x0 + 200, y + 10, 150, 26, [("NGSysInfo", "OnlineNo")], "Medium;20", "red", "right")
	d.lab(x0 + 22, y + 40, 330, 44, [("NGSysInfo", "IP")], "Medium;32", "fg")
	d.lab(x0 + 22, y + 86, 330, 26, [("NGSysInfo", "NetType")], "Regular;18", "fgDim")
	d.line(x0 + 368, y + 14, 1, 96)
	for x, t, conv, col, sub in ((x0 + 388, "تحميل", "NetDown", "accent", "سرعة التنزيل"), (x0 + 532, "رفع", "NetUp", "gold", "سرعة الرفع")):
		d.text(x, y + 10, 130, 26, t, "Regular;18", "fgDim")
		d.lab(x, y + 42, 136, 40, [("NGSysInfo", conv)], "Medium;24", col)
		d.text(x, y + 86, 136, 26, sub, "Regular;16", "fgMute")
	return d.out


def dashNet(x0):
	d = Dash("net")
	d.small(x0, "الشبكة", [(("NGContext", "Ssid"), "green")], None, "اسم الشبكة")
	d.small(x0 + 228, "سرعة الاتصال", [(("NGContext", "NetRate"), "accent")], None, "بين الجهاز والراوتر")
	d.small(x0 + 456, "التحميل الآن", "NetDown", "gold", "عبر الإنترنت")
	y = 108
	d.pix(x0, y, 670, 220, "card_l.png")
	d.text(x0 + 22, y + 10, 300, 28, "إعدادات الاتصال", "Regular;20", "fgDim")
	d.rows(x0, y + 44, [("العنوان IP", [("NGSysInfo", "IP")], SYS), ("البوابة", [("NGSysInfo", "Gateway")], SYS),
		("قوة الإشارة", [("NGContext", "Signal")], SYS), ("خوادم DNS", [("NGSysInfo", "Dns")], SYS), ("عنوان MAC", [("NGSysInfo", "Mac")], SYS)])
	y = 340
	d.pix(x0, y, 670, 124, "card_m.png")
	d.text(x0 + 22, y + 10, 300, 26, "حركة البيانات", "Regular;20", "fgDim")
	d.lab(x0 + 330, y + 10, 318, 26, [("NGSysInfo", "NetType")], "Regular;18", "fgMute", "right")
	for i, (t, conv, col) in enumerate((("تحميل", "NetDown", "accent"), ("رفع", "NetUp", "gold"), ("المستلم", "RxTotal", "fg"), ("المرسل", "TxTotal", "fg"))):
		x = x0 + 22 + i * 160
		d.text(x, y + 46, 150, 24, t, "Regular;18", "fgDim")
		d.lab(x, y + 74, 156, 36, [("NGSysInfo", conv)], "Medium;22", col)
	return d.out


def dashTuner(x0):
	d = Dash("tuner")
	d.small(x0, "جودة الإشارة", [(("FrontendInfo", "SNR"), "green")], None, "SNR", src=FE)
	d.small(x0 + 228, "قوة الاستقبال", [(("FrontendInfo", "AGC"), "accent")], None, "AGC", src=FE)
	d.small(x0 + 456, "الطبق", "Rotor", "gold", "موضع الموتور")
	y = 108
	d.pix(x0, y, 670, 220, "card_l.png")
	d.text(x0 + 22, y + 10, 300, 28, "القمر والتردد", "Regular;20", "fgDim")
	d.lab(x0 + 22, y + 42, 220, 40, [("ServiceOrbitalPosition", "Short")], "Medium;32", "fg")
	d.lab(x0 + 250, y + 46, 398, 34, [("PliExtraInfo", "TunerSystem")], "Medium;24", "accent", "right")
	d.lab(x0 + 22, y + 86, 626, 30, [("PliExtraInfo", "TransponderInfo")], "Regular;20", "fgDim")
	for i, (t, conv, val, img) in enumerate((("SNR", "SNR", "SNRdB", "bar_green.png"), ("AGC", "AGC", "AGC", "bar_white.png"))):
		yy = y + 130 + i * 42
		d.text(x0 + 22, yy, 70, 28, t, "Medium;20", "fg")
		d.progress(x0 + 100, yy + 10, 420, [("FrontendInfo", conv)], img, src=FE)
		d.lab(x0 + 530, yy, 118, 28, [("FrontendInfo", val)], "Regular;20", "fgDim", "right", src=FE)
	y = 340
	d.pix(x0, y, 670, 124, "card_m.png")
	d.text(x0 + 22, y + 10, 200, 26, "الموالفات", "Regular;20", "fgDim")
	d.lab(x0 + 22, y + 40, 120, 50, [("NGSysInfo", "TunerCount")], "Medium;40", "fg")
	d.text(x0 + 22, y + 88, 120, 24, "موالف", "Regular;16", "fgMute")
	d.line(x0 + 150, y + 14, 1, 96)
	d.lab(x0 + 172, y + 40, 476, 34, [("NGSysInfo", "TunerName")], "Medium;22", "fg")
	d.lab(x0 + 172, y + 78, 476, 30, [("NGSysInfo", "TunerTypes")], "Regular;20", "accent")
	return d.out


def dashAv(x0):
	d = Dash("av")
	d.small(x0, "الدقة", [(("NGCodec", "Resolution"), "accent")], None, "القناة الحالية")
	d.small(x0 + 228, "الفيديو", [(("NGCodec", "Video"), "gold")], None, "ترميز الصورة")
	d.small(x0 + 456, "الصوت", [(("NGCodec", "Audio"), "fg")], None, "ترميز الصوت")
	y = 108
	d.pix(x0, y, 670, 220, "card_l.png")
	d.text(x0 + 22, y + 10, 300, 28, "الصورة على الشاشة", "Regular;20", "fgDim")
	d.rows(x0, y + 44, [("مخرج الفيديو", [("NGSysInfo", "VideoOut")], SYS), ("الألوان", [("NGSysInfo", "HdmiColour")], SYS),
		("أبعاد الشاشة", [("NGSysInfo", "Aspect")], SYS), ("الإطارات", [("NGCodec", "Fps")], SYS), ("الصورة كاملة", [("NGCodec", "Full")], SYS)])
	y = 340
	d.pix(x0, y, 670, 124, "card_m.png")
	d.text(x0 + 22, y + 10, 200, 26, "الصوت", "Regular;20", "fgDim")
	d.lab(x0 + 22, y + 40, 200, 50, [("NGSysInfo", "Volume")], "Medium;40", "fg")
	d.text(x0 + 22, y + 88, 200, 24, "مستوى الصوت", "Regular;16", "fgMute")
	d.line(x0 + 240, y + 14, 1, 96)
	d.text(x0 + 262, y + 40, 150, 30, "Dolby / AC3", "Regular;20", "fgDim")
	d.lab(x0 + 420, y + 40, 228, 30, [("NGSysInfo", "Ac3")], "Medium;22", "gold", "right")
	d.text(x0 + 262, y + 80, 150, 30, "المسار", "Regular;20", "fgDim")
	d.lab(x0 + 420, y + 80, 228, 30, [("NGCodec", "Audio")], "Medium;22", "fg", "right")
	return d.out


CT = "global.CurrentTime"
HOST = "ctx"


def dashTime(x0):
	"""time settings: the time here and in the world, zone, summer time, where the time comes from"""
	d = Dash("time")
	C = lambda f: [("NGContext", f)]
	d.small(x0, "الساعة الآن", [(("NGContext", "Local"), "accent")], None, "توقيتك")
	d.small(x0 + 228, "التوقيت العالمي", [(("NGContext", "Utc"), "gold")], None, "UTC / جرينتش")
	d.small(x0 + 456, "فرق التوقيت", [(("NGContext", "Offset"), "fg")], None, "عن جرينتش")
	y = 108
	d.pix(x0, y, 670, 220, "card_l.png")
	d.text(x0 + 22, y + 10, 300, 28, "المنطقة والمزامنة", "Regular;20", "fgDim")
	d.rows(x0, y + 44, [("التاريخ", [("ClockToText", "Format:%A %d %B %Y")], CT), ("الهجري", [("NGHijri", "")], CT),
		("المنطقة", C("Zone"), SYS), ("الصيفي", C("Dst"), SYS), ("مصدر الوقت", C("Sync"), SYS)], lw=150)
	y = 340
	d.pix(x0, y, 670, 124, "card_m.png")
	d.text(x0 + 22, y + 10, 300, 26, "الساعة في مدن تانية", "Regular;20", "fgDim")
	for i in range(4):
		d.lab(x0 + 22 + (i % 2) * 320, y + 44 + (i // 2) * 38, 300, 34, C("City%d" % (i + 1)), "Medium;24", "fg")
	return d.out


def dashImage(x0):
	"""updates / image: the image, its versions, the updates waiting in the feed"""
	d = Dash("image")
	C = lambda f: [("NGContext", f)]
	d.small(x0, "بايثون", [(("NGContext", "Python"), "accent")], None, "Python")
	d.small(x0 + 228, "الكيرنل", [(("NGContext", "Kernel"), "gold")], None, "Linux kernel")
	d.small(x0 + 456, "شغال من", "Uptime", "fg", "آخر تشغيل للجهاز")
	y = 108
	d.pix(x0, y, 670, 220, "card_l.png")
	d.text(x0 + 22, y + 10, 300, 28, "الصورة", "Regular;20", "fgDim")
	d.lab(x0 + 22, y + 40, 626, 44, C("Image"), "Medium;30", "fg")
	d.rows(x0, y + 92, [("الجهاز", C("Model"), SYS), ("اتسطبت", C("Flashed"), SYS), ("آخر تعديل لإنيجما", C("Enigma"), SYS)], lw=190)
	y = 340
	d.pix(x0, y, 670, 124, "card_m.png")
	d.text(x0 + 22, y + 10, 300, 26, "التحديثات", "Regular;20", "fgDim")
	d.lab(x0 + 330, y + 10, 318, 26, C("FeedAge"), "Regular;18", "fgMute", "right")
	d.lab(x0 + 22, y + 44, 626, 40, C("Updates"), "Medium;28", "accent")
	d.text(x0 + 22, y + 88, 400, 24, "الفلاش الفاضي", "Regular;18", "fgDim")
	d.lab(x0 + 330, y + 86, 318, 26, [("NGSysInfo", "FlashFree")], "Regular;20", "fg", "right")
	return d.out


def dashEmu(x0):
	"""emu manager: the emu running, its version and time up, what it decodes now, the emus installed"""
	d = Dash("emu")
	C = lambda f: [("NGContext", f)]
	d.small(x0, "الإيمو الشغال", [(("NGContext", "EmuRunning"), "gold")], None, "دلوقتي")
	d.small(x0 + 228, "الإصدار", [(("NGContext", "EmuVersion"), "accent")], None, "من الإيمو نفسه")
	d.small(x0 + 456, "شغال من", [(("NGContext", "EmuUptime"), "fg")], None, "من غير توقف")
	y = 108
	d.pix(x0, y, 670, 220, "card_l.png")
	d.text(x0 + 22, y + 10, 300, 28, "فك التشفير للقناة دي", "Regular;20", "fgDim")
	d.lab(x0 + 330, y + 10, 318, 28, [("NGEcm", "State")], "Medium;20", "green", "right")
	d.rows(x0, y + 44, [("الشفرة", [("NGEcm", "Caid")], SYS), ("الريدر", [("NGEcm", "Reader")], SYS), ("السيرفر", [("NGEcm", "From")], SYS),
		("وقت ECM", [("NGEcm", "Time")], SYS), ("البروتوكول", [("NGEcm", "Protocol")], SYS)], lw=130)
	y = 340
	d.pix(x0, y, 670, 124, "card_m.png")
	d.text(x0 + 22, y + 10, 300, 26, "الإيمو المتثبت على الجهاز", "Regular;20", "fgDim")
	d.lab(x0 + 500, y + 10, 148, 26, C("EmuCount"), "Medium;22", "gold", "right")
	d.out.append('\t\t<widget source="%s" render="Label" position="%d,%d" size="626,64" font="Medium;24" foregroundColor="fg" backgroundColor="%s" transparent="1" halign="left" valign="top" zPosition="%d"><convert type="NGContext">EmuInstalled</convert></widget>' % (SYS, x0 + 22, y + 46, PANEL, d.fz))
	return d.out


def dashBt(x0):
	"""bluetooth: the devices connected now, paired ones, the adapter"""
	d = Dash("bt")
	d.small(x0, "متصل دلوقتي", [(("NGContext", "BtCount"), "accent")], None, "جهاز")
	d.small(x0 + 228, "مقترن", [(("NGContext", "BtPaired"), "gold")], None, "جهاز متسجل")
	d.small(x0 + 456, "البلوتوث", [(("NGContext", "BtAdapter"), "fg")], None, "على الريسيفر")
	y = 108
	d.pix(x0, y, 670, 220, "card_l.png")
	d.text(x0 + 22, y + 10, 300, 28, "الأجهزة المتصلة", "Regular;20", "fgDim")
	d.out.append('\t\t<widget source="%s" render="Label" position="%d,%d" size="626,160" font="Medium;30" foregroundColor="fg" backgroundColor="%s" transparent="1" halign="left" valign="top" zPosition="%d"><convert type="NGContext">BtConnected</convert></widget>' % (SYS, x0 + 22, y + 46, PANEL, d.fz))
	y = 340
	d.pix(x0, y, 670, 124, "card_m.png")
	d.text(x0 + 22, y + 10, 400, 26, "نصيحة", "Regular;20", "fgDim")
	d.text(x0 + 22, y + 44, 626, 30, "الريموت أو السماعة: شغّل وضع الاقتران على الجهاز الأول", "Regular;20", "fg")
	d.text(x0 + 22, y + 78, 626, 30, "وبعدين ابحث من الشاشة دي واختاره من القائمة", "Regular;20", "fg")
	return d.out


def dashOption(x0):
	"""a settings screen of its own: the option under the cursor, its value, default and choices, and the plugin it belongs to"""
	d = Dash("option")
	H = lambda f: [("NGHostInfo", f)]
	d.small(x0, "الإعدادات", [(("NGHostInfo", "Total"), "accent")], None, "في الشاشة دي", src=HOST)
	d.small(x0 + 228, "اتغيّر", [(("NGHostInfo", "Changed"), "gold")], None, "عن الافتراضي", src=HOST)
	d.small(x0 + 456, "الإصدار", [(("NGHostInfo", "OwnerVersion"), "fg")], None, "", src=HOST)
	d.lab(x0 + 456 + 16, 68, 186, 22, H("Owner"), "Regular;16", "fgMute", src=HOST)
	y = 108
	d.pix(x0, y, 670, 220, "card_l.png")
	d.text(x0 + 22, y + 10, 300, 28, "الاختيار الحالي", "Regular;20", "fgDim")
	d.lab(x0 + 22, y + 40, 626, 32, H("Item"), "Regular;24", "fg", src=HOST)
	d.lab(x0 + 22, y + 76, 626, 50, H("Value"), "Medium;36", "accent", src=HOST)
	d.rows(x0, y + 136, [("الافتراضي", H("Default"), HOST), ("النوع", H("Kind"), HOST)], lw=130)
	y = 340
	d.pix(x0, y, 670, 124, "card_m.png")
	d.text(x0 + 22, y + 10, 300, 26, "الاختيارات المتاحة", "Regular;20", "fgDim")
	d.out.append('\t\t<widget source="%s" render="Label" position="%d,%d" size="626,72" font="Regular;22" foregroundColor="fg" backgroundColor="%s" transparent="1" halign="left" valign="top" zPosition="%d"><convert type="NGHostInfo">Choices</convert></widget>' % (HOST, x0 + 22, y + 42, PANEL, d.fz))
	return d.out


SKINS = "skins"
SKIN_H = 740
PREVIEW = (22, 150, 626, 352)    # where the skin selector's own preview picture goes (tools/gen_more.py)


def dashSkin(x0):
	"""skin selector: the skin under the cursor - its preview, resolution, size, screens, fonts, colours"""
	d = Dash("skin")
	K = lambda f: [("NGSkinInfo", f)]
	d.small(x0, "الدقة", [(("NGSkinInfo", "Resolution"), "accent")], None, "مقاس الشاشات", src=SKINS)
	d.small(x0 + 228, "الحجم", [(("NGSkinInfo", "Size"), "gold")], None, "على الفلاش", src=SKINS)
	d.small(x0 + 456, "الشاشات", [(("NGSkinInfo", "Screens"), "fg")], None, "شاشة متصممة", src=SKINS)
	y = 108
	d.pix(x0, y, 670, 410, "card_l.png")
	d.text(x0 + 22, y + 10, 300, 28, "المعاينة", "Regular;20", "fgDim")
	d.lab(x0 + 260, y + 10, 388, 28, K("Name"), "Medium;22", "fg", "right", src=SKINS)
	y = 530
	d.pix(x0, y, 670, SKIN_H - y, "card_m.png")
	d.text(x0 + 22, y + 10, 300, 26, "عن الاسكين", "Regular;20", "fgDim")
	d.rows(x0, y + 40, [("المصمم", K("Author"), SKINS), ("الإصدار", K("Version"), SKINS), ("الخطوط", K("Fonts"), SKINS)], lw=120)
	d.text(x0 + 22, y + 148, 120, 30, "الألوان", "Regular;20", "fgDim")
	for i in range(6):
		d.out.append('\t\t<widget source="%s" render="NGSwatch" position="%d,%d" size="74,30" backgroundColor="bg" zPosition="%d" cornerRadius="8"><convert type="NGSkinInfo">Color%d</convert></widget>' % (SKINS, x0 + 142 + i * 84, y + 150, d.fz, i + 1))
	return d.out


def dashboard(x0):
	return dashSystem(x0) + dashNet(x0) + dashTuner(x0) + dashAv(x0)



LIST = "list"
PLUGIN_H = 820


def dashPlugins(x0):
	"""beside a plugin list: everything about the plugin under the cursor (Converter/NGPluginInfo.py)"""
	d = Dash("plugins")
	P = lambda f: [("NGPluginInfo", f)]

	def wrap(x, y, w, h, field, font, color, z=None):
		d.out.append('\t\t<widget source="%s" render="Label" position="%d,%d" size="%d,%d" font="%s" foregroundColor="%s" backgroundColor="%s" transparent="1" halign="left" valign="top" zPosition="%d"><convert type="NGPluginInfo">%s</convert></widget>' % (LIST, x, y, w, h, font, color, PANEL, z or d.fz, field))
	for i, (t, f, col, sub) in enumerate((("الإصدار", "Version", "accent", "المثبت على الجهاز"), ("آخر فتح", "Last", "gold", "من الريموت"), ("مرات الفتح", "Runs", "fg", "من أول ما اتسجل"))):
		d.small(x0 + i * 228, t, [(("NGPluginInfo", f), col)], None, sub, src=LIST)
	y = 108
	d.pix(x0, y, 670, 296, "card_l.png")
	d.text(x0 + 22, y + 10, 300, 28, "عن الإضافة", "Regular;20", "fgDim")
	d.lab(x0 + 22, y + 40, 626, 48, P("Name"), "Medium;34", "fg", src=LIST)
	wrap(x0 + 22, y + 92, 626, 104, "Description", "Regular;24", "fgDim")
	d.line(x0 + 22, y + 206, 626, 1)
	d.rows(x0, y + 216, [("الحزمة", P("Package"), LIST), ("المطوّر", P("Maker"), LIST)], lw=130)
	y = 416
	d.pix(x0, y, 670, 230, "card_l.png")
	d.text(x0 + 22, y + 10, 300, 28, "التثبيت", "Regular;20", "fgDim")
	d.rows(x0, y + 44, [("تاريخ التثبيت", P("Installed"), LIST), ("الحجم", P("Size"), LIST), ("النوع", P("Kind"), LIST),
		("في الفيد", P("Feed"), LIST), ("المجلد", P("Folder"), LIST)], lw=150)
	y = 658
	d.pix(x0, y, 670, PLUGIN_H - y, "card_m.png")
	d.text(x0 + 22, y + 10, 300, 28, "التشغيل", "Regular;20", "fgDim")
	d.text(x0 + 22, y + 44, 190, 30, "مع تشغيل الجهاز", "Regular;20", "fgDim")
	d.lab(x0 + 214, y + 44, 434, 30, P("Background"), "Medium;22", "green", src=LIST)
	d.text(x0 + 22, y + 82, 190, 30, "بيظهر في", "Regular;20", "fgDim")
	wrap(x0 + 214, y + 82, 434, 70, "Places", "Regular;22", "fg")
	return d.out


def dashTimers(x0):
	"""beside the timer list: the next recording, conflicts, room on the disk (Converter/NGTimerInfo.py)"""
	d = Dash("timers")
	T = lambda f: [("NGTimerInfo", f)]
	for i, (t, f, col, sub) in enumerate((("التسجيل الجاي", "NextIn", "gold", "من دلوقتي"), ("المجدول", "Count", "accent", "تسجيل جاي"),
			("التعارض", "Conflicts", "fg", "بين المؤقتات"))):
		d.small(x0 + i * 228, t, [(("NGTimerInfo", f), col)], None, sub)
	y = 108
	d.pix(x0, y, 670, 220, "card_l.png")
	d.text(x0 + 22, y + 10, 300, 28, "التسجيل الجاي", "Regular;20", "fgDim")
	d.lab(x0 + 22, y + 40, 626, 44, T("NextName"), "Medium;30", "fg")
	d.rows(x0, y + 92, [("الموعد", T("NextWhen"), SYS), ("القناة", T("NextChannel"), SYS), ("المدة", T("NextLength"), SYS)], lw=110)
	d.lab(x0 + 22, y + 92 + 3 * 34, 626, 26, T("Recording"), "Medium;20", "red")
	y = 340
	d.pix(x0, y, 670, 124, "card_m.png")
	d.text(x0 + 22, y + 10, 200, 26, "مكان التسجيل", "Regular;20", "fgDim")
	d.lab(x0 + 230, y + 10, 418, 26, T("Path"), "Regular;18", "fgMute", "right")
	d.lab(x0 + 22, y + 40, 300, 40, T("FreeSpace"), "Medium;28", "fg")
	d.lab(x0 + 330, y + 44, 318, 34, T("FreeHours"), "Regular;22", "gold", "right")
	d.progress(x0 + 22, y + 94, 626, T("UsedPercent"), "bar_green.png")
	return d.out


SEL = "ng_sel"


def dashPkgs(x0):
	"""beside the package list (download / remove): the package under the cursor"""
	d = Dash("pkgs")
	P = lambda f: [("NGPluginInfo", f)]
	for i, (t, f, col, sub) in enumerate((("حجم التحميل", "PkgSize", "accent", "من الفيد"), ("الحالة", "PkgState", "gold", "على الجهاز"),
			("الفلاش الفاضي", "Free", "fg", "دلوقتي"))):
		d.small(x0 + i * 228, t, [(("NGPluginInfo", f), col)], None, sub, src=SEL)
	y = 108
	d.pix(x0, y, 670, 296, "card_l.png")
	d.text(x0 + 22, y + 10, 300, 28, "الحزمة", "Regular;20", "fgDim")
	d.lab(x0 + 22, y + 40, 626, 44, P("PkgName"), "Medium;28", "fg", src=SEL)
	d.out.append('\t\t<widget source="%s" render="Label" position="%d,%d" size="626,104" font="Regular;24" foregroundColor="fgDim" backgroundColor="%s" transparent="1" halign="left" valign="top" zPosition="%d"><convert type="NGPluginInfo">PkgDescription</convert></widget>' % (SEL, x0 + 22, y + 90, PANEL, d.fz))
	d.line(x0 + 22, y + 206, 626, 1)
	d.rows(x0, y + 216, [("الإصدار", P("PkgVersion"), SEL), ("القسم", P("Section"), SEL)], lw=130)
	y = 416
	d.pix(x0, y, 670, 160, "card_m.png")
	d.text(x0 + 22, y + 10, 300, 28, "قبل ما تثبّت", "Regular;20", "fgDim")
	d.rows(x0, y + 44, [("بعد التثبيت", P("After"), SEL), ("المطلوب معاها", P("Depends"), SEL), ("المطوّر", P("PkgMaker"), SEL)], lw=170)
	return d.out


SPECIAL = {"DeliteGreenPanel": "plugins", "PluginBrowser": "plugins", "TimerEditList": "timers", "PluginDownloadBrowser": "pkgs", "SkinSelector": "skin"}
SPECIAL_BUILDERS = {"plugins": dashPlugins, "timers": dashTimers, "pkgs": dashPkgs, "skin": dashSkin}
SPECIAL_H = {"plugins": PLUGIN_H, "timers": DASH_H, "pkgs": 576, "skin": SKIN_H}


BUILDERS = {"system": dashSystem, "net": dashNet, "tuner": dashTuner, "av": dashAv, "time": dashTime, "image": dashImage, "emu": dashEmu, "bt": dashBt, "option": dashOption}
