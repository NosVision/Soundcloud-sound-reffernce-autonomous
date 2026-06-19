#!/usr/bin/env python3
"""
เทสต์ Phase 3: LINE notify (offline — mock HTTP poster)
รัน:  python3 tests/test_notify.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scfinder.config import Config
from scfinder.finder import Result
from scfinder.notify import build_summary, send_line, notify_line_results

_ok = True


def check(cond, msg):
    global _ok
    print(("  \033[32mPASS\033[0m " if cond else "  \033[31mFAIL\033[0m ") + msg)
    _ok = _ok and cond


def _r(rank, title, ms, bpm=124, cam="8A"):
    return Result(rank=rank, matched_seeds=ms, title=title, artist="dj",
                  genre="edit", bpm=bpm, key="A minor", camelot=cam,
                  plays=1000, likes=10, duration_min=3.5,
                  url=f"https://soundcloud.com/x/{rank}", track_id=rank)


RESULTS = [_r(1, "Track One", 8), _r(2, "Track Two", 5), _r(3, "Track Three", 3)]


class FakePost:
    """จำลอง requests.post — เก็บ payload ไว้ตรวจ"""
    def __init__(self, status=200):
        self.status = status
        self.called = {}

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.called = {"url": url, "headers": headers, "json": json}
        return type("R", (), {"status_code": self.status, "text": ""})()


def test_summary():
    msg = build_summary(RESULTS, top_n=2, when="2026-06-19")
    check("มี reference ใหม่ 3 เพลง" in msg, "สรุปบอกจำนวนเพลงถูก")
    check("Track One" in msg and "8A" in msg and "124bpm" in msg,
          "ข้อความมีชื่อเพลง + Camelot + BPM")
    check("อีก 1 เพลง" in msg, "บอกว่ามีอีกกี่เพลงเกิน top_n")
    check("Track Three" not in msg, "เกิน top_n ไม่โชว์")


def test_send_line_ok():
    fp = FakePost(200)
    ok, info = send_line("hello", token="TOK", to="U123", poster=fp)
    check(ok and "200" in info, "ส่งสำเร็จเมื่อ HTTP 200")
    check(fp.called["url"].endswith("/message/push"), "ยิงไป endpoint push ถูก")
    check(fp.called["headers"]["Authorization"] == "Bearer TOK",
          "ใส่ Bearer token ใน header")
    check(fp.called["json"]["to"] == "U123" and
          fp.called["json"]["messages"][0]["text"] == "hello",
          "payload to + text ถูก")


def test_send_line_guards():
    ok, info = send_line("hi", token="", to="U1", poster=FakePost())
    check(not ok and "LINE_CHANNEL_TOKEN" in info, "ไม่มี token -> ไม่ส่ง + แจ้งเหตุ")
    ok2, _ = send_line("", token="T", to="U", poster=FakePost())
    check(not ok2, "ข้อความว่าง -> ไม่ส่ง")


def test_send_line_http_error():
    ok, info = send_line("x", token="T", to="U", poster=FakePost(403))
    check(not ok and "403" in info, "HTTP 403 -> ok=False + บอก status")


def test_notify_respects_config():
    fp = FakePost(200)
    cfg = Config(line_enabled=False, line_token="T", line_to="U")
    ok, info = notify_line_results(RESULTS, cfg, poster=fp)
    check(not ok and "ปิดอยู่" in info, "enabled=false -> ไม่ส่ง")

    cfg2 = Config(line_enabled=True, line_token="T", line_to="U", notify_top_n=10)
    ok2, _ = notify_line_results(RESULTS, cfg2, when="now", poster=fp)
    check(ok2, "enabled=true + ครบ -> ส่งได้")


if __name__ == "__main__":
    print(">> Phase 3 LINE notify tests\n")
    test_summary()
    test_send_line_ok()
    test_send_line_guards()
    test_send_line_http_error()
    test_notify_respects_config()
    print()
    if _ok:
        print("\033[32m✅ ผ่านทุกข้อ\033[0m"); sys.exit(0)
    print("\033[31m❌ มีข้อไม่ผ่าน\033[0m"); sys.exit(1)
