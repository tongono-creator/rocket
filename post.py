# -*- coding: utf-8 -*-
"""post.py — สร้างรูปคำคม + โพส Facebook อัตโนมัติ"""

import sys, io, os, requests, time, random
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai

# === CONFIG (รับจาก env vars — GitHub Actions ใส่ใน Secrets) ===
GOOGLE_API_KEY    = os.environ.get("GOOGLE_API_KEY",    "")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
PAGE_ID           = os.environ.get("PAGE_ID",           "111830598532037")
IMAGE_MODEL       = "gemini-2.0-flash-preview-image-generation"  # unused in post.py (PIL renders text)
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
    hour = now.hour
    if hour < 10:
        return random.choice(MORNING_TOPICS), "morning"
    elif hour < 16:
        return random.choice(NOON_TOPICS), "noon"
    elif hour < 21:
        return random.choice(EVENING_TOPICS), "evening"
    else:
        return random.choice(LATE_TOPICS), "late"

# slot → style ที่เหมาะที่สุดตาม content matrix
SLOT_STYLE = {
    "morning": 0,   # คำคมสั้น กระแทกใจ
    "noon":    3,   # Tips กระชับ หรือ ก่อน vs หลัง (สลับวัน)
    "evening": 1,   # เล่าเรื่องชีวิตจริง relatable
    "late":    2,   # คำถาม A/B ตอบง่าย
}

CONTENT_STYLES = [
    # style 0: คำคมสั้น กระแทกใจ
    (
        "สร้างคำคมภาษาไทยแบบไวรัลเกี่ยวกับ: {topic}\n"
        "1-2 ประโยคสั้นมาก กระแทกใจ หยุดนิ้วเลื่อนได้ทันที ภาษาพูดธรรมดา\n"
        "ข้อความรวม (ไม่นับ hashtag) ห้ามเกิน 50 ตัวอักษร ขึ้นบรรทัดใหม่จริงๆ ตรงจุดหยุดตามธรรมชาติ\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น"
    ),
    # style 1: เล่าเรื่องชีวิตจริง relatable
    (
        "เขียน post ภาษาไทยเล่าเรื่องชีวิตจริงเกี่ยวกับ: {topic}\n"
        "2 ประโยคสั้นๆ เหมือนเพื่อนโพส ลงท้ายด้วยคำถามให้คนอยากคอมเม้น\n"
        "ข้อความรวม (ไม่นับ hashtag) ห้ามเกิน 70 ตัวอักษร ขึ้นบรรทัดใหม่จริงๆ ตรงจุดหยุดตามธรรมชาติ\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น"
    ),
    # style 2: คำถาม A/B ตอบง่าย
    (
        "เขียน post ภาษาไทยตั้งคำถามแบบให้เลือก A หรือ B เกี่ยวกับ: {topic}\n"
        "คำถามสั้น ตอบง่าย ไม่ต้องคิดนาน ภาษาพูด ให้คนอยากตอบในคอมเม้น\n"
        "ข้อความรวม (ไม่นับ hashtag) ห้ามเกิน 60 ตัวอักษร ขึ้นบรรทัดใหม่จริงๆ ตรงจุดหยุดตามธรรมชาติ\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น"
    ),
    # style 3: Tips กระชับ
    (
        "เขียน post ภาษาไทย tips เกี่ยวกับ: {topic}\n"
        "หัวข้อดึงดูด 1 บรรทัด + 3 ข้อสั้นมากๆ ข้อละไม่เกิน 10 ตัวอักษร\n"
        "ข้อความรวม (ไม่นับ hashtag) ห้ามเกิน 70 ตัวอักษร ขึ้นบรรทัดใหม่จริงๆ ตรงจุดหยุดตามธรรมชาติ\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น"
    ),
    # style 4: ก่อน vs หลัง
    (
        "เขียน post ภาษาไทยเปรียบเทียบ ก่อน vs หลัง เกี่ยวกับ: {topic}\n"
        "มีตัวเลขตัดกันชัด 2 บรรทัด เห็นภาพชัด ภาษาพูด\n"
        "ข้อความรวม (ไม่นับ hashtag) ห้ามเกิน 60 ตัวอักษร ขึ้นบรรทัดใหม่จริงๆ ตรงจุดหยุดตามธรรมชาติ\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น"
    ),
]

# ─── 1. สร้างคำคม ──────────────────────────────────────────────
def clean_text(text):
    """ลบ markdown formatting + แปลง literal \\n → newline จริง"""
    import re
    text = text.replace('\\n', '\n')                # literal \n → newline จริง
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)   # **bold**
    text = re.sub(r'\*(.+?)\*',     r'\1', text)   # *italic*
    text = re.sub(r'__(.+?)__',     r'\1', text)   # __bold__
    text = re.sub(r'_(.+?)_',       r'\1', text)   # _italic_
    text = re.sub(r'^#+\s*',        '',    text, flags=re.MULTILINE)  # ## heading
    return text.strip()

def generate_quote(topic, slot="morning"):
    style_idx = random.randint(0, len(CONTENT_STYLES) - 1)
    style = CONTENT_STYLES[style_idx]
    prompt = style.format(topic=topic)
    print(f"Topic: {topic} | Slot: {slot} | Style: {style_idx}")
    for model in TEXT_MODELS:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                quote = clean_text(resp.text)
                print(f"Quote [{model}]:\n{quote}\n")
                return quote
            except Exception as e:
                print(f"[{model}] attempt {attempt+1} failed: {str(e)[:100]}")
                if attempt < 1:
                    time.sleep(10)
        print(f"[{model}] unavailable, trying next model...")
    raise RuntimeError("Quote generation failed on all models")


def generate_story(topic, slot="morning"):
    """สร้าง bullet narrative caption สำหรับ Facebook post description"""
    time_context = {
        "morning": "เช้า — เหมาะสำหรับเริ่มวัน ปลุกพลัง",
        "noon":    "กลางวัน — อ่านระหว่างพักเที่ยง ย่อยง่าย",
        "evening": "เย็น-ค่ำ — คนเพิ่งเลิกงาน relatable สูง",
        "late":    "ดึก — ชวนคิดก่อนนอน",
    }
    time_line = time_context.get(slot, "")
    prompt = (
        f"หัวข้อ: {topic}\n"
        f"บริบท: {time_line}\n\n"
        "เขียน Facebook caption แบบ ▪️ bullet narrative สำหรับเพจไลฟ์สไตล์/การเงิน คนวัย 30-45\n"
        "ใช้ ▪️ นำหน้าทุก bullet — 6-8 จุด เล่าเรื่องมีความต่อเนื่อง\n"
        "โครงสร้าง:\n"
        "▪️ 1-2: Setup — ปัญหา/สถานการณ์ relatable ที่คนวัย 30-45 เจอจริง\n"
        "▪️ 3-4: เนื้อหาหลัก — บทเรียน ข้อมูล หรือตัวอย่างจริงพร้อมตัวเลข\n"
        "▪️ 5-6: Insight — สิ่งที่ตระหนัก มุมมองใหม่ หรือ turning point\n"
        "▪️ 7-8: Engage — คำถามชวน comment หรือ call to action\n"
        "แต่ละ bullet: 1-2 ประโยค ภาษาพูดธรรมดา ไม่ประดิษฐ์ ตรงใจคนวัย 30-45\n"
        "จบด้วย hashtag 2-3 อัน\n"
        "ห้ามใช้ ** markdown ตอบแค่ caption"
    )
    for model in TEXT_MODELS:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                story = clean_text(resp.text)
                print(f"Story [{model}]:\n{story[:200]}...\n")
                return story
            except Exception as e:
                print(f"[{model}] story attempt {attempt+1} failed: {str(e)[:100]}")
    return ""  # fallback: empty → use quote as caption

# ─── 2. สร้างรูป (PIL + Kanit-Bold — ข้อความถูกต้อง 100%) ────────
FONT_PATH      = os.path.join(os.path.dirname(__file__), "fonts", "Kanit-Bold.ttf")
FONT_HASH_PATH = os.path.join(os.path.dirname(__file__), "fonts", "Kanit-Bold.ttf")
IMG_SIZE = 1080

_LEADING_VOWELS  = set('เแโใไ')
_COMBINING_CHARS = set('่้๊๋์ิีึืุูัํ็')

def _wrap_char(draw, text, font, max_width):
    """ตัดบรรทัด char-by-char — รองรับภาษาไทยที่ไม่มี space
    - combining chars (วรรณยุกต์/สระ) ไม่ขึ้นบรรทัดใหม่เด็ดขาด
    - สระนำหน้า (เแโใไ) ไม่ค้างท้ายบรรทัด — ดึงติดพยัญชนะถัดไป
    """
    lines, current = [], ""
    for ch in text:
        test = current + ch
        fits = draw.textbbox((0, 0), test, font=font)[2] <= max_width
        if fits or ch in _COMBINING_CHARS:
            current = test
        else:
            if current:
                if current[-1] in _LEADING_VOWELS:
                    orphan  = current[-1]
                    current = current[:-1]
                    if current:
                        lines.append(current)
                    current = orphan + ch
                else:
                    lines.append(current)
                    current = ch
            else:
                current = ch
    if current:
        lines.append(current)
    return lines or [text]


def _balance_last(draw, lines, font, max_width, min_ratio=0.42, min_chars=4):
    """ป้องกัน orphan บรรทัดสุดท้ายที่สั้นเกิน — merge 2 บรรทัดสุดท้ายแล้ว re-wrap"""
    if len(lines) <= 1:
        return lines
    last = lines[-1].strip()
    prev = lines[-2].strip()
    if not last or not prev:
        return lines
    last_w = draw.textbbox((0, 0), last, font=font)[2]
    prev_w = draw.textbbox((0, 0), prev, font=font)[2]
    # trigger ถ้า pixel ratio ต่ำ หรือ char น้อยมาก ("าได้", "ม?", "มี" ฯลฯ)
    is_orphan = (last_w < prev_w * min_ratio) or (len(last) <= min_chars)
    if not is_orphan:
        return lines
    merged   = prev + last
    total_w  = draw.textbbox((0, 0), merged, font=font)[2]
    target_w = min(max_width, int(total_w * 0.55))
    rebalanced = _wrap_char(draw, merged, font, target_w)
    if all(draw.textbbox((0, 0), l, font=font)[2] <= max_width for l in rebalanced):
        return lines[:-2] + rebalanced
    return lines


def wrap_thai(text, font, draw, max_width):
    """ตัดบรรทัดให้พอดีความกว้าง — char-by-char + balance orphan"""
    lines = _wrap_char(draw, text, font, max_width)
    return _balance_last(draw, lines, font, max_width)

def _build_lines(quote, font_main, font_hash, draw, max_w):
    """แยก hashtag + wrap content → คืน list of (text, font)"""
    raw_lines = quote.strip().split("\n")
    content_lines, hash_lines = [], []
    for l in raw_lines:
        (hash_lines if l.strip().startswith("#") else content_lines).append(l.strip())
    all_lines = []
    for l in content_lines:
        if not l:
            all_lines.append(("", font_main))
            continue
        for w in wrap_thai(l, font_main, draw, max_w):
            all_lines.append((w, font_main))
    all_lines.append(("", font_main))
    for l in hash_lines:
        if l:
            all_lines.append((l, font_hash))
    return all_lines

def generate_image(quote):
    print("Generating image (PIL)...")
    bkk = timezone(timedelta(hours=7))
    ts  = datetime.now(bkk).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"quote_{ts}.png")

    img  = Image.new("RGB", (IMG_SIZE, IMG_SIZE), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    PAD    = 100
    max_w  = IMG_SIZE - PAD * 2
    max_h  = IMG_SIZE - PAD * 2   # พื้นที่สูงสุดที่ text ใช้ได้
    LINE_GAP = 18

    # auto-fit: หา font size ใหญ่ที่สุดที่ยังพอดีกรอบ
    font_size = 82
    while font_size >= 36:
        font_main = ImageFont.truetype(FONT_PATH,      font_size)
        font_hash = ImageFont.truetype(FONT_HASH_PATH, int(font_size * 0.65))
        all_lines = _build_lines(quote, font_main, font_hash, draw, max_w)
        total_h = sum(draw.textbbox((0,0), t, font=f)[3] + LINE_GAP for t, f in all_lines)
        if total_h <= max_h:
            break
        font_size -= 2

    print(f"Font size: {font_size}")
    # all_lines พร้อมแล้วจาก loop สุดท้าย
    total_h = sum(draw.textbbox((0,0), t, font=f)[3] + LINE_GAP for t, f in all_lines)
    y = (IMG_SIZE - total_h) // 2

    for text, font in all_lines:
        if not text:
            y += draw.textbbox((0,0), "ก", font=font)[3] // 2
            continue
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        x = (IMG_SIZE - w) // 2
        color = (150, 150, 150) if font == font_hash else (255, 255, 255)
        draw.text((x+2, y+2), text, font=font, fill=(30, 30, 30))
        draw.text((x, y), text, font=font, fill=color)
        y += bbox[3] + LINE_GAP

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
        if isinstance(msg, dict):
            data = {"access_token": PAGE_ACCESS_TOKEN, "message": msg["message"]}
            if msg.get("picture_url"):
                data["attachment_url"] = msg["picture_url"]
        else:
            data = {"access_token": PAGE_ACCESS_TOKEN, "message": msg}
        resp = requests.post(
            f"https://graph.facebook.com/v25.0/{post_id}/comments",
            data=data
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
    story    = generate_story(topic, slot)
    img_path = generate_image(quote)
    post_facebook(img_path, story or quote)
