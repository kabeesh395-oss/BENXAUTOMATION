# AutoClip AI — standalone local app

A separate, self-hosted application for turning long videos and stream recordings into short vertical clips. It does not import BENXAUTOMATION or use a paid inference API.

## MVP features
- Upload local MP4/MKV/MOV/WebM/AVI video.
- Submit a supported VOD URL through yt-dlp.
- Livestream URL capture from stream start; processing begins after the stream ends (not instant live clipping).
- Local timestamped transcription with Faster-Whisper.
- Local highlight selection with Ollama (default `qwen2.5:3b`).
- 9:16 H.264 clips with burned-in SRT subtitles.
- Mobile-friendly browser UI and job progress.

## Windows setup

```powershell
cd autoclip-app
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Install FFmpeg and add it to PATH. Install Ollama, then:

```powershell
ollama pull qwen2.5:3b
ollama serve
uvicorn autoclip_app.app:app --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765. To use the app from a phone on the same Wi-Fi, run Uvicorn with `--host 0.0.0.0` and open the computer's LAN IP on the phone. Do not expose this unauthenticated development server to the public internet.

## Runtime notes
- First Whisper/Ollama model use downloads model weights.
- CPU transcription of multi-hour video can take longer than the video itself; five hours is a development target, not a guaranteed processing SLA.
- Livestream mode records the source until it ends, then runs transcription/highlight/rendering. It does not create instant rolling live clips.
- Job state is in memory and resets when the app restarts.
- YouTube publishing is intentionally excluded from this standalone MVP; review exports and upload manually.
- Only process videos you own or have permission to repurpose.

## Open-source components
- Faster-Whisper (MIT): https://github.com/SYSTRAN/faster-whisper
- yt-dlp (Unlicense): https://github.com/yt-dlp/yt-dlp
- FFmpeg (LGPL/GPL depending on build): https://ffmpeg.org/
- Ollama runtime (MIT): https://github.com/ollama/ollama
- Qwen model weights have their own model license; check the selected model card before commercial use.

The app's pipeline is original integration code inspired by common local transcription → highlight selection → FFmpeg export workflows. No third-party application source files are copied wholesale.
