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

        # 1. Topic only passes topic to pipeline
        rc = main(["--asset", str(dummy_asset), "--topic", "My Topic"])
        assert rc == 0
        call_kwargs = mock_pipeline.run.call_args[1]
        assert call_kwargs["topic"] == "My Topic"
        assert call_kwargs["script_text"] is None
        assert call_kwargs["enable_subtitles"] is True

        # 2. Script provided (passes both to pipeline where script takes precedence)
        rc = main(["--asset", str(dummy_asset), "--topic", "My Topic", "--script", "Actual script"])
        assert rc == 0
        call_kwargs = mock_pipeline.run.call_args[1]
        assert call_kwargs["topic"] == "My Topic"
        assert call_kwargs["script_text"] == "Actual script"

        # 3. No subtitles and no music flags
        rc = main([
            "--asset", str(dummy_asset),
            "--script", "Test",
            "--no-subtitles",
            "--no-music",
            "--voice", "en-GB-SoniaNeural",
            "--provider", "fallback",
        ])
        assert rc == 0
        call_kwargs = mock_pipeline.run.call_args[1]
        assert call_kwargs["enable_subtitles"] is False
        assert call_kwargs["enable_music"] is False
        assert call_kwargs["voice_name"] == "en-GB-SoniaNeural"
        assert call_kwargs["provider_name"] == "fallback"


def test_main_missing_inputs_returns_error():
    """Verify that calling main with no topic, script, or asset returns an error."""
    rc = main([])
    assert rc == 1


def test_main_dry_run_success(tmp_path: Path):
    rc = main(["--script", "Test script", "--dry-run"])
    assert rc == 0


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


def test_main_mode_dry_run_routes_safely():
    """Verify --mode dry_run executes dry-run validation cleanly without rendering."""
    rc = main(["--script", "Dry run test narration.", "--mode", "dry_run"])
    assert rc == 0


def test_main_mode_render_only_flag(tmp_path: Path):
    """Verify --mode render_only does not trigger upload."""
    with patch("benxautomation.main.VideoPipeline") as mock_pipeline_cls:
        mock_pipeline = MagicMock()
        mock_pipeline_cls.return_value = mock_pipeline
        mock_pipeline.run.return_value = MagicMock(
            shorts_result=None, longform_result=None, audio_path=None, subtitle_path=None
        )
        rc = main(["--script", "Test text", "--mode", "render_only"])
        assert rc == 0


def test_main_mode_upload_private_without_oauth_warns_safely(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify --mode upload_private safely preserves local artifacts when OAuth is unconfigured."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    dummy_video = tmp_path / "video_shorts.mp4"
    dummy_video.write_bytes(b"dummy")

    with patch("benxautomation.main.VideoPipeline") as mock_pipeline_cls:
        mock_pipeline = MagicMock()
        mock_pipeline_cls.return_value = mock_pipeline
        mock_pipeline.run.return_value = MagicMock(
            shorts_result=MagicMock(output_path=dummy_video),
            longform_result=None,
            audio_path=None,
            subtitle_path=None,
        )
        rc = main(["--script", "Test script", "--mode", "upload_private"])
        assert rc == 0


def test_main_mode_upload_private_with_oauth_invokes_publisher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify --mode upload_private invokes YouTubePublisher with privacy_status='private'."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    token_dir = tmp_path / ".benxautomation"
    token_dir.mkdir(parents=True, exist_ok=True)
    secret_file = token_dir / "client_secret.json"
    secret_file.write_text('{"installed": {"client_id": "test", "client_secret": "test"}}', encoding="utf-8")

    dummy_video = tmp_path / "video_shorts.mp4"
    dummy_video.write_bytes(b"dummy")

    with patch("benxautomation.main.VideoPipeline") as mock_pipeline_cls:
        mock_pipeline = MagicMock()
        mock_pipeline_cls.return_value = mock_pipeline
        mock_pipeline.run.return_value = MagicMock(
            shorts_result=MagicMock(output_path=dummy_video),
            longform_result=None,
            audio_path=None,
            subtitle_path=None,
        )
        with patch("benxautomation.publisher.youtube.YouTubeOAuthManager") as mock_oauth_cls:
            mock_oauth = MagicMock()
            mock_oauth_cls.return_value = mock_oauth
            with patch("benxautomation.publisher.youtube.YouTubePublisher") as mock_pub_cls:
                mock_pub = MagicMock()
                mock_pub_cls.return_value = mock_pub
                mock_pub.upload.return_value = {"video_id": "test_id", "url": "https://youtu.be/test_id"}

                rc = main(["--script", "Test text", "--mode", "upload_private"])
                assert rc == 0
                mock_pub.upload.assert_called_once()
                call_kwargs = mock_pub.upload.call_args[1]
                assert call_kwargs["privacy_status"] == "private"
