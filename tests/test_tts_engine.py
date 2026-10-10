"""Tests for TTSEngine."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from benxautomation.tts.engine import TTSEngine, TTSError
from tests.conftest import skip_no_ffprobe


class TestTTSEngine:
    def test_empty_text_raises_error(self, tmp_path: Path):
        engine = TTSEngine()
        with pytest.raises(TTSError, match="empty text"):
            engine.synthesize("   ", tmp_path / "out.mp3")

    def test_synthesize_produces_real_audio(self, tmp_path: Path):
        engine = TTSEngine()
        out_file = tmp_path / "voiceover.mp3"
        result = engine.synthesize(
            "BENX Automation testing.",
            out_file,
            voice="en-US-AriaNeural",
        )

        assert result.file_path == out_file
        assert out_file.is_file()
        assert out_file.stat().st_size > 0
        assert result.duration_seconds > 0
        assert result.voice_name == "en-US-AriaNeural"

    def test_duration_from_probe_metadata_when_available(self, tmp_path: Path):
        """Verify probe_file metadata is used directly when available."""
        fake_audio = tmp_path / "fake.mp3"
        fake_audio.write_bytes(b"dummy audio content" * 100)

        engine = TTSEngine()

        with patch("edge_tts.Communicate.save"):
            with patch("benxautomation.renderer.ffmpeg_utils.probe_file") as mock_probe:
                mock_probe.return_value = {
                    "format": {"duration": "18.750"}
                }
                result = engine.synthesize("Some narration text", fake_audio)
                assert result.duration_seconds == 18.750
                mock_probe.assert_called_once_with(fake_audio)

    def test_duration_fallback_when_probe_fails(self, tmp_path: Path):
        """Verify byte-based estimation is used when probe_file fails or returns empty."""
        fake_audio = tmp_path / "fake_fallback.mp3"
        # 12,000 bytes -> 12000 / 6000 = 2.0s
        fake_audio.write_bytes(b"0" * 12000)

        engine = TTSEngine()

        with patch("edge_tts.Communicate.save"):
            with patch("benxautomation.renderer.ffmpeg_utils.probe_file") as mock_probe:
                mock_probe.side_effect = RuntimeError("ffprobe crashed")
                result = engine.synthesize("Some narration text", fake_audio)
                assert result.duration_seconds == 2.0
