"""Tests for upload ledger, duplicate-upload prevention, safe retry, and crash recovery."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from benxautomation.config import PublishingConfig
from benxautomation.errors import DuplicateUploadError, PublishingDisabledError
from benxautomation.publisher.ledger import UploadLedger, UploadRecord
from benxautomation.publisher.youtube import (
    ChannelInfo,
    YouTubeOAuthManager,
    YouTubePublisher,
)


@pytest.fixture
def temp_ledger(tmp_path: Path) -> UploadLedger:
    """Isolated SQLite upload ledger for testing."""
    db_file = tmp_path / "test_ledger.sqlite"
    return UploadLedger(db_file)


@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    """Create a non-empty sample MP4 video file."""
    vid = tmp_path / "test_video.mp4"
    vid.write_bytes(b"TEST_VIDEO_PAYLOAD_BYTES_BENX_AUTOMATION_1234567890")
    return vid


class TestUploadLedgerDirectOperations:
    def test_compute_file_hash(self, sample_video: Path, temp_ledger: UploadLedger):
        h1 = temp_ledger.compute_file_hash(sample_video)
        assert len(h1) == 64
        assert isinstance(h1, str)
        # Consistent hash
        h2 = temp_ledger.compute_file_hash(sample_video)
        assert h1 == h2

    def test_record_lifecycle_start_complete(self, sample_video: Path, temp_ledger: UploadLedger):
        h = temp_ledger.compute_file_hash(sample_video)
        rec = temp_ledger.record_start(
            content_hash=h,
            file_path=sample_video,
            file_size=sample_video.stat().st_size,
            title="Acceptance Test Video",
            privacy_status="private",
            session_uri="https://upload.youtube.com/resume/session_1",
            channel_id="UC_BENX_07",
        )
        assert rec.status == "IN_PROGRESS"
        assert rec.session_uri == "https://upload.youtube.com/resume/session_1"
        assert rec.video_id is None

        # Check active session lookup
        active = temp_ledger.get_active_session(h)
        assert active is not None
        assert active.id == rec.id

        # No completed upload yet
        assert temp_ledger.get_completed_upload(h) is None

        # Complete upload
        completed = temp_ledger.record_complete(rec.id, video_id="nmdEewLCffw", privacy_status="private")
        assert completed.status == "COMPLETED"
        assert completed.video_id == "nmdEewLCffw"

        # Now get_completed_upload finds it
        found = temp_ledger.get_completed_upload(h)
        assert found is not None
        assert found.video_id == "nmdEewLCffw"

        # Active session should no longer return it
        assert temp_ledger.get_active_session(h) is None

    def test_record_failure(self, sample_video: Path, temp_ledger: UploadLedger):
        h = temp_ledger.compute_file_hash(sample_video)
        rec = temp_ledger.record_start(
            content_hash=h,
            file_path=sample_video,
            file_size=100,
            title="Failing Video",
            privacy_status="private",
            session_uri="https://upload.youtube.com/session_fail",
        )
        temp_ledger.record_failure(rec.id, "Connection reset by peer")
        updated = temp_ledger.get_record_by_id(rec.id)
        assert updated is not None
        assert updated.status == "FAILED"
        assert updated.error_message == "Connection reset by peer"

    def test_record_completed_upload_direct(self, temp_ledger: UploadLedger):
        rec = temp_ledger.record_completed_upload(
            content_hash="manual_hash_123",
            video_id="nmdEewLCffw",
            title="Pre-verified video",
            privacy_status="private",
            channel_id="BENX_07",
        )
        assert rec.status == "COMPLETED"
        assert rec.video_id == "nmdEewLCffw"

        by_vid = temp_ledger.get_record_by_video_id("nmdEewLCffw")
        assert by_vid is not None
        assert by_vid.channel_id == "BENX_07"

    def test_persistence_across_instances(self, tmp_path: Path, sample_video: Path):
        db_path = tmp_path / "persistent.sqlite"
        ledger1 = UploadLedger(db_path)
        h = ledger1.compute_file_hash(sample_video)
        ledger1.record_completed_upload(
            content_hash=h,
            video_id="vid_persisted_999",
            title="Persisted Video",
        )

        # New instance pointing to same file
        ledger2 = UploadLedger(db_path)
        record = ledger2.get_completed_upload(h)
        assert record is not None
        assert record.video_id == "vid_persisted_999"


class TestDuplicateUploadPrevention:
    def test_duplicate_upload_prevented_returns_existing_record(
        self,
        sample_video: Path,
        temp_ledger: UploadLedger,
    ):
        h = temp_ledger.compute_file_hash(sample_video)
        temp_ledger.record_completed_upload(
            content_hash=h,
            video_id="nmdEewLCffw",
            title="BENX_07 Acceptance Test",
            privacy_status="private",
            channel_id="BENX_07",
        )

        cfg = PublishingConfig(enabled=True, enforce_private=True)
        mock_mgr = MagicMock(spec=YouTubeOAuthManager)
        pub = YouTubePublisher(cfg, oauth_manager=mock_mgr, ledger=temp_ledger)

        # Attempt to upload the exact same video file again
        res = pub.upload(sample_video, title="Second Attempt")
        assert res["already_uploaded"] is True
        assert res["id"] == "nmdEewLCffw"
        assert res["url"] == "https://youtu.be/nmdEewLCffw"

        # Verify no YouTube API requests were made
        mock_mgr.verify_channel.assert_not_called()
        mock_mgr.get_valid_access_token.assert_not_called()

    def test_duplicate_upload_raise_on_duplicate_flag(
        self,
        sample_video: Path,
        temp_ledger: UploadLedger,
    ):
        h = temp_ledger.compute_file_hash(sample_video)
        temp_ledger.record_completed_upload(
            content_hash=h,
            video_id="nmdEewLCffw",
            title="BENX_07 Acceptance Test",
        )

        cfg = PublishingConfig(enabled=True)
        mock_mgr = MagicMock(spec=YouTubeOAuthManager)
        pub = YouTubePublisher(cfg, oauth_manager=mock_mgr, ledger=temp_ledger)

        with pytest.raises(DuplicateUploadError, match="Duplicate upload prevented"):
            pub.upload(sample_video, title="Second Attempt", raise_on_duplicate=True)

    @patch("requests.post")
    @patch("requests.put")
    def test_allow_duplicate_flag_permits_reupload_when_explicit(
        self,
        mock_put,
        mock_post,
        sample_video: Path,
        temp_ledger: UploadLedger,
    ):
        h = temp_ledger.compute_file_hash(sample_video)
        temp_ledger.record_completed_upload(
            content_hash=h,
            video_id="existing_id",
            title="Initial Video",
        )

        cfg = PublishingConfig(enabled=True)
        mock_mgr = MagicMock(spec=YouTubeOAuthManager)
        mock_mgr.verify_channel.return_value = ChannelInfo("UC123", "Channel")
        mock_mgr.get_valid_access_token.return_value = "ya29.token"

        mock_post.return_value = MagicMock(
            status_code=200,
            headers={"Location": "https://upload.youtube.com/new_session"},
        )
        mock_put.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "new_video_id_222"},
        )

        pub = YouTubePublisher(cfg, oauth_manager=mock_mgr, ledger=temp_ledger)
        res = pub.upload(sample_video, title="Forced Duplicate", allow_duplicate=True)
        assert res["id"] == "new_video_id_222"
        mock_post.assert_called_once()


class TestEnforcePrivateOnlyPublishing:
    def test_public_upload_blocked_by_enforce_private_guard(
        self,
        sample_video: Path,
        temp_ledger: UploadLedger,
    ):
        cfg = PublishingConfig(enabled=True, enforce_private=True)
        mock_mgr = MagicMock(spec=YouTubeOAuthManager)
        pub = YouTubePublisher(cfg, oauth_manager=mock_mgr, ledger=temp_ledger)

        with pytest.raises(PublishingDisabledError, match="enforces private-only uploads"):
            pub.upload(sample_video, title="Test", privacy_status="public")

    def test_unlisted_upload_blocked_by_enforce_private_guard(
        self,
        sample_video: Path,
        temp_ledger: UploadLedger,
    ):
        cfg = PublishingConfig(enabled=True, enforce_private=True)
        mock_mgr = MagicMock(spec=YouTubeOAuthManager)
        pub = YouTubePublisher(cfg, oauth_manager=mock_mgr, ledger=temp_ledger)

        with pytest.raises(PublishingDisabledError, match="enforces private-only uploads"):
            pub.upload(sample_video, title="Test", privacy_status="unlisted")

    @patch("requests.post")
    @patch("requests.put")
    def test_private_upload_allowed_when_enforce_private_is_true(
        self,
        mock_put,
        mock_post,
        sample_video: Path,
        temp_ledger: UploadLedger,
    ):
        cfg = PublishingConfig(enabled=True, enforce_private=True)
        mock_mgr = MagicMock(spec=YouTubeOAuthManager)
        mock_mgr.verify_channel.return_value = ChannelInfo("UC123", "Channel")
        mock_mgr.get_valid_access_token.return_value = "ya29.token"

        mock_post.return_value = MagicMock(
            status_code=200,
            headers={"Location": "https://upload.youtube.com/session_private"},
        )
        mock_put.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "private_vid_id"},
        )

        pub = YouTubePublisher(cfg, oauth_manager=mock_mgr, ledger=temp_ledger)
        res = pub.upload(sample_video, title="Private Video", privacy_status="private")
        assert res["id"] == "private_vid_id"


class TestResumableUploadRecoveryAndSafeRetry:
    @patch("requests.put")
    def test_recovery_when_upload_already_finished_on_youtube(
        self,
        mock_put,
        sample_video: Path,
        temp_ledger: UploadLedger,
    ):
        """Simulate crash right after bytes finished transferring, before saving completion."""
        h = temp_ledger.compute_file_hash(sample_video)
        rec = temp_ledger.record_start(
            content_hash=h,
            file_path=sample_video,
            file_size=sample_video.stat().st_size,
            title="Interrupted Video",
            privacy_status="private",
            session_uri="https://upload.youtube.com/session_interrupted",
        )

        # Probing Google with Content-Range: bytes */size returns 200 (completed!)
        mock_put.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "nmdEewLCffw"},
        )

        cfg = PublishingConfig(enabled=True)
        mock_mgr = MagicMock(spec=YouTubeOAuthManager)
        mock_mgr.get_valid_access_token.return_value = "ya29.token"
        pub = YouTubePublisher(cfg, oauth_manager=mock_mgr, ledger=temp_ledger)

        # Re-attempt upload: should probe, discover it finished, and NOT start a new session!
        res = pub.upload(sample_video, title="Interrupted Video")
        assert res["id"] == "nmdEewLCffw"
        assert res["resumed"] is True

        # Ledger must now be COMPLETED
        updated_rec = temp_ledger.get_record_by_id(rec.id)
        assert updated_rec.status == "COMPLETED"
        assert updated_rec.video_id == "nmdEewLCffw"

    @patch("requests.put")
    def test_recovery_resumes_from_partial_bytes_308(
        self,
        mock_put,
        sample_video: Path,
        temp_ledger: UploadLedger,
    ):
        """Simulate resuming after connection dropped at byte 20."""
        file_size = sample_video.stat().st_size
        h = temp_ledger.compute_file_hash(sample_video)
        rec = temp_ledger.record_start(
            content_hash=h,
            file_path=sample_video,
            file_size=file_size,
            title="Partial Video",
            privacy_status="private",
            session_uri="https://upload.youtube.com/resume/session_part",
        )

        # First PUT (probe) returns 308 Resume Incomplete with Range: bytes=0-19
        probe_resp = MagicMock(
            status_code=308,
            headers={"Range": "bytes=0-19"},
        )
        # Second PUT (streaming remaining bytes) returns 200 OK
        stream_resp = MagicMock(
            status_code=200,
            json=lambda: {"id": "recovered_vid_308"},
        )
        mock_put.side_effect = [probe_resp, stream_resp]

        cfg = PublishingConfig(enabled=True)
        mock_mgr = MagicMock(spec=YouTubeOAuthManager)
        mock_mgr.get_valid_access_token.return_value = "ya29.token"
        pub = YouTubePublisher(cfg, oauth_manager=mock_mgr, ledger=temp_ledger)

        res = pub.upload(sample_video, title="Partial Video")
        assert res["id"] == "recovered_vid_308"
        assert res["resumed"] is True

        # Check that second PUT sent Content-Range starting from byte 20
        assert mock_put.call_count == 2
        second_call_headers = mock_put.call_args_list[1][1]["headers"]
        assert second_call_headers["Content-Range"] == f"bytes 20-{file_size - 1}/{file_size}"

        # Ledger is updated to COMPLETED
        updated_rec = temp_ledger.get_record_by_id(rec.id)
        assert updated_rec.status == "COMPLETED"
        assert updated_rec.video_id == "recovered_vid_308"

    @patch("requests.post")
    @patch("requests.put")
    def test_recovery_when_session_expired_starts_fresh_session(
        self,
        mock_put,
        mock_post,
        sample_video: Path,
        temp_ledger: UploadLedger,
    ):
        """Simulate probe returning 404/expired -> safely starts fresh session."""
        h = temp_ledger.compute_file_hash(sample_video)
        rec = temp_ledger.record_start(
            content_hash=h,
            file_path=sample_video,
            file_size=sample_video.stat().st_size,
            title="Expired Video",
            privacy_status="private",
            session_uri="https://upload.youtube.com/expired_session",
        )

        # Probe returns 404
        probe_resp = MagicMock(
            status_code=404,
            text="Session not found",
        )
        # New upload session stream returns 200
        new_stream_resp = MagicMock(
            status_code=200,
            json=lambda: {"id": "fresh_video_id"},
        )
        mock_put.side_effect = [probe_resp, new_stream_resp]

        mock_post.return_value = MagicMock(
            status_code=200,
            headers={"Location": "https://upload.youtube.com/fresh_session_location"},
        )

        cfg = PublishingConfig(enabled=True)
        mock_mgr = MagicMock(spec=YouTubeOAuthManager)
        mock_mgr.verify_channel.return_value = ChannelInfo("UC123", "Channel")
        mock_mgr.get_valid_access_token.return_value = "ya29.token"
        pub = YouTubePublisher(cfg, oauth_manager=mock_mgr, ledger=temp_ledger)

        res = pub.upload(sample_video, title="Expired Video")
        assert res["id"] == "fresh_video_id"
        assert res["resumed"] is False

        # Old record marked FAILED
        old_rec = temp_ledger.get_record_by_id(rec.id)
        assert old_rec.status == "FAILED"

        # New record marked COMPLETED
        completed = temp_ledger.get_completed_upload(h)
        assert completed is not None
        assert completed.video_id == "fresh_video_id"

    @patch("requests.post")
    @patch("requests.put")
    def test_network_failure_during_transfer_records_failure_in_ledger(
        self,
        mock_put,
        mock_post,
        sample_video: Path,
        temp_ledger: UploadLedger,
    ):
        mock_post.return_value = MagicMock(
            status_code=200,
            headers={"Location": "https://upload.youtube.com/session_dropping"},
        )
        mock_put.side_effect = ConnectionResetError("Connection dropped by remote server")

        cfg = PublishingConfig(enabled=True)
        mock_mgr = MagicMock(spec=YouTubeOAuthManager)
        mock_mgr.verify_channel.return_value = ChannelInfo("UC123", "Channel")
        mock_mgr.get_valid_access_token.return_value = "ya29.token"
        pub = YouTubePublisher(cfg, oauth_manager=mock_mgr, ledger=temp_ledger)

        with pytest.raises(PublishingDisabledError, match="stream interrupted"):
            pub.upload(sample_video, title="Dropping Video")

        records = temp_ledger.list_records()
        assert len(records) == 1
        assert records[0].status == "FAILED"
        assert "Connection dropped" in records[0].error_message
