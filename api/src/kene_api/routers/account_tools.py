"""Account tool-inventory endpoint (AH-PRD-06 §6).

``GET /api/v1/accounts/{account_id}/tools`` — returns every tool the account
can attach to its agents, tagged by source so the Workflows > Agents tool
picker can group them.

Spec: ``docs/design/components/agentic-harness/projects/AH-PRD-06-tool-mapping.md``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from google.cloud import firestore  # type: ignore[import-untyped]

from ..auth import UserContext
from ..auth.user_context import get_current_user_context
from ..dependencies import get_firestore
from ..models.tool_models import AccountToolsResponse
from ..services.account_tools_service import compose_inventory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/accounts", tags=["account-tools"])


@router.get(
    "/{account_id}/tools",
    response_model=AccountToolsResponse,
    summary="List tools available to this account",
)
async def list_account_tools(
    account_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: firestore.Client = Depends(get_firestore),
) -> AccountToolsResponse:
    """Return the account's tool inventory.

    Function tools tagged ``default_global`` in the catalogue are always
    present. MCP-attached tools are gated on a connected integration for
    the account (see the ``integration_credentials`` collection).
    """
    if not user.has_account_access(account_id):
        raise HTTPException(status_code=403, detail="Access denied to this account")

    try:
        return compose_inventory(account_id=account_id, db=db)
    except Exception as exc:
        logger.error(
            "Failed to compose tool inventory for account %s: %s", account_id, exc
        )
        raise HTTPException(
            status_code=500, detail="Failed to load tool inventory"
        ) from exc
