"""Rights and copyright verification module for Podcast-to-Shorts.

Ensures strict compliance, transparent declarations, and prevents unauthorized
distribution of third-party footage or unlicensed audio.
"""

from __future__ import annotations

from typing import List, Tuple

from benxautomation.logger import get_logger
from benxautomation.podcast.errors import RightsVerificationError
from benxautomation.podcast.models import RightsDeclaration

log = get_logger(__name__)

LEGAL_DISCLAIMER_TEXT = (
    "LEGAL NOTICE & COPYRIGHT COMPLIANCE DISCLAIMER:\n"
    "Attribution alone does NOT grant copyright usage rights. Automated checks cannot\n"
    "guarantee copyright clearance, fair use protection, or immunity from copyright claims.\n"
    "You must hold verifiable ownership, an explicit license, or authorized written\n"
    "permission from the copyright holder before processing or publishing third-party content.\n"
    "Content labeled 'copyright-free' or 'creative commons' without primary documentation\n"
    "must not be treated as cleared."
)

VALID_OWNERSHIP_TYPES = {
    "creator_owned": "Original creator / Sole copyright owner",
    "licensed": "Commercially or non-commercially licensed with documentation",
    "permitted": "Explicit written permission from rights holder",
    "public_domain": "Verified Public Domain material",
}

VALID_MUSIC_SOURCES = {
    "cleared": "Directly licensed audio with explicit sync/commercial rights",
    "royalty_free": "Verified royalty-free track from an authorized library",
    "no_music": "Podcast speech only; no background music track",
    "unlicensed": "Unclear / Commercial third-party music (FLAGGED FOR BLOCK)",
}


class RightsReviewer:
    """Validates user rights declarations before allowing rendering or publication."""

    @staticmethod
    def get_disclaimer() -> str:
        """Return the official statutory legal disclaimer."""
        return LEGAL_DISCLAIMER_TEXT

    @classmethod
    def validate_declaration(cls, declaration: RightsDeclaration) -> tuple[bool, list[str]]:
        """Perform strict inspection of the rights declaration.

        Returns (is_valid, list_of_errors_or_flags).
        """
        errors: list[str] = []

        if not declaration.disclaimer_accepted:
            errors.append(
                "You must acknowledge and accept the legal copyright compliance disclaimer."
            )

        if not declaration.user_confirmed_rights:
            errors.append(
                "You must explicitly confirm that you possess ownership, licensing, or valid permissions."
            )

        if declaration.ownership_type not in VALID_OWNERSHIP_TYPES:
            errors.append(
                f"Invalid ownership type '{declaration.ownership_type}'. Must be one of: {list(VALID_OWNERSHIP_TYPES.keys())}"
            )

        # Licensed / Permitted requirements
        if declaration.ownership_type == "licensed":
            if not declaration.license_evidence or len(declaration.license_evidence.strip()) < 5:
                errors.append(
                    "Licensed content requires verifiable license evidence (e.g. license agreement reference, URL, or invoice ID)."
                )

        if declaration.ownership_type == "permitted":
            if not declaration.rights_holder or len(declaration.rights_holder.strip()) < 2:
                errors.append(
                    "Permitted third-party content requires specifying the verified rights holder or entity granting permission."
                )
            if not declaration.license_evidence or len(declaration.license_evidence.strip()) < 5:
                errors.append(
                    "Permitted third-party content requires reference to the written permission documentation."
                )

        # Music clearance checks
        if declaration.music_source not in VALID_MUSIC_SOURCES:
            errors.append(
                f"Invalid music source '{declaration.music_source}'. Must be one of: {list(VALID_MUSIC_SOURCES.keys())}"
            )
        elif declaration.music_source == "unlicensed":
            errors.append(
                "CRITICAL: Unlicensed background music or third-party audio detected. "
                "Publication is blocked until music is removed or cleared with a valid license."
            )

        # Attribution requirements check
        if declaration.ownership_type in ("licensed", "permitted") and declaration.attribution_required:
            if not declaration.attribution_text or len(declaration.attribution_text.strip()) < 5:
                errors.append(
                    "Attribution is required for this license/permission, but no attribution text was specified."
                )

        return (len(errors) == 0, errors)

    @classmethod
    def assert_publishing_allowed(cls, declaration: RightsDeclaration) -> None:
        """Raise RightsVerificationError if declaration is invalid or incomplete."""
        valid, errors = cls.validate_declaration(declaration)
        if not valid:
            err_msg = "\n  - ".join(errors)
            raise RightsVerificationError(
                f"Rights verification failed. Publishing is strictly blocked:\n  - {err_msg}"
            )
        log.info("Rights verification passed for ownership type '%s'", declaration.ownership_type)
