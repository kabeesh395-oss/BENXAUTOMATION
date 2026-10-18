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

from benxautomation.animation.mascot_assets import MascotAssetBuilder
from benxautomation.animation.mascot_engine import (
    MascotAnimationEngine,
    MascotRenderConfig,
    MascotRig,
    MascotScene,
)
from benxautomation.animation.story_pipeline import (
    LocalStoryScriptCatalog,
    MascotStoryResult,
    StoryAnimationPipeline,
    StoryScript,
)

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
    "MascotAssetBuilder",
    "MascotAnimationEngine",
    "MascotRenderConfig",
    "MascotRig",
    "MascotScene",
    "StoryAnimationPipeline",
    "StoryScript",
    "MascotStoryResult",
    "LocalStoryScriptCatalog",
    "ComedyScene",
    "StickmanAnimationEngine",
    "StickmanRig",
    "StickmanPose",
    "LimbAngles",
    "StickmanStoryPipeline",
    "StickmanStoryScript",
    "StickmanStoryResult",
    "FunnyStickmanScriptCatalog",
    "ComedyIdea",
    "StickmanIdeaGenerator",
    "StickmanStoryboardGenerator",
    "AutomatedStickmanChannel",
    "CharacterProfile",
    "DynamicCharacterFactory",
]
from benxautomation.animation.stickman_engine import (
    ComedyScene,
    LimbAngles,
    StickmanAnimationEngine,
    StickmanPose,
    StickmanRig,
)
from benxautomation.animation.stickman_story import (
    FunnyStickmanScriptCatalog,
    StickmanStoryPipeline,
    StickmanStoryResult,
    StickmanStoryScript,
)
from benxautomation.animation.stickman_ideas import (
    ComedyIdea,
    StickmanIdeaGenerator,
)
from benxautomation.animation.stickman_storyboard import (
    StickmanStoryboardGenerator,
)
from benxautomation.animation.character_universe import (
    CharacterProfile,
    DynamicCharacterFactory,
)


def __getattr__(name: str):
    if name == "AutomatedStickmanChannel":
        from benxautomation.animation.automated_channel import AutomatedStickmanChannel
        return AutomatedStickmanChannel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

