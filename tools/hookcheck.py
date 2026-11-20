#!/usr/bin/env python3
"""Static check: nothing but bound methods (self.x / obj.method) may be appended to
onLayoutFinish - enigma2 exec()s any other callable and crashes.  argv: PYROOT"""
import re, sys, os
bad = []
for root, _d, files in os.walk(sys.argv[1]):
	for f in files:
		if f.endswith(".py"):
			p = os.path.join(root, f)
			for i, line in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
				m = re.search(r"onLayoutFinish\.append\((.*)\)\s*$", line.strip())
				arg = m.group(1).strip() if m else ""
				plain = bool(re.match(r"^[A-Za-z_]\w*$", arg)) and not re.match(r"^_?[A-Z][A-Z0-9_]*$", arg)   # a local function: not a bound method (CONSTANTS are compiled code, exec'd on purpose)
				if m and (plain or arg.startswith(("lambda", "partial", "boundFunction")) or "(" in arg.rstrip(")").split(".")[-1] and not arg.endswith(".run")):
					bad.append("%s:%d %s" % (p, i, line.strip()))
print("\n".join(bad) if bad else "hook check ok")
sys.exit(1 if bad else 0)
