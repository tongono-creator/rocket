# -*- coding: utf-8 -*-
"""post.py — สร้างรูปคำคม + โพส Facebook อัตโนมัติ"""

import sys, io, os, base64, json, requests, time, random
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

# ─── Topic rotation (30 วัน × 3 slots = 90 โพสไม่ซ้ำ) ──────────
MORNING_TOPICS = [
    "แรงบันดาลใจเช้า สำหรับคนวัย 30-45 ที่กำลังดิ้นรนสร้างอนาคต",
    "ความจริงของชีวิตคนทำงานยุคนี้ที่ไม่มีใครบอก",
    "เงินเก็บไม่เคยพอ แต่ชีวิตต้องไปต่อ",
    "วิธีคิดของคนที่ประสบความสำเร็จจากศูนย์",
    "ทำไมคนเก่งถึงยังรู้สึกว่าตัวเองไม่พอ",
    "ความฝันที่ถูกชีวิตจริงกดทับทุกวัน",
    "บทเรียนการเงินที่ไม่มีสอนในโรงเรียน",
    "อย่ารอให้พร้อม จงเริ่มเลย แม้จะยังไม่มีทุน",
    "ความแตกต่างระหว่างคนรวยและคนจนคือนิสัยเหล่านี้",
    "เช้านี้เตือนตัวเองว่า เราเกิดมาเพื่อมากกว่านี้",
]
NOON_TOPICS = [
    "ชีวิตคนอายุ 30-45 ที่ต้องแบกทั้งลูกและพ่อแม่",
    "ค่าใช้จ่ายที่ไม่คาดคิดที่ทำให้เงินเก็บหายไปทุกเดือน",
    "ความเครียดของมนุษย์เงินเดือนที่ไม่มีใครเข้าใจ",
    "ทำงานหนักแค่ไหน ทำไมยังไม่รวยสักที",
    "สิ่งที่อยากบอกตัวเองตอนอายุ 25",
    "ความจริงที่เจ็บปวดของการเป็นพ่อแม่ในยุคนี้",
    "เมื่อความฝันชนกับความจริงเรื่องเงิน",
    "ทำไมคนรุ่นเราถึงเหนื่อยกว่าคนรุ่นก่อน",
    "ถ้าเงินเดือนเท่านี้จะวางแผนยังไงให้มีเงินเก็บ",
    "ความสำเร็จที่ซื้อไม่ได้ด้วยเงิน แต่สร้างได้ด้วยวินัย",
]
EVENING_TOPICS = [
    "สิ่งที่ควรทำกับเงินก่อนอายุ 45",
    "บทสรุปวันนี้ ชีวิตสอนอะไร",
    "ทำไมคนส่วนใหญ่เกษียณไม่ได้ตามที่ฝัน",
    "ความสำเร็จที่แท้จริงไม่ใช่แค่เรื่องเงิน",
    "ถึงเวลาหยุดแลกเวลากับเงิน แล้วให้เงินทำงานแทน",
    "ทบทวนชีวิต ทบทวนเป้าหมาย ก่อนนอน",
    "ความสุขเล็กๆ ที่คนวัยนี้มักมองข้าม",
    "ปลดหนี้ได้อย่างไร บทเรียนจากคนที่ทำสำเร็จ",
    "อย่าปล่อยให้ความกลัวหยุดคุณจากอิสรภาพทางการเงิน",
    "คืนนี้ขอบคุณตัวเองที่ยังสู้มาได้จนถึงตรงนี้",
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
    else:
        return EVENING_TOPICS[day_idx], "evening"

CONTENT_STYLES = [
    # style 0: คำคมกระแทกใจ
    (
        "สร้างคำคมภาษาไทยแบบไวรัลเกี่ยวกับ: {topic}\n"
        "สั้นมาก 1-2 ประโยคเท่านั้น กระแทกใจ หยุดนิ้วเลื่อนได้ทันที\n"
        "ใช้ภาษาพูดธรรมดา ไม่วิจิตร คนอายุ 30-45 อ่านแล้วรู้สึกเลย\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น"
    ),
    # style 1: เรื่องเล่าสั้น relatable
    (
        "เขียน Facebook post ภาษาไทยเล่าเรื่องชีวิตจริงเกี่ยวกับ: {topic}\n"
        "สั้น 3-4 บรรทัด เหมือนเพื่อนโพส เข้าใจง่าย คนอ่านแล้วพยักหน้า\n"
        "ลงท้ายด้วยประโยคที่ให้คนอยากคอมเม้น\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น"
    ),
    # style 2: คำถามสั้นกระตุ้น
    (
        "เขียน Facebook post ภาษาไทยตั้งคำถามเกี่ยวกับ: {topic}\n"
        "1 คำถามสั้นๆ ที่คนอ่านแล้วต้องคิด อยากตอบ อยากแชร์\n"
        "ไม่เกิน 2 บรรทัด ภาษาง่าย พูดตรงๆ\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น"
    ),
    # style 3: Tips กระชับ
    (
        "เขียน Facebook post ภาษาไทย tips เกี่ยวกับ: {topic}\n"
        "3 ข้อสั้นๆ ข้อละ 1 บรรทัด ใช้ได้ทันที ไม่อ้อมค้อม\n"
        "เริ่มด้วยหัวข้อดึงดูด 1 บรรทัด\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น"
    ),
    # style 4: ก่อน vs หลัง
    (
        "เขียน Facebook post ภาษาไทยเปรียบเทียบ ก่อน vs หลัง เกี่ยวกับ: {topic}\n"
        "สั้น 2-3 บรรทัด เห็นภาพชัด ขำหรือจริงใจ คนแชร์ได้เลย\n"
        "ภาษาพูด ไม่เป็นทางการ\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น"
    ),
]

# ─── 1. สร้างคำคม ──────────────────────────────────────────────
def generate_quote(topic):
    bkk = timezone(timedelta(hours=7))
    now = datetime.now(bkk)
    style_idx = (now.timetuple().tm_yday * 3 + now.hour) % len(CONTENT_STYLES)
    style = CONTENT_STYLES[style_idx]
    prompt = style.format(topic=topic)
    print(f"Topic: {topic} | Style: {style_idx}")
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

# ─── 2. สร้างรูป ────────────────────────────────────────────────
def generate_image(quote):
    print("Generating image...")
    prompt = (
        f"Square social media quote card. Pure solid black background, NO border, NO white frame, NO padding, image fills edge to edge. "
        f"White Thai text centered, large bold readable font, maximum 2-3 lines only. "
        f"Thai text: {quote}. "
        f"Minimalist, no decorations, no frame, no border, bleed to edges, viral Thai Facebook scroll-stopping style."
    )
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=IMAGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"]
                )
            )
            for part in resp.candidates[0].content.parts:
                if part.inline_data:
                    data = part.inline_data.data
                    if isinstance(data, str):
                        data = base64.b64decode(data)
                    bkk = timezone(timedelta(hours=7))
                    ts = datetime.now(bkk).strftime("%Y%m%d_%H%M%S")
                    path = os.path.join(OUTPUT_DIR, f"quote_{ts}.png")
                    with open(path, "wb") as f:
                        f.write(data)
                    print(f"Image saved: {path}")
                    return path
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {str(e)[:100]}")
            if attempt < 2:
                time.sleep(15)
    raise RuntimeError("Image generation failed after 3 attempts")

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
    quote    = generate_quote(topic)
    img_path = generate_image(quote)
    post_facebook(img_path, quote)
