"""Feature Flags evaluation primitives.

This module is the home for all Feature Flags evaluation logic as defined in
FF-PRD-01. hash_bucket is landed in FF-2; the evaluator is now landed by FF-3;
the service class is landed by FF-4; is_feature_enabled and
get_feature_flag_service are landed by FF-5; mutating methods and domain
exceptions are landed by FF-13.
"""

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache

from google.api_core import exceptions as gcp_exceptions
from google.cloud import firestore

from ..dependencies import get_firestore_client
from ..models.feature_flag_models import (
    EvaluationContext,
    FeatureFlag,
    FeatureFlagWriteRequest,
    FlagEvaluation,
)
from .feature_flag_audit import compute_flag_diff, record_audit

logger = logging.getLogger(__name__)

# TTL for in-process flag config cache entries (seconds). Exported so downstream
# modules (FF-5 helper, tests) can reference the authoritative constant.
TTL_SECONDS: float = 60.0

# Hard ceiling on cache entries — defence against runaway key generation.
MAX_CACHE_ENTRIES: int = 10_000


def hash_bucket(flag_key: str, entity_id: str) -> int:
    """Return a deterministic bucket in [0, 99] for a (flag_key, entity_id) pair.

    Uses sha256(f"{flag_key}:{entity_id}") truncated to 8 hex chars, parsed as
    base-16, reduced modulo 100.  This algorithm is pinned by FF-PRD-01 §4 —
    any change to the byte sequence or modulus breaks cross-process
    determinism and silently shuffles users between rollout cohorts.

    Salting on flag_key gives each flag an independent hash distribution per
    entity.  entity_id MUST be an opaque identifier (ULID, UUID, branded
    string) — never an email address or any PII-bearing field (feature-flags
    README §7.3).
    """
    digest = hashlib.sha256(f"{flag_key}:{entity_id}".encode()).hexdigest()
    return int(digest[:8], 16) % 100


def evaluate(
    flag: FeatureFlag, ctx: EvaluationContext, *, cache_hit: bool
) -> FlagEvaluation:
    """Evaluate a feature flag against an evaluation context.

    Applies the precedence ladder defined in component README §7.2 and FF-PRD-01 §4
    (highest precedence first):
      1. Kill switch — flag.is_active is False → return default_enabled.
      2. Email allowlist — exact match on lowercased user_email. (grant only)
      3. Email domain — domain extracted from user_email. (grant only)
      4. Organisation ID — exact match on ctx.organization_id. (grant only)
      5. Account ID — exact match on ctx.account_id. (grant only)
      6. Percentage rollout — hash_bucket(flag.key, entity_id) < rollout_percentage.
      7. Default — flag.default_enabled.

    Note: all allowlist rules (steps 2-5) unconditionally grant enabled=True. They
    cannot be used to deny access. If both an allowlist rule and the rollout percentage
    would fire, the allowlist rule wins (higher precedence).

    Note: kill switch (step 1) returns default_enabled, which may be True if the flag
    was already at GA. To guarantee the feature is off, set both is_active=False and
    default_enabled=False.

    Emits exactly one structured INFO log per call with the fixed field set
    {flag_key, reason, cache_hit} (FF-PRD-01 §5.3 / AC-13). The message string is
    always the literal "feature_flag_evaluated" — no f-string interpolation — to
    eliminate the most common PII-leak vector. PII fields (user_id, user_email,
    organization_id, account_id) are never logged.

    cache_hit is a required keyword-only argument (no default) so a future call site
    that omits it raises TypeError immediately rather than silently logging False for
    a cached read and corrupting the ops cache-health signal.
    """
    if not flag.is_active:
        result = FlagEvaluation(
            key=flag.key, enabled=flag.default_enabled, reason="kill_switch"
        )
    else:
        rules = flag.targeting_rules
        email = ctx.user_email.strip().lower()

        if email in rules.user_emails:
            result = FlagEvaluation(key=flag.key, enabled=True, reason="email_match")
        elif (
            domain := (email.split("@", 1)[-1] if "@" in email else "")
        ) and domain in rules.email_domains:
            result = FlagEvaluation(key=flag.key, enabled=True, reason="domain_match")
        elif ctx.organization_id and ctx.organization_id in rules.organization_ids:
            result = FlagEvaluation(key=flag.key, enabled=True, reason="org_match")
        elif ctx.account_id and ctx.account_id in rules.account_ids:
            result = FlagEvaluation(key=flag.key, enabled=True, reason="account_match")
        elif (
            rules.rollout_percentage > 0
            and (
                entity_id := {
                    "account": ctx.account_id,
                    "organization": ctx.organization_id,
                    "user": ctx.user_id,
                }[flag.bucketing_entity]
            )
            and hash_bucket(flag.key, entity_id) < rules.rollout_percentage
        ):
            result = FlagEvaluation(key=flag.key, enabled=True, reason="rollout")
        else:
            result = FlagEvaluation(
                key=flag.key, enabled=flag.default_enabled, reason="default"
            )

    logger.info(
        "feature_flag_evaluated",
        extra={"flag_key": result.key, "reason": result.reason, "cache_hit": cache_hit},
    )
    return result


# ---------------------------------------------------------------------------
# FF-13: Domain exceptions for mutating operations
# ---------------------------------------------------------------------------


class FeatureFlagNotFoundError(Exception):
    """Raised by mutating service methods when the target flag doc does not exist.

    Callers (routers) catch this and convert it to an HTTP 404 response.
    """

    def __init__(self, key: str) -> None:
        super().__init__(f"Feature flag '{key}' not found")
        self.key = key


class DuplicateFeatureFlagError(Exception):
    """Raised by create_flag when a doc already exists for the given key.

    Callers (routers) catch this and convert it to an HTTP 409 response.
    """

    def __init__(self, key: str) -> None:
        super().__init__(f"Feature flag '{key}' already exists")
        self.key = key


# ---------------------------------------------------------------------------
# FF-4: FeatureFlagService — Firestore I/O + in-process TTL cache
# ---------------------------------------------------------------------------


@dataclass
class _CacheEntry:
    """Holds a resolved flag config (or None for a confirmed absent doc) with expiry."""

    flag: FeatureFlag | None
    expires_at: float


class FeatureFlagService:
    """Resolves and evaluates feature flags with a 60 s in-process TTL cache.

    The cache is keyed by flag_key (not by user) and holds the FeatureFlag
    config document. Unknown keys (doc absent) are also cached for the same
    TTL so repeated absent-key lookups do not thunder Firestore.

    Transient Firestore errors (transport failures, timeouts) are NOT cached —
    a subsequent call retries the read on the next request so a brief blip
    does not pin a flag as unknown for 60 s.

    Every Cloud Run instance owns its own cache; kill-switch propagation is
    bounded by TTL per instance (≤60 s SLO, README §7.4).
    """

    def __init__(
        self,
        db: firestore.Client,
        time_provider: Callable[[], float] = time.monotonic,
    ) -> None:
        self._db = db
        self._time_provider = time_provider
        self._cache: dict[str, _CacheEntry] = {}

    async def evaluate_batch(
        self,
        flag_keys: list[str],
        ctx: EvaluationContext,
    ) -> dict[str, FlagEvaluation]:
        """Evaluate a batch of flags for the given evaluation context.

        Returns one FlagEvaluation per requested key. Never raises for normal
        flow (unknown flags, transient Firestore errors). Cold-cache reads are
        issued in parallel via asyncio.gather.
        """
        now = self._time_provider()

        # Separate warm (cache hit) from cold (need Firestore) keys.
        cold_keys: list[str] = []
        for key in flag_keys:
            entry = self._cache.get(key)
            if entry is None or entry.expires_at <= now:
                cold_keys.append(key)
        cold_set: frozenset[str] = frozenset(cold_keys)

        # Fetch cold keys in parallel; return_exceptions=True so a single
        # Firestore error doesn't abort the whole batch.
        if cold_keys:
            fetch_results = await asyncio.gather(
                *[self._fetch_flag(k) for k in cold_keys],
                return_exceptions=True,
            )
            now = self._time_provider()
            for key, result in zip(cold_keys, fetch_results, strict=True):
                if isinstance(result, Exception):
                    # Transient error — log type only (no exc_info to avoid serialising
                    # Firestore document contents or gRPC internals into Cloud Logging).
                    # Do NOT cache so the next call retries.
                    logger.error(
                        "feature_flag_fetch_error",
                        extra={"flag_key": key, "error_type": type(result).__name__},
                    )
                else:
                    # result is FeatureFlag | None; cache both (None = confirmed miss).
                    self._install_cache(key, result, now)

        # Build response dict — use the same `now` captured after the gather so
        # freshly-installed entries (expires_at = now + TTL_SECONDS) are never
        # incorrectly treated as expired on this same call.
        evaluations: dict[str, FlagEvaluation] = {}
        for key in flag_keys:
            entry = self._cache.get(key)
            if entry is None or entry.expires_at <= now:
                # Still no entry after fetch attempt — was a transient error.
                evaluations[key] = FlagEvaluation(
                    key=key, enabled=False, reason="unknown_flag"
                )
            elif entry.flag is None:
                # Confirmed doc-absent (cached miss).
                evaluations[key] = FlagEvaluation(
                    key=key, enabled=False, reason="unknown_flag"
                )
            else:
                evaluations[key] = evaluate(
                    entry.flag, ctx, cache_hit=(key not in cold_set)
                )
        return evaluations

    def _install_cache(
        self,
        flag_key: str,
        flag: FeatureFlag | None,
        now: float,
    ) -> None:
        """Write a (possibly None) flag into the cache with FIFO eviction."""
        if len(self._cache) >= MAX_CACHE_ENTRIES and flag_key not in self._cache:
            # Evict the oldest entry (insertion-ordered dict, O(1)).
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[flag_key] = _CacheEntry(flag=flag, expires_at=now + TTL_SECONDS)

    async def list_flags(self) -> list[FeatureFlag]:
        """Return every flag document sorted by updated_at descending.

        Issues a single unbounded Firestore read — does NOT consult or warm the
        per-flag TTL cache because the cache is keyed per flag_key and cannot
        serve a full-collection list without a separate meta-entry.

        This is intentionally uncached; it is a super-admin-only endpoint on a
        small collection (<100 flags in Release 1). If N exceeds ~500 in a future
        release, add cursor pagination and an indexed updated_at sort instead of
        caching the full list.
        """
        docs = await asyncio.to_thread(
            lambda: list(self._db.collection("feature_flags").stream())
        )
        flags: list[FeatureFlag] = []
        for doc in docs:
            try:
                flags.append(
                    FeatureFlag.model_validate(doc.to_dict() | {"key": doc.id})
                )
            except Exception:
                logger.error("feature_flag_invalid_doc", extra={"doc_id": doc.id})
        flags.sort(key=lambda f: f.updated_at, reverse=True)
        return flags

    async def get_flag(self, flag_key: str) -> FeatureFlag | None:
        """Return a single flag by key, using the in-process TTL cache.

        Mirrors the _fetch_flag cache-aware path used by evaluate_batch so a
        recently-evaluated flag appears in the admin UI without an extra Firestore
        read (same TTL, same cache entry).

        Returns:
            FeatureFlag if the doc exists.
            None if the doc does not exist (confirmed miss).

        Raises:
            Any exception from Firestore or Pydantic — admin callers need real
            errors (unlike is_feature_enabled which swallows them).
        """
        now = self._time_provider()
        entry = self._cache.get(flag_key)
        if entry is not None and entry.expires_at > now:
            return entry.flag

        flag = await self._fetch_flag(flag_key)
        now = (
            self._time_provider()
        )  # re-capture after I/O, mirrors evaluate_batch pattern
        self._install_cache(flag_key, flag, now)
        return flag

    async def _fetch_flag(self, flag_key: str) -> FeatureFlag | None:
        """Fetch a single flag document from Firestore.

        Returns:
            FeatureFlag if the doc exists and is valid.
            None if the doc does not exist (confirmed miss — caller should cache).

        Raises:
            Any exception from Firestore or Pydantic validation — caller uses
            return_exceptions=True in asyncio.gather and must NOT cache the result.
        """
        doc = await asyncio.to_thread(
            self._db.collection("feature_flags").document(flag_key).get
        )
        if not doc.exists:
            return None
        # Merge the document-ID as the canonical key so a body/ID mismatch is
        # corrected at read time (PRD §4, Decisions & Assumptions).
        return FeatureFlag.model_validate(doc.to_dict() | {"key": flag_key})

    # -------------------------------------------------------------------------
    # FF-13: Mutating methods — create_flag / update_flag / delete_flag
    #
    # Audit writes happen inside these methods (service-as-chokepoint per
    # FF-PRD-02 §5 Backend).  Local-instance cache invalidation also lives here
    # so FF-16's cache-invalidation hook has a single place to extend.
    # -------------------------------------------------------------------------

    async def create_flag(
        self,
        request: FeatureFlagWriteRequest,
        actor_email: str,
    ) -> FeatureFlag:
        """Create a new feature flag document in Firestore.

        Uses DocumentReference.create() for an atomic, conflict-safe write so
        a duplicate key raises google.api_core.exceptions.AlreadyExists rather
        than silently overwriting an existing flag (FF-PRD-02 §5 Backend,
        architecture decision 1).

        Args:
            request:     Validated inbound payload (server ignores timestamps).
            actor_email: Email of the super-admin performing the create.

        Returns:
            The newly created FeatureFlag with server-stamped timestamps.

        Raises:
            DuplicateFeatureFlagError: if a flag with request.key already exists.
        """
        now = datetime.now(timezone.utc)
        flag = FeatureFlag(
            **request.model_dump(),
            created_at=now,
            updated_at=now,
        )
        data = flag.model_dump(mode="json")
        data.pop("key", None)  # key lives as the document ID, not in the body

        try:
            await asyncio.to_thread(
                self._db.collection("feature_flags").document(flag.key).create,
                data,
            )
        except gcp_exceptions.AlreadyExists:
            raise DuplicateFeatureFlagError(flag.key)

        # Invalidate any stale cache entry so a GET /{key} immediately after
        # POST returns the newly-created state, not a cached absent entry.
        self._cache.pop(flag.key, None)

        diff = compute_flag_diff(None, flag)
        await record_audit(self._db, flag.key, actor_email, "create", diff)

        return flag

    async def update_flag(
        self,
        key: str,
        request: FeatureFlagWriteRequest,
        actor_email: str,
    ) -> FeatureFlag:
        """Full-replace a feature flag document in Firestore.

        Reads the existing document first so the audit diff records the true
        before-state.  Race-condition risk is accepted for this low-volume
        super-admin surface (FF-PRD-02 §5 Backend, architecture decision 2 —
        get-then-write rather than a Firestore transaction).

        Args:
            key:         The snake_case flag key to update.  Must equal
                         ``request.key`` — the router enforces this before calling.
            request:     Validated inbound payload; server preserves
                         ``created_at`` from the existing document and stamps
                         a new ``updated_at``.
            actor_email: Email of the super-admin performing the update.

        Returns:
            The updated FeatureFlag with a fresh ``updated_at`` timestamp.

        Raises:
            FeatureFlagNotFoundError: if no document exists for ``key``.
        """
        existing = await self._fetch_flag(key)
        if existing is None:
            raise FeatureFlagNotFoundError(key)

        now = datetime.now(timezone.utc)
        updated = FeatureFlag(
            **request.model_dump(),
            key=key,  # canonical key from URL (router ensures body key == URL key)
            created_at=existing.created_at,
            updated_at=now,
        )
        data = updated.model_dump(mode="json")
        data.pop("key", None)

        await asyncio.to_thread(
            self._db.collection("feature_flags").document(key).set,
            data,
        )

        # Invalidate so subsequent reads don't serve the stale pre-update entry.
        self._cache.pop(key, None)

        diff = compute_flag_diff(existing, updated)
        await record_audit(self._db, key, actor_email, "update", diff)

        return updated

    async def delete_flag(
        self,
        key: str,
        actor_email: str,
    ) -> None:
        """Hard-delete a feature flag document from Firestore.

        Reads the existing document before deletion so the audit diff records
        the full before-state (after=None).  The audit entry for the deleted
        flag persists in ``feature_flag_audit`` so the action remains traceable
        after the flag document is gone (PRD §9 accepted risk — orphaned audit).

        Args:
            key:         The snake_case flag key to delete.
            actor_email: Email of the super-admin performing the delete.

        Raises:
            FeatureFlagNotFoundError: if no document exists for ``key``.
        """
        existing = await self._fetch_flag(key)
        if existing is None:
            raise FeatureFlagNotFoundError(key)

        await asyncio.to_thread(
            self._db.collection("feature_flags").document(key).delete,
        )

        # Remove the cache entry so a subsequent evaluation returns unknown_flag
        # rather than the stale config within the TTL window.
        self._cache.pop(key, None)

        diff = compute_flag_diff(existing, None)
        await record_audit(self._db, key, actor_email, "delete", diff)


# ---------------------------------------------------------------------------
# FF-5: Process-wide singleton factory + is_feature_enabled ergonomic helper
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_feature_flag_service() -> FeatureFlagService:
    """Return the process-wide FeatureFlagService singleton.

    Uses @lru_cache(maxsize=1) so the 60 s in-process TTL cache inside
    FeatureFlagService is preserved across all helper calls — constructing
    a new instance per call would discard the cache and defeat the SLO.

    Reuses the cached Firestore client from dependencies.get_firestore_client()
    to preserve the single connection pool (see api/CLAUDE.md §Dependency
    Injection).

    Call get_feature_flag_service.cache_clear() in tests to reset the singleton
    between cases.
    """
    return FeatureFlagService(db=get_firestore_client())


async def is_feature_enabled(
    flag_key: str,
    ctx: EvaluationContext,
    default: bool = False,
) -> bool:
    """Return whether a feature flag is enabled for the given evaluation context.

    This is the primary call-site API for routers and services. It is intentionally
    async — callers must await it; do not invoke synchronously inside FastAPI routes.

    On success, returns FlagEvaluation.enabled for flag_key. On any exception from
    the service layer (Firestore outage, transient network error, validation failure),
    logs the error type at WARN level and returns default. A flag-system outage must
    never propagate into an unrelated request path (FF-PRD-01 §9).

    The WARN log payload is {flag_key, error_type} only — no PII from ctx is logged.

    Args:
        flag_key: The snake_case flag key to evaluate.
        ctx: The evaluation context built from the authenticated user's token.
        default: Fallback value when the service raises. Defaults to False (safe floor).

    Returns:
        bool — True if the flag is enabled for this context, False otherwise.
    """
    try:
        service = get_feature_flag_service()
        result = await service.evaluate_batch([flag_key], ctx)
        return result[flag_key].enabled
    except Exception as exc:
        logger.warning(
            "feature_flag_helper_error",
            extra={"flag_key": flag_key, "error_type": type(exc).__name__},
        )
        return default
