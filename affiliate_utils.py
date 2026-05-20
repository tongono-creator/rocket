# affiliate_utils.py — อ่าน product links จาก affiliate_products.xlsx
import os
from datetime import datetime, timezone, timedelta

WEBSITE_URL      = "https://shopee-ranking.vercel.app/"
SHOPEE_FOOD_URL  = "วางลิงก์ Shopee Food ที่นี่"  # TODO: ใส่ลิงก์จริง

EXCEL_PATH = os.path.join(os.path.dirname(__file__), "affiliate_products.xlsx")

def get_active_products():
    """โหลด product links ที่ Active=yes จาก Excel"""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
        ws = wb.active
        products = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            no, name, shopee, lazada, active = row[0], row[1], row[2], row[3], row[4]
            desc = row[5] if len(row) > 5 else None
            if str(active).strip().lower() == "yes" and shopee and "xxx" not in str(shopee):
                products.append({"name": name, "shopee": shopee, "lazada": lazada, "desc": desc or ""})
        return products
    except Exception as e:
        print(f"Excel read failed: {e}")
        return []

def get_rotating_product():
    """หยิบ product วันนี้ตาม day rotation"""
    products = get_active_products()
    if not products:
        return None
    bkk = timezone(timedelta(hours=7))
    day_idx = datetime.now(bkk).timetuple().tm_yday % len(products)
    return products[day_idx]

WEBSITE_VARIATIONS = [
    f"🔥 อยากรู้ว่าสินค้าไหนขายดีที่สุดบน Shopee ตอนนี้?\nดูอันดับสินค้าขายดีได้เลยที่ → {WEBSITE_URL}",
    f"📊 เช็คอันดับสินค้าขายดีก่อนซื้อ ประหยัดได้เยอะมาก\n→ {WEBSITE_URL}",
    f"🛒 ของขายดีอันดับ 1 บน Shopee วันนี้คืออะไร?\nเช็คได้เลย → {WEBSITE_URL}",
    f"💡 ก่อนซื้อของออนไลน์ ดูอันดับก่อนนะ\n→ {WEBSITE_URL}",
    f"🏆 คนไทยกำลังซื้ออะไรกันเยอะที่สุด?\nดูได้ที่นี่ → {WEBSITE_URL}",
]

FOOD_VARIATIONS = [
    f"🍜 หิวแล้วสั่ง Shopee Food เลย มีโปรลดทุกวัน → {SHOPEE_FOOD_URL}",
    f"🍱 สั่งข้าวง่ายๆ ส่งถึงบ้าน Shopee Food → {SHOPEE_FOOD_URL}",
    f"🔖 Shopee Food มีคูปองลดให้ทุกวัน สั่งเลย → {SHOPEE_FOOD_URL}",
    f"🛵 อยากกินอะไร สั่งได้เลย Shopee Food → {SHOPEE_FOOD_URL}",
    f"🍔 ประหยัดค่าอาหารด้วย Shopee Food โปรเด็ดทุกมื้อ → {SHOPEE_FOOD_URL}",
]

def _get_variation(variations):
    bkk = timezone(timedelta(hours=7))
    now = datetime.now(bkk)
    idx = (now.timetuple().tm_yday * 3 + now.hour) % len(variations)
    return variations[idx]

def get_standard_comments():
    """standard comments (website + Shopee Food) — หมุน variations"""
    comments = [_get_variation(WEBSITE_VARIATIONS)]
    if "วางลิงก์" not in SHOPEE_FOOD_URL:
        comments.append(_get_variation(FOOD_VARIATIONS))
    return comments

SHOPEE_INTROS = ["🛒 ช้อปได้บน Shopee", "🔥 ราคาดีที่สุดบน Shopee", "🎯 แนะนำบน Shopee", "💥 Deal เด็ดบน Shopee"]
LAZADA_INTROS = ["🛍️ ช้อปได้บน Lazada", "🔥 ราคาดีที่สุดบน Lazada", "🎯 แนะนำบน Lazada", "💥 Deal เด็ดบน Lazada"]

def get_product_comments():
    """comments สินค้าหมุนเวียน แยก Shopee / Lazada คนละ comment + หมุน intro"""
    p = get_rotating_product()
    if not p:
        return []
    bkk = timezone(timedelta(hours=7))
    now = datetime.now(bkk)
    vi = (now.timetuple().tm_yday + now.hour) % len(SHOPEE_INTROS)
    desc_line = f"\n✨ {p['desc']}" if p.get("desc") else ""
    comments = []
    if p.get("shopee") and "xxx" not in str(p["shopee"]):
        comments.append(f"{SHOPEE_INTROS[vi]}: {p['name']}{desc_line}\n→ {p['shopee']}")
    if p.get("lazada") and "xxx" not in str(p["lazada"]):
        comments.append(f"{LAZADA_INTROS[vi]}: {p['name']}{desc_line}\n→ {p['lazada']}")
    return comments
