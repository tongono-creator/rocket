# -*- coding: utf-8 -*-
"""reels_prototype.py — สร้าง Reel นิทานคุณธรรม: รูปการ์ตูน + text overlay"""

import sys, io, os, base64, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip
from moviepy.video.fx import CrossFadeIn, CrossFadeOut
import numpy as np

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
IMAGE_MODEL    = "gemini-3-pro-image-preview"
TEXT_MODEL = "gemini-1.5-flash"
OUTPUT_DIR     = "output"
FONT_PATH      = r"C:\Windows\Fonts\ARIALUNI.TTF"
SCENE_DURATION = 4   # seconds per scene
VIDEO_W, VIDEO_H = 1080, 1350  # 4:5 portrait

os.makedirs(OUTPUT_DIR, exist_ok=True)
client = genai.Client(api_key=GOOGLE_API_KEY)

# ─── Themes ──────────────────────────────────────────────────────
STORY_THEMES = [
    # การเงิน
    "ชายหนุ่มที่ใช้เงินเก่งแต่เก็บเงินไม่เป็น จนวันหนึ่งเขาค้นพบความจริงที่เปลี่ยนชีวิต",
    "หญิงสาวที่กู้หนี้ซื้อของแบรนด์เนม แต่สุดท้ายพบว่าสิ่งที่แท้จริงอยู่ตรงหน้า",
    "คนที่ไม่เคยออมเงิน กับวันที่ต้องเจอเหตุฉุกเฉิน",
    # ออฟฟิศ
    "ลูกน้องที่โดนบอสกดขี่ทุกวัน แต่เลือกที่จะทนและพัฒนาตัวเองอย่างเงียบๆ",
    "พนักงานที่ถูกมองข้ามมา 5 ปี จนถึงวันที่ทุกอย่างเปลี่ยน",
    "หัวหน้างานที่เข้มงวด กับลูกน้องใหม่ที่ไม่ยอมแพ้",
    # ครอบครัว
    "พ่อที่ทำงาน 2 งานเพื่อลูก โดยที่ลูกไม่เคยรู้",
    "แม่ที่เสียสละทุกอย่าง แต่ไม่เคยบ่น",
    "ลูกที่เพิ่งเข้าใจว่าพ่อแม่ทำอะไรไปเพื่ออะไร",
]

def get_theme():
    from datetime import datetime, timezone, timedelta
    bkk = timezone(timedelta(hours=7))
    day = datetime.now(bkk).timetuple().tm_yday
    return STORY_THEMES[(day - 1) % len(STORY_THEMES)]

def generate_story(theme):
    print(f"Generating story: {theme}")
    prompt = (
        f"เขียนนิทานคุณธรรมภาษาไทยสั้นๆ เรื่อง: {theme}\n"
        "แบ่งเป็น 4 scene เท่านั้น\n"
        "แต่ละ scene มี:\n"
        "- caption: ข้อความสั้น 1-2 บรรทัด (ไม่เกิน 40 ตัวอักษร/บรรทัด) สำหรับแสดงบนหน้าจอ\n"
        "- image_desc: คำอธิบายรูปการ์ตูนภาษาอังกฤษ สำหรับ generate รูป\n"
        "ตอบเป็น JSON array เท่านั้น รูปแบบ:\n"
        '[{"scene": 1, "caption": "...", "image_desc": "..."}, ...]'
    )
    resp = client.models.generate_content(model=TEXT_MODEL, contents=prompt)
    text = resp.text.strip()
    # strip markdown code block
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())

def generate_scene_image(scene_num, image_desc, caption):
    print(f"  Scene {scene_num}: generating image...")
    prompt = (
        f"Thai cartoon illustration, simple clean style. "
        f"Scene: {image_desc}. "
        f"Warm colors, expressive characters, no text in image. "
        f"9:16 portrait, fill edge to edge, no border, no white frame."
    )
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=IMAGE_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])
            )
            for part in resp.candidates[0].content.parts:
                if part.inline_data:
                    data = part.inline_data.data
                    if isinstance(data, str):
                        data = base64.b64decode(data)
                    path = os.path.join(OUTPUT_DIR, f"scene_{scene_num}.png")
                    with open(path, "wb") as f:
                        f.write(data)
                    print(f"  Scene {scene_num} saved: {path}")
                    return path
        except Exception as e:
            print(f"  Scene {scene_num} attempt {attempt+1} failed: {str(e)[:80]}")
            if attempt < 2:
                time.sleep(10)
    raise RuntimeError(f"Scene {scene_num} image generation failed")

def add_text_overlay(img_path, caption, scene_num):
    """Add caption text at bottom of image"""
    img = Image.open(img_path).convert("RGBA")
    img = img.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Dark gradient bar at bottom
    bar_h = int(VIDEO_H * 0.28)
    for y in range(bar_h):
        alpha = int(200 * (y / bar_h))
        draw.rectangle([(0, VIDEO_H - bar_h + y), (VIDEO_W, VIDEO_H - bar_h + y + 1)],
                       fill=(0, 0, 0, alpha))

    img = Image.alpha_composite(img, overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Text
    font_large = ImageFont.truetype(FONT_PATH, 52)
    font_scene = ImageFont.truetype(FONT_PATH, 32)

    # Scene number
    draw.text((40, VIDEO_H - bar_h + 20), f"Scene {scene_num}/4",
              font=font_scene, fill=(200, 200, 200))

    # Caption — wrap lines
    lines = caption.split("\n")
    y_start = VIDEO_H - bar_h + 60
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_large)
        w = bbox[2] - bbox[0]
        x = (VIDEO_W - w) // 2
        # shadow
        draw.text((x + 2, y_start + 2), line, font=font_large, fill=(0, 0, 0))
        draw.text((x, y_start), line, font=font_large, fill=(255, 255, 255))
        y_start += 65

    out_path = os.path.join(OUTPUT_DIR, f"scene_{scene_num}_overlay.png")
    img.save(out_path)
    return out_path

def make_ken_burns_clip(img_path, duration=SCENE_DURATION, fps=24, zoom_in=True):
    """Slow zoom in or out (Ken Burns effect) using numpy frame generation"""
    img = Image.open(img_path).convert("RGB").resize((VIDEO_W, VIDEO_H), Image.LANCZOS)
    img_np = np.array(img)

    n_frames = int(duration * fps)
    zoom_start = 1.0 if zoom_in else 1.08
    zoom_end   = 1.08 if zoom_in else 1.0

    def make_frame(t):
        progress = t / duration
        zoom = zoom_start + (zoom_end - zoom_start) * progress
        new_w = int(VIDEO_W * zoom)
        new_h = int(VIDEO_H * zoom)
        resized = np.array(Image.fromarray(img_np).resize((new_w, new_h), Image.LANCZOS))
        x0 = (new_w - VIDEO_W) // 2
        y0 = (new_h - VIDEO_H) // 2
        return resized[y0:y0 + VIDEO_H, x0:x0 + VIDEO_W]

    return ImageClip(make_frame, duration=duration, ismask=False)

def create_video(scene_images, output_name="reel_prototype.mp4"):
    FADE = 0.5  # crossfade seconds
    clips = []
    for i, img_path in enumerate(scene_images):
        zoom_in = (i % 2 == 0)  # alternate zoom direction
        clip = make_ken_burns_clip(img_path, duration=SCENE_DURATION, zoom_in=zoom_in)
        # fade in/out for crossfade
        clip = clip.with_effects([CrossFadeIn(FADE), CrossFadeOut(FADE)])
        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose", padding=-FADE)
    out_path = os.path.join(OUTPUT_DIR, output_name)
    final.write_videofile(out_path, fps=24, codec="libx264",
                          audio=False, logger=None)
    print(f"\nVideo saved: {out_path}")
    return out_path

if __name__ == "__main__":
    theme = get_theme()
    print(f"Theme: {theme}\n")

    scenes = generate_story(theme)
    print(f"Story generated: {len(scenes)} scenes\n")
    for s in scenes:
        print(f"  Scene {s['scene']}: {s['caption']}")

    print()
    scene_images = []
    for s in scenes:
        img_path = generate_scene_image(s["scene"], s["image_desc"], s["caption"])
        overlay_path = add_text_overlay(img_path, s["caption"], s["scene"])
        scene_images.append(overlay_path)
        time.sleep(3)

    video_path = create_video(scene_images)
    print(f"\nDone! Open: {video_path}")
