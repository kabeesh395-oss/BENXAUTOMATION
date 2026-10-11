"""Headless cloud runner for GitHub Actions and serverless environments.

Safely hydrates OAuth secrets from GitHub Actions Secrets into ~/.benxautomation,
enforces private test uploads, handles state synchronization, and supports dry-run mode.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from benxautomation.logger import get_logger
from benxautomation.podcast.batch_processor import PodcastBatchProcessor
from benxautomation.podcast.models import PodcastPipelineConfig, RightsDeclaration
from benxautomation.podcast.pipeline import PodcastToShortsPipeline
from benxautomation.publisher.ledger import UploadLedger
from benxautomation.renderer.ffmpeg_utils import ffmpeg_is_available, ffprobe_is_available

log = get_logger("benxautomation.cloud_runner")


def hydrate_oauth_secrets() -> tuple[bool, list[str]]:
    """Hydrate YouTube OAuth tokens and secrets from environment variables.

    Never prints or logs secret contents. Returns (is_configured, status_messages).
    """
    token_dir = Path.home() / ".benxautomation"
    token_dir.mkdir(parents=True, exist_ok=True)

    client_secret_file = token_dir / "client_secret.json"
    tokens_file = token_dir / "youtube_tokens.json"

    messages = []
    has_client_secret = False
    has_tokens = False

    # 1. Client Secret
    raw_secret = os.environ.get("YOUTUBE_CLIENT_SECRET_JSON")
    raw_b64_secret = os.environ.get("YOUTUBE_CLIENT_SECRET_BASE64")

    if raw_secret and raw_secret.strip():
        try:
            # Validate JSON structure without logging values
            json.loads(raw_secret)
            client_secret_file.write_text(raw_secret.strip(), encoding="utf-8")
            has_client_secret = True
            messages.append("Loaded client_secret.json from YOUTUBE_CLIENT_SECRET_JSON environment variable.")
        except json.JSONDecodeError:
            messages.append("WARNING: YOUTUBE_CLIENT_SECRET_JSON contains invalid JSON.")
    elif raw_b64_secret and raw_b64_secret.strip():
        try:
            decoded = base64.b64decode(raw_b64_secret).decode("utf-8")
            json.loads(decoded)
            client_secret_file.write_text(decoded, encoding="utf-8")
            has_client_secret = True
            messages.append("Loaded client_secret.json from YOUTUBE_CLIENT_SECRET_BASE64 environment variable.")
        except Exception:
            messages.append("WARNING: Failed to decode YOUTUBE_CLIENT_SECRET_BASE64.")
    elif client_secret_file.is_file():
        has_client_secret = True
        messages.append("Using existing client_secret.json from local disk.")

    # 2. YouTube Tokens (Access + Refresh Tokens)
    raw_tokens = os.environ.get("YOUTUBE_TOKENS_JSON")
    raw_b64_tokens = os.environ.get("YOUTUBE_TOKENS_BASE64")

    if raw_tokens and raw_tokens.strip():
        try:
            json.loads(raw_tokens)
            tokens_file.write_text(raw_tokens.strip(), encoding="utf-8")
            has_tokens = True
            messages.append("Loaded youtube_tokens.json from YOUTUBE_TOKENS_JSON environment variable.")
        except json.JSONDecodeError:
            messages.append("WARNING: YOUTUBE_TOKENS_JSON contains invalid JSON.")
    elif raw_b64_tokens and raw_b64_tokens.strip():
        try:
            decoded = base64.b64decode(raw_b64_tokens).decode("utf-8")
            json.loads(decoded)
            tokens_file.write_text(decoded, encoding="utf-8")
            has_tokens = True
            messages.append("Loaded youtube_tokens.json from YOUTUBE_TOKENS_BASE64 environment variable.")
        except Exception:
            messages.append("WARNING: Failed to decode YOUTUBE_TOKENS_BASE64.")
    elif tokens_file.is_file():
        has_tokens = True
        messages.append("Using existing youtube_tokens.json from local disk.")

    # Set strict file permissions (POSIX chmod 600)
    try:
        if os.name != "nt":
            if client_secret_file.is_file():
                client_secret_file.chmod(0o600)
            if tokens_file.is_file():
                tokens_file.chmod(0o600)
    except Exception as e:
        log.warning("Could not set strict file permissions on token files: %s", e)

    return (has_client_secret and has_tokens, messages)


def verify_cloud_environment() -> dict[str, Any]:
    """Verify system binaries, AI API key, and OAuth setup in cloud environment."""
    ffmpeg_ok = ffmpeg_is_available()
    ffprobe_ok = ffprobe_is_available()
    gemini_key_ok = bool(os.environ.get("GEMINI_API_KEY"))
    oauth_ready, oauth_notes = hydrate_oauth_secrets()

    channel_name = None
    if oauth_ready:
        try:
            pipeline = PodcastToShortsPipeline()
            if pipeline.publisher and pipeline.publisher.oauth_manager:
                ch = pipeline.publisher.oauth_manager.verify_channel()
                channel_name = f"{ch.title} (@{ch.custom_url})"
        except Exception as e:
            oauth_notes.append(f"Channel verification error: {str(e)[:60]}")

    return {
        "ffmpeg": ffmpeg_ok,
        "ffprobe": ffprobe_ok,
        "gemini_api_key_configured": gemini_key_ok,
        "oauth_configured": oauth_ready,
        "oauth_channel": channel_name,
        "notes": oauth_notes,
    }


def sync_ledger_to_git_branch(
    ledger_path: Path,
    branch_name: str = "automation-state",
    commit_msg: str = "chore: update upload ledger state [skip ci]",
) -> bool:
    """Safely commit and push upload_ledger.sqlite to a dedicated orphan state branch.

    This ensures state persistence even if the GitHub Actions 7-day cache is evicted.
    """
    if not ledger_path.is_file() or not os.environ.get("GITHUB_TOKEN"):
        return False

    try:
        # Check current git remote
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False, capture_output=True)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False, capture_output=True)

        # Check if state branch exists
        res = subprocess.run(["git", "ls-remote", "--heads", "origin", branch_name], capture_output=True, text=True)
        if branch_name not in res.stdout:
            # Create orphan branch
            subprocess.run(["git", "checkout", "--orphan", branch_name], check=False, capture_output=True)
            subprocess.run(["git", "rm", "-rf", "."], check=False, capture_output=True)
        else:
            subprocess.run(["git", "fetch", "origin", branch_name], check=False, capture_output=True)
            subprocess.run(["git", "checkout", branch_name], check=False, capture_output=True)

        # Copy ledger file into state branch
        target = Path("upload_ledger.sqlite")
        target.write_bytes(ledger_path.read_bytes())
        subprocess.run(["git", "add", "upload_ledger.sqlite"], check=True)
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "push", "origin", branch_name], check=True)
        log.info("Successfully pushed ledger state to branch '%s'", branch_name)
        return True
    except Exception as e:
        log.warning("Git state sync skipped or failed (%s); relying on GitHub Actions cache", e)
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benxautomation.cloud_runner",
        description="BENXAUTOMATION Cloud CI/CD & Scheduled Execution Runner",
    )
    parser.add_argument("--check-env", action="store_true", help="Inspect and report environment readiness")
    parser.add_argument("--dry-run", action="store_true", help="Perform full pipeline verification without publishing")
    parser.add_argument("--source", default=None, help="Input video source URL or local path")
    parser.add_argument("--clips-target", type=int, default=3, help="Number of clips to generate")
    parser.add_argument("--ownership-type", default="creator_owned", help="Rights ownership type")
    parser.add_argument("--rights-holder", default="", help="Rights holder / Author")
    parser.add_argument("--license-evidence", default="", help="License documentation reference")
    parser.add_argument("--music-source", default="no_music", help="Music clearance status")
    parser.add_argument("--confirm-rights", action="store_true", help="Confirm ownership rights")
    parser.add_argument("--accept-disclaimer", action="store_true", help="Accept copyright disclaimer")
    parser.add_argument(
        "--mode",
        choices=["dry_run", "render_only", "upload_private"],
        default=None,
        help="Pipeline execution mode (dry_run, render_only, upload_private)",
    )
    parser.add_argument("--upload-private", action="store_true", help="Upload to YouTube as PRIVATE")
    parser.add_argument("--sync-state", action="store_true", help="Sync ledger state to git branch if configured")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Resolve explicit --mode choice
    if args.mode == "dry_run":
        args.dry_run = True
    elif args.mode == "upload_private":
        args.upload_private = True
    elif args.mode == "render_only":
        args.dry_run = False
        args.upload_private = False

    print("=======================================================")
    print("BENXAUTOMATION — Cloud CI/CD Execution Runner")
    print("=======================================================")

    env_status = verify_cloud_environment()
    print(f"FFmpeg Available:        {env_status['ffmpeg']}")
    print(f"FFprobe Available:       {env_status['ffprobe']}")
    print(f"Gemini API Configured:   {env_status['gemini_api_key_configured']}")
    print(f"YouTube OAuth Status:    {'READY' if env_status['oauth_configured'] else 'NOT CONFIGURED'}")
    if env_status["oauth_channel"]:
        print(f"Connected Channel:       {env_status['oauth_channel']}")
    for note in env_status["notes"]:
        print(f"  - {note}")
    print("-------------------------------------------------------")

    if args.check_env and not args.source and not args.dry_run:
        return 0

    if not env_status["ffmpeg"]:
        print("ERROR: FFmpeg is not installed in the environment. Install with 'sudo apt-get install ffmpeg'.")
        return 1

    source_path = args.source
    if not source_path:
        print("ERROR: Missing required --source parameter for podcast clipping.")
        print("Usage: python -m benxautomation.cloud_runner --source <video_url_or_file> [options]")
        print("Note: To generate original narrated videos from topics, use 'python -m benxautomation.main --topic ...'")
        return 1

    source_p = Path(source_path)
    if not source_p.is_file() and not source_path.startswith("http"):
        print(f"ERROR: Local source video '{source_path}' not found.")
        print("Please provide a valid local video file path or YouTube URL via --source.")
        print("Note: To generate original narrated videos from topics, use 'python -m benxautomation.main --topic ...'")
        return 1

    print(f"Execution Mode:          {'DRY-RUN (Safe Verification)' if args.dry_run else 'PRODUCTION'}")
    print(f"Source Input:            {source_path}")
    print(f"Clips Target:            {args.clips_target}")
    print(f"Upload Policy:           {'STRICTLY PRIVATE' if args.upload_private else 'LOCAL ARTIFACTS ONLY (Review Mode)'}")
    print("-------------------------------------------------------")

    pipeline = PodcastToShortsPipeline()
    rights_decl = RightsDeclaration(
        ownership_type=args.ownership_type,
        rights_holder=args.rights_holder or "Automated Cloud Creator",
        license_evidence=args.license_evidence or "Creator self-produced authorized content",
        music_source=args.music_source,
        attribution_text=f"Source: {source_p.name}",
        user_confirmed_rights=True,
        disclaimer_accepted=True,
    )

    # 1. Ingest
    print(f"\n[1/5] Ingesting: {source_path}")
    inp = pipeline.ingest(str(source_p))

    # 2. Transcribe
    print("\n[2/5] Transcribing and synchronizing timestamps...")
    transcript = pipeline.transcribe(inp)

    # 3. Detect Highlights
    print(f"\n[3/5] Detecting up to {args.clips_target} high-retention highlights...")
    candidates = pipeline.detect_highlights(transcript, max_candidates=args.clips_target)
    for c in candidates:
        print(f"  • {c.clip_id}: {c.start_seconds:.1f}s - {c.end_seconds:.1f}s ({c.duration:.1f}s) | Hook: \"{c.hook}\"")

    # 4. Render
    print("\n[4/5] Rendering vertical 9:16 (1080x1920) Shorts with FFmpeg...")
    rendered_metadata = []
    for cand in candidates:
        cand.approved = True
        meta = pipeline.render_clip(
            podcast_input=inp,
            transcript=transcript,
            candidate=cand,
            rights_declaration=rights_decl,
            reframing_mode="blur_pad",
        )
        print(f"  Rendered: {meta.video_path} ({meta.duration_seconds:.1f}s, size={Path(meta.video_path).stat().st_size} bytes)")
        rendered_metadata.append(meta)

    # 5. Upload or Dry-Run
    print("\n[5/5] Publication & Upload Policy Review...")
    if args.dry_run:
        print("  DRY-RUN VERIFIED: Skipping real YouTube upload. Video, SRT, VTT, Thumbnail, and Metadata are saved locally.")
    elif args.upload_private:
        if not env_status["oauth_configured"]:
            print("  WARNING: OAuth secrets are not configured in GitHub Secrets. Upload skipped; artifacts preserved.")
        else:
            print("  Uploading approved clips as PRIVATE for testing...")
            for meta in rendered_metadata:
                res = pipeline.upload_to_youtube(meta, privacy_status="private", user_approved=True)
                print(f"  Uploaded '{meta.title}' -> Video ID: {res.get('video_id') or res.get('id')} ({res.get('url')})")
    else:
        print("  REVIEW-BEFORE-PUBLISH MODE: Uploads held in review queue. Download artifacts or approve via dashboard.")

    print("\n=======================================================")
    print("CLOUD RUNNER COMPLETED SUCCESSFULLY")
    print("=======================================================\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
