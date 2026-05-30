# -*- coding: utf-8 -*-
"""review.py — generate รูปรีวิวสินค้าจาก review_products.xlsx แล้วโพส FB"""

import sys, io, os, base64, requests, time, random, re
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai
import openpyxl
from overlay_utils import add_overlay

GOOGLE_API_KEY    = os.environ.get("GOOGLE_API_KEY",    "")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN", "")
PAGE_ID           = os.environ.get("PAGE_ID", "111830598532037")
TEXT_MODELS       = ["gemini-2.5-flash", "gemini-3.5-flash"]
OUTPUT_DIR        = "output"
EXCEL_PATH        = os.path.join(os.path.dirname(__file__), "review_products.xlsx")
ACCENT_COLOR      = (255, 215, 0) # Gold สำหรับ Rocket21
API_ENABLED       = True

if not GOOGLE_API_KEY:
    try:
        from config import GOOGLE_API_KEY, PAGE_ACCESS_TOKEN
    except ImportError:
        pass

os.makedirs(OUTPUT_DIR, exist_ok=True)
client = genai.Client(api_key=GOOGLE_API_KEY, http_options={'timeout': 15000.0})

_LEADING_VOWELS  = set('เแโใไ')
_COMBINING_CHARS = set('่้๊๋์ิีึืุูัํ็')

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

def segment_thai_text(text, client=client):
    global API_ENABLED
    if not text or not contains_thai(text):
        return text
    if not API_ENABLED:
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
            resp = client.models.generate_content(model=model, contents=prompt)
            segmented = resp.text.strip().replace('\\u200b', '\u200b')
            clean_orig = text.replace('\u200b', '').replace('\\u200b', '')
            clean_seg = segmented.replace('\u200b', '').replace('\\u200b', '')
            if len(clean_orig) == len(clean_seg):
                return segmented
        except Exception as e:
            print(f"[{model}] segment_thai_text failed: {e}")
            
    print("[Warning] segment_thai_text failed on all models. Disabling API calls for this run.")
    API_ENABLED = False
    return local_segment_thai(text)

def load_next_product():
    wb = openpyxl.load_workbook(EXCEL_PATH)
    ws = wb.active
    for row in ws.iter_rows(min_row=2, values_only=False):
        no    = row[0].value
        detail= row[1].value
        shopee= row[2].value
        lazada= row[3].value
        imgurl= row[4].value
        promo = row[5].value
        posted= row[6].value

        # ข้าม sample row และ posted แล้ว
        if not detail or "วางรายละเอียด" in str(detail):
            continue
        if str(posted).strip().lower() == "done" or str(posted).strip().startswith("done"):
            continue
        if not shopee or "xxx" in str(shopee):
            continue

        return {
            "row": row[0].row,
            "no": no,
            "detail": str(detail).strip(),
            "shopee": str(shopee).strip(),
            "lazada": str(lazada).strip() if lazada else "",
            "image_url": str(imgurl).strip() if imgurl else "",
            "promo": str(promo).strip() if promo else "",
        }, wb, ws
    return None, wb, ws

def mark_posted(wb, ws, row_num):
    bkk = timezone(timedelta(hours=7))
    ts = datetime.now(bkk).strftime("%Y-%m-%d %H:%M")
    ws.cell(row=row_num, column=7, value=f"done {ts}")
    wb.save(EXCEL_PATH)
    print(f"Marked row {row_num} as done")

def clean_promo(raw):
    """เอาเฉพาะบรรทัดที่มี ฿ หรือ ลด หรือ % หรือ ส่งฟรี"""
    if not raw:
        return ""
    lines = raw.strip().splitlines()
    kept = [l.strip() for l in lines if re.search(r'฿|ลด|%|ส่งฟรี|flash|sale', l, re.IGNORECASE)]
    return " | ".join(kept[:3]) if kept else ""

def extract_highlights(detail, promo):
    """ให้ AI สกัดจุดเด่นจาก raw detail"""
    global API_ENABLED
    highlights = None
    if API_ENABLED:
        prompt = (
            f"จากรายละเอียดสินค้านี้:\n{detail}\n\n"
            f"สกัดออกมาเป็น bullet points ภาษาไทยสั้นๆ 3-5 จุดเด่น "
            f"เน้นประโยชน์ที่คนซื้อสนใจ ห้ามใส่ข้อมูลราคาหรือโปรโมชั่น "
            f"ตอบแค่ bullet points เท่านั้น"
        )
        for model in TEXT_MODELS:
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                highlights = resp.text.strip()
                if highlights:
                    break
            except Exception as e:
                print(f"[{model}] highlights failed: {str(e)[:80]}")
                
        if not highlights:
            print("[Warning] Highlights generation failed on all models. Disabling API calls for this run.")
            API_ENABLED = False
            
    if not highlights:
        print("[Warning] Falling back to local heuristic extraction.")
        lines = [l.strip() for l in detail.splitlines() if l.strip()]
        thai_lines = [l for l in lines if contains_thai(l)]
        if not thai_lines:
            thai_lines = lines
        
        bullets = []
        for line in thai_lines:
            cleaned = re.sub(r'^[•\-\*\d\.\s\u2013]+', '', line).strip()
            if cleaned and len(cleaned) > 5 and len(cleaned) < 100:
                bullets.append(f"• {cleaned}")
            if len(bullets) >= 4:
                break
        if not bullets:
            bullets = [f"• {line[:80]}" for line in thai_lines[:3]]
        highlights = "\n".join(bullets) if bullets else "• รายละเอียดเพิ่มเติมตามระบุในลิงก์ร้านค้าครับ"

    if promo:
        highlights += f"\n🔥 โปรตอนนี้: {promo}"
    return highlights

def download_image(url):
    """Download รูปแรกจาก URL"""
    first_url = url.strip().split("\n")[0].strip()
    resp = requests.get(first_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    if resp.status_code == 200:
        bkk = timezone(timedelta(hours=7))
        ts = datetime.now(bkk).strftime("%Y%m%d_%H%M%S")
        ext = "webp" if "webp" in first_url else "jpg"
        path = os.path.join(OUTPUT_DIR, f"product_{ts}.{ext}")
        with open(path, "wb") as f:
            f.write(resp.content)
        print(f"Product image downloaded: {path}")
        return path
    raise RuntimeError(f"Image download failed: {resp.status_code}")

def generate_hook(detail, highlights):
    """สร้างหัวข้อสั้นพาดหัวรูปภาพ 2 บรรทัด คั่นด้วย '|'"""
    global API_ENABLED
    if API_ENABLED:
        prompt = (
            f"จากรายละเอียดสินค้าต่อไปนี้:\n{detail}\n\n"
            f"จุดเด่นสินค้าที่สกัดแล้ว:\n{highlights}\n\n"
            "กรุณาสร้างคำพาดหัวโฆษณารีวิวสินค้านี้ภาษาไทยสั้นๆ 2 บรรทัด คั่นด้วยเครื่องหมาย pipe '|' (บรรทัด 1 | บรรทัด 2)\n"
            "กฎในการร่าง:\n"
            "- บรรทัด 1: คำโปรย/ชื่อเล่นสุดปังสไตล์วัยรุ่นหรือคนทำงานขำขัน (3-5 คำ)\n"
            "- บรรทัด 2: เหตุผลโดนใจ/จุดเด่นในการแก้ปัญหา (4-7 คำ)\n"
            "- ห้ามใช้เครื่องหมายคำพูด อัญประกาศ หรือข้อความนำหน้า/ตามหลังใดๆ\n"
            "- ห้ามมี Emoji ปนในหัวข้อนี้เด็ดขาด\n"
            "ตัวอย่าง: เบาะรองนั่งสู้ชีวิต | นั่งทำงาน 10 ชม. ไม่ปวดหลัง"
        )
        for model in TEXT_MODELS:
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                result = resp.text.strip()
                label_pattern = r'^(ข้อความในโพสต์\s*Facebook|Facebook\s*Caption|Facebook\s*caption|Caption|caption|ข้อความบนรูป|ข้อความในรูป|ข้อความ|คำบรรยาย|คำอธิบาย|บรรทัดที่\s*\d+|บรรทัด\s*\d+|ประโยคที่\s*\d+|ประโยค\s*\d+|Hook\s*text|Hook|Line\s*\d+|[L|l]ine\s*\d+|\d+)\s*[:\-\.\s]\s*'
                result = re.sub(label_pattern, '', result, flags=re.IGNORECASE).strip()
                result = result.strip('"\'“”‘’')
                if "|" in result:
                    parts = result.split("|", 1)
                    line1 = parts[0].strip()
                    line2 = parts[1].strip()
                    return line1, line2
                else:
                    return result[:15], ""
            except Exception as e:
                print(f"[{model}] hook generation failed: {e}")
        
        print("[Warning] Hook generation failed on all models. Disabling API calls for this run.")
        API_ENABLED = False
        
    # Local fallback for hook
    title = re.sub(r'^[•\-\*\d\.\s\u2013\(\[\{\)\|\}]+', '', detail).strip()
    first_line = title.split('\n')[0].split('|')[0].split(' - ')[0].split(' – ')[0].strip()
    line1 = first_line[:15] if first_line else "สินค้าแนะนำ"
    line2 = "รายละเอียดเพิ่มเติม"
    return line1, line2

def generate_caption(detail, shopee, lazada, promo, highlights):
    global API_ENABLED
    promo_line = f"\n🔥 โปรโมชั่น: {promo}" if promo else ""
    lazada_line = f"\n🛍️ Lazada → {lazada}" if lazada and "xxx" not in lazada else ""
    caption = None
    if API_ENABLED:
        prompt = (
            f"เขียน Facebook post ภาษาไทยรีวิวสินค้าอย่างตรงไปตรงมาและน่าอ่าน สไตล์เพจรีวิวชื่อดัง (เช่น CatDumb)\n"
            f"เขียนด้วยบุคลิกแอดมินผู้ชาย (ใช้คำลงท้ายว่า 'ครับ' และแทนตัวว่า 'ผม' หรือ 'พี่' เท่านั้น)\n"
            f"รายละเอียดสินค้า:\n{detail}\n\n"
            f"จุดเด่นสินค้า:\n{highlights}\n\n"
            f"คุณต้องเขียนรีวิวโดยใช้เทคนิค 3 ขั้นตอนดังนี้:\n"
            f"1. เปิดให้น่าสนใจ (Hook): ประโยคเปิดหัวพาดหัวเรื่องให้น่าตื่นเต้น จี้ใจ ดึงดูดให้อยากอ่านต่อทันที\n"
            f"2. เล่าให้เห็นภาพ (Vivid Storytelling): รีวิวคุณสมบัติเด่น ประสิทธิภาพการใช้งานจริง หรือผลลัพธ์หลังจากใช้แล้วให้เห็นภาพชัดเจน\n"
            f"3. ปิดจบต้องบอกว่า 'ควรทำอะไร' (Call to Action): บอกให้สั่งซื้อโดยการกดที่ตะกร้า ชี้เป้าลิงก์ หรือบอกว่ามีโปรโมชั่นจัดหนักอยู่\n\n"
            f"เขียนให้น่าอ่าน สั้นกระชับ เป็นกันเอง ท้ายโพสต์ใส่แฮชแท็ก 2-3 อัน\n"
            f"ห้ามใช้ markdown ตัวหนา (**) และตอบเฉพาะตัวแคปชั่นรีวิวเท่านั้น"
        )
        for model in TEXT_MODELS:
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                caption = resp.text.strip()
                if caption:
                    break
            except Exception as e:
                print(f"[{model}] caption generation failed: {e}")
                
        if not caption:
            print("[Warning] Caption generation failed on all models. Disabling API calls for this run.")
            API_ENABLED = False
            
    if not caption:
        print("[Warning] Falling back to local heuristic caption.")
        first_few_lines = " ".join([l.strip() for l in detail.splitlines() if l.strip()][:3])
        caption = (
            f"สวัสดีครับทุกคน วันนี้ผมมีสินค้าดีๆ มาแนะนำครับ!\n\n"
            f"ตัวนี้คือ {first_few_lines} บอกเลยว่าตอบโจทย์ชีวิตประจำวันมากครับ ลองดูรายละเอียดและจุดเด่นด้านล่างได้เลยครับ\n\n"
            f"{highlights}\n\n"
            f"ใครที่กำลังมองหาอยู่หรืออยากสั่งซื้อไปลองใช้งาน สามารถกดสั่งได้ที่ลิงก์ตะกร้าด้านล่างนี้ได้เลยครับผม 👇"
        )
    else:
        lines = caption.splitlines()
        while lines and (
            re.search(r'^(ได้เลย|นี่คือ|แน่นอน|โพสต์รีวิว|ครับ|ค่ะ|---)', lines[0].strip(), re.IGNORECASE)
            or lines[0].strip() in ("", "---")
        ):
            lines.pop(0)
        caption = "\n".join(lines).strip()
        
    caption += f"{promo_line}\n\n👉 Shopee → {shopee}{lazada_line}"
    return caption

def post_to_page(img_path, caption):
    print("Posting to Facebook Page...")
    with open(img_path, "rb") as f:
        resp = requests.post(
            f"https://graph.facebook.com/v25.0/{PAGE_ID}/photos",
            data={"access_token": PAGE_ACCESS_TOKEN, "caption": caption, "published": "true"},
            files={"source": ("review.png", f, "image/png")},
            timeout=60
        )
    result = resp.json()
    if "id" in result:
        post_id = result.get("post_id") or result["id"]
        print(f"Page Posted! ID: {post_id}")
        print(f"https://www.facebook.com/{post_id}")
        return post_id
    else:
        print(f"FB Error: {result}")
        raise SystemExit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run without posting or marking as done")
    args = parser.parse_args()

    product, wb, ws = load_next_product()
    if not product:
        print("ไม่มีสินค้าที่ต้องโพส (ครบแล้วหรือยังไม่ได้เพิ่ม)")
        raise SystemExit(0)

    print(f"Product #{product['no']}: {product['detail'][:60]}...")

    promo_clean = clean_promo(product["promo"])
    highlights  = extract_highlights(product["detail"], promo_clean)
    print(f"Highlights:\n{highlights}\n")

    line1, line2 = generate_hook(product["detail"], highlights)
    line1 = segment_thai_text(line1, client)
    line2 = segment_thai_text(line2, client)
    print(f"Hook generated: {line1} | {line2}")

    product_img = download_image(product["image_url"])
    
    # PIL Overlay
    try:
        review_img = add_overlay(product_img, line1, line2, ACCENT_COLOR)
        os.unlink(product_img)
        print(f"Review image overlaid: {review_img}")
    except Exception as overlay_err:
        print(f"Overlay failed, using original image: {overlay_err}")
        review_img = product_img

    caption = generate_caption(
        product["detail"], product["shopee"],
        product["lazada"], promo_clean, highlights
    )
    print(f"Caption:\n{caption}\n")

    if args.dry_run:
        print(f"Dry run complete. Local image path: {review_img}")
    else:
        post_to_page(review_img, caption)
        if os.path.exists(review_img):
            os.unlink(review_img)
        mark_posted(wb, ws, product["row"])
