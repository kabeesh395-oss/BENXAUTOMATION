# AutoClip AI — self-hosted worker

This adds an optional local long-video → Shorts worker to BENXAUTOMATION. It reuses the
repository's existing YouTube OAuth publisher and SQLite duplicate-upload ledger.

## Free local stack

- Faster-Whisper (MIT) for timestamped transcription; models are downloaded once and run locally.
- Ollama local REST API for transcript-based highlight selection. Default model: `qwen2.5:3b`.
- FFmpeg for H.264 vertical 9:16 rendering and permanently burned SRT subtitles.
- Existing BENXAUTOMATION YouTube publisher for resumable uploads, OAuth and duplicate protection.

No Gemini, OpenAI, paid inference endpoint, paid rendering API, or paid hosting is required.
The first model download requires internet. Processing then runs on the worker computer.

## Install (Windows PowerShell)

```powershell
Set-Location "E:\New folder\BENXAUTOMATION"
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[autoclip]"
```

Install FFmpeg and make `ffmpeg` available on PATH. Install Ollama from its official
installer, then download a local model:

```powershell
ollama pull qwen2.5:3b
ollama serve
```

The Ollama app may already run the local server; if so, do not start a second server.
For Faster-Whisper, the default is CPU + int8 to reduce memory use. Set
`WHISPER_DEVICE=cuda` and a compatible `WHISPER_COMPUTE_TYPE` only when the machine
has a supported NVIDIA/CUDA setup. Model choice affects speed and accuracy.

## Run without uploading (recommended first)

```powershell
python -m benxautomation.autoclip_worker "E:\Videos\long-video.mp4" --language en
```

For Tamil speech, use `--language ta`; omit the flag to let Whisper detect the language.
Outputs are written under `output/autoclip/`: timestamped transcript JSON, per-clip MP4,
per-clip SRT, and `autoclip_manifest.json`.

## Enable YouTube upload

Configure the existing BENXAUTOMATION Desktop OAuth client secret and token using the
repository's publisher setup. The YouTube Data API must be enabled in a Google Cloud
project. Then run:

```powershell
python -m benxautomation.autoclip_worker "E:\Videos\long-video.mp4" --language en --upload --rights-confirmed
```

Uploads are **PRIVATE only**. The `--rights-confirmed` flag is an explicit declaration
that you own the source or have permission to repurpose it. Do not use it for third-party
content without permission. Public publishing remains a separate manual action.

## Important limits / truthful status

- Highlight timestamps and scores are model-generated suggestions, not guaranteed viral
  performance. Review every clip before publishing.
- This worker only reports Faster-Whisper transcription and Ollama analysis when those
  components actually ran. It never substitutes synthetic transcript text.
- Local inference is not costless: it uses your CPU/GPU, RAM, disk, electricity and internet
  for initial downloads. Large models may be too slow or memory-heavy on low-end machines.
- YouTube upload is free to call within the applicable API quota, but requires OAuth
  consent and is subject to Google/YouTube policy, quota and account restrictions.
- The source must be locally available. This command processes long-form files; it does not
  continuously ingest a live stream yet.
- Hugging Face model repositories can have different licenses. Check the exact model card
  and terms before commercial use; the Ollama runtime license does not grant rights to
  every model it can run.

## References

- Faster-Whisper: https://github.com/SYSTRAN/faster-whisper (MIT)
- Ollama: https://github.com/ollama/ollama
- Qwen2.5 model family: https://huggingface.co/Qwen/Qwen2.5-3B-Instruct
- FFmpeg: https://ffmpeg.org/
- YouTube upload API: https://developers.google.com/youtube/v3/guides/uploading_a_video
