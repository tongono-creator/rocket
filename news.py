# -*- coding: utf-8 -*-
"""news.py — ดึงข่าวเทคโนโลยีและเรื่องราวน่าสนใจจาก Reddit แปลเป็นไทยด้วย Gemini Vision ทำรูปพาดหัว แล้วโพสต์ลง FB"""

import sys
import io
import os
import re
import time
import random
import argparse
import requests
import feedparser
from PIL import Image
from io import BytesIO
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai
from google.genai import types
from overlay_utils import add_overlay

# === CONFIG (ดึงจาก env vars หรือ config.py) ===
GOOGLE_API_KEY    = os.environ.get("GOOGLE_API_KEY", "")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
PAGE_ID           = os.environ.get("PAGE_ID", "111830598532037")
TEXT_MODELS       = ["gemini-2.5-flash", "gemini-3.5-flash"]
OUTPUT_DIR        = "output"
ACCENT_COLOR      = (255, 215, 0)  # Gold/Yellow สำหรับ Rocket21

if not GOOGLE_API_KEY:
    try:
        from config import GOOGLE_API_KEY, PAGE_ACCESS_TOKEN, PAGE_ID
    except ImportError:
        pass

os.makedirs(OUTPUT_DIR, exist_ok=True)
client = genai.Client(api_key=GOOGLE_API_KEY, http_options={'timeout': 90.0})

# --- Thai Helpers and Fallbacks ---
def contains_thai(text):
    if not text:
        return False
    return bool(re.search(r'[\u0e00-\u0e7f]', text))

def segment_thai_text(text, client=client):
    if not text or not contains_thai(text):
        return text
    prompt = (
        "You are an expert Thai word segmentation tool. "
        "Your task is to insert a zero-width space character (\\u200b) at every natural word boundary in the provided Thai text. "
        "Strict rules:\n"
        "1. Do NOT modify, delete, or add any words, characters, punctuation, spaces, or newlines of the original text. "
        "Keep the exact same characters and layout.\n"
        "2. Do NOT add any introductory or concluding remarks. Output ONLY the segmented text.\n"
        "3. Ensure words like 'หวยออก', 'เงินเก็บ', 'แสนแรก', 'ทำงาน' are segmented at their natural boundaries (e.g., 'หวย\\u200bออก' or left as 'หวยออก', but never break syllables awkwardly).\n\n"
        f"Text to segment:\n{text}"
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            segmented = resp.text.strip()
            clean_orig = text.replace('\\u200b', '')
            clean_seg = segmented.replace('\\u200b', '')
            if len(clean_orig) == len(clean_seg):
                return segmented
        except Exception as e:
            print(f"[{model}] segment_thai_text failed: {e}")
    return text

def translate_to_thai(text):
    if not text:
        return ""
    if contains_thai(text):
        return text
    prompt = f"Translate the following technology/science news text to natural Thai. Only output the translation, no explanation:\n\n{text}"
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            translated = resp.text.strip()
            if contains_thai(translated):
                return translated
        except Exception as e:
            print(f"[{model}] Translation failed: {e}")
    return text  # Fallback to original text if translation fails

FALLBACK_NEWS = [
    {
        "line1": "ความสำเร็จขั้นสุด",
        "line2": "นักวิทย์ผลิตแบตเตอรี่โซลิดสเตตสำเร็จ",
        "caption": "นักวิทยาศาสตร์ประสบความสำเร็จในการพัฒนาแบตเตอรี่โซลิดสเตต (Solid-State Battery) รุ่นใหม่ที่มีความหนาแน่นพลังงานสูงกว่าเดิมถึง 2 เท่า และสามารถชาร์จเต็มได้ภายในเวลาเพียง 5 นาทีครับ\n\nเทคโนโลยีนี้คาดว่าจะถูกนำมาใช้งานในรถยนต์ไฟฟ้า (EV) ยุคถัดไป ซึ่งจะช่วยแก้ปัญหาเรื่องระยะเวลาการชาร์จและเพิ่มความปลอดภัยอย่างมาก เนื่องจากไม่มีของเหลวไวไฟอยู่ภายในเหมือนแบตเตอรี่ลิเธียมไอออนทั่วไปครับ\n\nทุกท่านคิดว่าเทคโนโลยีแบตเตอรี่ใหม่นี้จะเปลี่ยนโฉมวงการรถยนต์ไฟฟ้าได้เร็วแค่ไหนครับ ลองคอมเมนต์คุยกันได้เลยครับ\n\n#เทคโนโลยี #แบตเตอรี่ #รถยนต์ไฟฟ้า"
    },
    {
        "line1": "เทคโนโลยีสุดล้ำ",
        "line2": "จีนสร้างศูนย์ข้อมูล AI ใต้น้ำเป็นที่แรก",
        "caption": "วิศวกรจีนประสบความสำเร็จในการจัดตั้งศูนย์ข้อมูล (Data Center) สำหรับ AI ใต้ทะเลลึกเพื่อใช้ประโยชน์จากน้ำทะเลเย็นในการช่วยระบายความร้อนให้กับเครื่องเซิร์ฟเวอร์ครับ\n\nการย้ายศูนย์ข้อมูลลงใต้น้ำช่วยประหยัดพลังงานไฟฟ้าที่ใช้ในระบบหล่อเย็นได้มากกว่า 40% และยังช่วยประหยัดพื้นที่บนบกที่มีราคาสูงอีกด้วย โดยระบบทั้งหมดถูกออกแบบมาให้ทนทานต่อแรงดันน้ำและการกัดกร่อนของเกลือทะเลได้เป็นอย่างดีครับ\n\nทุกท่านคิดว่าไอเดียการสร้างดาต้าเซ็นเตอร์ใต้น้ำแบบนี้จะกลายเป็นมาตรฐานใหม่ในอนาคตไหมครับ\n\n#ศูนย์ข้อมูลใต้น้ำ #ปัญญาประดิษฐ์ #เทคโนโลยีจีน"
    },
    {
        "line1": "การค้นพบใหม่",
        "line2": "นาซาพบเบาะแสน้ำเหลวบนดาวอังคาร",
        "caption": "ยานสำรวจรุ่นล่าสุดขององค์การนาซา (NASA) ได้ค้นพบหลักฐานใหม่ที่บ่งชี้ถึงการมีอยู่ของแหล่งน้ำไหลที่เป็นของเหลวใต้พื้นผิวดาวอังคารในอดีต ซึ่งอาจเป็นกุญแจสำคัญในการค้นหาสิ่งมีชีวิตนอกโลกครับ\n\nข้อมูลระบุว่าน้ำดังกล่าวอาจมีความเค็มจัดจนไม่แข็งตัวภายใต้อุณหภูมิที่หนาวเย็นของดาวอังคาร ทำให้นักวิทยาศาสตร์มีความหวังมากขึ้นในการส่งภารกิจสำรวจที่มีมนุษย์ควบคุมไปลงจอดในพื้นที่ดังกล่าวในอนาคตครับ\n\nคิดว่าเราจะได้เห็นมนุษย์คนแรกไปเหยียบดาวอังคารภายในทศวรรษนี้ไหมครับ ลองแบ่งปันมุมมองกันได้ครับ\n\n#นาซา #ดาวอังคาร #ดาราศาสตร์"
    }
]

# --- แหล่งข่าวซับเรดดิตยอดนิยม (เน้นเทคโนโลยี วิทยาศาสตร์ และเรื่องราวน่าสนใจระดับโลก) ---
NEWS_SUBREDDITS = [
    "technology",
    "science",
    "interestingasfuck",
    "nextfuckinglevel",
    "Damnthatsinteresting",
    "weird",
    "nottheonion"
]

def get_reddit_image(entry):
    """สกัดรูปภาพประกอบจาก feed entry ของ Reddit"""
    # 1. เช็ก media_thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        url = entry.media_thumbnail[0].get("url", "")
        if url and "redd.it" in url:
            return url

    # 2. ค้นหารูปในเนื้อหา (summary/content)
    for field in ["summary", "content"]:
        text = ""
        if field == "content" and hasattr(entry, "content"):
            text = entry.content[0].value
        elif field == "summary" and hasattr(entry, "summary"):
            text = entry.summary
        urls = re.findall(r'<img[^>]+src="([^"]+)"', text)
        for url in urls:
            if "redd.it" in url:
                return url
    return None

def fetch_interesting_news():
    """ดึงและคัดเลือกข่าวที่มีรูปภาพจาก Reddit"""
    random.shuffle(NEWS_SUBREDDITS)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for sub in NEWS_SUBREDDITS:
        url = f"https://www.reddit.com/r/{sub}/.rss"
        print(f"Fetching RSS from r/{sub}...")
        try:
            feed = feedparser.parse(url, request_headers=headers)
            entries = list(feed.entries)
            random.shuffle(entries)

            for entry in entries[:15]:
                img_url = get_reddit_image(entry)
                if not img_url:
                    continue

                # ตรวจสอบว่าเป็นไฟล์รูปและโหลดมาทดสอบเบื้องต้น
                try:
                    resp = requests.get(img_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code != 200:
                        continue
                    content_type = resp.headers.get("Content-Type", "")
                    if not content_type.startswith("image/"):
                        continue
                    img_bytes = resp.content
                    # ตรวจสอบความถูกต้องของภาพ
                    Image.open(BytesIO(img_bytes)).verify()
                    
                    return {
                        "img_bytes": img_bytes,
                        "reddit_title": getattr(entry, "title", ""),
                        "subreddit": sub,
                        "link": getattr(entry, "link", "")
                    }
                except Exception as e:
                    print(f"Image verify failed: {e}")
                    continue
        except Exception as e:
            print(f"Failed to fetch from r/{sub}: {e}")
            continue
    return None

def generate_news_content(img_bytes, reddit_title, sub, original_link):
    """ส่งให้ Gemini Vision ช่วยแปล วิเคราะห์ และแต่งข้อความพาดหัว+แคปชั่นข่าวในสไตล์แอดมินเพจผู้ชาย"""
    prompt = (
        f"This image is from the Reddit thread: '{reddit_title}' in r/{sub}.\n"
        "Analyze the Reddit title and the image together to understand the context. Then, generate highly engaging, informative tech/science news content in Thai.\n"
        "Output format must have exactly 3 sections separated by labels:\n"
        "===HOOK1=== [Hook Line 1: very short, 3-5 Thai words, e.g. 'ที่แรกในโลก', 'เทคโนโลยีใหม่', 'สุดล้ำ', 'วิทยาศาสตร์พบ']\n"
        "===HOOK2=== [Hook Line 2: very short, 4-7 Thai words, describing the core event/breakthrough, e.g. 'จีนตั้งศูนย์ข้อมูล AI ใต้น้ำ']\n"
        "===CAPTION=== [Facebook Caption: A detailed, highly informative explanation structured in 2-3 paragraphs. Expand on the facts, science, background, or impact of this news. Write in a friendly, polite, and professional male persona using 'ครับ' and 'ผม' or 'พี่'. Ask a question at the end to invite discussion. No markdown like **. Include hashtags and citation.]\n\n"
        "Requirements:\n"
        "- Write in natural, fluent Thai.\n"
        "- Maintain strict factual accuracy. Do not fabricate or speculate. Use real numbers or data if mentioned.\n"
        "- Hook lines and caption must be logical and consistent.\n"
        "- Do not use any markdown bolding (**) in the caption.\n"
    )

    part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
    
    for model in TEXT_MODELS:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=[part, prompt]
                )
                result = resp.text.strip()
                print(f"Gemini Response [{model}]:\n{result[:500]}...\n")

                line1 = "ข่าวใหม่วันนี้"
                line2 = ""
                caption = ""

                h1_match = re.search(r'===HOOK1===\s*(.*)', result, re.IGNORECASE)
                h2_match = re.search(r'===HOOK2===\s*(.*)', result, re.IGNORECASE)
                cap_match = re.search(r'===CAPTION===\s*(.*)', result, re.DOTALL | re.IGNORECASE)

                if h1_match:
                    line1 = h1_match.group(1).split('\n')[0].strip()
                if h2_match:
                    line2 = h2_match.group(1).split('\n')[0].strip()
                if cap_match:
                    caption = cap_match.group(1).strip()

                # คลีนป้ายกำกับที่อาจปนมาบนภาพพาดหัว
                label_pattern = r'^(ข้อความในโพสต์\s*Facebook|Facebook\s*Caption|Facebook\s*caption|Caption|caption|ข้อความบนรูป|ข้อความในรูป|ข้อความ|คำบรรยาย|คำอธิบาย|บรรทัดที่\s*\d+|บรรทัด\s*\d+|ประโยคที่\s*\d+|ประโยค\s*\d+|Hook\s*text|Hook|Line\s*\d+|[L|l]ine\s*\d+|\d+)\s*[:\-\.\s]\s*'
                line1 = re.sub(label_pattern, '', line1, flags=re.IGNORECASE).strip()
                line2 = re.sub(label_pattern, '', line2, flags=re.IGNORECASE).strip()
                line1 = line1.strip('"\'“”‘’')
                line2 = line2.strip('"\'“”‘’')

                # ประกอบที่มาของข่าว
                if original_link:
                    caption += f"\n.\nที่มา: {original_link}"

                return line1, line2, caption, False
            except Exception as e:
                print(f"[{model}] attempt {attempt + 1} failed: {e}")
                time.sleep(5)
                
    # Fallback if all models and attempts fail
    translated_title = translate_to_thai(reddit_title)
    if contains_thai(translated_title):
        line1 = "ข่าวเด่นวันนี้"
        line2 = translated_title[:30] if len(translated_title) <= 30 else translated_title[:27] + "..."
        caption = f"{translated_title}\n\nรายละเอียดเพิ่มเติมกำลังตามมาครับ ติดตามอัปเดตข่าวสารเทคโนโลยีกับพวกเราได้เลยครับ\n\n#เทคโนโลยี #ข่าวสาร"
        if original_link:
            caption += f"\n.\nที่มา: {original_link}"
        return line1, line2, caption, False

    fb = random.choice(FALLBACK_NEWS)
    caption = fb["caption"]
    if original_link:
        caption += f"\n.\nที่มา: {original_link}"
    return fb["line1"], fb["line2"], caption, True

def post_facebook(img_path, caption):
    """โพสต์รูปภาพข่าวพร้อมแคปชั่นลงเพจ Facebook"""
    print("Posting to Facebook...")
    try:
        api_url = f"https://graph.facebook.com/v25.0/{PAGE_ID}/photos"
        with open(img_path, "rb") as f:
            resp = requests.post(
                api_url,
                data={"access_token": PAGE_ACCESS_TOKEN, "caption": caption, "published": "true"},
                files={"source": ("news.png", f, "image/png")},
                timeout=60,
            )
        result = resp.json()
        if "id" in result:
            post_id = result.get("post_id") or result["id"]
            print(f"Posted Successfully! ID: {post_id}")
            add_comment(post_id, caption=caption, img_path=img_path)
            return post_id
        else:
            print(f"Post failed: {result}")
            return None
    except Exception as e:
        print(f"Facebook API error: {e}")
        return None

def add_comment(post_id, caption=None, img_path=None):
    """คอมเมนต์ลิงก์สินค้าแนะนำหรือข้อมูลสมาชิกร่วมกันหลังจากโพสต์"""
    try:
        from affiliate_utils import get_all_comments
        comments = get_all_comments(caption=caption, img_path=img_path)
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
                data=data,
                timeout=30
            )
            result = resp.json()
            if "id" in result:
                print(f"Comment {i} added: {result['id']}")
            else:
                print(f"Comment {i} error: {result}")
            if i < len(comments):
                time.sleep(random.uniform(30, 90))
    except Exception as e:
        print(f"Failed to post comments: {e}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run locally without posting to Facebook")
    args = parser.parse_args()

    print("=== Rocket21 News Bot ===")
    news = fetch_interesting_news()
    if not news:
        print("No suitable news with image found.")
        return

    print(f"Selected Subreddit: r/{news['subreddit']}")
    print(f"Title: {news['reddit_title']}")

    # โหลดไฟล์ภาพชั่วคราว
    temp_path = "temp_news.jpg"
    with open(temp_path, "wb") as f:
        f.write(news["img_bytes"])

    # เจนเนอเรตเนื้อหาข่าว
    line1, line2, caption, is_static_fallback = generate_news_content(
        news["img_bytes"], 
        news["reddit_title"], 
        news["subreddit"],
        news["link"]
    )
    line1 = segment_thai_text(line1, client)
    line2 = segment_thai_text(line2, client)
    print(f"Hook generated: {line1} | {line2}")
    print(f"Caption:\n{caption}\n")

    # ใส่ overlay ข้อความบนรูปภาพ
    out_path = os.path.join(OUTPUT_DIR, f"news_{int(time.time())}.jpg")
    try:
        img_to_overlay = None if is_static_fallback else temp_path
        final_img = add_overlay(img_to_overlay, line1, line2, accent_color=ACCENT_COLOR, out_path=out_path)
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass
        print(f"Overlay created: {final_img}")
    except Exception as e:
        print(f"Overlay failed: {e}")
        final_img = None if is_static_fallback else temp_path

    # โพสต์หรือหยุดทำแห้ง (dry-run)
    if args.dry_run:
        print(f"Dry-run mode complete. Local image path: {final_img}")
    else:
        post_facebook(final_img, caption)
        if os.path.exists(final_img):
            os.unlink(final_img)

if __name__ == "__main__":
    main()
