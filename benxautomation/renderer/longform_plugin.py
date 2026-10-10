"""Long-form renderer plugin — generates 16:9 landscape videos."""

from __future__ import annotations

from pathlib import Path

from benxautomation.config import LongformConfig
from benxautomation.errors import AssetError, RenderingError
from benxautomation.logger import get_logger
from benxautomation.renderer.base import RendererPlugin, RenderResult
from benxautomation.renderer.ffmpeg_utils import run_ffmpeg

log = get_logger(__name__)


class LongformRendererPlugin(RendererPlugin):
    """Render a source image/video into a 16:9 landscape MP4.

    Uses FFmpeg to scale/pad the input into a 1920×1080 video
    with a solid background and centered content.
    """

    def __init__(self, config: LongformConfig, *, ffmpeg_path: str = "ffmpeg"):
        self._cfg = config
        self._ffmpeg_path = ffmpeg_path

    @property
    def format_name(self) -> str:
        return "longform_16x9"

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
            "-an",
            str(output_path),
        ]

        log.info("Rendering long-form %dx%d, %ds → %s", w, h, dur, output_path)
        run_ffmpeg(args, ffmpeg_path=self._ffmpeg_path)

        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RenderingError(f"Render produced empty output: {output_path}")

        return RenderResult(
            output_path=output_path,
            width=w,
            height=h,
            duration_seconds=float(dur),
            format_name=self.format_name,
        )
