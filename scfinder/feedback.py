"""
feedback — เก็บ like/dislike (ปัดซ้าย/ขวา) + โมเดลเรียนรู้รสนิยม  [Phase 4]

หลักการ (เบาๆ ไม่ต้องพึ่ง ML lib):
  - เก็บทุกครั้งที่ผู้ใช้กด 👍/👎 พร้อม "feature" ของเพลง (genre / artist / camelot / bpm bucket)
  - เรียน like-rate ของแต่ละ feature value (smoothed) -> รู้ว่าชอบ genre ไหน คีย์ไหน BPM ช่วงไหน
  - ให้คะแนน pref ของเพลงใหม่ = เฉลี่ยถ่วงน้ำหนักของ like-rate ของ feature ที่เพลงนั้นมี
  - เอา pref ไป "เสริม" การจัดอันดับ โดย co-occurrence (matched_seeds) ยังเป็นหัวใจหลัก

ออกแบบให้ต่อยอดง่าย: อยากเปลี่ยนไปใช้ logistic regression / embedding ก็แทนที่ PreferenceModel ได้เลย
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional


# ---------- ดึง feature จากเพลง ----------
def track_features(t: dict) -> Dict[str, str]:
    """t = dict ของเพลง (จาก Result.__dict__ หรือ track) -> feature สำหรับเรียนรู้"""
    feats = {}
    g = (t.get("genre") or "").strip().lower()
    a = (t.get("artist") or t.get("user", {}).get("username", "") if isinstance(t.get("user"), dict)
         else t.get("artist") or "").strip().lower()
    cam = (t.get("camelot") or "").strip()
    bpm = t.get("bpm") or 0
    if g:
        feats["genre"] = g
    if a:
        feats["artist"] = a
    if cam:
        feats["camelot"] = cam
    try:
        bpm = float(bpm)
    except (TypeError, ValueError):
        bpm = 0
    if bpm:
        lo = int(bpm // 10) * 10
        feats["bpm"] = f"{lo}s"      # เช่น 120s = 120-129
    return feats


class FeedbackStore:
    """เก็บ record การปัด -> feedback.json"""

    def __init__(self, path: str = "feedback.json"):
        self.path = path
        self.records: List[dict] = []
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                self.records = json.load(f).get("records", [])
        except (json.JSONDecodeError, OSError):
            self.records = []

    def rated_ids(self) -> set:
        return {r["track_id"] for r in self.records}

    def record(self, track: dict, liked: bool) -> dict:
        """บันทึก 1 การปัด (ถ้าเคยปัดเพลงนี้แล้ว = อัปเดต)"""
        tid = track.get("track_id") or track.get("id")
        rec = {
            "track_id": tid,
            "liked": bool(liked),
            "title": track.get("title", ""),
            "features": track_features(track),
            "when": datetime.now(timezone.utc).isoformat(),
        }
        self.records = [r for r in self.records if r["track_id"] != tid]
        self.records.append(rec)
        return rec

    def save(self):
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"records": self.records,
                       "updated": datetime.now(timezone.utc).isoformat()},
                      f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def counts(self) -> Dict[str, int]:
        likes = sum(1 for r in self.records if r["liked"])
        return {"total": len(self.records), "likes": likes,
                "dislikes": len(self.records) - likes}


class PreferenceModel:
    """เรียน like-rate ต่อ feature value แล้วให้คะแนนเพลงใหม่"""

    def __init__(self, records: List[dict]):
        # tally[kind][value] = [like, dislike]
        self.tally: Dict[str, Dict[str, List[int]]] = {}
        for r in records:
            liked = r["liked"]
            for kind, val in (r.get("features") or {}).items():
                slot = self.tally.setdefault(kind, {}).setdefault(val, [0, 0])
                slot[0 if liked else 1] += 1

    def _like_rate(self, kind: str, val: str) -> Optional[float]:
        slot = self.tally.get(kind, {}).get(val)
        if not slot:
            return None
        like, dislike = slot
        return (like + 1) / (like + dislike + 2)        # Laplace smoothing

    def score(self, track: dict) -> float:
        """
        คะแนนรสนิยมของเพลง ~[-1, 1]  (0 = ไม่รู้/กลางๆ)
        เฉลี่ยถ่วงน้ำหนักด้วย "ความมั่นใจ" (เคยปัด feature นั้นมากี่ครั้ง)
        """
        feats = track_features(track) if "features" not in track else track["features"]
        num = den = 0.0
        for kind, val in feats.items():
            rate = self._like_rate(kind, val)
            if rate is None:
                continue
            slot = self.tally[kind][val]
            n = slot[0] + slot[1]
            w = n / (n + 2)                 # support weight
            num += (rate - 0.5) * 2 * w
            den += w
        return round(num / den, 4) if den else 0.0

    def profile(self, top: int = 5) -> dict:
        """สรุป taste: feature ไหนชอบ/ไม่ชอบสุด (เฉพาะที่มี support พอ)"""
        out: Dict[str, list] = {}
        for kind, vals in self.tally.items():
            scored = []
            for val, (like, dislike) in vals.items():
                n = like + dislike
                rate = (like + 1) / (n + 2)
                scored.append({"value": val, "like_rate": round(rate, 2),
                               "n": n, "likes": like, "dislikes": dislike})
            scored.sort(key=lambda x: (x["like_rate"], x["n"]), reverse=True)
            out[kind] = scored[:top]
        return out


def annotate_and_rank(results: List, records: List[dict], weight: float = 0.5) -> List:
    """
    ใส่ .pref ให้ทุก Result + จัดอันดับใหม่แบบ blend (co-occurrence ยังนำ)
      blend = matched_seeds + weight * pref * scale
    pref เป็นแค่ตัว "ดัน" ภายในกลุ่ม matched_seeds ใกล้กัน ไม่กลบสัญญาณหลัก
    """
    model = PreferenceModel(records)
    scale = 1.0   # pref ~[-1,1] -> ปรับได้ ±weight ระดับ
    for r in results:
        r.pref = model.score(r.__dict__)
    ranked = sorted(
        results,
        key=lambda r: (r.matched_seeds + weight * r.pref * scale,
                       r.plays),
        reverse=True,
    )
    for i, r in enumerate(ranked, 1):
        r.rank = i
    return ranked
