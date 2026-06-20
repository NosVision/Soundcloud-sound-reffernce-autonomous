"""
quality — ตรวจคุณภาพไฟล์เสียง ให้ผ่านเกณฑ์ ≥ min_bitrate (default 320kbps)  [Phase 2/3]

กฎเหล็กของโปรเจกต์: ไฟล์ที่โหลดมาต้อง ≥ 320kbps เท่านั้น
  - lossless (wav/flac/aiff) -> ถือว่าเกินเกณฑ์เสมอ
  - mp3/m4a -> อ่าน bitrate จริงด้วย mutagen
  - อ่านไม่ได้ (ไม่มี mutagen) -> bitrate = -1 = "ไม่รู้" -> ไม่ reject (กันพังตอน lib ไม่ครบ)
"""

import os

LOSSLESS_EXT = (".wav", ".aif", ".aiff", ".flac", ".alac", ".ape")


def bitrate_kbps(path: str) -> int:
    """คืน bitrate โดยประมาณ (kbps); lossless -> 9999 ; -1 ถ้าอ่านไม่ได้/ไม่มี mutagen"""
    ext = os.path.splitext(path)[1].lower()
    if ext in LOSSLESS_EXT:
        return 9999
    try:
        from mutagen import File as MutagenFile
    except ImportError:
        return -1
    try:
        audio = MutagenFile(path)
        br = getattr(getattr(audio, "info", None), "bitrate", 0) or 0
        if br:
            return int(br / 1000)
    except Exception:
        pass
    return -1


def passes(path: str, min_bitrate: int = 320):
    """(ok, bitrate) — ok เมื่อ bitrate ≥ min หรืออ่านค่าไม่ได้ (-1 = ไม่รู้ -> ไม่ตัดทิ้ง)"""
    br = bitrate_kbps(path)
    return (br < 0 or br >= min_bitrate), br
