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
from .camelot import to_camelot


@dataclass
class Result:
    rank: int
    matched_seeds: int
    title: str
    artist: str
    genre: str
    bpm: float
    key: str
    camelot: str
    plays: int
    likes: int
    duration_min: float
    url: str
    track_id: int
    pref: float = 0.0          # คะแนนรสนิยมที่เรียนรู้ (Phase 4) — ไม่อยู่ใน CSV หลัก

    def as_row(self) -> list:
        return [self.rank, self.matched_seeds, self.title, self.artist,
                self.genre, self.bpm, self.key, self.camelot,
                self.plays, self.likes, self.duration_min, self.url]


COLUMNS = ["rank", "matched_seeds", "title", "artist", "genre",
           "bpm", "key", "camelot", "plays", "likes", "duration_min", "url"]


def _dur_min(track: dict) -> float:
    return round((track.get("duration", 0) or 0) / 60000, 1)


def _bpm(track: dict) -> float:
    """ดึง BPM จาก metadata ของ SC (uploader ใส่มา) — 0 ถ้าไม่มี"""
    raw = track.get("bpm")
    try:
        return round(float(raw), 1) if raw else 0.0
    except (TypeError, ValueError):
        return 0.0


def _key(track: dict) -> str:
    """ดึง key signature จาก metadata ของ SC — '' ถ้าไม่มี"""
    return str(track.get("key_signature") or "").strip()


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

    # ---- filter BPM (เฉพาะเพลงที่มี BPM ในข้อมูล) ----
    bmin, bmax = cfg.bpm_min, cfg.bpm_max
    if bmin or bmax:
        before = len(pool)
        for tid in list(pool):
            b = _bpm(pool[tid])
            if b == 0:                       # ไม่มี BPM -> เก็บไว้ (อย่าตัดทิ้งมั่ว)
                continue
            if (bmin and b < bmin) or (bmax and b > bmax):
                pool.pop(tid)
        log(f"filter BPM {bmin or '-'}–{bmax or '-'}: {before} -> {len(pool)} เพลง")

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
        key = _key(t)
        results.append(Result(
            rank=i,
            matched_seeds=hits.get(t["id"], 0),
            title=t.get("title", ""),
            artist=(t.get("user") or {}).get("username", ""),
            genre=t.get("genre", ""),
            bpm=_bpm(t),
            key=key,
            camelot=to_camelot(key),
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


def group_by_bpm(results: List[Result], width: int = 10) -> dict:
    """จัดกลุ่มตามช่วง BPM (เช่น 120–129) -> {'120-129': [Result,...]}; 'no-bpm' สำหรับเพลงไม่มี BPM"""
    groups: dict = {}
    for r in results:
        if not r.bpm:
            groups.setdefault("no-bpm", []).append(r)
            continue
        lo = int(r.bpm // width) * width
        groups.setdefault(f"{lo}-{lo + width - 1}", []).append(r)
    return groups


def group_by_camelot(results: List[Result]) -> dict:
    """จัดกลุ่มตาม Camelot code -> {'8A': [Result,...]}; 'no-key' สำหรับเพลงไม่มีคีย์"""
    groups: dict = {}
    for r in results:
        groups.setdefault(r.camelot or "no-key", []).append(r)
    return groups
