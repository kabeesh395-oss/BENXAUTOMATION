"""Tests for official YouTube OAuth publisher and safety guards."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from benxautomation.config import PublishingConfig
from benxautomation.errors import PublishingDisabledError
from benxautomation.publisher.youtube import (
    ChannelInfo,
    YouTubeOAuthManager,
    YouTubePublisher,
)


class TestYouTubeOAuthManager:
    def test_missing_client_secret_file_raises(self, tmp_path: Path):
        mgr = YouTubeOAuthManager(tmp_path / "nope.json")
        with pytest.raises(PublishingDisabledError, match="not found"):
            mgr.load_client_credentials()

    def test_load_client_credentials(self, tmp_path: Path):
        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text(
            json.dumps({"installed": {"client_id": "test_id", "client_secret": "test_sec"}}),
            encoding="utf-8",
        )
        mgr = YouTubeOAuthManager(secret_file)
        cid, csec = mgr.load_client_credentials()
        assert cid == "test_id"
        assert csec == "test_sec"

    def test_get_authorization_url(self, tmp_path: Path):
        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text(
            json.dumps({"installed": {"client_id": "my_client_id", "client_secret": "my_sec"}}),
            encoding="utf-8",
        )
        mgr = YouTubeOAuthManager(secret_file)
        url = mgr.get_authorization_url()
        assert "https://accounts.google.com/o/oauth2/v2/auth" in url
        assert "client_id=my_client_id" in url
        assert "youtube.upload" in url


class TestYouTubePublisherSafetyGuards:
    def test_upload_disabled_by_config(self, tmp_path: Path):
        cfg = PublishingConfig(enabled=False)
        pub = YouTubePublisher(cfg)
        test_vid = tmp_path / "vid.mp4"
        test_vid.write_bytes(b"data")

        with pytest.raises(PublishingDisabledError, match="disabled in configuration"):
            pub.upload(test_vid, title="Test")

    def test_upload_missing_oauth_manager_raises(self, tmp_path: Path):
        cfg = PublishingConfig(enabled=True)
        pub = YouTubePublisher(cfg)
        test_vid = tmp_path / "vid.mp4"
        test_vid.write_bytes(b"data")

        with pytest.raises(PublishingDisabledError, match="not configured"):
            pub.upload(test_vid, title="Test")

    def test_upload_invalid_visibility_raises(self, tmp_path: Path):
        cfg = PublishingConfig(enabled=True)
        mock_mgr = MagicMock(spec=YouTubeOAuthManager)
        mock_mgr.verify_channel.return_value = ChannelInfo("UC123", "TestChannel")
        pub = YouTubePublisher(cfg, oauth_manager=mock_mgr)
        test_vid = tmp_path / "vid.mp4"
        test_vid.write_bytes(b"data")

        with pytest.raises(PublishingDisabledError, match="Invalid privacy status"):
            pub.upload(test_vid, title="Test", privacy_status="invalid_mode")

    @patch("requests.post")
    @patch("requests.put")
    def test_successful_private_upload(self, mock_put, mock_post, tmp_path: Path):
        cfg = PublishingConfig(enabled=True)
        mock_mgr = MagicMock(spec=YouTubeOAuthManager)
        mock_mgr.verify_channel.return_value = ChannelInfo("UC123", "VerifiedChannel")
        mock_mgr.get_valid_access_token.return_value = "ya29.valid_token"

        mock_post.return_value = MagicMock(
            status_code=200,
            headers={"Location": "https://upload.youtube.com/resume/123"},
        )
        mock_put.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "yt_video_999", "status": {"privacyStatus": "private"}},
        )

        pub = YouTubePublisher(cfg, oauth_manager=mock_mgr)
        test_vid = tmp_path / "sample.mp4"
        test_vid.write_bytes(b"sample video bytes")

        res = pub.upload(test_vid, title="Private Test Video", privacy_status="private")
        assert res["id"] == "yt_video_999"
