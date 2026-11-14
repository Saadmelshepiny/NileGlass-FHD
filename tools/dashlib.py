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
GROUPS = {"net": 1, "tuner": 2, "av": 3, "system": 4}


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
	d.small(x0, "الحالة", [("OnlineYes", "green"), ("OnlineNo", "red")], None, "اتصال الشبكة")
	d.small(x0 + 228, "سرعة المنفذ", "LinkSpeed", "accent", "سرعة الربط")
	d.small(x0 + 456, "التحميل الآن", "NetDown", "gold", "عبر الإنترنت")
	y = 108
	d.pix(x0, y, 670, 220, "card_l.png")
	d.text(x0 + 22, y + 10, 300, 28, "إعدادات الاتصال", "Regular;20", "fgDim")
	d.rows(x0, y + 44, [("العنوان IP", [("NGSysInfo", "IP")], SYS), ("البوابة", [("NGSysInfo", "Gateway")], SYS),
		("قناع الشبكة", [("NGSysInfo", "Netmask")], SYS), ("خوادم DNS", [("NGSysInfo", "Dns")], SYS), ("عنوان MAC", [("NGSysInfo", "Mac")], SYS)])
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


def dashboard(x0):
	return dashSystem(x0) + dashNet(x0) + dashTuner(x0) + dashAv(x0)



BUILDERS = {"system": dashSystem, "net": dashNet, "tuner": dashTuner, "av": dashAv}
