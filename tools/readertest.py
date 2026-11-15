#!/usr/bin/env python3
"""Tests of the emu readers screen.  argv: PYROOT"""
import http.server, importlib.util, os, sys, tempfile, threading, time, types
PY = sys.argv[1]
T = tempfile.mkdtemp(prefix="ngrd")
def mod(n, **kw):
	m = types.ModuleType(n); m.__dict__.update(kw); sys.modules[n] = m; return m
class Timer:
	def __init__(self): self.callback = []; self.active = False; self.ms = None
	def start(self, ms, single=False): self.active = True; self.ms = ms
	def stop(self): self.active = False
class Label:
	def __init__(self, t=""): self.text = t
	def setText(self, t): self.text = t
	def getText(self): return self.text
class ListSrc:
	def __init__(self, l): self.list, self.idx, self.onSelectionChanged = l, 0, []
	def setList(self, l): self.list = l; self.idx = 0
	def getCurrent(self): return self.list[self.idx] if self.list else None
	def getIndex(self): return self.idx
	def setIndex(self, i): self.idx = i; [f() for f in self.onSelectionChanged]
	def up(self): self.setIndex(max(0, self.idx - 1))
	def down(self): self.setIndex(min(len(self.list) - 1, self.idx + 1))
	pageUp, pageDown = up, down
class Screen(dict):
	def __init__(self, s): self.session = s; self.onLayoutFinish = []; self.onClose = []
	def setTitle(self, t): self.title = t
	def close(self, *a): pass
class MB:
	TYPE_YESNO, TYPE_INFO, TYPE_WARNING, TYPE_ERROR = 0, 1, 2, 3
ui = []
mod("enigma", eTimer=Timer)
mod("twisted"); mod("twisted.internet", reactor=types.SimpleNamespace(callFromThread=lambda f, *a: ui.append((f, a))))
for n in ("Components", "Components.Sources", "Screens"): mod(n)
mod("Components.ActionMap", ActionMap=lambda *a, **k: None)
mod("Components.Label", Label=Label)
mod("Components.Sources.List", List=ListSrc)
mod("Components.Sources.StaticText", StaticText=Label)
mod("Screens.ChoiceBox", ChoiceBox="ChoiceBox"); mod("Screens.MessageBox", MessageBox=MB); mod("Screens.Screen", Screen=Screen)
mod("Screens.VirtualKeyBoard", VirtualKeyBoard="VKB")
class El:
	def __init__(self, default=None, **k): self.value = default
class Sel(El):
	def __init__(self, default=None, choices=()): self.value = default; self.choices = choices
class CLS:
	def __init__(self, lst, session=None, fullUI=False, **k):
		self["config"] = types.SimpleNamespace(list=lst)
		self["key_red"] = Label("Cancel"); self["key_green"] = Label("Save")
mod("Components.config", ConfigSelection=Sel, ConfigText=El, ConfigYesNo=El, getConfigListEntry=lambda *a: a)
mod("Components.ConfigList", ConfigListScreen=CLS)
spec = importlib.util.spec_from_file_location("ngrd", os.path.join(PY, "Plugins/Extensions/NileGlassSetup/readers.py"))
rd = importlib.util.module_from_spec(spec); spec.loader.exec_module(rd)
ok = True
def check(c, m):
	global ok; print(("PASS " if c else "FAIL ") + m); ok = ok and c

SAMPLE = """# my lines - do not lose this comment
[reader]
label = server1
protocol = cccam
device = s1.example.com,12000
user = ali
password = secret1
group = 1
cccversion = 2.3.2

[reader]
label  =  local_card
protocol = internal
device = /dev/sci0
caid = 1830
# keep me
group = 2
enable = 0

[reader]
label = server3
protocol = newcamd
device = s3.example.com,15000
user = bob
password = pw3
key = 0102030405060708091011121314
group = 1
"""
cdir = os.path.join(T, "config"); os.makedirs(cdir)
path = os.path.join(cdir, "oscam.server")
open(path, "w").write(SAMPLE); os.chmod(path, 0o600)

sf = rd.ServerFile(path)
check([r.label for r in sf.readers] == ["server1", "local_card", "server3"], "three readers parsed")
check(sf.readers[1].get("caid") == "1830" and not sf.readers[1].enabled and sf.readers[0].enabled, "fields and enable state")
check(sf.text() == SAMPLE, "unchanged file written back byte for byte")

# edit an existing field, add a missing field, remove a field
sf.setField(0, "device", "new.example.com,13000")
sf.setField(0, "inactivitytimeout", "30")
sf.removeField(2, "key")
t = sf.text()
check("device = new.example.com,13000\n" in t and "s1.example.com" not in t, "field edited in place")
check(t.index("inactivitytimeout = 30") < t.index("[reader]\nlabel  =  local_card"), "new field stays inside its reader")
check("0102030405" not in t and "label = server3" in t, "field removed")
check("# my lines - do not lose this comment" in t and "# keep me" in t, "comments kept")
# delete the middle reader
sf.delete(1)
t = sf.text()
check([r.label for r in sf.readers] == ["server1", "server3"] and "/dev/sci0" not in t and "\n\n\n" not in t, "reader deleted cleanly")
# add
sf.add([("label", "srv4"), ("protocol", "cccam"), ("device", "h,1"), ("user", "u"), ("password", "p")])
check(sf.readers[-1].label == "srv4" and sf.text().endswith("[reader]\nlabel = srv4\nprotocol = cccam\ndevice = h,1\nuser = u\npassword = p\n"), "reader added at the end")

# save: backup + atomic + mode kept
time.sleep(0.01)
b = sf.save()
check(os.path.isfile(b) and open(b).read() == SAMPLE, "backup holds the old file")
check(open(path).read() == sf.text() and oct(os.stat(path).st_mode & 0o777) == "0o600", "file written, permissions kept")
check(not os.path.exists(path + ".ngtmp"), "no temp file left")

# another program changes the file -> nothing written
open(path, "a").write("# written by the other plugin\n")
os.utime(path, ns=(time.time_ns() + 10**9, time.time_ns() + 10**9))
sf.setField(0, "user", "zzz")
try:
	sf.save(); refused = False
except rd.ChangedOutside:
	refused = True
check(refused and "# written by the other plugin" in open(path).read() and "zzz" not in open(path).read(), "outside change detected, nothing overwritten")

# backups are trimmed
sf.load()
for i in range(13):
	sf.setField(0, "group", str(i)); time.sleep(1.01 if i == 12 else 0)
	open(path + rd.BACKUP_TAG + "2020010%02d-000000" % i, "w").write("x")
sf.save()
check(len(sf.backups()) == rd.KEEP_BACKUPS, "only the last %d backups kept (%d)" % (rd.KEEP_BACKUPS, len(sf.backups())))
# restore
first = [b2 for b2 in sf.backups()][0]
sf.restore(first)
check(sf.text() == open(first).read() and any("before-restore" in x for x in sf.backups()), "restore writes the backup back and keeps the current file")

# CRLF file
crlf = os.path.join(T, "crlf.server")
open(crlf, "w", newline="").write("[reader]\r\nlabel = a\r\nenable = 1\r\n")
c = rd.ServerFile(crlf); c.setField(0, "enable", "0"); c.setField(0, "group", "1")
check(c.text() == "[reader]\r\nlabel = a\r\nenable = 0\r\ngroup = 1\r\n", "Windows line endings kept")

# finding the file of the running emu
check(rd.findServerFile("oscam", cdir) == path, "server file from the emu's config dir")
check(rd.findServerFile("ncam", cdir) == path, "ncam falls back to oscam.server in its dir")

# live state from the emu's own web interface
XML = b'<?xml version="1.0"?><oscam><status><client type="p" name="server1" protocol="cccam"><request caid="0500" ecmtime="312">x</request><connection ip="1.2.3.4" port="12000">CONNECTED</connection></client><client type="p" name="server3"><connection>DISCONNECTED</connection></client><client type="c" name="me"><connection>OK</connection></client></status></oscam>'
class H(http.server.BaseHTTPRequestHandler):
	def do_GET(self):
		if "oscamapi.html?part=status" in self.path:
			self.send_response(200); self.end_headers(); self.wfile.write(XML)
		else:
			self.send_response(404); self.end_headers()
	def log_message(self, *a): pass
srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
open(os.path.join(cdir, "oscam.conf"), "w").write("[global]\nlogfile=/tmp/x\n[webif]\nhttpport = %d\n" % srv.server_port)
st = rd.readerStates("oscam", cdir)
check(st == {"server1": "CONNECTED", "server3": "DISCONNECTED", rd.TIMES: {"server1": 312}}, "states from the webif: %r" % st)
class _R:
	def __init__(s, label, en=True): s.label, s.enabled = label, en
_sum = rd.summary([_R("server1"), _R("server3"), _R("off", False)], st)
check("شغال 1 من 2" in _sum and "واقع: server3" in _sum and "الأسرع: server1 (312 ms)" in _sum, "summary line: %r" % _sum)
open(os.path.join(cdir, "oscam.conf"), "w").write("[webif]\nhttpport = 0\n")
check(rd.readerStates("oscam", cdir) == {}, "webif off: no states, no error")
srv.shutdown()

# the screen: every change asks first; "no" changes nothing
open(path, "w").write(SAMPLE)
answers = []
opened = []
class Session:
	def open(self, *a, **k): opened.append(a)
	def openWithCallback(self, cb, scr, *a, **k):
		opened.append((scr,) + a)
		if scr is MB:
			cb(answers.pop(0) if answers else False)
s = Session()
rd.runningEmu = lambda: ("oscam", cdir)
scr = rd.NileGlassReaders(s)
for f in scr.onLayoutFinish: f()
check([r[0] for r in scr["list"].list] == ["server1", "local_card", "server3"] and scr["list"].list[1][4] == "موقوف", "list filled, stopped reader marked")
check("secret1" not in scr["details"].text and "password = ****" in scr["details"].text, "password hidden")
scr.toggleSecrets(); check("password = secret1" in scr["details"].text, "INFO shows the password"); scr.toggleSecrets()
before = open(path).read()
answers[:] = [False]
scr.askDelete()
check(open(path).read() == before, "delete answered no: file untouched")
answers[:] = [True, False]   # yes delete, no restart
scr.askDelete()
after = open(path).read()
check("label = server1" not in after and "local_card" in after and len(scr.sf.backups()) >= 1, "delete answered yes: reader gone, backup made")
check(any(o[0] is MB and "إعادة تشغيل" in o[1] for o in opened), "asks before restarting the emu")
restarted = []
sys.modules["ngrd"] = rd
answers[:] = [True, False]
scr["list"].setIndex(0)   # local_card
scr.askToggle()
check("enable = 1" in open(path).read().split("[reader]")[1], "stopped reader started (enable = 1)")
# edit through the edit screen: open it, change fields, green
edits = []
s.openWithCallback = (lambda orig: (lambda cb, scr2, *a, **k: edits.append((cb, scr2, a)) if scr2 is rd.NileGlassReaderEdit else orig(cb, scr2, *a, **k)))(s.openWithCallback)
scr["list"].setIndex(1)   # server3 (second row after the delete)
scr.edit()
cb, cls, args = edits[-1]
ed = cls(s, *args)
check(ed.title.startswith("تعديل") and [k for k, _e in ed.items][:5] == ["label", "protocol", "device", "user", "password"], "edit screen lists the fields: %r" % [k for k, _e in ed.items])
check(ed["key_green"].text == "حفظ" and ed["key_red"].text == "إلغاء", "green save / red cancel")
dict(ed.items)["password"].value = "newpw"
dict(ed.items)["device"].value = "s9.example.com,15009"
closed = []
ed.close = lambda *a: closed.append(a)
ed.keySave()
check(closed and closed[0][0] == {"password": "newpw", "device": "s9.example.com,15009"}, "only changed fields returned: %r" % (closed and closed[0]))
answers[:] = [True, False]
cb(closed[0][0])
t = open(path).read()
check("password = newpw" in t and "device = s9.example.com,15009" in t and "label = server3" in t, "edit saved")
# cancel changes nothing
before = open(path).read()
scr.edit(); cb, cls, args = edits[-1]; ed = cls(s, *args); ed.close = lambda *a: cb(*a) if a else cb(None)
ed.keyCancel()
check(open(path).read() == before, "cancel: file untouched")
# a new reader through the same screen
answers[:] = [True, False]
scr.addWizard(); cb, cls, args = edits[-1]; nd = cls(s, *args)
d = dict(nd.items); d["label"].value = "newsrv"; d["device"].value = "n.example.com:16000"; d["user"].value = "u9"; d["password"].value = "p9"
nd.close = lambda *a: cb(*a); nd.keySave()
t = open(path).read()
check("label = newsrv\nprotocol = cccam\ndevice = n.example.com,16000\nuser = u9\npassword = p9" in t, "new reader from the edit screen")
nd2 = cls(s, *args); nd2.close = lambda *a: cb(*a); n = len(opened); nd2.keySave()
check(len(opened) == n + 1 and "label" in opened[-1][1], "new reader without name refused")
check(os.path.isfile(rd.LOG) and "edit screen save" in open(rd.LOG).read(), "steps written to the log")
# a C: line
answers[:] = [True, False]
scr.gotCLine("C: my.server.net 23000 user1 pass1")
t = open(path).read()
check("label = my\nprotocol = cccam\ndevice = my.server.net,23000\nuser = user1\npassword = pass1" in t, "C: line added as a cccam reader")
answers[:] = []
n = len(opened); scr.gotCLine("rubbish"); check(len(opened) == n + 1 and open(path).read() == t, "bad C: line refused")
# the other plugin changed the file while the screen was open
open(path, "a").write("# other plugin\n"); os.utime(path, ns=(time.time_ns() + 5 * 10**9,) * 2)
answers[:] = [True, False]
scr.askDelete()
check("# other plugin" in open(path).read() and "label = my" in open(path).read(), "outside change: delete not done, file re-read")
# keys through the ActionMap wrappers: no file -> a message, not silence
opened.clear()
empty = rd.NileGlassReaders(s); empty.sf = None
empty.safe(empty.askDelete)()
check(opened and opened[-1][0] is MB, "key with no file open explains why")
opened.clear()
scr.reload()
def boom(): raise ValueError("x")
boom.__name__ = "addMenu"
scr.safe(boom)()
check(opened and opened[-1][0] is MB and "ValueError" in opened[-1][1], "an error is shown, not swallowed")
import shutil; shutil.rmtree(T, ignore_errors=True)
print("ALL OK" if ok else "SOME TESTS FAILED")
