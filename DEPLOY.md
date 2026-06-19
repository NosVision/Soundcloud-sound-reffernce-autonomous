# Deploy — เปิด Dashboard เป็น URL จริง

Dashboard (`app.py`) เป็น Flask web app ปกติ deploy ได้หลายที่ ไฟล์ที่เตรียมไว้:

| ไฟล์ | ใช้กับ |
|---|---|
| `Procfile` | Render / Railway / Heroku-style |
| `render.yaml` | Render Blueprint (กดทีเดียวจาก repo) |
| `Dockerfile` + `.dockerignore` | Hugging Face Spaces / Fly.io / Cloud Run / Railway |
| `requirements.txt` | มี `gunicorn` (production server) แล้ว |

> ⚠️ **Supabase โฮสต์ตัวนี้ไม่ได้** — มันเป็น database/auth/storage ไม่ใช่ที่รัน Python web app
> เก็บไว้ใช้ Phase 3 (เก็บผลลัพธ์/ทำ auth) ได้ ตอนนี้ใช้ Render หรือ HF Spaces

---

## ตัวเลือก A — Render (แนะนำ: ฟรี ไม่ต้องใช้บัตร ได้ public URL)

1. push repo ขึ้น GitHub ให้เรียบร้อย (สาขานี้ทำแล้ว)
2. ไป <https://render.com> → Sign up ด้วย GitHub
3. **New → Blueprint** → เลือก repo นี้ → Render อ่าน `render.yaml` ให้เอง
   (หรือ **New → Web Service** → เลือก repo → ตั้ง start command:
   `gunicorn app:app --bind 0.0.0.0:$PORT`)
4. (ถ้า likes เป็น private) ไปแท็บ **Environment** ใส่ค่า:
   - `SC_OAUTH_TOKEN` = access_token ของคุณ
   - `SC_PROFILE_URL` = `https://soundcloud.com/your-handle`
5. กด **Create** → รอ build เสร็จ → ได้ URL เช่น `https://sc-reference-finder.onrender.com`

> free tier จะ "หลับ" หลังไม่มีคนเข้า ~15 นาที เข้าครั้งแรกหลังหลับจะช้า ~30 วิ แล้วปกติ

---

## ตัวเลือก B — Hugging Face Spaces (ฟรี, ใช้ Docker)

1. ไป <https://huggingface.co/spaces> → **Create new Space**
2. **SDK = Docker** → Blank
3. push โค้ดทั้งหมดเข้า Space repo (มี `Dockerfile` แล้ว)
4. ใส่ secret ที่ **Settings → Variables and secrets**: `SC_OAUTH_TOKEN`, `SC_PROFILE_URL`
5. ได้ URL `https://<user>-<space>.hf.space`

> Dockerfile ตั้ง `PORT=7860` ให้ตรงกับที่ HF Spaces ต้องการแล้ว

---

## ตัวเลือก C — Fly.io / Railway / Cloud Run

ใช้ `Dockerfile` ตัวเดิม:
```bash
# Fly.io
fly launch        # ตอบ no ตอนถาม Postgres/Redis
fly deploy
# ตั้ง secret
fly secrets set SC_OAUTH_TOKEN=xxx SC_PROFILE_URL=https://soundcloud.com/your-handle
```

---

## รันในเครื่องตัวเอง (ก่อน deploy)

```bash
pip install -r requirements.txt
python3 app.py                       # dev server: http://127.0.0.1:5000
# หรือแบบ production:
gunicorn app:app --bind 0.0.0.0:5000
```

ลองหน้าตา/flow โดยไม่ต้องต่อเน็ต: เปิดหน้าเว็บแล้วติ๊ก **demo mode** → Run

---

## หมายเหตุความปลอดภัย

- **อย่า** commit `config.yaml` / `.env` (ถูก gitignore แล้ว) — ของลับใส่ผ่าน env บน host
- app เป็น read-only ต่อ SoundCloud + มี backoff อยู่แล้ว
- ถ้าอยากกันคนนอกเข้า dashboard: ใส่ basic auth หน้า reverse proxy หรือทำ login (Phase 3)
