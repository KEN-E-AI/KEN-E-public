"""Account → organization resolver and cross-org access guard.

Provides a single shared lookup for the owning organization of an account and
the canonical cross-org-safe account access guard for all account-scoped
endpoints.

``require_account_access_for`` is the **only sanctioned account-level gate**
for account-scoped endpoints.  ``UserContext.has_account_access`` is unsafe
and deprecated — do not use it in new code.  See IN-2 for context.
"""

import logging

from fastapi import HTTPException

from ..database import neo4j_service

logger = logging.getLogger(__name__)

_QUERY = """
MATCH (acc:Account {account_id: $account_id})-[:BELONGS_TO]->(org:Organization)
RETURN org.organization_id AS organization_id
"""


async def resolve_owning_organization_id(account_id: str) -> str | None:
    """Return the organization_id that owns *account_id*, or None.

    Returns None when:
    - No :BELONGS_TO edge exists for the account (account not found).
    - Any Neo4j exception occurs (fail-closed — the caller should 404 or 503).
    """
    try:
        result = await neo4j_service.execute_query(_QUERY, {"account_id": account_id})
        if not result:
            return None
        return result[0]["organization_id"]
    except Exception:
        logger.warning(
            "resolve_owning_organization_id failed for account_id=%s",
            account_id,
            exc_info=True,
        )
        return None


async def require_account_access_for(
    user: "UserContext",  # type: ignore[name-defined]  # avoid circular import
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

    owning_org_id = await resolve_owning_organization_id(account_id)
    if owning_org_id is None or not user.has_account_permission(
        account_id, owning_org_id, required_level
    ):
        raise HTTPException(status_code=404, detail="Account not found")
