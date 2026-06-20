#!/usr/bin/env python3
"""
เทสต์ Phase 1: resolver จำแนกเส้นทางโหลด (route)
รัน:  python3 tests/test_resolver.py   หรือ  pytest tests/test_resolver.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scfinder.resolver import classify, enrich, resolve_route


def test_direct_sc():
    route, target = classify({"downloadable": True, "purchase_url": ""})
    assert route == "direct_sc" and target == "", route
    route, _ = classify({"has_downloads_left": True})
    assert route == "direct_sc"


def test_gate_hypeddit():
    route, target = classify({"purchase_url": "https://hypeddit.com/abc/track"})
    assert route == "gate" and "hypeddit" in target, (route, target)


def test_gate_from_description():
    t = {"purchase_url": "", "description": "Free DL here: https://hypeddit.com/xy/zz enjoy"}
    route, target = classify(t)
    assert route == "gate" and target.startswith("https://hypeddit.com"), (route, target)


def test_gate_preferred_over_paid():
    # มีทั้ง bandcamp (paid) ใน purchase + hypeddit ใน desc -> เลือก gate (ของฟรีคุณภาพเต็ม)
    t = {"purchase_url": "https://artist.bandcamp.com/track/x",
         "description": "free download https://hypeddit.com/a/b"}
    route, _ = classify(t)
    assert route == "gate", route


def test_direct_file():
    route, target = classify({"purchase_url": "https://www.mediafire.com/file/x/song.mp3"})
    assert route == "direct_file", (route, target)
    route2, _ = classify({"purchase_url": "https://example.com/track.wav"})
    assert route2 == "direct_file", route2


def test_paid():
    route, _ = classify({"purchase_url": "https://artist.bandcamp.com/track/x"})
    assert route == "paid", route
    route2, _ = classify({"purchase_url": "https://www.beatport.com/track/x/123"})
    assert route2 == "paid", route2


def test_none():
    route, target = classify({"purchase_url": "", "description": "just a normal track"})
    assert route == "none" and target == "", (route, target)


def test_unknown_purchase_is_gate():
    # purchase_url แปลกๆ ที่ไม่รู้จัก -> ลองเปิดด้วย Playwright (gate)
    route, target = classify({"purchase_url": "https://weird-host.xyz/dl/123"})
    assert route == "gate" and target.endswith("/dl/123"), (route, target)


class _FakeClient:
    def __init__(self, full):
        self.full = full
        self.calls = 0

    def resolve_track(self, url):
        self.calls += 1
        return self.full


def test_enrich_refetches():
    # Result dict ไม่มี description/purchase_url -> enrich ไป re-fetch
    rec = {"track_id": 1, "url": "https://soundcloud.com/a/b"}
    client = _FakeClient({"purchase_url": "https://hypeddit.com/a/b", "description": ""})
    out = enrich(rec, client)
    assert client.calls == 1 and out["purchase_url"].startswith("https://hypeddit.com")
    route, _ = resolve_route(rec, client)
    assert route == "gate"


def test_enrich_skips_when_known():
    rec = {"track_id": 1, "purchase_url": "https://hypeddit.com/a/b"}
    client = _FakeClient({"description": "x"})
    enrich(rec, client)
    assert client.calls == 0, "มี purchase_url แล้วไม่ต้อง re-fetch"


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
