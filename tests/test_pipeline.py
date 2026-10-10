"""Integration tests for VideoPipeline."""

from pathlib import Path
import pytest

from benxautomation.config import AppConfig
from benxautomation.errors import AssetError, ManifestError
from benxautomation.pipeline import VideoPipeline
from benxautomation.renderer.ffmpeg_utils import probe_file
from tests.conftest import skip_no_ffmpeg, skip_no_ffprobe


class TestVideoPipeline:
    def test_missing_asset_raises(self, tmp_path: Path):
        pipeline = VideoPipeline(AppConfig())
        with pytest.raises(AssetError):
            pipeline.run(tmp_path / "not_there.png", tmp_path / "out")

    def test_manifest_missing_asset_raises(self, tmp_path: Path, sample_image: Path):
        pipeline = VideoPipeline(AppConfig())
        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(
            "assets:\n  - file: missing_asset.png\n    license: cc0\n",
            encoding="utf-8",
        )
        with pytest.raises(ManifestError, match="missing on disk"):
            pipeline.run(sample_image, tmp_path / "out", manifest_path=manifest)

    @skip_no_ffmpeg
    def test_end_to_end_pipeline_execution(self, sample_image: Path, tmp_output: Path):
        cfg = AppConfig()
        cfg.rendering.shorts.duration_seconds = 1
        cfg.rendering.longform.duration_seconds = 1
        pipeline = VideoPipeline(cfg)

        manifest = sample_image.parent / "license_manifest.yaml"
        manifest.write_text(
            f"assets:\n  - file: {sample_image.name}\n    license: cc0\n",
            encoding="utf-8",
        )

        res = pipeline.run(
            asset_path=sample_image,
            output_dir=tmp_output,
            duration_seconds=1,
            manifest_path=manifest,
        )

        assert res.shorts_result is not None
        assert res.shorts_result.output_path.is_file()
        assert res.shorts_result.output_path.stat().st_size > 0

        assert res.longform_result is not None
        assert res.longform_result.output_path.is_file()
        assert res.longform_result.output_path.stat().st_size > 0

    @skip_no_ffmpeg
    @skip_no_ffprobe
    def test_pipeline_narration_and_subtitle_duration_alignment(
        self, sample_image: Path, tmp_output: Path
    ):
        """Verify video duration encloses narration and subtitles align to audio."""
        cfg = AppConfig()
        pipeline = VideoPipeline(cfg)

        manifest = sample_image.parent / "license_manifest.yaml"
        manifest.write_text(
            f"assets:\n  - file: {sample_image.name}\n    license: cc0\n",
            encoding="utf-8",
        )

        script = "First sentence of test narration. Second sentence of test narration."
        res = pipeline.run(
            asset_path=sample_image,
            output_dir=tmp_output,
            script_text=script,
            manifest_path=manifest,
            enable_subtitles=True,
        )

        assert res.audio_path is not None
        assert res.audio_path.is_file()
        audio_dur = float(probe_file(res.audio_path)["format"]["duration"])
        assert audio_dur > 0

        assert res.subtitle_path is not None
        assert res.subtitle_path.is_file()
        srt_text = res.subtitle_path.read_text(encoding="utf-8")
        # Subtitles must contain the text
        assert "First sentence" in srt_text
        assert "Second sentence" in srt_text

        # Video outputs must cover the complete audio narration
        assert res.shorts_result is not None
        assert res.shorts_metadata is not None
        assert res.shorts_metadata.has_audio is True
        assert res.shorts_metadata.duration_seconds >= audio_dur - 0.1

        assert res.longform_result is not None
        assert res.longform_metadata is not None
        assert res.longform_metadata.has_audio is True
        assert res.longform_metadata.duration_seconds >= audio_dur - 0.1
