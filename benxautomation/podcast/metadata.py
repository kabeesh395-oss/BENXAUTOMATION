"""Metadata and thumbnail generation for per-clip Short assets.

Generates compliant, search-optimized title, description with full attribution,
hashtags, tags, SRT/VTT references, thumbnail extraction, and metadata.json.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Any, List, Optional

from benxautomation.logger import get_logger
from benxautomation.podcast.models import (
    ClipMetadata,
    HighlightCandidate,
    PodcastInput,
    RightsDeclaration,
)
from benxautomation.renderer.ffmpeg_utils import run_ffmpeg

log = get_logger(__name__)


def _seconds_to_timestamp(sec: float) -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    return f"{m:02d}:{s:02d}"


class ClipMetadataGenerator:
    """Creates metadata and extracts thumbnails for podcast short clips."""

    def extract_thumbnail(
        self,
        clip_mp4: Path,
        thumbnail_output: Path,
        offset_seconds: float = 2.0,
    ) -> Path:
        """Extract a representative keyframe thumbnail from the rendered clip."""
        thumbnail_output.parent.mkdir(parents=True, exist_ok=True)
        # Offset slightly into the clip to avoid black intro frames
        args = [
            "-ss", f"{offset_seconds:.2f}",
            "-i", str(clip_mp4),
            "-vframes", "1",
            "-q:v", "2",
            str(thumbnail_output),
        ]
        log.info("Extracting thumbnail from %s at %.1fs -> %s", clip_mp4.name, offset_seconds, thumbnail_output.name)
        try:
            run_ffmpeg(args)
        except Exception as exc:
            log.warning("Thumbnail extraction failed (%s), creating placeholder fallback", exc)
            # Create a simple BMP/JPG fallback if ffmpeg fails
            from PIL import Image
            img = Image.new("RGB", (1080, 1920), color=(20, 24, 33))
            img.save(thumbnail_output)

        return thumbnail_output

    def generate_metadata(
        self,
        candidate: HighlightCandidate,
        podcast_input: PodcastInput,
        rights_declaration: RightsDeclaration,
        *,
        video_path: Path,
        srt_path: Path,
        vtt_path: Path,
        thumbnail_path: Path,
    ) -> ClipMetadata:
        """Generate complete, attribution-compliant per-clip metadata."""
        start_ts = _seconds_to_timestamp(candidate.start_seconds)
        end_ts = _seconds_to_timestamp(candidate.end_seconds)

        # 1. Clean, compelling title
        raw_hook = candidate.hook.strip().strip('"').strip("'")
        if len(raw_hook) > 65:
            title = raw_hook[:62].rsplit(" ", 1)[0] + "..."
        else:
            title = raw_hook or f"{podcast_input.title} Highlight"

        # Ensure #Shorts tag in title
        if "#Shorts" not in title and "#shorts" not in title.lower():
            if len(title) <= 60:
                title = f"{title} #Shorts"

        # 2. Extract content hashtags
        hashtags = ["#Shorts", "#Podcast", "#Highlights", "#Interview"]
        words = re.findall(r"\b[A-Za-z]{4,}\b", candidate.transcript_text)
        for w in words[:6]:
            tag = f"#{w.capitalize()}"
            if tag not in hashtags and len(hashtags) < 7:
                hashtags.append(tag)

        # 3. Search tags
        tags = [
            "shorts",
            "podcast clip",
            "podcast highlight",
            "livestream highlight",
            podcast_input.channel_or_author.lower(),
        ]
        tags.extend([w.lower() for w in words[:8] if len(w) > 3])
        # Deduplicate while preserving order
        unique_tags = list(dict.fromkeys(tags))[:15]

        # 4. Search keywords
        keywords = [
            f"{podcast_input.title} highlights",
            f"{podcast_input.channel_or_author} best moments",
            title.replace("#Shorts", "").strip(),
            candidate.summary[:50],
        ]

        # 5. Full attribution description
        source_ref = podcast_input.webpage_url or podcast_input.source_identifier
        author = podcast_input.channel_or_author or "Original Creator"

        description_lines = [
            f"{candidate.summary}",
            "",
            f"Original Segment: {start_ts} - {end_ts}",
            "--- SOURCE ATTRIBUTION & RIGHTS NOTICE ---",
            f"Original Video: {podcast_input.title}",
            f"Channel/Creator: {author}",
            f"Source URL: {source_ref}",
            f"Rights Type: {rights_declaration.ownership_type.replace('_', ' ').title()}",
        ]

        if rights_declaration.attribution_text:
            description_lines.append(f"Attribution: {rights_declaration.attribution_text}")

        description_lines.extend([
            "",
            "Notice: Processed under verified rights declaration. Attribution alone does not grant copyright permissions.",
            " ",
            " ".join(hashtags),
        ])

        description = "\n".join(description_lines)

        meta = ClipMetadata(
            clip_id=candidate.clip_id,
            title=title,
            hook=candidate.hook,
            description=description,
            hashtags=hashtags,
            tags=unique_tags,
            search_keywords=keywords,
            start_seconds=candidate.start_seconds,
            end_seconds=candidate.end_seconds,
            duration_seconds=candidate.duration,
            source_url=source_ref,
            source_attribution=f"{author} ({source_ref})",
            srt_path=str(srt_path),
            vtt_path=str(vtt_path),
            thumbnail_path=str(thumbnail_path),
            video_path=str(video_path),
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            rights_declaration=rights_declaration.to_dict(),
        )

        # Save metadata.json
        meta_json_path = video_path.parent / f"{candidate.clip_id}_metadata.json"
        meta.save_json(meta_json_path)
        log.info("Saved metadata JSON for %s to %s", candidate.clip_id, meta_json_path.name)

        return meta
