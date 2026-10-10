"""YouTube publisher — safely disabled until OAuth is configured.

This module intentionally refuses to upload anything.  It exists to
define the interface and guard against accidental publishing.  A real
implementation requires:

1.  A valid ``client_secret.json`` obtained from Google Cloud Console.
2.  An OAuth2 flow that stores refresh tokens securely.
3.  The ``google-api-python-client`` and ``google-auth`` packages.

None of these are implemented yet.  Calling ``upload()`` will always
raise ``PublishingDisabledError``.

STATUS: STUB — NOT IMPLEMENTED
"""

from __future__ import annotations

from pathlib import Path

from benxautomation.config import PublishingConfig
from benxautomation.errors import PublishingDisabledError
from benxautomation.logger import get_logger

log = get_logger(__name__)


class YouTubePublisher:
    """Guard-rail stub for YouTube uploads.

    Raises ``PublishingDisabledError`` on every call to ``upload()``.
    """

    def __init__(self, config: PublishingConfig):
        self._config = config

    def upload(
        self,
        video_path: Path,
        *,
        title: str = "",
        description: str = "",
        tags: list[str] | None = None,
    ) -> None:
        """Attempt to upload *video_path* to YouTube.

        Always raises ``PublishingDisabledError`` — real OAuth is required.
        """
        if not self._config.enabled:
            raise PublishingDisabledError(
                "YouTube publishing is disabled in config. "
                "Set publishing.enabled=true and configure OAuth first."
            )
        # Even if enabled=true in config, we still refuse until real OAuth
        # credentials are verified.  This prevents accidental uploads if
        # someone flips the flag without completing the OAuth setup.
        raise PublishingDisabledError(
            "YouTube OAuth is not yet implemented. "
            "This is a safety guard — do not bypass it. "
            "See README for setup instructions."
        )
