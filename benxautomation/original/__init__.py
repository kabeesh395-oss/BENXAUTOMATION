"""Original content creation module for BENXAUTOMATION.

Builds completely original, copyright-safe video content from topic research
references without reusing copyrighted footage, audio, or transcripts.
"""

from benxautomation.original.models import (
    AssetSpec,
    OriginalScript,
    OriginalTopicConfig,
    OriginalVideoResult,
)
from benxautomation.original.engine import OriginalContentEngine

__all__ = [
    "OriginalContentEngine",
    "OriginalTopicConfig",
    "OriginalScript",
    "AssetSpec",
    "OriginalVideoResult",
]
