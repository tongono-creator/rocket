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

def get_standard_comments():
    """standard comments (website + Shopee Food)"""
    comments = [
        f"🔥 อยากรู้ว่าสินค้าไหนขายดีที่สุดบน Shopee ตอนนี้?\nดูอันดับสินค้าขายดีได้เลยที่ → {WEBSITE_URL}",
    ]
    if "วางลิงก์" not in SHOPEE_FOOD_URL:
        comments.append(f"🍜 สั่งอาหาร Shopee Food ลดเพิ่ม → {SHOPEE_FOOD_URL}")
    return comments

def get_product_comments():
    """comments สินค้าหมุนเวียน แยก Shopee / Lazada คนละ comment"""
    p = get_rotating_product()
    if not p:
        return []
    desc_line = f"\n✨ {p['desc']}" if p.get("desc") else ""
    comments = []
    if p.get("shopee") and "xxx" not in str(p["shopee"]):
        comments.append(f"🎯 {p['name']}{desc_line}\n🛒 Shopee → {p['shopee']}")
    if p.get("lazada") and "xxx" not in str(p["lazada"]):
        comments.append(f"🎯 {p['name']}{desc_line}\n🛍️ Lazada → {p['lazada']}")
    return comments
