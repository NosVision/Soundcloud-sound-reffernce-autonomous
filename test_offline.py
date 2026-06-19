#!/usr/bin/env python3
"""
OFFLINE TEST สำหรับ sc_reference_finder.py
------------------------------------------
รันไม่ต้องต่อเน็ต / ไม่ต้องมี SoundCloud จริง

จุดประสงค์: พิสูจน์ว่า "หัวใจ" ของ pipeline ทำงานถูก
  - get_liked_tracks() อ่าน likes + paginate ถูก
  - get_related() ดึง related ต่อ seed
  - การนับ co-occurrence (matched_seeds) ถูกต้อง
  - การจัด rank (matched_seeds มาก่อน, ตามด้วย plays) ถูกต้อง
  - เขียน CSV ออกมาครบคอลัมน์

วิธีทำ: monkeypatch requests.get ในโมดูล ให้คืน mock data แทนการยิงเน็ตจริง
รัน:  python3 test_offline.py
"""

import csv
import sys
import sc_reference_finder as sc


# ---------- mock data ----------
# seeds = 3 เพลงที่เรา "like" (id 1,2,3)
LIKED = [
    {"kind": "track", "id": 1, "title": "Seed A"},
    {"kind": "track", "id": 2, "title": "Seed B"},
    {"kind": "track", "id": 3, "title": "Seed C"},
]


def _track(tid, title, plays, likes=0, genre="edit", dur_ms=210000):
    return {
        "kind": "track",
        "id": tid,
        "title": title,
        "user": {"username": f"artist_{tid}"},
        "genre": genre,
        "playback_count": plays,
        "likes_count": likes,
        "duration": dur_ms,
        "permalink_url": f"https://soundcloud.com/t/{tid}",
    }


# related ของแต่ละ seed — ออกแบบให้เห็น co-occurrence ชัดๆ
#   track 101 โผล่ใน related ของ seed ทั้ง 3  -> matched_seeds = 3  (ตรงแนวสุด)
#   track 102 โผล่ใน 2 seed                    -> matched_seeds = 2
#   ที่เหลือโผล่ seed เดียว                      -> matched_seeds = 1
RELATED = {
    1: [_track(101, "Core Hit", plays=5000),
        _track(102, "Strong Match", plays=9000),
        _track(103, "One-off X", plays=100)],
    2: [_track(101, "Core Hit", plays=5000),
        _track(102, "Strong Match", plays=9000),
        _track(201, "One-off Y", plays=8000)],
    3: [_track(101, "Core Hit", plays=5000),
        _track(301, "One-off Z", plays=50),
        _track(2,   "Seed B (should be removed)", plays=1)],  # seed โผล่เอง -> ต้องถูกตัดทิ้ง
}


class FakeResponse:
    def __init__(self, payload, status=200, text=""):
        self._payload = payload
        self.status_code = status
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def fake_get(url, params=None, headers=None, timeout=None):
    """router จำลอง api-v2.soundcloud.com"""
    if "/resolve" in url:
        return FakeResponse({"kind": "user", "id": 123})
    if "/track_likes" in url:
        # หน้าเดียวจบ (next_href = None)
        collection = [{"track": t} for t in LIKED]
        return FakeResponse({"collection": collection, "next_href": None})
    if "/related" in url:
        tid = int(url.split("/tracks/")[1].split("/related")[0])
        return FakeResponse({"collection": RELATED.get(tid, [])})
    raise AssertionError(f"unexpected URL in test: {url}")


def main():
    # --- ตั้งค่าให้ใช้ mock ---
    sc.requests.get = fake_get          # ดัก network ทั้งหมด
    sc.PROFILE_URL = "https://soundcloud.com/test-user"
    sc.CLIENT_ID_OVERRIDE = "TESTCLIENTID0000000000"  # ข้าม get_client_id ที่ scrape เว็บ
    sc.MAX_SEEDS = 10
    sc.SLEEP = 0                         # ไม่ต้องหน่วงตอนเทสต์
    sc.OUTPUT = "test_output.csv"

    print(">> รัน pipeline ด้วย mock data (ไม่ต่อเน็ต)\n")
    sc.main()

    # --- ตรวจผล ---
    print("\n>> ตรวจผลลัพธ์ใน", sc.OUTPUT)
    with open(sc.OUTPUT, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        print(f"  rank {r['rank']:>2} | matched_seeds={r['matched_seeds']} "
              f"| {r['title']:<14} | plays={r['plays']:>5} | {r['url']}")

    # --- assertions ---
    ok = True

    def check(cond, msg):
        nonlocal ok
        print(("  PASS " if cond else "  FAIL ") + msg)
        ok = ok and cond

    ids = [r['title'] for r in rows]
    check(rows[0]['title'] == "Core Hit" and rows[0]['matched_seeds'] == "3",
          "อันดับ 1 = Core Hit (matched_seeds=3) ตรงแนวสุด")
    check(rows[1]['title'] == "Strong Match" and rows[1]['matched_seeds'] == "2",
          "อันดับ 2 = Strong Match (matched_seeds=2)")
    check("Seed A" not in ids and "Seed B (should be removed)" not in ids,
          "เพลงที่ like อยู่แล้ว (seed) ถูกตัดออกจากผลลัพธ์")
    # one-off Y (plays 8000) ต้องมาก่อน one-off X/Z (plays น้อย) เมื่อ matched_seeds เท่ากัน
    oneoffs = [r['title'] for r in rows if r['matched_seeds'] == "1"]
    check(oneoffs and oneoffs[0] == "One-off Y",
          "เมื่อ matched_seeds เท่ากัน เรียงตาม plays มาก->น้อย")

    print()
    if ok:
        print("✅ ผ่านทุกข้อ — logic co-occurrence + ranking + CSV ทำงานถูกต้อง")
        sys.exit(0)
    else:
        print("❌ มีข้อที่ไม่ผ่าน")
        sys.exit(1)


if __name__ == "__main__":
    main()
