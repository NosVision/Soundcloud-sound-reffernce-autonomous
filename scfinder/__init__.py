"""
scfinder — SoundCloud reference finder (Phase 1)

โครงสร้าง:
  config.py  — โหลด config.yaml + override ด้วย env / .env
  client.py  — คุยกับ api-v2.soundcloud.com (ของจริง)
  mockclient — client ปลอมไว้ลองใช้ offline / demo บน dashboard
  store.py   — dedupe ข้ามรอบ (seen.json)
  finder.py  — pipeline หลัก: seeds -> related -> co-occurrence rank -> filter -> dedupe
"""

from .config import Config, load_config            # noqa: F401
from .finder import find_references, Result         # noqa: F401
from .store import SeenStore                        # noqa: F401
from .camelot import to_camelot, compatible_camelot  # noqa: F401
from .mixset import build_harmonic_set              # noqa: F401
