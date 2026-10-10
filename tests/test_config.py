"""Tests for configuration loading and validation."""

import textwrap
from pathlib import Path

import pytest

from benxautomation.config import AppConfig, load_config
from benxautomation.errors import ConfigurationError


class TestAppConfigDefaults:
    """Verify sane defaults when no values are provided."""

    def test_default_project_name(self):
        cfg = AppConfig()
        assert cfg.project_name == "BENXAUTOMATION"

    def test_default_language(self):
        cfg = AppConfig()
        assert cfg.default_language == "en"

    def test_publishing_disabled_by_default(self):
        cfg = AppConfig()
        assert cfg.publishing.enabled is False

    def test_shorts_dimensions(self):
        cfg = AppConfig()
        assert cfg.rendering.shorts.width == 1080
        assert cfg.rendering.shorts.height == 1920

    def test_longform_dimensions(self):
        cfg = AppConfig()
        assert cfg.rendering.longform.width == 1920
        assert cfg.rendering.longform.height == 1080


class TestLoadConfig:
    """Test YAML config loading."""

    def test_load_valid_config(self, sample_config_path: Path):
        cfg = load_config(sample_config_path)
        assert cfg.project_name == "TestProject"
        assert cfg.rendering.shorts.duration_seconds == 2

    def test_load_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(ConfigurationError, match="not found"):
            load_config(tmp_path / "nonexistent.yaml")

    def test_load_empty_yaml_uses_defaults(self, tmp_path: Path):
        p = tmp_path / "empty.yaml"
        p.write_text("", encoding="utf-8")
        cfg = load_config(p)
        assert cfg.project_name == "BENXAUTOMATION"

    def test_invalid_language_code_rejected(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text('default_language: ""', encoding="utf-8")
        with pytest.raises(ConfigurationError):
            load_config(p)

    def test_negative_duration_rejected(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text(
            textwrap.dedent("""\
            rendering:
              shorts:
                duration_seconds: -5
            """),
            encoding="utf-8",
        )
        with pytest.raises(ConfigurationError):
            load_config(p)

    def test_shorts_duration_max_60(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text(
            textwrap.dedent("""\
            rendering:
              shorts:
                duration_seconds: 120
            """),
            encoding="utf-8",
        )
        with pytest.raises(ConfigurationError):
            load_config(p)
