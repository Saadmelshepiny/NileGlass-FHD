#!/usr/bin/env python3
"""Screen additions that each show what belongs to that screen:
  - MovieSelection (recordings): the list on the left, cards on the right with
    poster, channel, date, length, size, quality, how far it was watched and
    the description;
  - every infobar: a small warning when the flash or the disk is almost full;
  - the readers screen: one summary line (working / down / fastest / scrambled
    channels opened today).
Idempotent (marked blocks are replaced).  Run after gen_cards.py / gen_dash.py.
argv: SKINDIR"""
import os, re, sys

SK = sys.argv[1]
path = os.path.join(SK, "skin.xml")
skin = open(path, encoding="utf-8").read()


def W(src, render, x, y, w, h, conv=(), font=None, fg="fg", halign="left", valign="center", wrap=False, extra=""):
	a = '<widget source="%s" render="%s" position="%d,%d" size="%d,%d"' % (src, render, x, y, w, h)
	if font:
		a += ' font="%s" foregroundColor="%s" backgroundColor="bgCard" transparent="1" halign="%s" valign="%s"%s' % (font, fg, halign, valign, "" if wrap else ' noWrap="1"')
	a += (" " + extra if extra else "")
	c = "".join('<convert type="%s">%s</convert>' % cv for cv in conv)
	return "\t\t" + a + (">%s</widget>" % c if c else "/>")


def card(x, y, w, h):
	return '\t\t<eLabel position="%d,%d" size="%d,%d" backgroundColor="bgCard" cornerRadius="18" zPosition="-9"/>' % (x, y, w, h)


def text(x, y, w, h, t, font="Regular;20", fg="fgDim", halign="left"):
	return '\t\t<eLabel text="%s" position="%d,%d" size="%d,%d" font="%s" foregroundColor="%s" backgroundColor="bgCard" transparent="1" halign="%s" valign="center" noWrap="1"/>' % (t, x, y, w, h, font, fg, halign)


# ------------------------------------------------------------------ recordings
S = "Service"
X, Y, CW = 1046, 140, 814
LC = CW - 40 - 170
movie = ['\t<!-- NG-MORE MovieSelection BEGIN -->',
	'\t<screen name="MovieSelection" position="0,0" size="1920,1080" backgroundColor="transparent" flags="wfNoBorder">',
	'\t\t<panel name="NG_Frame"/>',
	'\t\t<widget name="list" position="64,140" size="960,750" itemHeight="50" font="Regular;27" pbarShift="12" pbarHeight="12" pbarLargeWidth="70" pbarColour="#2f9cff" pbarColourSeen="#3cc85a" pbarColourRec="#e23b3b" partIconeShift="6" spaceIconeText="10" iconsWidth="32" spaceRight="8" dateWidth="220" backgroundColor="bg" foregroundColor="fg" foregroundColorSelected="white" backgroundColorSelected="bgSel" scrollbarMode="showOnDemand" scrollbarWidth="6" scrollbarSliderForegroundColor="accent" enableWrapAround="1" transparent="1"/>',
	'\t\t<widget name="chosenletter" position="64,140" size="960,750" font="Medium;120" foregroundColor="gold" backgroundColor="bg" transparent="1" halign="center" valign="center" zPosition="4"/>',
	'\t\t<eLabel position="64,900" size="960,1" backgroundColor="line" zPosition="-8"/>',
	'\t\t<widget name="TrashcanSize" position="64,906" size="420,44" font="Regular;22" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1"/>',
	'\t\t<widget name="freeDiskSpace" position="490,906" size="534,44" font="Regular;22" foregroundColor="fgDim" backgroundColor="bg" transparent="1" halign="right" valign="center" noWrap="1"/>',
	'\t\t<widget name="waitingtext" position="64,906" size="960,44" font="Regular;22" foregroundColor="gold" backgroundColor="bg" transparent="1" halign="left" valign="center" noWrap="1" zPosition="2"/>',
	'\t\t<widget name="DescriptionBorder" position="0,0" size="0,0"/>',
	'\t\t<widget name="movie_sort" position="0,0" size="0,0"/>',
	'\t\t<widget name="movie_off" position="0,0" size="0,0"/>',
	'\t\t<!-- the recording under the cursor -->',
	card(X, Y, CW, 300),
	W(S, "NGPoster", X + CW - 166, Y + 16, 150, 225, extra='delay="300" fallback="NileGlass_FHD/ui/noposter.png" borderWidth="2" borderColor="posterBorder" zPosition="3"'),
	W(S, "Label", X + 20, Y + 12, LC, 30, [("MovieInfo", "RecordServiceName")], "Medium;22", "fgDim"),
	W(S, "Label", X + 20, Y + 44, LC, 76, [("ServiceName", "Name")], "Medium;30", "accent", valign="top", wrap=True)]
for i, (label, conv, col) in enumerate((("التاريخ", ("NGMovieInfo", "Recorded"), "fg"), ("المدة", ("NGMovieInfo", "Length"), "fg"),
		("الحجم", ("NGMovieInfo", "Size"), "fg"), ("الجودة", ("NGMovieInfo", "Quality"), "gold"))):
	yy = Y + 130 + i * 38
	movie += [text(X + 20, yy, 110, 34, label), W(S, "Label", X + 130, yy, LC - 110, 34, [conv], "Regular;24", col)]
movie += [card(X, Y + 312, CW, 128),
	text(X + 20, Y + 322, 300, 28, "المشاهدة"),
	W(S, "Label", X + 20, Y + 352, CW - 40, 36, [("NGMovieInfo", "Watched")], "Medium;26", "fg"),
	'\t\t<eLabel position="%d,%d" size="%d,8" backgroundColor="bgBar" cornerRadius="4" zPosition="-7"/>' % (X + 20, Y + 400, CW - 240),
	W(S, "Progress", X + 20, Y + 400, CW - 240, 8, [("NGMovieInfo", "WatchedPct")], extra='pixmap="NileGlass_FHD/ui/progress_sib.png" transparent="1" zPosition="1"'),
	W(S, "Label", X + CW - 210, Y + 388, 190, 32, [("NGMovieInfo", "Left")], "Regular;22", "gold", halign="right"),
	card(X, Y + 452, CW, 358),
	text(X + 20, Y + 462, 300, 28, "القصة"),
	W(S, "Label", X + 20, Y + 494, CW - 40, 304, [("EventName", "FullDescription")], "Regular;23", "#d6dbe1", valign="top", wrap=True),
	'\t</screen>',
	'\t<!-- NG-MORE MovieSelection END -->']
skin = re.sub(r"\t<!-- NG-MORE MovieSelection BEGIN -->.*?<!-- NG-MORE MovieSelection END -->\n", "", skin, flags=re.S)
skin = skin.replace("</skin>", "\n".join(movie) + "\n</skin>")

# ------------------------------------------------------------------ infobars: storage almost full
WARN = '\t\t<widget source="session.CurrentService" render="Label" position="1266,%d" size="118,54" font="Medium;19" foregroundColor="orange" backgroundColor="bgDeep" transparent="1" halign="center" valign="center" noWrap="1" zPosition="3"><convert type="NGSysInfo">StorageWarn</convert></widget><!-- NG-MORE storage -->'


def addWarn(text):
	text = re.sub(r"\n[^\n]*<!-- NG-MORE storage -->", "", text)
	return re.sub(r'(\n\t\t<ePixmap pixmap="NileGlass_FHD/ui/ib_top_right.png" position="1130,(\d+)"[^\n]*)', lambda m: m.group(1) + "\n" + WARN % int(m.group(2)), text)


skin = addWarn(skin)
lp = os.path.join(SK, "layouts", "infobar_compact.xml")
if os.path.isfile(lp):
	lay = open(lp, encoding="utf-8").read()       # read first: opening for writing empties the file
	if lay.strip():
		lay = addWarn(lay)
		open(lp, "w", encoding="utf-8").write(lay)
		print("gen_more: compact infobar warnings:", lay.count("NG-MORE storage"))

# ------------------------------------------------------------------ readers: summary line
m = re.search(r'<screen name="NileGlassReaders".*?</screen>', skin, re.S)
if m:
	block = m.group(0)
	new = re.sub(r'\n[^\n]*<!-- NG-MORE summary -->', "", block)
	new = new.replace('<widget name="file" position="80,138" size="1760,36"', '<widget name="file" position="80,138" size="860,36"')
	new = new.replace('<panel name="NG_Frame"/>', '<panel name="NG_Frame"/>\n\t\t<widget name="summary" position="950,138" size="890,36" font="Regular;22" foregroundColor="fg" backgroundColor="bg" transparent="1" halign="right" valign="center" noWrap="1"/><!-- NG-MORE summary -->', 1)
	skin = skin.replace(block, new)
# ------------------------------------------------------------------ skin selector: its preview picture inside the skin cards
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashlib import PREVIEW
m = re.search(r'<screen name="SkinSelector".*?</screen>', skin, re.S)
if m and "NG-DASH skin cards" in m.group(0):
	block = m.group(0)
	x0 = int(re.search(r'<!-- NG-DASH skin cards -->\n\t*<panel position="(\d+),0"', block).group(1))
	new = re.sub(r'<widget name="preview"[^>]*/>', '<widget name="preview" position="%d,%d" size="%d,%d" alphatest="blend" zPosition="200"/>' % (x0 + PREVIEW[0], PREVIEW[1], PREVIEW[2], PREVIEW[3]), block, count=1)
	skin = skin.replace(block, new)
	print("gen_more: skin preview at", x0 + PREVIEW[0], PREVIEW[1])
open(path, "w", encoding="utf-8").write(skin)
print("gen_more: MovieSelection, %d infobar warnings, readers summary" % skin.count("NG-MORE storage"))
