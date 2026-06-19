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
