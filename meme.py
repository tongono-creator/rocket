# -*- coding: utf-8 -*-
"""meme.py — Reddit meme parser with Gemini translation, overlay rendering and Facebook post"""

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
import overlay_utils

GOOGLE_API_KEY    = os.environ.get("GOOGLE_API_KEY",    "")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
PAGE_ID           = os.environ.get("PAGE_ID",           "111830598532037")
TEXT_MODELS       = ["gemini-2.5-flash", "gemini-2.0-flash"]
OUTPUT_DIR        = "output"

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

# ─── Reddit Meme Scraping ───────────────────────────────────────────
MEME_SUBREDDITS = ["OfficeHumor", "workplaceculture", "memes", "dankmemes", "me_irl", "funny"]
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")
HEADERS_RSS = {"User-Agent": "Mozilla/5.0 (compatible; RocketMemeBot/1.0; +github)"}

def get_reddit_meme(history=None):
    if history is None:
        history = set()
    
    # Shuffle subreddits to get different themes
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
                
                # Extract image URL from HTML content
                img_urls = re.findall(r'https?://[^\s"<>]+\.(?:jpg|jpeg|png|gif|webp)', content)
                good_imgs = [u for u in img_urls if ("i.redd.it" in u or "imgur.com" in u) and u not in history]
                
                if good_imgs and title:
                    posts.append({
                        "url": good_imgs[0], 
                        "title": title,
                        "subreddit": subreddit
                    })
            
            if posts:
                # Pick one of the top posts
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

# ─── Gemini Vision Translation ──────────────────────────────────────
def analyze_meme_image(img_path, reddit_title):
    with open(img_path, "rb") as f:
        img_data = f.read()
        
    mime_type = "image/jpeg"
    if img_path.lower().endswith(".png"):
        mime_type = "image/png"
    elif img_path.lower().endswith(".webp"):
        mime_type = "image/webp"
    elif img_path.lower().endswith(".gif"):
        mime_type = "image/gif"

    prompt = (
        "นี่คือมีม (Meme) ภาษาอังกฤษจาก Reddit ของต่างประเทศ\n"
        f"ชื่อโพสต์ต้นฉบับ: \"{reddit_title}\"\n\n"
        "งานของคุณคือแสดงความเป็นผู้เชี่ยวชาญด้านอารมณ์ขัน แปลความหมายเชิงเสียดสีและมุกตลกในมีมนี้ให้เป็นมุกที่โดนใจวัยทำงานคนไทย (อายุ 30+) โดยการคิดพาดหัวและเขียนแคปชั่นตามข้อกำหนดต่อไปนี้:\n\n"
        "1. พาดหัวแบบไทย (Thai Overlay Text): คิดประโยคสั้นๆ 2 บรรทัดที่อธิบายมีมนี้เป็นภาษาไทยแนวพาดหัวเด็ดๆ ขำๆ\n"
        "   - บรรทัดที่ 1 (headline_accent): สีทอง (Accent) สั้นกระชับ (2-6 คำ) เช่น 'เมื่อบอกบอสว่าใกล้เสร็จ'\n"
        "   - บรรทัดที่ 2 (headline_white): สีขาว (White) หักมุม/ความจริงอันโหดร้าย (2-6 คำ) เช่น 'แต่ยังไม่ได้สร้างไฟล์'\n"
        "2. แคปชั่น (Caption): เขียน 1 ย่อหน้าสั้นๆ แนวพูดคุยเป็นมิตรตลกๆ ภาษาธรรมชาติ (ความยาวประมาณ 2-4 บรรทัด) ในบุคลิกแอดมินเพจผู้ชาย (ใช้หางเสียงครับ/ผม/พี่ เสมอ) ชวนให้คนอ่านรู้สึกอินตามและคอมเมนต์แชร์เรื่องของตัวเอง\n"
        "3. แฮชแท็ก (Hashtags): ใส่แฮชแท็ก 2-3 อัน ท้ายข้อความแคปชั่น\n\n"
        "ตอบกลับในรูปแบบ JSON เท่านั้น โดยมีรูปแบบตามคีย์ดังนี้:\n"
        "{\n"
        "  \"headline_accent\": \"...\",\n"
        "  \"headline_white\": \"...\",\n"
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
                data.get("headline_accent", "").strip(),
                data.get("headline_white", "").strip(),
                data.get("caption", "").strip()
            )
        except Exception as e:
            print(f"[{model}] vision analysis attempt failed: {e}")
            time.sleep(5)
            
    raise RuntimeError("Meme vision analysis failed on all models")

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
    parser.add_argument("--dry-run", action="store_true", help="Run locally and render image without posting")
    args = parser.parse_args()

    history = set(load_history())
    
    # Step 1: Scrape Reddit Meme
    post = get_reddit_meme(history)
    if not post:
        print("No new memes found in Reddit feeds.")
        sys.exit(0)
        
    img_url = post["url"]
    reddit_title = post["title"]
    subreddit = post["subreddit"]

    # Step 2: Download Image
    tmp_path = download_meme_image(img_url)
    if not tmp_path:
        print("Failed to download meme image.")
        sys.exit(1)

    try:
        # Step 3: Analyze using Gemini
        print("Analyzing meme with Gemini Vision...")
        headline_accent, headline_white, caption = analyze_meme_image(tmp_path, reddit_title)
        
        caption_with_via = f"{caption}\n\n📷 via r/{subreddit}"
        
        print("\n--- [GEMINI LOCALIZATION RESULTS] ---")
        print(f"Reddit Title: {reddit_title}")
        print(f"Accent line:  {headline_accent}")
        print(f"White line:   {headline_white}")
        print(f"Caption:\n{caption_with_via}\n")

        # Step 4: Render Text Overlay Matichon Style
        # Accent color = Gold (255, 215, 0)
        GOLD_ACCENT = (255, 215, 0)
        
        bkk = timezone(timedelta(hours=7))
        ts = datetime.now(bkk).strftime("%Y%m%d_%H%M%S")
        rendered_jpg_path = os.path.join(OUTPUT_DIR, f"meme_overlay_{ts}.jpg")
        
        print("Rendering overlay on image...")
        overlay_utils.add_overlay(
            img_path=tmp_path,
            line1=headline_accent,
            line2=headline_white,
            accent_color=GOLD_ACCENT,
            out_path=rendered_jpg_path
        )
        print(f"Rendered image saved to: {rendered_jpg_path}")

        # Step 5: Post or Dry Run
        if args.dry_run:
            print("\nDry run completed successfully. Posting skipped.")
        else:
            post_facebook(rendered_jpg_path, caption_with_via)
            save_to_history(img_url)
            
    finally:
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

if __name__ == "__main__":
    main()
