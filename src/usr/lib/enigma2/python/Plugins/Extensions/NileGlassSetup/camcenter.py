# -*- coding: utf-8 -*-
# NileGlass FHD - the emu center: everything about OScam / NCam in one place,
# in the skin's own screens.
#   * readers / lines of OScam and NCam (edit, add, delete, stop / start)
#   * live status (all readers, lines and clients, from the emu's own api)
#   * live log, emu information, the config files (read only, secrets hidden)
#   * CCcam.cfg -> readers, line test
# Reading only, in background threads; a timer runs only while its screen is
# on top.  Every change goes through the readers screen (confirmation, backup,
# safe write) - this file never writes an emu file itself.

import os
import re
import threading
import time

from enigma import eTimer

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

from .readers import (NileGlassReaders, SECRET, findCCcamCfg, findServerFile, runningEmu, webif)

try:
	from twisted.internet import reactor
except Exception:  # tests
	reactor = None

EMUS = ("oscam", "ncam")
FILES = ("{n}.conf", "{n}.server", "{n}.user", "{n}.dvbapi", "{n}.services", "{n}.srvid2", "{n}.srvid", "{n}.provid", "{n}.whitelist",
	"{n}.fs", "SoftCam.Key", "constant.cw", "CCcam.cfg")
HIDE = set(SECRET) | {"pwd", "httppwd", "httpuser", "pass", "passwd", "secret", "token", "account"}


def later(fn, *args):
	if reactor:
		reactor.callFromThread(fn, *args)
	else:
		fn(*args)


def background(work, done, name="NileGlass-emu"):
	def run():
		try:
			res = work()
		except Exception as err:
			print("[NileGlass] emu center:", err)
			res = None
		later(done, res)
	threading.Thread(target=run, name=name, daemon=True).start()


# ---------------------------------------------------------------- reading
def emuDirs():
	"""{emu: (config dir, server file)} for OScam and NCam (the running one first)"""
	running, cdir = runningEmu()
	out = {}
	for name in ([running] if running else []) + [n for n in EMUS if n != running]:
		path = findServerFile(name, cdir if name == running else None)
		if path and os.path.basename(path).startswith(name):
			out[name] = (cdir if name == running and cdir else os.path.dirname(path), path)
	return running, out


def versionInfo(name):
	"""/tmp/.oscam/oscam.version -> [(key, value)]"""
	p = "/tmp/.%s/%s.version" % (name, name)
	rows = []
	try:
		with open(p, errors="replace") as f:
			for line in f:
				if ":" in line:
					k, v = line.split(":", 1)
					rows.append((k.strip(), v.strip()))
	except Exception:
		pass
	return rows


INFO_AR = {"version": "النسخة", "compiler": "المترجم (compiler)", "box type": "نوع الجهاز", "pid": "رقم العملية (PID)", "tempdir": "فولدر المؤقت",
	"configdir": "فولدر الإعدادات", "webifport": "بورت الويب", "web interface support": "واجهة الويب", "livelog support": "السجل المباشر",
	"unix starttime": "وقت التشغيل", "starttime": "وقت التشغيل", "build date": "تاريخ البناء", "max. clients": "أقصى عدد عملاء"}


def nice(seconds):
	seconds = int(seconds)
	d, h, m = seconds // 86400, seconds % 86400 // 3600, seconds % 3600 // 60
	return ("%d يوم " % d if d else "") + "%d ساعة %d دقيقة" % (h, m)


def infoRows(name, cdir, root=None):
	"""-> [(shown key, value)]: the version file, then the api (uptime, readers count)"""
	rows = []
	for k, v in versionInfo(name):
		low = k.lower()
		if low in ("unix starttime",):
			try:
				rows.append(("شغال من", nice(time.time() - int(v))))
				continue
			except ValueError:
				pass
		rows.append((INFO_AR.get(low, k), v))
	if root is not None:
		osc = root if root.tag in ("oscam", "ncam") else root.find(name)
		if osc is not None:
			if osc.get("uptime"):
				rows = [r for r in rows if r[0] != "شغال من"]
				rows.insert(0, ("شغال من", nice(osc.get("uptime"))))
			if osc.get("version") and not any(k == "النسخة" for k, v in rows):
				rows.insert(0, ("النسخة", osc.get("version")))
	if not rows:
		rows.append(("—", "%s مش شغال، أو مفيش ملف /tmp/.%s/%s.version" % (name.upper(), name, name)))
	rows.append(("ملف السطور", findServerFile(name, cdir) or "—"))
	return rows


KIND = {"s": "سيرفر", "h": "الويب", "p": "سطر", "r": "كارت", "c": "عميل", "m": "مراقبة", "a": "تلقائي"}
STATE = (("CARDOK", "شغال"), ("CONNECTED", "متصل"), ("OK", "تمام"), ("NEEDINIT", "بيتصل ..."), ("OFF", "موقوف"), ("DISCONNECTED", "مقطوع"),
	("READER DEVICE", "الكارت مش موجود"), ("ERROR", "خطأ"), ("UNKNOWN", "غير معروف"))
GREEN, RED, AMBER, GREY = 0x3cc85a, 0xe23b3b, 0xf0c419, 0x9aa3ae


def stateAr(text):
	t = (text or "").strip().upper()
	for k, v in STATE:
		if t.startswith(k):
			return v
	return text.title() if text else "—"


def stateCol(ar):
	return GREEN if ar in ("شغال", "متصل", "تمام") else RED if ar in ("مقطوع", "خطأ", "الكارت مش موجود") else GREY if ar in ("موقوف", "—") else AMBER


def statusRows(root, onlyLines=False):
	"""-> [(name, kind, host, port, protocol, ecm, state, color)] readers and lines first"""
	rows = []
	if root is None:
		return rows
	order = {"r": 0, "p": 1, "c": 2, "s": 3, "h": 4, "m": 5, "a": 6}
	for c in root.iter("client"):
		t = c.get("type", "")
		if onlyLines and t not in ("r", "p"):
			continue
		conn = c.find("connection")
		req = c.find("request")
		ms = ""
		try:
			v = int((req.get("ecmtime") if req is not None else "") or 0)
			ms = "%d ms" % v if v > 0 else ""
		except ValueError:
			pass
		st = stateAr((conn.text or "") if conn is not None else "")
		rows.append((order.get(t, 9), c.get("name", "") or "?", KIND.get(t, t), conn.get("ip", "") if conn is not None else "",
			conn.get("port", "") if conn is not None else "", c.get("protocol", ""), ms, st, stateCol(st)))
	rows.sort(key=lambda r: (r[0], r[1].lower()))
	return [r[1:] for r in rows]


def statusSummary(rows):
	lines = [r for r in rows if r[1] in ("سطر", "كارت")]
	if not lines:
		return ""
	ok = [r for r in lines if r[7] == GREEN]
	bad = [r for r in lines if r[7] == RED]
	clients = sum(1 for r in rows if r[1] == "عميل")
	out = "شغال %d من %d" % (len(ok), len(lines))
	if bad:
		out += "   ·   واقع: " + "، ".join(r[0] for r in bad[:3]) + (" +%d" % (len(bad) - 3) if len(bad) > 3 else "")
	if clients:
		out += "   ·   عملاء: %d" % clients
	return out


def maskText(text):
	"""secret values -> ****  (key = value, C:/N: lines, F: users)"""
	out = []
	for line in text.splitlines():
		m = re.match(r"^(\s*)([A-Za-z0-9_\-]+)(\s*=\s*)(.+)$", line)
		if m and m.group(2).lower() in HIDE:
			line = m.group(1) + m.group(2) + m.group(3) + "****"
		else:
			m = re.match(r"^(\s*[CcNnFf]\s*:\s*)(\S+)(\s+)(\S+)(\s+)(\S+)(\s+)(\S+)(.*)$", line)
			if m:
				g = list(m.groups())
				if line.strip()[0] in "Ff":           # F: user pass ...
					g[3] = "****"
				else:                                  # C: host port user pass
					g[7] = "****"
				line = "".join(g)
		out.append(line)
	return "\n".join(out)


def tail(path, limit=65536):
	with open(path, "rb") as f:
		f.seek(0, 2)
		size = f.tell()
		f.seek(max(0, size - limit))
		data = f.read().decode("utf-8", "replace")
	return data.split("\n", 1)[1] if size > limit and "\n" in data else data


def logFile(name, cdir):
	"""the emu's log file from [global] logfile, else the usual places"""
	conf = os.path.join(cdir or "", "%s.conf" % name)
	cand = []
	try:
		section = ""
		with open(conf, errors="replace") as f:
			for line in f:
				s = line.strip()
				if s.startswith("["):
					section = s.lower()
				elif section == "[global]" and s.lower().startswith("logfile") and "=" in s:
					cand += [x.strip() for x in s.split("=", 1)[1].split(";")]
	except Exception:
		pass
	cand += ["/tmp/%s.log" % name, "/var/log/%s.log" % name, "/tmp/.%s/%s.log" % (name, name)]
	for p in cand:
		if p and p not in ("stdout", "syslog") and os.path.isfile(p):
			return p
	return None


def logText(name, cdir):
	"""the last log lines: the api's live log, else the log file"""
	root = webif(name, cdir, "part=status&appendlog=1")
	if root is not None:
		lg = root.find(".//log")
		if lg is not None and (lg.text or "").strip():
			return "الويب (السجل المباشر)", lg.text.strip()
	p = logFile(name, cdir)
	if p:
		return p, tail(p).strip()
	return "", ""


# ---------------------------------------------------------------- screens
class _Live(Screen):
	"""a screen that reads in the background every few seconds while it is on top"""
	EVERY = 5000

	def startLive(self):
		self.gone = False
		self.busy = False
		self.paused = False
		self.timer = eTimer()
		self.timer.callback.append(self.tick)
		self.onShow.append(lambda: self.timer.start(100, True))
		self.onHide.append(self.timer.stop)
		self.onClose.append(self.stopLive)

	def stopLive(self):
		self.gone = True
		self.timer.stop()

	def tick(self):
		if self.gone or self.busy or self.paused:
			return
		self.busy = True
		background(self.read, self._got)

	def _got(self, res):
		self.busy = False
		if self.gone:
			return
		self.show_(res)
		if self.shown and not self.paused:
			self.timer.start(self.EVERY, True)


class NileGlassCamStatus(_Live):
	"""all readers, lines and clients of the running emu, live"""

	def __init__(self, session, name, cdir):
		Screen.__init__(self, session)
		self.skinName = "NileGlassCamStatus"
		self.name, self.cdir = name, cdir
		self.setTitle("%s - الحالة المباشرة" % name.upper())
		self["list"] = List([])
		self["summary"] = Label("")
		self["hint"] = Label("")
		self["key_red"] = StaticText("")
		self["key_green"] = StaticText("تحديث")
		self["key_yellow"] = StaticText("السطور بس")
		self["key_blue"] = StaticText("الريدرات")
		self.onlyLines = False
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions"], {
			"cancel": self.close, "ok": self.close,
			"green": self.tick, "yellow": self.toggleLines, "blue": self.readers,
			"up": lambda: self["list"].up(), "down": lambda: self["list"].down(),
			"left": lambda: self["list"].pageUp(), "right": lambda: self["list"].pageDown(),
		}, -1)
		self.root = None
		self.startLive()

	def read(self):
		return webif(self.name, self.cdir, "part=status")

	def show_(self, root):
		self.root = root
		if root is None:
			self["list"].setList([])
			self["summary"].setText("")
			self["hint"].setText("واجهة الويب بتاعة %s مقفولة (httpport = 0) أو الإيمو مش شغال - الحالة المباشرة بتيجي منها." % self.name.upper())
			return
		self.fill()

	def fill(self):
		idx = self["list"].getIndex() if self["list"].list else 0
		rows = statusRows(self.root, self.onlyLines)
		self["list"].setList(rows)
		if rows:
			self["list"].setIndex(min(idx, len(rows) - 1))
		self["summary"].setText(statusSummary(rows))
		self["hint"].setText("آخر تحديث %s   ·   بيتحدث كل %d ثواني" % (time.strftime("%H:%M:%S"), self.EVERY // 1000))

	def toggleLines(self):
		self.onlyLines = not self.onlyLines
		self["key_yellow"].setText("الكل" if self.onlyLines else "السطور بس")
		if self.root is not None:
			self.fill()

	def readers(self):
		path = findServerFile(self.name, self.cdir)
		if path:
			self.session.open(NileGlassReaders, self.name, path)


class NileGlassCamInfo(Screen):
	def __init__(self, session, name, cdir):
		Screen.__init__(self, session)
		self.skinName = "NileGlassCamInfo"
		self.name, self.cdir = name, cdir
		self.setTitle("%s - معلومات" % name.upper())
		self["list"] = List([])
		self["hint"] = Label("")
		self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
			"cancel": self.close, "ok": self.close,
			"up": lambda: self["list"].up(), "down": lambda: self["list"].down(),
			"left": lambda: self["list"].pageUp(), "right": lambda: self["list"].pageDown(),
		}, -1)
		self.gone = False
		self.onClose.append(self.closing)
		self["list"].setList(infoRows(name, cdir))
		background(lambda: webif(name, cdir, "part=status"), self.got)

	def closing(self):
		self.gone = True

	def got(self, root):
		if not self.gone and root is not None:
			self["list"].setList(infoRows(self.name, self.cdir, root))


class NileGlassCamText(_Live):
	"""the live log (refreshes, yellow = pause) or one config file (secrets hidden, INFO shows them)"""
	EVERY = 3000

	def __init__(self, session, name, cdir, path=None):
		Screen.__init__(self, session)
		self.skinName = "NileGlassCamText"
		self.name, self.cdir, self.path = name, cdir, path
		self.setTitle(("%s - %s" % (name.upper(), os.path.basename(path))) if path else ("%s - السجل المباشر" % name.upper()))
		self["text"] = ScrollLabel("")
		self["file"] = Label("")
		self["hint"] = Label("")
		self["key_red"] = StaticText("")
		self["key_green"] = StaticText("" if path else "تحديث")
		self["key_yellow"] = StaticText("" if path else "إيقاف مؤقت")
		self["key_blue"] = StaticText("آخر السجل" if not path else "")
		self.secrets = False
		self.raw = ""
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "InfoActions"], {
			"cancel": self.close, "ok": self.close,
			"green": self.tick, "yellow": self.pause, "blue": self.end, "info": self.toggleSecrets,
			"up": lambda: self["text"].pageUp(), "down": lambda: self["text"].pageDown(),
			"left": lambda: self["text"].pageUp(), "right": lambda: self["text"].pageDown(),
		}, -1)
		self.first = True
		self.startLive()

	def read(self):
		if self.path:
			if os.path.getsize(self.path) > 512 * 1024:
				return self.path, tail(self.path, 512 * 1024)
			with open(self.path, encoding="utf-8", errors="replace") as f:
				return self.path, f.read()
		return logText(self.name, self.cdir)

	def show_(self, res):
		src, text = res or ("", "")
		self.raw = text
		self["file"].setText(src)
		if not text:
			self["text"].setText("مفيش سجل: الويب مقفولة ومفيش logfile في %s.conf" % self.name if not self.path else "الملف فاضي")
		else:
			self.render()
		if self.path:
			self.paused = True       # a file is read once
			self["hint"].setText("INFO: %s الباسوردات   ·   للتعديل: شاشة السطور (فيها نسخة احتياطية وتأكيد)" % ("إخفاء" if self.secrets else "إظهار"))
		else:
			self["hint"].setText("آخر تحديث %s   ·   الأصفر: %s" % (time.strftime("%H:%M:%S"), "تكملة" if self.paused else "إيقاف مؤقت"))

	def render(self):
		lines = self.raw.splitlines()[-400:]
		text = "\n".join(lines)
		self["text"].setText(text if self.secrets else maskText(text))
		if not self.path or self.first:
			if not self.path:
				self["text"].lastPage()
			self.first = False

	def toggleSecrets(self):
		self.secrets = not self.secrets
		if self.raw:
			self.render()
			if self.path:
				self["hint"].setText("INFO: %s الباسوردات   ·   للتعديل: شاشة السطور (فيها نسخة احتياطية وتأكيد)" % ("إخفاء" if self.secrets else "إظهار"))

	def pause(self):
		if self.path:
			return
		self.paused = not self.paused
		self["key_yellow"].setText("تكملة" if self.paused else "إيقاف مؤقت")
		if not self.paused:
			self.tick()

	def end(self):
		self["text"].lastPage()


class NileGlassCamCenter(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = "NileGlassCamCenter"
		self.setTitle("مركز الإيمو")
		self["list"] = List([])
		self["info"] = Label("")
		self["key_red"] = StaticText("")
		self["key_green"] = StaticText("إعادة تشغيل الإيمو")
		self["key_yellow"] = StaticText("")
		self["key_blue"] = StaticText("تبديل الإيمو")
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions"], {
			"ok": self.ok, "cancel": self.close, "green": self.askRestart, "blue": self.switch,
			"up": lambda: self["list"].up(), "down": lambda: self["list"].down(),
			"left": lambda: self["list"].pageUp(), "right": lambda: self["list"].pageDown(),
		}, -1)
		self.gone = False
		self.onClose.append(self.closing)
		self.onLayoutFinish.append(self.build)
		self.onShow.append(self.headline)

	def closing(self):
		self.gone = True

	def build(self):
		self.running, self.emus = emuDirs()
		run, cdir = self.running, (self.emus.get(self.running) or (None, None))[0]
		items = []
		for name, (d, path) in self.emus.items():
			items.append(("سطور وريدرات %s" % name.upper(), path, ("readers", name, path)))
		if run:
			items += [("الحالة المباشرة", "كل الريدرات والسطور والعملاء وحالتهم ووقت الـ ECM", ("status", run, cdir)),
				("السجل المباشر", "آخر سطور سجل %s، بيتحدث لوحده" % run.upper(), ("log", run, cdir)),
				("معلومات %s" % run.upper(), "النسخة، شغال من إمتى، الفولدرات، البورت", ("info", run, cdir))]
		if self.emus:
			items.append(("ملفات الإعدادات", "عرض بس (الباسوردات مخفية)", ("files", None, None)))
			cfg = findCCcamCfg()
			items.append(("تحويل CCcam.cfg لريدرات", cfg if cfg else "مفيش CCcam.cfg على الجهاز", ("import", None, None)))
			items.append(("اختبار السطور", "السيرفر بيرد ولا لأ، وفي كام ms", ("test", None, None)))
		if not items:
			items.append(("مفيش OScam ولا NCam", "شغّل إيمو الأول (الأزرق: تبديل الإيمو)", ("none", None, None)))
		self["list"].setList(items)
		self.headline()

	def headline(self):
		if not hasattr(self, "emus"):
			return
		if not self.running:
			self["info"].setText("مفيش إيمو شغال" if self.emus else "")
			return
		cdir = self.emus.get(self.running, (None, None))[0]
		self["info"].setText("الشغال: %s" % self.running.upper())

		def work():
			root = webif(self.running, cdir, "part=status", 2)
			rows = statusRows(root, True) if root is not None else []
			ver = dict(versionInfo(self.running)).get("Version", "")
			return ver, statusSummary(rows)

		def done(res):
			if self.gone or not res:
				return
			ver, summ = res
			self["info"].setText("   ·   ".join(x for x in ("الشغال: %s" % self.running.upper(), ver, summ) if x))
		background(work, done)

	def target(self):
		"""(emu, server file) for import / test: the running one, else ask"""
		if self.running in self.emus:
			return self.running, self.emus[self.running][1]
		name = list(self.emus)[0]
		return name, self.emus[name][1]

	def ok(self):
		cur = self["list"].getCurrent()
		if not cur:
			return
		what, a, b = cur[2]
		if what == "readers":
			self.session.openWithCallback(lambda *x: self.headline(), NileGlassReaders, a, b)
		elif what == "status":
			self.session.open(NileGlassCamStatus, a, b)
		elif what == "log":
			self.session.open(NileGlassCamText, a, b)
		elif what == "info":
			self.session.open(NileGlassCamInfo, a, b)
		elif what in ("import", "test"):
			name, path = self.target()
			self.session.open(NileGlassReaders, name, path, what)
		elif what == "files":
			self.files()
		elif what == "none":
			self.switch()

	def files(self):
		items = []
		for name, (d, path) in self.emus.items():
			for pat in FILES:
				p = os.path.join(d, pat.format(n=name))
				if os.path.isfile(p) and (name, p) not in [(i[1][0], i[1][2]) for i in items]:
					items.append(("%s   %s" % (os.path.basename(p), d), (name, d, p)))
		cfg = findCCcamCfg()
		if cfg and cfg not in [i[1][2] for i in items]:
			items.append(("%s   %s" % (os.path.basename(cfg), os.path.dirname(cfg)), (self.running or "oscam", None, cfg)))
		if not items:
			self.session.open(MessageBox, "مفيش ملفات إعدادات.", MessageBox.TYPE_INFO, timeout=5)
			return
		self.session.openWithCallback(lambda c: c and self.session.open(NileGlassCamText, c[1][0], c[1][1], c[1][2]), ChoiceBox, title="ملفات الإعدادات (عرض بس)", list=items)

	def askRestart(self):
		if not self.running:
			return
		self.session.openWithCallback(self.restart, MessageBox, "إعادة تشغيل %s؟" % self.running.upper(), MessageBox.TYPE_YESNO, default=False)

	def restart(self, yes):
		if not yes:
			return
		try:
			from .cambar import camSystem
			cams = camSystem()
			name = cams.current() if cams else None
			if not name:
				raise RuntimeError("مش لاقي الإيمو الشغال")
			cams.restart(name)
			self["info"].setText("جاري إعادة تشغيل %s ..." % name)
			t = self.restartTimer = eTimer()
			t.callback.append(self.headline)
			t.start(6000, True)
		except Exception as err:
			self.session.open(MessageBox, "إعادة التشغيل ما نفعتش:\n%s" % err, MessageBox.TYPE_WARNING)

	def switch(self):
		try:
			from .cambar import NileGlassCamBar
			self.session.openWithCallback(lambda *x: self.build(), NileGlassCamBar)
		except Exception as err:
			self.session.open(MessageBox, str(err), MessageBox.TYPE_ERROR, timeout=8)
