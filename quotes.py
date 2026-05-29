import os
import re
import random
import time
import requests
import tempfile
from PIL import Image, ImageDraw, ImageFont
from google import genai

# -- Config --
PAGE_ID           = "111830598532037"
PAGE_ACCESS_TOKEN = os.environ["PAGE_ACCESS_TOKEN"]
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY    = os.environ["PEXELS_API_KEY"]

client      = genai.Client(api_key=GEMINI_API_KEY, http_options={'timeout': 90.0})
TEXT_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash"]
GOLD        = (255, 215, 0)
WHITE       = (255, 255, 255)
SILVER      = (200, 200, 200)
FONT_PATH   = os.path.join(os.path.dirname(__file__), "fonts", "Kanit-Bold.ttf")
HEADERS     = {"User-Agent": "Mozilla/5.0 (compatible; RocketBot/1.0)"}

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


_LEADING_VOWELS  = set("เแโใไ")
_COMBINING_CHARS = set("่้๊๋์ิีึืุูัํ็")


def _wrap_char(draw, text, font, max_width):
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
def main():
    print("=== Rocket21 Quotes Bot ===")

    for attempt in range(5):
        print(f"Attempt {attempt + 1}/5")

        quote_en, author_en = get_quote()
        if not quote_en:
            continue

        quote_thai  = translate_quote(quote_en, author_en)
        author_thai = transliterate_author(author_en)
        lines       = split_quote_lines(quote_thai)

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

        success = post_photo(caption, final_path)
        if success:
            save_to_history(quote_en)
            return

    print("Failed after 5 attempts")


if __name__ == "__main__":
    main()
