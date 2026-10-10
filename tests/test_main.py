"""Tests for CLI entrypoint."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from benxautomation.main import build_parser, main
from tests.conftest import skip_no_ffmpeg


def test_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["--asset", "test.jpg"])
    assert args.asset == Path("test.jpg")
    assert args.output_dir == Path("output")
    assert args.topic is None
    assert args.script is None
    assert args.voice is None
    assert args.no_subtitles is False
    assert args.shorts_only is False
    assert args.longform_only is False


def test_parser_topic_and_script():
    parser = build_parser()
    args = parser.parse_args([
        "--asset", "test.jpg",
        "--topic", "Deep ocean mysteries",
        "--voice", "en-US-AriaNeural",
        "--no-subtitles",
    ])
    assert args.topic == "Deep ocean mysteries"
    assert args.voice == "en-US-AriaNeural"
    assert args.no_subtitles is True


def test_main_passes_script_and_topic_to_pipeline(tmp_path: Path):
    """Verify script takes precedence over topic, and topic is used when script is absent."""
    dummy_asset = tmp_path / "card.jpg"
    dummy_asset.write_bytes(b"image")

    with patch("benxautomation.main.VideoPipeline") as mock_pipeline_cls:
        mock_pipeline = MagicMock()
        mock_pipeline_cls.return_value = mock_pipeline
        mock_pipeline.run.return_value = MagicMock(
            shorts_result=None, longform_result=None, audio_path=None, subtitle_path=None
        )

        # 1. Topic only
        rc = main(["--asset", str(dummy_asset), "--topic", "My Topic"])
        assert rc == 0
        call_kwargs = mock_pipeline.run.call_args[1]
        assert call_kwargs["script_text"] == "My Topic"
        assert call_kwargs["enable_subtitles"] is True

        # 2. Script provided (overrides topic)
        rc = main(["--asset", str(dummy_asset), "--topic", "My Topic", "--script", "Actual script"])
        assert rc == 0
        call_kwargs = mock_pipeline.run.call_args[1]
        assert call_kwargs["script_text"] == "Actual script"

        # 3. No subtitles flag
        rc = main(["--asset", str(dummy_asset), "--script", "Test", "--no-subtitles", "--voice", "en-GB-SoniaNeural"])
        assert rc == 0
        call_kwargs = mock_pipeline.run.call_args[1]
        assert call_kwargs["enable_subtitles"] is False
        assert call_kwargs["voice_name"] == "en-GB-SoniaNeural"


def test_main_missing_asset_returns_error(tmp_path: Path):
    rc = main(["--asset", str(tmp_path / "nonexistent.jpg")])
    assert rc == 2


@skip_no_ffmpeg
def test_main_execution_success(sample_image: Path, tmp_output: Path):
    manifest = sample_image.parent / "license_manifest.yaml"
    manifest.write_text(
        f"assets:\n  - file: {sample_image.name}\n    license: cc0\n",
        encoding="utf-8",
    )
    rc = main([
        "--asset", str(sample_image),
        "--output-dir", str(tmp_output),
        "--duration", "1",
        "--manifest", str(manifest),
        "--shorts-only",
    ])
    assert rc == 0
    assert (tmp_output / f"{sample_image.stem}_shorts.mp4").is_file()
