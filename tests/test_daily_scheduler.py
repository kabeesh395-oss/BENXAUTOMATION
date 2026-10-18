"""Tests for Daily Autonomous Scheduler."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.daily_autonomous_scheduler import (
    CATEGORY_ROTATION,
    get_next_recommended_category,
    load_history,
    save_history,
)


def test_category_rotation():
    """Verify that category rotation cycles evenly."""
    empty_history = []
    assert get_next_recommended_category(empty_history) == CATEGORY_ROTATION[0]

    history_with_tech = [{"category": "tech"}]
    assert get_next_recommended_category(history_with_tech) == "logic"

    history_with_history = [{"category": "history"}]
    assert get_next_recommended_category(history_with_history) == "tech"


def test_save_and_load_history(tmp_path, monkeypatch):
    """Verify history persistence without corrupting state."""
    test_hist_file = tmp_path / "test_history.json"
    monkeypatch.setattr("scripts.daily_autonomous_scheduler.HISTORY_FILE", test_hist_file)

    assert load_history() == []

    entry = {
        "timestamp": "2026-10-18T18:00:00",
        "topic_id": "test_topic",
        "title": "Test Title",
        "category": "tech",
        "format": "longform",
        "repurposed_shorts_count": 2,
    }
    save_history(entry)

    loaded = load_history()
    assert len(loaded) == 1
    assert loaded[0]["topic_id"] == "test_topic"
    assert loaded[0]["repurposed_shorts_count"] == 2
