import os
import random
import textwrap
from datetime import datetime

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
YT_CLIENT_ID = os.environ["YT_CLIENT_ID"]
YT_CLIENT_SECRET = os.environ["YT_CLIENT_SECRET"]
YT_REFRESH_TOKEN = os.environ["YT_REFRESH_TOKEN"]

os.makedirs(OUTPUT_DIR, exist_ok=True)


HISTORY_STORIES = [
    {
        "title": "He survived both atomic bombs",
        "hook": "One man survived both atomic bombs in Japan.",
        "body": "Tsutomu Yamaguchi was in Hiroshima when the first bomb exploded. He survived, traveled home to Nagasaki, and then survived the second bomb too.",
        "ending": "He lived for decades after the war, making his story one of the most unbelievable survival stories in history.",
        "search_query": "hiroshima nagasaki war memorial",
        "category": "history",
    },
    {
        "title": "The shortest war lasted under an hour",
        "hook": "The shortest war in history lasted less than an hour.",
        "body": "In 1896, Britain and Zanzibar went to war. After a dispute over the sultanate, British ships opened fire and destroyed the palace defenses almost immediately.",
        "ending": "The entire war lasted about 38 minutes.",
        "search_query": "old warship ocean battle historic city",
        "category": "history",
    },
    {
        "title": "A city was buried in a single day",
        "hook": "An entire Roman city disappeared in a single day.",
        "body": "When Mount Vesuvius erupted in 79 A.D., Pompeii was buried under ash and volcanic debris. Many people had no time to escape.",
        "ending": "The buried city stayed hidden for centuries, freezing one of history's worst disasters in time.",
        "search_query": "ancient ruins volcanic ash italy",
        "category": "history",
    },
    {
        "title": "A dancing plague took over a city",
        "hook": "In 1518, people in one city danced until they collapsed.",
        "body": "In Strasbourg, dozens and then hundreds of people began dancing uncontrollably in the streets. Some reportedly kept going for days.",
        "ending": "Nobody fully agrees on what caused it, making it one of history's strangest mass events.",
        "search_query": "old european street crowd town square",
        "category": "history",
    },
    {
        "title": "A killer fog choked an entire city",
        "hook": "A fog once killed thousands of people in one major city.",
        "body": "In 1952, London's Great Smog mixed cold air, smoke, and pollution into a deadly cloud. It was so thick people could barely see a few feet ahead.",
        "ending": "Thousands died, and the disaster changed modern air pollution laws.",
        "search_query": "foggy city street london night",
        "category": "history",
    },
    {
        "title": "A woman ruled for only 9 days",
        "hook": "One queen ruled England for just 9 days.",
        "body": "Lady Jane Grey was placed on the throne during a brutal power struggle. But the political plan collapsed almost immediately.",
        "ending": "She was removed, imprisoned, and later executed, turning her into one of history's most tragic rulers.",
        "search_query": "castle crown royal portrait hallway",
        "category": "history",
    },
    {
        "title": "The Titanic had warnings all day",
        "hook": "The Titanic received multiple iceberg warnings before it sank.",
        "body": "Radio operators got repeated messages about dangerous ice ahead, but not all of them were treated with enough urgency. That night, the ship struck an iceberg in the Atlantic.",
        "ending": "More than 1,500 people died in one of history's most famous disasters.",
        "search_query": "ocean ship night iceberg sea",
        "category": "history",
    },
    {
        "title": "A horse became a military hero",
        "hook": "One war horse became a national hero.",
        "body": "Sergeant Reckless carried ammunition and supplies during the Korean War, often moving through heavy fighting and dangerous terrain.",
        "ending": "She became famous for bravery under fire, and soldiers treated her like one of their own.",
        "search_query": "horse mountain soldier memorial",
        "category": "history",
    },
    {
        "title": "The Black Death reshaped Europe",
        "hook": "One plague changed the entire balance of Europe.",
        "body": "The Black Death killed enormous numbers of people in the 1300s. Towns collapsed, labor became scarce, and long-standing systems of power were shaken.",
        "ending": "It was one of the deadliest events in human history, and its effects lasted for generations.",
        "search_query": "medieval town dark street candle",
        "category": "history",
    },
    {
        "title": "A man was trapped underground for days",
        "hook": "A cave rescue became one of the most terrifying survival stories ever.",
        "body": "Explorer Floyd Collins became trapped inside a Kentucky cave in 1925. Rescue attempts were slow, dangerous, and followed closely by the public.",
        "ending": "He died before rescuers could reach him, and the disaster shocked the country.",
        "search_query": "cave dark rescue underground",
        "category": "history",
    },
    {
        "title": "A bridge collapse horrified America",
        "hook": "One bridge disaster was caught in front of horrified witnesses.",
        "body": "In 1940, the Tacoma Narrows Bridge twisted violently in the wind before collapsing. The dramatic motion was so strange it looked unreal.",
        "ending": "The footage became one of the most famous engineering failure videos ever recorded.",
        "search_query": "bridge wind storm water",
        "category": "history",
    },
    {
        "title": "The Hindenburg disaster happened in seconds",
        "hook": "One of history's most famous air disasters happened in seconds.",
        "body": "In 1937, the Hindenburg airship caught fire while attempting to land in New Jersey. News cameras and reporters captured the disaster almost live.",
        "ending": "The fire ended the age of giant passenger airships.",
        "search_query": "airship fire sky historic landing",
        "category": "history",
    },
    {
        "title": "The ocean sent a wall of death",
        "hook": "A single wave destroyed entire communities in minutes.",
        "body": "The 2004 Indian Ocean tsunami was triggered by a massive undersea earthquake. Giant waves slammed into coastlines across multiple countries.",
        "ending": "It became one of the deadliest natural disasters in modern history.",
        "search_query": "ocean wave disaster coastline",
        "category": "history",
    },
    {
        "title": "An expedition ended in frozen silence",
        "hook": "A famous Arctic expedition vanished into the ice.",
        "body": "Sir John Franklin's 1845 expedition set out to find the Northwest Passage. The ships became trapped, and the crew disappeared into one of the harshest environments on Earth.",
        "ending": "For years, the mystery haunted the world and became one of history's darkest exploration stories.",
        "search_query": "arctic ice ship snow",
        "category": "history",
    },
    {
        "title": "A city burned for days",
        "hook": "One fire nearly destroyed an entire city.",
        "body": "In 1871, the Great Chicago Fire spread rapidly through wooden buildings and dry conditions. Huge sections of the city were wiped out.",
        "ending": "The disaster changed building practices and reshaped Chicago forever.",
        "search_query": "city fire smoke night historic",
        "category": "history",
    },
    {
        "title": "A stampede killed hundreds at a coronation",
        "hook": "A celebration turned into one of Russia's deadliest public disasters.",
        "body": "During festivities for Tsar Nicholas the Second, rumors spread that gifts were running out. Massive crowds surged forward in panic.",
        "ending": "Hundreds were crushed to death in the chaos at Khodynka Field.",
        "search_query": "huge crowd historic field city",
        "category": "history",
    },
    {
        "title": "A prison on the sea was almost impossible to escape",
        "hook": "One prison was designed so escape felt impossible.",
        "body": "Alcatraz sat on an island in cold, rough water surrounded by strong currents. It held some of America's most notorious prisoners.",
        "ending": "A few men tried to escape, and some disappearances are still debated today.",
        "search_query": "prison island fog ocean",
        "category": "history",
    },
    {
        "title": "A volcano darkened the world",
        "hook": "One eruption changed weather across the planet.",
        "body": "When Mount Tambora erupted in 1815, ash and gases spread high into the atmosphere. The next year became known in places as the year without a summer.",
        "ending": "Crop failures and famine followed, proving one volcano can change the world.",
        "search_query": "volcano ash mountain dramatic sky",
        "category": "history",
    },
    {
        "title": "A tunnel trapped workers beneath the river",
        "hook": "A construction disaster became a nightmare beneath the water.",
        "body": "During the building of early tunnels under rivers, workers faced collapses, flooding, and deadly pressure changes. The danger was constant and often invisible.",
        "ending": "These disasters helped reveal the terrifying condition later known as decompression sickness.",
        "search_query": "tunnel underground construction water dark",
        "category": "history",
    },
    {
        "title": "A nuclear accident poisoned a region",
        "hook": "One explosion turned a city into a warning for the world.",
        "body": "In 1986, Reactor Four at Chernobyl exploded during a failed safety test. Fire, radiation, and confusion spread through the area before many people understood what had happened.",
        "ending": "The disaster contaminated a huge region and remains one of history's worst nuclear accidents.",
        "search_query": "abandoned city radiation building",
        "category": "history",
    },
]


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
            "orientation": "portrait",
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
            reverse=True,
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
            "orientation": "portrait",
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
        height=HEIGHT,
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
        image_path = os.path.join(OUTPUT_DIR, "bg.jpg")
        with open(image_path, "wb") as f:
            f.write(download_binary(photo_url))

        clip = ImageClip(image_path).set_duration(duration)
        clip = fit_clip_to_vertical(clip)
        return clip.set_fps(FPS)

    fallback = Image.new("RGB", (WIDTH, HEIGHT), color=(15, 15, 15))
    fallback_path = os.path.join(OUTPUT_DIR, "fallback.jpg")
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


def shorten(text: str, max_len: int) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)[0].strip()
    return cut + "..."


def make_caption_image(lines_top, main_text, lines_bottom, out_path):
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(
        [(60, 1010), (1020, 1730)],
        radius=42,
        fill=(0, 0, 0, 165),
    )
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    top_font = get_font(48)
    main_font = get_font(82)
    bottom_font = get_font(36)

    y = 1070

    for line in lines_top:
        bbox = draw.textbbox((0, 0), line, font=top_font)
        w = bbox[2] - bbox[0]
        draw.text(((WIDTH - w) / 2, y), line, font=top_font, fill="white")
        y += 60

    y += 20
    wrapped = textwrap.wrap(main_text, width=16)
    for line in wrapped[:4]:
        bbox = draw.textbbox((0, 0), line, font=main_font)
        w = bbox[2] - bbox[0]
        draw.text(((WIDTH - w) / 2, y), line, font=main_font, fill="white")
        y += 92

    y += 15
    for line in lines_bottom[:3]:
        wrapped_bottom = textwrap.wrap(line, width=34)
        for subline in wrapped_bottom[:2]:
            bbox = draw.textbbox((0, 0), subline, font=bottom_font)
            w = bbox[2] - bbox[0]
            draw.text(((WIDTH - w) / 2, y), subline, font=bottom_font, fill="white")
            y += 42
        y += 8

    img.save(out_path)


def pick_story():
    return random.choice(HISTORY_STORIES)


def build_narration(story):
    return (
        f"This actually happened in history. {story['hook']} "
        f"{story['body']} {story['ending']}"
    )


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
            "categoryId": "27",
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


def main():
    story = pick_story()

    narration = build_narration(story)
    audio_path = os.path.join(OUTPUT_DIR, "voice.mp3")
    make_voice(narration, audio_path)

    audio = AudioFileClip(audio_path)
    duration = max(audio.duration, 10.0)

    bg = make_background_clip(story["search_query"], duration)

    caption_path = os.path.join(OUTPUT_DIR, "caption.png")
    make_caption_image(
        lines_top=["THIS ACTUALLY", "HAPPENED IN HISTORY"],
        main_text=shorten(story["title"], 52),
        lines_bottom=[
            shorten(story["hook"], 72),
            shorten(story["ending"], 72),
        ],
        out_path=caption_path,
    )

    caption = (
        ImageClip(caption_path)
        .set_duration(duration)
        .set_position(("center", "center"))
    )

    final = CompositeVideoClip([bg, caption]).set_audio(audio)
    out_path = os.path.join(OUTPUT_DIR, "short.mp4")

    final.write_videofile(
        out_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
    )

    today = datetime.utcnow().strftime("%b %d")
    yt_title = f"{story['title']} | {today} #shorts"
    yt_description = (
        f"{story['hook']} {story['body']} {story['ending']}\n\n"
        "#shorts #history #darkhistory #facts"
    )
    yt_tags = ["shorts", "history", "dark history", "facts", "true story"]

    upload_to_youtube(out_path, yt_title, yt_description, yt_tags)


if __name__ == "__main__":
    main()
