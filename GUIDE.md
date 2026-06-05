# คู่มือระบบ rocket-facebook-page

## ภาพรวม

ระบบโพส Facebook + Threads อัตโนมัติ ทำงานผ่าน GitHub Actions ทุกวัน ไม่ต้องเปิดเครื่อง

```
GitHub Actions (cron)
├── post.py         → รูปคำคม + caption → Facebook Page (4 ครั้ง/วัน)
├── meme.py         → รูปมุกการ์ตูน Reddit → Facebook Page (3 ครั้ง/วัน)
├── news.py         → รูปข่าวพาดหัวไอที Reddit → Facebook Page (1 ครั้ง/วัน)
├── lotto_poster.py → โพสต์รายงานผลสลากกินแบ่งรัฐบาล (เฉพาะวันที่ 1 และ 16)
└── threads.py      → รูปคำคม + caption → Threads (3 ครั้ง/วัน)
         ↓
   affiliate_utils.py → comment ลิงก์ affiliate อัตโนมัติ (สุ่มลำดับ)
         ↓
   affiliate_products.xlsx → ข้อมูลสินค้า + ร้านอาหาร
```

---

## ฟังก์ชันเด่นและความสำเร็จล่าสุด (Success Features)

### 1. ระบบดึงภาพและแปลมีม Reddit (Reddit-sourced Cartoon Meme Generator)
* **การปรับปรุง**: พัฒนาระบบดึงมีมสุดฮิตจาก Reddit เช่นห้อง `OfficeHumor`, `memes`, `dankmemes`, `me_irl` มาวิเคราะห์และดึงแก่นความตลก แล้วสร้างเป็นภาพการ์ตูนสไตล์เพจเอง เพื่อลดปัญหารูปภาพลิขสิทธิ์ และเพิ่มการเข้าถึงคนไทย
* **การทำงาน**: สคริปต์ `meme.py` จะวิเคราะห์มีมต้นฉบับภาษาอังกฤษด้วย Gemini Vision จากนั้นจะเขียนภาพพาดหัวภาษาไทยและเจนภาพตัวการ์ตูนสไตล์ "Thai Retro 90s Chibi" (คาแรคเตอร์หนุ่มแว่นพนักงานออฟฟิศ) 2 ช่องแนว "คาดหวัง vs ความจริง" โดยซ้อนตัวอักษรไทยตัวหนาลงบนแถบไล่เฉดสีดำ (Matichon Style) ด้านล่างของรูป เพื่อให้ผู้ใช้เข้าใจมีมได้ทันทีโดยไม่ต้องแปลภาษาอังกฤษเอง

### 2. ระบบคัดกรองข่าวสารตามความนิยม (High-Popularity News Curation)
* **การปรับปรุง**: แก้ไขปัญหาข่าวสารที่โพสต์ไม่ได้รับความนิยมหรือไม่มีคนรับชม โดยการเพิ่มระบบวิเคราะห์ความนิยมแบบอัจฉริยะใน `news.py`
* **การทำงาน**: บอทจะกรองข่าวเฉพาะข่าวที่มีค่า Engagement (เช่น จำนวนอัพโหวต คอมเมนต์ บน Reddit) สูงกว่าเกณฑ์ที่กำหนดเพื่อคัดกรองข่าวที่มีคุณภาพ จากนั้นส่งเนื้อข่าวให้ Gemini วิเคราะห์และคัดเลือกข่าวที่น่าดึงดูดที่สุด 1 ข่าว ก่อนจะนำมาสร้างภาพพาดหัวและโพสต์ลงเพจ

### 3. ระบบตรวจผลสลากกินแบ่งรัฐบาลไทยอัตโนมัติ (Thai Lottery Auto Poster)
* **การปรับปรุง**: เพิ่มบอทรายงานผลหวยอัตโนมัติ ทุกวันที่ 1 และ 16 ของเดือน ดึงข้อมูล Real-time ทันทีหลังจากประกาศผล
* **การทำงาน**: สคริปต์ `lotto_poster.py` จะถูกเรียกทำงานและดึงข้อมูลผลรางวัลจาก Sanook Lotto ตรวจสอบความถูกต้องอย่างละเอียด แล้วโพสต์ประกาศบนหน้า Facebook Page ทันทีพร้อมแคปชั่นที่เข้ากับคาแรคเตอร์เพจ

---

## GitHub Actions Schedule

### post.yml (คำคม Facebook)
| เวลา BKK | Slot | Style |
|----------|------|-------|
| 08:00 | morning | คำคมสั้น กระแทกใจ |
| 12:00 | noon | Tips 3 ข้อ หรือ ก่อน vs หลัง (สลับวัน) |
| 17:00 | evening | เล่าเรื่องชีวิตจริง relatable |
| 21:00 | late | คำถาม A/B ให้คนตอบ |

### meme.yml (มุกการ์ตูน Reddit)
| เวลา BKK | Slot |
|----------|------|
| 07:30 | slot 0 |
| 11:30 | slot 1 |
| 16:30 | slot 2 |

### news.yml (ข่าวไอทีพาดหัว Reddit)
- 14:00 BKK (ทุกวัน)

### lotto_bot.yml (รายงานผลหวย)
- ทำงานทุก 15 นาที ระหว่างเวลา 14:00 - 16:45 BKK (เฉพาะวันที่ 1 และ 16 ของเดือน)

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

## meme.py — มุกการ์ตูน Reddit (3 ครั้ง/วัน)

### Flow
1. `get_reddit_meme()` → ดึง RSS feed ของมีมสุดฮิตจาก Reddit (`OfficeHumor`, `memes`, `dankmemes`, `me_irl` ฯลฯ) ที่ยังไม่เคยโพสต์
2. `analyze_meme_to_scenario()` → ใช้ Gemini Vision วิเคราะห์มีมภาษาอังกฤษ ดึงอารมณ์ขัน แล้วแปลงเป็นสถานการณ์ 2 ช่อง "ความคาดหวัง vs ความจริง" และแต่งแคปชั่นสไตล์แอดมินเพจผู้ชาย (ครับ/ผม/พี่)
3. `generate_panel_image()` → ส่ง prompt รายละเอียดฉากไปให้ Gemini Image Model เพื่อวาดรูปการ์ตูนตัวละคร Rocket21 (หนุ่มแว่นพนักงานออฟฟิศ) 2 ช่องเดี่ยว
4. `stitch_panels()` → รวมรูป 2 ช่องเข้าด้วยกันแนวตั้ง ขนาด 1080×1080 และเขียนพาดหัวภาษาไทยตัวหนาขาวขอบดำเพื่อให้คนไทยเก็ตมุกทันที
5. `post_facebook()` → อัปโหลดภาพมุกการ์ตูนและคอมเมนต์แนะนำลิงก์สินค้าแนะนำ

### สไตล์ศิลปะการ์ตูน (Art Style Signature)
**Thai Manga / Cel-shaded** — การ์ตูนเส้นหนา หัวโตเล็กน้อย สื่ออารมณ์ทางใบหน้าชัดเจน ไม่มีการใส่บอลลูนคำพูดในรูปเพื่อเน้นเล่าเรื่องผ่านอารมณ์ตัวละครและข้อความพาดหัวแทน

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

## news.py — โพสต์ข่าวเทคโนโลยี (1 ครั้ง/วัน)

### Flow
1. `fetch_top_candidates()` → ดึงข่าวเด่นจากซับเรดดิตเทคโนโลยี/ไอทีและบอร์ดข่าวกรองคัดสรร โดยคำนวณจากค่าความนิยม (Engagement = Upvotes + Comments)
2. `select_best_news_candidate()` → ส่งตัวเลือกข่าวเด่นให้ Gemini วิเคราะห์เพื่อเลือกข่าวที่มีแนวโน้มว่าคนไทยจะสนใจมากที่สุด 1 ข่าว
3. `verify_image_title_match()` → คัดกรองและตรวจสอบความเข้ากันของรูปภาพกับเนื้อหาข่าวเพื่อป้องกันความสับสน
4. `generate_news_content()` → ให้ Gemini สรุปข่าวเขียนออกมาเป็นแคปชั่นภาษาไทยและพาดหัวสั้น 2 บรรทัด (line1, line2)
5. `add_overlay()` → เขียนข้อความพาดหัวตัวหนาลงบนแถบไล่เฉดสีดำ (Matichon Style) ด้านล่างของรูปภาพเพื่อดึงดูดความสนใจ
6. `post_facebook()` → อัปโหลดโพสต์ลง Facebook และแนบลิงก์สินค้าแนะแนวใต้คอมเมนต์

---

## lotto_poster.py — บอทรายงานผลหวย (เฉพาะวันที่ 1 และ 16)

* ดึงข้อมูลผลรางวัลสลากกินแบ่งรัฐบาลแบบ Real-time จากหน้าหวยของ Sanook Lotto
* ตรวจสอบความถูกต้องของเลขรางวัลที่ 1, เลขหน้า 3 ตัว, เลขท้าย 3 ตัว และเลขท้าย 2 ตัวอย่างรอบคอบป้องกันความผิดพลาดก่อนโพสต์
* โพสต์ลง Facebook เพจอัตโนมัติพร้อมแคปชั่นแสดงความยินดีในสไตล์แอดมิน Rocket21

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

# รัน meme.py local (ดึงจาก Reddit และเจนภาพ 2 ช่องพร้อม overlay)
python meme.py --dry-run
python meme.py --dry-run-image

# รัน news.py local (คัดกรองข่าวเด่น Reddit และเจนภาพพาดหัว)
python news.py --dry-run

# รัน lotto_poster.py local
python lotto_poster.py

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

---

## พรอมต์สร้างภาพรีวิวสินค้าจาก AI (AI Product Review Prompt Template)

พรอมต์ที่ได้รับอนุมัติสำหรับการเจนรูปภาพรีวิวสินค้า:

```plaintext
Act as a professional e-commerce visual content creator. Create a high-quality promotional image for [PRODUCT NAME] inspired by the combined composition and text aesthetic of images_1.png through images_5.png. 

Key Visual Elements:
- Background: Minimalist, clean desk setup or styled nook with soft, bright light, and a shallow depth of field (blurred background elements).
- Subject: A prominent, central placement of [PRODUCT NAME] based on the photo you provided.
- Graphics: Incorporate playful, stylized *Thai* text overlays using both free-floating text and text within outlined boxes (similar to the examples in the reference images). 
- Decorative Elements: Include floating sparkles, small ingredient-relevant icons (like tiny fruits, flowers, clouds), and subtle sizing indicators, but NO prices.

Text Content Strategy (Generate ONE unique Thai perspective per render):
1. "Problem Solver/Result-Focused": Focus on a key problem the product solves (e.g., dry skin, messy desk). Use clean, professional Thai fonts.
2. "Lifestyle/Emotional Benefit": Focus on how the product makes you feel (e.g., "Elevate Your Space", "Feel Luxurious"). Use playful Thai fonts.
3. "Functional/Tech Feature Callout": Pick ONE unique benefit (e.g., specific sizing, a technology). Use bold Thai fonts.

[PASTE DETAILED PRODUCT DESCRIPTION HERE]
```

