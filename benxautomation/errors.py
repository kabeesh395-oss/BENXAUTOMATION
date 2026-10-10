"""Custom exception hierarchy for BENXAUTOMATION."""


class BenxError(Exception):
    """Base exception for all BENXAUTOMATION errors."""


class ConfigurationError(BenxError):
    """Raised when configuration is invalid or missing."""


class RenderingError(BenxError):
    """Raised when video rendering fails."""


class FFmpegNotFoundError(RenderingError):
    """Raised when FFmpeg binary is not available."""


class AssetError(BenxError):
    """Raised when an asset file is missing or invalid."""


class ManifestError(BenxError):
    """Raised when the license manifest is invalid."""


class PublishingDisabledError(BenxError):
    """Raised when publishing is attempted without OAuth configuration or when safeguards block it."""


class DuplicateUploadError(PublishingDisabledError):
    """Raised when an identical video has already been published to YouTube."""

