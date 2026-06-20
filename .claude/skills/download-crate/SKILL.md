---
name: download-crate
description: โหลดเพลงในคิว crate ของ SC Reference Finder (Hypeddit/Playwright, ไฟล์ ≥320kbps). ใช้เมื่อผู้ใช้สั่ง "โหลดเพลงในคิว", "เคลียร์คิวโหลด", "download crate", หรืออยากเติม gate rule ใหม่เมื่อ Hypeddit gate เปลี่ยน layout.
---

# download-crate

โหลดเพลงที่อยู่ในคิว `crate` (เพลงที่กด ⬇ จาก dashboard/มือถือ) ลงเครื่องนี้ —
ได้ไฟล์คุณภาพ **≥320kbps** จาก SC Free-Download หรือผ่าน Hypeddit/Toneden gate

## ขั้นตอน

1. **รันรอบเดียว** เพื่อโหลดทุกเพลงที่ pending:
   ```bash
   python3 download_agent.py --once
   ```
   - `direct_sc` / `direct_file` → โหลดไฟล์ original ตรง
   - `gate` → เปิด Playwright กดผ่าน gate ตาม `gate_rules.json`
   - `paid` / `none` → ข้าม (mark ไว้)

2. **อ่านผลสรุป** ที่ท้าย output (`สรุปคิว: {...}`) แล้วรายงานผู้ใช้:
   - เสร็จกี่เพลง (`done`), คุณภาพต่ำ (`low_quality`), พัง (`failed`)
   - ไฟล์อยู่ใน `downloads/` (หรือ `download.dir` ใน config)

3. **ถ้ามีเพลง `failed` ที่เป็น gate** (Hypeddit layout ใหม่/เปลี่ยน) — สอน rule ใหม่:
   - ดู `reason` + screenshot ใน `downloads/_fails/<track_id>.png`
   - เปิด `target_url` ของเพลงนั้นด้วย **Playwright MCP** แล้วไล่กดผ่าน gate ทีละขั้น
     (รอ timer → กดปุ่ม Free Download → social-unlock ถ้าจำเป็น → จับปุ่ม Download)
   - สรุปลำดับ step ที่ใช้ได้ เป็น rule ใหม่ใน `gate_rules.json` (ดู `scfinder/gate_rules.py`
     สำหรับรูปแบบ step: `wait` / `click_text` / `click` / `social_all` / `expect_download`)
   - รัน `--once` ซ้ำ ให้ state-machine ทำเองได้อัตโนมัติรอบหน้า

## หมายเหตุ
- ต้องมี `playwright` + chromium: `pip install playwright && playwright install chromium`
- เพลง gate ที่บังคับ follow/like/repost จะปลดล็อกได้ก็ต่อเมื่อ `download.social_unlock: true`
  และ login SoundCloud ค้างไว้ใน browser profile (`download.browser_profile`)
- **กฎเหล็ก:** ทุกไฟล์ต้อง ≥320kbps — ถ้าได้ต่ำกว่า ระบบ mark `low_quality` ไม่ถือว่าสำเร็จ
- daemon (โหลดอัตโนมัติตลอด): `python3 download_agent.py --watch`
