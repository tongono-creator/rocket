# -*- coding: utf-8 -*-
"""threads.py — โพสรูปคำคม + caption ลง Threads อัตโนมัติ"""

import sys, io, os, base64, requests, time
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai
from google.genai import types

GOOGLE_API_KEY       = os.environ.get("GOOGLE_API_KEY",       "")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID      = os.environ.get("THREADS_USER_ID",      "")
IMAGE_MODEL          = "gemini-3.1-flash-image-preview"
TEXT_MODEL           = "gemini-2.5-flash"
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

def generate_quote(topic):
    print(f"Topic: {topic}")
    resp = client.models.generate_content(
        model=TEXT_MODEL,
        contents=(
            f"สร้างคำคมภาษาไทยแบบไวรัลเกี่ยวกับ: {topic}\n"
            "สำหรับคนอายุ 30-45 ปี สั้น กระชับ 4-6 บรรทัด ให้รู้สึก relatable มาก\n"
            "ท้ายสุดใส่ hashtag 2-3 อัน ตอบแค่คำคมเท่านั้น ไม่ต้องมีคำอธิบาย"
        )
    )
    quote = resp.text.strip()
    print(f"Quote:\n{quote}\n")
    return quote

def generate_image(quote):
    print("Generating image...")
    prompt = (
        f"Square social media quote card. Pure black background. "
        f"White Thai text centered, large bold readable font. "
        f"Thai text: {quote}. "
        f"Minimalist, no decorations, viral Facebook post style."
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
                    path = os.path.join(OUTPUT_DIR, f"threads_{ts}.png")
                    with open(path, "wb") as f:
                        f.write(data)
                    print(f"Image saved: {path}")
                    return path
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {str(e)[:100]}")
            if attempt < 2:
                time.sleep(15)
    raise RuntimeError("Image generation failed after 3 attempts")

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

def post_threads(image_url, caption):
    print("Posting to Threads...")
    # Step 1: Create media container
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
    time.sleep(5)  # รอ container พร้อม

    # Step 2: Publish
    resp2 = requests.post(
        f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish",
        data={
            "creation_id": container_id,
            "access_token": THREADS_ACCESS_TOKEN,
        }
    )
    result2 = resp2.json()
    if "id" in result2:
        print(f"Threads Posted! ID: {result2['id']}")
    else:
        print(f"Threads Error (publish): {result2}")
        raise SystemExit(1)

if __name__ == "__main__":
    topic    = get_topic()
    quote    = generate_quote(topic)
    img_path = generate_image(quote)
    img_url  = upload_image_to_imgur(img_path)
    post_threads(img_url, quote)
