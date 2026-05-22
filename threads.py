# -*- coding: utf-8 -*-
"""threads.py — โพสรูปคำคม + caption ลง Threads อัตโนมัติ"""

import sys, io, os, re, base64, requests, time, random, tempfile
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai
from google.genai import types

GOOGLE_API_KEY       = os.environ.get("GOOGLE_API_KEY",       "")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID      = os.environ.get("THREADS_USER_ID",      "")
IMAGE_MODEL          = "gemini-2.0-flash-preview-image-generation"  # unused (PIL renders)
TEXT_MODELS          = ["gemini-3.5-flash", "gemini-2.5-flash"]
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
    hour = now.hour
    if hour < 10:
        return random.choice(MORNING_TOPICS)
    elif hour < 16:
        return random.choice(NOON_TOPICS)
    else:
        return random.choice(EVENING_TOPICS)

CONTENT_STYLES = [
    "สร้างคำคมภาษาไทยแบบไวรัลเกี่ยวกับ: {topic}\n1-2 ประโยคสั้นๆ กระแทกใจ หยุดนิ้วเลื่อนได้ทันที ภาษาพูดธรรมดา คนอายุ 30-45 อ่านแล้วรู้สึกเลย\nข้อความรวม (ไม่นับ hashtag) ห้ามเกิน 60 ตัวอักษร ขึ้นบรรทัดใหม่จริงๆ ตรงจุดหยุดตามธรรมชาติ\nท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น",
    "เขียน post ภาษาไทยเล่าเรื่องชีวิตจริงเกี่ยวกับ: {topic}\n2 ประโยคสั้นๆ เหมือนเพื่อนโพส เข้าใจง่าย ลงท้ายด้วยคำถามให้คนอยากคอมเม้น\nข้อความรวม (ไม่นับ hashtag) ห้ามเกิน 80 ตัวอักษร ขึ้นบรรทัดใหม่จริงๆ ตรงจุดหยุดตามธรรมชาติ\nท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น",
    "เขียน post ภาษาไทยตั้งคำถามเกี่ยวกับ: {topic}\n1 คำถามสั้นๆ ที่คนอ่านแล้วต้องคิด อยากตอบ อยากแชร์ ภาษาง่าย พูดตรงๆ\nข้อความรวม (ไม่นับ hashtag) ห้ามเกิน 60 ตัวอักษร ขึ้นบรรทัดใหม่จริงๆ ตรงจุดหยุดตามธรรมชาติ\nท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น",
    "เขียน post ภาษาไทย tips เกี่ยวกับ: {topic}\nหัวข้อดึงดูด 1 บรรทัด + 3 ข้อสั้นมากๆ ข้อละไม่เกิน 10 ตัวอักษร ใช้ได้ทันที\nข้อความรวม (ไม่นับ hashtag) ห้ามเกิน 80 ตัวอักษร ขึ้นบรรทัดใหม่จริงๆ ตรงจุดหยุดตามธรรมชาติ\nท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น",
    "เขียน post ภาษาไทยเปรียบเทียบ ก่อน vs หลัง เกี่ยวกับ: {topic}\n2 บรรทัด เห็นภาพชัด ขำหรือจริงใจ คนแชร์ได้เลย ภาษาพูด ไม่เป็นทางการ\nข้อความรวม (ไม่นับ hashtag) ห้ามเกิน 70 ตัวอักษร ขึ้นบรรทัดใหม่จริงๆ ตรงจุดหยุดตามธรรมชาติ\nท้ายใส่ hashtag 2 อัน ตอบแค่ content เท่านั้น",
]

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

def generate_quote(topic):
    style_idx = random.randint(0, len(CONTENT_STYLES) - 1)
    prompt = CONTENT_STYLES[style_idx].format(topic=topic)
    print(f"Topic: {topic} | Style: {style_idx}")
    for model in TEXT_MODELS:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                quote = clean_text(resp.text)
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

_SOFT_BREAK = set('…—–-/!?ๆฯ')

def _break_long_word(word, font, draw, max_width):
    """แตก word ที่ยาวเกิน — ลอง break ที่ punctuation ก่อน แล้วค่อยแตก char"""
    result, buf = [], ""
    for ch in word:
        if draw.textbbox((0, 0), buf + ch, font=font)[2] <= max_width:
            buf += ch
        else:
            back = -1
            for j in range(len(buf) - 1, max(len(buf) - 9, -1), -1):
                if buf[j] in _SOFT_BREAK:
                    back = j + 1
                    break
            dot3 = buf.rfind('...')
            if dot3 >= 0 and dot3 + 3 > back:
                back = dot3 + 3
            if back > 0:
                result.append(buf[:back])
                buf = buf[back:] + ch
            else:
                if buf:
                    result.append(buf)
                buf = ch
    if buf:
        result.append(buf)
    return result

def wrap_thai(text, font, draw, max_width):
    """ตัดบรรทัดให้พอดีความกว้าง — break ที่ punctuation ก่อน แล้วค่อย char"""
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            if draw.textbbox((0, 0), word, font=font)[2] > max_width:
                parts = _break_long_word(word, font, draw, max_width)
                lines.extend(parts[:-1])
                current = parts[-1] if parts else ""
            else:
                current = word
            continue
    if current:
        lines.append(current)
    return lines

def _build_lines(quote, font_main, font_hash, draw, max_w):
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
    path = os.path.join(OUTPUT_DIR, f"threads_{ts}.png")

    img  = Image.new("RGB", (IMG_SIZE, IMG_SIZE), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    PAD      = 100
    max_w    = IMG_SIZE - PAD * 2
    max_h    = IMG_SIZE - PAD * 2
    LINE_GAP = 18

    # auto-fit: หา font size ใหญ่ที่สุดที่พอดีกรอบ
    font_size = 82
    while font_size >= 36:
        font_main = ImageFont.truetype(FONT_PATH, font_size)
        font_hash = ImageFont.truetype(FONT_PATH, int(font_size * 0.65))
        all_lines = _build_lines(quote, font_main, font_hash, draw, max_w)
        total_h = sum(draw.textbbox((0,0), t, font=f)[3] + LINE_GAP for t, f in all_lines)
        if total_h <= max_h:
            break
        font_size -= 2

    print(f"Font size: {font_size}")
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
        text = msg["message"] if isinstance(msg, dict) else msg
        reply_id = _create_and_publish(text, reply_to_id=post_id)
        print(f"Reply {i} added! ID: {reply_id}")
        if i < len(all_comments):
            delay = random.uniform(30, 90)
            print(f"Waiting {delay:.0f}s before next reply...")
            time.sleep(delay)

# ─── Meme mode ────────────────────────────────────────────────────────
MEME_SUBREDDITS = [
    "funny", "memes", "dankmemes", "me_irl",
    "Unexpected", "therewasanattempt", "facepalm",
    "AnimalsBeingDerps", "WhatsWrongWithYourCat", "oddlyterrifying",
    "AbruptChaos", "Whatcouldgowrong",
]
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")
HEADERS_RSS = {"User-Agent": "Mozilla/5.0 (compatible; ThreadsBot/1.0; +github)"}


def get_meme_image():
    subreddit = random.choice(MEME_SUBREDDITS)
    url = f"https://www.reddit.com/r/{subreddit}/hot.rss"
    try:
        resp = requests.get(url, headers=HEADERS_RSS, timeout=10)
        resp.raise_for_status()
        root    = ET.fromstring(resp.content)
        ns      = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        posts = []
        for entry in entries:
            content   = entry.findtext("atom:content", "", ns)
            img_urls  = re.findall(r'https?://[^\s"<>]+\.(?:jpg|jpeg|png|gif|webp)', content or "")
            good_imgs = [u for u in img_urls if "i.redd.it" in u or "imgur.com" in u]
            if good_imgs:
                posts.append({"url": good_imgs[0], "subreddit": subreddit})
        if not posts:
            return None, None
        post = random.choice(posts[:10])
        print(f"Meme: r/{subreddit} | {post['url'][:60]}")
        return post["url"], subreddit
    except Exception as e:
        print(f"Reddit error: {e}")
        return None, None


def download_image(url):
    MAX_BYTES = 4 * 1024 * 1024
    try:
        resp = requests.get(url, headers=HEADERS_RSS, timeout=15, stream=True)
        resp.raise_for_status()
        data = b""
        for chunk in resp.iter_content(chunk_size=65536):
            data += chunk
            if len(data) > MAX_BYTES:
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


def analyze_meme(img_path):
    """Vision ดูรูปว่าตลกยังไง"""
    with open(img_path, "rb") as f:
        img_data = f.read()
    prompt = (
        "ดูรูปนี้แล้วอธิบายสั้นๆ ภาษาไทยว่าเห็นอะไร หรือสถานการณ์ตลกอะไรในรูป 1-2 ประโยค "
        "ถ้าไม่มีอะไรน่าสนใจเลย ตอบว่า 'ไม่น่าสนใจ'"
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=img_data, mime_type="image/jpeg"),
                    types.Part.from_text(text=prompt),
                ],
            )
            result = resp.text.strip()
            print(f"Vision: {result}")
            return result
        except Exception as e:
            print(f"[{model}] vision failed: {e}")
    return None


def generate_funny_caption(image_desc, subreddit):
    prompt = (
        f"รูปจาก r/{subreddit}: {image_desc}\n\n"
        "เขียน caption ภาษาไทย ตลกๆ เหมือนโพส meme ของคนไทย\n"
        "1-2 ประโยคสั้นมาก ขำ เข้าใจง่าย ภาษาพูด ใส่ emoji ได้\n"
        "ท้ายใส่ hashtag 2-3 อัน\n"
        "ห้ามใช้ ** ตอบแค่ caption เลย"
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            return clean_text(resp.text.strip())
        except Exception as e:
            print(f"[{model}] funny caption failed: {e}")
    return "555 😂\n#meme #ตลก"


def run_meme_mode():
    """โหมดมีมตลก — Reddit → Vision → funny caption → Threads"""
    for attempt in range(4):
        img_url, subreddit = get_meme_image()
        if not img_url:
            continue
        img_path = download_image(img_url)
        if not img_path:
            continue
        desc = analyze_meme(img_path)
        if not desc or "ไม่น่าสนใจ" in desc:
            os.unlink(img_path)
            continue
        caption = generate_funny_caption(desc, subreddit)
        caption += f"\n📷 via r/{subreddit}"
        print(f"Funny caption:\n{caption}\n")
        # upload ผ่าน ImgBB
        hosted_url = upload_image_to_imgur(img_path)
        os.unlink(img_path)
        post_threads(hosted_url, caption)
        return
    print("Meme mode failed after 4 attempts, fallback to quote mode")
    run_quote_mode()


def run_quote_mode():
    """โหมดคำคม — PIL image + quote"""
    topic    = get_topic()
    quote    = generate_quote(topic)
    img_path = generate_image(quote)
    img_url  = upload_image_to_imgur(img_path)
    post_threads(img_url, quote)


if __name__ == "__main__":
    if random.random() < 0.5:
        print("Mode: MEME")
        run_meme_mode()
    else:
        print("Mode: QUOTE")
        run_quote_mode()
