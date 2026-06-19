#!/usr/bin/env python3
"""
เทสต์ storage layer (Supabase) แบบ offline — inject getter/poster ปลอม
รัน:  python3 tests/test_storage.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scfinder.storage import SupabaseStorage, make_storage
from scfinder.config import Config
from scfinder.store import SeenStore
from scfinder.feedback import FeedbackStore

_ok = True


def check(cond, msg):
    global _ok
    print(("  \033[32mPASS\033[0m " if cond else "  \033[31mFAIL\033[0m ") + msg)
    _ok = _ok and cond


class Resp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def json(self):
        return self._p


class FakeGet:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status
        self.url = None

    def __call__(self, url, headers=None, timeout=None):
        self.url = url
        self.headers = headers
        return Resp(self.payload, self.status)


class FakePost:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return Resp([], 201)


def test_factory():
    check(make_storage(Config()) is None, "ไม่มี supabase env -> None (ใช้ไฟล์ local)")
    s = make_storage(Config(supabase_url="https://x.supabase.co", supabase_key="k"))
    check(isinstance(s, SupabaseStorage), "มี url+key -> สร้าง SupabaseStorage")


def test_headers_and_load():
    g = FakeGet([{"track_id": 10}, {"track_id": 20}])
    st = SupabaseStorage("https://x.supabase.co", "KEY", getter=g)
    seen = st.load_seen()
    check(seen == {10, 20}, "load_seen แปลง rows -> set ถูก")
    check(g.url.endswith("/rest/v1/seen?select=track_id"), "ยิง endpoint seen ถูก")
    check(g.headers["apikey"] == "KEY" and g.headers["Authorization"] == "Bearer KEY",
          "ใส่ apikey + Bearer header")


def test_save_upsert():
    p = FakePost()
    st = SupabaseStorage("https://x.supabase.co", "K", poster=p)
    st.save_seen({5, 7})
    call = p.calls[-1]
    check(call["url"].endswith("/rest/v1/seen"), "save_seen POST ไป /seen")
    check(call["headers"]["Prefer"] == "resolution=merge-duplicates", "ใช้ upsert (merge-duplicates)")
    check({r["track_id"] for r in call["json"]} == {5, 7}, "ส่ง track_id ครบ")


def test_feedback_roundtrip():
    g = FakeGet([{"track_id": 1, "liked": True, "title": "t",
                  "features": {"genre": "edit"}, "updated_at": "now"}])
    p = FakePost()
    st = SupabaseStorage("https://x.supabase.co", "K", getter=g, poster=p)
    recs = st.load_feedback()
    check(recs[0]["track_id"] == 1 and recs[0]["features"]["genre"] == "edit",
          "load_feedback คืน record ครบ")
    st.save_feedback(recs)
    check(p.calls[-1]["url"].endswith("/rest/v1/feedback"), "save_feedback POST ไป /feedback")


def test_stores_use_storage():
    g = FakeGet([{"track_id": 99}])
    p = FakePost()
    st = SupabaseStorage("https://x.supabase.co", "K", getter=g, poster=p)
    seen = SeenStore("ignored.json", enabled=True, storage=st)
    check(seen.is_seen(99), "SeenStore โหลด seen จาก Supabase (ไม่แตะไฟล์)")
    seen.add_many([1, 2]); seen.save()
    check(any(c["url"].endswith("/seen") for c in p.calls), "SeenStore.save ยิง Supabase")

    g2 = FakeGet([])
    fb = FeedbackStore("ignored.json", storage=SupabaseStorage("https://x.supabase.co", "K", getter=g2, poster=p))
    fb.record({"track_id": 3, "title": "x", "genre": "edit", "camelot": "8A", "bpm": 124}, True)
    fb.save()
    check(any(c["url"].endswith("/feedback") for c in p.calls), "FeedbackStore.save ยิง Supabase")


def test_resilient_on_error():
    def boom(*a, **k):
        raise RuntimeError("network down")
    st = SupabaseStorage("https://x.supabase.co", "K", getter=boom, poster=boom)
    check(st.load_seen() == set(), "load ล้มเหลว -> คืน set ว่าง (ไม่ crash)")
    check(st.save_seen({1}) is False, "save ล้มเหลว -> คืน False (ไม่ throw)")


if __name__ == "__main__":
    print(">> storage (Supabase) tests\n")
    test_factory()
    test_headers_and_load()
    test_save_upsert()
    test_feedback_roundtrip()
    test_stores_use_storage()
    test_resilient_on_error()
    print()
    if _ok:
        print("\033[32m✅ ผ่านทุกข้อ\033[0m"); sys.exit(0)
    print("\033[31m❌ มีข้อไม่ผ่าน\033[0m"); sys.exit(1)
