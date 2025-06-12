# server_http.py

import os
import json
import base64
import subprocess
from pathlib import Path
from flask import Flask, request, jsonify

app = Flask(__name__)

# Directory where incoming images are saved
PI_INPUT = Path("pi_input_http")
PI_INPUT.mkdir(exist_ok=True)

@app.route("/plants/health", methods=["POST"])
def plants_health():
    """
    Expects JSON:
      {
        "timestamp": "...",
        "filename": "someName.jpg",
        "image_b64": "<base64-encoded JPEG>"
      }
    Saves the JPEG under pi_input_http/<filename>, then spawns process_image.py.
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No JSON payload"}), 400

    ts      = data.get("timestamp")
    name    = data.get("filename")
    img_b64 = data.get("image_b64")

    if not (ts and name and img_b64):
        return jsonify({"error": "missing fields"}), 400

    # 1) Decode & write the JPEG
    img_path = PI_INPUT / name
    try:
        img_path.write_bytes(base64.b64decode(img_b64))
    except Exception as e:
        return jsonify({"error": f"Failed to write image: {e}"}), 500

    print(f"✅ Saved image {name} to {PI_INPUT}/")

    # 2) Spawn process_image.py (in the same folder) to do the rest.
    #    We use Popen so Flask returns immediately without waiting.
    try:
        subprocess.Popen(
            ["python3", "process_image.py", str(img_path)]
        )
    except Exception as e:
        print(f"❌ Error launching process_image.py: {e}")

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    # Flask listens on 0.0.0.0:8080, so Pi can reach http://<PC_IP>:8080/plants/health
    app.run(host="0.0.0.0", port=8080)