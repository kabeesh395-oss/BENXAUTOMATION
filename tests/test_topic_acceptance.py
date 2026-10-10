"""Acceptance tests for complete topic-to-video automation pipeline."""

from pathlib import Path
import pytest

from benxautomation.config import AppConfig
from benxautomation.pipeline import VideoPipeline
from benxautomation.renderer.ffmpeg_utils import probe_file, run_ffmpeg
from tests.conftest import skip_no_ffmpeg, skip_no_ffprobe


@skip_no_ffmpeg
@skip_no_ffprobe
class TestTopicToVideoAcceptance:
    """End-to-end acceptance test for topic-to-video workflow using real local assets."""

    def test_end_to_end_topic_pipeline_with_local_assets(self, tmp_path: Path):
        cfg = AppConfig()
        cfg.rendering.shorts.duration_seconds = 3
        cfg.rendering.longform.duration_seconds = 3

        repo_root = Path(__file__).parent.parent
        assets_dir = repo_root / "assets"
        manifest_path = assets_dir / "license_manifest.yaml"
        sample_img = assets_dir / "deep_sea_abyss.jpg"

        if not sample_img.is_file():
            pytest.skip("Local test asset deep_sea_abyss.jpg not found")

        pipeline = VideoPipeline(cfg)
        out_dir = tmp_path / "acceptance_output"

        # Run with structured fallback provider (offline, deterministic, no API quota consumed)
        res = pipeline.run(
            output_dir=out_dir,
            topic="Surprising deep ocean creatures and abyss exploration",
            manifest_path=manifest_path,
            provider_name="fallback",
            render_shorts=True,
            render_longform=True,
            enable_subtitles=True,
            enable_music=False,
        )

        assert res.success is True
        assert res.script_path is not None and res.script_path.is_file()
        assert res.scene_plan_path is not None and res.scene_plan_path.is_file()
        assert res.quality_report_path is not None and res.quality_report_path.is_file()
        assert res.narration_path is not None and res.narration_path.is_file()
        assert res.subtitle_path is not None and res.subtitle_path.is_file()

        audio_info = probe_file(res.narration_path)
        audio_dur = float(audio_info["format"]["duration"])

        # Shorts (9:16, 1080x1920) validation
        assert res.shorts_result is not None
        assert res.shorts_result.output_path.is_file()
        assert res.shorts_metadata is not None
        assert res.shorts_metadata.width == 1080
        assert res.shorts_metadata.height == 1920
        assert res.shorts_metadata.has_video is True
        assert res.shorts_metadata.has_audio is True
        assert res.shorts_metadata.is_playable is True
        # Video duration must cover the full narration duration
        assert res.shorts_metadata.duration_seconds >= audio_dur

        # Longform (16:9, 1920x1080) validation
        assert res.longform_result is not None
        assert res.longform_result.output_path.is_file()
        assert res.longform_metadata is not None
        assert res.longform_metadata.width == 1920
        assert res.longform_metadata.height == 1080
        assert res.longform_metadata.has_video is True
        assert res.longform_metadata.has_audio is True
        assert res.longform_metadata.is_playable is True
        # Video duration must cover the full narration duration
        assert res.longform_metadata.duration_seconds >= audio_dur

        # Subtitle duration validation
        from benxautomation.subtitles.generator import SubtitleGenerator
        assert SubtitleGenerator.validate_srt_duration(res.subtitle_path, audio_dur, tolerance_seconds=0.05) is True

        # Complete decode test using FFmpeg directly
        shorts_decode = run_ffmpeg([
            "-v", "error",
            "-i", str(res.shorts_result.output_path),
            "-f", "null",
            "-",
        ])
        assert shorts_decode.strip() == ""

        longform_decode = run_ffmpeg([
            "-v", "error",
            "-i", str(res.longform_result.output_path),
            "-f", "null",
            "-",
        ])
        assert longform_decode.strip() == ""
