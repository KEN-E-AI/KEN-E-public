"""Tests for app.adk.tracking.specialists_spans (CH-58).

Modelled on app/adk/tracking/tests/test_skill_spans.py — same
_SimpleState / _FakeIC / _FakeCallbackContext fakes, same
_GET_CLIENT_PATH patching idiom.

Test cases:
  (a) Happy path — state has 2 specialists; span emitted with correct
      op and attributes.
  (b) Empty roster — key present, list []; span emitted with
      specialist_count=0.
  (c) State key MISSING — no span emitted; create_call NOT invoked.
  (d) _weave_get_client is None — no exception, callback returns None.
  (e) account_id absent — span emitted with account_id="unknown".
  (f) create_call raises — caught, logged, no exception propagated.
  (g) agent_id equals name invariant.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

_GET_CLIENT_PATH = "app.adk.tracking.specialists_spans._weave_get_client"
_CALL_CTX_PATH = "app.adk.tracking.specialists_spans._weave_call_context"


# ---------------------------------------------------------------------------
# Minimal fakes (mirrors test_skill_spans.py)
# ---------------------------------------------------------------------------


class _SimpleState(dict):
    """dict subclass so hasattr(state, 'get') and state['x'] = v both work."""


@dataclass
class _FakeIC:
    agent: Any = None


@dataclass
class _FakeCallbackContext:
    state: Any = field(default_factory=_SimpleState)
    _invocation_context: Any = field(default_factory=_FakeIC)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(
    specialists: list[dict] | None = None,
    *,
    account_id: str = "acc_test",
    omit_key: bool = False,
) -> _FakeCallbackContext:
    """Return a callback context with the given specialists in state.

    ``omit_key=True`` leaves ``_available_specialists`` absent from state,
    simulating a capture failure (missing-key degradation case).
    """
    state: dict[str, Any] = {"account_id": account_id}
    if not omit_key:
        state["_available_specialists"] = specialists if specialists is not None else []
    return _FakeCallbackContext(state=_SimpleState(state))


def _make_client_mock() -> MagicMock:
    client = MagicMock()
    fake_call = MagicMock()
    fake_call.id = "call-id-123"
    client.create_call.return_value = fake_call
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSpecialistsSpanBeforeAgentCallback:
    """Tests for specialists_span_before_agent_callback."""

    def _run(
        self,
        ctx: _FakeCallbackContext,
        client: MagicMock | None = None,
        *,
        call_ctx: MagicMock | None = None,
    ) -> Any:
        from app.adk.tracking.specialists_spans import (
            specialists_span_before_agent_callback,
        )

        effective_client = client or _make_client_mock()
        effective_call_ctx = call_ctx or MagicMock()
        with (
            patch(_GET_CLIENT_PATH, return_value=effective_client),
            patch(_CALL_CTX_PATH, effective_call_ctx),
        ):
            return specialists_span_before_agent_callback(ctx)

    # (a) Happy path -------------------------------------------------------

    def test_happy_path_emits_span_with_correct_op(self) -> None:
        """Span created with op='specialists.list'."""
        specs = [
            {
                "name": "ga_specialist",
                "description": "GA expert",
                "agent_id": "ga_specialist",
            },
            {
                "name": "seo_specialist",
                "description": "SEO expert",
                "agent_id": "seo_specialist",
            },
        ]
        ctx = _make_ctx(specialists=specs, account_id="acc_1")
        client = _make_client_mock()
        result = self._run(ctx, client)

        assert result is None
        client.create_call.assert_called_once()
        call_kwargs = client.create_call.call_args[1]
        assert call_kwargs["op"] == "specialists.list"

    def test_happy_path_attributes_match_specialist_list(self) -> None:
        """Span attributes carry specialist_count and full specialists array."""
        specs = [
            {
                "name": "ga_specialist",
                "description": "GA expert",
                "agent_id": "ga_specialist",
            },
            {
                "name": "seo_specialist",
                "description": "SEO expert",
                "agent_id": "seo_specialist",
            },
        ]
        ctx = _make_ctx(specialists=specs, account_id="acc_1")
        client = _make_client_mock()
        self._run(ctx, client)

        attrs = client.create_call.call_args[1]["attributes"]
        assert attrs["account_id"] == "acc_1"
        assert attrs["specialist_count"] == 2
        assert attrs["specialists"] == specs

    def test_happy_path_uses_stack_true(self) -> None:
        """Span is nested under the active root span via use_stack=True."""
        specs = [{"name": "s", "description": "d", "agent_id": "s"}]
        ctx = _make_ctx(specialists=specs)
        client = _make_client_mock()
        self._run(ctx, client)

        assert client.create_call.call_args[1]["use_stack"] is True

    def test_happy_path_finishes_call(self) -> None:
        """finish_call is invoked with output={'status': 'ok'}."""
        specs = [{"name": "s", "description": "d", "agent_id": "s"}]
        ctx = _make_ctx(specialists=specs)
        client = _make_client_mock()
        self._run(ctx, client)

        client.finish_call.assert_called_once()
        args, kwargs = client.finish_call.call_args
        # finish_call is called as: client.finish_call(call, output={"status": "ok"})
        output = kwargs.get("output") or (args[1] if len(args) > 1 else None)
        assert output == {"status": "ok"}

    def test_happy_path_pops_call_from_call_context(self) -> None:
        """call_context.pop_call is invoked to clean up the Weave stack."""
        specs = [{"name": "s", "description": "d", "agent_id": "s"}]
        ctx = _make_ctx(specialists=specs)
        client = _make_client_mock()
        call_ctx = MagicMock()
        self._run(ctx, client, call_ctx=call_ctx)

        call_ctx.pop_call.assert_called_once()

    # (b) Empty roster ------------------------------------------------------

    def test_empty_roster_span_emitted(self) -> None:
        """Empty list → span IS emitted (create_call.call_count == 1)."""
        ctx = _make_ctx(specialists=[], account_id="acc_empty")
        client = _make_client_mock()
        self._run(ctx, client)

        assert client.create_call.call_count == 1

    def test_empty_roster_specialist_count_is_zero(self) -> None:
        ctx = _make_ctx(specialists=[])
        client = _make_client_mock()
        self._run(ctx, client)

        attrs = client.create_call.call_args[1]["attributes"]
        assert attrs["specialist_count"] == 0
        assert attrs["specialists"] == []

    # (c) State key MISSING -------------------------------------------------

    def test_missing_state_key_no_span_emitted(self) -> None:
        """Missing key → create_call.call_count == 0 (degradation signal)."""
        ctx = _make_ctx(omit_key=True)
        client = _make_client_mock()
        result = self._run(ctx, client)

        assert result is None
        assert client.create_call.call_count == 0

    def test_missing_state_key_callback_returns_none(self) -> None:
        ctx = _make_ctx(omit_key=True)
        client = _make_client_mock()
        result = self._run(ctx, client)
        assert result is None

    # (d) Weave client absent -----------------------------------------------

    def test_weave_client_none_no_exception(self) -> None:
        """When _weave_get_client is None, callback returns None without error."""
        from app.adk.tracking.specialists_spans import (
            specialists_span_before_agent_callback,
        )

        ctx = _make_ctx(
            specialists=[{"name": "s", "description": "d", "agent_id": "s"}]
        )
        with patch(_GET_CLIENT_PATH, None):
            result = specialists_span_before_agent_callback(ctx)

        assert result is None

    def test_weave_client_returns_none_no_span(self) -> None:
        """When get_client() returns None/falsy, no span is emitted."""
        from app.adk.tracking.specialists_spans import (
            specialists_span_before_agent_callback,
        )

        ctx = _make_ctx(
            specialists=[{"name": "s", "description": "d", "agent_id": "s"}]
        )
        with patch(_GET_CLIENT_PATH, return_value=None):
            result = specialists_span_before_agent_callback(ctx)

        assert result is None

    # (e) account_id absent -------------------------------------------------

    def test_missing_account_id_defaults_to_unknown(self) -> None:
        """account_id defaults to 'unknown' when absent from state."""
        state = _SimpleState({"_available_specialists": []})
        ctx = _FakeCallbackContext(state=state)
        client = _make_client_mock()
        self._run(ctx, client)

        attrs = client.create_call.call_args[1]["attributes"]
        assert attrs["account_id"] == "unknown"

    # (f) create_call raises ------------------------------------------------

    def test_create_call_raises_no_exception_propagated(self, caplog) -> None:
        """If create_call raises, it is caught, logged, and the callback returns None."""
        from app.adk.tracking.specialists_spans import (
            specialists_span_before_agent_callback,
        )

        ctx = _make_ctx(
            specialists=[{"name": "s", "description": "d", "agent_id": "s"}]
        )
        mock_client = MagicMock()
        mock_client.create_call.side_effect = RuntimeError("weave exploded")

        with (
            caplog.at_level(
                logging.WARNING, logger="app.adk.tracking.specialists_spans"
            ),
            patch(_GET_CLIENT_PATH, return_value=mock_client),
            patch(_CALL_CTX_PATH, MagicMock()),
        ):
            result = specialists_span_before_agent_callback(ctx)

        assert result is None
        assert any("non-blocking" in r.message for r in caplog.records)

    # (f2) finish_call raises -----------------------------------------------

    def test_finish_call_raises_no_exception_propagated(self, caplog) -> None:
        """If finish_call raises, it is caught by the outer handler; callback returns None."""
        from app.adk.tracking.specialists_spans import (
            specialists_span_before_agent_callback,
        )

        ctx = _make_ctx(
            specialists=[{"name": "s", "description": "d", "agent_id": "s"}]
        )
        mock_client = _make_client_mock()
        mock_client.finish_call.side_effect = RuntimeError("finish exploded")

        with (
            caplog.at_level(
                logging.WARNING, logger="app.adk.tracking.specialists_spans"
            ),
            patch(_GET_CLIENT_PATH, return_value=mock_client),
            patch(_CALL_CTX_PATH, MagicMock()),
        ):
            result = specialists_span_before_agent_callback(ctx)

        assert result is None
        assert any("non-blocking" in r.message for r in caplog.records)

    # (f3) non-list specialists type guard ----------------------------------

    def test_non_list_specialists_skips_span(self, caplog) -> None:
        """If state['_available_specialists'] has an unexpected type, skip emission."""
        from app.adk.tracking.specialists_spans import (
            specialists_span_before_agent_callback,
        )

        state = _SimpleState(
            {"_available_specialists": "not-a-list", "account_id": "acc_x"}
        )
        ctx = _FakeCallbackContext(state=state)
        client = _make_client_mock()

        with (
            caplog.at_level(
                logging.WARNING, logger="app.adk.tracking.specialists_spans"
            ),
            patch(_GET_CLIENT_PATH, return_value=client),
            patch(_CALL_CTX_PATH, MagicMock()),
        ):
            result = specialists_span_before_agent_callback(ctx)

        assert result is None
        assert client.create_call.call_count == 0
        assert any("unexpected type" in r.message for r in caplog.records)

    # (g) agent_id == name invariant ----------------------------------------

    def test_agent_id_equals_name_invariant(self) -> None:
        """The captured specialist roster has agent_id == name for every entry.

        This is a regression guard for the ADK contract that
        agent.name == Firestore doc_id (specialist_runtime.py:510-512, 572, 626).
        If a future refactor decouples these, this test fails before the spec
        contract in docs/trace-structure-spec.md §16.4 is updated.
        """
        specs = [
            {"name": "ga_spec", "description": "GA", "agent_id": "ga_spec"},
            {"name": "seo_spec", "description": "SEO", "agent_id": "seo_spec"},
        ]
        ctx = _make_ctx(specialists=specs)
        client = _make_client_mock()
        self._run(ctx, client)

        emitted = client.create_call.call_args[1]["attributes"]["specialists"]
        for entry in emitted:
            assert entry["agent_id"] == entry["name"], (
                f"agent_id={entry['agent_id']!r} != name={entry['name']!r}; "
                "ADK contract: specialist_runtime.py:510-512, 572, 626"
            )
