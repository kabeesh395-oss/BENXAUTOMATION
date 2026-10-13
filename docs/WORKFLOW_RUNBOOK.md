# BENXAUTOMATION — Operational Workflow Runbook

**Date:** 2026-10-13  
**Audience:** Developers, DevOps Engineers, and Content Operations  
**Repository:** [kabeesh395-oss/BENXAUTOMATION](https://github.com/kabeesh395-oss/BENXAUTOMATION)

---

## 1. System Architecture & Workflows

BENXAUTOMATION provides four automated content production workflows:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        BENXAUTOMATION PLATFORM                         │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
      ┌────────────────────────────┼───────────────────────────┐
      ▼                            ▼                           ▼
1. 2D Mascot Story           2. Topic-to-Video           3. Podcast-to-Shorts
   (Character Animation)        (Narration & Media)         (Highlights & Reframing)
      │                            │                           │
      └────────────────────────────┼───────────────────────────┘
                                   │
                                   ▼
                      [MediaValidator Quality Gate]
                                   │
                                   ▼
                 [UploadLedger (SHA-256 Deduplication)]
                                   │
                                   ▼
                    [YouTube Publisher (Strict PRIVATE)]
```

---

## 2. Operating Modes & Safety Policies

Every workflow supports three standardized operational execution modes:

| Mode | Video Rendered? | Subtitles & Metadata? | YouTube Upload? | Purpose |
| :--- | :---: | :---: | :---: | :--- |
| **`dry_run`** | No | Yes (Mock/Plan) | **No** | Fast validation of scripts, parameters, and credentials in CI. |
| **`render_only`** | **Yes** | **Yes** | **No** | Generates full local video artifacts for human preview and QA. |
| **`upload_private`** | **Yes** | **Yes** | **Yes (PRIVATE)** | Production automated run. Uploads strictly with `PRIVATE` visibility. |

> [!IMPORTANT]
> **Strict Private-Only Safety Policy:** Automated cloud workflows NEVER publish videos publicly. All uploads are stored in `PRIVATE` state so that a human creator can review audio, video, title, and tags in YouTube Studio before manually making the video public.

---

## 3. How to Run Locally (Windows)

### Prerequisites
- Python 3.11 (`C:\Users\Admin\python311\tools\python.exe` or system Python 3.11+).
- FFmpeg 6.0+ added to PATH.

### 3.1 Local Runner PowerShell Script
Use the unified local runner [run_automation.ps1](file:///e:/New%20folder/BENXAUTOMATION/run_automation.ps1):

```powershell
# 1. Generate both 9:16 Shorts and 16:9 Long-form video from a topic
.\run_automation.ps1 -Topic "5 Surprising Breakthroughs in Quantum Computing" -Format both

# 2. Render only 9:16 vertical Short with custom duration
.\run_automation.ps1 -Topic "Mariana Trench Mysteries" -Format shorts -Duration 30

# 3. Dry-run mode for parameter validation
.\run_automation.ps1 -Topic "Space Exploration 2026" -DryRun
```

### 3.2 Python CLI Direct Execution
You can also invoke `benxautomation.main` directly:

```powershell
# Run 2D Mascot Animated Story (Shorts format)
python -m benxautomation.main --workflow animated --sample-only

# Run Topic-to-Video Pipeline (Offline deterministic fallback provider)
python -m benxautomation.main --topic "Mysteries of the Deep Sea" --format both --provider fallback --mode render_only

# Run Podcast Repurposing (Extract 1 clip from local video)
python -m benxautomation.main --workflow repurpose --source "path/to/podcast.mp4" --clips 1 --mode render_only
```

---

## 4. How to Operate Cloud GitHub Actions Workflows

### 4.1 Scheduled Workflows (UTC vs IST)

| Workflow | Target IST | GitHub Cron (UTC) | File |
| :--- | :--- | :--- | :--- |
| **Daily Shorts** | 09:30 AM, 02:30 PM, 07:30 PM | `'0 4,9,14 * * *'` | `.github/workflows/podcast_shorts_automation.yml` |
| **Weekly Long-Form** | Sun & Wed 06:30 PM | `'0 13 * * 0,3'` | `.github/workflows/longform_automation.yml` |

### 4.2 Manual Trigger via GitHub Actions UI (workflow_dispatch)
1. Go to repository **Actions** tab on GitHub.
2. Select **"Long-Form Landscape Weekly Automation"** or **"Podcast & Shorts Daily Automation"**.
3. Click **"Run workflow"** button on the right.
4. Select inputs:
   - `Topic`: Desired video subject.
   - `Format`: `both`, `shorts`, or `longform`.
   - `Mode`: Select `dry_run` for testing or `upload_private` for real channel testing.

### 4.3 Scheduled Run Fallback Behavior
- If `secrets.PODCAST_SCHEDULED_SOURCE_URL` is configured, the scheduled podcast workflow processes highlights from that video.
- If no secret is configured, the workflow does **NOT** silently skip; it executes `--fallback-to-topic --mode upload_private`, generating an authorized, educational original Short and saving verified artifacts.

---

## 5. Persistent State & Deduplication Runbook

### 5.1 Upload Ledger (`output/upload_ledger.sqlite`)
- Every upload attempt computes the **SHA-256** checksum of the video file before contacting YouTube.
- If the hash already exists in `upload_ledger` with status `COMPLETED`:
  - The upload call is skipped.
  - The existing video ID is returned.
  - Zero YouTube API quota units are consumed.

### 5.2 Resuming Interrupted Uploads
- Resumable upload session URIs are cached in the ledger.
- If a network error occurs mid-transfer:
  - On the next run, the publisher sends a `308 Resume Incomplete` probe to YouTube.
  - Transfer resumes from the exact byte offset where it disconnected.

---

## 6. Diagnostic & Troubleshooting Checklist

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **FFmpeg not found** | FFmpeg binaries missing from system PATH | Install FFmpeg via `winget install Gyan.FFmpeg` on Windows or `sudo apt-get install ffmpeg` on Ubuntu. |
| **YouTube 403 Insufficient Scope** | Stored OAuth token lacks `youtube.upload` scope | Delete expired `~/.benxautomation/youtube_tokens.json` and re-authenticate via `python -m benxautomation.publisher.youtube --authorize`. |
| **Font rendering glitch** | Required TrueType fonts missing in Linux runner | Ensure CI installs `fonts-dejavu-core fonts-freefont-ttf` before rendering. |
| **Quota Exceeded (403 quotaExceeded)** | Daily 10,000 unit budget exhausted | Budget allows 6,400 units/day max. Wait for daily reset at 12:30 PM IST (midnight PT). |
