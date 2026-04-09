import os
import re
import random
import textwrap
from datetime import datetime
from urllib.parse import quote_plus

import feedparser
import requests
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont

from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
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


def clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def shorten(text: str, max_len: int) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)[0].strip()
    return cut + "..."


def fetch_top_trend():
    feed = feedparser.parse(GOOGLE_TRENDS_RSS_URL)
    if not feed.entries:
        raise RuntimeError("No trends found in the Google Trends RSS feed.")

    for entry in feed.entries:
        title = clean_text(entry.get("title", ""))
        if title:
            return {
                "title": title,
                "summary": clean_text(entry.get("summary", "")),
            }

    raise RuntimeError("No valid trend title found.")


def fetch_news_headlines(query: str, limit=4):
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}+when:1d&hl=en-US&gl=US&ceid=US:en"
    )
    feed = feedparser.parse(url)

    headlines = []
    seen = set()

    for entry in feed.entries:
        title = clean_text(entry.get("title", ""))
        title = re.sub(r"\s*[-|•]\s*[^-|•]+$", "", title).strip()

        if not title:
            continue

        key = title.lower()
        if key in seen:
            continue

        seen.add(key)
        headlines.append(title)

        if len(headlines) >= limit:
            break

    return headlines


def choose_hook(topic: str):
    hooks = [
        f"People cannot stop talking about {topic} right now.",
        f"This is why {topic} is suddenly everywhere.",
        f"What happened with {topic} is blowing up fast.",
        f"There is a reason {topic} is all over the internet right now.",
        f"{topic} just became one of the biggest things people are talking about.",
    ]
    return random.choice(hooks)


def build_script(topic: str, summary: str, headlines: list[str]) -> str:
    hook = choose_hook(topic)

    if len(headlines) >= 3:
        middle = (
            f"It really started taking off after {headlines[0]}. "
            f"Then even more attention came when {headlines[1]}. "
            f"And now people keep searching because of {headlines[2]}."
        )
    elif len(headlines) == 2:
        middle = (
            f"It really started taking off after {headlines[0]}. "
            f"Then even more attention came when {headlines[1]}."
        )
    elif len(headlines) == 1:
        middle = f"It really started taking off after {headlines[0]}."
    elif summary:
        middle = f"It is trending because {shorten(summary, 220)}."
    else:
        middle = "It suddenly picked up a lot of attention online."

    ending_options = [
        "That is why this is blowing up right now.",
        "That is why everyone keeps searching for it.",
        "That is why this topic is suddenly everywhere.",
    ]
    ending = random.choice(ending_options)

    return f"{hook} {middle} {ending}"


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
            "per_page": 12,
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


def make_background_clip(query: str, duration: float):
    video_url = search_pexels_video(query)
    if video_url:
        video_path = os.path.join(OUTPUT_DIR, "bg.mp4")
        with open(video_path, "wb") as f:
            f.write(download_binary(video_url))

        clip = VideoFileClip(video_path)
        clip = fit_clip_to_vertical(clip)

        if clip.duration > duration:
            clip = clip.subclip(0, duration)
        return clip.set_fps(FPS)

    fallback = Image.new("RGB", (WIDTH, HEIGHT), color=(15, 15, 15))
    fallback_path = os.path.join(OUTPUT_DIR, "fallback.jpg")
    fallback.save(fallback_path)
    return ImageClip(fallback_path).set_duration(duration).set_fps(FPS)


def get_font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def make_caption_image(topic: str, headline_lines: list[str], out_path: str):
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(
        [(70, 1030), (1010, 1710)],
        radius=42,
        fill=(0, 0, 0, 170)
    )
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    top_font = get_font(50)
    main_font = get_font(84)
    bottom_font = get_font(34)

    y = 1080

    top_lines = ["WHY IS THIS", "BLOWING UP?"]
    for line in top_lines:
        bbox = draw.textbbox((0, 0), line, font=top_font)
        w = bbox[2] - bbox[0]
        draw.text(((WIDTH - w) / 2, y), line, font=top_font, fill="white")
        y += 64

    y += 14
    for line in textwrap.wrap(topic, width=16)[:3]:
        bbox = draw.textbbox((0, 0), line, font=main_font)
        w = bbox[2] - bbox[0]
        draw.text(((WIDTH - w) / 2, y), line, font=main_font, fill="white")
        y += 96

    y += 18
    for line in headline_lines[:2]:
        wrapped = textwrap.wrap(line, width=34)
        for subline in wrapped[:2]:
            bbox = draw.textbbox((0, 0), subline, font=bottom_font)
            w = bbox[2] - bbox[0]
            draw.text(((WIDTH - w) / 2, y), subline, font=bottom_font, fill="white")
            y += 42
        y += 8

    img.save(out_path)


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
            "categoryId": "25",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        video_path,
        chunksize=-1,
        resumable=True,
        mimetype="video/*",
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    return response


def make_title(topic: str) -> str:
    options = [
        f"Why {topic} is suddenly everywhere #shorts",
        f"{topic} is blowing up right now #shorts",
        f"Why everyone is talking about {topic} #shorts",
        f"What made {topic} go viral? #shorts",
    ]
    return random.choice(options)


def make_description(topic: str, script: str, headlines: list[str]) -> str:
    hash_tags = [
        "#shorts",
        "#trending",
        "#viral",
        "#news",
        "#breaking",
    ]

    if "sports" in topic.lower():
        hash_tags.extend(["#sports", "#nba", "#nfl"])
    elif "movie" in topic.lower() or "show" in topic.lower():
        hash_tags.extend(["#entertainment", "#tv", "#celebrity"])
    else:
        hash_tags.extend(["#explained", "#trendalert"])

    headline_block = "\n".join([f"- {h}" for h in headlines[:3]])

    return (
        f"{script}\n\n"
        f"Top recent headlines:\n{headline_block}\n\n"
        f"{' '.join(hash_tags)}"
    )


def main():
    trend = fetch_top_trend()
    topic = trend["title"]
    summary = trend["summary"]
    headlines = fetch_news_headlines(topic, limit=4)

    script = build_script(topic, summary, headlines)

    audio_path = os.path.join(OUTPUT_DIR, "voice.mp3")
    make_voice(script, audio_path)
    audio = AudioFileClip(audio_path)

    duration = max(audio.duration, 8.0)

    bg = make_background_clip(topic, duration)

    bottom_lines = []
    if len(headlines) >= 2:
        bottom_lines = [
            shorten(f"it started after: {headlines[0]}", 74),
            shorten(f"then got bigger: {headlines[1]}", 74),
        ]
    elif len(headlines) == 1:
        bottom_lines = [shorten(f"it started after: {headlines[0]}", 74)]
    elif summary:
        bottom_lines = [shorten(summary, 74)]
    else:
        bottom_lines = ["everyone suddenly started searching for it"]

    caption_path = os.path.join(OUTPUT_DIR, "caption.png")
    make_caption_image(topic, bottom_lines, caption_path)

    caption = ImageClip(caption_path).set_duration(duration).set_position(("center", "center"))
    final = CompositeVideoClip([bg, caption]).set_audio(audio)

    out_path = os.path.join(OUTPUT_DIR, "short.mp4")
    final.write_videofile(
        out_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        verbose=False,
        logger=None,
    )

    yt_title = make_title(topic)
    yt_description = make_description(topic, script, headlines)
    yt_tags = [
        "shorts",
        "trending",
        "viral",
        "news",
        "breaking news",
        topic[:30],
    ]

    upload_to_youtube(out_path, yt_title, yt_description, yt_tags)


if __name__ == "__main__":
    main()
