"""Configuration models for Vizard AI-inspired long-form-to-Shorts repurposing."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class RepurposingConfig:
    """Settings controlling longform-to-Shorts repurposing."""
    vertical_width: int = 1080
    vertical_height: int = 1920
    fps: int = 30
    min_clip_duration: float = 15.0
    max_clip_duration: float = 60.0
    max_clips: int = 3
    reframing_mode: str = "blur_pad"  # "blur_pad" or "center_crop"
    remove_silence: bool = False
    bgm_path: Optional[str] = None
    bgm_volume: float = 0.15
    language: str = "en"
    burn_subtitles: bool = True
    output_dir: str = "output/repurposed"
    cache_dir: str = "output/repurposed_cache"
    default_privacy: str = "private"
    enforce_private: bool = True
    dry_run: bool = False
    upload_private: bool = False
    ownership_type: str = "creator_owned"
    rights_holder: str = ""
    license_evidence: str = ""
    confirm_rights: bool = False
    accept_disclaimer: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
