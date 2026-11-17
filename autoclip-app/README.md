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
- Live clipping for public Twitch and YouTube Live URLs: Streamlink captures the stream into short rolling segments; recent windows are transcribed with Faster-Whisper and ranked with local Ollama; FFmpeg renders clips while the stream is still running.
- Live dashboard controls to start/stop one active live session and poll for newly generated clips.
- Live moment ranking blends local transcript relevance with FFmpeg-measured audio loudness. Optional timestamped chat events can be supplied as JSONL at `autoclip-app/data/live/<session-id>/chat.jsonl` (one JSON object per line with a numeric `time` field in seconds from stream start). This is an import/sidecar hook, not an automatic Twitch chat or YouTube live-chat collector; chat scoring is omitted when no sidecar is present.
- The dashboard is responsive on mobile browsers, but capture, Whisper inference, Ollama and FFmpeg still run on the host computer. It is not a phone-only worker.
- Existing recorded-video/VOD processing remains available separately. The legacy URL mode `live` still records until stream end; use the dedicated Live clipping panel for in-progress clipping.

## Windows setup

Run from this folder:

    py -3.11 -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    pip install -r requirements-dev.txt

Install FFmpeg and add it to PATH. Streamlink is installed from requirements. Install Ollama and pull the local model:

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
- The dedicated Live clipping panel supports public Twitch and YouTube Live URLs only. It uses Streamlink + FFmpeg for rolling capture, then analyzes roughly 80-second rolling windows every 15 seconds. Clips include the captured pre-roll within the selected window and become available before the stream ends. Candidate scores now blend transcript relevance and measured audio loudness; optional imported chat activity can add another ranking signal.
- Live clipping is local and CPU-intensive. Keep the computer awake, the network connected, AutoClip, FFmpeg, Ollama and Streamlink running. The first clip appears only after enough stream segments have accumulated and local AI analysis/rendering finishes.
- Only one live clipping session can run at a time. Stop it from the dashboard. A stream ending unexpectedly or a platform changing its playback format can stop capture; verify the session status in the UI.
- Chat activity currently requires a timestamped JSONL sidecar supplied by the operator; automatic Twitch/YouTube chat ingestion and platform 'most replayed' data are not implemented. No automatic voice cloning or ElevenLabs integration is included; the original stream audio is preserved.
- This implementation does not bypass private streams, DRM, subscriptions or other access controls. Only clip streams you own or have permission to repurpose.
- The local development server has no user authentication. Bind to localhost; do not expose it directly to the public internet.

## Tests

    python -m pytest -q tests

## Open-source components

- Faster-Whisper: https://github.com/SYSTRAN/faster-whisper
- yt-dlp: https://github.com/yt-dlp/yt-dlp
- Streamlink: https://github.com/streamlink/streamlink
- FFmpeg: https://ffmpeg.org/
- Ollama: https://github.com/ollama/ollama
- YouTube Data API: https://developers.google.com/youtube/data/guides/uploading_a_video

The app is an original integration of these tools; no third-party application source files are copied wholesale.
