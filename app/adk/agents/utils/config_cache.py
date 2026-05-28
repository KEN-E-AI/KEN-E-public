"""TTL-based in-process cache for agent configs (Sprint 6 Decision B).

The ADK ``Agent`` constructor accepts a callable only for ``instruction``;
``model``, ``generate_content_config`` (incl. temperature), and tools are
baked at construction time. So the hot-reload path is: the
``InstructionProvider`` closure reads ``instruction`` from this cache on
every turn. Changes made via the admin PUT endpoint propagate on the next
turn after the cached entry expires (~60 s by default).

Design choices:

* **Hand-rolled** — no new dependency (``cachetools`` is not in the
  project's dep tree). Simple ``dict`` + ``threading.Lock`` + ``time.monotonic``.
* **Single-flight** — one stripe lock covers the check-and-populate window
  so N concurrent cold reads for the same key hit Firestore once, not N.
* **Serve-stale-on-error** — if a refresh fails and we have a prior
  cached value, return it with a WARN log rather than failing the turn.
  If there's no prior cached value, re-raise (no safe fallback to serve).
* **No error caching** — a failed load never overwrites a good cached
  value, so the next successful refresh can replace the stale entry.
* **32-stripe locking** (AH-59) — 32 independent ``threading.Lock``
  instances replace the former single lock. Keys hash into a stripe so a
  slow Firestore call for specialist A never blocks reads for specialist B
  (unless they share the same stripe by hash collision, which occurs ~3 %
  of the time for a typical 10-specialist roster).

Two caches, one stripe array:

* ``_cache`` — ``{doc_id: (LlmAgentConfig, metadata, extensions, expires)}``
  Hot-reload surface for the strategy agent and deploy-time specialists.
  ``get_cached_config(doc_id)`` is the read path; lock key is ``doc_id``.

* ``_merged_cache`` — ``{(doc_id, account_id): (MergedAgentConfig, expires)}``
  Per-turn hot-reload surface for the per-dispatch-agent surface (AH-PRD-09).
  ``get_cached_merged_config(doc_id, account_id)`` is the read path; lock
  key is the ``(doc_id, account_id)`` tuple.

See :func:`get_cached_config` and :func:`get_cached_merged_config` for the
read paths. Callers must tolerate a stale value up to ``ttl_seconds`` old;
if strict freshness is required they should ``clear_config_cache()`` first
(used only in tests today).
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from google.adk.agents.llm_agent_config import LlmAgentConfig

from app.utils.weave_observability import safe_weave_op
from shared.structured_logging import get_structured_logger

from ..agent_factory.config_loader import MergedAgentConfig, load_agent_config
from ..strategy_agent.config_loader import load_config_from_firestore

logger = get_structured_logger(__name__)


def _current_project_id() -> str:
    """Resolve the GCP project the cache should query.

    Matches ``load_and_apply_config_overrides`` behavior in
    ``strategy_agent/config_loader.py`` — env var first, ``"ken-e-dev"`` as
    a development fallback. Without this, the cache would always use the
    ``load_config_from_firestore`` default (dev project) regardless of
    ``ENVIRONMENT``, silently mis-routing staging/prod reads.
    """
    return os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")


_CacheEntry = tuple[
    LlmAgentConfig, dict[str, Any], dict[str, Any], float
]  # (config, metadata, extensions, expires_at_monotonic)

_MergedCacheEntry = tuple[MergedAgentConfig, float]  # (config, expires_at_monotonic)

_cache: dict[str, _CacheEntry] = {}
_merged_cache: dict[tuple[str, str | None], _MergedCacheEntry] = {}

# 32 independent per-key locks. Keys hash into stripe[hash(key) % 32].
# Cold reads under lock hold a Firestore call; 32 stripes means a slow read
# for key A only blocks reads of keys that share the same stripe — roughly
# 1/32 probability for any two keys chosen uniformly.
_LOCK_STRIPES: int = 32
_locks: list[threading.Lock] = [threading.Lock() for _ in range(_LOCK_STRIPES)]


def _lock_for(key: Any) -> threading.Lock:
    return _locks[hash(key) % _LOCK_STRIPES]


@safe_weave_op(name="load_config_from_firestore")
def get_cached_config(
    doc_id: str, ttl_seconds: int = 60
) -> tuple[LlmAgentConfig, dict[str, Any], dict[str, Any]]:
    """Return the cached (config, metadata, extensions) for ``doc_id``.

    Refreshes if expired.

    Args:
        doc_id: Firestore document ID in the ``agent_configs`` collection.
        ttl_seconds: How long a successful load stays fresh before re-fetching.

    Returns:
        ``(LlmAgentConfig, metadata_dict, extensions_dict)`` — same shape as
        ``load_config_from_firestore`` returns. ``extensions_dict`` carries
        KEN-E-specific top-level Firestore fields (e.g. ``deployment_status``)
        that aren't part of the ADK ``LlmAgentConfig`` schema.

    Raises:
        Whatever ``load_config_from_firestore`` raises, *but only* when there
        is no cached value to fall back to. When a cached value exists, a
        failed refresh logs a WARN and returns the stale value.
    """
    now = time.monotonic()

    with _lock_for(doc_id):
        cached = _cache.get(doc_id)
        if cached is not None and now < cached[3]:
            logger.info("config_cache_read", extra={"doc_id": doc_id, "cache_hit": True})
            return cached[0], cached[1], cached[2]

        try:
            config, metadata, extensions = load_config_from_firestore(
                doc_id, project_id=_current_project_id()
            )
        except Exception as e:
            if cached is not None:
                logger.warning(
                    "Failed to refresh agent config %r from Firestore; "
                    "serving stale cached value (version=%s). Error: %s",
                    doc_id,
                    cached[1].get("version", "unknown"),
                    e,
                )
                return cached[0], cached[1], cached[2]
            raise

        logger.info("config_cache_read", extra={"doc_id": doc_id, "cache_hit": False})
        _cache[doc_id] = (config, metadata, extensions, now + ttl_seconds)
        return config, metadata, extensions


@safe_weave_op(name="load_merged_config_from_firestore")
def get_cached_merged_config(
    doc_id: str,
    account_id: str | None = None,
    ttl_seconds: int = 60,
) -> MergedAgentConfig:
    """Return the cached ``MergedAgentConfig`` for ``(doc_id, account_id)``.

    Refreshes if expired. Identical stale-on-error semantics to
    :func:`get_cached_config`: on Firestore failure, the last-good value is
    returned with a WARN log; on first-call failure (no cached value) the
    exception is re-raised.

    Args:
        doc_id: Firestore document ID in the ``agent_configs`` collection.
        account_id: When provided, the per-account overlay is merged on top of
            the global config.  ``None`` loads the global config only.
        ttl_seconds: TTL in seconds for successful loads.

    Returns:
        Validated ``MergedAgentConfig`` with per-account overlay applied if
        ``account_id`` is set.

    Raises:
        ``ConfigNotFoundError``, ``ConfigValidationError``, or
        ``FirestoreConnectionError`` — only when no stale entry exists.
    """
    key: tuple[str, str | None] = (doc_id, account_id)
    now = time.monotonic()

    with _lock_for(key):
        cached = _merged_cache.get(key)
        if cached is not None and now < cached[1]:
            logger.info("config_cache_read", extra={"doc_id": doc_id, "cache_hit": True})
            return cached[0]

        try:
            config = load_agent_config(
                doc_id, account_id=account_id, project_id=_current_project_id()
            )
        except Exception as e:
            if cached is not None:
                logger.warning(
                    "Failed to refresh merged agent config %r (account=%r) from Firestore; "
                    "serving stale cached value. Error: %s",
                    doc_id,
                    account_id,
                    e,
                )
                return cached[0]
            raise

        logger.info("config_cache_read", extra={"doc_id": doc_id, "cache_hit": False})
        _merged_cache[key] = (config, now + ttl_seconds)
        return config


def clear_config_cache() -> None:
    """Drop all cached entries. Primarily for tests.

    Acquires all 32 stripes in index order (avoids deadlock) then clears
    both ``_cache`` and ``_merged_cache`` atomically.
    """
    for lock in _locks:
        lock.acquire()
    try:
        _cache.clear()
        _merged_cache.clear()
    finally:
        for lock in _locks:
            lock.release()
