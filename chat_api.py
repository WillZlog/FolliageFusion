#!/usr/bin/env python3
"""
chat_api.py

Flask backend to power Plant Care Chat on camera pages.
Responds based on provided care + health JSON context, with optional best-practice supplementation.
- Env-configurable OpenAI settings.
- Robust error handling and structured prompts.
- Logging for auditing.
"""
import os
import json
import logging
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv

# ——— Load environment & keys ———
load_dotenv()
openai_api_key = os.getenv("OPENAIKEY")
if not openai_api_key:
    raise RuntimeError("Missing OPENAIKEY in environment")

# ——— Configurable model parameters ———
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0"))
MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "512"))

# ——— Initialize Flask + CORS + Logging ———
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat_api")

# ——— OpenAI client ———
client = OpenAI(api_key=openai_api_key)

# ——— Helper: load JSON context for camera ———
def load_camera_context(camera_id: str) -> dict:
    path = os.path.join("finalSuggestions", f"{camera_id}Rec.json")
    if not os.path.isfile(path):
        logger.warning("Context file missing: %s", path)
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed loading %s: %s", path, e)
        return {}

# ——— Endpoint: /api/cameras/<camera_id>/chat ———
@app.route("/api/cameras/<camera_id>/chat", methods=["POST"])
def camera_chat(camera_id: str):
    data = request.get_json(force=True)
    user_msg = (data.get("message") or "").strip()
    if not user_msg:
        return jsonify({"error": "Empty message. Please send your question."}), 400

    ctx = load_camera_context(camera_id)
    if not ctx:
        abort(404, description=f"No context for camera {camera_id}")

    # Separate care vs. health
    care_json = ctx.get("care_recommendations") or ctx.get("recommendations") or {}
    health_json = {k: v for k, v in ctx.items() if k not in ("species", "recommendations", "care_recommendations")}

    species = ctx.get("species", camera_id)
    care_str = json.dumps(care_json, indent=2)
    health_str = json.dumps(health_json, indent=2)

    # Construct system prompt with JSON and best-practice guidance
    system_msg = (
        f"You are a plant care assistant for a {species} tree.\n"
        f"Use the JSON data provided below to inform your responses.\n"
        f"You may also draw on standard {species} care practices (e.g., typical watering frequency) to supplement the data when needed.\n\n"
        "Care recommendations (JSON):\n```json\n" + care_str + "\n```\n"
        "Current health analysis (JSON):\n```json\n" + health_str + "\n```"
        "Keep answers short and consise, but still accurate"
    )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg}
    ]

    logger.info("Request [%s]: %s", camera_id, user_msg)
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            top_p=1
        )
        reply = resp.choices[0].message.content.strip()
        logger.info("Reply [%s]: %s", camera_id, reply)
        return jsonify({"reply": reply})

    except Exception:
        logger.exception("OpenAI API error")
        return jsonify({"error": "AI service error. Please try later."}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    app.run(host="0.0.0.0", port=port)
