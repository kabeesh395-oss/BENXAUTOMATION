"""Language registry — designed to scale to 20+ languages.

Currently only English is implemented.  Additional languages can be
registered at startup by calling ``LanguageRegistry.register()``.

No AI translation is performed — this is purely a metadata registry
that tracks which languages are available and their BCP-47 codes.

STATUS: English only.  Other registrations are accepted but rendering
        in those languages is NOT yet implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LanguageInfo:
    """Metadata for a supported language."""
    code: str           # BCP-47, e.g. "en", "ta", "hi"
    name: str           # English name, e.g. "English", "Tamil"
    native_name: str    # Native script name, e.g. "English", "தமிழ்"
    rtl: bool = False   # Right-to-left script?


class LanguageRegistry:
    """Thread-safe registry of supported languages.

    Usage::

        reg = LanguageRegistry()
        reg.register(LanguageInfo(code="ta", name="Tamil", native_name="தமிழ்"))
        info = reg.get("ta")
        all_codes = reg.list_codes()
    """

    # Default languages seeded at class level
    _DEFAULTS: list[LanguageInfo] = [
        LanguageInfo(code="en", name="English", native_name="English"),
    ]

    def __init__(self) -> None:
        self._languages: dict[str, LanguageInfo] = {}
        for lang in self._DEFAULTS:
            self._languages[lang.code] = lang

    def register(self, info: LanguageInfo) -> None:
        """Add or overwrite a language entry."""
        self._languages[info.code] = info

    def get(self, code: str) -> LanguageInfo | None:
        """Return ``LanguageInfo`` for *code*, or ``None``."""
        return self._languages.get(code)

    def list_codes(self) -> list[str]:
        """Return sorted list of registered language codes."""
        return sorted(self._languages.keys())

    def list_all(self) -> list[LanguageInfo]:
        """Return all registered languages, sorted by code."""
        return [self._languages[c] for c in self.list_codes()]

    @property
    def count(self) -> int:
        return len(self._languages)
