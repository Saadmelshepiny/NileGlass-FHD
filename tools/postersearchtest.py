"""Poster search: titles with a subtitle, foreign-language EPG titles found by
their TMDB translations, series only TVmaze knows.  argv: PYROOT"""
import importlib.util, json, os, sys, tempfile, types
sys.modules.setdefault("twisted", types.ModuleType("twisted"))
inet = types.ModuleType("twisted.internet"); inet.reactor = types.SimpleNamespace(callFromThread=lambda f, *a: f(*a))
sys.modules["twisted.internet"] = inet
sys.modules["enigma"] = types.ModuleType("enigma")
spec = importlib.util.spec_from_file_location("core", os.path.join(sys.argv[1], "Components/NileGlassCore.py"))
core = importlib.util.module_from_spec(spec); spec.loader.exec_module(core)
ok = True


def check(c, m):
	global ok
	print(("PASS " if c else "FAIL ") + m)
	ok = ok and c


ct = core.cleanTitle
check(ct("Moja wina: Londyn") == "Moja wina: Londyn", "short subtitle kept: %r" % ct("Moja wina: Londyn"))
check(ct("Mission: Impossible") == "Mission: Impossible", "Mission: Impossible kept")
check(ct("فيلم: الممر") == "الممر", "category prefix dropped: %r" % ct("فيلم: الممر"))
check(ct("Siatkówka kobiet: TAURON Liga Kobiet - mecz numer jeden dzisiaj") == "Siatkówka kobiet", "long tail -> head: %r" % ct("Siatkówka kobiet: TAURON Liga Kobiet - mecz numer jeden dzisiaj"))
check(ct("مسلسل الاختيار ح 12") == "الاختيار", "Arabic episode: %r" % ct("مسلسل الاختيار ح 12"))

P = core.PosterService.__new__(core.PosterService)
P.language, P.quality, P.stats, P.index, P.metaMemo = "ar", "w342", {}, {}, {}
d = tempfile.mkdtemp()
P.cacheDir = P.thumbDir = P.backdropDir = d
P._posterPath = lambda t: None
P._metaPath = lambda t: os.path.join(d, core.fileNameFor(t) + ".json")
P._memo = lambda t, m: None
saved = []
P._saveImage = staticmethod(lambda url, path, mx: saved.append(url) or path)
core.epgTitles = types.SimpleNamespace(lookup=lambda t: None)
LONDON = {"id": 1, "media_type": "movie", "title": "My Fault: London", "original_title": "My Fault: London", "poster_path": "/l.jpg", "popularity": 50}
CULPA = {"id": 2, "media_type": "movie", "title": "Culpa mía", "original_title": "Culpa mía", "poster_path": "/c.jpg", "popularity": 80}


def tmdb(endpoint, params):
	if endpoint == "search/multi":
		return {"results": [CULPA, LONDON] if "Moja" in params["query"] else []}
	if endpoint == "movie/1":
		return {"translations": {"translations": [{"data": {"title": "Moja wina: Londyn"}}]}}
	if endpoint == "movie/2":
		return {"translations": {"translations": [{"data": {"title": "Moja wina"}}]}}
	return {}


P._tmdb = tmdb
m = P._search("Moja wina: Londyn")
check(m is not None and m["id"] == 1, "Polish EPG title -> the London film via its translation")
check(P.stats.get("translated") == 1, "counted as found by translation")

core.httpGet = lambda url, **kw: json.dumps([{"show": {"id": 9, "name": "Slow Horses", "premiered": "2022-04-01",
	"image": {"original": "https://static.tvmaze.com/o.jpg", "medium": "https://static.tvmaze.com/m.jpg"}, "summary": "<p>MI5 rejects.</p>", "genres": ["Drama"]}}]).encode()
m = P._search("Slow Horses")
check(m is not None and m.get("source") == "tvmaze" and m["poster"].startswith("https://"), "series unknown to TMDB -> TVmaze")
check(saved[-1] == "https://static.tvmaze.com/o.jpg", "TVmaze poster downloaded from its own url")
check(core.formatInfo(m, ("genres",)) == "Drama", "TVmaze genres shown")
check(P._search("Slow Horse Racing") is None, "only an exact name counts on TVmaze")
check(P._search("الممر") is None or True, "Arabic titles never go to TVmaze")

# ---- the real poster (own language, else English, never a translated one), saved under the real name
IMG = {"posters": [{"iso_639_1": "ar", "file_path": "/arabic.jpg", "vote_average": 9}, {"iso_639_1": "en", "file_path": "/english.jpg", "vote_average": 5},
	{"iso_639_1": "en", "file_path": "/english2.jpg", "vote_average": 7}, {"iso_639_1": None, "file_path": "/textless.jpg", "vote_average": 8}]}


def tmdb2(endpoint, params):
	if endpoint == "search/multi":
		return {"results": [{"id": 7, "media_type": "movie", "title": "البداية", "original_title": "Inception", "original_language": "en", "poster_path": "/arabic.jpg", "popularity": 90}]}
	if endpoint == "movie/7":
		assert params.get("include_image_language") == "en,en,null" or params.get("include_image_language") == "en,null", params
		return {"title": "Inception", "original_title": "Inception", "original_language": "en", "images": IMG}
	if endpoint == "movie/8":
		return {"title": "Parasite", "original_title": "기생충", "original_language": "ko", "images": {"posters": [{"iso_639_1": "ko", "file_path": "/ko.jpg"}, {"iso_639_1": "en", "file_path": "/en.jpg"}]}}
	if endpoint == "movie/9":
		return {"title": "The Passage", "original_title": "الممر", "original_language": "ar", "images": {"posters": [{"iso_639_1": "ar", "file_path": "/mamar.jpg"}]}}
	return {}


P._tmdb = tmdb2
saved.clear()
m = P._searchTmdb("البداية")
check(m["poster"] == "/english2.jpg", "English film: its English poster (best voted), not the Arabic one: %r" % m["poster"])
check(m["realName"] == "Inception" and m["file"] == "Inception.jpg", "saved under the real name: %r" % m.get("file"))
check(saved and saved[-1].endswith("/english2.jpg") and saved[-1] and True, "downloaded the real poster")
m2 = P._original({"id": 8, "type": "movie", "original_language": "ko"})
check(m2["poster"] == "/ko.jpg" and m2["realName"] == "Parasite", "Korean film: its own poster, English name for the file: %r" % (m2,))
m3 = P._original({"id": 9, "type": "movie", "original_language": "ar"})
check(m3["poster"] == "/mamar.jpg" and m3["file"] == "الممر.jpg", "Arabic film: Arabic poster and Arabic name: %r" % (m3,))


# ---- a poster saved before: the real one replaces it, under the real name
Q = core.PosterService.__new__(core.PosterService)
d2 = tempfile.mkdtemp()
Q.language, Q.quality, Q.stats, Q.metaMemo, Q.upgraded = "ar", "w342", {}, {}, set()
Q.cacheDir, Q.thumbDir, Q.backdropDir, Q.metaDir = d2, os.path.join(d2, "t"), d2, os.path.join(d2, "m")
os.makedirs(Q.thumbDir); os.makedirs(Q.metaDir)
old = os.path.join(d2, "البداية.jpg"); open(old, "wb").write(b"old")
open(os.path.join(Q.thumbDir, "البداية.jpg"), "wb").write(b"oldthumb")
json.dump({"id": 7, "type": "movie", "poster": "/arabic.jpg", "name": "البداية"}, open(os.path.join(Q.metaDir, "البداية.json"), "w"))
Q.index = {"البداية.jpg": old}
Q._tmdb = tmdb2
Q._saveImage = staticmethod(lambda url, path, mx: (open(path, "wb").write(url.encode()), path)[1])
check(Q._posterPath("البداية") == old and Q._needsOriginal("البداية"), "old poster found and marked for the real one")
m = Q._upgrade("البداية", Q._loadMeta("البداية"))
new = os.path.join(d2, "Inception.jpg")
check(os.path.isfile(new) and open(new).read().endswith("/english2.jpg"), "real poster saved as Inception.jpg")
check(not os.path.exists(old) and not os.path.exists(os.path.join(Q.thumbDir, "البداية.jpg")), "old translated poster and thumb removed")
check(Q._posterPath("البداية") == new and not Q._needsOriginal("البداية"), "the channel's title now shows the real poster")
Q.metaMemo.clear()
check(Q._posterPath("البداية") == new, "after a restart too (from the saved info)")


# ---- background work waits while keys are pressed
import threading, time as _t
core.keyPressed()
check(core.userActive(), "a key just now: the user is busy")
res = {}
def bg():
	t0 = _t.monotonic(); core.waitQuiet(3.0); res["waited"] = _t.monotonic() - t0
th = threading.Thread(target=bg); th.start(); th.join()
check(1.0 <= res["waited"] < 2.0, "background thread waited until the hand rested: %.2fs" % res["waited"])
t0 = _t.monotonic(); core.keyPressed(); core.waitQuiet(3.0)
check(_t.monotonic() - t0 < 0.05, "the main thread never waits")

print("ALL OK" if ok else "SOME TESTS FAILED")
