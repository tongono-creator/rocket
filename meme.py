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
import hashlib
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

def reddit_title_key(title):
    """Stable dedup key for a Reddit post's identity (prefix 'title:').
    Catches reposts that reuse the same title/image under a new URL or headline."""
    norm = re.sub(r"[^\w฀-๿]+", "", (title or "").strip().lower())
    if not norm:
        return ""
    return "title:" + hashlib.md5(norm.encode("utf-8")).hexdigest()[:16]

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
                
                if good_imgs and title and reddit_title_key(title) not in history:
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
        "งานของคุณคือวิเคราะห์อารมณ์ขัน มุกตลก และแก่นของเรื่อง (Core Joke) ในมีมนี้ จากนั้น **แปลและดัดแปลงมุกนี้ตรงๆ** มาทำเป็นบทการ์ตูน 2 ช่องแนว 'ความคาดหวัง vs ความจริง' (Before vs After) หรือสถานการณ์หักมุมที่ตรงตามมีมต้นฉบับ โดยปรับให้เข้ากับบริบทคนไทยออฟฟิศ/ผู้ใหญ่ชาวไทย (อายุ 30+) โดยใช้ตัวละครหลักตัวเดิม\n\n"
        "บทการ์ตูนจะมีตัวละครหลักเป็นหนุ่มไทยอายุ 30 ปี ผมสั้นสีดำเรียบร้อย สวมแว่นตากรอบโลหะทรงสี่เหลี่ยมผืนผ้าบาง ใส่เสื้อเชิ้ตสีขาวมีรอยยับเล็กน้อย\n\n"
        "**กฎเหล็กสำหรับมุกการ์ตูน (Comic Strip Rules)**:\n"
        "1. **ห้ามแต่งมุกใหม่ขึ้นมาเองเด็ดขาด**: มุกตลกในการ์ตูนทั้ง 2 ช่องและแคปชั่นจะต้องเป็นเรื่องเดียวกับมีมภาษาอังกฤษต้นฉบับเท่านั้น ห้ามนำเรื่องที่ไม่เกี่ยวข้อง เช่น เรื่องผ่อนของ บัตรเครดิต ปวดหลัง หรืออื่นๆ มาใส่หากมีมต้นฉบับไม่ได้พูดถึงเรื่องนั้น\n"
        "2. **โครงสร้างมุก 2 จังหวะ (Setup / Punchline)**:\n"
        "   - ช่อง 1 (panel1_text) = Setup: ต้องเป็นการกระทำที่มีเจตนาดี/ความตั้งใจดีที่คนทำงานเข้าใจและมีอารมณ์ร่วมได้ง่าย\n"
        "   - ช่อง 2 (panel2_text) = Punchline: ต้องเป็นผลลัพธ์ที่เกินคาด/ตลกร้าย/หักมุม และข้อความช่อง 2 ต้องเป็นคำตบมุกที่จบและสมบูรณ์ในตัวมันเองเด็ดขาด ห้ามเป็นประโยคค้างคา (เช่น ห้ามทิ้งประโยคค้างแบบ 'โดน HR เตือนเรื่อง...' โดยไม่มีคำตบ ให้ระบุประเด็นตบมุกให้สมบูรณ์ เช่น 'HR บอกใช้ของบริษัทผิดวัตถุประสงค์' หรือ 'โดนเรียกคุยเรื่องของส่วนกลาง')\n"
        "3. **ห้ามใช้คำหรือฉากที่บริบทสับสน/หลุดธีม**: ห้ามใช้คำที่ทำให้สับสนหรือขัดแย้งกับฉากหลังของเนื้อเรื่องหลัก เช่น ถ้าฉากหลักอยู่ในออฟฟิศหรือมุมทำงาน ห้ามใช้คำว่า 'ครัว' หรือ 'ห้องครัว' (ให้ใช้คำที่ตรงบริบทออฟฟิศ เช่น 'มุมกาแฟออฟฟิศ', 'โต๊ะทำงาน', 'ของส่วนกลาง')\n"
        "4. **ภาพและคำอธิบายฉากต้องแสดงสาเหตุอย่างชัดเจน (Visual Cause)**: คำอธิบายภาพ (panel1_scene และ panel2_scene) ต้องแสดงให้เห็นเหตุผลหรือพฤติกรรมอย่างชัดเจนว่าทำไมตัวละครถึงถูกเตือน/มีปัญหา (เช่น ถ้าตัวละครโดนเตือนเรื่องของใช้ส่วนกลาง ภาพช่อง 1 ต้องเห็นชัดเจนว่ากำลังเอาของตกแต่งของส่วนกลางมาใช้เกินเลย หรือภาพช่อง 2 ต้องเน้นย้ำถึงปมปัญหาหรือผลลัพธ์อย่างชัดเจน)\n"
        "5. **ข้อความบนรูปภาพต้องสั้นมาก**: ใช้ภาษาพูดที่เป็นกันเอง/ภาษาปากสั้นๆ กระชับ ห้ามเขียนประโยคยาว ห้ามใส่คำบรรยายยืดยาว และห้ามเกิน 12 คำภาษาไทยต่อช่อง\n"
        "6. **การเชื่อมโยงบริบทออฟฟิศไทย (Localization)**: ปรับประเด็นใน Reddit ให้โยงกับชีวิตจริงของคนทำงานไทย เช่น เด็กฝาก, คนใน, เปิดรับสมัครตามพิธี, หัวหน้า, KPI, เงินเดือน, ประชุม, OT, HR, โปรโมชัน, สัมภาษณ์งาน\n"
        "7. **ห้ามมีมบอสสั่งงานด่วนในวันหยุดซ้ำซาก**: ยกเว้นแต่มีมต้นฉบับพูดถึงเรื่องนี้โดยตรง\n"
        f"{recent_topics_str}\n"
        "**กฎเหล็กสำหรับแคปชั่น (Caption Rules)**:\n"
        "- เขียนเหมือนคนจริงมาเล่า/แชร์ประสบการณ์ในกลุ่ม ไม่ใช่บทความ ไม่ใช่ข่าว ไม่ใช่คำชี้แจง\n"
        "- ความยาว 2-3 ย่อหน้าสั้น (กระชับและไม่ยืดยาว)\n"
        "- **ห้ามอธิบายภาพหรือสปอยล์คำจบการ์ตูนซ้ำเด็ดขาด**: ไม่ต้องอธิบายสรุปว่าภาพช่อง 1 ทำอะไร ช่อง 2 ทำอะไร แต่ให้เริ่มประโยคเปิดด้วยประเด็นปมปัญหาหรือคำถามชวนคุยถึงสถานการณ์จริงหรือประสบการณ์ร่วมของคนอ่านทันที\n"
        "- **ห้ามมีคำว่า 'ดูเพิ่มเติม' หรือลิงก์หลุดระบบ/ตัวยึดตำแหน่งเด็ดขาด**\n"
        "- ต้องมีความขัดแย้ง/ความลังเลชัดเจนในเรื่องงาน\n"
        "- ห้ามใช้ Bullet point หรือการจัดรายการ\n"
        "- ห้ามใส่ Hashtag ใดๆ ทั้งสิ้นในตัวแคปชั่น\n"
        "- ห้ามใช้คำว่า ดราม่า, ช็อก, ไวรัล, ปัญหาสังคม หรือคำแนว AI/บอต\n"
        "- ห้ามสรุปสอนศีลธรรมหรือเทศนาคำคมชีวิต\n"
        "- ภาษาเป็นผู้ชายสุภาพและเป็นกันเอง ใช้ ครับ / ผม / พี่ๆ เสมอ\n"
        "- จบด้วยคำถามท้ายโพสต์ที่บังคับให้คนอ่านแชร์ประสบการณ์ตรงเกี่ยวกับเรื่องนั้นๆ ในออฟฟิศ\n\n"
        "**ตัวอย่างการแปลงหัวข้อ Reddit (Few-shot Examples)**:\n"
        "- หัวข้อ: สมัครงานแล้วไม่ได้ทั้งที่ตอบดี\n"
        "  panel1_text: \"ตอบอย่างเทพ\"\n"
        "  panel2_text: \"แพ้เด็กฝาก\"\n"
        "- หัวข้อ: ตั้งใจทำงานแต่หัวหน้าไม่เห็น\n"
        "  panel1_text: \"ทำงานแทบตาย\"\n"
        "  panel2_text: \"เครดิตอยู่ที่คนพูดเก่ง\"\n"
        "- หัวข้อ: ประชุมทั้งวันแต่งานไม่เดิน\n"
        "  panel1_text: \"ประชุม 3 ชั่วโมง\"\n"
        "  panel2_text: \"สรุปคือประชุมต่อพรุ่งนี้\"\n"
        "- หัวข้อ: เงินเดือนออก\n"
        "  panel1_text: \"เงินเดือนเข้า\"\n"
        "  panel2_text: \"หนี้ออกก่อน\"\n\n"
        "กรุณาสร้างองค์ประกอบและอธิบายองค์ประกอบสำหรับรูปภาพการ์ตูน 2 ช่องนี้ โดยตอบกลับในรูปแบบ JSON ที่มีคีย์ดังนี้:\n"
        "1. original_joke_analysis_en: วิเคราะห์แก่นของมีมนี้เป็นภาษาอังกฤษอย่างละเอียด\n"
        "2. panel1_text: ข้อความภาษาไทยสั้นๆ ปูเรื่องช่องที่ 1 (ห้ามเกิน 12 คำ)\n"
        "3. panel1_scene: คำอธิบายภาพช่องแรกเป็นภาษาอังกฤษ (15-25 คำ)\n"
        "4. panel2_text: ข้อความภาษาไทยสั้นๆ หักมุมช่องที่ 2 (ห้ามเกิน 12 คำ)\n"
        "5. panel2_scene: คำอธิบายภาพช่องสองเป็นภาษาอังกฤษ (15-25 คำ) เน้นการแสดงออกทางสีหน้าหรือองค์ประกอบให้เข้าใจจุดตลกร้าย/หักมุม\n"
        "6. caption: แคปชั่นภาษาไทย 2-3 ย่อหน้าสั้นสไตล์ผู้ชายสุภาพ ดึงดูดคอมเมนต์ ไม่สปอยล์คำจบการ์ตูน ไร้แฮชแท็ก ไร้บลูเล็ต\n\n"
        "กรุณาตอบเป็น JSON ในรูปแบบนี้เท่านั้น (ห้ามมี markdown codeblock หรือคำนำหน้าใดๆ):\n"
        "{\n"
        "  \"original_joke_analysis_en\": \"...\",\n"
        "  \"panel1_text\": \"...\",\n"
        "  \"panel1_scene\": \"...\",\n"
        "  \"panel2_text\": \"...\",\n"
        "  \"panel2_scene\": \"...\",\n"
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
            analysis = data.get("original_joke_analysis_en", "").strip()
            print(f"\nOriginal Reddit Meme Analysis:\n{analysis}\n")
            return (
                data.get("panel1_text", "").strip(),
                data.get("panel1_scene", "").strip(),
                data.get("panel2_text", "").strip(),
                data.get("panel2_scene", "").strip(),
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
            save_to_history(reddit_title_key(reddit_title))
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
