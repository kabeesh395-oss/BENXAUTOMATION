"""Research and script authoring for copyright-safe educational topics.

Translates high-level topic references into completely original, fact-checked
video scripts without reproducing third-party footage, audio, or transcripts.
"""

from __future__ import annotations

from typing import Dict, List
from benxautomation.original.models import (
    OriginalScript,
    OriginalTopicConfig,
    SceneDefinition,
)

TOPIC_CONFIGS: dict[str, OriginalTopicConfig] = {
    "ai_future": OriginalTopicConfig(
        topic_id="ai_future",
        reference_url="https://youtu.be/xAt1xcC6qfM",
        reference_subject="Artificial Intelligence, Computing Horizons & Science",
        core_factual_domain="Machine learning, algorithmic reasoning, healthcare innovation, compute scaling",
        target_shorts_count=2,
        create_longform=True,
        educational_summary="Educational exploration of how next-generation AI accelerates laboratory research and productivity.",
    ),
    "compounding_wealth": OriginalTopicConfig(
        topic_id="compounding_wealth",
        reference_url="https://youtu.be/61_ouz8Rr4s",
        reference_subject="Compounding Mathematics & Long-term Financial Discipline",
        core_factual_domain="Geometric compounding rate, volatility management, patient investing horizon",
        target_shorts_count=2,
        create_longform=True,
        educational_summary="Quantitative overview of compound growth principles and portfolio resilience.",
    ),
    "cyber_defense": OriginalTopicConfig(
        topic_id="cyber_defense",
        reference_url="https://youtu.be/txryxBFzmSs",
        reference_subject="Cybersecurity, Cryptography & Threat Intelligence",
        core_factual_domain="Cryptographic protocols, Zero Trust frameworks, defensive digital infrastructure",
        target_shorts_count=2,
        create_longform=True,
        educational_summary="Architectural guide on modern encryption and global infrastructure cyber defense.",
    ),
}


class OriginalScriptAuthor:
    """Generates strictly original scripts for YouTube Shorts and Long-form formats."""

    @classmethod
    def get_topics(cls) -> list[OriginalTopicConfig]:
        return list(TOPIC_CONFIGS.values())

    @classmethod
    def create_scripts_for_topic(cls, topic_id: str) -> list[OriginalScript]:
        scripts: list[OriginalScript] = []
        if topic_id == "ai_future":
            scripts.extend(cls._get_ai_future_scripts())
        elif topic_id == "compounding_wealth":
            scripts.extend(cls._get_compounding_wealth_scripts())
        elif topic_id == "cyber_defense":
            scripts.extend(cls._get_cyber_defense_scripts())
        return scripts

    @classmethod
    def _get_ai_future_scripts(cls) -> list[OriginalScript]:
        # 1. Longform: AI In Science and Productivity
        longform = OriginalScript(
            topic_id="ai_future",
            title="The Future of Computing: How Artificial Intelligence Accelerates Science",
            format="longform",
            hook="Artificial intelligence is no longer just answering questions; it is solving complex scientific challenges.",
            scenes=[
                SceneDefinition(
                    scene_index=1,
                    title="The Shift to Scientific AI",
                    narration="Artificial intelligence is transforming from simple pattern recognition to active scientific hypothesis generation.",
                    visual_theme="ai_science_hero",
                    asset_file="orig_ai_future_hero.png",
                    estimated_duration_seconds=7.0,
                ),
                SceneDefinition(
                    scene_index=2,
                    title="Molecular Modeling & Medicine",
                    narration="Biological models can now fold proteins and simulate molecular structures in hours instead of decades.",
                    visual_theme="ai_molecular_biology",
                    asset_file="orig_ai_molecular.png",
                    estimated_duration_seconds=7.0,
                ),
                SceneDefinition(
                    scene_index=3,
                    title="Reasoning and Inference Scale",
                    narration="Modern reasoning architectures verify logic step by step, drastically reducing hallucinations in technical tasks.",
                    visual_theme="ai_reasoning_logic",
                    asset_file="orig_ai_reasoning.png",
                    estimated_duration_seconds=7.5,
                ),
                SceneDefinition(
                    scene_index=4,
                    title="The Next Frontier",
                    narration="As computing infrastructure expands, AI becomes a collaborative research assistant for humanity.",
                    visual_theme="ai_future_horizon",
                    asset_file="orig_ai_horizon.png",
                    estimated_duration_seconds=7.0,
                ),
            ],
            total_estimated_duration=28.5,
            research_attribution="Independent research inspired by technology discussions on AI frontiers.",
            tags=["artificialintelligence", "technology", "datascience", "futureofwork", "science"],
        )

        # 2. Short 1: Accelerating Discovery
        short_1 = OriginalScript(
            topic_id="ai_future",
            title="How AI Is Accelerating Scientific Discovery #Shorts",
            format="shorts",
            hook="Did you know AI models can predict molecular structures in seconds?",
            scenes=[
                SceneDefinition(
                    scene_index=1,
                    title="The Research Bottleneck",
                    narration="Traditional scientific discovery often requires years of physical trial and error in laboratories.",
                    visual_theme="ai_shorts_bottleneck",
                    asset_file="orig_ai_short1_scene1.png",
                    estimated_duration_seconds=5.0,
                ),
                SceneDefinition(
                    scene_index=2,
                    title="Simulating Chemistry",
                    narration="New neural architectures simulate complex biological chemistry at digital speed.",
                    visual_theme="ai_shorts_simulation",
                    asset_file="orig_ai_short1_scene2.png",
                    estimated_duration_seconds=5.0,
                ),
                SceneDefinition(
                    scene_index=3,
                    title="Faster Cures",
                    narration="This breakthrough is dramatically shortening the discovery timeline for life-saving therapeutics.",
                    visual_theme="ai_shorts_breakthrough",
                    asset_file="orig_ai_short1_scene3.png",
                    estimated_duration_seconds=5.5,
                ),
            ],
            total_estimated_duration=15.5,
            research_attribution="Independent synthesis of modern computational biology breakthroughs.",
            tags=["shorts", "ai", "technology", "future", "science"],
        )

        # 3. Short 2: Reasoning Models
        short_2 = OriginalScript(
            topic_id="ai_future",
            title="Why Reasoning AI Changes Everything #Shorts",
            format="shorts",
            hook="Here is the difference between simple chatbots and true reasoning systems.",
            scenes=[
                SceneDefinition(
                    scene_index=1,
                    title="Chatbots vs Reasoning",
                    narration="Early models merely predicted the next plausible word without checking factual validity.",
                    visual_theme="ai_shorts_pattern_matching",
                    asset_file="orig_ai_short2_scene1.png",
                    estimated_duration_seconds=5.0,
                ),
                SceneDefinition(
                    scene_index=2,
                    title="System Two Thinking",
                    narration="Modern reasoning architectures deliberately deliberate, back-track, and verify each logical step.",
                    visual_theme="ai_shorts_deliberation",
                    asset_file="orig_ai_short2_scene2.png",
                    estimated_duration_seconds=5.2,
                ),
                SceneDefinition(
                    scene_index=3,
                    title="High Reliability",
                    narration="The result is engineering-grade precision across code, math, and scientific problem-solving.",
                    visual_theme="ai_shorts_precision",
                    asset_file="orig_ai_short2_scene3.png",
                    estimated_duration_seconds=5.0,
                ),
            ],
            total_estimated_duration=15.2,
            research_attribution="Independent study of reinforcement learning from reasoning models.",
            tags=["shorts", "ai", "reasoning", "machinelearning", "tech"],
        )

        return [longform, short_1, short_2]

    @classmethod
    def _get_compounding_wealth_scripts(cls) -> list[OriginalScript]:
        # 1. Longform: Mathematics of Compounding
        longform = OriginalScript(
            topic_id="compounding_wealth",
            title="The Mathematics of Compounding: How Long-Term Capital Compounds",
            format="longform",
            hook="The most powerful force in financial mathematics is geometric exponential compounding.",
            scenes=[
                SceneDefinition(
                    scene_index=1,
                    title="The Principle of Exponential Growth",
                    narration="Compound interest is not merely linear addition; it is mathematical acceleration where growth generates further growth.",
                    visual_theme="finance_compound_curve",
                    asset_file="orig_fin_compound_hero.png",
                    estimated_duration_seconds=7.0,
                ),
                SceneDefinition(
                    scene_index=2,
                    title="The Critical Variable: Time",
                    narration="The exponent in the compound equation is time, meaning the majority of returns arrive in the final decades.",
                    visual_theme="finance_time_horizon",
                    asset_file="orig_fin_time.png",
                    estimated_duration_seconds=7.0,
                ),
                SceneDefinition(
                    scene_index=3,
                    title="Emotional Discipline",
                    narration="Frequent trading and panic reactions interrupt compounding. Real wealth requires enduring market cycles quietly.",
                    visual_theme="finance_discipline_cycles",
                    asset_file="orig_fin_discipline.png",
                    estimated_duration_seconds=7.0,
                ),
                SceneDefinition(
                    scene_index=4,
                    title="Systematic Execution",
                    narration="By focusing on cash-generative assets and patient reinvestment, investors harness the true power of compounding.",
                    visual_theme="finance_execution_plan",
                    asset_file="orig_fin_plan.png",
                    estimated_duration_seconds=7.2,
                ),
            ],
            total_estimated_duration=28.2,
            research_attribution="Independent research inspired by long-term compounding and disciplined value investing principles.",
            tags=["investing", "finance", "compounding", "wealthbuilding", "economics"],
        )

        # 2. Short 1: The Exponential Curve
        short_1 = OriginalScript(
            topic_id="compounding_wealth",
            title="The Math of Exponential Compounding #Shorts",
            format="shorts",
            hook="Why do 90 percent of investment returns arrive at the very end of your horizon?",
            scenes=[
                SceneDefinition(
                    scene_index=1,
                    title="Linear vs Exponential",
                    narration="Human intuition expects growth to be a straight line, but capital compounds on an exponential curve.",
                    visual_theme="finance_shorts_intuition",
                    asset_file="orig_fin_short1_scene1.png",
                    estimated_duration_seconds=5.0,
                ),
                SceneDefinition(
                    scene_index=2,
                    title="The Hockey Stick",
                    narration="In the early years, progress feels slow. But once compound interest accelerates, gains dwarf your principal.",
                    visual_theme="finance_shorts_acceleration",
                    asset_file="orig_fin_short1_scene2.png",
                    estimated_duration_seconds=5.2,
                ),
                SceneDefinition(
                    scene_index=3,
                    title="The Secret",
                    narration="The true secret to wealth is never interrupting the mathematical curve prematurely.",
                    visual_theme="finance_shorts_secret",
                    asset_file="orig_fin_short1_scene3.png",
                    estimated_duration_seconds=5.0,
                ),
            ],
            total_estimated_duration=15.2,
            research_attribution="Quantitative breakdown of compound interest mechanics.",
            tags=["shorts", "money", "investing", "financialliteracy", "wealth"],
        )

        # 3. Short 2: Time vs Timing
        short_2 = OriginalScript(
            topic_id="compounding_wealth",
            title="Time in the Market Always Beats Timing the Market #Shorts",
            format="shorts",
            hook="Trying to predict the exact peak and bottom of the market is mathematically flawed.",
            scenes=[
                SceneDefinition(
                    scene_index=1,
                    title="Missing the Best Days",
                    narration="Missing just the ten best trading days over twenty years can cut your overall returns in half.",
                    visual_theme="finance_shorts_market_timing",
                    asset_file="orig_fin_short2_scene1.png",
                    estimated_duration_seconds=5.0,
                ),
                SceneDefinition(
                    scene_index=2,
                    title="The Volatility Reality",
                    narration="Market volatility is not a defect; it is the fundamental admission fee for long-term compound growth.",
                    visual_theme="finance_shorts_volatility",
                    asset_file="orig_fin_short2_scene2.png",
                    estimated_duration_seconds=5.0,
                ),
                SceneDefinition(
                    scene_index=3,
                    title="Stay the Course",
                    narration="Stay invested, allocate consistently, and let compounding do the heavy lifting for you.",
                    visual_theme="finance_shorts_consistency",
                    asset_file="orig_fin_short2_scene3.png",
                    estimated_duration_seconds=5.2,
                ),
            ],
            total_estimated_duration=15.2,
            research_attribution="Analysis of historical equity returns and timing risk.",
            tags=["shorts", "investingtips", "stockmarket", "finance", "discipline"],
        )

        return [longform, short_1, short_2]

    @classmethod
    def _get_cyber_defense_scripts(cls) -> list[OriginalScript]:
        # 1. Longform: Inside Cryptographic Defense
        longform = OriginalScript(
            topic_id="cyber_defense",
            title="The Invisible Shield: Inside Modern Cybersecurity and Cryptographic Intelligence",
            format="longform",
            hook="Every second, billions of encrypted handshakes defend global communications from intrusion.",
            scenes=[
                SceneDefinition(
                    scene_index=1,
                    title="The Modern Threat Matrix",
                    narration="In our interconnected world, critical infrastructure, banking, and communications face persistent automated probes.",
                    visual_theme="cyber_threat_matrix",
                    asset_file="orig_cyber_hero.png",
                    estimated_duration_seconds=7.0,
                ),
                SceneDefinition(
                    scene_index=2,
                    title="The Mathematical Shield",
                    narration="Modern public key cryptography relies on computationally irreversible mathematical problems to safeguard data.",
                    visual_theme="cyber_cryptography_keys",
                    asset_file="orig_cyber_crypto.png",
                    estimated_duration_seconds=7.2,
                ),
                SceneDefinition(
                    scene_index=3,
                    title="Zero Trust Architecture",
                    narration="Modern defense abandons the old perimeter mindset. In Zero Trust, every user and device must verify continuously.",
                    visual_theme="cyber_zero_trust",
                    asset_file="orig_cyber_zerotrust.png",
                    estimated_duration_seconds=7.0,
                ),
                SceneDefinition(
                    scene_index=4,
                    title="Resilience into the Future",
                    narration="With quantum-resistant encryption on the horizon, defensive intelligence stays one step ahead of adversaries.",
                    visual_theme="cyber_quantum_horizon",
                    asset_file="orig_cyber_quantum.png",
                    estimated_duration_seconds=7.0,
                ),
            ],
            total_estimated_duration=28.4,
            research_attribution="Independent research inspired by intelligence and cybersecurity defensive frameworks.",
            tags=["cybersecurity", "infosec", "encryption", "technology", "privacy"],
        )

        # 2. Short 1: How Encryption Protects You
        short_1 = OriginalScript(
            topic_id="cyber_defense",
            title="How End-to-End Encryption Actually Works #Shorts",
            format="shorts",
            hook="How does private messaging protect your words from eavesdroppers?",
            scenes=[
                SceneDefinition(
                    scene_index=1,
                    title="The Digital Lock",
                    narration="When you hit send, your message is mathematically scrambled into unreadable cryptographic ciphertext.",
                    visual_theme="cyber_shorts_scramble",
                    asset_file="orig_cyber_short1_scene1.png",
                    estimated_duration_seconds=5.0,
                ),
                SceneDefinition(
                    scene_index=2,
                    title="Private Keys",
                    narration="Only the intended recipient holds the unique mathematical private key required to decrypt the text.",
                    visual_theme="cyber_shorts_keys",
                    asset_file="orig_cyber_short1_scene2.png",
                    estimated_duration_seconds=5.2,
                ),
                SceneDefinition(
                    scene_index=3,
                    title="Mathematical Certainty",
                    narration="Even supercomputers would require billions of years to brute-force modern two-hundred-fifty-six-bit encryption.",
                    visual_theme="cyber_shorts_certainty",
                    asset_file="orig_cyber_short1_scene3.png",
                    estimated_duration_seconds=5.2,
                ),
            ],
            total_estimated_duration=15.4,
            research_attribution="Technical explanation of AES-256 and asymmetric cryptographic exchange.",
            tags=["shorts", "cybersecurity", "encryption", "privacy", "tech"],
        )

        # 3. Short 2: Zero Trust Architecture
        short_2 = OriginalScript(
            topic_id="cyber_defense",
            title="Why Hackers Hate Zero Trust Architecture #Shorts",
            format="shorts",
            hook="The biggest revolution in cybersecurity is a concept called Zero Trust.",
            scenes=[
                SceneDefinition(
                    scene_index=1,
                    title="The Old Castle Mindset",
                    narration="Old security treated the network like a castle: once inside the moat, you had access to everything.",
                    visual_theme="cyber_shorts_castle",
                    asset_file="orig_cyber_short2_scene1.png",
                    estimated_duration_seconds=5.0,
                ),
                SceneDefinition(
                    scene_index=2,
                    title="Never Trust, Always Verify",
                    narration="Zero Trust assumes breaches are already present. Every micro-request requires strict token authentication.",
                    visual_theme="cyber_shorts_verify",
                    asset_file="orig_cyber_short2_scene2.png",
                    estimated_duration_seconds=5.2,
                ),
                SceneDefinition(
                    scene_index=3,
                    title="Stopping Lateral Movement",
                    narration="Even if an intruder breaches one laptop, they are completely locked out of the rest of the company.",
                    visual_theme="cyber_shorts_containment",
                    asset_file="orig_cyber_short2_scene3.png",
                    estimated_duration_seconds=5.2,
                ),
            ],
            total_estimated_duration=15.4,
            research_attribution="Enterprise security guide on NIST SP 800-207 Zero Trust Architecture.",
            tags=["shorts", "security", "zerotrust", "networksecurity", "hacks"],
        )

        return [longform, short_1, short_2]
