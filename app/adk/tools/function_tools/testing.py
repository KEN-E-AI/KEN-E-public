"""Shared test helpers for function_tools tests.

Exported for use by orchestration and e2e test modules.
"""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock


def make_register_artifact_mock() -> AsyncMock:
    """Return a fresh AsyncMock suitable for patching register_artifact."""
    return AsyncMock(return_value=MagicMock())


def register_artifact_sys_modules_patch(mock_fn: AsyncMock) -> dict[str, Any]:
    """Build the sys.modules patch dict for the deferred register_artifact import.

    Inject this via ``patch.dict(sys.modules, ...)`` around any test that
    calls ``create_visualization()`` with a real ``tool_context``. The stub
    ensures the deferred ``from shared.chat_artifacts import register_artifact``
    inside the function body resolves to ``mock_fn`` without exercising the real
    GCS/Firestore write path. (The wrapper moved from kene_api to shared/ so the
    Agent Engine can import it — see DESIGN-REVIEW-LOG.)

    Must be used with ``import pydantic.root_model`` at module level in test
    files to prevent the lazy-load / patch.dict teardown KeyError — see
    test_supervisor_artifacts.py for the rationale.
    """
    stub_mod = ModuleType("shared.chat_artifacts")
    stub_mod.register_artifact = mock_fn  # type: ignore[attr-defined]
    shared_mod = sys.modules.get("shared") or ModuleType("shared")
    return {
        "shared": shared_mod,
        "shared.chat_artifacts": stub_mod,
    }
