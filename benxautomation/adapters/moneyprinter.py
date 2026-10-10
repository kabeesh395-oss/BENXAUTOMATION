"""Adapter for MoneyPrinterTurbo video generation engine.

Supports both direct CLI execution and REST API interaction with a
MoneyPrinterTurbo server instance.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests

from benxautomation.errors import BenxError, RenderingError
from benxautomation.logger import get_logger

log = get_logger(__name__)


class MoneyPrinterError(BenxError):
    """Raised when MoneyPrinterTurbo execution or API call fails."""


@dataclass
class MoneyPrinterVideoRequest:
    """Parameters for generating a video with MoneyPrinterTurbo."""
    subject: str
    script: str = ""
    aspect: str = "9:16"  # "9:16", "16:9", "1:1"
    voice_name: str = "en-US-AriaNeural-Female"
    video_source: str = "local"
    video_materials: list[str] = field(default_factory=list)
    bgm_type: str = "none"
    bgm_file: str = ""
    subtitle_enabled: bool = False
    stop_at: str = "video"


@dataclass
class MoneyPrinterResult:
    """Output from MoneyPrinterTurbo generation."""
    task_id: str
    video_paths: list[Path]
    audio_path: Optional[Path] = None
    subtitle_path: Optional[Path] = None
    script: str = ""
    raw_result: dict[str, Any] = field(default_factory=dict)


class MoneyPrinterAdapter:
    """Connects BENXAUTOMATION to MoneyPrinterTurbo.

    Can execute via local CLI subprocess or through the HTTP REST API.
    """

    def __init__(
        self,
        *,
        repo_dir: Optional[Path] = None,
        python_executable: str = "python",
        api_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        ffmpeg_dir: Optional[str] = None,
    ):
        self.repo_dir = Path(repo_dir) if repo_dir else None
        self.python_executable = python_executable
        self.api_base_url = api_base_url.rstrip("/") if api_base_url else None
        self.api_key = api_key
        self.ffmpeg_dir = ffmpeg_dir

    def generate_via_cli(
        self,
        request: MoneyPrinterVideoRequest,
        *,
        timeout_seconds: int = 300,
    ) -> MoneyPrinterResult:
        """Run MoneyPrinterTurbo directly using cli.py."""
        if not self.repo_dir or not (self.repo_dir / "cli.py").is_file():
            raise MoneyPrinterError(
                f"MoneyPrinterTurbo repository not found at {self.repo_dir}"
            )

        cmd = [
            self.python_executable,
            str(self.repo_dir / "cli.py"),
            "--video-subject", request.subject,
            "--video-aspect", request.aspect,
            "--voice-name", request.voice_name,
            "--video-source", request.video_source,
            "--bgm-type", request.bgm_type,
            "--stop-at", request.stop_at,
        ]

        if request.script:
            cmd.extend(["--video-script", request.script])

        if request.video_materials:
            cmd.extend(["--video-materials", ",".join(request.video_materials)])

        if not request.subtitle_enabled:
            cmd.append("--no-subtitle-enabled")

        env = os.environ.copy()
        if self.ffmpeg_dir:
            env["PATH"] = f"{self.ffmpeg_dir}{os.pathsep}{env.get('PATH', '')}"

        log.info("Running MoneyPrinterTurbo CLI in %s", self.repo_dir)
        proc = subprocess.run(
            cmd,
            cwd=str(self.repo_dir),
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout_seconds,
        )

        if proc.returncode != 0:
            raise MoneyPrinterError(
                f"MoneyPrinterTurbo CLI failed (exit {proc.returncode}):\n{proc.stderr}\n{proc.stdout}"
            )

        # Parse JSON output from last line of stdout
        output_line = ""
        for line in reversed(proc.stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                output_line = line
                break

        if not output_line:
            raise MoneyPrinterError(
                f"Could not parse JSON output from MoneyPrinterTurbo:\n{proc.stdout}"
            )

        try:
            data = json.loads(output_line)
        except json.JSONDecodeError as exc:
            raise MoneyPrinterError(f"Invalid JSON from MoneyPrinterTurbo: {exc}") from exc

        task_id = data.get("task_id", "")
        res_data = data.get("result", {})
        videos = [Path(p) for p in res_data.get("videos", []) if Path(p).is_file()]
        audio = Path(res_data["audio_file"]) if res_data.get("audio_file") and Path(res_data["audio_file"]).is_file() else None
        subs = Path(res_data["subtitle_path"]) if res_data.get("subtitle_path") and Path(res_data["subtitle_path"]).is_file() else None

        return MoneyPrinterResult(
            task_id=task_id,
            video_paths=videos,
            audio_path=audio,
            subtitle_path=subs,
            script=res_data.get("script", request.script),
            raw_result=data,
        )

    def generate_via_api(
        self,
        request: MoneyPrinterVideoRequest,
        *,
        poll_interval_seconds: float = 2.0,
        timeout_seconds: int = 300,
    ) -> MoneyPrinterResult:
        """Submit job to MoneyPrinterTurbo FastAPI server and poll until complete."""
        if not self.api_base_url:
            raise MoneyPrinterError("API base URL is not configured.")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "video_subject": request.subject,
            "video_script": request.script,
            "video_aspect": request.aspect,
            "voice_name": request.voice_name,
            "video_source": request.video_source,
            "bgm_type": request.bgm_type,
            "subtitle_enabled": request.subtitle_enabled,
        }
        if request.video_materials:
            payload["video_materials"] = [
                {"provider": "local", "url": mat, "duration": 0}
                for mat in request.video_materials
            ]

        create_url = f"{self.api_base_url}/api/v1/videos"
        resp = requests.post(create_url, json=payload, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise MoneyPrinterError(f"API request failed ({resp.status_code}): {resp.text}")

        task_data = resp.json().get("data", {})
        task_id = task_data.get("task_id")
        if not task_id:
            raise MoneyPrinterError(f"No task_id in response: {resp.text}")

        # Poll status
        import time
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            status_url = f"{self.api_base_url}/api/v1/tasks/{task_id}"
            s_resp = requests.get(status_url, headers=headers, timeout=10)
            if s_resp.status_code == 200:
                s_data = s_resp.json().get("data", {})
                state = s_data.get("state")
                progress = s_data.get("progress", 0)
                if state == 1 or progress >= 100:  # Completed
                    videos = [Path(v) for v in s_data.get("videos", [])]
                    return MoneyPrinterResult(
                        task_id=task_id,
                        video_paths=videos,
                        script=request.script,
                        raw_result=s_data,
                    )
                elif state == -1:
                    raise MoneyPrinterError(f"MoneyPrinterTurbo task failed: {s_data}")
            time.sleep(poll_interval_seconds)

        raise MoneyPrinterError(f"Task {task_id} timed out after {timeout_seconds}s")
