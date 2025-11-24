# utils/video_builder.py — PIL text; no ImageMagick; no moviepy.resize
import os, uuid, textwrap
from typing import List, Tuple
import numpy as np

# --- Pillow 10+ compatibility shim (removed constants) ---
from PIL import Image
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS
if not hasattr(Image, "BICUBIC"):
    Image.BICUBIC = Image.Resampling.BICUBIC
if not hasattr(Image, "BILINEAR"):
    Image.BILINEAR = Image.Resampling.BILINEAR
# ---------------------------------------------------------

from PIL import ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip, CompositeVideoClip, ImageClip, concatenate_videoclips
)
from moviepy.audio.fx.all import audio_fadein, audio_fadeout

VIDEO_SIZES = {
    "vertical": (1080, 1920),
    "square": (1080, 1080),
    "landscape": (1920, 1080),
}

def _wrap_lines(text: str, max_chars: int = 36) -> str:
    lines = []
    for para in text.split("\n"):
        lines.extend(textwrap.wrap(para, width=max_chars) or [""])
    return "\n".join(lines)

def _gradient_bg(size: Tuple[int,int], seed: int = 0):
    w, h = size
    top = np.array([30, 34, 56], dtype=np.float32)
    bot = np.array([8, 8, 12], dtype=np.float32)
    ys = np.linspace(0, 1, h).reshape(-1, 1)
    grad = (top * (1 - ys) + bot * ys).astype(np.uint8)
    return np.repeat(grad, w, axis=1)

def _solid_bg(size: Tuple[int,int]):
    w, h = size
    color = np.array([12, 12, 16], dtype=np.uint8)
    return np.tile(color, (h, w, 1))

def _render_text_image(text: str, size: Tuple[int,int]) -> np.ndarray:
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 78)
    except Exception:
        font = ImageFont.load_default()

    lines = _wrap_lines(text, max_chars=36).split("\n")
    boxes = [draw.textbbox((0, 0), ln, font=font) for ln in lines]
    sizes = [(bx[2]-bx[0], bx[3]-bx[1]) for bx in boxes]
    max_w = max([sw for sw, _ in sizes] + [0])
    total_h = sum([sh for _, sh in sizes]) + max(0, len(lines)-1)*12

    x = (w - max_w)//2
    y = (h - total_h)//2
    for ln, (_, sh) in zip(lines, sizes):
        draw.text((x+2, y+2), ln, fill=(0,0,0,180), font=font, align="center")
        draw.text((x, y), ln, fill=(255,255,255,255), font=font, align="center")
        y += sh + 12

    return np.array(img.convert("RGB"))

def _make_scene(text: str, audio_path: str, size: Tuple[int,int], style: str, seed: int):
    bg_img = _solid_bg(size) if style == "solid" else _gradient_bg(size, seed)
    bg = ImageClip(bg_img).set_duration(AudioFileClip(audio_path).duration)
    caption = ImageClip(_render_text_image(text, size)).set_duration(bg.duration)

    voice = AudioFileClip(audio_path)
    voice = audio_fadein(voice, 0.05).fx(audio_fadeout, 0.1)

    return CompositeVideoClip([bg, caption]).set_duration(voice.duration).set_audio(voice)

def _make_srt(segments: List[Tuple[str, float]]) -> str:
    def fmt(ts: float) -> str:
        ms = int((ts - int(ts)) * 1000)
        s = int(ts) % 60
        m = (int(ts) // 60) % 60
        h = int(ts) // 3600
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    out, t = [], 0.0
    for i, (line, dur) in enumerate(segments, 1):
        start, end = t, t + dur
        out.append(f"{i}\n{fmt(start)} --> {fmt(end)}\n{line}\n")
        t = end
    return "\n".join(out)

def build_video_from_script(script: str, out_dir: str, tts, style: str = "gradient",
                            target_seconds: int = 60, aspect: str = "vertical"):
    size = VIDEO_SIZES.get(aspect, VIDEO_SIZES["vertical"])
    lines = [ln.strip() for ln in script.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("Script has no non-empty lines.")

    audio_files, durations, segments = [], [], []
    for idx, line in enumerate(lines):
        wav_path = os.path.join(out_dir, f"scene_{idx+1:02d}.wav")
        dur = tts.synth(line, wav_path)
        audio_files.append(wav_path); durations.append(dur); segments.append((line, dur))

    total = sum(durations)
    if total > target_seconds:
        new_lines, new_audio, new_durs, run = [], [], [], 0.0
        for ln, af, d in zip(lines, audio_files, durations):
            if run + d <= target_seconds:
                new_lines.append(ln); new_audio.append(af); new_durs.append(d); run += d
            else:
                remaining = max(0.3, target_seconds - run)
                new_lines.append(ln + " …"); new_audio.append(af); new_durs.append(remaining)
                break
        lines, audio_files, durations = new_lines, new_audio, new_durs

    clips = []
    for i, (ln, af, d) in enumerate(zip(lines, audio_files, durations)):
        scene = _make_scene(ln, af, size=size, style=style, seed=1234+i)
        if scene.duration > d: scene = scene.set_duration(d)
        clips.append(scene)

    video = concatenate_videoclips(clips, method="compose")

    base = str(uuid.uuid4())[:8]
    video_out = os.path.join(out_dir, f"{base}.mp4")
    srt_out   = os.path.join(out_dir, f"{base}.srt")
    audio_out = os.path.join(out_dir, f"{base}.wav")

    video.write_videofile(video_out, fps=30, codec="libx264", audio_codec="aac",
                          threads=4, verbose=False, logger=None)
    try:
        if video.audio is not None:
            video.audio.write_audiofile(audio_out, fps=44100, nbytes=2, logger=None)
        else:
            audio_out = None
    except Exception:
        audio_out = None

    with open(srt_out, "w", encoding="utf-8") as f:
        f.write(_make_srt(segments))

    for c in clips: c.close()
    video.close()
    return video_out, srt_out, audio_out
