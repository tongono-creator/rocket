# -*- coding: utf-8 -*-
"""meme.py — สร้าง comic strip มุกตลก 3 panel โพส Facebook วันละ 1 ครั้ง"""

import sys, io, os, base64, requests, time
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai
from google.genai import types

GOOGLE_API_KEY    = os.environ.get("GOOGLE_API_KEY",    "")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
PAGE_ID           = os.environ.get("PAGE_ID",           "111830598532037")
IMAGE_MODEL       = "gemini-3.1-flash-image-preview"
TEXT_MODEL        = "gemini-2.5-flash"
OUTPUT_DIR        = "output"

if not GOOGLE_API_KEY:
    try:
        from config import GOOGLE_API_KEY, PAGE_ACCESS_TOKEN, PAGE_ID
    except ImportError:
        pass

os.makedirs(OUTPUT_DIR, exist_ok=True)
client = genai.Client(api_key=GOOGLE_API_KEY)

# ─── มุกหมุนเวียน 30 วัน ──────────────────────────────────────
MEME_SCENARIOS = [
    "คนวางแผนเก็บเงิน vs เงินเดือนออก — panel 1: ตั้งใจเก็บ panel 2: บิลเข้า panel 3: เงินหาย",
    "เพื่อนชวนกินข้าว vs กระเป๋าตัง — panel 1: ดูเมนูแพง panel 2: แกล้งทำเป็นดูโทรศัพท์ panel 3: สั่งน้ำเปล่า",
    "ตั้งนาฬิกาออกกำลังกาย vs ความเป็นจริง — panel 1: ตั้ง 5 โมงเช้า panel 2: กดเลื่อน panel 3: ตื่นสาย",
    "ดูยูทูบสอนลงทุน vs พอร์ตจริง — panel 1: มั่นใจมาก panel 2: กดซื้อ panel 3: ติดลบ",
    "บอสบอกให้ทำงานพิเศษ vs ในใจ — panel 1: หน้ายิ้ม panel 2: พยักหน้า panel 3: ในหัวโกรธ",
    "วางแผนออมเงิน vs แฟชั่นเซล — panel 1: ตั้งใจจะออม panel 2: เห็นป้ายลด panel 3: กดซื้อ",
    "บอกตัวเองจะนอนเร็ว vs โทรศัพท์ — panel 1: วางโทรศัพท์ panel 2: หยิบขึ้นมา panel 3: ตี 2",
    "ประชุมยาว vs ประชุมจบ — panel 1: ในห้องประชุม panel 2: เห็นนาฬิกา panel 3: ยังไม่จบ",
    "อยากลาออก vs เงินเดือนเข้า — panel 1: เตรียมใบลาออก panel 2: โอนเงิน panel 3: ยังอยู่",
    "เด็กขอเงินค่าขนม vs กระเป๋าพ่อแม่ — panel 1: ลูกยิ้มน่ารัก panel 2: พ่อแม่หน้าเครียด panel 3: ควักให้",
    "ตั้งงบซื้อของ vs ของจริงที่ซื้อ — panel 1: ตั้งงบ 500 panel 2: ชอบหลายอย่าง panel 3: จ่าย 2000",
    "คิดว่าเครียดคนเดียว vs เพื่อนร่วมงาน — panel 1: นั่งเครียด panel 2: มองรอบข้าง panel 3: ทุกคนเครียดเหมือนกัน",
    "แพลนเที่ยว vs บัญชีธนาคาร — panel 1: ดูรีวิวที่เที่ยว panel 2: เปิดแอพธนาคาร panel 3: เที่ยวในหัว",
    "กาแฟแก้วแรก vs กาแฟแก้วที่สาม — panel 1: ง่วงมาก panel 2: ดื่มกาแฟ panel 3: ยังง่วงอยู่",
    "บอกว่าไม่ซื้อของออนไลน์ vs แอพช้อปปิ้ง — panel 1: ปิดแอพ panel 2: โฆษณาขึ้น panel 3: กดซื้อ",
    "ทำ to-do list vs ทำจริง — panel 1: เขียนยาวมาก panel 2: เริ่มข้อแรก panel 3: เหนื่อยแล้ว",
    "เงินเดือนเข้า vs เงินออก — panel 1: ดีใจเงินเข้า panel 2: จ่ายบิล panel 3: เหลือน้อยมาก",
    "อยากรวย vs ขี้เกียจ — panel 1: ดูคนรวยในยูทูบ panel 2: ตั้งใจจะทำ panel 3: นอนต่อ",
    "ประหยัดค่ากาแฟ vs กาแฟดีๆ — panel 1: ชงเอง panel 2: เห็นร้านกาแฟ panel 3: แวะซื้อ",
    "วันหยุดยาว vs วันจันทร์กลับมา — panel 1: มีความสุข panel 2: วันอาทิตย์กลางคืน panel 3: เศร้ามาก",
    "ดูแลสุขภาพ vs ของอร่อย — panel 1: ตั้งใจกินคลีน panel 2: เห็นหมูกระทะ panel 3: กินหมด",
    "ประชุม zoom vs กล้องปิด — panel 1: เปิด zoom panel 2: ปิดกล้อง panel 3: ไปนอน",
    "รอเงินเดือนสิ้นเดือน vs ยังอีกนาน — panel 1: ดูปฏิทิน panel 2: นับวัน panel 3: เหนื่อย",
    "โบนัส vs หนี้ — panel 1: ดีใจโบนัสออก panel 2: เห็นยอดหนี้ panel 3: โบนัสหาย",
    "อ่านหนังสือพัฒนาตัวเอง vs ดูซีรีส์ — panel 1: หยิบหนังสือ panel 2: เปิดทีวี panel 3: ดูซีรีส์จนดึก",
    "พ่อแม่ถามเรื่องแต่งงาน vs ในใจ — panel 1: ถูกถาม panel 2: หน้ายิ้ม panel 3: ในใจเครียด",
    "ลดน้ำหนัก vs อาหารอร่อย — panel 1: ตั้งใจลด panel 2: เพื่อนชวนกิน panel 3: กินหมด",
    "สัมภาษณ์งาน vs ความเป็นจริง — panel 1: บอกว่าเก่ง panel 2: ได้งาน panel 3: งานจริงต่างมาก",
    "ออมเงินไว้ฉุกเฉิน vs เงินฉุกเฉิน — panel 1: เก็บเงิน panel 2: รถเสีย panel 3: เงินหาย",
    "คิดว่าจะไม่ซื้อ vs Flash Sale — panel 1: ตั้งใจแน่วแน่ panel 2: Flash sale 5 นาที panel 3: ซื้อหมด",
]

def get_scenario():
    bkk = timezone(timedelta(hours=7))
    day_idx = (datetime.now(bkk).timetuple().tm_yday - 1) % len(MEME_SCENARIOS)
    return MEME_SCENARIOS[day_idx]

def generate_meme_caption(scenario):
    print(f"Scenario: {scenario}")
    resp_text = None
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=TEXT_MODEL,
                contents=(
                    f"เขียน Facebook caption ภาษาไทยสำหรับมุกตลก: {scenario}\n"
                    "สั้นกระชับ 1-3 บรรทัด ขำขัน relatable สำหรับคนอายุ 30-45 ปี\n"
                    "ท้ายใส่ hashtag 2-3 อัน ตอบแค่ caption เท่านั้น"
                )
            )
            resp_text = resp.text.strip()
            print(f"Caption:\n{resp_text}\n")
            return resp_text
        except Exception as e:
            print(f"Caption attempt {attempt+1} failed: {str(e)[:100]}")
            if attempt < 2:
                time.sleep(15)
    raise RuntimeError("Caption generation failed")

def generate_meme_image(scenario):
    print("Generating meme comic strip...")
    prompt = (
        "Create a horizontal 3-panel comic strip (wide format, white background). "
        "Each panel has a simple cartoon style with a Thai office worker or family character. "
        "Silent comic — minimal text, story told through expressions and visuals. "
        f"Story: {scenario}. "
        "Panel borders visible, clean and funny cartoon style, "
        "relatable Thai everyday life humor. No offensive content."
    )
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=IMAGE_MODEL,
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
                    path = os.path.join(OUTPUT_DIR, f"meme_{ts}.png")
                    with open(path, "wb") as f:
                        f.write(data)
                    print(f"Meme saved: {path}")
                    return path
        except Exception as e:
            print(f"Image attempt {attempt+1} failed: {str(e)[:100]}")
            if attempt < 2:
                time.sleep(15)
    raise RuntimeError("Meme image generation failed after 3 attempts")

def post_facebook(img_path, caption):
    print("Posting meme to Facebook...")
    with open(img_path, "rb") as f:
        resp = requests.post(
            f"https://graph.facebook.com/v25.0/{PAGE_ID}/photos",
            data={"access_token": PAGE_ACCESS_TOKEN, "caption": caption, "published": "true"},
            files={"source": ("meme.png", f, "image/png")}
        )
    result = resp.json()
    if "id" in result:
        post_id = result.get("post_id") or result["id"]
        print(f"Meme Posted! ID: {post_id}")
        add_comment(post_id)
    else:
        print(f"FB Error: {result}")
        raise SystemExit(1)

def add_comment(post_id):
    from affiliate_utils import get_all_comments
    for i, msg in enumerate(get_all_comments(), 1):
        resp = requests.post(
            f"https://graph.facebook.com/v25.0/{post_id}/comments",
            data={"access_token": PAGE_ACCESS_TOKEN, "message": msg}
        )
        result = resp.json()
        if "id" in result:
            print(f"Comment {i} added! ID: {result['id']}")
        else:
            print(f"Comment {i} error: {result}")
        time.sleep(2)

if __name__ == "__main__":
    scenario = get_scenario()
    caption  = generate_meme_caption(scenario)
    img_path = generate_meme_image(scenario)
    post_facebook(img_path, caption)
