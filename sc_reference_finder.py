#!/usr/bin/env python3
"""
SC REFERENCE FINDER — CLI
-------------------------
หา reference เพลงตรงแนวที่ชอบจาก SoundCloud (likes / ลิงก์เพลง -> related -> rank)

ตั้งค่าใน config.yaml (คัดลอกจาก config.example.yaml) แล้วรัน:
    python3 sc_reference_finder.py
ได้ sc_references.csv -> เปิดใน Sheets / Obsidian คัดต่อ

ดู dashboard เว็บได้ที่:  python3 app.py
"""

import sys

from scfinder import load_config, find_references, SeenStore
from scfinder.finder import write_csv
from scfinder.export import to_mixedinkey_csv, to_m3u8
from scfinder.client import SoundCloudClient, SoundCloudError
from scfinder.mockclient import MockClient


def build_client(cfg):
    if cfg.demo_mode:
        print("** demo_mode = true -> ใช้ข้อมูลปลอม (ไม่ต่อเน็ต) **")
        return MockClient()
    return SoundCloudClient(
        oauth_token=cfg.oauth_token,
        client_id_override=cfg.client_id_override,
        sleep=cfg.sleep,
    )


def main():
    cfg = load_config()
    client = build_client(cfg)
    store = SeenStore(cfg.seen_file, cfg.dedupe_enabled)

    try:
        results = find_references(client, cfg, store, log=print)
    except SoundCloudError as e:
        sys.exit(f"SoundCloud error: {e}")
    except ValueError as e:
        sys.exit(str(e))

    write_csv(results, cfg.output)
    # export เพิ่ม: พร้อมเข้า Mixed In Key / player
    with open("sc_references_mixedinkey.csv", "w", encoding="utf-8") as f:
        f.write(to_mixedinkey_csv(results))
    with open("sc_references.m3u8", "w", encoding="utf-8") as f:
        f.write(to_m3u8(results))
    store.save()

    print(f"\nเสร็จ -> {cfg.output} ({len(results)} เพลง)")
    print("           sc_references_mixedinkey.csv (Key=Camelot) / sc_references.m3u8")
    print("matched_seeds สูง = โผล่ซ้ำหลาย seed = ตรงแนวสุด คัด 100 ตัวบนได้เลย")


if __name__ == "__main__":
    main()
