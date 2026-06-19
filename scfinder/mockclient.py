"""
MockClient — client ปลอม ไม่ต่อเน็ต ใช้ลอง dashboard / เขียน test

ข้อมูลตัวอย่างเลียนแบบแนว edit / bootleg / remix (ตามรสนิยมใน README)
co-occurrence ถูกออกแบบให้บางเพลงโผล่ใน related ของหลาย seed -> matched_seeds สูง
"""

import random

# คลังเพลงปลอม (id, title, artist, genre, plays, likes, duration_ms)
_CATALOG = [
    (1001, "NOKIA esentrik edit",        "esentrik",     "Edit",   42000, 3100, 215000),
    (1002, "COME THRU edit",             "nightdrive",   "Edit",   38000, 2800, 198000),
    (1003, "Slow Grind (NIE Remix)",     "NIE",          "Remix",  51000, 4200, 242000),
    (1004, "YO-ZU edit",                 "yo-zu",        "Edit",   29000, 1900, 187000),
    (1005, "Midnight Bootleg",           "lowkey",       "Bootleg",61000, 5200, 233000),
    (1006, "Drift (Slowed)",             "vaporkid",     "Edit",   18000, 1200, 256000),
    (1007, "After Hours Flip",           "moonset",      "Remix",  73000, 6100, 221000),
    (1008, "Tokyo Night edit",           "citypop_x",    "Edit",   45000, 3400, 205000),
    (1009, "No Sleep (VIP)",             "darkmatter",   "Bootleg",33000, 2100, 178000),
    (1010, "Velvet Groove edit",         "smoothop",     "Edit",   27000, 1700, 263000),
    (1011, "Echoes Bootleg",             "reverbz",      "Bootleg",55000, 4800, 248000),
    (1012, "Sunset Drive (Remix)",       "goldenhour",   "Remix",  88000, 7300, 229000),
    (1013, "Lonely Tape edit",           "cassette",     "Edit",   21000, 1400, 192000),
    (1014, "Neon Pulse Flip",            "synthwave_jp", "Remix",  47000, 3600, 211000),
    (1015, "Faded Memory edit",          "haze",         "Edit",   36000, 2500, 240000),
]


def _track(rec):
    tid, title, artist, genre, plays, likes, dur = rec
    return {
        "kind": "track", "id": tid, "title": title,
        "user": {"username": artist}, "genre": genre,
        "playback_count": plays, "likes_count": likes,
        "duration": dur,
        "permalink_url": f"https://soundcloud.com/{artist}/{tid}",
    }


_BY_ID = {r[0]: _track(r) for r in _CATALOG}


class MockClient:
    def __init__(self, *_, **__):
        self.client_id = "MOCKCLIENTID0000000000"
        random.seed(7)  # ผลคงที่ เทสต์ได้

    def resolve_user_id(self, profile_url: str) -> int:
        return 999

    def resolve_track(self, track_url: str):
        # ลองจับ id จากท้าย url ก่อน ไม่งั้นสุ่มจากคลัง (deterministic ตาม url)
        for tid in _BY_ID:
            if str(tid) in track_url:
                return _BY_ID[tid]
        idx = abs(hash(track_url)) % len(_CATALOG)
        return _track(_CATALOG[idx])

    def get_liked_tracks(self, user_id: int, max_seeds: int) -> list:
        return [_BY_ID[t] for t in list(_BY_ID)[:max_seeds]]

    def get_related(self, track_id: int, limit: int) -> list:
        """
        ทำให้บางเพลง 'ยอดนิยมในแนว' (1003,1005,1007,1012) โผล่ใน related บ่อย
        -> ได้ matched_seeds สูง = ตรงแนวสุด เหมือนของจริง
        """
        anchors = [1003, 1005, 1007, 1012]
        rnd = random.Random(track_id)
        pool = [t for t in _BY_ID if t != track_id]
        picks = set(a for a in anchors if a != track_id)        # anchor โผล่เกือบทุกครั้ง
        while len(picks) < min(limit, 8):
            picks.add(rnd.choice(pool))
        return [_BY_ID[t] for t in picks]
