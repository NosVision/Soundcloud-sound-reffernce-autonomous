"""
resolver — จำแนก "เส้นทางโหลด" ของแต่ละเพลง ก่อนเอาเข้า Crate  [Phase 1]

ทำไม: เพลง reference แต่ละเพลงโหลดได้ไม่เหมือนกัน
  - บางเพลง SC เปิดปุ่ม Free Download -> ได้ไฟล์ original เต็มคุณภาพเลย (ง่ายสุด)
  - บางเพลงต้องผ่าน Hypeddit / Toneden gate (กด follow/like/timer) -> Playwright (Phase 3)
  - บางเพลงลิงก์ไฟล์ตรง (Mediafire/Drive) -> โหลด GET ตรง
  - บางเพลงขายอย่างเดียว (Bandcamp/Beatport) -> ข้าม
รู้เส้นทางก่อน = agent เลือกวิธีโหลดถูก + ครั้งหน้าไม่ต้องเดาใหม่

classify(track) -> (route, target_url)
  route ∈ {direct_sc, direct_file, gate, paid, none}
  target_url = ลิงก์ gate/ไฟล์ที่จะเอาไปโหลด ('' สำหรับ direct_sc/none)
"""

import re

ROUTES = ("direct_sc", "direct_file", "gate", "paid", "none")

# gate = หน้า download-gate ที่ต้องกดผ่าน (free DL คุณภาพเต็ม) -> Playwright
GATE_DOMAINS = ("hypeddit.com", "hypeddit.co", "toneden.io", "fanlink.to",
                "found.ee", "push.fm", "pixl.to", "theartist.fm", "gate.fm")
# direct_file = ลิงก์ไฟล์ตรง โหลด GET ได้เลย
DIRECT_FILE_HINTS = ("mediafire.com", "dropbox.com", "drive.google.com",
                     "wetransfer.com", "we.tl", "dropbox.com/s",
                     ".mp3", ".wav", ".aiff", ".aif", ".flac", ".zip", ".rar")
# paid = ร้านขายเพลง -> ข้าม (mark paid)
PAID_DOMAINS = ("bandcamp.com", "beatport.com", "itunes.apple.com",
                "music.apple.com", "open.spotify.com", "spotify.com",
                "amazon.", "junodownload.com", "traxsource.com",
                "tidal.com", "deezer.com")

_URL_RE = re.compile(r"https?://[^\s)>\]\"']+")


def _links_in(text: str):
    return _URL_RE.findall(text or "")


def classify(track: dict):
    """จำแนก track (Result.__dict__ หรือ raw SC track) -> (route, target_url)"""
    # 1) SC เปิด Free Download = ได้ original file เต็มคุณภาพ (ทางที่ดีสุด)
    if track.get("downloadable") or track.get("has_downloads_left"):
        return ("direct_sc", "")

    # รวมลิงก์ผู้สมัคร: purchase_url ก่อน แล้วลิงก์ใน description
    candidates = []
    purchase = (track.get("purchase_url") or "").strip()
    if purchase:
        candidates.append(purchase)
    candidates += _links_in(track.get("description", ""))

    def _match(hosts):
        for u in candidates:
            low = u.lower()
            if any(h in low for h in hosts):
                return u
        return ""

    # 2) gate (free DL ผ่านประตู) — เลือกก่อน paid เสมอ (อยากได้ของฟรีคุณภาพเต็ม)
    g = _match(GATE_DOMAINS)
    if g:
        return ("gate", g)
    # 3) ไฟล์ตรง
    d = _match(DIRECT_FILE_HINTS)
    if d:
        return ("direct_file", d)
    # 4) ร้านขาย -> ข้าม
    p = _match(PAID_DOMAINS)
    if p:
        return ("paid", p)
    # 5) มี purchase_url แต่ไม่รู้จัก host -> ลองเปิดด้วย Playwright (มัก gate รูปแบบใหม่)
    if purchase:
        return ("gate", purchase)
    return ("none", "")


def enrich(track: dict, client=None) -> dict:
    """
    เติม purchase_url / description / downloadable ให้ครบก่อน classify
    (related payload มักไม่มี field พวกนี้ -> re-fetch track เต็มผ่าน client)
    """
    url = track.get("url") or track.get("permalink_url") or ""
    needs = "description" not in track and not track.get("purchase_url")
    if needs and client is not None and url and hasattr(client, "resolve_track"):
        try:
            full = client.resolve_track(url)
        except Exception:
            full = None
        if full:
            track = dict(track)
            track["purchase_url"] = (full.get("purchase_url") or "").strip()
            track["description"] = full.get("description") or ""
            track["downloadable"] = bool(full.get("downloadable")
                                         or full.get("has_downloads_left"))
    return track


def resolve_route(track: dict, client=None):
    """enrich แล้ว classify -> (route, target_url)"""
    return classify(enrich(track, client))
