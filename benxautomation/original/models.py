"""Data models for copyright-safe original video production."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List, Optional


@dataclass
class SceneDefinition:
    """Individual scene within an original video."""
    scene_index: int
    title: str
    narration: str
    visual_theme: str
    asset_file: str
    estimated_duration_seconds: float = 6.0


@dataclass
class OriginalScript:
    """Fully authored, original video script."""
    topic_id: str
    title: str
    format: str  # "shorts" (9:16) or "longform" (16:9)
    hook: str
    scenes: list[SceneDefinition]
    total_estimated_duration: float
    research_attribution: str
    license_statement: str = "Original text by BENXAUTOMATION; no copyrighted third-party script used"
    tags: list[str] = field(default_factory=list)

    @property
    def full_script(self) -> str:
        return " ".join(s.narration for s in self.scenes)


@dataclass
class AssetSpec:
    """Specification for an original graphic or visual asset."""
    filename: str
    title: str
    subtitle: str
    format: str  # "portrait" (1080x1920) or "landscape" (1920x1080)
    primary_color: str
    secondary_color: str
    icon_symbol: str
    bullet_points: list[str] = field(default_factory=list)
    license: str = "original_creator_owned"
    attribution: str = "Created by BENXAUTOMATION original content engine"


@dataclass
class OriginalTopicConfig:
    """Topic configuration derived from research references."""
    topic_id: str
    reference_url: str
    reference_subject: str
    core_factual_domain: str
    target_shorts_count: int = 2
    create_longform: bool = True
    educational_summary: str = ""


@dataclass
class OriginalVideoResult:
    """Verification and publishing result for an authored video."""
    video_id: str
    topic_id: str
    title: str
    format: str  # "shorts" or "longform"
    output_path: Path
    duration_seconds: float
    quality_passed: bool
    quality_issues: list[str] = field(default_factory=list)
    rights_verified: bool = True
    rights_notes: str = "All visual assets and scripts are creator-owned original creations."
    upload_status: str = "PENDING"  # "UPLOADED_PRIVATE", "RIGHTS_BLOCKED", "QUALITY_BLOCKED", "QUOTA_EXHAUSTED", "OAUTH_UNCONFIGURED"
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None
    youtube_privacy_status: Optional[str] = None
    upload_timestamp: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["output_path"] = str(self.output_path)
        return d


@dataclass
class DailyProductionSummary:
    """Summary of daily capacity, generation and upload metrics."""
    timestamp: str
    total_shorts_generated: int = 0
    total_longform_generated: int = 0
    quality_approved_videos: int = 0
    quality_rejected_videos: int = 0
    private_uploads_completed: int = 0
    uploads_blocked_rights: int = 0
    uploads_blocked_quality: int = 0
    uploads_blocked_quota: int = 0
    videos: list[dict[str, Any]] = field(default_factory=list)
    quota_units_used: int = 0
    remaining_candidates: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
