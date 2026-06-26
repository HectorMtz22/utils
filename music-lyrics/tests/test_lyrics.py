import lyrics_on_nas


# ---------------------------------------------------------------------------
# is_synced
# ---------------------------------------------------------------------------

def test_is_synced_true_on_timestamped():
    assert lyrics_on_nas.is_synced("[00:12.34] hola") is True


def test_is_synced_false_on_plain():
    assert lyrics_on_nas.is_synced("just some plain lyrics\nno timestamps") is False


def test_is_synced_false_on_empty():
    assert lyrics_on_nas.is_synced("") is False


def test_is_synced_false_on_none():
    assert lyrics_on_nas.is_synced(None) is False


# ---------------------------------------------------------------------------
# fetch_netease
# ---------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def _make_netease_get(search_payload, lyric_payload,
                      search_status=200, lyric_status=200):
    def fake_get(url, params=None, headers=None, timeout=None):
        if "search" in url:
            return FakeResponse(search_status, search_payload)
        if "lyric" in url:
            return FakeResponse(lyric_status, lyric_payload)
        raise AssertionError(f"unexpected url: {url}")
    return fake_get


def test_fetch_netease_returns_synced(monkeypatch):
    search = {"result": {"songs": [{"id": 42}]}}
    lyric = {"lrc": {"lyric": "[00:01.00] línea sincronizada"}}
    monkeypatch.setattr(lyrics_on_nas.requests, "get",
                        _make_netease_get(search, lyric))
    synced, plain = lyrics_on_nas.fetch_netease("Artist", "Title")
    assert synced == "[00:01.00] línea sincronizada"
    assert plain is None


def test_fetch_netease_returns_plain(monkeypatch):
    search = {"result": {"songs": [{"id": 42}]}}
    lyric = {"lrc": {"lyric": "letra sin marcas de tiempo"}}
    monkeypatch.setattr(lyrics_on_nas.requests, "get",
                        _make_netease_get(search, lyric))
    synced, plain = lyrics_on_nas.fetch_netease("Artist", "Title")
    assert synced is None
    assert plain == "letra sin marcas de tiempo"


def test_fetch_netease_no_songs(monkeypatch):
    search = {"result": {"songs": []}}
    lyric = {"lrc": {"lyric": "[00:01.00] never reached"}}
    monkeypatch.setattr(lyrics_on_nas.requests, "get",
                        _make_netease_get(search, lyric))
    assert lyrics_on_nas.fetch_netease("Artist", "Title") == (None, None)


def test_fetch_netease_request_error(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network down")
    monkeypatch.setattr(lyrics_on_nas.requests, "get", boom)
    assert lyrics_on_nas.fetch_netease("Artist", "Title") == (None, None)


# ---------------------------------------------------------------------------
# resolve_synced selection
# ---------------------------------------------------------------------------

def test_resolve_synced_lrclib_synced_skips_netease(monkeypatch):
    monkeypatch.setattr(lyrics_on_nas, "fetch_lrclib",
                        lambda a, t: ("[00:01.00] desde lrclib", None))

    def must_not_call(a, t):
        raise AssertionError("fetch_netease should not be called")
    monkeypatch.setattr(lyrics_on_nas, "fetch_netease", must_not_call)

    assert lyrics_on_nas.resolve_synced("A", "T") == ("[00:01.00] desde lrclib", "lrclib")


def test_resolve_synced_lrclib_plain_then_netease(monkeypatch, capsys):
    monkeypatch.setattr(lyrics_on_nas, "fetch_lrclib",
                        lambda a, t: (None, "plana lrclib"))
    monkeypatch.setattr(lyrics_on_nas, "fetch_netease",
                        lambda a, t: ("[00:02.00] desde netease", None))

    synced, source = lyrics_on_nas.resolve_synced("A", "T")
    assert synced == "[00:02.00] desde netease"
    assert source == "NetEase"
    out = capsys.readouterr().out
    assert "⚠ Solo letra plana en lrclib" in out


def test_resolve_synced_both_plain(monkeypatch, capsys):
    monkeypatch.setattr(lyrics_on_nas, "fetch_lrclib",
                        lambda a, t: (None, "plana lrclib"))
    monkeypatch.setattr(lyrics_on_nas, "fetch_netease",
                        lambda a, t: (None, "plana netease"))

    assert lyrics_on_nas.resolve_synced("A", "T") == (None, None)
    out = capsys.readouterr().out
    assert "⚠ Solo letra plana en lrclib" in out
    assert "⚠ Solo letra plana en NetEase" in out


def test_resolve_synced_nothing(monkeypatch, capsys):
    monkeypatch.setattr(lyrics_on_nas, "fetch_lrclib", lambda a, t: (None, None))
    monkeypatch.setattr(lyrics_on_nas, "fetch_netease", lambda a, t: (None, None))

    assert lyrics_on_nas.resolve_synced("A", "T") == (None, None)
    out = capsys.readouterr().out
    assert "⚠" not in out


# ---------------------------------------------------------------------------
# fetch_lrclib
# ---------------------------------------------------------------------------

def _make_lrclib_get(payload, status=200):
    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResponse(status, payload)
    return fake_get


def test_fetch_lrclib_returns_synced_and_plain(monkeypatch):
    payload = {"syncedLyrics": "[00:01.00] sync", "plainLyrics": "plain"}
    monkeypatch.setattr(lyrics_on_nas.requests, "get", _make_lrclib_get(payload))
    assert lyrics_on_nas.fetch_lrclib("A", "T") == ("[00:01.00] sync", "plain")


def test_fetch_lrclib_plain_only(monkeypatch):
    payload = {"syncedLyrics": None, "plainLyrics": "plain"}
    monkeypatch.setattr(lyrics_on_nas.requests, "get", _make_lrclib_get(payload))
    assert lyrics_on_nas.fetch_lrclib("A", "T") == (None, "plain")


def test_fetch_lrclib_non_200(monkeypatch):
    monkeypatch.setattr(lyrics_on_nas.requests, "get",
                        _make_lrclib_get({"syncedLyrics": "[00:01.00] x"}, status=404))
    assert lyrics_on_nas.fetch_lrclib("A", "T") == (None, None)


def test_fetch_lrclib_request_error(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network down")
    monkeypatch.setattr(lyrics_on_nas.requests, "get", boom)
    assert lyrics_on_nas.fetch_lrclib("A", "T") == (None, None)


# ---------------------------------------------------------------------------
# fetch_netease — error / empty branches
# ---------------------------------------------------------------------------

def test_fetch_netease_search_non_200(monkeypatch):
    monkeypatch.setattr(lyrics_on_nas.requests, "get",
                        _make_netease_get({}, {}, search_status=500))
    assert lyrics_on_nas.fetch_netease("A", "T") == (None, None)


def test_fetch_netease_lyric_non_200(monkeypatch):
    search = {"result": {"songs": [{"id": 42}]}}
    monkeypatch.setattr(lyrics_on_nas.requests, "get",
                        _make_netease_get(search, {}, lyric_status=404))
    assert lyrics_on_nas.fetch_netease("A", "T") == (None, None)


def test_fetch_netease_empty_body(monkeypatch):
    search = {"result": {"songs": [{"id": 42}]}}
    lyric = {"lrc": {"lyric": "   "}}
    monkeypatch.setattr(lyrics_on_nas.requests, "get",
                        _make_netease_get(search, lyric))
    assert lyrics_on_nas.fetch_netease("A", "T") == (None, None)


# ---------------------------------------------------------------------------
# is_placeholder_lyric — NetEase instrumental / metadata-only filtering
# ---------------------------------------------------------------------------

def test_is_placeholder_instrumental():
    assert lyrics_on_nas.is_placeholder_lyric("[99:00.00]纯音乐，请欣赏") is True


def test_is_placeholder_timestamps_only():
    assert lyrics_on_nas.is_placeholder_lyric("[00:00.00]\n[00:01.00]") is True


def test_is_placeholder_false_on_real_lyrics():
    assert lyrics_on_nas.is_placeholder_lyric("[00:01.00] hola mundo") is False


def test_fetch_netease_skips_instrumental(monkeypatch):
    search = {"result": {"songs": [{"id": 42}]}}
    lyric = {"lrc": {"lyric": "[99:00.00]纯音乐，请欣赏"}}
    monkeypatch.setattr(lyrics_on_nas.requests, "get",
                        _make_netease_get(search, lyric))
    assert lyrics_on_nas.fetch_netease("A", "T") == (None, None)
