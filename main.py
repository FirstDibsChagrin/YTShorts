import os
import re
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


def clean(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def fetch_trend():
    feed = feedparser.parse(GOOGLE_TRENDS_RSS_URL)
    for entry in feed.entries:
        title = clean(entry.title)
        if title:
            return title
    raise RuntimeError("No trend found")


def fetch_news(query):
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}+when:1d&hl=en-US&gl=US&ceid=US:en"
    )
    feed = feedparser.parse(url)

    headlines = []
    for entry in feed.entries:
        t = clean(entry.title)
        if t and t not in headlines:
            headlines.append(t)
        if len(headlines) >= 3:
            break

    return headlines


def build_script(topic, headlines):
    hook = f"Why is everyone talking about {topic} right now?"

    if len(headlines) >= 2:
        body = (
            f"It started because {headlines[0]}. "
            f"But then it got bigger when {headlines[1]}."
        )
    elif len(headlines) == 1:
        body = f"It started because {headlines[0]}."
    else:
        body = "It suddenly started trending across the internet."

    ending = "That’s why this is blowing up everywhere right now."

    return hook + " " + body + " " + ending


def make_voice(text, path):
    gTTS(text=text).save(path)


def download(url):
    return requests.get(url).content


def search_video(query):
    headers = {"Authorization": PEXELS_API_KEY}
    r = requests.get(
        "https://api.pexels.com/videos/search",
        headers=headers,
        params={"query": query, "orientation": "portrait"},
    ).json()

    for v in r.get("videos", []):
        for f in v.get("video_files", []):
            if f.get("link"):
                return f["link"]
    return None


def make_bg(query, duration):
    url = search_video(query)
    if url:
        path = OUTPUT_DIR + "/bg.mp4"
        open(path, "wb").write(download(url))
        clip = VideoFileClip(path)
        clip = clip.resize(height=HEIGHT).crop(
            x_center=clip.w / 2,
            y_center=clip.h / 2,
            width=WIDTH,
            height=HEIGHT,
        )
        return clip.subclip(0, min(duration, clip.duration))

    return ImageClip(
        Image.new("RGB", (WIDTH, HEIGHT), (20, 20, 20))
    ).set_duration(duration)


def font(size):
    return ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size
    )


def make_caption(topic, lines, path):
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    y = 1100

    for t in ["TRENDING RIGHT NOW"]:
        w = draw.textbbox((0, 0), t, font=font(50))[2]
        draw.text(((WIDTH - w) / 2, y), t, fill="white", font=font(50))
        y += 80

    for t in textwrap.wrap(topic, 16):
        w = draw.textbbox((0, 0), t, font=font(80))[2]
        draw.text(((WIDTH - w) / 2, y), t, fill="white", font=font(80))
        y += 100

    y += 30

    for l in lines:
        for t in textwrap.wrap(l, 34):
            w = draw.textbbox((0, 0), t, font=font(36))[2]
            draw.text(((WIDTH - w) / 2, y), t, fill="white", font=font(36))
            y += 50

    img.save(path)


def upload(video, title, desc, tags):
    creds = Credentials(
        None,
        refresh_token=YT_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )

    youtube = build("youtube", "v3", credentials=creds)

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title[:100],
                "description": desc,
                "tags": tags,
                "categoryId": "25",
            },
            "status": {"privacyStatus": "public"},
        },
        media_body=MediaFileUpload(video, resumable=True),
    )

    while request.next_chunk()[1] is None:
        pass


def main():
    topic = fetch_trend()
    headlines = fetch_news(topic)

    script = build_script(topic, headlines)

    audio_path = OUTPUT_DIR + "/voice.mp3"
    make_voice(script, audio_path)
    audio = AudioFileClip(audio_path)

    bg = make_bg(topic, audio.duration)

    caption_path = OUTPUT_DIR + "/cap.png"
    make_caption(topic, headlines[:2], caption_path)

    video = CompositeVideoClip(
        [bg, ImageClip(caption_path).set_duration(audio.duration)]
    ).set_audio(audio)

    out = OUTPUT_DIR + "/out.mp4"
    video.write_videofile(out, fps=FPS)

    today = datetime.utcnow().strftime("%b %d")

    upload(
        out,
        f"{topic} is blowing up right now… {today} #shorts",
        script,
        [
            "shorts",
            topic,
            "trending",
            "viral",
            "news",
            "breaking",
        ],
    )


if __name__ == "__main__":
    main()
