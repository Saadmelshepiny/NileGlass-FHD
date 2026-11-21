# -*- coding: utf-8 -*-
# NileGlass FHD - what the cards beside a screen show about that screen's
# subject (any source, the values are global):
#
#   time  : Utc, Zone, Offset, Dst, Sync, City1..City4
#   image : Image, Flashed, Python, Kernel, Enigma, Updates, FeedAge, Model
#   emu   : EmuRunning, EmuVersion, EmuUptime, EmuInstalled, EmuCount
#   bt    : BtAdapter, BtConnected, BtCount, BtPaired
#   wifi  : Ssid, Signal, NetRate
# Values that need a command (iw, hcitool / bluetoothctl) are read in a
# thread and kept for a few seconds; the screen never waits for them.

import glob
import os
import re
import subprocess
import sys
import threading
import time

from Components.Converter.Converter import Converter
from Components.Converter.NGPoll import NGPoll as Poll
from Components.Element import cached

CITIES = (("مكة", "Asia/Riyadh"), ("دبي", "Asia/Dubai"), ("لندن", "Europe/London"), ("نيويورك", "America/New_York"))
EMU_DIRS = ("/usr/softcams", "/usr/bin", "/usr/emu", "/usr/camscript")
EMU_NAMES = re.compile(r"^(oscam|ncam|cccam|mgcamd|wicardd|gbox|doscam|camd3|evocamd|ultracam)[\w.\-]*$", re.I)

_cmdCache = {}
_cmdBusy = set()


def command(key, args, ttl=8, timeout=4):
	"""output of a command, read in a thread; None until the first answer"""
	now = time.time()
	have = _cmdCache.get(key)
	if (have is None or now - have[0] > ttl) and key not in _cmdBusy:
		_cmdBusy.add(key)

		def run():
			try:
				try:
					from Components.NileGlassCore import waitQuiet
					waitQuiet(2.0)
				except Exception:
					pass
				out = subprocess.run(args, capture_output=True, timeout=timeout, text=True, errors="ignore").stdout
			except Exception:
				out = ""
			_cmdCache[key] = (time.time(), out)
			_cmdBusy.discard(key)
		threading.Thread(target=run, daemon=True).start()
	return have[1] if have else None


def readFile(path, limit=65536):
	try:
		with open(path, encoding="utf-8", errors="ignore") as f:
			return f.read(limit)
	except Exception:
		return ""


def config(path, default=""):
	try:
		from Components.config import config as c
		obj = c
		for part in path.split("."):
			obj = getattr(obj, part)
		return obj.value
	except Exception:
		return default


# ---------------------------------------------------------------- time
def cityTime(zone):
	try:
		from zoneinfo import ZoneInfo
		from datetime import datetime
		return datetime.now(ZoneInfo(zone)).strftime("%H:%M")
	except Exception:
		return ""


def offsetText():
	z = time.strftime("%z")
	if len(z) == 5:
		h, m = int(z[1:3]), int(z[3:])
		return "UTC%s%d%s" % (z[0], h, ":%02d" % m if m else "")
	return "UTC"


# ---------------------------------------------------------------- image
def systemInfo(key):
	try:
		from Components.SystemInfo import SystemInfo, BoxInfo
		v = SystemInfo.get(key) if hasattr(SystemInfo, "get") else None
		return v if v not in (None, "") else BoxInfo.getItem(key)
	except Exception:
		return None


def imageText():
	distro = systemInfo("displaydistro") or "OpenBh"
	ver, build, kind = systemInfo("imageversion") or systemInfo("imgversion"), systemInfo("imagebuild"), systemInfo("imagetype")
	out = "%s %s" % (distro, ver or "")
	if build:
		out += ".%s" % build
	if kind:
		out += " (%s)" % str(kind).title()
	return out.strip()


def updatesText():
	try:
		from Components import NileGlassPlugins as P
		P.prepare([])
		if P._index is None:
			return "…"
		if not P._feed:
			return "حدّث الفيد الأول"
		n = sum(1 for pkg, st in P._status.items() if "installed" in st.get("Status", "") and pkg in P._feed and P._feed[pkg] != st.get("Version"))
		return "كله محدّث" if n == 0 else "%d حزمة ليها تحديث" % n
	except Exception:
		return ""


def ageText(ts):
	if not ts:
		return "—"
	d = int(time.time() - ts)
	if d < 3600:
		return "من %d دقيقة" % max(1, d // 60)
	if d < 86400:
		return "من %d ساعة" % (d // 3600)
	return "من %d يوم" % (d // 86400)


# ---------------------------------------------------------------- emu
def installedEmus():
	found = []
	for d in EMU_DIRS:
		for p in glob.glob(os.path.join(d, "*")):
			n = os.path.basename(p)
			if EMU_NAMES.match(n) and os.access(p, os.X_OK) and n.lower() not in [f.lower() for f in found]:
				found.append(n)
	return found


def runningEmu():
	for pid in os.listdir("/proc"):
		if not pid.isdigit():
			continue
		name = readFile("/proc/%s/comm" % pid, 64).strip()
		if name and EMU_NAMES.match(name):
			return name, pid
	return None, None


def emuVersion(name):
	for d in ("/tmp/.oscam", "/tmp/.ncam", "/tmp/.%s" % (name or "").lower()):
		text = readFile(os.path.join(d, "oscam.version")) or readFile(os.path.join(d, "ncam.version"))
		m = re.search(r"Version:\s*(\S+)", text)
		if m:
			return m.group(1)
	return ""


def processUptime(pid):
	try:
		start = int(readFile("/proc/%s/stat" % pid).rsplit(")", 1)[1].split()[19])
		hz = os.sysconf("SC_CLK_TCK")
		up = float(readFile("/proc/uptime").split()[0])
		sec = int(up - start / hz)
		d, h, m = sec // 86400, (sec % 86400) // 3600, (sec % 3600) // 60
		return "%d يوم %d س" % (d, h) if d else "%d س %d د" % (h, m) if h else "%d د" % m
	except Exception:
		return ""


# ---------------------------------------------------------------- bluetooth
def btAdapter():
	ads = sorted(glob.glob("/sys/class/bluetooth/hci*"))
	if not ads:
		return None
	return os.path.basename(ads[0])


def btConnected():
	"""[(address, name)] of connected devices"""
	out = command("bt-connected", ["bluetoothctl", "devices", "Connected"], ttl=6)
	devs = []
	if out:
		for line in out.splitlines():
			m = re.match(r"Device\s+([0-9A-F:]{17})\s+(.*)", line.strip())
			if m:
				devs.append((m.group(1), m.group(2).strip()))
	if not devs:
		con = command("bt-hcitool", ["hcitool", "con"], ttl=6) or ""
		for mac in re.findall(r"([0-9A-F]{2}(?::[0-9A-F]{2}){5})", con):
			name = (command("bt-name-" + mac, ["hcitool", "name", mac], ttl=300) or "").strip()
			devs.append((mac, name or mac))
	return devs


def btPaired():
	out = command("bt-paired", ["bluetoothctl", "devices", "Paired"], ttl=30) or command("bt-all", ["bluetoothctl", "devices"], ttl=30) or ""
	return len(re.findall(r"^Device ", out, re.M))


# ---------------------------------------------------------------- wifi
def wifiInterface():
	for line in readFile("/proc/net/wireless").splitlines()[2:]:
		name = line.split(":")[0].strip()
		if name:
			return name
	return None


def wifiLink(iface):
	out = command("iw-" + iface, ["iw", "dev", iface, "link"], ttl=5)
	if out is None:
		return None
	ssid = re.search(r"SSID:\s*(.+)", out)
	rate = re.search(r"tx bitrate:\s*([\d.]+)\s*MBit/s", out)
	rate = rate.group(1) if rate else ""
	if not rate:          # no iw, or the driver does not tell it there: wireless-tools
		iwc = command("iwconfig-" + iface, ["iwconfig", iface], ttl=5) or ""
		m = re.search(r"Bit Rate[=:]\s*([\d.]+)\s*([MG])b/s", iwc)
		if m:
			rate = m.group(1) if m.group(2) == "M" else "%g" % (float(m.group(1)) * 1000)
		if not ssid:
			ssid = re.search(r'ESSID:"([^"]+)"', iwc)
	if not ssid:
		cfg = readFile("/etc/wpa_supplicant.%s.conf" % iface) or readFile("/etc/wpa_supplicant.conf")
		m = re.search(r'ssid="([^"]+)"', cfg)
		ssid = m
	return (ssid.group(1).strip() if ssid else ""), rate


def wifiSignal(iface):
	for line in readFile("/proc/net/wireless").splitlines()[2:]:
		parts = line.split()
		if parts and parts[0].rstrip(":") == iface and len(parts) > 3:
			try:
				q, lvl = float(parts[2].rstrip(".")), float(parts[3].rstrip("."))
				pct = int(min(100, q * 100 / 70))
				return "%d dBm · %d%%" % (lvl, pct) if lvl < 0 else "%d%%" % pct
			except ValueError:
				return ""
	return ""


class NGContext(Poll, Converter):
	FAST = ("Utc", "City1", "City2", "City3", "City4")

	def __init__(self, arg):
		Converter.__init__(self, arg)
		Poll.__init__(self)
		self.type = (arg or "Utc").strip()
		self.poll_interval = 1000 if self.type in ("Utc", "Local") else 15000 if self.type in self.FAST else 5000
		self.poll_enabled = True

	@cached
	def getText(self):
		try:
			return self.text_() or ""
		except Exception as err:
			print("[NileGlass] NGContext %s:" % self.type, err)
			return ""

	def text_(self):
		t = self.type
		# time
		if t == "Utc":
			return time.strftime("%H:%M:%S", time.gmtime())
		if t == "Local":
			return time.strftime("%H:%M:%S")
		if t == "Zone":
			return config("timezone.val") or readFile("/etc/timezone").strip() or time.tzname[0]
		if t == "Offset":
			return offsetText()
		if t == "Dst":
			return "التوقيت الصيفي شغال" if time.localtime().tm_isdst > 0 else "من غير توقيت صيفي"
		if t == "Sync":
			return ("NTP · %s" % (config("misc.NTPserver") or "pool.ntp.org")) if config("misc.SyncTimeUsing") == "ntp" else "من إشارة القمر (الترانسبوندر)"
		if t.startswith("City") and t[4:].isdigit():
			i = int(t[4:]) - 1
			if 0 <= i < len(CITIES):
				return "%s  %s" % (CITIES[i][0], cityTime(CITIES[i][1]))
			return ""
		# image
		if t == "Image":
			return imageText()
		if t == "Model":
			return "%s %s" % (systemInfo("displaybrand") or "", (systemInfo("displaymodel") or systemInfo("machinename") or "").replace("4k", "4K"))
		if t == "Flashed":
			try:
				from Screens.About import getFlashDateString
				return getFlashDateString()
			except Exception:
				return time.strftime("%d/%m/%Y", time.localtime(os.path.getmtime("/etc/version"))) if os.path.exists("/etc/version") else ""
		if t == "Python":
			return "%d.%d.%d" % sys.version_info[:3]
		if t == "Kernel":
			return os.uname().release.split("-")[0]
		if t == "Enigma":
			try:
				from Screens.About import getLastCommitDate
				return getLastCommitDate()
			except Exception:
				return ""
		if t == "Updates":
			return updatesText()
		if t == "FeedAge":
			try:
				return ageText(os.path.getmtime("/var/lib/opkg/lists"))
			except Exception:
				return "الفيد لسه متحدثش"
		# emu
		if t in ("EmuRunning", "EmuVersion", "EmuUptime"):
			name, pid = runningEmu()
			if not name:
				return "مفيش إيمو شغال" if t == "EmuRunning" else ""
			if t == "EmuRunning":
				return name
			if t == "EmuVersion":
				return emuVersion(name)
			return processUptime(pid)
		if t == "EmuInstalled":
			return " · ".join(installedEmus()) or "مفيش إيمو متثبت"
		if t == "EmuCount":
			return str(len(installedEmus()))
		# bluetooth
		if t == "BtAdapter":
			a = btAdapter()
			return ("%s جاهز" % a) if a else "مفيش بلوتوث على الجهاز"
		if t in ("BtConnected", "BtCount"):
			if not btAdapter():
				return "—" if t == "BtCount" else ""
			devs = btConnected()
			if t == "BtCount":
				return str(len(devs))
			return " · ".join(n for _, n in devs) or "مفيش جهاز متصل دلوقتي"
		if t == "BtPaired":
			return str(btPaired()) if btAdapter() else "—"
		# wifi
		if t in ("Ssid", "Signal", "NetRate"):
			from Components.Converter.NGSysInfo import linkSpeed, mainInterface, _isWifi
			main = mainInterface()
			iface = main if main and _isWifi(main) else None
			if t == "Signal":
				return wifiSignal(iface) if iface else "كابل"
			if not iface:
				if t == "Ssid":
					return "كابل (سلكي)" if main else "مش متصل"
				return linkSpeed(main) or ""
			link = wifiLink(iface)
			if link is None:
				return "…"
			return (link[0] or "مش متصل") if t == "Ssid" else (("%s Mbit/s" % link[1]) if link[1] else "—")
		return ""

	text = property(getText)
