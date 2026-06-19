# SoundCloud Sound Reference — Autonomous

หา **reference เพลง** ที่ตรงแนวที่เราชอบจาก SoundCloud โดยอัตโนมัติ
ใช้ "likes" ของเราเป็น seed → ดึง related → จัดอันดับ → export เป็น list ให้คัดต่อ

เป้าหมายปลายทาง: ให้มันรันเองเป็นรอบๆ (เช่นทุกสัปดาห์บน Mac Mini) แล้วส่ง list เพลงใหม่ๆ
ที่ตรงแนวเข้ามาเตรียมไว้ — โดยที่เราแค่เข้ามาคัดตอน edit travel vlog / mix set

---

## แนวคิด (ทำไมออกแบบแบบนี้)

**1. ทำไม SoundCloud ไม่ใช่ Spotify**
แนวที่เราฟังคือ edit / bootleg / remix culture (NOKIA esentrik edit, COME THRU edit,
Slow Grind NIE Remix, YO-ZU edit ฯลฯ) เพลงพวกนี้ **ไม่มีบน Spotify หรือ Last.fm**
มันเกิดและอยู่บน SoundCloud อย่างเดียว เพราะงั้น source ที่ตรงแนวที่สุดคือ SC เอง

**2. ทำไมใช้ co-occurrence ในการ rank**
แทนที่จะเชื่อ related ของเพลงเดียว เราดึง related ของ **ทุกเพลงที่ like** มารวมกัน
เพลงไหนโผล่ซ้ำใน related ของหลาย seed = อยู่ตรง "แกน" รสนิยมเรา ไม่ใช่ outlier
→ คอลัมน์ `matched_seeds` ยิ่งสูง ยิ่งตรงแนว

**3. ทำไมฟรี**
ใช้ `api-v2.soundcloud.com` ตัวเดียวกับที่หน้าเว็บ SC เรียกใช้เอง
เราแค่ "ยืม" `client_id` จาก browser = เหมือนเปิดเว็บปกติ ไม่มี billing ไม่ต้องสมัคร app
(official API ปิดรับสมัครอยู่ แต่ก็ฟรีอยู่ดี เลยไม่เกี่ยว)

---

## โครงสร้าง (หลัง Phase 1)

```
.
├── app.py                   # 🆕 Dashboard เว็บ (Flask) — วางลิงก์/ปรับ config/กด Run/โหลด CSV
├── sc_reference_finder.py   # CLI: อ่าน config.yaml -> รัน pipeline -> CSV
├── scfinder/                # 🆕 core package
│   ├── config.py            #   โหลด config.yaml + .env / env override
│   ├── client.py            #   SoundCloud api-v2 client (read-only + backoff)
│   ├── mockclient.py        #   client ปลอม (demo/offline ไม่ต่อเน็ต)
│   ├── store.py             #   dedupe ข้ามรอบ (seen.json)
│   ├── camelot.py           # 🆕 key -> Camelot + หาคีย์ที่ mix เข้ากัน (Phase 2)
│   ├── mixset.py            # 🆕 เรียงเป็นลำดับ mix ต่อกัน (harmonic set)
│   ├── export.py            # 🆕 export: Mixed In Key CSV / M3U8 / JSON
│   ├── notify.py            # 🆕 แจ้งเตือนเข้า LINE (Messaging API) — Phase 3
│   ├── feedback.py          # 🆕 like/dislike store + โมเดลเรียนรู้รสนิยม — Phase 4
│   ├── storage.py           # 🆕 สลับเก็บข้อมูล local JSON ↔ Supabase (deploy)
│   └── finder.py            #   pipeline: seeds -> related -> co-occurrence rank (+bpm/key/camelot)
├── templates/login.html     # 🆕 หน้า login (เปิดเมื่อตั้ง APP_PASSWORD)
├── static/{manifest.webmanifest,sw.js,icon.svg}  # 🆕 PWA — ติดตั้งเป็นแอปบนมือถือได้
├── autorun.py               # 🆕 รัน 1 รอบสำหรับ cron/launchd + ส่ง LINE (Phase 3)
├── AUTORUN.md               # 🆕 คู่มือตั้ง LINE + cron/launchd
├── SUPABASE.md              # 🆕 คู่มือ Supabase + login + ใช้บนมือถือ
├── templates/ , static/     # 🆕 หน้า dashboard (HTML/CSS/JS) ธีมดำ-ส้ม / ขาว-ส้ม
├── config.example.yaml      # 🆕 ตัวอย่าง config (คัดลอกเป็น config.yaml)
├── .env.example             # 🆕 ตัวอย่างใส่ของลับ (oauth/client_id)
├── requirements.txt         # 🆕 requests / PyYAML / Flask
├── tests/test_finder.py     # 🆕 เทสต์ pipeline (offline)
└── sc_references.csv         # output (ถูกสร้างหลังรัน)
```

---

## การใช้งาน

### ติดตั้ง + ตั้งค่า (ครั้งแรก)

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml      # แล้วแก้ค่าในนี้
# (ถ้ามีของลับ) cp .env.example .env แล้วใส่ SC_OAUTH_TOKEN / SC_CLIENT_ID
```

ใน `config.yaml` เลือก seed ได้ 3 แบบ:
- `seed_mode: urls` → วาง **ลิงก์เพลงที่ชอบ** ใน `seed_urls` (ไม่ต้อง login)
- `seed_mode: likes` → ดึง likes จาก `profile_url`
- `seed_mode: both` → ใช้ทั้งคู่

### เชื่อมต่อ SoundCloud จริง (ปิด demo)

ไม่ต้องสมัคร API / ไม่ต้องผูกบัตร — ใช้ `api-v2` ตัวเดียวกับเว็บ SC (ขุด `client_id` ให้อัตโนมัติ)

**ทางลัด — กดทีเดียวจบ:**
```bash
python3 quickstart.py
```
มันจะติดตั้ง deps → ถามลิงก์เพลงที่ชอบ (หรือโปรไฟล์) → เขียน `config.yaml` ให้ → ปิด demo → กด `doctor.py` เช็คการเชื่อมต่อ → เปิด dashboard/CLI ให้เลย

**หรือตั้งเอง:**
1. ใน `config.yaml` ตั้ง **`demo_mode: false`**
2. ใส่ seed: `seed_urls:` (ลิงก์เพลงจริง) หรือ `profile_url:` (ใช้ likes)
3. (เฉพาะกรณี) ใส่ใน `.env`:
   - `SC_OAUTH_TOKEN` — ถ้า likes เป็น **private** (DevTools → Network → `session` → `access_token`)
   - `SC_CLIENT_ID` — ถ้า auto scrape ไม่เจอ (DevTools → Network → request `api-v2` → param `client_id`)
4. **เช็คว่าต่อติดไหม** ก่อนรันจริง:
   ```bash
   python3 doctor.py
   ```
   มันไล่เช็คทีละ step (network → client_id → resolve seed → related) แล้วบอกว่าพังตรงไหน + วิธีแก้

### A) Dashboard เว็บ (แนะนำ) 🆕

```bash
python3 app.py
# เปิด http://127.0.0.1:5000
```
วางลิงก์เพลงที่ชอบ → ปรับ config → กด **Run** → ได้ตารางเรียงตาม `matched_seeds` → กด **⬇ CSV**
มีปุ่มสลับธีม **ดำ-ส้ม / ขาว-ส้ม** และ **demo mode** (ลองได้เลยไม่ต้องต่อเน็ต)

> 🌐 อยากเปิดเป็น **URL จริง** (Render / Hugging Face Spaces / Fly.io)? ดู **[DEPLOY.md](DEPLOY.md)** — มี `Procfile` / `render.yaml` / `Dockerfile` เตรียมไว้ให้แล้ว
>
> 🔐📱 อยากมี **login + เก็บข้อมูลถาวร (Supabase) + ใช้บนมือถือ (PWA)**? ดู **[SUPABASE.md](SUPABASE.md)**
> ตั้ง `APP_PASSWORD` = มีหน้า login · ตั้ง `SUPABASE_URL`+`SUPABASE_KEY` = seen/feedback ไม่หายตอน restart + sync ข้ามอุปกรณ์ · เปิดบนมือถือกด **Add to Home Screen** ได้เลย

### B) CLI

```bash
python3 sc_reference_finder.py     # อ่าน config.yaml -> sc_references.csv
```

ได้ `sc_references.csv` → เปิดใน Sheets / Obsidian → เรียงตาม `matched_seeds` → คัด 100 ตัวบน

### ลองแบบ offline / รันเทสต์

```bash
python3 test_offline.py        # demo: mock data -> ตัวอย่างผลลัพธ์
python3 tests/test_finder.py   # เทสต์ pipeline (co-occurrence/filter/dedupe/CSV)
```

### Config ที่ปรับได้ (ใน `config.yaml`)

| key | ความหมาย | default |
|---|---|---|
| `profile_url` | profile SoundCloud (เมื่อใช้ likes) | ต้องใส่เอง |
| `seed_mode` | `urls` / `likes` / `both` | `urls` |
| `seed_urls` | ลิงก์เพลงที่ชอบ (seed) | `[]` |
| `max_seeds` | ดึง likes ล่าสุดกี่เพลง | 60 |
| `target` | จำนวนเพลงใน output | 120 |
| `related_per_seed` | related สูงสุดต่อ 1 seed | 50 |
| `sleep` | หน่วงกัน rate limit (วินาที) | 0.4 |
| `duration.min_minutes` / `max_minutes` | filter ความยาว (0 = ไม่จำกัด) | 0 / 0 |
| `bpm.min` / `bpm.max` | filter BPM (0 = ไม่จำกัด) — Phase 2 | 0 / 0 |
| `dedupe.enabled` / `seen_file` | dedupe ข้ามรอบ | true / `seen.json` |
| `auth.oauth_token` | ใส่ถ้า likes private (หรือผ่าน `.env`) | ว่าง |
| `auth.client_id_override` | ใส่ถ้า auto หา client_id ไม่เจอ | ว่าง |
| `demo_mode` | ใช้ข้อมูลปลอม (ไม่ต่อเน็ต) | false |

> ทำไม `max_seeds` ไม่เอา likes ทั้งหมด: เรามี ~1,745 likes ถ้า seed หมดจะยิง API หลายพันครั้ง
> = ช้า + เสี่ยงโดน rate limit แบน. likes ล่าสุด 60–80 = รสนิยมปัจจุบัน กำลังพอดี

---

## Output: คอลัมน์ CSV

| คอลัมน์ | คือ |
|---|---|
| `rank` | อันดับ |
| `matched_seeds` | โผล่ใน related ของกี่ seed (**ตัวชี้วัดหลัก** — สูง = ตรงแนวสุด) |
| `title` / `artist` | ชื่อเพลง / คนทำ |
| `bpm` | BPM (จาก metadata ของ uploader — Phase 2) |
| `key` | คีย์ดนตรี (ดิบจาก SC) |
| `camelot` | คีย์แบบ Camelot wheel (เช่น `8A`) — ภาษาเดียวกับ Mixed In Key |
| `genre` | แนว (ตามที่ uploader ใส่ — ไม่ค่อยน่าเชื่อถือ) |
| `plays` / `likes` | ยอดเล่น / ยอดไลก์ |
| `duration_min` | ความยาว (นาที) |
| `url` | ลิงก์ SoundCloud |

---

## 🎚️ Harmonic mixing / ต่อยอด Mixed In Key (Phase 2)

ทุกเพลงถูก enrich **BPM + key → Camelot code** อัตโนมัติ (BPM/key มาจาก metadata ที่ uploader ใส่บน SC)
แล้วเอาไปใช้มิกซ์ต่อได้ทันที:

**บน Dashboard**
- คอลัมน์ `bpm` / `key (Camelot)` ในตาราง — กรองด้วยช่อง **BPM ขั้นต่ำ/สูงสุด**
- **คลิกที่ Camelot badge** (เช่น `8A`) → กรองเหลือเฉพาะเพลงที่ mix เข้ากันได้ (harmonic)
- ปุ่ม **🎚 Harmonic order** → เรียงผลเป็น "ลำดับที่ mix ต่อกันลื่นที่สุด" (Camelot + BPM ใกล้)
- ปุ่ม export: **⬇ CSV**, **⬇ Mixed In Key** (Key=Camelot), **⬇ M3U8** (playlist)

**ฟอร์แมต export** (CLI สร้างให้อัตโนมัติ + Dashboard มีปุ่ม)
| ไฟล์ | เอาไปใช้ |
|---|---|
| `sc_references.csv` | ตารางเต็ม (มี bpm/key/camelot) |
| `sc_references_mixedinkey.csv` | หัวตารางแนว Mixed In Key (Artist/Title/**Key=Camelot**/BPM/Energy) |
| `sc_references.m3u8` | playlist ลิงก์ SoundCloud เปิดต่อใน player |

**Camelot rule (harmonic):** เข้ากันได้ = เลขเดียวกัน (สลับ A/B) หรือเลข ±1 ตัวอักษรเดิม
โค้ดอยู่ที่ `scfinder/camelot.py` (แปลงคีย์) + `scfinder/mixset.py` (เรียงลำดับมิกซ์) + `scfinder/export.py` (ฟอร์แมต)

> หมายเหตุ: บางเพลงบน SC ไม่มี BPM/key ใน metadata → คอลัมน์จะว่าง (ไม่ถูกตัดทิ้ง)
> อยากได้ครบทุกเพลง: Phase 2 ต่อไปคือต่อ GetSongBPM / Tunebat / วิเคราะห์เองด้วย librosa (hook เตรียมไว้ใน `client.py`)

---

## 🔥 Swipe & เรียนรู้รสนิยม (Phase 4)

แบบ Tinder ของเพลง — ผมไปหาเพลงมาให้ คุณฟังแล้วปัด ระบบเรียนรู้เอง

**บน Dashboard** (หลัง Run กดปุ่ม **🔥 Swipe**)
- การ์ดทีละเพลง มี **SoundCloud player ฟังในตัว** → กด 👍/👎 หรือลูกศร **←/→**
- ทุกการปัดถูกเก็บใน `feedback.json` + อัปเดต **taste profile** ทันที (genre/คีย์/BPM/ศิลปินที่ชอบ)
- กด **✨ ตามรสนิยม** → จัดอันดับผลใหม่โดยเอารสนิยมที่เรียนรู้มา "เสริม"

**หลักการเรียนรู้** (`scfinder/feedback.py` — เบา ไม่ต้องใช้ ML lib)
- เรียน *like-rate* ของแต่ละ feature (genre / camelot / bpm bucket / artist) แบบ smoothed
- คะแนน `pref` ของเพลง = เฉลี่ยถ่วงน้ำหนักด้วยความมั่นใจ (ปัด feature นั้นมากี่ครั้ง)
- re-rank แบบ blend: `matched_seeds + 0.5 × pref` → **co-occurrence ยังเป็นหัวใจ** pref แค่ดันในกลุ่มที่ matched ใกล้กัน

> ออกแบบให้ต่อยอดง่าย: อยากเปลี่ยนไปใช้ logistic regression / embedding แทน → สลับ `PreferenceModel` ตัวเดียวจบ

API ที่เปิดไว้ (เผื่อทำ mobile app ต่อ): `POST /api/feedback`, `GET /api/profile`, `POST /api/rerank`

---

## Pipeline ทำงานยังไง (สำหรับคนจะมาแก้ต่อ)

```
PROFILE_URL
   └─ resolve ──────────────► user_id
                                 └─ /users/{id}/track_likes (paginate) ──► seeds[]
seeds[] ──┬─ /tracks/{id}/related ──► candidates
          │  (วนทุก seed, นับ co-occurrence)
          ▼
   pool{} + hit_count{}
          └─ เอา seed ออก → sort by (matched_seeds, plays) → top TARGET → CSV
```

ฟังก์ชันหลักใน `sc_reference_finder.py`:
- `get_client_id()` — ขุด client_id จาก JS bundle ของหน้า SC อัตโนมัติ
- `resolve_user_id()` — แปลง profile URL → user id
- `get_liked_tracks()` — ดึง likes (paginate ผ่าน `next_href`)
- `get_related()` — ดึง related ต่อ 1 track
- `main()` — ประกอบ pipeline + เขียน CSV

---

## Roadmap → ทำให้ Autonomous

สิ่งที่อยากให้ build ต่อ (เรียงตาม priority):

### Phase 1 — ทำให้ใช้จริงสะดวกขึ้น ✅ (เสร็จแล้ว)
- [x] แยก config ออกมาเป็น `.env` / `config.yaml` ไม่ต้องแก้ในโค้ด
- [x] **dedupe ข้ามรอบ**: เก็บ track id ที่เคยเห็นใน `seen.json` → รอบหน้าไม่เสนอซ้ำ
- [x] เพิ่ม seed source แบบเลือกได้: `likes` / `urls (ลิงก์เพลงที่ชอบ)` / `both`
      _(playlist / station / genre tag ต่อยอดได้ใน client.py)_
- [x] filter ความยาว (เช่นเอาเฉพาะ 2–5 นาที เหมาะกับ vlog BGM)
- [x] 🆕 **Dashboard เว็บ** (`app.py`) ธีมดำ-ส้ม / ขาว-ส้ม + demo mode + เทสต์ offline

### Phase 2 — Enrichment (ของที่เราใช้จริงตอน mix) ✅ (เสร็จแล้ว)
- [x] **ดึง BPM + key** ต่อเพลง (จาก metadata SC) → คอลัมน์ `bpm`, `key`, `camelot` ใน CSV
      _(ต่อ GetSongBPM / Tunebat / librosa สำหรับเพลงที่ไม่มี metadata = งานต่อยอด)_
- [x] จัดกลุ่ม/กรองตาม BPM range + Camelot wheel (compatible keys) — `camelot.py`, `mixset.py`
- [x] 🆕 **Mixed In Key integration**: export Camelot CSV / M3U8, ปุ่ม harmonic order + คลิก key กรองเพลงที่ mix เข้ากัน

### Phase 3 — Autonomous loop 🚧 (กำลังทำ)
- [x] รันเป็น cron / launchd บน Mac Mini (`autorun.py` + `AUTORUN.md`)
- [x] **แจ้งเตือนผ่าน LINE** ว่า "มี reference ใหม่ N เพลงรอคัด" (Messaging API + ปุ่ม 📱 บน dashboard)
- [ ] ส่ง output เข้า Obsidian vault (NOS-VISION-BRAIN) หรือ Notion อัตโนมัติ
- [ ] (optional) auto-สร้าง playlist บน SC จาก top picks ผ่าน oauth

### Phase 4 — เรียนรู้รสนิยม (Tinder-style feedback) ✅ (เสร็จแล้ว)
- [x] ฟังเพลงแล้วปัดซ้าย/ขวา (👎/👍) บน dashboard — มี SoundCloud player ในการ์ด + ลูกศร ←/→
- [x] โมเดลเรียนรู้ like/dislike -> re-rank ด้วยปุ่ม **✨ ตามรสนิยม** (co-occurrence ยังนำ ไม่ถูกกลบ)
- [x] โชว์ **taste profile** (genre/BPM/Camelot/artist ที่ชอบ + like-rate)

### หลักที่อยากให้รักษาไว้ตอน build ต่อ
1. **read-only, ใช้ส่วนตัว** — อย่ายิง API ถี่ ใส่ sleep/backoff เสมอ
2. **อย่า hardcode credential** — client_id auto, oauth ผ่าน env เท่านั้น
3. **co-occurrence คือหัวใจ** — ฟีเจอร์ใหม่ไม่ควรทำลาย ranking signal ตัวนี้

---

## ข้อควรระวัง

- ใช้ **unofficial api-v2** — SC เปลี่ยนโครงสร้างเมื่อไหร่อาจต้องแก้ (จุดเปราะคือ `get_client_id` กับชื่อ endpoint)
- มี rate limit — อย่าลด `SLEEP` ต่ำกว่า 0.3 และอย่ารันถี่ๆ ติดกัน
- เป็นการใช้ส่วนตัวเพื่อ research รสนิยมตัวเอง ไม่ใช่ commercial scraping
