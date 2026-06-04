"""Tests for app.adk.agents.agent_factory.specialist_runtime (AH-59).

Hermetic — no Firestore, no real ADK Runner, no MCP servers.  Every
external call is mocked or stubbed.

Test classes:

* ``TestResolveConfig`` — TTL caching and stale-on-error via
  ``get_cached_merged_config``.
* ``TestResolveAgent`` — LRU eviction and content-hash invalidation.
* ``TestRun`` — review-pipeline path and single-pass path.
* ``TestAvailableSpecialistsProvider`` — ``visible_in_frontend`` filter and
  failure isolation.
* ``TestPerAccountOverlay`` — per-account overlay is propagated to the cache
  layer as a distinct key from the global config.
* ``TestAgentCache`` — unit tests for the internal ``_AgentCache`` LRU.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_merged_config(
    instruction: str = "v1",
    model: str = "gemini-2.5-pro",
    visible_in_frontend: bool = True,
    ken_e_sub_agent: bool = True,
) -> Any:
    """Return a minimal MergedAgentConfig-like object suitable for tests."""
    from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

    return MergedAgentConfig(
        instruction=instruction,
        model=model,
        description="Test specialist",
        visible_in_frontend=visible_in_frontend,
        ken_e_sub_agent=ken_e_sub_agent,
    )


def _make_llm_agent(name: str = "test_specialist") -> MagicMock:
    """Return a MagicMock that quacks like an LlmAgent."""
    agent = MagicMock()
    agent.name = name
    agent.description = "Test specialist"
    return agent


@pytest.fixture(autouse=True)
def clear_specialists_cache() -> Any:
    """Each test starts with a clean agent cache, config cache, block cache, list cache,
    and system-settings cache."""
    from app.adk.agents.agent_factory import specialist_runtime
    from app.adk.agents.utils.config_cache import clear_config_cache
    from app.adk.agents.utils.system_settings import (
        clear_system_settings_cache_for_tests,
    )

    specialist_runtime._specialists_cache.clear()
    specialist_runtime._clear_block_cache_for_tests()
    specialist_runtime._clear_list_cache_for_tests()
    clear_config_cache()
    clear_system_settings_cache_for_tests()
    yield
    specialist_runtime._specialists_cache.clear()
    specialist_runtime._clear_block_cache_for_tests()
    specialist_runtime._clear_list_cache_for_tests()
    clear_config_cache()
    clear_system_settings_cache_for_tests()


# ---------------------------------------------------------------------------
# TestResolveConfig
# ---------------------------------------------------------------------------


class TestResolveConfig:
    def test_delegates_to_get_cached_merged_config(self) -> None:
        from app.adk.agents.agent_factory import specialist_runtime

        cfg = _make_merged_config("v1")

        with patch.object(
            specialist_runtime, "get_cached_merged_config", return_value=cfg
        ) as mock_cache:
            result = specialist_runtime.resolve_config("my_specialist", "acct_1")

        mock_cache.assert_called_once_with("my_specialist", "acct_1", 60)
        assert result is cfg

    def test_propagates_exception_when_no_stale_value(self) -> None:
        from app.adk.agents.agent_factory import specialist_runtime

        with patch.object(
            specialist_runtime,
            "get_cached_merged_config",
            side_effect=RuntimeError("Firestore down"),
        ):
            with pytest.raises(RuntimeError, match="Firestore down"):
                specialist_runtime.resolve_config("missing_doc")

    def test_none_account_id_is_accepted(self) -> None:
        """account_id=None (global config) must be forwarded as-is."""
        from app.adk.agents.agent_factory import specialist_runtime

        cfg = _make_merged_config()

        with patch.object(
            specialist_runtime, "get_cached_merged_config", return_value=cfg
        ) as mock_cache:
            specialist_runtime.resolve_config("global_doc", None)

        _, call_account_id, _ = mock_cache.call_args.args
        assert call_account_id is None


# ---------------------------------------------------------------------------
# TestResolveAgent
# ---------------------------------------------------------------------------


class TestResolveAgent:
    def test_cache_miss_builds_and_caches_agent(self) -> None:
        from app.adk.agents.agent_factory import specialist_runtime

        cfg = _make_merged_config("v1")
        fake_agent = _make_llm_agent()

        with (
            patch.object(specialist_runtime, "resolve_config", return_value=cfg),
            patch.object(
                specialist_runtime, "_build_specialist", return_value=fake_agent
            ) as mock_build,
        ):
            agent = specialist_runtime.resolve_agent("spe_1")

        mock_build.assert_called_once()
        assert agent is fake_agent
        assert len(specialist_runtime._specialists_cache) == 1

    def test_cache_hit_returns_same_agent_without_rebuild(self) -> None:
        from app.adk.agents.agent_factory import specialist_runtime

        cfg = _make_merged_config("v1")
        fake_agent = _make_llm_agent()

        with (
            patch.object(specialist_runtime, "resolve_config", return_value=cfg),
            patch.object(
                specialist_runtime, "_build_specialist", return_value=fake_agent
            ) as mock_build,
        ):
            a1 = specialist_runtime.resolve_agent("spe_1")
            a2 = specialist_runtime.resolve_agent("spe_1")

        assert mock_build.call_count == 1
        assert a1 is a2

    def test_content_hash_change_triggers_rebuild(self) -> None:
        """When config changes (different content hash), a new LlmAgent is built."""
        from app.adk.agents.agent_factory import specialist_runtime

        cfg_v1 = _make_merged_config("v1")
        cfg_v2 = _make_merged_config("v2")
        agent_v1 = _make_llm_agent("agent_v1")
        agent_v2 = _make_llm_agent("agent_v2")

        build_returns = iter([agent_v1, agent_v2])

        with (
            patch.object(
                specialist_runtime,
                "resolve_config",
                side_effect=[cfg_v1, cfg_v2],
            ),
            patch.object(
                specialist_runtime,
                "_build_specialist",
                side_effect=build_returns,
            ) as mock_build,
        ):
            a1 = specialist_runtime.resolve_agent("spe_1")
            a2 = specialist_runtime.resolve_agent("spe_1")

        assert mock_build.call_count == 2
        assert a1 is agent_v1
        assert a2 is agent_v2

    def test_same_config_different_account_ids_are_independent(self) -> None:
        """(doc_id, acct_A) and (doc_id, acct_B) are separate cache keys."""
        from app.adk.agents.agent_factory import specialist_runtime

        cfg_a = _make_merged_config("for_a")
        cfg_b = _make_merged_config("for_b")
        agent_a = _make_llm_agent("agent_a")
        agent_b = _make_llm_agent("agent_b")

        build_returns = iter([agent_a, agent_b])

        with (
            patch.object(
                specialist_runtime,
                "resolve_config",
                side_effect=[cfg_a, cfg_b],
            ),
            patch.object(
                specialist_runtime,
                "_build_specialist",
                side_effect=build_returns,
            ) as mock_build,
        ):
            ra = specialist_runtime.resolve_agent("spe_1", "account_a")
            rb = specialist_runtime.resolve_agent("spe_1", "account_b")

        assert mock_build.call_count == 2
        assert ra is agent_a
        assert rb is agent_b


# ---------------------------------------------------------------------------
# TestResolveAgentWithHit, TestAgentCacheGetOrBuildWithHit, and TestRun were
# deleted in AH-75. Background:
#   - resolve_agent_with_hit + the cache.get_or_build_with_hit variant existed
#     to back delegate_to_specialist's cache_hit observability attribute.
#     Approach 1 removes delegate_to_specialist entirely; review-pipeline
#     wrap-on-criteria still rides on the same content-hash invalidation
#     covered by TestResolveAgent + TestSpecialistRuntimeReviewWrap.
#   - TestRun targeted specialist_runtime.run(), which was the runtime side
#     of the deleted function-tool dispatch. Inner-Runner pipeline coverage
#     stays via TestSpecialistRuntimeReviewWrap + test_review_pipeline.py.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# TestAvailableSpecialistsProvider
# ---------------------------------------------------------------------------


class TestAvailableSpecialistsProvider:
    def _make_context(self, account_id: str | None) -> MagicMock:
        ctx = MagicMock()
        ctx.state = {"account_id": account_id} if account_id else {}
        return ctx

    def test_returns_empty_block_when_no_account_id(self) -> None:
        from app.adk.agents.agent_factory import specialist_runtime

        ctx = self._make_context(None)
        result = specialist_runtime.available_specialists_provider(ctx)

        assert "## Available Specialists" in result
        assert "None registered" in result

    def test_returns_empty_block_when_account_id_invalid(self) -> None:
        """Malformed account_id (e.g. path-traversal attempt) must be rejected."""
        from app.adk.agents.agent_factory import specialist_runtime

        ctx = MagicMock()
        ctx.state = {"account_id": "../../etc/passwd"}
        result = specialist_runtime.available_specialists_provider(ctx)

        assert "## Available Specialists" in result
        assert "None registered" in result

    def test_returns_empty_block_on_firestore_error(self) -> None:
        from app.adk.agents.agent_factory import specialist_runtime
        from app.adk.agents.agent_factory.config_loader import FirestoreConnectionError

        ctx = self._make_context("acct_1")

        with patch(
            "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
            side_effect=FirestoreConnectionError("down"),
        ):
            result = specialist_runtime.available_specialists_provider(ctx)

        assert "None registered" in result

    def test_filters_out_not_ken_e_sub_agent(self) -> None:
        """AH-82: delegation filter is ken_e_sub_agent, not visible_in_frontend.

        An agent with ken_e_sub_agent=False is excluded from the block
        regardless of visible_in_frontend.  An agent with ken_e_sub_agent=True
        is included even if visible_in_frontend=False.
        """
        from app.adk.agents.agent_factory import specialist_runtime

        # ken_e_sub_agent=False → excluded, even though visible_in_frontend=True.
        not_delegatable_cfg = _make_merged_config(
            "not_delegatable", visible_in_frontend=True, ken_e_sub_agent=False
        )
        # ken_e_sub_agent=True, visible_in_frontend=False → still delegatable.
        delegatable_hidden_cfg = _make_merged_config(
            "delegatable", visible_in_frontend=False, ken_e_sub_agent=True
        )
        delegatable_agent = _make_llm_agent("delegatable_spe")

        ctx = self._make_context("acct_1")

        with (
            patch(
                "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
                return_value=["not_delegatable_spe", "delegatable_spe"],
            ),
            patch.object(
                specialist_runtime,
                "resolve_config",
                side_effect=[not_delegatable_cfg, delegatable_hidden_cfg],
            ),
            patch.object(
                specialist_runtime,
                "resolve_agent",
                return_value=delegatable_agent,
            ),
        ):
            result = specialist_runtime.available_specialists_provider(ctx)

        assert "delegatable_spe" in result
        assert "not_delegatable_spe" not in result

    def test_visible_in_frontend_does_not_affect_delegation(self) -> None:
        """AH-82: visible_in_frontend=False does NOT exclude from block when
        ken_e_sub_agent=True.  The two flags are fully independent."""
        from app.adk.agents.agent_factory import specialist_runtime

        # UI-hidden but delegatable agent.
        cfg = _make_merged_config(
            "hidden_but_delegatable", visible_in_frontend=False, ken_e_sub_agent=True
        )
        agent = _make_llm_agent("hidden_but_delegatable_spe")

        ctx = self._make_context("acct_1")

        with (
            patch(
                "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
                return_value=["hidden_but_delegatable_spe"],
            ),
            patch.object(specialist_runtime, "resolve_config", return_value=cfg),
            patch.object(specialist_runtime, "resolve_agent", return_value=agent),
        ):
            result = specialist_runtime.available_specialists_provider(ctx)

        assert "hidden_but_delegatable_spe" in result

    def test_failed_specialist_resolve_is_excluded_not_raised(self) -> None:
        from app.adk.agents.agent_factory import specialist_runtime

        good_cfg = _make_merged_config("good", ken_e_sub_agent=True)
        good_agent = _make_llm_agent("good_spe")

        ctx = self._make_context("acct_1")

        def resolve_config_side(doc_id: str, account_id: str | None, *a: Any) -> Any:
            if doc_id == "bad_spe":
                raise RuntimeError("bad config")
            return good_cfg

        with (
            patch(
                "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
                return_value=["bad_spe", "good_spe"],
            ),
            patch.object(
                specialist_runtime, "resolve_config", side_effect=resolve_config_side
            ),
            patch.object(specialist_runtime, "resolve_agent", return_value=good_agent),
        ):
            result = specialist_runtime.available_specialists_provider(ctx)

        assert "good_spe" in result
        assert "bad_spe" not in result

    # -----------------------------------------------------------------------
    # Regression coverage for AH-62 (PR #721) — provider/callback parity
    #
    # ``available_specialists_provider`` and
    # ``attach_specialists_before_agent_callback`` both extract
    # ``session_state`` from their respective context objects. ADK gives them
    # different state types:
    #
    # * ``CallbackContext.state`` returns ADK's ``State`` (no ``keys()`` /
    #   ``__iter__``; ``dict(state)`` raises ``KeyError: 0``).
    # * ``ReadonlyContext.state`` returns ``MappingProxyType`` over
    #   ``session.state`` today, which ``dict()`` casts cleanly.
    #
    # The provider previously used ``dict(context.state)``; it works for the
    # current ``MappingProxyType`` shape but silently breaks if a future ADK
    # release aligns the two contexts on ``State``. The
    # ``hasattr(state, "to_dict")`` guard in the provider matches the fix
    # already shipped in ``sub_agent_attacher.py:362`` so a future ADK shape
    # change cannot silently degrade the specialists block.
    # -----------------------------------------------------------------------

    def test_real_adk_state_session_state_forwarded(self) -> None:
        """When ``ReadonlyContext.state`` is an ADK ``State`` (forward-compat
        shape), the provider must extract session state via ``to_dict()`` and
        forward it to ``resolve_agent``. A regression here (e.g. reintroducing
        ``dict(state)``) would crash with ``KeyError: 0``."""
        from types import SimpleNamespace

        from google.adk.sessions.state import State

        from app.adk.agents.agent_factory import specialist_runtime

        good_cfg = _make_merged_config("good", ken_e_sub_agent=True)
        good_agent = _make_llm_agent("good_spe")
        state = State(
            value={"account_id": "acct_1", "mcp_creds_x": "v1"},
            delta={"mcp_creds_y": "v2"},
        )
        ctx = SimpleNamespace(state=state)
        seen_session_states: list[Any] = []

        def _capturing_resolve_agent(
            doc_id: str,
            _account_id: str | None = None,
            _ttl: int = 60,
            session_state: Any = None,
        ) -> Any:
            seen_session_states.append(session_state)
            return good_agent

        with (
            patch(
                "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
                return_value=["good_spe"],
            ),
            patch.object(specialist_runtime, "resolve_config", return_value=good_cfg),
            patch.object(
                specialist_runtime,
                "resolve_agent",
                side_effect=_capturing_resolve_agent,
            ),
        ):
            result = specialist_runtime.available_specialists_provider(ctx)  # type: ignore[arg-type]

        assert "good_spe" in result, (
            "Provider produced an empty block — likely a state→dict crash "
            "swallowed upstream. Did dict(state) regress for ADK State?"
        )
        assert seen_session_states, "resolve_agent was never called"
        forwarded = seen_session_states[0]
        assert forwarded is not None
        assert forwarded.get("account_id") == "acct_1"
        assert forwarded.get("mcp_creds_x") == "v1"
        assert forwarded.get("mcp_creds_y") == "v2"

    def test_mappingproxy_state_session_state_forwarded(self) -> None:
        """Today's ADK shape — ``ReadonlyContext.state`` returns
        ``MappingProxyType`` over ``session.state``. The provider must extract
        session state via the ``dict()`` fallback branch and forward it."""
        from types import MappingProxyType, SimpleNamespace

        from app.adk.agents.agent_factory import specialist_runtime

        good_cfg = _make_merged_config("good", ken_e_sub_agent=True)
        good_agent = _make_llm_agent("good_spe")
        proxy = MappingProxyType({"account_id": "acct_1", "mcp_creds_x": "v1"})
        ctx = SimpleNamespace(state=proxy)
        seen_session_states: list[Any] = []

        def _capturing_resolve_agent(
            doc_id: str,
            _account_id: str | None = None,
            _ttl: int = 60,
            session_state: Any = None,
        ) -> Any:
            seen_session_states.append(session_state)
            return good_agent

        with (
            patch(
                "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
                return_value=["good_spe"],
            ),
            patch.object(specialist_runtime, "resolve_config", return_value=good_cfg),
            patch.object(
                specialist_runtime,
                "resolve_agent",
                side_effect=_capturing_resolve_agent,
            ),
        ):
            result = specialist_runtime.available_specialists_provider(ctx)  # type: ignore[arg-type]

        assert "good_spe" in result
        forwarded = seen_session_states[0]
        assert forwarded.get("account_id") == "acct_1"
        assert forwarded.get("mcp_creds_x") == "v1"

    def test_slow_path_carries_name_and_title_into_block(self) -> None:
        """AH-84: slow path (no _available_specialists in state) must wire
        config.name + config.title from resolve_config into the metadata arg
        of assemble_available_specialists_block so the rendered bullet is
        enriched."""
        from app.adk.agents.agent_factory import specialist_runtime
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

        cfg_with_identity = MergedAgentConfig(
            instruction="Brand specialist.",
            model="gemini-2.5-pro",
            description="Guards the brand voice.",
            name="BEN-E",
            title="Brand Guardian",
            ken_e_sub_agent=True,
        )
        agent = _make_llm_agent("ben_e_agent")
        ctx = self._make_context("acct_1")  # no _available_specialists key

        with (
            patch(
                "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
                return_value=["ben_e_agent"],
            ),
            patch.object(
                specialist_runtime, "resolve_config", return_value=cfg_with_identity
            ),
            patch.object(specialist_runtime, "resolve_agent", return_value=agent),
        ):
            result = specialist_runtime.available_specialists_provider(ctx)

        assert '- **ben_e_agent** — known as "BEN-E", Brand Guardian:' in result, (
            "Slow path must include human_name and title in the block when "
            "config.name and config.title are set."
        )


# ---------------------------------------------------------------------------
# TestAvailableSpecialistsProviderFastPath — AH-86
# ---------------------------------------------------------------------------


class TestAvailableSpecialistsProviderFastPath:
    """Regression guard for AH-86.

    When ``state["_available_specialists"]`` is present and non-empty,
    ``available_specialists_provider`` MUST:

    1. Return the correctly-formatted block directly from those dicts.
    2. NOT call ``list_account_agent_configs_cached`` or ``resolve_agent``
       (patched to raise so any accidental call fails the test immediately).
    3. Produce output byte-for-byte identical to
       ``assemble_available_specialists_block`` for the same specialists.

    When the key is absent or empty, the provider MUST fall back to the
    existing Firestore resolution path (slow path preserved).
    """

    def _make_state_context(
        self,
        account_id: str | None = "acct_1",
        specialists: list[dict[str, Any]] | None = None,
    ) -> MagicMock:
        """Return a minimal ReadonlyContext mock with the given state."""
        ctx = MagicMock()
        state: dict[str, Any] = {}
        if account_id:
            state["account_id"] = account_id
        if specialists is not None:
            state["_available_specialists"] = specialists
        ctx.state = state
        return ctx

    # ------------------------------------------------------------------
    # Fast path — regression guard for the AH-86 hang
    # ------------------------------------------------------------------

    def test_fast_path_returns_block_without_firestore_or_resolution(
        self,
    ) -> None:
        """When _available_specialists is in state, the block is built from
        those dicts and neither list_account_agent_configs_cached nor
        resolve_agent is called.  Both are patched to raise so any accidental
        invocation fails the test immediately."""
        from app.adk.agents.agent_factory import specialist_runtime

        state_specialists = [
            {
                "name": "analytics",
                "description": "GA4 analytics specialist",
                "agent_id": "analytics",
            },
            {
                "name": "strategy",
                "description": "Strategy specialist",
                "agent_id": "strategy",
            },
        ]
        ctx = self._make_state_context(specialists=state_specialists)

        with (
            patch.object(
                specialist_runtime,
                "list_account_agent_configs_cached",
                side_effect=AssertionError(
                    "list_account_agent_configs_cached must NOT be called on fast path"
                ),
            ),
            patch.object(
                specialist_runtime,
                "resolve_agent",
                side_effect=AssertionError(
                    "resolve_agent must NOT be called on fast path"
                ),
            ),
        ):
            result = specialist_runtime.available_specialists_provider(ctx)

        assert "## Available Specialists" in result
        assert "analytics" in result
        assert "strategy" in result
        assert "GA4 analytics specialist" in result
        assert "Strategy specialist" in result

    def test_fast_path_output_matches_assemble_block_output(self) -> None:
        """Block from fast path must be byte-for-byte identical to the block
        produced by assemble_available_specialists_block for the same data."""
        from app.adk.agents.agent_factory import specialist_runtime
        from app.adk.agents.agent_factory.dispatch import (
            assemble_available_specialists_block,
            assemble_specialists_block_from_state,
        )

        state_specialists = [
            {
                "name": "analytics",
                "description": "GA4 analytics specialist",
                "agent_id": "analytics",
            },
            {
                "name": "strategy",
                "description": "Strategy specialist",
                "agent_id": "strategy",
            },
        ]
        ctx = self._make_state_context(specialists=state_specialists)

        # Build the reference block via the BaseAgent path.
        agents: dict[str, Any] = {}
        for entry in state_specialists:
            agent = MagicMock()
            agent.name = entry["name"]
            agent.description = entry["description"]
            agents[entry["name"]] = agent
        reference_block = assemble_available_specialists_block(agents)

        # Fast path must match.
        fast_path_block = assemble_specialists_block_from_state(state_specialists)
        assert fast_path_block == reference_block, (
            f"Fast path block differs from reference:\n"
            f"fast:      {fast_path_block!r}\n"
            f"reference: {reference_block!r}"
        )

        # Provider must also match.
        with (
            patch.object(
                specialist_runtime,
                "list_account_agent_configs_cached",
                side_effect=AssertionError("must not call list on fast path"),
            ),
            patch.object(
                specialist_runtime,
                "resolve_agent",
                side_effect=AssertionError("must not call resolve_agent on fast path"),
            ),
        ):
            provider_block = specialist_runtime.available_specialists_provider(ctx)

        assert provider_block == reference_block, (
            f"Provider block differs from reference:\n"
            f"provider:  {provider_block!r}\n"
            f"reference: {reference_block!r}"
        )

    def test_fast_path_alphabetical_ordering(self) -> None:
        """Specialists are listed in alphabetical order on the fast path,
        matching the behaviour of assemble_available_specialists_block."""
        from app.adk.agents.agent_factory import specialist_runtime

        state_specialists = [
            {"name": "zeta", "description": "Last alphabetically", "agent_id": "zeta"},
            {
                "name": "alpha",
                "description": "First alphabetically",
                "agent_id": "alpha",
            },
            {"name": "mu", "description": "Middle alphabetically", "agent_id": "mu"},
        ]
        ctx = self._make_state_context(specialists=state_specialists)

        with (
            patch.object(
                specialist_runtime,
                "list_account_agent_configs_cached",
                side_effect=AssertionError("must not call list on fast path"),
            ),
            patch.object(
                specialist_runtime,
                "resolve_agent",
                side_effect=AssertionError("must not call resolve_agent on fast path"),
            ),
        ):
            result = specialist_runtime.available_specialists_provider(ctx)

        lines = [ln for ln in result.splitlines() if ln.startswith("- **")]
        assert lines[0].startswith("- **alpha**"), f"Expected alpha first; got {lines}"
        assert lines[1].startswith("- **mu**"), f"Expected mu second; got {lines}"
        assert lines[2].startswith("- **zeta**"), f"Expected zeta third; got {lines}"

    def test_fast_path_empty_description_uses_fallback(self) -> None:
        """Empty description in state dict produces '(no description provided)'."""
        from app.adk.agents.agent_factory import specialist_runtime

        state_specialists = [
            {"name": "nodesc", "description": "", "agent_id": "nodesc"},
        ]
        ctx = self._make_state_context(specialists=state_specialists)

        with (
            patch.object(
                specialist_runtime,
                "list_account_agent_configs_cached",
                side_effect=AssertionError("must not call list on fast path"),
            ),
            patch.object(
                specialist_runtime,
                "resolve_agent",
                side_effect=AssertionError("must not call resolve_agent on fast path"),
            ),
        ):
            result = specialist_runtime.available_specialists_provider(ctx)

        assert "(no description provided)" in result

    # ------------------------------------------------------------------
    # Slow path — fallback when _available_specialists absent/empty
    # ------------------------------------------------------------------

    def test_slow_path_used_when_state_key_absent(self) -> None:
        """When _available_specialists is not in state, the provider falls back
        to the existing Firestore resolution path."""
        from app.adk.agents.agent_factory import specialist_runtime

        cfg = _make_merged_config("v1", visible_in_frontend=True)
        agent = _make_llm_agent("spe_1")
        # No _available_specialists key in state — only account_id.
        ctx = MagicMock()
        ctx.state = {"account_id": "acct_1"}
        list_mock = MagicMock(return_value=["spe_1"])

        with (
            patch(
                "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
                list_mock,
            ),
            patch.object(specialist_runtime, "resolve_config", return_value=cfg),
            patch.object(specialist_runtime, "resolve_agent", return_value=agent),
        ):
            result = specialist_runtime.available_specialists_provider(ctx)

        # list_account_agent_configs should have been called (slow path ran).
        assert list_mock.called, "Slow path should call list_account_agent_configs"
        assert "spe_1" in result

    def test_slow_path_used_when_state_key_is_empty_list(self) -> None:
        """When _available_specialists is [] (empty), the slow path runs."""
        from app.adk.agents.agent_factory import specialist_runtime

        cfg = _make_merged_config("v1", visible_in_frontend=True)
        agent = _make_llm_agent("spe_1")
        ctx = self._make_state_context(specialists=[])  # empty list
        list_mock = MagicMock(return_value=["spe_1"])

        with (
            patch(
                "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
                list_mock,
            ),
            patch.object(specialist_runtime, "resolve_config", return_value=cfg),
            patch.object(specialist_runtime, "resolve_agent", return_value=agent),
        ):
            result = specialist_runtime.available_specialists_provider(ctx)

        assert list_mock.called, "Slow path should call list_account_agent_configs"
        assert "spe_1" in result

    # ------------------------------------------------------------------
    # assemble_specialists_block_from_state unit tests
    # ------------------------------------------------------------------

    def test_assemble_block_from_state_empty_list(self) -> None:
        """Empty dicts list returns the heading + 'None registered.'."""
        from app.adk.agents.agent_factory.dispatch import (
            assemble_specialists_block_from_state,
        )

        result = assemble_specialists_block_from_state([])
        assert result == "## Available Specialists\n\n- None registered."

    def test_assemble_block_from_state_single_specialist(self) -> None:
        """Single entry produces one bullet with name and description."""
        from app.adk.agents.agent_factory.dispatch import (
            assemble_specialists_block_from_state,
        )

        result = assemble_specialists_block_from_state(
            [
                {
                    "name": "analytics",
                    "description": "GA4 analytics",
                    "agent_id": "analytics",
                }
            ]
        )
        assert result == "## Available Specialists\n\n- **analytics**: GA4 analytics"

    def test_assemble_block_from_state_skips_entries_without_name(self) -> None:
        """Entries with a missing or empty 'name' key are silently skipped."""
        from app.adk.agents.agent_factory.dispatch import (
            assemble_specialists_block_from_state,
        )

        result = assemble_specialists_block_from_state(
            [
                {"name": "", "description": "Should be skipped", "agent_id": ""},
                {"name": "analytics", "description": "GA4", "agent_id": "analytics"},
            ]
        )
        assert "analytics" in result
        assert "Should be skipped" not in result


# ---------------------------------------------------------------------------
# TestListCache
# ---------------------------------------------------------------------------


class TestListCache:
    """Verify TTL caching of ``list_account_agent_configs_cached``."""

    def test_second_call_within_ttl_skips_firestore(self) -> None:
        """Two calls within TTL should issue only one underlying list call."""
        from app.adk.agents.agent_factory import specialist_runtime

        list_mock = MagicMock(return_value=["spe_1", "spe_2"])

        with patch(
            "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
            list_mock,
        ):
            first = specialist_runtime.list_account_agent_configs_cached("acct_1")
            second = specialist_runtime.list_account_agent_configs_cached("acct_1")

        assert first == ["spe_1", "spe_2"]
        assert first == second
        assert list_mock.call_count == 1

    def test_call_after_ttl_expiry_refetches(self, monkeypatch: Any) -> None:
        """After TTL elapses the next call must re-issue the underlying list."""
        from app.adk.agents.agent_factory import specialist_runtime

        list_mock = MagicMock(return_value=["spe_1"])
        fake_clock = {"t": 1000.0}

        def fake_monotonic() -> float:
            return fake_clock["t"]

        monkeypatch.setattr(specialist_runtime.time, "monotonic", fake_monotonic)

        with patch(
            "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
            list_mock,
        ):
            specialist_runtime.list_account_agent_configs_cached("acct_1")
            fake_clock["t"] += specialist_runtime._LIST_CACHE_TTL + 1
            specialist_runtime.list_account_agent_configs_cached("acct_1")

        assert list_mock.call_count == 2

    def test_different_accounts_cached_independently(self) -> None:
        """Two different account_ids must each issue their own underlying list call."""
        from app.adk.agents.agent_factory import specialist_runtime

        list_mock = MagicMock(side_effect=[["spe_a"], ["spe_b"]])

        with patch(
            "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
            list_mock,
        ):
            r1 = specialist_runtime.list_account_agent_configs_cached("acct_1")
            r2 = specialist_runtime.list_account_agent_configs_cached("acct_2")
            # Repeat of acct_1 must hit the cache.
            r1b = specialist_runtime.list_account_agent_configs_cached("acct_1")

        assert r1 == ["spe_a"]
        assert r2 == ["spe_b"]
        assert r1b == ["spe_a"]
        assert list_mock.call_count == 2

    def test_available_specialists_provider_and_attach_share_one_list_call(
        self,
    ) -> None:
        """``available_specialists_provider`` and ``_attach_locked`` should share
        the cached list result within the same TTL window."""
        from unittest.mock import MagicMock, patch

        from google.adk.agents import LlmAgent

        from app.adk.agents.agent_factory import specialist_runtime, sub_agent_attacher

        cfg = _make_merged_config("v1", visible_in_frontend=True)
        agent = _make_llm_agent("spe_1")
        ctx = MagicMock()
        ctx.state = {"account_id": "acct_shared"}
        list_mock = MagicMock(return_value=["spe_1"])

        root = LlmAgent(name="root", model="gemini-2.5-pro", instruction="root")

        with (
            patch(
                "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
                list_mock,
            ),
            patch.object(specialist_runtime, "resolve_config", return_value=cfg),
            patch.object(specialist_runtime, "resolve_agent", return_value=agent),
        ):
            specialist_runtime.available_specialists_provider(ctx)
            sub_agent_attacher.attach_account_specialists(root, "acct_shared")

        assert list_mock.call_count == 1


# ---------------------------------------------------------------------------
# TestAvailableSpecialistsBlockCache
# ---------------------------------------------------------------------------


class TestAvailableSpecialistsBlockCache:
    """Verify TTL caching of the rendered ``## Available Specialists`` block."""

    def _make_context(self, account_id: str | None) -> MagicMock:
        ctx = MagicMock()
        ctx.state = {"account_id": account_id} if account_id else {}
        return ctx

    def test_repeated_call_within_ttl_skips_list_documents(self) -> None:
        """Two calls with same account_id should issue only one Firestore list."""
        from app.adk.agents.agent_factory import specialist_runtime

        cfg = _make_merged_config("v1", visible_in_frontend=True)
        agent = _make_llm_agent("spe_1")
        ctx = self._make_context("acct_1")
        list_mock = MagicMock(return_value=["spe_1"])

        with (
            patch(
                "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
                list_mock,
            ),
            patch.object(specialist_runtime, "resolve_config", return_value=cfg),
            patch.object(specialist_runtime, "resolve_agent", return_value=agent),
        ):
            first = specialist_runtime.available_specialists_provider(ctx)
            second = specialist_runtime.available_specialists_provider(ctx)

        assert first == second
        assert "spe_1" in first
        assert list_mock.call_count == 1

    def test_call_after_ttl_expiry_refetches(self, monkeypatch: Any) -> None:
        """When the TTL elapses, the next call must re-issue the list."""
        from app.adk.agents.agent_factory import specialist_runtime

        cfg = _make_merged_config("v1", visible_in_frontend=True)
        agent = _make_llm_agent("spe_1")
        ctx = self._make_context("acct_1")
        list_mock = MagicMock(return_value=["spe_1"])

        fake_clock = {"t": 1000.0}

        def fake_monotonic() -> float:
            return fake_clock["t"]

        monkeypatch.setattr(specialist_runtime.time, "monotonic", fake_monotonic)

        with (
            patch(
                "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
                list_mock,
            ),
            patch.object(specialist_runtime, "resolve_config", return_value=cfg),
            patch.object(specialist_runtime, "resolve_agent", return_value=agent),
        ):
            specialist_runtime.available_specialists_provider(ctx)
            fake_clock["t"] += specialist_runtime._BLOCK_CACHE_TTL + 1
            specialist_runtime.available_specialists_provider(ctx)

        assert list_mock.call_count == 2

    def test_different_account_ids_cached_independently(self) -> None:
        """Two different account_ids should each issue their own list call."""
        from app.adk.agents.agent_factory import specialist_runtime

        cfg = _make_merged_config("v1", visible_in_frontend=True)
        agent = _make_llm_agent("spe_1")
        list_mock = MagicMock(return_value=["spe_1"])

        with (
            patch(
                "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
                list_mock,
            ),
            patch.object(specialist_runtime, "resolve_config", return_value=cfg),
            patch.object(specialist_runtime, "resolve_agent", return_value=agent),
        ):
            specialist_runtime.available_specialists_provider(
                self._make_context("acct_1")
            )
            specialist_runtime.available_specialists_provider(
                self._make_context("acct_2")
            )
            # Repeats of acct_1 still hit the cache.
            specialist_runtime.available_specialists_provider(
                self._make_context("acct_1")
            )

        assert list_mock.call_count == 2

    def test_firestore_error_not_cached(self) -> None:
        """A FirestoreConnectionError fallback must not poison the cache."""
        from app.adk.agents.agent_factory import specialist_runtime
        from app.adk.agents.agent_factory.config_loader import FirestoreConnectionError

        cfg = _make_merged_config("v1", visible_in_frontend=True)
        agent = _make_llm_agent("spe_1")
        ctx = self._make_context("acct_1")

        list_mock = MagicMock(side_effect=[FirestoreConnectionError("down"), ["spe_1"]])

        with (
            patch(
                "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
                list_mock,
            ),
            patch.object(specialist_runtime, "resolve_config", return_value=cfg),
            patch.object(specialist_runtime, "resolve_agent", return_value=agent),
        ):
            first = specialist_runtime.available_specialists_provider(ctx)
            second = specialist_runtime.available_specialists_provider(ctx)

        assert "None registered" in first
        assert "spe_1" in second
        assert list_mock.call_count == 2

    def test_invalid_account_id_not_cached(self) -> None:
        """Invalid account_id returns fallback without touching or populating the cache."""
        from app.adk.agents.agent_factory import specialist_runtime

        cfg = _make_merged_config("v1", visible_in_frontend=True)
        agent = _make_llm_agent("spe_1")
        list_mock = MagicMock(return_value=["spe_1"])

        bad_ctx = MagicMock()
        bad_ctx.state = {"account_id": "../../etc/passwd"}
        good_ctx = self._make_context("acct_1")

        with (
            patch(
                "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
                list_mock,
            ),
            patch.object(specialist_runtime, "resolve_config", return_value=cfg),
            patch.object(specialist_runtime, "resolve_agent", return_value=agent),
        ):
            fallback = specialist_runtime.available_specialists_provider(bad_ctx)
            good = specialist_runtime.available_specialists_provider(good_ctx)

        assert "None registered" in fallback
        assert "spe_1" in good
        assert list_mock.call_count == 1
        # The invalid account_id never made it into the cache.
        assert "../../etc/passwd" not in specialist_runtime._block_cache


# ---------------------------------------------------------------------------
# TestPerAccountOverlay
# ---------------------------------------------------------------------------


class TestPerAccountOverlay:
    """Verify that per-account overlays produce distinct cache keys."""

    def test_global_and_account_configs_are_independent_keys(self) -> None:
        """resolve_config(doc_id, None) and resolve_config(doc_id, 'acct_1')
        must call get_cached_merged_config with different account_id values."""
        from app.adk.agents.agent_factory import specialist_runtime

        global_cfg = _make_merged_config("global_instr")
        account_cfg = _make_merged_config("account_instr")

        call_log: list[tuple[str, str | None]] = []

        def fake_get_cached(doc_id: str, account_id: str | None, ttl: int = 60) -> Any:
            call_log.append((doc_id, account_id))
            return global_cfg if account_id is None else account_cfg

        with patch.object(
            specialist_runtime, "get_cached_merged_config", side_effect=fake_get_cached
        ):
            cfg_global = specialist_runtime.resolve_config("specialist_1", None)
            cfg_account = specialist_runtime.resolve_config("specialist_1", "acct_1")

        assert call_log == [("specialist_1", None), ("specialist_1", "acct_1")]
        assert cfg_global.instruction == "global_instr"
        assert cfg_account.instruction == "account_instr"

    def test_account_overlay_produces_separate_agent_cache_entry(self) -> None:
        """(doc_id, None) and (doc_id, 'acct_1') must be separate agent cache keys."""
        from app.adk.agents.agent_factory import specialist_runtime

        cfg_global = _make_merged_config("global")
        cfg_account = _make_merged_config("account")
        agent_global = _make_llm_agent("global_agent")
        agent_account = _make_llm_agent("account_agent")

        resolve_config_returns = iter([cfg_global, cfg_account])
        build_returns = iter([agent_global, agent_account])

        with (
            patch.object(
                specialist_runtime,
                "resolve_config",
                side_effect=resolve_config_returns,
            ),
            patch.object(
                specialist_runtime,
                "_build_specialist",
                side_effect=build_returns,
            ) as mock_build,
        ):
            a_global = specialist_runtime.resolve_agent("spe_x", None)
            a_account = specialist_runtime.resolve_agent("spe_x", "acct_1")

        assert mock_build.call_count == 2
        assert a_global is agent_global
        assert a_account is agent_account


# ---------------------------------------------------------------------------
# TestAgentCache
# ---------------------------------------------------------------------------


class TestAgentCache:
    def test_put_and_get_returns_cached_agent(self) -> None:
        from app.adk.agents.agent_factory.specialist_runtime import _AgentCache

        cache = _AgentCache(maxsize=10)
        key = ("doc", None, "abc123")
        agent = _make_llm_agent()

        cache.put(key, agent)
        assert cache.get(key) is agent

    def test_miss_returns_none(self) -> None:
        from app.adk.agents.agent_factory.specialist_runtime import _AgentCache

        cache = _AgentCache(maxsize=10)
        assert cache.get(("missing", None, "xyz")) is None

    def test_lru_evicts_least_recently_used(self) -> None:
        """When at capacity, inserting a new entry evicts the LRU entry."""
        from app.adk.agents.agent_factory.specialist_runtime import _AgentCache

        cache = _AgentCache(maxsize=3)
        agents = [_make_llm_agent(f"a{i}") for i in range(4)]
        keys = [(f"doc_{i}", None, f"h{i}") for i in range(4)]

        for i in range(3):
            cache.put(keys[i], agents[i])

        # Access key_0 to make it the MRU — key_1 becomes the LRU.
        cache.get(keys[0])

        # Insert key_3: evicts key_1 (LRU).
        cache.put(keys[3], agents[3])

        assert cache.get(keys[0]) is agents[0], "key_0 (MRU) must be retained"
        assert cache.get(keys[1]) is None, "key_1 (LRU) must be evicted"
        assert cache.get(keys[2]) is agents[2], "key_2 must be retained"
        assert cache.get(keys[3]) is agents[3], "key_3 (new) must be present"

    def test_put_existing_key_updates_mru_position(self) -> None:
        """Re-inserting an existing key promotes it to MRU."""
        from app.adk.agents.agent_factory.specialist_runtime import _AgentCache

        cache = _AgentCache(maxsize=2)
        a0 = _make_llm_agent("a0")
        a0_new = _make_llm_agent("a0_new")
        a1 = _make_llm_agent("a1")
        a2 = _make_llm_agent("a2")

        key0 = ("doc_0", None, "h0")
        key1 = ("doc_1", None, "h1")
        key2 = ("doc_2", None, "h2")

        cache.put(key0, a0)
        cache.put(key1, a1)

        # Re-put key0 (makes it MRU); key1 becomes LRU.
        cache.put(key0, a0_new)

        # Insert key2: evicts key1 (LRU).
        cache.put(key2, a2)

        assert cache.get(key0) is a0_new
        assert cache.get(key1) is None, "key1 must be evicted as LRU"
        assert cache.get(key2) is a2

    def test_clear_empties_cache(self) -> None:
        from app.adk.agents.agent_factory.specialist_runtime import _AgentCache

        cache = _AgentCache(maxsize=10)
        for i in range(5):
            cache.put((f"doc_{i}", None, f"h{i}"), _make_llm_agent(f"a{i}"))

        cache.clear()
        assert len(cache) == 0

    def test_len_returns_entry_count(self) -> None:
        from app.adk.agents.agent_factory.specialist_runtime import _AgentCache

        cache = _AgentCache(maxsize=10)
        assert len(cache) == 0

        cache.put(("d1", None, "h1"), _make_llm_agent())
        assert len(cache) == 1

        cache.put(("d2", None, "h2"), _make_llm_agent())
        assert len(cache) == 2


# ---------------------------------------------------------------------------
# Helpers for _build_specialist regression tests (AH-PRD-06 + roster cap +
# default_global) — restored from the deleted hierarchy.py e2e tests.
# ---------------------------------------------------------------------------


def _make_specialist_config(
    *,
    mcp_servers: list[str] | None = None,
    tool_ids: list[str] | None = None,
) -> Any:
    """Return a MergedAgentConfig wired for ``_build_specialist`` tests."""
    from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

    return MergedAgentConfig(
        instruction="Test instruction",
        model="gemini-2.5-pro",
        description="Test specialist",
        mcp_servers=mcp_servers or [],
        tool_ids=tool_ids,
    )


class _FakeFirestoreDb:
    """Minimal in-memory Firestore stand-in for ``_build_firestore_client``.

    Keyed by ``(collection_name, doc_id)``. Mirrors the surface
    ``_build_specialist`` exercises:
    ``db.collection(name).document(id).get()`` returns a snapshot with
    ``exists: bool`` and ``to_dict() -> dict``.
    """

    def __init__(self, docs: dict[tuple[str, str], dict[str, Any]]) -> None:
        self._docs = docs

    def collection(self, name: str) -> Any:
        return _FakeCollection(self._docs, name)


class _FakeCollection:
    def __init__(
        self, docs: dict[tuple[str, str], dict[str, Any]], collection_name: str
    ) -> None:
        self._docs = docs
        self._collection_name = collection_name

    def document(self, doc_id: str) -> Any:
        return _FakeDocRef(self._docs, self._collection_name, doc_id)


class _FakeDocRef:
    def __init__(
        self,
        docs: dict[tuple[str, str], dict[str, Any]],
        collection_name: str,
        doc_id: str,
    ) -> None:
        self._docs = docs
        self._collection_name = collection_name
        self._doc_id = doc_id

    def get(self) -> Any:
        key = (self._collection_name, self._doc_id)
        if key in self._docs:
            return MagicMock(exists=True, to_dict=lambda: self._docs[key])
        return MagicMock(exists=False, to_dict=lambda: None)


def _enabled_mcp_doc() -> dict[str, Any]:
    """A minimal ``mcp_server_configs`` doc that passes the ``enabled`` gate.

    The doc shape doesn't have to match the full schema — we patch
    ``build_toolset_for_doc`` to bypass actual MCP construction; only the
    ``enabled`` flag affects ``_build_specialist`` control flow.
    """
    return {"enabled": True}


def _patch_specialist_runtime_externals(
    *,
    fake_db: _FakeFirestoreDb | None = None,
    default_global_tools: list[Any] | None = None,
    mock_resolver: bool = True,
) -> Any:
    """Build an ``ExitStack`` patching every external dep of ``_build_specialist``.

    All targets patch the *source* module path (e.g. ``...mcp.build_toolset_for_doc``)
    rather than ``specialist_runtime.*`` because ``_build_specialist`` re-imports
    each symbol via local ``from … import …`` inside the function body.

    AH-62 Phase 3: also patches ``specialist_runtime._DEFAULT_MCP_POOL`` with a
    fresh ``McpToolsetPool()`` so tests are isolated from each other (the module-level
    singleton would otherwise cache toolsets across test invocations).

    Args:
        fake_db: In-memory Firestore stand-in.  When ``None``, an empty
            ``_FakeFirestoreDb`` is used (no MCP server docs — all server
            lookups return ``exists=False``).
        default_global_tools: Pre-built list of stub ``FunctionTool``s to
            return from the mocked ``resolve_default_global_tools`` call.
            Ignored when ``mock_resolver=False``.
        mock_resolver: When ``True`` (default) the
            ``resolve_default_global_tools`` and ``get_default_registry``
            symbols are patched so tests control the default_global set
            directly.  Set to ``False`` to exercise the *real*
            ``function_tool_registry`` path — callers are then responsible
            for pre-populating ``_REGISTRY`` via ``register_function_tool``
            and cleaning up via ``clear_function_tool_registry``.

    Returns ``(stack, mock_build_toolset, mock_build_agent)`` so callers can
    inspect captured call args / kwargs after entering the stack.
    """
    from contextlib import ExitStack
    from unittest.mock import patch as _patch

    from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

    stack = ExitStack()

    if fake_db is None:
        fake_db = _FakeFirestoreDb({})

    # AH-62: inject a fresh pool per test for isolation.
    stack.enter_context(
        _patch(
            "app.adk.agents.agent_factory.specialist_runtime._DEFAULT_MCP_POOL",
            new=McpToolsetPool(),
        )
    )
    stack.enter_context(
        _patch(
            "app.adk.agents.agent_factory.mcp._build_firestore_client",
            return_value=fake_db,
        )
    )
    mock_btf = stack.enter_context(
        _patch(
            "app.adk.agents.agent_factory.mcp.build_toolset_for_doc",
            side_effect=lambda server_id, _doc, **_kw: MagicMock(
                name=f"toolset_{server_id}"
            ),
        )
    )
    if mock_resolver:
        stack.enter_context(
            _patch(
                "app.adk.tools.registry.function_tool_registry.resolve_default_global_tools",
                return_value=default_global_tools or [],
            )
        )
        stack.enter_context(
            _patch(
                "app.adk.tools.registry.tool_registry.get_default_registry",
                return_value=MagicMock(name="fake_registry"),
            )
        )
    mock_ba = stack.enter_context(
        _patch(
            "app.adk.agents.agent_factory.builder.build_agent",
            side_effect=lambda config, *, name, tools=None, **_kw: MagicMock(
                name=f"llmagent_{name}", tools=tools or []
            ),
        )
    )

    return stack, mock_btf, mock_ba


# ---------------------------------------------------------------------------
# TestSpecialistRuntimeToolIdsThreading — AH-PRD-06 MCP allowlist
# ---------------------------------------------------------------------------


class TestSpecialistRuntimeToolIdsThreading:
    """``_build_specialist`` must thread ``tool_ids`` into ``build_toolset_for_doc``
    via the ``allowed_tool_names`` kwarg, mirroring the pre-AH-PRD-09
    ``hierarchy.py`` path. Servers with no ``tool_ids`` match must be skipped
    entirely (no Firestore read, no toolset construction).

    Migrated from ``main:tests/test_hierarchy_e2e.py::TestAhPrd06ToolIdsThreading``
    after AH-60 moved specialist construction into ``specialist_runtime``.
    """

    def test_tool_ids_set_passes_allowed_tool_names_at_construction(self) -> None:
        from app.adk.agents.agent_factory import specialist_runtime as sr

        config = _make_specialist_config(
            mcp_servers=["ga_mcp"],
            tool_ids=["ga_mcp.list_ga_accounts"],
        )
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "ga_mcp"): _enabled_mcp_doc()}
        )
        stack, mock_btf, _ = _patch_specialist_runtime_externals(fake_db=fake_db)
        with stack:
            sr._build_specialist(config, "analytics_specialist", None)

        ga_calls = [
            kwargs for args, kwargs in mock_btf.call_args_list if args[0] == "ga_mcp"
        ]
        assert len(ga_calls) == 1, f"Expected one ga_mcp call, got {ga_calls!r}"
        assert ga_calls[0].get("allowed_tool_names") == ["list_ga_accounts"], (
            f"tool_ids must thread into allowed_tool_names; got {ga_calls[0]!r}"
        )

    def test_tool_ids_none_omits_allowed_tool_names_kwarg(self) -> None:
        """Legacy path: ``tool_ids=None`` preserves the two-arg signature so
        the ``McpToolset`` receives every tool the server exposes."""
        from app.adk.agents.agent_factory import specialist_runtime as sr

        config = _make_specialist_config(mcp_servers=["ga_mcp"], tool_ids=None)
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "ga_mcp"): _enabled_mcp_doc()}
        )
        stack, mock_btf, _ = _patch_specialist_runtime_externals(fake_db=fake_db)
        with stack:
            sr._build_specialist(config, "analytics_specialist", None)

        assert mock_btf.call_count == 1
        assert "allowed_tool_names" not in mock_btf.call_args.kwargs, (
            f"tool_ids=None must omit the kwarg; got {mock_btf.call_args!r}"
        )

    def test_tool_ids_skips_servers_with_no_match(self) -> None:
        """A server in ``mcp_servers`` that is not represented in ``tool_ids``
        must be dropped before any Firestore fetch or toolset construction —
        no point paying the connection cost for a toolset whose tools are
        all filtered out downstream."""
        from app.adk.agents.agent_factory import specialist_runtime as sr

        config = _make_specialist_config(
            mcp_servers=["ga_mcp", "shared_viz_mcp"],
            tool_ids=["ga_mcp.list_ga_accounts"],  # no shared_viz_mcp.* entry
        )
        fake_db = _FakeFirestoreDb(
            {
                ("mcp_server_configs", "ga_mcp"): _enabled_mcp_doc(),
                ("mcp_server_configs", "shared_viz_mcp"): _enabled_mcp_doc(),
            }
        )
        stack, mock_btf, _ = _patch_specialist_runtime_externals(fake_db=fake_db)
        with stack:
            sr._build_specialist(config, "analytics_specialist", None)

        called_servers = [args[0] for args, _ in mock_btf.call_args_list]
        assert called_servers == ["ga_mcp"], (
            f"shared_viz_mcp must be skipped (no tool_ids match); got {called_servers!r}"
        )


# ---------------------------------------------------------------------------
# TestSpecialistRuntimeDefaultGlobalTools — AH-PRD-06 PR-C
# ---------------------------------------------------------------------------


def _stub_function_tool(name: str) -> Any:
    """Return an object whose ``.name`` attribute matches ``name``.

    ``resolve_specialist_roster._filter_function_tools_by_ids`` reads
    ``getattr(tool, "name", None) or getattr(tool, "__name__", None)`` and
    keeps the tool when ``f"function.{name}"`` is in the allowlist.
    """
    tool = MagicMock(spec=["name"])
    tool.name = name
    return tool


class TestSpecialistRuntimeDefaultGlobalTools:
    """``_build_specialist`` must include every catalogued
    ``default_global: true`` function tool on every specialist (e.g.
    ``create_visualization`` from AH-PRD-04). When ``tool_ids`` is set, the
    same per-spec filter from ``resolve_specialist_roster`` applies.

    Migrated from ``main:tests/test_hierarchy_e2e.py::TestAhPrd06PrcDefaultGlobalFunctionTools``
    after AH-60 moved specialist construction into ``specialist_runtime``.
    """

    def test_default_global_tools_reach_specialist_when_tool_ids_none(self) -> None:
        """Legacy path: ``tool_ids=None`` keeps every default_global function
        tool alongside every MCP toolset."""
        from app.adk.agents.agent_factory import specialist_runtime as sr

        viz_tool = _stub_function_tool("create_visualization")
        config = _make_specialist_config(mcp_servers=[], tool_ids=None)

        stack, _, mock_ba = _patch_specialist_runtime_externals(
            default_global_tools=[viz_tool]
        )
        with stack:
            sr._build_specialist(config, "any_specialist", None)

        resolved_tools = mock_ba.call_args.kwargs["tools"]
        assert viz_tool in resolved_tools, (
            f"default_global tool must reach build_agent; got tools={resolved_tools!r}"
        )

    def test_default_global_tools_excluded_when_tool_ids_empty(self) -> None:
        """``tool_ids=[]`` is the "no tools" sentinel — both MCP and
        default_global function tools must be filtered out."""
        from app.adk.agents.agent_factory import specialist_runtime as sr

        viz_tool = _stub_function_tool("create_visualization")
        config = _make_specialist_config(mcp_servers=[], tool_ids=[])

        stack, _, mock_ba = _patch_specialist_runtime_externals(
            default_global_tools=[viz_tool]
        )
        with stack:
            sr._build_specialist(config, "any_specialist", None)

        resolved_tools = mock_ba.call_args.kwargs["tools"]
        assert viz_tool not in resolved_tools, (
            f"tool_ids=[] must exclude default_global; got tools={resolved_tools!r}"
        )

    def test_default_global_tool_included_when_named_in_tool_ids(self) -> None:
        """``tool_ids=["function.create_visualization"]`` keeps that tool and
        only that tool."""
        from app.adk.agents.agent_factory import specialist_runtime as sr

        viz_tool = _stub_function_tool("create_visualization")
        other_tool = _stub_function_tool("send_email")
        config = _make_specialist_config(
            mcp_servers=[], tool_ids=["function.create_visualization"]
        )

        stack, _, mock_ba = _patch_specialist_runtime_externals(
            default_global_tools=[viz_tool, other_tool]
        )
        with stack:
            sr._build_specialist(config, "any_specialist", None)

        resolved_tools = mock_ba.call_args.kwargs["tools"]
        assert viz_tool in resolved_tools
        assert other_tool not in resolved_tools

    def test_default_global_tool_excluded_when_other_function_named(self) -> None:
        """``tool_ids=["function.send_email"]`` keeps send_email and drops
        create_visualization — the filter is per-function-name, not "all
        default_global pass through"."""
        from app.adk.agents.agent_factory import specialist_runtime as sr

        viz_tool = _stub_function_tool("create_visualization")
        other_tool = _stub_function_tool("send_email")
        config = _make_specialist_config(
            mcp_servers=[], tool_ids=["function.send_email"]
        )

        stack, _, mock_ba = _patch_specialist_runtime_externals(
            default_global_tools=[viz_tool, other_tool]
        )
        with stack:
            sr._build_specialist(config, "any_specialist", None)

        resolved_tools = mock_ba.call_args.kwargs["tools"]
        assert other_tool in resolved_tools
        assert viz_tool not in resolved_tools

    def test_all_three_current_default_global_tools_reach_ga_specialist(self) -> None:
        """AH-PRD-09 Phase 3 AC #14 — every ``default_global: true`` function
        tool reaches every runtime-resolved specialist without per-specialist
        config edits.

        The current set of ``default_global`` tools is:
          * ``create_visualization`` (AH-PRD-04 / AH-PRD-06 PR-C)
          * ``set_todo_list`` (CH-PRD-05)
          * ``update_todo_list`` (CH-PRD-05)

        This test uses a GA-specialist config (``mcp_servers=["google_analytics_mcp"]``,
        ``tool_ids=None``) to mirror the real production setup. Every tool is
        asserted **by name** — a count-only or wildcard assertion would fail to
        catch a regression that drops one tool while keeping the others.
        """
        from app.adk.agents.agent_factory import specialist_runtime as sr

        viz_tool = _stub_function_tool("create_visualization")
        set_todo_tool = _stub_function_tool("set_todo_list")
        update_todo_tool = _stub_function_tool("update_todo_list")

        # Simulate a GA specialist with all three default_global tools injected.
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "google_analytics_mcp"): _enabled_mcp_doc()}
        )
        config = _make_specialist_config(
            mcp_servers=["google_analytics_mcp"], tool_ids=None
        )
        stack, _, mock_ba = _patch_specialist_runtime_externals(
            fake_db=fake_db,
            default_global_tools=[viz_tool, set_todo_tool, update_todo_tool],
        )
        with stack:
            sr._build_specialist(config, "google_analytics_specialist", None)

        resolved_tools = mock_ba.call_args.kwargs["tools"]
        tool_names = {
            getattr(t, "name", None) or getattr(t, "__name__", None)
            for t in resolved_tools
        }

        assert "create_visualization" in tool_names, (
            f"create_visualization must reach the GA specialist; got {tool_names!r}"
        )
        assert "set_todo_list" in tool_names, (
            f"set_todo_list must reach the GA specialist; got {tool_names!r}"
        )
        assert "update_todo_list" in tool_names, (
            f"update_todo_list must reach the GA specialist; got {tool_names!r}"
        )

    def test_default_global_tools_reach_specialist_via_real_registry(self) -> None:
        """Integration-level check: exercise the *real* ``function_tool_registry``
        rather than the mocked resolver path, so a regression in the
        catalogue→callable resolution chain is caught here independently of
        the mock-based tests above.

        Uses ``mock_resolver=False`` to bypass the
        ``resolve_default_global_tools`` patch, then pre-populates the real
        ``_REGISTRY`` with stub callables for each of the three current
        ``default_global`` tools.  ``get_default_registry()`` is NOT mocked so
        the real ``ToolRegistry`` (loaded from ``tools.yaml``) drives
        ``list_default_global_tools()``.

        AH-PRD-09 Phase 3 / AH-64 task 3.
        """
        import functools

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.tools.registry.function_tool_registry import (
            clear_function_tool_registry,
            register_function_tool,
        )

        # Stub callables that stand in for the real tool implementations.
        def _make_stub(tool_name: str) -> Any:
            @functools.wraps(lambda **kw: f"{tool_name} stub result")
            def stub(**kwargs: Any) -> str:
                return f"{tool_name} stub result"

            stub.__name__ = tool_name
            return stub

        clear_function_tool_registry()
        try:
            register_function_tool(
                "create_visualization", _make_stub("create_visualization")
            )
            register_function_tool("set_todo_list", _make_stub("set_todo_list"))
            register_function_tool("update_todo_list", _make_stub("update_todo_list"))

            fake_db = _FakeFirestoreDb(
                {("mcp_server_configs", "google_analytics_mcp"): _enabled_mcp_doc()}
            )
            config = _make_specialist_config(
                mcp_servers=["google_analytics_mcp"], tool_ids=None
            )
            # mock_resolver=False → real function_tool_registry is used;
            # only Firestore, MCP toolset construction, and build_agent are stubbed.
            stack, _, mock_ba = _patch_specialist_runtime_externals(
                fake_db=fake_db, mock_resolver=False
            )
            with stack:
                sr._build_specialist(config, "google_analytics_specialist", None)

            resolved_tools = mock_ba.call_args.kwargs["tools"]
            tool_names = {
                getattr(t, "name", None) or getattr(t, "__name__", None)
                for t in resolved_tools
            }

            assert "create_visualization" in tool_names, (
                f"create_visualization must reach specialist via real registry; "
                f"got {tool_names!r}"
            )
            assert "set_todo_list" in tool_names, (
                f"set_todo_list must reach specialist via real registry; "
                f"got {tool_names!r}"
            )
            assert "update_todo_list" in tool_names, (
                f"update_todo_list must reach specialist via real registry; "
                f"got {tool_names!r}"
            )
        finally:
            clear_function_tool_registry()


# ---------------------------------------------------------------------------
# TestSpecialistRuntimeRosterCap — AH-PRD-02 §2.5 ≤30-tool cap enforcement
# ---------------------------------------------------------------------------


class TestSpecialistRuntimeRosterCap:
    """``_build_specialist`` must enforce the ≤30-tool roster cap by calling
    ``resolve_specialist_roster``. The literal ``len(tools) > MAX_…`` check
    inside ``builder.build_agent`` counts each ``McpToolset`` as 1 item, so
    a single MCP server exposing 80 tools would slip past it; the logical
    cap is enforced upstream in ``resolve_specialist_roster``.
    """

    def test_roster_cap_exceeded_propagates(self) -> None:
        """When ``resolve_specialist_roster`` raises ``RosterCapExceededError``,
        ``_build_specialist`` must let it propagate so the dispatch surface
        can surface a clear error (mirrors deploy-time behaviour)."""
        from unittest.mock import patch as _patch

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.roster import RosterCapExceededError

        config = _make_specialist_config(mcp_servers=[], tool_ids=None)

        stack, _, _ = _patch_specialist_runtime_externals()
        with (
            stack,
            _patch(
                "app.adk.agents.agent_factory.roster.resolve_specialist_roster",
                side_effect=RosterCapExceededError("test cap exceeded: 31 tools > 30"),
            ),
            pytest.raises(RosterCapExceededError, match="test cap exceeded"),
        ):
            sr._build_specialist(config, "fat_specialist", None)

    def test_roster_cap_within_limit_succeeds(self) -> None:
        """A within-cap roster must produce a successful build with the
        resolved tools forwarded to ``build_agent``."""
        from app.adk.agents.agent_factory import specialist_runtime as sr

        viz_tool = _stub_function_tool("create_visualization")
        config = _make_specialist_config(mcp_servers=[], tool_ids=None)

        stack, _, mock_ba = _patch_specialist_runtime_externals(
            default_global_tools=[viz_tool]
        )
        with stack:
            result = sr._build_specialist(config, "small_specialist", None)

        # build_agent was called with the resolved tools (function tool only,
        # since no MCP servers were attached). The patched build_agent uses
        # ``side_effect`` to mint a fresh MagicMock per call, so verify the
        # returned object is the mock instance with the expected name.
        assert mock_ba.call_count == 1
        assert result._extract_mock_name() == "llmagent_small_specialist"
        assert viz_tool in mock_ba.call_args.kwargs["tools"]

    def test_roster_cap_error_propagates_through_resolve_agent(self) -> None:
        """When ``resolve_agent`` triggers a cache miss and ``_build_specialist``
        raises ``RosterCapExceededError``, the error must surface at the
        ``resolve_agent`` boundary so callers (``run`` →
        ``delegate_to_specialist``) can render a graceful error."""
        from unittest.mock import patch as _patch

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.roster import RosterCapExceededError

        cfg = _make_specialist_config(mcp_servers=[], tool_ids=None)

        with (
            _patch.object(sr, "resolve_config", return_value=cfg),
            _patch.object(
                sr,
                "_build_specialist",
                side_effect=RosterCapExceededError("31 > 30"),
            ),
            pytest.raises(RosterCapExceededError, match="31 > 30"),
        ):
            sr.resolve_agent("fat_specialist", account_id=None)

    def test_default_global_tools_count_against_roster_cap(self) -> None:
        """The ≤30-tool budget includes ``default_global`` function tools, not
        just MCP tools.  A specialist with 28 MCP-catalogued tools + 3
        default_global function tools (31 total) must trigger
        ``RosterCapExceededError``.

        AH-64 documents that this is a stricter check than the old deploy-time
        factory's literal ``len(tools) > MAX_…`` guard (which counted each
        ``McpToolset`` as one item regardless of how many tools it exposed).
        """
        from unittest.mock import patch as _patch

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.roster import RosterCapExceededError
        from shared.agent_tool_limits import MAX_TOOLS_PER_SPECIALIST

        viz_tool = _stub_function_tool("create_visualization")
        set_todo_tool = _stub_function_tool("set_todo_list")
        update_todo_tool = _stub_function_tool("update_todo_list")

        # 28 MCP tools + 3 default_global function tools = 31 > MAX (30).
        mcp_tool_count = (
            MAX_TOOLS_PER_SPECIALIST
            - len([viz_tool, set_todo_tool, update_todo_tool])
            + 1
        )

        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "huge_mcp"): _enabled_mcp_doc()}
        )
        config = _make_specialist_config(mcp_servers=["huge_mcp"], tool_ids=None)

        stack, _, _ = _patch_specialist_runtime_externals(
            fake_db=fake_db,
            default_global_tools=[viz_tool, set_todo_tool, update_todo_tool],
        )
        with (
            stack,
            _patch(
                "app.adk.agents.agent_factory.roster._tool_count_for_server",
                return_value=mcp_tool_count,
            ),
            pytest.raises(RosterCapExceededError),
        ):
            sr._build_specialist(config, "fat_specialist", None)

    def test_default_global_tools_within_cap_when_mcp_count_fits(self) -> None:
        """Inverse of the stress test: a specialist with 27 MCP-catalogued
        tools + 3 default_global function tools = 30 (exactly at cap) must
        succeed.  Confirms the off-by-one boundary is correct.
        """
        from unittest.mock import patch as _patch

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from shared.agent_tool_limits import MAX_TOOLS_PER_SPECIALIST

        viz_tool = _stub_function_tool("create_visualization")
        set_todo_tool = _stub_function_tool("set_todo_list")
        update_todo_tool = _stub_function_tool("update_todo_list")

        # Exactly at cap: 27 MCP + 3 default_global = 30.
        mcp_tool_count = MAX_TOOLS_PER_SPECIALIST - len(
            [viz_tool, set_todo_tool, update_todo_tool]
        )

        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "large_mcp"): _enabled_mcp_doc()}
        )
        config = _make_specialist_config(mcp_servers=["large_mcp"], tool_ids=None)

        stack, _, mock_ba = _patch_specialist_runtime_externals(
            fake_db=fake_db,
            default_global_tools=[viz_tool, set_todo_tool, update_todo_tool],
        )
        with (
            stack,
            _patch(
                "app.adk.agents.agent_factory.roster._tool_count_for_server",
                return_value=mcp_tool_count,
            ),
        ):
            sr._build_specialist(config, "at_cap_specialist", None)

        # Build succeeded — no exception; build_agent was called once.
        assert mock_ba.call_count == 1


# ---------------------------------------------------------------------------
# TestSpecialistRuntimeReviewWrap — AH-75 / AH-PRD-09: review-pipeline opt-in
# moves from per-call dispatch arg to a property of the specialist's Firestore
# config (``default_acceptance_criteria``). When set, ``_build_specialist``
# wraps the constructed ``LlmAgent`` in ``build_review_pipeline`` and renames
# the resulting ``LoopAgent`` to the specialist's doc_id so
# ``transfer_to_agent(agent_name=<doc_id>)`` resolves to the wrapped pipeline.
# ---------------------------------------------------------------------------


class TestSpecialistRuntimeReviewWrap:
    def test_no_criteria_returns_unwrapped_llmagent(self) -> None:
        """When ``default_acceptance_criteria`` is unset, the returned agent is the
        raw ``LlmAgent`` from ``build_agent`` — no review-pipeline construction."""
        from app.adk.agents.agent_factory import specialist_runtime as sr

        config = _make_specialist_config(mcp_servers=[], tool_ids=None)
        # Sanity: helper builds a config with default_acceptance_criteria=None.
        assert config.default_acceptance_criteria is None

        stack, _mock_btf, mock_ba = _patch_specialist_runtime_externals()
        with stack:
            from unittest.mock import patch as _patch

            with _patch(
                "app.adk.agents.utils.review_pipeline.build_review_pipeline"
            ) as mock_build_pipeline:
                result = sr._build_specialist(config, "plain_spec", None)

        # Wrap NOT applied.
        mock_build_pipeline.assert_not_called()
        # Returned agent is the build_agent output (raw LlmAgent mock).
        assert mock_ba.call_count == 1
        assert result._extract_mock_name() == "llmagent_plain_spec"

    def test_criteria_set_wraps_in_review_pipeline_renamed_to_doc_id(self) -> None:
        """When ``default_acceptance_criteria`` is set, ``_build_specialist`` calls
        ``build_review_pipeline`` with the sanitised criteria and renames the
        returned LoopAgent to the specialist's doc_id so ADK's
        ``transfer_to_agent(agent_name=<doc_id>)`` finds it via
        ``root.find_agent``."""
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

        config = MergedAgentConfig(
            instruction="Strategy specialist.",
            model="gemini-2.5-pro",
            description="Strategy specialist description.",
            default_acceptance_criteria="Cite at least 3 sources.",
        )

        # Build a custom externals stack so build_agent returns a mock whose
        # ``.description`` actually reflects the config (the default helper's
        # side_effect leaves .description as an auto-generated child MagicMock,
        # which masks the carry-over assertion below).
        from contextlib import ExitStack
        from unittest.mock import patch as _patch

        with ExitStack() as stack:
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.mcp._build_firestore_client",
                    return_value=_FakeFirestoreDb({}),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.tools.registry.function_tool_registry.resolve_default_global_tools",
                    return_value=[],
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.tools.registry.tool_registry.get_default_registry",
                    return_value=MagicMock(name="fake_registry"),
                )
            )

            def _make_specialist_mock(_config: Any, *, name: str, **_kw: Any) -> Any:
                m = MagicMock(name=f"llmagent_{name}")
                m.name = name  # explicit, not the MagicMock auto-name
                m.description = _config.description
                return m

            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.build_agent",
                    side_effect=_make_specialist_mock,
                )
            )

            # MagicMock LoopAgent stand-in. The production build_review_pipeline
            # returns a LoopAgent named ``f"{output_key_prefix}_loop"``; the
            # _build_specialist body assigns .name = doc_id post-construction.
            fake_pipeline = MagicMock(name="loopagent")
            fake_pipeline.name = "strategy_review_loop"  # production default
            fake_pipeline.description = ""

            mock_build_pipeline = stack.enter_context(
                _patch(
                    "app.adk.agents.utils.review_pipeline.build_review_pipeline",
                    return_value=fake_pipeline,
                )
            )
            result = sr._build_specialist(config, "strategy", None)

        # Pipeline construction called with sanitised criteria + correct prefix.
        mock_build_pipeline.assert_called_once()
        call_kwargs = mock_build_pipeline.call_args.kwargs
        assert call_kwargs["acceptance_criteria"] == "Cite at least 3 sources."
        assert call_kwargs["output_key_prefix"] == "strategy_review"
        # The returned agent IS the pipeline (not the inner specialist).
        assert result is fake_pipeline
        # Renamed to the doc_id so find_agent resolves transfer_to_agent.
        assert result.name == "strategy"
        # Description carried across from the inner specialist.
        assert result.description == "Strategy specialist description."

    def test_blank_criteria_treated_as_no_criteria(self) -> None:
        """Whitespace-only ``default_acceptance_criteria`` does NOT trigger wrap —
        keeps the contract that empty config means single-pass dispatch."""
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

        config = MergedAgentConfig(
            instruction="Test instruction.",
            model="gemini-2.5-pro",
            description="Test specialist",
            default_acceptance_criteria="   \n\t  ",  # whitespace-only
        )

        stack, _mock_btf, _mock_ba = _patch_specialist_runtime_externals()
        with stack:
            from unittest.mock import patch as _patch

            with _patch(
                "app.adk.agents.utils.review_pipeline.build_review_pipeline"
            ) as mock_build_pipeline:
                sr._build_specialist(config, "whitespace_spec", None)

        mock_build_pipeline.assert_not_called()

    def test_company_news_agent_with_criteria_wraps_in_review_pipeline(self) -> None:
        """When ``company_news_agent`` has ``default_acceptance_criteria`` set to
        ``REVIEW_CRITERIA_TEXT``, ``_build_specialist`` wraps the constructed
        ``LlmAgent`` in a ``LoopAgent`` review pipeline and renames it to the
        doc_id so ``transfer_to_agent(agent_name="company_news_agent")`` resolves."""
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool
        from app.adk.agents.scripts.seed_news_researcher_review_criteria import (
            REVIEW_CRITERIA_TEXT,
        )

        config = MergedAgentConfig(
            instruction="Company news specialist.",
            model="gemini-2.5-pro",
            description="Company news assistant.",
            default_acceptance_criteria=REVIEW_CRITERIA_TEXT,
        )

        from contextlib import ExitStack
        from unittest.mock import patch as _patch

        with ExitStack() as stack:
            # Isolate the module-level pool singleton (isolation contract from
            # _patch_specialist_runtime_externals, line 1336).
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.specialist_runtime._DEFAULT_MCP_POOL",
                    new=McpToolsetPool(),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.mcp._build_firestore_client",
                    return_value=_FakeFirestoreDb({}),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.tools.registry.function_tool_registry.resolve_default_global_tools",
                    return_value=[],
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.tools.registry.tool_registry.get_default_registry",
                    return_value=MagicMock(name="fake_registry"),
                )
            )

            def _make_specialist_mock(_config: Any, *, name: str, **_kw: Any) -> Any:
                m = MagicMock(name=f"llmagent_{name}")
                m.name = name
                m.description = _config.description
                return m

            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.build_agent",
                    side_effect=_make_specialist_mock,
                )
            )

            fake_pipeline = MagicMock(name="loopagent")
            fake_pipeline.name = "company_news_agent_review_loop"
            fake_pipeline.description = ""

            mock_build_pipeline = stack.enter_context(
                _patch(
                    "app.adk.agents.utils.review_pipeline.build_review_pipeline",
                    return_value=fake_pipeline,
                )
            )
            result = sr._build_specialist(config, "company_news_agent", None)

        mock_build_pipeline.assert_called_once()
        call_kwargs = mock_build_pipeline.call_args.kwargs
        # REVIEW_CRITERIA_TEXT uses only ASCII characters so sanitise_criteria
        # passes it through unchanged — assert the raw constant directly.
        assert call_kwargs["acceptance_criteria"] == REVIEW_CRITERIA_TEXT
        assert call_kwargs["output_key_prefix"] == "company_news_agent_review"
        assert result is fake_pipeline
        assert result.name == "company_news_agent"
        assert result.description == "Company news assistant."

    # --- AH-92: reviewer_model threads from config → reviewer child ---------

    def _build_with_real_review_pipeline(self, config: Any, doc_id: str) -> Any:
        """Drive ``_build_specialist`` through the *real* ``build_review_pipeline``
        so the returned ``LoopAgent``'s reviewer child reflects the resolved
        ``reviewer_model``.

        Only GCP/registry infrastructure is stubbed; ``build_agent`` returns a
        real minimal ``LlmAgent`` (``build_review_pipeline`` copies its field set
        onto the worker) and the pipeline itself runs unpatched, so the reviewer
        child is a real ``LlmAgent`` carrying ``.model``.
        """
        from contextlib import ExitStack
        from unittest.mock import patch as _patch

        from google.adk.agents import LlmAgent

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        def _real_specialist(_config: Any, *, name: str, **_kw: Any) -> LlmAgent:
            return LlmAgent(
                name=name,
                model=_config.model,
                instruction=_config.instruction,
                description=_config.description,
            )

        with ExitStack() as stack:
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.specialist_runtime._DEFAULT_MCP_POOL",
                    new=McpToolsetPool(),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.mcp._build_firestore_client",
                    return_value=_FakeFirestoreDb({}),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.tools.registry.function_tool_registry.resolve_default_global_tools",
                    return_value=[],
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.tools.registry.tool_registry.get_default_registry",
                    return_value=MagicMock(name="fake_registry"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.build_agent",
                    side_effect=_real_specialist,
                )
            )
            # build_review_pipeline runs unpatched.
            return sr._build_specialist(config, doc_id, None)

    def test_reviewer_model_set_threads_to_reviewer_child(self) -> None:
        """AH-92 AC1: a config with ``reviewer_model`` set builds a review
        ``LoopAgent`` whose reviewer child (``sub_agents[1]``) uses that model,
        independent of the specialist's own ``model``."""
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

        config = MergedAgentConfig(
            instruction="News researcher.",
            model="gemini-2.5-pro",
            description="News researcher.",
            default_acceptance_criteria="Cite at least 3 sources.",
            reviewer_model="gemini-2.5-flash",
        )

        worker, reviewer = self._build_with_real_review_pipeline(
            config, "news_researcher"
        ).sub_agents

        assert (worker.model, reviewer.model) == ("gemini-2.5-pro", "gemini-2.5-flash")

    def test_reviewer_model_unset_falls_back_to_default(self) -> None:
        """AH-92 AC2: a config with ``reviewer_model`` unset (None) falls back to
        ``DEFAULT_REVIEWER_MODEL`` on the reviewer child — no behavior change from
        before the field existed, and independent of the specialist's ``model``."""
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
        from app.adk.agents.utils.review_pipeline import DEFAULT_REVIEWER_MODEL

        config = MergedAgentConfig(
            instruction="News researcher.",
            model="gemini-2.5-flash",
            description="News researcher.",
            default_acceptance_criteria="Cite at least 3 sources.",
        )
        assert config.reviewer_model is None  # sanity: field defaults to unset

        worker, reviewer = self._build_with_real_review_pipeline(
            config, "news_researcher"
        ).sub_agents

        assert (worker.model, reviewer.model) == ("gemini-2.5-flash", DEFAULT_REVIEWER_MODEL)


# ---------------------------------------------------------------------------
# TestHarnessDefaultReviewerModel — AH-93: harness-wide default reviewer model
# ---------------------------------------------------------------------------
# This class tests the three ACs of the resolution chain:
#
#   AC1: No override + no system doc  → DEFAULT_REVIEWER_MODEL (code floor).
#   AC2: No override + system doc set → system-doc value used.
#   AC3: Per-specialist override wins over system doc.
#   AC4: Cache propagation — changing the system default yields a new cache key
#        so already-resolved LoopAgents are NOT reused stale.
#   AC5: Non-review specialists' cache keys are UNAFFECTED by system-default
#        changes (gate on default_acceptance_criteria truthy).
#   AC6: _content_hash is deterministic for identical inputs.
# ---------------------------------------------------------------------------


class TestHarnessDefaultReviewerModel:
    """AH-93: harness-wide default reviewer model resolution chain + cache propagation."""

    def _build_with_real_review_pipeline(
        self,
        config: Any,
        doc_id: str,
        *,
        harness_default: str | None = None,
    ) -> Any:
        """Drive ``_build_specialist`` with the *real* ``build_review_pipeline``.

        Stubs GCP / registry infrastructure and patches
        ``harness_default_reviewer_model`` to return *harness_default*.
        ``build_agent`` returns a real minimal ``LlmAgent`` so the reviewer
        child has a real ``.model`` attribute.
        """
        from contextlib import ExitStack
        from unittest.mock import patch as _patch

        from google.adk.agents import LlmAgent

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        def _real_specialist(_config: Any, *, name: str, **_kw: Any) -> LlmAgent:
            return LlmAgent(
                name=name,
                model=_config.model,
                instruction=_config.instruction,
                description=_config.description,
            )

        with ExitStack() as stack:
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.specialist_runtime._DEFAULT_MCP_POOL",
                    new=McpToolsetPool(),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.mcp._build_firestore_client",
                    return_value=_FakeFirestoreDb({}),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.tools.registry.function_tool_registry.resolve_default_global_tools",
                    return_value=[],
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.tools.registry.tool_registry.get_default_registry",
                    return_value=MagicMock(name="fake_registry"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.build_agent",
                    side_effect=_real_specialist,
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.utils.system_settings.harness_default_reviewer_model",
                    return_value=harness_default,
                )
            )
            # build_review_pipeline runs unpatched.
            return sr._build_specialist(
                config,
                doc_id,
                None,
                resolved_reviewer_model=sr._resolve_reviewer_model(config),
            )

    def test_ac1_no_override_no_system_doc_uses_default_reviewer_model(self) -> None:
        """AC1: no per-specialist override + no system doc → ``DEFAULT_REVIEWER_MODEL``."""
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
        from app.adk.agents.utils.review_pipeline import DEFAULT_REVIEWER_MODEL

        config = MergedAgentConfig(
            instruction="Test specialist.",
            model="gemini-2.5-pro",
            description="Test specialist.",
            default_acceptance_criteria="Must include a numbered list.",
        )
        assert config.reviewer_model is None  # sanity

        _worker, reviewer = self._build_with_real_review_pipeline(
            config, "test_spec", harness_default=None
        ).sub_agents

        assert reviewer.model == DEFAULT_REVIEWER_MODEL

    def test_ac2_no_override_system_doc_set_uses_harness_default(self) -> None:
        """AC2: no per-specialist override + system doc has a value → harness value used."""
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

        config = MergedAgentConfig(
            instruction="Test specialist.",
            model="gemini-2.5-pro",
            description="Test specialist.",
            default_acceptance_criteria="Must include a numbered list.",
        )

        _worker, reviewer = self._build_with_real_review_pipeline(
            config, "test_spec", harness_default="gemini-2.5-flash"
        ).sub_agents

        assert reviewer.model == "gemini-2.5-flash"

    def test_ac3_per_specialist_override_wins_over_harness_default(self) -> None:
        """AC3: per-specialist ``reviewer_model`` beats the harness default."""
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

        config = MergedAgentConfig(
            instruction="Test specialist.",
            model="gemini-2.5-pro",
            description="Test specialist.",
            default_acceptance_criteria="Must include a numbered list.",
            reviewer_model="gemini-2.5-pro",  # explicit override
        )

        _worker, reviewer = self._build_with_real_review_pipeline(
            config, "test_spec", harness_default="gemini-2.5-flash"
        ).sub_agents

        # Override wins.
        assert reviewer.model == "gemini-2.5-pro"

    def test_ac4_cache_propagation_changing_system_default_produces_new_hash(self) -> None:
        """AC4: changing the harness default yields a new content hash so stale
        LoopAgents are NOT served from the cache."""
        from unittest.mock import patch as _patch

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

        config = MergedAgentConfig(
            instruction="Test specialist.",
            model="gemini-2.5-pro",
            description="Test specialist.",
            default_acceptance_criteria="Must include a numbered list.",
        )

        # Resolve the hash with harness_default = "gemini-2.5-flash".
        with _patch(
            "app.adk.agents.utils.system_settings.harness_default_reviewer_model",
            return_value="gemini-2.5-flash",
        ):
            resolved_a = sr._resolve_reviewer_model(config)
            hash_a = sr._content_hash(config, resolved_reviewer_model=resolved_a)

        # Resolve the hash with harness_default = "gemini-2.5-pro".
        with _patch(
            "app.adk.agents.utils.system_settings.harness_default_reviewer_model",
            return_value="gemini-2.5-pro",
        ):
            resolved_b = sr._resolve_reviewer_model(config)
            hash_b = sr._content_hash(config, resolved_reviewer_model=resolved_b)

        # Different harness defaults → different hashes → distinct cache entries.
        assert resolved_a != resolved_b
        assert hash_a != hash_b

    def test_ac4_fresh_build_invoked_after_default_change(self) -> None:
        """AC4 (extended): changing the system default triggers a fresh _build_specialist
        call instead of reusing the stale cached LoopAgent."""
        from contextlib import ExitStack
        from unittest.mock import patch as _patch

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        config_a = MergedAgentConfig(
            instruction="Test spec.",
            model="gemini-2.5-pro",
            description="Test spec.",
            default_acceptance_criteria="Must include a numbered list.",
        )

        build_call_count = [0]

        def _counting_build(
            cfg: Any, *, name: str, account_id: Any = None, **kw: Any
        ) -> MagicMock:
            build_call_count[0] += 1
            m = MagicMock(name=f"agent_build_{build_call_count[0]}")
            m.name = name
            m.description = "Test spec."
            return m

        with ExitStack() as stack:
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.specialist_runtime._DEFAULT_MCP_POOL",
                    new=McpToolsetPool(),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.mcp._build_firestore_client",
                    return_value=_FakeFirestoreDb({}),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.tools.registry.function_tool_registry.resolve_default_global_tools",
                    return_value=[],
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.tools.registry.tool_registry.get_default_registry",
                    return_value=MagicMock(name="fake_registry"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.build_agent",
                    side_effect=_counting_build,
                )
            )
            # Also mock build_review_pipeline to avoid needing real LlmAgent internals.
            def _fake_pipeline(specialist: Any, **_kw: Any) -> MagicMock:
                m = MagicMock(name="pipeline")
                m.name = specialist.name
                m.description = specialist.description
                return m

            stack.enter_context(
                _patch(
                    "app.adk.agents.utils.review_pipeline.build_review_pipeline",
                    side_effect=_fake_pipeline,
                )
            )

            # First call with harness default A.
            with _patch(
                "app.adk.agents.utils.system_settings.harness_default_reviewer_model",
                return_value="gemini-2.5-flash",
            ):
                resolved_a = sr._resolve_reviewer_model(config_a)
                hash_a = sr._content_hash(config_a, resolved_reviewer_model=resolved_a)
                key_a = ("spec", None, hash_a)
                sr._specialists_cache.get_or_build(
                    key_a,
                    lambda: sr._build_specialist(
                        config_a, "spec", None, resolved_reviewer_model=resolved_a
                    ),
                )

            assert build_call_count[0] == 1  # fresh build triggered

            # Second call with harness default B (different value).
            with _patch(
                "app.adk.agents.utils.system_settings.harness_default_reviewer_model",
                return_value="gemini-2.5-pro",
            ):
                resolved_b = sr._resolve_reviewer_model(config_a)
                hash_b = sr._content_hash(config_a, resolved_reviewer_model=resolved_b)
                key_b = ("spec", None, hash_b)
                assert hash_a != hash_b  # different key
                sr._specialists_cache.get_or_build(
                    key_b,
                    lambda: sr._build_specialist(
                        config_a, "spec", None, resolved_reviewer_model=resolved_b
                    ),
                )

            # A NEW build was triggered — stale entry not reused.
            assert build_call_count[0] == 2

    def test_ac5_non_review_specialist_hash_unaffected_by_harness_default(self) -> None:
        """AC5: specialists without default_acceptance_criteria have ``resolved_reviewer=None``
        so their cache key / hash does NOT change when the harness default changes."""
        from unittest.mock import patch as _patch

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

        config = MergedAgentConfig(
            instruction="Plain specialist.",
            model="gemini-2.5-pro",
            description="Plain specialist.",
            # No default_acceptance_criteria — not a review specialist.
        )
        assert not (config.default_acceptance_criteria or "").strip()  # sanity

        with _patch(
            "app.adk.agents.utils.system_settings.harness_default_reviewer_model",
            return_value="gemini-2.5-flash",
        ):
            # resolve_agent computes resolved_reviewer=None for non-review specs
            # and passes None to _content_hash.
            hash_a = sr._content_hash(config, resolved_reviewer_model=None)

        with _patch(
            "app.adk.agents.utils.system_settings.harness_default_reviewer_model",
            return_value="gemini-2.5-pro",
        ):
            hash_b = sr._content_hash(config, resolved_reviewer_model=None)

        # Hash unchanged — no churn for non-review specialists.
        assert hash_a == hash_b

    def test_ac6_content_hash_deterministic(self) -> None:
        """AC6: ``_content_hash`` returns the same hex for identical inputs."""
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

        config = MergedAgentConfig(
            instruction="Test.",
            model="gemini-2.5-pro",
            description="Test.",
            default_acceptance_criteria="Must be accurate.",
        )

        h1 = sr._content_hash(config, resolved_reviewer_model="gemini-2.5-flash")
        h2 = sr._content_hash(config, resolved_reviewer_model="gemini-2.5-flash")
        assert h1 == h2

    def test_resolve_reviewer_model_resolution_chain(self) -> None:
        """Unit-test ``_resolve_reviewer_model`` independently of the build path."""
        from unittest.mock import patch as _patch

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
        from app.adk.agents.utils.review_pipeline import DEFAULT_REVIEWER_MODEL

        # Level 3: no override, no system default → code floor.
        config_none = MergedAgentConfig(
            instruction="Test.", model="gemini-2.5-pro", description="Test."
        )
        with _patch(
            "app.adk.agents.utils.system_settings.harness_default_reviewer_model",
            return_value=None,
        ):
            assert sr._resolve_reviewer_model(config_none) == DEFAULT_REVIEWER_MODEL

        # Level 2: no override, system default set → harness value.
        with _patch(
            "app.adk.agents.utils.system_settings.harness_default_reviewer_model",
            return_value="gemini-2.5-flash",
        ):
            assert sr._resolve_reviewer_model(config_none) == "gemini-2.5-flash"

        # Level 1: per-specialist override wins regardless of harness default.
        config_override = MergedAgentConfig(
            instruction="Test.",
            model="gemini-2.5-pro",
            description="Test.",
            reviewer_model="my-custom-model",
        )
        with _patch(
            "app.adk.agents.utils.system_settings.harness_default_reviewer_model",
            return_value="gemini-2.5-flash",
        ):
            assert sr._resolve_reviewer_model(config_override) == "my-custom-model"

    def test_ah92_regression_reviewer_model_set_still_threads_to_reviewer_child(
        self,
    ) -> None:
        """AH-92 regression: per-specialist ``reviewer_model`` still threads
        correctly via the new ``resolved_reviewer_model`` kwarg path."""
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

        config = MergedAgentConfig(
            instruction="News researcher.",
            model="gemini-2.5-pro",
            description="News researcher.",
            default_acceptance_criteria="Cite at least 3 sources.",
            reviewer_model="gemini-2.5-flash",
        )

        worker, reviewer = self._build_with_real_review_pipeline(
            config, "news_researcher", harness_default="gemini-2.5-pro"
        ).sub_agents

        # Per-specialist override (gemini-2.5-flash) beats harness default.
        assert (worker.model, reviewer.model) == ("gemini-2.5-pro", "gemini-2.5-flash")


# ---------------------------------------------------------------------------
# AH-90 regression: build_agent + build_review_pipeline end-to-end (no mocks)
# ---------------------------------------------------------------------------
# This class closes the test gap identified in AH-90:
#   "There is no test that builds a specialist via production build_agent and
#    then wraps it. That gap must be closed as part of the fix."
#
# The existing test_criteria_set_wraps_in_review_pipeline_renamed_to_doc_id and
# test_company_news_agent_with_criteria_wraps_in_review_pipeline both mock BOTH
# build_agent AND build_review_pipeline.  The tests below call the real
# implementations so a regression to the pre-AH-90 TypeError would surface here.
# ---------------------------------------------------------------------------


class TestBuildSpecialistRealBuildAgentWrap:
    """Non-mocked regression: real build_agent + real build_review_pipeline.

    Verifies that a MergedAgentConfig driven through the production build_agent
    path (which wraps instruction in a callable provider) can then be wrapped
    by the production build_review_pipeline without error (AH-90 fix).

    This test FAILS on main before the AH-90 fix (TypeError from
    build_review_pipeline rejecting the callable instruction) and PASSES after.
    """

    def test_real_build_agent_then_real_build_review_pipeline_succeeds(self) -> None:
        """build_agent → callable instruction → build_review_pipeline: no TypeError.

        This is the missing coverage that let the AH-90 regression slip past
        PR #759's mocked test.  The key invariant is that build_agent always
        produces a callable instruction (via _make_factory_instruction_provider),
        so any test that mocks build_agent bypasses the problematic path.
        """
        from contextlib import ExitStack
        from unittest.mock import MagicMock
        from unittest.mock import patch as _patch

        from google.adk.agents import LoopAgent

        from app.adk.agents.agent_factory.builder import build_agent
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
        from app.adk.agents.utils.review_pipeline import build_review_pipeline

        config = MergedAgentConfig(
            instruction="Real instruction for the news researcher.",
            model="gemini-2.5-pro",
            description="Company news assistant.",
            default_acceptance_criteria="Cite at least 3 sources.",
        )

        # Minimal patch surface: only infrastructure calls that would hit GCP/
        # Weave in a unit test context are stubbed. build_agent and
        # build_review_pipeline run unpatched so the callable-instruction
        # wiring is exercised end-to-end.
        _fake_cached_cfg = MagicMock()
        _fake_cached_cfg.instruction = config.instruction

        with ExitStack() as stack:
            # config_cache.get_cached_config is called inside the callable
            # instruction provider on every context invocation.  Return a
            # minimal fake so it falls back to the deploy-time instruction.
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.config_cache.get_cached_config",
                    return_value=(_fake_cached_cfg, {}, {}),
                )
            )
            # Callback and skill-loader infrastructure — irrelevant to the
            # callable-instruction wiring contract being tested.
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.weave_before_agent_callback",
                    new=MagicMock(name="weave_before"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.weave_after_agent_callback",
                    new=MagicMock(name="weave_after"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.adk_before_tool_callback",
                    new=MagicMock(name="adk_before_tool"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.adk_after_tool_callback",
                    new=MagicMock(name="adk_after_tool"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.skill_allowed_tools_before_tool_callback",
                    new=MagicMock(name="skill_filter"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.skill_spans_before_agent_callback",
                    new=MagicMock(name="sk_spans_before_agent"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.skill_spans_before_tool_callback",
                    new=MagicMock(name="sk_spans_before_tool"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.skill_spans_after_tool_callback",
                    new=MagicMock(name="sk_spans_after_tool"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder._build_skill_toolset",
                    return_value=(None, {}, False),
                )
            )

            # --- Step 1: real build_agent ---
            specialist = build_agent(
                config,
                name="real_news_researcher",
                account_id=None,
                tools=[],
                config_doc_id="real_news_researcher",
            )

        # build_agent always wraps instruction in _make_factory_instruction_provider.
        assert callable(specialist.instruction), (
            "build_agent must produce a callable instruction; "
            f"got {type(specialist.instruction).__name__}"
        )

        # --- Step 2: real build_review_pipeline — must NOT raise TypeError ---
        # This is the regression assertion: on main before the AH-90 fix,
        # the line below raises:
        #   TypeError: build_review_pipeline requires specialist.instruction to be a str;
        #              got function. Callable instructions are not supported by this factory.
        pipeline = build_review_pipeline(
            specialist=specialist,
            acceptance_criteria=config.default_acceptance_criteria,
            output_key_prefix="real_news_researcher_review",
        )

        assert isinstance(pipeline, LoopAgent), (
            "build_review_pipeline must return a LoopAgent"
        )
        worker, reviewer = pipeline.sub_agents
        assert worker.name == "real_news_researcher_worker"
        assert reviewer.name == "real_news_researcher_review_reviewer"

        # Worker's instruction must be callable (the wrapping closure).
        assert callable(worker.instruction), (
            "Worker instruction must be callable (wrapping the original provider)"
        )

        # Invoking the worker's callable must render the base instruction text
        # plus the criteria block.
        stub_ctx = MagicMock()
        stub_ctx.state = {}
        rendered = worker.instruction(stub_ctx)
        assert "Real instruction for the news researcher." in rendered
        assert "<<<CRITERIA_START>>>" in rendered
        assert "Cite at least 3 sources." in rendered
        assert "<<<CRITERIA_END>>>" in rendered
        # ADK skips template injection for callable instructions, so the raw
        # {prefix_feedback?} token must NOT leak into the prompt — the closure
        # resolves feedback from session state instead (verified below).
        assert "{real_news_researcher_review_feedback?}" not in rendered

        # With the reviewer's feedback present in state, the closure renders it
        # under the Previous Feedback header (the Generator-Critic revision loop
        # depends on this reaching the worker on iterations 2+).
        stub_ctx_with_feedback = MagicMock()
        stub_ctx_with_feedback.state = {
            "real_news_researcher_review_feedback": "Add a fourth source."
        }
        rendered_with_feedback = worker.instruction(stub_ctx_with_feedback)
        assert "Add a fourth source." in rendered_with_feedback


# ---------------------------------------------------------------------------
# Pool integration tests (AH-62 Phase 3)
# ---------------------------------------------------------------------------


class TestBuildSpecialistMcpPoolIntegration:
    """``_build_specialist`` Phase 3: pool-backed MCP toolset checkout (AH-62).

    Verifies that:
    - Pool checkout is used instead of direct Firestore get() for each server.
    - Pool hit: build_toolset_for_doc is NOT called a second time.
    - Pool miss: build_toolset_for_doc IS called once.
    - Session-state creds_hash keys pool correctly (different creds → different entry).
    - Pool checkout timeout: server is skipped gracefully.
    - Injected mcp_pool kwarg overrides _DEFAULT_MCP_POOL.
    """

    def test_pool_called_for_each_mcp_server(self) -> None:
        """build_toolset_for_doc is called once per enabled MCP server (pool miss)."""
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        config = _make_specialist_config(mcp_servers=["ga_mcp", "ads_mcp"])
        fake_db = _FakeFirestoreDb(
            {
                ("mcp_server_configs", "ga_mcp"): _enabled_mcp_doc(),
                ("mcp_server_configs", "ads_mcp"): _enabled_mcp_doc(),
            }
        )
        fresh_pool = McpToolsetPool()
        stack, mock_btf, _ = _patch_specialist_runtime_externals(fake_db=fake_db)
        with stack:
            sr._build_specialist(config, "multi_srv", "acc1", mcp_pool=fresh_pool)

        assert mock_btf.call_count == 2
        called_ids = {call.args[0] for call in mock_btf.call_args_list}
        assert called_ids == {"ga_mcp", "ads_mcp"}

    def test_pool_hit_does_not_call_build_toolset_again(self) -> None:
        """Pool hit on second call → build_toolset_for_doc NOT called again."""
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        config = _make_specialist_config(mcp_servers=["ga_mcp"])
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "ga_mcp"): _enabled_mcp_doc()}
        )
        fresh_pool = McpToolsetPool()
        stack, mock_btf, _ = _patch_specialist_runtime_externals(fake_db=fake_db)
        with stack:
            sr._build_specialist(config, "spec", "acc1", mcp_pool=fresh_pool)
            assert mock_btf.call_count == 1

            sr._build_specialist(config, "spec", "acc1", mcp_pool=fresh_pool)
            assert mock_btf.call_count == 1, (
                "build_toolset_for_doc must NOT be called on pool hit"
            )

    def test_different_creds_hash_produces_new_pool_entry(self) -> None:
        """Different session-state creds for the same server produce distinct pool entries."""
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        config = _make_specialist_config(mcp_servers=["ga_mcp"])
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "ga_mcp"): _enabled_mcp_doc()}
        )
        fresh_pool = McpToolsetPool()
        stack, mock_btf, _ = _patch_specialist_runtime_externals(fake_db=fake_db)
        with stack:
            sr._build_specialist(
                config,
                "spec",
                "acc1",
                session_state={"mcp_creds_ga_mcp": {"token": "tok1"}},
                mcp_pool=fresh_pool,
            )
            assert mock_btf.call_count == 1

            sr._build_specialist(
                config,
                "spec",
                "acc1",
                session_state={"mcp_creds_ga_mcp": {"token": "tok2"}},
                mcp_pool=fresh_pool,
            )
            assert mock_btf.call_count == 2, (
                "Different creds should produce a new pool entry"
            )

    def test_pool_checkout_timeout_skips_server(self) -> None:
        """Pool checkout timeout logs a warning and skips the server (no hard failure)."""
        import concurrent.futures
        from unittest.mock import patch as _patch

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        config = _make_specialist_config(mcp_servers=["slow_mcp"])
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "slow_mcp"): _enabled_mcp_doc()}
        )
        fresh_pool = McpToolsetPool()
        stack, _mock_btf, mock_ba = _patch_specialist_runtime_externals(fake_db=fake_db)
        with stack:
            with _patch(
                "concurrent.futures.Future.result",
                side_effect=concurrent.futures.TimeoutError,
            ):
                sr._build_specialist(config, "spec", "acc1", mcp_pool=fresh_pool)

        mock_ba.assert_called_once()

    def test_mcp_pool_kwarg_overrides_default_pool(self) -> None:
        """The mcp_pool= kwarg takes precedence over _DEFAULT_MCP_POOL."""
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        config = _make_specialist_config(mcp_servers=["ga_mcp"])
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "ga_mcp"): _enabled_mcp_doc()}
        )
        injected_pool = McpToolsetPool()
        stack, _mock_btf, _ = _patch_specialist_runtime_externals(fake_db=fake_db)
        with stack:
            sr._build_specialist(config, "spec", "acc1", mcp_pool=injected_pool)

        assert len(injected_pool._pool) == 1, (
            "Injected pool should have received the toolset entry"
        )

    def test_session_state_none_uses_empty_creds(self) -> None:
        """session_state=None and session_state={} produce identical pool keys."""
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        config = _make_specialist_config(mcp_servers=["ga_mcp"])
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "ga_mcp"): _enabled_mcp_doc()}
        )
        pool_a = McpToolsetPool()
        pool_b = McpToolsetPool()
        stack, _mock_btf, _ = _patch_specialist_runtime_externals(fake_db=fake_db)
        with stack:
            sr._build_specialist(
                config, "spec", "acc1", session_state=None, mcp_pool=pool_a
            )
            sr._build_specialist(
                config, "spec", "acc1", session_state={}, mcp_pool=pool_b
            )

        key_a = next(iter(pool_a._pool.keys()))
        key_b = next(iter(pool_b._pool.keys()))
        assert key_a == key_b, (
            "None and {} session_state must produce identical pool keys"
        )

    def test_non_json_serialisable_creds_do_not_crash_build(self) -> None:
        """AH-62 follow-up: ``mcp_creds_*`` values that are not natively
        JSON-serialisable (datetime, bytes, set, ...) must coerce via
        ``default=str`` rather than aborting the entire specialist build
        with ``TypeError``. The creds substrate is owned by upstream auth
        flows the pool does not control; defensive coercion keeps the pool
        from being a hard failure mode for chat dispatch."""
        import datetime as _dt

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        config = _make_specialist_config(mcp_servers=["ga_mcp"])
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "ga_mcp"): _enabled_mcp_doc()}
        )
        fresh_pool = McpToolsetPool()
        stack, _mock_btf, _ = _patch_specialist_runtime_externals(fake_db=fake_db)

        nasty_creds = {
            "expires_at": _dt.datetime(2026, 1, 1, 0, 0, 0),
            "binary_blob": b"\x00\x01\x02",
            "scopes": {"read", "write"},  # set — not JSON-serialisable
        }
        with stack:
            # Must not raise.
            sr._build_specialist(
                config,
                "spec",
                "acc1",
                session_state={"mcp_creds_ga_mcp": nasty_creds},
                mcp_pool=fresh_pool,
            )

        assert len(fresh_pool._pool) == 1, (
            "Build aborted before reaching the pool — defensive coercion regressed."
        )


# ---------------------------------------------------------------------------
# TestExecutorSingleton — AH-77 Item F
# ---------------------------------------------------------------------------


class TestExecutorSingleton:
    """The MCP pool checkout path reuses the process-wide singleton executor."""

    def test_get_pool_checkout_executor_returns_singleton(self) -> None:
        """get_pool_checkout_executor() always returns the same instance."""
        from app.adk.agents.agent_factory._executors import get_pool_checkout_executor

        e1 = get_pool_checkout_executor()
        e2 = get_pool_checkout_executor()
        assert e1 is e2, "Expected singleton — got two distinct executor instances"

    def test_specialist_runtime_uses_singleton_executor(self) -> None:
        """_build_specialist submits MCP pool checkout to the singleton, not a fresh executor.

        We monkeypatch get_pool_checkout_executor to return a recording mock and
        verify its .submit() is called at least once during a specialist build
        that includes an MCP server.
        """
        import concurrent.futures

        import app.adk.agents.agent_factory.specialist_runtime as sr

        # Config with one MCP server.
        config = _make_specialist_config(mcp_servers=["ga_mcp"])

        # Fake Firestore DB that returns an enabled MCP server doc.
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "ga_mcp"): _enabled_mcp_doc()}
        )

        # A recording executor that wraps a real ThreadPoolExecutor so that
        # futures still behave correctly.
        real_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        recording_executor = MagicMock(wraps=real_executor)

        stack, _, _ = _patch_specialist_runtime_externals(
            fake_db=fake_db, mock_resolver=True
        )
        with (
            stack,
            patch(
                "app.adk.agents.agent_factory.specialist_runtime.get_pool_checkout_executor",
                return_value=recording_executor,
            ),
        ):
            sr._build_specialist(
                config,
                "ga_specialist",
                "acc1",
                session_state={},
            )

        real_executor.shutdown(wait=False)
        assert recording_executor.submit.called, (
            "get_pool_checkout_executor().submit() was not called — "
            "_build_specialist is not using the singleton executor"
        )


# ---------------------------------------------------------------------------
# TestSpecialistRuntimeCodeExecutor — AH-27 AC #2
# ---------------------------------------------------------------------------


class TestSpecialistRuntimeCodeExecutor:
    """AH-27 AC #2: runtime resolver materialises BuiltInCodeExecutor when
    code_execution_enabled=True.

    Exercises the _build_specialist → build_agent → _build_code_executor chain on
    the runtime resolver's actual entry point, including the LoopAgent wrap that
    GA's default_acceptance_criteria triggers in _build_specialist.

    The existing test_factory.py::TestCodeExecution tests build_agent directly
    (without the LoopAgent wrap) and is necessary but not sufficient for
    PRD AC #2: "The runtime-resolved specialist has code_executor set to a
    BuiltInCodeExecutor when code_execution_enabled=true." This class closes
    the gap at the resolver layer.
    """

    def _build_infra_stack(self, config: Any) -> Any:
        """Return an ExitStack with all infrastructure patches applied.

        Patches every external dependency of ``_build_specialist`` / ``build_agent``
        that would hit GCP, Weave, or MCP in a unit-test context.  Critically,
        ``build_agent`` and ``build_review_pipeline`` are NOT patched — the real
        implementations run so that ``_build_code_executor`` wiring is exercised
        end-to-end.
        """
        from contextlib import ExitStack
        from unittest.mock import MagicMock
        from unittest.mock import patch as _patch

        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        fake_cached_cfg = MagicMock()
        fake_cached_cfg.instruction = config.instruction

        # Cannot use _patch_specialist_runtime_externals: that helper always
        # mocks build_agent, which would bypass _build_code_executor entirely.
        # We need the real build_agent so the code_executor wiring is exercised.
        stack = ExitStack()
        try:
            # 1. Fresh MCP pool per test for isolation.
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.specialist_runtime._DEFAULT_MCP_POOL",
                    new=McpToolsetPool(),
                )
            )
            # 2. Empty Firestore — no MCP servers needed for these tests.
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.mcp._build_firestore_client",
                    return_value=_FakeFirestoreDb({}),
                )
            )
            # 3 & 4. Tool registry — empty roster, no default globals.
            stack.enter_context(
                _patch(
                    "app.adk.tools.registry.function_tool_registry.resolve_default_global_tools",
                    return_value=[],
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.tools.registry.tool_registry.get_default_registry",
                    return_value=MagicMock(name="fake_registry"),
                )
            )
            # 5. config_cache — return minimal fake so the callable instruction
            #    provider falls back to the deploy-time instruction string.
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.config_cache.get_cached_config",
                    return_value=(fake_cached_cfg, {}, {}),
                )
            )
            # 6-13. Callbacks - irrelevant to code_executor wiring.
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.weave_before_agent_callback",
                    new=MagicMock(name="weave_before"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.weave_after_agent_callback",
                    new=MagicMock(name="weave_after"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.adk_before_tool_callback",
                    new=MagicMock(name="adk_before_tool"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.adk_after_tool_callback",
                    new=MagicMock(name="adk_after_tool"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.skill_allowed_tools_before_tool_callback",
                    new=MagicMock(name="skill_filter"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.skill_spans_before_agent_callback",
                    new=MagicMock(name="sk_spans_before_agent"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.skill_spans_before_tool_callback",
                    new=MagicMock(name="sk_spans_before_tool"),
                )
            )
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder.skill_spans_after_tool_callback",
                    new=MagicMock(name="sk_spans_after_tool"),
                )
            )
            # 14. Skill toolset — no skills attached.
            stack.enter_context(
                _patch(
                    "app.adk.agents.agent_factory.builder._build_skill_toolset",
                    return_value=(None, {}, False),
                )
            )
            return stack
        except Exception:
            stack.close()
            raise

    def test_code_execution_enabled_no_criteria_returns_llm_agent_with_executor(
        self,
    ) -> None:
        """(a) code_execution_enabled=True, no criteria → raw LlmAgent with BuiltInCodeExecutor."""
        from google.adk.agents import LlmAgent
        from google.adk.code_executors import BuiltInCodeExecutor

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

        config = MergedAgentConfig(
            instruction="You are a GA specialist. Use code execution for ALL numerical analysis.",
            model="gemini-2.0-flash",
            description="GA specialist",
            code_execution_enabled=True,
            mcp_servers=[],
        )

        with self._build_infra_stack(config):
            result = sr._build_specialist(
                config,
                "google_analytics_specialist",
                account_id=None,
            )

        assert isinstance(result, LlmAgent), (
            f"Expected LlmAgent (no criteria → no wrap); got {type(result).__name__}"
        )
        assert isinstance(result.code_executor, BuiltInCodeExecutor), (
            f"Expected BuiltInCodeExecutor; got {type(result.code_executor).__name__}"
        )

    def test_code_execution_enabled_with_criteria_loop_agent_worker_has_executor(
        self,
    ) -> None:
        """(b) code_execution_enabled=True + default_acceptance_criteria → LoopAgent.

        The inner worker (first sub_agent) must preserve the BuiltInCodeExecutor
        that build_agent sets on the specialist before build_review_pipeline wraps it.
        """
        from google.adk.agents import LlmAgent, LoopAgent
        from google.adk.code_executors import BuiltInCodeExecutor

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

        config = MergedAgentConfig(
            instruction="You are a GA specialist. Use code execution for ALL numerical analysis.",
            model="gemini-2.0-flash",
            description="GA specialist",
            code_execution_enabled=True,
            mcp_servers=[],
            default_acceptance_criteria="Show the executed formula so the reviewer can verify the calculation.",
        )

        with self._build_infra_stack(config):
            result = sr._build_specialist(
                config,
                "google_analytics_specialist",
                account_id=None,
            )

        assert isinstance(result, LoopAgent), (
            f"Expected LoopAgent (criteria set → review-pipeline wrap); got {type(result).__name__}"
        )
        assert result.name == "google_analytics_specialist", (
            f"LoopAgent must be renamed to doc_id by _build_specialist; got {result.name!r}"
        )

        worker = result.sub_agents[0]
        assert isinstance(worker, LlmAgent), (
            f"First sub_agent must be the specialist worker LlmAgent; got {type(worker).__name__}"
        )
        assert worker.name == "google_analytics_specialist_worker", (
            f"Worker must be named '<doc_id>_worker'; got {worker.name!r}"
        )
        assert isinstance(worker.code_executor, BuiltInCodeExecutor), (
            "Worker must inherit BuiltInCodeExecutor from the specialist — "
            f"build_review_pipeline propagates all LlmAgent fields; got {type(worker.code_executor).__name__}"
        )

    def test_code_execution_disabled_returns_llm_agent_without_executor(
        self,
    ) -> None:
        """(c) code_execution_enabled=False → raw LlmAgent with code_executor=None."""
        from google.adk.agents import LlmAgent

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

        config = MergedAgentConfig(
            instruction="You are a GA specialist.",
            model="gemini-2.0-flash",
            description="GA specialist",
            code_execution_enabled=False,
            mcp_servers=[],
        )

        with self._build_infra_stack(config):
            result = sr._build_specialist(
                config,
                "google_analytics_specialist",
                account_id=None,
            )

        assert isinstance(result, LlmAgent), (
            f"Expected LlmAgent (no criteria → no wrap); got {type(result).__name__}"
        )
        assert result.code_executor is None, (
            f"code_execution_enabled=False must produce code_executor=None; "
            f"got {result.code_executor!r}"
        )


# ---------------------------------------------------------------------------
# TestGaOauthCallbackWiring — AH-28
# ---------------------------------------------------------------------------


class TestGaOauthCallbackWiring:
    """``_build_specialist`` must attach ``ga_oauth_after_tool_callback`` to any
    specialist whose MCP roster includes a server with ``auth_type=="ga_oauth"``.

    Specialists with no ``ga_oauth`` server must not receive the callback.
    Two servers with ``auth_type=="ga_oauth"`` produce exactly one callback
    entry (de-duped by the boolean flag).
    """

    def _ga_oauth_mcp_doc(self) -> dict[str, Any]:
        """MCP server doc with auth_type=ga_oauth (enabled)."""
        return {"enabled": True, "auth_type": "ga_oauth"}

    def _non_oauth_mcp_doc(self) -> dict[str, Any]:
        """MCP server doc without ga_oauth (e.g. a public server)."""
        return {"enabled": True, "auth_type": None}

    def test_ga_oauth_server_attaches_callback(self) -> None:
        """AC-1: specialist with a ga_oauth MCP server gets the callback."""
        import app.adk.agents.agent_factory.specialist_runtime as sr
        from app.adk.security.hooks import ga_oauth_after_tool_callback

        config = _make_specialist_config(mcp_servers=["ga_mcp"])
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "ga_mcp"): self._ga_oauth_mcp_doc()}
        )

        captured_kwargs: dict = {}

        def _capture_build_agent(cfg, *, name, tools=None, **kw):  # type: ignore[no-untyped-def]
            captured_kwargs.update(kw)
            return MagicMock(name=f"llmagent_{name}", tools=tools or [])

        stack, _, _ = _patch_specialist_runtime_externals(fake_db=fake_db)
        with (
            stack,
            patch(
                "app.adk.agents.agent_factory.builder.build_agent",
                side_effect=_capture_build_agent,
            ),
        ):
            sr._build_specialist(config, "ga_specialist", "acc1", session_state={})

        callbacks = captured_kwargs.get("additional_after_tool_callbacks") or []
        assert ga_oauth_after_tool_callback in callbacks, (
            "ga_oauth_after_tool_callback not in additional_after_tool_callbacks"
        )

    def test_non_ga_oauth_server_does_not_attach_callback(self) -> None:
        """AC-2: specialist with no ga_oauth server must not get the callback."""
        import app.adk.agents.agent_factory.specialist_runtime as sr
        from app.adk.security.hooks import ga_oauth_after_tool_callback

        config = _make_specialist_config(mcp_servers=["public_mcp"])
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "public_mcp"): self._non_oauth_mcp_doc()}
        )

        captured_kwargs: dict = {}

        def _capture_build_agent(cfg, *, name, tools=None, **kw):  # type: ignore[no-untyped-def]
            captured_kwargs.update(kw)
            return MagicMock(name=f"llmagent_{name}", tools=tools or [])

        stack, _, _ = _patch_specialist_runtime_externals(fake_db=fake_db)
        with (
            stack,
            patch(
                "app.adk.agents.agent_factory.builder.build_agent",
                side_effect=_capture_build_agent,
            ),
        ):
            sr._build_specialist(config, "public_specialist", "acc1", session_state={})

        callbacks = captured_kwargs.get("additional_after_tool_callbacks") or []
        assert ga_oauth_after_tool_callback not in callbacks, (
            "ga_oauth_after_tool_callback should NOT be attached for non-ga_oauth specialist"
        )

    def test_no_mcp_servers_does_not_attach_callback(self) -> None:
        """AC-2: specialist with no MCP servers must not get the callback."""
        import app.adk.agents.agent_factory.specialist_runtime as sr
        from app.adk.security.hooks import ga_oauth_after_tool_callback

        config = _make_specialist_config(mcp_servers=[])
        fake_db = _FakeFirestoreDb({})

        captured_kwargs: dict = {}

        def _capture_build_agent(cfg, *, name, tools=None, **kw):  # type: ignore[no-untyped-def]
            captured_kwargs.update(kw)
            return MagicMock(name=f"llmagent_{name}", tools=tools or [])

        stack, _, _ = _patch_specialist_runtime_externals(fake_db=fake_db)
        with (
            stack,
            patch(
                "app.adk.agents.agent_factory.builder.build_agent",
                side_effect=_capture_build_agent,
            ),
        ):
            sr._build_specialist(config, "no_mcp_specialist", "acc1", session_state={})

        callbacks = captured_kwargs.get("additional_after_tool_callbacks") or []
        assert ga_oauth_after_tool_callback not in callbacks

    def test_two_ga_oauth_servers_produce_one_callback_entry(self) -> None:
        """AC-4: two MCP servers both with ga_oauth produce exactly one callback entry."""
        import app.adk.agents.agent_factory.specialist_runtime as sr
        from app.adk.security.hooks import ga_oauth_after_tool_callback

        config = _make_specialist_config(mcp_servers=["ga_mcp_1", "ga_mcp_2"])
        fake_db = _FakeFirestoreDb(
            {
                ("mcp_server_configs", "ga_mcp_1"): self._ga_oauth_mcp_doc(),
                ("mcp_server_configs", "ga_mcp_2"): self._ga_oauth_mcp_doc(),
            }
        )

        captured_kwargs: dict = {}

        def _capture_build_agent(cfg, *, name, tools=None, **kw):  # type: ignore[no-untyped-def]
            captured_kwargs.update(kw)
            return MagicMock(name=f"llmagent_{name}", tools=tools or [])

        stack, _, _ = _patch_specialist_runtime_externals(fake_db=fake_db)
        with (
            stack,
            patch(
                "app.adk.agents.agent_factory.builder.build_agent",
                side_effect=_capture_build_agent,
            ),
        ):
            sr._build_specialist(config, "dual_ga_specialist", "acc1", session_state={})

        callbacks = captured_kwargs.get("additional_after_tool_callbacks") or []
        count = callbacks.count(ga_oauth_after_tool_callback)
        assert count == 1, (
            f"Expected exactly 1 ga_oauth_after_tool_callback entry, got {count}"
        )

    def test_auth_type_read_failure_is_nonfatal(self) -> None:
        """AC: Firestore read failure during auth_type check is non-fatal; specialist still builds."""
        import app.adk.agents.agent_factory.specialist_runtime as sr
        from app.adk.security.hooks import ga_oauth_after_tool_callback

        config = _make_specialist_config(mcp_servers=["ga_mcp"])

        # DB that raises on the auth_type pre-check read
        class _ErrorDb:
            def collection(self, name: str) -> Any:
                return _ErrorCollection()

        class _ErrorCollection:
            def document(self, doc_id: str) -> Any:
                return _ErrorDocRef()

        class _ErrorDocRef:
            def get(self) -> Any:
                raise RuntimeError("Firestore unavailable")

        captured_kwargs: dict = {}

        def _capture_build_agent(cfg, *, name, tools=None, **kw):  # type: ignore[no-untyped-def]
            captured_kwargs.update(kw)
            return MagicMock(name=f"llmagent_{name}", tools=tools or [])

        # Use the error DB; _build_firestore_client is patched to return it
        stack, _, _ = _patch_specialist_runtime_externals(
            fake_db=_FakeFirestoreDb({})  # toolset fetch uses the standard fake
        )
        with (
            stack,
            patch(
                "app.adk.agents.agent_factory.mcp._build_firestore_client",
                return_value=_ErrorDb(),
            ),
            patch(
                "app.adk.agents.agent_factory.builder.build_agent",
                side_effect=_capture_build_agent,
            ),
        ):
            # Should not raise even though the auth_type Firestore read fails
            sr._build_specialist(config, "ga_specialist", "acc1", session_state={})

        # The specialist still built successfully; callback not attached (fail-safe)
        callbacks = captured_kwargs.get("additional_after_tool_callbacks") or []
        assert ga_oauth_after_tool_callback not in callbacks


# ---------------------------------------------------------------------------
# TestUserBuiltGaAgent — AH-95: user-built custom agent with GA MCP tools
# ---------------------------------------------------------------------------


class TestUserBuiltGaAgent:
    """AH-95: Verifies that a custom agent created via the AgentToolPicker
    (with ``tool_ids`` set but ``mcp_servers=[]``) resolves correctly.

    Covers:
    * Option A fix — ``_build_specialist`` derives the server set from
      ``tool_ids`` prefixes when ``mcp_servers`` is falsy (AH-95 Task 3).
    * ``McpToolsetPool`` keying isolation (AH-95 Task 5).
    * Review-loop opt-in via ``default_acceptance_criteria`` (AH-95 Task 6).

    Sub-agent attachment tests (Task 4 / AH-82 delegation gate) live in
    ``test_sub_agent_attacher.py::TestUserBuiltGaAgentAttach`` where the
    required ``attach_account_specialists`` helpers already exist.
    """

    # -----------------------------------------------------------------
    # Task 3: resolver derives mcp_servers from tool_ids (Option A)
    # -----------------------------------------------------------------

    def test_custom_agent_derives_mcp_server_from_tool_ids(self) -> None:
        """A custom agent with ``mcp_servers=[]`` and ``tool_ids`` containing
        GA tool IDs builds an ``LlmAgent`` with a single ``McpToolset`` for
        ``google_analytics_mcp`` filtered to the selected tool.

        This validates the ~5 LoC Option A fix in ``_build_specialist``:
        when ``config.mcp_servers`` is falsy and ``config.tool_ids`` is
        non-None, the server set is derived from the ``tool_ids`` prefixes.
        """
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        config = _make_specialist_config(
            mcp_servers=[],
            tool_ids=["google_analytics_mcp.run_report_mt"],
        )
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "google_analytics_mcp"): _enabled_mcp_doc()}
        )
        fresh_pool = McpToolsetPool()
        stack, mock_btf, mock_ba = _patch_specialist_runtime_externals(fake_db=fake_db)
        with stack:
            sr._build_specialist(
                config, "custom_ga_agent", "acc1", mcp_pool=fresh_pool
            )

        # build_toolset_for_doc must be called for google_analytics_mcp
        assert mock_btf.call_count == 1, (
            f"Expected exactly one toolset build for google_analytics_mcp; "
            f"got {mock_btf.call_count}"
        )
        called_server_id = mock_btf.call_args.args[0]
        assert called_server_id == "google_analytics_mcp"

        # The toolset must pass the per-server allowlist
        assert mock_btf.call_args.kwargs.get("allowed_tool_names") == [
            "run_report_mt"
        ], (
            f"allowed_tool_names must be ['run_report_mt']; "
            f"got {mock_btf.call_args.kwargs!r}"
        )

        # build_agent must have been called (specialist was constructed)
        mock_ba.assert_called_once()

    def test_custom_agent_with_multiple_ga_tools_derives_single_server(self) -> None:
        """Multiple tool_ids from the same server still produce one toolset."""
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        config = _make_specialist_config(
            mcp_servers=[],
            tool_ids=[
                "google_analytics_mcp.run_report_mt",
                "google_analytics_mcp.run_realtime_report_mt",
                "function.create_visualization",
            ],
        )
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "google_analytics_mcp"): _enabled_mcp_doc()}
        )
        fresh_pool = McpToolsetPool()
        stack, mock_btf, _mock_ba = _patch_specialist_runtime_externals(fake_db=fake_db)
        with stack:
            sr._build_specialist(
                config, "custom_ga_agent", "acc1", mcp_pool=fresh_pool
            )

        # Only one server — google_analytics_mcp
        assert mock_btf.call_count == 1
        assert mock_btf.call_args.args[0] == "google_analytics_mcp"

        # Both GA tools in the allowlist
        allowed = mock_btf.call_args.kwargs.get("allowed_tool_names")
        assert set(allowed) == {"run_report_mt", "run_realtime_report_mt"}, (
            f"Both GA tools must be in the allowlist; got {allowed!r}"
        )

    def test_real_ga_seed_tool_ids_wire_the_four_live_mt_tools(self) -> None:
        """AH-149 regression proof: building the GA specialist from the REAL
        seed ``_GA_MCP_TOOL_IDS`` wires the ``google_analytics_mcp`` toolset with
        a ``tool_filter`` equal to the four live ``_mt`` tool names the deployed
        server actually serves. The pre-fix seed used catalogue names that matched
        no live tool, so the filter resolved to an empty roster (zero GA tools).
        """
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool
        from app.adk.agents.scripts.migrate_ga_specialist_to_firestore import (
            _GA_MCP_TOOL_IDS,
        )

        config = _make_specialist_config(
            mcp_servers=["google_analytics_mcp"],
            tool_ids=_GA_MCP_TOOL_IDS,
        )
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "google_analytics_mcp"): _enabled_mcp_doc()}
        )
        fresh_pool = McpToolsetPool()
        stack, mock_btf, _ = _patch_specialist_runtime_externals(fake_db=fake_db)
        with stack:
            sr._build_specialist(
                config, "google_analytics_specialist", None, mcp_pool=fresh_pool
            )

        ga_calls = [
            c
            for c in mock_btf.call_args_list
            if c.args and c.args[0] == "google_analytics_mcp"
        ]
        assert len(ga_calls) == 1, (
            f"expected one google_analytics_mcp toolset build; got {len(ga_calls)}"
        )
        allowed = ga_calls[0].kwargs.get("allowed_tool_names")
        assert allowed is not None and set(allowed) == {
            "get_account_summaries_mt",
            "get_property_details_mt",
            "run_report_mt",
            "run_realtime_report_mt",
        }, (
            f"GA toolset must be filtered to the 4 live _mt tools; got {allowed!r}"
        )

    def test_legacy_mcp_servers_set_is_not_affected_by_option_a(self) -> None:
        """When ``mcp_servers`` is explicitly set (e.g. the seeded global GA
        specialist), Option A is not triggered — the existing server list is
        used verbatim, preserving the pre-AH-95 behaviour.
        """
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        config = _make_specialist_config(
            mcp_servers=["google_analytics_mcp"],
            tool_ids=["google_analytics_mcp.run_report_mt"],
        )
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "google_analytics_mcp"): _enabled_mcp_doc()}
        )
        fresh_pool = McpToolsetPool()
        stack, mock_btf, _ = _patch_specialist_runtime_externals(fake_db=fake_db)
        with stack:
            sr._build_specialist(
                config, "google_analytics_specialist", "acc1", mcp_pool=fresh_pool
            )

        # Exactly one call — same as before; no duplication
        assert mock_btf.call_count == 1
        assert mock_btf.call_args.args[0] == "google_analytics_mcp"

    def test_tool_ids_none_with_empty_mcp_servers_builds_no_toolsets(self) -> None:
        """``tool_ids=None`` with ``mcp_servers=[]`` must not trigger the
        Option A derivation — ``None`` signals legacy "every tool" semantics
        which requires ``mcp_servers`` to be set explicitly.
        """
        from app.adk.agents.agent_factory import specialist_runtime as sr

        config = _make_specialist_config(mcp_servers=[], tool_ids=None)
        stack, mock_btf, mock_ba = _patch_specialist_runtime_externals()
        with stack:
            sr._build_specialist(config, "no_server_agent", "acc1")

        assert mock_btf.call_count == 0, (
            "tool_ids=None with no mcp_servers must produce zero toolset builds"
        )
        mock_ba.assert_called_once()  # agent itself is still built

    def test_tool_ids_empty_list_with_empty_mcp_servers_builds_no_toolsets(
        self,
    ) -> None:
        """``tool_ids=[]`` with ``mcp_servers=[]`` must trigger Option A but
        produce an empty ``effective_mcp_servers`` (``per_server_allowed`` is
        ``{}`` — non-None but empty — so ``list({}.keys()) == []``).

        Explicitly tests the AH-95 code path for the empty-allowlist case:
        ``per_server_allowed is not None`` but ``per_server_allowed.keys()``
        is empty, so no toolset build is attempted.
        """
        from app.adk.agents.agent_factory import specialist_runtime as sr

        config = _make_specialist_config(mcp_servers=[], tool_ids=[])
        stack, mock_btf, mock_ba = _patch_specialist_runtime_externals()
        with stack:
            sr._build_specialist(config, "empty_tools_agent", "acc1")

        assert mock_btf.call_count == 0, (
            "tool_ids=[] must derive empty effective_mcp_servers and build "
            "no toolsets"
        )
        mock_ba.assert_called_once()  # agent is still built (with zero tools)

    # -----------------------------------------------------------------
    # Task 5: McpToolsetPool keying — OAuth isolation
    # -----------------------------------------------------------------

    def test_different_ga_creds_produce_distinct_pool_entries_for_custom_agent(
        self,
    ) -> None:
        """Two sessions with different ``ga_credentials`` for the same
        custom GA agent produce distinct pool entries (no cross-account token
        reuse).

        Pool key: ``(server_id, account_id, sha256(creds_json))``.
        Mirrors the AH-29 isolation test for the global GA specialist.
        """
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        config = _make_specialist_config(
            mcp_servers=[],
            tool_ids=["google_analytics_mcp.run_report_mt"],
        )
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "google_analytics_mcp"): _enabled_mcp_doc()}
        )
        fresh_pool = McpToolsetPool()
        stack, _mock_btf, _ = _patch_specialist_runtime_externals(fake_db=fake_db)

        cred_key = "mcp_creds_google_analytics_mcp"
        with stack:
            sr._build_specialist(
                config,
                "custom_ga_agent",
                "acc1",
                session_state={cred_key: {"access_token": "tok_account_1"}},
                mcp_pool=fresh_pool,
            )
            sr._build_specialist(
                config,
                "custom_ga_agent",
                "acc1",
                session_state={cred_key: {"access_token": "tok_account_2"}},
                mcp_pool=fresh_pool,
            )

        assert len(fresh_pool._pool) == 2, (
            f"Different creds must produce distinct pool entries; "
            f"got {len(fresh_pool._pool)} entry/entries"
        )

    def test_different_account_ids_produce_distinct_pool_entries(self) -> None:
        """Two different accounts with the same GA creds payload still get
        separate pool entries because account_id is part of the pool key.
        """
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        config = _make_specialist_config(
            mcp_servers=[],
            tool_ids=["google_analytics_mcp.run_report_mt"],
        )
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "google_analytics_mcp"): _enabled_mcp_doc()}
        )
        fresh_pool = McpToolsetPool()
        stack, _mock_btf, _ = _patch_specialist_runtime_externals(fake_db=fake_db)

        shared_creds = {"access_token": "shared_tok"}
        cred_key = "mcp_creds_google_analytics_mcp"
        with stack:
            sr._build_specialist(
                config,
                "custom_ga_agent",
                "acc_alpha",
                session_state={cred_key: shared_creds},
                mcp_pool=fresh_pool,
            )
            sr._build_specialist(
                config,
                "custom_ga_agent",
                "acc_beta",
                session_state={cred_key: shared_creds},
                mcp_pool=fresh_pool,
            )

        assert len(fresh_pool._pool) == 2, (
            f"Different account_ids must produce distinct pool entries even with "
            f"identical creds; got {len(fresh_pool._pool)} entry/entries"
        )

    def test_four_combinations_produce_four_distinct_pool_entries(self) -> None:
        """2 account_ids x 2 creds payloads -> 4 distinct pool entries."""
        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        config = _make_specialist_config(
            mcp_servers=[],
            tool_ids=["google_analytics_mcp.run_report_mt"],
        )
        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "google_analytics_mcp"): _enabled_mcp_doc()}
        )
        fresh_pool = McpToolsetPool()
        stack, _mock_btf, _ = _patch_specialist_runtime_externals(fake_db=fake_db)

        cred_key = "mcp_creds_google_analytics_mcp"
        combos = [
            ("acc_alpha", "tok_1"),
            ("acc_alpha", "tok_2"),
            ("acc_beta", "tok_1"),
            ("acc_beta", "tok_2"),
        ]
        with stack:
            for account_id, token in combos:
                sr._build_specialist(
                    config,
                    "custom_ga_agent",
                    account_id,
                    session_state={cred_key: {"access_token": token}},
                    mcp_pool=fresh_pool,
                )

        assert len(fresh_pool._pool) == 4, (
            f"2 accounts x 2 creds must yield 4 distinct pool entries; "
            f"got {len(fresh_pool._pool)}"
        )

    # -----------------------------------------------------------------
    # Task 6: review loop engages when default_acceptance_criteria is set
    # -----------------------------------------------------------------

    def test_review_loop_wraps_custom_ga_agent_when_criteria_set(self) -> None:
        """When ``default_acceptance_criteria`` is set on a custom GA agent
        (with ``mcp_servers=[]``, ``tool_ids`` set), ``_build_specialist``
        calls ``build_review_pipeline`` and renames the returned pipeline to
        the doc_id so ``transfer_to_agent`` resolves.

        Mirrors the pattern from ``TestSpecialistRuntimeReviewWrap`` —
        ``build_review_pipeline`` is mocked so no real ``LoopAgent``
        construction is required, keeping the test isolated from ADK
        internals.
        """
        from contextlib import ExitStack
        from unittest.mock import patch as _patch

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        custom_id = "custom_ga_with_review"
        config = MergedAgentConfig(
            instruction="You are a custom GA agent with review.",
            model="gemini-2.5-flash",
            description="Custom GA + review loop",
            mcp_servers=[],
            tool_ids=["google_analytics_mcp.run_report_mt"],
            default_acceptance_criteria="Must include at least one numeric figure.",
            ken_e_sub_agent=True,
        )

        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "google_analytics_mcp"): _enabled_mcp_doc()}
        )
        fresh_pool = McpToolsetPool()
        externals_stack, _mock_btf, _mock_ba = _patch_specialist_runtime_externals(
            fake_db=fake_db
        )

        # Fake LoopAgent pipeline returned by build_review_pipeline.
        fake_pipeline = MagicMock(name="fake_loop_agent")
        fake_pipeline.name = f"{custom_id}_review_loop"  # pre-rename default
        fake_pipeline.description = config.description

        with ExitStack() as outer:
            outer.enter_context(externals_stack)
            mock_build_pipeline = outer.enter_context(
                _patch(
                    "app.adk.agents.utils.review_pipeline.build_review_pipeline",
                    return_value=fake_pipeline,
                )
            )
            result = sr._build_specialist(
                config, custom_id, "acc1", mcp_pool=fresh_pool
            )

        # build_review_pipeline was called with the criteria.
        mock_build_pipeline.assert_called_once()
        call_kwargs = mock_build_pipeline.call_args.kwargs
        assert "Must include at least one numeric figure" in call_kwargs.get(
            "acceptance_criteria", ""
        )
        # Returned agent IS the pipeline, renamed to the doc_id.
        assert result is fake_pipeline
        assert result.name == custom_id, (
            f"Review pipeline must be renamed to the doc_id '{custom_id}'; "
            f"got {result.name!r}"
        )

    def test_no_review_loop_when_criteria_absent_for_custom_ga_agent(self) -> None:
        """When ``default_acceptance_criteria`` is absent, ``_build_specialist``
        does NOT call ``build_review_pipeline`` — a bare ``LlmAgent`` mock is
        returned.
        """
        from unittest.mock import patch as _patch

        from app.adk.agents.agent_factory import specialist_runtime as sr
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig
        from app.adk.agents.agent_factory.mcp_pool import McpToolsetPool

        custom_id = "custom_ga_no_review"
        config = MergedAgentConfig(
            instruction="You are a custom GA agent without review.",
            model="gemini-2.5-flash",
            description="Custom GA, no review loop",
            mcp_servers=[],
            tool_ids=["google_analytics_mcp.run_report_mt"],
            ken_e_sub_agent=True,
            # default_acceptance_criteria not set
        )

        fake_db = _FakeFirestoreDb(
            {("mcp_server_configs", "google_analytics_mcp"): _enabled_mcp_doc()}
        )
        fresh_pool = McpToolsetPool()
        stack, _mock_btf, mock_ba = _patch_specialist_runtime_externals(
            fake_db=fake_db
        )
        with stack:
            with _patch(
                "app.adk.agents.utils.review_pipeline.build_review_pipeline"
            ) as mock_build_pipeline:
                result = sr._build_specialist(
                    config, custom_id, "acc1", mcp_pool=fresh_pool
                )

        # Review pipeline was NOT constructed.
        mock_build_pipeline.assert_not_called()
        # Returned agent is the raw build_agent mock (LlmAgent stand-in).
        mock_ba.assert_called_once()
        assert result._extract_mock_name() == f"llmagent_{custom_id}"
