"""Structural checks for the text-only Agensi skill package."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "agensi-skill" / "benxautomation-video-production"
BUILDER = ROOT / "scripts" / "build_agensi_skill.py"


def test_skill_frontmatter_has_required_fields() -> None:
    content = (PACKAGE / "SKILL.md").read_text(encoding="utf-8")
    assert content.startswith("---\n")
    frontmatter = content.split("---", 2)[1]
    assert "\nname:" in frontmatter
    assert "\ndescription:" in frontmatter


def test_package_contains_only_supported_text_files() -> None:
    allowed = {".md", ".py", ".txt", ".json", ".yaml", ".yml", ".toml"}
    files = [path for path in PACKAGE.rglob("*") if path.is_file()]
    assert files
    assert all(path.suffix.lower() in allowed for path in files)
    assert not any(path.name.startswith(".") for path in files)


def test_zip_builder_creates_single_top_level_skill_folder(tmp_path: Path) -> None:
    output = tmp_path / "benxautomation-video-production.zip"
    result = subprocess.run(
        [sys.executable, str(BUILDER), "--output", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert output.is_file()
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert "benxautomation-video-production/SKILL.md" in names
        assert all(name.startswith("benxautomation-video-production/") for name in names)
        assert all(Path(name).suffix.lower() in {".md", ".py", ".txt", ".json", ".yaml", ".yml", ".toml"} for name in names)
