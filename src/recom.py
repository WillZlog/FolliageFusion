import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import requests
import os
import json
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api._api import YouTubeTranscriptApi
from openai import OpenAI
from webcolors import hex_to_name, CSS3
import ssl

requests.packages.urllib3.disable_warnings()
requests.Session.verify = False


from pathlib import Path

load_dotenv()

openai_api_key = os.getenv("OPENAIKEY")
if not openai_api_key:
    raise RuntimeError("Missing OPENAIKEY in environment. Check your .env.")

youtubeAPIKEY = os.getenv("YOUTUBEAPI")
openWeatherMapAPIKEY = os.getenv("OPENWEATHERMAP_API_KEY")

YOUTUBE_PROXY_URL = os.getenv("YOUTUBE_PROXY_URL")

ssl._create_default_https_context = ssl._create_unverified_context #!!!ONLY FOR TESTING NEED FIX

def get_closest_color_name(hex_color):
    """Converts a hex color code to its closest CSS3 color name."""
    try:
        return hex_to_name(hex_color, spec=CSS3)
    except ValueError:
        return "Color name not found"

def get_youtube_transcript_text_only(video_id):
    """Fetches the transcript of a YouTube video (if available)."""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(
            video_id,
            proxies={"http": YOUTUBE_PROXY_URL, "https": YOUTUBE_PROXY_URL}
        )
        return " ".join(entry["text"] for entry in transcript).strip()
    except Exception as e:
        # Silent fail if no transcript or proxy issue
        print(f"Error fetching transcript for video {video_id}: {e}")
        return None

def get_youtube_id_and_transcript(species_name):
    """Searches YouTube for “How to care for {species_name}” and returns the first transcriptable video."""
    # Swap in/out HTTP_PROXY so Google client uses our Webshare proxy
    original_http = os.environ.get("HTTP_PROXY")
    original_https = os.environ.get("HTTPS_PROXY")
    # os.environ["HTTP_PROXY"] = YOUTUBE_PROXY_URL
    # os.environ["HTTPS_PROXY"] = YOUTUBE_PROXY_URL

    vid_id = None
    transcript_text = None
    try:
        youtube = build("youtube", "v3", developerKey=youtubeAPIKEY)
        search_query = f"How to care for {species_name}"
        results = (
            youtube.search()
                   .list(part="snippet", q=search_query, maxResults=4)
                   .execute()
        )
        video_ids = [
            item["id"]["videoId"]
            for item in results.get("items", [])
            if item["id"].get("videoId")
        ]

        for vid in video_ids:
            txt = get_youtube_transcript_text_only(vid)
            if txt:
                vid_id = vid
                transcript_text = txt
                break
        return vid_id, transcript_text

    except HttpError as e:
        print(f"YouTube Data API HTTP error: {e}")
        return None, None
    except Exception as e:
        print(f"Unexpected YouTube error: {e}")
        return None, None
    finally:
        # Restore original proxy settings
        if original_http is not None:
            os.environ["HTTP_PROXY"] = original_http
        else:
            os.environ.pop("HTTP_PROXY", None)

        if original_https is not None:
            os.environ["HTTPS_PROXY"] = original_https
        else:
            os.environ.pop("HTTPS_PROXY", None)

def get_recommendations_from_openai(transcript_content, species_name):
    """
    Uses OpenAI’s chat API (via the v0.28+ `OpenAI` SDK) to get a raw-JSON response.
    """

    client = OpenAI(api_key=openai_api_key)

    system_prompt = (
        "You are an intuitive assistant providing care recommendations for a given tree species. "
        "You will be provided with the species and a video transcript. Your response **MUST be a raw JSON object, "
        "with no markdown formatting.** The JSON must have keys:\n"
        "  • \"Temp\": ideal temperature range in both °F and °C (e.g. \"60-75°F / 15-24°C\").\n"
        "  • \"Humidity\": ideal humidity level (e.g. \"40-60%\").\n"
        "  • \"Soil PH\": ideal soil pH range (e.g. \"6.0-7.0\").\n"
        "  • \"Leaf color\": an object with keys \"Spring\", \"Summer\", \"Autumn\", \"Winter\"; "
        "each is a list of five hex codes equally spaced over that season’s typical leaf range.\n"
        "  • \"Trunk color\": same structure (keys for each season, lists of five hex codes).\n"
        "  • \"Recommendations\": a string of general care instructions for that species, "
         "  • \"Watering Schedule\": recommended watering frequency MUST BE A NUMBER. (e.g. for once a week do 7, for twice a week do 3 etc.).\n"
        "derived from the transcript and any outside resources you access."
        
    )

    user_prompt = (
        f"Based on the transcript and any outside resources, give care recommendations for a {species_name} tree. "
        f"Transcript: {transcript_content}"
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
        raw = resp.choices[0].message.content
        if raw and isinstance(raw, str):
            if raw.startswith("```json") and raw.endswith("```"):
                raw = raw[len("```json"): -len("```")].strip()
            return raw
        else:
            return "{}"
    except Exception as e:
        print(f"OpenAI error: {e}")
        return "{}"

def get_weather_data(latitude, longitude):
    """Fetch current weather from OpenWeatherMap (imperial units)."""
    if not openWeatherMapAPIKEY:
        print("Warning: OPENWEATHERMAP_API_KEY not set, skipping weather.")
        return None

    try:
        url = (
            f"http://api.openweathermap.org/data/2.5/weather?"
            f"lat={latitude}&lon={longitude}&appid={openWeatherMapAPIKEY}&units=imperial"
        )
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        temp_f = data["main"]["temp"]
        hum = data["main"]["humidity"]
        descr = data["weather"][0]["description"]
        city = data["name"]
        temp_c = (temp_f - 32) * 5/9
        return {
            "temperature_f": round(temp_f, 1),
            "temperature_c": round(temp_c, 1),
            "humidity": hum,
            "description": descr,
            "city": city,
        }
    except Exception as e:
        print(f"Error fetching weather: {e}")
        return None

def generate_tree_care_json(
    species_name: str,
    latitude: float,
    longitude: float,
    output_file_path: str = str(((Path(__file__).parent).parent / "static" / "data" / "savedJson" / "SavedRec.json"))
) -> dict:
    """
    1) Pull YouTube transcript
    2) Ask OpenAI for JSON recommendations
    3) Pull current weather
    4) Combine into one dict, save to disk, and return it.
    """
    # 1. YouTube transcript
    vid_id, transcript = get_youtube_id_and_transcript(species_name)
    if not transcript:
        print("Could not find any transcript. ⚠️ Going to default")
        transcript = f"Caring for a {species_name} tree."

    # 2. OpenAI JSON string
    raw_json = get_recommendations_from_openai(transcript, species_name)
    if not raw_json:
        print("OpenAI did not return any JSON.")
        return {}

    try:
        rec_data = json.loads(raw_json)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON from OpenAI:\n{e}\nRaw: {raw_json}")
        return {}

    # 3. Weather lookup
    weather = get_weather_data(latitude, longitude) or {}

    # 4. Combine & save
    out = {
        "species": species_name,
        "recommendations": rec_data,
        "current_weather": weather,
    }

    out_dir = os.path.dirname(output_file_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    try:
        with open(output_file_path, "w") as f:
            json.dump(out, f, indent=2)
        print(f"Successfully saved to {output_file_path}")
    except Exception as e:
        print(f"Error writing file: {e}")
        return {}

    return out

# If you ever run this module directly, you can prompt for species & location:
if __name__ == "__main__":
    species = input("Species? ").strip()
    try:
        lat = float(input("Latitude? "))
        lon = float(input("Longitude? "))
    except ValueError:
        print("Invalid coordinates.")
        exit(1)

    generate_tree_care_json(species, lat, lon)