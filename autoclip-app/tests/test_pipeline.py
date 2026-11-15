from autoclip_app.pipeline import Segment, _srt_stamp, choose_highlights


def test_srt_stamp_uses_milliseconds():
    assert _srt_stamp(61.234) == "00:01:01,234"


def test_choose_highlights_validates_and_ranks_candidates(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"response": '[{"start_seconds":0,"end_seconds":25,"title":"Strong hook","reason":"Clear insight","score":92},'
                               '{"start_seconds":10,"end_seconds":40,"title":"Overlap","score":99},'
                               '{"start_seconds":30,"end_seconds":120,"title":"Too long","score":100}]'}

    monkeypatch.setattr("autoclip_app.pipeline.requests.post", lambda *a, **k: FakeResponse())
    rows = [Segment(0, 10, "Opening idea."), Segment(10, 25, "Complete explanation."),
            Segment(25, 40, "Another idea.")]
    clips = choose_highlights(rows)
    assert len(clips) == 1
    assert clips[0].title == "Strong hook"
    assert clips[0].score == 92


def test_choose_highlights_rejects_empty_transcript():
    try:
        choose_highlights([])
    except ValueError as exc:
        assert "empty" in str(exc).lower()
    else:
        raise AssertionError("Empty transcript must be rejected.")
