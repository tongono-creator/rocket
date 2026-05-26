# -*- coding: utf-8 -*-
"""รัน script นี้เพื่อ save long-lived Threads token ลงไฟล์"""
import requests, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

APP_ID = "2463163784112591"
APP_SECRET = "4e85a97bc5f6aaf8b0bcb8b6d82b8a43"

short_token = input("วาง Threads token ที่นี่: ").strip()

resp = requests.get(
    "https://graph.threads.net/access_token",
    params={
        "grant_type": "th_exchange_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "access_token": short_token,
    }
)
data = resp.json()

if "access_token" in data:
    long_token = data["access_token"]
    with open("threads_token.txt", "w") as f:
        f.write(long_token)
    print(f"บันทึกแล้วที่: threads_token.txt")
    print(f"Token: {long_token}")
else:
    print(f"Error: {data}")
