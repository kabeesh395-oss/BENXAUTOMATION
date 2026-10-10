"""Tests for TTSEngine."""

from pathlib import Path
import pytest

from benxautomation.tts.engine import TTSEngine, TTSError


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
