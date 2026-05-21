# คู่มือระบบ rocket-facebook-page

## ภาพรวม

ระบบโพส Facebook + Threads อัตโนมัติ ทำงานผ่าน GitHub Actions ทุกวัน ไม่ต้องเปิดเครื่อง

```
GitHub Actions (cron)
├── post.py      → รูปคำคม + caption → Facebook Page (4 ครั้ง/วัน)
├── meme.py      → รูปมุกตลก comic strip → Facebook Page (3 ครั้ง/วัน)
└── threads.py   → รูปคำคม + caption → Threads (3 ครั้ง/วัน)
         ↓
   affiliate_utils.py → comment ลิงก์ affiliate อัตโนมัติ (สุ่มลำดับ)
         ↓
   affiliate_products.xlsx → ข้อมูลสินค้า + ร้านอาหาร
```

---

## GitHub Actions Schedule

### post.yml (คำคม Facebook)
| เวลา BKK | Slot | Style |
|----------|------|-------|
| 08:00 | morning | คำคมสั้น กระแทกใจ |
| 12:00 | noon | Tips 3 ข้อ หรือ ก่อน vs หลัง (สลับวัน) |
| 17:00 | evening | เล่าเรื่องชีวิตจริง relatable |
| 21:00 | late | คำถาม A/B ให้คนตอบ |

### meme.yml (มุก Facebook)
| เวลา BKK | Slot |
|----------|------|
| 07:30 | slot 0 |
| 11:30 | slot 1 |
| 16:30 | slot 2 |

### threads.yml (Threads)
ดูไฟล์ `.github/workflows/threads.yml`

---

## post.py — คำคม Facebook

### Flow
1. `get_topic()` → เลือกหัวข้อตาม slot เวลา + วันที่ (day_idx = วันที่ % 10)
2. `generate_quote()` → ส่ง prompt ไป Gemini (gemini-3.5-flash fallback gemini-2.5-flash)
3. `generate_image()` → วาดรูป 1080×1080 ด้วย PIL + Kanit-Bold font
4. `post_facebook()` → upload รูป + caption ผ่าน Graph API
5. `add_comment()` → รอ 60-180s แล้ว comment ลิงก์ affiliate

### หัวข้อ (Topics)
แต่ละ slot มี 10 หัวข้อ หมุนตามวันที่ ครบ 10 วันวนซ้ำ

- **MORNING_TOPICS** — แรงบันดาลใจ, ปลุกใจ
- **NOON_TOPICS** — บทเรียนการเงิน, Tips
- **EVENING_TOPICS** — มนุษย์เงินเดือน, แบกครอบครัว
- **LATE_TOPICS** — ปลดหนี้, อิสรภาพทางการเงิน

### เพิ่มหัวข้อใหม่
เปิด `post.py` หา list ที่ต้องการ แล้วเพิ่มบรรทัดได้เลย (ไม่ต้อง push โค้ดอื่น)

---

## meme.py — มุก Facebook

### Flow
1. `get_scenario()` → เลือก scenario + style ตาม seed (วัน × 3 + slot) ไม่ซ้ำ 3 ครั้ง/วัน
2. `generate_meme_caption()` → ส่ง prompt ไป Gemini ได้ caption ภาษาไทย
3. `generate_meme_image()` → ส่ง prompt ไป Gemini image model (gemini-3-pro-image-preview)
4. `post_facebook()` → upload + comment affiliate

### Art Style (Signature)
**Thai Retro 90s Chibi** — หัวโต ตัวเล็ก เส้นหนา สีโทนอบอุ่น เหมือนการ์ตูนไทยยุค 90

### MEME_STYLES (6 แบบ)
| # | ชื่อ | รูปแบบ |
|---|------|--------|
| 0 | 3-panel comic | 3 ช่องแนวตั้ง เล่าเรื่อง |
| 1 | Khaby Lame style | 2 ช่อง: วิธียาก vs วิธีง่าย |
| 2 | Cat reaction meme | แมวแสดงอารมณ์ relatable |
| 3 | Distracted choice meme | เดินไปแต่หันมองสิ่งล่อใจ |
| 4 | Expectation vs Reality | ที่คิดไว้ vs ความเป็นจริง |
| 5 | Generation comparison | 2×2 grid: รุ่นปู่/พ่อ/ลูก/หลาน |

### เพิ่มมุกใหม่
เปิด `meme.py` หา `MEME_SCENARIOS` แล้วเพิ่ม string ได้เลย
- มุก Generation comparison ต้องมีคำว่า "รุ่นปู่" อยู่ในข้อความ (ระบบแยก list อัตโนมัติ)

---

## threads.py — Threads

### Flow
เหมือน post.py แต่:
1. upload รูปไป ImgBB ก่อน (Threads ต้องการ public URL)
2. สร้าง container → publish ผ่าน Threads API
3. comment เป็น reply thread แทน Facebook comment

### ต้องการ Secret เพิ่ม
- `THREADS_ACCESS_TOKEN`
- `THREADS_USER_ID`
- `IMGBB_API_KEY`

---

## affiliate_utils.py — ระบบ Comment

### ทำงานยังไง
ทุกครั้งที่โพส ระบบจะ comment ลิงก์ affiliate โดยอัตโนมัติ

**พฤติกรรมสุ่ม (ดูเหมือนคนโพสเอง):**
| ประเภท | โอกาสออก | รายละเอียด |
|--------|----------|------------|
| website link | 85% | ลิงก์ shopee-ranking.vercel.app |
| food | 60% | ลิงก์ Shopee Food จาก Excel |
| product | 70% | ลิงก์ Shopee/Lazada จาก Excel |
| ลำดับ | shuffle ทุกครั้ง | ไม่เรียงเดิม |

**Delay:**
- รอ 60–180s ก่อน comment แรก
- รอ 30–90s ระหว่าง comment

---

## affiliate_products.xlsx — อัปเดตสินค้า/อาหาร

### โครงสร้างไฟล์
| Column | ข้อมูล |
|--------|--------|
| A | No. |
| B | ชื่อสินค้า |
| C | Shopee link |
| D | Lazada link |
| E | active (yes/no) |
| F | desc (คำอธิบายสั้น) |
| G | Food link (Shopee Food) |

### วิธีเพิ่มสินค้าใหม่
1. เปิด `affiliate_products.xlsx`
2. เพิ่มแถวใหม่ ใส่ชื่อ + ลิงก์ + ใส่ column E = `yes`
3. ถ้าไม่มีลิงก์ใดก็ใส่ `xxx` แทน (ระบบจะข้ามไป)
4. save → push ขึ้น GitHub

### วิธีเพิ่มร้านอาหาร
ใส่ลิงก์ Shopee Food ใน column G ของแถวไหนก็ได้ (row ไหนก็ได้ไม่ต้องเป็นสินค้า)
ลิงก์รูปแบบ: `ลองเข้ามาดู ShopName ที่ Shopee! https://...`

### วิธี disable สินค้าชั่วคราว
เปลี่ยน column E จาก `yes` เป็น `no`

---

## GitHub Secrets ที่ต้องมี

ไปที่ GitHub repo → Settings → Secrets and variables → Actions

| Secret | ใช้ใน |
|--------|-------|
| `GOOGLE_API_KEY` | ทุก script (Gemini API) |
| `PAGE_ACCESS_TOKEN` | post.py, meme.py (Facebook) |
| `PAGE_ID` | post.py, meme.py (Facebook) |
| `THREADS_ACCESS_TOKEN` | threads.py |
| `THREADS_USER_ID` | threads.py |
| `IMGBB_API_KEY` | threads.py (upload รูป) |

---

## Fonts

เก็บอยู่ที่ `fonts/Kanit-Bold.ttf`
ใช้ render ข้อความไทยบนรูปคำคม (PIL) — ถูกต้อง 100% ไม่มีอักขระพัง

---

## รัน Manual (ทดสอบ)

```bash
# รัน post.py local
python post.py

# รัน meme.py local
python meme.py

# รัน threads.py local
python threads.py
```

ต้องมี `config.py` ใน project root:
```python
GOOGLE_API_KEY = "..."
PAGE_ACCESS_TOKEN = "..."
PAGE_ID = "..."
THREADS_ACCESS_TOKEN = "..."
THREADS_USER_ID = "..."
IMGBB_API_KEY = "..."
```

---

## Troubleshooting

| ปัญหา | สาเหตุ | วิธีแก้ |
|-------|--------|---------|
| Comment ซ้ำ | เคยใช้ deterministic rotation | แก้แล้ว → random.choice() |
| ข้อความภาษาไทยพัง | เคยใช้ Gemini gen image | แก้แล้ว → PIL + Kanit-Bold |
| โพสสินค้าซ้ำ | Excel local ≠ repo | push Excel ขึ้น GitHub ทุกครั้ง |
| Image gen fail | Gemini API quota/error | retry 3 ครั้งอัตโนมัติ |
| Quote gen fail | Gemini model unavailable | fallback gemini-2.5-flash อัตโนมัติ |
