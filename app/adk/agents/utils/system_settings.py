"""TTL-cached accessor for the ``system_settings/harness`` Firestore document.

Provides a single global knob — ``harness_default_reviewer_model`` — that sits
between the per-specialist ``MergedAgentConfig.reviewer_model`` override (AH-92)
and the ``DEFAULT_REVIEWER_MODEL`` code constant:

    config.reviewer_model               # per-specialist override (AH-92)
      or harness_default_reviewer_model()  # ONE global knob (AH-93)
      or DEFAULT_REVIEWER_MODEL            # code floor

Design mirrors :mod:`app.adk.agents.utils.config_cache` TTL + single-flight +
serve-stale-on-error idiom, but uses a single ``threading.Lock`` (instead of a
32-stripe array) because there is exactly one key.

The ``system_settings`` Firestore collection is deliberately distinct from
``agent_configs`` so the document is not mistaken for a delegatable specialist
and is naturally excluded from ``list_account_agent_configs`` and the Available
Specialists block.

Decorator ``@safe_weave_op(name="load_system_settings_from_firestore")``
mirrors the observability seam on :func:`get_cached_config` so system-settings
fetches appear in the same Weave trace hierarchy as config fetches.
"""

# NOTE: do NOT add `from __future__ import annotations` here — see
# specialist_runtime.py header for the cloudpickle rationale.

import os
import threading
import time

from google.cloud import (
    firestore as _firestore,
)

from app.utils.weave_observability import safe_weave_op
from shared.structured_logging import get_structured_logger

logger = get_structured_logger(__name__)

# Firestore collection + document for harness-wide settings.
_SYSTEM_SETTINGS_COLLECTION = "system_settings"
_HARNESS_DOC_ID = "harness"

# Field name on the harness doc that holds the default reviewer model string.
_REVIEWER_MODEL_FIELD = "default_reviewer_model"

# Single-key TTL cache — (value_or_None, expires_at_monotonic).
# ``None`` means the doc does not exist or the field is absent.
_CacheEntry = tuple[str | None, float]

_cache: _CacheEntry | None = None
_lock: threading.Lock = threading.Lock()


def _current_project_id() -> str:
    """Resolve the GCP project to query.

    Matches :func:`app.adk.agents.utils.config_cache._current_project_id`:
    ``GOOGLE_CLOUD_PROJECT_ID`` env var first, ``"ken-e-dev"`` as a
    development fallback.
    """
    return os.getenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-dev")


@safe_weave_op(name="load_system_settings_from_firestore")
def harness_default_reviewer_model(ttl_seconds: int = 60) -> str | None:
    """Return the harness-wide default reviewer model, or ``None``.

    Reads ``system_settings/harness.default_reviewer_model`` from Firestore with
    a TTL cache (default 60 s, matching :func:`resolve_config`).  Returns
    ``None`` when the document does not exist or the field is absent — callers
    should fall back to ``DEFAULT_REVIEWER_MODEL`` in that case.

    Stale-on-error semantics (mirrors :func:`get_cached_config`):
    * On Firestore failure with a cached value: logs WARNING, returns stale.
    * On Firestore failure with no cached value: re-raises.

    Args:
        ttl_seconds: How long a successful load stays fresh before re-fetching.

    Returns:
        The stored model string (e.g. ``"gemini-2.5-flash"``), or ``None`` if
        the document / field is absent.

    Raises:
        Any Firestore exception — only when no cached value exists.
    """
    global _cache

    # Clamp negative values; callers should not cache for a negative duration.
    # Zero is accepted for tests that need to force a cache miss on every call.
    ttl_seconds = max(ttl_seconds, 0)
    now = time.monotonic()

    with _lock:
        if _cache is not None and now < _cache[1]:
            logger.debug(
                "system_settings_cache_hit",
                extra={"json_fields": {"field": _REVIEWER_MODEL_FIELD, "cache_hit": True}},
            )
            return _cache[0]

        try:
            db = _firestore.Client(project=_current_project_id())
            snap = (
                db.collection(_SYSTEM_SETTINGS_COLLECTION)
                .document(_HARNESS_DOC_ID)
                .get()
            )
            if not snap.exists:
                value: str | None = None
            else:
                doc: dict = snap.to_dict() or {}
                raw = doc.get(_REVIEWER_MODEL_FIELD)
                value = str(raw).strip() if raw and str(raw).strip() else None

        except Exception as exc:
            if _cache is not None:
                logger.warning(
                    "Failed to refresh system_settings/harness from Firestore; "
                    "serving stale cached value. Error: %s",
                    exc,
                )
                return _cache[0]
            raise

        logger.debug(
            "system_settings_cache_miss",
            extra={"json_fields": {"field": _REVIEWER_MODEL_FIELD, "cache_hit": False}},
        )
        _cache = (value, now + ttl_seconds)
        return value


def clear_system_settings_cache_for_tests() -> None:
    """Drop the cached system-settings entry.  Primarily for tests."""
    global _cache
    with _lock:
        _cache = None
