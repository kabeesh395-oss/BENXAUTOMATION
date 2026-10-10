"""Shared test fixtures."""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

import pytest

from benxautomation.renderer.ffmpeg_utils import ffmpeg_is_available, ffprobe_is_available


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
