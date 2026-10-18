"""Automatic Idea Generator and Heuristic Ranker for Funny Stickman (BEN & MAX) Shorts.

Features:
- Generates batches of relatable, everyday physical comedy premises starring BEN & MAX.
- Transparent heuristic ranking based on:
  * hook_strength: Immediate punchiness of the first 2 seconds.
  * visual_slapstick_potential: Suitability for physical action, props, and facial expressions.
  * clarity: How fast a mobile viewer grasps the conflict without complex exposition.
  * novelty: Originality and twist factor.
- Does NOT fabricate trend metrics or fake view-count data.
- Built-in multi-location scenes supporting colorful backgrounds (bedroom, kitchen, gym, etc.).
- Optional Gemini API integration with robust deterministic procedural fallbacks.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class ComedyIdea:
    """Structured representation of a comedy Short idea."""
    idea_id: str
    title: str
    premise: str
    conflict: str
    twist: str
    locations: List[str]               # e.g., ["bedroom", "kitchen", "street", "comedy_burst"]
    props: List[str]                   # e.g., ["alarm_clock", "coffee_mug", "frying_pan"]
    hook_strength: float = 0.85        # 0.0 to 1.0: grab factor in first 2 seconds
    visual_slapstick_potential: float = 0.90  # 0.0 to 1.0: action/gag richness
    clarity: float = 0.90              # 0.0 to 1.0: instant comprehensibility
    novelty: float = 0.80              # 0.0 to 1.0: fresh angle
    rank_score: float = 0.0            # Computed weighted heuristic score
    rationale: str = ""                # Transparent ranking rationale

    def compute_heuristic_score(self) -> float:
        """Transparent heuristic formula prioritizing hook, visual slapstick, and clarity.

        Weights:
        - 35% hook_strength: Vital for Shorts retention.
        - 30% visual_slapstick_potential: Ensures physical 2D animation humor.
        - 20% clarity: Minimalist stickman gags must be instantly understood.
        - 15% novelty: Rewards creative unexpected twists.
        """
        score = (
            0.35 * self.hook_strength
            + 0.30 * self.visual_slapstick_potential
            + 0.20 * self.clarity
            + 0.15 * self.novelty
        )
        self.rank_score = round(score, 4)
        self.rationale = (
            f"Heuristic score {self.rank_score:.3f} = "
            f"Hook({self.hook_strength:.2f}*0.35) + "
            f"Slapstick({self.visual_slapstick_potential:.2f}*0.30) + "
            f"Clarity({self.clarity:.2f}*0.20) + "
            f"Novelty({self.novelty:.2f}*0.15)"
        )
        return self.rank_score

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Curated catalog of original everyday comedy premises starring BEN and MAX
CORE_IDEA_LIBRARY: List[ComedyIdea] = [
    ComedyIdea(
        idea_id="snooze_math_trap",
        title="When Your 5 AM Alarm Has a Math Puzzle",
        premise="Ben sets a smart alarm clock requiring complex calculus to turn off so he will wake up early.",
        conflict="At 5:00 AM, half-asleep Ben effortlessly solves calculus in his dreams just to smash snooze.",
        twist="Ben wakes up at 2:00 PM feeling like a math genius, while Max has been awake since 5 AM losing his mind.",
        locations=["bedroom", "bedroom", "bedroom", "comedy_burst"],
        props=["alarm_clock", "phone"],
        hook_strength=0.95,
        visual_slapstick_potential=0.92,
        clarity=0.96,
        novelty=0.88,
    ),
    ComedyIdea(
        idea_id="gym_first_day_fail",
        title="Day 1 at the Gym vs The Lightest Dumbbell",
        premise="Ben buys an expensive neon gym outfit and announces he is bench pressing 200kg today.",
        conflict="Ben struts past the heavy racks straight to a 2kg dumbbell and gets pinned under it.",
        twist="Max casually lifts the dumbbell with his pinky finger while asking if Ben needs an ambulance.",
        locations=["gym", "gym", "gym", "comedy_burst"],
        props=["dumbbell", "phone"],
        hook_strength=0.92,
        visual_slapstick_potential=0.95,
        clarity=0.94,
        novelty=0.85,
    ),
    ComedyIdea(
        idea_id="coffee_overdose_matrix",
        title="What Happens When You Drink 4 Espressos at Once",
        premise="Ben needs to finish one tiny email, so he brews an apocalyptic mega-espresso.",
        conflict="Time slows down in The Matrix. Clock hands freeze, steam halts mid-air, Ben vibrates across dimensions.",
        twist="After experiencing enlightenment, Ben realizes he forgot to press Send and sends 'aaaaaaaaaa'.",
        locations=["kitchen", "office", "street", "comedy_burst"],
        props=["coffee_mug", "gadget"],
        hook_strength=0.94,
        visual_slapstick_potential=0.93,
        clarity=0.92,
        novelty=0.90,
    ),
    ComedyIdea(
        idea_id="chef_scrambled_egg",
        title="Cooking Like a Michelin Chef Goes Wrong",
        premise="Ben watches 3 cooking tutorials and attempts a dramatic 5-foot frying pan pancake flip.",
        conflict="The egg launches gracefully into the ceiling fan and spreads across every wall.",
        twist="A single clean eggshell lands precisely on Max's nose while Max is taking his morning tea.",
        locations=["kitchen", "kitchen", "kitchen", "comedy_burst"],
        props=["frying_pan", "coffee_mug"],
        hook_strength=0.91,
        visual_slapstick_potential=0.96,
        clarity=0.95,
        novelty=0.86,
    ),
    ComedyIdea(
        idea_id="wifi_router_kick",
        title="The 1% Battery and Router Reboot Panic",
        premise="The Wi-Fi dies during an intense online gaming boss fight with Ben's phone at 1% battery.",
        conflict="Ben sprints through the hallway in slow motion dodging cords to blow into the router like a Nintendo cartridge.",
        twist="The router turns back on just in time to display: 'System Update 1 of 4,000 - Do Not Turn Off'.",
        locations=["bedroom", "street", "office", "comedy_burst"],
        props=["phone", "gadget"],
        hook_strength=0.93,
        visual_slapstick_potential=0.89,
        clarity=0.93,
        novelty=0.87,
    ),
    ComedyIdea(
        idea_id="quantum_banana_slip",
        title="When Your Anti-Gravity Gizmo Meets a Banana Peel",
        premise="Ben builds a futuristic anti-gravity hover device to avoid ever walking again.",
        conflict="He cruises at 100 mph boasting about his superior genius, straight into a single discarded banana peel.",
        twist="Universal physics proves that slippery banana peel friction overrides quantum levitation every time.",
        locations=["street", "street", "street", "comedy_burst"],
        props=["banana", "gadget"],
        hook_strength=0.90,
        visual_slapstick_potential=0.97,
        clarity=0.94,
        novelty=0.84,
    ),
    ComedyIdea(
        idea_id="study_2am_cleaning",
        title="The 2 AM Sudden Urgent Cleaning Motivation",
        premise="Ben sits down at his desk to study for the final exam in 6 hours.",
        conflict="Suddenly, reorganizing his sock drawer and scrubbing the baseboards becomes the highest priority of his life.",
        twist="The room is spotless, the books are alphabetized, but Ben knows exactly 0 answers on the test.",
        locations=["classroom", "bedroom", "bedroom", "comedy_burst"],
        props=["alarm_clock", "gadget"],
        hook_strength=0.89,
        visual_slapstick_potential=0.88,
        clarity=0.95,
        novelty=0.89,
    ),
]


class StickmanIdeaGenerator:
    """Generates and ranks original comedy ideas for the Funny Stickman channel."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.catalog = list(CORE_IDEA_LIBRARY)

    def generate_batch(self, count: int = 4) -> List[ComedyIdea]:
        """Generate a batch of original comedy ideas with transparent ranking."""
        ideas: List[ComedyIdea] = []

        # Attempt AI generation if Gemini API key is configured
        if self.api_key:
            ai_ideas = self._generate_with_gemini(count)
            if ai_ideas:
                ideas.extend(ai_ideas)

        # Ensure we always have sufficient diverse ideas by supplementing with catalog
        if len(ideas) < count:
            for item in self.catalog:
                if not any(i.idea_id == item.idea_id for i in ideas):
                    ideas.append(item)
                if len(ideas) >= count:
                    break

        # Compute heuristic scores for all ideas
        for idea in ideas:
            idea.compute_heuristic_score()

        # Sort descending by transparent rank score
        ideas.sort(key=lambda x: x.rank_score, reverse=True)
        return ideas[:count]

    def rank_ideas(self, ideas: List[ComedyIdea]) -> List[ComedyIdea]:
        """Rank an arbitrary list of ideas using our transparent heuristic formula."""
        for idea in ideas:
            idea.compute_heuristic_score()
        return sorted(ideas, key=lambda x: x.rank_score, reverse=True)

    def get_by_id(self, idea_id: str) -> Optional[ComedyIdea]:
        """Retrieve a specific idea from the catalog."""
        for item in self.catalog:
            if item.idea_id == idea_id:
                item.compute_heuristic_score()
                return item
        return None

    def _generate_with_gemini(self, count: int) -> List[ComedyIdea]:
        """Optional AI generation via Google GenAI SDK with graceful fallback."""
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            prompt = f"""Generate {count} funny, relatable everyday physical comedy Shorts concepts starring two stickman characters:
- BEN: energetic, overconfident prankster with a backwards cyan cap.
- MAX: dry, analytical straight man with glasses and bow tie.

Art style: 2D minimalist stick-figure cartoon with colorful backgrounds (bedroom, kitchen, gym, office, street, park, classroom).
Aspect ratio: 9:16 vertical Short.
Each concept MUST have:
1. title: catchy, relatable
2. premise: everyday struggle
3. conflict: escalation
4. twist: funny slapstick punchline
5. locations: list of 4 locations from [bedroom, kitchen, office, street, park, gym, classroom, comedy_burst]
6. props: list of props from [alarm_clock, coffee_mug, dumbbell, frying_pan, phone, banana, gadget]
7. scores: hook_strength (0.7-1.0), visual_slapstick_potential (0.7-1.0), clarity (0.7-1.0), novelty (0.7-1.0)

Return ONLY valid JSON array with keys: title, premise, conflict, twist, locations, props, hook_strength, visual_slapstick_potential, clarity, novelty."""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                ),
            )

            data = json.loads(response.text)
            results: List[ComedyIdea] = []
            for idx, item in enumerate(data):
                title = item.get("title", f"Comedy Short {idx+1}")
                idea_id = "ai_" + hashlib.md5(title.encode("utf-8")).hexdigest()[:8]
                idea = ComedyIdea(
                    idea_id=idea_id,
                    title=title,
                    premise=item.get("premise", ""),
                    conflict=item.get("conflict", ""),
                    twist=item.get("twist", ""),
                    locations=item.get("locations", ["bedroom", "kitchen", "street", "comedy_burst"]),
                    props=item.get("props", ["phone", "alarm_clock"]),
                    hook_strength=float(item.get("hook_strength", 0.88)),
                    visual_slapstick_potential=float(item.get("visual_slapstick_potential", 0.90)),
                    clarity=float(item.get("clarity", 0.90)),
                    novelty=float(item.get("novelty", 0.85)),
                )
                results.append(idea)
            return results
        except Exception as e:
            log.warning("Gemini idea generation unavailable, using procedural catalog: %s", e)
            return []
