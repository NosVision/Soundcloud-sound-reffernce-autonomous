#!/usr/bin/env python3
"""
doctor — ไล่เช็คการเชื่อมต่อ SoundCloud ทีละ step
(debug-mantra: reproduce -> trace the fail path)

รัน:  python3 doctor.py

บอกว่าต่อ SoundCloud ได้ครบไหม ถ้าพัง พังตรง step ไหน + แนะวิธีแก้
อ่านค่าจาก config.yaml / .env เหมือนตอนรันจริง (บังคับเช็คของจริง ไม่สน demo_mode)
"""

import sys
import requests

from scfinder import load_config
from scfinder.client import SoundCloudClient, SoundCloudError

OK = "\033[32m✓\033[0m"
BAD = "\033[31m✗\033[0m"


def step(n, msg):
    print(f"\n[{n}] {msg}")


def ok(msg):
    print(f"   {OK} {msg}")


def fail(msg, hint=""):
    print(f"   {BAD} {msg}")
    if hint:
        print(f"      → {hint}")


def main():
    cfg = load_config()
    print("=== SoundCloud connection doctor ===")
    print(f"seed_mode = {cfg.seed_mode} | profile = {cfg.profile_url}")
    print(f"seed_urls = {len(cfg.seed_urls)} อัน | oauth = {'set' if cfg.oauth_token else '-'}"
          f" | client_id override = {'set' if cfg.client_id_override else '-'}")
    if cfg.demo_mode:
        print("หมายเหตุ: config.yaml ตั้ง demo_mode: true อยู่ — doctor บังคับเช็ค SC จริง")
        print("         (ก่อนใช้งานจริงอย่าลืมตั้ง demo_mode: false)")

    client = SoundCloudClient(
        oauth_token=cfg.oauth_token,
        client_id_override=cfg.client_id_override,
        sleep=cfg.sleep,
    )

    # 1) network
    step(1, "เน็ตถึง soundcloud.com")
    try:
        r = requests.get("https://soundcloud.com/",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code == 200:
            ok("เชื่อมต่อได้ (HTTP 200)")
        else:
            fail(f"HTTP {r.status_code}",
                 "ถ้า 403/host_not_allowed = เครือข่ายบล็อก SoundCloud "
                 "(เช่นแซนด์บ็อกซ์/บริษัท) ต้องรันบนเครื่องที่เน็ตเปิด")
            return 1
    except Exception as e:
        fail(f"ต่อไม่ได้: {e}", "เช็คเน็ต / proxy / firewall")
        return 1

    # 2) client_id
    step(2, "ขุด client_id")
    try:
        cid = client.client_id
        ok(f"ได้ client_id: {cid[:6]}…{cid[-4:]}")
    except SoundCloudError as e:
        fail(str(e),
             "ใส่ SC_CLIENT_ID เอง: DevTools → Network → คลิก request ไป api-v2 "
             "→ ดู query param client_id")
        return 1

    # 3) seed (ตาม seed_mode)
    seeds = []
    if cfg.seed_mode in ("urls", "both") and cfg.seed_urls:
        step(3, f"resolve ลิงก์เพลง ({min(3, len(cfg.seed_urls))}/{len(cfg.seed_urls)} อัน)")
        for u in cfg.seed_urls[:3]:
            t = client.resolve_track(u)
            if t:
                ok(f"{t.get('title', '?')}  (id {t['id']})")
                seeds.append(t)
            else:
                fail(f"resolve ไม่ได้/ไม่ใช่เพลง: {u}",
                     "ตรวจว่าลิงก์เป็นเพลง (ไม่ใช่ playlist/โปรไฟล์) และเป็นสาธารณะ")

    if cfg.seed_mode in ("likes", "both"):
        step("3b" if seeds else 3, f"profile + likes: {cfg.profile_url}")
        if "YOUR-HANDLE" in cfg.profile_url:
            fail("ยังไม่ได้ตั้ง profile_url", "แก้ profile_url ใน config.yaml เป็นโปรไฟล์จริง")
        else:
            try:
                uid = client.resolve_user_id(cfg.profile_url)
                ok(f"user id = {uid}")
                liked = client.get_liked_tracks(uid, min(5, cfg.max_seeds))
                if liked:
                    ok(f"ดึง likes ได้ {len(liked)} เพลง (เช่น: {liked[0].get('title', '?')})")
                    seeds += liked
                else:
                    fail("likes ว่าง/ดึงไม่ได้", "likes เป็น private? ใส่ SC_OAUTH_TOKEN ใน .env")
            except SoundCloudError as e:
                fail(str(e), "PROFILE_URL ถูกไหม / likes private → ใส่ SC_OAUTH_TOKEN")

    if not seeds:
        step(3, "seed")
        fail("ไม่มี seed ที่ใช้ได้เลย",
             "ใส่ seed_urls (ลิงก์เพลง) หรือ profile_url ที่ถูกต้องใน config.yaml")
        return 1

    # 4) related (หัวใจของระบบ)
    step(4, "ดึง related (หัวใจ co-occurrence)")
    rel = client.get_related(seeds[0]["id"], 5)
    if rel:
        ok(f"ได้ related {len(rel)} เพลง จาก seed '{seeds[0].get('title', '?')}'")
    else:
        fail("related ว่าง",
             "เพลงนี้อาจไม่มี related ลองเพลงอื่น / หรือ SC เปลี่ยน endpoint "
             "/tracks/{id}/related")
        return 1

    print("\n✅ เชื่อมต่อ SoundCloud ได้ครบทุก step")
    print("   รันจริงได้เลย:  python3 sc_reference_finder.py   หรือ   python3 app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
