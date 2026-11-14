from pathlib import Path

from benxautomation.autoclip_worker import (
    TranscriptLine,
    detect_highlights,
    write_clip_srt,
)


def test_write_clip_srt_uses_clip_relative_timestamps(tmp_path: Path) -> None:
    lines = [
        TranscriptLine(10.0, 12.0, "First sentence."),
        TranscriptLine(12.0, 15.0, "Second sentence."),
        TranscriptLine(15.0, 20.0, "Outside the selected clip."),
    ]
    target = tmp_path / "clip.srt"
    write_clip_srt(lines, 11.0, 16.0, target)
    text = target.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:01,000" in text
    assert "00:00:01,000 --> 00:00:04,000" in text
    assert "Outside the selected clip." in text


def test_detect_highlights_validates_ollama_json(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": '[{"start_seconds":0,"end_seconds":25,"title":"Useful clip","reason":"Clear insight","score":91}]'}

    def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr("benxautomation.autoclip_worker.requests.post", fake_post)
    lines = [TranscriptLine(0.0, 10.0, "Opening statement."),
             TranscriptLine(10.0, 25.0, "A complete explanation.")]
    clips = detect_highlights(lines, min_seconds=20, max_seconds=58)
    assert len(clips) == 1
    assert clips[0].title == "Useful clip"
    assert clips[0].score == 91
    assert clips[0].transcript == "Opening statement. A complete explanation."


def test_detect_highlights_rejects_out_of_range_candidate(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": '[{"start_seconds":0,"end_seconds":120,"title":"Too long","score":99}]'}

    monkeypatch.setattr("benxautomation.autoclip_worker.requests.post", lambda *a, **k: FakeResponse())
    lines = [TranscriptLine(0.0, 60.0, "Speech.")]
    try:
        detect_highlights(lines)
    except RuntimeError as exc:
        assert "no valid clips" in str(exc)
    else:
        raise AssertionError("Invalid duration candidate should be rejected.")
