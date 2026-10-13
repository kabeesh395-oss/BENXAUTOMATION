"""Unit and integration tests for GitHub Actions cloud automation runner."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from benxautomation.cloud_runner import (
    build_parser,
    hydrate_oauth_secrets,
    main,
    verify_cloud_environment,
)


def test_workflow_yaml_syntax():
    """Verify that GitHub Actions workflow files have valid YAML syntax."""
    wf_dir = Path(".github/workflows")
    for wf in wf_dir.glob("*.yml"):
        content = wf.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict)
        assert "name" in parsed
        assert "jobs" in parsed


def test_cron_ist_schedule_math():
    """Verify that workflow cron expressions map to the exact IST hours requested."""
    # Asia/Kolkata is UTC+5:30
    # 04:00 UTC -> 09:30 IST
    # 09:00 UTC -> 14:30 (2:30 PM) IST
    # 14:00 UTC -> 19:30 (7:30 PM) IST
    shorts_wf = Path(".github/workflows/podcast_shorts_automation.yml")
    parsed = yaml.safe_load(shorts_wf.read_text(encoding="utf-8"))
    on_block = parsed.get("on") or parsed.get(True)
    cron_expr = on_block["schedule"][0]["cron"]
    assert cron_expr == "0 4,9,14 * * *"

    # Longform: 13:00 UTC -> 18:30 (6:30 PM) IST on Sunday (0) and Wednesday (3)
    longform_wf = Path(".github/workflows/longform_automation.yml")
    parsed_lf = yaml.safe_load(longform_wf.read_text(encoding="utf-8"))
    on_lf = parsed_lf.get("on") or parsed_lf.get(True)
    cron_lf = on_lf["schedule"][0]["cron"]
    assert cron_lf == "0 13 * * 0,3"


def test_hydrate_oauth_secrets_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify hydration of OAuth secrets from environment variables."""
    # Redirect token dir to tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    secret_data = {"installed": {"client_id": "test_id", "client_secret": "test_secret"}}
    tokens_data = {"access_token": "ya29.test", "refresh_token": "1//test_refresh"}

    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET_JSON", json.dumps(secret_data))
    monkeypatch.setenv("YOUTUBE_TOKENS_JSON", json.dumps(tokens_data))

    ready, messages = hydrate_oauth_secrets()
    assert ready is True

    secret_file = tmp_path / ".benxautomation" / "client_secret.json"
    token_file = tmp_path / ".benxautomation" / "youtube_tokens.json"

    assert secret_file.is_file()
    assert token_file.is_file()
    assert json.loads(secret_file.read_text(encoding="utf-8")) == secret_data
    assert json.loads(token_file.read_text(encoding="utf-8")) == tokens_data


def test_hydrate_oauth_secrets_base64(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify base64-encoded secrets hydration."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    secret_data = {"installed": {"client_id": "b64_id", "client_secret": "b64_secret"}}
    tokens_data = {"access_token": "ya29.b64", "refresh_token": "1//b64_refresh"}

    b64_secret = base64.b64encode(json.dumps(secret_data).encode("utf-8")).decode("utf-8")
    b64_tokens = base64.b64encode(json.dumps(tokens_data).encode("utf-8")).decode("utf-8")

    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET_BASE64", b64_secret)
    monkeypatch.setenv("YOUTUBE_TOKENS_BASE64", b64_tokens)

    ready, messages = hydrate_oauth_secrets()
    assert ready is True

    secret_file = tmp_path / ".benxautomation" / "client_secret.json"
    assert secret_file.is_file()
    assert json.loads(secret_file.read_text(encoding="utf-8")) == secret_data


def test_hydrate_oauth_secrets_missing_graceful(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify graceful handling when secrets are absent."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRET_JSON", raising=False)
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRET_BASE64", raising=False)
    monkeypatch.delenv("YOUTUBE_TOKENS_JSON", raising=False)
    monkeypatch.delenv("YOUTUBE_TOKENS_BASE64", raising=False)

    ready, messages = hydrate_oauth_secrets()
    assert ready is False


def _create_test_podcast_fixture(path: Path) -> Path:
    """Helper to create a minimal valid test video with srt transcript for testing."""
    from benxautomation.renderer.ffmpeg_utils import run_ffmpeg

    path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-f", "lavfi", "-i", "color=c=black:s=640x360:r=25",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=24000",
        "-t", "15",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(path),
    ])
    srt_path = path.with_suffix(".srt")
    srt_path.write_text(
        "1\n00:00:00,000 --> 00:00:05,000\nWelcome to creator podcast.\n\n"
        "2\n00:00:05,000 --> 00:00:10,000\nConsistency matters most.\n\n"
        "3\n00:00:10,000 --> 00:00:15,000\nKeep creating every day.\n",
        encoding="utf-8",
    )
    return path


def test_cloud_runner_missing_source_fails_with_actionable_error(tmp_path: Path):
    """Regression test: Cloud runner must abort with code 1 if source file is missing."""
    missing_src = tmp_path / "non_existent_source.mp4"
    ret = main(["--source", str(missing_src)])
    assert ret == 1
    assert not missing_src.exists()


def test_cloud_runner_omitted_source_fails_cleanly():
    """Regression test: Cloud runner must abort with code 1 if --source is not specified."""
    ret = main([])
    assert ret == 1


def test_no_sine_beep_generated_in_codebase():
    """Regression test: Ensure no 1000Hz or other sine tone fallbacks exist in python source files."""
    repo_root = Path(__file__).parent.parent
    py_files = list((repo_root / "benxautomation").rglob("*.py"))
    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8")
        assert "sine=frequency=" not in content, f"Found sine test tone in {py_file}"
        assert "sine=" not in content, f"Found sine generator in {py_file}"


def test_cloud_runner_dry_run_execution(tmp_path: Path):
    """Verify that cloud runner completes dry-run execution on a valid source video without uploading."""
    test_src = _create_test_podcast_fixture(tmp_path / "test_sample.mp4")
    ret = main(["--dry-run", "--source", str(test_src), "--clips-target", "1"])
    assert ret == 0


def test_workflow_dispatch_inputs_specification():
    """Verify podcast_shorts_automation.yml workflow_dispatch matches exact requirements."""
    shorts_wf = Path(".github/workflows/podcast_shorts_automation.yml")
    parsed = yaml.safe_load(shorts_wf.read_text(encoding="utf-8"))
    on_block = parsed.get("on") or parsed.get(True)
    assert "workflow_dispatch" in on_block
    inputs = on_block["workflow_dispatch"]["inputs"]

    assert "mode" in inputs
    assert inputs["mode"]["type"] == "choice"
    assert inputs["mode"]["options"] == ["dry_run", "render_only", "upload_private"]
    assert inputs["mode"]["default"] == "dry_run"

    assert "clips_target" in inputs
    assert str(inputs["clips_target"]["default"]) == "1"


def test_cloud_runner_mode_flag_routing(tmp_path: Path):
    """Verify that --mode dry_run sets dry_run flag and succeeds safely."""
    test_src = _create_test_podcast_fixture(tmp_path / "test_sample_mode.mp4")
    ret = main(["--mode", "dry_run", "--source", str(test_src), "--clips-target", "1"])
    assert ret == 0


def test_cloud_runner_fallback_to_topic_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Regression test: Cloud runner executes deliberate fallback topic workflow when source is omitted."""
    # Ensure no external API keys are required for test
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PODCAST_SOURCE_URL", raising=False)

    ret = main([
        "--fallback-to-topic",
        "--dry-run",
        "--fallback-topic",
        "Deep Sea Marine Mysteries",
    ])
    assert ret == 0


def test_ci_workflow_no_monkeypatch_and_clean_requests_version():
    """Regression test: Ensure ci.yml does not monkeypatch requests and uses official __version__."""
    ci_wf = Path(".github/workflows/ci.yml")
    content = ci_wf.read_text(encoding="utf-8")
    assert "version = __version__" not in content, "Monkeypatching requests.__file__ must be eliminated from CI"
    assert "requests.version" not in content, "requests.version is unsupported; requests.__version__ must be used"
    assert "requests.__version__" in content


def test_scheduled_workflows_no_silent_exit_zero_skip():
    """Regression test: Scheduled workflows must never silently exit 0 without executing a pipeline."""
    for wf_path in Path(".github/workflows").glob("*.yml"):
        content = wf_path.read_text(encoding="utf-8")
        assert "Skipping run.\n            exit 0" not in content, (
            f"{wf_path.name} contains silent exit 0 without processing"
        )

