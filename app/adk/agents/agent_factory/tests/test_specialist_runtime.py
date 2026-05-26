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
) -> Any:
    """Return a minimal MergedAgentConfig-like object suitable for tests."""
    from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

    return MergedAgentConfig(
        instruction=instruction,
        model=model,
        description="Test specialist",
        visible_in_frontend=visible_in_frontend,
    )


def _make_llm_agent(name: str = "test_specialist") -> MagicMock:
    """Return a MagicMock that quacks like an LlmAgent."""
    agent = MagicMock()
    agent.name = name
    agent.description = "Test specialist"
    return agent


@pytest.fixture(autouse=True)
def clear_specialists_cache() -> Any:
    """Each test starts with a clean agent cache, config cache, and block cache."""
    from app.adk.agents.agent_factory import specialist_runtime
    from app.adk.agents.utils.config_cache import clear_config_cache

    specialist_runtime._specialists_cache.clear()
    specialist_runtime._clear_block_cache_for_tests()
    clear_config_cache()
    yield
    specialist_runtime._specialists_cache.clear()
    specialist_runtime._clear_block_cache_for_tests()
    clear_config_cache()


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
# TestRun
# ---------------------------------------------------------------------------


class TestRun:
    def test_single_pass_when_no_criteria(self) -> None:
        from app.adk.agents.agent_factory import specialist_runtime

        fake_agent = _make_llm_agent()

        # run() imports invoke_agent_with_retry lazily from agent_retry; patch it there.
        import app.adk.agents.utils.agent_retry as agent_retry_mod

        with (
            patch.object(specialist_runtime, "resolve_agent", return_value=fake_agent),
            patch.object(
                agent_retry_mod,
                "invoke_agent_with_retry",
                return_value="single pass result",
            ) as mock_retry,
        ):
            result = specialist_runtime.run("spe_1", "do something")

        assert result == "single pass result"
        mock_retry.assert_called_once()

    def test_review_pipeline_when_criteria_present(self) -> None:
        from app.adk.agents.agent_factory import specialist_runtime

        fake_agent = _make_llm_agent()
        fake_pipeline = MagicMock()
        fake_outcome = {"approved": True, "result": "pipeline result"}
        fake_final_state = {"spe_1_review_outcome": fake_outcome}

        with patch.object(specialist_runtime, "resolve_agent", return_value=fake_agent):
            with patch(
                "app.adk.agents.utils.review_pipeline.build_review_pipeline",
                return_value=fake_pipeline,
            ):
                with patch(
                    "app.adk.agents.utils.supervisor_utils.invoke_pipeline",
                    return_value=("text", fake_final_state, []),
                ):
                    with patch(
                        "app.adk.agents.utils.review_pipeline._check_hallucinated_approval"
                    ):
                        with patch(
                            "app.adk.agents.utils.review_pipeline.extract_pipeline_result",
                            return_value=fake_outcome,
                        ):
                            with patch(
                                "app.adk.agents.utils.review_pipeline.extract_iterations",
                                return_value=[],
                            ):
                                with patch(
                                    "app.adk.agents.utils.review_pipeline_tracing.set_pipeline_attrs"
                                ):
                                    result = specialist_runtime.run(
                                        "spe_1",
                                        "do something",
                                        acceptance_criteria="must be accurate",
                                    )

        assert result == "pipeline result"

    def test_resolve_failure_returns_error_string(self) -> None:
        from app.adk.agents.agent_factory import specialist_runtime

        with patch.object(
            specialist_runtime,
            "resolve_agent",
            side_effect=RuntimeError("Firestore down"),
        ):
            result = specialist_runtime.run("broken_spe", "query")

        assert "broken_spe" in result
        assert "unavailable" in result.lower()

    def test_dispatch_failure_returns_error_string(self) -> None:
        from app.adk.agents.agent_factory import specialist_runtime

        fake_agent = _make_llm_agent()

        with patch.object(specialist_runtime, "resolve_agent", return_value=fake_agent):
            import app.adk.agents.utils.agent_retry as agent_retry_mod

            with patch.object(
                agent_retry_mod,
                "invoke_agent_with_retry",
                side_effect=RuntimeError("agent crashed"),
            ):
                result = specialist_runtime.run("spe_1", "query")

        assert "spe_1" in result
        assert "unavailable" in result.lower()


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

    def test_filters_out_not_visible_in_frontend(self) -> None:
        from app.adk.agents.agent_factory import specialist_runtime

        hidden_cfg = _make_merged_config("hidden", visible_in_frontend=False)
        visible_cfg = _make_merged_config("visible", visible_in_frontend=True)
        visible_agent = _make_llm_agent("visible_spe")

        ctx = self._make_context("acct_1")

        with (
            patch(
                "app.adk.agents.agent_factory.config_loader.list_account_agent_configs",
                return_value=["hidden_spe", "visible_spe"],
            ),
            patch.object(
                specialist_runtime,
                "resolve_config",
                side_effect=[hidden_cfg, visible_cfg],
            ),
            patch.object(
                specialist_runtime,
                "resolve_agent",
                return_value=visible_agent,
            ),
        ):
            result = specialist_runtime.available_specialists_provider(ctx)

        assert "visible_spe" in result
        assert "hidden_spe" not in result

    def test_failed_specialist_resolve_is_excluded_not_raised(self) -> None:
        from app.adk.agents.agent_factory import specialist_runtime

        good_cfg = _make_merged_config("good", visible_in_frontend=True)
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
            specialist_runtime.available_specialists_provider(self._make_context("acct_1"))
            specialist_runtime.available_specialists_provider(self._make_context("acct_2"))
            # Repeats of acct_1 still hit the cache.
            specialist_runtime.available_specialists_provider(self._make_context("acct_1"))

        assert list_mock.call_count == 2

    def test_firestore_error_not_cached(self) -> None:
        """A FirestoreConnectionError fallback must not poison the cache."""
        from app.adk.agents.agent_factory import specialist_runtime
        from app.adk.agents.agent_factory.config_loader import FirestoreConnectionError

        cfg = _make_merged_config("v1", visible_in_frontend=True)
        agent = _make_llm_agent("spe_1")
        ctx = self._make_context("acct_1")

        list_mock = MagicMock(
            side_effect=[FirestoreConnectionError("down"), ["spe_1"]]
        )

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
