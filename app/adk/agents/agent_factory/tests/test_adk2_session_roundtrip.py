"""ADK 2.0 session round-trip test — AH-110 / AH-PRD-13 §7 AC #3.

Ports AH-99 probe-5 (docs/spike-adk2/probe-5-session-service-schema.py) into CI
as a deterministic offline test. The live VertexAiSessionService round-trip is owned
by AH-112 (against a deployed 2.0 agent); this file covers the model-level invariant:

  ADK 2.0 Event.node_info (NodeInfo) and Event.isolation_scope survive
  InMemorySessionService.append_event() → get_session() and Event.model_dump()
  → Event.model_validate() round-trips on google-adk==2.0.0.

Why this matters (AH-PRD-13 §9 behavioural-drift risk):
  VertexAiSessionService serialises events through a Pydantic model layer before
  storing them in the Vertex AI managed-session backend. If node_info or
  isolation_scope are silently stripped at the model boundary, the chat_sessions
  Firestore mirror and any downstream trace consumers (MER-E) would lose the
  ADK 2.0 task-mode context. This test catches that regression at the Pydantic
  model layer using the same in-memory backend — if the fields survive here but
  not against the live backend, AH-112 will surface the divergence.

Coverage:
  1. InMemorySessionService round-trip: node_info.path, node_info.output_for,
     and isolation_scope survive append_event() → get_session() via STORED events.
  2. Pydantic serialisation round-trip: Event.model_dump() preserves both fields;
     Event.model_validate(dump) reconstructs them faithfully.
  3. Two event shapes are covered: task-mode (path + output_for) and
     dynamic-graph (path only), mirroring the probe-5 event shapes.

Scope note:
  - Live VertexAiSessionService round-trip: AH-112.
  - Supervisor-orchestration turn shape: AH-PRD-05.
  - This test uses InMemorySessionService only.
"""

from __future__ import annotations

import importlib.util as _importlib_util
import sys as _sys
import types as _types
from pathlib import Path as _Path

import pytest
from google.adk.events import Event
from google.adk.events.event import NodeInfo
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

# ---------------------------------------------------------------------------
# Event constructors (mirroring probe-5 shapes)
# ---------------------------------------------------------------------------


def _make_task_mode_event() -> Event:
    """ADK 2.0 event with task-mode node_info (path + output_for) and isolation_scope."""
    return Event(
        author="task_specialist",
        invocation_id="inv-task-001",
        isolation_scope="fc_task_mode_abc123",
        node_info=NodeInfo(
            path="/coordinator/task_mode_specialist",
            output_for=["task_1"],
        ),
        content=Content(
            role="model",
            parts=[Part(text="Task completed: Paris is the capital of France.")],
        ),
    )


def _make_dynamic_graph_event() -> Event:
    """ADK 2.0 event with dynamic-graph node_info (path only) and isolation_scope."""
    return Event(
        author="specialist_a",
        invocation_id="inv-dyngraph-001",
        isolation_scope="fc_dyngraph_xyz789",
        node_info=NodeInfo(
            path="/coordinator/run_node_branch_a",
        ),
        content=Content(
            role="model",
            parts=[Part(text="Branch A analysis complete.")],
        ),
    )


# ---------------------------------------------------------------------------
# TestInMemorySessionRoundtrip
# ---------------------------------------------------------------------------


class TestInMemorySessionRoundtrip:
    """node_info and isolation_scope survive InMemorySessionService storage.

    These tests assert the model-level Pydantic serialisation contract.
    AH-112 owns the live VertexAiSessionService counterpart.
    """

    @pytest.mark.asyncio
    async def test_task_mode_all_fields_survive(self) -> None:
        """All ADK 2.0 fields survive the in-memory session round-trip for a task-mode event.

        Asserts node_info.path, node_info.output_for, and isolation_scope in one
        round-trip per T-8 convention (test the entire structure in one assertion).
        If this fails, ADK 2.0 stripped one of these fields at the Pydantic model
        layer — check VertexAiSessionService behaviour in AH-112.
        """
        svc = InMemorySessionService()
        sess = await svc.create_session(app_name="rt_test", user_id="u1")

        event = _make_task_mode_event()
        await svc.append_event(sess, event)

        retrieved = await svc.get_session(app_name="rt_test", user_id="u1", session_id=sess.id)
        assert retrieved is not None
        stored = next(
            (e for e in retrieved.events if getattr(e, "author", None) == "task_specialist"),
            None,
        )
        assert stored is not None, "task_specialist event must appear in stored events"
        assert stored.node_info is not None, (
            "node_info must not be None after InMemorySessionService round-trip."
        )
        assert stored.node_info.path == "/coordinator/task_mode_specialist", (
            f"node_info.path must survive round-trip. Got: {stored.node_info.path!r}"
        )
        assert stored.node_info.output_for == ["task_1"], (
            f"node_info.output_for must survive round-trip. Got: {stored.node_info.output_for!r}"
        )
        assert stored.isolation_scope == "fc_task_mode_abc123", (
            f"isolation_scope must survive round-trip. Got: {stored.isolation_scope!r}"
        )

    @pytest.mark.asyncio
    async def test_dynamic_graph_event_fields_survive(self) -> None:
        """node_info.path and isolation_scope survive for a dynamic-graph-shape event."""
        svc = InMemorySessionService()
        sess = await svc.create_session(app_name="rt_test4", user_id="u4")

        event = _make_dynamic_graph_event()
        await svc.append_event(sess, event)

        retrieved = await svc.get_session(app_name="rt_test4", user_id="u4", session_id=sess.id)
        assert retrieved is not None
        stored = next(
            (e for e in retrieved.events if getattr(e, "author", None) == "specialist_a"),
            None,
        )
        assert stored is not None, "specialist_a event must appear in stored events"
        assert stored.node_info is not None
        assert stored.node_info.path == "/coordinator/run_node_branch_a", (
            f"dynamic-graph node_info.path must survive round-trip. "
            f"Got: {stored.node_info.path!r}"
        )
        assert stored.isolation_scope == "fc_dyngraph_xyz789", (
            f"dynamic-graph isolation_scope must survive round-trip. "
            f"Got: {stored.isolation_scope!r}"
        )

    @pytest.mark.asyncio
    async def test_multiple_events_both_survive(self) -> None:
        """Two events with distinct isolation scopes both survive in the same session."""
        svc = InMemorySessionService()
        sess = await svc.create_session(app_name="rt_test5", user_id="u5")

        task_event = _make_task_mode_event()
        dyn_event = _make_dynamic_graph_event()
        await svc.append_event(sess, task_event)
        await svc.append_event(sess, dyn_event)

        retrieved = await svc.get_session(app_name="rt_test5", user_id="u5", session_id=sess.id)
        assert retrieved is not None
        by_author = {e.author: e for e in retrieved.events if getattr(e, "author", None)}

        assert "task_specialist" in by_author, "task_specialist event must be stored"
        assert "specialist_a" in by_author, "specialist_a event must be stored"
        assert by_author["task_specialist"].isolation_scope == "fc_task_mode_abc123"
        assert by_author["specialist_a"].isolation_scope == "fc_dyngraph_xyz789"


# ---------------------------------------------------------------------------
# TestPydanticRoundtrip
# ---------------------------------------------------------------------------


class TestPydanticRoundtrip:
    """node_info and isolation_scope survive Event.model_dump() → model_validate().

    VertexAiSessionService serialises events through this Pydantic layer before
    persisting them. If either field is dropped here, it cannot survive the live
    backend round-trip. These tests catch Pydantic-layer regressions independently
    of the session backend.
    """

    def test_task_mode_model_dump_preserves_node_info_path(self) -> None:
        event = _make_task_mode_event()
        dumped = event.model_dump()
        assert dumped.get("node_info") is not None, "model_dump must include node_info"
        assert dumped["node_info"]["path"] == "/coordinator/task_mode_specialist", (
            f"model_dump must preserve node_info.path. Got: {dumped['node_info']!r}"
        )

    def test_task_mode_model_dump_preserves_node_info_output_for(self) -> None:
        event = _make_task_mode_event()
        dumped = event.model_dump()
        assert dumped["node_info"]["output_for"] == ["task_1"], (
            f"model_dump must preserve node_info.output_for. Got: {dumped['node_info']!r}"
        )

    def test_task_mode_model_dump_preserves_isolation_scope(self) -> None:
        event = _make_task_mode_event()
        dumped = event.model_dump()
        assert dumped.get("isolation_scope") == "fc_task_mode_abc123", (
            f"model_dump must preserve isolation_scope. Got: {dumped.get('isolation_scope')!r}"
        )

    def test_task_mode_model_validate_round_trip(self) -> None:
        """Full model_dump → model_validate round-trip preserves both fields."""
        event = _make_task_mode_event()
        dumped = event.model_dump()
        restored = Event.model_validate(dumped)

        assert restored.node_info is not None
        assert restored.node_info.path == "/coordinator/task_mode_specialist", (
            f"model_validate must restore node_info.path. Got: {restored.node_info.path!r}"
        )
        assert restored.node_info.output_for == ["task_1"], (
            f"model_validate must restore node_info.output_for. Got: {restored.node_info.output_for!r}"
        )
        assert restored.isolation_scope == "fc_task_mode_abc123", (
            f"model_validate must restore isolation_scope. Got: {restored.isolation_scope!r}"
        )

    def test_dynamic_graph_model_validate_round_trip(self) -> None:
        """Dynamic-graph event survives model_dump → model_validate."""
        event = _make_dynamic_graph_event()
        dumped = event.model_dump()
        restored = Event.model_validate(dumped)

        assert restored.node_info is not None
        assert restored.node_info.path == "/coordinator/run_node_branch_a"
        assert restored.isolation_scope == "fc_dyngraph_xyz789"


# ---------------------------------------------------------------------------
# TestChatSessionsMirrorAllowlist
# ---------------------------------------------------------------------------

def _load_side_table_handlers_allowed_delta_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> frozenset[str]:
    """Load _ALLOWED_DELTA_FIELDS from side_table_handlers without FastAPI deps.

    Uses spec_from_file_location with the full dotted module name so that the
    relative import `from .side_table import get_chat_side_table_service`
    resolves against our stub, not the real package.  Heavy dependencies
    (google.cloud.firestore, shared.turn_delta) are stubbed via monkeypatch so
    the ADK venv does not need the API service's full dependency set, and the
    stubs are automatically removed after the test completes (no sys.modules
    pollution between tests).

    Returns the frozenset value, which is a plain literal at module scope —
    independent of any runtime behaviour.
    """
    _repo_root = _Path(__file__).resolve().parents[5]
    _handlers_path = (
        _repo_root / "api" / "src" / "kene_api" / "chat" / "side_table_handlers.py"
    )

    # Register stubs for heavy deps via monkeypatch so they are auto-removed
    # after the test.  Only register stubs for modules not already present so
    # we don't overwrite real packages (e.g., google.adk is present in this venv).
    _stub_specs: list[tuple[str, dict[str, object]]] = [
        ("google.api_core", {}),
        ("google.api_core.exceptions", {}),
        ("google.cloud.firestore", {}),
        ("shared", {}),
        ("shared.turn_delta", {"TurnDelta": type("TurnDelta", (), {})}),
        ("kene_api", {}),
        ("kene_api.chat", {}),
        # Relative import target: `from .side_table import get_chat_side_table_service`
        ("kene_api.chat.side_table", {"get_chat_side_table_service": lambda: None}),
    ]
    for _mod_name, _attrs in _stub_specs:
        if _mod_name not in _sys.modules:
            _stub = _types.ModuleType(_mod_name)
            for _k, _v in _attrs.items():
                setattr(_stub, _k, _v)
            monkeypatch.setitem(_sys.modules, _mod_name, _stub)

    # Load with the full dotted name so __package__ is inferred as "kene_api.chat"
    # and the relative import can look up sys.modules["kene_api.chat.side_table"].
    _full_name = "kene_api.chat.side_table_handlers"
    if _full_name in _sys.modules:
        # Already loaded in a prior test iteration — return from cache.
        return _sys.modules[_full_name]._ALLOWED_DELTA_FIELDS  # type: ignore[attr-defined]

    _spec = _importlib_util.spec_from_file_location(_full_name, str(_handlers_path))
    assert _spec is not None, f"Could not locate {_handlers_path}"
    _mod = _importlib_util.module_from_spec(_spec)
    _mod.__package__ = "kene_api.chat"
    monkeypatch.setitem(_sys.modules, _full_name, _mod)  # register before exec
    assert _spec.loader is not None
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

    return _mod._ALLOWED_DELTA_FIELDS  # type: ignore[attr-defined]


class TestChatSessionsMirrorAllowlist:
    """CI guard: _ALLOWED_DELTA_FIELDS is disjoint from ADK 2.0 session-layer fields.

    The chat_sessions Firestore mirror is written via _ALLOWED_DELTA_FIELDS in
    api/src/kene_api/chat/side_table_handlers.py.  ADK 2.0 events gain two
    additive fields (node_info, isolation_scope) that must NOT be copied into
    the mirror — they are session-layer internals, not user-facing chat-session
    metadata.  This test pins that invariant in CI so a future PR that accidentally
    adds node_info or isolation_scope to the allow-list fails the app-adk-tests
    Cloud Build step (per AH-PRD-13 §10 reference list).

    AH-112 owns the live VertexAiSessionService counterpart that verifies the
    mirror row on a deployed engine.  This test guards the code-level gate.
    """

    def test_adk2_fields_disjoint_from_allowed_delta_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_ALLOWED_DELTA_FIELDS must be disjoint from {node_info, isolation_scope}.

        If this test fails, a PR added at least one of these ADK 2.0 session-layer
        fields to the mirror allow-list, which would cause task-mode metadata to
        leak into the chat_sessions side-table.  Revert the allow-list change in
        api/src/kene_api/chat/side_table_handlers.py.
        """
        _adk2_session_fields: frozenset[str] = frozenset({"node_info", "isolation_scope"})
        allowed = _load_side_table_handlers_allowed_delta_fields(monkeypatch)
        leaked = allowed & _adk2_session_fields
        assert not leaked, (
            f"ADK 2.0 session-layer field(s) found in _ALLOWED_DELTA_FIELDS: {leaked!r}. "
            "These fields (node_info, isolation_scope) are ADK 2.0 task-mode internals and "
            "must never be mirrored into the chat_sessions Firestore side-table. "
            "Revert the allow-list change in api/src/kene_api/chat/side_table_handlers.py."
        )
