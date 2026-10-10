"""Pipeline orchestrator for BENXAUTOMATION.

Coordinates configuration loading, asset manifest validation, TTS audio narration,
subtitle generation, plugin rendering, and media validation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from benxautomation.asset_manifest import LicenseManifest, load_manifest, validate_assets_exist
from benxautomation.config import AppConfig
from benxautomation.errors import AssetError, ManifestError, RenderingError
from benxautomation.logger import get_logger
from benxautomation.renderer.base import RenderResult
from benxautomation.renderer.longform_plugin import LongformRendererPlugin
from benxautomation.renderer.media_validator import MediaMetadata, MediaValidator
from benxautomation.renderer.shorts_plugin import ShortsRendererPlugin
from benxautomation.subtitles.generator import SubtitleGenerator
from benxautomation.tts.engine import TTSEngine

log = get_logger(__name__)


@dataclass
class PipelineResult:
    """Summary of pipeline execution."""
    shorts_result: Optional[RenderResult] = None
    longform_result: Optional[RenderResult] = None
    shorts_metadata: Optional[MediaMetadata] = None
    longform_metadata: Optional[MediaMetadata] = None
    audio_path: Optional[Path] = None
    subtitle_path: Optional[Path] = None


class VideoPipeline:
    """Executes the end-to-end video automation pipeline."""

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
        self.tts_engine = TTSEngine()
        self.subtitle_generator = SubtitleGenerator()
        self.validator = MediaValidator(
            ffmpeg_path=self.config.rendering.ffmpeg_path,
            ffprobe_path=self.config.rendering.ffprobe_path,
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
        script_text: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        render_shorts: bool = True,
        render_longform: bool = True,
        manifest_path: Optional[Path] = None,
        enable_subtitles: bool = True,
        voice_name: Optional[str] = None,
    ) -> PipelineResult:
        """Run the end-to-end video pipeline."""
        if not asset_path.is_file():
            raise AssetError(f"Asset file not found: {asset_path}")

        if manifest_path is not None:
            self.validate_manifest(manifest_path, asset_path.parent)

        output_dir.mkdir(parents=True, exist_ok=True)
        result = PipelineResult()

        audio_path: Optional[Path] = None
        subtitle_path: Optional[Path] = None
        calc_duration = duration_seconds

        # 1. Synthesize audio narration if script text provided
        if script_text:
            audio_out = output_dir / f"{asset_path.stem}_narration.mp3"
            log.info("Generating voiceover for script...")
            audio_res = self.tts_engine.synthesize(
                script_text,
                audio_out,
                voice=voice_name,
            )
            audio_path = audio_res.file_path
            result.audio_path = audio_path
            calc_duration = max(calc_duration or 0, int(math.ceil(audio_res.duration_seconds)))

            # 2. Generate subtitles aligned to voiceover
            if enable_subtitles:
                sub_out = output_dir / f"{asset_path.stem}_subtitles.srt"
                self.subtitle_generator.generate_srt_from_text(
                    script_text,
                    total_duration_seconds=float(audio_res.duration_seconds),
                    output_path=sub_out,
                )
                subtitle_path = sub_out
                result.subtitle_path = subtitle_path

        # 3. Render Shorts (9:16)
        if render_shorts:
            shorts_out = output_dir / f"{asset_path.stem}_shorts.mp4"
            log.info("Rendering Shorts video to %s", shorts_out)
            res = self.shorts_plugin.render(
                asset_path,
                shorts_out,
                duration_seconds=calc_duration,
                audio_path=audio_path,
                subtitle_path=subtitle_path,
            )
            result.shorts_result = res
            result.shorts_metadata = self.validator.inspect(res.output_path)

        # 4. Render Long-form (16:9)
        if render_longform:
            longform_out = output_dir / f"{asset_path.stem}_longform.mp4"
            log.info("Rendering Long-form video to %s", longform_out)
            res = self.longform_plugin.render(
                asset_path,
                longform_out,
                duration_seconds=calc_duration,
                audio_path=audio_path,
                subtitle_path=subtitle_path,
            )
            result.longform_result = res
            result.longform_metadata = self.validator.inspect(res.output_path)

        return result
