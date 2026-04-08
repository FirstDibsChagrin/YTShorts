import os
import re
import random
import textwrap
import tempfile
from io import BytesIO
from datetime import datetime

import feedparser
import requests
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont

from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_audioclips,
    concatenate_videoclips,
)

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


WIDTH = 1080
HEIGHT = 1920
FPS = 24
OUTPUT_DIR = "output"

PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
GOOGLE_TRENDS_RSS_URL = os.environ["GOOGLE_TRENDS_RSS_URL"]
YT_CLIENT_ID = os.environ["YT_CLIENT_ID"]
YT_CLIENT_SECRET = os.environ["YT_CLIENT_SECRET"]
YT_REFRESH_TOKEN = os.environ["YT_REFRESH_TOKEN"]

os.makedirs(OUTPUT_DIR, exist_ok=True)


def clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_topic(text: str) -> str:
    text = clean_html(text)
    text = text.replace(" - Google Trends", "").strip()
    return text


def fetch_trends(limit=3):
    feed = feedparser.parse(GOOGLE_TRENDS_RSS_URL)
    if not feed.entries:
        raise RuntimeError("No trends found in the RSS feed.")

    topics = []
    seen = set()

    for entry in feed.entries:
        title = clean_topic(entry.get("title", ""))
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)

        summary = clean_html(entry.get("summary", ""))
        topics.append({
            "title": title,
            "summary": summary
        })

        if len(topics) >= limit:
            break

    if len(topics) < limit:
        raise RuntimeError("Not enough trends found in the RSS feed.")

    return topics


def make_voice(text: str, out_path: str):
    tts = gTTS(text=text, lang="en")
    tts.save(out_path)


def download_binary(url: str) -> bytes:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content


def search_pexels_video(query: str):
    headers = {"Authorization": PEXELS_API_KEY}
    r = requests.get(
        "https://api.pexels.com/videos/search",
        headers=headers,
        params={
            "query": query,
            "per_page": 10,
            "orientation": "portrait"
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()

    for item in data.get("videos", []):
        files = item.get("video_files", [])
        files = sorted(
            files,
            key=lambda x: x.get("width", 0) * x.get("height", 0),
            reverse=True
        )
        for f in files:
            link = f.get("link")
            if link:
                return link
    return None


def search_pexels_photo(query: str):
    headers = {"Authorization": PEXELS_API_KEY}
    r = requests.get(
        "https://api.pexels.com/v1/search",
        headers=headers,
        params={
            "query": query,
            "per_page": 10,
            "orientation": "portrait"
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    photos = data.get("photos", [])
    if not photos:
        return None

    src = photos[0].get("src", {})
    return src.get("large2x") or src.get("original")


def fit_clip_to_vertical(clip):
    clip = clip.resize(height=HEIGHT)
    if clip.w < WIDTH:
        clip = clip.resize(width=WIDTH)

    clip = clip.crop(
        x_center=clip.w / 2,
        y_center=clip.h / 2,
        width=WIDTH,
        height=HEIGHT
    )
    return clip


def make_background_clip(query: str, duration: float, idx: int):
    video_url = search_pexels_video(query)
    if video_url:
        video_path = os.path.join(OUTPUT_DIR, f"bg_{idx}.mp4")
        with open(video_path, "wb") as f:
            f.write(download_binary(video_url))

        clip = VideoFileClip(video_path)
        clip = fit_clip_to_vertical(clip)

        if clip.duration >= duration:
            clip = clip.subclip(0, duration)
        else:
            loops = []
            remaining = duration
            while remaining > 0:
                seg = clip.subclip(0, min(clip.duration, remaining))
                loops.append(seg)
                remaining -= seg.duration
            clip = concatenate_videoclips(loops)

        return clip.set_fps(FPS)

    photo_url = search_pexels_photo(query)
    if photo_url:
        image_bytes = download_binary(photo_url)
        image_path = os.path.join(OUTPUT_DIR, f"bg_{idx}.jpg")
        with open(image_path, "wb") as f:
            f.write(image_bytes)

        clip = ImageClip(image_path).set_duration(duration)
        clip = fit_clip_to_vertical(clip)
        return clip.set_fps(FPS)

    fallback = Image.new("RGB", (WIDTH, HEIGHT), color=(20, 20, 20))
    fallback_path = os.path.join(OUTPUT_DIR, f"fallback_{idx}.jpg")
    fallback.save(fallback_path)
    return ImageClip(fallback_path).set_duration(duration).set_fps(FPS)


def get_font(size: int):
    possible = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]
    for path in possible:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def make_caption_image(lines_top, main_text, lines_bottom, out_path):
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(
        [(70, 1080), (1010, 1680)],
        radius=40,
        fill=(0, 0, 0, 150)
    )
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    top_font = get_font(54)
    main_font = get_font(90)
    bottom_font = get_font(42)

    y = 1125

    for line in lines_top:
        bbox = draw.textbbox((0, 0), line, font=top_font)
        w = bbox[2] - bbox[0]
        draw.text(((WIDTH - w) / 2, y), line, font=top_font, fill="white")
        y += 72

    wrapped = textwrap.wrap(main_text, width=16)
    y += 10
    for line in wrapped:
        bbox = draw.textbbox((0, 0), line, font=main_font)
        w = bbox[2] - bbox[0]
        draw.text(((WIDTH - w) / 2, y), line, font=main_font, fill="white")
        y += 108

    y += 20
    for line in lines_bottom:
        bbox = draw.textbbox((0, 0), line, font=bottom_font)
        w = bbox[2] - bbox[0]
        draw.text(((WIDTH - w) / 2, y), line, font=bottom_font, fill="white")
        y += 56

    img.save(out_path)


def make_segment(rank: int, topic: dict, idx: int):
    title = topic["title"]
    summary = topic["summary"]

    # keep narration honest and simple
    narration = f"Number {rank}. {title}. This is one of the search topics surging on Google right now."
    if summary:
        short_summary = summary[:150].strip()
        narration += f" Quick context: {short_summary}."
    narration += " "

    audio_path = os.path.join(OUTPUT_DIR, f"voice_{idx}.mp3")
    make_voice(narration, audio_path)
    audio = AudioFileClip(audio_path)
    duration = max(audio.duration, 4.5)

    bg = make_background_clip(title, duration, idx)

    caption_path = os.path.join(OUTPUT_DIR, f"caption_{idx}.png")
    make_caption_image(
        lines_top=["TRENDING RIGHT NOW", f"#{rank}"],
        main_text=title,
        lines_bottom=["search spike on Google"],
        out_path=caption_path
    )

    caption = (
        ImageClip(caption_path)
        .set_duration(duration)
        .set_position(("center", "center"))
    )

    clip = CompositeVideoClip([bg, caption]).set_audio(audio)
    return clip, title


def upload_to_youtube(video_path: str, title: str, description: str, tags):
    creds = Credentials(
        None,
        refresh_token=YT_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )

    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": "25"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(
        video_path,
        chunksize=-1,
        resumable=True,
        mimetype="video/*"
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    return response


def main():
    trends = fetch_trends(limit=3)

    clips = []
    used_titles = []

    # Show #3, then #2, then #1
    ordered = list(reversed(trends))

    for idx, topic in enumerate(ordered, start=1):
        rank = 4 - idx
        clip, used_title = make_segment(rank, topic, idx)
        clips.append(clip)
        used_titles.append(used_title)

    final = concatenate_videoclips(clips, method="compose")
    out_path = os.path.join(OUTPUT_DIR, "short.mp4")

    final.write_videofile(
        out_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac"
    )

    today = datetime.utcnow().strftime("%b %d")
    yt_title = f"3 Google Trends exploding right now | {today} #shorts"
    yt_description = (
        "Top search spikes on Google right now:\n"
        f"1. {used_titles[2]}\n"
        f"2. {used_titles[1]}\n"
        f"3. {used_titles[0]}\n\n"
        "#shorts #trending #googletrends"
    )
    yt_tags = ["shorts", "trending", "google trends", "viral", "today"]

    upload_to_youtube(out_path, yt_title, yt_description, yt_tags)


if __name__ == "__main__":
    main()
