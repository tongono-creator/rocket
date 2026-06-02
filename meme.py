# -*- coding: utf-8 -*-
"""meme.py — Reddit-sourced 2-panel comic strip generator featuring consistent Rocket21 character"""

import sys
import io
import os
import re
import base64
import requests
import time
import random
import tempfile
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai
from google.genai import types
from google.genai.types import HttpOptions

GOOGLE_API_KEY    = os.environ.get("GOOGLE_API_KEY",    "")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
PAGE_ID           = os.environ.get("PAGE_ID",           "111830598532037")
IMAGE_MODELS      = ["gemini-2.5-flash-image", "gemini-3.1-flash-image-preview", "gemini-2.0-flash-preview-image-generation"]
TEXT_MODELS       = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.5-pro", "gemini-1.5-pro"]
OUTPUT_DIR        = "output"
FONT_PATH         = os.path.join(os.path.dirname(__file__), "fonts", "Sarabun-ExtraBold.ttf")

if not GOOGLE_API_KEY:
    try:
        from config import GOOGLE_API_KEY, PAGE_ACCESS_TOKEN, PAGE_ID
    except ImportError:
        pass

os.makedirs(OUTPUT_DIR, exist_ok=True)
client = genai.Client(api_key=GOOGLE_API_KEY, http_options=HttpOptions(timeout=300000))

HISTORY_FILE = "posted_history.txt"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except Exception:
            return []
    return []

def save_to_history(item):
    items = load_history()
    items.append(item)
    items = items[-300:] # Cap history
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            for it in items:
                f.write(it + "\n")
    except Exception as e:
        print(f"Error saving history: {e}")

MEME_TOPICS_HISTORY_FILE = "posted_meme_topics.txt"

def load_meme_topics_history():
    if os.path.exists(MEME_TOPICS_HISTORY_FILE):
        try:
            with open(MEME_TOPICS_HISTORY_FILE, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except Exception:
            return []
    return []

def save_to_meme_topics_history(topic):
    items = load_meme_topics_history()
    items.append(topic)
    items = items[-100:] # Cap at 100 entries
    try:
        with open(MEME_TOPICS_HISTORY_FILE, "w", encoding="utf-8") as f:
            for it in items:
                f.write(it + "\n")
    except Exception as e:
        print(f"Error saving meme topics history: {e}")


# ─── Reddit Meme Scraping ───────────────────────────────────────────
MEME_SUBREDDITS = ["OfficeHumor", "workplaceculture", "memes", "dankmemes", "me_irl", "funny"]
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")
HEADERS_RSS = {"User-Agent": "Mozilla/5.0 (compatible; RocketMemeBot/1.0; +github)"}

def get_reddit_meme(history=None):
    if history is None:
        history = set()
    
    subs = list(MEME_SUBREDDITS)
    random.shuffle(subs)
    
    for subreddit in subs:
        url = f"https://www.reddit.com/r/{subreddit}/hot.rss"
        try:
            resp = requests.get(url, headers=HEADERS_RSS, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)
            
            posts = []
            for entry in entries:
                title = entry.findtext("atom:title", "", ns).strip()
                content = entry.findtext("atom:content", "", ns) or ""
                
                img_urls = re.findall(r'https?://[^\s"<>]+\.(?:jpg|jpeg|png|gif|webp)', content)
                good_imgs = [u for u in img_urls if ("i.redd.it" in u or "imgur.com" in u) and u not in history]
                
                if good_imgs and title:
                    posts.append({
                        "url": good_imgs[0], 
                        "title": title,
                        "subreddit": subreddit
                    })
            
            if posts:
                post = random.choice(posts[:10])
                print(f"Selected Reddit post: r/{subreddit} | {post['title'][:60]} | URL: {post['url']}")
                return post
        except Exception as e:
            print(f"Failed to fetch RSS for r/{subreddit}: {e}")
            continue
            
    return None

def download_meme_image(url):
    MAX_BYTES = 4 * 1024 * 1024 # 4MB max
    try:
        resp = requests.get(url, headers=HEADERS_RSS, timeout=20, stream=True)
        resp.raise_for_status()
        data = b""
        for chunk in resp.iter_content(chunk_size=65536):
            data += chunk
            if len(data) > MAX_BYTES:
                print("Image too large, skipping")
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

# ─── Gemini Vision Joke-to-Scenario Mapping ─────────────────────────
def analyze_meme_to_scenario(img_path, reddit_title, recent_topics=None):
    with open(img_path, "rb") as f:
        img_data = f.read()
        
    mime_type = "image/jpeg"
    if img_path.lower().endswith(".png"):
        mime_type = "image/png"
    elif img_path.lower().endswith(".webp"):
        mime_type = "image/webp"
    elif img_path.lower().endswith(".gif"):
        mime_type = "image/gif"

    recent_topics_str = ""
    if recent_topics:
        recent_topics_str = (
            "\n[คำเตือนสำคัญ: ห้ามออกไอเดียหรือเขียนข้อความพาดหัวที่มีความหมายซ้ำหรือใกล้เคียงกับหัวข้อเหล่านี้อย่างเด็ดขาด เนื่องจากเป็นเรื่องที่เพิ่งโพสต์ไปแล้ว]:\n"
            + "\n".join([f"- {t}" for t in recent_topics])
            + "\n"
        )

    prompt = (
        "นี่คือมีม (Meme) ภาษาอังกฤษจาก Reddit ของต่างประเทศ\n"
        f"ชื่อโพสต์ต้นฉบับ: \"{reddit_title}\"\n\n"
        "งานของคุณคือวิเคราะห์อารมณ์ขันและมุกตลกในมีมนี้ จากนั้นแปลงมุกนี้มาทำเป็นบทการ์ตูน 2 ช่องแนว 'ความคาดหวัง vs ความจริง' (Before vs After) หรือสถานการณ์หักมุมที่เข้ากับคนทำงานออฟฟิศ/ผู้ใหญ่ชาวไทย (อายุ 30+)\n\n"
        "บทการ์ตูนจะมีตัวละครหลักเป็นหนุ่มไทยอายุ 30 ปี ผมสั้นสีดำเรียบร้อย สวมแว่นตากรอบโลหะทรงสี่เหลี่ยมผืนผ้าบาง ใส่เสื้อเชิ้ตสีขาวมีรอยยับเล็กน้อย\n\n"
        "**กฎเหล็กเพื่อความหลากหลายและป้องกันเนื้อหาซ้ำซาก**:\n"
        "1. ห้ามเลือกใช้มุกหัวหน้าสั่งงานด่วน หรือทำงานในวันหยุด/วันพักร้อนโดยเด็ดขาด (เช่น 'วันหยุดแสนสุข' vs 'งานด่วนจากบอส', 'ตอนพักร้อน' vs 'บอสส่งอีเมลมาตาม' เป็นต้น) เพราะเราโพสต์เรื่องนี้ซ้ำบ่อยเกินไปแล้ว\n"
        "2. พยายามเลือกใช้ประเด็นที่หลากหลายขึ้นของคนทำงานและผู้ใหญ่วัย 30+ ตัวอย่างหัวข้อที่ควรนำมาเล่น:\n"
        "   - การเงินและหนี้สิน (เช่น การออมเงินแสนแรก, การผ่อนของ 0% 10 เดือน, ซื้อของฟุ่มเฟือยประชดชีวิต, กระเป๋าตังค์แบนปลายเดือน)\n"
        "   - สุขภาพร่างกาย (เช่น ตื่นนอนแล้วปวดหลัง/คอเคล็ด, ปวดบ่าไหล่จากออฟฟิศซินโดรม, นอนไม่หลับ, กินของมันแล้วกรดไหลย้อน, ตรวจสุขภาพประจำปี)\n"
        "   - ชีวิตประจำวันออฟฟิศทั่วไป (เช่น เมนูอาหารกลางวันที่คิดไม่ตก, ตื่นสายในวันรถติด, การหลบหน้าเพื่อนร่วมงาน, ประชุมที่คุยเรื่องเดิมซ้ำๆ, รอเวลาเลิกงาน)\n"
        "   - ความสัมพันธ์และไลฟ์สไตล์ (เช่น การเปรียบเทียบตัวเองกับเพื่อนรุ่นเดียวกัน, การไปปาร์ตี้แล้วง่วงนอนตั้งแต่สามทุ่ม, การซื้อของลดราคามารกบ้าน)\n"
        f"{recent_topics_str}\n"
        "กรุณาสร้างและอธิบายองค์ประกอบสำหรับการ์ตูน 2 ช่องนี้ โดยตอบกลับเป็นรูปแบบ JSON ที่มีคีย์ดังนี้:\n"
        "1. label1_th: ข้อความพาดหัวภาษาไทยของช่องที่ 1 (สั้นกระชับ 3-7 คำ อธิบายบริบทความหวัง/ช่วงแรก) เช่น 'ตอนตั้งใจจะเก็บเงิน' หรือ 'ตอนวางแผนจะตื่นมาออกกำลังกาย'\n"
        "2. scene1_en: คำอธิบายภาพช่องที่ 1 เป็นภาษาอังกฤษ (15-25 คำ) เพื่อใช้ป้อนให้ AI วาดรูป (ตัวละครหลักสีหน้าผ่อนคลาย/มีความหวัง ทำกิจกรรมตามหัวข้อ เช่น Thai man in 30s holding piggy bank with a bright smile)\n"
        "3. label2_th: ข้อความพาดหัวภาษาไทยของช่องที่ 2 (สั้นกระชับ 3-7 คำ อธิบายความจริงอันโหดร้าย/จุดหักมุม) เช่น 'ช้อปปิ้งออนไลน์ตอนเที่ยงคืน' หรือ 'ตื่นมาปวดหลังคอเคล็ดจนลุกไม่ขึ้น'\n"
        "4. scene2_en: คำอธิบายภาพช่องที่ 2 เป็นภาษาอังกฤษ (15-25 คำ) เพื่อใช้ป้อนให้ AI วาดรูป (ตัวละครหลักสีหน้ากังวล/เหงื่อตก/ช็อกค้าง เช่น Same Thai man staring at a massive stack of online shopping boxes in shock, sweat drops)\n"
        "5. caption: แคปชั่นภาษาไทย 1 ย่อหน้าสั้นๆ (2-4 ประโยค) สไตล์แอดมินเพจผู้ชาย (ใช้หางเสียงครับ/ผม/พี่ เสมอ และห้ามใช้หัวข้อหรือเรื่องสั่งงานด่วนเป็นแก่นหลักของแคปชั่น) ชวนให้คนกดคอมเมนต์แชร์เรื่องตัวเอง ท้ายข้อความใส่แฮชแท็ก 2-3 อัน\n\n"
        "กรุณาตอบเป็น JSON ในรูปแบบนี้เท่านั้น (ห้ามมี markdown codeblock หรือคำนำหน้าใดๆ):\n"
        "{\n"
        "  \"label1_th\": \"...\",\n"
        "  \"scene1_en\": \"...\",\n"
        "  \"label2_th\": \"...\",\n"
        "  \"scene2_en\": \"...\",\n"
        "  \"caption\": \"...\"\n"
        "}"
    )

    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=img_data, mime_type=mime_type),
                    types.Part.from_text(text=prompt),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            result_text = resp.text.strip()
            data = json.loads(result_text)
            return (
                data.get("label1_th", "").strip(),
                data.get("scene1_en", "").strip(),
                data.get("label2_th", "").strip(),
                data.get("scene2_en", "").strip(),
                data.get("caption", "").strip()
            )
        except Exception as e:
            print(f"[{model}] scenario analysis failed: {e}")
            time.sleep(5)
            
    raise RuntimeError("Scenario analysis failed on all models")

# ─── Comic Strip Visual Settings ─────────────────────────────────────
ROCKET_CHARACTER = (
    "Thai man in his early 30s, short neat black hair, thin rectangular metal-frame glasses, "
    "white button-up shirt slightly wrinkled. SAME character must appear in this panel."
)

ART_STYLE = (
    "ART STYLE: Thai manga comic panel illustration. Clean thick black outlines. "
    "Flat cel-shaded colors. Slightly chibi proportions with expressive faces. "
    "Warm color palette — blues, warm grays, soft yellows. "
    "Rich background showing context clearly (office, home, street). "
    "ABSOLUTELY NO speech bubbles — not empty, not filled, not any balloon shape. "
    "NO thought bubbles. NO text or captions anywhere in the image. "
    "Story told ENTIRELY through character expression and body language. "
    "Wide horizontal composition. The main character must be fully visible and centered in the frame, "
    "with generous safety margins (at least 25% empty background space) at both the top and the bottom. "
    "Do not crop the character's head or body to the edges; keep the character relatively compact within the center "
    "so they fit perfectly when cropped to a wide panel, without white outer border."
)

def generate_panel_image(scene_en, panel_num):
    prompt = (
        f"Draw a single comic panel illustration. "
        f"{ROCKET_CHARACTER} "
        f"Scene: {scene_en}. "
        f"{ART_STYLE}"
    )
    for model in IMAGE_MODELS:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model,
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
                        path = os.path.join(OUTPUT_DIR, f"panel{panel_num}_{ts}.png")
                        with open(path, "wb") as f:
                            f.write(data)
                        print(f"Panel {panel_num} saved: {path} (model={model})")
                        return path
            except Exception as e:
                err = str(e)[:120]
                print(f"Panel {panel_num} [{model}] attempt {attempt+1} failed: {err}")
                if "404" in err or "not found" in err.lower():
                    break
                if attempt < 2:
                    time.sleep(15)
    raise RuntimeError(f"Panel {panel_num} generation failed — all models exhausted")

def stitch_panels(img1_path, img2_path, label1, label2):
    W, H = 1080, 1080
    panel_h = H // 2  # 540px each panel
    canvas = Image.new("RGB", (W, H), (240, 240, 240))
    
    for idx, (ipath, label) in enumerate([(img1_path, label1), (img2_path, label2)]):
        img = Image.open(ipath).convert("RGB")
        iw, ih = img.size
        # Crop to 2:1 ratio from center
        target_ratio = W / panel_h
        if iw / ih > target_ratio:
            new_w = int(ih * target_ratio)
            left = (iw - new_w) // 2
            img = img.crop((left, 0, left + new_w, ih))
        else:
            new_h = int(iw / target_ratio)
            top = int(max(0, (ih - new_h) // 2.5))
            img = img.crop((0, top, iw, top + new_h))
            
        img = img.resize((W, panel_h), Image.LANCZOS)
        canvas.paste(img, (0, idx * panel_h))
        
        # Draw label text
        draw = ImageDraw.Draw(canvas)
        try:
            font = ImageFont.truetype(FONT_PATH, 42)
        except Exception:
            font = ImageFont.load_default()
            
        MARGIN = 28
        tx = MARGIN
        ty = idx * panel_h + MARGIN
        # 8-direction outline
        for dx, dy in [(-3,-3),(-3,0),(-3,3),(0,-3),(0,3),(3,-3),(3,0),(3,3)]:
            draw.text((tx + dx, ty + dy), label, font=font, fill=(0, 0, 0))
        draw.text((tx, ty), label, font=font, fill=(255, 255, 255))
        
    draw = ImageDraw.Draw(canvas)
    draw.line([(0, panel_h), (W, panel_h)], fill=(20, 20, 20), width=4)
    
    bkk = timezone(timedelta(hours=7))
    ts = datetime.now(bkk).strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(OUTPUT_DIR, f"meme_comic_{ts}.jpg")
    canvas.save(out_path, "JPEG", quality=92)
    print(f"Stitched comic saved: {out_path}")
    return out_path

# ─── Facebook Post and Comments ──────────────────────────────────────
def post_facebook(img_path, caption):
    print("Posting to Facebook...")
    with open(img_path, "rb") as f:
        resp = requests.post(
            f"https://graph.facebook.com/v25.0/{PAGE_ID}/photos",
            data={"access_token": PAGE_ACCESS_TOKEN, "caption": caption, "published": "true"},
            files={"source": ("meme.jpg", f, "image/jpeg")},
            timeout=60
        )
    result = resp.json()
    if "id" in result:
        post_id = result.get("post_id") or result["id"]
        print(f"Posted successfully! ID: {post_id}")
        add_comment(post_id)
        return post_id
    else:
        print(f"FB Error: {result}")
        raise SystemExit(1)

def add_comment(post_id):
    from affiliate_utils import get_all_comments
    comments = get_all_comments()
    delay0 = random.uniform(60, 180)
    print(f"Waiting {delay0:.0f}s before first comment...")
    time.sleep(delay0)
    for i, msg in enumerate(comments, 1):
        if isinstance(msg, dict):
            data = {"access_token": PAGE_ACCESS_TOKEN, "message": msg["message"]}
            pic = msg.get("picture_url", "")
            if pic and pic.startswith("http"):
                data["attachment_url"] = pic
        else:
            data = {"access_token": PAGE_ACCESS_TOKEN, "message": msg}
            
        if not data.get("message", "").strip():
            print(f"Comment {i} skipped (empty message)")
            continue
            
        resp = requests.post(
            f"https://graph.facebook.com/v25.0/{post_id}/comments",
            data=data,
            timeout=60
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

# ─── Main Execution ──────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run locally and map scenario without generating images or posting")
    parser.add_argument("--dry-run-image", action="store_true", help="Run locally, map scenario, generate images and stitch, but skip posting")
    args = parser.parse_args()

    history = set(load_history())
    topics_history = load_meme_topics_history()
    
    # Step 1: Scrape Reddit Meme
    post = get_reddit_meme(history)
    if not post:
        print("No new memes found in Reddit feeds.")
        sys.exit(0)
        
    img_url = post["url"]
    reddit_title = post["title"]
    subreddit = post["subreddit"]

    # Step 2: Download Image for Vision Analysis
    tmp_path = download_meme_image(img_url)
    if not tmp_path:
        print("Failed to download meme image.")
        sys.exit(1)

    try:
        # Step 3: Analyze and map to 2-panel cartoon scenario using Gemini
        print("Analyzing meme with Gemini Vision (passing topics history for negative constraints)...")
        label1, scene1, label2, scene2, caption = analyze_meme_to_scenario(tmp_path, reddit_title, recent_topics=topics_history)
        
        caption_with_via = f"{caption}\n\n📷 via r/{subreddit}"
        topic_summary = f"{label1} - {label2}"
        
        print("\n--- [GEMINI COMIC SCENARIO MAP] ---")
        print(f"Reddit Title: {reddit_title}")
        print(f"Topic Summary:  {topic_summary}")
        print(f"Panel 1 Label:  {label1}")
        print(f"Panel 1 Prompt: {scene1}")
        print(f"Panel 2 Label:  {label2}")
        print(f"Panel 2 Prompt: {scene2}")
        print(f"Caption:\n{caption_with_via}\n")

        # Step 4: Conditional Image Generation & Stitching
        if args.dry_run:
            print("\nDry run completed successfully. Image generation and posting skipped.")
            return

        print("Generating Panel 1...")
        img1 = generate_panel_image(scene1, panel_num=1)
        
        print("Generating Panel 2...")
        img2 = generate_panel_image(scene2, panel_num=2)
        
        print("Stitching panels...")
        comic_path = stitch_panels(img1, img2, label1, label2)
        
        # Clean up panel files
        for p in [img1, img2]:
            try:
                os.unlink(p)
            except Exception:
                pass

        # Step 5: Post or Dry Run Image
        if args.dry_run_image:
            print(f"\nDry run image completed successfully. Comic saved to: {comic_path}. Posting skipped.")
        else:
            post_facebook(comic_path, caption_with_via)
            save_to_history(img_url)
            save_to_meme_topics_history(topic_summary)
            
    finally:
        # Clean up downloaded temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

if __name__ == "__main__":
    main()
