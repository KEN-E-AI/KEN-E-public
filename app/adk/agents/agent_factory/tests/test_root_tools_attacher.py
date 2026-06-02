"""Unit tests for app.adk.agents.agent_factory.root_tools_attacher.

Covers:
  - Module exports attach_root_tools and attach_root_tools_before_agent_callback.
  - Callback always returns None and never raises.
  - Successful resolve: root_agent.tools replaced with the resolved list.
  - Fingerprint cache hit: no resolve, no replacement on second consecutive call.
  - Config change (fingerprint miss): tools replaced with new list.
  - RosterCapExceededError: logs, leaves tools unchanged, fingerprint NOT committed.
  - Generic resolver failure: same degradation policy.
  - Firestore error: same degradation policy.
  - No account_id (None): global config used without ValueError.
  - Invalid account_id: warning logged, falls back to global config.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from google.adk.agents import LlmAgent

from app.adk.agents.agent_factory import root_tools_attacher as rta
from app.adk.agents.agent_factory.root_tools_attacher import (
    attach_root_tools,
    attach_root_tools_before_agent_callback,
)
from app.adk.agents.agent_factory.roster import RosterCapExceededError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_root_agent(tools: list[Any] | None = None) -> LlmAgent:
    return LlmAgent(
        name="ken_e",
        model="gemini-2.0-flash",
        instruction="You are the root.",
        tools=tools or [],
    )


def _make_config(tool_ids: list[str] | None = None) -> MagicMock:
    cfg = MagicMock()
    cfg.tool_ids = tool_ids
    cfg.model_dump_json.return_value = f'{{"tool_ids": {tool_ids!r}}}'
    return cfg


def _make_tool(name: str = "dummy_tool") -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


def _make_callback_context(
    account_id: str | None = "acc_test123",
    agent: LlmAgent | None = None,
) -> MagicMock:
    ctx = MagicMock()
    state_dict: dict[str, Any] = {}
    if account_id is not None:
        state_dict["account_id"] = account_id

    ctx.state.get = lambda key, default=None: state_dict.get(key, default)
    ctx.state.to_dict = lambda: dict(state_dict)

    mock_invocation = MagicMock()
    mock_invocation.agent = agent or _make_root_agent()
    ctx._invocation_context = mock_invocation

    return ctx


@pytest.fixture(autouse=True)
def _reset_applied_hash():
    """Reset the applied-hash slot between tests."""
    rta._reset_applied_hash_for_tests()
    yield
    rta._reset_applied_hash_for_tests()


# ---------------------------------------------------------------------------
# Module API
# ---------------------------------------------------------------------------


class TestModuleExports:
    def test_attach_root_tools_is_callable(self) -> None:
        assert callable(attach_root_tools)

    def test_attach_root_tools_before_agent_callback_is_callable(self) -> None:
        assert callable(attach_root_tools_before_agent_callback)


# ---------------------------------------------------------------------------
# Callback contract: always returns None, never raises
# ---------------------------------------------------------------------------


class TestCallbackContract:
    def test_callback_returns_none(self) -> None:
        agent = _make_root_agent()
        ctx = _make_callback_context(agent=agent)
        cfg = _make_config(tool_ids=[])

        with patch.object(
            rta, "get_cached_merged_config", return_value=cfg
        ), patch.object(
            rta, "resolve_specialist_roster", return_value=[]
        ):
            result = attach_root_tools_before_agent_callback(ctx)

        assert result is None

    def test_callback_never_raises_on_exception(self) -> None:
        """Even if _attach_locked raises, the callback must return None."""
        ctx = _make_callback_context()

        with patch.object(
            rta,
            "_attach_locked",
            side_effect=RuntimeError("unexpected"),
        ):
            result = attach_root_tools_before_agent_callback(ctx)

        assert result is None


# ---------------------------------------------------------------------------
# Successful resolve path
# ---------------------------------------------------------------------------


class TestSuccessfulResolve:
    def test_resolved_tools_replace_root_tools(self) -> None:
        """On a fingerprint miss, root_agent.tools is replaced with the resolved list."""
        agent = _make_root_agent(tools=[])
        tool_a = _make_tool("tool_a")
        cfg = _make_config(tool_ids=["agent.tool_a"])

        with patch.object(
            rta, "get_cached_merged_config", return_value=cfg
        ), patch.object(
            rta, "resolve_specialist_roster", return_value=[tool_a]
        ):
            attach_root_tools(agent, account_id="acc_test123")

        assert agent.tools == [tool_a]

    def test_null_tool_ids_resolves_to_empty(self) -> None:
        """tool_ids=None on the config resolves to an empty list (no agent tools
        are default_global) and replaces the root tools."""
        agent = _make_root_agent(tools=[_make_tool("old_tool")])
        cfg = _make_config(tool_ids=None)

        with patch.object(
            rta, "get_cached_merged_config", return_value=cfg
        ), patch.object(
            rta, "resolve_specialist_roster", return_value=[]
        ):
            attach_root_tools(agent, account_id="acc_test123")

        assert agent.tools == []

    def test_none_account_id_uses_global_config(self) -> None:
        """account_id=None resolves the global config without raising ValueError."""
        agent = _make_root_agent(tools=[])
        cfg = _make_config(tool_ids=[])

        with patch.object(
            rta, "get_cached_merged_config", return_value=cfg
        ), patch.object(
            rta, "resolve_specialist_roster", return_value=[]
        ):
            attach_root_tools(agent, account_id=None)  # Must not raise

        assert agent.tools == []

    def test_invalid_account_id_falls_back_to_global_config(self) -> None:
        """An invalid account_id (contains path traversal etc.) logs a warning
        and falls back to the global config rather than raising."""
        agent = _make_root_agent(tools=[])
        cfg = _make_config(tool_ids=[])

        with patch.object(
            rta, "get_cached_merged_config", return_value=cfg
        ), patch.object(
            rta, "resolve_specialist_roster", return_value=[]
        ):
            # This bad id would raise ValueError inside validate_account_id.
            attach_root_tools(agent, account_id="../../admin")  # Must not raise

        assert agent.tools == []


# ---------------------------------------------------------------------------
# Fingerprint cache semantics
# ---------------------------------------------------------------------------


class TestFingerprintCache:
    def test_fingerprint_hit_skips_resolve(self) -> None:
        """Second call with no config change does NOT call resolve_specialist_roster."""
        agent = _make_root_agent(tools=[])
        tool_a = _make_tool("tool_a")
        cfg = _make_config(tool_ids=["agent.tool_a"])

        with patch.object(
            rta, "get_cached_merged_config", return_value=cfg
        ), patch.object(
            rta, "resolve_specialist_roster", return_value=[tool_a]
        ) as mock_resolve:
            attach_root_tools(agent, account_id="acc_fingerprint")
            attach_root_tools(agent, account_id="acc_fingerprint")

        # resolve_specialist_roster called exactly once despite two attach calls.
        mock_resolve.assert_called_once()

    def test_fingerprint_miss_on_config_change_updates_tools(self) -> None:
        """After a config change (different tool_ids hash) the resolver runs again
        and the tool list is updated."""
        agent = _make_root_agent(tools=[])
        tool_a = _make_tool("tool_a")
        tool_b = _make_tool("tool_b")

        cfg_v1 = _make_config(tool_ids=["agent.tool_a"])
        cfg_v2 = _make_config(tool_ids=["agent.tool_b"])
        # Give the two configs different JSON representations so _content_hash differs.
        cfg_v1.model_dump_json.return_value = '{"tool_ids": ["agent.tool_a"]}'
        cfg_v2.model_dump_json.return_value = '{"tool_ids": ["agent.tool_b"]}'

        with patch.object(
            rta, "get_cached_merged_config", return_value=cfg_v1
        ), patch.object(
            rta, "resolve_specialist_roster", return_value=[tool_a]
        ):
            attach_root_tools(agent, account_id="acc_change")

        assert agent.tools == [tool_a]

        # Simulate config change: next call returns cfg_v2.
        with patch.object(
            rta, "get_cached_merged_config", return_value=cfg_v2
        ), patch.object(
            rta, "resolve_specialist_roster", return_value=[tool_b]
        ):
            attach_root_tools(agent, account_id="acc_change")

        assert agent.tools == [tool_b]

    def test_dropped_tool_not_in_new_list(self) -> None:
        """After a config edit that removes a tool, the next turn's tools list
        does NOT contain the dropped tool."""
        agent = _make_root_agent(tools=[])
        tool_a = _make_tool("tool_a")

        cfg_with = _make_config(tool_ids=["agent.tool_a"])
        cfg_with.model_dump_json.return_value = '{"tool_ids": ["agent.tool_a"]}'

        cfg_without = _make_config(tool_ids=[])
        cfg_without.model_dump_json.return_value = '{"tool_ids": []}'

        with patch.object(
            rta, "get_cached_merged_config", return_value=cfg_with
        ), patch.object(
            rta, "resolve_specialist_roster", return_value=[tool_a]
        ):
            attach_root_tools(agent, account_id="acc_drop")

        assert tool_a in agent.tools

        with patch.object(
            rta, "get_cached_merged_config", return_value=cfg_without
        ), patch.object(
            rta, "resolve_specialist_roster", return_value=[]
        ):
            attach_root_tools(agent, account_id="acc_drop")

        assert tool_a not in agent.tools

    def test_applied_hash_not_committed_on_resolver_error(self) -> None:
        """On a resolver failure, the applied hash must NOT be updated so the
        next turn retries rather than silently serving stale tools."""
        agent = _make_root_agent(tools=[_make_tool("old")])
        cfg = _make_config(tool_ids=["agent.tool_a"])

        with patch.object(
            rta, "get_cached_merged_config", return_value=cfg
        ), patch.object(
            rta, "resolve_specialist_roster", side_effect=RuntimeError("boom")
        ):
            attach_root_tools(agent, account_id="acc_err")

        # Applied hash was not updated (stays None → next turn retries).
        assert rta._applied_hash is None

    def test_applied_hash_not_committed_on_cap_error(self) -> None:
        """On RosterCapExceededError, tools are unchanged and the applied hash
        is NOT updated."""
        old_tool = _make_tool("old")
        agent = _make_root_agent(tools=[old_tool])
        cfg = _make_config(tool_ids=["agent.tool_a"] * 35)  # would exceed cap

        with patch.object(
            rta, "get_cached_merged_config", return_value=cfg
        ), patch.object(
            rta,
            "resolve_specialist_roster",
            side_effect=RosterCapExceededError("cap exceeded"),
        ):
            attach_root_tools(agent, account_id="acc_cap")

        assert agent.tools == [old_tool]
        assert rta._applied_hash is None

    def test_multi_account_interleave_does_not_serve_stale_tools(self) -> None:
        """A→B→A on one shared root: account A's third turn must get A's tools,
        not the tools account B left in the shared ``root.tools`` slot.

        Regression for the per-account-fingerprint stale read: a per-account
        cache would early-return on A's repeat turn (A's config unchanged) and
        leave B's tools live. The single applied-hash slot re-resolves on the
        account switch because the config hash differs.
        """
        agent = _make_root_agent(tools=[])
        tool_x = _make_tool("tool_x")
        tool_y = _make_tool("tool_y")

        cfg_a = _make_config(tool_ids=["agent.tool_x"])
        cfg_a.model_dump_json.return_value = '{"tool_ids": ["agent.tool_x"]}'
        cfg_b = _make_config(tool_ids=["agent.tool_y"])
        cfg_b.model_dump_json.return_value = '{"tool_ids": ["agent.tool_y"]}'

        def _attach(account_id: str, cfg: Any, resolved: list[Any]) -> None:
            with patch.object(
                rta, "get_cached_merged_config", return_value=cfg
            ), patch.object(
                rta, "resolve_specialist_roster", return_value=resolved
            ):
                attach_root_tools(agent, account_id=account_id)

        _attach("acc_A", cfg_a, [tool_x])
        assert agent.tools == [tool_x]

        _attach("acc_B", cfg_b, [tool_y])
        assert agent.tools == [tool_y]

        # A again, A's config unchanged — must re-apply A's tools, not serve B's.
        _attach("acc_A", cfg_a, [tool_x])
        assert agent.tools == [tool_x]


# ---------------------------------------------------------------------------
# Error degradation
# ---------------------------------------------------------------------------


class TestErrorDegradation:
    def test_firestore_error_leaves_tools_unchanged(self) -> None:
        """A FirestoreConnectionError on config fetch leaves root.tools unchanged."""
        from app.adk.agents.agent_factory.config_loader import FirestoreConnectionError

        old_tool = _make_tool("old")
        agent = _make_root_agent(tools=[old_tool])

        with patch.object(
            rta,
            "get_cached_merged_config",
            side_effect=FirestoreConnectionError("connect failed"),
        ):
            attach_root_tools(agent, account_id="acc_fs_err")

        assert agent.tools == [old_tool]

    def test_generic_config_error_leaves_tools_unchanged(self) -> None:
        """Any unexpected exception during config fetch leaves root.tools unchanged."""
        old_tool = _make_tool("old")
        agent = _make_root_agent(tools=[old_tool])

        with patch.object(
            rta,
            "get_cached_merged_config",
            side_effect=ValueError("unexpected"),
        ):
            attach_root_tools(agent, account_id="acc_gen_err")

        assert agent.tools == [old_tool]

    def test_resolver_error_leaves_tools_unchanged(self) -> None:
        """An unexpected resolver error leaves root.tools unchanged."""
        old_tool = _make_tool("old")
        agent = _make_root_agent(tools=[old_tool])
        cfg = _make_config(tool_ids=["agent.tool_a"])

        with patch.object(
            rta, "get_cached_merged_config", return_value=cfg
        ), patch.object(
            rta,
            "resolve_specialist_roster",
            side_effect=RuntimeError("unexpected"),
        ):
            attach_root_tools(agent, account_id="acc_res_err")

        assert agent.tools == [old_tool]

    def test_missing_tools_attr_logs_error_and_skips(self) -> None:
        """An object without a ``tools`` list attribute logs and returns without
        raising."""

        class _NoTools:
            name = "no_tools_agent"

        no_tools_agent = _NoTools()
        # Must not raise — just log.
        attach_root_tools(no_tools_agent, account_id=None)  # type: ignore[arg-type]

    def test_none_account_id_lock_key_is_none_not_global_string(self) -> None:
        """When account_id is None, the lock key passed to block_lock_for must be
        ``None`` (a hashable sentinel that cannot collide with a valid account ID).
        Using a synthetic string like "global" could collide with an account
        literally named "global" (which matches [a-zA-Z0-9_-]{1,128})."""
        agent = _make_root_agent(tools=[])
        cfg = _make_config(tool_ids=[])
        lock_keys_used: list[Any] = []

        original_block_lock_for = rta.block_lock_for

        def _recording_lock_for(key: Any):
            lock_keys_used.append(key)
            return original_block_lock_for(key)

        with patch.object(
            rta, "get_cached_merged_config", return_value=cfg
        ), patch.object(
            rta, "resolve_specialist_roster", return_value=[]
        ), patch.object(
            rta, "block_lock_for", side_effect=_recording_lock_for
        ):
            attach_root_tools(agent, account_id=None)

        # Lock key must be None, not any string (including "global").
        assert len(lock_keys_used) == 1
        assert lock_keys_used[0] is None, (
            f"Expected lock key None for no-account turn; got {lock_keys_used[0]!r}. "
            "Using a string key risks collision with a valid account ID."
        )
