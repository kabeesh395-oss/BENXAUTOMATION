"""OpenAI-compatible script generation provider."""

from __future__ import annotations

import json
import os
import re
from typing import Optional

from benxautomation.errors import ScriptGenerationError
from benxautomation.logger import get_logger
from benxautomation.script.models import ScriptRequest, ScriptResult, ScriptScene
from benxautomation.script.provider import ScriptProvider

log = get_logger(__name__)


class OpenAIScriptProvider(ScriptProvider):
    """Generates structured video scripts using OpenAI or OpenAI-compatible APIs."""

    def __init__(
        self,
        *,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        api_key_env: str = "OPENAI_API_KEY",
        base_url: Optional[str] = None,
        base_url_env: str = "OPENAI_BASE_URL",
        temperature: float = 0.7,
        timeout_seconds: int = 30,
    ):
        self.model = model
        self.api_key_env = api_key_env
        self.base_url_env = base_url_env
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

        # Resolve credentials
        self._api_key = api_key or os.environ.get(api_key_env)
        self._base_url = base_url or os.environ.get(base_url_env)

    @property
    def provider_name(self) -> str:
        return "openai"

    def _get_client(self):
        if not self._api_key:
            raise ScriptGenerationError(
                f"API key not found. Please set the {self.api_key_env} environment variable "
                "or pass a manual script with --script."
            )
        try:
            import openai
        except ImportError as exc:
            raise ScriptGenerationError("openai package is not installed.") from exc

        client_kwargs = {
            "api_key": self._api_key,
            "timeout": float(self.timeout_seconds),
        }
        if self._base_url:
            client_kwargs["base_url"] = self._base_url

        return openai.OpenAI(**client_kwargs)

    def _build_prompt(self, request: ScriptRequest) -> list[dict]:
        format_guidance = (
            "YouTube Shorts vertical (9:16) format, fast-paced, high retention"
            if request.video_format.lower() == "shorts"
            else "landscape (16:9) format, well-structured, clear flow"
        )

        system_message = (
            "You are an expert video producer and scriptwriter. "
            "Write a factual, engaging, and well-structured video narration script. "
            "Do not fabricate citations, academic papers, or unverified statistical claims. "
            "You MUST respond ONLY with a valid JSON object matching the following structure:\n"
            "{\n"
            '  "title": "Title of the video",\n'
            '  "scenes": [\n'
            '    {\n'
            '      "scene_index": 1,\n'
            '      "title": "Opening Hook",\n'
            '      "narration": "Exact spoken narration for this scene",\n'
            '      "visual_description": "Clear visual description of what should appear on screen",\n'
            '      "estimated_duration_seconds": 6.0\n'
            '    }\n'
            '  ]\n'
            "}"
        )

        target_scenes = max(3, min(10, request.duration_seconds // 6))

        user_message = (
            f"Topic: {request.topic}\n"
            f"Target Audience: {request.target_audience}\n"
            f"Language: {request.language}\n"
            f"Tone: {request.tone}\n"
            f"Target Duration: approximately {request.duration_seconds} seconds\n"
            f"Format: {format_guidance}\n"
            f"Please structure this into roughly {target_scenes} distinct scenes starting with an attention-grabbing hook "
            "and ending with a crisp conclusion or call to action."
        )

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

    def _clean_json_response(self, text: str) -> str:
        """Strip markdown code fence if present."""
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text

    def generate_script(self, request: ScriptRequest) -> ScriptResult:
        """Call OpenAI and parse the returned structured script."""
        if not request.topic or not request.topic.strip():
            raise ScriptGenerationError("Cannot generate script for an empty topic.")

        client = self._get_client()
        messages = self._build_prompt(request)

        log.info("Requesting AI script for topic '%s' using model %s...", request.topic, self.model)
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            err_type = type(exc).__name__
            msg = str(exc)
            if "RateLimitError" in err_type or "429" in msg:
                raise ScriptGenerationError(f"OpenAI API rate limit exceeded: {msg}") from exc
            if "AuthenticationError" in err_type or "401" in msg:
                raise ScriptGenerationError(
                    f"OpenAI authentication failed: {msg}. Check {self.api_key_env}."
                ) from exc
            if "Timeout" in err_type or "timed out" in msg.lower():
                raise ScriptGenerationError(
                    f"OpenAI API request timed out after {self.timeout_seconds}s."
                ) from exc
            raise ScriptGenerationError(f"OpenAI API call failed ({err_type}): {msg}") from exc

        choice = response.choices[0] if response.choices else None
        if not choice or not choice.message or not choice.message.content:
            raise ScriptGenerationError("OpenAI returned an empty response.")

        raw_content = choice.message.content
        cleaned_json = self._clean_json_response(raw_content)

        try:
            data = json.loads(cleaned_json)
        except json.JSONDecodeError as exc:
            raise ScriptGenerationError(
                f"Failed to parse JSON response from OpenAI: {exc}\nRaw: {raw_content[:200]}"
            ) from exc

        raw_scenes = data.get("scenes", [])
        if not raw_scenes or not isinstance(raw_scenes, list):
            raise ScriptGenerationError("OpenAI response did not contain any valid scenes.")

        parsed_scenes: list[ScriptScene] = []
        for idx, sc in enumerate(raw_scenes, start=1):
            narration = str(sc.get("narration", "")).strip()
            if not narration:
                continue
            title = str(sc.get("title", f"Scene {idx}")).strip()
            visual_desc = str(sc.get("visual_description", "")).strip()
            est_dur = float(sc.get("estimated_duration_seconds", 0.0))
            parsed_scenes.append(
                ScriptScene(
                    scene_index=idx,
                    title=title,
                    narration=narration,
                    visual_description=visual_desc,
                    estimated_duration_seconds=est_dur,
                )
            )

        if not parsed_scenes:
            raise ScriptGenerationError("All generated scenes had empty narration.")

        full_narration = " ".join(s.narration for s in parsed_scenes)
        total_dur = sum(s.estimated_duration_seconds for s in parsed_scenes)

        return ScriptResult(
            topic=request.topic,
            scenes=parsed_scenes,
            full_script=full_narration,
            provider=self.provider_name,
            model=self.model,
            target_audience=request.target_audience,
            language=request.language,
            tone=request.tone,
            estimated_duration_seconds=total_dur or float(request.duration_seconds),
            is_ai_generated=True,
        )
