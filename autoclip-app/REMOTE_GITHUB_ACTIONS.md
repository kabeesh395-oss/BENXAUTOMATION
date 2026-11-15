# AutoClip remote publishing with GitHub Actions

This workflow runs AutoClip on a GitHub-hosted Ubuntu runner. Your Windows PC does not need to stay on while the workflow is running.

## Important limitations

- The workflow currently runs on-demand from **Actions → AutoClip Remote Publisher → Run workflow**.
- It also has a daily schedule at **18:00 India Standard Time**. GitHub only runs scheduled workflows from the repository's default branch. Merge this workflow into the default branch before expecting the daily schedule to run.
- For the daily schedule, set the repository variable `AUTOCLIP_DAILY_VIDEO_URL` to the one source URL you want processed that day. Update this variable each day; otherwise the same URL will be processed again.
- Scheduled GitHub Actions runs can be delayed or skipped during high load. This is not a guaranteed exact-time scheduler.
- GitHub-hosted runners have execution/time/resource limits. Long or high-resolution sources may fail or time out. The workflow uses CPU Whisper inference and downloads the Ollama model on each fresh runner.
- The workflow publishes generated Shorts as **PUBLIC** immediately. Only use videos you own or are licensed to repurpose. Review the source URL carefully before starting a run.

## One-time setup

### 1. Connect YouTube locally first

1. Enable YouTube Data API v3 in Google Cloud.
2. Create an OAuth Desktop app client and save its JSON as `autoclip-app/client_secrets.json`.
3. Start AutoClip on your Windows PC and connect your YouTube channel using the app's **Connect YouTube** button.
4. Confirm that `autoclip-app/data/youtube_token.json` exists locally.

Do not commit either file. They contain credentials.

### 2. Add GitHub Actions secrets

In the repository, open **Settings → Secrets and variables → Actions → New repository secret**.

Create these two secrets. Paste the complete JSON file contents as the secret values:

| Secret name | Value to copy from your PC |
|---|---|
| `AUTOCLIP_YOUTUBE_CLIENT_SECRETS_JSON` | `autoclip-app/client_secrets.json` |
| `AUTOCLIP_YOUTUBE_TOKEN_JSON` | `autoclip-app/data/youtube_token.json` |

Never paste either JSON value into chat, issues, pull requests, or source files. If you rotate/revoke the OAuth client or token, update the corresponding secret.

### 3. Configure the daily source URL (optional)

Open **Settings → Secrets and variables → Actions → Variables → New repository variable**.

- Name: `AUTOCLIP_DAILY_VIDEO_URL`
- Value: the public VOD URL you own or have permission to repurpose

Change the variable to the next day's source before the scheduled run. The schedule is 12:30 UTC (18:00 IST).

## Run immediately

After the workflow has been merged into a branch where Actions can run:

1. Open the repository's **Actions** tab.
2. Select **AutoClip Remote Publisher**.
3. Click **Run workflow**.
4. Enter a source URL you own or are licensed to repurpose.
5. Choose language, Whisper model and clip count (maximum five).
6. Start the run and inspect its logs and the `autoclip-run-...` artifact.

A successful workflow run means the generated clips were accepted by the YouTube API as public uploads. Check the artifact and YouTube channel after the run.

## Privacy and credential handling

The workflow reads OAuth JSON only from GitHub Actions secrets and writes temporary copies into ignored runtime paths. It does not print the secret values. Limit repository access to trusted collaborators because anyone who can change workflow code may be able to exfiltrate repository secrets.
