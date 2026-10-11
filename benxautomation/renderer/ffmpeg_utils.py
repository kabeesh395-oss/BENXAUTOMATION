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


def build_scene_motion_filter(
    idx: int,
    w: int,
    h: int,
    fps: int,
    dur: float,
    *,
    motion_effect: str = "zoom_in",
    title: str = "",
    is_video: bool = False,
    is_portrait: bool = False,
) -> str:
    """Construct an FFmpeg filter chain for a scene with 2D camera motion and animated graphics.

    Includes:
    - Base aspect ratio scaling with letterboxing / pillarboxing
    - 2D camera pan / zoom (Ken Burns animation)
    - Dynamic animated scene title lower-third badge with fade in / out
    - Subtle floating bioluminescent particles (moving 2D micro-elements)
    - Standardized pixel format, SAR, and framerate.
    """
    d_frames = max(1, int(round(dur * fps)))
    filters = []

    # 1. Base scale and pad
    filters.append(f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=bicubic")
    filters.append(f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black")

    # 2. 2D camera motion (Ken Burns pan/zoom) for static images
    if not is_video:
        if motion_effect == "zoom_in":
            zp = f"zoompan=z='min(zoom+0.0012,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d_frames}:s={w}x{h}:fps={fps}"
        elif motion_effect == "pan_left":
            zp = f"zoompan=z='1.10':x='if(lte(on,1),0,min(x+0.5,iw-iw/zoom))':y='ih/2-(ih/zoom/2)':d={d_frames}:s={w}x{h}:fps={fps}"
        elif motion_effect == "zoom_out":
            zp = f"zoompan=z='if(lte(on,1),1.15,max(1.0,zoom-0.0012))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d_frames}:s={w}x{h}:fps={fps}"
        elif motion_effect == "pan_right":
            zp = f"zoompan=z='1.10':x='if(lte(on,1),iw-iw/zoom,max(0,x-0.5))':y='ih/2-(ih/zoom/2)':d={d_frames}:s={w}x{h}:fps={fps}"
        else:
            zp = f"zoompan=z='min(zoom+0.0012,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d_frames}:s={w}x{h}:fps={fps}"
        filters.append(zp)

    # 3. Animated scene title badge (fades in during first 0.5s, visible for scene, fades out at end)
    if title and title.strip():
        clean_title = (
            title.strip()
            .replace("\\", "\\\\")
            .replace("'", "\u2019")
            .replace(":", "\\:")
            .replace("%", "\\%")
        )
        font_sz = 36 if is_portrait else 28
        y_pos = 180 if is_portrait else 75
        fade_dur = min(0.5, dur / 4)
        fade_out_start = max(fade_dur, dur - fade_dur)
        alpha_expr = f"if(lte(t,{fade_dur}),t/{fade_dur},if(gte(t,{fade_out_start}),({dur}-t)/{fade_dur},1))"
        dt = (
            f"drawtext=text='{clean_title}':font='Arial':fontcolor=white:fontsize={font_sz}:"
            f"x=(w-tw)/2:y={y_pos}:box=1:boxcolor=black@0.65:boxborderw=10:alpha='{alpha_expr}'"
        )
        filters.append(dt)

    # 4. Subtle ambient lighting particles (moving 2D micro-elements for visual dynamism)
    p1 = "drawbox=x='w/2 + 220*sin(t*1.8)':y='h/2 + 160*cos(t*1.4)':w=4:h=4:color=white@0.20:t=fill"
    p2 = "drawbox=x='w/3 + 190*cos(t*1.5)':y='h/3 + 200*sin(t*1.1)':w=3:h=3:color=white@0.15:t=fill"
    filters.append(p1)
    filters.append(p2)

    # 5. Output standardization
    filters.append("setsar=1")
    filters.append(f"fps={fps}")
    filters.append("format=yuv420p")

    return f"[{idx}:v]" + ",".join(filters) + f"[v{idx}]"
