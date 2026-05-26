# -*- coding: utf-8 -*-
"""fb_insights.py — ดึง engagement จากทุก Facebook page แล้ววิเคราะห์"""

import os, sys, io, requests, csv
from datetime import datetime, timezone, timedelta
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ─────────────────────────────────────────────────────────────────
# CONFIG — ใส่ token ตรงนี้ถ้าไม่ได้ set env vars
# หรือ run: $env:KRAM_PAGE_ACCESS_TOKEN = "xxx" ใน PowerShell ก่อน
# ─────────────────────────────────────────────────────────────────
try:
    from config import PAGE_ACCESS_TOKEN as _ROCKET_TOKEN
except ImportError:
    _ROCKET_TOKEN = ""

PAGES = {
    "Rocket21": {
        "page_id": "111830598532037",
        "token":   os.environ.get("PAGE_ACCESS_TOKEN", _ROCKET_TOKEN),
    },
    "กรามค้าง": {
        "page_id": "116701184708556",
        "token":   os.environ.get("KRAM_PAGE_ACCESS_TOKEN", ""),
    },
    "ส้มตำคุณอร": {
        "page_id": "554501167740603",
        "token":   os.environ.get("SOMTAM_PAGE_ACCESS_TOKEN", ""),
    },
    "ChowChow": {
        "page_id": "102319399434080",
        "token":   os.environ.get("CHOWCHOW_PAGE_ACCESS_TOKEN", ""),
    },
}

LIMIT     = 50   # จำนวนโพสต่อเพจ
BKK_TZ    = timezone(timedelta(hours=7))
API_VER   = "v21.0"

# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────

def parse_time(iso_str):
    """ISO 8601 → datetime BKK"""
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt.astimezone(BKK_TZ)


def time_slot(dt):
    h = dt.hour
    if h < 10:   return "morning (00-09)"
    if h < 16:   return "noon    (10-15)"
    if h < 21:   return "evening (16-20)"
    return              "late    (21+)  "


def content_format(message):
    """ตรวจจับ format จาก message text"""
    if not message:
        return "no_text"
    if "▪️" in message or "▪" in message:
        return "bullet_narrative"
    if any(c in message for c in ("✅", "❌")):
        return "false_flip"
    if "ก่อน" in message and "หลัง" in message:
        return "before_after"
    if message.count("•") >= 2 or message.count("-") >= 3:
        return "list"
    return "paragraph"


def somtam_content_type(message):
    """ตรวจจับ content type เพจส้มตำจากข้อความ"""
    if not message:
        return "unknown"
    kw = {
        "ช็อกเผ็ด":   ["เผ็ด", "น้ำตา", "หน้าแดง", "เหงื่อ", "ช็อก"],
        "ติดใจ":      ["ติดใจ", "อยากกลับ", "สั่งซ้ำ"],
        "งงแต่กิน":   ["งง", "ไม่รู้", "ไม่เข้าใจ"],
        "ไม่คาดหวัง": ["ไม่คิด", "ไม่คาด", "แปลกใจ", "เซอร์ไพรส์"],
        "กลับมาอีก":  ["กลับมา", "มาอีก", "regular"],
    }
    for t, words in kw.items():
        if any(w in message for w in words):
            return t
    return "other"


def fetch_post_comments(post_id, token):
    """ดึง top-level comments เพื่อนับ organic (กรอง affiliate bot ออก)
    affiliate comments มาจาก page เอง → `from.id` == page_id
    """
    url = f"https://graph.facebook.com/{API_VER}/{post_id}/comments"
    params = {
        "fields":       "id,from,message",
        "limit":        25,
        "access_token": token,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        return data.get("data", [])
    except Exception:
        return []


def fetch_posts(page_id, token, limit=LIMIT):  # noqa: redefined below
    """ดึง posts พร้อม engagement fields — page_id ใช้กรอง affiliate comments"""
    if not token:
        return None, "token ว่าง — ใส่ใน env vars หรือบรรทัด PAGES ด้านบน"

    fields = ",".join([
        "id", "message", "created_time",
        "likes.summary(true).limit(0)",
        "comments.summary(true).limit(0)",
        "shares",
        "reactions.summary(true).limit(0)",
    ])
    url = f"https://graph.facebook.com/{API_VER}/{page_id}/posts"
    params = {
        "fields":       fields,
        "limit":        limit,
        "access_token": token,
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        if "error" in data:
            return None, data["error"].get("message", str(data["error"]))
        return data.get("data", []), None
    except Exception as e:
        return None, str(e)


# ─────────────────────────────────────────────────────────────────
# ANALYSIS
# ─────────────────────────────────────────────────────────────────

def analyze_page(name, posts, page_id="", token=""):
    """วิเคราะห์ posts ของเพจเดียว → dict ผลลัพธ์"""
    records = []
    for p in posts:
        msg        = p.get("message", "")
        created    = parse_time(p["created_time"])
        reactions  = p.get("reactions", {}).get("summary", {}).get("total_count", 0)
        shares     = p.get("shares",    {}).get("count", 0)

        # กรอง affiliate bot comments ออก (from.id == page_id)
        all_cmts   = fetch_post_comments(p["id"], token)
        organic_cmts = [c for c in all_cmts
                        if c.get("from", {}).get("id") != page_id]
        comments   = len(organic_cmts)

        engage     = reactions + comments + shares
        records.append({
            "id":        p["id"],
            "date":      created.strftime("%Y-%m-%d %H:%M"),
            "slot":      time_slot(created),
            "format":    content_format(msg),
            "likes":     reactions,
            "comments":  comments,
            "shares":    shares,
            "engage":    engage,
            "msg":       (msg or "")[:80].replace("\n", " "),
        })

    if not records:
        return {}

    total      = len(records)
    avg_engage = sum(r["engage"] for r in records) / total

    # top 5 posts
    top5 = sorted(records, key=lambda r: r["engage"], reverse=True)[:5]

    # by time slot
    slot_data = defaultdict(list)
    for r in records:
        slot_data[r["slot"]].append(r["engage"])
    slot_avg = {s: sum(v)/len(v) for s, v in slot_data.items()}

    # by content format
    fmt_data = defaultdict(list)
    for r in records:
        fmt_data[r["format"]].append(r["engage"])
    fmt_avg = {f: (sum(v)/len(v), len(v)) for f, v in fmt_data.items()}

    return {
        "total":    total,
        "avg":      avg_engage,
        "top5":     top5,
        "slot_avg": slot_avg,
        "fmt_avg":  fmt_avg,
        "records":  records,
    }


# ─────────────────────────────────────────────────────────────────
# PRINT HELPERS
# ─────────────────────────────────────────────────────────────────

SEP  = "─" * 72
SEP2 = "═" * 72

def pr(s=""):
    print(s)

def print_page_summary(name, result):
    pr(SEP2)
    pr(f"  {name}  ({result['total']} โพส)")
    pr(SEP2)

    pr(f"\n  avg engagement / โพส : {result['avg']:.1f}")

    pr(f"\n  ── Time slot ──────────────────────────────")
    for slot, avg in sorted(result["slot_avg"].items(), key=lambda x: -x[1]):
        bar = "█" * int(avg)
        pr(f"  {slot}  avg {avg:5.1f}  {bar}")

    pr(f"\n  ── Content format ─────────────────────────")
    for fmt, (avg, cnt) in sorted(result["fmt_avg"].items(), key=lambda x: -x[1][0]):
        pr(f"  {fmt:<20} n={cnt:2d}  avg {avg:5.1f}")

    pr(f"\n  ── Top 5 โพส ──────────────────────────────")
    for i, r in enumerate(result["top5"], 1):
        pr(f"  {i}. [{r['date']}] engage={r['engage']:3d}  ❤️{r['likes']} 💬{r['comments']} 🔁{r['shares']}")
        pr(f"     {r['msg'][:70]}")
    pr()


def print_cross_page(all_results):
    pr(SEP2)
    pr("  CROSS-PAGE SUMMARY")
    pr(SEP2)
    pr(f"\n  {'เพจ':<16} {'avg engage':>12}  {'โพส':>6}")
    pr("  " + "─" * 38)
    for name, res in sorted(all_results.items(), key=lambda x: -x[1].get("avg", 0)):
        if res:
            pr(f"  {name:<16} {res['avg']:>12.1f}  {res['total']:>6}")

    # bullet vs paragraph cross-page
    pr(f"\n  ── Bullet vs Paragraph (รวมทุกเพจ) ────────")
    bucket = defaultdict(list)
    for res in all_results.values():
        if not res:
            continue
        for fmt, (avg, cnt) in res.get("fmt_avg", {}).items():
            bucket[fmt].append((avg, cnt))
    for fmt in ["bullet_narrative", "paragraph", "false_flip", "before_after", "list"]:
        if fmt in bucket:
            vals = bucket[fmt]
            overall_avg = sum(a*c for a, c in vals) / sum(c for _, c in vals)
            total_n     = sum(c for _, c in vals)
            pr(f"  {fmt:<20} n={total_n:2d}  avg {overall_avg:5.1f}")
    pr()


def save_csv(all_records, path="fb_insights_export.csv"):
    fields = ["page","date","slot","format","likes","comments","shares","engage","msg"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for name, records in all_records.items():
            for r in records:
                row = {"page": name}
                row.update({k: r[k] for k in fields if k != "page"})
                w.writerow(row)
    print(f"\n  CSV saved → {path}")


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def main():
    pr(SEP2)
    pr("  Facebook Engagement Insights")
    pr(f"  ดึง {LIMIT} โพสล่าสุดต่อเพจ  |  {datetime.now(BKK_TZ).strftime('%Y-%m-%d %H:%M')} BKK")
    pr(SEP2)

    all_results = {}
    all_records = {}

    for name, cfg in PAGES.items():
        pr(f"\n  ดึงข้อมูล {name}...")
        posts, err = fetch_posts(cfg["page_id"], cfg["token"])
        if err:
            pr(f"  ⚠️  {name}: {err}")
            all_results[name] = {}
            continue

        result = analyze_page(name, posts, page_id=cfg["page_id"], token=cfg["token"])
        all_results[name] = result
        all_records[name] = result.get("records", [])
        print_page_summary(name, result)

    print_cross_page(all_results)

    # save CSV รวมทุกเพจ
    flat = {n: r for n, r in all_records.items() if r}
    if flat:
        save_csv(flat)


if __name__ == "__main__":
    main()
