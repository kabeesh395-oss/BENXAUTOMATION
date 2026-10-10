"""Abstract base class for renderer plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RenderResult:
    """Describes the output of a successful render."""
    output_path: Path
    width: int
    height: int
    duration_seconds: float
    format_name: str  # e.g. "shorts_9x16", "longform_16x9"


class RendererPlugin(ABC):
    """Interface that every renderer plugin must implement.

    Plugins are responsible for a single video format (e.g. Shorts 9:16
    or long-form 16:9).  They accept an input asset, apply format-
    specific processing via FFmpeg, and produce a rendered output file.
    """

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Human-readable format identifier, e.g. ``'shorts_9x16'``."""

    @abstractmethod
    def render(
        self,
        input_path: Path,
        output_path: Path,
        *,
        duration_seconds: int | None = None,
    ) -> RenderResult:
        """Render *input_path* into *output_path*.

        Parameters
        ----------
        input_path:
            Path to a source image or video asset.
        output_path:
            Destination path for the rendered video.
        duration_seconds:
            Override the configured duration (optional).

        Returns
        -------
        RenderResult with metadata about the generated file.

        Raises
        ------
        RenderingError
            If FFmpeg fails or the input is invalid.
        """
