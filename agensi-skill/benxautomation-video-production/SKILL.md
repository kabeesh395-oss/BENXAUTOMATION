---
name: benxautomation-video-production
description: Use when a user wants to create original YouTube Shorts or long-form videos, or repurpose footage they own or are licensed to use, with an existing BENXAUTOMATION installation. Requires Python 3.11 or 3.12 and FFmpeg/FFprobe. This skill renders locally and does not publish videos.
summary: Safely guide an agent through BENXAUTOMATION's local video creation and rights-gated repurposing workflows.
version: 0.1.0
tags:
  - video
  - youtube
  - shorts
  - automation
  - ffmpeg
keywords:
  - video production
  - long-form to shorts
  - subtitles
  - local rendering
use_cases:
  - Create original short-form videos from a user-provided script
  - Repurpose user-owned or licensed long-form footage into reviewable Shorts
  - Check a BENXAUTOMATION installation before running a render
docs_url: https://github.com/kabeesh395-oss/BENXAUTOMATION
---

# BENXAUTOMATION Video Production

Use the user's existing BENXAUTOMATION checkout to create local video outputs. This skill is an agent workflow guide; it does not contain or install the BENXAUTOMATION engine.

## Hard safety rules

- Never claim a render succeeded until the output file exists and FFprobe can inspect it.
- Never publish, upload, schedule, or share a video. This skill is render-only.
- Never use `--upload-public` or `--upload-private`.
- For repurposing, proceed only when the user explicitly confirms they own the source or have permission/licensing to use it. Do not infer rights from a public URL.
- Do not download or process third-party footage without explicit rights confirmation.
- Do not read, print, copy, transmit, or ask the user to paste API keys, OAuth credentials, tokens, or contents of `.env`, `client_secret.json`, or token files.
- Do not install packages, upgrade dependencies, or download binaries without the user's approval.
- Do not make paid API calls unless the user has explicitly approved the provider and expected cost. Prefer a user-provided script and local rendering.
- Keep source media and rendered outputs on the user's machine. Do not upload them to external services.

## 1. Check the environment

1. Ask for the path to the existing BENXAUTOMATION project if it is not already open.
2. Run the supporting `scripts/preflight.py` from that project directory, or perform the same checks:
   - Python 3.11 or 3.12
   - `ffmpeg` and `ffprobe` available on PATH
   - The project root contains `pyproject.toml` and `benxautomation/main.py`, or the `benxautomation` package is installed.
3. If a requirement is missing, report the exact missing item. Ask before installing anything.
4. Run `python -m benxautomation.main --help` to confirm the CLI is callable.

## 2. Create an original video from a user-provided script

Ask for the narration script, target format (Shorts or long-form), language, and output folder. Do not invent factual claims or source material.

Use an argument-array process invocation rather than building a shell command from untrusted text. Example:

```text
python -m benxautomation.main --script "<USER_SCRIPT>" --format shorts --mode render_only --output-dir "<OUTPUT_DIR>"
```

Use `--format longform` for 16:9 output. Use `--format both` only when the user requests both formats.

Do not use `--topic` if it would trigger a paid or external AI provider unless the user has approved that provider and its cost. A manual `--script` is the default low-cost path.

## 3. Repurpose long-form footage into Shorts

Before processing, ask the user to confirm:
- They own the footage or have explicit permission/a valid licence to repurpose it.
- The rights holder's name and the licence/evidence reference, if applicable.
- The requested number of candidate clips and target language.

Use a local file path by default. Do not fetch a YouTube URL unless the user explicitly confirms the rights and asks to use that URL.

First create a review draft; do not render or upload yet:

```text
python -m benxautomation.main --workflow repurpose --source "<SOURCE_PATH>" --draft --clips 3 --mode dry_run --output-dir "<OUTPUT_DIR>"
```

If the CLI's dry-run mode prevents candidate analysis for the installed version, explain that and ask before rerunning without `--mode dry_run`. Do not silently change execution mode.

Inspect the generated manifest and candidate hooks. Show the user the candidate start/end times and ask which clips to approve. Never approve clips on the user's behalf.

After the user approves specific clips, use the generated manifest with render-only mode. Include the truthful rights details the user supplied and the CLI's required rights confirmations:

```text
python -m benxautomation.main --workflow repurpose --source "<SOURCE_PATH>" --apply-manifest "<MANIFEST_PATH>" --mode render_only --ownership-type "<creator_owned|licensed|permitted|public_domain>" --rights-holder "<RIGHTS_HOLDER>" --license-evidence "<EVIDENCE_REFERENCE>" --confirm-rights --accept-disclaimer --output-dir "<OUTPUT_DIR>"
```

Do not invent a rights holder or evidence reference. If the user cannot provide truthful rights details, stop.

## 4. Verify and report outputs

For each expected video:
1. Confirm the file exists and is non-empty.
2. Run `ffprobe -v error -show_format -show_streams "<VIDEO_PATH>"`.
3. Confirm a video stream exists and dimensions match the requested format (Shorts: 1080x1920; long-form: 1920x1080, where the renderer reports those dimensions).
4. Report the exact output path, duration, dimensions, subtitle file (if produced), and any failed checks.
5. If validation fails, report failure and do not describe the video as ready.

## Scope and limitations

- Requires the separate BENXAUTOMATION project to be installed or checked out by the user. This skill does not bundle the Python application, media assets, FFmpeg, or dependencies.
- Requires a desktop environment with Python and FFmpeg; it is not a mobile-only renderer.
- AI script generation, transcription, and optional voice services may require separate providers or local components. Their availability and costs must be checked before use.
- This skill does not upload to YouTube, manage a channel, guarantee copyright clearance, or guarantee monetisation.
