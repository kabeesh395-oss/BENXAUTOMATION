"""Models for procedural cartoon character animation and storyboards."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class CharacterPose(str, Enum):
    NEUTRAL_STAND = "NEUTRAL_STAND"
    TALKING_EXCITED = "TALKING_EXCITED"
    POINTING_RIGHT = "POINTING_RIGHT"
    POINTING_UP = "POINTING_UP"
    SHRUGGING_CONFUSED = "SHRUGGING_CONFUSED"
    THINKING_CHIN = "THINKING_CHIN"
    SURPRISED_GASPS = "SURPRISED_GASPS"
    TRIUMPHANT_ARMS_UP = "TRIUMPHANT_ARMS_UP"
    PEEKING_CURIOUS = "PEEKING_CURIOUS"
    NODDING_AGREE = "NODDING_AGREE"


class FacialExpression(str, Enum):
    NEUTRAL = "NEUTRAL"
    HAPPY_CONFIDENT = "HAPPY_CONFIDENT"
    SURPRISED_WIDE = "SURPRISED_WIDE"
    FOCUSED_SMIRK = "FOCUSED_SMIRK"
    PUZZLED_RAISED_BROW = "PUZZLED_RAISED_BROW"
    SERIOUS_WARN = "SERIOUS_WARN"


class CameraMotion(str, Enum):
    STATIC_MEDIUM = "STATIC_MEDIUM"
    DOLLY_IN_CLOSEUP = "DOLLY_IN_CLOSEUP"
    PAN_LEFT_TO_RIGHT = "PAN_LEFT_TO_RIGHT"
    SLOW_DUTCH_TILT = "SLOW_DUTCH_TILT"
    ORBIT_SUBTLE = "ORBIT_SUBTLE"


class SceneTheme(str, Enum):
    QUANTUM_GRID = "QUANTUM_GRID"
    CHART_EXPONENTIAL = "CHART_EXPONENTIAL"
    SECURITY_LOCK = "SECURITY_LOCK"
    BRAIN_NEURAL = "BRAIN_NEURAL"
    CLOCK_TIME = "CLOCK_TIME"
    MINIMAL_TOON_STAGE = "MINIMAL_TOON_STAGE"


@dataclass
class AnimationScene:
    scene_index: int
    title: str
    narration: str
    duration_seconds: float
    pose: CharacterPose
    expression: FacialExpression
    camera_motion: CameraMotion
    theme: SceneTheme
    key_action: str


@dataclass
class AnimatedShortScript:
    script_id: str
    topic_category: str
    title: str
    hook: str
    target_duration: float
    scenes: list[AnimationScene]
    description: str
    tags: list[str]
    license_statement: str = "Original script and procedural animation by BENXAUTOMATION open-source engine."


@dataclass
class AnimatedVideoResult:
    video_id: str
    title: str
    video_path: Path
    audio_path: Path
    srt_path: Path
    thumbnail_path: Path
    metadata_path: Path
    duration_seconds: float
    fps: int
    frame_count: int
    motion_verified: bool
    motion_score: float
    quality_passed: bool
    quality_issues: list[str] = field(default_factory=list)
    rights_verified: bool = True
    youtube_status: str = "PENDING"
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None
