# -*- coding: utf-8 -*-
# NileGlass FHD - lightweight system information converter.
#
#   <widget source="session.CurrentService" render="Label" ...>
#       <convert type="NGSysInfo">CpuTemp</convert>
#   </widget>
#   <widget source="session.CurrentService" render="Progress" ...>
#       <convert type="NGSysInfo">RamPercent</convert>
#   </widget>
#
# Text types : CpuTemp, CpuLoad, RamUsed, RamPercent, FlashFree, HddFree,
#              Uptime, IP, BoxName, Image,
#              LoadAvg, Fan, RamMB, HddFreeOnly, UsbFree, NetDown, NetUp,
#              NetType, Online, SkinVersion
# Value types: CpuLoad, RamPercent, FlashPercent, HddPercent, UsbPercent (0..100)
#
# Everything is read from /proc or with statvfs on local disks only - no
# subprocesses, no network shares (a sleeping NAS would freeze the UI).

import fcntl
import os
import socket
import struct
import time

from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached

try:
	from Components.NileGlassCore import isLocalMount
except Exception:
	def isLocalMount(path):
		return False

_cpuPrev = [0, 0]  # shared between all instances: (idle, total)
_cpuLast = [0.0, 0]  # (timestamp, percent)


# Many widgets show the same facts (the menu and settings dashboards have
# dozens): each fact is read once and shared for a few seconds.
_memo = {}


def shared(ttl):
	def wrap(fn):
		def call(*args):
			key = (fn.__name__,) + args
			now = time.monotonic()
			hit = _memo.get(key)
			if hit is not None and now - hit[0] < ttl:
				return hit[1]
			value = fn(*args)
			_memo[key] = (now, value)
			return value
		call.__name__ = fn.__name__
		return call
	return wrap


def _readFirstLine(path):
	try:
		with open(path, "r") as f:
			return f.readline().strip()
	except Exception:
		return ""


@shared(3)
def cpuTemp():
	for path in ("/proc/stb/sensors/temp0/value", "/proc/stb/sensors/temp/value", "/proc/stb/fp/temp_sensor_avs", "/proc/stb/fp/temp_sensor"):
		v = _readFirstLine(path)
		if v and v.lstrip("-").isdigit():
			return int(v)
	v = _readFirstLine("/sys/devices/virtual/thermal/thermal_zone0/temp")
	if v.isdigit():
		v = int(v)
		return v // 1000 if v > 1000 else v
	return None


def cpuLoad():
	now = time.time()
	if now - _cpuLast[0] < 2:  # several widgets ask at once -> compute once
		return _cpuLast[1]
	try:
		with open("/proc/stat", "r") as f:
			parts = [int(x) for x in f.readline().split()[1:]]
		idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
		total = sum(parts)
		dIdle, dTotal = idle - _cpuPrev[0], total - _cpuPrev[1]
		_cpuPrev[0], _cpuPrev[1] = idle, total
		pct = int(round(100 * (1 - dIdle / dTotal))) if dTotal > 0 else 0
	except Exception:
		pct = 0
	_cpuLast[0], _cpuLast[1] = now, max(0, min(100, pct))
	return _cpuLast[1]


@shared(3)
def memInfo():
	info = {}
	try:
		with open("/proc/meminfo", "r") as f:
			for line in f:
				k, v = line.split(":", 1)
				info[k] = int(v.split()[0])
	except Exception:
		pass
	total = info.get("MemTotal", 0)
	avail = info.get("MemAvailable", info.get("MemFree", 0) + info.get("Buffers", 0) + info.get("Cached", 0))
	return total, max(0, total - avail)


@shared(10)
def diskInfo(path):
	try:
		st = os.statvfs(path)
		total = st.f_blocks * st.f_frsize
		free = st.f_bavail * st.f_frsize
		return total, free
	except Exception:
		return 0, 0


def human(n):
	for unit in ("B", "KB", "MB", "GB", "TB"):
		if n < 1024 or unit == "TB":
			return ("%.0f %s" if unit in ("B", "KB", "MB") else "%.1f %s") % (n, unit)
		n /= 1024.0


@shared(10)
def interfaces():
	"""Network interfaces of the box, wired first (any name: eth0, end0, enp1s0, wlan0, ra0 ...)."""
	try:
		names = [n for n in os.listdir("/sys/class/net") if n != "lo" and not n.startswith(("sit", "tun", "tap", "dummy", "ip6", "gre", "ifb", "veth", "docker", "can"))]
	except Exception:
		names = ["eth0", "wlan0", "eth1", "wlan1", "ra0"]
	return sorted(names, key=lambda n: (_isWifi(n), n))


def _isWifi(name):
	return name.startswith(("wl", "ra", "wifi", "ath")) or os.path.isdir("/sys/class/net/%s/wireless" % name)


def _ifAddress(ifname):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	try:
		packed = fcntl.ioctl(s.fileno(), 0x8915, struct.pack("256s", ifname[:15].encode()))  # SIOCGIFADDR
		return socket.inet_ntoa(packed[20:24])
	except Exception:
		return ""
	finally:
		s.close()


def _routeAddress():
	"""Address the box would use to reach the internet (no packet is sent)."""
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	try:
		s.connect(("8.8.8.8", 53))
		ip = s.getsockname()[0]
		return "" if ip.startswith("0.") else ip
	except Exception:
		return ""
	finally:
		s.close()


def _ifUp(ifname):
	state = _readFirstLine("/sys/class/net/%s/operstate" % ifname)
	if state == "up":
		return True
	return state in ("unknown", "dormant", "") and _readFirstLine("/sys/class/net/%s/carrier" % ifname) == "1"


@shared(5)
def ipAddress():
	for ifname in interfaces():
		ip = _ifAddress(ifname)
		if ip and not ip.startswith("127."):
			return ip
	return _routeAddress()


def uptime():
	try:
		secs = int(float(_readFirstLine("/proc/uptime").split()[0]))
	except Exception:
		return ""
	d, rem = divmod(secs, 86400)
	h, rem = divmod(rem, 3600)
	m = rem // 60
	if d:
		return "%dd %dh" % (d, h)
	if h:
		return "%dh %02dm" % (h, m)
	return "%dm" % m


@shared(3600)
def boxName():
	try:
		from Components.SystemInfo import getBoxDisplayName
		brand, model = getBoxDisplayName()
		return ("%s %s" % (brand, model)).strip()
	except Exception:
		return _readFirstLine("/proc/stb/info/vumodel") or _readFirstLine("/proc/stb/info/model")


@shared(3600)
def imageName():
	try:
		from Components.SystemInfo import BoxInfo
		return ("%s %s" % (BoxInfo.getItem("displaydistro", "OpenBh"), BoxInfo.getItem("imgversion", ""))).strip()
	except Exception:
		return "OpenBh"


@shared(3)
def loadAvg():
	v = _readFirstLine("/proc/loadavg").split()
	return v[0] if v else ""


@shared(5)
def fanSpeed():
	for path in ("/proc/stb/fp/fan_speed", "/proc/stb/fp/fanspeed"):
		v = _readFirstLine(path)
		if v:
			return v.replace("RPM", "").strip()
	return "N/A"


_net = {"t": 0.0, "rx": 0, "tx": 0, "down": 0, "up": 0}


def netRates():
	"""Download / upload of the whole box in kbit/s (shared, at most every 2 s)."""
	now = time.monotonic()
	if now - _net["t"] < 1.5:
		return _net["down"], _net["up"]
	rx = tx = 0
	try:
		with open("/proc/net/dev") as f:
			for line in f.readlines()[2:]:
				name, data = line.split(":", 1)
				if name.strip() != "lo":
					d = data.split()
					rx += int(d[0])
					tx += int(d[8])
	except Exception:
		return 0, 0
	dt = now - _net["t"]
	if _net["t"] and dt > 0 and rx >= _net["rx"] and tx >= _net["tx"]:
		_net["down"] = int((rx - _net["rx"]) * 8 / 1000.0 / dt)
		_net["up"] = int((tx - _net["tx"]) * 8 / 1000.0 / dt)
	_net.update(t=now, rx=rx, tx=tx)
	return _net["down"], _net["up"]


def kbits(v):
	return "%.1f Mbit/s" % (v / 1000.0) if v >= 1000 else "%d kbit/s" % v


@shared(5)
def mainInterface():
	"""The interface that carries the box's address (wired first); else the first one that is up."""
	names = interfaces()
	for ifname in names:
		ip = _ifAddress(ifname)
		if ip and not ip.startswith("127."):
			return ifname
	for ifname in names:
		if _ifUp(ifname):
			return ifname
	return ""


@shared(5)
def netType():
	ifname = mainInterface()
	return "%s · %s" % ("Wi-Fi" if _isWifi(ifname) else "Ethernet", ifname) if ifname else ""


def _ioctlAddr(ifname, req):
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	try:
		return socket.inet_ntoa(fcntl.ioctl(s.fileno(), req, struct.pack("256s", ifname[:15].encode()))[20:24])
	except Exception:
		return ""
	finally:
		s.close()


@shared(10)
def gateway():
	try:
		with open("/proc/net/route") as f:
			for line in f.readlines()[1:]:
				p = line.split()
				if len(p) > 2 and p[1] == "00000000" and p[2] != "00000000":
					return socket.inet_ntoa(struct.pack("<L", int(p[2], 16)))
	except Exception:
		pass
	return ""


@shared(30)
def dnsServers():
	out = []
	try:
		with open("/etc/resolv.conf") as f:
			for line in f:
				p = line.split()
				if len(p) > 1 and p[0] == "nameserver" and p[1] not in out:
					out.append(p[1])
	except Exception:
		pass
	return "  ·  ".join(out[:2])


@shared(10)
def linkSpeed(ifname):
	if not ifname or _isWifi(ifname):
		return "Wi-Fi" if ifname else ""
	sp = _readFirstLine("/sys/class/net/%s/speed" % ifname)
	if not sp.isdigit() or int(sp) <= 0:
		return ""
	dup = _readFirstLine("/sys/class/net/%s/duplex" % ifname)
	sp = int(sp)
	return ("%d Gb/s" % (sp // 1000) if sp >= 1000 else "%d Mb/s" % sp) + (" (Half)" if dup == "half" else "")


def ifTotals(ifname):
	try:
		with open("/proc/net/dev") as f:
			for line in f.readlines()[2:]:
				name, data = line.split(":", 1)
				if name.strip() == ifname:
					d = data.split()
					return int(d[0]), int(d[8])
	except Exception:
		pass
	return None, None


def rotorPosition():
	try:
		from Components.config import config
		pos = int(config.misc.lastrotorposition.value)
	except Exception:
		return ""
	if pos <= 0 or pos >= 3600:
		return ""
	return "%.1f°W" % ((3600 - pos) / 10.0) if pos > 1800 else "%.1f°E" % (pos / 10.0)


@shared(600)
def nimSockets():
	"""[(slot letter, name, type)] from /proc/bus/nim_sockets"""
	out, cur = [], None
	try:
		with open("/proc/bus/nim_sockets") as f:
			for line in f:
				line = line.strip()
				if line.startswith("NIM Socket"):
					cur = {"n": len(out)}
					out.append(cur)
				elif cur is not None and ":" in line:
					k, v = line.split(":", 1)
					cur.setdefault(k.strip(), v.strip())
	except Exception:
		return []
	return [(chr(65 + c["n"]), c.get("Name", ""), c.get("Type", "")) for c in out]


AC3 = {"downmix": "تحويل ستيريو", "passthrough": "تمرير رقمي", "multichannel": "متعدد القنوات", "force_ac3": "تحويل AC3", "use_hdmi_caps": "حسب الشاشة"}


@shared(5)
def videoOutput():
	mode = _readFirstLine("/proc/stb/video/videomode")
	return mode.replace("multi", "").strip() if mode else ""


@shared(10)
def hdmiColour():
	cs = _readFirstLine("/proc/stb/video/hdmi_colorspace")
	cd = _readFirstLine("/proc/stb/video/hdmi_colordepth")
	return "  ·  ".join(p for p in (cs, cd) if p)


def volume():
	try:
		from enigma import eDVBVolumecontrol
		v = eDVBVolumecontrol.getInstance()
		return "صامت" if v.isMuted() else "%d%%" % v.getVolume()
	except Exception:
		return ""


@shared(10)
def usbPath():
	try:
		for name in sorted(os.listdir("/media")):
			p = "/media/" + name
			if name.startswith("usb") and os.path.isdir(p) and isLocalMount(p):
				return p
	except Exception:
		pass
	return None


class NGSysInfo(Poll, Converter):
	SLOW_TYPES = ("FlashFree", "HddFree", "FlashPercent", "HddPercent", "IP", "BoxName", "Image",
		"HddFreeOnly", "UsbFree", "UsbPercent", "NetType", "Online", "OnlineYes", "OnlineNo", "SkinVersion", "Gateway", "Dns",
		"Mac", "Netmask", "LinkSpeed", "TunerCount", "TunerName", "TunerTypes", "VideoOut", "HdmiColour", "Aspect", "Ac3")
	FAST_TYPES = ("NetDown", "NetUp", "Volume")

	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)
		self.type = (type or "CpuTemp").strip()
		self.poll_interval = 30000 if self.type in self.SLOW_TYPES else 2000 if self.type in self.FAST_TYPES else 5000
		self.poll_enabled = self.type not in ("BoxName", "Image", "SkinVersion")
		self._static = None

	def _hddPath(self):
		for p in ("/media/hdd", "/media/usb"):
			if os.path.isdir(p) and isLocalMount(p):
				return p
		return None

	@cached
	def getText(self):
		t = self.type
		if t == "CpuTemp":
			v = cpuTemp()
			return "%d°C" % v if v is not None else ""
		if t == "CpuLoad":
			return "%d%%" % cpuLoad()
		if t in ("RamUsed", "RamPercent"):
			total, used = memInfo()
			if not total:
				return ""
			if t == "RamPercent":
				return "%d%%" % round(100 * used / total)
			return "%s / %s" % (human(used * 1024), human(total * 1024))
		if t == "FlashFree":
			total, free = diskInfo("/")
			return human(free) if total else ""
		if t == "HddFree":
			p = self._hddPath()
			if not p:
				return ""
			total, free = diskInfo(p)
			return ("%s / %s" % (human(free), human(total))) if total else ""
		if t == "Uptime":
			return uptime()
		if t == "IP":
			return ipAddress()
		if t == "LoadAvg":
			return loadAvg()
		if t == "Fan":
			return fanSpeed()
		if t == "RamMB":
			total, used = memInfo()
			return "%d / %d MB" % (used // 1024, total // 1024) if total else ""
		if t == "HddFreeOnly":
			p = self._hddPath()
			total, free = diskInfo(p) if p else (0, 0)
			return human(free) if total else "—"
		if t == "UsbFree":
			p = usbPath()
			total, free = diskInfo(p) if p else (0, 0)
			return human(free) if total else "—"
		if t in ("NetDown", "NetUp"):
			down, up = netRates()
			return kbits(down if t == "NetDown" else up)
		if t == "NetType":
			return netType()
		if t == "Online":
			return "متصل" if self.getBoolean() else "غير متصل"
		if t == "OnlineYes":
			return "متصل" if self.getBoolean() else ""
		if t == "OnlineNo":
			return "" if self.getBoolean() else "غير متصل"
		if t == "Gateway":
			return gateway() or "—"
		if t == "Dns":
			return dnsServers() or "—"
		if t == "Mac":
			i = mainInterface()
			return _readFirstLine("/sys/class/net/%s/address" % i).upper() if i else ""
		if t == "Netmask":
			i = mainInterface()
			return _ioctlAddr(i, 0x891b) if i else ""        # SIOCGIFNETMASK
		if t == "LinkSpeed":
			return linkSpeed(mainInterface()) or "—"
		if t in ("RxTotal", "TxTotal"):
			rx, tx = ifTotals(mainInterface())
			v = rx if t == "RxTotal" else tx
			return human(v) if v is not None else "—"
		if t == "Rotor":
			return rotorPosition() or "—"
		if t == "TunerCount":
			n = nimSockets()
			return "%d" % len(n) if n else "—"
		if t == "TunerName":
			n = nimSockets()
			return n[0][1] if n else ""
		if t == "TunerTypes":
			types = []
			for _l, _n, ty in nimSockets():
				if ty and ty not in types:
					types.append(ty)
			return "  ·  ".join(types)
		if t == "VideoOut":
			return videoOutput() or "—"
		if t == "HdmiColour":
			return hdmiColour() or "—"
		if t == "Aspect":
			return _readFirstLine("/proc/stb/video/aspect") or "—"
		if t == "Ac3":
			v = _readFirstLine("/proc/stb/audio/ac3")
			return AC3.get(v, v) or "—"
		if t == "Volume":
			return volume() or "—"
		if t == "SkinVersion":
			if self._static is None:
				v = _readFirstLine("/usr/share/enigma2/NileGlass_FHD/version.txt")
				self._static = ("v" + v) if v else ""
			return self._static
		if t in ("BoxName", "Image"):
			if self._static is None:
				self._static = boxName() if t == "BoxName" else imageName()
			return self._static
		return ""

	text = property(getText)

	@cached
	def getValue(self):
		t = self.type
		if t == "CpuLoad":
			return cpuLoad()
		if t == "RamPercent":
			total, used = memInfo()
			return int(round(100 * used / total)) if total else 0
		if t == "FlashPercent":
			total, free = diskInfo("/")
			return int(round(100 * (total - free) / total)) if total else 0
		if t == "HddPercent":
			p = self._hddPath()
			if p:
				total, free = diskInfo(p)
				return int(round(100 * (total - free) / total)) if total else 0
			return 0
		if t == "UsbPercent":
			p = usbPath()
			if p:
				total, free = diskInfo(p)
				return int(round(100 * (total - free) / total)) if total else 0
			return 0
		if t == "CpuTemp":
			v = cpuTemp()
			return max(0, min(100, v)) if v is not None else 0
		return 0

	value = property(getValue)

	@cached
	def getBoolean(self):
		if self.type in ("Online", "OnlineYes", "OnlineNo"):
			return bool(ipAddress()) or any(_ifUp(n) for n in interfaces())
		return bool(self.getValue())

	boolean = property(getBoolean)
	range = 100
