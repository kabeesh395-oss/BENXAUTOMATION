"""Unit tests for the Dynamic Character Universe module."""

from __future__ import annotations

import pytest

from benxautomation.animation.character_universe import (
    CORE_UNIVERSE_ROSTER,
    CharacterProfile,
    DynamicCharacterFactory,
)


def test_core_roster_integrity():
    """Verify that all core archetypes have complete visual specs and valid voices."""
    assert len(CORE_UNIVERSE_ROSTER) >= 8

    required_keys = {"tech", "story", "news", "finance", "fitness", "science", "gaming", "cooking", "law"}
    assert required_keys.issubset(set(CORE_UNIVERSE_ROSTER.keys()))

    for key, prof in CORE_UNIVERSE_ROSTER.items():
        assert prof.name != ""
        assert "white bald marshmallow head" in prof.build_art_prompt()
        assert "bold black comic ink outlines" in prof.build_art_prompt()
        assert "9:16" in prof.build_art_prompt()
        assert prof.voice.startswith("en-US-")


def test_topic_classification():
    """Verify topic classifier selects the appropriate character host."""
    factory = DynamicCharacterFactory()

    # Tech
    p_tech = factory.classify_topic_and_get_character("How ChatGPT was built using Python AI")
    assert p_tech.character_id == "tech_ben"

    # History / Story
    p_hist = factory.classify_topic_and_get_character("The secret battle tactics of Ancient Roman Empires")
    assert p_hist.character_id == "story_king"

    # Finance
    p_fin = factory.classify_topic_and_get_character("How to invest in Bitcoin and generate passive money")
    assert p_fin.character_id == "finance_cash"

    # News
    p_news = factory.classify_topic_and_get_character("Breaking news: Shocking mystery exposed today")
    assert p_news.character_id == "news_scoop"

    # Fitness
    p_fit = factory.classify_topic_and_get_character("Why do gym bros drink raw eggs before lifting weights")
    assert p_fit.character_id == "fitness_tank"

    # Science
    p_sci = factory.classify_topic_and_get_character("What happens if you fall into a quantum black hole in space")
    assert p_sci.character_id == "science_quantum"


def test_dynamic_on_demand_character_synthesis():
    """Verify that unlisted novel categories dynamically synthesize a matching OverSimplified character."""
    factory = DynamicCharacterFactory()

    # Novel topic: Dentistry / Teeth
    p_novel = factory.classify_topic_and_get_character("Why dentists tell you to brush teeth twice a day")
    assert p_novel is not None
    assert "white bald marshmallow head" in p_novel.build_art_prompt()
    assert "bold black comic ink outlines" in p_novel.build_art_prompt()
    name_lower = p_novel.name.lower()
    assert "dentist" in name_lower or "teeth" in name_lower or "universal" in name_lower
