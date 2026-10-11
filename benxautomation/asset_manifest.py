"""Asset license manifest validation.

Every asset used in a rendered video must be declared in a YAML manifest
with its license type and attribution.  This module validates that manifest.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, field_validator

from benxautomation.errors import ManifestError


class AssetEntry(BaseModel):
    """A single entry in the license manifest."""
    file: str
    license: str
    attribution: str = ""
    source_url: Optional[str] = None
    asset_origin: Optional[str] = None
    commercial_terms_verified: bool = True
    terms_reference: Optional[str] = None

    @field_validator("license")
    @classmethod
    def _known_license(cls, v: str) -> str:
        allowed = {
            "cc0", "cc-by-4.0", "cc-by-sa-4.0", "mit", "apache-2.0",
            "public-domain", "royalty-free", "original", "ai_generated",
        }
        if v.lower() not in allowed:
            raise ValueError(
                f"Unknown license '{v}'. Allowed: {sorted(allowed)}"
            )
        return v.lower()


class LicenseManifest(BaseModel):
    """The full license manifest for project assets."""
    assets: list[AssetEntry]


def load_manifest(path: Path | str) -> LicenseManifest:
    """Load and validate a license manifest YAML file.

    Raises ``ManifestError`` on missing file or validation failure.
    """
    path = Path(path)
    if not path.is_file():
        raise ManifestError(f"Manifest file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if raw is None:
            raw = {"assets": []}
        return LicenseManifest(**raw)
    except ManifestError:
        raise
    except Exception as exc:
        raise ManifestError(f"Invalid manifest: {exc}") from exc


def validate_assets_exist(manifest: LicenseManifest, base_dir: Path) -> list[str]:
    """Return a list of manifest entries whose files are missing on disk."""
    missing: list[str] = []
    for entry in manifest.assets:
        if not (base_dir / entry.file).is_file():
            missing.append(entry.file)
    return missing
