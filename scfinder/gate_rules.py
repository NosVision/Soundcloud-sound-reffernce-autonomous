"""
gate_rules — Case library ของ download gate (ระบบฉลาดขึ้นเอง)  [Phase 4]

เก็บ "pattern ของแต่ละแบบ gate -> ลำดับ step กดผ่าน" ไว้ใน gate_rules.json
+ สถิติ (เพลงติด route ไหนบ่อย) + รายการ fail (layout ใหม่ที่ยังไม่มี rule)

flow การเรียนรู้:
  gatebot เจอ gate -> match() หา rule -> ทำตาม step
  ถ้าไม่ผ่าน (layout ใหม่/เปลี่ยน) -> record_failure() เก็บ signature+screenshot
  -> คน/Claude(Playwright MCP) ดูใน Review loop -> add_rule() เขียน rule ใหม่
  -> ครั้งหน้า match เจอ ทำเองอัตโนมัติ

step actions ที่ gatebot เข้าใจ:
  {"action":"wait","seconds":N}
  {"action":"click_text","text":"Free Download"}   # คลิกปุ่มตามข้อความ
  {"action":"click","selector":"css..."}
  {"action":"social_all"}                            # follow+like+repost (เฉพาะ social_unlock=true)
  {"action":"expect_download","timeout":60}          # รอไฟล์เด้งลงเครื่อง
"""

import json
import os
from datetime import datetime, timezone

# rule เริ่มต้น (baseline) — ครอบ Hypeddit/Toneden แบบทั่วไป
DEFAULT_RULES = {
    "rules": [
        {
            "name": "hypeddit-generic",
            "domains": ["hypeddit.com", "hypeddit.co"],
            "signature": "",
            "steps": [
                {"action": "wait", "seconds": 3},
                {"action": "click_text", "text": "Free Download"},
                {"action": "social_all"},
                {"action": "wait", "seconds": 2},
                {"action": "click_text", "text": "Download"},
                {"action": "expect_download", "timeout": 60},
            ],
        },
        {
            "name": "toneden-generic",
            "domains": ["toneden.io"],
            "signature": "",
            "steps": [
                {"action": "wait", "seconds": 3},
                {"action": "click_text", "text": "Download"},
                {"action": "social_all"},
                {"action": "wait", "seconds": 2},
                {"action": "click_text", "text": "Download"},
                {"action": "expect_download", "timeout": 60},
            ],
        },
    ],
    "stats": {},        # {route: count}
    "failures": [],     # [{url, reason, signature, when}]
}


def _now():
    return datetime.now(timezone.utc).isoformat()


class GateRules:
    def __init__(self, path: str = "gate_rules.json"):
        self.path = path
        self.data = None
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.data = None
        if not self.data:
            self.data = json.loads(json.dumps(DEFAULT_RULES))  # deep copy
        self.data.setdefault("rules", [])
        self.data.setdefault("stats", {})
        self.data.setdefault("failures", [])

    @property
    def rules(self):
        return self.data["rules"]

    def match(self, url: str, signature: str = ""):
        """หา rule แรกที่ domain อยู่ใน url (และ signature ตรงถ้า rule กำหนดไว้)"""
        low = (url or "").lower()
        sig = (signature or "").lower()
        best = None
        for rule in self.data["rules"]:
            if not any(d in low for d in rule.get("domains", [])):
                continue
            rsig = (rule.get("signature") or "").lower()
            if rsig:
                if rsig in sig:
                    return rule          # signature ตรง = แม่นสุด เอาเลย
                continue
            best = best or rule          # rule ทั่วไป (ไม่ผูก signature) เก็บไว้เป็น fallback
        return best

    def add_rule(self, rule: dict):
        """เพิ่ม/แทนที่ rule (key = name)"""
        name = rule.get("name")
        self.data["rules"] = [r for r in self.data["rules"] if r.get("name") != name]
        self.data["rules"].append(rule)

    def record_stat(self, route: str):
        self.data["stats"][route] = self.data["stats"].get(route, 0) + 1

    def record_failure(self, url: str, reason: str, signature: str = ""):
        self.data["failures"].append({"url": url, "reason": reason,
                                      "signature": signature[:500], "when": _now()})
        self.data["failures"] = self.data["failures"][-100:]   # เก็บล่าสุด 100

    def save(self):
        tmp = f"{self.path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
