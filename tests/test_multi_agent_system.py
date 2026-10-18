"""Unit tests for the Multi-Agent Autonomous Video Production System."""

import tempfile
from pathlib import Path
import pytest
from PIL import Image

from benxautomation.agents.animator import CartoonAnimatorAgent
from benxautomation.agents.audio_engineer import AudioEngineerAgent
from benxautomation.agents.orchestrator import MasterOrchestratorAgent
from benxautomation.agents.script_director import ScriptDirectorAgent, ScriptScene
from benxautomation.agents.seo_growth import SEOGrowthAgent
from benxautomation.agents.trend_scout import TopicIdea, TrendScoutAgent


def test_trend_scout_selects_viral_topics():
    scout = TrendScoutAgent()
    # Test shorts selection
    short_topic = scout.select_viral_topic(format_type="shorts")
    assert short_topic.format == "shorts"
    assert short_topic.curiosity_score >= 9.0
    assert "welcome" not in short_topic.hook.lower()
    assert len(short_topic.hook) > 10

    # Test longform selection
    long_topic = scout.select_viral_topic(format_type="longform")
    assert long_topic.format == "longform"
    assert len(long_topic.chapters) > 0


def test_script_director_generates_retention_script():
    director = ScriptDirectorAgent()
    topic = TopicIdea(
        id="test_hack",
        title="Why You Should NEVER Charge Your Phone at Airports!",
        hook="Never plug your phone into a public airport charger!",
        category="tech",
        target_character="ben",
        format="shorts",
        target_duration=28.0,
        curiosity_score=9.8,
        core_premise="Juice jacking risk at public USB ports",
    )
    script = director.create_script(topic)
    assert script.topic_id == "test_hack"
    assert len(script.scenes) >= 4
    # First scene must be the high stakes hook
    assert "Never plug your phone" in script.scenes[0].dialogue
    assert len(script.loop_sentence) > 0


def test_seo_growth_agent_generates_metadata_and_thumbnail():
    seo = SEOGrowthAgent()
    topic = TopicIdea(
        id="test_thumb",
        title="Why You Should NEVER Charge Your Phone!",
        hook="Never plug your phone into an airport charger!",
        category="tech",
        target_character="ben",
        format="shorts",
        target_duration=28.0,
        curiosity_score=9.5,
        core_premise="Juice Jacking USB exploit",
        tags=["tech", "safety", "shorts"],
    )
    director = ScriptDirectorAgent()
    script = director.create_script(topic)

    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        seo_pkg = seo.optimize_metadata(topic, script, out_dir)
        assert seo_pkg.title.startswith("Why You Should NEVER")
        assert "#tech" in seo_pkg.description
        assert seo_pkg.thumbnail_path.exists()
        with Image.open(seo_pkg.thumbnail_path) as im:
            assert im.size == (1080, 1920)


def test_animator_lip_sync_and_blinking():
    animator = CartoonAnimatorAgent()
    scene = ScriptScene(
        scene_index=1,
        character="ben",
        expression="shocked",
        dialogue="Warning!",
        visual_description="BEN speaking",
        background_theme="airport",
        sfx="alert",
    )
    # Speaking frame
    frame_speaking = animator.animate_scene_frame(
        scene=scene,
        frame_idx_in_scene=5,
        total_scene_frames=40,
        is_speaking=True,
        global_frame_idx=10,
        target_size=(360, 640),
    )
    assert frame_speaking.size == (360, 640)

    # Blinking frame (frame 0)
    frame_blink = animator.animate_scene_frame(
        scene=scene,
        frame_idx_in_scene=0,
        total_scene_frames=40,
        is_speaking=False,
        global_frame_idx=80,  # 80 % 80 == 0 -> blinking
        target_size=(360, 640),
    )
    assert frame_blink.size == (360, 640)


def test_orchestrator_initialization():
    orchestrator = MasterOrchestratorAgent()
    assert orchestrator.scout is not None
    assert orchestrator.director is not None
    assert orchestrator.animator is not None
    assert orchestrator.audio is not None
    assert orchestrator.assembler is not None
    assert orchestrator.seo is not None
    assert orchestrator.repurposer is not None

