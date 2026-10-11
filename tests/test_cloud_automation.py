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


def test_cloud_runner_dry_run_execution(tmp_path: Path):
    """Verify that cloud runner completes dry-run execution without uploading."""
    test_src = tmp_path / "test_sample.mp4"
    ret = main(["--dry-run", "--source", str(test_src), "--clips-target", "1"])
    assert ret == 0
