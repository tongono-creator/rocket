# -*- coding: utf-8 -*-
"""meme.py — 2-panel comic strip style จ้อง 8 รั้ว โพส Facebook วันละ 1 ครั้ง"""

import sys, io, os, re, base64, requests, time, random
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai
from google.genai import types
from google.genai.types import HttpOptions

GOOGLE_API_KEY    = os.environ.get("GOOGLE_API_KEY",    "")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
PAGE_ID           = os.environ.get("PAGE_ID",           "111830598532037")
IMAGE_MODELS      = ["gemini-2.0-flash-exp", "gemini-2.0-flash-preview-image-generation"]
TEXT_MODELS       = ["gemini-2.5-flash", "gemini-2.0-flash"]
OUTPUT_DIR        = "output"
FONT_PATH         = os.path.join(os.path.dirname(__file__), "fonts", "Kanit-Bold.ttf")

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


# ─── ตัวละครประจำ Rocket21 ─────────────────────────────────────
# ใส่ทุก image prompt — ให้ character เดิมปรากฏทั้ง 2 panel
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

# ─── Fallback scenarios (label1_th, scene1_en, label2_th, scene2_en) ──
FALLBACK_SCENARIOS = [
    (
        "ตอนประกาศจะตั้งใจทำงาน",
        "Thai man in 30s confidently looking at his blank calendar with a bright morning smile, ready to work",
        "หลังผ่านไป 1 ชั่วโมง",
        "Same man looking exhausted, holding a cup of coffee with stress sweat drops, looking at a calendar filled with urgent meetings",
    ),
    (
        "เมื่อบอสบอกว่ามีรางวัลพิเศษให้",
        "Thai man in 30s clapping hands happily with eyes sparkling with hope in a neat modern office",
        "รางวัลที่ได้รับจริง",
        "Same man slumped at desk buried under giant stacks of new folders, holding a massive pile of files with a blank numb expression",
    ),
    (
        "เช้าวันเสาร์ที่ตั้งใจจะพักผ่อน",
        "Thai man lying peacefully on bed reading a book, soft morning light, relaxed smile",
        "เมื่อมีแจ้งเตือน LINE จากหัวหน้า",
        "Same man staring at his glowing smartphone screen in panic, eyes wide with horror, sweat drops flying",
    ),
    (
        "ตอนบอสบอกว่า 'เปิดใจคุยกันได้'",
        "Thai man smiling warmly, preparing to speak at a conference table, boss nodding",
        "หลังจากพูดความจริงไป",
        "Same man sweating profusely with a forced tight smile, packaging his personal belongings into a cardboard box",
    ),
    (
        "วันเงินเดือนออก กินหรูอยู่แพง",
        "Thai man sitting happily at a fancy steakhouse table, gourmet food, confident rich expression",
        "สัปดาห์ถัดมา จ้องซองกาแฟ 3-in-1",
        "Same man in his kitchen looking sadly at a near-empty wallet and holding a single instant coffee sachet",
    ),
]


def gemini_text(prompt):
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            return resp.text.strip()
        except Exception as e:
            print(f"[{model}] text failed: {str(e)[:80]}")
    return ""


# ─── มุมมองการเสียดสีและมุกตลกเพื่อความหลากหลาย (Meme Angles Rotation) ───
MEME_ANGLES = [
    {
        "category": "การประชุมและงานด่วน (Meetings & Urgent Tasks)",
        "focus": "การประชุมที่ลากยาวอย่างไร้สาระเพื่อหาข้อสรุปที่ไม่มีใครทำตาม หรือการโดนเรียกประชุมด่วนช่วงจะเลิกงาน"
    },
    {
        "category": "เงินเดือนและสภาพคล่อง (Salary & Mid-month struggles)",
        "focus": "ความรู้สึกรวยในวันเงินเดือนออกเพียง 5 นาที ก่อนที่บิลค่าใช้จ่าย/หนี้สินจะหักไปจนแทบหมด"
    },
    {
        "category": "วันหยุดและงานลาม (Weekends vs Work)",
        "focus": "การวางแผนนอนโง่ๆ พักผ่อนเต็มที่ในวันเสาร์อาทิตย์ แต่โดนหัวหน้าแท็กสั่งงานด่วนในกลุ่ม LINE"
    },
    {
        "category": "คำสัญญาของหัวหน้า (Boss Promises vs Reality)",
        "focus": "หัวหน้าบอกว่า 'ถ้างานนี้ผ่านจะมีรางวัลพิเศษให้' หรือ 'เปิดใจคุยกันได้' แต่ผลลัพธ์กลับตรงกันข้ามโดยสิ้นเชิง"
    },
    {
        "category": "การซื้อของประชดชีวิต (Retail Therapy)",
        "focus": "การทำงานหนักแล้วเอาเงินไปซื้อกาแฟแก้วละ 150 บาท หรือของฟุ่มเฟือยเพื่อบำบัดจิตใจ ทั้งที่เงินเก็บไม่มี"
    },
    {
        "category": "ประเมินผลงานและความก้าวหน้า (Performance & Career)",
        "focus": "ความขยันทำงานแทบตายแต่ตอนประเมินผลได้เท่าเดิม หรือการทำงานหนักจนหลังหักแต่คนอื่นได้เลื่อนขั้น"
    },
    {
        "category": "สุขภาพร่างกายและออฟฟิศซินโดรม (Office Syndrome & Health)",
        "focus": "ตอนเริ่มงานอายุ 25 ร่างกายแข็งแรงฟิตปั๋ง ตอนนี้อายุ 30+ ตื่นมาพร้อมความปวดหลัง คอ บ่า ไหล่ และพลาสเตอร์ยาเต็มตัว"
    },
    {
        "category": "พนักงานใหม่ vs พนักงานเก่า (Junior vs Senior)",
        "focus": "พนักงานใหม่เข้ามาทำงานด้วยพลังเปี่ยมล้นและรอยยิ้มสดใส VS รุ่นพี่อายุ 30+ ที่จิบกาแฟจ้องหน้าจอด้วยสายตาว่างเปล่าและเหนื่อยล้า"
    },
    {
        "category": "การวางแผนเก็บเงิน (Failed Savings Plan)",
        "focus": "ตั้งเป้าต้นปีว่าจะเก็บเงิน 1 แสนบาทถ้วนเพื่ออนาคต แต่กลางปีพบว่าเงินเก็บเหลือ 50 บาทถ้วนและหนี้งอกขึ้นมาใหม่"
    },
    {
        "category": "ความฝันในการลาออก (Dreams of Resigning)",
        "focus": "จินตนาการในหัวว่าถ้าถูกหวยรางวัลที่ 1 จะเดินไปโยนใบลาออกใส่หน้าหัวหน้าอย่างสง่างาม แต่ความจริงคือเสียงนาฬิกาปลุกดังและต้องรีบวิ่งไปขึ้นรถเมล์"
    }
]


def generate_scenario_2panel():
    """AI คิด 2-panel scenario — คืน (label1_th, scene1_en, label2_th, scene2_en, category) โดยใช้การหมุนเวียนมุมมองมุกตลกเพื่อป้องกันมุกซ้ำ"""
    history = set(load_history())
    available = [a for a in MEME_ANGLES if a['category'] not in history]
    if not available:
        print("All meme angles already posted. Resetting history for angles.")
        available = MEME_ANGLES
    selected_angle = random.choice(available)
    
    print(f"Selected Angle: {selected_angle['category']}")

    prompt = (
        "Create a 2-panel 'before vs after' or 'expectation vs reality' Thai comic scenario for office workers aged 30-45.\n"
        f"You MUST base the comic scenario on this specific joke theme:\n"
        f"- Category: {selected_angle['category']}\n"
        f"- Focus/Angle: {selected_angle['focus']}\n\n"
        "Ensure the contrast from panel 1 (expectation/hopeful) to panel 2 (brutal reality/sarcastic twist) is very funny, relatable, and prompt-driven to get comments.\n\n"
        "Output EXACTLY 4 lines, nothing else:\n"
        "Line 1: Panel 1 Thai label — short specific phrase 3-7 words (e.g. ตอนอาสาทำงานใหม่)\n"
        "Line 2: Panel 1 image — English description of what character does/feels, 15-25 words\n"
        "Line 3: Panel 2 Thai label — short specific phrase 3-7 words (e.g. สิ่งที่ได้คืองานเพื่อนร่วมงาน)\n"
        "Line 4: Panel 2 image — English description of SAME character in contrasting situation, 15-25 words\n"
        "Do NOT include line numbers or prefixes. Just the 4 lines."
    )
    result = gemini_text(prompt)
    lines = [re.sub(r'^(Line\s*\d+[:.]\s*|[\d]+[.)]\s*)', '', l).strip()
             for l in result.split("\n") if l.strip()]
    lines = [l for l in lines if l]

    if len(lines) >= 4:
        label1, scene1, label2, scene2 = lines[0], lines[1], lines[2], lines[3]
        print(f"Scenario: [{label1}] {scene1}")
        print(f"          [{label2}] {scene2}")
        return label1, scene1, label2, scene2, selected_angle['category']

    print("Scenario gen failed — using fallback")
    fb = random.choice(FALLBACK_SCENARIOS)
    return fb[0], fb[1], fb[2], fb[3], "Fallback"


def generate_panel_image(scene_en, panel_num):
    """Generate รูป 1 panel — คืน path PNG"""
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
                    break  # ไม่ต้อง retry — model ไม่มี
                if attempt < 2:
                    time.sleep(15)
    raise RuntimeError(f"Panel {panel_num} generation failed — all models exhausted")


def stitch_panels(img1_path, img2_path, label1, label2):
    """
    ต่อ 2 panel แนวตั้ง → 1080x1080
    วาด label box style จ้อง 8 รั้ว บนแต่ละ panel
    """
    W, H = 1080, 1080
    panel_h = H // 2  # 540px ต่อ panel

    canvas = Image.new("RGB", (W, H), (240, 240, 240))

    bkk = timezone(timedelta(hours=7))
    ts = datetime.now(bkk).strftime("%Y%m%d_%H%M%S")

    for idx, (ipath, label) in enumerate([(img1_path, label1), (img2_path, label2)]):
        img = Image.open(ipath).convert("RGB")
        iw, ih = img.size

        # Crop ให้เป็น 2:1 ratio — ตัดจากตรงกลาง
        target_ratio = W / panel_h  # 2.0
        if iw / ih > target_ratio:
            # กว้างเกิน — crop ซ้ายขวา
            new_w = int(ih * target_ratio)
            left = (iw - new_w) // 2
            img = img.crop((left, 0, left + new_w, ih))
        else:
            # สูงเกิน — crop บนล่าง (ใช้ offset ปานกลาง 2.5 เพื่อให้เหลือพื้นที่หัวและตัวด้านล่างสมดุลกัน)
            new_h = int(iw / target_ratio)
            top = int(max(0, (ih - new_h) // 2.5))
            img = img.crop((0, top, iw, top + new_h))

        img = img.resize((W, panel_h), Image.LANCZOS)
        canvas.paste(img, (0, idx * panel_h))

        # ─── วาด label text โดยตรงบน panel (style Jod 8riew) ────────
        draw = ImageDraw.Draw(canvas)
        try:
            font = ImageFont.truetype(FONT_PATH, 42)
        except Exception:
            font = ImageFont.load_default()

        MARGIN = 28
        tx = MARGIN
        ty = idx * panel_h + MARGIN
        # 8-direction outline → อ่านได้บนทุกพื้นหลัง ไม่ต้องมี box
        for dx, dy in [(-3,-3),(-3,0),(-3,3),(0,-3),(0,3),(3,-3),(3,0),(3,3)]:
            draw.text((tx + dx, ty + dy), label, font=font, fill=(0, 0, 0))
        draw.text((tx, ty), label, font=font, fill=(255, 255, 255))

    # Divider ระหว่าง 2 panel
    draw = ImageDraw.Draw(canvas)
    draw.line([(0, panel_h), (W, panel_h)], fill=(20, 20, 20), width=4)

    out_path = os.path.join(OUTPUT_DIR, f"meme_comic_{ts}.jpg")
    canvas.save(out_path, "JPEG", quality=92)
    print(f"Comic saved: {out_path}")
    return out_path


def generate_caption(label1, label2):
    """Caption Facebook จาก label ทั้งสอง"""
    prompt = (
        f"เขียน Facebook caption ภาษาไทย 1-2 บรรทัด สำหรับการ์ตูน 2 panel:\n"
        f"Panel 1: '{label1}'\n"
        f"Panel 2: '{label2}'\n"
        "สั้น ขำ relatable คนอายุ 30+ — ห้ามอธิบายว่ามีกี่ panel ไม่ต้องบอกว่า 'ในรูป'\n"
        "ท้ายใส่ hashtag 2-3 อัน ตอบแค่ caption เท่านั้น"
    )
    caption = gemini_text(prompt)
    print(f"Caption:\n{caption}\n")
    return caption or f"{label1} → {label2}\n\n#ชีวิตคนทำงาน #Relatable #Rocket21"


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
        print(f"Posted! ID: {post_id}")
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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode without generating images or posting")
    args = parser.parse_args()

    # Step 1: AI คิด scenario
    label1, scene1, label2, scene2, category = generate_scenario_2panel()

    if args.dry_run:
        print("\n--- [DRY RUN RESULTS] ---")
        print(f"Category: {category}")
        print(f"Panel 1 Label: {label1}")
        print(f"Panel 1 Image Prompt: {scene1}")
        print(f"Panel 2 Label: {label2}")
        print(f"Panel 2 Image Prompt: {scene2}")
        caption = generate_caption(label1, label2)
        print("\nDry run completed successfully (image generation and posting skipped).")
        sys.exit(0)

    # Step 2: Generate 2 panels แยกกัน → ป้องกัน duplicate panel bug
    img1 = generate_panel_image(scene1, panel_num=1)
    img2 = generate_panel_image(scene2, panel_num=2)

    # Step 3: Stitch + วาด label box
    comic = stitch_panels(img1, img2, label1, label2)

    # Step 4: ลบ temp files
    for p in [img1, img2]:
        try:
            os.unlink(p)
        except Exception:
            pass

    # Step 5: Caption + Post
    caption = generate_caption(label1, label2)
    post_id = post_facebook(comic, caption)
    if post_id and category != "Fallback":
        save_to_history(category)
