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
#              Uptime, IP, BoxName, Image
# Value types: CpuLoad, RamPercent, FlashPercent, HddPercent (0..100, for Progress)
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


def _readFirstLine(path):
	try:
		with open(path, "r") as f:
			return f.readline().strip()
	except Exception:
		return ""


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


def ipAddress():
	for ifname in ("eth0", "wlan0", "eth1", "wlan1", "ra0"):
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			try:
				addr = fcntl.ioctl(s.fileno(), 0x8915, struct.pack("256s", ifname[:15].encode()))[20:24]  # SIOCGIFADDR
			finally:
				s.close()
			return socket.inet_ntoa(addr)
		except Exception:
			continue
	return ""


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


def boxName():
	try:
		from Components.SystemInfo import getBoxDisplayName
		brand, model = getBoxDisplayName()
		return ("%s %s" % (brand, model)).strip()
	except Exception:
		return _readFirstLine("/proc/stb/info/vumodel") or _readFirstLine("/proc/stb/info/model")


def imageName():
	try:
		from Components.SystemInfo import BoxInfo
		return ("%s %s" % (BoxInfo.getItem("displaydistro", "OpenBh"), BoxInfo.getItem("imgversion", ""))).strip()
	except Exception:
		return "OpenBh"


class NGSysInfo(Poll, Converter):
	SLOW_TYPES = ("FlashFree", "HddFree", "FlashPercent", "HddPercent", "IP", "BoxName", "Image")

	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)
		self.type = (type or "CpuTemp").strip()
		self.poll_interval = 30000 if self.type in self.SLOW_TYPES else 5000
		self.poll_enabled = self.type not in ("BoxName", "Image")
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
		if t == "CpuTemp":
			v = cpuTemp()
			return max(0, min(100, v)) if v is not None else 0
		return 0

	value = property(getValue)
	range = 100
