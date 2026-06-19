"""
MockClient — client ปลอม ไม่ต่อเน็ต ใช้ลอง dashboard / เขียน test

ข้อมูลตัวอย่างเลียนแบบแนว edit / bootleg / remix (ตามรสนิยมใน README)
co-occurrence ถูกออกแบบให้บางเพลงโผล่ใน related ของหลาย seed -> matched_seeds สูง
"""

import random

# คลังเพลงปลอม (id, title, artist, genre, plays, likes, duration_ms, bpm, key)
_CATALOG = [
    (1001, "NOKIA esentrik edit",    "esentrik",     "Edit",   42000, 3100, 215000, 124, "A minor"),
    (1002, "COME THRU edit",         "nightdrive",   "Edit",   38000, 2800, 198000, 122, "C major"),
    (1003, "Slow Grind (NIE Remix)", "NIE",          "Remix",  51000, 4200, 242000, 126, "E minor"),
    (1004, "YO-ZU edit",             "yo-zu",        "Edit",   29000, 1900, 187000, 120, "G major"),
    (1005, "Midnight Bootleg",       "lowkey",       "Bootleg",61000, 5200, 233000, 128, "A minor"),
    (1006, "Drift (Slowed)",         "vaporkid",     "Edit",   18000, 1200, 256000,  90, "D minor"),
    (1007, "After Hours Flip",       "moonset",      "Remix",  73000, 6100, 221000, 125, "F# minor"),
    (1008, "Tokyo Night edit",       "citypop_x",    "Edit",   45000, 3400, 205000, 118, "Bb major"),
    (1009, "No Sleep (VIP)",         "darkmatter",   "Bootleg",33000, 2100, 178000, 140, "C minor"),
    (1010, "Velvet Groove edit",     "smoothop",     "Edit",   27000, 1700, 263000, 112, "D major"),
    (1011, "Echoes Bootleg",         "reverbz",      "Bootleg",55000, 4800, 248000, 127, "E minor"),
    (1012, "Sunset Drive (Remix)",   "goldenhour",   "Remix",  88000, 7300, 229000, 123, "Bb minor"),
    (1013, "Lonely Tape edit",       "cassette",     "Edit",   21000, 1400, 192000, 100, ""),
    (1014, "Neon Pulse Flip",        "synthwave_jp", "Remix",  47000, 3600, 211000, 124, "F major"),
    (1015, "Faded Memory edit",      "haze",         "Edit",   36000, 2500, 240000, 119, "Ab major"),
]


def _track(rec):
    tid, title, artist, genre, plays, likes, dur, bpm, key = rec
    return {
        "kind": "track", "id": tid, "title": title,
        "user": {"username": artist}, "genre": genre,
        "playback_count": plays, "likes_count": likes,
        "duration": dur, "bpm": bpm, "key_signature": key,
        "permalink_url": f"https://soundcloud.com/{artist}/{tid}",
    }


_BY_ID = {r[0]: _track(r) for r in _CATALOG}

# anchor = เพลง 'ยอดนิยมในแนว' จงใจให้โผล่ใน related บ่อย -> matched_seeds สูง = ตรงแนวสุด
# แยกออกจาก seed เสมอ เพื่อให้ demo เห็นผลไม่ว่า max_seeds เท่าไหร่
_ANCHORS = [1003, 1005, 1007, 1012]
# เพลงที่ใช้เป็น 'likes' (ไม่รวม anchor -> anchor จะไม่ถูกตัดทิ้งตอน remove seed)
_LIKE_POOL = [1001, 1002, 1004, 1006, 1008, 1010, 1013, 1015]


class MockClient:
    def __init__(self, *_, **__):
        self.client_id = "MOCKCLIENTID0000000000"

    def resolve_user_id(self, profile_url: str) -> int:
        return 999

    def resolve_track(self, track_url: str):
        # ลองจับ id จากท้าย url ก่อน ไม่งั้น map แบบคงที่ตาม url (ไม่เอา anchor มาเป็น seed)
        for tid in _BY_ID:
            if str(tid) in track_url:
                return _BY_ID[tid]
        idx = abs(hash(track_url)) % len(_LIKE_POOL)
        return _BY_ID[_LIKE_POOL[idx]]

    def get_liked_tracks(self, user_id: int, max_seeds: int) -> list:
        return [_BY_ID[t] for t in _LIKE_POOL[:max(1, max_seeds)]]

    def get_related(self, track_id: int, limit: int) -> list:
        """anchor โผล่เกือบทุกครั้ง + สุ่มเพิ่มให้หลากหลาย (deterministic ตาม track_id)"""
        rnd = random.Random(track_id)
        others = [t for t in _BY_ID if t != track_id]
        picks = [a for a in _ANCHORS if a != track_id]   # anchor มาก่อน -> matched_seeds สูง
        extra = [t for t in others if t not in picks]
        rnd.shuffle(extra)
        picks += extra[:max(0, min(limit, 8) - len(picks))]
        return [_BY_ID[t] for t in picks]
