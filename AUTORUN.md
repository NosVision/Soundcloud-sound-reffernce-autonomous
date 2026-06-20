# Autorun + LINE แจ้งเตือน (Phase 3)

รันอัตโนมัติเป็นรอบๆ บน Mac Mini แล้วเด้งเข้า LINE ว่า "มี reference ใหม่ N เพลงรอคัด"

## 1. ตั้ง LINE Messaging API (ครั้งเดียว)

> ⚠️ **LINE Notify ปิดบริการแล้ว (มี.ค. 2025)** — ใช้ Messaging API แทน (ฟรีเหมือนกัน)

1. ไป <https://developers.line.biz/console/> → สร้าง **Provider** → สร้าง **Messaging API channel**
2. แท็บ **Messaging API** → กดออก **Channel access token (long-lived)** → คัดลอก
3. **แอด bot เป็นเพื่อน** (สแกน QR ในหน้า channel)
4. หา **userId** ของตัวเอง:
   - วิธีง่าย: แท็บ Messaging API จะมี "Your user ID" ของเจ้าของ channel
   - หรือส่งข้อความหา bot แล้วดู `userId` จาก webhook event
5. ใส่ลง `.env`:
   ```
   LINE_CHANNEL_TOKEN=<token ที่คัดลอกมา>
   LINE_TO=<userId หรือ groupId>
   ```
   (ตั้งครบ 2 ตัว = เปิดแจ้งเตือนอัตโนมัติ ไม่ต้องแก้ config.yaml)

ลองส่งดู:
```bash
python3 autorun.py          # รันจริง 1 รอบ + ส่ง LINE
# หรือกดปุ่ม 📱 LINE บน dashboard หลัง Run
```

## 2. ตั้งเวลาอัตโนมัติ

### A) crontab (ง่ายสุด)
```bash
crontab -e
# ทุกวันจันทร์ 9:00 น.
0 9 * * 1  cd /path/to/Soundcloud-sound-reffernce-autonomous && /usr/bin/python3 autorun.py >> autorun.log 2>&1
```

### B) launchd (แนะนำบน macOS — รันแม้ปิด terminal)
สร้างไฟล์ `~/Library/LaunchAgents/com.nosvision.screffinder.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.nosvision.screffinder</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/path/to/Soundcloud-sound-reffernce-autonomous/autorun.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/path/to/Soundcloud-sound-reffernce-autonomous</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key><integer>1</integer>
    <key>Hour</key><integer>9</integer>
    <key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardOutPath</key><string>/tmp/screffinder.log</string>
  <key>StandardErrorPath</key><string>/tmp/screffinder.err</string>
</dict>
</plist>
```
โหลดเข้า:
```bash
launchctl load ~/Library/LaunchAgents/com.nosvision.screffinder.plist
```

> launchd ไม่เห็น `.env` อัตโนมัติ — ใส่ `LINE_CHANNEL_TOKEN` ฯลฯ เป็น `EnvironmentVariables`
> ใน plist หรือ source `.env` ใน wrapper script ก็ได้

## 3. แนะนำเปิด dedupe

`dedupe.enabled: true` (default) → แต่ละรอบเสนอ **เฉพาะเพลงใหม่** ที่ไม่เคยเห็น
ทำให้ LINE เด้งเฉพาะของใหม่จริงๆ ไม่ซ้ำของเดิม

---

# Auto-Downloader (คิว crate → โหลดไฟล์ ≥320kbps)

กด ⬇ บน dashboard (รวมบนมือถือ) → เพลงเข้าคิว `crate` → **เครื่อง Mac นี้โหลดไฟล์ให้อัตโนมัติ**
(SC Free-DL ตรง / ผ่าน Hypeddit/Toneden gate ด้วย Playwright) ดูภาพรวมการออกแบบใน `README.md`

## ติดตั้งครั้งแรก
```bash
pip install -r requirements.txt
playwright install chromium          # ตัว browser ที่ใช้กดผ่าน gate
# (ครั้งแรก) login SoundCloud ค้างไว้ใน profile — ถ้าจะใช้ social-unlock:
#   เปิด chromium ด้วย profile เดียวกับ download.browser_profile แล้ว login ทิ้งไว้
```

## รัน
```bash
python3 download_agent.py --once     # โหลดทุกเพลงในคิวรอบเดียว (cron / สั่งเอง / Claude skill)
python3 download_agent.py --watch    # daemon: poll คิวทุก download.poll_seconds วินาที
```

## ตั้ง launchd ให้ `--watch` รันค้างตลอด (แนะนำ)
สร้าง `~/Library/LaunchAgents/com.nosvision.screffinder.downloader.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.nosvision.screffinder.downloader</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/path/to/Soundcloud-sound-reffernce-autonomous/download_agent.py</string>
    <string>--watch</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/path/to/Soundcloud-sound-reffernce-autonomous</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/screffinder-dl.log</string>
  <key>StandardErrorPath</key><string>/tmp/screffinder-dl.err</string>
</dict>
</plist>
```
```bash
launchctl load ~/Library/LaunchAgents/com.nosvision.screffinder.downloader.plist
```
> ต้องตั้ง `SUPABASE_URL`+`SUPABASE_KEY` (เป็น `EnvironmentVariables` ใน plist หรือ source `.env`)
> เพื่อให้ agent เห็นคิวเดียวกับที่มือถือกด ⬇ เข้ามา

## เพลงที่ติด gate ใหม่ (Review loop)
- เพลงที่ Playwright กดไม่ผ่าน (layout เปลี่ยน/captcha) → สถานะ `failed` + screenshot ใน `downloads/_fails/`
- ดูได้ในแท็บ **คิวโหลด → ต้องดู** บน dashboard → กด **ลองใหม่** ได้
- อยากให้ฉลาดขึ้น: ใช้ Claude Code skill **`download-crate`** ไล่กด gate ใหม่ผ่าน Playwright MCP
  แล้วบันทึกเป็น rule ใน `gate_rules.json` → ครั้งหน้า state-machine ทำเอง
