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
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache

from google.api_core import exceptions as gcp_exceptions
from google.cloud import firestore
from pydantic import ValidationError

from ..dependencies import get_firestore_client
from ..models.feature_flag_models import (
    EvaluationContext,
    FeatureFlag,
    FeatureFlagAuditEntry,
    FeatureFlagWriteRequest,
    FlagEvaluation,
)
from .feature_flag_audit import compute_flag_diff, record_audit

logger = logging.getLogger(__name__)

# TTL for in-process flag config cache entries (seconds). Exported so downstream
# modules (FF-5 helper, tests) can reference the authoritative constant.
TTL_SECONDS: float = float(os.environ.get("KENE_FF_CACHE_TTL_SECONDS", "60.0"))

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

        # Separate warm (cache hit) from cold (need Firestore) keys. Dedupe so a
        # key repeated in flag_keys issues at most one Firestore read. Freshness
        # uses strict `<` (entry at exactly its expiry instant is still warm) — the
        # TTL=0 kill-switch path relies on a same-timestamp re-read being a hit.
        cold_keys: list[str] = []
        seen: set[str] = set()
        for key in flag_keys:
            if key in seen:
                continue
            seen.add(key)
            entry = self._cache.get(key)
            if entry is None or entry.expires_at < now:
                cold_keys.append(key)
        cold_set: frozenset[str] = frozenset(cold_keys)

        # Cold keys whose read hit a transient error: not cached, and reported as
        # `fetch_error` so ops can tell a Firestore blip apart from a confirmed
        # absent flag (`unknown_flag`).
        fetch_error_keys: set[str] = set()

        # Fetch cold keys in parallel; return_exceptions=True so a single
        # Firestore error doesn't abort the whole batch.
        if cold_keys:
            fetch_results = await asyncio.gather(
                *[self._fetch_flag(k) for k in cold_keys],
                return_exceptions=True,
            )
            now = self._time_provider()
            for key, result in zip(cold_keys, fetch_results, strict=True):
                if isinstance(result, ValidationError):
                    # Permanently malformed config doc — re-fetching every request
                    # won't fix it. Cache as None so it isn't hammered for the TTL
                    # window, and emit a distinct event an operator can alert on,
                    # separate from a transient transport blip.
                    logger.error("feature_flag_invalid_config", extra={"flag_key": key})
                    self._install_cache(key, None, now)
                elif isinstance(result, BaseException):
                    # BaseException catches asyncio.CancelledError, which is not a
                    # subclass of Exception in Python 3.8+, but can surface here via
                    # gather(return_exceptions=True).  Transient error — log type only
                    # (no exc_info to avoid serialising Firestore document contents or
                    # gRPC internals into Cloud Logging).
                    # Do NOT cache so the next call retries.
                    logger.error(
                        "feature_flag_fetch_error",
                        extra={"flag_key": key, "error_type": type(result).__name__},
                    )
                    fetch_error_keys.add(key)
                else:
                    # result is FeatureFlag | None; cache both (None = confirmed miss).
                    self._install_cache(key, result, now)

        # Build response dict — use the same `now` captured after the gather so
        # freshly-installed entries (expires_at = now + TTL_SECONDS) are never
        # incorrectly treated as expired on this same call.
        evaluations: dict[str, FlagEvaluation] = {}
        for key in flag_keys:
            entry = self._cache.get(key)
            if entry is None or entry.expires_at < now:
                # No fresh entry after the fetch attempt: a transient read error
                # (transient reads aren't cached). Confirmed-absent docs fall to
                # the elif below as a cached None.
                if key in fetch_error_keys:
                    evaluations[key] = FlagEvaluation(
                        key=key, enabled=False, reason="fetch_error"
                    )
                else:
                    evaluations[key] = FlagEvaluation(
                        key=key, enabled=False, reason="unknown_flag"
                    )
            elif entry.flag is None:
                # Confirmed doc-absent, or a malformed doc cached as None.
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
            # Evict the oldest entry (insertion-ordered dict, O(1)). Reaching the
            # ceiling signals runaway key cardinality (a caller minting new flag
            # keys at a high rate) — surface it so it doesn't fail silently.
            oldest = next(iter(self._cache))
            del self._cache[oldest]
            logger.warning(
                "feature_flag_cache_eviction",
                extra={"evicted_key": oldest, "cache_size": len(self._cache)},
            )
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

    async def get_flag_audit(
        self,
        flag_key: str,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[FeatureFlagAuditEntry], str | None]:
        """Return a page of audit entries for flag_key, newest-first.

        Queries the global ``feature_flag_audit`` collection using the composite
        index on ``(flag_key ASC, created_at DESC)`` added by FF-PRD-01.  Does NOT
        read ``feature_flags/{flag_key}`` — intentionally works for deleted flags
        whose audit history is retained (FF-PRD-02 §9 risk row).

        created_at is stored as an ISO-8601 string by record_audit.  String
        comparison on ISO-8601 timestamps is time-monotonic, which is why this
        works correctly without a Firestore Timestamp field.

        Cursor semantics:
        - cursor is an opaque ``audit_id`` value from a prior page's next_cursor.
        - Resolved server-side by fetching ``feature_flag_audit/{cursor}`` and
          passing the resulting DocumentSnapshot to Firestore's start_after().
        - A stale cursor (audit doc no longer exists) returns ([], None) without
          raising — callers (FF-22 Load more) treat this as an empty terminal page.

        Exception semantics:
        - Firestore exceptions propagate to the caller; this method does NOT
          swallow them.  Admin callers need real errors (contrast with
          is_feature_enabled which swallows for the evaluation hot-path).

        Spec: FF-PRD-02 §4, §7 AC-5.

        Args:
            flag_key: The snake_case flag key to query.
            limit:    Maximum entries to return per page (1-50; validated by caller).
            cursor:   audit_id of the last entry from the prior page, or None for
                      the first page.

        Returns:
            (entries, next_cursor) where next_cursor is None when no more pages exist,
            or equals the audit_id of the last entry when a further page is available.
        """

        def _run() -> tuple[list[FeatureFlagAuditEntry], str | None]:
            coll = self._db.collection("feature_flag_audit")

            query = coll.where(
                filter=firestore.FieldFilter("flag_key", "==", flag_key)
            ).order_by("created_at", direction=firestore.Query.DESCENDING)

            if cursor is not None:
                cursor_doc = coll.document(cursor).get()
                if not cursor_doc.exists:
                    # Stale cursor — audit doc was deleted; return empty terminal page.
                    return [], None
                # Verify the cursor belongs to the same flag_key to prevent cross-flag
                # position leakage: a valid audit_id from a different flag would cause
                # start_after() to advance the index position outside flag_key's rows.
                if cursor_doc.to_dict().get("flag_key") != flag_key:
                    return [], None
                query = query.start_after(cursor_doc)

            # Fetch limit+1 to detect whether a next page exists.
            raw_docs = list(query.limit(limit + 1).stream())

            has_next = len(raw_docs) == limit + 1
            page_docs = raw_docs[:limit]

            entries: list[FeatureFlagAuditEntry] = []
            for doc in page_docs:
                try:
                    entries.append(FeatureFlagAuditEntry.model_validate(doc.to_dict()))
                except Exception:
                    logger.error(
                        "feature_flag_audit_invalid_doc", extra={"doc_id": doc.id}
                    )

            # Guard against empty entries when has_next is True (can occur if all
            # page_docs fail Pydantic validation — skipped by the loop above).
            next_cursor: str | None = (
                entries[-1].audit_id if (has_next and entries) else None
            )
            return entries, next_cursor

        return await asyncio.to_thread(_run)

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
        except gcp_exceptions.AlreadyExists as exc:
            raise DuplicateFeatureFlagError(flag.key) from exc

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
        # Read fresh from Firestore (bypasses TTL cache) so the audit diff
        # records the true before-state and updated_at reflects the actual
        # current document, not a potentially stale cache entry.
        existing = await self._fetch_flag(key)
        if existing is None:
            raise FeatureFlagNotFoundError(key)

        now = datetime.now(timezone.utc)
        flag_data = request.model_dump()
        flag_data["key"] = key  # canonical key from URL, overwrites body key
        flag_data["created_at"] = existing.created_at
        flag_data["updated_at"] = now
        updated = FeatureFlag(**flag_data)
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
        # Read fresh from Firestore (bypasses TTL cache) so the audit diff
        # captures the full before-state that was actually deleted.
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
