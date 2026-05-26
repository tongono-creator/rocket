# -*- coding: utf-8 -*-
"""threads.py — โพสรูปคำคม + caption ลง Threads อัตโนมัติ"""

import sys, io, os, re, base64, requests, time, random, tempfile
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai
from google.genai import types

GOOGLE_API_KEY       = os.environ.get("GOOGLE_API_KEY",       "")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID      = os.environ.get("THREADS_USER_ID",      "")
IMAGE_MODEL          = "gemini-2.0-flash-preview-image-generation"  # unused (PIL renders)
TEXT_MODELS          = ["gemini-3.5-flash", "gemini-2.5-flash"]
OUTPUT_DIR           = "output"

if not GOOGLE_API_KEY:
    try:
        from config import GOOGLE_API_KEY, THREADS_ACCESS_TOKEN, THREADS_USER_ID
    except ImportError:
        pass

os.makedirs(OUTPUT_DIR, exist_ok=True)
client = genai.Client(api_key=GOOGLE_API_KEY)

# ─── Topics (เหมือน post.py) ─────────────────────────────────────
# เช้า: เสียดสีคนทำงาน (Brutal Truths / Work Sarcasm)
MORNING_TOPICS = [
    "ขยันทำงานแทบตาย ได้รางวัลเป็นงานที่เพิ่มขึ้น",
    "การลาออกไม่ได้แก้ปัญหา แต่การไม่มีเงินแก้ปัญหาลาออกไม่ได้",
    "ทำงานหนักไม่เคยทำให้ใครรวย ถ้าทำงานหนักแล้วรวย ควายคงรวยที่สุดในโลก",
    "ประชุมที่ยาวนานที่สุด มักได้ข้อสรุปที่ไม่มีใครทำตาม",
    "คำว่า 'ครอบครัวเดียวกัน' ในที่ทำงาน มักใช้ตอนจะให้ทำโอฟรี",
    "การตื่นเช้าไปทำงานทำให้เรารู้ว่า เงินสำคัญกว่าการนอนขนาดไหน",
    "หัวหน้าบอกว่า 'เปิดใจคุยกันได้' แปลว่าให้เรารับฟังและทำตามเงียบๆ",
    "โบนัสคือจินตนาการ แต่งานค้างคือความจริง",
    "ทำงานมา 5 ปี สิ่งที่เพิ่มขึ้นอย่างเดียวคือน้ำหนักตัวและรอยคล้ำใต้ตา",
    "ประเมินผลงานปลายปีเป็นเรื่องลึกลับที่สุด ยิ่งกว่าสามเหลี่ยมเบอร์มิวด้า",
]
# กลางวัน: กระทู้พันทิปจำลอง (Financial Dilemma)
NOON_TOPICS = [
    "อายุ 35 เงินเดือน 40,000 แต่ไม่มีเงินเก็บเลย แปลกและล้มเหลวไหม?",
    "เงินเดือน 30k เช่าคอนโด 10k ถือว่าใช้ชีวิตเกินตัวไปหรือเปล่า?",
    "แฟนเงินเดือนน้อยกว่า 3 เท่า แต่หนี้เยอะกว่า 5 เท่า ควรคบต่อหรือพอแค่นี้?",
    "มีเงินเก็บ 1 ล้านแรก ควรเอาไปโปะบ้านก่อน หรือเอาไปลงทุนหุ้นดี?",
    "ทำงานงกๆ เก็บเงินได้ 5 แสน แต่พ่อแม่ขอเอาไปให้ญาติกู้ ควรให้ไหม?",
    "อายุ 30 มีหนี้บัตรเครดิต 2 แสน แต่ยังอยากผ่อนรถป้ายแดงเพื่อสร้างโปรไฟล์?",
    "ถ้ามีเงิน 10 ล้าน ตอนนี้ ควรลาออกมานอนเล่นเฉยๆ หรือทนทำงานต่อดี?",
    "อยากลาออกจากงานประจำมาทำธุรกิจส่วนตัว แต่มีภาระผ่อนบ้านเดือนละ 20k ทำไงดี?",
    "เพื่อนสนิทยืมเงิน 50,000 ไปแต่งงาน ผ่านมา 2 ปีไม่คืน แต่โพสต์ไปเที่ยวต่างประเทศ",
    "รายได้ 50k ให้พ่อแม่เดือนละ 15k แต่โดนบอกว่ากตัญญูน้อยไปเมื่อเทียบกับลูกป้า",
]
# เย็น-ค่ำ: สมการเปรียบเทียบ (Financial Battle)
EVENING_TOPICS = [
    "ผ่อนรถ 12,000/เดือน VS นั่ง BTS+Taxi อะไรเหนื่อยน้อยและคุ้มเงินกว่า?",
    "ซื้อบ้านชานเมือง 3 ล้าน VS เช่าคอนโดติดรถไฟฟ้า 15,000/เดือน เลือกแบบไหน?",
    "แต่งงานจัดงานหรูหราหมดไป 5 แสน VS จดทะเบียนสมรสแล้วเอาเงินไปเที่ยวรอบโลก?",
    "ส่งลูกเรียนอินเตอร์เทอมละแสน VS ส่งเรียนรัฐบาลแล้วเก็บเงินไว้ให้ลูกตอนโต?",
    "ผ่อน iPhone รุ่นล่าสุดเดือนละ 3,000 VS เอาเงินไปออมทอง/ออมหุ้นทุกเดือน?",
    "ซื้อบ้านมือสองมารีโนเวทเอง VS ซื้อบ้านมือหนึ่งในโครงการหรูหราไปเลย?",
    "กินกาแฟแก้วละ 150 ทุกวันเพื่อความสุข VS ชงกาแฟซองละ 5 บาทประหยัดเงิน?",
    "ฝากเงินในสหกรณ์ดอกเบี้ย 4% VS ซื้อกองทุนปันผลที่มีโอกาสขาดทุน?",
    "ลงทุนในหุ้นปันผลกินยาวๆ VS ลงทุนคอนโดปล่อยเช่าเพื่อมี Passive Income?",
    "ทำโอทีวันเสาร์ได้เงินเพิ่ม 1,500 VS นอนอยู่บ้านพักผ่อนชาร์จแบตชีวิต?",
]
# ดึก: แบกรับภาระ/ชีวิตจริง (Adulting Struggles / Life Truths)
LATE_TOPICS = [
    "คนวัย 35 ที่ตื่นมาพร้อมความรู้สึกว่า 'เรากำลังใช้ชีวิตเพื่อใครอยู่กันแน่'",
    "เหนื่อยแค่ไหนก็ล้มไม่ได้ เพราะข้างหลังมีพ่อแม่และลูกที่รอคอยเราอยู่",
    "ไม่มีอะไรน่ากลัวไปกว่าการเจ็บป่วยตอนอายุ 40 แล้วไม่มีประกันสุขภาพ",
    "การเติบโตเป็นผู้ใหญ่ทำให้รู้ว่า เพื่อนแท้เหลือไม่ถึง 3 คนก็หรูแล้ว",
    "เงินซื้อความสุขไม่ได้ แต่ช่วยให้เราไปนั่งร้องไห้บนรถหรูๆ แทนที่จะเป็นเบาะรถเมล์",
    "อิสระที่แท้จริงไม่ใช่การมีเงินร้อยล้าน แต่คือการปฏิเสธงานที่ไม่อยากทำได้",
    "เวลาผ่านไปเร็วเกินไป ทำงานตั้งแต่เช้าจรดค่ำ หันมาอีกทีอายุจะ 40 แล้ว",
    "ขอบคุณตัวเองที่พยุงชีวิตผ่านความกดดันในแต่ละวันมาได้จนถึงค่ำคืนนี้",
    "สิ่งที่น่ากลัวที่สุดในวัยทำงานคือ สุขภาพพังก่อนจะได้ใช้เงินที่หามาได้",
    "ในวันที่เหนื่อยล้าที่สุด สิ่งที่อยากได้ไม่ใช่เงินล้าน แต่คือความสงบเงียบๆ สักชั่วโมง",
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
    "morning": 0,   # Sarcastic Office/Work Truths
    "noon":    1,   # Financial Dilemma
    "evening": 2,   # Financial Battle
    "late":    3,   # Adulting Sarcastic Truths
}

CONTENT_STYLES = [
    # style 0: Sarcastic Office/Work Truths (Brutal Truths)
    (
        "เขียนคำคมเสียดสีชีวิตคนทำงาน/มนุษย์เงินเดือนแบบเจ็บๆ ตลกฮาๆ ชวนคอมเมนต์และแชร์จากหัวข้อ: {topic}\n"
        "ความยาว 2 บรรทัดสั้นๆ (ขึ้นบรรทัดใหม่ด้วย \\n หรือขึ้นบรรทัดใหม่จริงๆ ตรงกลางประโยคตามธรรมชาติ)\n"
        "ห้ามเกิน 60 ตัวอักษรรวม\n"
        "ใช้ภาษาพูดปกติ ห้ามประดิษฐ์คำคมสวยหรู ห้ามสอนสั่ง ห้ามใส่ข้อคิดดีๆ\n"
        "ท้ายใส่ hashtag คมๆ ฮาๆ 2 อัน\n"
        "ตอบแค่ข้อความคำคมเท่านั้น ห้ามใส่ป้ายกำกับใดๆ ทั้งสิ้น เช่น 'บรรทัด 1:', 'คำคม:'"
    ),
    # style 1: Financial Dilemma (กระทู้พันทิปจำลอง)
    (
        "ตั้งคำถามจำลองสไตล์กระทู้พันทิปชวนคิดและถกเถียงเรื่องเงิน/การใช้ชีวิตจากหัวข้อ: {topic}\n"
        "ความยาว 2 บรรทัดสั้นๆ ดึงดูดความสนใจให้อยากกดอ่านคอมเมนต์และมาแชร์เรื่องตัวเอง\n"
        "บรรทัดแรก: เกริ่นสถานการณ์หรือคำถาม\n"
        "บรรทัดสอง: ถามความคิดเห็นชวนคุย เช่น 'คิดยังไงกันบ้างครับ?', 'แปลกไหม?', 'แบบนี้ควรทำไงดี?'\n"
        "ห้ามเกิน 70 ตัวอักษรรวม\n"
        "ใช้ภาษาพูดปกติ ภาษาคนทั่วไป ไม่เอาป้ายกำกับใดๆ เช่น 'บรรทัด 1:', 'คำถาม:'\n"
        "ท้ายใส่ hashtag 2 อัน"
    ),
    # style 2: Financial Battle / Comparison (สมการเปรียบเทียบ)
    (
        "ตั้งหัวข้อเปรียบเทียบแบบเลือกฝั่ง ดวลเดือดความคุ้มค่าทางการเงินหรือการใช้ชีวิตจากหัวข้อ: {topic}\n"
        "รูปแบบ 2 บรรทัดสั้นๆ\n"
        "บรรทัดแรก: เปรียบเทียบสองฝั่งชัดเจน เช่น 'ผ่อนรถ 12,000/เดือน VS นั่ง BTS+Taxi'\n"
        "บรรทัดสอง: ถามความคุ้มค่าหรือให้เลือกฝั่ง เช่น 'แบบไหนประหยัดและชีวิตดีกว่า?', 'ทีมไหนรายงานตัวหน่อย?'\n"
        "ห้ามเกิน 70 ตัวอักษรรวม\n"
        "ใช้ภาษาพูดตลกขำขัน ชวนคนคิดเลขเถียงในคอมเมนต์ ห้ามใส่ป้ายกำกับใดๆ\n"
        "ท้ายใส่ hashtag 2 อัน"
    ),
    # style 3: Adulting Sarcastic Truths / Sarcasm (เสียดสีวัยสร้างตัว)
    (
        "เขียนประโยคตลกร้าย/ประชดประชันความจริงอันเจ็บปวดวัย 30-45 เรื่องการเงิน/ครอบครัว/การเติบโตจากหัวข้อ: {topic}\n"
        "ความยาว 2 บรรทัดสั้นๆ ดึงดูดใจวัยทำงานสุดๆ\n"
        "ใช้ภาษาพูดแบบเพื่อนสนิทคุยกันหรือโพสต์สเตตัสบ่นชีวิต ห้ามสอนเด็ดขาด\n"
        "ห้ามเกิน 60 ตัวอักษรรวม\n"
        "ท้ายใส่ hashtag 2 อัน\n"
        "ตอบแค่ข้อความ ห้ามใส่ป้ายกำกับใดๆ เช่น 'บรรทัด 1:'"
    ),
]

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

def clean_hook_lines(raw_text):
    text = clean_text(raw_text)
    if "|" in text:
        parts = text.split("|")
    else:
        parts = text.split("\n")
    label_pattern = r'^(ข้อความในโพสต์\\s*Facebook|Facebook\\s*Caption|Facebook\\s*caption|Caption|caption|ข้อความบนรูป|ข้อความในรูป|ข้อความ|คำบรรยาย|คำอธิบาย|บรรทัดที่\\s*\\d+|บรรทัด\\s*\\d+|ประโยคที่\\s*\\d+|ประโยค\\s*\\d+|Hook\\s*text|Hook|Line\\s*\\d+|[L|l]ine\\s*\\d+|\\d+)\\s*[:\\-\\.\\s]\\s*'
    cleaned_lines = []
    for part in parts:
        cleaned = re.sub(label_pattern, '', part, flags=re.IGNORECASE).strip()
        cleaned = cleaned.strip('"\'“”‘’')
        if cleaned:
            cleaned_lines.append(cleaned)
    return "\n".join(cleaned_lines)

def generate_quote(topic, slot="morning"):
    style_idx = SLOT_STYLE.get(slot, 0)
    style = CONTENT_STYLES[style_idx]
    prompt = style.format(topic=topic)
    print(f"Topic: {topic} | Slot: {slot} | Style: {style_idx}")
    for model in TEXT_MODELS:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                quote = clean_hook_lines(resp.text)
                print(f"Quote [{model}]:\n{quote}\n")
                return quote
            except Exception as e:
                print(f"[{model}] attempt {attempt+1} failed: {str(e)[:100]}")
                if attempt < 1:
                    time.sleep(10)
        print(f"[{model}] unavailable, trying next model...")
    raise RuntimeError("Quote generation failed on all models")

FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "Kanit-Bold.ttf")
IMG_SIZE  = 1080

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
    """ป้องกัน orphan บรรทัดสุดท้ายที่สั้นเกิน"""
    if len(lines) <= 1:
        return lines
    last = lines[-1].strip()
    prev = lines[-2].strip()
    if not last or not prev:
        return lines
    last_w = draw.textbbox((0, 0), last, font=font)[2]
    prev_w = draw.textbbox((0, 0), prev, font=font)[2]
    is_orphan = (last_w < prev_w * min_ratio) or (len(last) <= min_chars)
    if not is_orphan:
        return lines
    merged   = prev + " " + last
    total_w  = draw.textbbox((0, 0), merged, font=font)[2]
    target_w = min(max_width, int(total_w * 0.55))
    if " " in merged.strip():
        rebalanced = _wrap_words(draw, merged, font, target_w)
    else:
        rebalanced = _wrap_char(draw, merged, font, target_w)
    if all(draw.textbbox((0, 0), l, font=font)[2] <= max_width for l in rebalanced):
        return lines[:-2] + rebalanced
    return lines


def _wrap_words(draw, text, font, max_width):
    """ตัดจากช่องว่างก่อน เพื่อไม่ผ่าคำไทยกลางคำโดยไม่จำเป็น"""
    words = [w for w in text.split(" ") if w]
    if not words:
        return [text]
    lines, current = [], ""
    for word in words:
        test = word if not current else current + " " + word
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines


def wrap_thai(text, font, draw, max_width):
    """ตัดบรรทัดให้พอดีความกว้าง โดยพยายามรักษาคำ/วลีไทยไว้ก่อน"""
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return [text]

    if " " in text.strip():
        lines = _wrap_words(draw, text, font, max_width)
    else:
        # อย่ารีบผ่าคำไทยตอน font ยังใหญ่ ให้ auto-fit ลด font ก่อน
        lines = [text] if getattr(font, "size", 99) > 42 else _wrap_char(draw, text, font, max_width)
    return _balance_last(draw, lines, font, max_width)

def _build_lines(quote, font_main, font_hash, draw, max_w):
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
    path = os.path.join(OUTPUT_DIR, f"threads_{ts}.png")

    img  = Image.new("RGB", (IMG_SIZE, IMG_SIZE), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    PAD      = 100
    max_w    = IMG_SIZE - PAD * 2
    max_h    = IMG_SIZE - PAD * 2
    LINE_GAP = 18

    # auto-fit: หา font size ใหญ่ที่สุดที่พอดีกรอบ
    font_size = 124
    while font_size >= 36:
        font_main = ImageFont.truetype(FONT_PATH, font_size)
        font_hash = ImageFont.truetype(FONT_PATH, int(font_size * 0.65))
        all_lines = _build_lines(quote, font_main, font_hash, draw, max_w)
        total_h = sum(
            # actual rendered height = bottom - top (bbox[1] is negative for Thai tone marks)
            ((draw.textbbox((0, 0), t, font=f)[3] - draw.textbbox((0, 0), t, font=f)[1]) + LINE_GAP)
            if t else
            ((draw.textbbox((0, 0), "ก", font=f)[3] - draw.textbbox((0, 0), "ก", font=f)[1]) // 2 + LINE_GAP)
            for t, f in all_lines
        )
        width_ok = all(
            (not t) or draw.textbbox((0, 0), t, font=f)[2] <= max_w
            for t, f in all_lines
        )
        if total_h <= max_h and width_ok:
            break
        font_size -= 2

    print(f"Font size: {font_size}")
    # y = actual top pixel of text block (accounting for negative bbox[1])
    y = (IMG_SIZE - total_h) // 2

    for text, font in all_lines:
        if not text:
            # empty line spacer — use full actual height of reference char
            ref = draw.textbbox((0, 0), "ก", font=font)
            y += (ref[3] - ref[1]) // 2
            continue
        bbox = draw.textbbox((0, 0), text, font=font)
        w    = bbox[2] - bbox[0]
        x    = (IMG_SIZE - w) // 2
        # draw_y: shift down by -bbox[1] so actual top pixel = y
        # (bbox[1] is negative for Thai tone marks above baseline)
        draw_y = y - bbox[1]
        color  = (150, 150, 150) if font == font_hash else (255, 255, 255)
        draw.text((x + 2, draw_y + 2), text, font=font, fill=(30, 30, 30))
        draw.text((x,     draw_y),     text, font=font, fill=color)
        # advance by actual rendered height (top to bottom inclusive)
        y += (bbox[3] - bbox[1]) + LINE_GAP

    img.save(path)
    print(f"Image saved: {path}")
    return path

def upload_image_to_imgur(img_path):
    """Threads ต้องการ public image URL — upload ผ่าน ImgBB"""
    IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")
    if not IMGBB_API_KEY:
        try:
            from config import IMGBB_API_KEY
        except ImportError:
            raise RuntimeError("IMGBB_API_KEY ไม่มี — ต้องสมัคร imgbb.com แล้วใส่ใน config.py")
    with open(img_path, "rb") as f:
        img_data = base64.b64encode(f.read()).decode("utf-8")
    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": IMGBB_API_KEY, "image": img_data}
    )
    result = resp.json()
    if result.get("success"):
        url = result["data"]["url"]
        print(f"Image uploaded: {url}")
        return url
    raise RuntimeError(f"ImgBB upload failed: {result}")

def _create_and_publish(text, reply_to_id=None):
    """สร้าง text container แล้ว publish — ใช้สำหรับ reply comment"""
    data = {
        "media_type": "TEXT",
        "text": text,
        "access_token": THREADS_ACCESS_TOKEN,
    }
    if reply_to_id:
        data["reply_to_id"] = reply_to_id
    resp = requests.post(
        f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads",
        data=data
    )
    container_id = resp.json().get("id")
    if not container_id:
        print(f"Reply container error: {resp.json()}")
        return None
    time.sleep(3)
    resp2 = requests.post(
        f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish",
        data={"creation_id": container_id, "access_token": THREADS_ACCESS_TOKEN}
    )
    result = resp2.json()
    return result.get("id")

def post_threads(image_url, caption, img_path=None):
    print("Posting to Threads...")
    # Step 1: Create image container
    resp = requests.post(
        f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads",
        data={
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": caption,
            "access_token": THREADS_ACCESS_TOKEN,
        }
    )
    result = resp.json()
    if "id" not in result:
        print(f"Threads Error (create): {result}")
        raise SystemExit(1)
    container_id = result["id"]
    print(f"Container created: {container_id}")
    time.sleep(5)

    # Step 2: Publish
    resp2 = requests.post(
        f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish",
        data={"creation_id": container_id, "access_token": THREADS_ACCESS_TOKEN}
    )
    result2 = resp2.json()
    if "id" not in result2:
        print(f"Threads Error (publish): {result2}")
        raise SystemExit(1)
    post_id = result2["id"]
    print(f"Threads Posted! ID: {post_id}")

    # Step 3: Add reply comments
    from affiliate_utils import get_all_comments
    all_comments = get_all_comments(caption=caption, img_path=img_path)
    delay0 = random.uniform(60, 180)
    print(f"Waiting {delay0:.0f}s before first reply...")
    time.sleep(delay0)
    for i, msg in enumerate(all_comments, 1):
        text = msg["message"] if isinstance(msg, dict) else msg
        reply_id = _create_and_publish(text, reply_to_id=post_id)
        print(f"Reply {i} added! ID: {reply_id}")
        if i < len(all_comments):
            delay = random.uniform(30, 90)
            print(f"Waiting {delay:.0f}s before next reply...")
            time.sleep(delay)

# ─── Meme mode ────────────────────────────────────────────────────────
MEME_SUBREDDITS = [
    "funny", "memes", "dankmemes", "me_irl",
    "Unexpected", "therewasanattempt", "facepalm",
    "AnimalsBeingDerps", "WhatsWrongWithYourCat", "oddlyterrifying",
    "AbruptChaos", "Whatcouldgowrong",
]
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")
HEADERS_RSS = {"User-Agent": "Mozilla/5.0 (compatible; ThreadsBot/1.0; +github)"}


def get_meme_image():
    subreddit = random.choice(MEME_SUBREDDITS)
    url = f"https://www.reddit.com/r/{subreddit}/hot.rss"
    try:
        resp = requests.get(url, headers=HEADERS_RSS, timeout=10)
        resp.raise_for_status()
        root    = ET.fromstring(resp.content)
        ns      = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        posts = []
        for entry in entries:
            content   = entry.findtext("atom:content", "", ns)
            img_urls  = re.findall(r'https?://[^\s"<>]+\.(?:jpg|jpeg|png|gif|webp)', content or "")
            good_imgs = [u for u in img_urls if "i.redd.it" in u or "imgur.com" in u]
            if good_imgs:
                posts.append({"url": good_imgs[0], "subreddit": subreddit})
        if not posts:
            return None, None
        post = random.choice(posts[:10])
        print(f"Meme: r/{subreddit} | {post['url'][:60]}")
        return post["url"], subreddit
    except Exception as e:
        print(f"Reddit error: {e}")
        return None, None


def download_image(url):
    MAX_BYTES = 4 * 1024 * 1024
    try:
        resp = requests.get(url, headers=HEADERS_RSS, timeout=15, stream=True)
        resp.raise_for_status()
        data = b""
        for chunk in resp.iter_content(chunk_size=65536):
            data += chunk
            if len(data) > MAX_BYTES:
                return None
        suffix = ".jpg"
        for ext in IMAGE_EXTS:
            if url.lower().split("?")[0].endswith(ext):
                suffix = ext
                break
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(data)
        tmp.close()
        return tmp.name
    except Exception as e:
        print(f"Download failed: {e}")
        return None


def analyze_meme(img_path):
    """Vision ดูรูปว่าตลกยังไง"""
    with open(img_path, "rb") as f:
        img_data = f.read()
    prompt = (
        "ดูรูปนี้แล้วอธิบายสั้นๆ ภาษาไทยว่าเห็นอะไร หรือสถานการณ์ตลกอะไรในรูป 1-2 ประโยค "
        "ถ้าไม่มีอะไรน่าสนใจเลย ตอบว่า 'ไม่น่าสนใจ'"
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=img_data, mime_type="image/jpeg"),
                    types.Part.from_text(text=prompt),
                ],
            )
            result = resp.text.strip()
            print(f"Vision: {result}")
            return result
        except Exception as e:
            print(f"[{model}] vision failed: {e}")
    return None


def generate_funny_caption(image_desc, subreddit):
    prompt = (
        f"รูปจาก r/{subreddit}: {image_desc}\n\n"
        "เขียน caption ภาษาไทย ตลกๆ เหมือนโพส meme ของคนไทย\n"
        "1-2 ประโยคสั้นมาก ขำ เข้าใจง่าย ภาษาพูด ใส่ emoji ได้\n"
        "ท้ายใส่ hashtag 2-3 อัน\n"
        "ห้ามใช้ ** ตอบแค่ caption เลย"
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            return clean_text(resp.text.strip())
        except Exception as e:
            print(f"[{model}] funny caption failed: {e}")
    return "555 😂\n#meme #ตลก"


def run_meme_mode():
    """โหมดมีมตลก — Reddit → Vision → funny caption → Threads"""
    for attempt in range(4):
        img_url, subreddit = get_meme_image()
        if not img_url:
            continue
        img_path = download_image(img_url)
        if not img_path:
            continue
        desc = analyze_meme(img_path)
        if not desc or "ไม่น่าสนใจ" in desc:
            os.unlink(img_path)
            continue
        caption = generate_funny_caption(desc, subreddit)
        caption += f"\n📷 via r/{subreddit}"
        print(f"Funny caption:\n{caption}\n")
        # upload ผ่าน ImgBB
        hosted_url = upload_image_to_imgur(img_path)
        post_threads(hosted_url, caption, img_path=img_path)
        os.unlink(img_path)
        return
    print("Meme mode failed after 4 attempts, fallback to quote mode")
    run_quote_mode()


def run_quote_mode():
    """โหมดคำคม — PIL image + quote"""
    topic, slot = get_topic()
    quote    = generate_quote(topic, slot)
    img_path = generate_image(quote)
    img_url  = upload_image_to_imgur(img_path)
    post_threads(img_url, quote, img_path=img_path)
    if img_path and os.path.exists(img_path):
        os.unlink(img_path)


if __name__ == "__main__":
    if random.random() < 0.5:
        print("Mode: MEME")
        run_meme_mode()
    else:
        print("Mode: QUOTE")
        run_quote_mode()
