"""Data models for script generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ScriptRequest:
    """Request parameters for generating or structuring a script."""
    topic: str
    target_audience: str = "general audience"
    language: str = "en"
    tone: str = "engaging and informative"
    video_format: str = "shorts"  # "shorts", "longform", "both"
    duration_seconds: int = 30


@dataclass
class ScriptScene:
    """A distinct scene within a generated or structured script."""
    scene_index: int
    title: str
    narration: str
    visual_description: str
    estimated_duration_seconds: float = 0.0


@dataclass
class ScriptResult:
    """Structured result of a script generation or manual structuring pass."""
    topic: str
    scenes: List[ScriptScene] = field(default_factory=list)
    full_script: str = ""
    provider: str = "unknown"
    model: Optional[str] = None
    target_audience: str = "general audience"
    language: str = "en"
    tone: str = "engaging and informative"
    estimated_duration_seconds: float = 0.0
    is_ai_generated: bool = False
