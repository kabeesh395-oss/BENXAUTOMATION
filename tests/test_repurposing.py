"""Comprehensive test suite for Vizard AI-inspired long-form-to-Shorts repurposing."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from benxautomation.errors import PublishingDisabledError
from benxautomation.main import main
from benxautomation.podcast.errors import PodcastAccessError, RightsVerificationError
from benxautomation.podcast.models import (
    HighlightCandidate,
    PodcastInput,
    PodcastTranscript,
    RightsDeclaration,
    TranscriptSegment,
)
from benxautomation.renderer.ffmpeg_utils import find_ffmpeg, probe_file, run_ffmpeg
from benxautomation.repurpose.cli import main as repurpose_cli_main
from benxautomation.repurpose.config import RepurposingConfig
from benxautomation.repurpose.engine import RepurposingEngine
from benxautomation.repurpose.manifest import RepurposeClipEntry, RepurposeManifest
from benxautomation.repurpose.quality_reporter import ClipQualityCheck, RepurposeQualityReporter


@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    """Generate a clean, lightweight 1920x1080 30fps MP4 video with real audio and subtitles."""
    video_path = tmp_path / "interview_source.mp4"
    srt_path = tmp_path / "interview_source.srt"

    # Create accompanying subtitles
    srt_content = """1
00:00:01,000 --> 00:00:05,000
Why do most software developers struggle with distributed systems?

2
00:00:05,500 --> 00:00:10,000
The secret truth is that network boundaries change failure semantics.

3
00:00:10,500 --> 00:00:15,000
Remember to always design for idempotency and graceful degradation.

4
00:00:15,500 --> 00:00:20,000
That is the single most important lesson from twenty years of engineering.
"""
    srt_path.write_text(srt_content, encoding="utf-8")

    # Generate real 20-second 1920x1080 test MP4 with synthesized test tone audio (low volume)
    ffmpeg_exe = find_ffmpeg()
    cmd = [
        "-f", "lavfi", "-i", "color=c=0x111827:s=1920x1080:r=30:d=20",
        "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=44100:duration=20",
        "-af", "volume=0.05",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-y", str(video_path),
    ]
    run_ffmpeg(cmd, ffmpeg_path=ffmpeg_exe)
    assert video_path.is_file()
    assert video_path.stat().st_size > 0
    return video_path


def test_repurpose_config_defaults():
    """Verify default repurposing configuration parameters."""
    cfg = RepurposingConfig()
    assert cfg.vertical_width == 1080
    assert cfg.vertical_height == 1920
    assert cfg.fps == 30
    assert cfg.min_clip_duration == 15.0
    assert cfg.max_clip_duration == 60.0
    assert cfg.max_clips == 3
    assert cfg.reframing_mode == "blur_pad"
    assert cfg.enforce_private is True
    assert cfg.burn_subtitles is True


def test_manifest_lifecycle_and_deterministic_job_id(tmp_path: Path):
    """Test manifest creation, serialization, deserialization, and deterministic IDs."""
    source_str = "https://example.com/videos/podcast_ep42"
    job_id_1 = RepurposeManifest.generate_job_id(source_str)
    assert "repurpose_" in job_id_1

    clips = [
        RepurposeClipEntry(
            clip_id="clip_1",
            start_seconds=1.0,
            end_seconds=16.0,
            duration=15.0,
            hook="Why do most software developers struggle?",
            summary="Discussion on distributed systems",
            score=90.0,
            approved=True,
        ),
        RepurposeClipEntry(
            clip_id="clip_2",
            start_seconds=16.0,
            end_seconds=32.0,
            duration=16.0,
            hook="The secret truth about network boundaries",
            summary="Network boundaries and failure modes",
            score=85.0,
            approved=True,
        ),
    ]

    manifest = RepurposeManifest(
        job_id="test_job_123",
        source=source_str,
        source_title="Podcast Episode 42",
        source_duration=120.0,
        language="en",
        clips=clips,
    )

    out_file = tmp_path / "manifest.json"
    manifest.save(out_file)
    assert out_file.is_file()

    loaded = RepurposeManifest.load(out_file)
    assert loaded.job_id == "test_job_123"
    assert loaded.source_title == "Podcast Episode 42"
    assert len(loaded.clips) == 2
    assert loaded.clips[0].hook == "Why do most software developers struggle?"


def test_manifest_reject_clip_and_adjust_timestamps():
    """Verify clip rejection and timestamp adjustments with boundary enforcement."""
    clips = [
        RepurposeClipEntry(
            clip_id="clip_1",
            start_seconds=5.0,
            end_seconds=25.0,
            duration=20.0,
            hook="Opening hook",
            summary="Summary 1",
            score=95.0,
            approved=True,
        )
    ]
    manifest = RepurposeManifest(
        job_id="job_test",
        source="local.mp4",
        source_title="Local Video",
        source_duration=100.0,
        clips=clips,
    )

    # Reject clip
    assert manifest.reject_clip("clip_1", reason="Uninteresting hook") is True
    assert manifest.clips[0].approved is False
    assert manifest.clips[0].status == "rejected"
    assert len(manifest.get_approved_clips()) == 0

    # Reset approval and adjust timestamps
    manifest.clips[0].approved = True
    manifest.clips[0].status = "pending"
    assert manifest.adjust_timestamps("clip_1", 10.0, 35.0) is True
    assert manifest.clips[0].start_seconds == 10.0
    assert manifest.clips[0].end_seconds == 35.0
    assert manifest.clips[0].duration == 25.0

    # Invalid timestamp boundary checks
    with pytest.raises(ValueError, match="start_seconds must be >= 0"):
        manifest.adjust_timestamps("clip_1", -5.0, 20.0)

    with pytest.raises(ValueError, match="greater than start_seconds"):
        manifest.adjust_timestamps("clip_1", 30.0, 20.0)

    with pytest.raises(ValueError, match="exceeds source video duration"):
        manifest.adjust_timestamps("clip_1", 10.0, 150.0)


def test_quality_reporter_empty_or_missing_file(tmp_path: Path):
    """Verify quality reporter flags missing and empty video files."""
    reporter = RepurposeQualityReporter()

    # Missing file
    missing_check = reporter.check_clip(tmp_path / "nonexistent.mp4", expected_duration=15.0)
    assert missing_check.file_exists is False
    assert missing_check.passed is False
    assert any("not found" in issue for issue in missing_check.issues)

    # Empty file
    empty_file = tmp_path / "empty.mp4"
    empty_file.write_bytes(b"")
    empty_check = reporter.check_clip(empty_file, expected_duration=15.0)
    assert empty_check.file_exists is True
    assert empty_check.file_size_bytes == 0
    assert empty_check.passed is False
    assert any("empty" in issue for issue in empty_check.issues)


def test_repurpose_engine_invalid_source_raises():
    """Verify that empty or invalid source inputs raise actionable errors."""
    engine = RepurposingEngine()

    with pytest.raises(PodcastAccessError, match="cannot be empty"):
        engine.ingest("")

    with pytest.raises(PodcastAccessError, match="not found"):
        engine.ingest("C:/this/path/does/not/exist_12345.mp4")


def test_repurpose_engine_draft_creation(sample_video: Path, tmp_path: Path):
    """Test draft manifest creation from a local video."""
    cfg = RepurposingConfig(
        output_dir=str(tmp_path / "output"),
        cache_dir=str(tmp_path / "cache"),
        min_clip_duration=5.0,
        max_clip_duration=18.0,
        max_clips=2,
    )
    engine = RepurposingEngine(cfg)

    manifest, manifest_path = engine.create_draft(str(sample_video), job_id="test_draft_job")
    assert manifest_path.is_file()
    assert manifest.job_id == "test_draft_job"
    assert manifest.status == "draft"
    assert len(manifest.clips) > 0
    assert manifest.clips[0].approved is True
    assert manifest.clips[0].status == "pending"


def test_repurpose_engine_dry_run(sample_video: Path, tmp_path: Path):
    """Test dry-run mode completes validation without generating video files."""
    cfg = RepurposingConfig(
        output_dir=str(tmp_path / "output"),
        cache_dir=str(tmp_path / "cache"),
        min_clip_duration=5.0,
        max_clip_duration=18.0,
        max_clips=2,
        dry_run=True,
    )
    engine = RepurposingEngine(cfg)

    manifest, report = engine.run(str(sample_video), job_id="dry_run_job", dry_run=True)
    assert manifest.status == "validated_dry_run"
    assert report["overall_status"] == "PASS"


def test_repurpose_engine_render_real_video(sample_video: Path, tmp_path: Path):
    """Integration test: Render actual 9:16 vertical Short from local test video."""
    cfg = RepurposingConfig(
        output_dir=str(tmp_path / "output"),
        cache_dir=str(tmp_path / "cache"),
        min_clip_duration=5.0,
        max_clip_duration=12.0,
        max_clips=1,
        reframing_mode="blur_pad",
    )
    engine = RepurposingEngine(cfg)

    manifest, report = engine.run(str(sample_video), job_id="real_render_job")
    assert manifest.status == "completed"
    assert len(manifest.clips) >= 1

    clip_entry = manifest.clips[0]
    assert clip_entry.status == "rendered"
    assert clip_entry.output_video is not None

    rendered_mp4 = Path(clip_entry.output_video)
    assert rendered_mp4.is_file()
    assert rendered_mp4.stat().st_size > 0

    # FFprobe stream inspection
    meta = probe_file(rendered_mp4)
    streams = meta.get("streams", [])
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    assert v_stream is not None, "Video stream must exist"
    assert int(v_stream.get("width", 0)) == 1080
    assert int(v_stream.get("height", 0)) == 1920
    assert a_stream is not None, "Audio stream must exist"

    # Quality report check
    assert report["overall_status"] == "PASS"
    assert report["passed_clips"] >= 1


def test_repurpose_apply_manifest_with_rejected_clip(sample_video: Path, tmp_path: Path):
    """Test editing a manifest to reject one clip and render only approved clips."""
    cfg = RepurposingConfig(
        output_dir=str(tmp_path / "output"),
        cache_dir=str(tmp_path / "cache"),
        min_clip_duration=5.0,
        max_clip_duration=10.0,
        max_clips=2,
    )
    engine = RepurposingEngine(cfg)

    # 1. Create draft
    manifest, manifest_path = engine.create_draft(str(sample_video), job_id="reject_test_job")
    assert len(manifest.clips) >= 1

    # 2. Add second candidate and reject first
    manifest.clips[0].approved = False
    manifest.clips[0].status = "rejected"

    if len(manifest.clips) == 1:
        manifest.clips.append(
            RepurposeClipEntry(
                clip_id="clip_2",
                start_seconds=10.0,
                end_seconds=18.0,
                duration=8.0,
                hook="Second hook for approved test",
                summary="Approved segment",
                score=88.0,
                approved=True,
                status="pending",
            )
        )
    manifest.save(manifest_path)

    # 3. Apply manifest
    reloaded_manifest = RepurposeManifest.load(manifest_path)
    res_manifest, report = engine.render_from_manifest(reloaded_manifest)

    # Verify first clip remained unrendered/rejected
    assert res_manifest.clips[0].status == "rejected"
    assert res_manifest.clips[0].output_video is None

    # Verify second clip rendered successfully
    assert res_manifest.clips[1].status == "rendered"
    assert Path(res_manifest.clips[1].output_video).is_file()


def test_repurpose_cli_routing_via_main(sample_video: Path, tmp_path: Path):
    """Test invoking repurposing workflow directly through benxautomation.main CLI."""
    out_dir = tmp_path / "cli_repurpose"
    rc = main([
        "--source", str(sample_video),
        "--clips", "1",
        "--min-clip-duration", "5.0",
        "--max-clip-duration", "10.0",
        "--output-dir", str(out_dir),
        "--dry-run",
    ])
    assert rc == 0


def test_repurpose_cli_direct_execution(sample_video: Path, tmp_path: Path):
    """Test executing benxautomation.repurpose.cli directly."""
    out_dir = tmp_path / "cli_direct_out"
    rc = repurpose_cli_main([
        "--source", str(sample_video),
        "--clips", "1",
        "--min-duration", "5.0",
        "--max-duration", "10.0",
        "--output-dir", str(out_dir),
        "--dry-run",
    ])
    assert rc == 0


def test_repurpose_cli_missing_args_returns_error():
    """Test repurposing CLI without source or manifest exits cleanly with code 1."""
    rc = repurpose_cli_main([])
    assert rc == 1


def test_repurpose_cli_apply_manifest_missing_file_returns_error(tmp_path: Path):
    """Test repurposing CLI with missing manifest exits with code 1."""
    rc = repurpose_cli_main(["--apply-manifest", str(tmp_path / "missing_manifest.json")])
    assert rc == 1


def test_10_clip_limits_on_long_source():
    """Verify up to 10 distinct non-overlapping candidate clips are generated on long source material."""
    from benxautomation.podcast.highlight_detector import HighlightDetector

    # Build 300s synthetic interview with distinct topics every 20s
    segments = []
    topics = [
        "Why did we launch the space telescope?",
        "How do distributed consensus algorithms achieve fault tolerance?",
        "What is the biggest secret to mastering software architecture?",
        "Never ignore the power of automated integration testing.",
        "The truth about scaling relational databases globally.",
        "Always remember to isolate side effects from core domain logic.",
        "The single most important leadership mistake in tech startups.",
        "Why is memory safety essential for modern system languages?",
        "The future of artificial intelligence in video production.",
        "How to balance rapid prototyping with rigorous engineering discipline.",
        "What happens when network partitions divide distributed clusters?",
        "The life lessons learned after twenty years building systems.",
    ]
    for i, top in enumerate(topics):
        start = i * 25.0
        segments.append(
            TranscriptSegment(
                index=i + 1,
                start_seconds=start,
                end_seconds=start + 20.0,
                text=top,
                speaker="Guest" if i % 2 == 0 else "Host",
            )
        )
    transcript = PodcastTranscript(segments=segments, language="en", source="synthetic")

    detector = HighlightDetector(min_clip_duration=10.0, max_clip_duration=25.0)
    candidates = detector.detect_highlights(transcript, max_candidates=10)

    # Must generate up to 10 clips
    assert len(candidates) == 10
    assert candidates[0].clip_id == "clip_1"
    assert candidates[-1].clip_id == "clip_10"

    # Verify no clips have substantial overlap
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            c1, c2 = candidates[i], candidates[j]
            overlap_start = max(c1.start_seconds, c2.start_seconds)
            overlap_end = min(c1.end_seconds, c2.end_seconds)
            overlap = max(0.0, overlap_end - overlap_start)
            assert overlap <= 0.25 * min(c1.duration, c2.duration)


def test_insufficient_source_material_generates_fewer_clips():
    """Verify short source material generates fewer clips gracefully without forcing overlapping duplicates."""
    from benxautomation.podcast.highlight_detector import HighlightDetector

    # Only 30s of dialogue total
    segments = [
        TranscriptSegment(index=1, start_seconds=0.0, end_seconds=15.0, text="Why is deep sea exploration so difficult?"),
        TranscriptSegment(index=2, start_seconds=15.0, end_seconds=30.0, text="Because atmospheric pressure increases dramatically."),
    ]
    transcript = PodcastTranscript(segments=segments, language="en", source="synthetic")

    detector = HighlightDetector(min_clip_duration=12.0, max_clip_duration=20.0)
    # Request 10 clips even though only ~2 can fit
    candidates = detector.detect_highlights(transcript, max_candidates=10)

    # Must produce <= 2 clips without error or duplicate overlapping clips
    assert 1 <= len(candidates) <= 2
    assert len(candidates) < 10


def test_duplicate_and_overlapping_candidate_deduplication():
    """Verify _filter_and_deduplicate strictly eliminates overlapping candidate windows."""
    from benxautomation.podcast.highlight_detector import HighlightDetector

    detector = HighlightDetector(min_clip_duration=10.0, max_clip_duration=30.0)
    segments = [
        TranscriptSegment(index=1, start_seconds=0.0, end_seconds=60.0, text="Full interview context"),
    ]
    transcript = PodcastTranscript(segments=segments, language="en", source="synthetic")

    overlapping_candidates = [
        HighlightCandidate(clip_id="c1", start_seconds=0.0, end_seconds=20.0, duration=20.0, hook="Hook 1", reason="", score=95.0, summary="", transcript_text=""),
        # c2 heavily overlaps with c1 (0.0 to 18.0)
        HighlightCandidate(clip_id="c2", start_seconds=2.0, end_seconds=20.0, duration=18.0, hook="Hook 2", reason="", score=80.0, summary="", transcript_text=""),
        # c3 is distinct (25.0 to 45.0)
        HighlightCandidate(clip_id="c3", start_seconds=25.0, end_seconds=45.0, duration=20.0, hook="Hook 3", reason="", score=90.0, summary="", transcript_text=""),
    ]

    deduped = detector._filter_and_deduplicate(overlapping_candidates, transcript, max_candidates=10)

    # c2 must be dropped because it heavily overlaps with the higher-scoring c1
    assert len(deduped) == 2
    hooks = [c.hook for c in deduped]
    assert "Hook 1" in hooks
    assert "Hook 3" in hooks
    assert "Hook 2" not in hooks


def test_source_rights_validation_enforces_confirmation_for_third_party(tmp_path: Path):
    """Verify third-party footage requires explicit source-rights confirmation."""
    sample_mp4 = tmp_path / "third_party.mp4"
    sample_mp4.write_bytes(b"dummy")

    # Ingest local file as permitted third party
    cfg = RepurposingConfig(
        ownership_type="permitted",
        rights_holder="Celebrity Interviewer",
        license_evidence="",
        confirm_rights=False,  # Unconfirmed!
        accept_disclaimer=False,
    )
    engine = RepurposingEngine(cfg)

    inp = PodcastInput(
        source_type="local_file",
        source_identifier=str(sample_mp4),
        title="Third Party Interview",
        duration_seconds=60.0,
        channel_or_author="Celebrity Channel",
    )

    with pytest.raises(RightsVerificationError, match="Explicit source-rights confirmation is required"):
        engine._resolve_rights_declaration(inp)

    # Now confirm rights and disclaimer, but omit required license evidence
    cfg.confirm_rights = True
    cfg.accept_disclaimer = True
    cfg.license_evidence = ""  # empty evidence!
    engine = RepurposingEngine(cfg)

    with pytest.raises(RightsVerificationError, match="reference to the written permission documentation"):
        engine._resolve_rights_declaration(inp)


def test_approval_gates_prevent_rendering_or_upload_of_rejected_clips(tmp_path: Path):
    """Verify rejected clips in manifest are never rendered or uploaded."""
    cfg = RepurposingConfig(output_dir=str(tmp_path / "repurpose_out"))
    engine = RepurposingEngine(cfg)

    clips = [
        RepurposeClipEntry(clip_id="clip_1", start_seconds=0.0, end_seconds=10.0, duration=10.0, hook="H1", summary="S1", score=90.0, approved=False, status="rejected"),
        RepurposeClipEntry(clip_id="clip_2", start_seconds=10.0, end_seconds=20.0, duration=10.0, hook="H2", summary="S2", score=85.0, approved=False, status="rejected"),
    ]
    manifest = RepurposeManifest(job_id="all_rejected_job", source="test.mp4", source_title="Test", source_duration=30.0, clips=clips)

    manifest, report = engine.render_from_manifest(manifest, dry_run=True)
    assert manifest.status == "completed"
    assert report["total_clips"] == 0
    assert report["passed_clips"] == 0


def test_private_upload_mode_without_oauth_preserves_artifacts_safely(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify upload_private=True safely preserves local artifacts when OAuth is unconfigured."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    job_dir = tmp_path / "job_test"
    job_dir.mkdir(parents=True, exist_ok=True)
    vid_p = job_dir / "clip_1.mp4"
    vid_p.write_bytes(b"dummy")

    clip = RepurposeClipEntry(clip_id="clip_1", start_seconds=0.0, end_seconds=8.0, duration=8.0, hook="H", summary="S", score=90.0, approved=True, status="rendered", output_video=str(vid_p))
    manifest = RepurposeManifest(job_id="job_test", source="local.mp4", source_title="Title", source_duration=20.0, clips=[clip])

    decl = RightsDeclaration(ownership_type="creator_owned", user_confirmed_rights=True, disclaimer_accepted=True)

    engine = RepurposingEngine(RepurposingConfig(upload_private=True))
    engine._handle_private_uploads(job_dir, manifest, [clip], decl)

    assert clip.youtube_upload_status == "OAUTH_UNCONFIGURED"
    assert vid_p.is_file()  # Local artifact strictly preserved!


def test_private_upload_mode_with_oauth_enforces_private_and_verifies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify upload_private=True invokes publisher with privacy_status='private' and validates verification."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    token_dir = tmp_path / ".benxautomation"
    token_dir.mkdir(parents=True, exist_ok=True)
    (token_dir / "client_secret.json").write_text('{"installed": {"client_id": "c", "client_secret": "s"}}', encoding="utf-8")

    job_dir = tmp_path / "job_test"
    job_dir.mkdir(parents=True, exist_ok=True)
    vid_p = job_dir / "clip_1.mp4"
    vid_p.write_bytes(b"dummy")

    clip = RepurposeClipEntry(clip_id="clip_1", start_seconds=0.0, end_seconds=8.0, duration=8.0, hook="Hook text", summary="Summary", score=90.0, approved=True, status="rendered", output_video=str(vid_p))
    manifest = RepurposeManifest(job_id="job_test", source="local.mp4", source_title="Title", source_duration=20.0, clips=[clip])
    decl = RightsDeclaration(ownership_type="creator_owned", user_confirmed_rights=True, disclaimer_accepted=True)

    with patch("benxautomation.publisher.youtube.YouTubeOAuthManager") as mock_oauth_cls:
        mock_oauth = MagicMock()
        mock_oauth_cls.return_value = mock_oauth

        with patch("benxautomation.publisher.youtube.YouTubePublisher") as mock_pub_cls:
            mock_pub = MagicMock()
            mock_pub_cls.return_value = mock_pub
            # Successful private upload
            mock_pub.upload.return_value = {"video_id": "test_vid_123", "url": "https://youtu.be/test_vid_123", "privacy_status": "private"}
            mock_pub.verify_video.return_value = {"privacy_status": "private"}

            engine = RepurposingEngine(RepurposingConfig(upload_private=True))
            engine._handle_private_uploads(job_dir, manifest, [clip], decl)

            assert clip.youtube_upload_status == "UPLOADED_PRIVATE"
            assert clip.youtube_video_id == "test_vid_123"
            mock_pub.upload.assert_called_once()
            assert mock_pub.upload.call_args[1]["privacy_status"] == "private"


def test_runtime_quality_check_failure_blocks_upload_and_saves_rejection_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify essential quality check failure prevents upload and saves rejection report."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    token_dir = tmp_path / ".benxautomation"
    token_dir.mkdir(parents=True, exist_ok=True)
    (token_dir / "client_secret.json").write_text('{"installed": {"client_id": "c", "client_secret": "s"}}', encoding="utf-8")

    job_dir = tmp_path / "job_test_fail"
    job_dir.mkdir(parents=True, exist_ok=True)
    bad_vid = job_dir / "bad_clip.mp4"
    bad_vid.write_bytes(b"")  # 0 bytes empty file: fails essential quality checks

    clip = RepurposeClipEntry(
        clip_id="bad_clip",
        start_seconds=0.0,
        end_seconds=10.0,
        duration=10.0,
        hook="Bad Clip",
        summary="Summary",
        score=80.0,
        approved=True,
        status="rendered",
        output_video=str(bad_vid),
    )
    manifest = RepurposeManifest(job_id="job_test_fail", source="local.mp4", source_title="Title", source_duration=20.0, clips=[clip])
    decl = RightsDeclaration(ownership_type="creator_owned", user_confirmed_rights=True, disclaimer_accepted=True)

    with patch("benxautomation.publisher.youtube.YouTubeOAuthManager") as mock_oauth_cls:
        mock_oauth_cls.return_value = MagicMock()
        with patch("benxautomation.publisher.youtube.YouTubePublisher") as mock_pub_cls:
            mock_pub = MagicMock()
            mock_pub_cls.return_value = mock_pub

            engine = RepurposingEngine(RepurposingConfig(upload_private=True))
            engine._handle_private_uploads(job_dir, manifest, [clip], decl)

            # Upload must NOT have been called due to failed quality check
            mock_pub.upload.assert_not_called()
            assert clip.youtube_upload_status == "QUALITY_CHECK_FAILED"

            # Rejection report must exist
            rej_file = job_dir / "bad_clip_upload_rejection.json"
            assert rej_file.is_file()
            data = json.loads(rej_file.read_text(encoding="utf-8"))
            assert data["status"] == "QUALITY_CHECK_FAILED"
            assert any("empty" in issue.lower() or "0 bytes" in issue.lower() or "zero" in issue.lower() for issue in data["issues"])

