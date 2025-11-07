import os, uuid
from typing import List, Tuple
import numpy as np

from moviepy.editor import (
    AudioFileClip, CompositeVideoClip, TextClip, ImageClip, concatenate_videoclips
)
from moviepy.video.fx.all import resize
from moviepy.audio.fx.all import audio_fadein, audio_fadeout

VIDEO_SIZES = {
    "vertical": (1080, 1920),
    "square": (1080, 1080),
    "landscape": (1920, 1080),
}

def _wrap_lines(text: str, max_chars: int = 36) -> str:
    words = text.split()
    lines, buf = [], []
    for w in words:
        candidate = (" ".join(buf + [w])).strip()
        if len(candidate) > max_chars and buf:
            lines.append(" ".join(buf))
            buf = [w]
        else:
            buf.append(w)
    if buf:
        lines.append(" ".join(buf))
    return "\\n".join(lines)

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

def _make_scene(text: str, audio_path: str, size: Tuple[int,int], style: str, seed: int):
    if style == "solid":
        bg_img = _solid_bg(size)
    else:
        bg_img = _gradient_bg(size, seed)

    bg = ImageClip(bg_img).set_duration(AudioFileClip(audio_path).duration)

    title = TextClip(
        _wrap_lines(text, max_chars=36),
        fontsize=78, font="Arial-Bold", color="white", method="caption",
        size=(size[0] - 120, None), align="center"
    ).set_position(("center","center"))

    dur = bg.duration
    def zoom(t):
        start, end = 1.0, 1.06
        return start + (end - start) * (t / max(0.01, dur))

    bg_zoom = bg.fx(resize, lambda t: zoom(t))

    voice = AudioFileClip(audio_path)
    voice = audio_fadein(voice, 0.05).fx(audio_fadeout, 0.1)

    scene = CompositeVideoClip([bg_zoom, title]).set_duration(voice.duration).set_audio(voice)
    return scene

def _make_srt(segments: List[Tuple[str, float]]) -> str:
    def fmt(ts: float) -> str:
        ms = int((ts - int(ts)) * 1000)
        s = int(ts) % 60
        m = (int(ts) // 60) % 60
        h = int(ts) // 3600
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    out = []
    t = 0.0
    for i, (line, dur) in enumerate(segments, 1):
        start, end = t, t + dur
        out.append(f"{i}\\n{fmt(start)} --> {fmt(end)}\\n{line}\\n")
        t = end
    return "\\n".join(out)

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
        # Trim to fit target length
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

    # Write video
    video.write_videofile(video_out, fps=30, codec="libx264", audio_codec="aac", threads=4, verbose=False, logger=None)

    # Export audio track if present
    try:
        if video.audio is not None:
            video.audio.write_audiofile(audio_mix_out, fps=44100, nbytes=2, logger=None)
        else:
            audio_mix_out = None
    except Exception:
        audio_mix_out = None

    # Write SRT
    with open(srt_out, "w", encoding="utf-8") as f:
        f.write(_make_srt(segments))

    # Cleanup
    for c in clips: c.close()
    video.close()

    return video_out, srt_out, audio_mix_out
