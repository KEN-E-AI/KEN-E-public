"""Local conftest for the Sprint 6 harness tests.

Some harness modules import `kene_api` (the API package). The KEN-E API
lives at `api/src/kene_api/`, so we prepend `api/` to `sys.path` here —
that mirrors the path layout the API's own pytest.ini sets up when tests
are run from the `api/` directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: harness tests that require a live API + ADC; "
        "skipped unless HARNESS_API_ENABLED=1",
    )


_REPO_ROOT = Path(__file__).resolve().parents[4]
_API_SRC = _REPO_ROOT / "api" / "src"
# Add `api/src` (not `api/`) so harness modules can `import kene_api.*`
# without dragging in `api/tests/` and shadowing this harness's own
# `tests.integration.*` namespace package.
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))
# Repo root for `from app.adk.tracking.compliance import ...`.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# Re-export the TTL fixture here so test files can use it as a parameter
# without importing it directly (which trips ruff's F811).
from tests.integration.stability.redis_ttl_fixture import (  # noqa: E402, F401
    ttl_controller,
)
