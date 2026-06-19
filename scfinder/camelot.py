"""
camelot — แปลง musical key -> Camelot code + หาคีย์ที่ mix เข้ากัน (harmonic mixing)

Camelot wheel: เลข 1–12 + ตัวอักษร A (minor) / B (major)
DJ ใช้คัดเพลงให้ mix เข้ากันแบบไม่ขัดหู:
    เข้ากันได้ = เลขเดียวกัน (สลับ A/B), หรือเลข ±1 ตัวอักษรเดิม
"""

from typing import List, Optional

# pitch class: C=0 ... B=11 (รวม enharmonic)
_ROOT_PC = {
    "C": 0, "B#": 0,
    "C#": 1, "DB": 1,
    "D": 2,
    "D#": 3, "EB": 3,
    "E": 4, "FB": 4,
    "F": 5, "E#": 5,
    "F#": 6, "GB": 6,
    "G": 7,
    "G#": 8, "AB": 8,
    "A": 9,
    "A#": 10, "BB": 10,
    "B": 11, "CB": 11,
}

# pitch class -> Camelot (major = ฝั่ง B, minor = ฝั่ง A)
_MAJOR_PC_TO_CAM = {0: "8B", 7: "9B", 2: "10B", 9: "11B", 4: "12B", 11: "1B",
                    6: "2B", 1: "3B", 8: "4B", 3: "5B", 10: "6B", 5: "7B"}
_MINOR_PC_TO_CAM = {9: "8A", 4: "9A", 11: "10A", 6: "11A", 1: "12A", 8: "1A",
                    3: "2A", 10: "3A", 5: "4A", 0: "5A", 7: "6A", 2: "7A"}


def parse_key(s: Optional[str]):
    """
    แปลงสตริงคีย์หลายรูปแบบ -> (pitch_class, mode)
    รองรับ: 'Cmaj', 'A minor', 'Am', 'F#min', 'Bb', 'Abmaj', 'C# Major', ...
    คืน None ถ้า parse ไม่ได้
    """
    if not s:
        return None
    u = str(s).strip().upper().replace("♯", "#").replace("♭", "B").replace(" ", "")
    if not u:
        return None

    # root: ลอง 2 ตัวอักษรก่อน (เช่น C#, BB) แล้วค่อย 1 ตัว
    root = None
    if len(u) >= 2 and u[:2] in _ROOT_PC:
        root = u[:2]
    elif u[:1] in _ROOT_PC:
        root = u[:1]
    if root is None:
        return None

    suffix = u[len(root):]
    # mode
    if "MIN" in suffix or suffix == "M" or suffix in ("MOLL",):
        mode = "minor"
    elif suffix in ("", "MAJ", "MAJOR", "DUR") or "MAJ" in suffix:
        mode = "major"
    elif suffix.startswith("M"):       # เผื่อ 'Mi' ฯลฯ
        mode = "minor"
    else:
        mode = "major"
    return _ROOT_PC[root], mode


def to_camelot(key: Optional[str]) -> str:
    """key string -> Camelot code (เช่น '8A'); '' ถ้าไม่รู้"""
    parsed = parse_key(key)
    if not parsed:
        return ""
    pc, mode = parsed
    table = _MINOR_PC_TO_CAM if mode == "minor" else _MAJOR_PC_TO_CAM
    return table.get(pc, "")


def split_camelot(code: str):
    """'10A' -> (10, 'A'); None ถ้าผิดรูป"""
    if not code or len(code) < 2:
        return None
    letter = code[-1].upper()
    if letter not in ("A", "B"):
        return None
    try:
        num = int(code[:-1])
    except ValueError:
        return None
    if not 1 <= num <= 12:
        return None
    return num, letter


def compatible_camelot(code: str) -> List[str]:
    """
    คืนลิสต์ Camelot code ที่ mix เข้ากันได้ (รวมตัวมันเอง):
      - ตัวเดียวกัน
      - เลขเดิม สลับ A/B (relative major/minor)
      - เลข +1 / -1 ตัวอักษรเดิม (วน 1..12)
    """
    sp = split_camelot(code)
    if not sp:
        return []
    num, letter = sp
    other = "B" if letter == "A" else "A"
    up = num % 12 + 1
    down = (num - 2) % 12 + 1
    return [f"{num}{letter}", f"{num}{other}", f"{up}{letter}", f"{down}{letter}"]


def is_compatible(a: str, b: str) -> bool:
    """a กับ b mix เข้ากันไหม (harmonic)"""
    return bool(a) and b in compatible_camelot(a)
