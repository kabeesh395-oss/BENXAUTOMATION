# AutoClip AI — standalone local app

A separate, self-hosted app for turning videos and VODs into vertical Shorts. Transcription, highlight selection and metadata generation run locally; YouTube publishing uses the official YouTube Data API with your own OAuth consent.

## Features

- Upload local MP4/MKV/MOV/WebM/AVI or submit a supported VOD URL.
- Local Faster-Whisper transcription and local Ollama (qwen2.5:3b) highlight selection.
- 9:16 H.264 clips with burned-in subtitles.
- Locally generated YouTube title, description and tags for each clip.
- Connect a YouTube channel with OAuth and upload up to five clips with public visibility.
- Daily queue: add one source URL for a selected date/time; the local scheduler downloads, processes and publishes up to five public Shorts.
- SQLite-backed schedule queue survives app restarts. The computer, Ollama and AutoClip server must be running at the scheduled time.
- Livestream URL capture records until the stream ends; it is not instant live clipping.

## Windows setup

Run from this folder:

    py -3.11 -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r requirements-dev.txt

Install FFmpeg and add it to PATH. Install Ollama and pull the local model:

    ollama pull qwen2.5:3b
    ollama serve

Start the app:

    python -m uvicorn autoclip_app.app:app --host 127.0.0.1 --port 8765

Open http://127.0.0.1:8765.

## One-time YouTube setup

1. Open Google Cloud Console and create/select a project.
2. Enable YouTube Data API v3.
3. Configure the OAuth consent screen and add your Google account as a test user if the app is in Testing.
4. Create an OAuth Client ID with application type Desktop app.
5. Download its JSON file and save it as autoclip-app/client_secrets.json (same folder as this README). Do not commit or share this file.
6. In AutoClip, click Connect YouTube, sign in to the Google account that owns the channel, and approve the YouTube upload permission. The refresh token is stored locally under data/youtube_token.json; the whole data/ folder is git-ignored.

After connecting, add one source link in Daily publisher, choose the date/time (India local time), and schedule it. At the scheduled time the app creates up to five clips and uploads each with public visibility. You can also submit a VOD URL immediately with the public-upload checkbox enabled.

## Important operational limits

- Public uploads go live without a review step. Check source rights, generated metadata and clips before scheduling. Only repurpose videos you own or have permission to use.
- YouTube API access/quota is controlled by Google Cloud. Current documentation describes a separate upload quota bucket; check your project quota in Google Cloud Console.
- Scheduled jobs run on this computer. If Windows sleeps, the app is closed, the network is offline, or Ollama is stopped, the schedule cannot run at its planned time. Keep the PC awake and the app running.
- If the app is restarted, queued schedule entries persist. A job interrupted while already running may need to be re-queued manually.
- Processing multi-hour videos on CPU may take longer than the source duration. The five-clip count is a maximum; fewer valid highlights may be produced.
- Livestream mode waits for the stream to finish before transcription and clipping.
- The local development server has no user authentication. Bind to localhost; do not expose it directly to the public internet.

## Tests

    python -m pytest -q tests

## Open-source components

- Faster-Whisper: https://github.com/SYSTRAN/faster-whisper
- yt-dlp: https://github.com/yt-dlp/yt-dlp
- FFmpeg: https://ffmpeg.org/
- Ollama: https://github.com/ollama/ollama
- YouTube Data API: https://developers.google.com/youtube/data/guides/uploading_a_video

The app is an original integration of these tools; no third-party application source files are copied wholesale.
