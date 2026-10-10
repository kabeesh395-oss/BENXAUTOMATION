"""Pipeline orchestrator for BENXAUTOMATION.

Coordinates script generation, visual scene planning, asset manifest validation,
TTS audio narration, background music mixing, subtitle generation, multi-scene
video rendering, media validation, and automated quality reporting.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from benxautomation.asset_manifest import LicenseManifest, load_manifest, validate_assets_exist
from benxautomation.config import AppConfig
from benxautomation.errors import (
    AssetError,
    ManifestError,
    RenderingError,
    ScenePlanningError,
    ScriptGenerationError,
)
from benxautomation.logger import get_logger
from benxautomation.renderer.base import RenderResult
from benxautomation.renderer.ffmpeg_utils import mix_narration_with_bgm
from benxautomation.renderer.longform_plugin import LongformRendererPlugin
from benxautomation.renderer.media_validator import MediaMetadata, MediaValidator
from benxautomation.renderer.shorts_plugin import ShortsRendererPlugin
from benxautomation.script import ScriptRequest, ScriptResult, get_script_provider
from benxautomation.subtitles.generator import SubtitleGenerator
from benxautomation.tts.engine import TTSEngine
from benxautomation.visuals import ScenePlan, ScenePlanner, VisualPlan

log = get_logger(__name__)


@dataclass
class PipelineResult:
    """Summary of pipeline execution."""
    shorts_result: Optional[RenderResult] = None
    longform_result: Optional[RenderResult] = None
    shorts_metadata: Optional[MediaMetadata] = None
    longform_metadata: Optional[MediaMetadata] = None
    audio_path: Optional[Path] = None
    narration_path: Optional[Path] = None
    bgm_path: Optional[Path] = None
    subtitle_path: Optional[Path] = None
    script_path: Optional[Path] = None
    scene_plan_path: Optional[Path] = None
    quality_report_path: Optional[Path] = None
    script_result: Optional[ScriptResult] = None
    visual_plan: Optional[VisualPlan] = None
    success: bool = True


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

    def _resolve_bgm(self, custom_bgm: Optional[Path]) -> Optional[Path]:
        """Find a valid background music track if available."""
        if custom_bgm and Path(custom_bgm).is_file():
            return Path(custom_bgm)

        if self.config.audio.default_bgm_path:
            p = Path(self.config.audio.default_bgm_path)
            if p.is_file():
                return p

        # Check assets/bgm directory
        bgm_dir = Path(self.config.assets.input_dir) / "bgm"
        if bgm_dir.is_dir():
            for ext in ("*.mp3", "*.wav", "*.m4a", "*.aac"):
                tracks = list(bgm_dir.glob(ext))
                if tracks:
                    return tracks[0]

        return None

    def run(
        self,
        asset_path: Optional[Path] = None,
        output_dir: Path = Path("output"),
        *,
        topic: Optional[str] = None,
        script_text: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        render_shorts: bool = True,
        render_longform: bool = True,
        manifest_path: Optional[Path] = None,
        enable_subtitles: bool = True,
        enable_music: bool = True,
        bgm_path: Optional[Path] = None,
        voice_name: Optional[str] = None,
        language: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> PipelineResult:
        """Run the end-to-end video pipeline."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        result = PipelineResult()

        # Validate input asset or manifest if specified
        base_assets_dir = Path(self.config.assets.input_dir)
        if asset_path is not None:
            asset_path = Path(asset_path)
            if not asset_path.is_file():
                raise AssetError(f"Asset file not found: {asset_path}")

        manifest: Optional[LicenseManifest] = None
        if manifest_path is not None:
            manifest_base = asset_path.parent if asset_path else base_assets_dir
            manifest = self.validate_manifest(manifest_path, manifest_base)
        elif self.config.assets.license_manifest:
            man_p = Path(self.config.assets.license_manifest)
            if man_p.is_file():
                manifest = self.validate_manifest(man_p, base_assets_dir)

        # ── 1. Script Determination & Generation ────────────────────────
        script_res: Optional[ScriptResult] = None
        target_lang = language or self.config.default_language
        target_dur = duration_seconds or self.config.rendering.shorts.duration_seconds

        if script_text:
            # Manual script takes explicit precedence
            log.info("Using provided manual script text (%d chars)...", len(script_text))
            fallback_provider = get_script_provider("fallback", manual_text=script_text)
            script_res = fallback_provider.generate_script(
                ScriptRequest(
                    topic=topic or "Manual Narration",
                    language=target_lang,
                    duration_seconds=target_dur,
                )
            )
        elif topic:
            # Topic provided: trigger real AI script generation or configured provider
            p_name = provider_name or self.config.script.provider
            log.info("Generating script for topic '%s' via provider '%s'...", topic, p_name)
            provider = get_script_provider(p_name, config=self.config.script)
            script_res = provider.generate_script(
                ScriptRequest(
                    topic=topic,
                    language=target_lang,
                    duration_seconds=target_dur,
                )
            )
        elif asset_path:
            # No script or topic: silent or asset-only mode (for backwards compatibility)
            script_res = None
        else:
            raise ScriptGenerationError(
                "Either --topic or --script must be provided for video automation."
            )

        if script_res:
            result.script_result = script_res
            # Save script to output
            stem_name = asset_path.stem if asset_path else "video"
            script_out = output_dir / f"{stem_name}_script.json"
            script_dict = {
                "topic": script_res.topic,
                "provider": script_res.provider,
                "model": script_res.model,
                "is_ai_generated": script_res.is_ai_generated,
                "language": script_res.language,
                "estimated_duration_seconds": script_res.estimated_duration_seconds,
                "full_script": script_res.full_script,
                "scenes": [
                    {
                        "scene_index": s.scene_index,
                        "title": s.title,
                        "narration": s.narration,
                        "visual_description": s.visual_description,
                        "estimated_duration_seconds": s.estimated_duration_seconds,
                    }
                    for s in script_res.scenes
                ],
            }
            script_out.write_text(json.dumps(script_dict, indent=2), encoding="utf-8")
            result.script_path = script_out
            log.info("Saved script to %s (AI=%s)", script_out, script_res.is_ai_generated)

        # ── 2. Narration Synthesis (TTS) ───────────────────────────────
        narration_path: Optional[Path] = None
        subtitle_path: Optional[Path] = None
        actual_audio_dur = float(target_dur)

        if script_res and script_res.full_script:
            stem_name = asset_path.stem if asset_path else "video"
            audio_out = output_dir / f"{stem_name}_narration.mp3"
            log.info("Synthesizing audio narration via TTS...")
            audio_res = self.tts_engine.synthesize(
                script_res.full_script,
                audio_out,
                voice=voice_name,
            )
            narration_path = audio_res.file_path
            result.narration_path = narration_path
            actual_audio_dur = audio_res.duration_seconds
            log.info("Synthesized narration duration: %.2fs", actual_audio_dur)

            # ── 3. Subtitles Generation ─────────────────────────────────
            if enable_subtitles:
                sub_out = output_dir / f"{stem_name}_subtitles.srt"
                self.subtitle_generator.generate_srt_from_text(
                    script_res.full_script,
                    total_duration_seconds=actual_audio_dur,
                    output_path=sub_out,
                )
                subtitle_path = sub_out
                result.subtitle_path = subtitle_path
                log.info("Generated subtitles aligned to voiceover: %s", sub_out)

        # ── 4. Background Music Mixing ──────────────────────────────────
        final_audio_path = narration_path
        if narration_path and enable_music and self.config.audio.music_enabled:
            resolved_bgm = self._resolve_bgm(bgm_path)
            if resolved_bgm:
                stem_name = asset_path.stem if asset_path else "video"
                mixed_out = output_dir / f"{stem_name}_mixed_audio.mp3"
                try:
                    log.info("Mixing narration with background music (%s)...", resolved_bgm.name)
                    mix_narration_with_bgm(
                        narration_path,
                        resolved_bgm,
                        mixed_out,
                        bgm_volume=self.config.audio.music_volume,
                        ffmpeg_path=self.config.rendering.ffmpeg_path,
                    )
                    final_audio_path = mixed_out
                    result.bgm_path = resolved_bgm
                except Exception as exc:
                    log.warning("Background music mixing failed (%s); using voiceover only", exc)
                    final_audio_path = narration_path
        result.audio_path = final_audio_path

        # Ensure video duration matches exact frames needed to cover narration without premature truncation
        fps = self.config.rendering.shorts.fps
        frames_needed = max(1, math.ceil(actual_audio_dur * fps))
        audio_frame_duration = frames_needed / fps
        calc_duration = max(float(duration_seconds or 0), audio_frame_duration)

        # ── 5. Visual Planning ──────────────────────────────────────────
        scenes_to_render: Optional[list[ScenePlan]] = None
        if script_res and script_res.scenes:
            planner = ScenePlanner(
                assets_dir=base_assets_dir,
                manifest=manifest,
                fallback_asset=asset_path,
            )
            visual_plan = planner.plan_visuals(
                script_res,
                total_audio_duration=actual_audio_dur,
                fps=fps,
                single_asset_override=asset_path if (not manifest and asset_path) else None,
            )
            result.visual_plan = visual_plan
            scenes_to_render = visual_plan.scenes
            calc_duration = max(calc_duration, visual_plan.total_duration_seconds)

            stem_name = asset_path.stem if asset_path else "video"
            plan_out = output_dir / f"{stem_name}_scene_plan.json"
            plan_data = [
                {
                    "scene_index": sp.scene_index,
                    "title": sp.title,
                    "duration_seconds": sp.duration_seconds,
                    "asset": str(sp.asset_path),
                    "visual_description": sp.visual_description,
                    "license": sp.license,
                    "attribution": sp.attribution,
                }
                for sp in visual_plan.scenes
            ]
            plan_out.write_text(json.dumps(plan_data, indent=2), encoding="utf-8")
            result.scene_plan_path = plan_out
            log.info("Saved visual scene plan to %s", plan_out)

        # Default fallback asset for legacy single-input renderer if no scenes planned
        primary_input_asset = (
            asset_path
            if asset_path
            else (scenes_to_render[0].asset_path if scenes_to_render else None)
        )
        if primary_input_asset is None:
            raise AssetError("No visual asset available for video rendering.")

        stem_name = asset_path.stem if asset_path else "video"

        # ── 6. Render Shorts (9:16) ─────────────────────────────────────
        if render_shorts:
            shorts_out = output_dir / f"{stem_name}_shorts.mp4"
            log.info("Rendering Shorts video to %s", shorts_out)
            res = self.shorts_plugin.render(
                primary_input_asset,
                shorts_out,
                duration_seconds=calc_duration,
                audio_path=final_audio_path,
                subtitle_path=subtitle_path,
                scenes=scenes_to_render,
            )
            result.shorts_result = res
            result.shorts_metadata = self.validator.inspect(res.output_path)

        # ── 7. Render Long-form (16:9) ──────────────────────────────────
        if render_longform:
            longform_out = output_dir / f"{stem_name}_longform.mp4"
            log.info("Rendering Long-form video to %s", longform_out)
            res = self.longform_plugin.render(
                primary_input_asset,
                longform_out,
                duration_seconds=calc_duration,
                audio_path=final_audio_path,
                subtitle_path=subtitle_path,
                scenes=scenes_to_render,
            )
            result.longform_result = res
            result.longform_metadata = self.validator.inspect(res.output_path)

        # ── 8. Quality Report Generation ───────────────────────────────
        report_out = output_dir / f"{stem_name}_quality_report.json"
        report_data = {
            "success": True,
            "topic": topic,
            "script_source": script_res.provider if script_res else "none",
            "is_ai_generated": script_res.is_ai_generated if script_res else False,
            "narration_duration_seconds": actual_audio_dur if narration_path else 0.0,
            "rendered_duration_seconds": calc_duration,
            "subtitles_enabled": bool(subtitle_path),
            "music_mixed": bool(result.bgm_path),
            "shorts": {
                "path": str(result.shorts_result.output_path) if result.shorts_result else None,
                "width": result.shorts_metadata.width if result.shorts_metadata else None,
                "height": result.shorts_metadata.height if result.shorts_metadata else None,
                "duration": result.shorts_metadata.duration_seconds if result.shorts_metadata else None,
                "playable": result.shorts_metadata.is_playable if result.shorts_metadata else None,
                "has_audio": result.shorts_metadata.has_audio if result.shorts_metadata else None,
            } if result.shorts_result else None,
            "longform": {
                "path": str(result.longform_result.output_path) if result.longform_result else None,
                "width": result.longform_metadata.width if result.longform_metadata else None,
                "height": result.longform_metadata.height if result.longform_metadata else None,
                "duration": result.longform_metadata.duration_seconds if result.longform_metadata else None,
                "playable": result.longform_metadata.is_playable if result.longform_metadata else None,
                "has_audio": result.longform_metadata.has_audio if result.longform_metadata else None,
            } if result.longform_result else None,
        }
        report_out.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        result.quality_report_path = report_out
        log.info("Generated quality report at %s", report_out)

        return result
