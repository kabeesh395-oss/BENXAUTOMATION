"""Pipeline orchestrator for BENXAUTOMATION.

Coordinates script generation, visual scene planning, asset manifest validation,
TTS audio narration, background music mixing, subtitle generation, multi-scene
video rendering, media validation, and automated quality reporting.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
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
    quality_report: Optional[dict] = None
    script_result: Optional[ScriptResult] = None
    visual_plan: Optional[VisualPlan] = None
    render_success: bool = True
    content_quality_passed: bool = True
    quality_issues: list[str] = field(default_factory=list)
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
                "research_sources": script_res.research_sources,
                "facts_count": script_res.facts_count,
                "scenes": [
                    {
                        "scene_index": s.scene_index,
                        "title": s.title,
                        "narration": s.narration,
                        "visual_description": s.visual_description,
                        "estimated_duration_seconds": s.estimated_duration_seconds,
                        "fact_number": s.fact_number,
                        "fact_title": s.fact_title,
                        "source": s.source,
                        "source_url": s.source_url,
                    }
                    for s in script_res.scenes
                ],
            }
            script_out.write_text(json.dumps(script_dict, indent=2), encoding="utf-8")
            result.script_path = script_out
            log.info("Saved script to %s (AI=%s, scenes=%d)", script_out, script_res.is_ai_generated, len(script_res.scenes))

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
        self.generate_quality_report(
            result=result,
            output_dir=output_dir,
            stem_name=stem_name,
            topic=topic,
            script_text=script_text,
            render_shorts=render_shorts,
            render_longform=render_longform,
            calc_duration=calc_duration,
            actual_audio_dur=actual_audio_dur,
            has_subtitles=bool(subtitle_path),
        )

        return result

    def evaluate_quality(
        self,
        result: PipelineResult,
        topic: Optional[str] = None,
        script_text: Optional[str] = None,
        render_shorts: bool = True,
        render_longform: bool = True,
    ) -> tuple[bool, bool, list[str], list[str]]:
        """Evaluate render file validity and script content adequacy separately.

        Returns:
            (render_success, content_quality_passed, render_issues, content_issues)
        """
        render_issues: list[str] = []
        content_issues: list[str] = []

        # ── 1. Evaluate Render & File Validity ──
        rendered_any = False
        if render_shorts:
            rendered_any = True
            if not result.shorts_result or not result.shorts_result.output_path.is_file():
                render_issues.append("Shorts output file is missing on disk.")
            elif not result.shorts_metadata:
                render_issues.append("Shorts metadata inspection is missing.")
            elif not result.shorts_metadata.has_video:
                render_issues.append("Shorts output contains no video stream.")
            elif not result.shorts_metadata.is_playable:
                render_issues.append("Shorts output failed playability decode check.")

        if render_longform:
            rendered_any = True
            if not result.longform_result or not result.longform_result.output_path.is_file():
                render_issues.append("Longform output file is missing on disk.")
            elif not result.longform_metadata:
                render_issues.append("Longform metadata inspection is missing.")
            elif not result.longform_metadata.has_video:
                render_issues.append("Longform output contains no video stream.")
            elif not result.longform_metadata.is_playable:
                render_issues.append("Longform output failed playability decode check.")

        if not rendered_any:
            render_issues.append("No video format was selected for rendering.")

        render_success = len(render_issues) == 0

        # ── 2. Evaluate Script Content Adequacy ──
        if not topic and not script_text and not result.script_result:
            # Silent asset-only render mode without script or topic
            content_quality_passed = True
        else:
            script_res = result.script_result
            if not script_res or not script_res.full_script.strip():
                content_issues.append("Script narration is missing or empty.")
            else:
                full_script = script_res.full_script
                script_text_clean = re.sub(r"[^\w\s]", "", full_script).strip().lower()
                topic_clean = re.sub(r"[^\w\s]", "", topic or "").strip().lower()

                # Narration merely repeating the topic string
                if topic_clean and script_text_clean == topic_clean:
                    content_issues.append(
                        "Script narration merely repeats the topic string without elaboration."
                    )

                # Excessive topic repetition across scenes
                if topic and len(topic.strip()) >= 5:
                    topic_escaped = re.escape(topic.strip().rstrip(".!?"))
                    topic_mentions = len(re.findall(topic_escaped, full_script, re.IGNORECASE))
                    if topic_mentions >= 3:
                        content_issues.append(
                            f"Excessive topic repetition: topic phrase appears {topic_mentions} times across scenes."
                        )

                # Generic template filler phrases
                generic_filler_patterns = [
                    r"foundational background and core themes",
                    r"understanding the foundational background",
                    r"this offline template (outlines|introduces)",
                    r"offline template outline",
                    r"key discussion areas for this (topic|subject)",
                    r"starting framework for (further )?research",
                    r"framework for research and content creation",
                    r"analyzing multiple perspectives, related evidence",
                    r"this is an unverified research outline",
                    r"does not provide the requested verified facts",
                ]
                if any(re.search(pat, full_script, re.IGNORECASE) for pat in generic_filler_patterns):
                    content_issues.append(
                        "Script contains generic template filler phrases rather than substantive content."
                    )

                # Fact-list / counted topic validation
                fact_list_match = re.search(
                    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|top\s+\d+)\s+(surprising\s+)?(facts|reasons|tips|secrets|ways|things|habits|steps)\b",
                    topic or "",
                    re.IGNORECASE,
                )
                if fact_list_match:
                    word_to_num = {
                        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                    }
                    raw_num = fact_list_match.group(1).lower().replace("top ", "").strip()
                    expected_count = int(raw_num) if raw_num.isdigit() else word_to_num.get(raw_num, 5)

                    # Missing list items
                    if len(script_res.scenes) < expected_count:
                        content_issues.append(
                            f"Missing list items: topic requested {expected_count} facts ('{topic}'), "
                            f"but script only provided {len(script_res.scenes)} scene(s)."
                        )

                    # Generic outline rejection
                    is_outline = any(
                        "outline" in s.title.lower() or "template" in s.title.lower()
                        for s in script_res.scenes
                    ) or "offline template" in full_script.lower() or "research outline" in full_script.lower()

                    if is_outline:
                        content_issues.append(
                            f"Topic requests a list of facts/items ('{topic}'), but script provides an unfulfilled generic outline without distinct verified facts."
                        )

                    # Duplicate facts check (titles and narration)
                    seen_titles: list[str] = []
                    for sc in script_res.scenes:
                        t = re.sub(r"^(fact\s*\d+\s*:\s*|scene\s*\d+\s*:\s*)", "", sc.title, flags=re.IGNORECASE).strip().lower()
                        t = re.sub(r"[^\w\s]", "", t).strip()
                        if t:
                            if t in seen_titles:
                                content_issues.append(f"Duplicate fact title detected: '{sc.title}'.")
                            seen_titles.append(t)

                    for i in range(len(script_res.scenes)):
                        for j in range(i + 1, len(script_res.scenes)):
                            words_i = set(re.findall(r"\b\w{4,}\b", script_res.scenes[i].narration.lower()))
                            words_j = set(re.findall(r"\b\w{4,}\b", script_res.scenes[j].narration.lower()))
                            if words_i and words_j:
                                jaccard = len(words_i & words_j) / len(words_i | words_j)
                                if jaccard > 0.70:
                                    content_issues.append(
                                        f"Duplicate or near-duplicate fact narration detected between Scene {i+1} and Scene {j+1}."
                                    )

                # Empty or near-empty narration in any scene
                for sc in script_res.scenes:
                    if not sc.narration or len(sc.narration.strip().split()) < 3:
                        content_issues.append(f"Scene {sc.scene_index} has empty or insufficient narration.")

                # Offline fallback outline notice
                if (
                    script_res.provider in ("manual_fallback", "fallback")
                    and not script_text
                    and ("unverified" in full_script.lower() or fact_list_match)
                ):
                    msg = "Offline fallback template is an unverified structural outline; verified research or a manual script is required to fulfill the topic."
                    if msg not in content_issues:
                        content_issues.append(msg)

                # Scene breakdown
                if len(script_res.scenes) < 2:
                    content_issues.append(
                        f"Insufficient scene breakdown: got {len(script_res.scenes)} scene(s), minimum 2 required."
                    )

                # Word count check
                words = full_script.split()
                min_words = 6 if script_text else 12
                if len(words) < min_words:
                    content_issues.append(
                        f"Insufficient narration word count: got {len(words)} words, minimum {min_words} required."
                    )

                # ── Topic-to-Scene Consistency Validation ──
                if topic and len(topic.strip()) >= 5:
                    topic_lower = topic.strip().lower()

                    for sc in script_res.scenes:
                        sc_title_clean = re.sub(
                            r"^(fact\s*\d+\s*:\s*|scene\s*\d+\s*:\s*)",
                            "",
                            sc.title,
                            flags=re.IGNORECASE,
                        ).strip().lower()

                        # Check for off-topic domain clash in scene headings
                        is_ocean = any(k in topic_lower for k in ("ocean", "sea", "marine", "underwater", "trench", "abyss"))
                        if is_ocean:
                            off_space = any(w in sc_title_clean for w in ("mars", "moon", "jupiter", "saturn", "galaxy", "asteroid"))
                            on_topic = any(w in sc_title_clean for w in ("ocean", "sea", "water", "marine", "floor", "depth", "earth", "abyss", "trench", "lake", "glow", "creature", "vent", "trash", "pressure", "unmapped", "unexplored"))
                            if off_space and not on_topic:
                                content_issues.append(
                                    f"Inconsistent scene heading: Scene {sc.scene_index} heading '{sc.title}' centers on an unrelated off-topic entity for topic '{topic}'."
                                )

                        is_space = any(k in topic_lower for k in ("solar system", "planet", "galaxy", "mars", "astronomy", "space", "cosmos", "moon"))
                        if is_space:
                            off_ocean = any(w in sc_title_clean for w in ("ocean", "submersible", "coral reef", "jellyfish", "anglerfish"))
                            on_topic = any(w in sc_title_clean for w in ("space", "planet", "orbit", "cosmic", "solar", "star", "crater", "gravity", "atmosphere", "system", "moon"))
                            if off_ocean and not on_topic:
                                content_issues.append(
                                    f"Inconsistent scene heading: Scene {sc.scene_index} heading '{sc.title}' centers on an unrelated off-topic entity for topic '{topic}'."
                                )

                # Scene visual diversity check
                if result.visual_plan and len(result.visual_plan.scenes) > 1:
                    total_sc = len(result.visual_plan.scenes)
                    distinct_sc = result.visual_plan.distinct_assets_count
                    if distinct_sc < total_sc:
                        content_issues.append(
                            f"Visual scene diversity limited: {distinct_sc} distinct assets for {total_sc} scenes "
                            "(some assets repeated due to limited local media pool)."
                        )

            content_quality_passed = len(content_issues) == 0

        return render_success, content_quality_passed, render_issues, content_issues

    def generate_quality_report(
        self,
        result: PipelineResult,
        output_dir: Path,
        stem_name: str,
        topic: Optional[str] = None,
        script_text: Optional[str] = None,
        render_shorts: bool = True,
        render_longform: bool = True,
        calc_duration: float = 0.0,
        actual_audio_dur: float = 0.0,
        has_subtitles: bool = False,
    ) -> dict:
        """Construct, write, and return the structured quality report with separate stage statuses."""
        render_success, content_quality_passed, render_issues, content_issues = self.evaluate_quality(
            result,
            topic=topic,
            script_text=script_text,
            render_shorts=render_shorts,
            render_longform=render_longform,
        )

        script_res = result.script_result

        # Separate stage-specific issue segregation
        script_issues = [
            iss for iss in content_issues
            if "scene breakdown" in iss.lower() or "word count" in iss.lower() or "empty or insufficient" in iss.lower()
        ]
        consistency_issues = [
            iss for iss in content_issues
            if "inconsistent scene heading" in iss.lower() or "off-topic" in iss.lower()
        ]
        research_issues = [
            iss for iss in content_issues
            if iss not in script_issues and "visual scene diversity" not in iss.lower()
        ]

        audio_issues: list[str] = []
        if result.narration_path and result.narration_path.is_file() and result.narration_path.stat().st_size == 0:
            audio_issues.append("Narration audio file is empty (0 bytes).")
        audio_passed = len(audio_issues) == 0

        subtitle_issues: list[str] = []
        if result.subtitle_path and result.subtitle_path.is_file() and result.subtitle_path.stat().st_size == 0:
            subtitle_issues.append("Subtitle file is empty (0 bytes).")
        subtitle_passed = len(subtitle_issues) == 0

        script_passed = bool(script_res and len(script_issues) == 0 and len(content_issues) == 0)
        research_passed = bool(len(research_issues) == 0)
        topic_consistency_passed = bool(len(consistency_issues) == 0)

        fact_list_match = re.search(
            r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|top\s+\d+)\s+(surprising\s+)?(facts|reasons|tips|secrets|ways|things|habits|steps)\b",
            topic or "",
            re.IGNORECASE,
        )
        expected_facts_count = None
        if fact_list_match:
            word_to_num = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            }
            raw_num = fact_list_match.group(1).lower().replace("top ", "").strip()
            expected_facts_count = int(raw_num) if raw_num.isdigit() else word_to_num.get(raw_num, 5)

        recorded_sources = []
        if script_res and script_res.research_sources:
            recorded_sources = [
                s.get("source") for s in script_res.research_sources if s.get("source")
            ]

        script_status = {
            "passed": script_passed,
            "provider": script_res.provider if script_res else "none",
            "model": script_res.model if script_res else None,
            "is_ai_generated": script_res.is_ai_generated if script_res else False,
            "scenes_count": len(script_res.scenes) if script_res else 0,
            "issues": script_issues,
        }

        research_status = {
            "passed": research_passed,
            "is_list_topic": bool(fact_list_match),
            "expected_facts_count": expected_facts_count,
            "actual_facts_count": len(script_res.scenes) if script_res else 0,
            "sources_recorded": recorded_sources,
            "duplicate_facts_detected": any("duplicate" in iss.lower() for iss in content_issues),
            "issues": research_issues,
        }

        topic_consistency_status = {
            "passed": topic_consistency_passed,
            "issues": consistency_issues,
        }

        rendering_status = {
            "passed": render_success,
            "shorts_rendered": bool(result.shorts_result and result.shorts_result.output_path.is_file()),
            "longform_rendered": bool(result.longform_result and result.longform_result.output_path.is_file()),
            "animation_type": result.visual_plan.animation_type if result.visual_plan else "static",
            "is_3d_animation": False,
            "distinct_assets_count": result.visual_plan.distinct_assets_count if result.visual_plan else 0,
            "issues": render_issues,
        }

        audio_status = {
            "passed": audio_passed,
            "narration_duration_seconds": actual_audio_dur if result.narration_path else 0.0,
            "music_mixed": bool(result.bgm_path),
            "issues": audio_issues,
        }

        subtitle_status = {
            "passed": subtitle_passed,
            "subtitles_enabled": bool(result.subtitle_path or has_subtitles),
            "issues": subtitle_issues,
        }

        acceptance_reasons: list[str] = []
        if not render_success:
            acceptance_reasons.append("Media rendering validation failed.")
        if not content_quality_passed:
            acceptance_reasons.append("Script/research content quality validation failed.")
        if not topic_consistency_passed:
            acceptance_reasons.append("Topic-to-scene consistency validation failed.")
        if not audio_passed:
            acceptance_reasons.append("Audio narration validation failed.")
        if not subtitle_passed:
            acceptance_reasons.append("Subtitle validation failed.")

        final_acceptance_passed = len(acceptance_reasons) == 0
        overall_success = final_acceptance_passed

        result.render_success = render_success
        result.content_quality_passed = content_quality_passed
        result.quality_issues = render_issues + content_issues
        result.success = overall_success

        report_data = {
            "success": overall_success,
            "final_acceptance_status": {
                "passed": final_acceptance_passed,
                "reasons": acceptance_reasons if acceptance_reasons else ["All validation gates passed."],
            },
            "script_status": script_status,
            "research_status": research_status,
            "topic_consistency_status": topic_consistency_status,
            "rendering_status": rendering_status,
            "audio_status": audio_status,
            "subtitle_status": subtitle_status,
            "render_success": render_success,
            "content_quality_passed": content_quality_passed,
            "script_adequate": content_quality_passed,
            "quality_issues": result.quality_issues,
            "render_issues": render_issues,
            "content_issues": content_issues,
            "topic": topic,
            "script_source": script_res.provider if script_res else "none",
            "is_ai_generated": script_res.is_ai_generated if script_res else False,
            "narration_duration_seconds": actual_audio_dur if result.narration_path else 0.0,
            "rendered_duration_seconds": calc_duration,
            "subtitles_enabled": bool(result.subtitle_path or has_subtitles),
            "music_mixed": bool(result.bgm_path),
            "visual_scenes": {
                "total_scenes": len(result.visual_plan.scenes) if result.visual_plan else 0,
                "distinct_assets_count": result.visual_plan.distinct_assets_count if result.visual_plan else 0,
                "has_repeated_assets": result.visual_plan.has_repeated_assets if result.visual_plan else False,
                "animation_type": result.visual_plan.animation_type if result.visual_plan else "static",
                "is_3d_animation": False,  # Explicit: 2D camera pan/zoom motion & moving particles; NOT 3D
                "motion_effects_used": [s.motion_effect for s in result.visual_plan.scenes] if result.visual_plan else [],
            },
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
        report_out = output_dir / f"{stem_name}_quality_report.json"
        report_out.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        result.quality_report_path = report_out
        result.quality_report = report_data
        log.info(
            "Generated quality report at %s (overall=%s, script=%s, research=%s, render=%s)",
            report_out,
            overall_success,
            script_passed,
            research_passed,
            render_success,
        )
        return report_data
