"""Agent 2: Retention Script Director.

Transforms viral topic ideas into retention-engineered production scripts.
Enforces the 3-second hook rule, tight pacing, character cues, visual directions,
and seamless loop endings for Shorts or episodic chapters for Longform.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

import requests

from benxautomation.agents.trend_scout import TopicIdea
from benxautomation.logger import get_logger

log = get_logger(__name__)


@dataclass
class ScriptScene:
    """A single storyboard scene with dialogue, visual directions, and SFX."""
    scene_index: int
    character: str  # "ben", "max", "mr_cash", "the_king", "dr_quantum"
    expression: str  # "shocked", "talking", "smirk", "explaining", "warning", "panic", "skeptical", "triumph"
    dialogue: str
    visual_description: str
    background_theme: str
    sfx: str = "none"  # "whoosh", "alert", "cash", "spark", "pop", "boom"
    estimated_duration: float = 4.0
    pose: str = "idle"  # "idle", "pointing", "shrugging", "panic_jump", "holding_phone", "holding_prop", "thumbs_up"
    badge_text: str = ""


@dataclass
class ProductionScript:
    """Complete production script with scenes, metadata, and loop points."""
    topic_id: str
    title: str
    format: str  # "shorts" or "longform"
    scenes: List[ScriptScene] = field(default_factory=list)
    total_estimated_duration: float = 0.0
    loop_sentence: str = ""

    @property
    def full_voiceover_text(self) -> str:
        """Concatenate all dialogue for unified TTS or duration estimation."""
        return " ".join(s.dialogue for s in self.scenes)


class ScriptDirectorAgent:
    """Agent 2: Directs retention-focused scriptwriting with Gemini AI & procedural templates."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

    def create_script(self, topic: TopicIdea, use_ai: bool = True) -> ProductionScript:
        """Generate a production script tailored to topic format and character universe."""
        if self.api_key and use_ai and not topic.id.startswith("test_"):
            try:
                ai_script = self._create_script_with_gemini(topic)
                if ai_script and len(ai_script.scenes) >= 3:
                    log.info("Successfully generated dynamic script via Gemini AI for '%s'", topic.title)
                    return ai_script
            except Exception as exc:
                log.warning("Gemini script generation failed (%s); falling back to retention template.", exc)

        if topic.format == "shorts":
            return self._create_shorts_script(topic)
        else:
            return self._create_longform_script(topic)


    def _create_script_with_gemini(self, topic: TopicIdea) -> Optional[ProductionScript]:
        """Call Gemini AI to generate rich, dynamic scenes with expressions, themes, and badges."""
        is_shorts = (topic.format == "shorts")
        num_scenes = 5 if is_shorts else 7
        dur_target = "25-30 seconds total" if is_shorts else "360-480 seconds total (6-8 minutes)"

        prompt = f"""
You are the Retention Script & Visual Director for the BENX 2D Cartoon Universe.
Universe Ensemble:
1. ben: Creator host, black sunglasses, cool tech vibe, smartphone.
2. max: Logic robot with digital LED screen visor, antenna, technical diagrams.
3. mr_cash: Wall Street tycoon in pinstripe navy suit, gold coins, financial breakdown.
4. the_king: Royal monarch with red velvet robe, crown, golden scepter, historical authority.
5. dr_quantum: Physics scientist with lab coat, atomic models, bubbling chemistry flask.

Task: Create a retention-engineered production script for topic: '{topic.title}'.
Core Premise: '{topic.core_premise}'.
Format: {topic.format} ({dur_target}).
Requirements:
1. Generate exactly {num_scenes} distinct scenes.
2. Ensure emotional variety: do NOT repeat the same character or expression every scene! Use:
   - character: "ben", "max", "mr_cash", "the_king", or "dr_quantum"
   - expression: "shocked", "panic", "smirk", "warning", "explaining", "skeptical", "triumph"
   - pose: "pointing", "shrugging", "panic_jump", "holding_prop", "thumbs_up", "idle"
   - background_theme: "bank_vault", "tech_blueprint", "cyber_matrix", "quantum_lab", "wall_street", "command_center", "airport_station", "throne_room", "retro_mainframe", "ben_studio", "street_day", "street_night"
   - sfx: "alert", "cash", "spark", "whoosh", "pop", "boom"
   - badge_text: Short punchy 2-4 word uppercase headline on screen (e.g. "ATM SECRETS", "DATA INTERCEPTED")
3. Pacing: Hook in first 3 seconds! Punchy, high-retention dialogue with zero fluff.
{"4. Seamless loop: the last sentence must flow directly into the opening hook." if is_shorts else "4. Episodic documentary flow with 3-act structure."}

Return ONLY valid JSON matching this schema:
{{
  "title": "{topic.title}",
  "format": "{topic.format}",
  "scenes": [
    {{
      "scene_index": 1,
      "character": "mr_cash",
      "expression": "shocked",
      "pose": "holding_prop",
      "dialogue": "Spoken dialogue here...",
      "visual_description": "Detailed visual action...",
      "background_theme": "bank_vault",
      "sfx": "alert",
      "badge_text": "ATM SECRETS",
      "estimated_duration": 4.5
    }}
  ],
  "loop_sentence": "Opening hook sentence..."
}}
"""
        models_to_try = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]
        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7},
            }
            try:
                resp = requests.post(url, json=payload, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    parsed = json.loads(raw_text)

                    scenes: List[ScriptScene] = []
                    for item in parsed.get("scenes", []):
                        scenes.append(
                            ScriptScene(
                                scene_index=int(item.get("scene_index", len(scenes) + 1)),
                                character=str(item.get("character", "ben")).lower().strip(),
                                expression=str(item.get("expression", "talking")).lower().strip(),
                                dialogue=str(item.get("dialogue", "")).strip(),
                                visual_description=str(item.get("visual_description", "")).strip(),
                                background_theme=str(item.get("background_theme", "ben_studio")).lower().strip(),
                                sfx=str(item.get("sfx", "none")).lower().strip(),
                                estimated_duration=float(item.get("estimated_duration", 4.5)),
                                pose=str(item.get("pose", "idle")).lower().strip(),
                                badge_text=str(item.get("badge_text", "")).strip().upper(),
                            )
                        )

                    total_dur = sum(s.estimated_duration for s in scenes)
                    return ProductionScript(
                        topic_id=topic.id,
                        title=parsed.get("title", topic.title),
                        format=topic.format,
                        scenes=scenes,
                        total_estimated_duration=total_dur,
                        loop_sentence=parsed.get("loop_sentence", topic.hook),
                    )
            except Exception as err:
                log.debug("Model %s attempt failed: %s", model, err)
                continue

        return None


    def _create_shorts_script(self, topic: TopicIdea) -> ProductionScript:
        """Generate a high-velocity 25-30s Short with a seamless loop."""
        if topic.id == "juice_jacking_airport_hack":
            scenes = [
                ScriptScene(
                    scene_index=1,
                    character="ben",
                    expression="shocked",
                    dialogue="Never plug your phone into a public airport charger!",
                    visual_description="BEN plugging smartphone into public kiosk station while red warning skull flashes on screen",
                    background_theme="airport_station",
                    sfx="alert",
                    estimated_duration=3.5,
                    pose="holding_phone",
                ),
                ScriptScene(
                    scene_index=2,
                    character="max",
                    expression="warning",
                    dialogue="That USB cord carries both power and DATA! Hackers hide microchips inside public ports that hijack your phone in twelve seconds!",
                    visual_description="MAX the logic robot points to split USB diagram showing secret data interception wires",
                    background_theme="tech_blueprint",
                    sfx="spark",
                    estimated_duration=6.5,
                    pose="pointing",
                ),
                ScriptScene(
                    scene_index=3,
                    character="ben",
                    expression="panic",
                    dialogue="They steal passwords, bank logins, and install stealth keyloggers while your battery charges!",
                    visual_description="BEN sweating profusely as dark digital silhouettes pull dollar bills and passwords out of phone",
                    background_theme="cyber_matrix",
                    sfx="whoosh",
                    estimated_duration=5.5,
                    pose="panic_jump",
                ),
                ScriptScene(
                    scene_index=4,
                    character="max",
                    expression="explaining",
                    dialogue="To stay safe, carry a USB data blocker, or always plug directly into an AC wall outlet!",
                    visual_description="MAX displays a USB data blocker shield adapter blocking all data arrows",
                    background_theme="tech_shield",
                    sfx="pop",
                    estimated_duration=5.5,
                    pose="shrugging",
                ),
                ScriptScene(
                    scene_index=5,
                    character="ben",
                    expression="smirk",
                    dialogue="Share this with a friend who travels, and remember to",
                    visual_description="BEN winks with sunglasses, pointing backward into the video start loop",
                    background_theme="ben_studio",
                    sfx="whoosh",
                    estimated_duration=3.5,
                    pose="thumbs_up",
                ),
            ]
            loop_sentence = "Never plug your phone into a public airport charger!"
        else:
            # Universal high-retention 5-scene template for any topic
            scenes = [
                ScriptScene(
                    scene_index=1,
                    character=topic.target_character,
                    expression="shocked",
                    dialogue=topic.hook,
                    visual_description=f"{topic.target_character} with dramatic shocked expression introducing {topic.title}",
                    background_theme="dramatic_curtain",
                    sfx="alert",
                    estimated_duration=4.0,
                ),
                ScriptScene(
                    scene_index=2,
                    character="max" if topic.target_character != "max" else "ben",
                    expression="explaining",
                    dialogue=f"Here is how this works: {topic.core_premise}",
                    visual_description="Character breaking down the core secret with comic charts and dynamic arrows",
                    background_theme="comic_diagram",
                    sfx="whoosh",
                    estimated_duration=6.5,
                ),
                ScriptScene(
                    scene_index=3,
                    character=topic.target_character,
                    expression="panic",
                    dialogue="Most people have no idea this is happening right under their noses every single day!",
                    visual_description="Dramatic comic reaction with floating alert icons and dynamic zoom",
                    background_theme="high_stakes",
                    sfx="spark",
                    estimated_duration=5.0,
                ),
                ScriptScene(
                    scene_index=4,
                    character="ben",
                    expression="smirk",
                    dialogue="So next time someone brings this up, you know the exact truth!",
                    visual_description="BEN leaning forward with confident sunglasses smile",
                    background_theme="ben_studio",
                    sfx="pop",
                    estimated_duration=4.5,
                ),
                ScriptScene(
                    scene_index=5,
                    character="ben",
                    expression="talking",
                    dialogue="Hit subscribe to get smarter every day, and that is why you should",
                    visual_description="BEN points back toward the opening loop hook",
                    background_theme="ben_studio",
                    sfx="whoosh",
                    estimated_duration=4.0,
                ),
            ]
            loop_sentence = topic.hook

        total_dur = sum(s.estimated_duration for s in scenes)
        return ProductionScript(
            topic_id=topic.id,
            title=topic.title,
            format="shorts",
            scenes=scenes,
            total_estimated_duration=total_dur,
            loop_sentence=loop_sentence,
        )

    def _create_longform_script(self, topic: TopicIdea) -> ProductionScript:
        """Generate a 6-9 minute multi-chapter episodic documentary script with character ensemble."""
        scenes: List[ScriptScene] = []
        scene_idx = 1

        # Act 1: The Inciting Incident (BEN)
        scenes.append(
            ScriptScene(
                scene_index=scene_idx,
                character="ben",
                expression="shocked",
                dialogue=f"{topic.hook} Today, we are breaking down the biggest untold story behind {topic.title}!",
                visual_description="BEN standing before massive glowing world map as alarms flash and monitors turn blue",
                background_theme="command_center",
                sfx="alert",
                estimated_duration=14.0,
            )
        )
        scene_idx += 1

        # Act 2: Technical Breakdown (MAX)
        scenes.append(
            ScriptScene(
                scene_index=scene_idx,
                character="max",
                expression="explaining",
                dialogue="To understand how this disaster unfolded, we have to look inside the machine architecture. "
                "Operating systems have layers: User Space where regular apps run safely, and Kernel Space where critical drivers live. "
                "A single unchecked memory pointer in Kernel Space crashes everything instantly with zero recovery buffer!",
                visual_description="MAX stands beside holographic interactive CPU architecture showing User Ring 3 vs Kernel Ring 0",
                background_theme="tech_blueprint",
                sfx="spark",
                estimated_duration=28.0,
            )
        )
        scene_idx += 1

        # Act 3: The Financial Stranglehold (Mr. Cash)
        scenes.append(
            ScriptScene(
                scene_index=scene_idx,
                character="mr_cash",
                expression="smirk",
                dialogue="And why did this happen? Follow the money! Corporations pay billions in cybersecurity insurance. "
                "The race to push updates before competitors forced automated deployment pipelines with zero human QA validation. "
                "Ten billion dollars in airline and retail revenue vanished before lunch!",
                visual_description="Mr. Cash tossing gold coins beside cascading stock market crash graphs and airline tarmac gridlock",
                background_theme="wall_street",
                sfx="cash",
                estimated_duration=26.0,
            )
        )
        scene_idx += 1

        # Act 4: The Physics & Engineering Scale (Dr. Quantum)
        scenes.append(
            ScriptScene(
                scene_index=scene_idx,
                character="dr_quantum",
                expression="shocked",
                dialogue="At the atomic scale, silicon chips operate with billions of transistors switching billions of times per second. "
                "When software commands invalid hardware instructions at that velocity, electrons enter race conditions that physical reboot cannot bypass without manual safe-mode overrides!",
                visual_description="Dr. Quantum holding glowing atomic transistor model with crackling electric arcs",
                background_theme="quantum_lab",
                sfx="spark",
                estimated_duration=24.0,
            )
        )
        scene_idx += 1

        # Act 5: Historical Parallel (The King)
        scenes.append(
            ScriptScene(
                scene_index=scene_idx,
                character="the_king",
                expression="talking",
                dialogue="In ancient empires, when Rome lost its aqueducts or London's Great Fire took down the supply roads, the whole kingdom froze! "
                "Modern humanity did not eliminate medieval vulnerability; we simply replaced stone aqueducts with cloud servers!",
                visual_description="The King wearing crown on golden throne comparing ancient Roman aqueduct to modern cloud data centers",
                background_theme="ancient_throne",
                sfx="whoosh",
                estimated_duration=22.0,
            )
        )
        scene_idx += 1

        # Act 6: Synthesis & Conclusion (BEN)
        scenes.append(
            ScriptScene(
                scene_index=scene_idx,
                character="ben",
                expression="smirk",
                dialogue="So what is the lesson here? Never assume technology is unbreakable. Keep offline backups, verify your update channels, "
                "and remember: the biggest empires always fall to the smallest flaws. "
                "If you enjoyed this deep dive, smash that subscribe button, leave a comment on what breakdown we should animate next, and stay curious!",
                visual_description="BEN standing center stage with all 4 universe characters standing proudly behind him in celebration",
                background_theme="ben_studio",
                sfx="pop",
                estimated_duration=24.0,
            )
        )

        total_dur = sum(s.estimated_duration for s in scenes)
        return ProductionScript(
            topic_id=topic.id,
            title=topic.title,
            format="longform",
            scenes=scenes,
            total_estimated_duration=total_dur,
        )
