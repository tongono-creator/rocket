# -*- coding: utf-8 -*-
"""schedule_reels.py - Automates uploading and scheduling Facebook Reels for Rocket21"""

import sys
import io
import os
import re
import time
import requests
from datetime import datetime, timezone, timedelta

# Redirect stdout for Thai character support in Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Import config
try:
    import config
    PAGE_ID = config.PAGE_ID
    PAGE_ACCESS_TOKEN = config.PAGE_ACCESS_TOKEN
except ImportError:
    print("Error: Could not import config.py. Make sure you run from D:\\Projects\\rocket-facebook-page")
    sys.exit(1)

SHORTS_DIR = r"D:\Projects\Video\videos\sino_japanese_wars\07_output\shorts"
CAPTIONS_FILE = os.path.join(SHORTS_DIR, "caption_facebook.txt")
API_VERSION = "v25.0"

def parse_captions(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    pattern = r'(EP\d+)\n(.*?)(?=\nEP\d+|\Z)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    captions = {}
    for ep, text in matches:
        text = text.strip()
        captions[ep] = text
    return captions

def get_scheduled_timestamp(time_str):
    bkk_tz = timezone(timedelta(hours=7))
    dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=bkk_tz)
    return int(dt.timestamp()), dt.strftime("%Y-%m-%d %H:%M:%S BKK")

def upload_and_schedule_reel(episode_num, file_path, caption, timestamp, formatted_time):
    print(f"\n==================================================")
    print(f"Starting upload for {episode_num}...")
    print(f"File: {file_path}")
    print(f"Schedule: {formatted_time} (Timestamp: {timestamp})")
    print(f"Caption: {caption.splitlines()[0]}...")
    print(f"==================================================")
    
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist.")
        return False
        
    file_size = os.path.getsize(file_path)
    
    # Step 1: Initialize upload session
    init_url = f"https://graph.facebook.com/{API_VERSION}/{PAGE_ID}/video_reels"
    init_payload = {
        "upload_phase": "start",
        "access_token": PAGE_ACCESS_TOKEN
    }
    
    try:
        r_init = requests.post(init_url, data=init_payload, timeout=30)
        init_res = r_init.json()
        if "video_id" not in init_res:
            print(f"Initialization failed: {init_res}")
            return False
        
        video_id = init_res["video_id"]
        upload_url = init_res.get("upload_url")
        print(f"Initialization successful. Video ID: {video_id}")
        
        # Step 2: Upload raw video data
        if not upload_url:
            upload_url = f"https://rupload.facebook.com/video-upload/{API_VERSION}/{video_id}"
            
        print(f"Uploading file bytes ({file_size} bytes) to {upload_url}...")
        
        headers = {
            "Authorization": f"OAuth {PAGE_ACCESS_TOKEN}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": "application/octet-stream"
        }
        
        with open(file_path, "rb") as f:
            r_upload = requests.post(upload_url, headers=headers, data=f, timeout=120)
            
        upload_res = r_upload.json()
        print(f"Upload response: {upload_res}")
            
        # Step 3: Publish / Schedule the reel
        publish_url = f"https://graph.facebook.com/{API_VERSION}/{PAGE_ID}/video_reels"
        publish_payload = {
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "SCHEDULED",
            "scheduled_publish_time": str(timestamp),
            "description": caption,
            "access_token": PAGE_ACCESS_TOKEN
        }
        
        print("Finalizing scheduling via Graph API...")
        r_pub = requests.post(publish_url, data=publish_payload, timeout=30)
        pub_res = r_pub.json()
        
        if "success" in pub_res and pub_res["success"]:
            print(f"SUCCESS: {episode_num} scheduled successfully! ID: {pub_res.get('video_id', video_id)}")
            return pub_res
        elif "id" in pub_res:
            print(f"SUCCESS: {episode_num} scheduled successfully! ID: {pub_res['id']}")
            return pub_res
        else:
            print(f"Publish failed: {pub_res}")
            return False
            
    except Exception as e:
        print(f"Exception occurred during scheduling: {e}")
        return False

def main():
    captions = parse_captions(CAPTIONS_FILE)
    
    episodes = [
        {"name": "EP02", "file": "EP02.mp4", "time_str": "2026-06-24 09:00:00"},
        {"name": "EP03", "file": "EP03.mp4", "time_str": "2026-06-24 11:30:00"},
        {"name": "EP04", "file": "EP04.mp4", "time_str": "2026-06-24 14:00:00"},
        {"name": "EP05", "file": "EP05.mp4", "time_str": "2026-06-24 16:30:00"},
        {"name": "EP06", "file": "EP06.mp4", "time_str": "2026-06-24 19:00:00"},
        {"name": "EP07", "file": "EP07.mp4", "time_str": "2026-06-24 21:30:00"},
        
        {"name": "EP08", "file": "EP08.mp4", "time_str": "2026-06-25 09:00:00"},
        {"name": "EP09", "file": "EP09.mp4", "time_str": "2026-06-25 11:00:00"},
        {"name": "EP10", "file": "EP10.mp4", "time_str": "2026-06-25 13:00:00"},
        {"name": "EP11", "file": "EP11.mp4", "time_str": "2026-06-25 15:00:00"},
        {"name": "EP12", "file": "EP12.mp4", "time_str": "2026-06-25 17:00:00"},
        {"name": "EP13", "file": "EP13.mp4", "time_str": "2026-06-25 19:00:00"},
        {"name": "EP14", "file": "EP14.mp4", "time_str": "2026-06-25 21:00:00"},
    ]
    
    results = {}
    for ep in episodes:
        ep_name = ep["name"]
        file_name = ep["file"]
        file_path = os.path.join(SHORTS_DIR, file_name)
        caption = captions.get(ep_name)
        
        if not caption:
            print(f"Error: Caption for {ep_name} not found in caption_facebook.txt")
            continue
            
        timestamp, formatted_time = get_scheduled_timestamp(ep["time_str"])
        
        success = upload_and_schedule_reel(ep_name, file_path, caption, timestamp, formatted_time)
        if success:
            results[ep_name] = {
                "status": "SUCCESS",
                "scheduled_time": formatted_time,
                "timestamp": timestamp,
                "response": success
            }
        else:
            results[ep_name] = {
                "status": "FAILED",
                "scheduled_time": formatted_time,
                "timestamp": timestamp
            }
            print(f"\nScheduling halted due to failure on {ep_name}.")
            break
            
        print("Waiting 15 seconds before next upload to prevent rate limits...")
        time.sleep(15)

    print("\n==============================================")
    print("Scheduling Summary:")
    for ep_name, info in results.items():
        print(f"{ep_name}: {info['status']} | {info['scheduled_time']}")
    print("==============================================")

if __name__ == "__main__":
    main()
