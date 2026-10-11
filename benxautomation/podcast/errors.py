"""Exceptions for the podcast-to-shorts automation pipeline."""

from benxautomation.errors import BenxError


class PodcastError(BenxError):
    """Base exception for podcast processing errors."""


class PodcastAccessError(PodcastError):
    """Raised when an input URL or video cannot legally or technically be accessed."""


class RightsVerificationError(PodcastError):
    """Raised when ownership, permission, or licensing requirements are not satisfied."""


class HighlightDetectionError(PodcastError):
    """Raised when highlight detection fails to find valid segments."""


class SubtitlesError(PodcastError):
    """Raised when subtitle extraction, parsing, or burning fails."""


class PodcastRenderingError(PodcastError):
    """Raised when video reframing, trimming, or rendering fails."""
