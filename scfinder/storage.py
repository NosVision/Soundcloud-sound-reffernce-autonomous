"""
storage — ชั้นเก็บข้อมูลที่สลับได้ระหว่าง local JSON กับ Supabase  [deploy]

ทำไมต้องมี: บน host (Render/HF) ไฟล์ local หายตอน restart
-> เก็บ seen / feedback ลง Supabase Postgres แทน เพื่อให้ข้อมูลคงอยู่ + ใช้ข้ามอุปกรณ์ (มือถือ)

make_storage(cfg):
  - มี SUPABASE_URL + SUPABASE_KEY  -> SupabaseStorage
  - ไม่มี                            -> None (SeenStore/FeedbackStore ใช้ไฟล์ local เหมือนเดิม)

SupabaseStorage คุยผ่าน PostgREST (REST) ด้วย requests — ไม่ต้องลง lib เพิ่ม
inject getter/poster ได้เพื่อเทสต์ offline
"""

import requests


def make_storage(cfg):
    if getattr(cfg, "supabase_url", "") and getattr(cfg, "supabase_key", ""):
        return SupabaseStorage(cfg.supabase_url, cfg.supabase_key)
    return None


class SupabaseStorage:
    def __init__(self, url, key, getter=None, poster=None):
        self.base = url.rstrip("/") + "/rest/v1"
        self.key = key
        self._get = getter or requests.get
        self._post = poster or requests.post

    def _headers(self, extra=None):
        h = {"apikey": self.key, "Authorization": f"Bearer {self.key}",
             "Content-Type": "application/json"}
        if extra:
            h.update(extra)
        return h

    # ---------- seen ----------
    def load_seen(self) -> set:
        try:
            r = self._get(f"{self.base}/seen?select=track_id",
                          headers=self._headers(), timeout=15)
            if getattr(r, "status_code", 0) != 200:
                return set()
            return {int(x["track_id"]) for x in r.json()}
        except Exception:
            return set()

    def save_seen(self, ids) -> bool:
        rows = [{"track_id": int(i)} for i in ids]
        if not rows:
            return True
        try:
            self._post(f"{self.base}/seen",
                       headers=self._headers({"Prefer": "resolution=merge-duplicates"}),
                       json=rows, timeout=30)
            return True
        except Exception:           # Supabase ล่ม -> ไม่ทำให้ run พัง
            return False

    # ---------- feedback ----------
    def load_feedback(self) -> list:
        try:
            r = self._get(f"{self.base}/feedback?select=*",
                          headers=self._headers(), timeout=15)
            if getattr(r, "status_code", 0) != 200:
                return []
            out = []
            for x in r.json():
                out.append({
                    "track_id": x["track_id"],
                    "liked": bool(x.get("liked")),
                    "title": x.get("title", "") or "",
                    "features": x.get("features") or {},
                    "when": x.get("updated_at", "") or "",
                })
            return out
        except Exception:
            return []

    def save_feedback(self, records) -> bool:
        rows = [{
            "track_id": r["track_id"],
            "liked": bool(r["liked"]),
            "title": r.get("title", "") or "",
            "features": r.get("features") or {},
        } for r in records]
        if not rows:
            return True
        try:
            self._post(f"{self.base}/feedback",
                       headers=self._headers({"Prefer": "resolution=merge-duplicates"}),
                       json=rows, timeout=30)
            return True
        except Exception:
            return False
