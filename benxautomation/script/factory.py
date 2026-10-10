"""Factory for resolving script generation providers."""

from __future__ import annotations

from typing import Optional

from benxautomation.config import ScriptConfig
from benxautomation.errors import ScriptGenerationError
from benxautomation.script.fallback import ManualFallbackScriptProvider
from benxautomation.script.openai_provider import OpenAIScriptProvider
from benxautomation.script.provider import ScriptProvider


def get_script_provider(
    provider_name: str,
    config: Optional[ScriptConfig] = None,
    manual_text: Optional[str] = None,
) -> ScriptProvider:
    """Return an instantiated ScriptProvider matching *provider_name*."""
    name = (provider_name or "openai").lower().strip()
    cfg = config or ScriptConfig()

    if name in ("openai", "ai"):
        return OpenAIScriptProvider(
            model=cfg.model,
            api_key_env=cfg.api_key_env,
            base_url_env=cfg.base_url_env,
            temperature=cfg.temperature,
            timeout_seconds=cfg.timeout_seconds,
        )
    elif name in ("fallback", "manual", "offline"):
        return ManualFallbackScriptProvider(manual_script_text=manual_text)
    else:
        raise ScriptGenerationError(
            f"Unknown script provider '{provider_name}'. "
            "Supported providers: 'openai', 'fallback'."
        )
