import os
import json
import base64
import certifi
from pathlib import Path
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from recom import generate_tree_care_json
from openai import OpenAI
import datetime

now = datetime.datetime.now()

os.environ["SSL_CERT_FILE"] = certifi.where()

# ---- Setup & load keys ----
load_dotenv()
openai_api_key = os.getenv("OPENAIKEY")
if not openai_api_key:
    raise RuntimeError("Missing OPENAIKEY in environment. Check your .env.")

client = OpenAI(api_key=openai_api_key)

# Where we store generated care JSONs and captured images
BASE_DIR   = Path(__file__).parent
SAVED_DIR  = BASE_DIR / "savedJson"
IMAGES_DIR = BASE_DIR / "images"


def get_location_from_zip(zip_code: str) -> (float, float):
    """
    Uses Nominatim (OpenStreetMap) to geocode a 5‑digit US ZIP.
    Returns (latitude, longitude).
    Raises ValueError if geocoding fails.
    """
    geolocator = Nominatim(user_agent="my_geocoder")
    loc = geolocator.geocode(f"{zip_code}, USA")
    if not loc:
        raise ValueError(f"Unable to geocode ZIP {zip_code}.")
    return loc.latitude, loc.longitude

userLat, userLong = get_location_from_zip("06870")
print(userLat, userLong)
def ensure_recommendations_exist(species: str, lat: float, lon: float) -> dict:
    """
    If savedJson/{species}Care.json exists, load it.
    Otherwise, call generate_tree_care_json(...) → save to that file → return it.
    """
    SAVED_DIR.mkdir(exist_ok=True)
    json_path = SAVED_DIR / f"{species}Care.json"

    if json_path.exists():
        with open(json_path, "r") as f:
            return json.load(f)

    # Otherwise generate & save
    info = generate_tree_care_json(
        species_name=species,
        latitude=lat,
        longitude=lon,
        output_file_path=str(json_path)
    )
    if not info:
        raise RuntimeError("Failed to generate tree care JSON.")
    return info


def encode_image_to_data_url(image_path: Path) -> str:
    """
    Reads an image file and returns a data URL (base64‑encoded).
    Throws FileNotFoundError if missing.
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    raw = image_path.read_bytes()
    b64 = base64.b64encode(raw).decode("utf-8")
    return f"data:image/{image_path.suffix.lstrip('.')};base64,{b64}"


def chat_with_json_and_image(image_url: str, recommendations: dict) -> dict:
    """
    Sends one multimodal message (text + image) to GPT-4o
    and returns exactly the parsed JSON object from the assistant.
    """
    system_prompt = (
        "You are a helpful assistant who, when given:\n"
        "  1) a base64-encoded image of a tree/plant\n"
        "  2) its JSON care recommendations (including seasonal hex-color ranges)\n\n"
        "You will return exactly one JSON object (no Markdown fences, no extra commentary) containing:\n"
        '  • "healthy": "YES" or "NO"\n'
        '  • "observed_leaf_color": a single hex code (e.g. "#RRGGBB") for the dominant leaf color\n'
        '  • "expected_leaf_colors": an array of five hex codes for this season’s recommended leaf colors\n'
        '  • "reasons_unhealthy": if "healthy" == "NO", an array of exactly three short strings explaining why; if "healthy" == "YES", return an empty array\n'
        '  • "treatment_recommendations": an array of three strings with concrete steps to improve plant health\n'
        '  • "timestamp": current UTC date/time in ISO 8601 format\n\n'
        "Strictly output only valid JSON—no Markdown fences, no extra keys, no commentary."
    )

    # Convert the recommendations dict to a JSON string for the user message
    recs_json_str = json.dumps(recommendations)

    # Build the user message with both the JSON string and the image URL
    user_message = {
        "role": "user",
        "content": (
            "Here are the care recommendations (in JSON):\n"
            f"{recs_json_str}\n\n"
            "Analyze the plant image and those recommendations, then return the required JSON."
            f"the current date/time is {now}"
            f"the trees location is Lat: {userLat}, Long: {userLong}"
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
        raise RuntimeError(f"Unexpected OpenAI response structure:\n{response}")

    content = getattr(assistant_msg, "content", None)
    if content is None:
        raise RuntimeError(f"No 'content' field in assistant response:\n{response}")

    # Strip any ```json fences if present
    if isinstance(content, str) and content.startswith("```json") and content.endswith("```"):
        content = content[len("```json"):-len("```")].strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse JSON from assistant:\n{content}\nError: {e}")


def main():
    # 1) Prompt for ZIP code
    zip_code = input("Enter your 5‑digit ZIP code: ").strip()
    if not zip_code.isdigit() or len(zip_code) != 5:
        print("Error: ZIP code must be exactly 5 digits.")
        return

    try:
        lat, lon = get_location_from_zip(zip_code)
    except ValueError as e:
        print(f"Geocoding error: {e}")
        return

    # 2) Prompt for species
    species = input("Enter tree species (e.g. spruce, oak): ").strip().lower()
    if not species:
        print("Error: Species cannot be blank.")
        return

    print(f"\n>> Step 1: Ensuring care‑recommendation JSON for '{species}' exists…")
    try:
        recommendations = ensure_recommendations_exist(species, lat, lon)
    except Exception as e:
        print(f"Failed to get/generate recommendations: {e}")
        return

    print(f"Recommendations for '{species}' loaded.\n")

    # 3) Locate the image
    image_path = IMAGES_DIR / f"{species}Image.png"
    if not image_path.exists():
        print(f"Error: Expected image at '{image_path}'. Please place a photo there.")
        return

    # 4) Encode the image
    try:
        print(">> Step 2: Encoding image…")
        data_url = encode_image_to_data_url(image_path)
    except FileNotFoundError as e:
        print(e)
        return

    print(f"Image '{image_path.name}' loaded and encoded.\n")

    # 5) Call the multimodal chat for diagnosis
    print(">> Step 3: Sending to OpenAI for plant health diagnosis…")
    try:
        diagnosis = chat_with_json_and_image(data_url, recommendations)
        observed_hex = diagnosis.get("observed_leaf_color")
        expected_list = diagnosis.get("expected_leaf_colors", [])

        try:
            # Convert "#RRGGBB" → int
            obs_val = int(observed_hex.lstrip("#"), 16)
            exp_vals = [int(h.lstrip("#"), 16) for h in expected_list]
        except Exception:
            # If anything weird happened (e.g. missing fields), skip the fix
            exp_vals = []
            obs_val = None

        if exp_vals and obs_val is not None:
            lo, hi = min(exp_vals), max(exp_vals)
            correct_match = "YES" if (lo <= obs_val <= hi) else "NO"

            # Only overwrite if the model got it wrong:
            if diagnosis.get("leaf_color_match") != correct_match:
                diagnosis["leaf_color_match"] = correct_match

                # If we flipped to YES, strip out any “leaf color mismatch” reason
                if correct_match == "YES":
                    new_reasons = []
                    for reason in diagnosis.get("reasons_unhealthy", []):
                        # drop any phrase that mentions leaf‑color mismatch
                        if "leaf color" in reason.lower() or "leaf colour" in reason.lower():
                            continue
                        new_reasons.append(reason)
                    diagnosis["reasons_unhealthy"] = new_reasons

                # If we flipped to NO, you might want to add a reason. For example:
                else:
                    diagnosis.setdefault("reasons_unhealthy", [])
                    # only add it if it isn’t already there
                    mismatch_msg = "Observed leaf color does not match expected range"
                    if mismatch_msg not in diagnosis["reasons_unhealthy"]:
                        diagnosis["reasons_unhealthy"].insert(0, mismatch_msg)

    except Exception as e:
        print(f"OpenAI API error: {e}")
        return

    # 6) Print and save the JSON result
    output_path = BASE_DIR / "finalSuggestions" / f"{species}Rec.json"
    (BASE_DIR / "finalSuggestions").mkdir(exist_ok=True)

    print("\n=== Plant Health Diagnosis ===")
    print(json.dumps(diagnosis, indent=2))

    with open(output_path, "w") as out_f:
        json.dump(diagnosis, out_f, indent=2)
        print(f"\nWrote data to {output_path}")


if __name__ == "__main__":
    main()