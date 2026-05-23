import os
import re
import random
import time
import textwrap
import requests
import tempfile
from PIL import Image, ImageDraw, ImageFont
from google import genai

# -- Config --
PAGE_ID           = "111830598532037"
PAGE_ACCESS_TOKEN = os.environ["PAGE_ACCESS_TOKEN"]
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY    = os.environ["PEXELS_API_KEY"]

client      = genai.Client(api_key=GEMINI_API_KEY)
TEXT_MODELS = ["gemini-2.5-flash", "gemini-3.5-flash"]
GOLD        = (255, 215, 0)
WHITE       = (255, 255, 255)
FONT_PATH   = os.path.join(os.path.dirname(__file__), "fonts", "Kanit-Bold.ttf")
HEADERS     = {"User-Agent": "Mozilla/5.0 (compatible; RocketBot/1.0)"}


# -- ZenQuotes API --
def get_quote():
    for _ in range(5):
        try:
            resp = requests.get(
                "https://zenquotes.io/api/random",
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if data:
                item = data[0]
                quote  = item.get("q", "").strip()
                author = item.get("a", "").strip()
                # skip generic/unknown authors
                if not quote or not author or author.lower() in ("unknown", "anonymous", ""):
                    continue
                print(f"Quote: {author} — {quote[:60]}")
                return quote, author
        except Exception as e:
            print(f"ZenQuotes error: {e}")
            time.sleep(2)
    return None, None


# -- Gemini --
def translate_quote(content, author):
    prompt = (
        f'Translate this English quote to natural Thai language.\n'
        f'Quote: "{content}"\n'
        f'Author: {author}\n'
        f'Return ONLY the Thai translation of the quote. Keep it natural and inspiring. No markdown.'
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


def make_caption(quote_thai, author):
    prompt = (
        f'Write a short Facebook caption in Thai for an inspirational quote post.\n'
        f'Quote (Thai): {quote_thai}\n'
        f'Author: {author}\n'
        f'Format:\n'
        f'Line 1: engaging hook sentence (Thai)\n'
        f'Line 2: short context about the author or quote (Thai)\n'
        f'Line 3: 2-3 relevant hashtags in Thai\n'
        f'No markdown, no **bold**.'
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            return clean_text(resp.text.strip())
        except Exception as e:
            print(f"[{model}] caption failed: {e}")
    return f'"{quote_thai}"\n— {author}\n#คำคม #แรงบันดาลใจ #Rocket21'


def clean_text(text):
    text = text.replace("\\n", "\n")
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",     r"\1", text)
    text = re.sub(r"__(.+?)__",     r"\1", text)
    text = re.sub(r"_(.+?)_",       r"\1", text)
    text = re.sub(r"^#+\s*",        "",    text, flags=re.MULTILINE)
    return text.strip()


# -- Pexels --
def get_author_photo(author_name):
    try:
        resp = requests.get(
            "https://api.pexels.com/v1/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": author_name, "per_page": 5, "orientation": "portrait"},
            timeout=10,
        )
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            print(f"Pexels: no photo for '{author_name}'")
            return None
        url = photos[0]["src"]["large"]
        print(f"Pexels photo: {url[:60]}")
        return url
    except Exception as e:
        print(f"Pexels error: {e}")
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
                print("Image too large")
                return None
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.write(data)
        tmp.close()
        return tmp.name
    except Exception as e:
        print(f"Download failed: {e}")
        return None


# -- PIL Quote Image --
def make_quote_image(quote_thai, author, img_path=None):
    size = 1080

    # Background: photo or black
    if img_path:
        try:
            bg = Image.open(img_path).convert("RGB")
            w, h = bg.size
            side = min(w, h)
            bg = bg.crop(((w - side) // 2, (h - side) // 2,
                          (w + side) // 2, (h + side) // 2))
            bg = bg.resize((size, size), Image.LANCZOS)
        except Exception as e:
            print(f"Photo load failed: {e}, using black")
            bg = Image.new("RGB", (size, size), (0, 0, 0))
    else:
        bg = Image.new("RGB", (size, size), (0, 0, 0))

    draw = ImageDraw.Draw(bg, "RGBA")

    # Dark overlay — full image for photo, lighter for black bg
    if img_path:
        draw.rectangle([(0, 0), (size, size)], fill=(0, 0, 0, 140))

    # Fonts
    try:
        font_quote  = ImageFont.truetype(FONT_PATH, 52)
        font_author = ImageFont.truetype(FONT_PATH, 40)
        font_mark   = ImageFont.truetype(FONT_PATH, 140)
    except Exception as e:
        print(f"Font error: {e}")
        font_quote = font_author = font_mark = ImageFont.load_default()

    # Decorative quote mark top-left
    draw.text((50, 30), "“", font=font_mark, fill=(255, 215, 0, 100))

    # Wrap quote text
    max_chars = 22
    lines = textwrap.wrap(quote_thai, width=max_chars)

    # Calculate total text block height
    line_h   = 65
    author_h = 55
    gap      = 30
    total_h  = len(lines) * line_h + gap + author_h
    y_start  = (size - total_h) // 2 + 60  # slight center-bias toward bottom

    # Draw quote lines (white, centered)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_quote)
        w_text = bbox[2] - bbox[0]
        x = (size - w_text) // 2
        # Shadow
        draw.text((x + 2, y_start + 2), line, font=font_quote, fill=(0, 0, 0, 180))
        draw.text((x, y_start), line, font=font_quote, fill=WHITE)
        y_start += line_h

    y_start += gap

    # Author line (gold, centered)
    author_text = f"— {author}"
    bbox = draw.textbbox((0, 0), author_text, font=font_author)
    w_text = bbox[2] - bbox[0]
    x = (size - w_text) // 2
    draw.text((x + 2, y_start + 2), author_text, font=font_author, fill=(0, 0, 0, 180))
    draw.text((x, y_start), author_text, font=font_author, fill=GOLD)

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
            f"https://graph.facebook.com/v21.0/{post_id}/comments",
            data=data,
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

        quote_en, author = get_quote()
        if not quote_en:
            continue

        quote_thai = translate_quote(quote_en, author)

        # Try to get author photo from Pexels
        img_path = None
        photo_url = get_author_photo(author)
        if photo_url:
            img_path = download_image(photo_url)
            if img_path:
                print(f"Using photo of {author}")
            else:
                print("Photo download failed, using black background")
        else:
            print("No photo found, using black background")

        final_path = make_quote_image(quote_thai, author, img_path)
        if img_path and os.path.exists(img_path):
            os.unlink(img_path)

        caption = make_caption(quote_thai, author)
        print(f"Caption:\n{caption}\n")

        success = post_photo(caption, final_path)
        if success:
            return

    print("Failed after 5 attempts")


if __name__ == "__main__":
    main()
