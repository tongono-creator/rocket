# -*- coding: utf-8 -*-
"""meme.py — สร้าง comic strip มุกตลก 3 panel โพส Facebook วันละ 1 ครั้ง"""

import sys, io, os, base64, requests, time, random
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai
from google.genai import types

GOOGLE_API_KEY    = os.environ.get("GOOGLE_API_KEY",    "")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
PAGE_ID           = os.environ.get("PAGE_ID",           "111830598532037")
IMAGE_MODEL       = "gemini-3.1-flash-image-preview"
TEXT_MODELS       = ["gemini-3.5-flash", "gemini-2.5-flash"]
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
    # สำหรับ Generation comparison style
    "การเก็บเงิน — รุ่นปู่: เก็บในไห รุ่นพ่อ: ฝากธนาคาร รุ่นลูก: ลงทุนหุ้น รุ่นหลาน: กู้ซื้อ iPhone",
    "การทำงาน — รุ่นปู่: ทำนาตากแดด รุ่นพ่อ: รับราชการ รุ่นลูก: พนักงานบริษัท รุ่นหลาน: Influencer นอนถ่ายคลิป",
    "การเดินทางไปทำงาน — รุ่นปู่: เดินเท้า รุ่นพ่อ: ขี่จักรยาน รุ่นลูก: ขับรถติด รุ่นหลาน: WFH ใส่ชุดนอน",
    "การซื้อบ้าน — รุ่นปู่: ปลูกเองด้วยมือ รุ่นพ่อ: ผ่อนธนาคาร 30 ปี รุ่นลูก: เช่าคอนโด รุ่นหลาน: อยู่บ้านพ่อแม่ไปก่อน",
    "การออมเงินเกษียณ — รุ่นปู่: มีที่ดินไว้ รุ่นพ่อ: บำนาญราชการ รุ่นลูก: ประกันชีวิต รุ่นหลาน: หวังว่าลูกจะเลี้ยง",
]

# ─── Meme styles ──────────────────────────────────────────────
NO_BORDER = "NO white outer border, NO white frame, image fills edge to edge, bleed to edges. "
SIGNATURE_STYLE = (
    "ART STYLE: Thai retro 90s comic with chibi characters — big round heads, tiny bodies, "
    "exaggerated cute expressions. Thick heavy black outlines. "
    "Warm retro color palette: earthy browns, muted oranges, warm yellows, soft reds, faded greens. "
    "Flat color fills with simple cel-shading shadows. Slightly aged paper texture feel. "
    "Characters look like classic Thai cartoon from 1990s but with chibi proportions. "
)

MEME_STYLES = [
    {
        "name": "3-panel comic",
        "image_prompt": (
            "Create a vertical 3-panel comic strip in 4:5 portrait ratio (tall format). "
            + SIGNATURE_STYLE +
            "Stack panels top to bottom. Thai office worker or family chibi character. "
            "Silent comic, story told through expressions. Panel borders visible between panels only. "
            "Story: {scenario}. Funny, relatable Thai everyday life humor. " + NO_BORDER
        ),
    },
    {
        "name": "Khaby Lame style",
        "image_prompt": (
            "Create a 2-panel meme image in 4:5 portrait ratio (tall format). "
            + SIGNATURE_STYLE +
            "Stack panels top and bottom. Top panel: complicated/stressful way someone does something "
            "related to: {scenario}. Bottom panel: a calm confident chibi person showing the obvious simple solution "
            "with open hands gesture (Khaby Lame style). Funny. " + NO_BORDER
        ),
    },
    {
        "name": "Cat reaction meme",
        "image_prompt": (
            "Create a funny cat meme image in 4:5 portrait ratio (tall format). "
            + SIGNATURE_STYLE +
            "Show an annoyed or unimpressed chibi cat in an office or home setting "
            "reacting to: {scenario}. Cat has huge expressive eyes showing relatable emotion. "
            "No text needed. " + NO_BORDER
        ),
    },
    {
        "name": "Distracted choice meme",
        "image_prompt": (
            "Create a 'distracted boyfriend' style meme cartoon in 4:5 portrait ratio (tall format). "
            + SIGNATURE_STYLE +
            "A chibi Thai office worker walking with 'responsible choice' "
            "but turning head to look at 'tempting bad choice' related to: {scenario}. "
            "Label each person/object clearly in Thai. Funny and relatable. " + NO_BORDER
        ),
    },
    {
        "name": "Expectation vs Reality",
        "image_prompt": (
            "Create a split image meme in 4:5 portrait ratio (tall format). "
            + SIGNATURE_STYLE +
            "Top half labeled 'ที่คิดไว้' (expectation) with a happy idealistic chibi scene. "
            "Bottom half labeled 'ความเป็นจริง' (reality) with a funny contrasting chibi scene. "
            "Topic: {scenario}. Very funny. " + NO_BORDER
        ),
    },
    {
        "name": "Generation comparison",
        "image_prompt": (
            "Create a 2x2 four-panel comic grid in 4:5 portrait ratio (tall format). "
            + SIGNATURE_STYLE +
            "Each panel shows the same topic across Thai generations with a funny ironic twist. "
            "Panel top-left: รุ่นปู่ (grandfather's era, old-fashioned hard way). "
            "Panel top-right: รุ่นพ่อ (father's era, slightly improved). "
            "Panel bottom-left: รุ่นลูก (our generation, modern approach). "
            "Panel bottom-right: รุ่นหลาน (grandchild's era, ironic/lazy/unexpected punchline). "
            "Each panel has a bold Thai label badge at bottom: รุ่นปู่ / รุ่นพ่อ / รุ่นลูก / รุ่นหลาน. "
            "Topic: {scenario}. Thin panel dividers only. " + NO_BORDER
        ),
    },
]

GENERATION_SCENARIOS = [s for s in MEME_SCENARIOS if "รุ่นปู่" in s]
REGULAR_SCENARIOS    = [s for s in MEME_SCENARIOS if "รุ่นปู่" not in s]

def get_slot():
    """คืนค่า slot 0/1/2 ตามเวลา BKK: 07:30=0, 11:30=1, 16:30=2"""
    bkk = timezone(timedelta(hours=7))
    hour = datetime.now(bkk).hour
    if hour < 10:
        return 0
    elif hour < 14:
        return 1
    else:
        return 2

def get_scenario():
    bkk = timezone(timedelta(hours=7))
    now = datetime.now(bkk)
    day  = now.timetuple().tm_yday
    slot = get_slot()
    # แต่ละ slot ใช้ offset ต่างกัน → scenario ไม่ซ้ำกัน 3 ครั้ง/วัน
    seed = (day - 1) * 3 + slot
    style_idx = seed % len(MEME_STYLES)
    style = MEME_STYLES[style_idx]
    if style["name"] == "Generation comparison":
        scenario = GENERATION_SCENARIOS[seed % len(GENERATION_SCENARIOS)]
    else:
        scenario = REGULAR_SCENARIOS[seed % len(REGULAR_SCENARIOS)]
    return scenario, style

def generate_meme_caption(scenario, style):
    print(f"Scenario: {scenario} | Style: {style['name']}")
    prompt = (
        f"เขียน Facebook caption ภาษาไทยสำหรับมุก style '{style['name']}' เรื่อง: {scenario}\n"
        "สั้น 1-2 บรรทัด ขำขัน relatable คนอายุ 30-45 อ่านแล้วขำได้เลย\n"
        "ห้ามบรรยายว่า 'ช่อง 1' 'ช่อง 2' ห้ามอธิบายรูป — caption ต้องสมบูรณ์ในตัวเอง\n"
        "ท้ายใส่ hashtag 2 อัน ตอบแค่ caption เท่านั้น"
    )
    for model in TEXT_MODELS:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                text = resp.text.strip()
                print(f"Caption [{model}]:\n{text}\n")
                return text
            except Exception as e:
                print(f"[{model}] attempt {attempt+1} failed: {str(e)[:100]}")
                if attempt < 1:
                    time.sleep(10)
        print(f"[{model}] unavailable, trying next model...")
    raise RuntimeError("Caption generation failed on all models")

def generate_meme_image(scenario, style):
    print(f"Generating meme [{style['name']}]...")
    prompt = style["image_prompt"].format(scenario=scenario)
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
    comments = get_all_comments()
    delay0 = random.uniform(60, 180)
    print(f"Waiting {delay0:.0f}s before first comment...")
    time.sleep(delay0)
    for i, msg in enumerate(comments, 1):
        resp = requests.post(
            f"https://graph.facebook.com/v25.0/{post_id}/comments",
            data={"access_token": PAGE_ACCESS_TOKEN, "message": msg}
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
    scenario, style = get_scenario()
    caption  = generate_meme_caption(scenario, style)
    img_path = generate_meme_image(scenario, style)
    post_facebook(img_path, caption)
