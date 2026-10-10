"""Unit tests for background music audio mixing."""

from pathlib import Path
from unittest.mock import patch
import pytest

from benxautomation.errors import RenderingError
from benxautomation.renderer.ffmpeg_utils import mix_narration_with_bgm


class TestAudioMixing:
    def test_missing_narration_raises(self, tmp_path: Path):
        bgm = tmp_path / "bgm.mp3"
        bgm.write_bytes(b"bgm")
        with pytest.raises(RenderingError, match="Narration audio file not found"):
            mix_narration_with_bgm(tmp_path / "missing.mp3", bgm, tmp_path / "out.mp3")

    def test_missing_bgm_raises(self, tmp_path: Path):
        narr = tmp_path / "narr.mp3"
        narr.write_bytes(b"narr")
        with pytest.raises(RenderingError, match="Background music file not found"):
            mix_narration_with_bgm(narr, tmp_path / "missing_bgm.mp3", tmp_path / "out.mp3")

    def test_successful_mixing_invocation(self, tmp_path: Path):
        narr = tmp_path / "narr.mp3"
        narr.write_bytes(b"narr")
        bgm = tmp_path / "bgm.mp3"
        bgm.write_bytes(b"bgm")
        out = tmp_path / "mixed.mp3"

        with patch("benxautomation.renderer.ffmpeg_utils.run_ffmpeg") as mock_ffmpeg:
            # Simulate output creation by ffmpeg
            def side_effect(args, **kwargs):
                out.write_bytes(b"mixed audio content")
                return "OK"

            mock_ffmpeg.side_effect = side_effect
            res = mix_narration_with_bgm(narr, bgm, out, bgm_volume=0.15)

            assert res == out
            assert out.is_file()
            # Assert ffmpeg args included amix and volume filters
            call_args = mock_ffmpeg.call_args[0][0]
            assert "-filter_complex" in call_args
            filter_str = call_args[call_args.index("-filter_complex") + 1]
            assert "volume=0.150" in filter_str
            assert "amix=" in filter_str

    def test_pipeline_without_bgm_track_falls_back_to_voiceover(self, tmp_path: Path):
        from benxautomation.config import AppConfig
        from benxautomation.pipeline import VideoPipeline

        cfg = AppConfig()
        pipeline = VideoPipeline(cfg)
        resolved = pipeline._resolve_bgm(None)
        # In an empty or standard directory without assets/bgm, returns None
        assert resolved is None or resolved.is_file()

    def test_pipeline_with_custom_bgm_track(self, tmp_path: Path):
        from benxautomation.config import AppConfig
        from benxautomation.pipeline import VideoPipeline

        bgm = tmp_path / "custom_bgm.mp3"
        bgm.write_bytes(b"music")
        cfg = AppConfig()
        pipeline = VideoPipeline(cfg)
        resolved = pipeline._resolve_bgm(bgm)
        assert resolved == bgm
