# -*- coding: utf-8 -*-
"""post.py — สร้างรูปคำคม + โพส Facebook อัตโนมัติ"""

import sys, io, os, re, requests, time, random
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

def clean_hook_lines(raw_text):
    text = clean_text(raw_text)
    
    # Check if we should split by pipe or newline
    if "|" in text:
        parts = text.split("|")
    else:
        parts = text.split("\n")
        
    # Pattern to strip prefixes like "บรรทัด 1: ", "ข้อความในโพสต์ Facebook: ", "1. ", etc.
    label_pattern = r'^(ข้อความในโพสต์\\s*Facebook|ข้อความบนรูป|ข้อความในรูป|ข้อความ|คำบรรยาย|คำอธิบาย|บรรทัดที่\\s*\\d+|บรรทัด\\s*\\d+|ประโยคที่\\s*\\d+|ประโยค\\s*\\d+|Hook\\s*text|Hook|Line\\s*\\d+|[L|l]ine\\s*\\d+|\\d+)\\s*[:\\-\\.\\s]\\s*'
    
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


def generate_story(topic, slot="morning"):
    """สร้าง bullet narrative caption สำหรับ Facebook post description"""
    if slot == "morning":
        # Sarcastic Office/Work Truths
        story_details = (
            "เขียน Facebook caption แบบ ▪️ bullet narrative — เรื่องราวเสียดสีชีวิตคนทำงาน/มนุษย์เงินเดือนแบบตลกขำขันและจริงใจสุดๆ\n"
            "โครงสร้าง:\n"
            "▪️ 1-2: Setup — ปวดใจกับตารางงาน การตื่นนอน หรือการทำงานหนักที่ไม่มีใครเห็นหัว\n"
            "▪️ 3-4: Reality — พฤติกรรมที่ต้องทำเพื่อเอาชีวิตรอด เช่น ดื่มกาแฟ 3 แก้ว แกล้งยิ้มในที่ประชุม หรือปลอบใจตัวเอง\n"
            "▪️ 5-6: Twist/Sarcastic Truth — ความจริงอันโหดร้ายแต่ขำแห้ง เช่น ขยันไปก็ได้งานเพิ่ม หรือโบนัสที่หักภาษีหมด\n"
            "▪️ 7-8: Engage — ใครตื่นเช้ามาเจออะไรแบบนี้บ่อยๆ ลองมาแชร์วีรกรรมความฮาในคอมเมนต์หน่อย"
        )
    elif slot == "noon":
        # Financial Dilemma
        story_details = (
            "เขียน Facebook caption แบบ ▪️ bullet narrative — เจาะประเด็นกระทู้เงินเดือนยอดฮิต/การวางแผนชีวิตที่เป็นปัญหากลืนไม่เข้าคายไม่ออก\n"
            "โครงสร้าง:\n"
            "▪️ 1-2: Scenario — ตั้งประเด็นจำลอง เช่น เรื่องอายุ เงินเดือน หนี้สิน หรือค่าเช่าบ้านที่ตึงมือสุดๆ\n"
            "▪️ 3-4: Breakdown — ทำไมคนยุคนี้ถึงเจอปัญหานี้กันเยอะ ตัวเลขค่าครองชีพหรือแรงกดดันทางสังคม\n"
            "▪️ 5-6: Perspectives — มุมมองฝั่งประหยัด VS ฝั่งให้รางวัลชีวิต/สร้างโอกาส\n"
            "▪️ 7-8: Engage — ถ้าเป็นคุณเจอปัญหานี้ จะตัดสินใจเลือกทางไหน? มาโหวตแสดงความคิดเห็นใต้โพสต์กัน"
        )
    elif slot == "evening":
        # Financial Battle
        story_details = (
            "เขียน Facebook caption แบบ ▪️ bullet narrative — สมการวิเคราะห์ดวลเปรียบเทียบค่าใช้จ่าย 2 ฝั่งในชีวิตประจำวันคนทำงาน\n"
            "โครงสร้าง:\n"
            "▪️ 1-2: Battle — แนะนำการดวล เช่น ผ่อนรถ VS นั่งรถไฟฟ้า, ซื้อบ้าน VS เช่าคอนโด\n"
            "▪️ 3-4: Calculation — คำนวณตัวเลขคร่าวๆ (ค่าผ่อน, ดอกเบี้ย, ค่าเดินทาง, ค่าเสียเวลา) ให้เห็นความต่าง\n"
            "▪️ 5-6: Pros & Cons — ข้อดีข้อเสียของแต่ละฝั่ง (เช่น ความสะดวกสบาย VS อิสรภาพทางการเงิน)\n"
            "▪️ 7-8: Engage — ทีมไหนได้เปรียบกว่ากัน? อยู่ฝั่งไหนคอมเมนต์ถกเถียงกันมาได้เลย"
        )
    else:
        # Late (Adulting Struggles / Life Truths)
        story_details = (
            "เขียน Facebook caption แบบ ▪️ bullet narrative — เรื่องราวลึกซึ้งเกี่ยวกับการสู้ชีวิต แบกรับภาระครอบครัว และความเหนื่อยล้าของคนวัย 30-45\n"
            "โครงสร้าง:\n"
            "▪️ 1-2: Reflection — ความเหนื่อยสะสมหลังหมดวัน หรือการคิดทบทวนชีวิตในความเงียบ\n"
            "▪️ 3-4: Struggle — การแบกภาระทั้งพ่อแม่ ลูก และความรับผิดชอบส่วนตัวที่แทบไม่มีเวลาให้ตัวเอง\n"
            "▪️ 5-6: Insight — ปลอบประโลมจิตใจ ปรับมุมมอง หรือให้กำลังใจว่าการสู้มาถึงตรงนี้ก็เก่งมากแล้ว\n"
            "▪️ 7-8: Engage — คืนนี้เหนื่อยไหม? มีอะไรที่อยากขอบคุณตัวเองมากที่สุด? ส่งกำลังใจให้กันในคอมเมนต์ได้เลย"
        )

    prompt = (
        f"หัวข้อ: {topic}\n\n"
        f"{story_details}\n"
        "ใช้ ▪️ นำหน้าทุก bullet — 6-8 จุด เล่าเรื่องมีความต่อเนื่องและตลกจริงใจ ภาษาพูดธรรมดาคนวัย 30-45\n"
        "จบด้วย hashtag 2-3 อัน ห้ามใช้ ** markdown ตอบเฉพาะตัว caption"
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
        width_ok = all(
            (not t) or draw.textbbox((0, 0), t, font=f)[2] <= max_w
            for t, f in all_lines
        )
        if total_h <= max_h and width_ok:
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
