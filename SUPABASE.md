# Supabase + Login (เก็บข้อมูลถาวร + ใช้บนมือถือ)

แอป Flask **host บน Render/HF** ส่วน **ข้อมูล** (seen / feedback) เก็บบน **Supabase**
→ ปัด swipe จากมือถือ แล้ว rerank จากคอม เห็นข้อมูลชุดเดียวกัน + ไม่หายตอน restart

> Supabase = database/auth/storage — **ไม่ใช่** ที่รันโค้ด Python (ตัวแอปยัง host ที่ Render/HF)

---

## 1. สร้างตารางใน Supabase

ไป **Supabase → SQL Editor** วางแล้ว Run:

```sql
create table if not exists seen (
  track_id  bigint primary key,
  seen_at   timestamptz default now()
);

create table if not exists feedback (
  track_id    bigint primary key,
  liked       boolean not null,
  title       text,
  features    jsonb,
  updated_at  timestamptz default now()
);

-- เก็บผลรันล่าสุด (ไว้กู้ตอนรีเฟรช/เปิดจากอีกเครื่อง โดยไม่ต้อง Run ใหม่)
create table if not exists app_state (
  key         text primary key,
  value       jsonb,
  updated_at  timestamptz default now()
);
```

(แอปใช้ **upsert** ผ่าน primary key — ปัด/รันซ้ำ = อัปเดต ไม่เพิ่มแถว)

> ⚠️ ถ้าตั้ง Supabase ไว้ก่อนหน้านี้แล้ว ให้รัน **เฉพาะ** ส่วน `app_state` เพิ่ม (ตารางใหม่)

## 2. เอา URL + Key

**Supabase → Project Settings → API**
- `Project URL`            → env `SUPABASE_URL`  (เช่น `https://abcd.supabase.co`)
- `service_role` secret    → env `SUPABASE_KEY`

> ใช้ **service_role** เพราะอยู่ฝั่ง server เท่านั้น (ข้าม RLS ได้) — **ห้ามเอาไปใส่ฝั่ง browser**
> ถ้าอยากใช้ `anon` key แทน ต้องตั้ง RLS policy ให้ insert/select ตาราง seen/feedback ได้เอง

## 3. ตั้ง Login

- `APP_PASSWORD` = รหัสผ่านเข้า dashboard (ไม่ตั้ง = เปิดโล่ง เหมาะเฉพาะตอน dev)
- `SECRET_KEY`   = สุ่มยาวๆ ไว้เซ็น session (ตั้งค้างไว้ ไม่งั้น login หลุดทุกครั้งที่ restart)
  ```bash
  python3 -c "import secrets; print(secrets.token_hex(32))"
  ```

## 4. ใส่ env บน host

**Render → Environment** (หรือ HF Spaces → Settings → Secrets):
```
SUPABASE_URL=https://abcd.supabase.co
SUPABASE_KEY=<service_role key>
APP_PASSWORD=<รหัสที่ตั้งเอง>
SECRET_KEY=<token_hex>
# ถ้าใช้ LINE / likes ส่วนตัว
LINE_CHANNEL_TOKEN=...
LINE_TO=...
SC_PROFILE_URL=https://soundcloud.com/your-handle
```

เสร็จแล้ว deploy → เปิด URL → เจอหน้า **login** → ใส่รหัส → ใช้งานได้ทั้งคอม/มือถือ
ข้อมูลปัด swipe + เพลงที่เคยเสนอ จะอยู่บน Supabase ถาวร

## ใช้บนมือถือ (PWA)

เปิด URL บนมือถือ → **Add to Home Screen** → ได้ไอคอนเปิดเหมือนแอป (เต็มจอ ไม่มีแถบ browser)

---

## ทำงานยังไง (สำหรับคนแก้ต่อ)

`scfinder/storage.py` → `make_storage(cfg)`:
- มี `SUPABASE_URL` + `SUPABASE_KEY` → `SupabaseStorage` (คุยผ่าน PostgREST REST)
- ไม่มี → `None` → `SeenStore` / `FeedbackStore` ใช้ไฟล์ local เหมือนเดิม (ตอน dev)

อยากเปลี่ยน backend (เช่นไป Firebase/Postgres ตรงๆ) → เขียน class ใหม่ที่มี
`load_seen/save_seen/load_feedback/save_feedback` แล้ว return ใน `make_storage` ก็พอ
