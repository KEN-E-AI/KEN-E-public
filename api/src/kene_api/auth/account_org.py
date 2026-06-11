"""Account → organization resolver and cross-org access guard.

Provides a single shared lookup for the owning organization of an account and
the canonical cross-org-safe account access guard for all account-scoped
endpoints.

``require_account_access_for`` is the **only sanctioned account-level gate**
for account-scoped endpoints.  ``UserContext.has_account_access`` is unsafe
and deprecated — do not use it in new code.  See IN-2 for context.

**NOTE: ``compute_account_access_level`` is NOT a security gate.** It is a
helper for callers that already hold a ``require_account_access_for`` grant and
need to compute the user's highest access level without a second Neo4j hop.
Always call ``require_account_access_for`` first.
"""

import logging
import os
import time as _time_module
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from fastapi import HTTPException

from ..database import neo4j_service

if TYPE_CHECKING:
    from ..auth.models import UserContext

logger = logging.getLogger(__name__)


class AuthBackendUnavailable(Exception):
    """Raised by ``resolve_owning_organization_id`` when Neo4j is unreachable.

    The account's existence cannot be determined; callers must fail closed
    at 503 rather than treating this as a not-found (404).  Transient errors
    are never cached, so the next request retries.
    """


_QUERY = """
MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization)
RETURN org.organization_id AS organization_id
"""

# ---------------------------------------------------------------------------
# In-process TTL cache for the account → org mapping
# ---------------------------------------------------------------------------
# The Account-[:BELONGS_TO]->Organization edge is treated as effectively
# immutable within the lifetime of a Cloud Run instance.  Caching it avoids a
# Neo4j round-trip on every account-scoped request.
#
# TTL default 300 s; override with KENE_ACCOUNT_ORG_CACHE_TTL_SECONDS.
# Per-Cloud-Run-instance only — no Redis, no cross-instance invalidation.
# A hypothetical account reparent (out-of-spec today) will self-heal within
# one TTL window per instance, or immediately after a restart.  If account
# reparents ever become a real workflow, replace this with a Redis-backed cache
# with pub/sub invalidation (tracked as a follow-up to IN-3).
#
# Confirmed hits (org found) are cached for _DEFAULT_TTL.
# Confirmed misses (account not found, empty graph result) are cached for
# _MISS_TTL (default 0 — not cached). This prevents a newly-created account
# from being unreachable for a full TTL window after provisioning.
# Transient Neo4j exceptions are never cached (the resolver raises
# AuthBackendUnavailable instead of returning a value to cache).
#
# Cache size is capped at _MAX_CACHE_ENTRIES to bound memory on instances that
# see many distinct account IDs. Simple FIFO eviction: when the cap is reached,
# the first (oldest-inserted) key is removed.
#
# _DEFAULT_TTL / _MISS_TTL are evaluated at module import time (env vars set
# after import have no effect; this is intentional and matches the
# feature_flag_service pattern).
#
# Pattern mirrors api/src/kene_api/services/feature_flag_service.py.

_DEFAULT_TTL: float = float(
    os.environ.get("KENE_ACCOUNT_ORG_CACHE_TTL_SECONDS", "300.0")
)
_MISS_TTL: float = float(
    os.environ.get("KENE_ACCOUNT_ORG_MISS_TTL_SECONDS", "0.0")
)
_MAX_CACHE_ENTRIES: int = int(
    os.environ.get("KENE_ACCOUNT_ORG_CACHE_MAX_ENTRIES", "10000")
)


@dataclass
class _CacheEntry:
    """Holds a resolved org_id (or None for confirmed miss) with expiry."""

    value: str | None
    expires_at: float


# Module-level cache dict.  CPython dict get/set are atomic for single keys, so
# no explicit lock is needed for the read-heavy case here (matching the
# feature_flag_service precedent).
_cache: dict[str, _CacheEntry] = {}

# Injected time provider — override in tests to avoid time.sleep.
_time_provider: Callable[[], float] = _time_module.monotonic


def _set_time_provider(fn: Callable[[], float]) -> None:
    """Replace the time provider (for testing). Not thread-safe."""
    global _time_provider
    _time_provider = fn


def _clear_cache() -> None:
    """Discard all cached entries (for testing)."""
    _cache.clear()


def _install_cache(account_id: str, org_id: str | None, now: float) -> None:
    """Insert *org_id* into the cache with the appropriate TTL."""
    ttl = _DEFAULT_TTL if org_id is not None else _MISS_TTL
    if ttl <= 0:
        return
    if len(_cache) >= _MAX_CACHE_ENTRIES:
        # Simple FIFO eviction: drop the oldest-inserted key.
        try:
            oldest = next(iter(_cache))
            del _cache[oldest]
        except StopIteration:
            pass
    _cache[account_id] = _CacheEntry(value=org_id, expires_at=now + ttl)


async def resolve_owning_organization_id(account_id: str) -> str | None:
    """Return the organization_id that owns *account_id*, or None.

    Returns None when no :BELONGS_TO edge exists for the account (account not
    found).

    Raises:
        AuthBackendUnavailable: When a Neo4j exception occurs. Callers must
            respond with 503 — this is a backend-availability failure, not a
            not-found condition.

    **Caching behaviour:**
    - Confirmed hits (org found) are cached for ``KENE_ACCOUNT_ORG_CACHE_TTL_SECONDS``
      (default 300 s) per Cloud Run instance.
    - Confirmed misses (account not found) are cached for
      ``KENE_ACCOUNT_ORG_MISS_TTL_SECONDS`` (default 0 — not cached) so that
      newly-created accounts are accessible immediately after provisioning.
    - Transient Neo4j exceptions are *not* cached (they raise) so the next
      request retries.
    - The ``Account-[:BELONGS_TO]->Organization`` edge is assumed immutable.
      An account reparent would take up to TTL seconds to propagate on each
      instance.  This is acceptable because account reparents are out-of-spec
      today.  See module docstring for follow-up path.
    """
    now = _time_provider()
    entry = _cache.get(account_id)
    if entry is not None and entry.expires_at >= now:
        return entry.value

    try:
        result = await neo4j_service.execute_query(_QUERY, {"account_id": account_id})
        org_id: str | None = result[0]["organization_id"] if result else None
    except Exception as e:
        logger.warning(
            "resolve_owning_organization_id failed for account_id=%s",
            account_id,
            exc_info=True,
        )
        # Do NOT cache transient errors — fail closed at 503 and let the next
        # call retry.
        raise AuthBackendUnavailable(
            f"Neo4j unavailable while resolving organization for account {account_id}"
        ) from e

    # Cache confirmed hit or confirmed miss (subject to per-type TTL).
    _install_cache(account_id, org_id, now)
    return org_id


async def require_account_access_for(
    user: "UserContext",
    account_id: str,
    required_level: str = "view",
) -> None:
    """Assert that *user* has *required_level* access to *account_id*.

    This is the **only sanctioned cross-org-safe account access gate**.
    Every account-scoped endpoint MUST call this instead of
    ``user.has_account_access()``.

    Raises ``HTTPException(404, "Account not found")`` when:
    - The account does not exist or its owning org cannot be resolved.
    - The user does not have the required permission level.

    Raises ``HTTPException(503, "Authorization backend unavailable")`` when the
    auth backend (Neo4j) is unreachable — fail-closed, never granting access.

    Returns ``None`` on success.

    Super-admins are never blocked (short-circuits before the resolver call).

    ``required_level`` must be ``"view"`` or ``"edit"``.
    """
    if required_level not in ("view", "edit"):
        raise ValueError(
            f"required_level must be 'view' or 'edit', got {required_level!r}"
        )

    if user.is_super_admin:
        return

    try:
        owning_org_id = await resolve_owning_organization_id(account_id)
    except AuthBackendUnavailable:
        raise HTTPException(
            status_code=503, detail="Authorization backend unavailable"
        ) from None

    if owning_org_id is None or not user.has_account_permission(
        account_id, owning_org_id, required_level
    ):
        raise HTTPException(status_code=404, detail="Account not found")


async def compute_account_access_level(
    user: "UserContext",
    account_id: str,
) -> Literal["admin", "edit", "view"] | None:
    """Return the highest access level *user* has for *account_id*, or None.

    **This is NOT a security gate.** Always call ``require_account_access_for``
    first to enforce access; use this helper only to compute the access level
    for response fields (e.g. ``StrategyDocumentResponse.access_level``) after
    the gate has already passed.

    Returns:
    - ``"admin"`` for super-admins (without calling the resolver).
    - ``"edit"`` when the user has edit-or-higher permission on the account.
    - ``"view"`` when the user has view-only permission.
    - ``None`` when the user has no access (resolver miss or no permission).

    Raises ``HTTPException(503, "Authorization backend unavailable")`` if the
    resolver hits a Neo4j outage. In the gate-first flow this is unreachable —
    ``require_account_access_for`` already populated the cache (Neo4j up) or
    503'd first (Neo4j down) — but the resolver can raise, so this fails closed
    rather than surfacing an uncontrolled 500 to a future non-gate-first caller.

    Reuses the cached ``resolve_owning_organization_id`` — a second call within
    the same request is a microsecond cache hit, never a second Neo4j round-trip.
    """
    if user.is_super_admin:
        return "admin"

    try:
        owning_org_id = await resolve_owning_organization_id(account_id)
    except AuthBackendUnavailable:
        raise HTTPException(
            status_code=503, detail="Authorization backend unavailable"
        ) from None

    if owning_org_id is None:
        return None

    if user.has_account_permission(account_id, owning_org_id, "edit"):
        return "edit"
    if user.has_account_permission(account_id, owning_org_id, "view"):
        return "view"
    return None
