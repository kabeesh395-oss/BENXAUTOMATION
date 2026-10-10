"""Tests for the abstract RendererPlugin interface."""

from pathlib import Path

import pytest

from benxautomation.renderer.base import RendererPlugin, RenderResult


class TestRendererPluginInterface:
    """Verify that RendererPlugin cannot be instantiated directly."""

    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            RendererPlugin()  # type: ignore[abstract]

    def test_render_result_fields(self):
        r = RenderResult(
            output_path=Path("/tmp/out.mp4"),
            width=1920,
            height=1080,
            duration_seconds=60.0,
            format_name="test",
        )
        assert r.width == 1920
        assert r.format_name == "test"
