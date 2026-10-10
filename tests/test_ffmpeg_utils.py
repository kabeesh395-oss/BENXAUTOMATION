"""Tests for FFmpeg utility functions."""

import pytest

from benxautomation.renderer.ffmpeg_utils import (
    ffmpeg_is_available,
    find_ffmpeg,
    probe_file,
)
from benxautomation.errors import FFmpegNotFoundError
from tests.conftest import HAS_FFMPEG, skip_no_ffmpeg, skip_no_ffprobe


class TestFindFFmpeg:
    def test_bogus_path_raises(self):
        with pytest.raises(FFmpegNotFoundError):
            find_ffmpeg("/nonexistent/ffmpeg_xyz_999")

    @skip_no_ffmpeg
    def test_default_path_resolves(self):
        path = find_ffmpeg("ffmpeg")
        assert path  # non-empty string


class TestFFmpegIsAvailable:
    def test_returns_bool(self):
        result = ffmpeg_is_available()
        assert isinstance(result, bool)

    def test_bogus_returns_false(self):
        assert ffmpeg_is_available("/no/such/ffmpeg") is False


class TestProbeFile:
    @skip_no_ffprobe
    def test_probe_valid_file(self, sample_image, tmp_output):
        """Generate a tiny video then probe it."""
        from benxautomation.config import ShortsConfig
        from benxautomation.renderer.shorts_plugin import ShortsRendererPlugin

        out = tmp_output / "probe_test.mp4"
        plugin = ShortsRendererPlugin(ShortsConfig(duration_seconds=1))
        plugin.render(sample_image, out, duration_seconds=1)

        info = probe_file(out)
        assert "streams" in info
        assert len(info["streams"]) > 0

    def test_probe_graceful_when_no_ffprobe(self, tmp_path):
        info = probe_file(tmp_path / "fake.mp4", ffprobe_path="/no/such/ffprobe")
        assert info == {}
