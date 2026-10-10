"""Tests for SubtitleGenerator."""

from pathlib import Path

from benxautomation.subtitles.generator import SubtitleGenerator, SubtitleSegment


class TestSubtitleGenerator:
    def test_segment_to_srt_block(self):
        seg = SubtitleSegment(
            index=1,
            start_seconds=0.0,
            end_seconds=2.5,
            text="Hello world",
        )
        block = seg.to_srt_block()
        assert "1\n00:00:00,000 --> 00:00:02,500\nHello world" in block

    def test_split_sentences(self):
        text = "First sentence. Second sentence! Third sentence?"
        sentences = SubtitleGenerator.split_sentences(text)
        assert len(sentences) == 3
        assert sentences[0] == "First sentence."

    def test_generate_srt_from_text(self, tmp_path: Path):
        gen = SubtitleGenerator()
        out_srt = tmp_path / "subs.srt"
        path = gen.generate_srt_from_text(
            "Welcome to the video. Hope you enjoy it.",
            total_duration_seconds=5.0,
            output_path=out_srt,
        )

        assert path.is_file()
        content = path.read_text(encoding="utf-8")
        assert "00:00:00,000 -->" in content
        assert "Welcome to the video." in content
