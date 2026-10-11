"""Unit tests for the Podcast & Livestream-to-Shorts Automation System."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from benxautomation.podcast.errors import (
    PodcastAccessError,
    PodcastRenderingError,
    RightsVerificationError,
)
from benxautomation.podcast.highlight_detector import HighlightDetector
from benxautomation.podcast.ingestion import PodcastIngester
from benxautomation.podcast.metadata import ClipMetadataGenerator
from benxautomation.podcast.models import (
    HighlightCandidate,
    PodcastInput,
    PodcastPipelineConfig,
    PodcastTranscript,
    RightsDeclaration,
    SubtitleStyle,
    TranscriptSegment,
)
from benxautomation.podcast.pipeline import PodcastToShortsPipeline
from benxautomation.podcast.reframer import VideoReframer
from benxautomation.podcast.rights_review import RightsReviewer
from benxautomation.podcast.subtitles import (
    PodcastSubtitleManager,
    _seconds_to_ass_time,
    _seconds_to_srt_time,
    _seconds_to_vtt_time,
)
from benxautomation.podcast.transcription import (
    PodcastTranscriber,
    _clean_subtitle_text,
    _timestamp_to_seconds,
)


def test_timestamp_conversions():
    """Verify millisecond-accurate timestamp conversion between formats."""
    # VTT / SRT format to seconds
    assert _timestamp_to_seconds("00:01:23.450") == 83.45
    assert _timestamp_to_seconds("01:23,450") == 83.45
    assert _timestamp_to_seconds("00:00:05.100") == 5.1

    # Seconds to SRT / VTT / ASS
    assert _seconds_to_srt_time(83.45) == "00:01:23,450"
    assert _seconds_to_vtt_time(83.45) == "00:01:23.450"
    assert _seconds_to_ass_time(83.45) == "0:01:23.45"


def test_subtitle_text_cleaning():
    """Verify that WebVTT/HTML formatting tags are stripped."""
    raw = "<c.yellow><font color='#fff'>Hello <b>World</b></font></c>&nbsp;&amp; welcome!"
    cleaned = _clean_subtitle_text(raw)
    assert cleaned == "Hello World & welcome!"


def test_vtt_parsing(tmp_path: Path):
    """Test parsing WebVTT files with rolling duplicate suppression."""
    vtt_content = """WEBVTT
Kind: captions
Language: en

00:00:01.000 --> 00:00:04.500
<c>Welcome to the podcast.</c>

00:00:04.500 --> 00:00:05.000
Welcome to the podcast.

00:00:05.000 --> 00:00:09.200
Today we reveal the secret truth about AI.
"""
    vtt_file = tmp_path / "sample.vtt"
    vtt_file.write_text(vtt_content, encoding="utf-8")

    transcriber = PodcastTranscriber()
    segments = transcriber.parse_vtt(vtt_file)

    assert len(segments) == 2  # Middle duplicate line suppressed
    assert segments[0].start_seconds == 1.0
    assert segments[0].end_seconds == 4.5
    assert segments[0].text == "Welcome to the podcast."
    assert segments[1].start_seconds == 5.0
    assert segments[1].end_seconds == 9.2
    assert "Today we reveal the secret truth about AI." in segments[1].text


def test_srt_parsing(tmp_path: Path):
    """Test parsing standard SubRip (.srt) subtitle files."""
    srt_content = """1
00:00:02,000 --> 00:00:06,500
Why do most creators fail early?

2
00:00:06,800 --> 00:00:11,200
Because they give up before consistency pays off.
"""
    srt_file = tmp_path / "sample.srt"
    srt_file.write_text(srt_content, encoding="utf-8")

    transcriber = PodcastTranscriber()
    segments = transcriber.parse_srt(srt_file)

    assert len(segments) == 2
    assert segments[0].start_seconds == 2.0
    assert segments[0].end_seconds == 6.5
    assert segments[0].text == "Why do most creators fail early?"


def test_subtitle_export_per_clip(tmp_path: Path):
    """Verify that export_srt and export_vtt time-shift cues relative to clip start."""
    segments = [
        TranscriptSegment(index=1, start_seconds=10.0, end_seconds=14.0, text="First insight"),
        TranscriptSegment(index=2, start_seconds=14.0, end_seconds=22.0, text="Second insight"),
        TranscriptSegment(index=3, start_seconds=22.0, end_seconds=30.0, text="Third insight"),
    ]
    transcript = PodcastTranscript(segments=segments)
    candidate = HighlightCandidate(
        clip_id="clip_test",
        start_seconds=12.0,
        end_seconds=25.0,
        duration=13.0,
        hook="Insight hook",
        reason="Good moment",
        score=90.0,
        summary="Summary",
        transcript_text="Test",
    )

    manager = PodcastSubtitleManager()
    srt_file = tmp_path / "test.srt"
    vtt_file = tmp_path / "test.vtt"
    ass_file = tmp_path / "test.ass"

    manager.export_srt(candidate, transcript, srt_file)
    manager.export_vtt(candidate, transcript, vtt_file)
    manager.export_ass(candidate, transcript, ass_file, SubtitleStyle())

    assert srt_file.is_file()
    assert vtt_file.is_file()
    assert ass_file.is_file()

    srt_text = srt_file.read_text(encoding="utf-8")
    assert "00:00:00,000 -->" in srt_text  # Shifted relative to 12.0s
    assert "First insight" in srt_text
    assert "Second insight" in srt_text


def test_rights_review_validation():
    """Verify that rights declarations strictly prevent unlicensed and unconfirmed uploads."""
    reviewer = RightsReviewer()

    # 1. Reject missing user confirmation
    decl_unconfirmed = RightsDeclaration(
        user_confirmed_rights=False,
        disclaimer_accepted=True,
    )
    valid, errors = reviewer.validate_declaration(decl_unconfirmed)
    assert not valid
    assert any("explicitly confirm" in e for e in errors)

    # 2. Reject unaccepted disclaimer
    decl_no_disclaimer = RightsDeclaration(
        user_confirmed_rights=True,
        disclaimer_accepted=False,
    )
    valid, errors = reviewer.validate_declaration(decl_no_disclaimer)
    assert not valid
    assert any("acknowledge and accept" in e for e in errors)

    # 3. Reject unlicensed music
    decl_unlicensed_music = RightsDeclaration(
        ownership_type="creator_owned",
        music_source="unlicensed",
        user_confirmed_rights=True,
        disclaimer_accepted=True,
    )
    valid, errors = reviewer.validate_declaration(decl_unlicensed_music)
    assert not valid
    assert any("Unlicensed background music" in e for e in errors)

    # 4. Reject missing evidence for licensed footage
    decl_missing_evidence = RightsDeclaration(
        ownership_type="licensed",
        license_evidence="",
        user_confirmed_rights=True,
        disclaimer_accepted=True,
    )
    valid, errors = reviewer.validate_declaration(decl_missing_evidence)
    assert not valid
    assert any("requires verifiable license evidence" in e for e in errors)

    # 5. Pass valid creator declaration
    decl_valid = RightsDeclaration(
        ownership_type="creator_owned",
        rights_holder="Self-Produced",
        music_source="royalty_free",
        user_confirmed_rights=True,
        disclaimer_accepted=True,
    )
    valid, errors = reviewer.validate_declaration(decl_valid)
    assert valid
    assert len(errors) == 0


def test_highlight_detector_heuristics():
    """Verify heuristic highlight discovery respects clip duration bounds and non-overlap."""
    segments = [
        TranscriptSegment(index=1, start_seconds=0.0, end_seconds=5.0, text="Why does this matter?"),
        TranscriptSegment(index=2, start_seconds=5.0, end_seconds=12.0, text="Because consistency is the secret to everything."),
        TranscriptSegment(index=3, start_seconds=12.0, end_seconds=20.0, text="Most people never realize this truth."),
        TranscriptSegment(index=4, start_seconds=20.0, end_seconds=26.0, text="They stop when it gets tough."),
        TranscriptSegment(index=5, start_seconds=26.0, end_seconds=34.0, text="Now let us look at the next part."),
        TranscriptSegment(index=6, start_seconds=34.0, end_seconds=45.0, text="Here is a completely different story."),
    ]
    transcript = PodcastTranscript(segments=segments)

    detector = HighlightDetector(min_clip_duration=15.0, max_clip_duration=30.0)
    candidates = detector.detect_highlights(transcript, max_candidates=3)

    assert len(candidates) >= 1
    for c in candidates:
        assert 15.0 <= c.duration <= 30.0
        assert len(c.hook) > 0


def test_clip_metadata_generation(tmp_path: Path):
    """Verify rich per-clip metadata generation with full attribution."""
    candidate = HighlightCandidate(
        clip_id="clip_01",
        start_seconds=10.0,
        end_seconds=35.0,
        duration=25.0,
        hook="Why do 90% of beginners quit?",
        reason="Captivating retention hook",
        score=94.0,
        summary="A discussion on resilience and creative longevity.",
        transcript_text="Why do 90% of beginners quit? Because they lack patience.",
    )
    inp = PodcastInput(
        source_type="url",
        source_identifier="https://www.youtube.com/watch?v=sample123",
        title="The Creator Podcast Ep. 42",
        duration_seconds=1800.0,
        channel_or_author="Creator Studio",
    )
    rights = RightsDeclaration(
        ownership_type="creator_owned",
        rights_holder="Creator Studio",
        music_source="royalty_free",
        user_confirmed_rights=True,
        disclaimer_accepted=True,
    )

    vid_file = tmp_path / "clip_01.mp4"
    vid_file.write_text("fake video", encoding="utf-8")
    srt_file = tmp_path / "clip_01.srt"
    vtt_file = tmp_path / "clip_01.vtt"
    thumb_file = tmp_path / "clip_01_thumbnail.jpg"

    generator = ClipMetadataGenerator()
    meta = generator.generate_metadata(
        candidate=candidate,
        podcast_input=inp,
        rights_declaration=rights,
        video_path=vid_file,
        srt_path=srt_file,
        vtt_path=vtt_file,
        thumbnail_path=thumb_file,
    )

    assert meta.clip_id == "clip_01"
    assert "#Shorts" in meta.title
    assert "Creator Studio" in meta.description
    assert "https://www.youtube.com/watch?v=sample123" in meta.description
    assert "#Shorts" in meta.hashtags
    assert "podcast clip" in meta.tags

    json_file = tmp_path / "clip_01_metadata.json"
    assert json_file.is_file()
    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert data["clip_id"] == "clip_01"


def test_youtube_upload_guardrails():
    """Verify upload fails safely without explicit user approval."""
    pipeline = PodcastToShortsPipeline()
    meta = MagicMock()
    meta.video_path = "non_existent.mp4"

    # User approval is mandatory
    with pytest.raises(RightsVerificationError, match="Explicit user approval is mandatory"):
        pipeline.upload_to_youtube(meta, user_approved=False)


def test_dashboard_server_endpoints():
    """Verify FastAPI dashboard endpoints respond with valid schemas."""
    from starlette.testclient import TestClient
    from benxautomation.podcast.server import app

    client = TestClient(app)

    # Status check
    r_status = client.get("/api/status")
    assert r_status.status_code == 200
    data = r_status.json()
    assert "ffmpeg_available" in data
    assert "youtube_oauth_status" in data

    # Root HTML dashboard check
    r_index = client.get("/")
    assert r_index.status_code == 200
    assert "BENX Podcast" in r_index.text

    # Rights verification endpoint check
    r_rights = client.post("/api/rights/verify", json={
        "ownership_type": "creator_owned",
        "rights_holder": "Creator",
        "license_evidence": "Owned footage",
        "music_source": "royalty_free",
        "user_confirmed_rights": True,
        "disclaimer_accepted": True,
    })
    assert r_rights.status_code == 200
    assert r_rights.json()["valid"] is True


def test_batch_processor_queue_lifecycle(tmp_path: Path):
    """Verify queueing, status filtering, restart recovery, and deduplication in batch processor."""
    from benxautomation.podcast.batch_processor import PodcastBatchProcessor

    db_file = tmp_path / "test_batch.db"
    processor = PodcastBatchProcessor(db_path=db_file)

    decl = RightsDeclaration(
        ownership_type="creator_owned",
        rights_holder="Creator",
        music_source="royalty_free",
        user_confirmed_rights=True,
        disclaimer_accepted=True,
    )

    # 1. Add jobs
    j1 = processor.add_job("sample_1.mp4", decl, clips_target=2)
    j2 = processor.add_job("sample_2.mp4", decl, clips_target=3)
    assert j1 == 1
    assert j2 == 2

    # 2. Duplicate insertion returns existing job id
    j1_dup = processor.add_job("sample_1.mp4", decl, clips_target=2)
    assert j1_dup == j1

    # 3. List and summary
    summary = processor.get_summary()
    assert summary["PENDING"] == 2
    assert summary["COMPLETED"] == 0

    # 4. Restart recovery test
    # Simulate a crashed job in PROCESSING
    with processor._get_connection() as conn:
        conn.execute("UPDATE batch_jobs SET status = 'PROCESSING' WHERE id = 1")
        conn.commit()

    recovered = processor.recover_interrupted_jobs()
    assert recovered == 1
    reloaded_j1 = processor.get_job(1)
    assert reloaded_j1.status == "PENDING"

