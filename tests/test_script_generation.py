"""Unit tests for script generation models, providers, and factory."""

import json
from unittest.mock import MagicMock, patch
import pytest

from benxautomation.errors import ScriptGenerationError
from benxautomation.script import (
    GeminiScriptProvider,
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

    def test_empty_input_whitespace_raises_error(self):
        provider = ManualFallbackScriptProvider(manual_script_text="   ")
        req = ScriptRequest(topic="   ")
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

    def test_manual_script_preservation_avoids_template(self):
        text = "Direct user statement one. Direct user statement two."
        provider = ManualFallbackScriptProvider(manual_script_text=text)
        req = ScriptRequest(topic="5 surprising facts about the deep sea", duration_seconds=20)
        res = provider.generate_script(req)

        # Exact manual script is preserved without substitution or template expansion
        assert res.full_script == "Direct user statement one. Direct user statement two."
        assert "offline template" not in res.full_script.lower()
        assert res.is_ai_generated is False

    def test_topic_only_generates_offline_template_scenes(self):
        topic = "5 surprising facts about the deep sea"
        provider = ManualFallbackScriptProvider()
        req = ScriptRequest(topic=topic, duration_seconds=30)
        res = provider.generate_script(req)

        assert res.topic == topic
        assert res.is_ai_generated is False
        assert res.provider == "manual_fallback"
        # Must produce multiple structured scenes, not merely the topic string
        assert len(res.scenes) >= 3
        assert res.full_script != topic
        assert len(res.full_script.split()) > 30
        assert topic in res.full_script
        # Factual details explicitly noted as requiring verification
        assert "verif" in res.full_script.lower()
        # Scenes clearly labelled as research outlines or offline templates
        assert all("outline" in s.title.lower() or "template" in s.title.lower() for s in res.scenes)
        assert sum(s.estimated_duration_seconds for s in res.scenes) == pytest.approx(30.0, 0.1)

    def test_offline_template_duration_scaling(self):
        provider = ManualFallbackScriptProvider()
        # Short format (<= 15s) produces 3 scenes
        res_short = provider.generate_script(ScriptRequest(topic="Deep Trenches", duration_seconds=10))
        assert len(res_short.scenes) == 3
        assert sum(s.estimated_duration_seconds for s in res_short.scenes) == pytest.approx(10.0, 0.1)

        # Standard format (15s - 40s) produces 4 scenes
        res_std = provider.generate_script(ScriptRequest(topic="Deep Trenches", duration_seconds=30))
        assert len(res_std.scenes) == 4
        assert sum(s.estimated_duration_seconds for s in res_std.scenes) == pytest.approx(30.0, 0.1)

        # Long format (>= 40s) produces 5 scenes
        res_long = provider.generate_script(ScriptRequest(topic="Deep Trenches", duration_seconds=60))
        assert len(res_long.scenes) == 5
        assert sum(s.estimated_duration_seconds for s in res_long.scenes) == pytest.approx(60.0, 0.1)


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



class TestGeminiScriptProvider:
    def test_missing_api_key_raises_actionable_error(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        provider = GeminiScriptProvider(api_key=None)
        req = ScriptRequest(topic="5 surprising facts about the deep sea")
        with pytest.raises(ScriptGenerationError, match="Gemini API key not found"):
            provider.generate_script(req)

    def test_empty_topic_raises_error(self):
        provider = GeminiScriptProvider(api_key="fake-gemini-key")
        req = ScriptRequest(topic="   ")
        with pytest.raises(ScriptGenerationError, match="empty topic"):
            provider.generate_script(req)

    def test_successful_script_generation(self):
        provider = GeminiScriptProvider(api_key="fake-gemini-key")
        req = ScriptRequest(
            topic="5 surprising facts about the deep sea",
            duration_seconds=30,
        )

        mock_facts = {
            "title": "5 Surprising Facts About the Deep Sea",
            "facts": [
                {
                    "fact_number": 1,
                    "fact_title": "Deep Ocean Artifacts",
                    "narration": "There are more historical artifacts preserved in the deep ocean than in all museums combined.",
                    "visual_suggestion": "Ancient shipwreck on abyssal plain",
                    "source": "UNESCO",
                    "source_url": "https://unesco.org",
                },
                {
                    "fact_number": 2,
                    "fact_title": "Hydrothermal Vents",
                    "narration": "Deep sea hydrothermal vents support chemosynthetic ecosystems completely independent of sunlight.",
                    "visual_suggestion": "Black smoker mineral chimney spewing superheated water",
                    "source": "Woods Hole Oceanographic Institution",
                    "source_url": "https://whoi.edu",
                },
                {
                    "fact_number": 3,
                    "fact_title": "Unmapped Sea Floor",
                    "narration": "More of the surfaces of Mars and the Moon have been mapped than Earth's ocean floor.",
                    "visual_suggestion": "Sonar bathymetry mapping Mariana Trench",
                    "source": "NOAA Ocean Exploration",
                    "source_url": "https://oceanexplorer.noaa.gov",
                },
                {
                    "fact_number": 4,
                    "fact_title": "Abyssal Bioluminescence",
                    "narration": "Over seventy-five percent of deep-sea animals produce their own living light.",
                    "visual_suggestion": "Glowing siphonophores and lanternfish in pitch black",
                    "source": "MBARI",
                    "source_url": "https://mbari.org",
                },
                {
                    "fact_number": 5,
                    "fact_title": "Global Conveyor Belt",
                    "narration": "Deep cold ocean currents take up to one thousand years to complete a single global journey.",
                    "visual_suggestion": "Thermocline ocean current visualization",
                    "source": "NASA JPL",
                    "source_url": "https://jpl.nasa.gov",
                },
            ],
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": json.dumps(mock_facts)}]
                    }
                }
            ]
        }

        with patch("requests.post", return_value=mock_resp):
            res = provider.generate_script(req)

            assert res.topic == "5 surprising facts about the deep sea"
            assert res.is_ai_generated is True
            assert res.provider == "gemini"
            assert len(res.scenes) == 5
            assert res.facts_count == 5
            assert len(res.research_sources) == 5
            assert res.scenes[0].fact_number == 1
            assert "historical artifacts" in res.scenes[0].narration
            assert res.scenes[0].source == "UNESCO"
            assert res.scenes[1].source == "Woods Hole Oceanographic Institution"

    def test_timeout_error_handling(self):
        import requests
        provider = GeminiScriptProvider(api_key="fake-gemini-key", timeout_seconds=10)
        req = ScriptRequest(topic="5 facts about space")

        with patch("requests.post", side_effect=requests.exceptions.Timeout("Read timeout")):
            with pytest.raises(ScriptGenerationError, match="timed out"):
                provider.generate_script(req)

    def test_rate_limit_error_handling(self):
        provider = GeminiScriptProvider(api_key="fake-gemini-key")
        req = ScriptRequest(topic="5 facts about space")

        mock_resp = MagicMock(status_code=429, text="Rate limit exceeded")
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(ScriptGenerationError, match="rate limit exceeded"):
                provider.generate_script(req)

    def test_authentication_error_handling(self):
        provider = GeminiScriptProvider(api_key="bad-gemini-key")
        req = ScriptRequest(topic="5 facts about space")

        mock_resp = MagicMock(status_code=401, text="Unauthorized")
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(ScriptGenerationError, match="authentication failed"):
                provider.generate_script(req)

    def test_malformed_json_raises_error(self):
        provider = GeminiScriptProvider(api_key="fake-gemini-key")
        req = ScriptRequest(topic="5 facts about space")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "Not valid JSON at all"}]
                    }
                }
            ]
        }
        with patch("requests.post", return_value=mock_resp):
            with pytest.raises(ScriptGenerationError, match="Failed to parse JSON"):
                provider.generate_script(req)


class TestScriptFactory:
    def test_resolve_openai_provider(self):
        p = get_script_provider("openai")
        assert isinstance(p, OpenAIScriptProvider)

    def test_resolve_gemini_provider(self):
        p = get_script_provider("gemini")
        assert isinstance(p, GeminiScriptProvider)

    def test_resolve_fallback_provider(self):
        p = get_script_provider("fallback", manual_text="Manual script")
        assert isinstance(p, ManualFallbackScriptProvider)

    def test_resolve_auto_provider_picks_gemini_when_gemini_key_set(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        p = get_script_provider("auto")
        assert isinstance(p, GeminiScriptProvider)

    def test_resolve_auto_provider_picks_openai_when_only_openai_key_set(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
        p = get_script_provider("auto")
        assert isinstance(p, OpenAIScriptProvider)

    def test_resolve_auto_provider_raises_when_no_keys_and_no_manual_text(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ScriptGenerationError, match="No AI API credentials found"):
            get_script_provider("auto")

    def test_unknown_provider_raises_error(self):
        with pytest.raises(ScriptGenerationError, match="Unknown script provider"):
            get_script_provider("nonexistent_provider")

