# -*- coding: utf-8 -*-
"""วาง short-lived Threads token แล้วรัน script นี้ จะได้ long-lived token"""

import requests

APP_ID = "2463163784112591"
APP_SECRET = "4e85a97bc5f6aaf8b0bcb8b6d82b8a43"

short_token = input("วาง Threads token ที่นี่: ").strip()

# Exchange for long-lived token
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
    print(f"\nLong-lived token (60 วัน):\n{long_token}")

    # Get Threads User ID
    me = requests.get(
        "https://graph.threads.net/v1.0/me",
        params={"fields": "id,username", "access_token": long_token}
    )
    me_data = me.json()
    print(f"\nThreads User ID: {me_data.get('id')}")
    print(f"Username: {me_data.get('username')}")
else:
    print(f"Error: {data}")
