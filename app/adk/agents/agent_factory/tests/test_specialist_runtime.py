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
) -> Any:
    """Build an ``ExitStack`` patching every external dep of ``_build_specialist``.

    All targets patch the *source* module path (e.g. ``...mcp.build_toolset_for_doc``)
    rather than ``specialist_runtime.*`` because ``_build_specialist`` re-imports
    each symbol via local ``from … import …`` inside the function body.

    Returns ``(stack, mock_build_toolset, mock_build_agent)`` so callers can
    inspect captured call args / kwargs after entering the stack.
    """
    from contextlib import ExitStack
    from unittest.mock import patch as _patch

    stack = ExitStack()

    if fake_db is None:
        fake_db = _FakeFirestoreDb({})

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
                side_effect=RosterCapExceededError(
                    "test cap exceeded: 31 tools > 30"
                ),
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
