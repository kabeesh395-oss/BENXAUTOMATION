"""Tests for Shorts renderer plugin."""

from pathlib import Path
import pytest

from benxautomation.config import ShortsConfig
from benxautomation.errors import AssetError
from benxautomation.renderer.shorts_plugin import ShortsRendererPlugin
from tests.conftest import skip_no_ffmpeg


class TestShortsRendererPlugin:
    def test_missing_input_raises_asset_error(self, tmp_path: Path):
        plugin = ShortsRendererPlugin(ShortsConfig())
        out_path = tmp_path / "out.mp4"
        with pytest.raises(AssetError, match="not found"):
            plugin.render(tmp_path / "nonexistent.png", out_path)

    @skip_no_ffmpeg
    def test_render_shorts_success(self, sample_image: Path, tmp_output: Path):
        cfg = ShortsConfig(width=1080, height=1920, duration_seconds=2, fps=30)
        plugin = ShortsRendererPlugin(cfg)
        out_path = tmp_output / "shorts_output.mp4"

        result = plugin.render(sample_image, out_path, duration_seconds=2)

        assert result.output_path == out_path
        assert result.width == 1080
        assert result.height == 1920
        assert result.duration_seconds == 2.0
        assert result.format_name == "shorts_9x16"
        assert out_path.is_file()
        assert out_path.stat().st_size > 0

    @skip_no_ffmpeg
    def test_render_shorts_multi_scene(self, sample_image: Path, tmp_output: Path):
        cfg = ShortsConfig(width=1080, height=1920, duration_seconds=2, fps=30)
        plugin = ShortsRendererPlugin(cfg)
        out_path = tmp_output / "shorts_multi.mp4"

        # Create two scene objects pointing to sample_image
        from benxautomation.visuals.models import ScenePlan
        scene1 = ScenePlan(1, "S1", "N1", "V1", 1.0, sample_image)
        scene2 = ScenePlan(2, "S2", "N2", "V2", 1.0, sample_image)

        result = plugin.render(
            sample_image,
            out_path,
            duration_seconds=2,
            scenes=[scene1, scene2],
        )

        assert result.output_path == out_path
        assert out_path.is_file()
        assert out_path.stat().st_size > 0

    @skip_no_ffmpeg
    def test_render_shorts_with_burned_subtitles_and_faststart(self, sample_image: Path, tmp_output: Path):
        cfg = ShortsConfig(width=1080, height=1920, duration_seconds=2, fps=30)
        plugin = ShortsRendererPlugin(cfg)
        out_path = tmp_output / "shorts_subs.mp4"

        # Create dummy srt
        srt_path = tmp_output / "test.srt"
        srt_path.write_text("1\n00:00:00,000 --> 00:00:02,000\nTesting Subtitles\n", encoding="utf-8")

        result = plugin.render(
            sample_image,
            out_path,
            duration_seconds=2,
            subtitle_path=srt_path,
        )

        assert result.output_path.is_file()
        # Verify moov atom is placed before mdat (faststart)
        with open(out_path, "rb") as f:
            data = f.read(1024 * 32)
            assert b"moov" in data, "Expected 'moov' atom near beginning of MP4 for faststart streaming"

    @skip_no_ffmpeg
    def test_render_shorts_produces_motion_frames(self, sample_image: Path, tmp_output: Path):
        cfg = ShortsConfig(width=320, height=568, duration_seconds=2, fps=30)
        plugin = ShortsRendererPlugin(cfg)
        out_path = tmp_output / "shorts_motion.mp4"

        from benxautomation.visuals.models import ScenePlan
        scene1 = ScenePlan(1, "Scene 1", "Narration 1", "Visual 1", 2.0, sample_image, motion_effect="zoom_in")

        result = plugin.render(
            sample_image,
            out_path,
            duration_seconds=2,
            scenes=[scene1],
        )
        assert result.output_path.is_file()

        # Extract frames at 0.5s and 1.5s using ffmpeg and compare pixel differences
        import subprocess
        f1 = tmp_output / "frame_05.png"
        f2 = tmp_output / "frame_15.png"
        subprocess.run(["ffmpeg", "-y", "-ss", "0.5", "-i", str(out_path), "-vframes", "1", str(f1)], check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-ss", "1.5", "-i", str(out_path), "-vframes", "1", str(f2)], check=True, capture_output=True)

        assert f1.is_file() and f2.is_file()
        # Frames should not be identical because 2D camera zoom/particles change pixel data over time
        assert f1.read_bytes() != f2.read_bytes(), "Expected frame pixel data to differ due to 2D motion (not frozen slideshow)"
