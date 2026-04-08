import os
import json
import time
import textwrap
import subprocess
from pathlib import Path
from typing import List, Dict

# =========================
# CONFIG
# =========================
ROOT = Path(__file__).parent
WORKDIR = ROOT / "shorts_workdir"
WORKDIR.mkdir(exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
YOUTUBE_CLIENT_SECRETS = os.getenv("YOUTUBE_CLIENT_SECRETS", "client_secret.json")

# Output settings
VIDEO_W = 1080
VIDEO_H = 1920
FPS = 30
SHORTS_MAX_SECONDS = 58
VOICE_NAME = os.getenv("VOICE_NAME", "en-US-Chirp3-HD-Achernar")
CHANNEL_DEFAULT_TAGS = ["shorts", "youtube shorts", "ai"]


# =========================
# USER SETTINGS
# =========================
NICHE = "history facts"
BRAND_STYLE = "fast-paced, punchy, clean, high-retention"
POST_PRIVACY = "private"  # private | public | unlisted
NUM_IMAGES = 6


# =========================
# STEP 1: SCRIPT GENERATION
# Replace this with your preferred LLM call.
# =========================
def generate_script(topic: str) -> Dict:
    """
    Expected return shape:
    {
      "title": "...",
      "hook": "...",
      "body": "full narration text",
      "image_prompts": ["...", "..."],
      "thumbnail_text": "...",
      "description": "...",
      "hashtags": ["#shorts", "#history"]
    }
    """
    # Placeholder. You can wire this to any LLM provider.
    return {
        "title": f"{topic.title()} in under 60 seconds",
        "hook": f"You probably learned {topic} wrong.",
        "body": (
            f"You probably learned {topic} wrong. "
            f"Here is the fastest version that actually makes sense. "
            f"First, the big misconception is that it happened all at once. "
            f"In reality, it built step by step, with one turning point changing everything. "
            f"That shift affected politics, culture, and everyday life. "
            f"And the wildest part is that one small decision early on changed what came next. "
            f"That is why {topic} still matters today."
        ),
        "image_prompts": [
            f"Vertical cinematic illustration about {topic}, scene 1, high contrast, modern editorial style",
            f"Vertical cinematic illustration about {topic}, scene 2, high contrast, modern editorial style",
            f"Vertical cinematic illustration about {topic}, scene 3, high contrast, modern editorial style",
            f"Vertical cinematic illustration about {topic}, scene 4, high contrast, modern editorial style",
            f"Vertical cinematic illustration about {topic}, scene 5, high contrast, modern editorial style",
            f"Vertical cinematic illustration about {topic}, scene 6, high contrast, modern editorial style",
        ],
        "thumbnail_text": topic.title(),
        "description": f"A quick short about {topic}.",
        "hashtags": ["#shorts", "#learnontiktok", "#history"]
    }


# =========================
# STEP 2: TEXT-TO-SPEECH
# Replace with Google Cloud TTS / other provider.
# =========================
def synthesize_voiceover(text: str, out_path: Path) -> Path:
    """
    Placeholder implementation.
    You should replace this with a real TTS provider.
    """
    # For now this just raises until connected.
    raise NotImplementedError("Connect a TTS provider here (e.g. Google Cloud TTS).")


# =========================
# STEP 3: IMAGE GENERATION
# Replace with image model provider.
# =========================
def generate_images(prompts: List[str], out_dir: Path) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Placeholder: assumes you will generate real images here.
    raise NotImplementedError("Connect an image generation provider here.")


# =========================
# STEP 4: CAPTIONS
# =========================
def write_srt_from_chunks(chunks: List[Dict], out_path: Path) -> Path:
    with out_path.open("w", encoding="utf-8") as f:
        for i, ch in enumerate(chunks, 1):
            f.write(f"{i}\n")
            f.write(f"{ch['start']} --> {ch['end']}\n")
            f.write(ch['text'].strip() + "\n\n")
    return out_path


def simple_caption_chunks(text: str, total_seconds: float) -> List[Dict]:
    words = text.split()
    groups = []
    step = max(3, min(8, len(words) // 8 or 3))
    grouped = [words[i:i + step] for i in range(0, len(words), step)]
    seg = total_seconds / max(1, len(grouped))
    out = []
    for idx, g in enumerate(grouped):
        start = idx * seg
        end = min(total_seconds, (idx + 1) * seg)
        out.append({
            "start": seconds_to_srt(start),
            "end": seconds_to_srt(end),
            "text": " ".join(g)
        })
    return out


def seconds_to_srt(seconds: float) -> str:
    ms = int((seconds - int(seconds)) * 1000)
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


# =========================
# STEP 5: VIDEO COMPOSITION
# Uses ffmpeg Ken Burns style motion on stills.
# =========================
def probe_duration(file_path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def make_video(image_paths: List[Path], audio_path: Path, srt_path: Path, out_path: Path) -> Path:
    duration = probe_duration(audio_path)
    per_image = max(1.5, duration / max(1, len(image_paths)))

    segment_paths = []
    for i, img in enumerate(image_paths):
        seg = out_path.parent / f"segment_{i:02d}.mp4"
        zoompan = (
            f"scale=1200:2133:force_original_aspect_ratio=increase,"
            f"crop={VIDEO_W}:{VIDEO_H},"
            f"zoompan=z='min(zoom+0.0008,1.12)':d={int(per_image * FPS)}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={VIDEO_W}x{VIDEO_H}:fps={FPS},"
            f"format=yuv420p"
        )
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-t", str(per_image),
            "-i", str(img),
            "-vf", zoompan,
            "-r", str(FPS),
            "-pix_fmt", "yuv420p",
            str(seg)
        ]
        subprocess.run(cmd, check=True)
        segment_paths.append(seg)

    concat_file = out_path.parent / "segments.ffconcat"
    with concat_file.open("w", encoding="utf-8") as f:
        f.write("ffconcat version 1.0\n")
        for seg in segment_paths:
            f.write(f"file '{seg.as_posix()}'\n")

    merged = out_path.parent / "merged.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(merged)
    ], check=True)

    styled = (
        "subtitles='{}':"
        "force_style='FontName=Arial,FontSize=13,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
        "Alignment=2,MarginV=120'"
    ).format(str(srt_path).replace('\\', '/').replace(':', '\\:'))

    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(merged),
        "-i", str(audio_path),
        "-vf", styled,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        str(out_path)
    ], check=True)

    return out_path


# =========================
# STEP 6: YOUTUBE UPLOAD
# Replace with Google API client auth flow.
# =========================
def upload_to_youtube(video_path: Path, title: str, description: str, tags: List[str], privacy_status: str = "private"):
    """
    Placeholder. Replace with YouTube Data API upload logic.
    """
    raise NotImplementedError("Connect YouTube Data API upload here.")


# =========================
# ORCHESTRATION
# =========================
def run_pipeline(topic: str):
    ts = int(time.time())
    run_dir = WORKDIR / str(ts)
    img_dir = run_dir / "images"
    run_dir.mkdir(parents=True, exist_ok=True)

    data = generate_script(topic)
    script_path = run_dir / "script.json"
    script_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    voice_path = run_dir / "voice.mp3"
    synthesize_voiceover(data["body"], voice_path)

    image_paths = generate_images(data["image_prompts"][:NUM_IMAGES], img_dir)

    duration = probe_duration(voice_path)
    caption_chunks = simple_caption_chunks(data["body"], min(duration, SHORTS_MAX_SECONDS))
    srt_path = write_srt_from_chunks(caption_chunks, run_dir / "captions.srt")

    final_video = make_video(image_paths, voice_path, srt_path, run_dir / "final_short.mp4")

    title = data["title"]
    description = data["description"] + "\n\n" + " ".join(data["hashtags"])
    tags = list(dict.fromkeys(CHANNEL_DEFAULT_TAGS + [h.replace("#", "") for h in data["hashtags"]]))

    upload_to_youtube(final_video, title, description, tags, privacy_status=POST_PRIVACY)
    print(f"Done: {final_video}")


if __name__ == "__main__":
    run_pipeline("the fall of the berlin wall")
