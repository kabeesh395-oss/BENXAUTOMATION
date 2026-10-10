"""Abstract base class for script generation providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from benxautomation.script.models import ScriptRequest, ScriptResult


class ScriptProvider(ABC):
    """Interface for generating or formatting scripts."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g., 'openai', 'manual_fallback')."""

    @abstractmethod
    def generate_script(self, request: ScriptRequest) -> ScriptResult:
        """Generate a structured script based on request parameters."""
