"""Tests for MoneyPrinterTurbo adapter."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from benxautomation.adapters.moneyprinter import (
    MoneyPrinterAdapter,
    MoneyPrinterError,
    MoneyPrinterVideoRequest,
)


class TestMoneyPrinterAdapter:
    def test_missing_repo_raises_error(self, tmp_path: Path):
        adapter = MoneyPrinterAdapter(repo_dir=tmp_path / "nonexistent")
        req = MoneyPrinterVideoRequest(subject="Test Subject")
        with pytest.raises(MoneyPrinterError, match="not found"):
            adapter.generate_via_cli(req)

    def test_cli_execution_with_real_repo_or_mock(self, tmp_path: Path):
        fake_repo = tmp_path / "fake_repo"
        fake_repo.mkdir()
        (fake_repo / "cli.py").write_text("# stub", encoding="utf-8")

        adapter = MoneyPrinterAdapter(
            repo_dir=fake_repo,
            python_executable="python",
        )
        req = MoneyPrinterVideoRequest(
            subject="AI Trends",
            script="This is a test script.",
            aspect="9:16",
        )

        dummy_out = tmp_path / "final.mp4"
        dummy_out.write_bytes(b"dummy mp4")

        mock_result = {
            "task_id": "test-uuid-123",
            "result": {
                "videos": [str(dummy_out)],
                "script": "This is a test script.",
            },
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=f"Logs...\n{json.dumps(mock_result)}\n",
                stderr="",
            )
            res = adapter.generate_via_cli(req)

            assert res.task_id == "test-uuid-123"
            assert len(res.video_paths) == 1
            assert res.video_paths[0] == dummy_out

    def test_api_missing_base_url_raises(self):
        adapter = MoneyPrinterAdapter()
        req = MoneyPrinterVideoRequest(subject="Test")
        with pytest.raises(MoneyPrinterError, match="not configured"):
            adapter.generate_via_api(req)

    @patch("requests.post")
    @patch("requests.get")
    def test_api_flow_success(self, mock_get, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"data": {"task_id": "api-task-456"}},
        )
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "data": {
                    "state": 1,
                    "progress": 100,
                    "videos": ["/tasks/api-task-456/final-1.mp4"],
                }
            },
        )

        adapter = MoneyPrinterAdapter(api_base_url="http://127.0.0.1:8080")
        req = MoneyPrinterVideoRequest(subject="Test", script="Hello world")
        res = adapter.generate_via_api(req, poll_interval_seconds=0.01)

        assert res.task_id == "api-task-456"
        assert len(res.video_paths) == 1
