#!/usr/bin/env python3
"""
download_agent — โหลดเพลงในคิว crate (รันบน Mac Mini)  [Phase 1-4]

ทำ: poll คิว crate -> claim เพลง pending -> เลือกวิธีโหลดตาม route
    direct_sc / direct_file -> DirectDownloader (Phase 2)
    gate                    -> GateBot (Playwright, Phase 3)
    paid / none             -> ข้าม (mark)
-> ตรวจ bitrate ≥ min -> mark done/low_quality/failed -> fail เก็บ screenshot+reason (Review, Phase 4)

ใช้:
    python3 download_agent.py --once     # รอบเดียว (cron / launchd / Claude Code skill)
    python3 download_agent.py --watch    # daemon: poll ทุก download.poll_seconds วินาที

สั่งจากมือถือ: กด ⬇ บน dashboard -> เข้า crate (Supabase) -> agent ตัวนี้บน Mac เห็นแล้วโหลด
"""

import argparse
import sys
import time

from scfinder import load_config
from scfinder.storage import make_storage
from scfinder.crate import Crate
from scfinder.client import SoundCloudClient, SoundCloudError
from scfinder.resolver import resolve_route
from scfinder.dl_direct import DirectDownloader
from scfinder.gatebot import GateBot
from scfinder.gate_rules import GateRules


def build_client(cfg):
    return SoundCloudClient(oauth_token=cfg.oauth_token,
                            client_id_override=cfg.client_id_override, sleep=cfg.sleep)


class Agent:
    def __init__(self, cfg, log=print):
        self.cfg = cfg
        self.log = log
        self.storage = make_storage(cfg)
        self.crate = Crate(cfg.crate_file, storage=self.storage)
        self.rules = GateRules(cfg.gate_rules_file)
        try:
            self.client = build_client(cfg)
        except SoundCloudError as e:
            self.log(f"client init เตือน: {e}")
            self.client = None
        self.direct = DirectDownloader(client=self.client,
                                       min_bitrate=cfg.download_min_bitrate)
        self.gatebot = GateBot(self.rules, cfg.download_dir,
                               min_bitrate=cfg.download_min_bitrate,
                               social_unlock=cfg.download_social_unlock,
                               browser_profile=cfg.download_browser_profile)

    def _finish_fail(self, rec, reason, screenshot=""):
        """เกิน max_tries -> failed ; ไม่งั้นคืน pending ให้ลองรอบหน้า"""
        if rec.get("tries", 0) >= self.cfg.download_max_tries:
            self.crate.mark(rec["track_id"], "failed", reason=reason, screenshot=screenshot)
            self.log(f"   ✗ failed: {reason}")
        else:
            self.crate.mark(rec["track_id"], "pending", reason=reason,
                            screenshot=screenshot, claimed_at="")
            self.log(f"   ↻ retry ({rec.get('tries')}/{self.cfg.download_max_tries}): {reason}")

    def _settle(self, rec, res):
        """แปลผลโหลด (DLResult/GateResult) -> mark crate"""
        tid = rec["track_id"]
        if res.ok:
            self.crate.mark(tid, "done", file_path=res.path, bitrate=res.bitrate, reason="")
            self.log(f"   ✓ done ({res.bitrate or '?'}kbps): {res.path}")
        elif res.bitrate and 0 < res.bitrate < self.cfg.download_min_bitrate:
            self.crate.mark(tid, "low_quality", file_path=res.path,
                            bitrate=res.bitrate, reason=res.reason)
            self.log(f"   ⚠ low_quality {res.bitrate}kbps < {self.cfg.download_min_bitrate}")
        else:
            shot = getattr(res, "screenshot", "") or ""
            if getattr(res, "signature", None) is not None and rec.get("route") == "gate":
                self.rules.record_failure(rec.get("target_url", ""), res.reason,
                                          getattr(res, "signature", "") or "")
            self._finish_fail(rec, res.reason, shot)

    def process(self, rec):
        cfg = self.cfg
        route = rec.get("route")
        if not route:
            route, target = resolve_route(rec, self.client)
            self.crate.mark(rec["track_id"], rec["status"], route=route, target_url=target)
            rec["route"], rec["target_url"] = route, target
        self.rules.record_stat(route)

        if route in ("paid", "none"):
            self.crate.mark(rec["track_id"], route,
                            reason=f"ข้ามอัตโนมัติ (route={route})")
            self.log(f"   – skip ({route})")
            return
        if route in ("direct_sc", "direct_file"):
            self._settle(rec, self.direct.download(rec, cfg.download_dir))
            return
        if route == "gate":
            self._settle(rec, self.gatebot.download(rec))
            return
        self._finish_fail(rec, f"route ไม่รองรับ: {route}")

    def run_once(self) -> int:
        """เดินทุกเพลง pending รอบเดียว (snapshot กัน re-claim วนไม่จบ)"""
        ids = [r["track_id"] for r in self.crate.pending()]
        done = 0
        for tid in ids:
            rec = self.crate.claim(track_id=tid)
            if not rec:
                continue
            self.log(f"-> [{rec.get('route') or '?'}] "
                     f"{rec.get('artist')} - {rec.get('title')}")
            try:
                self.process(rec)
            except Exception as e:                       # อะไรพังก็ไม่ให้ล้มทั้งรอบ
                self._finish_fail(rec, f"unexpected: {e}")
            self._save()
            done += 1
            time.sleep(self.cfg.sleep)
        return done

    def watch(self):
        """daemon: poll คิวเรื่อยๆ"""
        self.log(f"watch: poll ทุก {self.cfg.download_poll_seconds}s "
                 f"(Ctrl-C เพื่อหยุด) -> {self.cfg.download_dir}")
        while True:
            rec = self.crate.claim()
            if rec:
                self.log(f"-> [{rec.get('route') or '?'}] "
                         f"{rec.get('artist')} - {rec.get('title')}")
                try:
                    self.process(rec)
                except Exception as e:
                    self._finish_fail(rec, f"unexpected: {e}")
                self._save()
                time.sleep(self.cfg.sleep)
            else:
                time.sleep(self.cfg.download_poll_seconds)

    def _save(self):
        self.crate.save()
        try:
            self.rules.save()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser(description="โหลดเพลงในคิว crate")
    ap.add_argument("--watch", action="store_true", help="daemon: poll คิวต่อเนื่อง")
    ap.add_argument("--once", action="store_true", help="รอบเดียวแล้วจบ (default)")
    args = ap.parse_args()

    cfg = load_config()
    agent = Agent(cfg)
    agent.crate  # noqa  (โหลดคิวแล้ว)

    if args.watch:
        try:
            agent.watch()
        except KeyboardInterrupt:
            print("\nหยุด watch แล้ว")
        return

    n = agent.run_once()
    counts = agent.crate.counts()
    print(f"\n===== download_agent: ประมวลผล {n} เพลง =====")
    print(f"สรุปคิว: {counts}")
    failed = counts.get("failed", 0) + counts.get("low_quality", 0)
    sys.exit(1 if failed and n == 0 else 0)


if __name__ == "__main__":
    main()
