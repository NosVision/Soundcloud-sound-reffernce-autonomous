"""
SeenStore — จำ track id ที่เคยเสนอไปแล้ว เพื่อรอบหน้าไม่เสนอซ้ำ (dedupe ข้ามรอบ)
เก็บเป็น JSON ง่ายๆ:  {"seen": [id, id, ...], "updated": "ISO-8601"}
"""

import json
import os
from datetime import datetime, timezone
from typing import Iterable, Set


class SeenStore:
    def __init__(self, path: str = "seen.json", enabled: bool = True):
        self.path = path
        self.enabled = enabled
        self.seen: Set[int] = set()
        if enabled:
            self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self.seen = {int(x) for x in data.get("seen", [])}
        except (json.JSONDecodeError, ValueError, OSError):
            self.seen = set()

    def is_seen(self, track_id: int) -> bool:
        return self.enabled and int(track_id) in self.seen

    def add_many(self, track_ids: Iterable[int]) -> None:
        for t in track_ids:
            self.seen.add(int(t))

    def save(self) -> None:
        if not self.enabled:
            return
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                {"seen": sorted(self.seen),
                 "updated": datetime.now(timezone.utc).isoformat()},
                f, ensure_ascii=False, indent=2,
            )
        os.replace(tmp, self.path)  # atomic
