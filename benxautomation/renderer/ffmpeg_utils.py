"""Low-level FFmpeg/FFprobe wrapper using subprocess."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from benxautomation.errors import FFmpegNotFoundError, RenderingError
from benxautomation.logger import get_logger

log = get_logger(__name__)


def _sync_windows_path() -> None:
    """Ensure process PATH includes system & user PATH from Windows registry if on Windows."""
    if os.name != "nt":
        return
    try:
        import winreg
        paths = []
        for hkey, subkey in [
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            (winreg.HKEY_CURRENT_USER, r"Environment"),
        ]:
            try:
                with winreg.OpenKey(hkey, subkey) as k:
                    val, _ = winreg.QueryValueEx(k, "Path")
                    paths.extend(val.split(";"))
            except OSError:
                continue

        current = os.environ.get("PATH", "").split(";")
        updated = False
        for p in paths:
            p_clean = p.strip()
            if p_clean and p_clean not in current:
                current.append(p_clean)
                updated = True
        if updated:
            os.environ["PATH"] = ";".join(current)
    except Exception:
        pass


def find_ffmpeg(configured_path: str = "ffmpeg") -> str:
    """Resolve *configured_path* to an absolute path, or raise."""
    resolved = shutil.which(configured_path)
    if resolved is None:
        _sync_windows_path()
        resolved = shutil.which(configured_path)
    if resolved is None:
        raise FFmpegNotFoundError(
            f"FFmpeg not found at '{configured_path}'. "
            "Install FFmpeg or set rendering.ffmpeg_path in config."
        )
    return resolved


def find_ffprobe(configured_path: str = "ffprobe") -> str:
    """Resolve *configured_path* to an absolute path, or raise."""
    resolved = shutil.which(configured_path)
    if resolved is None:
        _sync_windows_path()
        resolved = shutil.which(configured_path)
    if resolved is None:
        raise FFmpegNotFoundError(
            f"FFprobe not found at '{configured_path}'. "
            "Install FFprobe or set rendering.ffprobe_path in config."
        )
    return resolved


def ffmpeg_is_available(path: str = "ffmpeg") -> bool:
    """Return True if FFmpeg can be invoked."""
    try:
        find_ffmpeg(path)
        return True
    except FFmpegNotFoundError:
        return False


def ffprobe_is_available(path: str = "ffprobe") -> bool:
    """Return True if FFprobe can be invoked."""
    try:
        find_ffprobe(path)
        return True
    except FFmpegNotFoundError:
        return False


def run_ffmpeg(args: list[str], *, ffmpeg_path: str = "ffmpeg") -> str:
    """Execute FFmpeg with *args* and return combined stdout+stderr.

    Raises ``RenderingError`` on non-zero exit.
    """
    binary = find_ffmpeg(ffmpeg_path)
    cmd = [binary, "-y"] + args  # -y = overwrite output without asking
    log.info("Running FFmpeg: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RenderingError(
            f"FFmpeg exited with code {result.returncode}:\n{result.stderr}"
        )
    return result.stdout + result.stderr


def probe_file(path: Path, *, ffprobe_path: str = "ffprobe") -> dict:
    """Run ffprobe on *path* and return the parsed JSON metadata.

    Returns an empty dict if ffprobe is unavailable (graceful degradation).
    """
    try:
        binary = find_ffprobe(ffprobe_path)
    except FFmpegNotFoundError:
        log.warning("ffprobe not available — skipping probe of %s", path)
        return {}

    cmd = [
        binary,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        log.warning("ffprobe failed for %s: %s", path, result.stderr)
        return {}
    return json.loads(result.stdout)


def mix_narration_with_bgm(
    narration_path: Path,
    bgm_path: Path,
    output_path: Path,
    *,
    bgm_volume: float = 0.15,
    ffmpeg_path: str = "ffmpeg",
) -> Path:
    """Mix narration voiceover with background music ducked to safe levels.

    The final duration is matched strictly to the narration audio track duration.
    """
    if not narration_path.is_file():
        raise RenderingError(f"Narration audio file not found: {narration_path}")
    if not bgm_path.is_file():
        raise RenderingError(f"Background music file not found: {bgm_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    filter_expr = f"[1:a]volume={bgm_volume:.3f}[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    args = [
        "-i", str(narration_path),
        "-stream_loop", "-1",
        "-i", str(bgm_path),
        "-filter_complex", filter_expr,
        "-map", "[aout]",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        str(output_path),
    ]
    log.info("Mixing narration %s with BGM %s (vol=%.2f) -> %s", narration_path, bgm_path, bgm_volume, output_path)
    run_ffmpeg(args, ffmpeg_path=ffmpeg_path)
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RenderingError(f"Audio mixing produced empty output: {output_path}")
    return output_path
