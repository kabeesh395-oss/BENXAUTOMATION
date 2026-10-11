"""Podcast and Livestream-to-Shorts Automation Module.

Converts full-length podcasts and livestream replays into high-engagement,
compliance-verified vertical shorts (1080x1920) with synchronized subtitles,
rich metadata, rights verification, and private YouTube publishing.
"""

from benxautomation.podcast.models import (
    ClipMetadata,
    HighlightCandidate,
    PodcastInput,
    PodcastPipelineConfig,
    PodcastTranscript,
    RightsDeclaration,
    SubtitleStyle,
    TranscriptSegment,
)
from benxautomation.podcast.pipeline import PodcastToShortsPipeline

__all__ = [
    "PodcastInput",
    "TranscriptSegment",
    "PodcastTranscript",
    "HighlightCandidate",
    "ClipMetadata",
    "RightsDeclaration",
    "SubtitleStyle",
    "PodcastPipelineConfig",
    "PodcastToShortsPipeline",
]
