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
    """Build the sys.modules patch dict for the deferred kene_api import.

    Inject this via ``patch.dict(sys.modules, ...)`` around any test that
    calls ``create_visualization()`` with a real ``tool_context``. The stub
    ensures the deferred ``from kene_api.chat.artifacts import register_artifact``
    inside the function body resolves to ``mock_fn`` without requiring the real
    kene_api package.

    Must be used with ``import pydantic.root_model`` at module level in test
    files to prevent the lazy-load / patch.dict teardown KeyError — see
    test_supervisor_artifacts.py for the rationale.
    """
    stub_mod = ModuleType("kene_api.chat.artifacts")
    stub_mod.register_artifact = mock_fn  # type: ignore[attr-defined]
    kene_api_mod = sys.modules.get("kene_api") or ModuleType("kene_api")
    kene_api_chat_mod = sys.modules.get("kene_api.chat") or ModuleType("kene_api.chat")
    return {
        "kene_api": kene_api_mod,
        "kene_api.chat": kene_api_chat_mod,
        "kene_api.chat.artifacts": stub_mod,
    }
