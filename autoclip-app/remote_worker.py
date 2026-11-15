from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yt_dlp

from autoclip_app.pipeline import process
from autoclip_app.youtube import upload_public_video, youtube_status

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUTPUTS = DATA / "remote_outputs"


def _write_secret(name: str, destination: Path) -> None:
    value = os.environ.get(name, "")
    if not value.strip():
        raise RuntimeError(f"Missing GitHub Actions secret: {name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(value, encoding="utf-8")


def download_source(url: str, destination: Path) -> Path:
    if not url.startswith(("https://", "http://")):
        raise ValueError("Source URL must start with http:// or https://")
    destination.mkdir(parents=True, exist_ok=True)
    options = {
        "outtmpl": str(destination / "%(title).80s-%(id)s.%(ext)s"),
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)
        filename = Path(downloader.prepare_filename(info))
    if not filename.exists():
        merged = filename.with_suffix(".mp4")
        if merged.exists():
            filename = merged
    if not filename.exists():
        matches = [p for p in destination.iterdir()
                   if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
        if not matches:
            raise RuntimeError("Source download completed but no video file was found.")
        filename = matches[0]
    return filename


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AutoClip on a GitHub-hosted runner.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--language", default="")
    parser.add_argument("--model", default="small")
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args()

    count = max(1, min(args.count, 5))
    _write_secret("YOUTUBE_CLIENT_SECRETS_JSON", ROOT / "client_secrets.json")
    _write_secret("YOUTUBE_TOKEN_JSON", DATA / "youtube_token.json")

    status = youtube_status()
    if not status.get("connected"):
        raise RuntimeError(f"YouTube OAuth is not usable on the runner: {status.get('message')}")

    job_dir = OUTPUTS / os.getenv("GITHUB_RUN_ID", "manual")
    source = download_source(args.url, DATA / "remote_source")
    clips = process(source, job_dir, args.language or None, args.model, count)
    if not clips:
        raise RuntimeError("AutoClip did not produce any valid clips.")

    uploaded = []
    for clip in clips:
        video_path = job_dir / Path(clip["video_url"]).name
        result = upload_public_video(
            video_path,
            clip.get("youtube_title", clip["title"]),
            clip.get("youtube_description", clip["reason"]),
            clip.get("youtube_tags", []),
        )
        uploaded.append({
            "title": clip.get("youtube_title", clip["title"]),
            "url": result["url"],
            "privacy_status": result["privacy_status"],
        })

    summary = {
        "source_url": args.url,
        "uploaded_count": len(uploaded),
        "uploads": uploaded,
        "note": "Uploads are public. Only process content you own or are licensed to repurpose.",
    }
    summary_path = job_dir / "upload-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"AutoClip remote run failed: {exc}", file=sys.stderr)
        raise
