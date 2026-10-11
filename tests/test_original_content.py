"""Tests for original content research, asset generation, rendering, and validation."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from PIL import Image

from benxautomation.asset_manifest import load_manifest
from benxautomation.original.asset_generator import OriginalAssetGenerator
from benxautomation.original.engine import OriginalContentEngine
from benxautomation.original.models import AssetSpec, OriginalScript
from benxautomation.original.research import OriginalScriptAuthor, TOPIC_CONFIGS


def test_research_topics_and_original_scripts():
    """Verify all 3 educational topics exist and produce original scripts without third-party text."""
    topics = OriginalScriptAuthor.get_topics()
    assert len(topics) == 3
    assert {t.topic_id for t in topics} == {"ai_future", "compounding_wealth", "cyber_defense"}

    for t in topics:
        scripts = OriginalScriptAuthor.create_scripts_for_topic(t.topic_id)
        assert len(scripts) >= 3  # 1 longform + at least 2 shorts
        formats = [s.format for s in scripts]
        assert "longform" in formats
        assert formats.count("shorts") >= 2

        for s in scripts:
            assert s.title
            assert s.hook
            assert len(s.scenes) >= 3
            assert s.total_estimated_duration > 10.0
            assert "Original text by BENXAUTOMATION" in s.license_statement
            assert s.full_script


def test_asset_generator_creates_valid_graphics(tmp_path: Path):
    """Verify asset generator creates high-res graphics and registers in manifest."""
    manifest_p = tmp_path / "license_manifest.yaml"
    manifest_p.write_text("assets: []\n", encoding="utf-8")
    gen = OriginalAssetGenerator(tmp_path, manifest_p)

    spec_portrait = AssetSpec(
        filename="test_portrait.png",
        title="Test Portrait Graphic",
        subtitle="Testing 9:16 layout",
        format="portrait",
        primary_color="#0f172a",
        secondary_color="#1e293b",
        icon_symbol="TEST",
        bullet_points=["Point 1", "Point 2"],
    )
    p_path = gen.create_graphic(spec_portrait, tmp_path / "test_portrait.png")
    assert p_path.is_file()
    with Image.open(p_path) as im:
        assert im.size == (1080, 1920)

    spec_landscape = AssetSpec(
        filename="test_landscape.png",
        title="Test Landscape Graphic",
        subtitle="Testing 16:9 layout",
        format="landscape",
        primary_color="#022c22",
        secondary_color="#064e3b",
        icon_symbol="LAND",
        bullet_points=["Wide Point 1", "Wide Point 2"],
    )
    l_path = gen.create_graphic(spec_landscape, tmp_path / "test_landscape.png")
    assert l_path.is_file()
    with Image.open(l_path) as im:
        assert im.size == (1920, 1080)

    # Verify manifest update
    gen._update_manifest([spec_portrait, spec_landscape])
    manifest = load_manifest(manifest_p)
    assert len(manifest.assets) == 2
    assert manifest.assets[0].license == "original"


def test_engine_renders_and_validates_single_video(tmp_path: Path):
    """Verify end-to-end rendering of a real original Short with full quality check."""
    out_dir = tmp_path / "output"
    assets_dir = tmp_path / "assets"
    manifest_p = assets_dir / "license_manifest.yaml"
    engine = OriginalContentEngine(
        output_dir=out_dir,
        assets_dir=assets_dir,
        manifest_path=manifest_p,
    )

    scripts = OriginalScriptAuthor.create_scripts_for_topic("ai_future")
    short_script = next(s for s in scripts if s.format == "shorts")

    # Generate assets first
    engine.prepare_assets()

    # Render video
    res = engine.render_video(short_script)
    assert res.output_path.is_file()
    assert res.output_path.stat().st_size > 50000  # Non-empty real MP4
    assert res.quality_passed is True
    assert res.rights_verified is True
    assert res.duration_seconds >= 10.0


def test_main_cli_routing_for_original_workflow(monkeypatch):
    """Verify --workflow original is properly accepted by main parser."""
    from benxautomation.main import build_parser

    parser = build_parser()
    args = parser.parse_args(["--workflow", "original", "--upload-private"])
    assert args.workflow == "original"
    assert args.upload_private is True
