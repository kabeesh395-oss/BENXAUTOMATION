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

    def test_split_long_sentences_into_phrases(self):
        long_sentence = (
            "The ocean floor contains extreme underwater trenches with depths exceeding thirty thousand feet, "
            "where temperatures hover near freezing and water pressure reaches extraordinary levels."
        )
        sentences = SubtitleGenerator.split_sentences(long_sentence)
        assert len(sentences) >= 2

    def test_unicode_subtitles(self, tmp_path: Path):
        gen = SubtitleGenerator()
        out_srt = tmp_path / "unicode.srt"
        text = "Deep ocean 🌊 is full of mysteries! 深海探索: lumière et obscurité."
        path = gen.generate_srt_from_text(text, total_duration_seconds=4.0, output_path=out_srt)
        content = path.read_text(encoding="utf-8")
        assert "🌊" in content
        assert "深海探索" in content

    def test_validate_srt_duration(self, tmp_path: Path):
        gen = SubtitleGenerator()
        out_srt = tmp_path / "timed.srt"
        gen.generate_srt_from_text("Short text.", total_duration_seconds=5.0, output_path=out_srt)
        assert gen.validate_srt_duration(out_srt, narration_duration_seconds=5.0, tolerance_seconds=0.1) is True
        assert gen.validate_srt_duration(out_srt, narration_duration_seconds=2.0, tolerance_seconds=0.1) is False
