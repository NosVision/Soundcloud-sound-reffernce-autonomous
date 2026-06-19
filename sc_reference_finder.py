#!/usr/bin/env python3
"""
SC REFERENCE FINDER (v2 - auto likes)
-------------------------------------
หา reference เพลงตรงแนวที่นอสชอบ โดยใช้ "likes" ทั้งหมดเป็น seed อัตโนมัติ
ฟรี 100% ใช้ api-v2 ตัวเดียวกับเว็บ SoundCloud (ไม่เสียตัง ไม่ต้องผูกบัตร)

วิธีใช้:
  1. ใส่ PROFILE_URL ของนอส (เช่น https://soundcloud.com/your-handle)
  2. python3 sc_reference_finder.py
  3. ได้ sc_references.csv -> เปิดใน Sheets / Obsidian คัดต่อ

ไม่ต้องเปิด DevTools — script หา client_id เอง
ถ้า likes เป็น private หรือ resolve ไม่ได้ -> ใส่ OAUTH_TOKEN (ดู comment ด้านล่าง)
"""

import csv
import re
import sys
import time
import requests

# ============== CONFIG ==============
PROFILE_URL = "https://soundcloud.com/YOUR-HANDLE"   # <-- ใส่ profile ตัวเอง

MAX_SEEDS = 60            # ดึง likes ล่าสุดกี่เพลงมาเป็น seed (1745 มันเยอะไป เอา recent พอ)
TARGET = 120             # ดึงเผื่อ แล้วค่อยคัดเหลือ 100
RELATED_PER_SEED = 50    # related สูงสุดต่อ 1 seed
SLEEP = 0.4              # กัน rate limit (อย่าลดต่ำกว่านี้)

CLIENT_ID_OVERRIDE = ""  # ใส่เองถ้า auto หาไม่เจอ
OAUTH_TOKEN = ""         # ใส่ถ้า likes เป็น private:
                         # soundcloud.com -> DevTools Network -> filter "session"
                         # -> Request Payload -> access_token
OUTPUT = "sc_references.csv"
# ====================================

API = "https://api-v2.soundcloud.com"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def auth_params(cid):
    return {"client_id": cid}


def headers():
    h = dict(UA)
    if OAUTH_TOKEN:
        h["Authorization"] = f"OAuth {OAUTH_TOKEN}"
    return h


def get_client_id() -> str:
    if CLIENT_ID_OVERRIDE:
        return CLIENT_ID_OVERRIDE
    html = requests.get("https://soundcloud.com/", headers=UA, timeout=15).text
    scripts = re.findall(r'<script[^>]+src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"', html)
    for url in reversed(scripts):
        js = requests.get(url, headers=UA, timeout=15).text
        m = re.search(r'client_id\s*[:=]\s*"([0-9a-zA-Z]{20,})"', js)
        if m:
            return m.group(1)
    sys.exit("หา client_id ไม่เจอ -> ใส่ CLIENT_ID_OVERRIDE เอง")


def resolve_user_id(cid) -> int:
    r = requests.get(f"{API}/resolve", params={"url": PROFILE_URL, **auth_params(cid)},
                     headers=headers(), timeout=15)
    r.raise_for_status()
    d = r.json()
    if d.get("kind") != "user":
        sys.exit("PROFILE_URL ไม่ใช่หน้า user")
    return d["id"]


def get_liked_tracks(cid, user_id):
    """ดึง likes ล่าสุด MAX_SEEDS เพลง (paginate ผ่าน next_href)"""
    if OAUTH_TOKEN:
        url = f"{API}/me/track_likes"
    else:
        url = f"{API}/users/{user_id}/track_likes"
    params = {**auth_params(cid), "limit": 50, "linked_partitioning": 1}
    seeds = []
    while url and len(seeds) < MAX_SEEDS:
        r = requests.get(url, params=params, headers=headers(), timeout=15)
        if r.status_code != 200:
            print(f"  ดึง likes ไม่ได้ (HTTP {r.status_code}) "
                  f"-> ถ้า likes private ลองใส่ OAUTH_TOKEN")
            break
        data = r.json()
        for item in data.get("collection", []):
            t = item.get("track", item)  # บาง endpoint ห่อใน 'track'
            if t and t.get("kind") == "track":
                seeds.append(t)
        url = data.get("next_href")
        params = {**auth_params(cid)}  # next_href มี param อื่นมาแล้ว
        time.sleep(SLEEP)
    return seeds[:MAX_SEEDS]


def get_related(cid, track_id):
    r = requests.get(f"{API}/tracks/{track_id}/related",
                     params={**auth_params(cid), "limit": RELATED_PER_SEED},
                     headers=headers(), timeout=15)
    if r.status_code != 200:
        return []
    return r.json().get("collection", [])


def main():
    cid = get_client_id()
    print(f"client_id ok: {cid[:8]}...")

    uid = resolve_user_id(cid)
    seeds = get_liked_tracks(cid, uid)
    print(f"seeds จาก likes: {len(seeds)} เพลง\n")

    pool, hit_count = {}, {}
    seed_ids = {s["id"] for s in seeds}

    for s in seeds:
        for rel in get_related(cid, s["id"]):
            tid = rel["id"]
            pool[tid] = rel
            hit_count[tid] = hit_count.get(tid, 0) + 1
        time.sleep(SLEEP)

    for sid in seed_ids:                 # ไม่เอาเพลงที่ like อยู่แล้วมาแนะนำ
        pool.pop(sid, None)

    ranked = sorted(
        pool.values(),
        key=lambda t: (hit_count.get(t["id"], 0), t.get("playback_count", 0) or 0),
        reverse=True,
    )[:TARGET]

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "matched_seeds", "title", "artist",
                    "genre", "plays", "likes", "duration_min", "url"])
        for i, t in enumerate(ranked, 1):
            user = (t.get("user") or {}).get("username", "")
            dur = round((t.get("duration", 0) or 0) / 60000, 1)
            w.writerow([i, hit_count.get(t["id"], 0), t.get("title", ""), user,
                        t.get("genre", ""), t.get("playback_count", 0),
                        t.get("likes_count", 0), dur, t.get("permalink_url", "")])

    print(f"เสร็จ -> {OUTPUT} ({len(ranked)} เพลง)")
    print("คอลัมน์ matched_seeds สูง = โผล่ซ้ำหลาย like = ตรงแนวสุด คัด 100 ตัวบนได้เลย")


if __name__ == "__main__":
    main()
