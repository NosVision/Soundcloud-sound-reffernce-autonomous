#!/usr/bin/env python3
"""
autorun — รันรอบเดียวแบบอัตโนมัติ (สำหรับ cron / launchd บน Mac Mini)  [Phase 3]

ทำ: หา reference -> เขียน CSV + export -> แจ้งเตือนเข้า LINE ("มี N เพลงรอคัด")

ตั้งเวลา (ตัวอย่าง crontab ทุกจันทร์ 9 โมง):
    0 9 * * 1  cd /path/to/repo && /usr/bin/python3 autorun.py >> autorun.log 2>&1

ต้องตั้ง env ก่อน (หรือใส่ใน .env):
    LINE_CHANNEL_TOKEN, LINE_TO   -> เปิดแจ้งเตือน LINE อัตโนมัติ
    SC_PROFILE_URL / SC_OAUTH_TOKEN ตามต้องการ
"""

import sys
from datetime import datetime

from scfinder import load_config, find_references, SeenStore
from scfinder.finder import write_csv
from scfinder.export import to_mixedinkey_csv, to_m3u8
from scfinder.client import SoundCloudClient, SoundCloudError
from scfinder.mockclient import MockClient
from scfinder.notify import notify_line_results
from scfinder.storage import make_storage


def build_client(cfg):
    if cfg.demo_mode:
        return MockClient()
    return SoundCloudClient(
        oauth_token=cfg.oauth_token,
        client_id_override=cfg.client_id_override,
        sleep=cfg.sleep,
    )


def main():
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n===== autorun {stamp} =====")

    cfg = load_config()
    client = build_client(cfg)
    store = SeenStore(cfg.seen_file, cfg.dedupe_enabled, storage=make_storage(cfg))

    try:
        results = find_references(client, cfg, store, log=print)
    except (SoundCloudError, ValueError) as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    write_csv(results, cfg.output)
    with open("sc_references_mixedinkey.csv", "w", encoding="utf-8") as f:
        f.write(to_mixedinkey_csv(results))
    with open("sc_references.m3u8", "w", encoding="utf-8") as f:
        f.write(to_m3u8(results))
    store.save()
    print(f"เขียน {len(results)} เพลง -> {cfg.output} (+ mixedinkey csv / m3u8)")

    # แจ้งเตือน LINE
    if cfg.line_enabled:
        ok, info = notify_line_results(results, cfg, when=stamp, demo=cfg.demo_mode)
        print(f"LINE notify: {'✅' if ok else '❌'} {info}")
    else:
        print("LINE notify: ปิดอยู่ (ตั้ง LINE_CHANNEL_TOKEN + LINE_TO เพื่อเปิด)")

    print("===== done =====")


if __name__ == "__main__":
    main()
