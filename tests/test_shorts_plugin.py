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
