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

    fallback = Image.new("RGB", (WIDTH, HEIGHT), color=(20, 20, 20))
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


def make_caption_image(lines_top, main_text, lines_bottom, out_path):
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(
        [(70, 1040), (1010, 1710)],
        radius=40,
        fill=(0, 0, 0, 160),
    )
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    top_font = get_font(50)
    main_font = get_font(84)
    bottom_font = get_font(36)

    y = 1090

    for line in lines_top:
        bbox = draw.textbbox((0, 0), line, font=top_font)
        w = bbox[2] - bbox[0]
        draw.text(((WIDTH - w) / 2, y), line, font=top_font, fill="white")
        y += 62

    wrapped = textwrap.wrap(main_text, width=16)
    y += 18
    for line in wrapped[:4]:
        bbox = draw.textbbox((0, 0), line, font=main_font)
        w = bbox[2] - bbox[0]
        draw.text(((WIDTH - w) / 2, y), line, font=main_font, fill="white")
        y += 94

    y += 18
    for line in lines_bottom[:3]:
        bbox = draw.textbbox((0, 0), line, font=bottom_font)
        w = bbox[2] - bbox[0]
        draw.text(((WIDTH - w) / 2, y), line, font=bottom_font, fill="white")
        y += 46

    img.save(out_path)


def shorten(text: str, max_len: int) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)[0].strip()
    return cut + "..."


def build_story():
    genres = [
        {
            "name": "scary story",
            "search": "dark alley night city",
            "hook_templates": [
                "At {time}, {name} heard knocking from inside the {place}.",
                "{name} thought the {place} was empty until a voice said, \"Don't turn around.\"",
                "Everyone in {town} avoided the {place}, but {name} went in anyway."
            ],
            "twist_templates": [
                "When {name} checked the security camera, the hallway was empty except for one shadow standing behind them.",
                "The message on the wall wasn't old. It had appeared while {name} was inside.",
                "The phone started ringing, and the caller ID was {name}'s own number."
            ],
            "ending_templates": [
                "{name} ran home, but the same knocking started at the bedroom door.",
                "The next morning, the {place} was locked, but {name}'s shoes were still inside.",
                "Now every night at {time}, someone whispers {name}'s name from the other side of the wall."
            ],
        },
        {
            "name": "mystery story",
            "search": "fog city street rain",
            "hook_templates": [
                "{name} found a note in the {place} that said, \"You only have one hour.\"",
                "A stranger left a key in {name}'s pocket and disappeared into the crowd.",
                "{name} opened the old locker in the {place} and found a photo taken that same morning."
            ],
            "twist_templates": [
                "The photo showed {name} standing next to someone who had vanished ten years earlier.",
                "Every clue led back to an apartment with {name}'s last name on the mailbox.",
                "Inside the envelope was a map of {town} with one building circled in red."
            ],
            "ending_templates": [
                "When {name} reached the address, the door opened and the person inside looked exactly like them.",
                "The mystery ended with one line written on the mirror: \"You were never supposed to remember.\"",
                "{name} solved the case, but the final clue revealed they had been part of it all along."
            ],
        },
        {
            "name": "sad story",
            "search": "lonely train station rain window",
            "hook_templates": [
                "Every week, {name} waited at the {place} for someone who never came back.",
                "{name} kept receiving birthday cards from a person who had died years ago.",
                "At sunset in {town}, {name} still set the table for two."
            ],
            "twist_templates": [
                "One day a final letter arrived, explaining why the goodbye had never happened.",
                "The old voicemail finally unlocked, and the message had been there the entire time.",
                "A neighbor returned a box of unopened gifts addressed to {name}."
            ],
            "ending_templates": [
                "{name} cried, smiled, and put the last letter in the drawer forever.",
                "That night, for the first time in years, {name} stopped waiting by the window.",
                "{name} never got the lost years back, but finally got the truth."
            ],
        },
        {
            "name": "drama story",
            "search": "city rooftop sunset emotional",
            "hook_templates": [
                "Right before the wedding, {name} got a text that changed everything.",
                "{name} went to the {place} to confess the truth, but someone had already told it.",
                "The one secret {name} hid for years came out in front of the whole family."
            ],
            "twist_templates": [
                "The message wasn't from an enemy. It was from the person {name} trusted most.",
                "What looked like betrayal was actually a sacrifice nobody knew about.",
                "The family argument stopped the moment an old recording started playing."
            ],
            "ending_templates": [
                "By midnight, nothing in {name}'s life looked the same, but at least the lies were over.",
                "{name} lost the relationship but finally stopped pretending.",
                "The truth hurt everyone, but it also saved them."
            ],
        },
        {
            "name": "funny story",
            "search": "cat office home chaos",
            "hook_templates": [
                "{name} tried to look professional until the cat joined the video call.",
                "The worst possible thing happened to {name} five seconds before the big presentation.",
                "{name} opened the package and realized it definitely was not the thing they ordered."
            ],
            "twist_templates": [
                "The boss loved it and asked where they bought one.",
                "The mix-up somehow made {name} internet famous by dinner.",
                "What started as a disaster turned into the best excuse {name} had ever used."
            ],
            "ending_templates": [
                "Now nobody remembers the presentation, but everyone remembers the cat.",
                "{name} never fixed the mistake, because somehow it worked.",
                "It was humiliating for about ten minutes, and hilarious forever after that."
            ],
        },
    ]

    names = [
        "Maya", "Ethan", "Lena", "Noah", "Ava", "Jace", "Sophie", "Lucas", "Emma", "Kai"
    ]
    places = [
        "subway station", "apartment hallway", "old library", "hotel room", "rooftop", "train platform",
        "coffee shop", "school gym", "parking garage", "empty theater"
    ]
    towns = [
        "Ashford", "Black Hollow", "Riverton", "Maple Glen", "Westbridge", "Pine Ridge"
    ]
    times = [
        "2:13 a.m.", "midnight", "11:47 p.m.", "3:02 a.m.", "sunset", "closing time"
    ]

    genre = random.choice(genres)
    name = random.choice(names)
    place = random.choice(places)
    town = random.choice(towns)
    time = random.choice(times)

    hook = random.choice(genre["hook_templates"]).format(
        name=name, place=place, town=town, time=time
    )
    twist = random.choice(genre["twist_templates"]).format(
        name=name, place=place, town=town, time=time
    )
    ending = random.choice(genre["ending_templates"]).format(
        name=name, place=place, town=town, time=time
    )

    full_story = f"{hook} {twist} {ending}"

    title_options = [
        f"{genre['name'].title()} you won't forget",
        f"One-minute {genre['name']}",
        f"This {genre['name']} has a twist",
        f"Short {genre['name']} with a dark ending",
    ]
    title = random.choice(title_options)

    caption_main = shorten(hook, 55)
    bottom_lines = [
        shorten(twist, 52),
        shorten(ending, 52),
    ]

    return {
        "genre_name": genre["name"],
        "search_query": genre["search"],
        "hook": hook,
        "twist": twist,
        "ending": ending,
        "story": full_story,
        "video_title": title,
        "caption_main": caption_main,
        "caption_bottom": bottom_lines,
    }


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
            "categoryId": "24",
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
    story_data = build_story()

    narration = story_data["story"]
    audio_path = os.path.join(OUTPUT_DIR, "voice.mp3")
    make_voice(narration, audio_path)

    audio = AudioFileClip(audio_path)
    duration = max(audio.duration, 10.0)

    bg = make_background_clip(story_data["search_query"], duration)

    caption_path = os.path.join(OUTPUT_DIR, "caption.png")
    make_caption_image(
        lines_top=["AI STORY", story_data["genre_name"].upper()],
        main_text=story_data["caption_main"],
        lines_bottom=story_data["caption_bottom"],
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
    yt_title = f"{story_data['video_title']} | {today} #shorts"
    yt_description = (
        "Original auto-generated short story.\n\n"
        f"{story_data['story']}\n\n"
        "#shorts #story #aistory #fiction"
    )
    yt_tags = ["shorts", "story", "fiction", "ai story", story_data["genre_name"]]

    upload_to_youtube(out_path, yt_title, yt_description, yt_tags)


if __name__ == "__main__":
    main()
