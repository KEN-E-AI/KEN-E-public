"""Account → organization resolver.

Provides a single shared lookup for the owning organization of an account.
Callers should treat None as "account not found or DB unavailable" and raise
an appropriate HTTP error (404 is the safe default — see fail-closed rationale
in IN-1 implementation plan).
"""

import logging

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
