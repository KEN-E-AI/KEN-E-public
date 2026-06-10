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
  - AH-116: agent-as-tool LlmAgent(mode='task') instances land in sub_agents, not tools.
  - AH-116: coexistence with attach_specialists_before_agent_callback (disjoint name-sets).
  - AH-116: hot-reload remove drops the agent-as-tool sub_agent from sub_agents.
  - AH-116: no AgentTool instance in root.tools or root.sub_agents (regression guard).
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
from app.adk.agents.agent_factory.roster import RosterCapExceededError, RosterResolution

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


@pytest.fixture
def _mock_supervisor_tools_empty():
    """Suppress supervisor function tools for tests that only care about the
    roster resolver (AH-133).  Apply via @pytest.mark.usefixtures."""
    from unittest.mock import patch

    with patch(
        "app.adk.agents.orchestration.supervisor.get_supervisor_function_tools",
        return_value=[],
    ):
        yield


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

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta, "resolve_specialist_roster", return_value=RosterResolution()
            ),
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


@pytest.mark.usefixtures("_mock_supervisor_tools_empty")
class TestSuccessfulResolve:
    def test_resolved_tools_replace_root_tools(self) -> None:
        """On a fingerprint miss, root_agent.tools is replaced with the resolved list."""
        agent = _make_root_agent(tools=[])
        tool_a = _make_tool("tool_a")
        cfg = _make_config(tool_ids=["agent.tool_a"])

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(tools=[tool_a]),
            ),
        ):
            attach_root_tools(agent, account_id="acc_test123")

        assert agent.tools == [tool_a]

    def test_null_tool_ids_resolves_to_empty(self) -> None:
        """When the resolver yields no tools (mocked empty here) and supervisor
        tools are suppressed, root.tools is replaced with an empty list.

        (In production with tool_ids=None the resolver returns the default-global
        function tools — exercised separately in
        TestDefaultGlobalFunctionTools — so this asserts the plumbing, not the
        real default-global set.)
        """
        agent = _make_root_agent(tools=[_make_tool("old_tool")])
        cfg = _make_config(tool_ids=None)

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta, "resolve_specialist_roster", return_value=RosterResolution()
            ),
        ):
            attach_root_tools(agent, account_id="acc_test123")

        assert agent.tools == []

    def test_none_account_id_uses_global_config(self) -> None:
        """account_id=None resolves the global config without raising ValueError."""
        agent = _make_root_agent(tools=[])
        cfg = _make_config(tool_ids=[])

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta, "resolve_specialist_roster", return_value=RosterResolution()
            ),
        ):
            attach_root_tools(agent, account_id=None)  # Must not raise

        assert agent.tools == []

    def test_invalid_account_id_falls_back_to_global_config(self) -> None:
        """An invalid account_id (contains path traversal etc.) logs a warning
        and falls back to the global config rather than raising."""
        agent = _make_root_agent(tools=[])
        cfg = _make_config(tool_ids=[])

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta, "resolve_specialist_roster", return_value=RosterResolution()
            ),
        ):
            # This bad id would raise ValueError inside validate_account_id.
            attach_root_tools(agent, account_id="../../admin")  # Must not raise

        assert agent.tools == []


# ---------------------------------------------------------------------------
# Fingerprint cache semantics
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("_mock_supervisor_tools_empty")
class TestFingerprintCache:
    def test_fingerprint_hit_skips_resolve(self) -> None:
        """Second call with no config change does NOT call resolve_specialist_roster."""
        agent = _make_root_agent(tools=[])
        tool_a = _make_tool("tool_a")
        cfg = _make_config(tool_ids=["agent.tool_a"])

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(tools=[tool_a]),
            ) as mock_resolve,
        ):
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

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg_v1),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(tools=[tool_a]),
            ),
        ):
            attach_root_tools(agent, account_id="acc_change")

        assert agent.tools == [tool_a]

        # Simulate config change: next call returns cfg_v2.
        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg_v2),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(tools=[tool_b]),
            ),
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

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg_with),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(tools=[tool_a]),
            ),
        ):
            attach_root_tools(agent, account_id="acc_drop")

        assert tool_a in agent.tools

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg_without),
            patch.object(
                rta, "resolve_specialist_roster", return_value=RosterResolution()
            ),
        ):
            attach_root_tools(agent, account_id="acc_drop")

        assert tool_a not in agent.tools

    def test_populated_guard_forces_resolve_on_fresh_empty_tools(self) -> None:
        """ADK 2.0 populated-guard (AH-108): a per-turn clone starts with
        ``tools=[]``.  Even when the config hash matches the previously applied
        hash, a non-empty ``root.tools`` is required to skip the resolve — so a
        fresh empty clone still gets its tools resolved.

        This mirrors ``sub_agent_attacher.py:284`` (``_applied_state == ...
        and root_agent.sub_agents``).
        """
        tool_a = _make_tool("tool_a")
        cfg = _make_config(tool_ids=["agent.tool_a"])

        # Turn 1 — first resolve; hash NOT applied yet.
        agent1 = _make_root_agent(tools=[])
        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(tools=[tool_a]),
            ),
        ):
            attach_root_tools(agent1, account_id="acc_guard")

        assert agent1.tools == [tool_a]
        # _applied_hash is now set to cfg's hash.

        # Turn 2 — simulate a fresh per-turn ADK 2.0 clone: same config, but
        # a NEW agent object with tools=[].  The hash hits but tools are empty →
        # populated-guard must force a re-resolve.
        agent2 = _make_root_agent(tools=[])  # fresh clone for turn 2
        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(tools=[tool_a]),
            ) as mock_resolve,
        ):
            attach_root_tools(agent2, account_id="acc_guard")
            # Resolve ran again (populated-guard bypassed the hash-hit early return).
            mock_resolve.assert_called_once()

        assert agent2.tools == [tool_a]

    def test_zero_tool_config_resolves_correctly_each_turn(self) -> None:
        """An account whose config legitimately resolves to zero tools always
        re-resolves on ADK 2.0 (fresh clone starts with ``tools=[]``), but the
        result is correct and stable — the resolver returns ``[]``, which matches
        the clone's starting state, so no spurious write occurs.

        This documents the accepted trade-off: per-turn re-resolve is necessary
        for correctness on ADK 2.0 (without it, every turn after the first
        would see zero tools even for accounts that have tools configured).
        """
        cfg_empty = _make_config(tool_ids=None)

        # Turn 1 — first clone for a zero-tool account.
        agent1 = _make_root_agent(tools=[])
        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg_empty),
            patch.object(
                rta, "resolve_specialist_roster", return_value=RosterResolution()
            ) as mock_resolve_1,
        ):
            attach_root_tools(agent1, account_id="acc_zero")
            mock_resolve_1.assert_called_once()

        assert agent1.tools == []

        # Turn 2 — fresh clone; same config; zero tools.  Hash matches but
        # tools=[] → populated-guard fires → re-resolve.
        agent2 = _make_root_agent(tools=[])
        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg_empty),
            patch.object(
                rta, "resolve_specialist_roster", return_value=RosterResolution()
            ) as mock_resolve_2,
        ):
            attach_root_tools(agent2, account_id="acc_zero")
            # Re-resolve fires (populated-guard) but result is still [].
            mock_resolve_2.assert_called_once()

        assert agent2.tools == []

    def test_inplace_slice_assignment_preserves_list_identity(self) -> None:
        """``root.tools[:] = resolved_tools`` mutates the list in-place so any
        holder that references the same list object sees the updated tools.

        Invoke ``attach_root_tools`` twice with different resolved tools (config
        change forces a second resolve) and assert the list identity of
        ``agent.tools`` is unchanged — the same list object is updated in-place
        rather than replaced.
        """
        agent = _make_root_agent(tools=[])
        original_list = agent.tools  # capture identity before any attach

        tool_a = _make_tool("tool_a")
        tool_b = _make_tool("tool_b")

        cfg_v1 = _make_config(tool_ids=["agent.tool_a"])
        cfg_v1.model_dump_json.return_value = '{"tool_ids": ["agent.tool_a"]}'

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg_v1),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(tools=[tool_a]),
            ),
        ):
            attach_root_tools(agent, account_id="acc_identity")

        assert agent.tools is original_list, (
            "In-place slice assignment should preserve the list identity; "
            "attribute reassignment (root.tools = ...) would break this."
        )
        assert agent.tools == [tool_a]

        # Trigger a second resolve (config change → hash miss).
        cfg_v2 = _make_config(tool_ids=["agent.tool_b"])
        cfg_v2.model_dump_json.return_value = '{"tool_ids": ["agent.tool_b"]}'

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg_v2),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(tools=[tool_b]),
            ),
        ):
            attach_root_tools(agent, account_id="acc_identity")

        # List identity preserved across the second resolve.
        assert agent.tools is original_list
        assert agent.tools == [tool_b]

    def test_applied_hash_not_committed_on_resolver_error(self) -> None:
        """On a resolver failure, the applied hash must NOT be updated so the
        next turn retries rather than silently serving stale tools."""
        agent = _make_root_agent(tools=[_make_tool("old")])
        cfg = _make_config(tool_ids=["agent.tool_a"])

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta, "resolve_specialist_roster", side_effect=RuntimeError("boom")
            ),
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

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta,
                "resolve_specialist_roster",
                side_effect=RosterCapExceededError("cap exceeded"),
            ),
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
            with (
                patch.object(rta, "get_cached_merged_config", return_value=cfg),
                patch.object(
                    rta,
                    "resolve_specialist_roster",
                    return_value=RosterResolution(tools=resolved),
                ),
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
# AH-PRD-04 follow-up: default-global function tools on the root
# ---------------------------------------------------------------------------


class TestDefaultGlobalFunctionTools:
    """The per-turn reconcile must feed the default-global function tools (e.g.
    ``create_visualization``) into the roster resolver as candidates, and dedupe
    the ``set_todo_list`` / ``update_todo_list`` overlap with the supervisor set.

    Before this fix the root passed ``function_tools=[]``, so the resolver's
    ``tool_ids`` filter had no candidate to match and silently dropped
    ``function.create_visualization`` from ``ken_e_chatbot.tool_ids``.
    """

    def test_default_global_tools_forwarded_as_candidates(self) -> None:
        """``resolve_default_global_tools`` output is passed verbatim as the
        ``function_tools=`` candidate list to ``resolve_specialist_roster``."""
        agent = _make_root_agent(tools=[])
        cfg = _make_config(tool_ids=["function.create_visualization"])
        viz = _make_tool("create_visualization")
        captured: dict[str, Any] = {}

        def _fake_resolver(*_args: Any, **kwargs: Any) -> RosterResolution:
            captured.update(kwargs)
            # Mimic the real filter: keep the supplied function-tool candidates.
            return RosterResolution(tools=list(kwargs["function_tools"]))

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(rta, "resolve_default_global_tools", return_value=[viz]),
            patch.object(rta, "resolve_specialist_roster", side_effect=_fake_resolver),
            patch(
                "app.adk.agents.orchestration.supervisor.get_supervisor_function_tools",
                return_value=[],
            ),
        ):
            attach_root_tools(agent, account_id="acc_viz")

        assert captured["function_tools"] == [viz]
        assert viz in agent.tools

    def test_rebuild_dedupes_supervisor_and_default_global_overlap(self) -> None:
        """A tool that appears in BOTH the resolved roster and the supervisor set
        (set_todo_list) is collapsed to a single entry; first occurrence wins."""
        agent = _make_root_agent(tools=[])
        cfg = _make_config(tool_ids=None)
        roster_todo = _make_tool("set_todo_list")
        sup_todo = _make_tool("set_todo_list")
        sup_save = _make_tool("save_pending_supervisor_tasks")

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta, "resolve_default_global_tools", return_value=[roster_todo]
            ),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(tools=[roster_todo]),
            ),
            patch(
                "app.adk.agents.orchestration.supervisor.get_supervisor_function_tools",
                return_value=[sup_todo, sup_save],
            ),
        ):
            attach_root_tools(agent, account_id="acc_dedupe")

        names = [getattr(t, "name", None) for t in agent.tools]
        assert names.count("set_todo_list") == 1
        assert "save_pending_supervisor_tasks" in names
        # First occurrence (the roster instance) wins; the supervisor dup is dropped.
        assert roster_todo in agent.tools
        assert sup_todo not in agent.tools


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

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta,
                "resolve_specialist_roster",
                side_effect=RuntimeError("unexpected"),
            ),
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

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta, "resolve_specialist_roster", return_value=RosterResolution()
            ),
            patch.object(rta, "block_lock_for", side_effect=_recording_lock_for),
        ):
            attach_root_tools(agent, account_id=None)

        # Lock key must be None, not any string (including "global").
        assert len(lock_keys_used) == 1
        assert lock_keys_used[0] is None, (
            f"Expected lock key None for no-account turn; got {lock_keys_used[0]!r}. "
            "Using a string key risks collision with a valid account ID."
        )


# ---------------------------------------------------------------------------
# AH-116: agent-as-tool partition — LlmAgent instances land in sub_agents
# ---------------------------------------------------------------------------


def _make_task_mode_agent(name: str) -> LlmAgent:
    """Build a minimal task-mode LlmAgent for use as an agent-as-tool stub."""
    return LlmAgent(
        name=name,
        model="gemini-2.0-flash",
        instruction=f"You are the {name} sub-agent.",
        mode="task",
    )


class TestAgentAsToolPartition:
    """AH-116: agent-as-tool LlmAgent(mode='task') instances from
    resolve_agent_subagents must land in root.sub_agents, NOT root.tools.

    The partition is driven by isinstance(item, LlmAgent) inside _attach_locked.
    These tests verify the partition semantics and the disjoint-name-sets
    coexistence contract with attach_specialists_before_agent_callback.
    """

    def test_task_mode_agent_lands_in_sub_agents_not_tools(self) -> None:
        """A task-mode LlmAgent returned from resolve_specialist_roster is
        routed to root.sub_agents — NOT to root.tools."""
        agent = _make_root_agent(tools=[])
        gs_sub = _make_task_mode_agent("google_search")
        cfg = _make_config(tool_ids=["agent.google_search"])

        # resolve_specialist_roster returns a RosterResolution with the LlmAgent
        # in sub_agents; _attach_locked must route it to root.sub_agents, not tools.
        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(sub_agents=[gs_sub]),
            ),
        ):
            attach_root_tools(agent, account_id="acc_partition")

        # The sub_agent is in sub_agents, not tools.
        gs_in_sub = next(
            (
                s
                for s in agent.sub_agents
                if isinstance(s, LlmAgent) and s.name == "google_search"
            ),
            None,
        )
        assert gs_in_sub is not None, (
            "Expected task-mode LlmAgent 'google_search' in root.sub_agents."
        )
        assert not any(isinstance(t, LlmAgent) for t in agent.tools), (
            "No LlmAgent should be in root.tools — it is not a valid tools= entry."
        )

    def test_regular_tools_stay_in_tools(self) -> None:
        """Non-LlmAgent items from resolve_specialist_roster stay in root.tools."""
        agent = _make_root_agent(tools=[])
        regular_tool = _make_tool("some_mcp_tool")
        cfg = _make_config(tool_ids=["ga4.some_mcp_tool"])

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(tools=[regular_tool]),
            ),
            patch.object(rta, "resolve_agent_subagents", return_value=[]),
        ):
            attach_root_tools(agent, account_id="acc_regular")

        assert regular_tool in agent.tools
        assert not any(s is regular_tool for s in agent.sub_agents)

    def test_coexistence_specialist_and_agent_tool_disjoint_name_sets(self) -> None:
        """A turn with both specialists (set by attach_specialists_*) and
        agent-as-tool sub_agents (set by AH-116) yields both in root.sub_agents
        with disjoint name-sets — neither callback drops the other's entries.

        Simulate by pre-populating root.sub_agents with a 'fake_specialist'
        (not in owned_names), then calling attach_root_tools.  After the call
        the specialist must still be present alongside the new agent-as-tool entry.
        """
        agent = _make_root_agent(tools=[])
        # Pre-populate a specialist (not in the agent-as-tool registry).
        fake_specialist = LlmAgent(
            name="fake_specialist",
            model="gemini-2.0-flash",
            instruction="I am a specialist.",
        )
        fake_specialist.parent_agent = agent
        agent.sub_agents = [fake_specialist]

        gs_sub = _make_task_mode_agent("google_search")
        cfg = _make_config(tool_ids=["agent.google_search"])

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(sub_agents=[gs_sub]),
            ),
        ):
            attach_root_tools(agent, account_id="acc_coexist")

        sub_names = [s.name for s in agent.sub_agents]
        assert "fake_specialist" in sub_names, (
            "Specialist added by attach_specialists_* must not be dropped by AH-116 reconcile."
        )
        assert "google_search" in sub_names, (
            "Agent-as-tool sub_agent must be present alongside the specialist."
        )

    def test_hot_reload_remove_drops_agent_sub_not_specialists(self) -> None:
        """Clearing tool_ids removes the agent-as-tool sub_agent from
        root.sub_agents on the next turn but leaves specialists untouched.
        """
        agent = _make_root_agent(tools=[])
        # Pre-populate: specialist + agent-as-tool entry.
        fake_specialist = LlmAgent(
            name="fake_specialist",
            model="gemini-2.0-flash",
            instruction="I am a specialist.",
        )
        gs_entry = _make_task_mode_agent("google_search")
        fake_specialist.parent_agent = agent
        gs_entry.parent_agent = agent
        agent.sub_agents = [fake_specialist, gs_entry]
        # Seed the applied hash so the guard passes (non-empty sub_agents).
        rta._applied_hash = None  # force re-resolve

        cfg_empty = _make_config(tool_ids=[])

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg_empty),
            patch.object(
                rta, "resolve_specialist_roster", return_value=RosterResolution()
            ),
            patch.object(rta, "resolve_agent_subagents", return_value=[]),
        ):
            attach_root_tools(agent, account_id="acc_hotreload_remove")

        sub_names = [s.name for s in agent.sub_agents]
        assert "fake_specialist" in sub_names, (
            "Specialist must not be removed when tool_ids is cleared."
        )
        assert "google_search" not in sub_names, (
            "Agent-as-tool sub_agent must be removed when it is no longer in tool_ids."
        )

    def test_no_agent_tool_instance_in_tools_or_sub_agents(self) -> None:
        """Regression guard (AH-116 AC #4): no AgentTool instance may exist in
        root.tools or root.sub_agents after the reconcile.

        This is the focused per-module variant of TestNoAgentToolInGate in
        test_chat_billing_parity.py; it provides a sharper failure signal
        during the AH-116 TDD loop without requiring the full billing-parity
        harness to run.
        """
        agent = _make_root_agent(tools=[])
        gs_sub = _make_task_mode_agent("google_search")
        cfg = _make_config(tool_ids=["agent.google_search"])

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(sub_agents=[gs_sub]),
            ),
        ):
            attach_root_tools(agent, account_id="acc_no_agent_tool")

        all_items = list(agent.tools) + list(agent.sub_agents)
        for item in all_items:
            assert type(item).__name__ != "AgentTool", (
                f"AgentTool found in root surface after AH-116 reconcile: {item!r}. "
                "AH-116 must route agent-as-tool entries as task-mode LlmAgents."
            )

    def test_task_mode_agent_injects_dispatchable_tool(self) -> None:
        """AH-117: routing a task-mode sub-agent to root.sub_agents must ALSO
        inject a ``_TaskAgentTool`` (named after the sub-agent) into root.tools.

        ADK creates that tool only in ``model_post_init``; the per-turn root is
        a clone reconciled post-construction, so without the explicit injection
        ``canonical_tools`` / ``_extract_task_delegation_fcs`` never see the
        delegation and a real LLM can't emit ``request_task_google_search`` — the
        search sub-agent's tokens go uncounted. This fails before the AH-117 fix.
        """
        from google.adk.tools.agent_tool import _TaskAgentTool

        agent = _make_root_agent(tools=[])
        gs_sub = _make_task_mode_agent("google_search")
        cfg = _make_config(tool_ids=["agent.google_search"])

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(sub_agents=[gs_sub]),
            ),
        ):
            attach_root_tools(agent, account_id="acc_dispatch")

        task_tools = [t for t in agent.tools if isinstance(t, _TaskAgentTool)]
        assert [t.name for t in task_tools] == ["google_search"], (
            "Expected exactly one _TaskAgentTool('google_search') in root.tools "
            f"after attach; got {[getattr(t, 'name', None) for t in agent.tools]}. "
            "Without it the LLM cannot dispatch request_task_google_search."
        )
        # The executable sub-agent must remain reachable via find_agent.
        assert any(
            getattr(s, "name", None) == "google_search" for s in agent.sub_agents
        )

    def test_hot_reload_remove_drops_task_tool(self) -> None:
        """AH-117: clearing tool_ids removes the ``_TaskAgentTool`` from
        root.tools, not just the sub-agent from root.sub_agents."""
        from google.adk.tools.agent_tool import _TaskAgentTool

        agent = _make_root_agent(tools=[])
        gs_entry = _make_task_mode_agent("google_search")
        gs_entry.parent_agent = agent
        agent.sub_agents = [gs_entry]
        # Seed a matching task tool as a prior turn's reconcile would have.
        agent.tools.append(_TaskAgentTool(gs_entry))
        rta._applied_hash = None  # force re-resolve

        cfg_empty = _make_config(tool_ids=[])
        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg_empty),
            patch.object(
                rta, "resolve_specialist_roster", return_value=RosterResolution()
            ),
            patch.object(rta, "resolve_agent_subagents", return_value=[]),
        ):
            attach_root_tools(agent, account_id="acc_hotreload_tool_remove")

        assert not any(isinstance(t, _TaskAgentTool) for t in agent.tools), (
            "Expected the _TaskAgentTool removed from root.tools after tool_ids "
            "was cleared."
        )
        assert not any(
            getattr(s, "name", None) == "google_search" for s in agent.sub_agents
        )


# ---------------------------------------------------------------------------
# AH-116: _reconcile_agent_subagents direct unit tests
# ---------------------------------------------------------------------------


class TestReconcileAgentSubagents:
    """Direct unit tests for _reconcile_agent_subagents, covering branches
    not easily reached via the full attach_root_tools path."""

    def test_noop_when_desired_already_present_by_identity(self) -> None:
        """If the desired instance is already in sub_agents by identity, no
        mutation occurs and changed == False."""
        from app.adk.agents.agent_factory.root_tools_attacher import (
            _reconcile_agent_subagents,
        )

        root = _make_root_agent()
        gs = _make_task_mode_agent("google_search")
        gs.parent_agent = root
        root.sub_agents = [gs]

        changed = _reconcile_agent_subagents(
            root, {"google_search": gs}, {"google_search"}
        )

        assert changed is False
        assert list(root.sub_agents) == [gs]

    def test_replaces_stale_instance_with_fresh_one(self) -> None:
        """When the same name maps to a different object identity (fresh factory
        call), the stale instance is dropped and the fresh one is attached.
        This exercises the 'replace with fresh instance' branch."""
        from app.adk.agents.agent_factory.root_tools_attacher import (
            _reconcile_agent_subagents,
        )

        root = _make_root_agent()
        stale_gs = _make_task_mode_agent("google_search")
        stale_gs.parent_agent = root
        root.sub_agents = [stale_gs]

        fresh_gs = _make_task_mode_agent("google_search")
        assert fresh_gs is not stale_gs

        changed = _reconcile_agent_subagents(
            root, {"google_search": fresh_gs}, {"google_search"}
        )

        assert changed is True
        gs_sub = next((s for s in root.sub_agents if s.name == "google_search"), None)
        assert gs_sub is fresh_gs, "Fresh instance must replace the stale one."
        assert gs_sub is not stale_gs
        assert getattr(stale_gs, "parent_agent", None) is not root
        assert getattr(fresh_gs, "parent_agent", None) is root

    def test_removes_entry_when_desired_is_empty(self) -> None:
        """An owned entry absent from desired_by_name is dropped."""
        from app.adk.agents.agent_factory.root_tools_attacher import (
            _reconcile_agent_subagents,
        )

        root = _make_root_agent()
        gs = _make_task_mode_agent("google_search")
        gs.parent_agent = root
        root.sub_agents = [gs]

        changed = _reconcile_agent_subagents(root, {}, {"google_search"})

        assert changed is True
        assert not any(s.name == "google_search" for s in root.sub_agents)
        assert getattr(gs, "parent_agent", None) is not root

    def test_non_owned_entries_pass_through_untouched(self) -> None:
        """Sub_agents whose names are NOT in owned_names are never touched."""
        from app.adk.agents.agent_factory.root_tools_attacher import (
            _reconcile_agent_subagents,
        )

        root = _make_root_agent()
        specialist = LlmAgent(
            name="some_specialist", model="gemini-2.0-flash", instruction="s"
        )
        specialist.parent_agent = root
        root.sub_agents = [specialist]

        changed = _reconcile_agent_subagents(root, {}, {"google_search"})

        assert changed is False
        assert specialist in list(root.sub_agents)


# ---------------------------------------------------------------------------
# AH-133: supervisor function tools are preserved on every reconcile
# ---------------------------------------------------------------------------


class TestSupervisorToolsPreservation:
    """Verifies that ``attach_root_tools`` appends ``set_todo_list`` and
    ``update_todo_list`` to ``root.tools`` after every reconcile, regardless
    of the ``ken_e_chatbot.tool_ids`` config (AH-133).
    """

    @pytest.fixture(autouse=True)
    def _ensure_todo_tools_registered(self) -> None:
        """Ensure the todo-list tools' registration side effect has fired.

        ``get_supervisor_function_tools`` resolves them from the process-global
        function-tool registry; importing the module registers them
        idempotently. A plain import (no ``reload``) is sufficient now that no
        suite clears the registry on teardown — ``test_todo_list_tools`` and the
        registry's own suite snapshot-restore it instead.
        """
        import app.adk.tools.todo_list_tools  # noqa: F401  # registration side effect

    def test_supervisor_tools_present_after_reconcile(self) -> None:
        """After any reconcile pass the root carries set_todo_list and
        update_todo_list, bypassing the admin tool_ids filter."""
        agent = _make_root_agent(tools=[])
        cfg = _make_config(tool_ids=None)  # no admin-configured tools

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta, "resolve_specialist_roster", return_value=RosterResolution()
            ),
        ):
            attach_root_tools(agent, account_id="acc_supervisor")

        tool_names = {getattr(t, "name", None) for t in agent.tools}
        assert "set_todo_list" in tool_names
        assert "update_todo_list" in tool_names

    def test_supervisor_tools_present_alongside_roster_tools(self) -> None:
        """Supervisor tools are appended after the roster; both are present."""
        agent = _make_root_agent(tools=[])
        roster_tool = _make_tool("agent.google_search")
        cfg = _make_config(tool_ids=["agent.google_search"])

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta,
                "resolve_specialist_roster",
                return_value=RosterResolution(tools=[roster_tool]),
            ),
        ):
            attach_root_tools(agent, account_id="acc_alongside")

        tool_names = {getattr(t, "name", None) for t in agent.tools}
        assert "set_todo_list" in tool_names
        assert "update_todo_list" in tool_names
        assert "agent.google_search" in tool_names or roster_tool in agent.tools

    def test_supervisor_tools_survive_config_change_reconcile(self) -> None:
        """After a config change forces a re-resolve, supervisor tools are still
        present on the updated root.tools."""
        agent = _make_root_agent(tools=[])
        cfg_v1 = _make_config(tool_ids=None)
        cfg_v1.model_dump_json.return_value = '{"tool_ids": null, "v": 1}'
        cfg_v2 = _make_config(tool_ids=None)
        cfg_v2.model_dump_json.return_value = '{"tool_ids": null, "v": 2}'

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg_v1),
            patch.object(
                rta, "resolve_specialist_roster", return_value=RosterResolution()
            ),
        ):
            attach_root_tools(agent, account_id="acc_v1")

        tool_names_v1 = {getattr(t, "name", None) for t in agent.tools}
        assert "set_todo_list" in tool_names_v1

        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg_v2),
            patch.object(
                rta, "resolve_specialist_roster", return_value=RosterResolution()
            ),
        ):
            attach_root_tools(agent, account_id="acc_v2")

        tool_names_v2 = {getattr(t, "name", None) for t in agent.tools}
        assert "set_todo_list" in tool_names_v2
        assert "update_todo_list" in tool_names_v2


class TestPreservesSpecialistTaskTools:
    """AH-161: attach_root_tools must NOT clobber the _TaskAgentTool that
    attach_specialists_before_agent_callback injects for per-turn specialists.

    Repro of the prod bug (dev trace 019eacc4): attach_root_tools rebuilds
    root.tools[:] and — before this fix — only re-wrapped agent-as-tool
    catalogue subs (agent_subs_desired), dropping the specialist delegation
    tool. The coordinator then emitted google_analytics_specialist(...) and ADK
    raised "Tool 'google_analytics_specialist' not found", silently breaking
    request_task dispatch in production. The two before_agent_callbacks run in
    sequence (attach_specialists then attach_root_tools); no unit test exercised
    that ordering, so the regression shipped.
    """

    @pytest.mark.usefixtures("_mock_supervisor_tools_empty")
    def test_specialist_task_tool_survives_root_tools_rebuild(self) -> None:
        from google.adk.agents import LlmAgent
        from google.adk.tools.agent_tool import _TaskAgentTool

        from app.adk.agents.agent_factory.roster import RosterResolution
        from app.adk.agents.agent_factory.sub_agent_attacher import (
            attach_task_subagent,
        )

        root = _make_root_agent()
        # Simulate attach_specialists_before_agent_callback having already run:
        # a task-mode specialist pinned into sub_agents + its delegation tool
        # injected into root.tools.
        specialist = LlmAgent(
            name="google_analytics_specialist",
            model="gemini-2.5-pro",
            mode="task",
        )
        attach_task_subagent(root, specialist)
        assert any(
            isinstance(t, _TaskAgentTool)
            and getattr(t, "name", None) == "google_analytics_specialist"
            for t in root.tools
        ), "precondition: attach_task_subagent should inject the delegation tool"

        # Now the second callback rebuilds root.tools.
        cfg = _make_config(tool_ids=["agent.google_search"])
        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta, "resolve_specialist_roster", return_value=RosterResolution()
            ),
        ):
            attach_root_tools(root, account_id="acc_test123")

        survivors = [
            t
            for t in root.tools
            if isinstance(t, _TaskAgentTool)
            and getattr(t, "name", None) == "google_analytics_specialist"
        ]
        assert len(survivors) == 1, (
            "attach_root_tools dropped the specialist _TaskAgentTool on rebuild; "
            f"root.tools = {[getattr(t, 'name', repr(t)) for t in root.tools]}"
        )
        # And the specialist remains dispatchable via find_agent (still in sub_agents).
        assert root.find_agent("google_analytics_specialist") is specialist

    @pytest.mark.usefixtures("_mock_supervisor_tools_empty")
    def test_no_duplicate_task_tool_on_hash_hit_early_return(self) -> None:
        """Regression: gemini-3.1-pro-preview rejects duplicate function declarations.

        Exact production interleaving that produces the duplicate:

        1. ``_seed_specialist_dispatch_tools`` (deploy-time) appends a placeholder
           ``_TaskAgentTool("google_analytics_specialist")`` to the original root.
        2. ADK 2.0 clones the root per-turn; the clone shallow-copies ``tools``,
           so the placeholder is present from turn 1 onward.
        3. ``attach_specialists_before_agent_callback`` (callback 1) runs and
           ``_reconcile`` appends a *real* ``_TaskAgentTool("google_analytics_specialist")``.
        4. ``attach_root_tools_before_agent_callback`` (callback 2) runs on turn ≥ 2:
           ``_applied_hash == content_hash`` AND ``root.tools`` is non-empty
           (callback 1 just appended the real tool) → **early return, no rebuild**.
        5. Result: two ``_TaskAgentTool("google_analytics_specialist")`` entries in
           ``root.tools`` → Gemini 400 "Duplicate function declaration found".

        The fix is in ``_reconcile`` (sub_agent_attacher.py): before appending a
        new ``_TaskAgentTool``, check whether a same-named tool already exists in
        ``root.tools``; if so, skip the append.  This test drives the real
        ``attach_account_specialists`` → ``_reconcile`` path so the guard is
        exercised, then drives ``attach_root_tools`` with a hash-hit (early-return)
        to confirm it does NOT introduce a rebuild-path duplicate either.
        """
        import hashlib

        from google.adk.agents import LlmAgent
        from google.adk.tools.agent_tool import _TaskAgentTool

        from app.adk.agents.agent_factory import sub_agent_attacher as saa
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
        from app.adk.agents.agent_factory.roster import RosterResolution
        from app.adk.agents.agent_factory.sub_agent_attacher import (
            _make_task_agent_tool,
            attach_account_specialists,
        )

        # --- Build root with a deploy-time placeholder already in tools ---
        root = _make_root_agent()
        specialist_agent = LlmAgent(
            name="google_analytics_specialist",
            model="gemini-2.0-flash",
            mode="task",
        )
        placeholder = _make_task_agent_tool(specialist_agent)
        assert placeholder is not None
        root.tools.append(placeholder)
        # root.tools = [placeholder_ga].  Simulates what _seed_specialist_dispatch_tools
        # puts into the deploy-time root, which the per-turn clone shallow-copies.

        # --- Pre-commit the root-tools applied hash to simulate "turn ≥ 2" ---
        # attach_root_tools will see an unchanged hash + non-empty tools and
        # early-return without rebuilding.
        cfg = _make_config(tool_ids=None)
        cfg.model_dump_json.return_value = '{"tool_ids": null}'
        pre_hash = hashlib.sha256(cfg.model_dump_json().encode()).hexdigest()
        rta._applied_hash = pre_hash

        # --- Reset the sub_agent_attacher applied-state so _reconcile actually runs ---
        saa._reset_applied_state_for_tests()

        # --- Run callback 1: attach_account_specialists (calls _reconcile) ---
        # _reconcile detects google_analytics_specialist as task-dispatchable and
        # attempts to append a _TaskAgentTool.  The guard must prevent the append
        # because placeholder_ga is already in root.tools under the same name.
        def _list(_account_id: str) -> list[str]:
            return ["google_analytics_specialist"]

        def _resolve_config(
            doc_id: str, _account_id: str | None = None, _ttl: int = 60
        ) -> MergedAgentConfig:
            return MergedAgentConfig(
                instruction="GA specialist instruction.",
                model="gemini-2.0-flash",
                description="Google Analytics specialist",
                visible_in_frontend=True,
                ken_e_sub_agent=True,
            )

        def _resolve_agent(
            doc_id: str,
            _account_id: str | None = None,
            _ttl: int = 60,
            session_state: Any = None,
            **_kw: object,
        ) -> LlmAgent:
            return specialist_agent

        with (
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher."
                "list_account_agent_configs_cached",
                side_effect=_list,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_config",
                side_effect=_resolve_config,
            ),
            patch(
                "app.adk.agents.agent_factory.sub_agent_attacher.resolve_agent",
                side_effect=_resolve_agent,
            ),
        ):
            attach_account_specialists(root, "acc_no_dup")

        # --- Run callback 2: attach_root_tools with hash-hit → early return ---
        with (
            patch.object(rta, "get_cached_merged_config", return_value=cfg),
            patch.object(
                rta, "resolve_specialist_roster", return_value=RosterResolution()
            ),
        ):
            attach_root_tools(root, account_id="acc_no_dup")

        # --- Assert: AT MOST ONE _TaskAgentTool per name ---
        task_tools_ga = [
            t
            for t in root.tools
            if isinstance(t, _TaskAgentTool)
            and getattr(t, "name", None) == "google_analytics_specialist"
        ]
        assert len(task_tools_ga) <= 1, (
            f"Duplicate _TaskAgentTool('google_analytics_specialist') found in "
            f"root.tools after both attach callbacks ran: "
            f"{[getattr(t, 'name', repr(t)) for t in root.tools]}. "
            "This causes Gemini 400 'Duplicate function declaration found' on "
            "gemini-3.1-pro-preview (and any strict model)."
        )
        # The specialist must remain dispatchable after dedup.
        assert any(
            getattr(s, "name", None) == "google_analytics_specialist"
            for s in root.sub_agents
        ), "Specialist must remain in sub_agents for find_agent dispatch."
