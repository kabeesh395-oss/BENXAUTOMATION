#!/usr/bin/env python3
"""Build a clean, text-only Agensi ZIP for the BENXAUTOMATION skill."""

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_FOLDER = "benxautomation-video-production"
PACKAGE_ROOT = ROOT / "agensi-skill" / SKILL_FOLDER
ALLOWED_SUFFIXES = {".md", ".py", ".txt", ".json", ".yaml", ".yml", ".toml"}


def validate_package() -> list[Path]:
    skill_file = PACKAGE_ROOT / "SKILL.md"
    if not skill_file.is_file():
        raise ValueError("Package is missing SKILL.md")
    content = skill_file.read_text(encoding="utf-8")
    frontmatter = re.match(r"^---\s*\n(?P<yaml>.*?)\n---\s*\n", content, re.DOTALL)
    if not frontmatter:
        raise ValueError("SKILL.md must begin with YAML frontmatter")
    for field in ("name:", "description:"):
        if not re.search(rf"(?m)^{re.escape(field)}\s*\S", frontmatter.group("yaml")):
            raise ValueError(f"SKILL.md frontmatter is missing {field[:-1]}")

    files = sorted(path for path in PACKAGE_ROOT.rglob("*") if path.is_file())
    if not files:
        raise ValueError("Package contains no files")
    for path in files:
        if path.is_symlink():
            raise ValueError(f"Symlinks are not allowed: {path}")
        if path.name.startswith(".") or path.name.lower() in {".env", "credentials.json", "client_secret.json"}:
            raise ValueError(f"Hidden or sensitive file is not allowed: {path}")
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            raise ValueError(f"Non-text or unsupported file type: {path}")
        path.read_text(encoding="utf-8")
    return files


def build_zip(output: Path) -> Path:
    files = validate_package()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive_name = Path(SKILL_FOLDER) / path.relative_to(PACKAGE_ROOT)
            archive.write(path, archive_name.as_posix())
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / f"{SKILL_FOLDER}.zip",
        help="Output ZIP path",
    )
    args = parser.parse_args()
    try:
        output = build_zip(args.output.resolve())
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))
    print(f"Built {output}")
    print(f"Files: {len(validate_package())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
