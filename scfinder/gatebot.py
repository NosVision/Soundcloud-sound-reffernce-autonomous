"""
gatebot — กดผ่าน Hypeddit/Toneden download gate ด้วย Playwright  [Phase 3]

state-machine: เปิดหน้า gate -> match rule จาก gate_rules -> ทำ step ทีละขั้น
-> จับไฟล์ที่เด้งลงเครื่อง -> ตรวจ bitrate ≥ min -> done
ถ้าไม่ผ่าน (layout ใหม่/captcha/timeout) -> เก็บ screenshot + reason -> Review loop (Phase 4)

ออกแบบให้เทสต์ offline ได้: แยก "ตัวกดหน้า" (Page protocol) ออกจาก browser จริง
  - ของจริง = PlaywrightPage (persistent context, login SC ค้างไว้สำหรับ social-unlock)
  - เทสต์   = inject page ปลอม (FakePage) ผ่านพารามิเตอร์ page=
"""

import os
from collections import namedtuple

GateResult = namedtuple("GateResult", "ok path reason bitrate screenshot signature")


class GateError(Exception):
    pass


class GateBot:
    def __init__(self, rules, dest_dir: str, min_bitrate: int = 320,
                 social_unlock: bool = False, browser_profile: str = "~/.sc-dl-profile",
                 headless: bool = True):
        self.rules = rules
        self.dest_dir = dest_dir
        self.min_bitrate = min_bitrate
        self.social_unlock = social_unlock
        self.browser_profile = browser_profile
        self.headless = headless

    # ---------- ตัวเดิน step (ใช้ได้ทั้ง page จริงและปลอม) ----------
    def run_steps(self, page, steps: list):
        """เดินตาม step; คืน path ไฟล์ที่โหลดได้ (None ถ้ายังไม่ได้)"""
        downloaded = None
        for step in steps:
            act = step.get("action")
            if act == "wait":
                page.wait(float(step.get("seconds", 1)))
            elif act == "click_text":
                page.click_text(step["text"])
            elif act == "click":
                page.click(step["selector"])
            elif act == "fill":
                page.fill(step["selector"], step.get("value", ""))
            elif act == "social_all":
                if self.social_unlock:
                    for kind in ("follow", "like", "repost"):
                        try:
                            page.social(kind)
                        except Exception:
                            pass            # บาง gate ไม่มีครบทุกปุ่ม
            elif act == "expect_download":
                downloaded = page.expect_download(float(step.get("timeout", 60)))
            else:
                raise GateError(f"ไม่รู้จัก action: {act}")
        return downloaded

    # ---------- โหลด 1 เพลงผ่าน gate ----------
    def download(self, rec: dict, page=None) -> GateResult:
        from .quality import passes
        url = rec.get("target_url") or rec.get("url") or ""
        own_page = page is None
        try:
            if own_page:
                page = self._open(url)
            signature = ""
            try:
                signature = page.signature()
            except Exception:
                pass
            rule = self.rules.match(url, signature) if hasattr(self.rules, "match") else None
            if not rule:
                shot = self._shot(page, rec)
                return GateResult(False, "", "ไม่มี rule สำหรับ gate นี้ (ต้องสอน rule ใหม่)",
                                  0, shot, signature)
            path = self.run_steps(page, rule.get("steps", []))
            if not path or not os.path.exists(path):
                shot = self._shot(page, rec)
                return GateResult(False, "", f"กดผ่าน rule '{rule.get('name')}' แล้วไม่ได้ไฟล์",
                                  0, shot, signature)
            ok, br = passes(path, self.min_bitrate)
            if not ok:
                return GateResult(False, path, f"bitrate {br} < {self.min_bitrate}kbps",
                                  br, "", signature)
            return GateResult(True, path, "", br if br > 0 else 0, "", signature)
        except Exception as e:
            shot = self._shot(page, rec) if page is not None else ""
            return GateResult(False, "", f"gate error: {e}", 0, shot, "")
        finally:
            if own_page and page is not None:
                try:
                    page.close()
                except Exception:
                    pass

    def _shot(self, page, rec) -> str:
        try:
            os.makedirs(os.path.join(self.dest_dir, "_fails"), exist_ok=True)
            path = os.path.join(self.dest_dir, "_fails", f"{rec.get('track_id', 'x')}.png")
            page.screenshot(path)
            return path
        except Exception:
            return ""

    # ---------- เปิด browser จริง (lazy import; รันบน Mac) ----------
    def _open(self, url: str):
        from playwright.sync_api import sync_playwright   # lazy: ไม่บังคับมีตอน import
        return PlaywrightPage(url, self.dest_dir,
                              os.path.expanduser(self.browser_profile),
                              self.headless, sync_playwright)


class PlaywrightPage:
    """adapter หุ้ม Playwright ให้มี interface เดียวกับ FakePage (wait/click_text/...)"""

    def __init__(self, url, dest_dir, profile_dir, headless, sync_playwright):
        self.dest_dir = dest_dir
        self._downloads = []
        self._pw = sync_playwright().start()
        self.ctx = self._pw.chromium.launch_persistent_context(
            profile_dir, headless=headless, accept_downloads=True)
        self.page = self.ctx.new_page()
        self.page.on("download", self._on_download)
        self.page.goto(url, wait_until="domcontentloaded", timeout=45000)

    def _on_download(self, download):
        try:
            name = download.suggested_filename or "gate-download"
            target = os.path.join(self.dest_dir, name)
            download.save_as(target)
            self._downloads.append(target)
        except Exception:
            pass

    def wait(self, seconds):
        self.page.wait_for_timeout(int(seconds * 1000))

    def click_text(self, text):
        self.page.get_by_text(text, exact=False).first.click(timeout=15000)

    def click(self, selector):
        self.page.click(selector, timeout=15000)

    def fill(self, selector, value):
        self.page.fill(selector, value, timeout=15000)

    def social(self, kind):
        # heuristic: ปุ่ม social บน gate มักมี aria-label/ข้อความตามชนิด
        label = {"follow": "Follow", "like": "Like", "repost": "Repost"}[kind]
        self.page.get_by_text(label, exact=False).first.click(timeout=8000)

    def expect_download(self, timeout):
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._downloads:
                return self._downloads[-1]
            self.page.wait_for_timeout(500)
        return None

    def signature(self):
        try:
            return (self.page.title() or "")[:200]
        except Exception:
            return ""

    def screenshot(self, path):
        self.page.screenshot(path=path, full_page=True)

    def close(self):
        try:
            self.ctx.close()
        finally:
            self._pw.stop()
