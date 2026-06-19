#!/usr/bin/env python3
"""
เทสต์ core pipeline (offline, ไม่ต่อเน็ต)
รัน:  python3 tests/test_finder.py
ครอบคลุม: co-occurrence rank, ตัด seed, filter ความยาว, dedupe ข้ามรอบ, seed จากลิงก์
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scfinder.config import Config
from scfinder.finder import find_references, write_csv, COLUMNS
from scfinder.store import SeenStore


def _t(tid, title, plays, dur_ms=210000):
    return {"kind": "track", "id": tid, "title": title,
            "user": {"username": f"a{tid}"}, "genre": "edit",
            "playback_count": plays, "likes_count": 0, "duration": dur_ms,
            "permalink_url": f"https://soundcloud.com/t/{tid}"}


class FakeClient:
    """seed 1,2,3 ; related ออกแบบให้ 101 โผล่ 3 seed, 102 โผล่ 2 seed"""
    LIKES = [_t(1, "Seed A", 1), _t(2, "Seed B", 1), _t(3, "Seed C", 1)]
    REL = {
        1: [_t(101, "Core Hit", 5000), _t(102, "Strong", 9000), _t(103, "X", 100)],
        2: [_t(101, "Core Hit", 5000), _t(102, "Strong", 9000), _t(201, "Y", 8000)],
        3: [_t(101, "Core Hit", 5000), _t(301, "Z", 50),
            _t(2, "Seed B self", 1), _t(401, "Long", 1, dur_ms=600000)],  # 10 นาที
        7: [_t(101, "Core Hit", 5000), _t(701, "Link Rel", 3000)],  # related ของ seed-จากลิงก์
    }

    def resolve_user_id(self, url): return 999
    def resolve_track(self, url):
        return _t(7, "From Link", 1234) if "track" in url else None
    def get_liked_tracks(self, uid, n): return self.LIKES[:n]
    def get_related(self, tid, limit): return self.REL.get(tid, [])


PASS, FAIL = "  \033[32mPASS\033[0m ", "  \033[31mFAIL\033[0m "
_ok = True


def check(cond, msg):
    global _ok
    print((PASS if cond else FAIL) + msg)
    _ok = _ok and cond


def base_cfg(**kw):
    c = Config(seed_mode="likes", profile_url="https://soundcloud.com/x",
               max_seeds=10, target=120, related_per_seed=50, sleep=0.0)
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def test_ranking():
    res = find_references(FakeClient(), base_cfg(), store=None)
    titles = [r.title for r in res]
    check(res[0].title == "Core Hit" and res[0].matched_seeds == 3,
          "co-occurrence: Core Hit (3 seeds) อันดับ 1")
    check(res[1].title == "Strong" and res[1].matched_seeds == 2,
          "matched_seeds มาก่อน plays (Strong 9000 ยังแพ้ Core 5000)")
    check("Seed A" not in titles and "Seed B self" not in titles,
          "seed ที่ like อยู่แล้วถูกตัดออก")
    oneoffs = [r.title for r in res if r.matched_seeds == 1]
    check(oneoffs[0] == "Y", "tie-break ด้วย plays (Y 8000 มาก่อน X/Z)")


def test_duration_filter():
    res = find_references(FakeClient(), base_cfg(duration_max=5.0), store=None)
    check(all(r.duration_min <= 5.0 for r in res),
          "filter ความยาว <=5 นาที ตัดเพลง 10 นาที (Long) ออก")
    check("Long" not in [r.title for r in res], "เพลง Long (10 นาที) หายไปจริง")


def test_dedupe():
    with tempfile.TemporaryDirectory() as d:
        seen = os.path.join(d, "seen.json")
        s1 = SeenStore(seen, enabled=True)
        r1 = find_references(FakeClient(), base_cfg(), store=s1)
        s1.save()
        check(len(r1) > 0 and os.path.exists(seen), "รอบ 1: ได้ผล + เขียน seen.json")

        s2 = SeenStore(seen, enabled=True)
        r2 = find_references(FakeClient(), base_cfg(), store=s2)
        check(len(r2) == 0, "รอบ 2: เพลงเดิมถูก dedupe หมด (ไม่เสนอซ้ำ)")


def test_seed_from_url():
    cfg = base_cfg(seed_mode="urls",
                   seed_urls=["https://soundcloud.com/a/track-1"])
    res = find_references(FakeClient(), cfg, store=None)
    check(len(res) > 0, "seed จากลิงก์ (urls mode) ทำงาน ได้ related ออกมา")


def test_csv():
    res = find_references(FakeClient(), base_cfg(), store=None)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "out.csv")
        write_csv(res, p)
        head = open(p, encoding="utf-8").readline().strip().split(",")
        check(head == COLUMNS, "CSV header ครบทุกคอลัมน์ตามสเปก")


if __name__ == "__main__":
    print(">> test core pipeline (offline)\n")
    test_ranking()
    test_duration_filter()
    test_dedupe()
    test_seed_from_url()
    test_csv()
    print()
    if _ok:
        print("\033[32m✅ ผ่านทุกข้อ\033[0m")
        sys.exit(0)
    print("\033[31m❌ มีข้อไม่ผ่าน\033[0m")
    sys.exit(1)
