# AI 1-Minute Video Generator (Flask)
Builds vertical ≤60s videos from a multi-line script. Each line becomes a scene.
Voice-over via pyttsx3 when available; silent fallback otherwise.

## Local
pip install -r requirements.txt
python app.py   # http://localhost:7860

## Render (Free)
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
