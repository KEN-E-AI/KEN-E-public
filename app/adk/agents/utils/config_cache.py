"""TTL-based in-process cache for agent configs (Sprint 6 Decision B).

The ADK ``Agent`` constructor accepts a callable only for ``instruction``;
``model``, ``generate_content_config`` (incl. temperature), and tools are
baked at construction time. So the hot-reload path is: the
``InstructionProvider`` closure reads ``instruction`` from this cache on
every turn. Changes made via the admin PUT endpoint propagate on the next
turn after the cached entry expires (~60 s by default).

Design choices:

* **Hand-rolled** — 35 lines, no new dependency (``cachetools`` is not in
  the project's dep tree). Simple ``dict`` + ``threading.Lock`` + ``time.monotonic``.
* **Single-flight** — one lock covers the check-and-populate window so N
  concurrent cold reads hit Firestore once, not N times.
* **Serve-stale-on-error** — if a refresh fails and we have a prior
  cached value, return it with a WARN log rather than failing the turn.
  If there's no prior cached value, re-raise (no safe fallback to serve).
* **No error caching** — a failed load never overwrites a good cached
  value, so the next successful refresh can replace the stale entry.

See :func:`get_cached_config` for the read path. Callers must tolerate a
stale value up to ``ttl_seconds`` old; if strict freshness is required
they should ``clear_config_cache()`` first (used only in tests today).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from google.adk.agents.llm_agent_config import LlmAgentConfig

from ..strategy_agent.config_loader import load_config_from_firestore

logger = logging.getLogger(__name__)


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
    LlmAgentConfig, dict[str, Any], float
]  # (config, metadata, expires_at_monotonic)

_cache: dict[str, _CacheEntry] = {}
_cache_lock = threading.Lock()


def get_cached_config(
    doc_id: str, ttl_seconds: int = 60
) -> tuple[LlmAgentConfig, dict[str, Any]]:
    """Return the cached (config, metadata) for ``doc_id``, refreshing if expired.

    Args:
        doc_id: Firestore document ID in the ``agent_configs`` collection.
        ttl_seconds: How long a successful load stays fresh before re-fetching.

    Returns:
        ``(LlmAgentConfig, metadata_dict)`` — same shape as
        ``load_config_from_firestore`` returns.

    Raises:
        Whatever ``load_config_from_firestore`` raises, *but only* when there
        is no cached value to fall back to. When a cached value exists, a
        failed refresh logs a WARN and returns the stale value.
    """
    now = time.monotonic()

    with _cache_lock:
        cached = _cache.get(doc_id)
        if cached is not None and now < cached[2]:
            return cached[0], cached[1]

        try:
            config, metadata = load_config_from_firestore(
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
                return cached[0], cached[1]
            raise

        _cache[doc_id] = (config, metadata, now + ttl_seconds)
        return config, metadata


def clear_config_cache() -> None:
    """Drop all cached entries. Primarily for tests."""
    with _cache_lock:
        _cache.clear()
