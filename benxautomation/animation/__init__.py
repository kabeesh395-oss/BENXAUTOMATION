"""Open-source character animation module using Blender, Godot, and FFmpeg."""

from benxautomation.animation.blender_animator import BlenderAnimator
from benxautomation.animation.models import (
    AnimatedShortScript,
    AnimatedVideoResult,
    AnimationScene,
    CameraMotion,
    CharacterPose,
    FacialExpression,
    SceneTheme,
)
from benxautomation.animation.motion_validator import MotionValidator
from benxautomation.animation.pipeline import AnimationPipeline
from benxautomation.animation.script_generator import AnimationScriptGenerator
from benxautomation.animation.tools import AnimationToolRegistry

__all__ = [
    "AnimationPipeline",
    "AnimationToolRegistry",
    "AnimationScriptGenerator",
    "BlenderAnimator",
    "MotionValidator",
    "AnimatedShortScript",
    "AnimatedVideoResult",
    "AnimationScene",
    "CharacterPose",
    "FacialExpression",
    "CameraMotion",
    "SceneTheme",
]
