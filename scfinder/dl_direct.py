"""
dl_direct — โหลดเพลงทางตรง (ไม่ผ่าน gate)  [Phase 2]

  route=direct_sc   : SC เปิด Free Download -> GET /tracks/{id}/download
                      -> redirectUri -> โหลดไฟล์ original เต็มคุณภาพ
  route=direct_file : ลิงก์ไฟล์ตรง (.mp3/.wav/Dropbox raw) -> GET เซฟ

คืน DLResult(ok, path, reason, bitrate) — ตรวจ bitrate ทุกไฟล์ก่อนถือว่าสำเร็จ
(Mediafire/Drive ที่เป็นหน้า landing จะได้ HTML -> ไม่ผ่าน -> ส่งเข้า Review loop)
"""

import os
import re
from collections import namedtuple

import requests

from .quality import passes

API = "https://api-v2.soundcloud.com"
UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

DLResult = namedtuple("DLResult", "ok path reason bitrate")

_CT_EXT = {
    "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/wav": ".wav",
    "audio/x-wav": ".wav", "audio/wave": ".wav", "audio/aiff": ".aiff",
    "audio/x-aiff": ".aiff", "audio/flac": ".flac", "audio/x-flac": ".flac",
    "audio/mp4": ".m4a", "audio/x-m4a": ".m4a", "application/zip": ".zip",
}


def sanitize(name: str) -> str:
    """ชื่อไฟล์ปลอดภัย: ตัดอักขระต้องห้าม (รองรับ Thai/emoji), จำกัดความยาว"""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", name or "").strip()
    name = re.sub(r"\s+", " ", name)
    return name[:120] or "track"


def _filename(rec: dict, ext: str) -> str:
    base = sanitize(f"{rec.get('artist', '')} - {rec.get('title', '')}".strip(" -"))
    return f"{base}{ext}"


def _ext_from(content_type: str, url: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in _CT_EXT:
        return _CT_EXT[ct]
    m = re.search(r"\.(mp3|wav|aiff?|flac|m4a|zip)(?:\?|$)", (url or "").lower())
    return f".{m.group(1)}" if m else ".mp3"


class DirectDownloader:
    def __init__(self, client=None, session=None, min_bitrate: int = 320):
        self.client = client
        self.session = session or (getattr(client, "session", None) or requests.Session())
        self.min_bitrate = min_bitrate

    def download(self, rec: dict, dest_dir: str) -> DLResult:
        os.makedirs(dest_dir, exist_ok=True)
        if rec.get("route") == "direct_sc":
            return self._download_sc(rec, dest_dir)
        return self._fetch_to_file(rec.get("target_url", ""), rec, dest_dir)

    def _download_sc(self, rec: dict, dest_dir: str) -> DLResult:
        if not self.client:
            return DLResult(False, "", "ไม่มี client สำหรับ SC download", 0)
        tid = rec.get("track_id")
        try:
            cid = self.client.client_id
            r = self.session.get(f"{API}/tracks/{tid}/download",
                                 params={"client_id": cid}, headers=UA, timeout=20)
            if r.status_code != 200:
                return DLResult(False, "", f"download endpoint HTTP {r.status_code} "
                                           f"(อาจปิด DL แล้ว)", 0)
            redirect = (r.json() or {}).get("redirectUri")
            if not redirect:
                return DLResult(False, "", "ไม่มี redirectUri (ไม่เปิด Free DL จริง)", 0)
            return self._fetch_to_file(redirect, rec, dest_dir)
        except Exception as e:
            return DLResult(False, "", f"sc download error: {e}", 0)

    def _fetch_to_file(self, url: str, rec: dict, dest_dir: str) -> DLResult:
        if not url:
            return DLResult(False, "", "ไม่มีลิงก์ไฟล์", 0)
        try:
            with self.session.get(url, stream=True, timeout=60, headers=UA) as resp:
                if resp.status_code != 200:
                    return DLResult(False, "", f"file HTTP {resp.status_code}", 0)
                ct = resp.headers.get("Content-Type", "")
                if ct.split(";")[0].strip().lower() in ("text/html", "application/xhtml+xml"):
                    return DLResult(False, "", "ได้หน้า HTML ไม่ใช่ไฟล์ "
                                               "(host นี้ต้องผ่าน gatebot/Review)", 0)
                ext = _ext_from(ct, url)
                path = os.path.join(dest_dir, _filename(rec, ext))
                if os.path.exists(path):
                    ok, br = passes(path, self.min_bitrate)
                    reason = "" if ok else f"ไฟล์เดิม bitrate {br} < {self.min_bitrate}"
                    return DLResult(ok, path, reason, br if br > 0 else 0)
                tmp = path + ".part"
                with open(tmp, "wb") as f:
                    for chunk in resp.iter_content(8192):
                        if chunk:
                            f.write(chunk)
                os.replace(tmp, path)
        except Exception as e:
            return DLResult(False, "", f"fetch error: {e}", 0)

        ok, br = passes(path, self.min_bitrate)
        if not ok:
            return DLResult(False, path, f"bitrate {br} < {self.min_bitrate}kbps", br)
        return DLResult(True, path, "", br if br > 0 else 0)
