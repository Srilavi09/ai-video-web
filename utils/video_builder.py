# utils/video_builder.py
import os, uuid, textwrap
from typing import List, Tuple
import numpy as np

from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip, CompositeVideoClip, ImageClip, concatenate_videoclips
)
from moviepy.video.fx.all import resize
from moviepy.audio.fx.all import audio_fadein, audio_fadeout

VIDEO_SIZES = {
    "vertical": (1080, 1920),
    "square": (1080, 1080),
    "landscape": (1920, 1080),
}

def _wrap_lines(text: str, max_chars: int = 36) -> str:
    # safe wrap for captions
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
    img = np.repeat(grad, w, axis=1)
    return img

def _solid_bg(size: Tuple[int,int]):
    w, h = size
    color = np.array([12, 12, 16], dtype=np.uint8)
    return np.tile(color, (h, w, 1))

def _render_text_image(text: str, size: Tuple[int,int], margin: int = 60) -> np.ndarray:
    """
    Draw multiline, centered text onto a transparent image using Pillow.
    """
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Choose a font. If this exact font isn’t on the server,
    # Pillow will fall back to a default. You can upload a .ttf and point to it.
    try:
        font = ImageFont.truetype("arial.ttf", 78)
    except:
        font = ImageFont.load_default()

    wrapped = _wrap_lines(text, max_chars=36)
    lines = wrapped.split("\n")
    line_heights = []
    max_line_w = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        line_h = bbox[3] - bbox[1]
        max_line_w = max(max_line_w, line_w)
        line_heights.append(line_h)

    total_h = sum(line_heights) + (len(lines) - 1) * 12
    x = (w - max_line_w) // 2
    y = (h - total_h) // 2

    # Draw with slight shadow for readability
    for i, line in enumerate(lines):
        lh = line_heights[i]
        # shadow
        draw.text((x+2, y+2), line, fill=(0,0,0,180), font=font, align="center")
        # main text
        draw.text((x, y), line, fill=(255,255,255,255), font=font, align="center")
        y += lh + 12

    return np.array(img.convert("RGB"))

def _make_scene(text: str, audio_path: str, size: Tuple[int,int], style: str, seed: int):
    if style == "solid":
        bg_img = _solid_bg(size)
    else:
        bg_img = _gradient_bg(size, seed)

    bg = ImageClip(bg_img).set_duration(AudioFileClip(audio_path).duration)

    # Render caption image with Pillow and overlay it
    caption_img = _render_text_image(text, size=size)
    caption = ImageClip(caption_img).set_duration(bg.duration)

    # Subtle Ken Burns on background
    dur = bg.duration
    def zoom(t):
        start, end = 1.0, 1.06
        return start + (end - start) * (t / max(0.01, dur))
    bg_zoom = bg.fx(resize, lambda t: zoom(t))

    voice = AudioFileClip(audio_path)
    voice = audio_fadein(voice, 0.05).fx(audio_fadeout, 0.1)

    scene = CompositeVideoClip([bg_zoom, caption]).set_duration(voice.duration).set_audio(voice)
    return scene

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
        audio_files.append(wav_path)
        durations.append(dur)
        segments.append((line, dur))

    total = sum(durations)
    if total > target_seconds:
        new_lines, new_audio, new_durs = [], [], []
        running = 0.0
        for ln, af, d in zip(lines, audio_files, durations):
            if running + d <= target_seconds:
                new_lines.append(ln); new_audio.append(af); new_durs.append(d)
                running += d
            else:
                remaining = max(0.3, target_seconds - running)
                new_lines.append(ln + " …"); new_audio.append(af); new_durs.append(remaining)
                break
        lines, audio_files, durations = new_lines, new_audio, new_durs

    clips = []
    for i, (ln, af, d) in enumerate(zip(lines, audio_files, durations)):
        scene = _make_scene(ln, af, size=size, style=style, seed=1234+i)
        if scene.duration > d:
            scene = scene.set_duration(d)
        clips.append(scene)

    video = concatenate_videoclips(clips, method="compose")

    basename = str(uuid.uuid4())[:8]
    video_out = os.path.join(out_dir, f"{basename}.mp4")
    srt_out = os.path.join(out_dir, f"{basename}.srt")
    audio_mix_out = os.path.join(out_dir, f"{basename}.wav")

    video.write_videofile(video_out, fps=30, codec="libx264", audio_codec="aac", threads=4, verbose=False, logger=None)

    try:
        if video.audio is not None:
            video.audio.write_audiofile(audio_mix_out, fps=44100, nbytes=2, logger=None)
        else:
            audio_mix_out = None
    except Exception:
        audio_mix_out = None

    with open(srt_out, "w", encoding="utf-8") as f:
        f.write(_make_srt(segments))

    for c in clips: c.close()
    video.close()

    return video_out, srt_out, audio_mix_out
