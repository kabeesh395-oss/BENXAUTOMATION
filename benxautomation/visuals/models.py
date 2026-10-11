"""Data models for visual scene planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class ScenePlan:
    """A planned visual scene matched to a script section."""
    scene_index: int
    title: str
    narration: str
    visual_description: str
    duration_seconds: float
    asset_path: Path
    source: str = "local"
    license: str = "unspecified"
    attribution: str = ""
    source_url: str = ""
    motion_effect: str = "zoom_in"


@dataclass
class VisualPlan:
    """Complete visual plan for rendering the video."""
    scenes: List[ScenePlan] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    is_multi_scene: bool = False
    distinct_assets_count: int = 0
    has_repeated_assets: bool = False
    animation_type: str = "2d_motion"  # Genuine 2D motion (pan/zoom/ken burns); NOT 3D

