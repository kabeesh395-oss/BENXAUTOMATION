"""Data models for Podcast & Livestream-to-Shorts Automation System."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List, Optional


@dataclass
class PodcastInput:
    """Represents an ingested podcast or livestream video."""
    source_type: str  # "url" or "local_file"
    source_identifier: str  # URL or local path
    title: str
    duration_seconds: float
    channel_or_author: str = ""
    local_video_path: Optional[str] = None
    local_audio_path: Optional[str] = None
    extracted_subtitles_path: Optional[str] = None
    webpage_url: Optional[str] = None
    description: str = ""
    upload_date: str = ""
    format_info: str = "mp4"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TranscriptSegment:
    """A timestamped segment of the podcast transcription."""
    index: int
    start_seconds: float
    end_seconds: float
    text: str
    speaker: str = "Speaker"

    @property
    def duration(self) -> float:
        return max(0.0, self.end_seconds - self.start_seconds)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PodcastTranscript:
    """Full timestamped transcript of the podcast."""
    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str = "en"  # "en", "ta", "ta-en"
    source: str = "subtitles"  # "subtitles", "gemini", "whisper", "manual"

    @property
    def full_text(self) -> str:
        return " ".join(seg.text for seg in self.segments)

    @property
    def total_duration(self) -> float:
        if not self.segments:
            return 0.0
        return self.segments[-1].end_seconds

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "source": self.source,
            "segments": [seg.to_dict() for seg in self.segments],
            "total_segments": len(self.segments),
            "total_duration": self.total_duration,
        }

    def save_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    @classmethod
    def load_json(cls, path: Path) -> PodcastTranscript:
        data = json.loads(path.read_text(encoding="utf-8"))
        segs = [
            TranscriptSegment(
                index=s.get("index", idx),
                start_seconds=float(s["start_seconds"]),
                end_seconds=float(s["end_seconds"]),
                text=s["text"],
                speaker=s.get("speaker", "Speaker"),
            )
            for idx, s in enumerate(data.get("segments", []), start=1)
        ]
        return cls(
            segments=segs,
            language=data.get("language", "en"),
            source=data.get("source", "json"),
        )


@dataclass
class HighlightCandidate:
    """An engaging candidate short segment detected from the podcast."""
    clip_id: str
    start_seconds: float
    end_seconds: float
    duration: float
    hook: str
    reason: str
    score: float
    summary: str
    transcript_text: str
    approved: bool = False
    speaker_context: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubtitleStyle:
    """Configurable styling for animated subtitles."""
    font_name: str = "Arial"
    font_size: int = 56
    primary_color: str = "&H00FFFF&"  # Yellow in ASS hex format (&H00BBGGRR&) or White
    outline_color: str = "&H000000&"
    back_color: str = "&H80000000&"
    bold: bool = True
    margin_v: int = 220  # Distance from bottom for vertical 9:16
    alignment: int = 2   # Bottom center
    border_style: int = 1
    outline_width: int = 3
    shadow_width: int = 2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RightsDeclaration:
    """Copyright, licensing, and usage declaration for the source content."""
    ownership_type: str = "creator_owned"  # "creator_owned", "licensed", "permitted", "public_domain"
    source_url: str = ""
    rights_holder: str = ""
    license_evidence: str = ""
    music_source: str = "royalty_free"  # "cleared", "royalty_free", "no_music", "unlicensed"
    attribution_required: bool = True
    attribution_text: str = ""
    user_confirmed_rights: bool = False
    disclaimer_accepted: bool = False
    review_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ClipMetadata:
    """Complete metadata package generated for an approved Short."""
    clip_id: str
    title: str
    hook: str
    description: str
    hashtags: list[str]
    tags: list[str]
    search_keywords: list[str]
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    source_url: str
    source_attribution: str
    srt_path: str
    vtt_path: str
    thumbnail_path: str
    video_path: str
    created_at: str
    rights_declaration: dict[str, Any] = field(default_factory=dict)
    youtube_upload_status: str = "NOT_UPLOADED"
    youtube_video_id: Optional[str] = None
    youtube_video_url: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path


@dataclass
class PodcastPipelineConfig:
    """Settings controlling podcast-to-shorts rendering and extraction."""
    vertical_width: int = 1080
    vertical_height: int = 1920
    fps: int = 30
    min_clip_duration: float = 15.0
    max_clip_duration: float = 60.0
    reframing_mode: str = "blur_pad"  # "blur_pad" or "center_crop"
    subtitle_language: str = "en"     # "en", "ta", "ta-en"
    default_privacy: str = "private"
    enforce_private: bool = True
    output_dir: str = "output/podcast_shorts"
    cache_dir: str = "output/podcast_cache"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
