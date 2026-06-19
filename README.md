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

## โครงสร้าง

```
.
├── sc_reference_finder.py   # ตัวหลัก: likes → related → rank → CSV
├── README.md                # ไฟล์นี้
└── sc_references.csv         # output (ถูกสร้างหลังรัน)
```

---

## การใช้งาน

```bash
pip install requests
# แก้ PROFILE_URL ใน sc_reference_finder.py เป็น profile ตัวเอง
python3 sc_reference_finder.py
```

ได้ `sc_references.csv` → เปิดใน Sheets / Obsidian → เรียงตาม `matched_seeds` → คัด 100 ตัวบน

### Config ที่ปรับได้ (ในไฟล์ .py)

| ตัวแปร | ความหมาย | ค่า default |
|---|---|---|
| `PROFILE_URL` | profile SoundCloud ของเรา | ต้องใส่เอง |
| `MAX_SEEDS` | ดึง likes ล่าสุดกี่เพลงมาเป็น seed | 60 |
| `TARGET` | จำนวนเพลงใน output (ดึงเผื่อ) | 120 |
| `RELATED_PER_SEED` | related สูงสุดต่อ 1 seed | 50 |
| `SLEEP` | หน่วงกัน rate limit (วินาที) | 0.4 |
| `OAUTH_TOKEN` | ใส่ถ้า likes เป็น private | ว่าง |
| `CLIENT_ID_OVERRIDE` | ใส่ถ้า auto หา client_id ไม่เจอ | ว่าง |

> ทำไม `MAX_SEEDS` ไม่เอา likes ทั้งหมด: เรามี ~1,745 likes ถ้า seed หมดจะยิง API หลายพันครั้ง
> = ช้า + เสี่ยงโดน rate limit แบน. likes ล่าสุด 60–80 = รสนิยมปัจจุบัน กำลังพอดี

---

## Output: คอลัมน์ CSV

| คอลัมน์ | คือ |
|---|---|
| `rank` | อันดับ |
| `matched_seeds` | โผล่ใน related ของกี่ seed (**ตัวชี้วัดหลัก** — สูง = ตรงแนวสุด) |
| `title` / `artist` | ชื่อเพลง / คนทำ |
| `genre` | แนว (ตามที่ uploader ใส่ — ไม่ค่อยน่าเชื่อถือ) |
| `plays` / `likes` | ยอดเล่น / ยอดไลก์ |
| `duration_min` | ความยาว (นาที) |
| `url` | ลิงก์ SoundCloud |

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

### Phase 1 — ทำให้ใช้จริงสะดวกขึ้น
- [ ] แยก config ออกมาเป็น `.env` / `config.yaml` ไม่ต้องแก้ในโค้ด
- [ ] **dedupe ข้ามรอบ**: เก็บ track id ที่เคยเห็นใน `seen.json` → รอบหน้าไม่เสนอซ้ำ
- [ ] เพิ่ม seed source แบบเลือกได้: `likes` / `playlist` / `station` / `genre tag`
- [ ] filter ความยาว (เช่นเอาเฉพาะ 2–5 นาที เหมาะกับ vlog BGM)

### Phase 2 — Enrichment (ของที่เราใช้จริงตอน mix)
- [ ] **ดึง BPM + key** ต่อเพลง (ผ่าน GetSongBPM / Tunebat / วิเคราะห์เองด้วย librosa)
      → เพิ่มคอลัมน์ `bpm`, `key` ใน CSV เพื่อคัดเพลงที่ mix เข้ากันได้เลย
- [ ] จัดกลุ่มผลลัพธ์ตาม BPM range / camelot wheel (compatible keys)

### Phase 3 — Autonomous loop
- [ ] รันเป็น cron / launchd บน Mac Mini (เช่นทุกวันจันทร์เช้า)
- [ ] ส่ง output เข้า Obsidian vault (NOS-VISION-BRAIN) หรือ Notion อัตโนมัติ
- [ ] แจ้งเตือนผ่าน LINE / Discord ว่า "มี reference ใหม่ N เพลงรอคัด"
- [ ] (optional) auto-สร้าง playlist บน SC จาก top picks ผ่าน oauth

### หลักที่อยากให้รักษาไว้ตอน build ต่อ
1. **read-only, ใช้ส่วนตัว** — อย่ายิง API ถี่ ใส่ sleep/backoff เสมอ
2. **อย่า hardcode credential** — client_id auto, oauth ผ่าน env เท่านั้น
3. **co-occurrence คือหัวใจ** — ฟีเจอร์ใหม่ไม่ควรทำลาย ranking signal ตัวนี้

---

## ข้อควรระวัง

- ใช้ **unofficial api-v2** — SC เปลี่ยนโครงสร้างเมื่อไหร่อาจต้องแก้ (จุดเปราะคือ `get_client_id` กับชื่อ endpoint)
- มี rate limit — อย่าลด `SLEEP` ต่ำกว่า 0.3 และอย่ารันถี่ๆ ติดกัน
- เป็นการใช้ส่วนตัวเพื่อ research รสนิยมตัวเอง ไม่ใช่ commercial scraping
