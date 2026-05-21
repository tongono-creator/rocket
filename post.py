# -*- coding: utf-8 -*-
"""post.py — สร้างรูปคำคม + โพส Facebook อัตโนมัติ"""

import sys, io, os, base64, json, requests, time, random, textwrap
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai
from google.genai import types

# === CONFIG (รับจาก env vars — GitHub Actions ใส่ใน Secrets) ===
GOOGLE_API_KEY    = os.environ.get("GOOGLE_API_KEY",    "")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
PAGE_ID           = os.environ.get("PAGE_ID",           "111830598532037")
IMAGE_MODEL       = "gemini-3-pro-image-preview"
TEXT_MODELS       = ["gemini-3.5-flash", "gemini-2.5-flash"]  # fallback order
OUTPUT_DIR        = "output"

# fallback รันบน local ใช้ config.py
if not GOOGLE_API_KEY:
    try:
        from config import GOOGLE_API_KEY, PAGE_ACCESS_TOKEN, PAGE_ID
    except ImportError:
        pass

os.makedirs(OUTPUT_DIR, exist_ok=True)
client = genai.Client(api_key=GOOGLE_API_KEY)

# ─── Topic rotation — 4 slots × 10 หัวข้อ = 40 โพสไม่ซ้ำ ────────
# เช้า: ปลุกใจ → คำคมสั้น
MORNING_TOPICS = [
    "แรงบันดาลใจเช้า สำหรับคนวัย 30-45 ที่กำลังดิ้นรนสร้างอนาคต",
    "วิธีคิดของคนที่ประสบความสำเร็จจากศูนย์",
    "ทำไมคนเก่งถึงยังรู้สึกว่าตัวเองไม่พอ",
    "ความฝันที่ถูกชีวิตจริงกดทับทุกวัน",
    "อย่ารอให้พร้อม จงเริ่มเลย แม้จะยังไม่มีทุน",
    "ความแตกต่างระหว่างคนรวยและคนจนคือนิสัยเหล่านี้",
    "เช้านี้เตือนตัวเองว่า เราเกิดมาเพื่อมากกว่านี้",
    "คนที่สู้ไม่ถอยไม่ใช่คนไม่เหนื่อย แต่คือคนที่เลือกสู้ต่อ",
    "ทุกความสำเร็จเริ่มจากการตัดสินใจเพียงครั้งเดียว",
    "ไม่มีใครรวยจากการนอนฝัน แต่รวยจากการลงมือทำ",
]
# กลางวัน: บทเรียนการเงิน → Tips / ก่อน vs หลัง (ย่อยง่าย อ่านฆ่าเวลา)
NOON_TOPICS = [
    "บทเรียนการเงินที่ไม่มีสอนในโรงเรียน",
    "ค่าใช้จ่ายที่ไม่คาดคิดที่ทำให้เงินเก็บหายไปทุกเดือน",
    "ถ้าเงินเดือนเท่านี้จะวางแผนยังไงให้มีเงินเก็บ",
    "ความสำเร็จที่ซื้อไม่ได้ด้วยเงิน แต่สร้างได้ด้วยวินัย",
    "สิ่งที่อยากบอกตัวเองตอนอายุ 25 เรื่องเงิน",
    "ทำไมคนรุ่นเราถึงเหนื่อยกว่าคนรุ่นก่อน",
    "เมื่อความฝันชนกับความจริงเรื่องเงิน",
    "3 นิสัยการเงินที่ทำให้คนส่วนใหญ่ไม่มีเงินเก็บ",
    "วิธีออมเงินที่ได้ผลจริง สำหรับคนที่บอกว่าไม่เหลือเก็บ",
    "ทำงานหนักแค่ไหน ทำไมยังไม่รวยสักที",
]
# เย็น-ค่ำ: มนุษย์เงินเดือน/แบกครอบครัว → เล่าเรื่องชีวิตจริง (คนเพิ่งเลิกงาน อิน)
EVENING_TOPICS = [
    "ชีวิตคนอายุ 30-45 ที่ต้องแบกทั้งลูกและพ่อแม่",
    "ความเครียดของมนุษย์เงินเดือนที่ไม่มีใครเข้าใจ",
    "ความจริงที่เจ็บปวดของการเป็นพ่อแม่ในยุคนี้",
    "เลิกงานแล้วแต่หัวยังคิดเรื่องงานอยู่",
    "เงินเดือนเข้าปุ๊บ หายปั๊บ ทุกสิ้นเดือน",
    "ทำงานเพื่อใคร ตอบตัวเองตรงๆ สักที",
    "ความรู้สึกที่ไม่กล้าบอกใครในที่ทำงาน",
    "วันที่อยากลาออกแต่ยังทำไม่ได้ คุณเป็นไหม",
    "ชีวิตคนเป็นพ่อแม่ที่ไม่มีเวลาพักจริงๆ",
    "เหนื่อยแค่ไหนก็ล้มไม่ได้ เพราะข้างหลังยังมีคนรอ",
]
# ดึก: ปลดหนี้/อิสรภาพ → คำถาม A/B (คนมีเวลา นั่งไล่ตอบ)
LATE_TOPICS = [
    "ปลดหนี้ได้อย่างไร บทเรียนจากคนที่ทำสำเร็จ",
    "ถึงเวลาหยุดแลกเวลากับเงิน แล้วให้เงินทำงานแทน",
    "อย่าปล่อยให้ความกลัวหยุดคุณจากอิสรภาพทางการเงิน",
    "ทบทวนชีวิต ทบทวนเป้าหมาย ก่อนนอน",
    "ทำไมคนส่วนใหญ่เกษียณไม่ได้ตามที่ฝัน",
    "สิ่งที่ควรทำกับเงินก่อนอายุ 45",
    "คืนนี้ขอบคุณตัวเองที่ยังสู้มาได้จนถึงตรงนี้",
    "ถ้าวันนี้มีเงิน 1 ล้าน คุณจะทำอะไรก่อน",
    "ความสุขที่แท้จริงคือไม่ต้องดูยอดในบัญชีก่อนใช้เงิน",
    "อิสรภาพทางการเงินไม่ใช่ความฝัน แต่คือทักษะที่ฝึกได้",
]

def get_topic():
    bkk = timezone(timedelta(hours=7))
    now = datetime.now(bkk)
    day_idx = (now.timetuple().tm_yday - 1) % 10
    hour = now.hour
    if hour < 10:
        return MORNING_TOPICS[day_idx], "morning"
    elif hour < 16:
        return NOON_TOPICS[day_idx], "noon"
    elif hour < 21:
        return EVENING_TOPICS[day_idx], "evening"
    else:
        return LATE_TOPICS[day_idx], "late"

# slot → style ที่เหมาะที่สุดตาม content matrix
SLOT_STYLE = {
    "morning": 0,   # คำคมสั้น กระแทกใจ
    "noon":    3,   # Tips กระชับ หรือ ก่อน vs หลัง (สลับวัน)
    "evening": 1,   # เล่าเรื่องชีวิตจริง relatable
    "late":    2,   # คำถาม A/B ตอบง่าย
}

CONTENT_STYLES = [
    # style 0: คำคมสั้น กระแทกใจ (เช้า)
    (
        "สร้างคำคมภาษาไทยแบบไวรัลเกี่ยวกับ: {topic}\n"
        "สั้นมาก 1-2 ประโยคเท่านั้น กระแทกใจ หยุดนิ้วเลื่อนได้ทันที\n"
        "ภาษาพูดธรรมดา เหมือนเพื่อนสนิทตบไหล่บอก ไม่วิจิตร\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น"
    ),
    # style 1: เล่าเรื่องชีวิตจริง relatable (เย็น)
    (
        "เขียน Facebook post ภาษาไทยเล่าเรื่องชีวิตจริงเกี่ยวกับ: {topic}\n"
        "สั้น 3-4 บรรทัด เหมือนเพื่อนโพสระบาย เข้าใจง่าย คนอ่านแล้วพยักหน้า\n"
        "ลงท้ายด้วยประโยคที่ให้คนอยากคอมเม้นระบายตาม เช่น 'ใครเป็นเหมือนกันบ้าง?'\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น"
    ),
    # style 2: คำถาม A/B ตอบง่าย (ดึก)
    (
        "เขียน Facebook post ภาษาไทยตั้งคำถามแบบให้เลือก A หรือ B เกี่ยวกับ: {topic}\n"
        "คำถามสั้น ตอบง่าย ไม่ต้องคิดนาน เช่น:\n"
        "'อายุ 30 มีเงินเก็บกันเท่าไหร่แล้ว? A. หลับสบาย B. สู้ชีวิตอยู่'\n"
        "ไม่เกิน 2 บรรทัด ภาษาพูด ให้คนอยากตอบในคอมเม้น\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น"
    ),
    # style 3: Tips กระชับ (กลางวัน)
    (
        "เขียน Facebook post ภาษาไทย tips เกี่ยวกับ: {topic}\n"
        "เริ่มด้วยหัวข้อดึงดูด 1 บรรทัด\n"
        "ตามด้วย 3 ข้อสั้นๆ ข้อละ 1 บรรทัด ใช้ได้ทันที ไม่อ้อมค้อม\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น"
    ),
    # style 4: ก่อน vs หลัง พร้อมตัวเลขชัดเจน (กลางวัน สลับ)
    (
        "เขียน Facebook post ภาษาไทยเปรียบเทียบ ก่อน vs หลัง เกี่ยวกับ: {topic}\n"
        "ต้องมีตัวเลขหรือข้อมูลที่ตัดกันชัดเจน เช่น 'ก่อน: หนี้ 5 แสน / หลัง: หนี้ 0 เงินออม 5 หมื่น'\n"
        "สั้น 2-3 บรรทัด เห็นภาพชัด คนแชร์ได้เลย ภาษาพูด\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น"
    ),
]

# ─── 1. สร้างคำคม ──────────────────────────────────────────────
def generate_quote(topic, slot="morning"):
    # noon สลับ style 3 / 4 ตามวัน เพื่อความหลากหลาย
    if slot == "noon":
        bkk = timezone(timedelta(hours=7))
        style_idx = 3 if (datetime.now(bkk).timetuple().tm_yday % 2 == 0) else 4
    else:
        style_idx = SLOT_STYLE.get(slot, 0)
    style = CONTENT_STYLES[style_idx]
    prompt = style.format(topic=topic)
    print(f"Topic: {topic} | Slot: {slot} | Style: {style_idx}")
    for model in TEXT_MODELS:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                quote = resp.text.strip()
                print(f"Quote [{model}]:\n{quote}\n")
                return quote
            except Exception as e:
                print(f"[{model}] attempt {attempt+1} failed: {str(e)[:100]}")
                if attempt < 1:
                    time.sleep(10)
        print(f"[{model}] unavailable, trying next model...")
    raise RuntimeError("Quote generation failed on all models")

# ─── 2. สร้างรูป (PIL + Kanit-Bold — ข้อความถูกต้อง 100%) ────────
FONT_PATH      = os.path.join(os.path.dirname(__file__), "fonts", "Kanit-Bold.ttf")
FONT_HASH_PATH = os.path.join(os.path.dirname(__file__), "fonts", "Kanit-Bold.ttf")
IMG_SIZE = 1080

def wrap_thai(text, font, draw, max_width):
    """ตัดบรรทัดให้พอดีความกว้าง"""
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        w = draw.textbbox((0, 0), test, font=font)[2]
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

def generate_image(quote):
    print("Generating image (PIL)...")
    bkk = timezone(timedelta(hours=7))
    ts  = datetime.now(bkk).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"quote_{ts}.png")

    img  = Image.new("RGB", (IMG_SIZE, IMG_SIZE), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_main = ImageFont.truetype(FONT_PATH, 78)
    font_hash = ImageFont.truetype(FONT_HASH_PATH, 50)

    PAD = 80
    max_w = IMG_SIZE - PAD * 2

    # แยก hashtag ออก
    raw_lines = quote.strip().split("\n")
    content_lines, hash_lines = [], []
    for l in raw_lines:
        (hash_lines if l.strip().startswith("#") else content_lines).append(l.strip())

    # wrap content
    all_lines = []
    for l in content_lines:
        if not l:
            all_lines.append(("", font_main))
            continue
        for wrapped in wrap_thai(l, font_main, draw, max_w):
            all_lines.append((wrapped, font_main))

    all_lines.append(("", font_main))  # spacer
    for l in hash_lines:
        if l:
            all_lines.append((l, font_hash))

    # calc total height
    line_gap = 18
    total_h = sum(draw.textbbox((0,0), t, font=f)[3] + line_gap for t, f in all_lines)
    y = (IMG_SIZE - total_h) // 2

    for text, font in all_lines:
        if not text:
            y += draw.textbbox((0,0), "ก", font=font)[3] // 2
            continue
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        x = (IMG_SIZE - w) // 2
        color = (150, 150, 150) if font == font_hash else (255, 255, 255)
        # subtle shadow
        draw.text((x+2, y+2), text, font=font, fill=(30, 30, 30))
        draw.text((x, y), text, font=font, fill=color)
        y += bbox[3] + line_gap

    img.save(path)
    print(f"Image saved: {path}")
    return path

# ─── 3. โพส Facebook ────────────────────────────────────────────
def post_facebook(img_path, caption):
    print("Posting to Facebook...")
    with open(img_path, "rb") as f:
        resp = requests.post(
            f"https://graph.facebook.com/v25.0/{PAGE_ID}/photos",
            data={"access_token": PAGE_ACCESS_TOKEN, "caption": caption, "published": "true"},
            files={"source": ("quote.png", f, "image/png")}
        )
    result = resp.json()
    if "id" in result:
        post_id = result.get("post_id") or result["id"]
        print(f"FB Posted! ID: {post_id}")
        add_comment(post_id)
        return post_id
    else:
        print(f"FB Error: {result}")
        raise SystemExit(1)

# ─── 4. Auto-comment ลิงก์เว็บ + product rotation ──────────────
def add_comment(post_id):
    from affiliate_utils import get_all_comments
    comments = get_all_comments()
    # หน่วงก่อน comment แรก — ดูเหมือนคนมาเห็นโพสแล้วคอมเม้น
    delay0 = random.uniform(60, 180)
    print(f"Waiting {delay0:.0f}s before first comment...")
    time.sleep(delay0)
    for i, msg in enumerate(comments, 1):
        resp = requests.post(
            f"https://graph.facebook.com/v25.0/{post_id}/comments",
            data={"access_token": PAGE_ACCESS_TOKEN, "message": msg}
        )
        result = resp.json()
        if "id" in result:
            print(f"Comment {i} added! ID: {result['id']}")
        else:
            print(f"Comment {i} error: {result}")
        if i < len(comments):
            delay = random.uniform(30, 90)
            print(f"Waiting {delay:.0f}s before next comment...")
            time.sleep(delay)

# ─── Main ────────────────────────────────────────────────────────
if __name__ == "__main__":
    topic, slot = get_topic()
    quote    = generate_quote(topic, slot)
    img_path = generate_image(quote)
    post_facebook(img_path, quote)
