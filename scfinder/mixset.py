"""
mixset — เรียงผลลัพธ์เป็น "ลำดับที่ mix ต่อกันได้" (harmonic set) สำหรับ DJ / Mixed In Key

หลัก: เริ่มจากเพลงหนึ่ง แล้วไล่เลือกเพลงถัดไปที่
  1) Camelot เข้ากันได้ (harmonic)  2) BPM ใกล้กันสุด
ถ้าไม่มีเพลงเข้ากันเหลือ -> เลือกเพลง BPM ใกล้สุด (ยอมข้าม key)
ได้ลำดับที่หยิบไปวางใน playlist / โหลดเข้า Mixed In Key แล้วมิกซ์ต่อได้เลย
"""

from typing import List, Optional

from .camelot import compatible_camelot


def _bpm_gap(a, b) -> float:
    if not a.bpm or not b.bpm:
        return 999.0          # ไม่มี BPM -> ถือว่าห่าง
    return abs(a.bpm - b.bpm)


def build_harmonic_set(results: List, start_index: int = 0) -> List:
    """
    คืน list เรียงใหม่ให้ mix ต่อกันลื่นที่สุด (greedy nearest harmonic neighbour)
    ไม่แก้ของเดิม — คืน list ใหม่
    """
    pool = list(results)
    if not pool:
        return []
    start_index = max(0, min(start_index, len(pool) - 1))

    ordered = [pool.pop(start_index)]
    while pool:
        cur = ordered[-1]
        compat = set(compatible_camelot(cur.camelot)) if cur.camelot else set()

        # 1) เพลงที่ harmonic เข้ากัน -> เลือก BPM ใกล้สุด
        harmonic = [t for t in pool if t.camelot and t.camelot in compat]
        if harmonic:
            nxt = min(harmonic, key=lambda t: _bpm_gap(cur, t))
        else:
            # 2) ไม่มี key เข้ากัน -> BPM ใกล้สุด (energy jump)
            nxt = min(pool, key=lambda t: _bpm_gap(cur, t))

        pool.remove(nxt)
        ordered.append(nxt)
    return ordered


def harmonic_neighbours(results: List, camelot: str) -> List:
    """กรองเฉพาะเพลงที่ mix เข้ากับ Camelot ที่ให้มา (รวม key เดียวกัน)"""
    if not camelot:
        return []
    compat = set(compatible_camelot(camelot))
    return [t for t in results if t.camelot and t.camelot in compat]
