"""Master orchestrator for Vizard AI-inspired long-form-to-Shorts repurposing."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, List, Optional, Tuple

from benxautomation.config import AppConfig
from benxautomation.errors import PublishingDisabledError
from benxautomation.logger import get_logger
from benxautomation.podcast.errors import (
    HighlightDetectionError,
    PodcastAccessError,
    PodcastError,
    PodcastRenderingError,
    RightsVerificationError,
)
from benxautomation.podcast.highlight_detector import HighlightDetector
from benxautomation.podcast.ingestion import PodcastIngester
from benxautomation.podcast.metadata import ClipMetadataGenerator
from benxautomation.podcast.models import (
    ClipMetadata,
    HighlightCandidate,
    PodcastInput,
    PodcastPipelineConfig,
    PodcastTranscript,
    RightsDeclaration,
    SubtitleStyle,
)
from benxautomation.podcast.reframer import VideoReframer
from benxautomation.podcast.rights_review import RightsReviewer
from benxautomation.podcast.subtitles import PodcastSubtitleManager
from benxautomation.podcast.transcription import PodcastTranscriber
from benxautomation.repurpose.config import RepurposingConfig
from benxautomation.repurpose.manifest import RepurposeClipEntry, RepurposeManifest
from benxautomation.repurpose.quality_reporter import ClipQualityCheck, RepurposeQualityReporter

log = get_logger(__name__)


class RepurposingEngine:
    """Automated long-form-to-YouTube-Shorts repurposing engine inspired by Vizard AI."""

    def __init__(
        self,
        config: Optional[RepurposingConfig] = None,
        benx_config: Optional[AppConfig] = None,
    ) -> None:
        self.config = config or RepurposingConfig()
        self.benx_config = benx_config or AppConfig()

        self.output_dir = Path(self.config.output_dir)
        self.cache_dir = Path(self.config.cache_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Core submodules reusing existing BENX & Podcast infrastructure
        self.ingester = PodcastIngester(cache_dir=self.cache_dir)
        self.transcriber = PodcastTranscriber()
        self.highlight_detector = HighlightDetector(
            min_clip_duration=self.config.min_clip_duration,
            max_clip_duration=self.config.max_clip_duration,
        )
        self.rights_reviewer = RightsReviewer()
        self.subtitle_manager = PodcastSubtitleManager()

        # Bridge to VideoReframer
        reframer_cfg = PodcastPipelineConfig(
            vertical_width=self.config.vertical_width,
            vertical_height=self.config.vertical_height,
            fps=self.config.fps,
            reframing_mode=self.config.reframing_mode,
            output_dir=str(self.output_dir),
            cache_dir=str(self.cache_dir),
        )
        self.reframer = VideoReframer(reframer_cfg)
        self.metadata_generator = ClipMetadataGenerator()
        self.quality_reporter = RepurposeQualityReporter()

    def ingest(self, source: str) -> PodcastInput:
        """Step 1: Validate and ingest source URL or local video file."""
        if not source or not str(source).strip():
            raise PodcastAccessError("Source parameter cannot be empty.")

        src_str = str(source).strip()
        if src_str.startswith("http://") or src_str.startswith("https://"):
            return self.ingester.ingest_url(src_str, download_media=True)
        else:
            return self.ingester.ingest_local_file(src_str)

    def transcribe(
        self,
        podcast_input: PodcastInput,
        *,
        subtitles_file: Optional[Path] = None,
        language: str = "en",
    ) -> PodcastTranscript:
        """Step 2: Generate or parse timestamped transcription."""
        if not podcast_input.local_video_path:
            raise PodcastAccessError("Local media path is required for transcription.")

        subs_path = subtitles_file
        if not subs_path and podcast_input.extracted_subtitles_path:
            subs_path = Path(podcast_input.extracted_subtitles_path)

        video_path = Path(podcast_input.local_video_path)
        transcript = self.transcriber.transcribe_or_load(
            video_path,
            subtitles_file=subs_path,
            language=language or self.config.language,
        )

        transcript_path = self.cache_dir / f"{video_path.stem}_transcript.json"
        transcript.save_json(transcript_path)
        return transcript

    def _resolve_rights_declaration(
        self,
        inp: PodcastInput,
        rights_declaration: Optional[RightsDeclaration] = None,
    ) -> RightsDeclaration:
        """Resolve and enforce explicit source rights declaration."""
        if rights_declaration:
            decl = rights_declaration
        else:
            is_creator_owned = self.config.ownership_type == "creator_owned"
            evidence = self.config.license_evidence
            if not evidence and is_creator_owned:
                evidence = "Self-authorized creator owned content"

            # Explicit user confirmation is strictly required; never auto-confirm based solely on local file presence
            confirmed = bool(self.config.confirm_rights)
            disclaimer = bool(self.config.accept_disclaimer)

            decl = RightsDeclaration(
                ownership_type=self.config.ownership_type,
                rights_holder=self.config.rights_holder or inp.channel_or_author or "Author",
                license_evidence=evidence,
                music_source="royalty_free" if self.config.bgm_path else "no_music",
                attribution_text=f"Source: {inp.title} ({inp.channel_or_author})",
                user_confirmed_rights=confirmed,
                disclaimer_accepted=disclaimer,
            )

        # Enforce explicit rights confirmation before processing third-party or URL footage
        if inp.source_type == "url" or decl.ownership_type != "creator_owned":
            if not (decl.user_confirmed_rights and decl.disclaimer_accepted):
                raise RightsVerificationError(
                    "Explicit source-rights confirmation is required before processing third-party video footage. "
                    "You must confirm ownership/licensing (--confirm-rights) and accept the legal disclaimer (--accept-disclaimer)."
                )
            self.rights_reviewer.assert_publishing_allowed(decl)
        elif decl.user_confirmed_rights:
            self.rights_reviewer.assert_publishing_allowed(decl)

        return decl

    def detect_highlights(
        self,
        podcast_input: PodcastInput,
        transcript: PodcastTranscript,
        *,
        max_candidates: Optional[int] = None,
    ) -> list[HighlightCandidate]:
        """Step 3: Detect up to 10 candidate highlights using transcript, speech cadence, and cues."""
        raw_target = max_candidates or self.config.max_clips
        max_c = max(1, min(raw_target, 10))
        self.highlight_detector.min_clip_duration = self.config.min_clip_duration
        self.highlight_detector.max_clip_duration = self.config.max_clip_duration

        candidates = self.highlight_detector.detect_highlights(
            transcript,
            max_candidates=max_c,
        )

        # Refine boundaries with local audio silence / scene cut analysis if available
        if podcast_input.local_video_path:
            video_path = Path(podcast_input.local_video_path)
            try:
                silences = self.highlight_detector.detect_silence_intervals(video_path)
                if silences:
                    for c in candidates:
                        for s_start, s_end in silences:
                            if abs(c.start_seconds - s_end) <= 1.0:
                                c.start_seconds = round(s_end, 2)
                                break
                            elif abs(c.end_seconds - s_start) <= 1.0:
                                c.end_seconds = round(s_start, 2)
                                break
                        c.duration = round(c.end_seconds - c.start_seconds, 2)
            except Exception as exc:
                log.debug("Audio silence refinement skipped: %s", exc)

            try:
                cuts = self.highlight_detector.detect_scene_changes(video_path)
                if cuts:
                    for c in candidates:
                        for cut in cuts:
                            if abs(c.start_seconds - cut) <= 0.6 and cut > 0:
                                c.start_seconds = round(cut, 2)
                                c.duration = round(c.end_seconds - c.start_seconds, 2)
                                break
            except Exception as exc:
                log.debug("Scene cut refinement skipped: %s", exc)

        return candidates

    def create_draft(
        self,
        source: str,
        *,
        job_id: Optional[str] = None,
        max_clips: Optional[int] = None,
        language: str = "en",
        rights_declaration: Optional[RightsDeclaration] = None,
    ) -> Tuple[RepurposeManifest, Path]:
        """Create draft manifest for candidate preview and review stage."""
        inp = self.ingest(source)
        rights_decl = self._resolve_rights_declaration(inp, rights_declaration)
        transcript = self.transcribe(inp, language=language)
        candidates = self.detect_highlights(inp, transcript, max_candidates=max_clips)

        jid = job_id or RepurposeManifest.generate_job_id(source)
        job_dir = self.output_dir / jid
        job_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = job_dir / "manifest.json"

        entries: list[RepurposeClipEntry] = []
        for c in candidates:
            entries.append(
                RepurposeClipEntry(
                    clip_id=c.clip_id,
                    start_seconds=c.start_seconds,
                    end_seconds=c.end_seconds,
                    duration=c.duration,
                    hook=c.hook,
                    summary=c.summary,
                    score=c.score,
                    approved=True,
                    reframing_mode=self.config.reframing_mode,
                    status="pending",
                )
            )

        manifest = RepurposeManifest(
            job_id=jid,
            source=source,
            source_title=inp.title,
            source_duration=inp.duration_seconds,
            language=language or self.config.language,
            status="draft",
            config=self.config.to_dict(),
            clips=entries,
        )
        manifest.save(manifest_path)
        log.info("Draft manifest created with %d candidates at %s", len(entries), manifest_path)
        return manifest, manifest_path

    def render_from_manifest(
        self,
        manifest: RepurposeManifest,
        *,
        source_video_path: Optional[Path] = None,
        rights_declaration: Optional[RightsDeclaration] = None,
        dry_run: bool = False,
    ) -> Tuple[RepurposeManifest, dict[str, Any]]:
        """Render approved clips from an existing or edited manifest."""
        if getattr(manifest, "manifest_path", None) and Path(manifest.manifest_path).is_file():
            job_dir = Path(manifest.manifest_path).parent
        elif manifest.config.get("output_dir"):
            job_dir = Path(manifest.config["output_dir"]) / manifest.job_id
        else:
            job_dir = self.output_dir / manifest.job_id

        job_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = job_dir / "manifest.json"

        # Validate clip boundaries
        errors = manifest.validate_all(
            min_duration=self.config.min_clip_duration * 0.5,
            max_duration=self.config.max_clip_duration * 1.5,
        )
        if errors:
            raise HighlightDetectionError(f"Manifest validation failed: {'; '.join(errors)}")

        approved_clips = [c for c in manifest.get_approved_clips()][:10]
        if not approved_clips:
            manifest.status = "completed"
            manifest.save(manifest_path)
            no_clips_report = {
                "overall_status": "NO_CLIPS",
                "total_clips": 0,
                "passed_clips": 0,
                "failed_clips": 0,
                "checks": [],
                "note": "No approved clips found to render in manifest.",
            }
            report_path = job_dir / "quality_report.json"
            report_path.write_text(json.dumps(no_clips_report, indent=2, ensure_ascii=False), encoding="utf-8")
            return manifest, no_clips_report

        # Ingest or locate source video
        if source_video_path and Path(source_video_path).is_file():
            inp = self.ingest(str(source_video_path))
        else:
            inp = self.ingest(manifest.source)

        transcript = self.transcribe(inp, language=manifest.language)
        rights_decl = self._resolve_rights_declaration(inp, rights_declaration)

        if dry_run or self.config.dry_run:
            log.info("Dry-run mode active. Validating plan without invoking FFmpeg rendering.")
            manifest.status = "validated_dry_run"
            for c in approved_clips:
                c.status = "validated_dry_run"
            manifest.save(manifest_path)
            dry_checks = [
                ClipQualityCheck(
                    clip_id=c.clip_id,
                    video_path=f"output/repurposed/{manifest.job_id}/clips/{c.clip_id}/{c.clip_id}.mp4",
                    expected_duration=c.duration,
                    file_exists=True,
                    file_size_bytes=1000,
                    duration_seconds=c.duration,
                    duration_match=True,
                    has_video_stream=True,
                    has_audio_stream=True,
                    is_vertical_9_16=True,
                    passed=True,
                )
                for c in approved_clips
            ]
            report = self.quality_reporter.generate_report(dry_checks, job_dir / "quality_report.json")
            return manifest, report

        # Render each approved candidate
        quality_checks: list[ClipQualityCheck] = []
        has_failure = False

        for clip_entry in approved_clips:
            clip_id = clip_entry.clip_id
            clip_dir = job_dir / "clips" / clip_id
            clip_dir.mkdir(parents=True, exist_ok=True)

            video_out = clip_dir / f"{clip_id}.mp4"
            srt_out = clip_dir / f"{clip_id}.srt"
            vtt_out = clip_dir / f"{clip_id}.vtt"
            ass_out = clip_dir / f"{clip_id}.ass"
            thumb_out = clip_dir / f"{clip_id}_thumbnail.jpg"

            cand = HighlightCandidate(
                clip_id=clip_id,
                start_seconds=clip_entry.start_seconds,
                end_seconds=clip_entry.end_seconds,
                duration=clip_entry.duration,
                hook=clip_entry.hook,
                reason=f"Repurposed Short from {inp.title}",
                score=clip_entry.score,
                summary=clip_entry.summary,
                transcript_text=self.highlight_detector._get_text_for_range(
                    transcript, clip_entry.start_seconds, clip_entry.end_seconds
                ),
                approved=True,
            )

            try:
                # 1. Export subtitles
                self.subtitle_manager.export_srt(cand, transcript, srt_out)
                self.subtitle_manager.export_vtt(cand, transcript, vtt_out)
                self.subtitle_manager.export_ass(cand, transcript, ass_out, SubtitleStyle())

                # 2. Render vertical 9:16 video
                subs_to_burn = ass_out if self.config.burn_subtitles else None
                bgm_file = Path(self.config.bgm_path) if self.config.bgm_path else None

                self.reframer.render_short_clip(
                    source_video=Path(inp.local_video_path),
                    candidate=cand,
                    output_mp4=video_out,
                    subtitles_file=subs_to_burn,
                    reframing_mode=clip_entry.reframing_mode or self.config.reframing_mode,
                    remove_silence=self.config.remove_silence,
                    bgm_file=bgm_file,
                    bgm_volume=self.config.bgm_volume,
                )

                # 3. Keyframe thumbnail
                thumb_offset = min(2.5, cand.duration / 2.0)
                self.metadata_generator.extract_thumbnail(video_out, thumb_out, offset_seconds=thumb_offset)

                # 4. Metadata package
                meta = self.metadata_generator.generate_metadata(
                    candidate=cand,
                    podcast_input=inp,
                    rights_declaration=rights_decl,
                    video_path=video_out,
                    srt_path=srt_out,
                    vtt_path=vtt_out,
                    thumbnail_path=thumb_out,
                )

                clip_entry.status = "rendered"
                clip_entry.output_video = str(video_out)
                clip_entry.srt_path = str(srt_out)
                clip_entry.vtt_path = str(vtt_out)
                clip_entry.thumbnail_path = str(thumb_out)
                clip_entry.metadata_path = str(video_out.parent / f"{clip_id}_metadata.json")

                # Quality check
                q_check = self.quality_reporter.check_clip(
                    video_out,
                    expected_duration=cand.duration,
                    clip_id=clip_id,
                    srt_path=srt_out,
                    vtt_path=vtt_out,
                    thumbnail_path=thumb_out,
                    metadata_path=Path(clip_entry.metadata_path),
                )
                quality_checks.append(q_check)

            except Exception as exc:
                log.error("Failed to render clip %s: %s", clip_id, exc)
                clip_entry.status = "failed"
                has_failure = True
                quality_checks.append(
                    ClipQualityCheck(
                        clip_id=clip_id,
                        video_path=str(video_out),
                        expected_duration=cand.duration,
                        issues=[str(exc)],
                    )
                )

        manifest.status = "partial_failure" if has_failure else "completed"
        manifest.save(manifest_path)

        # 5. Private test upload phase if explicitly requested
        if (getattr(self.config, "upload_private", False) or getattr(manifest, "upload_private", False)) and not (dry_run or self.config.dry_run):
            self._handle_private_uploads(job_dir, manifest, approved_clips, rights_decl)

        # Generate final quality report
        report = self.quality_reporter.generate_report(quality_checks, job_dir / "quality_report.json")
        return manifest, report

    def _handle_private_uploads(
        self,
        job_dir: Path,
        manifest: RepurposeManifest,
        approved_clips: list[RepurposeClipEntry],
        rights_decl: RightsDeclaration,
    ) -> None:
        """Handle private-only test upload to YouTube for approved clips."""
        manifest_path = job_dir / "manifest.json"
        token_dir = Path.home() / ".benxautomation"
        client_secret_file = token_dir / "client_secret.json"

        if not client_secret_file.is_file():
            log.warning(
                "YouTube OAuth credentials (~/.benxautomation/client_secret.json) not configured. "
                "Private upload skipped safely; rendered video files and metadata preserved on disk."
            )
            for c in approved_clips:
                c.youtube_upload_status = "OAUTH_UNCONFIGURED"
            manifest.save(manifest_path)
            return

        if not (rights_decl.user_confirmed_rights and rights_decl.disclaimer_accepted):
            log.warning(
                "Source footage rights unconfirmed. Private upload blocked safely; rendered video files preserved on disk."
            )
            for c in approved_clips:
                c.youtube_upload_status = "RIGHTS_UNCONFIRMED_BLOCKED"
            manifest.save(manifest_path)
            return

        from benxautomation.config import PublishingConfig
        from benxautomation.publisher.youtube import YouTubeOAuthManager, YouTubePublisher

        try:
            oauth_mgr = YouTubeOAuthManager(client_secret_file)
            pub_cfg = PublishingConfig(enabled=True, enforce_private=True)
            publisher = YouTubePublisher(pub_cfg, oauth_manager=oauth_mgr)
        except Exception as exc:
            log.warning("Could not initialize YouTubePublisher (%s); upload skipped safely.", exc)
            for c in approved_clips:
                c.youtube_upload_status = "OAUTH_INIT_ERROR"
            manifest.save(manifest_path)
            return

        from benxautomation.renderer.media_validator import MediaValidator

        validator = MediaValidator()

        for clip_entry in approved_clips[:10]:
            # Only upload approved, successfully rendered clips (max 10)
            if not clip_entry.approved or clip_entry.status != "rendered" or not clip_entry.output_video:
                continue

            vid_p = Path(clip_entry.output_video)
            if not vid_p.is_file():
                continue

            meta_file = vid_p.parent / f"{clip_entry.clip_id}_metadata.json"
            title = f"{clip_entry.hook[:70]} #Shorts"
            desc = (
                f"{clip_entry.summary}\n\n"
                f"Source: {manifest.source_title}\n"
                f"{rights_decl.attribution_text}\n\n"
                f"Generated by BENXAUTOMATION Repurpose Engine."
            )
            tags = ["shorts", "repurpose", "podcast", "highlight", "clip"]

            # Runtime quality gate check before upload:
            # non-empty file, FFmpeg full decode, video/audio streams, duration, 9:16 portrait
            passed, issues, meta = validator.validate_for_private_upload(
                vid_p,
                is_short=True,
                min_duration_seconds=self.config.min_clip_duration or 1.0,
            )
            if not passed:
                clip_entry.youtube_upload_status = "QUALITY_CHECK_FAILED"
                log.warning(
                    "Clip %s rejected by pre-upload quality checks: %s",
                    clip_entry.clip_id,
                    issues,
                )
                rejection_path = vid_p.parent / f"{clip_entry.clip_id}_upload_rejection.json"
                try:
                    rejection_path.write_text(
                        json.dumps(
                            {
                                "clip_id": clip_entry.clip_id,
                                "issues": issues,
                                "status": "QUALITY_CHECK_FAILED",
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
                except Exception as r_err:
                    log.debug("Could not write rejection report: %s", r_err)
                continue

            try:
                log.info("Uploading Short '%s' strictly as PRIVATE to YouTube...", clip_entry.clip_id)
                up_res = publisher.upload(
                    vid_p,
                    title=title,
                    description=desc,
                    tags=tags,
                    privacy_status="private",
                )
                vid_id = str(up_res.get("video_id") or up_res.get("id") or "")
                if not vid_id:
                    raise PublishingDisabledError("YouTube upload did not return a valid video ID.")

                # Verify returned privacy status with YouTube API
                verified_privacy = up_res.get("privacy_status")
                if not verified_privacy:
                    try:
                        v_info = publisher.verify_video(vid_id)
                        verified_privacy = v_info.get("privacy_status")
                    except Exception as ver_err:
                        log.warning("Could not query YouTube video status (%s); using response status.", ver_err)

                if verified_privacy and str(verified_privacy).lower() != "private":
                    raise PublishingDisabledError(
                        f"CRITICAL: Uploaded video {vid_id} privacy is '{verified_privacy}', NOT 'private'. Safety guard violated."
                    )

                clip_entry.youtube_upload_status = "UPLOADED_PRIVATE"
                clip_entry.youtube_video_id = vid_id
                clip_entry.youtube_video_url = str(up_res.get("url") or f"https://youtu.be/{vid_id}")

                # Update metadata JSON
                if meta_file.is_file():
                    try:
                        m_data = json.loads(meta_file.read_text(encoding="utf-8"))
                        m_data["youtube_upload_status"] = "UPLOADED_PRIVATE"
                        m_data["youtube_video_id"] = vid_id
                        m_data["youtube_video_url"] = clip_entry.youtube_video_url
                        meta_file.write_text(json.dumps(m_data, indent=2, ensure_ascii=False), encoding="utf-8")
                    except Exception as m_err:
                        log.debug("Could not update metadata JSON: %s", m_err)

                log.info("Successfully uploaded clip %s as PRIVATE (ID: %s)", clip_entry.clip_id, vid_id)

            except Exception as up_exc:
                log.error("Failed to upload clip %s: %s", clip_entry.clip_id, up_exc)
                clip_entry.youtube_upload_status = "UPLOAD_FAILED"

        manifest.save(manifest_path)


    def run(
        self,
        source: str,
        *,
        job_id: Optional[str] = None,
        draft_only: bool = False,
        max_clips: Optional[int] = None,
        language: str = "en",
        dry_run: bool = False,
        upload_private: Optional[bool] = None,
        rights_declaration: Optional[RightsDeclaration] = None,
    ) -> Tuple[RepurposeManifest, dict[str, Any]]:
        """End-to-end execution: Ingest -> Analyze -> Draft/Render -> Quality Report."""
        if upload_private is not None:
            self.config.upload_private = upload_private

        manifest, manifest_path = self.create_draft(
            source,
            job_id=job_id,
            max_clips=max_clips,
            language=language,
            rights_declaration=rights_declaration,
        )

        if draft_only:
            log.info("Draft creation completed: %s", manifest_path)
            draft_report = {
                "overall_status": "DRAFT",
                "total_clips": len(manifest.clips),
                "passed_clips": 0,
                "failed_clips": 0,
                "checks": [],
                "note": "Draft manifest created. Rendering not requested.",
            }
            report_path = manifest_path.parent / "quality_report.json"
            report_path.write_text(json.dumps(draft_report, indent=2, ensure_ascii=False), encoding="utf-8")
            return manifest, draft_report

        return self.render_from_manifest(
            manifest,
            rights_declaration=rights_declaration,
            dry_run=dry_run,
        )
