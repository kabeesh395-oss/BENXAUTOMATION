#!/usr/bin/env python3
"""Read-only preflight check for an existing BENXAUTOMATION installation.

Run this script from the BENXAUTOMATION project root. It does not read
environment variables, credentials, user media, or configuration files.
It makes no network requests and writes no files.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path


def command_check(name: str) -> dict[str, object]:
    executable = shutil.which(name)
    if not executable:
        return {"available": False, "path": None, "version": None}
    try:
        result = subprocess.run(
            [executable, "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        first_line = (result.stdout or result.stderr).splitlines()
        return {
            "available": result.returncode == 0,
            "path": executable,
            "version": first_line[0] if first_line else "version output unavailable",
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "path": executable, "version": None, "error": str(exc)}


def main() -> int:
    version_ok = sys.version_info[:2] in {(3, 11), (3, 12)}
    cwd = Path.cwd()
    checkout_found = (cwd / "pyproject.toml").is_file() and (cwd / "benxautomation" / "main.py").is_file()
    try:
        package_found = importlib.util.find_spec("benxautomation") is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        package_found = False

    ffmpeg = command_check("ffmpeg")
    ffprobe = command_check("ffprobe")
    result = {
        "python": {
            "version": sys.version.split()[0],
            "supported": version_ok,
        },
        "project": {
            "working_directory": str(cwd),
            "checkout_found": checkout_found,
            "package_importable": package_found,
        },
        "ffmpeg": ffmpeg,
        "ffprobe": ffprobe,
    }
    ready = version_ok and (checkout_found or package_found) and ffmpeg["available"] and ffprobe["available"]
    result["ready_for_cli_check"] = ready
    print(json.dumps(result, indent=2))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
