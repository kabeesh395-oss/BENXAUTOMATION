"""Unit tests for the open-source cartoon animation system (Blender, Godot, FFmpeg)."""

import pytest
from pathlib import Path
from benxautomation.animation.models import CharacterPose, FacialExpression
from benxautomation.animation.motion_validator import MotionValidator
from benxautomation.animation.script_generator import AnimationScriptGenerator
from benxautomation.animation.tools import AnimationToolRegistry
from benxautomation.main import build_parser


def test_tool_registry_detects_installed_engines():
    registry = AnimationToolRegistry()
    summary = registry.summary()

    # Blender must be available (verified installed)
    assert registry.blender.available is True
    assert registry.blender.path is not None
    assert "Blender" in summary

    # Godot must be available (verified installed)
    assert registry.godot.available is True
    assert registry.godot.path is not None

    # OpenToonz blocker status recorded cleanly
    assert "OpenToonz" in summary

    # FFmpeg & FFprobe available
    assert registry.ffmpeg.available is True
    assert registry.ffprobe.available is True


def test_script_generator_creates_25_distinct_shorts():
    scripts = AnimationScriptGenerator.generate_all_scripts()
    assert len(scripts) == 25

    # Check uniqueness of IDs and titles
    script_ids = [s.script_id for s in scripts]
    assert len(set(script_ids)) == 25

    titles = [s.title for s in scripts]
    assert len(set(titles)) == 25

    # Check duration and scene breakdown
    for s in scripts:
        assert 30.0 <= s.target_duration <= 42.0
        assert len(s.scenes) >= 4
        assert s.license_statement.startswith("Original script")
        for sc in s.scenes:
            assert isinstance(sc.pose, CharacterPose)
            assert isinstance(sc.expression, FacialExpression)
            assert len(sc.narration) > 10


def test_motion_validator_rejects_missing_file(tmp_path: Path):
    validator = MotionValidator()
    missing_p = tmp_path / "non_existent.mp4"
    res = validator.validate_animation(missing_p)
    assert res.is_valid is False
    assert any("does not exist" in r for r in res.reasons)


def test_cli_parsing_for_animated_workflow():
    parser = build_parser()
    args = parser.parse_args(["--workflow", "animated", "--sample-only", "--count", "5", "--upload-public"])
    assert args.workflow == "animated"
    assert args.sample_only is True
    assert args.count == 5
    assert args.upload_public is True
