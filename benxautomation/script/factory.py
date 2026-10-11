"""Factory for resolving script generation providers."""

from __future__ import annotations

import os
from typing import Optional

from benxautomation.config import ScriptConfig
from benxautomation.errors import ScriptGenerationError
from benxautomation.script.fallback import ManualFallbackScriptProvider
from benxautomation.script.gemini_provider import GeminiScriptProvider
from benxautomation.script.openai_provider import OpenAIScriptProvider
from benxautomation.script.provider import ScriptProvider


def get_script_provider(
    provider_name: str,
    config: Optional[ScriptConfig] = None,
    manual_text: Optional[str] = None,
) -> ScriptProvider:
    """Return an instantiated ScriptProvider matching *provider_name*."""
    name = (provider_name or "auto").lower().strip()
    cfg = config or ScriptConfig()

    if name in ("auto", ""):
        # Auto-detect available credentials
        if os.environ.get(cfg.gemini_api_key_env):
            return GeminiScriptProvider(
                model=cfg.gemini_model,
                api_key_env=cfg.gemini_api_key_env,
                temperature=cfg.temperature,
                timeout_seconds=cfg.timeout_seconds,
            )
        elif os.environ.get(cfg.api_key_env):
            return OpenAIScriptProvider(
                model=cfg.model,
                api_key_env=cfg.api_key_env,
                base_url_env=cfg.base_url_env,
                temperature=cfg.temperature,
                timeout_seconds=cfg.timeout_seconds,
            )
        elif manual_text:
            return ManualFallbackScriptProvider(manual_script_text=manual_text)
        else:
            raise ScriptGenerationError(
                f"No AI API credentials found. Please set {cfg.gemini_api_key_env} or {cfg.api_key_env}, "
                "or specify --provider fallback / pass --script."
            )

    if name in ("gemini", "google"):
        return GeminiScriptProvider(
            model=cfg.gemini_model,
            api_key_env=cfg.gemini_api_key_env,
            temperature=cfg.temperature,
            timeout_seconds=cfg.timeout_seconds,
        )
    elif name in ("openai", "ai"):
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
            "Supported providers: 'auto', 'gemini', 'openai', 'fallback'."
        )
