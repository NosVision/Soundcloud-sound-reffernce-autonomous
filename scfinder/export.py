"""
export — แปลงผลลัพธ์เป็นฟอร์แมตต่างๆ เพื่อเอาไปต่อยอด (Mixed In Key / DJ software / playlist)

ฟอร์แมต:
  - mixedinkey_csv : CSV หัวตารางแนว Mixed In Key collection (Artist/Title/Key=Camelot/BPM/Energy/Comments)
  - m3u8           : playlist (.m3u8) ของลิงก์ SoundCloud — เปิดต่อใน player/บางตัว import ได้
  - json           : โครงสร้างเต็ม เผื่อเขียน integration เอง

ทุกฟังก์ชันคืน "string" (ไม่เขียนไฟล์เอง) -> เอาไปเขียน/ส่งผ่าน HTTP ได้สะดวก
"""

import csv
import io
import json
from typing import List


def to_mixedinkey_csv(results: List) -> str:
    """
    CSV ที่หัวตารางเลียนแบบ Mixed In Key collection export
    Key = Camelot (เช่น 8A) ซึ่งเป็นภาษาเดียวกับ MIK -> เอาไปอ้างอิง/จัด crate ต่อได้ทันที
    """
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Artist", "Title", "Key", "BPM", "Energy", "Comments", "URL"])
    for r in results:
        comments = f"matched_seeds={r.matched_seeds}; key={r.key or '-'}; genre={r.genre or '-'}"
        w.writerow([r.artist, r.title, r.camelot or "", r.bpm or "",
                    "", comments, r.url])
    return buf.getvalue()


def to_m3u8(results: List) -> str:
    """playlist .m3u8 (extended) ของลิงก์ SoundCloud"""
    lines = ["#EXTM3U"]
    for r in results:
        secs = int(round(r.duration_min * 60)) if r.duration_min else -1
        tag = f"{r.artist} - {r.title}"
        if r.camelot or r.bpm:
            tag += f" [{r.camelot or '?'} / {r.bpm or '?'}bpm]"
        lines.append(f"#EXTINF:{secs},{tag}")
        lines.append(r.url)
    return "\n".join(lines) + "\n"


def to_json(results: List) -> str:
    return json.dumps([r.__dict__ for r in results], ensure_ascii=False, indent=2)


# ทะเบียน exporter -> ใช้เลือกจาก dashboard/CLI ได้ (ต่อยอดเพิ่มฟอร์แมตง่าย)
EXPORTERS = {
    "mixedinkey": (to_mixedinkey_csv, "text/csv", "sc_references_mixedinkey.csv"),
    "m3u8":       (to_m3u8, "audio/x-mpegurl", "sc_references.m3u8"),
    "json":       (to_json, "application/json", "sc_references.json"),
}
