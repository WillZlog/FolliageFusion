import io
import time
import base64
import requests
from datetime import datetime
from picamera import PiCamera

# ——— CONFIGURATION ———
PC_IP       = "192.168.1.42"    # <--- replace with your PC’s LAN IP
PC_PORT     = 5000
ENDPOINT    = f"http://{PC_IP}:{PC_PORT}/plants/health"

CAPTURE_DIR = "/home/pi/captures"  # local folder to save a copy (optional)
DELAY_SEC   = 30                   # how often to capture & POST

# Create the capture directory if it doesn't exist
import os
os.makedirs(CAPTURE_DIR, exist_ok=True)

# ——— FUNCTIONS ———

def capture_image(camera: PiCamera, filename: str) -> bytes:
    """
    Capture a JPEG image into memory and return its bytes.
    Also optionally save a copy to disk under CAPTURE_DIR/filename.
    """
    stream = io.BytesIO()
    camera.capture(stream, format="jpeg")
    image_bytes = stream.getvalue()

    # Optionally, write a physical copy to CAPTURE_DIR
    copy_path = os.path.join(CAPTURE_DIR, filename)
    with open(copy_path, "wb") as f:
        f.write(image_bytes)

    return image_bytes

def encode_image_to_b64(jpeg_bytes: bytes) -> str:
    """
    Take raw JPEG bytes and return a base64-encoded ASCII string.
    """
    return base64.b64encode(jpeg_bytes).decode("ascii")

def send_http_post(timestamp: str, filename: str, image_b64: str):
    """
    POST a JSON payload {"timestamp", "filename", "image_b64"} to the Flask server.
    """
    payload = {
        "timestamp": timestamp,
        "filename": filename,
        "image_b64": image_b64
    }
    try:
        resp = requests.post(ENDPOINT, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"[{timestamp}] ✅ Posted {filename} (status code {resp.status_code})")
    except requests.RequestException as e:
        print(f"[{timestamp}] ❌ HTTP error while posting {filename}: {e}")

# ——— MAIN LOOP ———

def main():
    camera = PiCamera()
    # Optional: camera.rotation = 180  # if your Pi Camera is upside down
    camera.resolution = (1024, 768)
    time.sleep(2)  # Allow camera sensor to warm up

    try:
        while True:
            # 1) Build timestamp + filename
            ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            fn = f"pi_cam_{int(time.time())}.jpg"

            # 2) Capture to memory
            jpeg = capture_image(camera, fn)

            # 3) Encode to base64
            b64 = encode_image_to_b64(jpeg)

            # 4) Send to PC
            send_http_post(ts, fn, b64)

            # 5) Wait before next capture
            time.sleep(DELAY_SEC)

    except KeyboardInterrupt:
        print("\nInterrupted by user, shutting down.")
    finally:
        camera.close()

if __name__ == "__main__":
    main()