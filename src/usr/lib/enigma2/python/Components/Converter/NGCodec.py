# -*- coding: utf-8 -*-
# NileGlass FHD - picture and sound format of the playing service.
#
#   <convert type="NGCodec">Resolution</convert>  ->  "1080p50"  /  "576i25"
#   <convert type="NGCodec">Codecs</convert>      ->  "HEVC · AAC"
#   <convert type="NGCodec">Full</convert>        ->  "1080p50 · HEVC · AAC"
#   <convert type="NGCodec">Video</convert> / Audio / Fps
# Everything comes from the service itself (no polling of its own beyond
# the service events); unknown parts are simply left out.

from enigma import iPlayableService, iServiceInformation

from Components.Converter.Converter import Converter
from Components.Element import cached

# iServiceInformation.sVideoType (stream type as enigma2 reports it)
VIDEO = {
	0: "MPEG-2", 1: "H.264", 2: "H.263", 3: "VC-1", 4: "MPEG-4", 5: "VC-1",
	6: "MPEG-1", 7: "HEVC", 8: "VP8", 9: "VP9", 10: "XviD", 13: "DivX",
	14: "DivX", 15: "DivX", 16: "AVS", 18: "VP6", 40: "AVS2",
}

# audio track descriptions -> short label (first match wins)
AUDIO = (
	("ATMOS", "Atmos"), ("TRUEHD", "TrueHD"), ("AC-4", "AC4"), ("AC4", "AC4"),
	("DIGITAL +", "DD+"), ("DIGITAL PLUS", "DD+"), ("EAC3", "DD+"), ("E-AC3", "DD+"), ("AC3+", "DD+"),
	("DTS", "DTS"), ("DOLBY", "AC3"), ("AC3", "AC3"), ("AC-3", "AC3"),
	("HE-AAC", "HE-AAC"), ("HEAAC", "HE-AAC"), ("AAC", "AAC"),
	("MPEG", "MPEG"), ("MP2", "MPEG"), ("MP3", "MP3"), ("LPCM", "PCM"), ("PCM", "PCM"),
	("FLAC", "FLAC"), ("OPUS", "Opus"), ("VORBIS", "Vorbis"), ("WMA", "WMA"),
)

SEP = " · "
EVENTS = tuple(getattr(iPlayableService, n) for n in (
	"evStart", "evUpdatedInfo", "evVideoSizeChanged", "evVideoFramerateChanged",
	"evVideoProgressiveChanged", "evEnd") if hasattr(iPlayableService, n))


def _int(info, what):
	if what is None:
		return -1
	try:
		v = info.getInfo(what)
		return v if isinstance(v, int) else -1
	except Exception:
		return -1


def videoCodec(info):
	return VIDEO.get(_int(info, getattr(iServiceInformation, "sVideoType", None)), "")


def resolution(info):
	h = _int(info, getattr(iServiceInformation, "sVideoHeight", None))
	if h <= 0:
		return ""
	if h >= 2000:
		label = "2160"
	elif h >= 1000:
		label = "1080"
	elif h >= 700:
		label = "720"
	elif h >= 560:
		label = "576"
	elif h >= 470:
		label = "480"
	else:
		label = str(h)
	prog = _int(info, getattr(iServiceInformation, "sProgressive", None))
	label += "i" if prog == 0 else "p"
	fps = fpsValue(info)
	return label + (str(fps) if fps else "")


def fpsValue(info):
	r = _int(info, getattr(iServiceInformation, "sFrameRate", None))
	if r <= 0:
		return 0
	return int(round(r / 1000.0)) if r > 1000 else r


def audioCodec(service):
	try:
		audio = service.audioTracks()
		if not audio:
			return ""
		n = audio.getNumberOfTracks()
		cur = audio.getCurrentTrack()
		if n <= 0 or cur < 0 or cur >= n:
			return ""
		desc = (audio.getTrackInfo(cur).getDescription() or "").upper()
	except Exception:
		return ""
	for key, label in AUDIO:
		if key in desc:
			return label
	return desc.split(" ")[0][:8].title() if desc else ""


class NGCodec(Converter):
	def __init__(self, arg):
		Converter.__init__(self, arg)
		self.mode = (arg or "Full").strip()

	@cached
	def getText(self):
		service = self.source.service
		info = service and service.info()
		if not info:
			return ""
		try:
			m = self.mode
			if m == "Resolution":
				return resolution(info)
			if m == "Video":
				return videoCodec(info)
			if m == "Audio":
				return audioCodec(service)
			if m == "Fps":
				fps = fpsValue(info)
				return "%d fps" % fps if fps else ""
			parts = [videoCodec(info), audioCodec(service)]
			if m == "Full":
				parts.insert(0, resolution(info))
			return SEP.join(p for p in parts if p)
		except Exception:
			return ""

	text = property(getText)

	def changed(self, what):
		if what[0] != self.CHANGED_SPECIFIC or what[1] in EVENTS:
			Converter.changed(self, what)
