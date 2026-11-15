#!/usr/bin/env python3
"""NileGlass front display skin (800x480 colour LCD). argv: OUT_XML"""
import sys
ACC, GOLD, DIM, BAR = "#2f9cff", "#f2c94c", "#9aa3ae", "#1d2633"

# The panel behind the front window shows a little less than its 800x480
# (the edges sit under the bezel), so everything keeps 40 px from the sides.
L, R = 40, 760          # usable left / right edge
EV = "#ffc83d"          # programme name: warm amber, readable from the sofa (blue was too dark)


def info(srcSvc, srcEv, picon, name="Name"):
	return f'''		<eLabel position="0,0" size="800,6" backgroundColor="{ACC}" zPosition="1"/>
		<widget source="{picon}" render="LcdPicon" position="{L},26" size="250,150" alphatest="blend" zPosition="2">
			<convert type="ServiceName">Reference</convert>
		</widget>
		<widget source="global.CurrentTime" render="Label" position="320,18" size="{R - 320},96" font="NGLcd;88" foregroundColor="#ffffff" halign="right" valign="center" noWrap="1">
			<convert type="ClockToText">Format:%H:%M</convert>
		</widget>
		<widget source="global.CurrentTime" render="Label" position="320,116" size="{R - 320},36" font="NGLcdLight;30" foregroundColor="#e6eaef" halign="right" valign="center" noWrap="1">
			<convert type="NGDate">{{A}} {{d}} {{B}}</convert>
		</widget>
		<widget source="global.CurrentTime" render="Label" position="320,152" size="{R - 320},30" font="NGLcdLight;25" foregroundColor="{DIM}" halign="right" valign="center" noWrap="1">
			<convert type="NGHijri"/>
		</widget>
		<widget source="session.RecordState" render="FixedLabel" text="REC" position="{L + 262},26" size="90,36" font="NGLcd;30" foregroundColor="#ff4040" halign="left" valign="center" zPosition="3">
			<convert type="ConditionalShowHide"/>
		</widget>
		<eLabel position="{L},194" size="{R - L},2" backgroundColor="{BAR}" zPosition="1"/>
		<widget source="{srcSvc}" render="Label" position="{L},204" size="{R - L},62" font="NGLcd;50" foregroundColor="#ffffff" halign="center" valign="center" noWrap="1">
			<convert type="ServiceName">{name}</convert>
		</widget>
		<widget source="{srcEv}" render="Label" position="{L},270" size="{R - L},104" font="NGLcd;44" foregroundColor="{EV}" halign="center" valign="center">
			<convert type="EventName">Name</convert>
		</widget>
		<eLabel position="{L},386" size="{R - L},14" backgroundColor="{BAR}" zPosition="1"/>
		<widget source="{srcEv}" render="Progress" position="{L},386" size="{R - L},14" foregroundColor="{EV}" backgroundColor="{BAR}" zPosition="2">
			<convert type="EventTime">Progress</convert>
		</widget>
		<widget source="{srcEv}" render="Label" position="{L},408" size="170,56" font="NGLcd;38" foregroundColor="{DIM}" halign="left" valign="center" noWrap="1">
			<convert type="EventTime">StartTime</convert><convert type="ClockToText">Format:%H:%M</convert>
		</widget>
		<widget source="{srcEv}" render="Label" position="{L + 180},408" size="{R - L - 360},56" font="NGLcd;38" foregroundColor="#ffffff" halign="center" valign="center" noWrap="1">
			<convert type="EventTime">VFDRemaining</convert><convert type="RemainingToText">VFD</convert>
		</widget>
		<widget source="{srcEv}" render="Label" position="{R - 170},408" size="170,56" font="NGLcd;38" foregroundColor="{DIM}" halign="right" valign="center" noWrap="1">
			<convert type="EventTime">EndTime</convert><convert type="ClockToText">Format:%H:%M</convert>
		</widget>'''


def screen(name, body):
	return f'\t<screen name="{name}" position="fill" resolution="800,480" backgroundColor="#000000">\n{body}\n\t</screen>\n'

out = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
	'<!-- NileGlass FHD - front display (800x480). Every screen not defined here comes from the image\'s default display skin. -->',
	'<skin>',
	'\t<include filename="/usr/share/enigma2/display/skin_default/skin_display_templates.xml"/>',
	'\t<fonts>',
	'\t\t<font filename="NileGlass-Medium.ttf" name="NGLcd" scale="100"/>',
	'\t\t<font filename="NileGlass-Regular.ttf" name="NGLcdLight" scale="100"/>',
	'\t</fonts>', '']
out.append(screen("InfoBarSummary", info("session.CurrentService", "session.Event_Now", "session.CurrentService")))
out.append(screen("ChannelSelectionSummary", info("parent.ServiceEvent", "parent.ServiceEvent", "parent.ServiceEvent")))
out.append(screen("ChannelSelectionRadioSummary", info("parent.ServiceEvent", "parent.ServiceEvent", "parent.ServiceEvent")))
for epg in ("GraphicalEPGPIGSummary", "GraphicalEPGSummary", "EPGSelectionSummary", "EPGSelectionMultiSummary", "GraphicalInfoBarEPGSummary"):
	out.append(screen(epg, info("parent.Service", "parent.Event", "parent.Service")))
out.append(screen("InfoBarMoviePlayerSummary", f'''		<eLabel position="0,0" size="800,6" backgroundColor="{ACC}" zPosition="1"/>
		<widget source="global.CurrentTime" render="Label" position="40,16" size="720,100" font="NGLcd;88" foregroundColor="#ffffff" halign="right" valign="center" noWrap="1">
			<convert type="ClockToText">Format:%H:%M</convert>
		</widget>
		<widget source="session.CurrentService" render="Label" position="40,40" size="400,56" font="NGLcd;40" foregroundColor="{GOLD}" halign="left" valign="center" noWrap="1">
			<convert type="NGPlayEnd"/>
		</widget>
		<widget source="session.CurrentService" render="Label" position="40,140" size="720,200" font="NGLcd;56" foregroundColor="#ffc83d" halign="center" valign="center">
			<convert type="ServiceName">Name</convert>
		</widget>
		<eLabel position="40,370" size="720,14" backgroundColor="{BAR}" zPosition="1"/>
		<widget source="session.CurrentService" render="Progress" position="40,370" size="720,14" foregroundColor="#ffc83d" backgroundColor="{BAR}" zPosition="2">
			<convert type="ServicePosition">Gauge</convert>
		</widget>
		<widget source="session.CurrentService" render="Label" position="40,396" size="350,64" font="NGLcd;44" foregroundColor="{DIM}" halign="left" valign="center" noWrap="1">
			<convert type="ServicePosition">Position,ShowHours</convert>
		</widget>
		<widget source="session.CurrentService" render="Label" position="410,396" size="350,64" font="NGLcd;44" foregroundColor="#ffffff" halign="right" valign="center" noWrap="1">
			<convert type="ServicePosition">Remaining,Negate,ShowHours</convert>
		</widget>'''))
out.append(screen("StandbySummary", f'''		<widget source="global.CurrentTime" render="Label" position="40,60" size="720,200" font="NGLcd;180" foregroundColor="#c8ced6" halign="center" valign="center" noWrap="1">
			<convert type="ClockToText">Format:%H:%M</convert>
		</widget>
		<widget source="global.CurrentTime" render="Label" position="40,290" size="720,60" font="NGLcdLight;46" foregroundColor="{GOLD}" halign="center" valign="center" noWrap="1">
			<convert type="ClockToText">Format:%A %d %B</convert>
		</widget>
		<widget source="global.CurrentTime" render="Label" position="40,356" size="720,52" font="NGLcdLight;38" foregroundColor="{DIM}" halign="center" valign="center" noWrap="1">
			<convert type="NGHijri"/>
		</widget>
		<widget source="session.RecordState" render="FixedLabel" text="REC" position="40,416" size="720,52" font="NGLcd;40" foregroundColor="#ff4040" halign="center" valign="center">
			<convert type="ConditionalShowHide"/>
		</widget>'''))
out.append('</skin>\n')
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(out))
print("lcd skin written")
