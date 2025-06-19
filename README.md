# 🌿 FolliageFusion

**FolliageFusion** is a smart, AI-powered tree health monitoring system designed for use with Raspberry Pi + Arduino-based cameras. It automatically takes photos of trees, identifies the species, and uses AI (via OpenAI + weather data + transcripts) to generate customized care recommendations based on real-time imagery and location data.

> **Project Status**: 🚧 In active beta — data processing is complete, UI and user auth are in progress.

---

## 📸 What It Does

* Takes automatic snapshots every 10 minutes via a Raspberry Pi camera
* Sends the image to a multi-server backend using Flask
* Processes the image to determine:

  * Tree species (e.g. birch, oak, spruce)
  * Zipcode/location
* Generates a care recommendation file using:

  * ChatGPT
  * Weather APIs
  * Watering data
  * YouTube video transcript for top search result
* Displays:

  * Most recent image
  * Species
  * Health score (%)
  * Watering schedule
  * Maintenance and treatment suggestions
  * AI-generated care plan

---

## 🧠 Tech Stack

* **Python + Flask** (multi-server architecture)
* **Raspberry Pi** + camera module
* **OpenAI GPT** (for recommendation synthesis)
* **HTML/CSS frontend** (in development)
* **SQLite** (for user auth and camera mapping)
* **JSON-based pipeline** for species-specific logic

---

## 📂 Project Structure (simplified)

```
FolliageFusion/
├── main.py                  # launches all servers
├── requirements.txt
├── .env              
│
├── src/
│   ├── server_http.py       # receives image, triggers pipeline
│   ├── chat_api.py          # AI interfacing for care generation
│   ├── recom.py             # parses and builds care guide
│   ├── process_image.py     # image preprocessing
│   ├── auth/
│   │   └── auth_api.py      # user account logic
│   └── server/
│       └── piServer.py      # Pi-specific network server
│
├── templates/
│   ├── index.html
│   ├── admin.html
│   └── camera.html
├── static/
│   ├── styles.css
│   └── images/
├── data/
    ├── cameras.json
    ├── savedJson/
    └── finalSuggestions/
        ├── birchRec.json
        ├── oakRec.json
        └── spruceRec.json
```

---

## 🧪 Requirements

* Raspberry Pi with camera module (or substitute setup)
* Python 3.8+
* An OpenAI API key
* Youtube API key
* Flask (multi-server)
* Internet access for API calls + YouTube transcript fetching

> The system also works on Windows machines for local testing or mock input.

---

## 🚀 Getting Started

1. **Clone the repo**

   ```bash
   git clone https://github.com/yourusername/folliagefusion.git
   cd folliagefusion
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Create `.env` file**

   ```env
   OPENAI_API_KEY=your_openai_key_here
   YOUTUBEAPI=your_youtube_key_here
   OPENWEATHERMAP_API_KEY=weatherkeyhere
   ```
    *WEATHER KEY IS OPTIONAL*

4. **Run the system**

   ```bash
   python main.py
   ```

   This will launch:

   * `server_http.py` – handles Pi image uploads
   * `chat_api.py` – generates care plans
   * `auth_api.py` – manages user accounts

5. **Connect your Pi + camera**

   * Once running, your Raspberry Pi will automatically begin submitting tree photos every 10 minutes.

---

## 🔒 Authentication & Admin

* User accounts are created and managed via `auth_api.py`
* Admins can assign specific cameras to user accounts
* Admin-only dashboard is accessible via `/admin`

---

## 🚣 Roadmap

✅ Core AI pipeline complete
✅ Multi-species support
✅ Automated image ingestion
✅ Basic care plan generation
🔧 Frontend UI + login system
🔧 Expand species library
🔧 Notifications / mobile interface
🔧 Deployment packaging for SD card images

---

## 🧑‍💻 Maintainers

Built by \[@WillZLog] and \[Carson] — high school researchers and builders passionate about AI + environmental sustainability.

---

## 📄 License

MIT License (or specify your own)

---

## 📸 Demo (coming soon)

> Screenshots or demo video will be added once UI development is complete.
