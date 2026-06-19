"""
notify — แจ้งเตือนผลรันเข้า LINE (Phase 3)

ใช้ LINE Messaging API (push message)
  *** LINE Notify ปิดบริการแล้ว (มี.ค. 2025) จึงใช้ Messaging API แทน ***

ตั้งครั้งเดียว:
  1. สร้าง Messaging API channel ที่ https://developers.line.biz/console/
  2. เอา "Channel access token (long-lived)" -> ใส่ env LINE_CHANNEL_TOKEN
  3. แอด bot เป็นเพื่อน แล้วเอา userId ของเรา (หรือ groupId) -> env LINE_TO
     (หา userId ได้จาก webhook event หรือ https://developers.line.biz เครื่องมือ)
"""

import requests

LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
MAX_LEN = 4800   # LINE text limit ~5000 เผื่อไว้


def build_summary(results, top_n: int = 10, when: str = "", demo: bool = False) -> str:
    """ประกอบข้อความสรุปผลรอบนี้"""
    n = len(results)
    head = "🎧 SC Reference Finder"
    if demo:
        head += " (DEMO)"
    when_part = f" — {when}" if when else ""
    lines = [head, f"มี reference ใหม่ {n} เพลงรอคัด{when_part}", ""]

    for r in results[:top_n]:
        tags = []
        if r.camelot:
            tags.append(r.camelot)
        if r.bpm:
            tags.append(f"{r.bpm:g}bpm")
        tag = f" [{' / '.join(tags)}]" if tags else ""
        lines.append(f"{r.rank}. {r.title} — {r.artist}{tag}  ×{r.matched_seeds}")

    if n > top_n:
        lines.append(f"…อีก {n - top_n} เพลงในไฟล์ CSV")

    msg = "\n".join(lines)
    return msg[:MAX_LEN]


def send_line(message: str, token: str, to: str, poster=None) -> tuple:
    """
    ส่ง push message เข้า LINE
    คืน (ok: bool, info: str) — poster แทนได้เพื่อเทสต์ (default = requests.post)
    """
    if not token or not to:
        return False, "ไม่ได้ตั้ง LINE_CHANNEL_TOKEN / LINE_TO"
    if not message:
        return False, "ข้อความว่าง"
    poster = poster or requests.post
    try:
        resp = poster(
            LINE_PUSH_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"to": to, "messages": [{"type": "text", "text": message}]},
            timeout=15,
        )
    except Exception as e:                      # network ฯลฯ
        return False, f"ส่งไม่สำเร็จ: {e}"
    ok = getattr(resp, "status_code", 0) == 200
    body = ""
    if not ok:
        try:
            body = " " + resp.text[:200]
        except Exception:
            pass
    return ok, f"HTTP {getattr(resp, 'status_code', '?')}{body}"


def notify_line_results(results, cfg, when: str = "", demo: bool = False,
                        poster=None) -> tuple:
    """สร้างข้อความ + ส่ง ตาม config (สะดวกเรียกจาก autorun / dashboard)"""
    if not cfg.line_enabled:
        return False, "LINE notify ปิดอยู่ (notify.line.enabled = false)"
    msg = build_summary(results, top_n=cfg.notify_top_n, when=when, demo=demo)
    return send_line(msg, cfg.line_token, cfg.line_to, poster=poster)
