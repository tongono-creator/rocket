# -*- coding: utf-8 -*-
"""reply_threads.py — ตรวจสอบและตอบกลับคอมเมนต์บน Threads ด้วย Gemini อัจฉริยะ"""

import sys, io, os, time, random, re, requests
from google import genai

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# === CONFIG (รับจาก env vars หรือ config.py) ===
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID      = os.environ.get("THREADS_USER_ID",      "")
GOOGLE_API_KEY       = os.environ.get("GOOGLE_API_KEY",       "")
TEXT_MODELS          = ["gemini-2.5-flash", "gemini-3.5-flash"]
HISTORY_FILE         = os.path.join(os.path.dirname(__file__), "replied_comments.txt")

# fallback รันบน local ใช้ config.py
if not THREADS_ACCESS_TOKEN or not THREADS_USER_ID or not GOOGLE_API_KEY:
    try:
        import config
        THREADS_ACCESS_TOKEN = getattr(config, "THREADS_ACCESS_TOKEN", THREADS_ACCESS_TOKEN)
        THREADS_USER_ID      = getattr(config, "THREADS_USER_ID",      THREADS_USER_ID)
        GOOGLE_API_KEY       = getattr(config, "GOOGLE_API_KEY",       GOOGLE_API_KEY)
    except ImportError:
        pass

# เช็คค่า CONFIG หลัก
if not THREADS_ACCESS_TOKEN or not THREADS_USER_ID:
    print("Error: THREADS_ACCESS_TOKEN หรือ THREADS_USER_ID ว่างเปล่า")
    sys.exit(1)

client = genai.Client(api_key=GOOGLE_API_KEY, http_options={'timeout': 90.0})

def load_replied_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}

def save_replied_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        for cid in sorted(history):
            f.write(f"{cid}\n")

def get_my_username():
    """ดึง Username ของเพจเรา"""
    url = f"https://graph.threads.net/v1.0/me?fields=username&access_token={THREADS_ACCESS_TOKEN}"
    try:
        resp = requests.get(url, timeout=15)
        result = resp.json()
        if "username" in result:
            return result["username"]
        print(f"Failed to get username: {result}")
    except Exception as e:
        print(f"Error getting username: {e}")
    return ""

def get_recent_posts():
    """ดึงโพสต์ล่าสุด 5 โพสต์"""
    url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads?fields=id,text,timestamp&limit=5&access_token={THREADS_ACCESS_TOKEN}"
    try:
        resp = requests.get(url, timeout=15)
        result = resp.json()
        if "data" in result:
            return result["data"]
        print(f"Failed to get posts: {result}")
    except Exception as e:
        print(f"Error getting posts: {e}")
    return []

def get_post_replies(post_id):
    """ดึงคอมเมนต์ (replies) ใต้โพสต์"""
    url = f"https://graph.threads.net/v1.0/{post_id}/replies?fields=id,text,username,timestamp&access_token={THREADS_ACCESS_TOKEN}"
    try:
        resp = requests.get(url, timeout=15)
        result = resp.json()
        if "data" in result:
            return result["data"]
        print(f"Failed to get replies for {post_id}: {result}")
    except Exception as e:
        print(f"Error getting replies for {post_id}: {e}")
    return []

def is_valid_comment(text):
    """กรองคอมเมนต์สั้น แท็กเพื่อน หรือไม่มีเนื้อหา"""
    if not text:
        return False
    clean = text.strip()
    # ข้ามพวกแท็กเพื่อน (เช่น @username หรือเริ่มด้วย @)
    if clean.startswith("@") or re.match(r'^@\w+\s*$', clean):
        return False
    # ข้ามคอมเมนต์สั้นเกินไป เช่น "555", "โอเค", "ดี" หรืออีโมจิ 1-2 ตัว
    if len(clean) < 4:
        return False
    # ข้ามคอมเมนต์ที่มีแค่อีโมจิล้วนๆ
    # (ถ้ามีแต่สัญลักษณ์และไม่มีภาษาไทยหรืออังกฤษเลย)
    if not re.search(r'[a-zA-Zก-๙0-9]', clean):
        return False
    return True

def generate_reply(post_text, username, comment_text):
    """ใช้ Gemini คิดคำตอบ"""
    # สุ่มเพศในการตอบ: ผู้หญิง (ค่ะ/คะ/พี่/เรา) หรือ ผู้ชาย (ครับ/ผม/พี่)
    gender = random.choice(["male", "female"])
    if gender == "male":
        gender_instruction = "ตอบกลับด้วยบุคลิกผู้ชายแอดมินเพจ (ใช้สรรพนามแทนตัวว่า 'ผม' หรือ 'พี่' และใช้คำลงท้ายว่า 'ครับ' เท่านั้น ห้ามลืมเด็ดขาด)"
    else:
        gender_instruction = "ตอบกลับด้วยบุคลิกผู้หญิงแอดมินเพจ (ใช้สรรพนามแทนตัวว่า 'พี่' หรือ 'เรา' และใช้คำลงท้ายว่า 'ค่ะ' หรือ 'คะ' เท่านั้น ห้ามลืมเด็ดขาด)"

    prompt = (
        "คุณคือแอดมินเพจ Rocket21 (เพจเกี่ยวกับวัยทำงาน ชีวิตมนุษย์ออฟฟิศ คำคมตลกสัจธรรมชีวิต การเงินเป็นกันเองมาก)\n"
        f"บุคลิกภาพเฉพาะกิจในรอบนี้: {gender_instruction}\n"
        f"โพสต์หลักมีข้อความดังนี้:\n\"\"\"\n{post_text}\n\"\"\"\n\n"
        f"มีลูกเพจชื่อ @{username} เข้ามาคอมเมนต์ใต้โพสต์นี้ว่า:\n\"\"\"\n{comment_text}\n\"\"\"\n\n"
        "กรุณาร่างข้อความตอบกลับคอมเมนต์นี้อย่างเป็นกันเอง ขำขัน ประชดประชันชีวิตเล็กน้อย หรือให้กำลังใจสไตล์คนสู้ชีวิต\n"
        "กฎในการตอบ:\n"
        "1. ตอบสั้นและเป็นกันเอง 1-2 ประโยคเท่านั้น (ห้ามเยิ่นเย้อหรือยาวเกินไป)\n"
        "2. ห้ามใช้ markdown ** ตัวหนา หรือเครื่องหมายอัญประกาศ/คำพูดใดๆ ในผลลัพธ์\n"
        "3. ห้ามตอบเป็นทางการเด็ดขาด ให้ตอบเหมือนรุ่นพี่ออฟฟิศคุยกับรุ่นน้อง\n"
        "4. ตอบกลับเป็นภาษาไทยเท่านั้น"
    )
    for model in TEXT_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            result = resp.text.strip()
            # ทำความสะอาดผลลัพธ์
            result = result.strip('"\'“”‘’')
            return result
        except Exception as e:
            print(f"[{model}] reply generation failed: {e}")
    return "สู้ๆ ครับมนุษย์ออฟฟิศอย่างพวกเรา 😂✌️"

def post_reply_comment(text, reply_to_id):
    """ส่งโพสต์ตอบกลับคอมเมนต์"""
    data = {
        "media_type": "TEXT",
        "text": text,
        "access_token": THREADS_ACCESS_TOKEN,
        "reply_to_id": reply_to_id
    }
    try:
        resp = requests.post(
            f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads",
            data=data,
            timeout=15
        )
        container_id = resp.json().get("id")
        if not container_id:
            print(f"Error creating reply container: {resp.json()}")
            return None
        
        # ดีเลย์สั้นๆ ป้องกันปัญหาการโพสต์เร็วไป
        time.sleep(3)
        
        resp2 = requests.post(
            f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish",
            data={"creation_id": container_id, "access_token": THREADS_ACCESS_TOKEN},
            timeout=15
        )
        result = resp2.json()
        return result.get("id")
    except Exception as e:
        print(f"Error posting reply: {e}")
    return None

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Run without posting reply or saving history")
    args = parser.parse_args()

    print("=== Threads Auto-Reply System ===")
    
    my_username = get_my_username()
    if my_username:
        print(f"My Page Username: @{my_username}")
    else:
        print("Warning: Could not fetch page username, will proceed cautiously")

    history = load_replied_history()
    print(f"Loaded {len(history)} replied comment history.")

    posts = get_recent_posts()
    if not posts:
        print("No recent posts found.")
        sys.exit(0)

    reply_count = 0
    max_replies_per_run = 3  # จำกัดตอบสูงสุด 3 คอมเมนต์ต่อรอบรัน
    reply_probability = 0.4  # โอกาสสุ่มตอบ 40%
    
    new_replies_made = []

    for post in posts:
        post_id = post["id"]
        post_text = post.get("text", "")
        print(f"\nChecking Post [{post_id}]: \"{post_text[:50]}...\"")
        
        replies = get_post_replies(post_id)
        if not replies:
            print("  No comments found under this post.")
            continue
            
        print(f"  Found {len(replies)} total comments.")
        
        for reply in replies:
            reply_id = reply["id"]
            commenter = reply.get("username", "")
            comment_text = reply.get("text", "")
            
            # 1. ข้ามถ้าเคยตอบไปแล้ว
            if reply_id in history:
                continue
                
            # 2. ข้ามคอมเมนต์ของตัวเราเอง (แอดมินตอบคอมเมนต์)
            if commenter and commenter == my_username:
                continue
                
            # 3. ข้ามคอมเมนต์ที่ไม่ผ่านเกณฑ์ความยาว/แท็กเพื่อน
            if not is_valid_comment(comment_text):
                print(f"  - Skip trivial comment from @{commenter}: \"{comment_text}\"")
                continue
                
            print(f"  - New valid comment from @{commenter}: \"{comment_text}\"")
            
            # 4. สุ่มตามสัดส่วนความน่าจะเป็น (เช่น 40%)
            if random.random() > reply_probability:
                print("    [Chance skipped] Random selection decided not to reply to this one.")
                # เพื่อป้องกันไม่ให้มาสุ่มซ้ำคอมเมนต์เดิมรอบถัดไปและดูเหมือนแช่แข็ง ให้ถือว่าประมวลผลแล้ว
                if not args.dry_run:
                    history.add(reply_id)
                continue

            # 5. เจนคำตอบด้วย AI
            print("    Generating AI reply...")
            reply_msg = generate_reply(post_text, commenter, comment_text)
            print(f"    AI Reply message: \"{reply_msg}\"")
            
            # 6. ตอบกลับคอมเมนต์
            if args.dry_run:
                print("    [Dry-run] Simulated reply. Not posting to API.")
            else:
                sent_id = post_reply_comment(reply_msg, reply_to_id=reply_id)
                if sent_id:
                    print(f"    Reply posted successfully! ID: {sent_id}")
                    history.add(reply_id)
                    reply_count += 1
                else:
                    print("    Failed to post reply.")
            
            # เช็คว่าเต็มโควตาการตอบในรอบนี้หรือยัง
            if reply_count >= max_replies_per_run:
                print("\nReached max replies quota per run. Stopping.")
                break
                
        if reply_count >= max_replies_per_run:
            break

    if not args.dry_run and reply_count > 0:
        save_replied_history(history)
        print(f"\nCompleted! Saved updated history with {reply_count} new replies.")
    else:
        print("\nFinished (No actual replies posted or run under --dry-run).")
