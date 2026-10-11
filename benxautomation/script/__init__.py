"""Script generation module for BENXAUTOMATION."""

from benxautomation.script.factory import get_script_provider
from benxautomation.script.fallback import ManualFallbackScriptProvider
from benxautomation.script.gemini_provider import GeminiScriptProvider
from benxautomation.script.models import ScriptRequest, ScriptResult, ScriptScene
from benxautomation.script.openai_provider import OpenAIScriptProvider
from benxautomation.script.provider import ScriptProvider

__all__ = [
    "ScriptRequest",
    "ScriptScene",
    "ScriptResult",
    "ScriptProvider",
    "GeminiScriptProvider",
    "OpenAIScriptProvider",
    "ManualFallbackScriptProvider",
    "get_script_provider",
]

