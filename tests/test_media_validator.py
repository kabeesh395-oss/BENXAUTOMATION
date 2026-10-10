"""Tests for MediaValidator."""

from pathlib import Path
import pytest

from benxautomation.renderer.media_validator import MediaValidationError, MediaValidator
from tests.conftest import skip_no_ffmpeg


class TestMediaValidator:
    def test_missing_file_raises(self, tmp_path: Path):
        validator = MediaValidator()
        with pytest.raises(MediaValidationError, match="does not exist"):
            validator.inspect(tmp_path / "not_found.mp4")

    def test_empty_file_raises(self, tmp_path: Path):
        validator = MediaValidator()
        empty = tmp_path / "empty.mp4"
        empty.write_bytes(b"")
        with pytest.raises(MediaValidationError, match="zero bytes"):
            validator.inspect(empty)

    @skip_no_ffmpeg
    def test_inspect_real_video(self, sample_image: Path, tmp_output: Path):
        from benxautomation.config import ShortsConfig
        from benxautomation.renderer.shorts_plugin import ShortsRendererPlugin

        out_path = tmp_output / "val_test.mp4"
        plugin = ShortsRendererPlugin(ShortsConfig(duration_seconds=2))
        plugin.render(sample_image, out_path, duration_seconds=2)

        validator = MediaValidator()
        meta = validator.inspect(out_path)

        assert meta.has_video is True
        assert meta.width == 1080
        assert meta.height == 1920
        assert meta.duration_seconds >= 1.5
        assert meta.is_playable is True

    @skip_no_ffmpeg
    def test_validate_constraints(self, sample_image: Path, tmp_output: Path):
        from benxautomation.config import ShortsConfig
        from benxautomation.renderer.shorts_plugin import ShortsRendererPlugin

        out_path = tmp_output / "constraint_test.mp4"
        plugin = ShortsRendererPlugin(ShortsConfig(duration_seconds=2))
        plugin.render(sample_image, out_path, duration_seconds=2)

        validator = MediaValidator()
        # Should pass
        validator.validate(out_path, expected_width=1080, expected_height=1920)

        # Should fail width check
        with pytest.raises(MediaValidationError, match="width mismatch"):
            validator.validate(out_path, expected_width=1920)
