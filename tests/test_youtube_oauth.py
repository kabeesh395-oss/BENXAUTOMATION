"""Tests for official YouTube OAuth publisher and safety guards."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from benxautomation.config import PublishingConfig
from benxautomation.errors import PublishingDisabledError
from benxautomation.publisher.youtube import (
    ChannelInfo,
    DEFAULT_YOUTUBE_SCOPES,
    YOUTUBE_READONLY_SCOPE,
    YOUTUBE_UPLOAD_SCOPE,
    YouTubeOAuthManager,
    YouTubePublisher,
    check_scopes_sufficient,
)


class TestYouTubeOAuthManager:
    def test_missing_client_secret_file_raises(self, tmp_path: Path):
        mgr = YouTubeOAuthManager(tmp_path / "nope.json")
        with pytest.raises(PublishingDisabledError, match="not found"):
            mgr.load_client_credentials()

    def test_invalid_json_client_secret_raises(self, tmp_path: Path):
        bad_file = tmp_path / "malformed.json"
        bad_file.write_text("NOT A VALID JSON {{{", encoding="utf-8")
        mgr = YouTubeOAuthManager(bad_file)
        with pytest.raises(PublishingDisabledError, match="invalid JSON"):
            mgr.load_client_credentials()

    def test_incorrect_oauth_client_format_web_raises(self, tmp_path: Path):
        web_file = tmp_path / "web_client.json"
        web_file.write_text(
            json.dumps({"web": {"client_id": "wid", "client_secret": "wsec"}}),
            encoding="utf-8",
        )
        mgr = YouTubeOAuthManager(web_file)
        with pytest.raises(PublishingDisabledError, match="Found 'web' client credentials"):
            mgr.load_client_credentials()

    def test_incorrect_oauth_client_format_missing_installed_raises(self, tmp_path: Path):
        unknown_file = tmp_path / "unknown.json"
        unknown_file.write_text(
            json.dumps({"something_else": {"foo": "bar"}}),
            encoding="utf-8",
        )
        mgr = YouTubeOAuthManager(unknown_file)
        with pytest.raises(PublishingDisabledError, match="Missing 'installed' key"):
            mgr.load_client_credentials()

    def test_missing_client_id_or_secret_raises(self, tmp_path: Path):
        incomplete_file = tmp_path / "incomplete.json"
        incomplete_file.write_text(
            json.dumps({"installed": {"client_id": "", "client_secret": "sec"}}),
            encoding="utf-8",
        )
        mgr = YouTubeOAuthManager(incomplete_file)
        with pytest.raises(PublishingDisabledError, match="'client_id' is missing"):
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

    def test_load_client_credentials_from_directory(self, tmp_path: Path):
        secret_dir = tmp_path / "secret_folder"
        secret_dir.mkdir()
        nested_file = secret_dir / "client_secret_12345.apps.googleusercontent.com.json"
        nested_file.write_text(
            json.dumps({"installed": {"client_id": "nested_id", "client_secret": "nested_sec"}}),
            encoding="utf-8",
        )
        mgr = YouTubeOAuthManager(secret_dir)
        cid, csec = mgr.load_client_credentials()
        assert cid == "nested_id"
        assert csec == "nested_sec"

    def test_multiple_candidate_files_in_directory_raises(self, tmp_path: Path):
        secret_dir = tmp_path / "multi_folder"
        secret_dir.mkdir()
        (secret_dir / "client_secret_1.json").write_text("{}", encoding="utf-8")
        (secret_dir / "client_secret_2.json").write_text("{}", encoding="utf-8")
        mgr = YouTubeOAuthManager(secret_dir)
        with pytest.raises(PublishingDisabledError, match="multiple candidate credential files"):
            mgr.load_client_credentials()

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
        assert "youtube.readonly" in url

    def test_get_authorization_url_custom_scopes(self, tmp_path: Path):
        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text(
            json.dumps({"installed": {"client_id": "my_client_id", "client_secret": "my_sec"}}),
            encoding="utf-8",
        )
        mgr = YouTubeOAuthManager(secret_file)
        custom_scopes = ["https://www.googleapis.com/auth/youtube.readonly"]
        url = mgr.get_authorization_url(scopes=custom_scopes)
        assert "youtube.readonly" in url
        assert "youtube.upload" not in url

    def test_check_scopes_sufficient_logic(self):
        # Exact scopes
        ok, missing = check_scopes_sufficient(
            {YOUTUBE_UPLOAD_SCOPE, YOUTUBE_READONLY_SCOPE},
            DEFAULT_YOUTUBE_SCOPES,
        )
        assert ok is True
        assert missing == []

        # Missing readonly
        ok, missing = check_scopes_sufficient(
            {YOUTUBE_UPLOAD_SCOPE},
            DEFAULT_YOUTUBE_SCOPES,
        )
        assert ok is False
        assert missing == [YOUTUBE_READONLY_SCOPE]

        # Missing upload
        ok, missing = check_scopes_sufficient(
            {YOUTUBE_READONLY_SCOPE},
            DEFAULT_YOUTUBE_SCOPES,
        )
        assert ok is False
        assert missing == [YOUTUBE_UPLOAD_SCOPE]

        # Full youtube scope satisfies all
        ok, missing = check_scopes_sufficient(
            {"https://www.googleapis.com/auth/youtube"},
            DEFAULT_YOUTUBE_SCOPES,
        )
        assert ok is True
        assert missing == []

        # Full force-ssl scope satisfies all
        ok, missing = check_scopes_sufficient(
            {"https://www.googleapis.com/auth/youtube.force-ssl"},
            DEFAULT_YOUTUBE_SCOPES,
        )
        assert ok is True
        assert missing == []

    def test_get_valid_access_token_with_sufficient_scopes(self, tmp_path: Path):
        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text(
            json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}),
            encoding="utf-8",
        )
        token_file = tmp_path / "youtube_tokens.json"
        token_file.write_text(
            json.dumps({
                "access_token": "ya29.good_token",
                "scope": f"{YOUTUBE_UPLOAD_SCOPE} {YOUTUBE_READONLY_SCOPE}",
            }),
            encoding="utf-8",
        )
        mgr = YouTubeOAuthManager(secret_file, token_path=token_file)
        token = mgr.get_valid_access_token()
        assert token == "ya29.good_token"
        assert token_file.exists()

    def test_get_valid_access_token_with_full_youtube_scope(self, tmp_path: Path):
        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text(
            json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}),
            encoding="utf-8",
        )
        token_file = tmp_path / "youtube_tokens.json"
        token_file.write_text(
            json.dumps({
                "access_token": "ya29.full_token",
                "scope": "https://www.googleapis.com/auth/youtube",
            }),
            encoding="utf-8",
        )
        mgr = YouTubeOAuthManager(secret_file, token_path=token_file)
        token = mgr.get_valid_access_token()
        assert token == "ya29.full_token"
        assert token_file.exists()

    def test_get_valid_access_token_insufficient_scope_backs_up_and_raises(self, tmp_path: Path):
        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text(
            json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}),
            encoding="utf-8",
        )
        token_file = tmp_path / "youtube_tokens.json"
        token_file.write_text(
            json.dumps({
                "access_token": "ya29.insufficient_token",
                "scope": YOUTUBE_UPLOAD_SCOPE,  # Missing readonly scope!
            }),
            encoding="utf-8",
        )
        mgr = YouTubeOAuthManager(secret_file, token_path=token_file)
        bak_file = tmp_path / "youtube_tokens.json.bak"

        with pytest.raises(PublishingDisabledError, match="insufficient scopes"):
            mgr.get_valid_access_token()

        # Token must have been invalidated (moved to .bak)
        assert not token_file.exists()
        assert bak_file.exists()
        bak_data = json.loads(bak_file.read_text(encoding="utf-8"))
        assert bak_data["access_token"] == "ya29.insufficient_token"

    @patch("requests.post")
    def test_refresh_token_insufficient_scope_backs_up_and_raises(self, mock_post, tmp_path: Path):
        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text(
            json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}),
            encoding="utf-8",
        )
        token_file = tmp_path / "youtube_tokens.json"
        token_file.write_text(
            json.dumps({
                "access_token": "ya29.old",
                "refresh_token": "1//refresh_token_abc",
            }),
            encoding="utf-8",
        )
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "access_token": "ya29.new",
                "scope": YOUTUBE_UPLOAD_SCOPE,  # Missing readonly scope
            },
        )
        mgr = YouTubeOAuthManager(secret_file, token_path=token_file)
        bak_file = tmp_path / "youtube_tokens.json.bak"

        with pytest.raises(PublishingDisabledError, match="insufficient scopes"):
            mgr.get_valid_access_token()

        assert not token_file.exists()
        assert bak_file.exists()

    @patch("requests.get")
    def test_verify_channel_success(self, mock_get, tmp_path: Path):
        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text(
            json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}),
            encoding="utf-8",
        )
        token_file = tmp_path / "youtube_tokens.json"
        token_file.write_text(
            json.dumps({
                "access_token": "ya29.valid",
                "scope": f"{YOUTUBE_UPLOAD_SCOPE} {YOUTUBE_READONLY_SCOPE}",
            }),
            encoding="utf-8",
        )
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [{
                    "id": "UC_TEST_123",
                    "snippet": {
                        "title": "My Automation Channel",
                        "customUrl": "@myautochannel",
                    },
                }]
            },
        )
        mgr = YouTubeOAuthManager(secret_file, token_path=token_file)
        info = mgr.verify_channel()
        assert info.channel_id == "UC_TEST_123"
        assert info.title == "My Automation Channel"
        assert info.custom_url == "@myautochannel"

    @patch("requests.get")
    def test_verify_channel_api_403_insufficient_scope_backs_up_and_raises(self, mock_get, tmp_path: Path):
        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text(
            json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}),
            encoding="utf-8",
        )
        token_file = tmp_path / "youtube_tokens.json"
        token_file.write_text(
            json.dumps({"access_token": "ya29.valid"}),
            encoding="utf-8",
        )
        mock_get.return_value = MagicMock(
            status_code=403,
            text='{"error": {"code": 403, "message": "Request had insufficient authentication scopes.", "status": "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}}',
        )
        mgr = YouTubeOAuthManager(secret_file, token_path=token_file)
        bak_file = tmp_path / "youtube_tokens.json.bak"

        with pytest.raises(PublishingDisabledError, match="ACCESS_TOKEN_SCOPE_INSUFFICIENT"):
            mgr.verify_channel()

        assert not token_file.exists()
        assert bak_file.exists()



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

    @patch("requests.get")
    def test_verify_video_success(self, mock_get):
        cfg = PublishingConfig(enabled=True)
        mock_mgr = MagicMock(spec=YouTubeOAuthManager)
        mock_mgr.get_valid_access_token.return_value = "ya29.valid"
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [{
                    "id": "abc123xyz",
                    "snippet": {"title": "Acceptance Test Video"},
                    "status": {"privacyStatus": "private", "uploadStatus": "uploaded"},
                }]
            },
        )
        pub = YouTubePublisher(cfg, oauth_manager=mock_mgr)
        info = pub.verify_video("abc123xyz")
        assert info["video_id"] == "abc123xyz"
        assert info["privacy_status"] == "private"
        assert info["url"] == "https://youtu.be/abc123xyz"

    @patch("requests.post")
    @patch("requests.put")
    @patch("requests.get")
    def test_upload_private_acceptance_test(self, mock_get, mock_put, mock_post, tmp_path: Path):
        cfg = PublishingConfig(enabled=True)
        mock_mgr = MagicMock(spec=YouTubeOAuthManager)
        mock_mgr.verify_channel.return_value = ChannelInfo("UC123", "VerifiedChannel")
        mock_mgr.get_valid_access_token.return_value = "ya29.valid"

        mock_post.return_value = MagicMock(
            status_code=200,
            headers={"Location": "https://upload.youtube.com/resume/456"},
        )
        mock_put.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "private_test_id"},
        )
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [{
                    "id": "private_test_id",
                    "snippet": {"title": "BENX Acceptance Test"},
                    "status": {"privacyStatus": "private", "uploadStatus": "uploaded"},
                }]
            },
        )

        pub = YouTubePublisher(cfg, oauth_manager=mock_mgr)
        test_vid = tmp_path / "private_test.mp4"
        test_vid.write_bytes(b"data")

        res = pub.upload_private_acceptance_test(test_vid, title="BENX Acceptance Test")
        assert res["video_id"] == "private_test_id"
        assert res["privacy_status"] == "private"
        assert res["url"] == "https://youtu.be/private_test_id"

    @patch("requests.post")
    def test_upload_initiation_403_scope_insufficient_triggers_backup_and_raises(self, mock_post, tmp_path: Path):
        cfg = PublishingConfig(enabled=True)
        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text(
            json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}),
            encoding="utf-8",
        )
        token_file = tmp_path / "youtube_tokens.json"
        token_file.write_text(
            json.dumps({"access_token": "ya29.valid"}),
            encoding="utf-8",
        )
        mgr = YouTubeOAuthManager(secret_file, token_path=token_file)
        mgr.verify_channel = MagicMock(return_value=ChannelInfo("UC123", "TestChannel"))

        mock_post.return_value = MagicMock(
            status_code=403,
            text='{"error": {"status": "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}}',
        )
        pub = YouTubePublisher(cfg, oauth_manager=mgr)
        test_vid = tmp_path / "vid.mp4"
        test_vid.write_bytes(b"sample bytes")

        with pytest.raises(PublishingDisabledError, match="ACCESS_TOKEN_SCOPE_INSUFFICIENT"):
            pub.upload(test_vid, title="Upload Test")

        assert not token_file.exists()
        assert (tmp_path / "youtube_tokens.json.bak").exists()

    @patch("requests.get")
    def test_verify_video_403_scope_insufficient_triggers_backup_and_raises(self, mock_get, tmp_path: Path):
        cfg = PublishingConfig(enabled=True)
        secret_file = tmp_path / "client_secret.json"
        secret_file.write_text(
            json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}),
            encoding="utf-8",
        )
        token_file = tmp_path / "youtube_tokens.json"
        token_file.write_text(
            json.dumps({"access_token": "ya29.valid"}),
            encoding="utf-8",
        )
        mgr = YouTubeOAuthManager(secret_file, token_path=token_file)

        mock_get.return_value = MagicMock(
            status_code=403,
            text='{"error": {"status": "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}}',
        )
        pub = YouTubePublisher(cfg, oauth_manager=mgr)

        with pytest.raises(PublishingDisabledError, match="ACCESS_TOKEN_SCOPE_INSUFFICIENT"):
            pub.verify_video("vid123")

        assert not token_file.exists()
        assert (tmp_path / "youtube_tokens.json.bak").exists()


