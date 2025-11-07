import numpy as np

try:
    import pyttsx3
    HAS_PYTT = True
except Exception:
    HAS_PYTT = False

from moviepy.audio.AudioClip import AudioArrayClip
from moviepy.editor import AudioFileClip

class TTSAdapter:
    """
    Offline-first TTS using pyttsx3.
    If pyttsx3 is unavailable, we generate silent audio with the estimated duration
    so the video timing still works.
    """
    def __init__(self, voice_name: str = "", rate_wpm: int = 170, language_hint: str = "en-US"):
        self.voice_name = voice_name or ""
        self.rate_wpm = int(rate_wpm)
        self.language = language_hint

        self.engine = None
        if HAS_PYTT:
            try:
                self.engine = pyttsx3.init()
                base = 175  # pyttsx3 scale baseline
                target = int(base * (self.rate_wpm / 170.0))
                self.engine.setProperty("rate", target)

                if self.voice_name:
                    for v in self.engine.getProperty("voices"):
                        if self.voice_name.lower() in (getattr(v, "name", "") or "").lower():
                            self.engine.setProperty("voice", v.id)
                            break
            except Exception:
                self.engine = None

    def _estimate_duration(self, text: str) -> float:
        words = max(1, len(text.split()))
        wps = max(1e-3, self.rate_wpm / 60.0)  # words per second
        return max(0.8, words / wps)

    def synth(self, text: str, out_wav: str) -> float:
        if self.engine is None:
            # Fallback: generate silence
            dur = self._estimate_duration(text)
            sr = 22050
            samples = np.zeros(int(dur * sr), dtype=np.float32)
            clip = AudioArrayClip(samples.reshape(-1,1), fps=sr)
            clip.write_audiofile(out_wav, fps=sr, logger=None)
            clip.close()
            return float(dur)

        # Use real TTS
        self.engine.save_to_file(text, out_wav)
        self.engine.runAndWait()
        # Measure
        a = AudioFileClip(out_wav)
        dur = float(a.duration)
        a.close()
        return dur
