"""Unit tests for the TTL-based agent config cache.

Covers Sprint 6 Decision B — the 60 s in-process cache that backs the
InstructionProvider hot-reload path. Hermetic — no Firestore, no agent
construction.
"""

from __future__ import annotations

import logging
import threading
from typing import Any
from unittest.mock import patch

import pytest
from google.adk.agents.llm_agent_config import LlmAgentConfig


def _make_config(
    instruction: str = "v1", model: str = "gemini-2.5-pro"
) -> LlmAgentConfig:
    return LlmAgentConfig(
        name="ken_e_chatbot",
        model=model,
        instruction=instruction,
        description="desc",
        generate_content_config={"temperature": 0.3, "max_output_tokens": 2048},
    )


@pytest.fixture(autouse=True)
def clear_cache_between_tests() -> Any:
    """Every test starts with a clean cache. Avoids bleed between tests."""
    from app.adk.agents.utils.config_cache import clear_config_cache

    clear_config_cache()
    yield
    clear_config_cache()


class TestTTLBehavior:
    def test_first_call_loads_from_firestore(self) -> None:
        from app.adk.agents.utils import config_cache

        with patch.object(config_cache, "load_config_from_firestore") as mock_load:
            mock_load.return_value = (_make_config("v1"), {"version": "v1"}, {})

            cfg, meta, ext = config_cache.get_cached_config("ken_e_chatbot")

            assert mock_load.call_count == 1
            assert cfg.instruction == "v1"
            assert meta["version"] == "v1"
            assert ext == {}

    def test_second_call_within_ttl_serves_cached(self) -> None:
        from app.adk.agents.utils import config_cache

        with patch.object(config_cache, "load_config_from_firestore") as mock_load:
            mock_load.return_value = (_make_config("v1"), {"version": "v1"}, {})

            config_cache.get_cached_config("ken_e_chatbot", ttl_seconds=60)
            config_cache.get_cached_config("ken_e_chatbot", ttl_seconds=60)

            assert mock_load.call_count == 1

    def test_call_after_ttl_expiry_refetches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.adk.agents.utils import config_cache

        clock = {"now": 1000.0}

        def fake_monotonic() -> float:
            return clock["now"]

        monkeypatch.setattr(config_cache.time, "monotonic", fake_monotonic)

        with patch.object(config_cache, "load_config_from_firestore") as mock_load:
            mock_load.return_value = (_make_config("v1"), {"version": "v1"}, {})

            config_cache.get_cached_config("ken_e_chatbot", ttl_seconds=60)
            clock["now"] = 1059.0  # just before expiry
            config_cache.get_cached_config("ken_e_chatbot", ttl_seconds=60)
            assert mock_load.call_count == 1

            clock["now"] = 1061.0  # just past expiry
            mock_load.return_value = (_make_config("v2"), {"version": "v2"}, {})
            cfg, _, _ = config_cache.get_cached_config("ken_e_chatbot", ttl_seconds=60)
            assert mock_load.call_count == 2
            assert cfg.instruction == "v2"

    def test_different_doc_ids_cached_independently(self) -> None:
        from app.adk.agents.utils import config_cache

        def loader(
            doc_id: str, project_id: str = "ken-e-dev"
        ) -> tuple[LlmAgentConfig, dict, dict]:
            return _make_config(f"{doc_id}_instr"), {"version": "v1"}, {}

        with patch.object(
            config_cache, "load_config_from_firestore", side_effect=loader
        ) as mock_load:
            a, _, _ = config_cache.get_cached_config("ken_e_chatbot")
            b, _, _ = config_cache.get_cached_config("business_researcher")

            assert a.instruction == "ken_e_chatbot_instr"
            assert b.instruction == "business_researcher_instr"
            assert mock_load.call_count == 2


class TestFailureHandling:
    def test_firestore_error_with_cached_value_serves_stale(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """On Firestore exception, the cache must serve the last-good value
        rather than propagate the error, and log a WARN."""
        from app.adk.agents.utils import config_cache

        clock = {"now": 1000.0}
        monkeypatch.setattr(config_cache.time, "monotonic", lambda: clock["now"])
        caplog.set_level(logging.WARNING)

        with patch.object(config_cache, "load_config_from_firestore") as mock_load:
            mock_load.return_value = (_make_config("v1"), {"version": "v1"}, {})
            config_cache.get_cached_config("ken_e_chatbot", ttl_seconds=60)

            clock["now"] = 1100.0  # force re-fetch
            mock_load.side_effect = RuntimeError("Firestore unreachable")

            cfg, meta, ext = config_cache.get_cached_config(
                "ken_e_chatbot", ttl_seconds=60
            )

        assert cfg.instruction == "v1", "should serve the stale-but-last-good value"
        assert meta["version"] == "v1"
        assert ext == {}
        assert any(
            "stale" in r.message.lower()
            for r in caplog.records
            if r.levelno >= logging.WARNING
        ), (
            f"Expected a WARN mentioning 'stale'. Got: {[r.message for r in caplog.records]}"
        )

    def test_firestore_error_with_no_cached_value_propagates(self) -> None:
        """First-call failure must re-raise — there's nothing safe to serve."""
        from app.adk.agents.utils import config_cache

        with patch.object(config_cache, "load_config_from_firestore") as mock_load:
            mock_load.side_effect = RuntimeError("Firestore unreachable")

            with pytest.raises(RuntimeError, match="Firestore unreachable"):
                config_cache.get_cached_config("ken_e_chatbot")

    def test_firestore_error_does_not_overwrite_good_cached_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An error during a refresh must not poison the cache — a subsequent
        successful refresh should replace the stale value."""
        from app.adk.agents.utils import config_cache

        clock = {"now": 1000.0}
        monkeypatch.setattr(config_cache.time, "monotonic", lambda: clock["now"])

        with patch.object(config_cache, "load_config_from_firestore") as mock_load:
            mock_load.return_value = (_make_config("v1"), {"version": "v1"}, {})
            config_cache.get_cached_config("ken_e_chatbot", ttl_seconds=60)

            # Expire → transient error → serve stale
            clock["now"] = 1100.0
            mock_load.side_effect = RuntimeError("transient")
            cfg, _, _ = config_cache.get_cached_config("ken_e_chatbot", ttl_seconds=60)
            assert cfg.instruction == "v1"

            # Next call after TTL should try again, and a successful response
            # should overwrite the stale cache
            clock["now"] = 1200.0
            mock_load.side_effect = None
            mock_load.return_value = (_make_config("v2"), {"version": "v2"}, {})
            cfg, _, _ = config_cache.get_cached_config("ken_e_chatbot", ttl_seconds=60)
            assert cfg.instruction == "v2"


class TestConcurrency:
    def test_concurrent_first_calls_only_load_once(self) -> None:
        """Cold start under N concurrent threads should fire exactly one
        Firestore load (thread-safe single-flight), not N. Relies on the
        cache using a lock that covers both the 'check' and 'populate'
        phases."""
        import time

        from app.adk.agents.utils import config_cache

        load_count = 0
        start_sem = threading.Event()

        def slow_loader(
            doc_id: str, project_id: str = "ken-e-dev"
        ) -> tuple[LlmAgentConfig, dict, dict]:
            nonlocal load_count
            # Small sleep widens the race window so any naive implementation
            # (check-then-populate without a single lock) would lose.
            time.sleep(0.05)
            load_count += 1
            return _make_config("v1"), {"version": "v1"}, {}

        def runner() -> None:
            start_sem.wait()
            config_cache.get_cached_config("ken_e_chatbot")

        with patch.object(
            config_cache, "load_config_from_firestore", side_effect=slow_loader
        ):
            threads = [threading.Thread(target=runner) for _ in range(5)]
            for t in threads:
                t.start()
            start_sem.set()  # release all threads simultaneously
            for t in threads:
                t.join(timeout=5)

        assert load_count == 1, (
            f"Expected single-flight under concurrent cold reads; got {load_count}"
        )


class TestClearCache:
    def test_clear_config_cache_forces_next_call_to_reload(self) -> None:
        from app.adk.agents.utils import config_cache

        with patch.object(config_cache, "load_config_from_firestore") as mock_load:
            mock_load.return_value = (_make_config("v1"), {"version": "v1"}, {})

            config_cache.get_cached_config("ken_e_chatbot")
            config_cache.clear_config_cache()
            config_cache.get_cached_config("ken_e_chatbot")

            assert mock_load.call_count == 2

    def test_clear_config_cache_safe_on_empty_cache(self) -> None:
        from app.adk.agents.utils import config_cache

        config_cache.clear_config_cache()
        config_cache.clear_config_cache()  # idempotent


class TestProjectIdEnvHonored:
    """Regression tests for the Sprint 6 code-review project_id fix.

    Pre-fix, ``get_cached_config`` called ``load_config_from_firestore(doc_id)``
    without a ``project_id``, so the loader's signature default
    ``"ken-e-dev"`` was used in every environment — silently mis-routing
    staging/prod hot-reload reads to the dev project. The stale-serve
    path would mask the misconfiguration as "Firestore unreachable".

    Post-fix, the cache resolves ``GOOGLE_CLOUD_PROJECT_ID`` at call time
    and passes it through (matches ``load_and_apply_config_overrides``).
    """

    def test_reads_project_id_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.adk.agents.utils import config_cache

        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-staging")

        with patch.object(config_cache, "load_config_from_firestore") as mock_load:
            mock_load.return_value = (_make_config("v1"), {"version": "v1"}, {})
            config_cache.get_cached_config("ken_e_chatbot")

        assert mock_load.call_count == 1
        kwargs = mock_load.call_args.kwargs
        args = mock_load.call_args.args
        # Loader should have been called with project_id="ken-e-staging" —
        # accepting it as either positional (2nd arg) or kwarg.
        project_id = kwargs.get("project_id") or (args[1] if len(args) > 1 else None)
        assert project_id == "ken-e-staging", (
            f"Expected loader called with project_id='ken-e-staging'; "
            f"got args={args!r}, kwargs={kwargs!r}"
        )

    def test_defaults_to_ken_e_dev_when_env_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.adk.agents.utils import config_cache

        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT_ID", raising=False)

        with patch.object(config_cache, "load_config_from_firestore") as mock_load:
            mock_load.return_value = (_make_config("v1"), {"version": "v1"}, {})
            config_cache.get_cached_config("ken_e_chatbot")

        kwargs = mock_load.call_args.kwargs
        args = mock_load.call_args.args
        project_id = kwargs.get("project_id") or (args[1] if len(args) > 1 else None)
        assert project_id == "ken-e-dev"


class TestStripedLocks:
    """Validate 32-stripe locking semantics added in AH-59.

    Two properties must hold:
    1. Same-key concurrent cold reads serialize: exactly one Firestore call
       fires regardless of thread count (single-flight per key).
    2. Different-key reads on *different* stripes run concurrently: the first
       key's Firestore call does not block the second key's Firestore call.
    """

    def test_same_key_concurrent_reads_serialize(self) -> None:
        """N concurrent cold reads for identical doc_id fire exactly one load."""
        import time

        from app.adk.agents.utils import config_cache

        load_count = 0
        start_sem = threading.Event()

        def slow_loader(
            doc_id: str, project_id: str = "ken-e-dev"
        ) -> tuple[LlmAgentConfig, dict, dict]:
            nonlocal load_count
            time.sleep(0.05)
            load_count += 1
            return _make_config("v1"), {"version": "v1"}, {}

        def runner() -> None:
            start_sem.wait()
            config_cache.get_cached_config("same_key_doc")

        with patch.object(
            config_cache, "load_config_from_firestore", side_effect=slow_loader
        ):
            threads = [threading.Thread(target=runner) for _ in range(6)]
            for t in threads:
                t.start()
            start_sem.set()
            for t in threads:
                t.join(timeout=5)

        assert load_count == 1, (
            f"Striped lock must provide single-flight for same key; got {load_count} loads"
        )

    def test_different_stripe_keys_do_not_block_each_other(self) -> None:
        """Reads on keys that fall into different stripes must not serialize.

        We pick two doc_ids that hash to *different* stripes and verify that
        two concurrent slow Firestore calls both complete — i.e., one doesn't
        block the other behind a global lock.  If they ran sequentially the
        total wall time would be >= 2 * sleep; concurrent execution keeps it
        under 1.5 * sleep.
        """
        import time

        from app.adk.agents.utils import config_cache

        sleep_secs = 0.1

        # Find two keys guaranteed to map to different stripes.
        stripes = config_cache._LOCK_STRIPES
        key_a, key_b = None, None
        for candidate in (f"doc_{i}" for i in range(200)):
            stripe = hash(candidate) % stripes
            if key_a is None:
                key_a = candidate
                stripe_a = stripe
            elif stripe != stripe_a:
                key_b = candidate
                break

        assert key_a is not None and key_b is not None, (
            "Could not find two keys on different stripes — increase candidate range"
        )

        call_times: list[float] = []

        def slow_loader(
            doc_id: str, project_id: str = "ken-e-dev"
        ) -> tuple[LlmAgentConfig, dict, dict]:
            call_times.append(time.monotonic())
            time.sleep(sleep_secs)
            return _make_config("v1"), {"version": "v1"}, {}

        results: list[Exception | None] = [None, None]

        def runner(idx: int, doc_id: str) -> None:
            try:
                config_cache.get_cached_config(doc_id)
            except Exception as exc:
                results[idx] = exc

        with patch.object(
            config_cache, "load_config_from_firestore", side_effect=slow_loader
        ):
            t0 = time.monotonic()
            threads = [
                threading.Thread(target=runner, args=(0, key_a)),
                threading.Thread(target=runner, args=(1, key_b)),
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            elapsed = time.monotonic() - t0

        assert results == [None, None], f"Unexpected errors: {results}"
        # Concurrent execution: wall time < 1.5 * sleep (not sequential 2 *)
        assert elapsed < sleep_secs * 1.5, (
            f"Different-stripe keys appear to have serialized: elapsed={elapsed:.3f}s "
            f"(expected < {sleep_secs * 1.5:.3f}s for concurrent execution)"
        )

    def test_merged_cache_same_key_concurrent_reads_serialize(self) -> None:
        """N concurrent cold reads for identical (doc_id, account_id) fire exactly one load."""
        import time

        from app.adk.agents.utils import config_cache

        load_count = 0
        start_sem = threading.Event()

        def slow_loader(
            doc_id: str,
            account_id: str | None = None,
            project_id: str = "ken-e-dev",
        ) -> Any:
            nonlocal load_count
            time.sleep(0.05)
            load_count += 1
            # Return a minimal MergedAgentConfig-like object
            from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

            return MergedAgentConfig(
                instruction="v1",
                model="gemini-2.5-pro",
                description="desc",
            )

        def runner() -> None:
            start_sem.wait()
            config_cache.get_cached_merged_config("merged_doc", "acct_1")

        with patch.object(config_cache, "load_agent_config", side_effect=slow_loader):
            threads = [threading.Thread(target=runner) for _ in range(5)]
            for t in threads:
                t.start()
            start_sem.set()
            for t in threads:
                t.join(timeout=5)

        assert load_count == 1, (
            f"Striped lock must provide single-flight for same (doc_id, account_id) key; "
            f"got {load_count} loads"
        )


class TestMergedConfigCache:
    """TTL-caching and error-handling for ``get_cached_merged_config``.

    Mirrors ``TestTTLBehavior`` and ``TestFailureHandling`` for the merged
    ``_merged_cache`` surface added in AH-59.
    """

    def _make_merged_config(self, instruction: str = "v1") -> Any:
        from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

        return MergedAgentConfig(
            instruction=instruction,
            model="gemini-2.5-pro",
            description="desc",
        )

    def test_first_call_loads_from_firestore(self) -> None:
        from app.adk.agents.utils import config_cache

        cfg = self._make_merged_config("v1")

        with patch.object(
            config_cache, "load_agent_config", return_value=cfg
        ) as mock_load:
            result = config_cache.get_cached_merged_config("specialist_1", "acct_1")

        assert mock_load.call_count == 1
        assert result.instruction == "v1"

    def test_second_call_within_ttl_serves_cached(self) -> None:
        from app.adk.agents.utils import config_cache

        cfg = self._make_merged_config("v1")

        with patch.object(
            config_cache, "load_agent_config", return_value=cfg
        ) as mock_load:
            config_cache.get_cached_merged_config(
                "specialist_1", "acct_1", ttl_seconds=60
            )
            config_cache.get_cached_merged_config(
                "specialist_1", "acct_1", ttl_seconds=60
            )

        assert mock_load.call_count == 1

    def test_call_after_ttl_expiry_refetches(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.adk.agents.utils import config_cache

        clock = {"now": 1000.0}
        monkeypatch.setattr(config_cache.time, "monotonic", lambda: clock["now"])

        cfg_v1 = self._make_merged_config("v1")
        cfg_v2 = self._make_merged_config("v2")

        with patch.object(config_cache, "load_agent_config") as mock_load:
            mock_load.return_value = cfg_v1
            config_cache.get_cached_merged_config(
                "specialist_1", "acct_1", ttl_seconds=60
            )

            clock["now"] = 1059.0  # just before expiry
            config_cache.get_cached_merged_config(
                "specialist_1", "acct_1", ttl_seconds=60
            )
            assert mock_load.call_count == 1

            clock["now"] = 1061.0  # just past expiry
            mock_load.return_value = cfg_v2
            result = config_cache.get_cached_merged_config(
                "specialist_1", "acct_1", ttl_seconds=60
            )
            assert mock_load.call_count == 2
            assert result.instruction == "v2"

    def test_different_account_ids_cached_independently(self) -> None:
        from app.adk.agents.utils import config_cache

        def loader(
            doc_id: str,
            account_id: str | None = None,
            project_id: str = "ken-e-dev",
        ) -> Any:
            from app.adk.agents.agent_factory.config_loader import MergedAgentConfig

            return MergedAgentConfig(
                instruction=f"{doc_id}_{account_id}_instr",
                model="gemini-2.5-pro",
                description="desc",
            )

        with patch.object(
            config_cache, "load_agent_config", side_effect=loader
        ) as mock_load:
            a = config_cache.get_cached_merged_config("specialist_1", "acct_a")
            b = config_cache.get_cached_merged_config("specialist_1", "acct_b")

        assert a.instruction == "specialist_1_acct_a_instr"
        assert b.instruction == "specialist_1_acct_b_instr"
        assert mock_load.call_count == 2

    def test_firestore_error_with_cached_value_serves_stale(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        from app.adk.agents.utils import config_cache

        clock = {"now": 1000.0}
        monkeypatch.setattr(config_cache.time, "monotonic", lambda: clock["now"])
        caplog.set_level(logging.WARNING)

        cfg_v1 = self._make_merged_config("v1")

        with patch.object(config_cache, "load_agent_config") as mock_load:
            mock_load.return_value = cfg_v1
            config_cache.get_cached_merged_config(
                "specialist_1", "acct_1", ttl_seconds=60
            )

            clock["now"] = 1100.0  # force re-fetch
            mock_load.side_effect = RuntimeError("Firestore unreachable")

            result = config_cache.get_cached_merged_config(
                "specialist_1", "acct_1", ttl_seconds=60
            )

        assert result.instruction == "v1", "should serve the stale-but-last-good value"
        assert any(
            "stale" in r.message.lower()
            for r in caplog.records
            if r.levelno >= logging.WARNING
        ), (
            f"Expected a WARN mentioning 'stale'. Got: {[r.message for r in caplog.records]}"
        )

    def test_firestore_error_with_no_cached_value_propagates(self) -> None:
        from app.adk.agents.utils import config_cache

        with patch.object(config_cache, "load_agent_config") as mock_load:
            mock_load.side_effect = RuntimeError("Firestore unreachable")

            with pytest.raises(RuntimeError, match="Firestore unreachable"):
                config_cache.get_cached_merged_config("specialist_1", "acct_1")

    def test_none_account_id_loads_global_config(self) -> None:
        """account_id=None is a valid key (global config without overlay)."""
        from app.adk.agents.utils import config_cache

        cfg = self._make_merged_config("global")

        with patch.object(
            config_cache, "load_agent_config", return_value=cfg
        ) as mock_load:
            result = config_cache.get_cached_merged_config("specialist_1", None)

        assert result.instruction == "global"
        assert mock_load.call_args.kwargs.get("account_id") is None
