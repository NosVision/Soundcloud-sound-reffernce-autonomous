#!/usr/bin/env python3
"""
เทสต์ Phase 4: feedback store + preference model + re-rank
รัน:  python3 tests/test_feedback.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scfinder.finder import Result
from scfinder.feedback import (FeedbackStore, PreferenceModel,
                               annotate_and_rank, track_features)

_ok = True


def check(cond, msg):
    global _ok
    print(("  \033[32mPASS\033[0m " if cond else "  \033[31mFAIL\033[0m ") + msg)
    _ok = _ok and cond


def _res(tid, ms, genre, cam, bpm, plays=1000):
    return Result(rank=0, matched_seeds=ms, title=f"T{tid}", artist=f"dj{tid}",
                  genre=genre, bpm=bpm, key="", camelot=cam, plays=plays,
                  likes=0, duration_min=3.0, url=f"u/{tid}", track_id=tid)


def test_features():
    f = track_features(_res(1, 3, "Edit", "8A", 124).__dict__)
    check(f["genre"] == "edit" and f["camelot"] == "8A" and f["bpm"] == "120s",
          "track_features ดึง genre/camelot/bpm bucket ถูก")


def test_store_persist():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "fb.json")
        s = FeedbackStore(p)
        s.record(_res(1, 3, "edit", "8A", 124).__dict__, True)
        s.record(_res(1, 3, "edit", "8A", 124).__dict__, False)  # ปัดซ้ำ -> อัปเดต
        s.save()
        check(s.counts()["total"] == 1, "ปัดซ้ำเพลงเดิม = อัปเดต ไม่เพิ่ม record")
        s2 = FeedbackStore(p)
        check(s2.counts()["total"] == 1 and 1 in s2.rated_ids(),
              "โหลดจากไฟล์กลับมาได้ + rated_ids ถูก")


def test_model_learns():
    # ชอบ edit ไม่ชอบ techno
    recs = []
    for tid in range(10, 15):
        recs.append({"track_id": tid, "liked": True,
                     "features": {"genre": "edit", "camelot": "8A"}})
    for tid in range(20, 25):
        recs.append({"track_id": tid, "liked": False,
                     "features": {"genre": "techno", "camelot": "3B"}})
    m = PreferenceModel(recs)
    s_edit = m.score(_res(99, 1, "edit", "8A", 124).__dict__)
    s_tech = m.score(_res(98, 1, "techno", "3B", 130).__dict__)
    check(s_edit > 0.5, "เพลง genre ที่ชอบ (edit) -> pref สูง (>0.5)")
    check(s_tech < -0.5, "เพลง genre ที่ไม่ชอบ (techno) -> pref ต่ำ (<-0.5)")
    check(abs(m.score(_res(97, 1, "house", "5A", 122).__dict__)) < 0.01,
          "เพลง feature ที่ไม่เคยเห็น -> pref ~0 (กลางๆ)")


def test_profile():
    recs = [{"track_id": 1, "liked": True, "features": {"genre": "edit"}},
            {"track_id": 2, "liked": True, "features": {"genre": "edit"}},
            {"track_id": 3, "liked": False, "features": {"genre": "techno"}}]
    prof = PreferenceModel(recs).profile()
    top_genre = prof["genre"][0]
    check(top_genre["value"] == "edit" and top_genre["like_rate"] > 0.5,
          "profile: edit เป็นแนวที่ like_rate สูงสุด")


def test_rerank_keeps_cooccurrence():
    # A: matched 5, แต่ genre ที่ชอบ ; B: matched 5 genre เฉยๆ ; C: matched 3 genre ชอบ
    results = [_res(1, 5, "edit", "8A", 124),
               _res(2, 5, "pop", "1A", 100),
               _res(3, 3, "edit", "8A", 124)]
    recs = [{"track_id": t, "liked": True, "features": {"genre": "edit", "camelot": "8A"}}
            for t in range(50, 56)]
    ranked = annotate_and_rank(results, recs, weight=0.5)
    ids = [r.track_id for r in ranked]
    check(ids[0] == 1, "ในกลุ่ม matched เท่ากัน เพลงที่ตรงรสนิยมขึ้นก่อน (1 ก่อน 2)")
    check(ids.index(3) == 2, "เพลง matched=3 ยังอยู่ท้าย — co-occurrence ไม่ถูกกลบ")
    check(all(hasattr(r, "pref") for r in ranked), "ทุกผลมีคะแนน pref")


if __name__ == "__main__":
    print(">> Phase 4 feedback/learning tests\n")
    test_features()
    test_store_persist()
    test_model_learns()
    test_profile()
    test_rerank_keeps_cooccurrence()
    print()
    if _ok:
        print("\033[32m✅ ผ่านทุกข้อ\033[0m"); sys.exit(0)
    print("\033[31m❌ มีข้อไม่ผ่าน\033[0m"); sys.exit(1)
