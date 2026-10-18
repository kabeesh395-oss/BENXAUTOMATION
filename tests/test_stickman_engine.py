"""Unit and integration tests for the Funny Stickman (BEN & MAX) Animation Engine."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from benxautomation.animation.stickman_engine import (
    ComedyScene,
    LimbAngles,
    StickmanAnimationEngine,
    StickmanPose,
    StickmanRig,
    ease_in_out,
    ease_out_bounce,
    lerp,
)
from benxautomation.animation.stickman_story import (
    FunnyStickmanScriptCatalog,
    StickmanStoryPipeline,
    StickmanStoryResult,
    StickmanStoryScript,
)
from benxautomation.renderer.ffmpeg_utils import find_ffmpeg, find_ffprobe, probe_file
from tests.conftest import skip_no_ffmpeg, skip_no_ffprobe


def test_rig_initialization():
    """Verify BEN and MAX rigs initialize with correct character tags and anatomy."""
    ben = StickmanRig("BEN")
    max_rig = StickmanRig("MAX")

    assert ben.character == "BEN"
    assert max_rig.character == "MAX"
    assert ben.head_radius > 0
    assert ben.torso_length > ben.head_radius


def test_easing_functions():
    """Verify smooth easing curves for slapstick physical animation."""
    assert lerp(0.0, 100.0, 0.5) == 50.0
    assert ease_in_out(0.0) == 0.0
    assert ease_in_out(1.0) == 1.0
    assert ease_out_bounce(0.0) == 0.0
    assert 0.95 <= ease_out_bounce(1.0) <= 1.05


def test_walk_and_run_cycles():
    """Verify deterministic walk and run cycles produce valid limb angles and bobs."""
    ben = StickmanRig("BEN")
    walk_pose_0 = ben.get_walk_cycle_pose(0.0)
    walk_pose_mid = ben.get_walk_cycle_pose(3.14159)

    assert isinstance(walk_pose_0, StickmanPose)
    assert walk_pose_0.limbs.left_hip != walk_pose_mid.limbs.left_hip

    run_pose = ben.get_run_cycle_pose(1.5)
    assert run_pose.limbs.spine_tilt > 10.0  # Forward lean during run
    assert run_pose.squash_x >= 1.0


def test_slip_and_fall_progression():
    """Verify slapstick 3-stage slip-and-fall physics."""
    ben = StickmanRig("BEN")
    # Stage 1: foot slip & pitch back
    s1 = ben.get_slip_fall_pose(0.1)
    assert s1.expression == "shocked"
    assert s1.rotation < 0.0

    # Stage 2: horizontal air hang
    s2 = ben.get_slip_fall_pose(0.45)
    assert s2.rotation < -40.0

    # Stage 3: ground splat with dizzy stars
    s3 = ben.get_slip_fall_pose(0.9)
    assert s3.expression == "dizzy"
    assert s3.squash_x > 1.0  # Comic squash on ground impact


def test_pose_interpolation():
    """Verify smooth interpolation between two distinct poses."""
    ben = StickmanRig("BEN")
    p1 = StickmanPose(x=0.0, y=0.0, scale=1.0)
    p2 = StickmanPose(x=100.0, y=50.0, scale=1.5)

    mid = ben.interpolate_pose(p1, p2, 0.5)
    assert mid.x == pytest.approx(50.0, abs=1.0)
    assert mid.y == pytest.approx(25.0, abs=1.0)
    assert mid.scale == pytest.approx(1.25, abs=0.05)


def test_render_scene_frame():
    """Verify rendering a 1080x1920 comedy frame with BEN, MAX, and backdrop."""
    engine = StickmanAnimationEngine(width=540, height=960, fps=24)
    scene = ComedyScene(
        scene_id="test_sc",
        duration_seconds=3.0,
        title="Test Slip",
        narration="Testing the banana peel!",
        ben_action="slip",
        max_action="shock",
        sfx_cue="boing",
    )

    frame = engine.render_scene_frame(scene, scene_time=1.0, global_time=1.0)
    assert isinstance(frame, Image.Image)
    assert frame.size == (540, 960)
    assert frame.mode == "RGBA"


def test_script_catalog_validation():
    """Verify the curated 30-second funny stickman script is valid."""
    script = FunnyStickmanScriptCatalog.get_quantum_banana_glitch()
    valid, errors = script.validate()

    assert valid is True
    assert len(errors) == 0
    assert 28.0 <= script.total_duration <= 32.0
    assert len(script.scenes) >= 3


@skip_no_ffmpeg
def test_short_mp4_render(tmp_path: Path):
    """Render a 2-second stickman test clip and verify FFmpeg output."""
    engine = StickmanAnimationEngine(width=480, height=854, fps=12)
    scenes = [
        ComedyScene(
            scene_id="s1",
            duration_seconds=2.0,
            title="Mini Clip",
            narration="Testing short render",
            ben_action="run",
            max_action="watch",
        )
    ]
    out_mp4 = tmp_path / "stickman_test.mp4"
    engine.render_to_mp4(scenes, out_mp4)

    assert out_mp4.is_file()
    assert out_mp4.stat().st_size > 5000

    info = probe_file(out_mp4)
    assert info is not None
    video_stream = next(s for s in info.get("streams", []) if s.get("codec_type") == "video")
    assert video_stream["width"] == 480
    assert video_stream["height"] == 854
    assert float(info["format"]["duration"]) >= 1.8
