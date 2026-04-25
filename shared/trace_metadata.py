"""Trace metadata utilities for KEN-E span instrumentation.

Provides semver validation for agent versions and other trace metadata helpers.
Used by config_loader.py and tracing callbacks to ensure trace compliance
with docs/trace-structure-spec.md.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

SEMVER_PATTERN = re.compile(r"^v?\d+\.\d+\.\d+(-[\w.]+)?$")

DEFAULT_VERSION = "v0.0.0"


def validate_semver(version: Any) -> str:
    """Validate and normalize a version string to semver format.

    Args:
        version: Version string to validate (e.g., "v1.2.3", "1.0.0", "v1.0.0-beta.1")

    Returns:
        Normalized version string with 'v' prefix, or DEFAULT_VERSION if invalid.
    """
    if not version or not isinstance(version, str):
        logger.warning(
            f"Invalid agent version: {version!r} (not a string). "
            f"Using default: {DEFAULT_VERSION}"
        )
        return DEFAULT_VERSION

    version = version.strip()

    if not SEMVER_PATTERN.match(version):
        logger.warning(
            f"Invalid agent version: {version!r} (does not match semver pattern). "
            f"Using default: {DEFAULT_VERSION}"
        )
        return DEFAULT_VERSION

    if not version.startswith("v"):
        version = f"v{version}"

    return version


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse a validated semver string into (major, minor, patch).

    Args:
        version: A validated semver string (e.g., "v1.2.3")

    Returns:
        Tuple of (major, minor, patch)

    Raises:
        ValueError: If version cannot be parsed
    """
    v = version.lstrip("v")
    # Strip prerelease suffix (e.g., "1.0.0-beta.1" → "1.0.0")
    base = v.split("-", 1)[0]
    parts = base.split(".")
    if len(parts) != 3:
        raise ValueError(f"Cannot parse '{version}' as semver (expected vX.Y.Z)")
    return int(parts[0]), int(parts[1]), int(parts[2])
