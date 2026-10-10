"""Shorts renderer plugin — generates 9:16 portrait videos."""

from __future__ import annotations

from pathlib import Path

from benxautomation.config import ShortsConfig
from benxautomation.errors import AssetError, RenderingError
from benxautomation.logger import get_logger
from benxautomation.renderer.base import RendererPlugin, RenderResult
from benxautomation.renderer.ffmpeg_utils import run_ffmpeg

log = get_logger(__name__)


class ShortsRendererPlugin(RendererPlugin):
    """Render a source image/video into a YouTube Shorts–format MP4.

    Uses FFmpeg to scale/pad the input into a 1080×1920 (9:16) video
    with a solid background and centered content.
    """

    def __init__(self, config: ShortsConfig, *, ffmpeg_path: str = "ffmpeg"):
        self._cfg = config
        self._ffmpeg_path = ffmpeg_path

    @property
    def format_name(self) -> str:
        return "shorts_9x16"

    def render(
        self,
        input_path: Path,
        output_path: Path,
        *,
        duration_seconds: int | None = None,
    ) -> RenderResult:
        if not input_path.is_file():
            raise AssetError(f"Input asset not found: {input_path}")

        dur = duration_seconds or self._cfg.duration_seconds
        w, h = self._cfg.width, self._cfg.height

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build FFmpeg command:
        #   - loop the input image (or trim video) to `dur` seconds
        #   - scale + pad to exact 1080×1920
        #   - encode with libx264 baseline for broad compatibility
        args = [
            "-loop", "1",
            "-i", str(input_path),
            "-t", str(dur),
            "-vf", (
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
            ),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",
            "-r", str(self._cfg.fps),
            "-an",  # no audio for MVP
            str(output_path),
        ]

        log.info("Rendering Shorts %dx%d, %ds → %s", w, h, dur, output_path)
        run_ffmpeg(args, ffmpeg_path=self._ffmpeg_path)

        # Verify output
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RenderingError(f"Render produced empty output: {output_path}")

        return RenderResult(
            output_path=output_path,
            width=w,
            height=h,
            duration_seconds=float(dur),
            format_name=self.format_name,
        )
