"""Google Gemini script generation provider."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Optional

from benxautomation.errors import ScriptGenerationError
from benxautomation.logger import get_logger
from benxautomation.script.models import ScriptRequest, ScriptResult, ScriptScene
from benxautomation.script.provider import ScriptProvider

log = get_logger(__name__)


class GeminiScriptProvider(ScriptProvider):
    """Generates structured, fact-checked video scripts using Google Gemini API."""

    def __init__(
        self,
        *,
        model: str = "gemini-3.5-flash",
        api_key: Optional[str] = None,
        api_key_env: str = "GEMINI_API_KEY",
        temperature: float = 0.4,
        timeout_seconds: int = 30,
    ):
        self.model = model
        self.api_key_env = api_key_env
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

        self._api_key = api_key or os.environ.get(api_key_env)

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _clean_json_response(self, text: str) -> str:
        """Strip markdown code fence if present."""
        text = text.strip()
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text

    def _build_prompt(self, request: ScriptRequest) -> tuple[str, Optional[int]]:
        """Construct a structured prompt for Gemini with strict fact verification."""
        topic = request.topic.strip()
        format_guidance = (
            "YouTube Shorts vertical (9:16) format: fast-paced, high retention, concise sentences"
            if request.video_format.lower() == "shorts"
            else "landscape (16:9) format: well-structured, clear flow, detailed visual descriptions"
        )

        # Detect list-based topic (e.g. "5 surprising facts about ...")
        count_match = re.search(
            r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|top\s+\d+)\s+(surprising\s+)?(facts|reasons|tips|secrets|ways|things|habits|steps)\b",
            topic,
            re.IGNORECASE,
        )
        word_to_num = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        }
        requested_count = None
        if count_match:
            raw_num = count_match.group(1).lower().replace("top ", "").strip()
            requested_count = int(raw_num) if raw_num.isdigit() else word_to_num.get(raw_num, 5)

        if requested_count:
            system_instructions = (
                f"You are a factual video researcher and scriptwriter. Write a script for the topic: '{topic}'.\n"
                f"Requirements:\n"
                f"1. Generate exactly {requested_count} distinct, verified facts. Each fact must be completely unique.\n"
                f"2. For each fact provide: fact_number (1 to {requested_count}), fact_title, narration (2-3 engaging spoken sentences), visual_suggestion, and source (an authoritative real-world institution or research body, such as NOAA, WHOI, MBARI, NASA, etc.) and source_url if known.\n"
                f"3. Do NOT invent fake URLs or citations. Use real, verified knowledge.\n"
                f"4. Format guidelines: {format_guidance}.\n"
                f"5. Total narration time should approximately cover {request.duration_seconds} seconds across all facts.\n"
                f"6. Topic Consistency: Every fact_title and scene heading MUST directly describe the phenomenon or subject belonging to '{topic}'. Never title a fact heading after an external comparison, analogy, or reference (e.g., if the topic is '{topic}', do NOT title a fact 'Mars is Better Mapped'; instead title it directly after the primary topic phenomenon, such as 'Unmapped Ocean Floor' or 'Unexplored Depths'). All visual descriptions and spoken narrations must remain strictly centered on '{topic}'.\n"
                f"You MUST respond ONLY with a valid JSON object matching this schema:\n"
                "{\n"
                f'  "title": "{topic}",\n'
                '  "facts": [\n'
                '    {\n'
                '      "fact_number": 1,\n'
                '      "fact_title": "Concise Fact Title Centered on Topic",\n'
                '      "narration": "Engaging spoken narration explaining this fact in 2-3 sentences.",\n'
                '      "visual_suggestion": "Description of matching visuals",\n'
                '      "source": "Authoritative Research Institution (e.g. NOAA, MBARI, WHOI)",\n'
                '      "source_url": "https://..."\n'
                '    }\n'
                '  ]\n'
                "}"
            )
        else:
            target_scenes = max(3, min(8, request.duration_seconds // 7))
            system_instructions = (
                f"You are an expert video researcher and scriptwriter. Write a factual video script for: '{topic}'.\n"
                f"Format: {format_guidance}.\n"
                f"Target duration: {request.duration_seconds} seconds.\n"
                f"Target audience: {request.target_audience}.\n"
                f"Tone: {request.tone}.\n"
                f"Structure into approximately {target_scenes} distinct scenes (hook, key points, conclusion).\n"
                f"Topic Consistency: Every scene title, visual description, and spoken narration must strictly and consistently focus on '{topic}' without off-topic headings, unrelated entities, or distracting analogies in titles.\n"
                f"You MUST respond ONLY with a valid JSON object matching this schema:\n"
                "{\n"
                f'  "title": "{topic}",\n'
                '  "scenes": [\n'
                '    {\n'
                '      "scene_index": 1,\n'
                '      "title": "Scene Title",\n'
                '      "narration": "Spoken narration for this scene",\n'
                '      "visual_description": "Visual description",\n'
                '      "estimated_duration_seconds": 6.0,\n'
                '      "source": "Authoritative Institution",\n'
                '      "source_url": "https://..."\n'
                '    }\n'
                '  ]\n'
                "}"
            )

        return system_instructions, requested_count

    @staticmethod
    def _refine_topic_heading(title: str, topic: str, narration: str) -> str:
        """Sanitize headings that center on external comparison objects rather than the primary topic."""
        clean = re.sub(r"^(fact\s*\d+\s*:\s*|scene\s*\d+\s*:\s*)", "", title, flags=re.IGNORECASE).strip()
        topic_lower = topic.lower()
        clean_lower = clean.lower()

        is_ocean = any(k in topic_lower for k in ("ocean", "sea", "marine", "underwater", "trench", "abyss"))
        if is_ocean and any(off in clean_lower for off in ("mars", "moon", "outer space", "space map")):
            if "map" in clean_lower or "map" in narration.lower():
                return "Unmapped Ocean Floor"
            return "Unexplored Ocean Depths"

        is_space = any(k in topic_lower for k in ("space", "solar system", "planet", "mars", "astronomy", "cosmos"))
        if is_space and any(off in clean_lower for off in ("ocean", "sea", "marine", "underwater")):
            return "Planetary Horizons"

        return clean

    def generate_script(self, request: ScriptRequest) -> ScriptResult:
        """Call Gemini API and return a structured, validated ScriptResult."""
        if not request.topic or not request.topic.strip():
            raise ScriptGenerationError("Cannot generate script for an empty topic.")

        if not self._api_key:
            raise ScriptGenerationError(
                f"Gemini API key not found. Please set the {self.api_key_env} environment variable "
                "or pass a manual script with --script."
            )

        try:
            import requests
        except ImportError as exc:
            raise ScriptGenerationError("requests package is not installed.") from exc

        prompt_text, requested_count = self._build_prompt(request)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self._api_key}"

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt_text}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": self.temperature,
            },
        }

        max_retries = 3
        resp = None
        for attempt in range(1, max_retries + 1):
            log.info("Requesting Gemini AI script for topic '%s' using model %s (attempt %d/%d)...", request.topic, self.model, attempt, max_retries)
            try:
                resp = requests.post(url, json=payload, timeout=float(self.timeout_seconds))
            except requests.exceptions.Timeout as exc:
                if attempt == max_retries:
                    raise ScriptGenerationError(
                        f"Gemini API request timed out after {self.timeout_seconds}s."
                    ) from exc
                time.sleep(2.0 * attempt)
                continue
            except requests.exceptions.RequestException as exc:
                if attempt == max_retries:
                    raise ScriptGenerationError(f"Gemini network request failed: {exc}") from exc
                time.sleep(2.0 * attempt)
                continue

            if resp.status_code in (503, 429) and attempt < max_retries:
                log.warning("Gemini API returned HTTP %d on attempt %d; retrying in %ds...", resp.status_code, attempt, 2 * attempt)
                time.sleep(2.0 * attempt)
                continue
            break

        if resp is None:
            raise ScriptGenerationError("Gemini API request failed to execute.")

        if resp.status_code == 401 or resp.status_code == 403:
            raise ScriptGenerationError(
                f"Gemini API authentication failed (HTTP {resp.status_code}). Please verify {self.api_key_env}."
            )
        if resp.status_code == 429:
            raise ScriptGenerationError("Gemini API rate limit exceeded (HTTP 429).")
        if resp.status_code != 200:
            raise ScriptGenerationError(
                f"Gemini API returned error HTTP {resp.status_code}: {resp.text[:200]}"
            )

        try:
            data_json = resp.json()
        except Exception as exc:
            raise ScriptGenerationError(f"Failed to parse Gemini response as JSON: {exc}") from exc

        candidates = data_json.get("candidates", [])
        if not candidates:
            raise ScriptGenerationError("Gemini API returned empty candidates.")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts or not parts[0].get("text"):
            raise ScriptGenerationError("Gemini candidate content was empty.")

        raw_text = parts[0]["text"]
        clean_text = self._clean_json_response(raw_text)

        try:
            parsed = json.loads(clean_text)
        except json.JSONDecodeError as exc:
            raise ScriptGenerationError(
                f"Failed to parse JSON script from Gemini: {exc}\nRaw: {raw_text[:200]}"
            ) from exc

        # Extract scenes or facts
        parsed_scenes: list[ScriptScene] = []
        research_sources: list[dict] = []

        total_dur = max(5.0, float(request.duration_seconds))

        if "facts" in parsed and isinstance(parsed["facts"], list):
            facts_list = parsed["facts"]
            per_scene_dur = round(total_dur / max(1, len(facts_list)), 2)
            for idx, item in enumerate(facts_list, start=1):
                narr = str(item.get("narration", "")).strip()
                if not narr:
                    continue
                raw_ftitle = str(item.get("fact_title") or item.get("title") or f"Fact {idx}").strip()
                ftitle = self._refine_topic_heading(raw_ftitle, request.topic, narr)
                vdesc = str(item.get("visual_suggestion") or item.get("visual_description") or "").strip()
                fnum = int(item.get("fact_number") or idx)
                src = str(item.get("source") or "").strip() or None
                surl = str(item.get("source_url") or "").strip() or None
                if src:
                    research_sources.append({"fact_number": fnum, "source": src, "url": surl})

                parsed_scenes.append(
                    ScriptScene(
                        scene_index=idx,
                        title=f"Fact {fnum}: {ftitle}" if not ftitle.lower().startswith("fact") else ftitle,
                        narration=narr,
                        visual_description=vdesc,
                        estimated_duration_seconds=per_scene_dur,
                        fact_number=fnum,
                        fact_title=ftitle,
                        source=src,
                        source_url=surl,
                    )
                )
        elif "scenes" in parsed and isinstance(parsed["scenes"], list):
            scenes_list = parsed["scenes"]
            per_scene_dur = round(total_dur / max(1, len(scenes_list)), 2)
            for idx, item in enumerate(scenes_list, start=1):
                narr = str(item.get("narration", "")).strip()
                if not narr:
                    continue
                raw_title = str(item.get("title") or f"Scene {idx}").strip()
                title = self._refine_topic_heading(raw_title, request.topic, narr)
                vdesc = str(item.get("visual_description") or item.get("visual_suggestion") or "").strip()
                dur = float(item.get("estimated_duration_seconds") or per_scene_dur)
                src = str(item.get("source") or "").strip() or None
                surl = str(item.get("source_url") or "").strip() or None
                if src:
                    research_sources.append({"scene_index": idx, "source": src, "url": surl})

                parsed_scenes.append(
                    ScriptScene(
                        scene_index=idx,
                        title=title,
                        narration=narr,
                        visual_description=vdesc,
                        estimated_duration_seconds=dur,
                        source=src,
                        source_url=surl,
                    )
                )

        if not parsed_scenes:
            raise ScriptGenerationError("Gemini response contained no valid scenes with narration.")

        full_narration = " ".join(s.narration for s in parsed_scenes)

        return ScriptResult(
            topic=request.topic,
            scenes=parsed_scenes,
            full_script=full_narration,
            provider=self.provider_name,
            model=self.model,
            target_audience=request.target_audience,
            language=request.language,
            tone=request.tone,
            estimated_duration_seconds=sum(s.estimated_duration_seconds for s in parsed_scenes) or total_dur,
            is_ai_generated=True,
            research_sources=research_sources,
            facts_count=len(parsed_scenes) if requested_count else 0,
        )
