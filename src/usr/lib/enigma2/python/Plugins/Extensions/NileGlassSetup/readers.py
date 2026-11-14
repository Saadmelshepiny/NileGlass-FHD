# -*- coding: utf-8 -*-
# NileGlass FHD - readers / lines of the running OScam or NCam.
#
# Shows every [reader] of oscam.server / ncam.server with its live state, and
# lets YOU edit, delete, add, stop or start a reader.  Nothing happens by
# itself:
#  - every change needs a key press and a "yes" in a confirmation;
#  - before writing, the file is checked: if something else (another plugin)
#    changed it since it was read, nothing is written and it is read again;
#  - a dated backup is made first (the last 10 are kept, MENU restores one);
#  - the new file is written to a temporary file and then put in place, so a
#    power cut never leaves half a file;
#  - only the lines of that reader change, comments and the rest stay as they
#    are;
#  - the emu is restarted only if you say yes afterwards.
# Passwords are shown as **** until you press INFO.

import os
import re
import shutil
import ssl
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from enigma import eTimer

from Components.ActionMap import ActionMap
from Components.config import ConfigSelection, ConfigText, ConfigYesNo, getConfigListEntry
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.Sources.List import List
from Components.Sources.StaticText import StaticText
from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

try:
	from twisted.internet import reactor
except Exception:  # tests
	reactor = None

KEEP_BACKUPS = 10
BACKUP_TAG = ".ngbak-"
PROTOCOLS = ("cccam", "newcamd", "mgcamd", "cs378x", "cs357x", "camd35", "gbox", "radegast", "constcw", "emu", "internal")
SECRET = ("password", "key", "pincode", "rsakey", "boxkey", "deskey", "des_key", "ins7e", "ins7e11", "ins42", "boxid")
MAIN_FIELDS = ("label", "protocol", "device", "user", "password", "group", "caid", "enable")
CONFIG_DIRS = ("/etc/tuxbox/config", "/etc/tuxbox/config/oscam", "/etc/tuxbox/config/ncam", "/var/tuxbox/config", "/usr/keys")


# -------------------------------------------------------------- the file ---
class Reader:
	def __init__(self, start, end, fields):
		self.start, self.end = start, end   # line indices [start, end)
		self.fields = fields                 # [(key, value, line index)]

	def get(self, key, default=""):
		key = key.lower()
		for k, v, _i in self.fields:
			if k == key:
				return v
		return default

	@property
	def label(self):
		return self.get("label") or "?"

	@property
	def enabled(self):
		return self.get("enable", "1").strip() != "0"


class ServerFile:
	"""oscam.server / ncam.server, kept line by line."""

	SECTION = re.compile(r"^\s*\[(\w+)\]\s*$")
	FIELD = re.compile(r"^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$")

	def __init__(self, path):
		self.path = path
		self.load()

	def load(self):
		with open(self.path, "rb") as f:
			raw = f.read()
		self.mtime = os.stat(self.path).st_mtime_ns
		self.size = len(raw)
		self.lines = raw.decode("utf-8", "replace").splitlines(True)
		self.parse()

	def parse(self):
		self.readers = []
		cur = None
		for i, line in enumerate(self.lines):
			m = self.SECTION.match(line)
			if m:
				if cur:
					cur.end = i
				cur = Reader(i, len(self.lines), []) if m.group(1).lower() == "reader" else None
				if cur:
					self.readers.append(cur)
				continue
			if cur:
				f = self.FIELD.match(line)
				if f and not line.lstrip().startswith(("#", ";")):
					cur.fields.append((f.group(1).lower(), f.group(2), i))
		if cur:
			cur.end = len(self.lines)

	def changedOutside(self):
		try:
			return os.stat(self.path).st_mtime_ns != self.mtime
		except OSError:
			return True

	@staticmethod
	def eol(line):
		return "\r\n" if line.endswith("\r\n") else "\n"

	def setField(self, idx, key, value):
		r = self.readers[idx]
		key = key.lower()
		for k, _v, i in r.fields:
			if k == key:
				old = self.lines[i]
				indent = old[:len(old) - len(old.lstrip())]
				self.lines[i] = "%s%s = %s%s" % (indent, key, value, self.eol(old))
				self.parse()
				return
		# not there: after the last field of the reader
		at = (r.fields[-1][2] + 1) if r.fields else r.start + 1
		eol = self.eol(self.lines[r.start])
		self.lines.insert(at, "%s = %s%s" % (key, value, eol))
		self.parse()

	def removeField(self, idx, key):
		r = self.readers[idx]
		for k, _v, i in r.fields:
			if k == key.lower():
				del self.lines[i]
				self.parse()
				return

	def delete(self, idx):
		r = self.readers[idx]
		end = r.end
		del self.lines[r.start:end]
		# no double empty line where the reader was
		if r.start < len(self.lines) and r.start > 0 and not self.lines[r.start].strip() and not self.lines[r.start - 1].strip():
			del self.lines[r.start]
		self.parse()

	def add(self, fields):
		eol = self.eol(self.lines[0]) if self.lines else "\n"
		if self.lines and not self.lines[-1].endswith(("\n", "\r\n")):
			self.lines[-1] += eol
		if self.lines and self.lines[-1].strip():
			self.lines.append(eol)
		self.lines.append("[reader]" + eol)
		for k, v in fields:
			self.lines.append("%s = %s%s" % (k, v, eol))
		self.parse()

	def text(self):
		return "".join(self.lines)

	def save(self):
		"""Backup, then atomic write. Raises if the file changed outside."""
		if self.changedOutside():
			raise ChangedOutside()
		stamp = time.strftime("%Y%m%d-%H%M%S")
		backup = "%s%s%s" % (self.path, BACKUP_TAG, stamp)
		shutil.copy2(self.path, backup)
		tmp = self.path + ".ngtmp"
		with open(tmp, "w", encoding="utf-8", newline="") as f:
			f.write(self.text())
			f.flush()
			os.fsync(f.fileno())
		try:
			shutil.copymode(self.path, tmp)
		except Exception:
			pass
		os.replace(tmp, self.path)
		self.trimBackups()
		self.mtime = os.stat(self.path).st_mtime_ns
		return backup

	def backups(self):
		folder, base = os.path.split(self.path)
		out = sorted((f for f in os.listdir(folder) if f.startswith(base + BACKUP_TAG)), reverse=True)
		return [os.path.join(folder, f) for f in out]

	def trimBackups(self):
		for old in self.backups()[KEEP_BACKUPS:]:
			try:
				os.remove(old)
			except OSError:
				pass

	def restore(self, backup):
		if self.changedOutside():
			raise ChangedOutside()
		shutil.copy2(self.path, "%s%s%s" % (self.path, BACKUP_TAG, time.strftime("%Y%m%d-%H%M%S") + "-before-restore"))
		tmp = self.path + ".ngtmp"
		shutil.copy2(backup, tmp)
		os.replace(tmp, self.path)
		self.trimBackups()
		self.load()


class ChangedOutside(Exception):
	pass


LOG = "/tmp/nileglass_readers.log"


def log(*parts):
	"""Every step of the readers screen, for when something does not work."""
	try:
		with open(LOG, "a") as f:
			f.write("%s %s\n" % (time.strftime("%H:%M:%S"), " ".join(str(p) for p in parts)))
	except Exception:
		pass


# ------------------------------------------------------- the running emu ---
def runningEmu():
	"""(name, config dir) of the running oscam / ncam, or (None, None)."""
	for name in ("ncam", "oscam"):
		ver = "/tmp/.%s/%s.version" % (name, name)
		if os.path.isfile(ver):
			cdir = None
			try:
				with open(ver, errors="replace") as f:
					for line in f:
						if line.lower().startswith("configdir:"):
							cdir = line.split(":", 1)[1].strip()
			except Exception:
				pass
			if pidOf(name):
				return name, cdir
	for pid in os.listdir("/proc"):
		if not pid.isdigit():
			continue
		try:
			comm = open("/proc/%s/comm" % pid).read().strip().lower()
		except Exception:
			continue
		if comm.startswith(("oscam", "ncam")):
			name = "ncam" if comm.startswith("ncam") else "oscam"
			cdir = None
			try:
				args = open("/proc/%s/cmdline" % pid, "rb").read().split(b"\0")
				for i, a in enumerate(args):
					if a in (b"-c", b"--config-dir") and i + 1 < len(args):
						cdir = args[i + 1].decode()
			except Exception:
				pass
			return name, cdir
	return None, None


def pidOf(name):
	for pid in os.listdir("/proc"):
		if pid.isdigit():
			try:
				if open("/proc/%s/comm" % pid).read().strip().lower().startswith(name):
					return pid
			except Exception:
				pass
	return None


def findServerFile(name, cdir):
	names = ("%s.server" % name, "oscam.server") if name else ("oscam.server", "ncam.server")
	dirs = ([cdir] if cdir else []) + ["%s/%s" % (d, name) for d in CONFIG_DIRS[:1] if name] + list(CONFIG_DIRS)
	for d in dirs:
		for n in names:
			p = os.path.join(d.rstrip("/"), n)
			if os.path.isfile(p):
				return p
	return None


# --------------------------------------------------- live state (webif) ---
def readerStates(name, cdir, timeout=3):
	"""{label: state} from the emu's own web interface; {} when not reachable."""
	conf = os.path.join(cdir or "", "%s.conf" % name)
	port, user, pwd = None, "", ""
	try:
		section = ""
		with open(conf, errors="replace") as f:
			for line in f:
				s = line.strip()
				if s.startswith("["):
					section = s.lower()
				elif section == "[webif]" and "=" in s and not s.startswith("#"):
					k, v = [x.strip() for x in s.split("=", 1)]
					k = k.lower()
					if k == "httpport":
						port = v
					elif k == "httpuser":
						user = v
					elif k == "httppwd":
						pwd = v
	except Exception:
		return {}
	if not port or port == "0":
		return {}
	proto = "https" if port.startswith("+") else "http"
	url = "%s://127.0.0.1:%s/%sapi.html?part=status" % (proto, port.lstrip("+"), name)
	handlers = []
	if user:
		pm = urllib.request.HTTPPasswordMgrWithDefaultRealm()
		pm.add_password(None, url, user, pwd)
		handlers += [urllib.request.HTTPDigestAuthHandler(pm), urllib.request.HTTPBasicAuthHandler(pm)]
	if proto == "https":
		ctx = ssl.create_default_context()
		ctx.check_hostname = False
		ctx.verify_mode = ssl.CERT_NONE   # the emu's own self-signed certificate on 127.0.0.1
		handlers.append(urllib.request.HTTPSHandler(context=ctx))
	try:
		data = urllib.request.build_opener(*handlers).open(url, timeout=timeout).read()
		root = ET.fromstring(data)
	except Exception as err:
		print("[NileGlass] readers webif:", err)
		return {}
	out = {}
	for c in root.iter("client"):
		if c.get("type") in ("p", "r"):
			conn = c.find("connection")
			out[c.get("name", "")] = (conn.text or "").strip() if conn is not None else ""
	return out


STATE_AR = {"CONNECTED": "متصل", "CARDOK": "شغال", "OFF": "موقوف", "DISCONNECTED": "مقطوع", "NEEDINIT": "بيتصل ...", "UNKNOWN": "غير معروف", "ERROR": "خطأ"}


def stateText(reader, states):
	if not reader.enabled:
		return "موقوف"
	s = states.get(reader.label)
	if s is None:
		return "—" if states else ""
	key = s.split()[0].upper() if s else "UNKNOWN"
	return STATE_AR.get(key, s.title())


STATE_COLOR = {"متصل": 0x3cc85a, "شغال": 0x3cc85a, "موقوف": 0xe23b3b, "مقطوع": 0xe23b3b, "خطأ": 0xe23b3b}


def stateColor(text):
	return STATE_COLOR.get(text, 0xf0c419 if text not in ("", "—") else 0x9aa3ae)


def mask(key, value):
	return "****" if key in SECRET and value else value


# ------------------------------------------------------------- the screen ---
class NileGlassReaders(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = "NileGlassReaders"
		self.setTitle("سطور وريدرات الإيمو")
		self["list"] = List([])
		self["details"] = Label("")
		self["file"] = Label("")
		self["hint"] = Label("")
		self["key_red"] = StaticText("حذف")
		self["key_green"] = StaticText("إيقاف / تشغيل")
		self["key_yellow"] = StaticText("تعديل")
		self["key_blue"] = StaticText("إضافة")
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "MenuActions", "InfoActions", "DirectionActions"], {
			"ok": self.safe(self.edit),
			"cancel": self.close,
			"red": self.safe(self.askDelete),
			"green": self.safe(self.askToggle),
			"yellow": self.safe(self.edit),
			"blue": self.safe(self.addMenu),
			"menu": self.safe(self.menu),
			"info": self.toggleSecrets,
			"up": self.up, "down": self.down, "left": self.pageUp, "right": self.pageDown,
		}, -1)
		self.showSecrets = False
		self.states = {}
		self.sf = None
		self.emu, self.cdir = None, None
		self.gone = False
		self.stateTimer = eTimer()
		self.stateTimer.callback.append(self.fetchStates)
		self["list"].onSelectionChanged.append(self.showDetails)
		self.onLayoutFinish.append(self.reload)
		self.onClose.append(self.closing)

	def closing(self):
		self.gone = True
		self.stateTimer.stop()

	def safe(self, action):
		"""Run a key action; never fail silently: say why nothing happens."""
		def run():
			if not self.sf:
				self.session.open(MessageBox, "مفيش ملف سطور مفتوح.\n%s" % (self["details"].getText() or "شغّل OScam أو NCam الأول."), MessageBox.TYPE_INFO, timeout=8)
				return
			if action.__name__ not in ("addMenu", "menu", "backupsMenu", "<lambda>") and self.current()[1] is None:
				self.session.open(MessageBox, "اختار ريدر من القائمة الأول.", MessageBox.TYPE_INFO, timeout=5)
				return
			try:
				log("key", action.__name__)
				action()
			except Exception as err:
				import traceback
				traceback.print_exc()
				self.session.open(MessageBox, "حصل خطأ ومفيش حاجة اتغيرت:\n%s: %s" % (type(err).__name__, err), MessageBox.TYPE_ERROR)
		return run

	# list navigation (the List source needs the screen to move it)
	def up(self):
		self["list"].up()

	def down(self):
		self["list"].down()

	def pageUp(self):
		self["list"].pageUp()

	def pageDown(self):
		self["list"].pageDown()

	# ---- loading
	def reload(self):
		self.emu, self.cdir = runningEmu()
		path = findServerFile(self.emu, self.cdir)
		if not path:
			self.sf = None
			self["file"].setText("")
			self["details"].setText("مفيش OScam أو NCam شغال، أو ملف .server مش موجود.")
			self["list"].setList([])
			return
		try:
			self.sf = ServerFile(path)
		except Exception as err:
			self.sf = None
			self["details"].setText("تعذّر قراءة الملف:\n%s" % err)
			return
		self["file"].setText("%s  ·  %s" % ((self.emu or "").upper(), path))
		self.fill()
		self.stateTimer.start(200, True)

	def fetchStates(self):
		if self.gone or not self.sf:
			return
		emu, cdir = self.emu, self.cdir or (os.path.dirname(self.sf.path) if self.sf else None)
		if not emu:
			return

		def work():
			states = readerStates(emu, cdir)
			if reactor:
				reactor.callFromThread(self.gotStates, states)
		threading.Thread(target=work, daemon=True).start()

	def gotStates(self, states):
		if self.gone or not self.sf:
			return
		self.states = states
		self.fill(keep=True)
		self.stateTimer.start(10000, True)   # refresh while the screen is open

	def fill(self, keep=False):
		idx = self["list"].getIndex() if keep else 0
		rows = []
		for i, r in enumerate(self.sf.readers if self.sf else []):
			dev = r.get("device").replace(",", ":")
			st = stateText(r, self.states)
			rows.append((r.label, r.get("protocol"), dev, r.get("user"), st, i, stateColor(st)))
		self["list"].setList(rows)
		if rows:
			self["list"].setIndex(min(idx, len(rows) - 1))
		n = len(rows)
		self["hint"].setText("%d %s   ·   INFO: إظهار الباسورد   ·   MENU: أدوات أكتر (تكرار، سطر C، تشغيل/إيقاف الكل، النسخ الاحتياطية)" % (n, "ريدر" if n == 1 else "ريدرات"))
		self.showDetails()

	def current(self):
		cur = self["list"].getCurrent()
		return (cur[5], self.sf.readers[cur[5]]) if cur and self.sf else (None, None)

	def showDetails(self):
		idx, r = self.current()
		if r is None:
			if self.sf:
				self["details"].setText("الملف مفيهوش ريدرات. الأزرق لإضافة سطر.")
			return
		lines = ["%s = %s" % (k, v if self.showSecrets else mask(k, v)) for k, v, _i in r.fields]
		self["details"].setText("\n".join(lines))

	def toggleSecrets(self):
		self.showSecrets = not self.showSecrets
		self.showDetails()

	# ---- the guarded write
	def commit(self, what):
		try:
			self.sf.save()
			log("saved", self.sf.path)
		except ChangedOutside:
			log("not saved: changed outside")
			self.session.open(MessageBox, "الملف اتغيّر من برّه (بلوجين تاني أو إيدك) من ساعة ما اتفتح.\nمحدش كتب حاجة، وهيتقري من جديد. اعمل التعديل تاني.", MessageBox.TYPE_WARNING, timeout=10)
			self.reload()
			return
		except Exception as err:
			log("save failed", repr(err))
			self.session.open(MessageBox, "فشل الحفظ، والملف زي ما هو:\n%s" % err, MessageBox.TYPE_ERROR)
			self.reload()
			return
		self.fill(keep=True)
		self.session.openWithCallback(self.restartAnswer, MessageBox,
			"%s\nاتعمل نسخة احتياطية قبل الحفظ.\n\nإعادة تشغيل %s دلوقتي علشان التعديل يشتغل؟" % (what, (self.emu or "الإيمو").upper()),
			MessageBox.TYPE_YESNO, default=False)

	def restartAnswer(self, yes):
		if not yes:
			return
		try:
			from .cambar import camSystem
			cams = camSystem()
			name = cams.current() if cams else None
			if not cams or not name:
				raise RuntimeError("مش لاقي الإيمو الشغال")
			cams.restart(name)
			self["hint"].setText("جاري إعادة تشغيل %s ..." % name)
			self.stateTimer.start(6000, True)
		except Exception as err:
			self.session.open(MessageBox, "إعادة التشغيل ما نفعتش:\n%s\nالتعديل محفوظ، وهيشتغل مع أول تشغيل للإيمو." % err, MessageBox.TYPE_WARNING)

	def guard(self):
		"""Reload first when the file changed since it was shown."""
		if not self.sf:
			return False
		if self.sf.changedOutside():
			log("changed outside before the action")
			self.session.open(MessageBox, "الملف اتغيّر من برّه، اتقري من جديد. راجع واعمل العملية تاني.", MessageBox.TYPE_INFO, timeout=6)
			self.reload()
			return False
		return True

	# ---- delete
	def askDelete(self):
		idx, r = self.current()
		if r is None or not self.guard():
			return
		self.session.openWithCallback(lambda yes: yes and self.doDelete(idx, r.label), MessageBox,
			"حذف الريدر «%s» (%s)؟\nالسطور بتاعته هتتشال من الملف." % (r.label, r.get("device")), MessageBox.TYPE_YESNO, default=False)

	def doDelete(self, idx, label):
		self.sf.delete(idx)
		self.commit("اتحذف «%s»." % label)

	# ---- stop / start one reader
	def askToggle(self):
		idx, r = self.current()
		if r is None or not self.guard():
			return
		new = "0" if r.enabled else "1"
		txt = "إيقاف" if new == "0" else "تشغيل"
		self.session.openWithCallback(lambda yes: yes and self.doToggle(idx, new, r.label, txt), MessageBox,
			"%s الريدر «%s»؟\n(enable = %s)" % (txt, r.label, new), MessageBox.TYPE_YESNO, default=False)

	def doToggle(self, idx, new, label, txt):
		self.sf.setField(idx, "enable", new)
		self.commit("تم %s «%s»." % (txt, label))

	# ---- edit: one screen with all the fields of the reader
	def edit(self):
		idx, r = self.current()
		log("edit", r.label if r else None)
		if r is None or not self.guard():
			return
		fields = [(k, v) for k, v, _i in r.fields]
		self.session.openWithCallback(lambda changes: self.edited(idx, r.label, changes), NileGlassReaderEdit, "تعديل «%s»" % r.label, fields)

	def edited(self, idx, label, changes):
		log("edited", label, sorted((changes or {}).keys()))
		if not changes:
			return
		if not self.guard():
			return
		if "label" in changes and changes["label"] != label:
			changes["label"] = self.freeLabel(changes["label"]) if changes["label"] else label
		r = self.sf.readers[idx]
		txt = "\n".join("%s:  %s  ←  %s" % (k, mask(k, v) or "(يتمسح)", mask(k, r.get(k)) or "(فاضي)") for k, v in changes.items())
		self.session.openWithCallback(lambda yes: yes and self.doEdit(idx, label, changes), MessageBox,
			"حفظ التعديلات على «%s»؟\n\n%s" % (label, txt), MessageBox.TYPE_YESNO, default=False)

	def doEdit(self, idx, label, changes):
		log("save edit", label, sorted(changes))
		for key, value in changes.items():
			if value:
				self.sf.setField(idx, key, value)
			else:
				self.sf.removeField(idx, key)
		self.commit("اتحفظت التعديلات على «%s»." % label)

	def askSet(self, idx, key, value):
		"""One field (kept for small callers)."""
		self.edited(idx, self.sf.readers[idx].label, {key: value})

	# ---- add
	def addMenu(self):
		log("add menu")
		if not self.sf or not self.guard():
			return
		self.session.openWithCallback(lambda c: c and c[1](), ChoiceBox, title="إضافة سطر",
			list=[("سطر CCcam  (C: host port user pass)", self.addCLine), ("ريدر جديد (كل الحقول في شاشة واحدة)", self.addWizard)])

	def addCLine(self):
		self.keyboard("اكتب سطر C:", "C: ", self.gotCLine)

	def gotCLine(self, text):
		log("C line", bool(text))
		if not text:
			return
		m = re.match(r"^\s*[Cc]\s*:\s*(\S+)\s+(\d+)\s+(\S+)\s+(\S+)", text)
		if not m:
			self.session.open(MessageBox, "السطر مش بالشكل ده:\nC: host port user pass", MessageBox.TYPE_ERROR, timeout=8)
			return
		host, port, user, pwd = m.groups()
		label = self.freeLabel(host.split(".")[0] or "cccam")
		fields = [("label", label), ("protocol", "cccam"), ("device", "%s,%s" % (host, port)), ("user", user), ("password", pwd),
			("inactivitytimeout", "30"), ("group", "1"), ("cccversion", "2.3.2"), ("ccckeepalive", "1"), ("enable", "1")]
		self.askAdd(fields)

	def addWizard(self):
		fields = [("label", ""), ("protocol", "cccam"), ("device", ""), ("user", ""), ("password", ""), ("group", "1"), ("enable", "1")]
		self.session.openWithCallback(self.gotNew, NileGlassReaderEdit, "ريدر جديد", fields, True)

	def gotNew(self, values):
		log("new reader", sorted((values or {}).keys()))
		if not values:
			return
		if not values.get("label") or not values.get("device"):
			self.session.open(MessageBox, "لازم تكتب الاسم (label) والسيرفر (device).", MessageBox.TYPE_ERROR, timeout=8)
			return
		values["label"] = self.freeLabel(values["label"])
		values["device"] = values["device"].replace(":", ",").replace(" ", ",")
		fields = [(k, values[k]) for k in ("label", "protocol", "device", "user", "password") if values.get(k)]
		if values.get("protocol") == "cccam":
			fields += [("inactivitytimeout", "30"), ("cccversion", "2.3.2"), ("ccckeepalive", "1")]
		elif values.get("protocol") == "newcamd":
			fields.append(("key", "0102030405060708091011121314"))
		fields += [("group", values.get("group") or "1"), ("enable", values.get("enable", "1"))]
		self.askAdd(fields)

	def askAdd(self, fields):
		if not self.guard():
			return
		txt = "\n".join("%s = %s" % (k, mask(k, v)) for k, v in fields)
		self.session.openWithCallback(lambda yes: yes and self.doAdd(fields), MessageBox, "إضافة الريدر ده؟\n\n" + txt, MessageBox.TYPE_YESNO, default=False)

	def doAdd(self, fields):
		self.sf.add(fields)
		self.commit("اتضاف «%s»." % dict(fields)["label"])
		if self.sf.readers:
			self["list"].setIndex(len(self.sf.readers) - 1)

	def freeLabel(self, base):
		used = {r.label for r in self.sf.readers}
		base = re.sub(r"[^\w\-.]", "_", base) or "reader"
		if base not in used:
			return base
		n = 2
		while "%s_%d" % (base, n) in used:
			n += 1
		return "%s_%d" % (base, n)

	# ---- backups
	def menu(self):
		if not self.sf:
			return
		idx, r = self.current()
		items = []
		if r is not None:
			items.append(("تكرار «%s» (نسخة منه باسم جديد)" % r.label, self.duplicate))
			if r.get("protocol").lower() == "cccam":
				items.append(("تعديل «%s» كسطر C" % r.label, self.editAsCLine))
		if self.sf.readers:
			items += [("تشغيل كل الريدرات", lambda: self.askAll("1")), ("إيقاف كل الريدرات", lambda: self.askAll("0"))]
		items.append(("النسخ الاحتياطية (استرجاع)", self.backupsMenu))
		self.session.openWithCallback(lambda c: c and self.safe(c[1])(), ChoiceBox, title="أدوات السطور", list=items)

	def duplicate(self):
		idx, r = self.current()
		if r is None or not self.guard():
			return
		fields = [(k, v) for k, v, _i in r.fields]
		fields = [("label", self.freeLabel(r.label + "_2")) if k == "label" else (k, v) for k, v in fields]
		if "label" not in dict(fields):
			fields.insert(0, ("label", self.freeLabel("reader")))
		self.askAdd(fields)

	def editAsCLine(self):
		idx, r = self.current()
		if r is None or not self.guard():
			return
		dev = r.get("device").replace(":", ",").split(",")
		line = "C: %s %s %s %s" % (dev[0] if dev else "", dev[1] if len(dev) > 1 else "", r.get("user"), r.get("password"))
		self.keyboard("عدّل السطر C:", line, lambda text: self.gotEditedCLine(idx, r.label, text))

	def gotEditedCLine(self, idx, label, text):
		if not text:
			return
		m = re.match(r"^\s*[Cc]\s*:\s*(\S+)\s+(\d+)\s+(\S+)\s+(\S+)", text)
		if not m:
			self.session.open(MessageBox, "السطر مش بالشكل ده:\nC: host port user pass", MessageBox.TYPE_ERROR, timeout=8)
			return
		host, port, user, pwd = m.groups()
		r = self.sf.readers[idx]
		changes = {}
		for k, v in (("device", "%s,%s" % (host, port)), ("user", user), ("password", pwd)):
			if r.get(k) != v:
				changes[k] = v
		if not changes:
			self.session.open(MessageBox, "مفيش حاجة اتغيرت.", MessageBox.TYPE_INFO, timeout=4)
			return
		self.edited(idx, label, changes)

	def askAll(self, value):
		if not self.guard():
			return
		todo = [i for i, r in enumerate(self.sf.readers) if (r.get("enable", "1").strip() != "0") != (value == "1")]
		if not todo:
			self.session.open(MessageBox, "كل الريدرات %s بالفعل." % ("شغالة" if value == "1" else "متوقفة"), MessageBox.TYPE_INFO, timeout=5)
			return
		names = ", ".join(self.sf.readers[i].label for i in todo)
		txt = "تشغيل" if value == "1" else "إيقاف"
		self.session.openWithCallback(lambda yes: yes and self.doAll(todo, value, txt), MessageBox,
			"%s %d ريدر؟\n%s" % (txt, len(todo), names), MessageBox.TYPE_YESNO, default=False)

	def doAll(self, todo, value, txt):
		for i in todo:
			self.sf.setField(i, "enable", value)
		self.commit("تم %s %d ريدر." % (txt, len(todo)))

	def backupsMenu(self):
		backs = self.sf.backups()
		if not backs:
			self.session.open(MessageBox, "مفيش نسخ احتياطية لسه.\nبتتعمل لوحدها قبل أي حفظ.", MessageBox.TYPE_INFO, timeout=6)
			return
		lst = [(os.path.basename(b).split(BACKUP_TAG, 1)[1].replace("-before-restore", "  (قبل استرجاع)"), b) for b in backs]
		self.session.openWithCallback(lambda c: c and self.askRestore(c[1]), ChoiceBox, title="استرجاع نسخة احتياطية", list=lst)

	def askRestore(self, path):
		self.session.openWithCallback(lambda yes: yes and self.doRestore(path), MessageBox,
			"استرجاع الملف من النسخة:\n%s\n؟ (الملف الحالي هيتحفظ نسخة قبلها)" % os.path.basename(path), MessageBox.TYPE_YESNO, default=False)

	def doRestore(self, path):
		try:
			self.sf.restore(path)
		except ChangedOutside:
			self.session.open(MessageBox, "الملف اتغيّر من برّه، اتقري من جديد. حاول تاني.", MessageBox.TYPE_WARNING, timeout=8)
			self.reload()
			return
		except Exception as err:
			self.session.open(MessageBox, "فشل الاسترجاع:\n%s" % err, MessageBox.TYPE_ERROR)
			return
		self.fill()
		self.session.openWithCallback(self.restartAnswer, MessageBox, "تم الاسترجاع.\nإعادة تشغيل %s دلوقتي؟" % (self.emu or "الإيمو").upper(), MessageBox.TYPE_YESNO, default=False)

	# ---- helpers
	def keyboard(self, title, text, cb):
		from Screens.VirtualKeyBoard import VirtualKeyBoard
		self.session.openWithCallback(cb, VirtualKeyBoard, title=title, text=text or "")


# ---------------------------------------------------------- the edit screen ---
FIELD_NAMES = {"label": "الاسم (label)", "protocol": "البروتوكول", "device": "السيرفر,البورت (device)", "user": "اليوزر", "password": "الباسورد",
	"group": "group", "caid": "caid", "enable": "شغال (enable)"}


COMMON_FIELDS = ("inactivitytimeout", "reconnecttimeout", "cccversion", "ccckeepalive", "cccmaxhops", "caid", "ident", "services",
	"key", "audisabled", "disablecrccws", "lb_weight", "fallback", "ecmwhitelist", "emmcache", "blockemm-unknown", "connectoninit")


class NileGlassReaderEdit(ConfigListScreen, Screen):
	"""All the fields of one reader. OK on a text field opens the keyboard,
	the number keys type directly, yellow adds a field, blue removes the
	field under the cursor, green saves (the readers screen still asks before
	writing), red cancels."""

	def __init__(self, session, title, fields, isNew=False):
		Screen.__init__(self, session)
		self.skinName = ["NileGlassReaderEdit", "Setup"]
		self.setTitle(title)
		self["description"] = Label("OK: كتابة بالكيبورد  ·  الأرقام: كتابة مباشرة  ·  الأصفر: إضافة حقل  ·  الأزرق: حذف الحقل")
		self["footnote"] = Label("")
		self.isNew = isNew
		self.orig = {}
		self.items = []
		self.removed = set()
		values = dict(fields)
		order = [k for k in MAIN_FIELDS if k in values] + [k for k, _v in fields if k not in MAIN_FIELDS]
		for key in order:
			value = values.get(key, "")
			self.orig[key] = value
			self.items.append((key, self.element(key, value)))
		ConfigListScreen.__init__(self, self.entries(), session=session, fullUI=True,
			yellow_button={"text": "إضافة حقل", "function": self.addField},
			blue_button={"text": "حذف الحقل", "function": self.removeField})
		self["key_red"].setText("إلغاء")
		self["key_green"].setText("حفظ")
		try:
			self["editConfigActions"].setEnabled(True)    # number keys type into the field
		except Exception:
			pass
		log("edit screen", title, len(self.items))

	@staticmethod
	def element(key, value):
		if key == "protocol":
			choices = list(PROTOCOLS) + ([value] if value and value not in PROTOCOLS else [])
			return ConfigSelection(default=value if value in choices else "cccam", choices=[(c, c) for c in choices])
		if key == "enable":
			return ConfigYesNo(default=value.strip() != "0")
		return ConfigText(default=value, fixed_size=False, visible_width=40)

	def entries(self):
		return [getConfigListEntry(FIELD_NAMES.get(k, k), el) for k, el in self.items]

	def refresh(self, index=None):
		self["config"].list = self.entries()
		if index is not None:
			self["config"].setCurrentIndex(max(0, min(index, len(self.items) - 1)))

	def addField(self):
		have = {k for k, _el in self.items}
		lst = [(k, k) for k in COMMON_FIELDS if k not in have] + [("اسم تاني ...", None)]
		self.session.openWithCallback(self.gotField, ChoiceBox, title="إضافة حقل للريدر", list=lst)

	def gotField(self, choice):
		if not choice:
			return
		if choice[1] is None:
			from Screens.VirtualKeyBoard import VirtualKeyBoard
			self.session.openWithCallback(lambda name: name and self.newField(name), VirtualKeyBoard, title="اسم الحقل", text="")
			return
		self.newField(choice[1])

	def newField(self, name):
		name = re.sub(r"[^A-Za-z0-9_\-]", "", name.strip().lower())
		if not name:
			return
		if any(k == name for k, _el in self.items):
			self.refresh([k for k, _el in self.items].index(name))
			return
		self.removed.discard(name)
		self.items.append((name, self.element(name, "")))
		self.refresh(len(self.items) - 1)
		log("edit screen add field", name)

	def removeField(self):
		i = self["config"].getCurrentIndex()
		if i is None or not 0 <= i < len(self.items):
			return
		key = self.items[i][0]
		if key in ("label", "protocol", "device"):
			self.session.open(MessageBox, "الحقل «%s» أساسي ومينفعش يتشال." % key, MessageBox.TYPE_INFO, timeout=5)
			return
		del self.items[i]
		if key in self.orig:
			self.removed.add(key)
		self.refresh(i)
		log("edit screen remove field", key)

	def valueOf(self, key, el):
		if key == "enable":
			return "1" if el.value else "0"
		return str(el.value).strip()

	def keySave(self):
		if self.isNew:
			result = {k: self.valueOf(k, el) for k, el in self.items}
		else:
			result = {k: self.valueOf(k, el) for k, el in self.items if self.valueOf(k, el) != self.orig.get(k, "").strip()}
			for k in self.removed:
				result[k] = ""          # empty = the line is removed (asked again before writing)
		log("edit screen save", sorted(result))
		self.close(result)

	def keyCancel(self):
		log("edit screen cancel")
		self.close(None)
