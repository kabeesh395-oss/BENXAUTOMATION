"""End-to-end Podcast-to-Shorts Automation Pipeline.

Orchestrates ingestion, transcription, highlight detection, rights verification,
vertical 9:16 rendering with subtitles, metadata generation, and YouTube publishing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional

from benxautomation.config import AppConfig
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
from benxautomation.publisher.youtube import YouTubeOAuthManager, YouTubePublisher

log = get_logger(__name__)


class PodcastToShortsPipeline:
    """Master pipeline converting longform podcasts/livestreams into vertical Shorts."""

    def __init__(
        self,
        config: Optional[PodcastPipelineConfig] = None,
        benx_config: Optional[AppConfig] = None,
    ) -> None:
        self.config = config or PodcastPipelineConfig()
        self.benx_config = benx_config or AppConfig()

        self.output_dir = Path(self.config.output_dir)
        self.cache_dir = Path(self.config.cache_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Submodules
        self.ingester = PodcastIngester(cache_dir=self.cache_dir)
        self.transcriber = PodcastTranscriber()
        self.highlight_detector = HighlightDetector(
            min_clip_duration=self.config.min_clip_duration,
            max_clip_duration=self.config.max_clip_duration,
        )
        self.rights_reviewer = RightsReviewer()
        self.subtitle_manager = PodcastSubtitleManager()
        self.reframer = VideoReframer(self.config)
        self.metadata_generator = ClipMetadataGenerator()

        # YouTube publisher integration
        self._publisher: Optional[YouTubePublisher] = None

    @property
    def publisher(self) -> Optional[YouTubePublisher]:
        """Lazy load YouTube publisher reusing existing OAuth configuration."""
        if self._publisher is None:
            try:
                from benxautomation.config import PublishingConfig
                pub_cfg = self.benx_config.publishing
                # Ensure enabled for podcast publisher
                default_secret = Path.home() / ".benxautomation" / "client_secret.json"
                secret_path = pub_cfg.youtube_client_secret_path or (str(default_secret) if default_secret.is_file() else None)
                active_cfg = PublishingConfig(
                    enabled=True,
                    youtube_client_secret_path=secret_path,
                    enforce_private=self.config.enforce_private,
                    upload_ledger_path=pub_cfg.upload_ledger_path,
                )
                self._publisher = YouTubePublisher(active_cfg)
            except Exception as e:
                log.warning("YouTube publisher could not be initialized (%s)", e)
        return self._publisher

    def ingest(self, source: str) -> PodcastInput:
        """Step 1: Ingest URL or local video file."""
        if source.startswith("http://") or source.startswith("https://"):
            return self.ingester.ingest_url(source, download_media=True)
        else:
            return self.ingester.ingest_local_file(source)

    def transcribe(
        self,
        podcast_input: PodcastInput,
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
            language=language or self.config.subtitle_language,
        )

        # Save transcript to cache
        transcript_path = self.cache_dir / f"{video_path.stem}_transcript.json"
        transcript.save_json(transcript_path)
        return transcript

    def detect_highlights(
        self,
        transcript: PodcastTranscript,
        max_candidates: int = 5,
    ) -> list[HighlightCandidate]:
        """Step 3: Detect candidate highlights with context and opening hooks."""
        return self.highlight_detector.detect_highlights(
            transcript,
            max_candidates=max_candidates,
        )

    def verify_rights(self, rights_declaration: RightsDeclaration) -> tuple[bool, list[str]]:
        """Step 4: Verify copyright declaration and license evidence."""
        return self.rights_reviewer.validate_declaration(rights_declaration)

    def render_clip(
        self,
        podcast_input: PodcastInput,
        transcript: PodcastTranscript,
        candidate: HighlightCandidate,
        rights_declaration: RightsDeclaration,
        *,
        style: Optional[SubtitleStyle] = None,
        burn_subtitles: bool = True,
        reframing_mode: Optional[str] = None,
        clip_output_dir: Optional[Path] = None,
    ) -> ClipMetadata:
        """Step 5: Render vertical 9:16 MP4, burn subtitles, extract thumbnail & metadata."""
        # Enforce rights declaration validity before rendering
        self.rights_reviewer.assert_publishing_allowed(rights_declaration)

        if not podcast_input.local_video_path:
            raise PodcastAccessError("No local video path available for rendering.")

        source_video = Path(podcast_input.local_video_path)
        base_dir = clip_output_dir or self.output_dir
        clip_dir = base_dir / candidate.clip_id
        clip_dir.mkdir(parents=True, exist_ok=True)

        video_out = clip_dir / f"{candidate.clip_id}.mp4"
        srt_out = clip_dir / f"{candidate.clip_id}.srt"
        vtt_out = clip_dir / f"{candidate.clip_id}.vtt"
        ass_out = clip_dir / f"{candidate.clip_id}.ass"
        thumb_out = clip_dir / f"{candidate.clip_id}_thumbnail.jpg"

        sub_style = style or SubtitleStyle()

        # 1. Generate subtitle files
        self.subtitle_manager.export_srt(candidate, transcript, srt_out)
        self.subtitle_manager.export_vtt(candidate, transcript, vtt_out)
        self.subtitle_manager.export_ass(candidate, transcript, ass_out, sub_style)

        # 2. Render vertical 9:16 video
        subs_to_burn = ass_out if burn_subtitles else None
        self.reframer.render_short_clip(
            source_video=source_video,
            candidate=candidate,
            output_mp4=video_out,
            subtitles_file=subs_to_burn,
            style=sub_style,
            reframing_mode=reframing_mode,
        )

        # 3. Extract representative keyframe thumbnail
        thumb_offset = min(2.5, candidate.duration / 2.0)
        self.metadata_generator.extract_thumbnail(video_out, thumb_out, offset_seconds=thumb_offset)

        # 4. Generate complete metadata package
        metadata = self.metadata_generator.generate_metadata(
            candidate=candidate,
            podcast_input=podcast_input,
            rights_declaration=rights_declaration,
            video_path=video_out,
            srt_path=srt_out,
            vtt_path=vtt_out,
            thumbnail_path=thumb_out,
        )

        return metadata

    def upload_to_youtube(
        self,
        metadata: ClipMetadata,
        *,
        privacy_status: str = "private",
        user_approved: bool = False,
    ) -> dict[str, Any]:
        """Step 6: Safely upload rendered Short to YouTube as private."""
        if not user_approved:
            raise RightsVerificationError(
                "Upload aborted: Explicit user approval is mandatory before any YouTube upload."
            )

        pub = self.publisher
        if not pub:
            raise PodcastError("YouTube publisher is not available. Check OAuth setup.")

        video_file = Path(metadata.video_path)
        if not video_file.is_file():
            raise PodcastRenderingError(f"Cannot upload missing video file: {video_file}")

        # Strict test safety: default and enforce private visibility
        target_privacy = "private" if self.config.enforce_private else privacy_status

        log.info(
            "Uploading Short to YouTube (privacy=%s): %s",
            target_privacy,
            metadata.title,
        )

        result = pub.upload(
            video_file,
            title=metadata.title,
            description=metadata.description,
            tags=metadata.tags,
            privacy_status=target_privacy,
        )

        # Update metadata file with upload results
        metadata.youtube_upload_status = result.get("upload_status", "UPLOADED")
        metadata.youtube_video_id = result.get("video_id") or result.get("id")
        metadata.youtube_video_url = result.get("url")

        meta_json_path = video_file.parent / f"{metadata.clip_id}_metadata.json"
        metadata.save_json(meta_json_path)

        return result
