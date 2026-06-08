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
AFFILIATE_DIR     = os.path.join(os.path.dirname(__file__), "affiliate_data")
ACCENT_COLOR      = (255, 215, 0) # Gold สำหรับ Rocket21
API_ENABLED       = True

if not GOOGLE_API_KEY:
    try:
        from config import GOOGLE_API_KEY, PAGE_ACCESS_TOKEN
    except ImportError:
        pass

os.makedirs(OUTPUT_DIR, exist_ok=True)

client = None
if not GOOGLE_API_KEY or GOOGLE_API_KEY in ("DUMMY_KEY", "DUMMY"):
    print("[Warning] GOOGLE_API_KEY is not set or is a dummy key. Disabling API calls.")
    API_ENABLED = False
else:
    try:
        client = genai.Client(api_key=GOOGLE_API_KEY, http_options={'timeout': 60000.0})
    except Exception as e:
        print(f"[Warning] Failed to initialize genai.Client: {e}. Disabling API calls.")
        API_ENABLED = False

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
            if any(x in err_msg.lower() for x in ["api key", "invalid_argument", "api_key", "timeout", "timed out", "deadline exceeded", "connection", "connect", "unreachable"]):
                print("Persistent API key or network/timeout issue detected. Disabling API calls immediately.")
                API_ENABLED = False
                break
            
    if not API_ENABLED:
        print("[Warning] API calls disabled. Falling back to local_segment_thai.")
    else:
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

def get_allowed_xlsx_files():
    path = os.path.abspath(__file__).replace("\\", "/")
    if "chowchow" in path:
        return ["สัตว์เลี้ยง.xlsx"]
    elif "somtam" in path:
        return ["อาหารและเครื่องดื่ม.xlsx"]
    elif "rocket" in path:
        return ["เครื่องใช้ไฟฟ้าภายในบ้าน.xlsx"]
    elif "x-bot" in path:
        return ["สินค้าขายดี.xlsx"]
    else:  # kram-facebook-page
        return ["เครื่องใช้ในบ้าน.xlsx", "ค่าคอมพิเศษ.xlsx", "เสื้อผ้าแฟชั่นผู้หญิง.xlsx", "สินค้าสำหรับเม้นใต้คลิป.xlsx"]

def get_posted_urls(ws):
    urls = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        if len(row) < 4:
            continue
        shopee = row[2]
        lazada = row[3]
        if shopee and str(shopee).strip().startswith("http"):
            urls.add(str(shopee).strip())
        if lazada and str(lazada).strip().startswith("http"):
            urls.add(str(lazada).strip())
    return urls

def append_posted_fallback(wb, ws, product):
    bkk = timezone(timedelta(hours=7))
    ts = datetime.now(bkk).strftime("%Y-%m-%d %H:%M")
    row_num = ws.max_row + 1
    
    ws.cell(row=row_num, column=1, value=product["no"])
    ws.cell(row=row_num, column=2, value=product["detail"])
    ws.cell(row=row_num, column=3, value=product["shopee"])
    ws.cell(row=row_num, column=4, value=product["lazada"])
    ws.cell(row=row_num, column=5, value=product["image_url"])
    ws.cell(row=row_num, column=6, value=product["promo"])
    ws.cell(row=row_num, column=7, value=f"done {ts}")
    
    wb.save(EXCEL_PATH)
    print(f"Appended fallback product to review_products.xlsx at row {row_num}")

def load_affiliate_product(posted_urls):
    """Fallback: สุ่มสินค้าจาก AFFILIATE_DIR เมื่อ review_products.xlsx หมด"""
    import glob
    allowed_names = get_allowed_xlsx_files()
    xlsx_files = []
    for name in allowed_names:
        p = os.path.join(AFFILIATE_DIR, name)
        if os.path.exists(p):
            xlsx_files.append(p)
            
    # Fallback to any xlsx files if no mapped files exist
    if not xlsx_files:
        xlsx_files = glob.glob(os.path.join(AFFILIATE_DIR, "*.xlsx"))
        
    if not xlsx_files:
        print(f"[affiliate] No xlsx files found in {AFFILIATE_DIR}")
        return None
        
    random.shuffle(xlsx_files)
    for xlsx_path in xlsx_files:
        try:
            wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
            ws = wb.active
            candidates = []
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or len(row) < 10:
                    continue
                name   = row[1]
                imgurl = row[2]
                price  = row[3]
                shopee = row[9]
                lazada = row[10] if len(row) > 10 else None
                if not shopee or not name:
                    continue
                
                shopee_val = str(shopee).strip()
                lazada_val = str(lazada).strip() if lazada else ""
                
                # Check against posted URLs
                if shopee_val in posted_urls or (lazada_val and lazada_val in posted_urls):
                    continue
                    
                candidates.append({
                    "no": row[0],
                    "detail": f"{name} ราคา {price} บาท",
                    "shopee": shopee_val,
                    "lazada": lazada_val,
                    "image_url": str(imgurl).strip() if imgurl else "",
                    "promo": "",
                    "row": None,
                })
            wb.close()
            if candidates:
                product = random.choice(candidates)
                print(f"[affiliate] Loaded from {os.path.basename(xlsx_path)}: {product['detail'][:60]}")
                return product
        except Exception as e:
            print(f"[affiliate] Failed to read {xlsx_path}: {e}")
    print("[affiliate] No valid product found in any xlsx file")
    return None


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
    if API_ENABLED and client:
        prompt = (
            f"จากรายละเอียดสินค้านี้:\n{detail}\n\n"
            f"สกัดจุดเด่นสินค้าเป็นประโยคข้อความสั้นแนวธรรมชาติ 1-2 ย่อหน้าสั้นๆ (ห้ามทำเป็นข้อๆ หรือมีสัญลักษณ์รายการ/bullet points เช่น •, ▪️, - หรือเลขข้อ) "
            f"เน้นประโยชน์ที่คนซื้อสนใจและใช้งานจริง ห้ามใส่ข้อมูลราคาหรือโปรโมชั่น "
            f"ตอบเฉพาะส่วนรายละเอียดเนื้อความเท่านั้น"
        )
        for model in TEXT_MODELS:
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                highlights = resp.text.strip()
                if highlights:
                    break
            except Exception as e:
                err_msg = str(e)
                print(f"[{model}] highlights failed: {err_msg[:80]}")
                if any(x in err_msg.lower() for x in ["api key not valid", "permission_denied", "api_key_invalid"]):
                    print("Persistent API key or network/timeout issue detected. Disabling API calls immediately.")
                    API_ENABLED = False
                    break

        if not highlights and API_ENABLED:
            print("[Warning] Highlights generation failed on all models, using local fallback.")
            
    if not highlights:
        print("[Warning] Falling back to local heuristic extraction.")
        lines = [l.strip() for l in detail.splitlines() if l.strip()]
        thai_lines = [l for l in lines if contains_thai(l)]
        if not thai_lines:
            thai_lines = lines
        
        points = []
        for line in thai_lines:
            cleaned = re.sub(r'^[•\-\*\d\.\s\u2013]+', '', line).strip()
            if cleaned and len(cleaned) > 5 and len(cleaned) < 100:
                points.append(cleaned)
            if len(points) >= 3:
                break
        if not points:
            points = [line[:80] for line in thai_lines[:2]]
        highlights = " ".join(points) if points else "รายละเอียดเพิ่มเติมศึกษาต่อได้ที่หน้าร้านเลยครับ"

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
    if API_ENABLED and client:
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
                else:
                    line1, line2 = result[:15], ""
                line1 = line1.strip("()[]{}| -–•*")
                line2 = line2.strip("()[]{}| -–•*")
                return line1, line2
            except Exception as e:
                err_msg = str(e)
                print(f"[{model}] hook generation failed: {err_msg[:80]}")
                if any(x in err_msg.lower() for x in ["api key", "invalid_argument", "api_key", "timeout", "timed out", "deadline exceeded", "connection", "connect", "unreachable"]):
                    print("Persistent API key or network/timeout issue detected. Disabling API calls immediately.")
                    API_ENABLED = False
                    break
        
        if API_ENABLED:
            print("[Warning] Hook generation failed on all models. Disabling API calls for this run.")
            API_ENABLED = False
        
    # Local fallback for hook
    title = re.sub(r'^[•\-\*\d\.\s\u2013\(\[\{\)\|\}]+', '', detail).strip()
    first_line = title.split('\n')[0].split('|')[0].split(' - ')[0].split(' – ')[0].strip()
    line1 = first_line[:15] if first_line else "สินค้าแนะนำ"
    # Smart local fallback for hook
    first_line = detail.split('\n')[0].strip()
    first_line = re.sub(r'^[•\-\*\d\.\s–]+', '', first_line).strip()
    _specs = ['ราคา', 'แพ็ค', 'ขนาด', 'สำหรับ', 'จำนวน', 'กรัม', 'ลิตร', ' ml', ' kg', ' g ', '(']
    _stop = len(first_line)
    for _kw in _specs:
        _idx = first_line.find(_kw)
        if _idx > 2:
            _stop = min(_stop, _idx)
    short_title = first_line[:_stop].strip()
    words = short_title.split()
    line1 = " ".join(words[:3]) if words else "สินค้าแนะนำ"
    price_m = re.search(r'ราคา\s*([\d,]+(?:\.\d+)?)\s*บาท', detail)
    if price_m:
        line2 = f"แค่ {price_m.group(1)} บาท คุ้มมาก"
    else:
        feat_lines = [l.strip() for l in detail.splitlines() if l.strip() and l.strip() != first_line.strip()]
        feat_lines = [re.sub(r'^[•\-\*\d\.\s–]+', '', l).strip() for l in feat_lines]
        feat_lines = [l for l in feat_lines if 5 < len(l) < 60]
        line2 = feat_lines[0][:20] if feat_lines else "คุ้มค่าน่าใช้"
    return line1, line2

def generate_caption(detail, shopee, lazada, promo, highlights):
    global API_ENABLED
    promo_line = f"\n🔥 โปรโมชั่น: {promo}" if promo else ""
    lazada_line = f"\n🛍️ Lazada → {lazada}" if lazada and "xxx" not in lazada else ""
    caption = None
    if API_ENABLED and client:
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
            f"ห้ามใช้ markdown ตัวหนา (**) และห้ามมีสัญลักษณ์หัวข้อย่อยหรือ bullet points (เช่น •, ▪️, -) เด็ดขาด เขียนอธิบายไหลลื่นเป็นย่อหน้าธรรมชาติเท่านั้น ตอบเฉพาะตัวแคปชั่นรีวิวเท่านั้น"
        )
        for model in TEXT_MODELS:
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                caption = resp.text.strip()
                if caption:
                    break
            except Exception as e:
                err_msg = str(e)
                print(f"[{model}] caption generation failed: {err_msg[:80]}")
                if any(x in err_msg.lower() for x in ["api key", "invalid_argument", "api_key", "timeout", "timed out", "deadline exceeded", "connection", "connect", "unreachable"]):
                    print("Persistent API key or network/timeout issue detected. Disabling API calls immediately.")
                    API_ENABLED = False
                    break
                
        if not caption and API_ENABLED:
            print("[Warning] Caption generation failed on all models. Disabling API calls for this run.")
            API_ENABLED = False
            
    if not caption:
        print("[Warning] Falling back to local heuristic caption.")
        import hashlib as _hs
        _seed = int(_hs.md5(detail.encode()).hexdigest()[:8], 16)
        _openers = [
            "เพิ่งลองใช้มาแล้ว บอกเลยว่าโอเคมาก",
            "ใครกำลังหาของแบบนี้อยู่ มาดูกัน",
            "ของดีราคาเข้าถึงได้ แนะนำจริงๆ",
            "ไม่ได้รับเงินมาพูด แต่อยากบอกว่าดี",
            "ลองแล้วถูกใจ เลยมาแชร์ให้เพื่อนๆ"
        ]
        _opener = _openers[_seed % len(_openers)]
        first_few_lines = " ".join([l.strip() for l in detail.splitlines() if l.strip()][:2])
        caption = (
            f"{_opener}\n\n"
            f"{first_few_lines}\n\n"
            f"{highlights}\n\n"
            f"ลิ้งซื้อในคอมเมนต์แรกเลยครับ 👇"
        )
    else:
        lines = caption.splitlines()
        while lines and (
            re.search(r'^(ได้เลย|นี่คือ|แน่นอน|โพสต์รีวิว|ครับ|ค่ะ|---)', lines[0].strip(), re.IGNORECASE)
            or lines[0].strip() in ("", "---")
        ):
            lines.pop(0)
        caption = "\n".join(lines).strip()
        
    if promo:
        caption += promo_line
    return caption

def _post_one_comment(post_id, text):
    try:
        resp = requests.post(
            f"https://graph.facebook.com/v21.0/{post_id}/comments",
            data={"access_token": PAGE_ACCESS_TOKEN, "message": text},
            timeout=30
        )
        result = resp.json()
        if "id" in result:
            print(f"Comment posted: {result['id']}")
        else:
            print(f"Comment failed: {result}")
    except Exception as e:
        print(f"Comment error: {e}")

def post_link_comment(post_id, shopee, lazada, promo):
    """โพส comment ลิ้งใต้โพส แยก Shopee / Lazada คนละคอมเม้น"""
    promo_line = f"\n🔥 โปร: {promo}" if promo else ""
    if shopee and "xxx" not in shopee:
        _post_one_comment(post_id, f"👉 ซื้อได้ที่ Shopee → {shopee}{promo_line}")
    if lazada and "xxx" not in lazada:
        _post_one_comment(post_id, f"🛍️ หรือสั่งทาง Lazada → {lazada}")

def post_to_page(img_path, caption, shopee=None, lazada=None, promo=None, scheduled_timestamp=None):
    print("Posting to Facebook Page...")
    from affiliate_utils import get_next_scheduled_time

    if scheduled_timestamp is not None:
        scheduled_time = scheduled_timestamp
    else:
        slots = ["08:00"]
        scheduled_time = get_next_scheduled_time(slots)
    
    if scheduled_time:
        comment_texts = []
        promo_line = f"\n🔥 โปร: {promo}" if promo else ""
        if shopee and "xxx" not in shopee:
            comment_texts.append(f"👉 ซื้อได้ที่ Shopee → {shopee}{promo_line}")
        if lazada and "xxx" not in lazada:
            comment_texts.append(f"🛍️ หรือสั่งทาง Lazada → {lazada}")
            
        if comment_texts:
            caption += "\n\n📌 ชี้เป้าของดีน่าสนใจ:\n" + "\n".join(comment_texts)
            
        print(f"Scheduling to Facebook for timestamp {scheduled_time}...")
        with open(img_path, "rb") as f:
            resp = requests.post(
                f"https://graph.facebook.com/v25.0/{PAGE_ID}/photos",
                data={
                    "access_token": PAGE_ACCESS_TOKEN,
                    "message": caption,
                    "published": "false",
                    "unpublished_content_type": "SCHEDULED",
                    "scheduled_publish_time": scheduled_time
                },
                files={"source": ("review.png", f, "image/png")},
                timeout=60
            )
        result = resp.json()
        if "id" in result:
            photo_id = result.get("post_id") or result["id"]
            print(f"Scheduled successfully! Photo ID: {photo_id}")
            return photo_id, True
        else:
            print(f"FB Error: {result}")
            raise SystemExit(1)

    with open(img_path, "rb") as f:
        resp = requests.post(
            f"https://graph.facebook.com/v25.0/{PAGE_ID}/photos",
            data={"access_token": PAGE_ACCESS_TOKEN, "message": caption, "published": "true"},
            files={"source": ("review.png", f, "image/png")},
            timeout=60
        )
    result = resp.json()
    if "id" in result:
        post_id = result.get("post_id") or result["id"]
        print(f"Page Posted! ID: {post_id}")
        print(f"https://www.facebook.com/{post_id}")
        return post_id, False
    else:
        print(f"FB Error: {result}")
        raise SystemExit(1)

def upload_image_to_imgbb(img_path):
    IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")
    if not IMGBB_API_KEY:
        try:
            from config import IMGBB_API_KEY
        except ImportError:
            pass
    if not IMGBB_API_KEY:
        print("[Threads] IMGBB_API_KEY not found. Skipping Threads post.")
        return None
    try:
        with open(img_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")
        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": IMGBB_API_KEY, "image": img_data},
            timeout=60
        )
        res = resp.json()
        if res.get("success"):
            url = res["data"]["url"]
            print(f"[Threads] Image uploaded to ImgBB: {url}")
            return url
        else:
            print(f"[Threads] ImgBB upload failed: {res}")
    except Exception as e:
        print(f"[Threads] Exception during ImgBB upload: {e}")
    return None

def post_to_threads(image_url, caption, shopee, lazada, promo):
    THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
    THREADS_USER_ID      = os.environ.get("THREADS_USER_ID",      "")
    if not THREADS_ACCESS_TOKEN or not THREADS_USER_ID:
        try:
            from config import THREADS_ACCESS_TOKEN, THREADS_USER_ID
        except ImportError:
            pass
    if not THREADS_ACCESS_TOKEN or not THREADS_USER_ID:
        print("[Threads] THREADS_ACCESS_TOKEN or THREADS_USER_ID not configured.")
        return

    print("[Threads] Creating Threads media container...")
    try:
        resp = requests.post(
            f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads",
            data={
                "media_type": "IMAGE",
                "image_url": image_url,
                "text": caption,
                "access_token": THREADS_ACCESS_TOKEN,
            },
            timeout=60
        )
        result = resp.json()
        if "id" not in result:
            print(f"[Threads] Error creating media container: {result}")
            return
        container_id = result["id"]
        print(f"[Threads] Media container created: {container_id}")
        time.sleep(5)

        print("[Threads] Publishing Threads post...")
        resp2 = requests.post(
            f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish",
            data={"creation_id": container_id, "access_token": THREADS_ACCESS_TOKEN},
            timeout=60
        )
        result2 = resp2.json()
        if "id" not in result2:
            print(f"[Threads] Error publishing post: {result2}")
            return
        post_id = result2["id"]
        print(f"[Threads] Published successfully! Post ID: {post_id}")
        
        # Post the links as a reply comment
        comments = []
        promo_line = f" 🔥 โปร: {promo}" if promo else ""
        if shopee and "xxx" not in shopee:
            comments.append(f"👉 ซื้อได้ที่ Shopee → {shopee}{promo_line}")
        if lazada and "xxx" not in lazada:
            comments.append(f"🛍️ หรือสั่งทาง Lazada → {lazada}")
            
        for idx, comment_text in enumerate(comments, 1):
            time.sleep(5)
            print(f"[Threads] Posting reply comment {idx}...")
            resp_c = requests.post(
                f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads",
                data={
                    "media_type": "TEXT",
                    "text": comment_text,
                    "reply_to_id": post_id,
                    "access_token": THREADS_ACCESS_TOKEN,
                },
                timeout=60
            )
            c_container_id = resp_c.json().get("id")
            if c_container_id:
                time.sleep(3)
                requests.post(
                    f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish",
                    data={"creation_id": c_container_id, "access_token": THREADS_ACCESS_TOKEN},
                    timeout=60
                )
                print(f"[Threads] Reply comment {idx} published.")
    except Exception as e:
        print(f"[Threads] Exception during Threads post: {e}")


def extract_badge_text(promo):
    if not promo:
        return None
    pct_match = re.search(r'(ลด\s*\d+\s*%)|(\d+\s*%\s*OFF)', promo, re.IGNORECASE)
    if pct_match:
        val = pct_match.group(0)
        val = re.sub(r'\s+', ' ', val)
        return val
    price_match = re.search(r'฿\s*\d+', promo)
    if price_match:
        return price_match.group(0).replace(" ", "")
    return None


if __name__ == "__main__":
    import argparse
    import time as _time

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run without posting or marking as done")
    args = parser.parse_args()

    bkk = timezone(timedelta(hours=7))
    now_bkk = datetime.now(bkk)

    # Pre-calculate 5 timestamps: 05:00/08:00/11:00/14:00/17:00 BKK
    slot_times = ["05:00", "08:00", "11:00", "14:00", "17:00"]
    def make_slot_ts(slot_str):
        h, m = map(int, slot_str.split(":"))
        dt = now_bkk.replace(hour=h, minute=m, second=0, microsecond=0)
        if dt <= now_bkk:
            dt += timedelta(days=1)
        return int(dt.timestamp())

    slot_timestamps = [make_slot_ts(s) for s in slot_times]
    posted_this_run = set()

    for i, sched_ts in enumerate(slot_timestamps):
        print(f"\n--- Post {i+1}/5 (slot {slot_times[i]}) ---")
        API_ENABLED = True

        product, wb, ws = load_next_product()
        affiliate_mode = False
        if not product:
            print("review_products.xlsx หมดแล้ว — ลอง fallback จาก AFFILIATE_DIR")
            posted_urls = get_posted_urls(ws)
            product = load_affiliate_product(posted_urls)
            affiliate_mode = True
            if not product:
                print("ไม่มีสินค้าเหลือ หยุด")
                break

        if product.get("shopee") in posted_this_run:
            print(f"[Skip] ซ้ำใน run นี้: {str(product.get('shopee',''))[:60]}")
            continue

        print(f"Product: {product['detail'][:60]}...")

        promo_clean = clean_promo(product["promo"])
        highlights  = extract_highlights(product["detail"], promo_clean)

        line1, line2 = generate_hook(product["detail"], highlights)
        line1 = segment_thai_text(line1, client)
        line2 = segment_thai_text(line2, client)
        print(f"Hook: {line1} | {line2}")

        try:
            product_img = download_image(product["image_url"])
        except Exception as img_err:
            print(f"[Warning] Failed to download product image: {img_err}. Using solid background fallback.")
            product_img = None

        try:
            badge_text = extract_badge_text(product.get("promo"))
            review_img = add_overlay(
                product_img, line1, line2, ACCENT_COLOR,
                font_name="Itim-Regular.ttf",
                badge_text=badge_text,
                watermark="Rocket 21"
            )
            if product_img and os.path.exists(product_img):
                os.unlink(product_img)
            print(f"Review image overlaid: {review_img}")
        except Exception as overlay_err:
            print(f"Overlay failed: {overlay_err}")
            review_img = product_img

        caption = generate_caption(
            product["detail"], product["shopee"],
            product["lazada"], promo_clean, highlights
        )
        print(f"Caption:\n{caption}\n")

        if args.dry_run:
            print(f"Dry run post {i+1}. image={review_img}")
            print(f"Link: 👉 Shopee → {product['shopee']}")
            posted_this_run.add(product.get("shopee"))
        else:
            post_id, was_scheduled = post_to_page(
                review_img, caption,
                product["shopee"], product["lazada"], promo_clean,
                scheduled_timestamp=sched_ts
            )
            posted_this_run.add(product.get("shopee"))

            # ─── Post to Threads if credentials are present ─────────────────
            try:
                threads_token = os.environ.get("THREADS_ACCESS_TOKEN", "")
                if not threads_token:
                    try:
                        from config import THREADS_ACCESS_TOKEN as threads_token
                    except ImportError:
                        pass
                if threads_token:
                    print("[Threads] Preparing to post to Threads...")
                    img_url = upload_image_to_imgbb(review_img)
                    if img_url:
                        post_to_threads(img_url, caption, product["shopee"], product["lazada"], promo_clean)
            except Exception as th_err:
                print(f"[Warning] Failed to post to Threads: {th_err}")
            # ────────────────────────────────────────────────────────────────

            if os.path.exists(review_img):
                os.unlink(review_img)
            if not was_scheduled:
                post_link_comment(post_id, product["shopee"], product["lazada"], promo_clean)
            if not affiliate_mode:
                mark_posted(wb, ws, product["row"])
            else:
                append_posted_fallback(wb, ws, product)
            _time.sleep(5)

