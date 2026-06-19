"""
finder — pipeline หลัก (รักษา co-occurrence เป็นหัวใจตาม README)

    seeds (likes / urls / both)
       └─ related ของทุก seed ──► นับ co-occurrence (matched_seeds)
              └─ ตัด seed เอง ► filter ความยาว ► dedupe ข้ามรอบ
                     └─ sort by (matched_seeds, plays) ► top TARGET
"""

import csv
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from .store import SeenStore


@dataclass
class Result:
    rank: int
    matched_seeds: int
    title: str
    artist: str
    genre: str
    plays: int
    likes: int
    duration_min: float
    url: str
    track_id: int

    def as_row(self) -> list:
        return [self.rank, self.matched_seeds, self.title, self.artist,
                self.genre, self.plays, self.likes, self.duration_min, self.url]


COLUMNS = ["rank", "matched_seeds", "title", "artist",
           "genre", "plays", "likes", "duration_min", "url"]


def _dur_min(track: dict) -> float:
    return round((track.get("duration", 0) or 0) / 60000, 1)


def build_seeds(client, cfg, log: Callable[[str], None]) -> list:
    """รวม seed ตาม seed_mode: likes / urls / both"""
    seeds, seen_ids = [], set()

    def add(t):
        if t and t.get("kind") == "track" and t["id"] not in seen_ids:
            seen_ids.add(t["id"])
            seeds.append(t)

    mode = cfg.seed_mode
    if mode in ("urls", "both"):
        for u in cfg.seed_urls:
            u = (u or "").strip()
            if not u:
                continue
            t = client.resolve_track(u)
            if t:
                add(t)
                log(f"  + seed จากลิงก์: {t.get('title','?')}")
            else:
                log(f"  ! ข้ามลิงก์ (resolve ไม่ได้/ไม่ใช่เพลง): {u}")
            time.sleep(cfg.sleep)

    if mode in ("likes", "both"):
        uid = client.resolve_user_id(cfg.profile_url)
        for t in client.get_liked_tracks(uid, cfg.max_seeds):
            add(t)
        log(f"  + seed จาก likes: {len(seeds)} เพลง (รวมทุก source)")

    return seeds[:max(cfg.max_seeds, len(cfg.seed_urls))]


def find_references(client, cfg, store: Optional[SeenStore] = None,
                    log: Optional[Callable[[str], None]] = None) -> List[Result]:
    log = log or (lambda *_: None)

    seeds = build_seeds(client, cfg, log)
    if not seeds:
        raise ValueError("ไม่มี seed เลย — ใส่ seed_urls หรือ profile_url ที่ถูกต้อง")
    log(f"seeds ทั้งหมด: {len(seeds)} เพลง")

    seed_ids = {s["id"] for s in seeds}
    pool, hits = {}, {}
    for s in seeds:
        for rel in client.get_related(s["id"], cfg.related_per_seed):
            tid = rel["id"]
            pool[tid] = rel
            hits[tid] = hits.get(tid, 0) + 1
        time.sleep(cfg.sleep)

    for sid in seed_ids:                 # ไม่เสนอเพลงที่เป็น seed อยู่แล้ว
        pool.pop(sid, None)

    # ---- filter ความยาว ----
    dmin, dmax = cfg.duration_min, cfg.duration_max
    if dmin or dmax:
        before = len(pool)
        for tid in list(pool):
            m = _dur_min(pool[tid])
            if (dmin and m < dmin) or (dmax and m > dmax):
                pool.pop(tid)
        log(f"filter ความยาว {dmin or '-'}–{dmax or '-'} นาที: "
            f"{before} -> {len(pool)} เพลง")

    # ---- dedupe ข้ามรอบ ----
    if store and store.enabled:
        before = len(pool)
        for tid in list(pool):
            if store.is_seen(tid):
                pool.pop(tid)
        log(f"dedupe ข้ามรอบ (seen.json): {before} -> {len(pool)} เพลง")

    ranked = sorted(
        pool.values(),
        key=lambda t: (hits.get(t["id"], 0), t.get("playback_count", 0) or 0),
        reverse=True,
    )[:cfg.target]

    results = []
    for i, t in enumerate(ranked, 1):
        results.append(Result(
            rank=i,
            matched_seeds=hits.get(t["id"], 0),
            title=t.get("title", ""),
            artist=(t.get("user") or {}).get("username", ""),
            genre=t.get("genre", ""),
            plays=t.get("playback_count", 0) or 0,
            likes=t.get("likes_count", 0) or 0,
            duration_min=_dur_min(t),
            url=t.get("permalink_url", ""),
            track_id=t["id"],
        ))

    if store and store.enabled:
        store.add_many(r.track_id for r in results)

    return results


def write_csv(results: List[Result], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for r in results:
            w.writerow(r.as_row())
