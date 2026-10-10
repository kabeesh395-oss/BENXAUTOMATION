"""Tests for Longform renderer plugin."""

from pathlib import Path
import pytest

from benxautomation.config import LongformConfig
from benxautomation.errors import AssetError
from benxautomation.renderer.longform_plugin import LongformRendererPlugin
from tests.conftest import skip_no_ffmpeg


class TestLongformRendererPlugin:
    def test_missing_input_raises_asset_error(self, tmp_path: Path):
        plugin = LongformRendererPlugin(LongformConfig())
        out_path = tmp_path / "out.mp4"
        with pytest.raises(AssetError, match="not found"):
            plugin.render(tmp_path / "nonexistent.png", out_path)

    @skip_no_ffmpeg
    def test_render_longform_success(self, sample_image: Path, tmp_output: Path):
        cfg = LongformConfig(width=1920, height=1080, duration_seconds=2, fps=30)
        plugin = LongformRendererPlugin(cfg)
        out_path = tmp_output / "longform_output.mp4"

        result = plugin.render(sample_image, out_path, duration_seconds=2)

        assert result.output_path == out_path
        assert result.width == 1920
        assert result.height == 1080
        assert result.duration_seconds == 2.0
        assert result.format_name == "longform_16x9"
        assert out_path.is_file()
        assert out_path.stat().st_size > 0

    @skip_no_ffmpeg
    def test_render_longform_multi_scene(self, sample_image: Path, tmp_output: Path):
        cfg = LongformConfig(width=1920, height=1080, duration_seconds=2, fps=30)
        plugin = LongformRendererPlugin(cfg)
        out_path = tmp_output / "longform_multi.mp4"

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
