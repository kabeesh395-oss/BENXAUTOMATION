"""Agent 1: Viral Trend Scout & Topic Hunter.

Finds and validates high-retention, high-curiosity video topics across Tech,
Cybersecurity, Finance, History, and Science for the Character Universe.
Strictly eliminates generic "channel intro" ideas in favor of high-stakes hooks.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional

from benxautomation.logger import get_logger

log = get_logger(__name__)


@dataclass
class TopicIdea:
    """A scored and validated topic candidate for production."""
    id: str
    title: str
    hook: str
    category: str  # "tech", "logic", "history", "finance", "science"
    target_character: str  # "ben", "max", "the_king", "mr_cash", "dr_quantum"
    format: str  # "shorts" or "longform"
    target_duration: float  # seconds
    curiosity_score: float  # 1.0 - 10.0
    core_premise: str
    chapters: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


class TrendScoutAgent:
    """Agent 1: Researches and scores viral topic candidates."""

    # Curated high-retention viral topics for Shorts and Long-Form
    VIRAL_TOPIC_CATALOG = [
        # --- High-Stakes Tech & Cybersecurity (BEN & MAX) ---
        TopicIdea(
            id="juice_jacking_airport_hack",
            title="Why You Should NEVER Charge Your Phone at Airports! 😱",
            hook="Never plug your phone into a public airport charger! Here is the terrifying secret hackers don't want you to know!",
            category="tech",
            target_character="ben",
            format="shorts",
            target_duration=28.0,
            curiosity_score=9.8,
            core_premise="Public USB stations can secretly transmit malware in seconds (Juice Jacking) unless you use a USB data blocker.",
            tags=["tech", "hacks", "cybersecurity", "smartphone", "safety", "shorts"],
        ),
        TopicIdea(
            id="crowdstrike_global_crash",
            title="How 1 Line of Bad Code Crashed 8.5 Million Computers! 💻",
            hook="This single microscopic line of code wiped out 8.5 million computers, grounded 5,000 airplanes, and froze global banks in 10 minutes!",
            category="logic",
            target_character="max",
            format="longform",
            target_duration=420.0,  # 7 mins
            curiosity_score=9.9,
            core_premise="The CrowdStrike Kernel incident: how a null pointer update bypassed testing and blue-screened the global economy.",
            chapters=[
                "Act 1: The Global Black Friday (The Blue Screen Wave)",
                "Act 2: MAX Explains: What is a Kernel Driver?",
                "Act 3: Mr. Cash Exposes: The Billion-Dollar Liability Panic",
                "Act 4: The 1-Line Typo that Broke Everything",
                "Act 5: How Sysadmins Fixed Millions of Machines Manually",
                "Act 6: Final Takeaway: Will It Happen Again?",
            ],
            tags=["tech", "coding", "windows", "crowdstrike", "computers", "documentary"],
        ),
        TopicIdea(
            id="tsmc_microchip_monopoly",
            title="The Most Dangerous Factory on Earth (The Microchip War) 🏭",
            hook="If this ONE single building in Taiwan stops running tomorrow, the entire world economy collapses in 48 hours!",
            category="tech",
            target_character="ben",
            format="longform",
            target_duration=480.0,  # 8 mins
            curiosity_score=9.7,
            core_premise="TSMC and ASML's monopoly on extreme ultraviolet lithography microchips that power every AI and phone on Earth.",
            chapters=[
                "Act 1: The Secret Cleanroom in Hsinchu",
                "Act 2: Dr. Quantum: How Atoms Are Etched with Extreme UV Light",
                "Act 3: Mr. Cash: Why Trillions of Dollars Depend on One Island",
                "Act 4: MAX: Can the US or China Replicate It?",
                "Act 5: The Fragile Silicon Supply Chain",
                "Act 6: BEN's Verdict: The Future of Global Tech",
            ],
            tags=["tech", "chips", "hardware", "ai", "economy", "documentary"],
        ),
        # --- Finance & Wealth Secrets (Mr. Cash) ---
        TopicIdea(
            id="credit_card_terminal_skimmer",
            title="The Invisible Card Scam at Gas Stations! 💳",
            hook="Always yank the card reader before tapping your card! If it moves even a millimeter, RUN!",
            category="finance",
            target_character="mr_cash",
            format="shorts",
            target_duration=26.0,
            curiosity_score=9.6,
            core_premise="How Bluetooth credit card skimmers are secretly installed in 30 seconds and how to spot them.",
            tags=["finance", "scams", "money", "creditcard", "security", "shorts"],
        ),
        # --- History & Empires (The King) ---
        TopicIdea(
            id="king_banned_beards",
            title="The King Who Made Having a Beard ILLEGAL! 👑",
            hook="In 1698, this angry Emperor ordered his guards to shave everyone's face on the spot, or pay a massive tax token!",
            category="history",
            target_character="the_king",
            format="shorts",
            target_duration=27.0,
            curiosity_score=9.5,
            core_premise="Peter the Great's bizarre modernization tax on Russian beards and copper tokens.",
            tags=["history", "weirdhistory", "emperor", "comedy", "shorts"],
        ),
        # --- Science & Mind-Blowing Physics (Dr. Quantum) ---
        TopicIdea(
            id="quantum_entanglement_spooky",
            title="The Mystery That Terrified Albert Einstein! 🌌",
            hook="Einstein called this 'spooky action at a distance' because it completely broke the laws of physics!",
            category="science",
            target_character="dr_quantum",
            format="shorts",
            target_duration=29.0,
            curiosity_score=9.6,
            core_premise="How two quantum particles communicate instantly across galaxies faster than the speed of light.",
            tags=["science", "physics", "quantum", "einstein", "space", "shorts"],
        ),
    ]

    def select_viral_topic(
        self,
        format_type: str = "shorts",
        category: Optional[str] = None,
        custom_topic: Optional[str] = None,
    ) -> TopicIdea:
        """Select the highest scoring topic matching the requested format and category."""
        if custom_topic:
            # Dynamically wrap user custom topic with high curiosity scoring
            return TopicIdea(
                id=f"custom_{abs(hash(custom_topic)) % 100000}",
                title=f"{custom_topic.title()} | Animated Breakdown",
                hook=f"Here is what nobody tells you about {custom_topic}!",
                category=category or "tech",
                target_character="ben",
                format=format_type,
                target_duration=30.0 if format_type == "shorts" else 420.0,
                curiosity_score=9.0,
                core_premise=custom_topic,
                tags=["animation", "education", "cartoons", format_type],
            )

        candidates = [t for t in self.VIRAL_TOPIC_CATALOG if t.format == format_type]
        if category:
            filtered = [t for t in candidates if t.category == category]
            if filtered:
                candidates = filtered

        if not candidates:
            candidates = self.VIRAL_TOPIC_CATALOG

        # Sort by curiosity score with slight non-deterministic top-selection
        top_tier = sorted(candidates, key=lambda x: x.curiosity_score, reverse=True)[:3]
        chosen = random.choice(top_tier)
        log.info(
            "Trend Scout selected topic '%s' (Score: %.1f, Format: %s, Character: %s)",
            chosen.title,
            chosen.curiosity_score,
            chosen.format,
            chosen.target_character,
        )
        return chosen
