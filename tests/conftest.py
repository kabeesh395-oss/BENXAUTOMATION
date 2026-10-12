"""Shared test fixtures."""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

import edge_tts
import pytest

from benxautomation.renderer.ffmpeg_utils import ffmpeg_is_available, ffprobe_is_available


# ── Cloud CI Resilience: Handle Bing 403 on Datacenter Runners ─────

_real_edge_tts_save = edge_tts.Communicate.save
_real_edge_tts_init = edge_tts.Communicate.__init__


def _benx_communicate_init(self, text: str, *args, **kwargs) -> None:
    self._benx_text = text
    _real_edge_tts_init(self, text, *args, **kwargs)


edge_tts.Communicate.__init__ = _benx_communicate_init


async def _resilient_edge_tts_save(self, output_path: str) -> None:
    try:
        await _real_edge_tts_save(self, output_path)
    except Exception as exc:
        err_msg = str(exc)
        if (
            "403" in err_msg
            or "WSServerHandshakeError" in err_msg
            or "speech.platform.bing.com" in err_msg
        ):
            from benxautomation.renderer.ffmpeg_utils import find_ffmpeg

            ffmpeg_bin = find_ffmpeg()
            text = getattr(self, "_benx_text", "") or ""
            words = len(text.split()) if text else 10
            # Natural speech is ~130-150 words/min (approx 2.2 words/sec).
            # Size audio slightly below target frame boundary so container padding
            # never exceeds the rendered video stream length.
            target_dur = max(3.0, round(words / 2.0, 2))
            audio_dur = max(2.5, target_dur - 0.40)
            cmd = [
                ffmpeg_bin,
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"anoisesrc=d={audio_dur:.2f}:c=pink:r=24000:a=0.3,volume='if(lt(mod(t,0.4),0.2),1,0.2)'",
                "-t",
                f"{audio_dur:.2f}",
                "-b:a",
                "64k",
                str(output_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return
        raise


edge_tts.Communicate.save = _resilient_edge_tts_save


# ── FFmpeg availability ─────────────────────────────────────────────

HAS_FFMPEG = ffmpeg_is_available()
HAS_FFPROBE = ffprobe_is_available()

skip_no_ffmpeg = pytest.mark.skipif(
    not HAS_FFMPEG,
    reason="FFmpeg is not installed",
)

skip_no_ffprobe = pytest.mark.skipif(
    not HAS_FFPROBE,
    reason="FFprobe is not installed",
)


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture()
def tmp_output(tmp_path: Path) -> Path:
    """Return a clean temporary output directory."""
    out = tmp_path / "output"
    out.mkdir()
    return out


@pytest.fixture()
def sample_image(tmp_path: Path) -> Path:
    """Create a minimal valid BMP image for FFmpeg input.

    This generates a tiny 4x4 uncompressed BMP — no external files needed.
    """
    # 4x4 24-bit BMP, 54-byte header + 48 bytes pixel data = 102 bytes
    import struct

    width, height = 4, 4
    row_size = (width * 3 + 3) & ~3  # rows padded to 4 bytes
    pixel_data_size = row_size * height
    file_size = 54 + pixel_data_size

    header = struct.pack(
        "<2sIHHI",
        b"BM",
        file_size,
        0, 0,
        54,
    )
    info_header = struct.pack(
        "<IiiHHIIiiII",
        40,
        width, height,
        1,    # planes
        24,   # bits per pixel
        0,    # no compression
        pixel_data_size,
        2835, 2835,  # 72 DPI
        0, 0,
    )
    # Blue pixels
    row = b"\xff\x00\x00" * width
    row += b"\x00" * (row_size - width * 3)  # padding
    pixels = row * height

    img_path = tmp_path / "sample.bmp"
    img_path.write_bytes(header + info_header + pixels)
    return img_path


@pytest.fixture()
def sample_config_path(tmp_path: Path) -> Path:
    """Write a minimal valid YAML config and return its path."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        textwrap.dedent("""\
        project_name: "TestProject"
        default_language: "en"
        rendering:
          shorts:
            duration_seconds: 2
          longform:
            duration_seconds: 2
        publishing:
          enabled: false
        assets:
          input_dir: "assets/"
          output_dir: "output/"
        """),
        encoding="utf-8",
    )
    return cfg


@pytest.fixture()
def sample_manifest_path(tmp_path: Path) -> Path:
    """Write a valid license manifest and return its path."""
    manifest = tmp_path / "license_manifest.yaml"
    manifest.write_text(
        textwrap.dedent("""\
        assets:
          - file: "sample.bmp"
            license: "cc0"
            attribution: "Test asset"
        """),
        encoding="utf-8",
    )
    return manifest
