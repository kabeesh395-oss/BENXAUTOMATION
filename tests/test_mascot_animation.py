"""Unit and integration tests for BENX Mascot 2D animation engine and story pipeline."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from benxautomation.animation.mascot_assets import MascotAssetBuilder
from benxautomation.animation.mascot_engine import (
    MascotAnimationEngine,
    MascotRenderConfig,
    MascotRig,
    MascotScene,
)
from benxautomation.animation.motion_validator import MotionValidator
from benxautomation.animation.story_pipeline import (
    LocalStoryScriptCatalog,
    MascotStoryResult,
    StoryAnimationPipeline,
    StoryScript,
)
from benxautomation.renderer.ffmpeg_utils import find_ffmpeg, find_ffprobe, probe_file
from tests.conftest import skip_no_ffmpeg, skip_no_ffprobe


def test_character_spec_and_manifest():
    """Verify BENX character specification JSON has required properties and colors."""
    spec_path = Path("assets/mascot/character_spec.json")
    assert spec_path.is_file(), "character_spec.json must exist"

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec["character_id"] == "benx_scout"
    assert spec["name"] == "BENX"
    assert "#00F2FE" in spec["colors"]["cyber_teal"].upper()
    assert "#0B132B" in spec["colors"]["obsidian_graphite"].upper()
    assert "happy" in spec["expressions"]
    assert "surprised" in spec["expressions"]
    assert "blink" not in spec["expressions"]  # Blink is an eye state, not a basic mood
    assert "idle" in spec["poses"]
    assert "pointing_up" in spec["poses"]
    assert "shorts" in spec["render_formats"]
    assert "longform" in spec["render_formats"]


def test_mascot_asset_builder_generates_all_layers(tmp_path: Path):
    """Verify that MascotAssetBuilder generates all layer files deterministically."""
    builder = MascotAssetBuilder(output_dir=tmp_path)
    layers = builder.generate_all(force=True)

    assert len(layers) >= 24
    assert (tmp_path / "head_base.png").is_file()
    assert (tmp_path / "visor_plate.png").is_file()
    assert (tmp_path / "eyes_happy.png").is_file()
    assert (tmp_path / "eyes_blink.png").is_file()
    assert (tmp_path / "mouth_a.png").is_file()
    assert (tmp_path / "torso_front.png").is_file()
    assert (tmp_path / "arms_gesture.png").is_file()
    assert (tmp_path / "rig_manifest.json").is_file()


def test_mascot_rig_compositing(tmp_path: Path):
    """Test that MascotRig properly layers character components into a 600x600 RGBA image."""
    builder = MascotAssetBuilder(output_dir=tmp_path)
    builder.generate_all()

    rig = MascotRig(assets_dir=tmp_path)
    char_img = rig.composite_character(
        pose="pointing_up",
        expression="excited",
        viseme="a",
        view="front",
        is_blinking=False,
    )

    assert char_img.size == (600, 600)
    assert char_img.mode == "RGBA"
    # Ensure non-transparent pixels exist
    arr = np.array(char_img)
    assert arr[:, :, 3].max() > 0


def test_mascot_scene_validation():
    """Verify that MascotScene rejects invalid durations, poses, or expressions."""
    # Valid scene
    valid_scene = MascotScene(
        scene_id="sc_1",
        duration_seconds=3.0,
        dialogue="Hello world",
        pose="gesture",
        expression="happy",
        view="front",
    )
    ok, errs = valid_scene.validate()
    assert ok
    assert not errs

    # Invalid duration
    bad_dur = MascotScene(
        scene_id="sc_bad_dur",
        duration_seconds=-1.0,
        dialogue="Negative time",
    )
    ok, errs = bad_dur.validate()
    assert not ok
    assert any("duration" in e.lower() for e in errs)

    # Unknown pose
    bad_pose = MascotScene(
        scene_id="sc_bad_pose",
        duration_seconds=2.0,
        dialogue="Bad pose",
        pose="invalid_backflip",
    )
    ok, errs = bad_pose.validate()
    assert not ok
    assert any("pose" in e.lower() for e in errs)

    # Unknown expression
    bad_expr = MascotScene(
        scene_id="sc_bad_expr",
        duration_seconds=2.0,
        dialogue="Bad mood",
        expression="rage_monster",
    )
    ok, errs = bad_expr.validate()
    assert not ok
    assert any("expression" in e.lower() for e in errs)


def test_mascot_render_configs():
    """Verify render configurations for both 9:16 Shorts and 16:9 Long-form."""
    shorts_cfg = MascotRenderConfig.for_shorts(fps=30)
    assert shorts_cfg.width == 1080
    assert shorts_cfg.height == 1920
    assert shorts_cfg.aspect_ratio == "9:16"
    assert shorts_cfg.fps == 30

    long_cfg = MascotRenderConfig.for_longform(fps=24)
    assert long_cfg.width == 1920
    assert long_cfg.height == 1080
    assert long_cfg.aspect_ratio == "16:9"
    assert long_cfg.fps == 24


def test_mascot_animation_engine_renders_distinct_moving_frames(tmp_path: Path):
    """Verify that sequential frames have mathematical inter-frame motion delta > 0."""
    builder = MascotAssetBuilder(output_dir=tmp_path / "mascot")
    builder.generate_all()

    cfg = MascotRenderConfig(width=540, height=960, fps=24, aspect_ratio="9:16")
    engine = MascotAnimationEngine(config=cfg, assets_dir=tmp_path / "mascot")

    scene = MascotScene(
        scene_id="test_sc",
        duration_seconds=2.0,
        dialogue="This is a test of animated movement across multiple frames.",
        pose="gesture",
        expression="surprised",
        view="front",
        camera_motion="DOLLY_IN_CLOSEUP",
    )

    frame_0 = engine.render_frame(scene, scene_time=0.0, global_time=0.0)
    frame_1 = engine.render_frame(scene, scene_time=0.5, global_time=0.5)
    frame_2 = engine.render_frame(scene, scene_time=1.0, global_time=1.0)

    assert frame_0.size == (540, 960)
    assert frame_1.size == (540, 960)
    assert frame_2.size == (540, 960)

    # Compute difference between frame_0 and frame_1
    arr0 = np.array(frame_0.convert("L"), dtype=np.float32)
    arr1 = np.array(frame_1.convert("L"), dtype=np.float32)
    delta_0_1 = float(np.mean(np.abs(arr0 - arr1))) / 255.0 * 100.0

    # Assert genuine movement (breathing, particle drift, viseme change)
    assert delta_0_1 > 0.5, f"Expected distinct moving frames, but delta was only {delta_0_1:.2f}%"


def test_local_story_script_catalog():
    """Verify preset stories and parsing of raw story text into structured scenes."""
    preset = LocalStoryScriptCatalog.get_preset_story("ai_quantum_leap", fmt="shorts")
    assert preset.title
    assert len(preset.scenes) >= 3
    valid, errs = preset.validate()
    assert valid

    raw_text = (
        "First, we discover a hidden digital realm.\n"
        "Next, security protocols attempt to block our progress.\n"
        "Finally, BENX overcomes the obstacles with quantum power."
    )
    custom_script = LocalStoryScriptCatalog.parse_raw_story_text("Custom Quest", raw_text, fmt="shorts")
    assert custom_script.title == "Custom Quest"
    assert len(custom_script.scenes) == 3
    assert custom_script.scenes[0].dialogue.startswith("First")
    assert custom_script.scenes[1].dialogue.startswith("Next")
    assert custom_script.scenes[2].dialogue.startswith("Finally")
    valid, errs = custom_script.validate()
    assert valid


@skip_no_ffmpeg
@skip_no_ffprobe
def test_mascot_story_pipeline_render_sample_video(tmp_path: Path):
    """Integration test: Render a real short animated video with BENX mascot and verify with ffprobe and MotionValidator."""
    output_dir = tmp_path / "output_test"
    assets_dir = tmp_path / "mascot_assets"

    # Pre-generate assets
    MascotAssetBuilder(output_dir=assets_dir).generate_all()

    pipeline = StoryAnimationPipeline(
        output_dir=output_dir,
        assets_dir=assets_dir,
    )

    # Short 2-scene test script (approx 3.0s total for fast deterministic test)
    script = StoryScript(
        story_id="test_mini_short",
        title="Mini Test Mascot Animation",
        topic="Testing",
        format="shorts",
        scenes=[
            MascotScene(
                scene_id="sc_1",
                duration_seconds=1.5,
                dialogue="BENX is actively animated and moving.",
                pose="gesture",
                expression="happy",
                view="front",
                camera_motion="DOLLY_IN_CLOSEUP",
                theme="cyber_grid",
                action_text="ACTION 1",
            ),
            MascotScene(
                scene_id="sc_2",
                duration_seconds=1.5,
                dialogue="Notice the changing pose and blinking eyes.",
                pose="pointing_up",
                expression="excited",
                view="three_quarter_left",
                camera_motion="STATIC_MEDIUM",
                theme="cyber_grid",
                action_text="ACTION 2",
            ),
        ],
    )

    result = pipeline.produce_story_animation(script, fps=24)

    assert result.video_path.is_file(), f"Video file missing: {result.video_path}"
    assert result.video_path.stat().st_size > 0, "Video file is empty"
    assert result.thumbnail_path.is_file(), "Thumbnail missing"
    assert result.srt_path.is_file(), "SRT subtitle file missing"
    assert result.vtt_path.is_file(), "VTT subtitle file missing"
    assert result.metadata_path.is_file(), "Metadata JSON missing"

    # FFprobe stream verification
    info = probe_file(result.video_path)
    streams = info.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    assert video_stream is not None, "No video stream"
    assert int(video_stream["width"]) == 1080
    assert int(video_stream["height"]) == 1920
    dur = float(info.get("format", {}).get("duration") or video_stream.get("duration", 0.0))
    assert dur > 2.0

    # Mathematical motion verification
    assert result.motion_verified, f"Motion failed: {result.quality_issues}"
    assert result.motion_score > 0.5


def test_story_pipeline_rejects_invalid_scenes(tmp_path: Path):
    """Verify that a broken scene produces a clean ValueError and never outputs a silent broken video."""
    pipeline = StoryAnimationPipeline(
        output_dir=tmp_path / "out",
        assets_dir=tmp_path / "mascot",
    )
    bad_script = StoryScript(
        story_id="bad_story",
        title="Bad Story",
        topic="Error Handling",
        scenes=[
            MascotScene(
                scene_id="bad_sc",
                duration_seconds=-5.0,  # Negative duration
                dialogue="Impossible scene",
                pose="invalid_pose_name",
            )
        ],
    )

    with pytest.raises(ValueError) as excinfo:
        pipeline.produce_story_animation(bad_script)

    assert "Script validation failed" in str(excinfo.value)


def test_story_pipeline_subtitle_phrase_chunking_and_ass_styling(tmp_path: Path):
    """Regression test: Ensure subtitles are chunked into short readable cues and formatted with ASS safe margins."""
    pipeline = StoryAnimationPipeline(
        output_dir=tmp_path / "out",
        assets_dir=tmp_path / "mascot",
    )
    long_dialogue = "Traditional chips check one path at a time. Quantum qubits explore every possibility simultaneously."
    cues = pipeline._chunk_dialogue_cues(long_dialogue, duration=4.0, max_words=6)

    # Must be split into at least 2 cues so no cue exceeds safe line limits
    assert len(cues) >= 2
    for start_t, end_t, text in cues:
        assert len(text.split()) <= 8
        assert start_t < end_t

    # Test ASS header and margin generation
    srt_out = tmp_path / "test.srt"
    vtt_out = tmp_path / "test.vtt"
    ass_out = tmp_path / "test.ass"

    scenes = [
        MascotScene(
            scene_id="s1",
            duration_seconds=3.0,
            dialogue=long_dialogue,
            action_text="QUANTUM TEST",
        )
    ]
    pipeline._generate_synced_subtitles(scenes, srt_out, vtt_out, ass_out, format_type="shorts")

    assert ass_out.is_file()
    ass_content = ass_out.read_text(encoding="utf-8")
    assert "PlayResX: 1080" in ass_content
    assert "PlayResY: 1920" in ass_content
    assert "MarginV, Encoding" in ass_content
    assert ",330,1" in ass_content  # Verifies 330px bottom margin for Shorts safe zone
    assert "QUANTUM TEST" not in ass_content  # Action pill is separate from subtitles

