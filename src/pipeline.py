#!/usr/bin/env python3
"""
pipeline.py

Called by process_image.py with:
    --image  /path/to/oak_pi_cam_12345.jpg
    --species oak
    --zip     06870

1) Geocode ZIP → lat,lon.
2) generate_tree_care_json (or load existing) via recom.py.
3) mask_out_trunk → leaf‑only PNG.
4) Encode leaf‑only PNG to a base64 data:URL.
5) Send to GPT‑4o (chat_with_json_and_image) to get health JSON.
6) Post‑process leaf_color_match, reasons_unhealthy, etc.
7) Write out final JSON → finalSuggestions/<species>Rec.json
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os
import json
import base64
import certifi
import argparse
from pathlib import Path
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from src.recom import generate_tree_care_json
from openai import OpenAI
import datetime
from PIL import Image
import numpy as np


now = datetime.datetime.utcnow()  # For timestamps

# Ensure we use system certificates for OpenAI
os.environ["SSL_CERT_FILE"] = certifi.where()

# ——— Load environment & API keys ———
load_dotenv()
openai_api_key = os.getenv("OPENAIKEY")
if not openai_api_key:
    raise RuntimeError("Missing OPENAIKEY in environment.")

client = OpenAI(api_key=openai_api_key)

# Directories
BASE_DIR     = Path(__file__).parent
DATA_DIR     = BASE_DIR / "data"
SAVED_DIR    = DATA_DIR / "savedJson"
FINAL_DIR    = DATA_DIR / "finalSuggestions"
IMAGES_DIR   = BASE_DIR.parent / "static" / "images"
SAVED_DIR.mkdir(parents=True, exist_ok=True)
FINAL_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def mask_out_trunk(image_path: Path) -> Path:
    """
    Opens the tree image, converts to HSV, and keeps only "green foliage" pixels.
    Anything non-green (e.g. brown trunk) becomes white. Saves as PNG and returns that path.
    """
    img_rgb = Image.open(image_path).convert("RGB")
    img_hsv = img_rgb.convert("HSV")
    hsv_arr = np.array(img_hsv).astype(np.int16)

    H = hsv_arr[:, :, 0]  # 0–255
    S = hsv_arr[:, :, 1]
    V = hsv_arr[:, :, 2]

    # Broad "green" band: 30 < H < 140
    hue_mask = (H > 30) & (H < 140)
    sat_mask = (S > 20)   # somewhat saturated
    val_mask = (V > 20)   # not too dark

    leaf_mask = hue_mask & sat_mask & val_mask

    arr_rgb = np.array(img_rgb)
    arr_leaf = np.zeros_like(arr_rgb) + 255  # white background
    arr_leaf[leaf_mask] = arr_rgb[leaf_mask]

    leaf_img = Image.fromarray(arr_leaf.astype(np.uint8))
    tmp_path = image_path.parent / f"{image_path.stem}_leaf_only.png"
    leaf_img.save(tmp_path)
    return tmp_path


def get_location_from_zip(zip_code: str) -> (float, float): # type: ignore
    """
    Geocode a US ZIP to (latitude, longitude) using Nominatim.
    """
    geolocator = Nominatim(user_agent="my_geocoder")
    loc = geolocator.geocode(f"{zip_code}, USA")
    if not loc:
        raise ValueError(f"Unable to geocode ZIP {zip_code}.")
    return loc.latitude, loc.longitude


def encode_image_to_data_url(image_path: Path) -> str:
    """
    Reads an image file (JPEG or PNG) and returns a data URL string.
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    raw = image_path.read_bytes()
    ext = image_path.suffix.lstrip(".").lower()
    b64 = base64.b64encode(raw).decode("utf-8")
    return f"data:image/{ext};base64,{b64}"


def chat_with_json_and_image(image_url: str, recommendations: dict) -> dict:
    """
    Sends a multimodal chat to GPT-4o with:
      • system prompt describing the required output schema
      • user message containing care JSON + image_url + date/time + location
    Returns exactly the parsed JSON object from GPT-4o.
    """
    system_prompt = (
        "You are a helpful assistant who, when given:\n"
        "  1) a base64-encoded image of a tree/plant\n"
        "  2) its JSON care recommendations (including seasonal hex-color ranges)\n\n"
        "You will return exactly one JSON object (no Markdown fences, no extra commentary) containing:\n"
        '  • "species": the species name (string)\n'
        '  • "healthy": "YES" or "NO"\n'
        '  • "percentage": a percentage value (0–100) on how healthy the tree is.\n'
        '  • "observed_leaf_color": a single hex code (e.g. "#RRGGBB") for the dominant leaf color\n'
        '    (⚠️Ignore bark/trunk/branches—sample only leaf/foliage pixels.)\n'
        '  • "expected_leaf_colors": an array of five hex codes for this season\'s recommended leaf colors\n'
        '  • "reasons_unhealthy": if `"healthy" == "NO"`, an array of exactly three short strings; if `"healthy" == "YES"`, an empty array\n'
        '  • "treatment_recommendations": an array of three strings with concrete steps to improve plant health\n'
        "  • 'Watering Schedule': recommended watering frequency MUST BE A NUMBER. (e.g. for once a week do 7, for twice a week do 3 etc.).\n"
        '  • "timestamp": current UTC date/time in ISO 8601 (e.g. "2025-06-02T22:39:11Z")\n\n'
        "⚠️IMPORTANT: Do not sample trunk or brown/bark areas—focus only on green leaf pixels.\n\n"
        "Strictly output only valid JSON—no Markdown fences, no extra keys, no commentary.\n"
    )

    recs_json_str = json.dumps(recommendations)

    user_message = {
        "role": "user",
        "content": (
            "Here are the care recommendations (in JSON):\n"
            f"{recs_json_str}\n\n"
            "Analyze the plant image and those recommendations, then return the required JSON.\n\n"
            f"The current date/time is {now.isoformat()}Z.\n"
            f"The tree's location is Lat: {recommendations.get('latitude')}, Lon: {recommendations.get('longitude')}."
        ),
        "image_url": image_url
    }

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            user_message
        ],
        response_format={"type": "json_object"},
        max_tokens=800,
    )

    try:
        assistant_msg = response.choices[0].message
    except (AttributeError, IndexError):
        raise RuntimeError(f"Unexpected OpenAI response:\n{response}")

    content = getattr(assistant_msg, "content", None)
    if content is None:
        raise RuntimeError(f"No 'content' in assistant response:\n{response}")

    if isinstance(content, str) and content.startswith("```json") and content.endswith("```"):
        content = content[len("```json"):-len("```")].strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse JSON from assistant:\n{content}\nError: {e}")


def ensure_recommendations_exist(species: str, lat: float, lon: float) -> dict:
    """
    If savedJson/{species}Care.json exists, return it.
    Otherwise, call recom.generate_tree_care_json(...) and save the result.
    """
    SAVED_DIR.mkdir(exist_ok=True)
    json_path = SAVED_DIR / f"{species}Care.json"

    if json_path.exists():
        with open(json_path, "r") as f:
            info = json.load(f)
            info["latitude"] = lat
            info["longitude"] = lon
            return info

    info = generate_tree_care_json(
        species_name=species,
        latitude=lat,
        longitude=lon,
        output_file_path=str(json_path)
    )
    if not info:
        raise RuntimeError("Failed to generate tree care JSON.")
    info["latitude"] = lat
    info["longitude"] = lon
    return info


def main():
    parser = argparse.ArgumentParser(
        description="Run tree care + health pipeline on a single image."
    )
    parser.add_argument("--image",   required=True, help="Path to the JPEG image (species_<orig>.jpg)")
    parser.add_argument("--species", required=True, help="Species name (e.g. 'oak', 'pine')")
    parser.add_argument("--zip",     required=True, help="5-digit US ZIP code for location")
    args = parser.parse_args()

    image_path = Path(args.image)
    species    = args.species.strip().lower()
    zip_code   = args.zip.strip()

    if not image_path.is_file():
        print(f"ERROR: Image not found: {image_path}")
        return

    if not (zip_code.isdigit() and len(zip_code) == 5):
        print("ERROR: ZIP code must be exactly 5 digits.")
        return

    # 1) Geocode ZIP → lat, lon
    try:
        lat, lon = get_location_from_zip(zip_code)
    except Exception as e:
        print(f"Geocoding error: {e}")
        return

    print(f"\n>> [Pipeline] Ensuring care JSON for '{species}' at ZIP {zip_code} ({lat:.5f}, {lon:.5f}) …")
    try:
        recommendations = ensure_recommendations_exist(species, lat, lon)
    except Exception as e:
        print(f"Failed to get/generate recommendations: {e}")
        return

    print(" ↪ Care recommendations loaded.\n")

    # 2) Mask out trunk → leaf-only image
    print(">> [Pipeline] Masking out trunk/bark …")
    try:
        leaf_only_path = mask_out_trunk(image_path)
    except Exception as e:
        print(f"⚠️ Warning: could not mask out trunk. Using original image. ({e})")
        leaf_only_path = image_path

    print(f" ↪ Leaf-only image at {leaf_only_path.name}\n")

    # 3) Encode leaf-only or original image to data URL
    print(">> [Pipeline] Encoding image …")
    try:
        data_url = encode_image_to_data_url(leaf_only_path)
    except Exception as e:
        print(f"ERROR: Could not encode image: {e}")
        return

    print(" ↪ Image encoded.\n")

    # 4) Send to OpenAI for diagnosis
    print(">> [Pipeline] Sending to OpenAI for plant health diagnosis …")
    try:
        diagnosis = chat_with_json_and_image(data_url, recommendations)
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return

    # 5) Post‑process leaf_color_match if needed
    observed_hex = diagnosis.get("observed_leaf_color")
    expected_list = diagnosis.get("expected_leaf_colors", [])

    try:
        obs_val = int(observed_hex.lstrip("#"), 16)
        exp_vals = [int(h.lstrip("#"), 16) for h in expected_list]
    except Exception:
        exp_vals = []
        obs_val = None

    if exp_vals and obs_val is not None:
        lo, hi = min(exp_vals), max(exp_vals)
        correct_match = "YES" if (lo <= obs_val <= hi) else "NO"

        if diagnosis.get("leaf_color_match") != correct_match:
            diagnosis["leaf_color_match"] = correct_match
            if correct_match == "YES":
                new_reasons = []
                for reason in diagnosis.get("reasons_unhealthy", []):
                    if "leaf color" in reason.lower():
                        continue
                    new_reasons.append(reason)
                diagnosis["reasons_unhealthy"] = new_reasons
            else:
                mismatch_msg = "Observed leaf color does not match expected range"
                diagnosis.setdefault("reasons_unhealthy", [])
                if mismatch_msg not in diagnosis["reasons_unhealthy"]:
                    diagnosis["reasons_unhealthy"].insert(0, mismatch_msg)

    # 6) Write out the final JSON to finalSuggestions/{species}Rec.json
    output_path = FINAL_DIR / f"{species}Rec.json"
    try:
        with open(output_path, "w") as out_f:
            json.dump(diagnosis, out_f, indent=2)
        print(f"\n✅ Pipeline complete. Wrote JSON to {output_path}")
    except Exception as e:
        print(f"ERROR: Failed to write final JSON: {e}")


if __name__ == "__main__":
    main()