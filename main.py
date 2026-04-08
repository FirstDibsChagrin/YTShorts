import os
import random
import textwrap
import requests
from gtts import gTTS
from moviepy import (
    AudioFileClip,
    ImageClip,
    VideoFileClip,
    TextClip,
    CompositeVideoClip,
    concatenate_videoclips
)
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from PIL import Image

WIDTH = 1080
HEIGHT = 1920
FPS = 24
THRESHOLD_TOP = 250
THRESHOLD_BOTTOM = 1650

PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
YT_CLIENT_ID = os.environ["YT_CLIENT_ID"]
YT_CLIENT_SECRET = os.environ["YT_CLIENT_SECRET"]
YT_REFRESH_TOKEN = os.environ["YT_REFRESH_TOKEN"]
YT_CHANNEL_TITLE = os.environ.get("YT_CHANNEL_TITLE", "")

OUTPUT_DIR = "output"
TOPICS_FILE = "data/topics.txt"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def pick_topic():
    with open(TOPICS_FILE, "r", encoding="utf-8") as f:
        topics = [line.strip() for line in f if line.strip()]
    return random.choice(topics)

def build_script(topic):
    # super simple free template-based script writer
    return (
        f"{topic}. "
        f"Here are the facts. "
        f"First, this topic has details most people never learn in school. "
        f"Second, one of the biggest reasons it matters is that it changes how we understand the world. "
        f"Third, the most surprising part is how strange the real facts are once you look closer. "
        f"Follow for more quick facts."
    )

def save_voice(script, path):
    tts = gTTS(text=script, lang="en")
    tts.save(path)

def search_pexels_video(query):
    headers = {"Authorization": PEXELS_API_KEY}
    url = "https://api.pexels.com/videos/search"
    params = {"query": query, "per_page": 10, "orientation": "portrait"}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    for item in data.get("videos", []):
        files = item.get("video_files", [])
        portrait = sorted(files, key=lambda x: x.get("width", 0) * x.get("height", 0), reverse=True)
        for f in portrait:
            link = f.get("link", "")
            if link:
                return link
    return None

def search_pexels_photo(query):
    headers = {"Authorization": PEXELS_API_KEY}
    url = "https://api.pexels.com/v1/search"
    params = {"query": query, "per_page": 10, "orientation": "portrait"}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    photos = data.get("photos", [])
    if photos:
        src = photos[0].get("src", {})
        return src.get("large2x") or src.get("original")
    return None

def download_file(url, path):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)

def make_background_clip(query, duration):
    video_url = search_pexels_video(query)
    if video_url:
        video_path = os.path.join(OUTPUT_DIR, "bg.mp4")
        download_file(video_url, video_path)
        clip = VideoFileClip(video_path).resized(height=HEIGHT)
        if clip.w < WIDTH:
            clip = clip.resized(width=WIDTH)
        clip = clip.cropped(
            x_center=clip.w / 2,
            y_center=clip.h / 2,
            width=WIDTH,
            height=HEIGHT
        )
        if clip.duration > duration:
            clip = clip.subclipped(0, duration)
        else:
            loops = []
            remaining = duration
            while remaining > 0:
                seg = clip.subclipped(0, min(clip.duration, remaining))
                loops.append(seg)
                remaining -= seg.duration
            clip = concatenate_videoclips(loops)
        return clip.with_fps(FPS)

    photo_url = search_pexels_photo(query)
    if photo_url:
        image_path = os.path.join(OUTPUT_DIR, "bg.jpg")
        download_file(photo_url, image_path)
        clip = ImageClip(image_path, duration=duration)
        clip = clip.resized(height=HEIGHT)
        if clip.w < WIDTH:
            clip = clip.resized(width=WIDTH)
        clip = clip.cropped(
            x_center=clip.w / 2,
            y_center=clip.h / 2,
            width=WIDTH,
            height=HEIGHT
        )
        return clip.with_fps(FPS)

    # plain fallback
    img = Image.new("RGB", (WIDTH, HEIGHT), color=(20, 20, 20))
    fallback = os.path.join(OUTPUT_DIR, "fallback.jpg")
    img.save(fallback)
    return ImageClip(fallback, duration=duration).with_fps(FPS)

def make_text_clip(text, duration):
    wrapped = textwrap.fill(text, width=18)
    txt = TextClip(
        text=wrapped,
        font_size=72,
        color="white",
        method="caption",
        size=(900, None),
        text_align="center",
        stroke_color="black",
        stroke_width=3,
        margin=(20, 20)
    ).with_duration(duration)

    return txt.with_position(("center", 1350))

def upload_to_youtube(video_path, title, description, tags):
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
            "categoryId": "27"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/*")
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
    topic = pick_topic()
    script = build_script(topic)

    audio_path = os.path.join(OUTPUT_DIR, "voice.mp3")
    save_voice(script, audio_path)

    audio = AudioFileClip(audio_path)
    duration = audio.duration

    bg = make_background_clip(topic, duration)
    text = make_text_clip(topic, duration)

    final = CompositeVideoClip([bg, text]).with_audio(audio)
    final_path = os.path.join(OUTPUT_DIR, "short.mp4")
    final.write_videofile(final_path, fps=FPS, codec="libx264", audio_codec="aac")

    title = f"{topic} #shorts"
    description = f"{script}\n\n#shorts"
    tags = ["shorts", "facts", "viral facts"]

    upload_to_youtube(final_path, title, description, tags)

if __name__ == "__main__":
    main()
