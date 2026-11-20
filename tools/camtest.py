#!/usr/bin/env python3
"""The emu center: CCcam.cfg import (only new lines), line test, live status rows,
info, log, secrets hidden in the file viewer, the readers table columns.  argv: PYROOT"""
import importlib.util, os, socket, sys, tempfile, threading, types
import xml.etree.ElementTree as ET
PY = sys.argv[1]
fails = []


def check(name, ok, extra=""):
	print(("PASS " if ok else "FAIL ") + name, "" if ok else extra)
	if not ok:
		fails.append(name)


def mod(n, **kw):
	m = types.ModuleType(n); m.__dict__.update(kw); sys.modules[n] = m; return m


class Timer:
	def __init__(self): self.callback = []
	def start(self, ms, single=False): pass
	def stop(self): pass


class Label:
	def __init__(self, t=""): self.text = t
	def setText(self, t): self.text = t
	def getText(self): return self.text


class ListSrc:
	def __init__(self, l): self.list, self.idx, self.onSelectionChanged = l, 0, []
	def setList(self, l): self.list = l
	def getCurrent(self): return self.list[self.idx] if self.list else None
	def getIndex(self): return self.idx
	def setIndex(self, i): self.idx = i


class Screen(dict):
	def __init__(self, s): self.session = s; self.onLayoutFinish = []; self.onClose = []; self.onShow = []; self.onHide = []; self.shown = True
	def setTitle(self, t): self.title = t
	def close(self, *a): pass


mod("enigma", eTimer=Timer)
mod("twisted"); mod("twisted.internet", reactor=None)
for n in ("Components", "Components.Sources", "Screens"):
	mod(n)
mod("Components.ActionMap", ActionMap=lambda *a, **k: None)
mod("Components.Label", Label=Label)
mod("Components.ScrollLabel", ScrollLabel=Label)
mod("Components.Sources.List", List=ListSrc)
mod("Components.Sources.StaticText", StaticText=Label)
mod("Screens.ChoiceBox", ChoiceBox="ChoiceBox"); mod("Screens.MessageBox", MessageBox=types.SimpleNamespace(TYPE_YESNO=0, TYPE_INFO=1, TYPE_WARNING=2, TYPE_ERROR=3))
mod("Screens.Screen", Screen=Screen); mod("Screens.VirtualKeyBoard", VirtualKeyBoard="VKB")
mod("Components.config", ConfigSelection=object, ConfigText=object, ConfigYesNo=object, getConfigListEntry=lambda *a: a)
mod("Components.ConfigList", ConfigListScreen=type("CLS", (), {}))
pkg = mod("ngs"); pkg.__path__ = [os.path.join(PY, "Plugins/Extensions/NileGlassSetup")]
for name in ("readers", "camcenter"):
	spec = importlib.util.spec_from_file_location("ngs." + name, os.path.join(pkg.__path__[0], name + ".py"))
	m = importlib.util.module_from_spec(spec); sys.modules["ngs." + name] = m; spec.loader.exec_module(m)
R, C = sys.modules["ngs.readers"], sys.modules["ngs.camcenter"]

# ---- device / CCcam.cfg
check("device split", R.splitDevice("s1.x.com,12000") == ("s1.x.com", "12000") and R.splitDevice("h:15000") == ("h", "15000") and R.splitDevice("/dev/sci0") == ("/dev/sci0", ""))
cfg = """# my lines
C: s1.example.com 12000 ali secret1
C: s1.example.com 12000 ali secret1
c:new.example.net 14000 user2 pw2 # comment
N: nc.example.org 15000 bob pw3 01 02 03 04 05 06 07 08 09 10 11 12 13 14
F: localuser localpass
garbage line
"""
lines = R.parseCCcamCfg(cfg)
check("C: and N: lines read, duplicates once", [l[0] for l in lines] == ["C", "C", "N"] and lines[1][1] == "new.example.net", lines)
check("newcamd DES key kept", lines[2][5] == "0102030405060708091011121314", lines[2])
T = tempfile.mkdtemp()
srv = os.path.join(T, "oscam.server")
open(srv, "w").write("[reader]\nlabel = s1\nprotocol = cccam\ndevice = s1.example.com,12000\nuser = ali\npassword = secret1\n\n[reader]\nlabel = card\nprotocol = internal\ndevice = /dev/sci0\n")
sf = R.ServerFile(srv)
have = R.existingKeys(sf)
new = [l for l in lines if R.lineKey(l) not in have]
check("lines already in the file are skipped", [l[1] for l in new] == ["new.example.net", "nc.example.org"], new)
used = {r.label for r in sf.readers}
f1 = R.linesToFields(new[0], used); used.add(dict(f1)["label"])
f2 = R.linesToFields(new[1], used)
check("cccam reader fields", dict(f1)["protocol"] == "cccam" and dict(f1)["device"] == "new.example.net,14000" and dict(f1)["label"] == "new", f1)
check("newcamd reader fields", dict(f2)["protocol"] == "newcamd" and dict(f2)["key"] == "0102030405060708091011121314", f2)
check("free label", dict(R.linesToFields(("C", "s1.other.com", "1", "u", "p", ""), {"s1"}))["label"] == "s1_2")

# ---- line test (a local listening socket answers, a closed port does not)
srvsock = socket.socket(); srvsock.bind(("127.0.0.1", 0)); srvsock.listen(1)
port = srvsock.getsockname()[1]
dead = socket.socket(); dead.bind(("127.0.0.1", 0)); deadport = dead.getsockname()[1]; dead.close()
res = R.testLines([("up", "127.0.0.1", str(port)), ("down", "127.0.0.1", str(deadport))], timeout=2)
check("line test: answering server", res[0][0] == "up" and res[0][1] is True, res)
check("line test: closed port", res[1][1] is False and res[1][3], res)
srvsock.close()

# ---- live status from the api
XML = """<oscam version="2.26.11-11989" uptime="93784"><status>
<client type="s" name="root" protocol="server"><connection ip="::1" port="0">OK</connection></client>
<client type="p" name="Line_02" protocol="cccam"><request ecmtime="0"/><connection ip="my.server.net" port="14000">ERROR</connection></client>
<client type="r" name="conax" protocol="internal"><connection ip="" port="0">READER DEVICE ERROR</connection></client>
<client type="r" name="emulator" protocol="emu"><request ecmtime="12"/><connection ip="" port="0">CARDOK</connection></client>
<client type="p" name="server1" protocol="newcamd"><request ecmtime="182"/><connection ip="88.198.72.200" port="60000">CONNECTED</connection></client>
<client type="c" name="user1" protocol="dvbapi"><connection ip="127.0.0.1" port="0">OK</connection></client>
</status></oscam>"""
root = ET.fromstring(XML)
rows = C.statusRows(root)
check("readers first, then lines, clients, server", [r[0] for r in rows] == ["conax", "emulator", "Line_02", "server1", "user1", "root"], [r[0] for r in rows])
check("state in Arabic with colour", rows[0][6] == "الكارت مش موجود" and rows[0][7] == C.RED and rows[1][6] == "شغال" and rows[1][7] == C.GREEN, rows[:2])
check("ecm time shown only when known", rows[1][5] == "12 ms" and rows[2][5] == "", rows[1:3])
check("only lines", [r[0] for r in C.statusRows(root, True)] == ["conax", "emulator", "Line_02", "server1"])
s = C.statusSummary(rows)
check("summary", "شغال 2 من 4" in s and "conax" in s and "Line_02" in s and "عملاء: 1" in s, s)
check("no api -> no rows", C.statusRows(None) == [])

# ---- info
os.makedirs("/tmp/.ngtestemu", exist_ok=True)
open("/tmp/.ngtestemu/ngtestemu.version", "w").write("Unix starttime: 0\nVersion: 2.26.11-11989\nCompiler: armv7\nConfigDir: /etc/tuxbox/config/\nWebifPort: 0\n")
info = dict(C.infoRows("ngtestemu", T, root))
check("info from the version file in Arabic", info.get("النسخة", "").startswith("2.26.11") and info.get("فولدر الإعدادات") == "/etc/tuxbox/config/" and info.get("بورت الويب") == "0", info)
check("uptime from the api", info.get("شغال من", "").startswith("1 يوم 2 ساعة"), info)
check("not running -> one clear line", C.infoRows("nothere", T)[0][0] == "—")

# ---- file viewer hides secrets
txt = "[reader]\nlabel = s1\npassword = secret1\nkey = 0102\n[account]\nuser = a\npwd = topsecret\n[webif]\nhttpuser = admin\nhttppwd = adm\nC: host 1 user pass\nF: u1 p1 1 0 0\n"
m = C.maskText(txt)
check("secrets hidden", all(x not in m for x in ("secret1", "topsecret", "adm\n", " pass", "p1 ")) and "label = s1" in m and "C: host 1 user ****" in m and "F: u1 ****" in m, m)

# ---- log file from [global] logfile, tail
logp = os.path.join(T, "oscam.log")
open(logp, "w").write("".join("line %d\n" % i for i in range(5000)))
open(os.path.join(T, "oscam.conf"), "w").write("[global]\nlogfile = %s\n[webif]\nhttpport = 0\n" % logp)
check("log file from oscam.conf", C.logFile("oscam", T) == logp)
t = C.tail(logp, 1000)
check("tail starts on a whole line", t.startswith("line ") and t.rstrip().endswith("line 4999") and len(t) <= 1000, t[:20])
src, text = C.logText("oscam", T)
check("no webif -> the log file", src == logp and "line 4999" in text)

# ---- emu center: both emus listed
open(os.path.join(T, "ncam.server"), "w").write("[reader]\nlabel = x\n")
R_find, R_run = C.findServerFile, C.runningEmu
C.runningEmu = lambda: ("oscam", T)
C.findServerFile = lambda name, cdir: os.path.join(T, name + ".server")
run, emus = C.emuDirs()
check("running emu first, the other one too", run == "oscam" and list(emus) == ["oscam", "ncam"], emus)

# ---- readers table columns: no., host, port, password masked
scr = R.NileGlassReaders(types.SimpleNamespace(open=lambda *a, **k: None, openWithCallback=lambda *a, **k: None), "oscam", srv)
scr.reload()
row = scr["list"].list[0]
check("row: name, protocol, host, user, state, idx, colour, no., port, password", row[0] == "s1" and row[2] == "s1.example.com" and row[7] == "1" and row[8] == "12000" and row[9] == "****", row)
scr.toggleSecrets()
check("INFO shows the password in the table", scr["list"].list[0][9] == "secret1")
check("local card: no port", scr["list"].list[1][2] == "/dev/sci0" and scr["list"].list[1][8] == "")

pl = open(os.path.join(pkg.__path__[0], "plugin.py"), encoding="utf-8").read()
check("cam bar MENU opens the emu center", "from .camcenter import NileGlassCamCenter" in pl and "openCamCenter" in pl)
src = open(os.path.join(pkg.__path__[0], "camcenter.py"), encoding="utf-8").read()
check("the center never writes an emu file", "open(" not in src.replace('open(p, errors="replace")', "").replace('open(conf, errors="replace")', "").replace('open(path, "rb")', "").replace('open(self.path, encoding="utf-8", errors="replace")', "").replace("self.session.open(", ""), [l for l in src.splitlines() if "open(" in l and "session.open" not in l])
# ---- Blue Panel: left / right move round the installed emus
spec = importlib.util.spec_from_file_location("ngs.screenhooks", os.path.join(pkg.__path__[0], "screenhooks.py"))
H = importlib.util.module_from_spec(spec); spec.loader.exec_module(H)
class ML:
	def __init__(self): self.list = ["OSCam", "NCam", "CCcam"]; self.i = 2
	def getSelectedIndex(self): return self.i
	def moveToIndex(self, i): self.i = i
	def getCurrent(self): return self.list[self.i]
bp = {"list": ML(), "ng_emupos": Label(), "ng_emuname": Label(), "activecam": Label("OSCam")}
H.emuMove(bp, 1)
check("right after the last emu -> the first", bp["list"].i == 0 and bp["ng_emupos"].text.startswith("1 من 3"), bp["ng_emupos"].text)
H.emuMove(bp, -1)
check("left before the first -> the last", bp["list"].i == 2 and bp["ng_emuname"].text == "CCcam", bp["ng_emuname"].text)
H.emuMove(bp, 1)
check("the shown name follows, the running one is marked", bp["ng_emuname"].text == "OSCam   (الشغال)", bp["ng_emuname"].text)
H.emuMove(bp, -1)
bp["list"].list = ["OSCam"]; H.emuMove(bp, 1); H.emuPos(bp)
check("one emu: nothing moves", bp["list"].i == 2 and bp["ng_emupos"].text == "إيمو واحد مثبت")
hs = open(os.path.join(pkg.__path__[0], "screenhooks.py"), encoding="utf-8").read()
check("hook on the Blue Panel, above its own keys", "_addEmuSwitch(DeliteBluePanel)" in hs and "}, -2)" in hs)
print("\n%d failed" % len(fails) if fails else "\nall passed")
sys.exit(1 if fails else 0)
