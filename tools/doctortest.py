#!/usr/bin/env python3
"""Skin doctor: checks run anywhere without failing, settings snapshots (last 10 kept,
newest first), fixes only through fix(), crash guard offers three answers.  argv: PYROOT"""
import importlib.util, os, sys, tempfile, time, types
fails = []


def check(name, ok, extra=""):
	print(("PASS " if ok else "FAIL ") + name, "" if ok else extra)
	if not ok:
		fails.append(name)


PY = sys.argv[1]
sys.path.insert(0, PY)
pkg = types.ModuleType("ngs"); pkg.__path__ = [os.path.join(PY, "Plugins/Extensions/NileGlassSetup")]
sys.modules["ngs"] = pkg
up = types.ModuleType("ngs.updater"); up.installedVersion = lambda: "3.1.0"; sys.modules["ngs.updater"] = up
spec = importlib.util.spec_from_file_location("ngs.doctor", os.path.join(pkg.__path__[0], "doctor.py"))
D = importlib.util.module_from_spec(spec); sys.modules["ngs.doctor"] = D; spec.loader.exec_module(D)

tmp = tempfile.mkdtemp()
D.CONF = os.path.join(tmp, "nileglass.conf")
D.SNAP_DIR = os.path.join(tmp, "snaps")
check("no settings file -> no snapshot", D.snapshot("update") is None)
open(D.CONF, "w").write("[style]\nlite = 0\n")
real = time.strftime
for i in range(13):
	D.time.strftime = lambda f, t=None, i=i: ("202611%02d-120000" % (i + 1)) if t is None else real(f, t)
	D.snapshot("update" if i % 2 else "manual")
D.time.strftime = real
snaps = D.snapshots()
check("only the last 10 kept", len(snaps) == 10, len(snaps))
check("newest first", "20261113" in snaps[0][0] and "20261104" in snaps[-1][0], [s[0] for s in snaps[:2]])
check("label says when, version and why", "13/11 12:00" in snaps[0][1] and "v3.1.0" in snaps[0][1] and ("يدوي" in snaps[0][1] or "قبل التحديث" in snaps[0][1]), snaps[0][1])
check("snapshot is a copy", open(snaps[0][0]).read() == open(D.CONF).read())

t0 = time.time()
items = D.checks()
check("checks run here without failing", isinstance(items, list) and len(items) >= 3, items)
check("each check: state, title, detail, fix", all(len(i) == 4 and i[0] in (D.OK, D.WARN, D.BAD) and (i[3] is None or i[3] in D.FIXES) for i in items), items)
check("checks are quick", time.time() - t0 < 5, time.time() - t0)
check("snapshot check sees the copies", any(i[1] == "نسخ الإعدادات" and i[0] == D.OK for i in items))
b, w = D.summary([(D.BAD, "", "", None), (D.WARN, "", "", None), (D.OK, "", "", None)])
check("summary counts", (b, w) == (1, 1))
check("mb", D.mb(5 * 1048576) == "5 MB" and D.mb(20 * 1073741824).endswith("GB"))

# fixes: safe mode writes lite + default font through setConf and keeps a copy first
got = {}
St = types.ModuleType("Components.NileGlassStyle"); St.apply = lambda: got.setdefault("applied", True)
import Components
sys.modules["Components.NileGlassStyle"] = St; Components.NileGlassStyle = St
n = len(D.snapshots())
D.fix("safemode", lambda v: got.update(v))
check("safe mode = lite + default font", got.get("style") == {"lite": 1, "font": "ubuntu"} and got.get("applied"), got)
check("a copy is kept before a fix", len(D.snapshots()) == min(10, n + 1) and "doctor" in D.snapshots()[0][0])

# crash guard: three answers, nothing done on 'leave it'
src = open(os.path.join(pkg.__path__[0], "crashguard.py"), encoding="utf-8").read()
check("crash offer has safe mode / previous / nothing", '"safe"' in src and '"previous"' in src and '"none"' in src and "ChoiceBox" in src)
pl = open(os.path.join(pkg.__path__[0], "plugin.py"), encoding="utf-8").read()
check("snapshot before every update download", pl.index('snapshot("update")') < pl.index("updater.downloadAsync(info, downloaded)"))
check("doctor in Tools", '"doctor"' in pl and "openDoctor(self.session)" in pl)
check("doctor after an update", "afterUpdate(session)" in pl)
check("doctor checks off the GUI thread", 'name="NileGlass-doctor"' in pl)
print("\n%d failed" % len(fails) if fails else "\nall passed")
sys.exit(1 if fails else 0)
