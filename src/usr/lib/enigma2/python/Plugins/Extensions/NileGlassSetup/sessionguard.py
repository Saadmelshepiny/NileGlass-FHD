# -*- coding: utf-8 -*-
# NileGlass FHD - never let a stray "close" take the main screen with it.
#
# enigma2's Session.close(screen) closes the dialog that is on TOP, whatever
# screen asked (the check for that is an assert, which the image runs without).
# So when a screen that is no longer on top still answers a key - a screen
# left behind by a plugin, or a key that a plugin delivers late - its EXIT
# closes the wrong dialog; when that is the InfoBar the box crashes:
#     runNextScreen  screensToRun[0][1]  IndexError: list index out of range
# Here a close from a screen that is not on top does not touch the top one:
#   - a screen lower in the stack closes as soon as it is on top again
#     (exactly what enigma2 does when close() is called on such a screen);
#   - a screen that is in no stack at all is hidden and its keys switched off.
# Every such case is written to /tmp/nileglass_perf.log ("guard ...").

LOG = "/tmp/nileglass_perf.log"


def _name(screen):
	try:
		from .perfwatch import screenName
		return screenName(screen)
	except Exception:
		return screen.__class__.__name__


def _log(text):
	print("[NileGlass] guard:", text)
	try:
		from .perfwatch import write
		write("guard %s" % text)
	except Exception:
		pass


def guardedClose(original):
	def close(self, screen, *retval):
		current = self.current_dialog
		if screen is current or current is None or not self.in_exec:
			return original(self, screen, *retval)
		try:
			inStack = any(s is screen for s, _shown in self.dialog_stack)
			_log("%s %s %s" % ("later" if inStack else "stray", _name(screen), _name(current)))
			if inStack:
				screen.execing = False
				screen.close_on_next_exec = retval
			elif getattr(screen, "instance", None) is not None:
				if screen.execing:
					screen.execEnd()        # its key maps stop answering
				screen.hide()
		except Exception as err:
			print("[NileGlass] guard:", err)
	close._ngGuard = True
	return close


def install(session):
	cls = type(session)
	if getattr(cls.close, "_ngGuard", False):
		return
	cls.close = guardedClose(cls.close)
