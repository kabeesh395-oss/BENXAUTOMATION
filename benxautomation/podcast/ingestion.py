"""Ingestion module for podcasts and livestreams.

Handles local files and authorized URL retrieval with strict adherence to platform
terms, DRM boundaries, and access restrictions.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from benxautomation.logger import get_logger
from benxautomation.podcast.errors import PodcastAccessError
from benxautomation.podcast.models import PodcastInput
from benxautomation.renderer.ffmpeg_utils import find_ffprobe, probe_file

log = get_logger(__name__)


class PodcastIngester:
    """Ingests local video files or authorized YouTube podcast/livestream replays."""

    def __init__(self, cache_dir: Path | str = "output/podcast_cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def ingest_local_file(self, file_path: Path | str) -> PodcastInput:
        """Ingest and validate a locally owned or licensed video file."""
        p = Path(file_path).resolve()
        if not p.is_file():
            raise PodcastAccessError(f"Local video file not found: {p}")
        if p.stat().st_size == 0:
            raise PodcastAccessError(f"Local video file is empty (0 bytes): {p}")

        meta = probe_file(p)
        fmt = meta.get("format", {})
        duration = float(fmt.get("duration", 0.0))
        if duration <= 0:
            raise PodcastAccessError(
                f"Could not read duration from {p.name}. Ensure it is a valid video file."
            )

        title = p.stem.replace("_", " ").title()
        log.info("Successfully ingested local file: %s (duration: %.1fs)", p.name, duration)

        return PodcastInput(
            source_type="local_file",
            source_identifier=str(p),
            title=title,
            duration_seconds=duration,
            local_video_path=str(p),
            channel_or_author="Local Creator",
            format_info=fmt.get("format_name", "mp4"),
        )

    def ingest_url(self, url: str, *, download_media: bool = True) -> PodcastInput:
        """Ingest a public/authorized video replay via yt-dlp.

        Enforces platform protections and rejects DRM-locked or inaccessible videos.
        """
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            raise PodcastAccessError(f"Invalid URL provided: '{url}'. Must be a valid HTTP(S) URL.")

        try:
            import yt_dlp
        except ImportError as exc:
            raise PodcastAccessError(
                "yt-dlp is required for URL ingestion. Install with 'pip install yt-dlp'."
            ) from exc

        log.info("Inspecting video URL: %s", url)

        # Configure yt-dlp for non-invasive extraction
        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": not download_media,
            "outtmpl": str(self.cache_dir / "%(id)s.%(ext)s"),
            "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en", "ta", "en-US", "en-GB"],
            "subtitlesformat": "vtt/srt/best",
            "noplaylist": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 1. Probe metadata first
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise PodcastAccessError(f"No metadata returned for video URL: {url}")

                # Check access restriction flags
                if info.get("is_live", False):
                    raise PodcastAccessError(
                        "The stream is currently LIVE. Wait until the livestream ends and is processed "
                        "into a replay before creating Shorts."
                    )

                if info.get("availability") in ("needs_auth", "subscriber_only", "premium_only"):
                    raise PodcastAccessError(
                        f"Access restriction detected ({info.get('availability')}). "
                        "Cannot access private, subscriber-only, or premium content without bypass. Platform protections respected."
                    )

                video_id = info.get("id", "stream")
                title = info.get("title", "Podcast Episode")
                duration = float(info.get("duration", 0.0))
                uploader = info.get("uploader", info.get("channel", "Unknown Channel"))

                # 2. Download media and subtitles if requested
                local_path: Optional[str] = None
                subs_path: Optional[str] = None

                if download_media:
                    log.info("Downloading authorized video stream for: %s (id: %s)", title, video_id)
                    downloaded_info = ydl.extract_info(url, download=True)
                    # Locate downloaded file
                    expected_file = self.cache_dir / f"{video_id}.mp4"
                    if expected_file.is_file():
                        local_path = str(expected_file)
                    else:
                        # Find matching file in cache dir
                        for f in self.cache_dir.glob(f"{video_id}.*"):
                            if f.suffix.lower() in (".mp4", ".mkv", ".webm"):
                                local_path = str(f)
                                break

                    # Look for downloaded subtitle files (.vtt / .srt)
                    for sf in self.cache_dir.glob(f"{video_id}*.vtt"):
                        subs_path = str(sf)
                        break
                    if not subs_path:
                        for sf in self.cache_dir.glob(f"{video_id}*.srt"):
                            subs_path = str(sf)
                            break

                return PodcastInput(
                    source_type="url",
                    source_identifier=url,
                    title=title,
                    duration_seconds=duration,
                    channel_or_author=uploader,
                    local_video_path=local_path,
                    extracted_subtitles_path=subs_path,
                    webpage_url=info.get("webpage_url", url),
                    description=info.get("description", "")[:1000],
                    upload_date=info.get("upload_date", ""),
                )

        except yt_dlp.utils.DownloadError as exc:
            err_msg = str(exc)
            hint = " If you have permission or licensed access to this footage, supply the authorized local file directly via --source 'path/to/video.mp4'."
            if "DRM" in err_msg or "protected" in err_msg.lower():
                raise PodcastAccessError(
                    f"DRM protection detected for URL '{url}'. Cannot bypass access controls or DRM protections.{hint}"
                ) from exc
            if "Private video" in err_msg or "Sign in" in err_msg:
                raise PodcastAccessError(
                    f"Video access denied (Private or Restricted). Platform access controls respected: {err_msg}.{hint}"
                ) from exc
            if "Geo" in err_msg or "country" in err_msg.lower():
                raise PodcastAccessError(
                    f"Geographic access restriction detected for URL '{url}'.{hint}"
                ) from exc
            raise PodcastAccessError(f"Failed to access video stream: {err_msg}.{hint}") from exc
        except Exception as exc:
            if isinstance(exc, PodcastAccessError):
                raise
            hint = " If you have permission or licensed access to this footage, supply the authorized local file directly via --source 'path/to/video.mp4'."
            raise PodcastAccessError(f"Unexpected error accessing video: {exc}.{hint}") from exc
