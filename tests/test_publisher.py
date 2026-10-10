"""Tests for YouTube publisher safety guards."""

from pathlib import Path
import pytest

from benxautomation.config import PublishingConfig
from benxautomation.errors import PublishingDisabledError
from benxautomation.publisher.youtube import YouTubePublisher


class TestYouTubePublisher:
    def test_disabled_by_default_raises(self, tmp_path: Path):
        cfg = PublishingConfig(enabled=False)
        pub = YouTubePublisher(cfg)
        test_file = tmp_path / "vid.mp4"
        test_file.write_bytes(b"dummy")

        with pytest.raises(PublishingDisabledError, match="disabled in config"):
            pub.upload(test_file)

    def test_enabled_without_oauth_still_raises(self, tmp_path: Path):
        cfg = PublishingConfig(enabled=True)
        pub = YouTubePublisher(cfg)
        test_file = tmp_path / "vid.mp4"
        test_file.write_bytes(b"dummy")

        with pytest.raises(PublishingDisabledError, match="OAuth is not yet implemented"):
            pub.upload(test_file)
