#!/usr/bin/env python3
"""
เทสต์ Phase 1: Crate (คิวโหลด) — enqueue/dedupe/claim/mark/clear/persist
รัน:  python3 tests/test_crate.py   หรือ  pytest tests/test_crate.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scfinder.crate import Crate


def _track(tid, title="T", route_url=""):
    return {"track_id": tid, "title": title, "artist": "dj",
            "url": f"https://soundcloud.com/dj/{tid}"}


def test_add_and_dedupe():
    with tempfile.TemporaryDirectory() as d:
        c = Crate(os.path.join(d, "crate.json"))
        c.add(_track(1), route="gate", target_url="https://hypeddit.com/a")
        c.add(_track(1), route="gate")        # ซ้ำ -> ไม่เพิ่ม
        assert c.counts()["total"] == 1
        assert c.pending()[0]["route"] == "gate"


def test_paid_none_not_pending():
    with tempfile.TemporaryDirectory() as d:
        c = Crate(os.path.join(d, "crate.json"))
        c.add(_track(1), route="paid")
        c.add(_track(2), route="none")
        assert c.pending() == [], "paid/none ไม่ควรอยู่ใน pending"
        assert c.counts()["paid"] == 1 and c.counts()["none"] == 1


def test_claim_locks():
    with tempfile.TemporaryDirectory() as d:
        c = Crate(os.path.join(d, "crate.json"))
        c.add(_track(1), route="gate")
        rec = c.claim()
        assert rec["status"] == "downloading" and rec["tries"] == 1
        assert c.claim() is None, "claim ซ้ำไม่ควรได้งานเดิม (ถูกล็อกแล้ว)"


def test_claim_specific_and_stale():
    with tempfile.TemporaryDirectory() as d:
        c = Crate(os.path.join(d, "crate.json"))
        c.add(_track(1), route="gate")
        c.add(_track(2), route="gate")
        rec = c.claim(track_id=2)
        assert rec["track_id"] == 2
        # งานที่ล็อกไว้ ถ้า stale=0 ควรถูกยึดใหม่ได้
        again = c.claim(stale_seconds=0, track_id=2)
        assert again is not None and again["tries"] == 2


def test_mark_and_requeue():
    with tempfile.TemporaryDirectory() as d:
        c = Crate(os.path.join(d, "crate.json"))
        c.add(_track(1), route="gate")
        c.claim()
        c.mark(1, "failed", reason="captcha", screenshot="x.png")
        assert c.counts()["failed"] == 1
        # requeue (Review loop) -> กลับเป็น pending, reason เคลียร์
        c.add(_track(1), requeue=True)
        rec = c.pending()[0]
        assert rec["status"] == "pending" and rec["reason"] == ""


def test_done_not_requeued_by_default():
    with tempfile.TemporaryDirectory() as d:
        c = Crate(os.path.join(d, "crate.json"))
        c.add(_track(1), route="direct_sc")
        c.claim()
        c.mark(1, "done", file_path="a.mp3", bitrate=320)
        c.add(_track(1))                       # add ปกติ -> ไม่ควรปลุก done กลับมา
        assert c.pending() == [] and c.counts()["done"] == 1


def test_clear_and_persist():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "crate.json")
        c = Crate(p)
        c.add(_track(1), route="gate")
        c.claim(); c.mark(1, "done", file_path="a.mp3", bitrate=320)
        c.add(_track(2), route="gate")
        c.save()
        c2 = Crate(p)                          # โหลดกลับจากไฟล์
        assert c2.counts()["total"] == 2
        c2.clear_finished()
        assert c2.counts()["total"] == 1 and c2.pending()[0]["track_id"] == 2


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
