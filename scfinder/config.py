"""
โหลด config จาก config.yaml แล้ว override ด้วย environment variables / .env

ลำดับความสำคัญ (สูงสุดชนะ):
    env var / .env   >   config.yaml   >   ค่า default ในโค้ด

env ที่รองรับ (ของลับไม่ควรอยู่ใน yaml):
    SC_OAUTH_TOKEN        -> auth.oauth_token
    SC_CLIENT_ID          -> auth.client_id_override
    SC_PROFILE_URL        -> profile_url
"""

import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


# ---------- ค่า default (ใช้เมื่อ yaml ไม่มี key นั้น) ----------
DEFAULTS = {
    "profile_url": "https://soundcloud.com/YOUR-HANDLE",
    "seed_mode": "urls",          # likes | urls | both
    "seed_urls": [],              # ลิงก์เพลงตัวอย่างที่ชอบ (seed แบบเลือกเอง)
    "max_seeds": 60,
    "target": 120,
    "related_per_seed": 50,
    "sleep": 0.4,
    "duration": {"min_minutes": 0, "max_minutes": 0},   # 0 = ไม่จำกัด
    "bpm": {"min": 0, "max": 0},                         # 0 = ไม่จำกัด (Phase 2)
    "dedupe": {"enabled": True, "seen_file": "seen.json"},
    "auth": {"oauth_token": "", "client_id_override": ""},
    "output": "sc_references.csv",
    "demo_mode": False,           # True = ใช้ mock data (ไม่ต่อเน็ต) ลอง dashboard ได้เลย
}


@dataclass
class Config:
    profile_url: str = DEFAULTS["profile_url"]
    seed_mode: str = DEFAULTS["seed_mode"]
    seed_urls: List[str] = field(default_factory=list)
    max_seeds: int = DEFAULTS["max_seeds"]
    target: int = DEFAULTS["target"]
    related_per_seed: int = DEFAULTS["related_per_seed"]
    sleep: float = DEFAULTS["sleep"]
    duration_min: float = 0.0     # นาที, 0 = ไม่จำกัด
    duration_max: float = 0.0     # นาที, 0 = ไม่จำกัด
    bpm_min: float = 0.0          # 0 = ไม่จำกัด
    bpm_max: float = 0.0          # 0 = ไม่จำกัด
    dedupe_enabled: bool = True
    seen_file: str = "seen.json"
    oauth_token: str = ""
    client_id_override: str = ""
    output: str = DEFAULTS["output"]
    demo_mode: bool = False

    def to_public_dict(self) -> dict:
        """สำหรับส่งให้ dashboard — ตัด secret (token) ออก"""
        d = asdict(self)
        d.pop("oauth_token", None)
        d.pop("client_id_override", None)
        return d


def _load_dotenv(path: str = ".env") -> None:
    """โหลด .env แบบง่ายๆ (ไม่ต้องพึ่ง python-dotenv) เข้า os.environ"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


def load_config(path: str = "config.yaml") -> Config:
    """อ่าน config.yaml (ถ้ามี) + override ด้วย .env / env vars"""
    _load_dotenv()

    data = dict(DEFAULTS)
    if yaml and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        _deep_update(data, loaded)

    dur = data.get("duration") or {}
    bpm = data.get("bpm") or {}
    dedupe = data.get("dedupe") or {}
    auth = data.get("auth") or {}

    cfg = Config(
        profile_url=data["profile_url"],
        seed_mode=data["seed_mode"],
        seed_urls=list(data.get("seed_urls") or []),
        max_seeds=int(data["max_seeds"]),
        target=int(data["target"]),
        related_per_seed=int(data["related_per_seed"]),
        sleep=float(data["sleep"]),
        duration_min=float(dur.get("min_minutes", 0) or 0),
        duration_max=float(dur.get("max_minutes", 0) or 0),
        bpm_min=float(bpm.get("min", 0) or 0),
        bpm_max=float(bpm.get("max", 0) or 0),
        dedupe_enabled=bool(dedupe.get("enabled", True)),
        seen_file=str(dedupe.get("seen_file", "seen.json")),
        oauth_token=str(auth.get("oauth_token", "") or ""),
        client_id_override=str(auth.get("client_id_override", "") or ""),
        output=data["output"],
        demo_mode=bool(data.get("demo_mode", False)),
    )

    # env override (secret + profile)
    cfg.oauth_token = os.environ.get("SC_OAUTH_TOKEN", cfg.oauth_token)
    cfg.client_id_override = os.environ.get("SC_CLIENT_ID", cfg.client_id_override)
    cfg.profile_url = os.environ.get("SC_PROFILE_URL", cfg.profile_url)
    return cfg


def _deep_update(base: dict, new: dict) -> None:
    for k, v in new.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
