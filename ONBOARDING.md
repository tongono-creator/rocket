# Onboarding — rocket-facebook-page

## Project Goal
โพส Facebook Page + Threads อัตโนมัติ ทุกวัน ไม่ต้องเปิดเครื่อง
เป้าหมาย: สร้าง engagement → followers → รายได้ affiliate (Shopee/Lazada)

**Page target audience:** คนไทยอายุ 30-45 มนุษย์เงินเดือน แบกครอบครัว สนใจการเงิน

---

## สิ่งที่ทำสำเร็จแล้ว (อย่าทำซ้ำ)

### ✅ post.py — คำคม Facebook
- PIL + Kanit-Bold render ข้อความไทย (แทน Gemini image gen ที่ text พัง)
- 4-slot content matrix: morning/noon/evening/late แต่ละ slot มี 10 หัวข้อ + style ต่างกัน
- โพส 4 ครั้ง/วัน: 08:00 / 12:00 / 17:00 / 21:00 BKK

### ✅ meme.py — มุก comic strip Facebook
- Art style: **Thai Retro 90s Chibi** (หัวโต ตัวเล็ก เส้นหนา สีอบอุ่น) — signature style ของเพจ
- 6 meme styles รวม Generation comparison (รุ่นปู่/พ่อ/ลูก/หลาน)
- โพส 3 ครั้ง/วัน: 07:30 / 11:30 / 16:30 BKK — seed-based ไม่ซ้ำกัน 3 slot/วัน

### ✅ threads.py — Threads
- รูป PIL เหมือน post.py
- upload ผ่าน ImgBB → Threads API
- comment เป็น reply thread

### ✅ [affiliate_utils.py](file:///D:/Projects/rocket-facebook-page/affiliate_utils.py) — comment ระบบ
- อ่านสินค้า/อาหารจาก `affiliate_products.xlsx`
- สุ่มลำดับ + สุ่มว่าจะโพส comment แต่ละ type ไหม (85%/60%/70%)
- Delay สุ่ม 60-180s ก่อน comment แรก, 30-90s ระหว่าง comment
- ดูเหมือนคนโพสเอง ไม่ใช่ bot
- **ฟีเจอร์เด่นที่เพิ่มล่าสุด**:
  - ลบลิงก์ affiliate ออกจากแคปชั่นตั้งเวลาเฉพาะของเพจ Rocket (Caption Cleaning) แล้วให้บอท [reply_facebook.py](file:///D:/Projects/rocket-facebook-page/reply_facebook.py) วางลิงก์แทนในคอมเมนต์แรก เพื่อป้องกันการถูกลดการมองเห็น (Meta Reach Penalty)
  - พัฒนาฟังก์ชัน [parse_thai_date](file:///D:/Projects/rocket-facebook-page/affiliate_utils.py#L19) รองรับการแปลงปี พ.ศ. และรูปแบบช่วงวันที่ของไทย เช่น `1-15 มิ.ย. 69` (ปี พ.ศ. 69 -> 2026 ค.ศ.) ทำให้เช็ควันหมดอายุของโปรโมชันได้แม่นยำ
  - นำลิงก์สินค้าขายดีที่ยัง Active จาก Excel มาจับคู่และแนบต่อท้ายคอมเมนต์ลิงก์จัดอันดับเว็บ Shopee Rank อัตโนมัติ เพื่อเพิ่มโอกาสขาย
  - ระบบป้องกันสแปม [has_affiliate_comment](file:///D:/Projects/rocket-facebook-page/reply_facebook.py#L271) ตรวจจับลิงก์หรือคำเชิญชวนอย่าง พิกัด/จิ้ม ที่เคยคอมเมนต์ไปแล้ว เพื่อเลี่ยงคอมเมนต์ซ้ำซ้อน

### ✅ GitHub Actions only
- ไม่ใช้ cron-job.org หรือ external scheduler ใดๆ
- ทุกอย่างอยู่ใน `.github/workflows/`

---

## Architecture ปัจจุบัน

```
repo: tongono-creator/rocket (GitHub)
├── post.py              ← คำคม Facebook
├── meme.py              ← มุก Facebook  
├── threads.py           ← Threads
├── affiliate_utils.py   ← comment ลิงก์ affiliate
├── affiliate_products.xlsx ← ข้อมูลสินค้า/อาหาร (อัปเดตแล้ว push)
├── fonts/
│   └── Kanit-Bold.ttf   ← font ภาษาไทย (committed ใน repo)
├── output/              ← รูปที่ generate (gitignored)
├── .github/workflows/
│   ├── post.yml
│   ├── meme.yml
│   └── threads.yml
├── GUIDE.md             ← คู่มือ operational
└── ONBOARDING.md        ← ไฟล์นี้
```

---

## Key Technical Decisions (ทำไมถึงเลือกแบบนี้)

| Decision | เหตุผล |
|----------|--------|
| PIL แทน Gemini image gen สำหรับ text | Gemini render ภาษาไทยผิดเสมอ |
| Kanit-Bold font | ผู้ใช้เลือกเอง — อ้วน อ่านง่าย บนพื้นดำ |
| random.choice() ไม่ใช่ deterministic | comment เดิมซ้ำทุกโพส ดู bot ชัด |
| GitHub Actions ไม่ใช้ cron-job.org | ลดความยุ่งยาก จัดการที่เดียว |
| Gemini image gen ใช้กับ meme เท่านั้น | meme ต้องการ AI สร้างภาพ ไม่มี text overlay |
| 4-slot content matrix | match กับ mindset คนอ่านแต่ละเวลา |
| Rocket Caption Cleaning | หลีกเลี่ยงการโดนลดการเข้าถึงเมื่อโพสต์ลิงก์ในแคปชั่น โดยย้ายมาขายผ่านคอมเมนต์แรกแทน |
| Thai BE Date Parser | รองรับวันที่ พ.ศ. ของไทยและรูปแบบช่วง (เช่น 1-15 มิ.ย. 69) ป้องกันข้อผิดพลาดของสินค้าหมดโปร |
| Web-Product Comment Pairing | สุ่มนำลิงก์สินค้า Active มาจับคู่และโพสต์ต่อท้ายลิงก์อันดับสินค้าเพื่อช่วยเพิ่มการมองเห็นและยอดขาย |

---

## Models ที่ใช้

| งาน | Model | Fallback |
|-----|-------|---------|
| Text (quote/caption) | gemini-3.5-flash | gemini-2.5-flash |
| Image (meme) | gemini-3-pro-image-preview | retry 3x |
| Image (quote) | PIL (ไม่ใช้ AI) | — |

---

## GitHub Secrets ที่ต้องมี

```
GOOGLE_API_KEY
PAGE_ACCESS_TOKEN
PAGE_ID
THREADS_ACCESS_TOKEN
THREADS_USER_ID
IMGBB_API_KEY
```

---

## งานที่ยังค้างอยู่

### 🔲 Google Sheets แทน Excel สำหรับ review.py
- review.py โพสรีวิวสินค้า ใช้ `review_products.xlsx` อยู่
- ปัญหา: Excel local ≠ repo → โพสซ้ำได้
- แผน: ใช้ gspread + Service Account (gspread ติดตั้งแล้ว)
- **ต้องทำ:** สร้าง Service Account ที่ console.cloud.google.com → download JSON key → ใส่ใน Secret

### 🔲 Reels automation
- prototype อยู่ที่ `reels_prototype.py` (ยังไม่ commit)
- Veo 3.1 ค่า API แพง ($1.50/clip) — ยังไม่ automate
- รอ Gemini Omni API หรือทางเลือกที่ถูกกว่า

---

## วิธีเริ่มงานต่อ

1. อ่าน `GUIDE.md` สำหรับ operational details
2. ดู commit ล่าสุด: `git log --oneline -10`
3. ดู pending tasks ด้านบน

---

## ไฟล์ที่อย่าแตะ

| ไฟล์ | เหตุผล |
|------|--------|
| `fonts/Kanit-Bold.ttf` | binary — ไม่ต้อง regenerate |
| `.github/workflows/*.yml` | schedule ปรับแล้ว ทำงานดี |
| `affiliate_utils.py` _rotate() | random.choice() แก้แล้ว อย่ากลับไปใช้ index |
