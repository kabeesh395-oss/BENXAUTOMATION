# Agensi listing draft — BENXAUTOMATION Video Production

Status: Draft only. Do not submit until the code licence and buyer prerequisites are resolved.

## Name
BENXAUTOMATION Video Production Assistant

## Summary
Guide an AI agent through local BENXAUTOMATION workflows for original Shorts and long-form videos, plus rights-confirmed long-video repurposing. Requires an existing BENXAUTOMATION installation, Python and FFmpeg.

## Description
Turn a user-provided script or rights-cleared long-form recording into a local video-production workflow with BENXAUTOMATION.

The skill helps an agent check the local environment, select the appropriate BENXAUTOMATION CLI workflow, prepare repurposing drafts for human review, render approved videos locally, and verify outputs with FFprobe. It supports vertical Shorts and horizontal long-form targets.

This is an agent workflow guide, not a hosted video editor or a standalone installer. Buyers must already have BENXAUTOMATION installed and configured, plus Python 3.11/3.12 and FFmpeg/FFprobe. Optional AI providers, transcription services and voice services may require separate setup or costs.

The skill does not upload or publish to YouTube. It does not grant rights to source footage. Repurposing requires the user to confirm ownership or a valid licence, and the user must approve the selected clips before rendering. API calls and paid services require separate user approval.

## See it in action — example request
"Create three vertical Shorts from this local recording. I own the recording. First show me the candidate clips and their timestamps. Do not render until I approve the clips."

Expected workflow:
1. The agent checks the BENXAUTOMATION installation, Python version, FFmpeg and FFprobe.
2. It asks for the source path and confirms that the user owns the footage or has permission to repurpose it.
3. It runs the draft-only repurposing workflow and reports the generated manifest path and candidate clips.
4. It presents candidate start/end times and asks the user to approve the exact clips.
5. After approval, it renders locally without uploading.
6. It verifies each output file with FFprobe and reports the actual dimensions, duration, subtitle files and any failed checks.

The skill must not invent a successful render, approve clips on the user's behalf, publish a video, or read credentials. If a required tool or dependency is missing, it stops and reports the blocker rather than silently installing software.

## Compatibility
Requires an existing BENXAUTOMATION checkout or installed package, Python 3.11 or 3.12, and FFmpeg/FFprobe on PATH. Desktop/local execution required. Not a mobile-only renderer.

## Suggested pricing
One-time: $5.99 (proposed, not submitted). At prices below $5, Agensi says buyers can only use their account balance; $5 or more supports card or balance purchases.

## Suggested categories
- Video & Media
- YouTube
- Automation

## Tags
video automation, youtube shorts, long form video, ffmpeg, subtitles, repurposing, local rendering

## FAQ

### Does this include the BENXAUTOMATION application?
No. It is an agent workflow guide. The buyer needs a separate, licensed BENXAUTOMATION installation.

### Does it publish videos to YouTube?
No. This listing is render-only and does not upload or schedule videos.

### Can I repurpose any public YouTube video?
No. The user must own the footage or have explicit permission or a valid licence. Public availability is not proof of reuse rights.

### Does it require paid AI APIs?
Not for a user-provided script and local render path. Optional AI or media providers may require separate configuration and costs; the agent must ask before paid use.

### Can I run it on a phone?
The current workflow requires a desktop/local environment with Python and FFmpeg. It is not advertised as mobile-only.

## Submission blockers
- The repository README and pyproject.toml declare MIT, but there is no root LICENSE file. Confirm ownership and add the intended licence before claiming buyers can install or use the repository.
- Confirm all third-party code, media assets and dependencies have appropriate redistribution/use rights.
- Test the skill in a real Agensi-connected agent and verify its requested tool permissions.
- Confirm Zoneless KYC, wallet/network fees and India tax treatment before enabling paid sales.
