"""Unit tests for script generation models, providers, and factory."""

import json
from unittest.mock import MagicMock, patch
import pytest

from benxautomation.errors import ScriptGenerationError
from benxautomation.script import (
    ManualFallbackScriptProvider,
    OpenAIScriptProvider,
    ScriptRequest,
    get_script_provider,
)


class TestManualFallbackScriptProvider:
    def test_empty_input_raises_error(self):
        provider = ManualFallbackScriptProvider()
        req = ScriptRequest(topic="")
        with pytest.raises(ScriptGenerationError, match="empty input"):
            provider.generate_script(req)

    def test_structures_manual_text_into_scenes(self):
        text = "Welcome to the deep ocean. It is dark and cold. Strange bioluminescent creatures live here. Thanks for watching."
        provider = ManualFallbackScriptProvider(manual_script_text=text)
        req = ScriptRequest(topic="Deep Ocean", duration_seconds=20)
        res = provider.generate_script(req)

        assert res.topic == "Deep Ocean"
        assert res.is_ai_generated is False
        assert res.provider == "manual_fallback"
        assert len(res.scenes) == 4
        assert res.scenes[0].title == "Hook"
        assert res.scenes[-1].title == "Conclusion"
        assert sum(s.estimated_duration_seconds for s in res.scenes) == pytest.approx(20.0, 0.1)


class TestOpenAIScriptProvider:
    def test_missing_api_key_raises_actionable_error(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = OpenAIScriptProvider(api_key=None)
        req = ScriptRequest(topic="Space Exploration")
        with pytest.raises(ScriptGenerationError, match="API key not found"):
            provider.generate_script(req)

    def test_empty_topic_raises_error(self):
        provider = OpenAIScriptProvider(api_key="sk-fake-key")
        req = ScriptRequest(topic="   ")
        with pytest.raises(ScriptGenerationError, match="empty topic"):
            provider.generate_script(req)

    def test_successful_script_generation(self):
        provider = OpenAIScriptProvider(api_key="sk-fake-key", model="gpt-4o-mini")
        req = ScriptRequest(
            topic="Deep Ocean Wonders",
            target_audience="curious learners",
            language="en",
            tone="mysterious",
            duration_seconds=30,
        )

        mock_payload = {
            "title": "Deep Ocean Wonders",
            "scenes": [
                {
                    "scene_index": 1,
                    "title": "Abyss Hook",
                    "narration": "Have you ever wondered what lives in the darkest ocean depths?",
                    "visual_description": "Dark ocean with faint bioluminescence",
                    "estimated_duration_seconds": 6.0,
                },
                {
                    "scene_index": 2,
                    "title": "Submersible Point",
                    "narration": "Deep sea exploration submersibles reveal alien-like creatures.",
                    "visual_description": "Research submersible diving in trench",
                    "estimated_duration_seconds": 8.0,
                },
                {
                    "scene_index": 3,
                    "title": "Outro",
                    "narration": "Subscribe to explore more frontiers of our planet.",
                    "visual_description": "Planet earth ocean view",
                    "estimated_duration_seconds": 6.0,
                },
            ],
        }

        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps(mock_payload)
        mock_response = MagicMock(choices=[mock_choice])
        mock_client.chat.completions.create.return_value = mock_response

        with patch.object(provider, "_get_client", return_value=mock_client):
            res = provider.generate_script(req)

            assert res.topic == "Deep Ocean Wonders"
            assert res.is_ai_generated is True
            assert res.provider == "openai"
            assert len(res.scenes) == 3
            assert "darkest ocean depths" in res.full_script
            assert res.scenes[0].title == "Abyss Hook"

    def test_empty_response_raises_error(self):
        provider = OpenAIScriptProvider(api_key="sk-fake-key")
        req = ScriptRequest(topic="Test")

        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = ""
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        with patch.object(provider, "_get_client", return_value=mock_client):
            with pytest.raises(ScriptGenerationError, match="empty response"):
                provider.generate_script(req)

    def test_malformed_json_raises_error(self):
        provider = OpenAIScriptProvider(api_key="sk-fake-key")
        req = ScriptRequest(topic="Test")

        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "This is not json at all."
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])

        with patch.object(provider, "_get_client", return_value=mock_client):
            with pytest.raises(ScriptGenerationError, match="Failed to parse JSON"):
                provider.generate_script(req)

    def test_rate_limit_error_handling(self):
        provider = OpenAIScriptProvider(api_key="sk-fake-key")
        req = ScriptRequest(topic="Test")

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("RateLimitError: 429 quota exceeded")

        with patch.object(provider, "_get_client", return_value=mock_client):
            with pytest.raises(ScriptGenerationError, match="rate limit exceeded"):
                provider.generate_script(req)

    def test_timeout_error_handling(self):
        provider = OpenAIScriptProvider(api_key="sk-fake-key", timeout_seconds=10)
        req = ScriptRequest(topic="Test")

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("APITimeoutError: Request timed out")

        with patch.object(provider, "_get_client", return_value=mock_client):
            with pytest.raises(ScriptGenerationError, match="timed out"):
                provider.generate_script(req)


class TestScriptFactory:
    def test_resolve_openai_provider(self):
        p = get_script_provider("openai")
        assert isinstance(p, OpenAIScriptProvider)

    def test_resolve_fallback_provider(self):
        p = get_script_provider("fallback", manual_text="Manual script")
        assert isinstance(p, ManualFallbackScriptProvider)

    def test_unknown_provider_raises_error(self):
        with pytest.raises(ScriptGenerationError, match="Unknown script provider"):
            get_script_provider("nonexistent_provider")
