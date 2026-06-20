#!/usr/bin/env python3
"""
เทสต์ Phase 2/3: dl_direct (ไฟล์ตรง/SC) + gatebot (Playwright state-machine) + quality
ทั้งหมด offline — inject session/page ปลอม ไม่ต่อเน็ต ไม่เปิด browser จริง
รัน:  python3 tests/test_downloader.py   หรือ  pytest tests/test_downloader.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scfinder.dl_direct import DirectDownloader, sanitize, _ext_from
from scfinder.gatebot import GateBot
from scfinder.gate_rules import GateRules
from scfinder.quality import passes, bitrate_kbps


# ---------- quality ----------
def test_quality_lossless_and_unknown():
    with tempfile.TemporaryDirectory() as d:
        wav = os.path.join(d, "a.wav")
        open(wav, "wb").write(b"RIFF....")
        assert bitrate_kbps(wav) == 9999, "lossless ถือว่าเกินเกณฑ์"
        ok, br = passes(wav, 320)
        assert ok
        # ไฟล์ที่อ่าน bitrate ไม่ได้ (ไม่มี mutagen/ไม่ใช่เสียงจริง) -> ไม่ reject
        mp3 = os.path.join(d, "b.mp3")
        open(mp3, "wb").write(b"\x00\x01\x02")
        ok2, br2 = passes(mp3, 320)
        assert ok2 and br2 < 0, (ok2, br2)


# ---------- sanitize / ext ----------
def test_sanitize_and_ext():
    assert sanitize("a/b:c*?<>|d") == "a b c d"
    assert sanitize("เพลง 🎵 edit") == "เพลง 🎵 edit"
    assert _ext_from("audio/mpeg", "x") == ".mp3"
    assert _ext_from("", "https://h/song.WAV?x=1") == ".wav"


# ---------- fake HTTP ----------
class FakeResp:
    def __init__(self, status=200, headers=None, body=b"AUDIODATA", js=None):
        self.status_code = status
        self.headers = headers or {}
        self._body = body
        self._js = js

    def json(self):
        return self._js

    def iter_content(self, n):
        yield self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeSession:
    def __init__(self, mapping):
        self.mapping = mapping

    def get(self, url, **kw):
        for key, resp in self.mapping.items():
            if key in url:
                return resp
        return FakeResp(404)


class FakeClient:
    client_id = "FAKECLIENTID"


def test_direct_sc_download():
    with tempfile.TemporaryDirectory() as d:
        sess = FakeSession({
            "/download": FakeResp(200, js={"redirectUri": "https://files.example/song.mp3"}),
            "song.mp3": FakeResp(200, headers={"Content-Type": "audio/mpeg"}, body=b"X" * 100),
        })
        dl = DirectDownloader(client=FakeClient(), session=sess, min_bitrate=320)
        rec = {"track_id": 1, "artist": "dj", "title": "edit", "route": "direct_sc"}
        res = dl.download(rec, d)
        assert res.ok, res.reason
        assert os.path.exists(res.path) and res.path.endswith(".mp3")


def test_direct_file_html_rejected():
    with tempfile.TemporaryDirectory() as d:
        sess = FakeSession({"landing": FakeResp(200, headers={"Content-Type": "text/html"})})
        dl = DirectDownloader(session=sess)
        rec = {"track_id": 2, "artist": "dj", "title": "x", "route": "direct_file",
               "target_url": "https://mediafire.com/landing/page"}
        res = dl.download(rec, d)
        assert not res.ok and "HTML" in res.reason, res


def test_direct_sc_no_redirect():
    with tempfile.TemporaryDirectory() as d:
        sess = FakeSession({"/download": FakeResp(200, js={})})
        dl = DirectDownloader(client=FakeClient(), session=sess)
        rec = {"track_id": 3, "artist": "dj", "title": "x", "route": "direct_sc"}
        res = dl.download(rec, d)
        assert not res.ok and "redirectUri" in res.reason


# ---------- gatebot (fake page) ----------
class FakePage:
    def __init__(self, dest, succeed=True, title="Hypeddit | Free Download"):
        self.dest = dest
        self.succeed = succeed
        self.actions = []
        self._title = title

    def wait(self, s):
        self.actions.append(("wait", s))

    def click_text(self, t):
        self.actions.append(("click_text", t))

    def click(self, sel):
        self.actions.append(("click", sel))

    def fill(self, sel, v):
        self.actions.append(("fill", sel, v))

    def social(self, kind):
        self.actions.append(("social", kind))

    def expect_download(self, timeout):
        self.actions.append(("expect_download", timeout))
        if not self.succeed:
            return None
        path = os.path.join(self.dest, "gate-song.wav")   # wav -> ผ่าน bitrate เสมอ
        open(path, "wb").write(b"RIFFDATA")
        return path

    def signature(self):
        return self._title

    def screenshot(self, path):
        open(path, "wb").write(b"PNG")

    def close(self):
        self.actions.append(("close",))


def _rules():
    with tempfile.TemporaryDirectory() as d:
        return GateRules(os.path.join(d, "gate_rules.json"))   # ใช้ DEFAULT_RULES


def test_gatebot_success():
    rules = _rules()
    with tempfile.TemporaryDirectory() as d:
        bot = GateBot(rules, d, min_bitrate=320, social_unlock=False)
        page = FakePage(d, succeed=True)
        rec = {"track_id": 1, "artist": "dj", "title": "edit",
               "route": "gate", "target_url": "https://hypeddit.com/a/b"}
        res = bot.download(rec, page=page)
        assert res.ok, res.reason
        assert ("expect_download", 60) in page.actions
        # social_unlock=False -> ต้องไม่กด social
        assert not any(a[0] == "social" for a in page.actions)


def test_gatebot_social_unlock():
    rules = _rules()
    with tempfile.TemporaryDirectory() as d:
        bot = GateBot(rules, d, min_bitrate=320, social_unlock=True)
        page = FakePage(d, succeed=True)
        rec = {"track_id": 1, "route": "gate", "target_url": "https://hypeddit.com/a/b"}
        bot.download(rec, page=page)
        kinds = [a[1] for a in page.actions if a[0] == "social"]
        assert kinds == ["follow", "like", "repost"], kinds


def test_gatebot_no_rule():
    rules = _rules()
    with tempfile.TemporaryDirectory() as d:
        bot = GateBot(rules, d)
        page = FakePage(d)
        rec = {"track_id": 9, "route": "gate", "target_url": "https://unknown-gate.zz/x"}
        res = bot.download(rec, page=page)
        assert not res.ok and "rule" in res.reason
        assert res.screenshot and os.path.exists(res.screenshot)


def test_gatebot_fail_captures_screenshot():
    rules = _rules()
    with tempfile.TemporaryDirectory() as d:
        bot = GateBot(rules, d)
        page = FakePage(d, succeed=False)
        rec = {"track_id": 5, "route": "gate", "target_url": "https://hypeddit.com/a/b"}
        res = bot.download(rec, page=page)
        assert not res.ok and "ไม่ได้ไฟล์" in res.reason
        assert os.path.exists(res.screenshot)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = True
    for fn in fns:
        try:
            fn()
            print(f"  \033[32mPASS\033[0m {fn.__name__}")
        except AssertionError as e:
            ok = False
            print(f"  \033[31mFAIL\033[0m {fn.__name__}: {e}")
    sys.exit(0 if ok else 1)
