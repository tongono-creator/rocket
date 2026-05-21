# -*- coding: utf-8 -*-
"""threads.py — โพสรูปคำคม + caption ลง Threads อัตโนมัติ"""

import sys, io, os, base64, requests, time, random
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai
from google.genai import types

GOOGLE_API_KEY       = os.environ.get("GOOGLE_API_KEY",       "")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID      = os.environ.get("THREADS_USER_ID",      "")
IMAGE_MODEL          = "gemini-2.0-flash-preview-image-generation"  # unused (PIL renders)
TEXT_MODELS          = ["gemini-2.5-flash", "gemini-2.0-flash"]
OUTPUT_DIR           = "output"

if not GOOGLE_API_KEY:
    try:
        from config import GOOGLE_API_KEY, THREADS_ACCESS_TOKEN, THREADS_USER_ID
    except ImportError:
        pass

os.makedirs(OUTPUT_DIR, exist_ok=True)
client = genai.Client(api_key=GOOGLE_API_KEY)

# ─── Topics (เหมือน post.py) ─────────────────────────────────────
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
        return MORNING_TOPICS[day_idx]
    elif hour < 16:
        return NOON_TOPICS[day_idx]
    else:
        return EVENING_TOPICS[day_idx]

CONTENT_STYLES = [
    "สร้างคำคมภาษาไทยแบบไวรัลเกี่ยวกับ: {topic}\nสั้นมาก 1-2 ประโยคเท่านั้น กระแทกใจ หยุดนิ้วเลื่อนได้ทันที ภาษาพูดธรรมดา คนอายุ 30-45 อ่านแล้วรู้สึกเลย\nท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น",
    "เขียน Facebook post ภาษาไทยเล่าเรื่องชีวิตจริงเกี่ยวกับ: {topic}\nสั้น 3-4 บรรทัด เหมือนเพื่อนโพส เข้าใจง่าย คนอ่านแล้วพยักหน้า ลงท้ายด้วยประโยคที่ให้คนอยากคอมเม้น\nท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น",
    "เขียน Facebook post ภาษาไทยตั้งคำถามเกี่ยวกับ: {topic}\n1 คำถามสั้นๆ ที่คนอ่านแล้วต้องคิด อยากตอบ อยากแชร์ ไม่เกิน 2 บรรทัด ภาษาง่าย พูดตรงๆ\nท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น",
    "เขียน Facebook post ภาษาไทย tips เกี่ยวกับ: {topic}\n3 ข้อสั้นๆ ข้อละ 1 บรรทัด ใช้ได้ทันที ไม่อ้อมค้อม เริ่มด้วยหัวข้อดึงดูด 1 บรรทัด\nท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น",
    "เขียน Facebook post ภาษาไทยเปรียบเทียบ ก่อน vs หลัง เกี่ยวกับ: {topic}\nสั้น 2-3 บรรทัด เห็นภาพชัด ขำหรือจริงใจ คนแชร์ได้เลย ภาษาพูด ไม่เป็นทางการ\nท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น",
]

def generate_quote(topic):
    bkk = timezone(timedelta(hours=7))
    now = datetime.now(bkk)
    style_idx = (now.timetuple().tm_yday * 3 + now.hour) % len(CONTENT_STYLES)
    prompt = CONTENT_STYLES[style_idx].format(topic=topic)
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

FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "Kanit-Bold.ttf")
IMG_SIZE  = 1080

def wrap_thai(text, font, draw, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
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
    path = os.path.join(OUTPUT_DIR, f"threads_{ts}.png")

    img  = Image.new("RGB", (IMG_SIZE, IMG_SIZE), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_main = ImageFont.truetype(FONT_PATH, 78)
    font_hash = ImageFont.truetype(FONT_PATH, 50)
    PAD, max_w = 80, IMG_SIZE - 160

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
        draw.text((x+2, y+2), text, font=font, fill=(30, 30, 30))
        draw.text((x, y), text, font=font, fill=color)
        y += bbox[3] + line_gap

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

def post_threads(image_url, caption):
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
    all_comments = get_all_comments()
    delay0 = random.uniform(60, 180)
    print(f"Waiting {delay0:.0f}s before first reply...")
    time.sleep(delay0)
    for i, msg in enumerate(all_comments, 1):
        reply_id = _create_and_publish(msg, reply_to_id=post_id)
        print(f"Reply {i} added! ID: {reply_id}")
        if i < len(all_comments):
            delay = random.uniform(30, 90)
            print(f"Waiting {delay:.0f}s before next reply...")
            time.sleep(delay)

if __name__ == "__main__":
    topic    = get_topic()
    quote    = generate_quote(topic)
    img_path = generate_image(quote)
    img_url  = upload_image_to_imgur(img_path)
    post_threads(img_url, quote)
