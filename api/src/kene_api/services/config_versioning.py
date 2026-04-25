"""Shared helpers for config admin routers.

Used by both :mod:`routers.agent_configs` and :mod:`routers.mcp_server_configs`
so version-bump + Firestore-safe user-id sanitization behavior stays in one
place (Sprint 6 Story 1.1.4-4 code review follow-up).
"""

from __future__ import annotations


def increment_version(current_version: str) -> str:
    """Bump a semver string's patch component by one.

    Handles both legacy 2-part (``vX.Y``) and semver 3-part (``vX.Y.Z``)
    formats. Prerelease suffixes (``-beta`` etc.) are stripped before
    incrementing.

    Args:
        current_version: Current version string (e.g., ``"v1.0.0"``, ``"v1.2"``).

    Returns:
        Incremented semver version (e.g., ``"v1.0.1"``).

    Raises:
        ValueError: If the input is not parseable as a 2- or 3-part semver.
    """
    version = current_version.strip() if current_version else ""
    if not version.startswith("v"):
        version = f"v{version}" if version else ""

    base = version[1:].split("-", 1)[0] if version.startswith("v") else ""
    parts = base.split(".") if base else []

    if len(parts) == 2:
        major, minor, patch = int(parts[0]), int(parts[1]), 0
    elif len(parts) == 3:
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    else:
        raise ValueError(
            f"Cannot increment version {current_version!r}: "
            f"expected vX.Y or vX.Y.Z format"
        )

    return f"v{major}.{minor}.{patch + 1}"


def sanitize_updated_by(email: str) -> str:
    """Sanitize an email for safe use as a Firestore nested-map field name.

    Firestore disallows ``.`` and ``$`` in field names; replace with ``_``.
    Truncates to 100 chars. Empty inputs normalize to ``"unknown"``.
    """
    if not email:
        return "unknown"
    return email.replace(".", "_").replace("$", "_")[:100]
