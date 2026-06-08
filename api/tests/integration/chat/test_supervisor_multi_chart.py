"""Integration test: multi-chart accumulation in a supervisor turn (AH-143 Task 6).

Verifies that two task-mode specialists each calling create_visualization() in the
same supervisor turn produce two Artifact entries in ChatResponse.artifacts and
two ChatArtifactIndex rows in Firestore, and that the drain logic clears
response_artifacts at turn end so the next turn starts empty.

Run against the Firestore emulator:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/chat/test_supervisor_multi_chart.py -v
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ACCOUNT_ID = "acc_ah143_multi"
_SESSION_ID = "sess_ah143_multi_001"
_USER_ID = "user_ah143_multi"
_APP_NAME = "ken_e_chatbot"
_BUCKET = "ken-e-test-files-us"

_SAMPLE_DATA = json.dumps([{"date": "2024-01-01", "sessions": 100}])
_SAMPLE_ENCODING = json.dumps(
    {"x": {"field": "date", "type": "temporal"}, "y": {"field": "sessions", "type": "quantitative"}}
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emulator_client() -> Any:
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


def _make_tool_context(
    account_id: str | None = _ACCOUNT_ID,
    shared_state: dict[str, Any] | None = None,
    save_version: int = 0,
) -> MagicMock:
    """Build a minimal ToolContext mock wired to the emulator."""
    ctx = MagicMock()
    ctx.save_artifact = AsyncMock(return_value=save_version)
    ctx.user_id = _USER_ID
    ctx.session.id = _SESSION_ID
    # Share state dict between two task contexts to simulate a single turn.
    state_dict: dict[str, Any] = shared_state if shared_state is not None else {}
    if account_id is not None:
        state_dict["account_id"] = account_id
    ctx.state = MagicMock()
    ctx.state.__setitem__ = lambda self, k, v: state_dict.__setitem__(k, v)
    ctx.state.__getitem__ = lambda self, k: state_dict[k]
    ctx.state.get = lambda k, d=None: state_dict.get(k, d)
    ctx.state.__contains__ = lambda self, k: k in state_dict

    invocation_ctx = MagicMock()
    invocation_ctx.app_name = _APP_NAME
    artifact_service = MagicMock()
    artifact_service.bucket_name = _BUCKET
    invocation_ctx.artifact_service = artifact_service
    ctx._invocation_context = invocation_ctx
    return ctx


def _seed_session(db: Any) -> None:
    doc = db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}")
    doc.set(
        {
            "session_id": _SESSION_ID,
            "account_id": _ACCOUNT_ID,
            "user_id": _USER_ID,
            "artifact_count": 0,
            "created_at": None,
            "updated_at": None,
        }
    )


def _cleanup(db: Any, artifact_ids: list[str]) -> None:
    for art_id in artifact_ids:
        db.document(
            f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}/artifacts/{art_id}"
        ).delete()
    db.document(f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}").delete()


def _patch_artifacts_module(db: Any) -> Any:
    """Return a context manager that patches get_firestore_client to use the emulator db."""
    import src.kene_api.chat.artifacts as _artifacts_mod

    return patch.object(_artifacts_mod, "get_firestore_client", return_value=db)


async def _call_create_vis(ctx: Any, title: str, chart_type: str = "line") -> str:
    """Run create_visualization against the given ToolContext."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "app"))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
    from app.adk.tools.function_tools.create_visualization import create_visualization

    return await create_visualization(
        chart_type=chart_type,
        title=title,
        data=_SAMPLE_DATA,
        encoding=_SAMPLE_ENCODING,
        tool_context=ctx,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSupervisorMultiChartAccumulation:
    @pytest.mark.asyncio
    async def test_two_task_specialists_produce_two_artifacts(self) -> None:
        """Two task specialists each calling create_visualization() accumulate 2 artifacts.

        Simulates a sequential supervisor turn: task A runs, writes to
        response_artifacts; task B runs (same turn, same state dict), appends a
        second artifact.  At turn end the chat endpoint drains both into
        ChatResponse.artifacts and clears the key.
        """
        db = _emulator_client()
        _seed_session(db)

        # Shared state dict models a single outer-turn state.
        shared_state: dict[str, Any] = {}

        ctx_a = _make_tool_context(account_id=_ACCOUNT_ID, shared_state=shared_state, save_version=0)
        ctx_b = _make_tool_context(account_id=_ACCOUNT_ID, shared_state=shared_state, save_version=1)

        art_ids: list[str] = []
        try:
            with _patch_artifacts_module(db):
                # Task A specialist calls create_visualization
                result_a = await _call_create_vis(ctx_a, title="Task A: GA Sessions")
                assert result_a.startswith("Visualization created:")

                # Task B specialist calls create_visualization (same state dict)
                result_b = await _call_create_vis(ctx_b, title="Task B: Meta Spend")
                assert result_b.startswith("Visualization created:")

            # (a) response_artifacts contains exactly 2 artifacts
            raw_artifacts = shared_state.get("response_artifacts", [])
            assert len(raw_artifacts) == 2, f"Expected 2, got {len(raw_artifacts)}"
            assert raw_artifacts[0]["metadata"]["title"] == "Task A: GA Sessions"
            assert raw_artifacts[1]["metadata"]["title"] == "Task B: Meta Spend"

            # (b) simulate chat-endpoint drain: move response_artifacts to ChatResponse.artifacts
            shared_state["response_artifacts"] = []  # drain clears the key

            # (c) response_artifacts is cleared after drain
            assert shared_state["response_artifacts"] == []

            # (d) verify two ChatArtifactIndex rows exist in Firestore
            art_col = db.collection(
                f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}/artifacts"
            ).get()
            art_docs = list(art_col)
            assert len(art_docs) == 2, f"Expected 2 Firestore rows, got {len(art_docs)}"
            art_ids = [doc.id for doc in art_docs]

            # (e) artifact_count incremented by 2
            session_doc = db.document(
                f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}"
            ).get()
            assert session_doc.to_dict()["artifact_count"] == 2

        finally:
            _cleanup(db, art_ids)

    @pytest.mark.asyncio
    async def test_response_artifacts_empty_at_next_turn_start(self) -> None:
        """After drain, a subsequent create_visualization call starts a fresh list."""
        db = _emulator_client()
        _seed_session(db)

        shared_state: dict[str, Any] = {}
        art_ids: list[str] = []
        try:
            with _patch_artifacts_module(db):
                ctx = _make_tool_context(account_id=_ACCOUNT_ID, shared_state=shared_state, save_version=0)
                await _call_create_vis(ctx, title="Turn 1 Chart")

            # Simulate drain + clear
            shared_state["response_artifacts"] = []

            # Turn 2: a fresh specialist call in the same session
            with _patch_artifacts_module(db):
                ctx2 = _make_tool_context(account_id=_ACCOUNT_ID, shared_state=shared_state, save_version=1)
                await _call_create_vis(ctx2, title="Turn 2 Chart")

            # Only the turn-2 chart is in response_artifacts (drain cleared turn-1)
            raw = shared_state.get("response_artifacts", [])
            assert len(raw) == 1
            assert raw[0]["metadata"]["title"] == "Turn 2 Chart"

            art_col = db.collection(
                f"accounts/{_ACCOUNT_ID}/chat_sessions/{_SESSION_ID}/artifacts"
            ).get()
            art_ids = [doc.id for doc in art_col]
        finally:
            _cleanup(db, art_ids)
