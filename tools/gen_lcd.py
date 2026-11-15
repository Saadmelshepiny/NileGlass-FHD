#!/usr/bin/env python3
"""NileGlass front display skin (800x480 colour LCD) with the default choices.
The layout itself lives in Components/NileGlassLcd.py (the settings screen
writes the same file with the user's choices).  argv: OUT_XML"""
import importlib.util, os, sys
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("lcd", os.path.join(here, "..", "build/root/usr/lib/enigma2/python/Components/NileGlassLcd.py"))
lcd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lcd)
open(sys.argv[1], "w", encoding="utf-8").write(lcd.build())
print("lcd skin written")
