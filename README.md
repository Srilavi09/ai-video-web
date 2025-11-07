# AI 1-Minute Video Generator (Flask)

Create 1‑minute vertical videos with automatic voice‑over. Each line of your script becomes a scene. Built with Flask + MoviePy + pyttsx3 (offline TTS).

## Run Locally
1) Install Python 3.10+ and FFmpeg (MoviePy requires it).
2) Install deps:
```
pip install -r requirements.txt
```
3) Start:
```
python app.py
```
Open http://localhost:7860

## Deploy on Render (Free)
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
- Environment: Python
- Instance Type: Free

## Notes
- If no OS voices are available, the app will generate silent audio (for timing).
- To use Telugu/Hindi voices, install those voices in your OS.
