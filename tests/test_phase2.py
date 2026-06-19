#!/usr/bin/env python3
"""
เทสต์ Phase 2: BPM/key enrichment, Camelot, harmonic set, export
รัน:  python3 tests/test_phase2.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scfinder.config import Config
from scfinder.finder import find_references, group_by_camelot, group_by_bpm
from scfinder.camelot import to_camelot, compatible_camelot, is_compatible
from scfinder.mixset import build_harmonic_set, harmonic_neighbours
from scfinder.export import to_mixedinkey_csv, to_m3u8, to_json

_ok = True


def check(cond, msg):
    global _ok
    print(("  \033[32mPASS\033[0m " if cond else "  \033[31mFAIL\033[0m ") + msg)
    _ok = _ok and cond


def _t(tid, title, plays, bpm=0, key="", dur_ms=210000):
    return {"kind": "track", "id": tid, "title": title,
            "user": {"username": f"a{tid}"}, "genre": "edit",
            "playback_count": plays, "likes_count": 0, "duration": dur_ms,
            "bpm": bpm, "key_signature": key,
            "permalink_url": f"https://soundcloud.com/t/{tid}"}


class FakeClient:
    LIKES = [_t(1, "Seed A", 1), _t(2, "Seed B", 1)]
    REL = {
        1: [_t(101, "Am 124", 5000, bpm=124, key="A minor"),
            _t(102, "Em 126", 4000, bpm=126, key="E minor"),
            _t(103, "Cmaj 175", 3000, bpm=175, key="C major")],
        2: [_t(101, "Am 124", 5000, bpm=124, key="A minor"),
            _t(104, "noBPM noKey", 2000)],
    }
    def resolve_user_id(self, url): return 1
    def resolve_track(self, url): return None
    def get_liked_tracks(self, uid, n): return self.LIKES[:n]
    def get_related(self, tid, limit): return self.REL.get(tid, [])


def cfg(**kw):
    c = Config(seed_mode="likes", max_seeds=10, target=120,
               related_per_seed=50, sleep=0.0, dedupe_enabled=False)
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def test_camelot_convert():
    check(to_camelot("A minor") == "8A", "A minor -> 8A")
    check(to_camelot("C major") == "8B", "C major -> 8B")
    check(to_camelot("Am") == "8A", "ย่อ 'Am' -> 8A")
    check(to_camelot("F#min") == "11A", "F#min -> 11A")
    check(to_camelot("Bb") == "6B", "'Bb' (major) -> 6B")
    check(to_camelot("") == "" and to_camelot("xyz") == "", "ว่าง/ไม่มี root -> ''")


def test_camelot_compat():
    c = compatible_camelot("8A")
    check(set(c) == {"8A", "8B", "9A", "7A"}, "8A เข้ากับ 8A/8B/9A/7A")
    check(is_compatible("8A", "8B"), "8A กับ relative major 8B เข้ากัน")
    check(not is_compatible("8A", "3B"), "8A กับ 3B ไม่เข้ากัน")
    check(compatible_camelot("12B")[2] == "1B", "wrap: 12B +1 -> 1B")


def test_enrichment():
    res = find_references(FakeClient(), cfg(), store=None)
    by = {r.title: r for r in res}
    check(by["Am 124"].bpm == 124 and by["Am 124"].camelot == "8A",
          "enrich BPM+Camelot จาก metadata (Am 124 -> 8A)")
    check(by["noBPM noKey"].bpm == 0 and by["noBPM noKey"].camelot == "",
          "เพลงไม่มี BPM/key -> 0 / '' (ไม่ crash)")


def test_bpm_filter():
    res = find_references(FakeClient(), cfg(bpm_max=140), store=None)
    titles = [r.title for r in res]
    check("Cmaj 175" not in titles, "filter BPM<=140 ตัดเพลง 175 ออก")
    check("noBPM noKey" in titles, "เพลงไม่มี BPM ไม่ถูกตัด (เก็บไว้)")


def test_harmonic_set():
    res = find_references(FakeClient(), cfg(), store=None)
    ordered = build_harmonic_set(res, start_index=0)
    check(len(ordered) == len(res), "harmonic set ครบทุกเพลง ไม่หาย")
    # 8A (Am124) ควรตามด้วย 9A (Em126) เพราะ harmonic + BPM ใกล้
    idx = [r.camelot for r in ordered]
    if "8A" in idx and "9A" in idx:
        check(abs(idx.index("8A") - idx.index("9A")) == 1,
              "8A ต่อ 9A ติดกัน (harmonic + BPM ใกล้)")
    nb = harmonic_neighbours(res, "8A")
    check(all(c.camelot in compatible_camelot("8A") for c in nb),
          "harmonic_neighbours คืนเฉพาะ key ที่เข้ากัน")


def test_exports():
    res = find_references(FakeClient(), cfg(), store=None)
    mik = to_mixedinkey_csv(res)
    check(mik.splitlines()[0].startswith("Artist,Title,Key,BPM"),
          "Mixed In Key CSV header ถูก")
    check("8A" in mik, "Camelot โผล่ในคอลัมน์ Key ของ MIK CSV")
    m3u = to_m3u8(res)
    check(m3u.startswith("#EXTM3U") and "soundcloud.com" in m3u,
          "M3U8 มี header + ลิงก์")
    import json as _j
    data = _j.loads(to_json(res))
    check(isinstance(data, list) and "camelot" in data[0],
          "JSON export มี field camelot")


def test_grouping():
    res = find_references(FakeClient(), cfg(), store=None)
    gc = group_by_camelot(res)
    gb = group_by_bpm(res, width=10)
    check("8A" in gc, "group_by_camelot มีกลุ่ม 8A")
    check(any("120" in k for k in gb), "group_by_bpm มีช่วง 120-129")


if __name__ == "__main__":
    print(">> Phase 2 tests\n")
    test_camelot_convert()
    test_camelot_compat()
    test_enrichment()
    test_bpm_filter()
    test_harmonic_set()
    test_exports()
    test_grouping()
    print()
    if _ok:
        print("\033[32m✅ ผ่านทุกข้อ\033[0m"); sys.exit(0)
    print("\033[31m❌ มีข้อไม่ผ่าน\033[0m"); sys.exit(1)
