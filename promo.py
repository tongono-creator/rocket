# -*- coding: utf-8 -*-
"""promo.py — โพส promo เว็บ shopee-ranking สัปดาห์ละ 3 ครั้ง"""

import sys, io, os, base64, json, requests, time
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai
from google.genai import types

GOOGLE_API_KEY    = os.environ.get("GOOGLE_API_KEY",    "")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
PAGE_ID           = os.environ.get("PAGE_ID",           "111830598532037")
WEBSITE_URL       = "https://shopee-ranking.vercel.app/"
IMAGE_MODEL       = "gemini-3.1-flash-image-preview"
TEXT_MODEL        = "gemini-2.5-flash"
OUTPUT_DIR        = "output"

if not GOOGLE_API_KEY:
    try:
        from config import GOOGLE_API_KEY, PAGE_ACCESS_TOKEN, PAGE_ID
    except ImportError:
        pass

os.makedirs(OUTPUT_DIR, exist_ok=True)
client = genai.Client(api_key=GOOGLE_API_KEY, http_options={'timeout': 90.0})

PROMO_ANGLES = [
    "10 สินค้าขายดีที่สุดบน Shopee เดือนนี้ คุณซื้อไปแล้วกี่อัน?",
    "สินค้าไหนกำลังมาแรงบน Shopee ตอนนี้? เช็คได้เลย",
    "ก่อนซื้อของออนไลน์ เช็คอันดับก่อนดีกว่า ประหยัดได้เยอะมาก",
    "ของขายดีอันดับ 1 บน Shopee วันนี้คืออะไร?",
    "คนไทยกำลังซื้ออะไรกันเยอะที่สุดบน Shopee ดูได้เลย",
    "เปรียบเทียบราคา เช็คอันดับขายดี ก่อนตัดสินใจซื้อ",
]

def get_promo_angle():
    bkk = timezone(timedelta(hours=7))
    now = datetime.now(bkk)
    idx = (now.timetuple().tm_yday) % len(PROMO_ANGLES)
    return PROMO_ANGLES[idx]

def generate_promo_caption(angle):
    print(f"Generating promo caption: {angle}")
    resp = client.models.generate_content(
        model=TEXT_MODEL,
        contents=(
            f"สร้าง Facebook post caption ภาษาไทยแบบไวรัล เกี่ยวกับ: {angle}\n"
            f"เป็น post โปรโมตเว็บไซต์จัดอันดับสินค้าขายดีบน Shopee\n"
            f"เขียนให้น่าสนใจ กระตุ้นให้คนกดลิงก์ 3-5 บรรทัด\n"
            f"ท้ายสุดใส่ลิงก์: {WEBSITE_URL}\n"
            f"ใส่ emoji พอประมาณ hashtag 2-3 อัน\n"
            f"ตอบแค่ตัว caption เท่านั้น"
        )
    )
    return resp.text.strip()

def generate_promo_image(angle):
    print("Generating promo image...")
    prompt = (
        f"Square social media promotional image for Shopee product ranking website. "
        f"Dark background with orange/coral Shopee-style accent colors. "
        f"Bold modern design, shopping icons or product ranking visual. "
        f"Thai text concept: {angle}. "
        f"Eye-catching, viral Facebook post style. No actual text needed."
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
                    path = os.path.join(OUTPUT_DIR, f"promo_{ts}.png")
                    with open(path, "wb") as f:
                        f.write(data)
                    print(f"Image saved: {path}")
                    return path
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {str(e)[:100]}")
            if attempt < 2:
                time.sleep(15)
    raise RuntimeError("Image generation failed")

def post_facebook(img_path, caption):
    print("Posting promo to Facebook...")
    with open(img_path, "rb") as f:
        resp = requests.post(
            f"https://graph.facebook.com/v25.0/{PAGE_ID}/photos",
            data={"access_token": PAGE_ACCESS_TOKEN, "caption": caption, "published": "true"},
            files={"source": ("promo.png", f, "image/png")},
            timeout=60
        )
    result = resp.json()
    if "id" in result:
        print(f"Promo Posted! ID: {result['id']}")
    else:
        print(f"FB Error: {result}")
        raise SystemExit(1)

if __name__ == "__main__":
    angle   = get_promo_angle()
    caption = generate_promo_caption(angle)
    print(f"Caption:\n{caption}\n")
    img     = generate_promo_image(angle)
    post_facebook(img, caption)
