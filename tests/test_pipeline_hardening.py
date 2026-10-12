"""Regression tests for pipeline hardening, Blender requirement, and private upload safety."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from benxautomation.animation.models import (
    AnimatedShortScript,
    AnimatedVideoResult,
    AnimationScene,
    CameraMotion,
    CharacterPose,
    FacialExpression,
    SceneTheme,
)
from benxautomation.animation.pipeline import AnimationPipeline
from benxautomation.animation.story_pipeline import StoryAnimationPipeline, StoryScript, MascotScene


def _make_dummy_video_result(
    tmp_path: Path,
    quality_passed: bool = True,
    motion_verified: bool = True,
    rights_verified: bool = True,
) -> tuple[AnimatedVideoResult, AnimatedShortScript]:
    vid_file = tmp_path / "dummy.mp4"
    vid_file.write_bytes(b"dummy_mp4_bytes")

    v_res = AnimatedVideoResult(
        video_id="dummy_01",
        title="Dummy Short",
        video_path=vid_file,
        audio_path=tmp_path / "dummy.mp3",
        srt_path=tmp_path / "dummy.srt",
        thumbnail_path=tmp_path / "dummy.jpg",
        metadata_path=tmp_path / "dummy.json",
        duration_seconds=30.0,
        fps=30,
        frame_count=900,
        motion_verified=motion_verified,
        motion_score=3.5,
        quality_passed=quality_passed,
        rights_verified=rights_verified,
    )

    script = AnimatedShortScript(
        script_id="dummy_01",
        topic_category="Tech",
        title="Dummy Short",
        hook="Hook",
        target_duration=30.0,
        scenes=[
            AnimationScene(
                scene_index=1,
                title="Scene 1",
                narration="Narration text",
                duration_seconds=30.0,
                pose=CharacterPose.NEUTRAL_STAND,
                expression=FacialExpression.HAPPY_CONFIDENT,
                camera_motion=CameraMotion.STATIC_MEDIUM,
                theme=SceneTheme.QUANTUM_GRID,
                key_action="Action",
            )
        ],
        description="Description",
        tags=["tech"],
    )
    return v_res, script


def test_blender_availability_condition_raises_runtime_error_when_missing(tmp_path: Path):
    """Verify that AnimationPipeline strictly raises RuntimeError when Blender is unavailable."""
    with patch("benxautomation.animation.pipeline.AnimationToolRegistry") as mock_registry_cls:
        mock_registry = MagicMock()
        mock_registry.blender.available = False
        mock_registry.blender.path = None
        mock_registry.blender.notes = "Blender executable missing"
        mock_registry_cls.return_value = mock_registry

        with pytest.raises(RuntimeError) as excinfo:
            AnimationPipeline(output_dir=tmp_path)

        assert "Blender is required for animation pipeline" in str(excinfo.value)
        assert "Blender executable missing" in str(excinfo.value)


def test_private_upload_forces_private_privacy_status(tmp_path: Path):
    """Verify that upload_private_video strictly forces privacy_status='private' even if caller passes public."""
    with patch("benxautomation.animation.pipeline.AnimationToolRegistry") as mock_reg:
        blender_file = tmp_path / "blender.exe"
        blender_file.write_bytes(b"")
        mock_reg.return_value.blender.available = True
        mock_reg.return_value.blender.path = blender_file
        mock_reg.return_value.ffmpeg.path = Path("ffmpeg")
        mock_reg.return_value.ffprobe.path = Path("ffprobe")

        pipeline = AnimationPipeline(output_dir=tmp_path)

        v_res, script = _make_dummy_video_result(tmp_path)

        with patch.object(pipeline, "upload_video") as mock_upload:
            mock_upload.return_value = ("UPLOADED_PRIVATE", "test_id", "https://youtu.be/test_id")

            # Caller tries to pass privacy_status="public" to upload_private_video
            pipeline.upload_private_video(v_res, script, privacy_status="public")

            # upload_video must have received privacy_status="private"
            mock_upload.assert_called_once_with(v_res, script, privacy_status="private")


def test_upload_video_rejects_unsupported_privacy_status(tmp_path: Path):
    """Verify that upload_video raises ValueError on unsupported privacy status."""
    with patch("benxautomation.animation.pipeline.AnimationToolRegistry") as mock_reg:
        blender_file = tmp_path / "blender.exe"
        blender_file.write_bytes(b"")
        mock_reg.return_value.blender.available = True
        mock_reg.return_value.blender.path = blender_file
        mock_reg.return_value.ffmpeg.path = Path("ffmpeg")
        mock_reg.return_value.ffprobe.path = Path("ffprobe")

        pipeline = AnimationPipeline(output_dir=tmp_path)
        v_res, script = _make_dummy_video_result(tmp_path)

        for bad_status in ["secret", "hidden", "internal", ""]:
            with pytest.raises(ValueError) as excinfo:
                pipeline.upload_video(v_res, script, privacy_status=bad_status)
            assert "Unsupported privacy status" in str(excinfo.value)


def test_rights_check_failure_blocks_publishing(tmp_path: Path):
    """Verify that a video with rights_verified=False is rejected and never uploaded."""
    with patch("benxautomation.animation.pipeline.AnimationToolRegistry") as mock_reg:
        blender_file = tmp_path / "blender.exe"
        blender_file.write_bytes(b"")
        mock_reg.return_value.blender.available = True
        mock_reg.return_value.blender.path = blender_file
        mock_reg.return_value.ffmpeg.path = Path("ffmpeg")
        mock_reg.return_value.ffprobe.path = Path("ffprobe")

        pipeline = AnimationPipeline(output_dir=tmp_path)
        v_res, script = _make_dummy_video_result(tmp_path, rights_verified=False)

        status, vid_id, url = pipeline.upload_video(v_res, script, privacy_status="private")
        assert status == "SKIPPED_RIGHTS_FAILED"
        assert vid_id is None
        assert url is None


def test_mascot_asset_builder_handles_custom_output_dir(tmp_path: Path):
    """Verify mascot asset builder generates full rig manifest in isolated directory."""
    from benxautomation.animation.mascot_assets import MascotAssetBuilder

    target = tmp_path / "custom_rig"
    builder = MascotAssetBuilder(output_dir=target)
    layers = builder.generate_all(force=True)

    assert len(layers) >= 24
    manifest = target / "rig_manifest.json"
    assert manifest.is_file()
    assert (target / "head_base.png").is_file()
    assert (target / "torso_front.png").is_file()
