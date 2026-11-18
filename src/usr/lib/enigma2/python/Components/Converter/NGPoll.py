# -*- coding: utf-8 -*-
# NileGlass FHD - one clock for all NileGlass converters that read something
# again and again (temperature, signal, ECM, weather, timers ...).
#
# enigma2's Poll gives every converter its own timer: with cards beside the
# screens that was dozens of timers, each waking the box at its own moment.
# Here converters with the same interval share one timer, so their updates
# come together (one drawing pass instead of many) and a converter whose
# widgets are all hidden is not polled at all.  Same interface as Poll:
#   class X(NGPoll, Converter): poll_interval = ms; poll_enabled = True

import weakref

try:
	from enigma import eTimer
except Exception:      # tests
	eTimer = None

_buckets = {}          # interval ms -> [timer, WeakSet of converters]


def _tick(interval):
	b = _buckets.get(interval)
	if not b:
		return
	for conv in list(b[1]):
		try:
			conv.poll()
		except Exception as err:
			print("[NileGlass] poll %s:" % conv.__class__.__name__, err)
	if not b[1] and b[0] is not None:
		b[0].stop()


def _add(conv, interval):
	b = _buckets.get(interval)
	if b is None:
		timer = None
		if eTimer is not None:
			timer = eTimer()
			timer.callback.append(lambda: _tick(interval))
		b = _buckets[interval] = [timer, weakref.WeakSet()]
	was = len(b[1])
	b[1].add(conv)
	if not was and b[0] is not None:
		b[0].start(interval, False)


def _remove(conv, interval):
	b = _buckets.get(interval)
	if b is not None:
		b[1].discard(conv)
		if not b[1] and b[0] is not None:
			b[0].stop()


def stats():
	"""{interval: number of converters polled} - for the speed report"""
	return dict((i, len(b[1])) for i, b in _buckets.items() if len(b[1]))


class NGPoll:
	def __init__(self):
		self._ngIv = 1000
		self._ngOn = False
		self._ngSusp = False
		self._ngIn = None          # the interval it is registered with

	def _ngSync(self):
		want = self._ngIv if (self._ngOn and not self._ngSusp and self._ngIv > 0) else None
		if want != self._ngIn:
			if self._ngIn is not None:
				_remove(self, self._ngIn)
			if want is not None:
				_add(self, want)
			self._ngIn = want

	def _setInterval(self, interval):
		self._ngIv = int(interval)
		self._ngSync()

	def _setEnabled(self, enabled):
		self._ngOn = bool(enabled)
		self._ngSync()

	poll_interval = property(lambda self: self._ngIv, _setInterval)
	poll_enabled = property(lambda self: self._ngOn, _setEnabled)

	def poll(self):
		self.changed((self.CHANGED_POLL,))

	def doSuspend(self, suspended):
		self._ngSusp = bool(suspended)
		if not suspended and self._ngOn:
			self.poll()
		self._ngSync()

	def destroy(self):
		self._ngOn = False
		self._ngSync()
