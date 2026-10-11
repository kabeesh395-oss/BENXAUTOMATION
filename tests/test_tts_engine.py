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

    def test_synthesized_audio_is_speech_not_constant_tone_or_silence(self, tmp_path: Path):
        """Verify that synthesized audio has dynamic speech amplitude, not a constant tone or silence."""
        import subprocess
        from benxautomation.renderer.ffmpeg_utils import find_ffmpeg

        engine = TTSEngine()
        out_file = tmp_path / "speech_check.mp3"
        res = engine.synthesize(
            "This is a verified test of genuine neural speech narration.",
            out_file,
            voice="en-US-AriaNeural",
        )
        assert out_file.is_file()
        assert out_file.stat().st_size > 1000

        ffmpeg_bin = find_ffmpeg()
        # Run astats to extract dynamic range
        cmd = [
            ffmpeg_bin, "-i", str(out_file),
            "-af", "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level",
            "-f", "null", "-",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        rms_levels = []
        for line in proc.stderr.splitlines():
            if "lavfi.astats.Overall.RMS_level=" in line:
                val = float(line.split("=")[-1])
                rms_levels.append(val)

        assert len(rms_levels) > 10, "Expected multiple audio frames"
        # A 1000Hz sine wave has constant RMS (-3.01 dB). Speech fluctuates with syllables and pauses.
        unique_levels = {round(x, 1) for x in rms_levels if x > -100}
        assert len(unique_levels) >= 5, f"Expected fluctuating speech levels, got {unique_levels}"

    def test_tts_failure_raises_actionable_error(self, tmp_path: Path):
        """Verify that TTS failure raises TTSError and never creates fake audio."""
        engine = TTSEngine()
        out_file = tmp_path / "failed.mp3"

        with patch("edge_tts.Communicate.save", side_effect=RuntimeError("EdgeTTS service unavailable")):
            with pytest.raises(TTSError, match="TTS synthesis failed"):
                engine.synthesize("Valid text", out_file)
        assert not out_file.exists()
