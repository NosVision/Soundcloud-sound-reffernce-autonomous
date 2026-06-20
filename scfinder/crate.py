"""
crate — คิวเพลงที่จะโหลด (กระบะ) + สถานะรายเพลง  [Phase 1]

เก็บผ่าน storage (Supabase ตาราง crate) ถ้ามี ไม่งั้นไฟล์ local crate.json
(เลียนแบบ FeedbackStore — ใช้ pattern เดียวกันทั้ง repo)

flow: เว็บ/มือถือ add เข้า crate (pending) -> agent บน Mac claim -> โหลด -> mark ผล
สถานะ: pending | downloading | done | low_quality | failed | paid | none
"""

import json
import os
import time
from datetime import datetime, timezone

STATUSES = ("pending", "downloading", "done", "low_quality", "failed", "paid", "none")
# สถานะที่ถือว่า "จบแล้ว" (agent ไม่แตะ) — ใช้ตอน clear/นับ
FINISHED = ("done", "paid", "none")
# สถานะที่ requeue ได้ (ลองใหม่)
RETRYABLE = ("failed", "low_quality", "none", "paid")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _age(iso: str, now: float) -> float:
    """อายุ (วินาที) ของ timestamp ISO เทียบกับ now (epoch); ค่ามากถ้า parse ไม่ได้"""
    if not iso:
        return 1e9
    try:
        return now - datetime.fromisoformat(iso).timestamp()
    except (ValueError, TypeError):
        return 1e9


class Crate:
    def __init__(self, path: str = "crate.json", storage=None):
        self.path = path
        self.storage = storage      # มี = ใช้ Supabase แทนไฟล์
        self.records = []
        self._load()

    def _load(self):
        if self.storage and hasattr(self.storage, "load_crate"):
            self.records = self.storage.load_crate()
            return
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                self.records = json.load(f).get("records", [])
        except (json.JSONDecodeError, OSError):
            self.records = []

    def _find(self, track_id):
        tid = str(track_id)
        return next((r for r in self.records if str(r.get("track_id")) == tid), None)

    def add(self, track: dict, route: str = "", target_url: str = "",
            requeue: bool = False) -> dict:
        """
        เพิ่มเพลงเข้าคิว (dedupe by track_id)
        - เคยมีและ done/downloading -> คงไว้ (กันโหลดซ้ำ) เว้นแต่ requeue=True
        - เคยมีและ failed/low_quality/none/paid -> reset เป็น pending (ลองใหม่)
        """
        tid = track.get("track_id") or track.get("id")
        if tid is None:
            return None
        rec = self._find(tid)
        if rec:
            if rec["status"] in ("done", "downloading") and not requeue:
                return rec
            if rec["status"] in RETRYABLE or requeue:
                rec["status"] = "pending"
                rec["reason"] = ""
                rec["screenshot"] = ""
                rec["claimed_at"] = ""
                if route:
                    rec["route"] = route
                if target_url:
                    rec["target_url"] = target_url
                rec["when"] = _now()
            return rec

        if route == "paid":
            status = "paid"
        elif route == "none":
            status = "none"
        else:
            status = "pending"
        rec = {
            "track_id": tid,
            "title": track.get("title", "") or "",
            "artist": (track.get("artist")
                       or (track.get("user") or {}).get("username", "") or ""),
            "url": track.get("url") or track.get("permalink_url", "") or "",
            "route": route or "",
            "target_url": target_url or "",
            "status": status,
            "file_path": "",
            "bitrate": 0,
            "reason": "",
            "screenshot": "",
            "tries": 0,
            "claimed_at": "",
            "when": _now(),
        }
        self.records.append(rec)
        return rec

    def pending(self) -> list:
        return [r for r in self.records if r["status"] == "pending"]

    def claim(self, stale_seconds: int = 900, track_id=None) -> dict:
        """
        ยึด 1 งานมาทำ: pending หรือ downloading ที่ค้างเกิน stale (agent เดิมตาย)
        ตั้งเป็น downloading + claimed_at + tries+1 กันรันซ้อนโหลดซ้ำ
        track_id ระบุ = ยึดเฉพาะเพลงนั้น (ใช้ตอน --once เดินทีละเพลงใน snapshot)
        """
        now = time.time()
        pool = [self._find(track_id)] if track_id is not None else self.records
        for r in pool:
            if not r:
                continue
            if r["status"] == "pending":
                pass
            elif r["status"] == "downloading" and _age(r.get("claimed_at"), now) >= stale_seconds:
                pass
            else:
                continue
            r["status"] = "downloading"
            r["claimed_at"] = _now()
            r["tries"] = r.get("tries", 0) + 1
            return r
        return None

    def mark(self, track_id, status: str, **fields) -> dict:
        rec = self._find(track_id)
        if not rec:
            return None
        rec["status"] = status
        rec.update(fields)
        rec["when"] = _now()
        return rec

    def counts(self) -> dict:
        c = {"total": len(self.records)}
        for r in self.records:
            c[r["status"]] = c.get(r["status"], 0) + 1
        return c

    def clear_finished(self):
        """ลบรายการที่จบแล้ว (done/paid/none/failed/low_quality) เก็บเฉพาะที่ยังทำงาน"""
        self.records = [r for r in self.records
                        if r["status"] in ("pending", "downloading")]

    def save(self):
        if self.storage and hasattr(self.storage, "save_crate"):
            self.storage.save_crate(self.records)
            return
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"records": self.records, "updated": _now()},
                      f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
