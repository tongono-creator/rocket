# affiliate_utils.py — อ่าน product links จาก affiliate_products.xlsx
import os
from datetime import datetime, timezone, timedelta

WEBSITE_URL = "https://shopee-ranking.vercel.app/"
SHOPEE_URL  = "https://s.shopee.co.th/7VDLdM5w8I"
LAZADA_URL  = "https://s.lazada.co.th/s.Z69ao3?c=b"

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
            if str(active).strip().lower() == "yes" and shopee and "xxx" not in str(shopee):
                products.append({"name": name, "shopee": shopee, "lazada": lazada})
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
    """3 comments มาตรฐาน (website / Shopee / Lazada)"""
    return [
        f"🔥 อยากรู้ว่าสินค้าไหนขายดีที่สุดบน Shopee ตอนนี้?\nดูอันดับสินค้าขายดีได้เลยที่ → {WEBSITE_URL}",
        f"🛒 ช้อปบน Shopee คลิกเลย → {SHOPEE_URL}",
        f"🛍️ ช้อปบน Lazada คลิกเลย → {LAZADA_URL}",
    ]

def get_product_comment():
    """comment สินค้าหมุนเวียน (ถ้ามีใน Excel)"""
    p = get_rotating_product()
    if not p:
        return None
    return (
        f"🎯 สินค้าแนะนำวันนี้: {p['name']}\n"
        f"Shopee → {p['shopee']}\n"
        f"Lazada → {p['lazada']}"
    )
