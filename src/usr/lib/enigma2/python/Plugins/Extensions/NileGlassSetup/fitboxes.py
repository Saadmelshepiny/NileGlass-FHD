# -*- coding: utf-8 -*-
# NileGlass FHD - message and choice boxes sized to what they show.
#
# The image draws every MessageBox / ChoiceBox at the fixed size of the skin
# (OpenBh has the resize code but never calls it), so a one-line notice got a
# big empty window.  Here, once the box is laid out, its text is measured and
# the window takes the size of its content: short notice -> small box, long
# text or many choices -> bigger box (up to a limit, then the list scrolls).
# The positions and margins of the skin are kept; only sizes change.

from enigma import ePoint, eSize, getDesktop

MSG_MIN_W, MSG_MAX_W = 620, 1400      # window width limits
CHOICE_MIN_W, CHOICE_MAX_W = 700, 1400
MAX_ROWS = 10                         # more choices scroll
GAP = 14


def _desk():
	s = getDesktop(0).size()
	return s.width(), s.height()


def _measure(label, maxWidth):
	"""Wrapped text size of a Label at the given width."""
	inst = label.instance
	inst.resize(eSize(maxWidth, 2000))
	size = inst.calculateSize()
	return min(maxWidth, size.width() + 12), size.height() + 8


def _itemHeight(widget, default=60):
	for attrib, value in getattr(widget, "skinAttributes", None) or []:
		if attrib == "itemHeight":
			try:
				return int(value)
			except ValueError:
				pass
	try:
		return widget.instance.getItemHeight() or default
	except Exception:
		return default


def fitMessageBox(box):
	try:
		inst, text = box.instance, box["text"]
		if not inst or not text.instance:
			return
		dw, dh = _desk()
		W0 = inst.size().width()
		tx, ty = text.instance.position().x(), text.instance.position().y()
		right = max(24, W0 - (tx + text.instance.size().width()))
		tw, th = _measure(text, MSG_MAX_W - tx - right) if text.getText() else (0, 0)
		icon = box["icon"].instance if "icon" in box and getattr(box, "picon", True) else None
		iconBottom = (icon.position().y() + icon.size().height()) if icon else 0
		items = len(getattr(box, "list", []) or [])
		lst = box["list"].instance if items else None
		ih = _itemHeight(box["list"]) if items else 0
		rows = min(items, MAX_ROWS)
		listW = 0
		if lst:
			try:
				listW = lst.getMaxItemTextWidth() + 60
			except Exception:
				listW = 400
		W = max(MSG_MIN_W, tx + tw + right, listW + 48)
		W = min(W, MSG_MAX_W)
		text.instance.resize(eSize(W - tx - right, max(th, 1)))
		y = max(ty + th, iconBottom)
		if lst:
			lx = lst.position().x()
			lst.move(ePoint(lx, y + GAP))
			lst.resize(eSize(W - 2 * lx, rows * ih))
			y += GAP + rows * ih
		H = y + 22
		inst.resize(eSize(W, H))
		inst.move(ePoint((dw - W) // 2, (dh - H) // 2))
	except Exception as err:
		print("[NileGlass] fit message box:", err)


def fitChoiceBox(box):
	try:
		inst, lstw = box.instance, box["list"]
		if not inst or not lstw.instance:
			return
		dw, dh = _desk()
		lst = lstw.instance
		lx, ly = lst.position().x(), lst.position().y()
		W0 = inst.size().width()
		H0 = inst.size().height()
		bottomArea = H0 - (ly + lst.size().height())     # separator + description of the skin
		items = len(getattr(box, "list", []) or [])
		ih = _itemHeight(lstw, 58)
		rows = max(1, min(items, MAX_ROWS))
		try:
			listW = lst.getMaxItemTextWidth() + 120
		except Exception:
			listW = W0 - 2 * lx
		text = box["text"] if "text" in box else None
		tw = th = 0
		if text is not None and text.instance and text.getText():
			tx = text.instance.position().x()
			tw, th = _measure(text, CHOICE_MAX_W - 2 * tx)
		W = min(CHOICE_MAX_W, max(CHOICE_MIN_W, listW + 2 * lx, tw + 2 * lx))
		y = ly
		if text is not None and text.instance:
			ty = text.instance.position().y()
			text.instance.resize(eSize(W - 2 * text.instance.position().x(), max(th, 1)))
			y = ty + th + GAP if th else ty
		lst.move(ePoint(lx, y))
		lst.resize(eSize(W - 2 * lx, rows * ih))
		shift = (y + rows * ih) - (ly + lst.size().height())
		# the separator / description under the list follow it
		for name in ("description",):
			if name in box and box[name].instance:
				d = box[name].instance
				d.move(ePoint(d.position().x(), y + rows * ih + 10 + 10))
				d.resize(eSize(W - 2 * d.position().x(), d.size().height()))
		H = y + rows * ih + max(bottomArea, 24)
		inst.resize(eSize(W, H))
		inst.move(ePoint(40, (dh - H) // 2))          # choice lists: left panel like the menus
		return shift
	except Exception as err:
		print("[NileGlass] fit choice box:", err)


def _ours(box, names):
	"""Only boxes drawn with the skin's own MessageBox / ChoiceBox screens
	(a plugin with its own box design is left alone)."""
	sn = getattr(box, "skinName", None) or box.__class__.__name__
	first = sn[0] if isinstance(sn, (list, tuple)) and sn else sn
	return first in names


# enigma2 calls an onLayoutFinish entry directly only when it has the same type
# as the screen's close(); anything else is run with exec(entry, globals,
# locals) where "self" is the screen.  Some plugins replace close() of a box
# with a plain function, and then even a bound method was exec'd -> crash
# (TypeError: exec() arg 1 must be a string ...).  A compiled code object is
# valid for exec in every case, so the fit is started through one.
_RUN = compile("self._ngFitRun()", "<NileGlass fit>", "exec")


class _Fitter:
	def __init__(self, box, fit):
		self.box, self.fit, self.done = box, fit, False

	def run(self):
		if self.done:
			return
		self.done = True
		try:
			self.fit(self.box)
		except Exception as err:
			print("[NileGlass] fit box:", err)

	def attach(self, box):
		box._ngFitRun = self.run
		if isinstance(self.run, type(box.close)):
			box.onLayoutFinish.append(self.run)
		else:
			box.onLayoutFinish.append(_RUN)


def _patch(cls, fit, names):
	if getattr(cls, "_ngFit", False):
		return
	original = cls.__init__

	def __init__(self, *args, **kwargs):
		original(self, *args, **kwargs)
		if _ours(self, names):
			try:
				_Fitter(self, fit).attach(self)
			except Exception as err:
				print("[NileGlass] fit box:", err)
	cls.__init__ = __init__
	cls._ngFit = True


def install():
	try:
		from Screens.MessageBox import MessageBox
		_patch(MessageBox, fitMessageBox, ("MessageBox", "MessageBoxSimple"))
	except Exception as err:
		print("[NileGlass] fit message box install:", err)
	try:
		from Screens.ChoiceBox import ChoiceBox
		_patch(ChoiceBox, fitChoiceBox, ("ChoiceBox",))
	except Exception as err:
		print("[NileGlass] fit choice box install:", err)
