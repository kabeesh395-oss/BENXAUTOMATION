"""Tests for asset license manifest validation."""

import textwrap
from pathlib import Path

import pytest

from benxautomation.asset_manifest import (
    AssetEntry,
    LicenseManifest,
    load_manifest,
    validate_assets_exist,
)
from benxautomation.errors import ManifestError


class TestAssetEntry:
    def test_valid_licenses_accepted(self):
        for lic in ("cc0", "CC-BY-4.0", "MIT", "public-domain", "original"):
            entry = AssetEntry(file="a.png", license=lic)
            assert entry.license == lic.lower()

    def test_unknown_license_rejected(self):
        with pytest.raises(ValueError, match="Unknown license"):
            AssetEntry(file="a.png", license="proprietary")


class TestLoadManifest:
    def test_load_valid_manifest(self, sample_manifest_path: Path):
        m = load_manifest(sample_manifest_path)
        assert len(m.assets) == 1
        assert m.assets[0].file == "sample.bmp"
        assert m.assets[0].license == "cc0"

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(ManifestError, match="not found"):
            load_manifest(tmp_path / "nope.yaml")

    def test_empty_yaml_gives_empty_list(self, tmp_path: Path):
        p = tmp_path / "empty.yaml"
        p.write_text("", encoding="utf-8")
        m = load_manifest(p)
        assert m.assets == []

    def test_invalid_yaml_raises(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text("assets:\n  - file: 1\n    license: nope", encoding="utf-8")
        with pytest.raises(ManifestError):
            load_manifest(p)


class TestValidateAssetsExist:
    def test_all_present(self, tmp_path: Path):
        (tmp_path / "a.png").write_bytes(b"fake")
        m = LicenseManifest(assets=[AssetEntry(file="a.png", license="cc0")])
        assert validate_assets_exist(m, tmp_path) == []

    def test_missing_reported(self, tmp_path: Path):
        m = LicenseManifest(assets=[AssetEntry(file="gone.png", license="cc0")])
        missing = validate_assets_exist(m, tmp_path)
        assert missing == ["gone.png"]
