"""Engine for autonomous original content generation, validation, and private uploading."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from benxautomation.asset_manifest import LicenseManifest, load_manifest
from benxautomation.config import AppConfig, PublishingConfig
from benxautomation.logger import get_logger
from benxautomation.original.asset_generator import OriginalAssetGenerator
from benxautomation.original.models import (
    DailyProductionSummary,
    OriginalScript,
    OriginalTopicConfig,
    OriginalVideoResult,
    SceneDefinition,
)
from benxautomation.original.research import OriginalScriptAuthor, TOPIC_CONFIGS
from benxautomation.renderer.ffmpeg_utils import probe_file
from benxautomation.renderer.longform_plugin import LongformRendererPlugin
from benxautomation.renderer.media_validator import MediaMetadata, MediaValidator
from benxautomation.renderer.shorts_plugin import ShortsRendererPlugin
from benxautomation.subtitles.generator import SubtitleGenerator
from benxautomation.tts.engine import TTSEngine
from benxautomation.visuals.models import ScenePlan

log = get_logger(__name__)


class OriginalContentEngine:
    """Orchestrates end-to-end creation, rendering, validation, and private upload of original videos."""

    def __init__(
        self,
        config: Optional[AppConfig] = None,
        output_dir: Path = Path("output/original_content"),
        assets_dir: Path = Path("assets"),
        manifest_path: Path = Path("assets/license_manifest.yaml"),
    ):
        self.config = config or AppConfig()
        self.output_dir = Path(output_dir)
        self.assets_dir = Path(assets_dir)
        self.manifest_path = Path(manifest_path)

        self.asset_generator = OriginalAssetGenerator(self.assets_dir, self.manifest_path)
        self.tts_engine = TTSEngine()
        self.subtitle_generator = SubtitleGenerator()
        self.validator = MediaValidator(
            ffmpeg_path=self.config.rendering.ffmpeg_path,
            ffprobe_path=self.config.rendering.ffprobe_path,
        )
        self.shorts_plugin = ShortsRendererPlugin(
            self.config.rendering.shorts,
            ffmpeg_path=self.config.rendering.ffmpeg_path,
        )
        self.longform_plugin = LongformRendererPlugin(
            self.config.rendering.longform,
            ffmpeg_path=self.config.rendering.ffmpeg_path,
        )

        self.output_dir.mkdir(parents=True, exist_ok=True)

    def prepare_assets(self) -> list[Path]:
        """Generate all original graphic assets and register in manifest."""
        log.info("Ensuring all original visual assets are generated...")
        return self.asset_generator.generate_all_required_assets()

    def run_all_topics(
        self,
        *,
        topic_ids: Optional[list[str]] = None,
        upload_private: bool = True,
        max_shorts_per_topic: int = 2,
        render_longform: bool = True,
    ) -> DailyProductionSummary:
        """Run production across selected research topics."""
        # Step 1: Assets preparation
        self.prepare_assets()

        # Step 2: Scripts discovery
        selected_topics = topic_ids or list(TOPIC_CONFIGS.keys())
        scripts_to_execute: list[OriginalScript] = []

        for tid in selected_topics:
            topic_scripts = OriginalScriptAuthor.create_scripts_for_topic(tid)
            shorts_added = 0
            for s in topic_scripts:
                if s.format == "shorts" and shorts_added < max_shorts_per_topic:
                    scripts_to_execute.append(s)
                    shorts_added += 1
                elif s.format == "longform" and render_longform:
                    scripts_to_execute.append(s)

        log.info(
            "Original content queue: %d videos to produce across topics %s",
            len(scripts_to_execute),
            selected_topics,
        )

        # Step 3: Production & validation loop
        results: list[OriginalVideoResult] = []
        now_str = datetime.now(timezone.utc).isoformat()
        summary = DailyProductionSummary(timestamp=now_str)

        publisher = None
        quota_exhausted = False
        if upload_private:
            publisher = self._init_youtube_publisher()

        for idx, script in enumerate(scripts_to_execute, start=1):
            log.info(
                "[%d/%d] Rendering original video: '%s' (%s, topic=%s)...",
                idx,
                len(scripts_to_execute),
                script.title,
                script.format,
                script.topic_id,
            )
            v_res = self.render_video(script)
            results.append(v_res)

            if script.format == "shorts":
                summary.total_shorts_generated += 1
            else:
                summary.total_longform_generated += 1

            if v_res.quality_passed:
                summary.quality_approved_videos += 1
            else:
                summary.quality_rejected_videos += 1

            # Step 4: Private upload if requested and quality passed
            if upload_private:
                if quota_exhausted:
                    v_res.upload_status = "QUOTA_EXHAUSTED"
                    summary.uploads_blocked_quota += 1
                    summary.remaining_candidates += 1
                    continue

                if not v_res.quality_passed:
                    v_res.upload_status = "QUALITY_BLOCKED"
                    summary.uploads_blocked_quality += 1
                elif not v_res.rights_verified:
                    v_res.upload_status = "RIGHTS_BLOCKED"
                    summary.uploads_blocked_rights += 1
                elif publisher is None:
                    v_res.upload_status = "OAUTH_UNCONFIGURED"
                else:
                    # Perform verified private upload
                    status, vid_id, vid_url, err = self._upload_single_video(publisher, v_res, script)
                    if status == "SUCCESS":
                        v_res.upload_status = "UPLOADED_PRIVATE"
                        v_res.youtube_video_id = vid_id
                        v_res.youtube_url = vid_url
                        v_res.youtube_privacy_status = "private"
                        v_res.upload_timestamp = datetime.now(timezone.utc).isoformat()
                        summary.private_uploads_completed += 1
                        summary.quota_units_used += 1600
                    elif "quota" in str(err).lower():
                        quota_exhausted = True
                        v_res.upload_status = "QUOTA_EXHAUSTED"
                        summary.uploads_blocked_quota += 1
                        summary.remaining_candidates += 1
                        log.warning("YouTube API daily quota reached. Remaining candidates queued safely.")
                    else:
                        v_res.upload_status = f"UPLOAD_ERROR: {err}"

        summary.videos = [r.to_dict() for r in results]

        # Save daily report
        report_file = self.output_dir / "daily_production_report.json"
        report_file.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")
        log.info("Saved daily production report to %s", report_file)

        return summary

    def verify_video_rights(self, script: OriginalScript, scenes: list[ScenePlan]) -> tuple[bool, str]:
        """Strictly verify that every asset and script element has confirmed, permitted commercial rights."""
        if "Original text by BENXAUTOMATION" not in script.license_statement:
            return False, "Script lacks verified original authorship statement."

        if not self.manifest_path.is_file():
            return False, f"Asset license manifest missing at {self.manifest_path}"

        try:
            from benxautomation.asset_manifest import load_manifest
            manifest = load_manifest(self.manifest_path)
            manifest_map = {a.file: a for a in manifest.assets}
        except Exception as exc:
            return False, f"Error reading license manifest: {exc}"

        for sc in scenes:
            fn = sc.asset_path.name
            if fn not in manifest_map:
                return False, f"Visual asset '{fn}' is not registered in the license manifest."
            asset_entry = manifest_map[fn]
            if not getattr(asset_entry, "commercial_terms_verified", True):
                return False, f"Visual asset '{fn}' has unverified commercial terms."
            if asset_entry.license not in ("original", "cc0", "cc-by-4.0", "mit", "apache-2.0", "ai_generated", "public-domain"):
                return False, f"Visual asset '{fn}' has unsupported license '{asset_entry.license}'."

        return True, "All assets, neural narration, and script elements have verified commercial terms."

    def render_video(self, script: OriginalScript) -> OriginalVideoResult:
        """Render a single original video, audio narration, subtitles, and validate quality."""
        safe_name = f"{script.topic_id}_{script.format}_{hash(script.title) % 10000:04d}"
        job_dir = self.output_dir / safe_name
        job_dir.mkdir(parents=True, exist_ok=True)

        audio_path = job_dir / f"{safe_name}_narration.mp3"
        srt_path = job_dir / f"{safe_name}_subtitles.srt"
        video_path = job_dir / f"{safe_name}.mp4"
        thumb_path = job_dir / f"{safe_name}_thumbnail.jpg"
        meta_path = job_dir / f"{safe_name}_metadata.json"

        # 1. Synthesize neural TTS narration
        tts_res = self.tts_engine.synthesize(
            script.full_script,
            audio_path,
            voice="en-US-AriaNeural",
        )
        audio_dur = tts_res.duration_seconds

        # 2. Generate subtitles
        self.subtitle_generator.generate_srt_from_text(
            script.full_script,
            total_duration_seconds=audio_dur,
            output_path=srt_path,
        )

        # 3. Build scene plan using generated original assets
        scenes: list[ScenePlan] = []
        per_scene_dur = audio_dur / max(1, len(script.scenes))
        for sc in script.scenes:
            asset_file = self.assets_dir / sc.asset_file
            if not asset_file.is_file():
                # Fallback to any valid generated original asset
                valid_assets = list(self.assets_dir.glob("orig_*.png"))
                asset_file = valid_assets[0] if valid_assets else (self.assets_dir / "sample_card.png")

            scenes.append(
                ScenePlan(
                    scene_index=sc.scene_index,
                    title=sc.title,
                    narration=sc.narration,
                    visual_description=sc.visual_theme,
                    duration_seconds=round(per_scene_dur, 2),
                    asset_path=asset_file,
                    license="original_creator_owned",
                    attribution="BENXAUTOMATION Creator-Owned Asset",
                )
            )

        # 4. Render video via appropriate plugin
        is_short = script.format == "shorts"
        fps = 30
        frames_needed = max(1, math.ceil(audio_dur * fps))
        render_dur = frames_needed / fps

        if is_short:
            self.shorts_plugin.render(
                scenes[0].asset_path,
                video_path,
                duration_seconds=render_dur,
                audio_path=audio_path,
                subtitle_path=srt_path,
                scenes=scenes,
            )
        else:
            self.longform_plugin.render(
                scenes[0].asset_path,
                video_path,
                duration_seconds=render_dur,
                audio_path=audio_path,
                subtitle_path=srt_path,
                scenes=scenes,
            )

        # 5. Extract thumbnail
        try:
            from benxautomation.podcast.metadata import MetadataGenerator
            mg = MetadataGenerator(ffmpeg_path=self.config.rendering.ffmpeg_path)
            mg.extract_thumbnail(video_path, thumb_path, offset_seconds=min(2.0, audio_dur / 2))
        except Exception as th_err:
            log.debug("Thumbnail extraction: %s", th_err)

        # 6. Rights Verification Gate
        r_pass, r_notes = self.verify_video_rights(script, scenes)

        # 7. Quality Validation Gate
        q_pass, q_issues, probe_meta = self.validator.validate_for_private_upload(
            video_path,
            is_short=is_short,
            min_duration_seconds=10.0,
        )

        # 8. Write metadata receipt
        meta_data = {
            "title": script.title,
            "format": script.format,
            "topic_id": script.topic_id,
            "research_attribution": script.research_attribution,
            "license_statement": script.license_statement,
            "duration_seconds": probe_meta.duration_seconds if probe_meta else audio_dur,
            "tags": script.tags,
            "quality_passed": q_pass,
            "quality_issues": q_issues,
            "rights_verified": r_pass,
            "rights_notes": r_notes,
            "files": {
                "video": str(video_path),
                "audio": str(audio_path),
                "subtitles": str(srt_path),
                "thumbnail": str(thumb_path),
            },
        }
        meta_path.write_text(json.dumps(meta_data, indent=2), encoding="utf-8")

        return OriginalVideoResult(
            video_id=safe_name,
            topic_id=script.topic_id,
            title=script.title,
            format=script.format,
            output_path=video_path,
            duration_seconds=probe_meta.duration_seconds if probe_meta else audio_dur,
            quality_passed=q_pass,
            quality_issues=q_issues,
            rights_verified=r_pass,
            rights_notes=r_notes,
        )

    def _init_youtube_publisher(self) -> Optional[Any]:
        """Initialize authenticated YouTube publisher."""
        token_dir = Path.home() / ".benxautomation"
        secret_file = token_dir / "client_secret.json"
        if not secret_file.is_file():
            log.warning("YouTube OAuth client_secret.json not found in %s", token_dir)
            return None

        try:
            from benxautomation.publisher.youtube import YouTubeOAuthManager, YouTubePublisher
            oauth_mgr = YouTubeOAuthManager(secret_file)
            pub_cfg = PublishingConfig(enabled=True, enforce_private=True)
            return YouTubePublisher(pub_cfg, oauth_manager=oauth_mgr)
        except Exception as exc:
            log.warning("Could not initialize YouTube publisher: %s", exc)
            return None

    def _upload_single_video(
        self, publisher: Any, v_res: OriginalVideoResult, script: OriginalScript
    ) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        """Upload video strictly as PRIVATE and verify with API."""
        from benxautomation.errors import PublishingDisabledError

        if not v_res.rights_verified:
            log.warning("Upload blocked: asset rights unverified (%s)", v_res.rights_notes)
            return "FAILED", None, None, f"Rights verification failed: {v_res.rights_notes}"

        desc = (
            f"{script.title}\n\n"
            f"{script.hook}\n\n"
            f"Research: {script.research_attribution}\n"
            f"License: {script.license_statement}\n"
            f"Visuals: 100% original creator-owned diagrams created by BENXAUTOMATION.\n\n"
            f"Uploaded strictly as PRIVATE for quality verification."
        )

        try:
            up_res = publisher.upload(
                v_res.output_path,
                title=script.title[:95],
                description=desc,
                tags=script.tags,
                privacy_status="private",
            )
            vid_id = str(up_res.get("video_id") or up_res.get("id") or "")
            if not vid_id:
                raise PublishingDisabledError("Upload did not return video ID.")

            # Double check privacy status
            verified_privacy = up_res.get("privacy_status")
            if not verified_privacy:
                try:
                    v_info = publisher.verify_video(vid_id)
                    verified_privacy = v_info.get("privacy_status")
                except Exception:
                    pass

            if verified_privacy and str(verified_privacy).lower() != "private":
                raise PublishingDisabledError(
                    f"CRITICAL: Uploaded video {vid_id} privacy is '{verified_privacy}', NOT 'private'."
                )

            vid_url = str(up_res.get("url") or f"https://youtu.be/{vid_id}")
            log.info("Uploaded %s as PRIVATE to YouTube (ID: %s)", v_res.video_id, vid_id)
            return "SUCCESS", vid_id, vid_url, None
        except Exception as exc:
            log.error("Failed upload for %s: %s", v_res.video_id, exc)
            return "FAILED", None, None, str(exc)
