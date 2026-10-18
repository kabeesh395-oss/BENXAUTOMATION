"""Multi-Agent Autonomous Production System for BENXAUTOMATION.

Coordinates specialized autonomous agents to research, script, animate, mix,
validate, optimize, and publish authentic 2D cartoon animated videos (Shorts and Long-form).
"""

from __future__ import annotations

from benxautomation.agents.trend_scout import TrendScoutAgent, TopicIdea
from benxautomation.agents.script_director import ScriptDirectorAgent, ProductionScript, ScriptScene
from benxautomation.agents.animator import CartoonAnimatorAgent
from benxautomation.agents.audio_engineer import AudioEngineerAgent
from benxautomation.agents.video_assembler import VideoAssemblerAgent
from benxautomation.agents.seo_growth import SEOGrowthAgent, SEOPackage
from benxautomation.agents.orchestrator import MasterOrchestratorAgent, PipelineRunResult

__all__ = [
    "TrendScoutAgent",
    "TopicIdea",
    "ScriptDirectorAgent",
    "ProductionScript",
    "ScriptScene",
    "CartoonAnimatorAgent",
    "AudioEngineerAgent",
    "VideoAssemblerAgent",
    "SEOGrowthAgent",
    "SEOPackage",
    "MasterOrchestratorAgent",
    "PipelineRunResult",
]
