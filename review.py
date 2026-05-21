# -*- coding: utf-8 -*-
"""review.py — generate รูปรีวิวสินค้าจาก review_products.xlsx แล้วโพส FB Group"""

import sys, io, os, base64, requests, time, random, re
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai
from google.genai import types
import openpyxl

GOOGLE_API_KEY    = os.environ.get("GOOGLE_API_KEY",    "")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
PAGE_ID           = os.environ.get("PAGE_ID", "111830598532037")
IMAGE_MODEL       = "gemini-3-pro-image-preview"
TEXT_MODEL        = "gemini-2.5-flash"
OUTPUT_DIR        = "output"
EXCEL_PATH        = os.path.join(os.path.dirname(__file__), "review_products.xlsx")

if not GOOGLE_API_KEY:
    try:
        from config import GOOGLE_API_KEY, PAGE_ACCESS_TOKEN
    except ImportError:
        pass

os.makedirs(OUTPUT_DIR, exist_ok=True)
client = genai.Client(api_key=GOOGLE_API_KEY)

REVIEW_IMAGE_PROMPT = """Create a Thai ecommerce review-style poster using the UPLOADED PRODUCT IMAGE as the STRICT MAIN REFERENCE.

IMPORTANT PRODUCT RULES:
- DO NOT redesign the product
- DO NOT change product shape, colors, materials, proportions, buttons, textures, logos, or lighting style
- Product must look IDENTICAL to the uploaded image
- Only improve lighting, sharpness, reflections, and background composition
- Keep exact real product details
- No AI reinterpretation
- No fantasy redesign

LAYOUT:
- Top 70% = product showcase only
- Bottom 30% = text section only
- ALL text stays strictly inside the black bottom section
- No text over product area

TRANSITION:
- Add a smooth cinematic dark gradient fade between image area and black section
- Fade from transparent dark gray into deep matte black

TEXT STYLE:
- Large bold Thai typography
- White main text
- Highlight keywords with deep muted green
- Minimal wording
- Easy mobile readability

PRODUCT SECTION:
- One large main product image
- 2-3 smaller close-up detail images
- Clean rectangular layout
- White or light gray background
- Premium commercial lighting

STYLE:
- Modern Thai viral ecommerce review ad
- High CTR Facebook/TikTok thumbnail style
- Minimal and premium
- Clean composition
- No fake UI

FINAL RESULT:
- Looks like a real successful Thai review page
- Extremely clean and clickable
- Product remains 100% accurate to uploaded reference
- 4:5 aspect ratio
- Ultra realistic commercial ad quality

Product info to highlight: {highlights}"""

def load_next_product():
    wb = openpyxl.load_workbook(EXCEL_PATH)
    ws = wb.active
    for row in ws.iter_rows(min_row=2, values_only=False):
        no    = row[0].value
        detail= row[1].value
        shopee= row[2].value
        lazada= row[3].value
        imgurl= row[4].value
        promo = row[5].value
        posted= row[6].value

        # ข้าม sample row และ posted แล้ว
        if not detail or "วางรายละเอียด" in str(detail):
            continue
        if str(posted).strip().lower() == "done":
            continue
        if not shopee or "xxx" in str(shopee):
            continue

        return {
            "row": row[0].row,
            "no": no,
            "detail": str(detail).strip(),
            "shopee": str(shopee).strip(),
            "lazada": str(lazada).strip() if lazada else "",
            "image_url": str(imgurl).strip() if imgurl else "",
            "promo": str(promo).strip() if promo else "",
        }, wb, ws
    return None, wb, ws

def mark_posted(wb, ws, row_num):
    bkk = timezone(timedelta(hours=7))
    ts = datetime.now(bkk).strftime("%Y-%m-%d %H:%M")
    ws.cell(row=row_num, column=7, value=f"done {ts}")
    wb.save(EXCEL_PATH)
    print(f"Marked row {row_num} as done")

def clean_promo(raw):
    """เอาเฉพาะบรรทัดที่มี ฿ หรือ ลด หรือ % หรือ ส่งฟรี"""
    if not raw:
        return ""
    lines = raw.strip().splitlines()
    kept = [l.strip() for l in lines if re.search(r'฿|ลด|%|ส่งฟรี|flash|sale', l, re.IGNORECASE)]
    return " | ".join(kept[:3]) if kept else ""

def extract_highlights(detail, promo):
    """ให้ AI สกัดจุดเด่นจาก raw detail"""
    prompt = (
        f"จากรายละเอียดสินค้านี้:\n{detail}\n\n"
        f"สกัดออกมาเป็น bullet points ภาษาไทยสั้นๆ 3-5 จุดเด่น "
        f"เน้นประโยชน์ที่คนซื้อสนใจ ห้ามใส่ข้อมูลราคาหรือโปรโมชั่น "
        f"ตอบแค่ bullet points เท่านั้น"
    )
    resp = client.models.generate_content(model=TEXT_MODEL, contents=prompt)
    highlights = resp.text.strip()
    if promo:
        highlights += f"\n🔥 โปรตอนนี้: {promo}"
    return highlights

def download_image(url):
    """Download รูปแรกจาก URL (รองรับหลาย URL ในช่อง)"""
    # เอา URL แรก
    first_url = url.strip().split("\n")[0].strip()
    # แปลง .webp → download ปกติ
    resp = requests.get(first_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    if resp.status_code == 200:
        bkk = timezone(timedelta(hours=7))
        ts = datetime.now(bkk).strftime("%Y%m%d_%H%M%S")
        ext = "webp" if "webp" in first_url else "jpg"
        path = os.path.join(OUTPUT_DIR, f"product_{ts}.{ext}")
        with open(path, "wb") as f:
            f.write(resp.content)
        print(f"Product image downloaded: {path}")
        return path
    raise RuntimeError(f"Image download failed: {resp.status_code}")

def generate_review_image(img_path, highlights):
    print("Generating review image...")
    prompt = REVIEW_IMAGE_PROMPT.format(highlights=highlights)

    with open(img_path, "rb") as f:
        img_data = f.read()

    # detect mime type
    mime = "image/webp" if img_path.endswith(".webp") else "image/jpeg"

    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=IMAGE_MODEL,
                contents=[
                    types.Part.from_bytes(data=img_data, mime_type=mime),
                    prompt
                ],
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
                    out = os.path.join(OUTPUT_DIR, f"review_{ts}.png")
                    with open(out, "wb") as f:
                        f.write(data)
                    print(f"Review image saved: {out}")
                    return out
        except Exception as e:
            print(f"Image attempt {attempt+1} failed: {str(e)[:120]}")
            if attempt < 2:
                time.sleep(15)
    raise RuntimeError("Review image generation failed after 3 attempts")

def generate_caption(detail, shopee, lazada, promo, highlights):
    promo_line = f"\n🔥 {promo}" if promo else ""
    lazada_line = f"\n🛍️ Lazada → {lazada}" if lazada and "xxx" not in lazada else ""
    prompt = (
        f"เขียน Facebook post ภาษาไทยรีวิวสินค้าแบบจริงใจ ไม่ขายของเกินจริง\n"
        f"จุดเด่นสินค้า:\n{highlights}\n\n"
        f"รูปแบบ:\n"
        f"✅ ดี: ...\n"
        f"⚠️ ข้อเสีย: ...\n"
        f"💡 คุ้มไหม: ...\n\n"
        f"สั้นกระชับ อ่านง่าย สำหรับ Facebook Group รีวิวสินค้า\n"
        f"ท้าย post ใส่ hashtag 2-3 อัน\n"
        f"ตอบแค่ content เท่านั้น"
    )
    resp = client.models.generate_content(model=TEXT_MODEL, contents=prompt)
    caption = resp.text.strip()
    # ตัด AI prefix เช่น "ได้เลย...", "นี่คือ...", "---" ออก
    lines = caption.splitlines()
    while lines and (
        re.search(r'^(ได้เลย|นี่คือ|แน่นอน|โพสต์รีวิว|ครับ|ค่ะ|---)', lines[0].strip(), re.IGNORECASE)
        or lines[0].strip() in ("", "---")
    ):
        lines.pop(0)
    caption = "\n".join(lines).strip()
    caption += f"{promo_line}\n\n👉 Shopee → {shopee}{lazada_line}"
    return caption

def post_to_page(img_path, caption):
    print("Posting to Facebook Page...")
    with open(img_path, "rb") as f:
        resp = requests.post(
            f"https://graph.facebook.com/v25.0/{PAGE_ID}/photos",
            data={"access_token": PAGE_ACCESS_TOKEN, "caption": caption, "published": "true"},
            files={"source": ("review.png", f, "image/png")}
        )
    result = resp.json()
    if "id" in result:
        post_id = result.get("post_id") or result["id"]
        print(f"Page Posted! ID: {post_id}")
        print(f"https://www.facebook.com/{post_id}")
        return post_id
    else:
        print(f"FB Error: {result}")
        raise SystemExit(1)

if __name__ == "__main__":
    product, wb, ws = load_next_product()
    if not product:
        print("ไม่มีสินค้าที่ต้องโพส (ครบแล้วหรือยังไม่ได้เพิ่ม)")
        raise SystemExit(0)

    print(f"Product #{product['no']}: {product['detail'][:60]}...")

    promo_clean = clean_promo(product["promo"])
    highlights  = extract_highlights(product["detail"], promo_clean)
    print(f"Highlights:\n{highlights}\n")

    product_img = download_image(product["image_url"])
    review_img  = generate_review_image(product_img, highlights)
    caption     = generate_caption(
        product["detail"], product["shopee"],
        product["lazada"], promo_clean, highlights
    )
    print(f"Caption:\n{caption}\n")

    post_to_page(review_img, caption)
    mark_posted(wb, ws, product["row"])
