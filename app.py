from flask import Flask, render_template, request, send_from_directory, jsonify
import os, uuid
from utils.tts_adapter import TTSAdapter
from utils.video_builder import build_video_from_script

app = Flask(__name__)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(APP_ROOT, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    script = (request.form.get("script") or "").strip()
    language = request.form.get("language", "en-US")
    voice = (request.form.get("voice") or "").strip()
    style = request.form.get("style", "gradient")  # gradient | solid
    aspect = request.form.get("aspect", "vertical")  # vertical | square | landscape
    target_seconds = int(request.form.get("target_seconds") or 60)

    if not script:
        return jsonify({"ok": False, "error": "Script cannot be empty."}), 400

    job_id = str(uuid.uuid4())[:8]
    job_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)

    tts = TTSAdapter(voice_name=voice, rate_wpm=170, language_hint=language)
    try:
        video_path, srt_path, audio_path = build_video_from_script(
            script=script,
            out_dir=job_dir,
            tts=tts,
            style=style,
            target_seconds=target_seconds,
            aspect=aspect
        )
    except Exception as e:
        return jsonify({"ok": False, "error": f"Generation failed: {e}"}), 500

    rel_video = os.path.relpath(video_path, OUTPUT_DIR).replace("\\", "/")
    rel_srt = os.path.relpath(srt_path, OUTPUT_DIR).replace("\\", "/") if srt_path else None
    rel_audio = os.path.relpath(audio_path, OUTPUT_DIR).replace("\\", "/") if audio_path else None

    return jsonify({
        "ok": True,
        "job_id": job_id,
        "video_url": f"/download/{rel_video}",
        "srt_url": f"/download/{rel_srt}" if rel_srt else None,
        "audio_url": f"/download/{rel_audio}" if rel_audio else None
    })

@app.route("/download/<path:path>", methods=["GET"])
def download(path):
    full_path = os.path.join(OUTPUT_DIR, os.path.normpath(path))
    if not os.path.isfile(full_path):
        return "Not found", 404
    return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path), as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860, debug=True)
