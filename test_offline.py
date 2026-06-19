#!/usr/bin/env python3
"""
DEMO รัน pipeline แบบ offline ด้วย MockClient (ไม่ต่อเน็ต)
ใช้ดูผลลัพธ์ตัวอย่างเร็วๆ:  python3 test_offline.py
(เทสต์จริงอยู่ที่ tests/test_finder.py)
"""

from scfinder.config import Config
from scfinder.finder import find_references, write_csv
from scfinder.mockclient import MockClient


def main():
    cfg = Config(seed_mode="likes", max_seeds=8, target=20,
                 related_per_seed=8, sleep=0.0, dedupe_enabled=False)
    res = find_references(MockClient(), cfg, store=None, log=print)
    write_csv(res, "test_output.csv")
    print(f"\nได้ {len(res)} เพลง -> test_output.csv\n")
    for r in res[:10]:
        print(f"  #{r.rank:>2} matched={r.matched_seeds} | {r.title:<24} "
              f"| plays={r.plays:>6} | {r.url}")


if __name__ == "__main__":
    main()
