"""Pipeline orchestrator for BENXAUTOMATION MVP.

Coordinates configuration loading, asset manifest validation,
plugin selection, video rendering, output verification, and ffprobe inspection.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from benxautomation.asset_manifest import LicenseManifest, load_manifest, validate_assets_exist
from benxautomation.config import AppConfig
from benxautomation.errors import AssetError, ManifestError, RenderingError
from benxautomation.logger import get_logger
from benxautomation.renderer.base import RenderResult
from benxautomation.renderer.ffmpeg_utils import probe_file
from benxautomation.renderer.longform_plugin import LongformRendererPlugin
from benxautomation.renderer.shorts_plugin import ShortsRendererPlugin

log = get_logger(__name__)


@dataclass
class PipelineResult:
    """Summary of pipeline execution."""
    shorts_result: Optional[RenderResult] = None
    longform_result: Optional[RenderResult] = None
    shorts_probe: Optional[dict] = None
    longform_probe: Optional[dict] = None


class VideoPipeline:
    """Executes the video automation pipeline."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.shorts_plugin = ShortsRendererPlugin(
            self.config.rendering.shorts,
            ffmpeg_path=self.config.rendering.ffmpeg_path,
        )
        self.longform_plugin = LongformRendererPlugin(
            self.config.rendering.longform,
            ffmpeg_path=self.config.rendering.ffmpeg_path,
        )

    def validate_manifest(self, manifest_path: Path | str, base_dir: Path) -> LicenseManifest:
        """Validate license manifest and check asset existence."""
        manifest = load_manifest(manifest_path)
        missing = validate_assets_exist(manifest, base_dir)
        if missing:
            raise ManifestError(f"Assets listed in manifest are missing on disk: {missing}")
        return manifest

    def run(
        self,
        asset_path: Path,
        output_dir: Path,
        *,
        duration_seconds: Optional[int] = None,
        render_shorts: bool = True,
        render_longform: bool = True,
        manifest_path: Optional[Path] = None,
    ) -> PipelineResult:
        """Run the end-to-end rendering pipeline."""
        if not asset_path.is_file():
            raise AssetError(f"Asset file not found: {asset_path}")

        if manifest_path is not None:
            self.validate_manifest(manifest_path, asset_path.parent)

        output_dir.mkdir(parents=True, exist_ok=True)
        result = PipelineResult()

        if render_shorts:
            shorts_out = output_dir / f"{asset_path.stem}_shorts.mp4"
            log.info("Starting Shorts render to %s", shorts_out)
            res = self.shorts_plugin.render(
                asset_path,
                shorts_out,
                duration_seconds=duration_seconds,
            )
            result.shorts_result = res
            result.shorts_probe = probe_file(
                res.output_path,
                ffprobe_path=self.config.rendering.ffprobe_path,
            )

        if render_longform:
            longform_out = output_dir / f"{asset_path.stem}_longform.mp4"
            log.info("Starting Long-form render to %s", longform_out)
            res = self.longform_plugin.render(
                asset_path,
                longform_out,
                duration_seconds=duration_seconds,
            )
            result.longform_result = res
            result.longform_probe = probe_file(
                res.output_path,
                ffprobe_path=self.config.rendering.ffprobe_path,
            )

        return result
