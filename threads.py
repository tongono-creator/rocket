# -*- coding: utf-8 -*-
"""threads.py — โพสรูปคำคม + caption ลง Threads อัตโนมัติ"""

import sys, io, os, re, base64, requests, time, random, tempfile
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai
from google.genai import types
from overlay_utils import add_overlay

GOOGLE_API_KEY       = os.environ.get("GOOGLE_API_KEY",       "")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID      = os.environ.get("THREADS_USER_ID",      "")
IMAGE_MODEL          = "gemini-2.0-flash-preview-image-generation"  # unused (PIL renders)
TEXT_MODELS          = ["gemini-2.5-flash", "gemini-2.5-pro"]
OUTPUT_DIR           = "output"

API_ENABLED = True

if not GOOGLE_API_KEY:
    try:
        from config import GOOGLE_API_KEY, THREADS_ACCESS_TOKEN, THREADS_USER_ID
    except ImportError:
        pass

os.makedirs(OUTPUT_DIR, exist_ok=True)
client = genai.Client(api_key=GOOGLE_API_KEY, http_options={'timeout': 60000.0})

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


# ─── Topics (เหมือน post.py) ─────────────────────────────────────
# เช้า: การเงินและวินัยการสร้างตัว (Financial Mindset & Social Realities)
MORNING_TOPICS = [
    "มีเงินเก็บ 1 แสนแรก ควรซื้อทองเก็บไว้ หรือซื้อกองทุนรวมดัชนีดี?",
    "ประกันชีวิตกับประกันสุขภาพจำเป็นจริงๆ ไหมสำหรับคนอายุ 30 ที่แข็งแรงดี?",
    "ค่านิยมผ่อนของ 0% 10 เดือน คือตัวช่วยแบ่งเบาภาระ หรือคือหลุมพรางสร้างหนี้?",
    "การซื้อบ้านเพื่ออยู่อาศัยเอง ถือเป็นการลงทุนที่ดี หรือเป็นภาระค่าใช้จ่ายระยะยาวกันแน่?",
    "คิดยังไงกับคำกล่าวที่ว่า 'ออมเงินในบัญชีออมทรัพย์ธรรมดา เท่ากับปล่อยให้เงินด้อยค่าลงทุกวัน'?",
    "อายุ 35 แล้วยังไม่มีทรัพย์สินชิ้นใหญ่เป็นของตัวเอง (บ้าน/รถ) ถือว่าล้มเหลวในสังคมไทยไหม?",
    "ผ่อนของใช้ฟุ่มเฟือยเพื่อสร้างความสุขเล็กๆ น้อยๆ ในชีวิตประจำวัน ถือว่าคุ้มค่าทางจิตใจไหม?",
    "ระหว่างการลงทุนในตัวเองเพื่อเพิ่มรายได้ VS การประหยัดเงินสุดขีดเพื่อเพิ่มเงินเก็บ ทางไหนรวยเร็วกว่า?",
    "คิดยังไงกับการให้เงินพ่อแม่ตามหน้าที่กตัญญู จนตัวเองไม่มีเงินเก็บเลย?",
    "การทำบัตรเครดิตใบแรกคือจุดเริ่มต้นของวินัยทางการเงิน หรือจุดเริ่มต้นของหนี้สินพอกพูน?",
]
# กลางวัน: กระทู้พันทิปจำลอง (Financial Dilemma)
NOON_TOPICS = [
    "อายุ 35 เงินเดือน 40,000 แต่ไม่มีเงินเก็บเลย แปลกและล้มเหลวไหม?",
    "เงินเดือน 30k เช่าคอนโด 10k ถือว่าใช้ชีวิตเกินตัวไปหรือเปล่า?",
    "แฟนเงินเดือนน้อยกว่า 3 เท่า แต่หนี้เยอะกว่า 5 เท่า ควรคบต่อหรือพอแค่นี้?",
    "มีเงินเก็บ 1 ล้านแรก ควรเอาไปโปะบ้านก่อน หรือเอาไปลงทุนหุ้นดี?",
    "ทำงานงกๆ เก็บเงินได้ 5 แสน แต่พ่อแม่ขอเอาไปให้ญาติกู้ ควรให้ไหม?",
    "อายุ 30 มีหนี้บัตรเครดิต 2 แสน แต่ยังอยากผ่อนรถป้ายแดงเพื่อสร้าง profile?",
    "ถ้ามีเงิน 10 ล้าน ตอนนี้ ควรลาออกมานอนเล่นเฉยๆ หรือทนทำงานต่อดี?",
    "อยากลาออกจากงานประจำมาทำธุรกิจส่วนตัว แต่มีภาระผ่อนบ้านเดือนละ 20k ทำไงดี?",
    "เพื่อนสนิทยืมเงิน 50,000 ไปแต่งงาน ผ่านมา 2 ปีไม่คืน แต่โพสต์ไปเที่ยวต่างประเทศ",
    "รายได้ 50k ให้พ่อแม่เดือนละ 15k แต่โดนบอกว่ากตัญญูน้อยไปเมื่อเทียบกับลูกป้า",
    "แฟนขอให้ช่วยกู้ร่วมซื้อบ้านราคา 5 ล้าน แต่ยังไม่ได้แต่งงานกัน ควรปฏิเสธยังไงดี?",
    "แต่งงานมา 3 ปี เพิ่งรู้ว่าสามีมีหนี้ซ่อนอยู่ 1.5 ล้านบาท ควรแยกทางหรือช่วยกันใช้หนี้?",
    "อายุ 28 ปี เงินเดือน 25k แต่แม่กดดันให้จัดงานแต่งงานงบ 3 แสนบาทเพื่อเอาหน้าตา ควรทำอย่างไร?",
    "เพื่อนที่เคยสนิททักมาขอยืมเงิน 10,000 ไปจ่ายค่างวดรถ ถ้าไม่ให้จะเสียเพื่อนไหม?",
    "เงินเดือน 80k ให้แฟนเก็บหมด แต่แฟนเอาไปผ่อนของแบรนด์เนมให้ตัวเองจนเงินเก็บเป็นศูนย์",
    "พ่อแม่เกษียณแล้วไม่มีเงินเก็บเลย และหวังให้เราผ่อนบ้านให้เดือนละ 15k ทั้งที่เราเพิ่งเริ่มทำงาน",
    "ทำงานบริษัทชั้นนำได้เงินเดือน 60k แต่เครียดมากจนนอนไม่หลับ VS ลาออกไปทำตำแหน่งธรรมดาได้ 30k สุขภาพจิตดีกว่า?",
    "ให้ญาติสนิทยืมทอง 5 บาทไปหมั้นสาว ผ่านมา 3 ปีญาติบอกว่าขายไปแล้วจะทยอยคืนเงิน แต่เงียบหาย",
    "เงินเดือน 35,000 ท่องเที่ยวต่างประเทศปีละ 2 ครั้ง ไม่มีเงินเก็บเลย โดนที่บ้านต่อว่าว่าประมาทกับชีวิต",
    "น้องสาวจะแต่งงาน ขอร้องให้เราช่วยออกค่าสินสอดทองหมั้น 1 แสนบาทถ้วน ทั้งที่เรากำลังจะซื้อบ้าน",
]
# เย็น-ค่ำ: สมการเปรียบเทียบ (Financial Battle)
EVENING_TOPICS = [
    "ผ่อนรถ 12,000/เดือน VS นั่ง BTS+Taxi อะไรเหนื่อยน้อยและคุ้มเงินกว่า?",
    "ซื้อบ้านชานเมือง 3 ล้าน VS เช่าคอนโดติดรถไฟฟ้า 15,000/เดือน เลือกแบบไหน?",
    "แต่งงานจัดงานหรูหราหมดไป 5 แสน VS จดทะเบียนสมรสแล้วเอาเงินไปเที่ยวรอบโลก?",
    "ส่งลูกเรียนอินเตอร์เทอมละแสน VS ส่งเรียนรัฐบาลแล้วเก็บเงินไว้ให้ลูกตอนโต?",
    "ผ่อน iPhone รุ่นล่าสุดเดือนละ 3,000 VS เอาเงินไปออมทอง/ออมหุ้นทุกเดือน?",
    "ซื้อบ้านมือสองมารีโนเวทเอง VS ซื้อบ้านมือหนึ่งในโครงการหรูหราไปเลย?",
    "กินกาแฟแก้วละ 150 ทุกวันเพื่อความสุข VS ชงกาแฟซองละ 5 บาทประหยัดเงิน?",
    "ฝากเงินในสหกรณ์ดอกเบี้ย 4% VS ซื้อกองทุนปันผลที่มีโอกาสขาดทุน?",
    "ลงทุนในหุ้นปันผลกินยาวๆ VS ลงทุนคอนโดปล่อยเช่าเพื่อมี Passive Income?",
    "ทำโอทีวันเสาร์ได้เงินเพิ่ม 1,500 VS นอนอยู่บ้านพักผ่อนชาร์จแบตชีวิต?",
]
# ดึก: แบกรับภาระ/ชีวิตจริง (Adulting Struggles / Life Truths)
LATE_TOPICS = [
    "คนวัย 35 ที่ตื่นมาพร้อมความรู้สึกว่า 'เรากำลังใช้ชีวิตเพื่อใครอยู่กันแน่'",
    "เหนื่อยแค่ไหนก็ล้มไม่ได้ เพราะข้างหลังมีพ่อแม่และลูกที่รอคอยเราอยู่",
    "ไม่มีอะไรน่ากลัวไปกว่าการเจ็บป่วยตอนอายุ 40 แล้วไม่มีประกันสุขภาพ",
    "การเติบโตเป็นผู้ใหญ่ทำให้รู้ว่า เพื่อนแท้เหลือไม่ถึง 3 คนก็หรูแล้ว",
    "เงินซื้อความสุขไม่ได้ แต่ช่วยให้เราไปนั่งร้องไห้บนรถหรูๆ แทนที่จะเป็นเบาะรถเมล์",
    "อิสระที่แท้จริงไม่ใช่การมีเงินร้อยล้าน แต่คือการปฏิเสธงานที่ไม่อยากทำได้",
    "เวลาผ่านไปเร็วเกินไป ทำงานตั้งแต่เช้าจรดค่ำ หันมาอีกทีอายุจะ 40 แล้ว",
    "ขอบคุณตัวเองที่พยุงชีวิตผ่านความกดดันในแต่ละวันมาได้จนถึงค่ำคืนนี้",
    "สิ่งที่น่ากลัวที่สุดในวัยทำงานคือ สุขภาพพังก่อนจะได้ใช้เงินที่หามาได้",
    "ในวันที่เหนื่อยล้าที่สุด สิ่งที่อยากได้ไม่ใช่เงินล้าน แต่คือความสงบเงียบๆ สักชั่วโมง",
]

SLOT_INFO = {
    "morning": {
        "desc": "การเงินและวินัยการสร้างตัว หรือความก้าวหน้าและการทำมาหากินในชีวิตคนทำงานวัยสร้างตัว 30+",
        "examples": [
            "มีเงินเก็บ 1 แสนแรก ควรซื้อทองเก็บไว้ หรือซื้อกองทุนรวมดัชนีดี?",
            "ประกันชีวิตกับประกันสุขภาพจำเป็นจริงๆ ไหมสำหรับคนอายุ 30 ที่แข็งแรงดี?",
            "ระหว่างการลงทุนในตัวเองเพื่อเพิ่มรายได้ VS การประหยัดเงินสุดขีดเพื่อเพิ่มเงินเก็บ ทางไหนรวยเร็วกว่า?",
            "คิดยังไงกับการให้เงินพ่อแม่ตามหน้าที่กตัญญู จนตัวเองไม่มีเงินเก็บเลย?"
        ]
    },
    "noon": {
        "desc": "ดราม่า/ทางเลือกยากๆ ในชีวิตการเงิน ครอบครัว หรือความสัมพันธ์ในวัยทำงาน (แนวๆ กระทู้ดราม่าการเงิน/ความรักพันทิป)",
        "examples": [
            "อายุ 35 เงินเดือน 40,000 แต่ไม่มีเงินเก็บเลย แปลกและล้มเหลวไหม?",
            "แฟนเงินเดือนน้อยกว่า 3 เท่า แต่หนี้เยอะกว่า 5 เท่า ควรคบต่อหรือพอแค่นี้?",
            "ทำงานงกๆ เก็บเงินได้ 5 แสน แต่พ่อแม่ขอเอาไปให้ญาติกู้ ควรให้ไหม?",
            "อายุ 28 ปี เงินเดือน 25k แต่แม่กดดันให้จัดงานแต่งงานงบ 3 แสนบาทเพื่อเอาหน้าตา ควรทำอย่างไร?"
        ]
    },
    "evening": {
        "desc": "ศึกเลือกทีม/เปรียบเทียบการเงินและการใช้ชีวิต (Financial Battle) ชวนคุยแบบเปรียบเทียบสองฝั่งชัดเจน",
        "examples": [
            "ผ่อนรถ 12,000/เดือน VS นั่ง BTS+Taxi อะไรเหนื่อยน้อยและคุ้มเงินกว่า?",
            "ซื้อบ้านชานเมือง 3 ล้าน VS เช่าคอนโดติดรถไฟฟ้า 15,000/เดือน เลือกแบบไหน?",
            "แต่งงานจัดงานหรูหราหมดไป 5 แสน VS จดทะเบียนสมรสแล้วเอาเงินไปเที่ยวรอบโลก?",
            "ผ่อน iPhone รุ่นล่าสุดเดือนละ 3,000 VS เอาเงินไปออมทอง/ออมหุ้นทุกเดือน?"
        ]
    },
    "late": {
        "desc": "การแบกรับภาระ หนี้สิน สุขภาพพัง หรือความจริงอันเจ็บปวดตลกร้ายในวัย 30+ (Adulting Struggles / Life Truths)",
        "examples": [
            "คนวัย 35 ที่ตื่นมาพร้อมความรู้สึกว่า 'เรากำลังใช้ชีวิตเพื่อใครอยู่กันแน่'",
            "ไม่มีอะไรน่ากลัวไปกว่าการเจ็บป่วยตอนอายุ 40 แล้วไม่มีประกันสุขภาพ",
            "การเติบโตเป็นผู้ใหญ่ทำให้รู้ว่า เพื่อนแท้เหลือไม่ถึง 3 คนก็หรูแล้ว",
            "เงินซื้อความสุขไม่ได้ แต่ช่วยให้เราไปนั่งร้องไห้บนรถหรูๆ แทนที่จะเป็นเบาะรถเมล์"
        ]
    }
}

def fetch_reddit_discussion_titles():
    """ดึงหัวข้อกระทู้ที่กำลังเป็นที่นิยมจาก Subreddits เพื่อนำมาใช้เป็นไอเดียตั้งต้น"""
    subreddits = ["personalfinance", "antiwork", "relationship_advice", "AskReddit", "jobs", "confession"]
    # สุ่มเลือกมา 2 ห้องเพื่อไม่ให้ใช้เวลาดึงข้อมูลนานเกินไป
    selected = random.sample(subreddits, 2)
    titles = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"}
    
    for sub in selected:
        url = f"https://www.reddit.com/r/{sub}/hot.rss"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                entries = root.findall("atom:entry", ns)
                count = 0
                for entry in entries:
                    title = entry.findtext("atom:title", "", ns)
                    if title:
                        title_clean = re.sub(r'^\[.*?\]\s*', '', title).strip()
                        if title_clean and title_clean not in titles:
                            titles.append(f"r/{sub}: {title_clean}")
                            count += 1
                            if count >= 5:
                                break
        except Exception as e:
            print(f"Error fetching Reddit titles from r/{sub}: {e}")
    return titles

def generate_dynamic_topic(slot, history_list):
    """สร้างหัวข้อประเด็นใหม่ล่าสุดแบบ dynamic โดยไม่ให้ซ้ำกับประวัติการโพสท์ที่ผ่านมา"""
    global API_ENABLED
    if not API_ENABLED:
        return None
    
    info = SLOT_INFO.get(slot)
    if not info:
        return None
    
    # ดึงข้อมูลหัวข้อฮิตจาก Reddit มาเป็นไอเดียตั้งต้น
    reddit_inspirations = fetch_reddit_discussion_titles()
    reddit_context = ""
    if reddit_inspirations:
        reddit_str = "\n".join([f"- {t}" for t in reddit_inspirations])
        reddit_context = (
            f"และนี่คือหัวข้อกระทู้ที่กำลังได้รับความนิยมบน Reddit ในต่างประเทศขณะนี้ (ใช้เป็นแรงบันดาลใจเพื่อนำมาประยุกต์หรือดัดแปลง):\n"
            f"{reddit_str}\n\n"
        )
    
    # กรองประวัติที่เป็น url หรือข้อความสั้นเกินไปออก
    recent_history = []
    for h in history_list:
        h_clean = h.strip()
        if not h_clean:
            continue
        if h_clean.startswith("http://") or h_clean.startswith("https://"):
            continue
        if len(h_clean) < 10:
            continue
        recent_history.append(h_clean)
    
    # เอาประวัติล่าสุด 150 รายการมาคุมไม่ให้ซ้ำ
    recent_history = recent_history[-150:]
    
    examples_str = "\n".join([f"- {ex}" for ex in info["examples"]])
    history_str = "\n".join([f"- {h}" for h in recent_history])
    
    prompt = (
        f"คุณคือแอดมินเพจแนวความชวนถกเถียงเรื่องเงิน การงาน ครอบครัว และการสร้างตัวของคนวัย 30+\n"
        f"จงสร้างประเด็น/หัวข้อชวนเลือกฝั่งหรือคำถามดราม่าทางการเงินชวนตอบ สำหรับช่วงเวลา: {slot}\n\n"
        f"คำอธิบายแนวทางช่วง {slot}:\n{info['desc']}\n\n"
        f"{reddit_context}"
        f"ตัวอย่างประเด็นแนวทางนี้:\n{examples_str}\n\n"
        f"**กฎเหล็กสำคัญมาก**:\n"
        f"1. ห้ามสร้างหัวข้อที่มีประเด็น ไอเดีย หรือคำถามที่ซ้ำหรือคล้ายคลึงกับรายการประเด็นที่โพสต์ไปแล้วด้านล่างนี้เด็ดขาด:\n"
        f"{history_str}\n\n"
        f"2. หัวข้อต้องเขียนเป็นภาษาไทยสั้นๆ 1 ประโยค (ห้ามเกิน 80 ตัวอักษร) ได้ใจความ กระชับ โดนใจคนวัยทำงาน\n"
        f"3. ห้ามมีเครื่องหมายคำพูด (เช่น อัญประกาศ \", '), ห้ามมีคำอธิบายเพิ่มเติมใดๆ หรือข้อความเกริ่นนำ ตอบเฉพาะข้อความหัวข้อเพียวๆ เท่านั้น\n"
        f"ตัวอย่างผลลัพธ์ที่ถูกต้อง: เงินเดือน 5 หมื่นขับรถหรูแต่ไม่มีเงินออม VS เงินเดือน 2 หมื่นเก็บได้หมื่นห้า แบบไหนมั่นคงกว่า?"
    )
    
    for model in TEXT_MODELS:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                topic = resp.text.strip().strip('"\'“”‘’')
                if topic:
                    print(f"[Dynamic Topic - {slot} ({model})]: {topic}")
                    return topic
            except Exception as e:
                print(f"[{model}] generate_dynamic_topic failed (attempt {attempt+1}): {e}")
    return None

def get_topic():
    history_list = load_history()
    history = set(history_list)
    bkk = timezone(timedelta(hours=7))
    now = datetime.now(bkk)
    hour = now.hour
    
    if hour < 10:
        topics = MORNING_TOPICS
        slot = "morning"
    elif hour < 13:
        topics = NOON_TOPICS
        slot = "noon"
    elif hour < 17:
        topics = EVENING_TOPICS
        slot = "evening"
    else:
        topics = LATE_TOPICS
        slot = "late"

    available = [t for t in topics if t not in history]
    if available:
        chosen = random.choice(available)
        print(f"Using hardcoded topic for {slot} slot: {chosen}")
        return chosen, slot
    else:
        print(f"All hardcoded topics in {slot} slot have been posted. Generating dynamic topic...")
        dynamic_topic = generate_dynamic_topic(slot, history_list)
        if dynamic_topic:
            return dynamic_topic, slot
        else:
            # Fallback to resetting history for that slot if dynamic generation fails
            print(f"Failed to generate dynamic topic. Resetting history for {slot} slot.")
            available = topics
            chosen = random.choice(available)
            return chosen, slot

# slot → style ที่เหมาะที่สุดตาม content matrix
SLOT_STYLE = {
    "morning": 0,   # Sarcastic Office/Work Truths
    "noon":    1,   # Financial Dilemma
    "evening": 2,   # Financial Battle
    "late":    3,   # Adulting Sarcastic Truths
}

CONTENT_STYLES = [
    # style 0: Work/Boss/Coworker Dilemmas (ดราม่าชีวิตทำงาน)
    (
        "เขียนประโยคดราม่าหรือสถานการณ์ตลกร้ายที่เป็นประเด็นชวนเลือกข้างเกี่ยวกับการทำงาน/เจ้านาย/เพื่อนร่วมงานจากหัวข้อ: {topic}\n"
        "เขียนด้วยบุคลิกแอดมินเพจที่เป็นผู้ชาย (หากมีการใช้คำลงท้ายหรือสรรพนาม ให้ใช้คำว่า 'ครับ' และแทนตัวว่า 'ผม' หรือ 'พี่' เท่านั้น)\n"
        "ความยาว 2 บรรทัดสั้นๆ (คั่นด้วย \\n)\n"
        "บรรทัดแรก: เกริ่นประเด็นดราม่าการทำงานสั้นๆ (3-5 คำ)\n"
        "บรรทัดสอง: คำถามชวนเลือกข้างหรือถามความเห็น เช่น 'ควรทนต่อไหมครับ?', 'แบบนี้ถอยดีกว่าไหมครับ?'\n"
        "ห้ามเกิน 70 ตัวอักษรรวม ใช้ภาษาพูด ห้ามมีป้ายกำกับใดๆ และท้ายใส่ hashtag 2 อัน"
    ),
    # style 1: Financial Dilemma (กระทู้ดราม่าการเงิน/ครอบครัว/แฟน)
    (
        "ตั้งคำถามเชิงดราม่าเกี่ยวกับเงิน ครอบครัว หรือความสัมพันธ์ในวัยผู้ใหญ่จากหัวข้อ: {topic}\n"
        "เขียนด้วยบุคลิกแอดมินเพจที่เป็นผู้ชาย (ใช้คำลงท้าย 'ครับ' และแทนตัวว่า 'ผม' หรือ 'พี่' เท่านั้น)\n"
        "ความยาว 2 บรรทัดสั้นๆ คั่นด้วย \\n ดึงดูดความสนใจให้คนอยากคอมเมนต์แชร์ความคิดเห็นทันที\n"
        "บรรทัดแรก: เกริ่นหัวเรื่องดราม่า/ปัญหาที่ต้องตัดสินใจ (3-5 คำ)\n"
        "บรรทัดสอง: คำถามปิดท้ายที่ตัดสินใจง่ายแต่เถียงกันยาว เช่น 'ควรให้ยืมไหมครับ?', 'เป็นคุณจะยอมไหมครับ?', 'แปลกไหมครับ?'\n"
        "ห้ามเกิน 75 ตัวอักษรรวม ใช้ภาษาพูด ห้ามมีป้ายกำกับใดๆ และท้ายใส่ hashtag 2 อัน"
    ),
    # style 2: Comparison/Team Selection (ศึกเลือกทีม/เปรียบเทียบสัจธรรมชีวิต)
    (
        "ตั้งประเด็นเปรียบเทียบแบบแบ่งทีมหรือเลือกฝั่งชวนคุยเรื่องการเงินและการใช้ชีวิตจากหัวข้อ: {topic}\n"
        "เขียนด้วยบุคลิกแอดมินเพจที่เป็นผู้ชาย (ใช้คำลงท้าย 'ครับ' และแทนตัวว่า 'ผม' หรือ 'พี่' เท่านั้น)\n"
        "รูปแบบ 2 บรรทัดสั้นๆ คั่นด้วย \\n\n"
        "บรรทัดแรก: เปรียบเทียบสองฝั่งชัดเจน เช่น 'ผ่อนคอนโดล้านสาม VS เช่าหอหมื่นห้า'\n"
        "บรรทัดสอง: ถามให้เลือกฝั่งหรือถามความคุ้มค่าตรงๆ เช่น 'ทีมไหนรายงานตัวหน่อย?', 'แบบไหนชีวิตรอดง่ายกว่า?'\n"
        "ห้ามเกิน 75 ตัวอักษรรวม ใช้ภาษาพูดตลกขำขัน ชวนคนเมนต์เถียงและแชร์ตัวเลข ห้ามมีป้ายกำกับ และท้ายใส่ hashtag 2 อัน"
    ),
    # style 3: Sarcastic Struggles (ประชดชีวิตผู้ใหญ่ 30+)
    (
        "เขียนประโยคตลกร้าย/ประชดประชันความเจ็บปวดวัยสร้างตัว (หนี้สิน/ครอบครัว/สุขภาพพัง) จากหัวข้อ: {topic}\n"
        "เขียนด้วยบุคลิกแอดมินเพจที่เป็นผู้ชาย (ใช้คำลงท้าย 'ครับ' และแทนตัวว่า 'ผม' หรือ 'พี่' เท่านั้น)\n"
        "ความยาว 2 บรรทัดสั้นๆ คั่นด้วย \\n ชวนให้คนอ่านแล้วพยักหน้ายอมรับและเมนต์เห็นด้วย\n"
        "บรรทัดแรก: คำกล่าวประชดประชันชีวิต/สัจธรรมผู้ใหญ่ (3-6 คำ)\n"
        "บรรทัดสอง: คำถามจี้ใจหรือถามความเห็น เช่น 'บ้านไหนแบกอยู่บ้างครับ?', 'เหนื่อยเหมือนกันไหมครับ?'\n"
        "ห้ามเกิน 70 ตัวอักษรรวม ใช้ภาษาบ่นชีวิตเพื่อนฝูง ห้ามสอนเด็ดขาด ห้ามมีป้ายกำกับ และท้ายใส่ hashtag 2 อัน"
    ),
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

def clean_hook_lines(raw_text):
    text = clean_text(raw_text)
    if "|" in text:
        parts = text.split("|")
    else:
        parts = text.split("\n")
    label_pattern = r'^(ข้อความในโพสต์\\s*Facebook|Facebook\\s*Caption|Facebook\\s*caption|Caption|caption|ข้อความบนรูป|ข้อความในรูป|ข้อความ|คำบรรยาย|คำอธิบาย|บรรทัดที่\\s*\\d+|บรรทัด\\s*\\d+|ประโยคที่\\s*\\d+|ประโยค\\s*\\d+|Hook\\s*text|Hook|Line\\s*\\d+|[L|l]ine\\s*\\d+|\\d+)\\s*[:\\-\\.\\s]\\s*'
    cleaned_lines = []
    for part in parts:
        cleaned = re.sub(label_pattern, '', part, flags=re.IGNORECASE).strip()
        cleaned = cleaned.strip('"\'“”‘’')
        if cleaned:
            cleaned_lines.append(cleaned)
    return "\n".join(cleaned_lines)
FALLBACK_QUOTES = [
    "อายุ 30+ สิ่ง\u200bที่\u200bน่าตื่นเต้น\u200bที่\u200bสุดไม่ใช่\u200bเงิน\u200bเดือน\u200bออก\nแต่\u200bคือตื่นมา\u200bแล้ว\u200bหลังไม่ปวด\u200bครับ\n#ชีวิต\u200bคน\u200bทำงาน",
    "ไม่\u200bมี\u200bอะไร\u200bทำ\u200bร้าย\u200bเรา\u200bได้\u200bเท่า\u200bเสียง\u200bแจ้งเตือน LINE สั่ง\u200bงาน\u200bตอนสี่ทุ่ม\n#ชีวิตมนุษย์\u200bเงิน\u200bเดือน",
    "งาน\u200bด่วน\u200bคือข้อยกเว้น งาน\u200bที่\u200bทำ\u200bไม่ทันคือเรื่องปกติ\nสู้ๆ ครับ\u200bมนุษย์ออฟฟิศ\u200bทุกคน\n#ชีวิตมนุษย์ออฟฟิศ",
    "การ\u200bทำงาน\u200bหนักไม่\u200bได้\u200bช่วย\u200bให้\u200bรวยขึ้นทันที\nแต่\u200bช่วย\u200bให้\u200bหมดวัน\u200bเร็ว\u200bขึ้นแน่\u200bนอน\u200bครับ\n#งาน\u200bคือ\u200bเงิน",
    "อยาก\u200bรวย\u200bต้อง\u200bทำงาน แต่\u200bพอ\u200bทำงาน\u200bก็\u200bไม่\u200bมี\u200bเวลา\u200bใช้\u200bเงิน\nตกลง\u200bเรา\u200bทำงาน\u200bไป\u200bเพื่อ\u200bอะไร\u200bกันแน่\u200bครับ\n#สู้ชีวิต\u200bแต่\u200bชีวิตสู้กลับ",
    "เงิน\u200bเก็บ 1 แสน\u200bแรก\u200bหา\u200bยาก\u200bที่\u200bสุด\nแต่ 1 พัน\u200bสุดท้าย\u200bหลัง\u200bจาก\u200bวัน\u200bหวย\u200bออก หา\u200bยาก\u200bกว่า\u200bเยอะ\u200bครับ\n#เรื่องมันเศร้า",
    "เป้าหมาย\u200bการ\u200bเงิน\u200bปี\u200bนี้\u200bคือรอดตาย\nเรื่องกำไรค่อยคุยกันปีหน้า\u200bครับ\n#รอดตายก่อน",
    "ความสุข\u200bไม่\u200bได้\u200bอยู่\u200bที่\u200bการ\u200bมี\u200bเงิน\u200bเยอะๆ\nแต่\u200bมันอยู่ตรง\u200bที่\u200bได้\u200bนอน\u200bเฉยๆ แล้ว\u200bมี\u200bเงิน\u200bโอน\u200bเข้าบัญชีต่างหาก\u200bครับ\n#อิสระ\u200bที่\u200bแท้\u200bจริง",
    "ทำงาน\u200bเหมือน\u200bเป็น\u200bเจ้า\u200bของ\u200bบริษัท\nแต่\u200bตอน\u200bเงิน\u200bเดือน\u200bออก นึ\u200bกว่า\u200bเป็น\u200bผู้บริจาค\u200bเงิน\u200bให้\u200bบริษัท\n#ฮาๆกันไป",
    "สุขภาพ\u200bที่\u200bดี\u200bคือลาภ\u200bอัน\u200bประเสริฐ\nแต่\u200bออฟฟิศซินโดรมคือ\u200bเพื่อน\u200bแท้\u200bที่\u200bไม่\u200bมี\u200bวันทิ้ง\u200bเรา\u200bไป\n#ออฟฟิศซินโดรม",
    "วัย 30+ เริ่ม\u200bรู้\u200bซึ้งว่า การ\u200bไม่\u200bมี\u200bห\u200bนี้\nคือลาภ\u200bอัน\u200bประเสริฐยิ่ง\u200bกว่า\u200bถูก\u200bหวย\u200bงวด\u200bนี้\u200bอีก\u200bครับ\n#ชีวิต\u200bคน\u200bทำงาน",
    "อยาก\u200bมี passive income เดือน\u200bละ\u200bหมื่น\nแต่\u200bตอน\u200bนี้\u200bนั่ง\u200bลุ้น\u200bเงิน\u200bฝากออมทรัพย์\u200bได้\u200bดอกเบี้ย\u200bสิ\u200bบบาท\n#ชีวิต\u200bต้อง\u200bสู้",
    "การ\u200bลงทุน\u200bมี\u200bความเสี่ยง\nแต่\u200bการ\u200bไม่ลงทุน\u200bอะไร\u200bเลย\u200bแล้ว\u200bหวัง\u200bจะ\u200bรวย เสี่ยง\u200bที่\u200bสุด\u200bครับ\n#คิด\u200bการ\u200bใหญ่\u200bใจ\u200bต้อง\u200bนิ่ง",
    "อย่าเอา\u200bสุขภาพ\u200bทั้งชีวิต\nไปแลก\u200bกับ\u200bเงิน\u200bเดือนหลัก\u200bหมื่น\u200bที่\u200bหมดไป\u200bกับ\u200bค่าหมอตอนแก่\u200bเลย\u200bครับ\n#ถนอม\u200bตัว\u200bด้วย\u200bนะ"
]

def generate_quote(topic, slot="morning"):
    global API_ENABLED
    try:
        if not API_ENABLED:
            raise RuntimeError("API is disabled due to previous failure")
        style_idx = SLOT_STYLE.get(slot, 0)
        style = CONTENT_STYLES[style_idx]
        prompt = style.format(topic=topic)
        print(f"Topic: {topic} | Slot: {slot} | Style: {style_idx}")
        for model in TEXT_MODELS:
            for attempt in range(2):
                try:
                    resp = client.models.generate_content(model=model, contents=prompt)
                    quote = clean_hook_lines(resp.text)
                    print(f"Quote [{model}]:\n{quote}\n")
                    return quote
                except Exception as e:
                    print(f"[{model}] attempt {attempt+1} failed: {str(e)[:100]}")
                    if attempt < 1:
                        time.sleep(10)
            print(f"[{model}] unavailable, trying next model...")
        raise RuntimeError("Quote generation failed on all models and attempts")
    except Exception as outer_e:
        print(f"Error during quote generation: {str(outer_e)}")
        print("[Warning] Disabling API calls for this run.")
        API_ENABLED = False
        print("Using random fallback quote from the local Thai/Office/Work/Life list.")
        quote = random.choice(FALLBACK_QUOTES)
        print(f"Fallback quote used:\n{quote}")
        return quote


def generate_threads_content(topic, slot):
    global API_ENABLED
    if not API_ENABLED:
        print("Falling back to local quotes list due to disabled API.")
        fb_quote = random.choice(FALLBACK_QUOTES)
        lines = fb_quote.strip().split("\n")
        clean_lines = [re.sub(r'#\S+', '', l).strip() for l in lines if l.strip()]
        img_l1 = clean_lines[0] if clean_lines else "เรื่องชวนคิดวันนี้"
        img_l2 = clean_lines[1] if len(clean_lines) > 1 else ""
        cap = " ".join(clean_lines)
        seed_c = "สำหรับเรื่องนี้ผมมองว่าความกตัญญูหรือความพยายามต้องมีขีดจำกัดนะ ไม่งั้นเราจะลำบากเองครับ"
        return {
            "image_line1": img_l1,
            "image_line2": img_l2,
            "caption": cap,
            "seed_comment": seed_c
        }

    slot_contexts = {
        "morning": "เกี่ยวกับชีวิตการทำงาน เจ้านาย หรือเพื่อนร่วมงานในออฟฟิศ",
        "noon": "ดราม่า/ทางเลือกที่ยากในการเงิน ครอบครัว หรือความสัมพันธ์ในชีวิตคู่",
        "evening": "การเปรียบเทียบสองทางเลือก หรือการเลือกข้างอย่างใดอย่างหนึ่งเกี่ยวกับการเงินและการใช้ชีวิต",
        "late": "ความกดดัน ความจริงอันเจ็บปวดวัยสร้างตัว หรือสัจธรรมตลกร้ายของผู้ใหญ่วัย 30+"
    }
    context_desc = slot_contexts.get(slot, "ประเด็นดราม่าการทำงานหรือชีวิตคนวัยสร้างตัว")

    prompt = (
        f"วิเคราะห์หัวข้อ: '{topic}' สำหรับโพสต์ Threads ในช่วงเวลา {slot} (เน้นเรื่อง: {context_desc})\n"
        "จงสร้างเนื้อหา 3 ส่วนดังต่อไปนี้ในรูปแบบ JSON เพื่อชวนคนมาคอมเมนต์เถียงและเลือกข้าง:\n\n"
        "1. ข้อความสำหรับแสดงบนภาพ (image_line1 และ image_line2):\n"
        "   - เป็นข้อความพาดหัวสั้นๆ คมๆ เจาะประเด็นหลักประเด็นเดียว\n"
        "   - ห้ามใส่แฮชแท็กบนรูปเด็ดขาด\n"
        "   - ความยาวบรรทัดละไม่เกิน 8-14 ตัวอักษรภาษาไทย\n"
        "   - ตัวอย่างบรรทัดแรก: 'แฟนหนี้ท่วม' บรรทัดสอง: 'ยังควรไปต่อไหม?'\n\n"
        "2. คำบรรยายโพสต์ (caption):\n"
        "   - เขียนบริบทหรือเรื่องราวนำ 1-2 ประโยค เพื่อให้คนเข้าใจที่มาของปัญหามากขึ้น\n"
        "   - ปิดท้ายด้วยคำถามที่ต้องเลือกข้างหรือตัดสินใจง่าย แต่ชวนให้คนเถียงกันยาว\n"
        "   - ห้ามใช้แฮชแท็กเด็ดขาด\n"
        "   - ความยาวรวมไม่เกิน 160 ตัวอักษร\n"
        "   - ใช้ภาษาพูดเป็นกันเอง สุภาพ มีคำลงท้ายว่า 'ครับ' และแทนตัวเองว่า 'ผม/พี่' เท่าที่มีโอกาส\n\n"
        "3. ความเห็นเปิดประเด็นคอมเมนต์ (seed_comment):\n"
        "   - เป็นความเห็นของแอดมิน (ผู้ชาย แทนตัวว่า 'ผม' หรือ 'พี่' ลงท้ายด้วย 'ครับ/ผม')\n"
        "   - ต้องแสดงจุดยืนเลือกข้างอย่างชัดเจนข้างใดข้างหนึ่งทันที เพื่อชวนเปิดศึก/ให้คนอื่นแย้งหรือสนับสนุน\n"
        "   - ห้ามประนีประนอมหรือตอบกลางๆ เด็ดขาด เช่น 'ผมทีมคบต่อได้ แต่ต้องเห็นแผนใช้หนี้ชัดๆ ถ้ารักอย่างเดียวแล้วโยนภาระมาให้เรา อันนี้ไม่ไหวครับ' หรือ 'ผมว่าความกตัญญูมีขีดจำกัดนะ ถ้าให้จนตัวเองไม่มีเงินเก็บเลย ระยะยาวพังแน่นอนครับ'\n"
        "   - ความยาว 1-2 ประโยคสั้นๆ\n"
        "   - ห้ามมีแฮชแท็กเด็ดขาด\n\n"
        "รูปแบบผลลัพธ์ที่ต้องการ (ตอบกลับเป็น JSON เพียวๆ เท่านั้น):\n"
        "{\n"
        '  "image_line1": "ข้อความบรรทัดที่ 1",\n'
        '  "image_line2": "ข้อความบรรทัดที่ 2",\n'
        '  "caption": "เนื้อหาโพสต์...",\n'
        '  "seed_comment": "ความคิดเห็นแอดมิน..."\n'
        "}"
    )

    for model in TEXT_MODELS:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    )
                )
                import json
                data = json.loads(resp.text.strip())
                image_line1 = data.get("image_line1", "").strip()
                image_line2 = data.get("image_line2", "").strip()
                caption = data.get("caption", "").strip()
                seed_comment = data.get("seed_comment", "").strip()

                if image_line1 and caption and seed_comment:
                    # Strip hashtags just in case
                    image_line1 = re.sub(r'#\S+', '', image_line1).strip()
                    image_line2 = re.sub(r'#\S+', '', image_line2).strip()
                    caption = re.sub(r'#\S+', '', caption).strip()
                    seed_comment = re.sub(r'#\S+', '', seed_comment).strip()

                    print(f"Generated JSON successfully:")
                    print(f"Image Line 1: {image_line1}")
                    print(f"Image Line 2: {image_line2}")
                    print(f"Caption: {caption}")
                    print(f"Seed Comment: {seed_comment}")
                    return {
                        "image_line1": image_line1,
                        "image_line2": image_line2,
                        "caption": caption,
                        "seed_comment": seed_comment
                    }
            except Exception as e:
                print(f"[{model}] generate_threads_content failed (attempt {attempt+1}): {e}")
                time.sleep(2)

    # Fallback if API fails
    print("Falling back to local quotes list due to generation failure.")
    fb_quote = random.choice(FALLBACK_QUOTES)
    lines = fb_quote.strip().split("\n")
    clean_lines = [re.sub(r'#\S+', '', l).strip() for l in lines if l.strip()]
    img_l1 = clean_lines[0] if clean_lines else "เรื่องชวนคิดวันนี้"
    img_l2 = clean_lines[1] if len(clean_lines) > 1 else ""
    cap = " ".join(clean_lines)
    seed_c = "สำหรับเรื่องนี้ผมมองว่าความกตัญญูหรือความพยายามต้องมีขีดจำกัดนะ ไม่งั้นเราจะลำบากเองครับ"
    return {
        "image_line1": img_l1,
        "image_line2": img_l2,
        "caption": cap,
        "seed_comment": seed_c
    }


FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "Sarabun-ExtraBold.ttf")
IMG_SIZE  = 1080

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

def segment_thai_text(text, client):
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

def _wrap_char(draw, text, font, max_width):
    if '\u200b' in text or '\\u200b' in text:
        tokens = text.replace('\\u200b', '\u200b').split('\u200b')
    else:
        tokens = list(text)
    lines, current = [], ""
    for token in tokens:
        test = current + token
        fits = draw.textbbox((0, 0), test, font=font)[2] <= max_width
        if fits or (len(token) == 1 and token in _COMBINING_CHARS):
            current = test
        else:
            if current:
                if current[-1] in _LEADING_VOWELS:
                    orphan  = current[-1]
                    current = current[:-1]
                    if current:
                        lines.append(current)
                    current = orphan + token
                else:
                    lines.append(current)
                    current = token
            else:
                current = token
    if current:
        lines.append(current)
    return lines or [text]


def _balance_last(draw, lines, font, max_width, min_ratio=0.42, min_chars=4):
    """ป้องกัน orphan บรรทัดสุดท้ายที่สั้นเกิน"""
    if len(lines) <= 1:
        return lines
    last = lines[-1].strip()
    prev = lines[-2].strip()
    if not last or not prev:
        return lines
    last_w = draw.textbbox((0, 0), last, font=font)[2]
    prev_w = draw.textbbox((0, 0), prev, font=font)[2]
    is_orphan = (last_w < prev_w * min_ratio) or (len(last) <= min_chars)
    if not is_orphan:
        return lines
    merged   = prev + " " + last
    total_w  = draw.textbbox((0, 0), merged, font=font)[2]
    target_w = min(max_width, int(total_w * 0.55))
    if " " in merged.strip():
        rebalanced = _wrap_words(draw, merged, font, target_w)
    else:
        rebalanced = _wrap_char(draw, merged, font, target_w)
    if all(draw.textbbox((0, 0), l, font=font)[2] <= max_width for l in rebalanced):
        return lines[:-2] + rebalanced
    return lines


def _wrap_words(draw, text, font, max_width):
    """ตัดจากช่องว่างก่อน เพื่อไม่ผ่าคำไทยกลางคำโดยไม่จำเป็น"""
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

def analyze_reddit_image_for_threads(img_path, reddit_title):
    """วิเคราะห์รูปและหัวข้อ Reddit เพื่อดัดแปลงเป็นประเด็นคนทำงาน/ชีวิตผู้ใหญ่"""
    global API_ENABLED
    if not API_ENABLED:
        return None
        
    try:
        with open(img_path, "rb") as f:
            img_data = f.read()
    except Exception as read_err:
        print(f"Error reading image file for analysis: {read_err}")
        return None
        
    mime_type = "image/jpeg"
    if img_path.lower().endswith(".png"):
        mime_type = "image/png"
    elif img_path.lower().endswith(".webp"):
        mime_type = "image/webp"
    elif img_path.lower().endswith(".gif"):
        mime_type = "image/gif"

    prompt = (
        "วิเคราะห์ภาพนี้ร่วมกับหัวข้อกระทู้ Reddit: '" + reddit_title + "'\n"
        "งานของคุณคือแปลงโพสต์นี้ให้กลายเป็นประเด็นตลกร้าย/ประเด็นชวนเถียงในชีวิตจริงของคนทำงาน/ผู้ใหญ่วัยสร้างตัว 30+ (Rocket21 Persona) โดยปฏิบัติตามกฎอย่างเคร่งครัด:\n\n"
        "1. การกรองเนื้อหา (Strict Filtering):\n"
        "   - รูปนี้ต้องนำมาเชื่อมโยงกับเรื่องการงาน, เงิน, ครอบครัว หรือความสัมพันธ์ได้\n"
        "   - หากรูปเป็นของแปลก/ธรรมชาติ/สัตว์/ดอกไม้ (เช่น ดอกไม้มีหนามข่วนมือ) ให้เปรียบเปรยหรือแปลงเป็นสถานการณ์ในออฟฟิศทันที (เช่น 'แค่จัดดอกไม้ ยังมีแผล' -> เปรียบกับการทำงานที่เบื้องหลังเต็มไปด้วยความยากลำบาก คำแก้งาน)\n"
        "   - หากรูปไม่สามารถเชื่อมโยงกับชีวิตการทำงานหรือเรื่องปากท้องได้อย่างเป็นธรรมชาติ หรือไม่เหมาะสมอย่างสิ้นเชิง ให้ระบุว่า 'invalid'\n\n"
        "2. องค์ประกอบที่ต้องเจน (หากนำมาปรับใช้ได้):\n"
        "   - image_line1: พาดหัวสั้นกระชับบรรทัดที่ 1 สำหรับใส่บนรูปภาพ (ความยาว 8-14 ตัวอักษรไทย ห้ามมีแฮชแท็ก)\n"
        "   - image_line2: รายละเอียดสั้นบรรทัดที่ 2 สำหรับใส่บนรูปภาพ (ความยาว 8-14 ตัวอักษรไทย ห้ามมีแฮชแท็ก)\n"
        "   - caption: คำบรรยายอธิบายประเด็นเชื่อมโยงกับชีวิตทำงาน/ชีวิตจริง 1-2 ประโยค ปิดท้ายด้วยคำถามปลายปิดหรือชวนเลือกข้างเพื่อดึงคนมาตอบคอมเมนต์ (ห้ามมีแฮชแท็กเด็ดขาด, ความยาวไม่เกิน 160 ตัวอักษร)\n"
        "   - seed_comment: ความเห็นของแอดมินในฐานะผู้ชาย (แทนตัว 'ผม/พี่' ลงท้ายด้วย 'ครับ/ผม') ที่เลือกข้างหรือแสดงจุดยืนชัดเจนข้างใดข้างหนึ่งทันที เพื่อกระตุ้นให้เกิดคอมเมนต์เถียงกันต่อ (ห้ามมีแฮชแท็กเด็ดขาด)\n\n"
        "กรุณาตอบกลับเป็น JSON รูปแบบนี้เท่านั้น (หากไม่เหมาะสม ให้ตอบคำว่า 'invalid' ในค่า status และปล่อยคีย์อื่นว่าง):\n"
        "{\n"
        '  "status": "valid",\n'
        '  "image_line1": "พาดหัวบรรทัด 1",\n'
        '  "image_line2": "พาดหัวบรรทัด 2",\n'
        '  "caption": "แคปชั่นโพสต์...",\n'
        '  "seed_comment": "คอมเมนต์แอดมิน..."\n'
        "}\n\n"
        "กรณีไม่ผ่านเกณฑ์:\n"
        "{\n"
        '  "status": "invalid"\n'
        "}"
    )

    for model in TEXT_MODELS:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=[
                        types.Part.from_bytes(data=img_data, mime_type=mime_type),
                        types.Part.from_text(text=prompt)
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                import json
                data = json.loads(resp.text.strip())
                if data.get("status") == "invalid":
                    print(f"[{model}] Vision filter: post marked as invalid for Rocket21 persona.")
                    return None
                
                # Verify we have the required keys
                if data.get("image_line1") and data.get("caption") and data.get("seed_comment"):
                    # Strip any potential hashtags
                    data["image_line1"] = re.sub(r'#\S+', '', data["image_line1"]).strip()
                    data["image_line2"] = re.sub(r'#\S+', '', data.get("image_line2", "")).strip()
                    data["caption"] = re.sub(r'#\S+', '', data["caption"]).strip()
                    data["seed_comment"] = re.sub(r'#\S+', '', data["seed_comment"]).strip()
                    return data
            except Exception as e:
                print(f"[{model}] analyze_reddit_image_for_threads failed (attempt {attempt+1}): {e}")
                time.sleep(2)
    return None

def run_meme_mode(dry_run=False):
    """โหมดสุ่มรูปตลกมาโพส — ปรับปรุงสไตล์คนทำงานออฟฟิศ"""
    print("Mode: MEME (Reddit/Meme localization to Rocket21 persona)")
    history = set(load_history())
    
    posted = False
    for attempt in range(6):
        img_url, title, subreddit = get_meme_image(history)
        if not img_url:
            continue
        img_path = download_image(img_url)
        if not img_path:
            continue
            
        print(f"Attempt {attempt+1}: Analyzing {img_url} with title '{title}'...")
        analysis = analyze_reddit_image_for_threads(img_path, title)
        if not analysis:
            print("Post is invalid or cannot be connected to work/life persona. Skipping.")
            os.unlink(img_path)
            continue
            
        line1 = segment_thai_text(analysis["image_line1"], client)
        line2 = segment_thai_text(analysis.get("image_line2", ""), client)
        caption = analysis["caption"]
        seed_comment = analysis["seed_comment"]
        
        # Draw overlay on the image using overlay_utils
        out_path = os.path.join(OUTPUT_DIR, f"threads_meme_overlay_{int(time.time())}.jpg")
        try:
            from overlay_utils import add_overlay
            # Quote mode uses Gold (#FFD700) for line1, White for line2.
            # add_overlay accepts accent_color. Let's pass "#FFD700" to make it look matching.
            add_overlay(img_path, line1, line2, accent_color="#FFD700", out_path=out_path)
        except Exception as oe:
            print(f"Error drawing overlay: {oe}. Using raw image.")
            out_path = img_path
            
        print("\n--- [THREADS MEME DETECTED & MAPPED] ---")
        print(f"Subreddit:   r/{subreddit}")
        print(f"Original:    {title}")
        print(f"Line 1:      {line1}")
        print(f"Line 2:      {line2}")
        print(f"Caption:     {caption}")
        print(f"Seed Comment: {seed_comment}")
        print(f"Image path:  {out_path}\n")
        
        if dry_run:
            print("[Dry-run] Skipping upload and post.")
            if out_path != img_path and os.path.exists(out_path):
                # keep for user inspection, do not unlink
                pass
            os.unlink(img_path)
            return True
            
        try:
            hosted_url = upload_image_to_imgur(out_path)
            post_threads(hosted_url, caption, seed_comment=seed_comment, img_path=out_path)
            save_to_history(img_url)
            posted = True
            
            # Clean up files
            if out_path != img_path and os.path.exists(out_path):
                os.unlink(out_path)
            os.unlink(img_path)
            break
        except Exception as pe:
            print(f"Posting failed: {pe}")
            if out_path != img_path and os.path.exists(out_path):
                os.unlink(out_path)
            os.unlink(img_path)
            continue
            
    if not posted:
        print("Meme mode failed to find a valid post or post it. Falling back to quote mode.")
        run_quote_mode(dry_run=dry_run)

def run_quote_mode(dry_run=False):
    """โหมดคำคม — PIL image + quote"""
    topic, slot = get_topic()
    content = generate_threads_content(topic, slot)
    
    line1 = segment_thai_text(content["image_line1"], client)
    line2 = segment_thai_text(content["image_line2"], client)
    
    img_path = generate_image(line1, line2)
    
    print("\n--- [THREADS QUOTE POST] ---")
    print(f"Topic:       {topic}")
    print(f"Line 1:      {line1}")
    print(f"Line 2:      {line2}")
    print(f"Caption:     {content['caption']}")
    print(f"Seed Comment: {content['seed_comment']}")
    print(f"Image path:  {img_path}\n")
    
    if dry_run:
        print("[Dry-run] Skipping upload and post.")
        return
        
    try:
        img_url  = upload_image_to_imgur(img_path)
        post_threads(img_url, content["caption"], seed_comment=content["seed_comment"], img_path=img_path)
        save_to_history(topic)
    finally:
        if img_path and os.path.exists(img_path):
            os.unlink(img_path)

def wrap_thai(text, font, draw, max_width):
    """ตัดบรรทัดให้พอดีความกว้าง โดยพยายามรักษาคำ/วลีไทยไว้ก่อน"""
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return [text]

    if " " in text.strip():
        lines = _wrap_words(draw, text, font, max_width)
        if getattr(font, "size", 99) <= 75:
            new_lines = []
            for l in lines:
                if draw.textbbox((0, 0), l, font=font)[2] > max_width:
                    new_lines.extend(_wrap_char(draw, l, font, max_width))
                else:
                    new_lines.append(l)
            lines = new_lines
    else:
        # อย่ารีบผ่าคำไทยตอน font ยังใหญ่ ให้ auto-fit ลด font ก่อน
        lines = [text] if getattr(font, "size", 99) > 75 else _wrap_char(draw, text, font, max_width)
    return _balance_last(draw, lines, font, max_width)

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

def generate_image(line1, line2=""):
    print("Generating image (PIL)...")
    bkk = timezone(timedelta(hours=7))
    ts  = datetime.now(bkk).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"threads_{ts}.png")

    img  = Image.new("RGB", (IMG_SIZE, IMG_SIZE), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    PAD      = 100
    max_w    = IMG_SIZE - PAD * 2
    max_h    = IMG_SIZE - PAD * 2
    LINE_GAP = 24

    # auto-fit: หา font size ใหญ่ที่สุดที่พอดีกรอบ
    font_size = 100
    lines = [line1]
    if line2:
        lines.append(line2)

    while font_size >= 36:
        font = ImageFont.truetype(FONT_PATH, font_size)
        total_h = 0
        width_ok = True
        for l in lines:
            bbox = draw.textbbox((0, 0), l, font=font)
            h = bbox[3] - bbox[1]
            w = bbox[2] - bbox[0]
            if w > max_w:
                width_ok = False
            total_h += h
        total_h += LINE_GAP * (len(lines) - 1)
        if total_h <= max_h and width_ok:
            break
        font_size -= 4

    print(f"Font size: {font_size}")
    font = ImageFont.truetype(FONT_PATH, font_size)

    # Calculate start y to center vertically
    y = (IMG_SIZE - total_h) // 2

    # Draw text lines centered
    for i, l in enumerate(lines):
        bbox = draw.textbbox((0, 0), l, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (IMG_SIZE - w) // 2
        draw_y = y - bbox[1]

        # Color: First line is Gold (#FFD700), second line is White
        color = (255, 215, 0) if i == 0 else (255, 255, 255)
        # Drop shadow for clean look
        draw.text((x + 3, draw_y + 3), l, font=font, fill=(30, 30, 30))
        draw.text((x, draw_y), l, font=font, fill=color)

        y += h + LINE_GAP

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
        data={"key": IMGBB_API_KEY, "image": img_data},
        timeout=60
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
        data=data,
        timeout=60
    )
    container_id = resp.json().get("id")
    if not container_id:
        print(f"Reply container error: {resp.json()}")
        return None
    time.sleep(3)
    resp2 = requests.post(
        f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish",
        data={"creation_id": container_id, "access_token": THREADS_ACCESS_TOKEN},
        timeout=60
    )
    result = resp2.json()
    return result.get("id")

def generate_seed_comment(caption):
    """สร้าง comment ความเห็นจากฝั่งแอดมิน (ครับ/ผม/พี่) เพื่อเปิดประเด็นถกเถียง"""
    global API_ENABLED
    if not API_ENABLED:
        return ""
    prompt = (
        f"จากโพสต์ (caption): {caption}\n\n"
        "จงเขียนคอมเมนต์สั้นๆ 1 ประโยค (ไม่เกิน 50 ตัวอักษร) เพื่อแสดงความคิดเห็นของแอดมินในฐานะผู้ชาย "
        "โดยสรรพนามแทนตัวเองด้วย 'ผม' หรือ 'พี่' ลงท้ายด้วย 'ครับ/ผม' เสมอ "
        "คอมเมนต์นี้ควรแสดงจุดยืนหรือแสดงความเห็นข้างใดข้างหนึ่งแบบกวนๆ หรือเป็นกันเอง เพื่อเริ่มการถกเถียง "
        "ห้ามใช้ markdown, ห้ามใส่ hashtag, ตอบเฉพาะตัวข้อความคอมเมนต์เท่านั้น"
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            comment = clean_text(resp.text)
            if comment:
                return comment
        except Exception as e:
            print(f"[{model}] generate_seed_comment failed: {e}")
    return ""

def post_threads(image_url, caption, seed_comment=None, img_path=None):
    print("Posting to Threads...")
    # Step 1: Create image container
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
        print(f"Threads Error (create): {result}")
        raise SystemExit(1)
    container_id = result["id"]
    print(f"Container created: {container_id}")
    time.sleep(5)

    # Step 2: Publish
    resp2 = requests.post(
        f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish",
        data={"creation_id": container_id, "access_token": THREADS_ACCESS_TOKEN},
        timeout=60
    )
    result2 = resp2.json()
    if "id" not in result2:
        print(f"Threads Error (publish): {result2}")
        raise SystemExit(1)
    post_id = result2["id"]
    print(f"Threads Posted! ID: {post_id}")

    # Seed comment integration
    if not seed_comment:
        seed_comment = generate_seed_comment(caption)
    if seed_comment:
        print(f"Posting seed comment: {seed_comment}")
        time.sleep(random.uniform(5, 10))
        seed_reply_id = _create_and_publish(seed_comment, reply_to_id=post_id)
        print(f"Seed reply added! ID: {seed_reply_id}")

    # Step 3: Add reply comments
    from affiliate_utils import get_all_comments
    all_comments = get_all_comments(caption=caption, img_path=img_path)
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


def get_meme_image(history=None):
    if history is None:
        history = set()
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
            title = entry.findtext("atom:title", "", ns)
            content   = entry.findtext("atom:content", "", ns)
            img_urls  = re.findall(r'https?://[^\s"<>]+\.(?:jpg|jpeg|png|gif|webp)', content or "")
            good_imgs = [u for u in img_urls if ("i.redd.it" in u or "imgur.com" in u) and u not in history]
            if good_imgs:
                posts.append({"url": good_imgs[0], "title": title, "subreddit": subreddit})
        if not posts:
            return None, None, None
        post = random.choice(posts[:10])
        print(f"Meme: r/{subreddit} | {post['url'][:60]}")
        return post["url"], post.get("title", ""), subreddit
    except Exception as e:
        print(f"Reddit error: {e}")
        return None, None, None


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
        "เขียนด้วยบุคลิกแอดมินเพจที่เป็นผู้ชาย (หากมีการใช้คำลงท้ายหรือสรรพนาม ให้ใช้คำว่า 'ครับ' และแทนตัวว่า 'ผม' หรือ 'พี่' เท่านั้น)\n"
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


# Run modes are defined above.


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Threads Post Script")
    parser.add_argument("--mode", choices=["quote", "meme"], default="quote", help="Content mode to run (default: quote)")
    parser.add_argument("--dry-run", action="store_true", help="Run script locally without posting to Threads or ImgBB")
    args = parser.parse_args()
    
    print(f"Running Threads bot in mode: {args.mode.upper()}")
    if args.dry_run:
        print("Dry-run mode activated. No posts will be published.")
        
    if args.mode == "quote":
        run_quote_mode(dry_run=args.dry_run)
    elif args.mode == "meme":
        run_meme_mode(dry_run=args.dry_run)
