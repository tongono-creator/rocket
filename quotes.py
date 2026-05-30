import os
import sys
import io
import re
import random
import time
import requests
import tempfile
from PIL import Image, ImageDraw, ImageFont
from google import genai

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# -- Config --
PAGE_ID           = os.environ.get("PAGE_ID", "111830598532037")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
PEXELS_API_KEY    = os.environ.get("PEXELS_API_KEY", "")

# Try fallback from config.py if they are not set in environment
if not GEMINI_API_KEY or not PAGE_ACCESS_TOKEN:
    try:
        from config import GOOGLE_API_KEY, PAGE_ACCESS_TOKEN as CFG_PAT, PAGE_ID as CFG_ID
        if not GEMINI_API_KEY:
            GEMINI_API_KEY = GOOGLE_API_KEY
        if not PAGE_ACCESS_TOKEN:
            PAGE_ACCESS_TOKEN = CFG_PAT
        if not PAGE_ID:
            PAGE_ID = CFG_ID
    except ImportError:
        pass

API_ENABLED = True
client = None
if not GEMINI_API_KEY or GEMINI_API_KEY in ("DUMMY_KEY", "DUMMY"):
    print("[Warning] GEMINI_API_KEY is not set or is a dummy key. Disabling API calls.")
    API_ENABLED = False
else:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY, http_options={'timeout': 15000.0})
    except Exception as e:
        print(f"[Warning] Failed to initialize genai.Client: {e}. Disabling API calls.")
        API_ENABLED = False

TEXT_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash"]
GOLD        = (255, 215, 0)
WHITE       = (255, 255, 255)
SILVER      = (200, 200, 200)
FONT_PATH   = os.path.join(os.path.dirname(__file__), "fonts", "Kanit-Bold.ttf")
HEADERS     = {"User-Agent": "Mozilla/5.0 (compatible; RocketBot/1.0)"}

HISTORY_FILE = "posted_history.txt"

THAI_WORDS = [
    "รายละเอียด", "โปรโมชั่น", "เครื่องมือ", "คอมพิวเตอร์", "แอปพลิเคชัน", "เก็บเงินปลายทาง",
    "โทรศัพท์", "แบตเตอรี่", "บัตรเครดิต", "พร้อมส่ง", "จัดส่ง", "ต่างประเทศ",
    "พรีออเดอร์", "ประหยัด", "ปลอดภัย", "คุ้มค่า", "สะดวกสบาย", "ธรรมชาติ",
    "คุณภาพ", "ภาพถ่าย", "พลาสติก", "ของแท้", "รับประกัน", "ลิขสิทธิ์",
    "แนะนำ", "สินค้า", "รีวิว", "สุดยอด", "ดีที่สุด", "สะดวก", "สบาย", "ง่ายดาย",
    "รวดเร็ว", "โปรโมชั่", "ส่วนลด", "คูปอง", "จัดส่ง", "ประกัน",
    "ชาร์จ", "หน้าจอ", "ลำโพง", "หูฟัง", "กล้อง", "เลนส์", "มือถือ", "ปุ่มกด",
    "สำหรับ", "เกี่ยวกับ", "อย่างไร", "เมื่อไหร่", "ที่ไหน", "เท่าไหร่",
    "ทุกคน", "ทุกวัน", "ทุกคืน", "สุดท้าย", "แรกเริ่ม", "จริงจัง",
    "สวัสดี", "ขอบคุณ", "ขอโทษ", "ยินดี", "หัวเราะ", "ร้องไห้",
    "ทำงาน", "พักผ่อน", "ออกกำลัง", "ท่องเที่ยว", "เดินทาง",
    "เก้าอี้", "โต๊ะทำงาน", "เบาะรอง", "พิงหลัง", "สายรัด", "การ์ตูน",
    "กระเป๋า", "รองเท้า", "เสื้อผ้า", "กางเกง", "นาฬิกา", "แว่นตา", "เครื่อง", "ระบบ",
    "ความสุข", "ร่างกาย", "สุขภาพ", "ออกกำลัง", "อาหาร", "ผลไม้", "น้ำดื่ม", "กาแฟ",
    "ราคา", "พิเศษ", "ทั่วไป", "ส่งฟรี", "ลดราคา", "ของแถม", "ปลายทาง",
    "ชั่วโมง", "นาที", "วินาที", "สัปดาห์", "ปีใหม่", "วันนี้", "พรุ่งนี้", "เมื่อวาน",
    "ใครก็ตาม", "สิ่งใด", "ทั้งหมด", "บางส่วน", "ประเภท", "รูปแบบ",
    "ติดตาม", "กดไลก์", "แชร์โพส", "คอมเมนต์", "คลิกลิงก์", "พิกัด", "ชี้เป้า",
    "ค่ะ", "ครับ", "ผม", "เรา", "คุณ", "ท่าน",
    "พี่", "น้อง", "พ่อ", "แม่", "เพื่อน", "บ้าน", "เมือง", "เวลา", "ดีใจ", "เสียใจ", 
    "รัก", "ชอบ", "เกลียด", "กลัว", "โกรธ", "ทำ", "กิน", "นอน", "เดิน", "วิ่ง", "นั่ง", 
    "ยืน", "พูด", "ฟัง", "ดู", "เห็น", "คิด", "รู้", "จำ", "ลืม", "เรียน", "เล่น", "ซื้อ", 
    "ขาย", "ราคา", "ถูก", "แพง", "ลด", "แถม", "ส่ง", "ด่วน", "ฟรี", "รับ", "ศูนย์",
    "แท้", "ใหม่", "เก่า", "แรก", "นี้", "นั้น", "โน้น", "นี่", "นั่น", "โน่น", "อะไร", 
    "ใคร", "กี่", "บ้าง", "ทุก", "บาง", "จริง", "จัง", "แท้", "เทียม", "ปลอม", "สาย", 
    "เคส", "ฟิล์ม", "ภาพ", "รูป", "เสียง", "เพลง", "หนัง", "เกม", "แอป", "เว็บ", "เน็ต", 
    "โค้ด", "โอน", "หวย", "ออก", "เงิน", "เก็บ", "แสน", "แรก", "งาน", "การ", "ช่วย", 
    "บอก", "ให้", "คน", "ทอง", "ร้อย", "พัน", "หมื่น", "ล้าน", "มาก", "น้อย", "ดี", 
    "เลว", "ชั่ว", "สูง", "ต่ำ", "ดำ", "ขาว", "แดง", "เขียว", "เหลือง", "ฟ้า", "ส้ม", 
    "ชมพู", "ม่วง", "เทา", "สวย", "หล่อ", "และ", "หรือ", "แต่", "ที่", "ซึ่ง", "อัน", 
    "ของ", "เพื่อ", "ใน", "จาก", "โดย", "ตาม", "กับ", "มี", "เป็น", "จะ", "ต้อง", 
    "อยาก", "นุ่ม", "แข็ง", "ใหญ่", "เล็ก", "ยาว", "สั้น", "กว้าง", "แคบ", "หนา", 
    "บาง", "ร้อน", "เย็น", "อุ่น", "หนาว", "ง่าย", "ยาก", "เร็ว", "ช้า", "ได้", 
    "เลย", "ด้วย", "จาก", "ถึง", "จน", "กว่า", "ก็", "ยัง", "อีก", "แล้ว", "นะ", 
    "สิ", "ละ", "หน่อย", "นิด", "ชิ้น", "กล่อง", "อัน", "ตัว", "ใบ", "คู่", "ชุด", 
    "แผ่น", "ม้วน"
]

def contains_thai(text):
    if not text:
        return False
    return bool(re.search(r'[\u0e00-\u0e7f]', text))

def local_segment_thai(text):
    if not text:
        return ""
    word_set = set(THAI_WORDS)
    max_len = max(len(w) for w in THAI_WORDS)
    
    result = []
    i = 0
    n = len(text)
    
    while i < n:
        if not contains_thai(text[i]):
            result.append(text[i])
            i += 1
            continue
            
        matched = False
        for l in range(min(max_len, n - i), 0, -1):
            substr = text[i:i+l]
            if substr in word_set:
                result.append(substr)
                i += l
                matched = True
                break
        
        if not matched:
            start = i
            while i < n and contains_thai(text[i]):
                word_matched_here = False
                if i > start:
                    for l in range(min(max_len, n - i), 0, -1):
                        if text[i:i+l] in word_set:
                            word_matched_here = True
                            break
                if word_matched_here:
                    break
                i += 1
            result.append(text[start:i])
            
    output = []
    for idx, part in enumerate(result):
        if idx > 0:
            prev_char = result[idx-1][-1]
            curr_char = part[0]
            if (contains_thai(prev_char) and contains_thai(curr_char) and 
                prev_char != '\u200b' and curr_char != '\u200b' and
                curr_char not in _COMBINING_CHARS and
                prev_char not in _LEADING_VOWELS):
                output.append('\u200b')
        output.append(part)
        
    return "".join(output)

def segment_thai_text(text, client_obj=None):
    global API_ENABLED
    if not text or not contains_thai(text):
        return text
    active_client = client_obj if client_obj is not None else client
    if not API_ENABLED or active_client is None:
        return local_segment_thai(text)
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
            resp = active_client.models.generate_content(model=model, contents=prompt)
            segmented = resp.text.strip().replace('\\u200b', '\u200b')
            clean_orig = text.replace('\u200b', '').replace('\\u200b', '')
            clean_seg = segmented.replace('\u200b', '').replace('\\u200b', '')
            if len(clean_orig) == len(clean_seg):
                return segmented
        except Exception as e:
            err_msg = str(e)
            print(f"[{model}] segment_thai_text failed: {err_msg[:80]}")
            if "API key" in err_msg or "INVALID_ARGUMENT" in err_msg or "API_KEY" in err_msg:
                print("Persistent API key issue detected. Disabling API calls immediately.")
                API_ENABLED = False
                break
            
    if not API_ENABLED:
        print("[Warning] API calls disabled. Falling back to local_segment_thai.")
    else:
        print("[Warning] segment_thai_text failed on all models. Disabling API calls for this run.")
        API_ENABLED = False
    return local_segment_thai(text)

FALLBACK_QUOTES = [
    {"quote": "หนทางเดียวที่จะทำงานที่ยิ่งใหญ่ได้ คือรักในสิ่งที่คุณทำ", "author_en": "Steve Jobs", "author_thai": "สตีฟ จอบส์"},
    {"quote": "จงเป็นตัวของตัวเอง เพราะคนอื่นมีคนเป็นไปหมดแล้ว", "author_en": "Oscar Wilde", "author_thai": "ออสการ์ ไวลด์"},
    {"quote": "ความล้มเหลวที่แท้จริงเพียงอย่างเดียวในชีวิต คือการไม่เรียนรู้จากมัน", "author_en": "Albert Einstein", "author_thai": "อัลเบิร์ต ไอน์สไตน์"},
    {"quote": "สิ่งที่อยู่ข้างหลังเราและสิ่งที่อยู่ข้างหน้าเรา เป็นเรื่องเล็กน้อยมากเมื่อเทียบกับสิ่งที่อยู่ภายในตัวเรา", "author_en": "Ralph Waldo Emerson", "author_thai": "ราล์ฟ วัลโด เอเมอร์สัน"},
    {"quote": "อย่ากลัวที่จะละทิ้งสิ่งที่ดี เพื่อไปหาสิ่งที่ยอดเยี่ยมกว่า", "author_en": "John D. Rockefeller", "author_thai": "จอห์น ดี. ร็อกกี้เฟลเลอร์"},
    {"quote": "ความลับของความก้าวหน้า คือการเริ่มต้น", "author_en": "Mark Twain", "author_thai": "มาร์ก ทเวน"},
    {"quote": "สิ่งที่คุณทำในวันนี้ สามารถปรับปรุงอนาคตทั้งหมดของคุณได้", "author_en": "Ralph Marston", "author_thai": "ราล์ฟ มาร์สตัน"},
    {"quote": "เชื่อว่าคุณทำได้ และคุณก็ไปได้ครึ่งทางแล้ว", "author_en": "Theodore Roosevelt", "author_thai": "ธีโอดอร์ รูสเวลต์"},
    {"quote": "ชีวิตคือสิ่งที่เกิดขึ้นในขณะที่คุณกำลังยุ่งอยู่กับการวางแผนอื่นๆ", "author_en": "John Lennon", "author_thai": "จอห์น เลนนอน"},
    {"quote": "เวลาของคุณมีจำกัด อย่าเสียเวลาไปกับการใช้ชีวิตของคนอื่น", "author_en": "Steve Jobs", "author_thai": "สตีฟ จอบส์"}
]

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


_LEADING_VOWELS  = set("เแโใไ")
_COMBINING_CHARS = set("่้๊๋์ิีึืุูัํ็")


def _wrap_char(draw, text, font, max_width):
    if '\u200b' in text or '\\u200b' in text:
        text = text.replace('\\u200b', '\u200b')
        tokens = text.split('\u200b')
        lines, current = [], ""
        for token in tokens:
            test = current + token
            if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                    current = token
                else:
                    current = token
        if current:
            lines.append(current)
        return lines

    lines, current = [], ""
    for ch in text:
        test = current + ch
        fits = draw.textbbox((0, 0), test, font=font)[2] <= max_width
        if fits or ch in _COMBINING_CHARS:
            current = test
            continue
        if current:
            if current[-1] in _LEADING_VOWELS:
                orphan = current[-1]
                current = current[:-1]
                if current:
                    lines.append(current)
                current = orphan + ch
            else:
                lines.append(current)
                current = ch
        else:
            current = ch
    if current:
        lines.append(current)
    return lines or [text]


def _wrap_words(draw, text, font, max_width):
    words = [w for w in text.split(" ") if w]
    if not words:
        return [text]
    lines, current = [], ""
    for word in words:
        test = word if not current else current + " " + word
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    return lines


def _wrap_quote_line(draw, text, font, max_width):
    text = text.strip()
    if not text or draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return [text] if text else []
    if '\u200b' in text or '\\u200b' in text:
        return _wrap_char(draw, text, font, max_width)
    if " " in text:
        lines = _wrap_words(draw, text, font, max_width)
        if getattr(font, "size", 99) <= 75:
            new_lines = []
            for l in lines:
                if draw.textbbox((0, 0), l, font=font)[2] > max_width:
                    new_lines.extend(_wrap_char(draw, l, font, max_width))
                else:
                    new_lines.append(l)
            lines = new_lines
        return lines
    return [text] if getattr(font, "size", 99) > 75 else _wrap_char(draw, text, font, max_width)


# -- ZenQuotes API --
def get_quote():
    history = set(load_history())
    for _ in range(5):
        try:
            resp = requests.get("https://zenquotes.io/api/random", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data:
                item   = data[0]
                quote  = item.get("q", "").strip()
                author = item.get("a", "").strip()
                if not quote or not author or author.lower() in ("unknown", "anonymous", ""):
                    continue
                if quote in history:
                    print(f"Quote already posted: {quote[:40]}... Retrying.")
                    continue
                print(f"Quote: {author} — {quote[:60]}")
                return quote, author
        except Exception as e:
            print(f"ZenQuotes error: {e}")
            time.sleep(2)
    return None, None


# -- Gemini helpers --
def clean_text(text):
    text = text.replace("\\n", "\n")
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",     r"\1", text)
    text = re.sub(r"__(.+?)__",     r"\1", text)
    text = re.sub(r"_(.+?)_",       r"\1", text)
    text = re.sub(r"^#+\s*",        "",    text, flags=re.MULTILINE)
    return text.strip()


def translate_quote(content, author):
    global API_ENABLED
    if not API_ENABLED or not client:
        return content
    prompt = (
        f'Translate this English quote to natural Thai language.\n'
        f'Quote: "{content}"\n'
        f'Author: {author}\n'
        f'Return ONLY the Thai translation. No markdown, no quotes around it.'
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            result = clean_text(resp.text.strip())
            print(f"Thai: {result[:60]}")
            return result
        except Exception as e:
            print(f"[{model}] translate failed: {e}")
    return content


def split_quote_lines(quote_thai):
    """ให้ Gemini ตัดคำคมเป็นวลีสั้นๆ ทีละบรรทัด สไตล์โปสเตอร์ดราม่า"""
    global API_ENABLED
    if not API_ENABLED or not client:
        # fallback: split at ~10 chars
        words = quote_thai.split()
        lines, cur = [], ""
        for w in words:
            if len(cur) + len(w) > 10 and cur:
                lines.append(cur.strip())
                cur = w + " "
            else:
                cur += w + " "
        if cur.strip():
            lines.append(cur.strip())
        return lines
    prompt = (
        f'ตัดประโยคนี้เป็นวลีสั้นๆ สำหรับโปสเตอร์คำคม\n'
        f'ประโยค: {quote_thai}\n'
        f'กฎ: แต่ละบรรทัดสั้น 3-8 คำ ตัดที่จุดหยุดธรรมชาติ ได้ 2-5 บรรทัด\n'
        f'ตอบแค่วลีที่ตัดแล้ว แต่ละบรรทัดคั่นด้วย newline ไม่มีเลข ไม่มี -'
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            lines = [l.strip() for l in clean_text(resp.text).split("\n") if l.strip()]
            if lines:
                print(f"Split: {lines}")
                return lines
        except Exception as e:
            print(f"[{model}] split failed: {e}")
    # fallback: split at ~10 chars
    words = quote_thai.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) > 10 and cur:
            lines.append(cur.strip())
            cur = w + " "
        else:
            cur += w + " "
    if cur.strip():
        lines.append(cur.strip())
    return lines


def transliterate_author(author):
    """แปลชื่อภาษาอังกฤษเป็นการออกเสียงภาษาไทย"""
    global API_ENABLED
    if not API_ENABLED or not client:
        return author
    prompt = (
        f'เขียนชื่อนี้เป็นภาษาไทยตามการออกเสียง: {author}\n'
        f'ตอบแค่ชื่อภาษาไทย ไม่มีอะไรอื่น'
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            result = clean_text(resp.text.strip())
            print(f"Thai name: {result}")
            return result
        except Exception as e:
            print(f"[{model}] transliterate failed: {e}")
    return author


def make_caption(quote_thai, author):
    global API_ENABLED
    if not API_ENABLED or not client:
        return f'"{quote_thai}"\n— {author}\n#คำคม #แรงบันดาลใจ'
    prompt = (
        f'เขียน Facebook caption ภาษาไทยสำหรับโพสคำคมของ {author}\n'
        f'คำคม: {quote_thai}\n'
        f'บรรทัด 1: hook ชวนอ่าน\n'
        f'บรรทัด 2: บริบทของคนพูด 1 ประโยค\n'
        f'บรรทัด 3: hashtag 2-3 อัน\n'
        f'ห้าม ** ตอบแค่ caption'
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            return clean_text(resp.text.strip())
        except Exception as e:
            print(f"[{model}] caption failed: {e}")
    return f'"{quote_thai}"\n— {author}\n#คำคม #แรงบันดาลใจ'


# -- Pexels --
def get_author_photo(author_name):
    # ค้นหาด้วย "portrait" เพื่อให้ได้รูปคนจริงๆ ไม่ใช่สินค้า
    for query in [f"{author_name} portrait", f"{author_name} speaker", author_name]:
        try:
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={"query": query, "per_page": 5, "orientation": "portrait"},
                timeout=10,
            )
            resp.raise_for_status()
            photos = resp.json().get("photos", [])
            if photos:
                url = photos[0]["src"]["large"]
                print(f"Pexels [{query}]: {url[:60]}")
                return url
        except Exception as e:
            print(f"Pexels error: {e}")
    print(f"No photo for '{author_name}', using black bg")
    return None


def download_image(url):
    MAX_BYTES = 4 * 1024 * 1024
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        resp.raise_for_status()
        data = b""
        for chunk in resp.iter_content(65536):
            data += chunk
            if len(data) > MAX_BYTES:
                return None
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(data)
        tmp.close()
        return tmp.name
    except Exception as e:
        print(f"Download failed: {e}")
        return None


# -- PIL Quote Image (สไตล์โปสเตอร์ดราม่า) --
def make_quote_image(lines, author_en, author_thai, img_path=None):
    size = 1080

    # Background: photo (square crop) หรือ black
    if img_path:
        try:
            bg = Image.open(img_path).convert("RGB")
            w, h = bg.size
            side = min(w, h)
            bg = bg.crop(((w - side) // 2, (h - side) // 2,
                          (w + side) // 2, (h + side) // 2))
            bg = bg.resize((size, size), Image.LANCZOS)
        except Exception as e:
            print(f"Photo failed: {e}")
            bg = Image.new("RGB", (size, size), (15, 15, 20))
    else:
        bg = Image.new("RGB", (size, size), (15, 15, 20))

    # Gradient overlay ซ้ายจาง → ขวาเข้ม (ให้อ่านข้อความได้)
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    split_x = size // 3  # เริ่ม gradient ที่ 1/3
    for x in range(split_x, size):
        alpha = int(180 * (x - split_x) / (size - split_x))
        ov_draw.line([(x, 0), (x, size)], fill=(0, 0, 0, alpha))
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(bg)

    # Layout: text zone ขวา (x: 480 - 1050)
    x_left  = 480
    x_right = 1050
    zone_w  = x_right - x_left

    # Auto-fit: รักษาวลีไทยไว้ก่อน ลด font ก่อนค่อย fallback char-wrap
    render_source = [l.strip() for l in lines if l and l.strip()]
    if not render_source:
        render_source = ["คำคมวันนี้"]
    
    # Prepend/append quotes to the text before wrapping
    render_source_with_quotes = [l for l in render_source]
    render_source_with_quotes[0] = "“" + render_source_with_quotes[0]
    render_source_with_quotes[-1] = render_source_with_quotes[-1] + "”"

    font_size = 120
    while font_size >= 42:
        try:
            font_big    = ImageFont.truetype(FONT_PATH, font_size)
            font_author = ImageFont.truetype(FONT_PATH, max(30, int(font_size * 0.58)))
            font_sub    = ImageFont.truetype(FONT_PATH, max(24, int(font_size * 0.46)))
        except Exception:
            font_big = font_author = font_sub = ImageFont.load_default()

        render_lines = []
        for line in render_source_with_quotes:
            render_lines.extend(_wrap_quote_line(draw, line, font_big, zone_w))

        line_gap = max(12, font_size // 6)
        line_heights = [
            draw.textbbox((0, 0), line, font=font_big)[3] -
            draw.textbbox((0, 0), line, font=font_big)[1]
            for line in render_lines
        ]
        quote_h = sum(line_heights) + line_gap * (len(render_lines) - 1)
        author_h = draw.textbbox((0, 0), f"...  {author_thai}  ...", font=font_author)[3]
        sub_h = draw.textbbox((0, 0), "วาทะคนดัง", font=font_sub)[3]
        gap = max(24, font_size // 2)
        total_h = quote_h + gap + author_h + sub_h + 40
        width_ok = all(draw.textbbox((0, 0), line, font=font_big)[2] <= zone_w for line in render_lines)
        if total_h <= 860 and width_ok:
            break
        font_size -= 4

    y_start = (size - total_h) // 2

    # บรรทัดคำคม (ขวาชิดขวา text zone)
    y = y_start
    for i, line in enumerate(render_lines):
        bbox   = draw.textbbox((0, 0), line, font=font_big)
        w_text = bbox[2] - bbox[0]
        x      = x_right - w_text  # right-align
        # shadow
        draw.text((x + 3, y + 3), line, font=font_big, fill=(0, 0, 0, 160))
        draw.text((x, y), line, font=font_big, fill=WHITE)
        y += (bbox[3] - bbox[1]) + line_gap

    y_author = y + gap

    # ชื่อผู้พูด (ภาษาไทย) right-align + "..." คั่น
    author_text = f"...  {author_thai}  ..."
    bbox        = draw.textbbox((0, 0), author_text, font=font_author)
    w_text      = bbox[2] - bbox[0]
    x_a         = x_right - w_text
    draw.text((x_a + 2, y_author + 2), author_text, font=font_author, fill=(0, 0, 0, 160))
    draw.text((x_a, y_author), author_text, font=font_author, fill=GOLD)

    # sub-label
    sub_text = "วาทะคนดัง"
    bbox     = draw.textbbox((0, 0), sub_text, font=font_sub)
    w_sub    = bbox[2] - bbox[0]
    draw.text((x_right - w_sub, y_author + author_h + 10), sub_text, font=font_sub, fill=SILVER)

    # Save
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    bg.save(tmp.name, "JPEG", quality=92)
    tmp.close()
    print(f"Image saved: {tmp.name}")
    return tmp.name


# -- Facebook --
def post_photo(caption, img_path):
    try:
        api_url = f"https://graph.facebook.com/v21.0/{PAGE_ID}/photos"
        with open(img_path, "rb") as f:
            resp = requests.post(
                api_url,
                data={"message": caption, "access_token": PAGE_ACCESS_TOKEN},
                files={"source": ("photo.jpg", f, "image/jpeg")},
                timeout=60,
            )
        result = resp.json()
        if "id" in result:
            post_id = result.get("post_id") or result["id"]
            print(f"Posted: {post_id}")
            add_comment(post_id)
            return True
        else:
            print(f"Post failed: {result}")
            return False
    except Exception as e:
        print(f"Facebook error: {e}")
        return False
    finally:
        if img_path and os.path.exists(img_path):
            os.unlink(img_path)


def add_comment(post_id):
    from affiliate_utils import get_all_comments
    comments = get_all_comments()
    delay0   = random.uniform(60, 180)
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
            f"https://graph.facebook.com/v21.0/{post_id}/comments",
            data=data,
            timeout=60,
        )
        result = resp.json()
        if "id" in result:
            print(f"Comment {i} added: {result['id']}")
        else:
            print(f"Comment {i} error: {result}")
        if i < len(comments):
            time.sleep(random.uniform(30, 90))


# -- Main --
def main(dry_run=False):
    print("=== Rocket21 Quotes Bot ===")

    for attempt in range(5):
        print(f"Attempt {attempt + 1}/5")

        quote_en, author_en = get_quote()
        if not quote_en:
            continue

        quote_thai  = translate_quote(quote_en, author_en)
        if not quote_thai or not contains_thai(quote_thai):
            print("Translation returned no Thai text. Using a local famous Thai quote fallback...")
            fallback = random.choice(FALLBACK_QUOTES)
            quote_thai = fallback["quote"]
            author_en = fallback["author_en"]
            author_thai = fallback["author_thai"]
        else:
            author_thai = transliterate_author(author_en)
            
        lines       = split_quote_lines(quote_thai)
        lines       = [segment_thai_text(l, client) for l in lines]

        # หารูปผู้พูด
        img_path  = None
        photo_url = get_author_photo(author_en)
        if photo_url:
            img_path = download_image(photo_url)

        final_path = make_quote_image(lines, author_en, author_thai, img_path)
        if img_path and os.path.exists(img_path):
            os.unlink(img_path)

        caption = make_caption(quote_thai, author_en)
        print(f"Caption:\n{caption}\n")

        if dry_run:
            print("\n--- [DRY RUN RESULTS] ---")
            print(f"Quote EN: {quote_en}")
            print(f"Quote TH: {quote_thai}")
            print(f"Author: {author_thai} ({author_en})")
            print(f"Lines: {lines}")
            print(f"Image Path: {final_path}")
            print("\nDry run completed successfully (posting skipped).")
            return
        else:
            success = post_photo(caption, final_path)
            if success:
                save_to_history(quote_en)
                return

    print("Failed after 5 attempts")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run without posting to Facebook")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
