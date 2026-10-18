"""Unit and integration tests for Stickman Ideas, Storyboard, and Automated Channel Controller."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from benxautomation.animation.automated_channel import (
    AutomatedStickmanChannel,
    ChannelState,
)
from benxautomation.animation.stickman_engine import ComedyScene
from benxautomation.animation.stickman_ideas import (
    ComedyIdea,
    StickmanIdeaGenerator,
)
from benxautomation.animation.stickman_story import StickmanStoryResult, StickmanStoryScript
from benxautomation.animation.stickman_storyboard import StickmanStoryboardGenerator
from benxautomation.config import AppConfig, PublishingConfig
from benxautomation.publisher.ledger import UploadLedger


def test_heuristic_scoring_transparency():
    """Verify that heuristic score is calculated using exact transparent weights without fabricated trends."""
    idea = ComedyIdea(
        idea_id="test_calc",
        title="Test Calculator",
        premise="Test Premise",
        conflict="Test Conflict",
        twist="Test Twist",
        locations=["bedroom", "kitchen", "street", "comedy_burst"],
        props=["phone"],
        hook_strength=1.0,
        visual_slapstick_potential=1.0,
        clarity=1.0,
        novelty=1.0,
    )
    score = idea.compute_heuristic_score()
    assert score == pytest.approx(1.0, abs=0.001)
    assert "Hook(1.00*0.35)" in idea.rationale

    # Asymmetric test
    idea2 = ComedyIdea(
        idea_id="test_calc_2",
        title="Test 2",
        premise="P2",
        conflict="C2",
        twist="T2",
        locations=["gym"],
        props=["dumbbell"],
        hook_strength=0.8,
        visual_slapstick_potential=0.6,
        clarity=0.9,
        novelty=0.5,
    )
    # 0.35*0.8 + 0.30*0.6 + 0.20*0.9 + 0.15*0.5 = 0.28 + 0.18 + 0.18 + 0.075 = 0.715
    score2 = idea2.compute_heuristic_score()
    assert score2 == pytest.approx(0.715, abs=0.001)


def test_idea_generator_batch_and_ranking():
    """Verify batch idea generation returns ranked ideas in descending score order."""
    gen = StickmanIdeaGenerator()
    batch = gen.generate_batch(count=4)

    assert len(batch) == 4
    for i in range(len(batch) - 1):
        assert batch[i].rank_score >= batch[i + 1].rank_score
        assert batch[i].title != ""
        assert len(batch[i].locations) >= 1
        assert len(batch[i].props) >= 1


def test_storyboard_generator_scenes_and_colors():
    """Verify multi-scene storyboard contains 4 scenes, colorful backgrounds, and valid gags."""
    gen = StickmanIdeaGenerator()
    idea = gen.get_by_id("snooze_math_trap")
    assert idea is not None

    sb_gen = StickmanStoryboardGenerator()
    script = sb_gen.generate_storyboard(idea)

    valid, errors = script.validate()
    assert valid is True
    assert len(errors) == 0

    assert script.format == "shorts"
    assert len(script.scenes) == 4
    assert 28.0 <= script.total_duration <= 32.0

    # Verify background locations and props
    assert script.scenes[0].backdrop_theme == "bedroom"
    assert script.scenes[0].ben_prop == "alarm_clock"
    assert script.scenes[3].backdrop_theme == "comedy_burst"
    assert script.scenes[3].max_action == "laugh"


def test_channel_operational_controls(tmp_path: Path):
    """Verify pause, resume, emergency stop, and status inspection."""
    config_file = tmp_path / "test_channel_config.json"
    ledger_file = tmp_path / "test_ledger.sqlite"

    channel = AutomatedStickmanChannel(
        state_path=config_file,
        ledger_path=ledger_file,
    )

    # Setup
    setup_info = channel.setup_channel(channel_name="Test Cartoon Channel", publish_mode="private")
    assert setup_info["channel_name"] == "Test Cartoon Channel"
    assert setup_info["publish_mode"] == "private"

    # Status check
    st = channel.get_status()
    assert st["is_paused"] is False
    assert st["emergency_stopped"] is False

    # Pause
    channel.pause()
    assert channel.get_status()["is_paused"] is True

    # Resume
    channel.resume()
    assert channel.get_status()["is_paused"] is False

    # Emergency stop
    channel.emergency_stop()
    assert channel.get_status()["emergency_stopped"] is True
    assert channel.get_status()["is_paused"] is True

    # When stopped, produce_short should raise RuntimeError
    with pytest.raises(RuntimeError, match="Emergency stop is active"):
        channel.produce_short()


def test_channel_duplicate_prevention_in_ledger(tmp_path: Path):
    """Verify that completed uploads in ledger prevent duplicate uploads."""
    config_file = tmp_path / "test_channel_config.json"
    ledger_file = tmp_path / "test_ledger.sqlite"

    channel = AutomatedStickmanChannel(
        state_path=config_file,
        ledger_path=ledger_file,
    )

    # Create dummy video file
    dummy_video = tmp_path / "dummy_short.mp4"
    dummy_video.write_bytes(b"FAKE_VIDEO_CONTENT_12345")

    h = channel.ledger.compute_file_hash(dummy_video)
    # Pre-record completed upload in ledger
    channel.ledger.record_completed_upload(
        content_hash=h,
        video_id="YT_EXISTING_999",
        title="Existing Video",
        privacy_status="private",
        file_path=str(dummy_video),
        file_size=len(b"FAKE_VIDEO_CONTENT_12345"),
    )

    dummy_meta = tmp_path / "dummy_meta.json"
    dummy_meta.write_text("{}", encoding="utf-8")

    result = StickmanStoryResult(
        story_id="test_dup",
        title="Existing Video",
        format="shorts",
        video_path=dummy_video,
        audio_path=tmp_path / "audio.mp3",
        srt_path=tmp_path / "sub.srt",
        vtt_path=tmp_path / "sub.vtt",
        ass_path=tmp_path / "sub.ass",
        thumbnail_path=tmp_path / "thumb.jpg",
        metadata_path=dummy_meta,
        duration_seconds=30.0,
        fps=24,
        motion_verified=True,
        motion_score=8.5,
        quality_passed=True,
    )

    script = StickmanStoryScript(
        story_id="test_dup",
        title="Existing Video",
        topic="Comedy",
        scenes=[ComedyScene("s1", 30.0, "Title", "Narration", "idle", "watch")],
    )

    # Queue or upload should detect duplicate and skip
    channel._queue_or_upload_video(result, script)
    assert result.youtube_status == "ALREADY_UPLOADED"
    assert result.youtube_video_id == "YT_EXISTING_999"
    assert result.youtube_url == "https://youtu.be/YT_EXISTING_999"
