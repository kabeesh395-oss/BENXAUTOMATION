# BENXAUTOMATION — 100% Free Cloud Automation Setup Guide

This guide details how to run **BENXAUTOMATION** completely in the cloud using **GitHub Actions** with **zero paid services** and **zero credit cards required**. It runs automatically even when your Windows PC is powered off.

---

## 1. Architecture & Limits Verification

### A. Hosting & Compute (GitHub Actions Free Tier)
- **Repo Type:** GitHub Actions provides free runners (`ubuntu-latest` with 4 vCPUs, 16 GB RAM, and pre-installed FFmpeg).
  - **Public repository:** 100% free with unlimited workflow minutes.
  - **Private repository:** 2,000 free minutes/month included.
- **Estimated Monthly Usage:**
  - **3 Shorts Daily:** ~2 minutes per run = 6 min/day × 30 days = **180 minutes/month**.
  - **2 Long-form Weekly:** ~15 minutes per run = 30 min/week × 4 weeks = **120 minutes/month**.
  - **Total:** ~300 minutes/month (<15% of the 2,000 free monthly quota if private; 0% quota impact if public).
- **Timeouts:** Workflows are protected with strict job timeouts (`timeout-minutes: 45` for Shorts, `60` for Long-form).

### B. YouTube Data API Quota
- **Daily Quota:** 10,000 units/day (free, resets at 12:30 PM IST / midnight PT).
- **Cost Breakdown:**
  - Upload 1 video (any duration): `1,600 units`
  - Upload thumbnail: `50 units`
  - Channel / Status check: `1 unit`
- **Daily Budget:**
  - 3 Shorts × 1,600 = `4,800 units`
  - 1 Long-form (on upload days) = `1,600 units`
  - **Peak Daily Usage:** `6,400 units` (leaving a safe buffer of **3,600 units**).

### C. State Persistence, Concurrency & Duplicate Protection
- **No Reliance on GitHub Cache as Database:**
  - Level 1: `actions/cache@v4` persists `output/upload_ledger.sqlite` across runs.
  - Level 2: `benxautomation.publisher.youtube.YouTubePublisher` idempotently verifies existing channel video titles and SHA-256 media hashes to prevent duplicate uploads if cache resets.
  - Level 3: All generated media (MP4, SRT, VTT, Thumbnails, Metadata JSON) are exported as downloadable GitHub Actions Artifacts retained for 14 days.
- **Concurrency Locks:**
  - `concurrency: group: podcast-shorts-pipeline, cancel-in-progress: false` ensures multiple runs never overlap or race against each other.

---

## 2. Configurable Scheduling (Asia/Kolkata vs UTC)

GitHub Actions cron operates in **UTC**. The workflows are pre-configured to match peak viewing times in India Standard Time (**IST = UTC+05:30**):

| Content | Target Time (IST) | GitHub Cron Expression (UTC) | Workflow File |
| :--- | :--- | :--- | :--- |
| **Shorts #1 (Morning)** | 09:30 AM IST | `0 4 * * *` (04:00 UTC) | `.github/workflows/podcast_shorts_automation.yml` |
| **Shorts #2 (Afternoon)** | 02:30 PM IST | `0 9 * * *` (09:00 UTC) | `.github/workflows/podcast_shorts_automation.yml` |
| **Shorts #3 (Evening)** | 07:30 PM IST | `0 14 * * *` (14:00 UTC) | `.github/workflows/podcast_shorts_automation.yml` |
| **Combined Shorts Cron** | **09:30 AM, 02:30 PM, 07:30 PM IST** | `'0 4,9,14 * * *'` | `.github/workflows/podcast_shorts_automation.yml` |
| **Long-Form #1 (Sunday)** | Sunday 06:30 PM IST | `0 13 * * 0` (13:00 UTC Sunday) | `.github/workflows/longform_automation.yml` |
| **Long-Form #2 (Wednesday)** | Wednesday 06:30 PM IST | `0 13 * * 3` (13:00 UTC Wednesday) | `.github/workflows/longform_automation.yml` |
| **Combined Long-Form Cron**| **Sun & Wed 06:30 PM IST** | `'0 13 * * 0,3'` | `.github/workflows/longform_automation.yml` |

---

## 3. Required GitHub Secrets Setup

Navigate to your GitHub repository:
**Settings** -> **Secrets and variables** -> **Actions** -> Click **New repository secret**.

Add the following 3 secrets:

### Secret 1: `GEMINI_API_KEY`
- **Description:** Google Gemini API Key used for topic script generation and highlight selection.
- **Value:** Your existing Gemini API key.

### Secret 2: `YOUTUBE_CLIENT_SECRET_JSON`
- **Description:** Google OAuth 2.0 Desktop Client credentials JSON file.
- **How to retrieve from your local PC:**
  Open PowerShell and copy the text:
  ```powershell
  Get-Content "C:\Users\Admin\.benxautomation\client_secret.json" | Set-Clipboard
  ```
  Paste the clipboard content directly as the secret value.

### Secret 3: `YOUTUBE_TOKENS_JSON`
- **Description:** Authorized OAuth access and refresh token for your YouTube Channel (`BENX_07`).
- **How to retrieve from your local PC:**
  Open PowerShell and copy the text:
  ```powershell
  Get-Content "C:\Users\Admin\.benxautomation\youtube_tokens.json" | Set-Clipboard
  ```
  Paste the clipboard content directly as the secret value.

> [!SECURITY NOTE]
> These secrets are encrypted by GitHub using libsodium before being stored. The workflows never echo or write secrets to console output. The `cloud_runner.py` writes them exclusively to the runner's ephemeral `~/.benxautomation/` directory with strict file permissions (`0o600`), and all logs mask credentials.

---

## 4. Initial Deployment & Manual Dry Run Verification

Before enabling real private uploads:

1. **Push the workflows and runner to GitHub:**
   ```bash
   git add .github/ benxautomation/ tests/ CLOUD_DEPLOYMENT.md
   git commit -m "feat: add 100% free cloud automation workflows and cloud runner"
   git push origin main
   ```

2. **Trigger the Dry Run on GitHub:**
   - In GitHub, click on the **Actions** tab.
   - In the left sidebar, click **"Podcast & Shorts Daily Automation"**.
   - Click the **"Run workflow"** dropdown button on the right.
   - Choose:
     - **Execution mode:** `dry_run` (default)
     - **Clips to render:** `1`
   - Click **Run workflow**.

3. **Verify Execution Evidence:**
   - The workflow will run, install FFmpeg, run automated health checks, render a 9:16 vertical Short, extract thumbnails, and verify rights.
   - Under the job summary, download the generated artifact zip (`podcast-shorts-dry_run-1`).
   - Check that `clip_1.mp4`, `clip_1.srt`, `clip_1.vtt`, `clip_1_thumbnail.jpg`, and `clip_1_metadata.json` are present.

---

## 5. Review-Before-Publish Policy

To ensure complete safety:
- All cloud uploads are strictly set to **`PRIVATE`** status.
- Videos are never published publicly automatically.
- After a scheduled run finishes, inspect the uploaded video in YouTube Studio ([studio.youtube.com](https://studio.youtube.com/channel/UCe1iIEm9P3qZAReiLhNanQA/videos)).
- You retain 100% control to review title, tags, description, captions, and playback before switching the video to **Unlisted** or **Public**.
