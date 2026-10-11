"""Manifest management and draft/preview review lifecycle for repurposed Shorts."""

from __future__ import annotations

import datetime
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List, Optional


@dataclass
class RepurposeClipEntry:
    """Individual candidate or approved clip in the repurposing manifest."""
    clip_id: str
    start_seconds: float
    end_seconds: float
    duration: float
    hook: str
    summary: str
    score: float
    approved: bool = True
    reframing_mode: str = "blur_pad"
    status: str = "pending"  # "pending", "rendered", "rejected", "failed"
    output_video: Optional[str] = None
    srt_path: Optional[str] = None
    vtt_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    metadata_path: Optional[str] = None
    rejection_reason: Optional[str] = None
    youtube_upload_status: str = "NOT_UPLOADED"
    youtube_video_id: Optional[str] = None
    youtube_video_url: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RepurposeClipEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class RepurposeManifest:
    """Deterministic manifest recording source, configuration, and clip processing status."""
    job_id: str
    source: str
    source_title: str
    source_duration: float
    language: str = "en"
    status: str = "draft"  # "draft", "approved", "completed", "partial_failure"
    created_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    config: dict[str, Any] = field(default_factory=dict)
    clips: list[RepurposeClipEntry] = field(default_factory=list)
    manifest_path: Optional[Path] = None

    @staticmethod
    def generate_job_id(source: str, prefix: str = "repurpose") -> str:
        """Create a deterministic, URL/filename-safe job identifier."""
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        h = hashlib.sha256(source.encode("utf-8")).hexdigest()[:6]
        return f"{prefix}_{ts}_{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "source": self.source,
            "source_title": self.source_title,
            "source_duration": round(self.source_duration, 2),
            "language": self.language,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "config": self.config,
            "clips": [c.to_dict() for c in self.clips],
        }

    def save(self, path: Path) -> Path:
        """Write manifest atomically to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path = path.resolve()
        self.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> RepurposeManifest:
        """Load manifest from JSON file."""
        resolved = Path(path).resolve()
        data = json.loads(resolved.read_text(encoding="utf-8"))
        clips = [RepurposeClipEntry.from_dict(c) for c in data.get("clips", [])]
        inst = cls(
            job_id=data["job_id"],
            source=data["source"],
            source_title=data["source_title"],
            source_duration=float(data.get("source_duration", 0.0)),
            language=data.get("language", "en"),
            status=data.get("status", "draft"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            config=data.get("config", {}),
            clips=clips,
            manifest_path=resolved,
        )
        return inst


    def reject_clip(self, clip_id: str, reason: str = "User rejected in draft review") -> bool:
        """Mark a specific candidate clip as rejected so it will not be rendered."""
        for c in self.clips:
            if c.clip_id == clip_id:
                c.approved = False
                c.status = "rejected"
                c.rejection_reason = reason
                return True
        return False

    def adjust_timestamps(
        self,
        clip_id: str,
        start_seconds: float,
        end_seconds: float,
    ) -> bool:
        """Adjust start and end timestamps for a candidate clip with boundary validation."""
        if start_seconds < 0:
            raise ValueError(f"start_seconds must be >= 0 (got {start_seconds})")
        if end_seconds <= start_seconds:
            raise ValueError(
                f"end_seconds ({end_seconds}) must be greater than start_seconds ({start_seconds})"
            )
        if self.source_duration > 0 and end_seconds > self.source_duration + 1.0:
            raise ValueError(
                f"end_seconds ({end_seconds}) exceeds source video duration ({self.source_duration})"
            )

        for c in self.clips:
            if c.clip_id == clip_id:
                c.start_seconds = round(start_seconds, 2)
                c.end_seconds = round(end_seconds, 2)
                c.duration = round(end_seconds - start_seconds, 2)
                return True
        return False

    def get_approved_clips(self) -> list[RepurposeClipEntry]:
        """Return list of candidate clips approved for rendering."""
        return [c for c in self.clips if c.approved and c.status != "rejected"]

    def validate_all(self, min_duration: float = 5.0, max_duration: float = 120.0) -> list[str]:
        """Validate all clip boundaries and return any validation errors."""
        errors: list[str] = []
        for c in self.clips:
            if c.approved:
                if c.start_seconds < 0:
                    errors.append(f"{c.clip_id}: start_seconds {c.start_seconds} is negative")
                if c.end_seconds <= c.start_seconds:
                    errors.append(f"{c.clip_id}: end_seconds {c.end_seconds} <= start_seconds {c.start_seconds}")
                dur = c.end_seconds - c.start_seconds
                if dur < min_duration:
                    errors.append(f"{c.clip_id}: duration {dur:.1f}s is less than minimum {min_duration}s")
                if dur > max_duration:
                    errors.append(f"{c.clip_id}: duration {dur:.1f}s exceeds maximum {max_duration}s")
        return errors
