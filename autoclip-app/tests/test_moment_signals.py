from pathlib import Path

from autoclip_app.moment_signals import (
    chat_activity_score,
    combine_moment_score,
    load_chat_events,
)


def test_chat_activity_score_detects_burst():
    events = [{"time": float(t)} for t in [0, 10, 20, 21, 22, 23, 24, 50, 80]]
    assert chat_activity_score(events, 20, 25) > chat_activity_score(events, 40, 45)


def test_chat_activity_missing_events_is_none():
    assert chat_activity_score([], 0, 20) is None


def test_chat_loader_skips_malformed_and_negative_rows(tmp_path: Path):
    path = tmp_path / "chat.jsonl"
    path.write_text('{"time":12,"text":"wow"}\nnot json\n{"time":-1}\n', encoding="utf-8")
    events = load_chat_events(path)
    assert len(events) == 1
    assert events[0]["time"] == 12


def test_combined_score_renormalizes_missing_signals():
    assert combine_moment_score(80) == 80
    score = combine_moment_score(80, {"mean_db": -10, "peak_db": -2}, 100)
    assert score > 80


def test_chat_score_validates_range():
    try:
        chat_activity_score([], 10, 10)
    except ValueError:
        return
    raise AssertionError("Invalid time range must fail")
