"""Admin router — super-admin role management (DM-81 Phase 2).

`super_admin` is the only path to super-admin privileges (see
`UserContext.is_super_admin`). These endpoints are the *only* sanctioned
writers of the `roles` field on `users/{uid}` — every other write path to that
document rejects a client-supplied `roles` (see `routers/firestore.py`).

All three endpoints require the caller to already hold the role, so the role
can only ever be spread by an existing super admin. The bootstrap migration
(`scripts/migrate_super_admin_roles.py`) seeds the first holders.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from google.cloud import firestore
from pydantic import BaseModel, Field, model_validator

from ..auth.audit_logger import SecurityEventType, get_audit_logger
from ..auth.cached_user_context import get_cached_user_context_service
from ..auth.dependencies import require_super_admin
from ..auth.firebase_admin import get_user, get_user_by_email
from ..auth.models import SUPER_ADMIN_ROLE, UserContext
from ..firestore import FirestoreService, get_firestore_service
from ..models.kene_models import SuccessResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class SuperAdminEntry(BaseModel):
    """A user holding the super_admin role."""

    uid: str = Field(..., description="Firebase uid")
    email: str | None = Field(None, description="User email, if known")


class SuperAdminListResponse(BaseModel):
    """Response model for listing super admins."""

    super_admins: list[SuperAdminEntry] = Field(..., description="Super-admin users")
    total: int = Field(..., description="Number of super admins")


class GrantSuperAdminRequest(BaseModel):
    """Request to grant the super_admin role. Provide exactly one identifier."""

    uid: str | None = Field(None, description="Firebase uid of the target user")
    email: str | None = Field(None, description="Email of the target user")

    @model_validator(mode="after")
    def _exactly_one_identifier(self) -> "GrantSuperAdminRequest":
        if bool(self.uid) == bool(self.email):
            raise ValueError("Provide exactly one of 'uid' or 'email'")
        return self


def _query_super_admin_docs(
    firestore_service: FirestoreService,
) -> list[dict]:
    """Return every `users/{uid}` doc that carries the super_admin role."""
    return firestore_service.list_documents(
        "users",
        where_filters=[("roles", "array_contains", SUPER_ADMIN_ROLE)],
    )


def _entry_from_doc(doc: dict) -> SuperAdminEntry:
    """Build a SuperAdminEntry from a Firestore user doc (`id` set by list)."""
    email = doc.get("profile", {}).get("email") or doc.get("email")
    return SuperAdminEntry(uid=doc["id"], email=email)


def _resolve_target(body: GrantSuperAdminRequest) -> tuple[str, str | None]:
    """Resolve a grant request to a (uid, email) pair via the Firebase Admin SDK.

    Resolving through Firebase confirms the identity exists and pins the grant
    to the immutable uid, even when the request came in by email.
    """
    try:
        if body.uid is not None:
            record = get_user(body.uid)
        else:
            # GrantSuperAdminRequest guarantees exactly one identifier is set.
            assert body.email is not None
            record = get_user_by_email(body.email)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return record.uid, record.email


async def _audit_role_change(
    request: Request,
    actor: UserContext,
    event_type: SecurityEventType,
    target_uid: str,
    target_email: str | None,
) -> None:
    """Audit-log a super-admin grant or revoke, attributing it to the actor."""
    await get_audit_logger().log_event(
        event_type=event_type,
        user_id=actor.user_id,
        email=actor.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
        details={"target_uid": target_uid, "target_email": target_email},
        severity="WARNING",
    )


@router.get("/super-admins", response_model=SuperAdminListResponse)
async def list_super_admins(
    _admin: UserContext = Depends(require_super_admin),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> SuperAdminListResponse:
    """List every user holding the super_admin role."""
    entries = [
        _entry_from_doc(doc) for doc in _query_super_admin_docs(firestore_service)
    ]
    return SuperAdminListResponse(super_admins=entries, total=len(entries))


@router.post(
    "/super-admins",
    response_model=SuperAdminEntry,
    status_code=status.HTTP_201_CREATED,
)
async def grant_super_admin(
    request: Request,
    body: GrantSuperAdminRequest,
    admin: UserContext = Depends(require_super_admin),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> SuperAdminEntry:
    """Grant the super_admin role to a user, identified by uid or email.

    Idempotent: granting an existing super admin is a no-op. A staff member who
    has no `users/{uid}` doc yet gets a baseline skeleton written.
    """
    uid, email = _resolve_target(body)
    client = firestore_service.get_client()
    user_ref = client.collection("users").document(uid)
    snapshot = user_ref.get()

    if snapshot.exists:
        if SUPER_ADMIN_ROLE in (snapshot.to_dict() or {}).get("roles", []):
            return SuperAdminEntry(uid=uid, email=email)
        user_ref.update({"roles": firestore.ArrayUnion([SUPER_ADMIN_ROLE])})
    else:
        user_ref.set(
            {
                "uid": uid,
                "email": email,
                "profile": {"email": email},
                "permissions": {"organizations": {}, "account_permissions": {}},
                "roles": [SUPER_ADMIN_ROLE],
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )

    get_cached_user_context_service().invalidate_user_context(uid)
    await _audit_role_change(
        request, admin, SecurityEventType.SUPER_ADMIN_GRANTED, uid, email
    )
    logger.info(f"User {admin.user_id} granted super_admin to {uid}")
    return SuperAdminEntry(uid=uid, email=email)


@router.delete("/super-admins/{uid}", response_model=SuccessResponse)
async def revoke_super_admin(
    uid: str,
    request: Request,
    admin: UserContext = Depends(require_super_admin),
    firestore_service: FirestoreService = Depends(get_firestore_service),
) -> SuccessResponse:
    """Revoke the super_admin role from a user.

    Refuses to remove the last remaining super admin — that would leave nobody
    able to grant the role back.
    """
    current_uids = {doc["id"] for doc in _query_super_admin_docs(firestore_service)}

    if uid not in current_uids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {uid} is not a super admin",
        )

    # Last-admin guard. This count-then-remove is not atomic: two concurrent
    # revokes of different admins could each observe >1 and both proceed,
    # reaching zero super admins. Very unlikely on a human-driven admin
    # endpoint, and recovery is just re-running the bootstrap migration —
    # make this a Firestore transaction if the race ever needs to be airtight.
    if len(current_uids) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot revoke the last remaining super admin",
        )

    client = firestore_service.get_client()
    client.collection("users").document(uid).update(
        {"roles": firestore.ArrayRemove([SUPER_ADMIN_ROLE])}
    )

    get_cached_user_context_service().invalidate_user_context(uid)
    await _audit_role_change(
        request, admin, SecurityEventType.SUPER_ADMIN_REVOKED, uid, None
    )
    logger.info(f"User {admin.user_id} revoked super_admin from {uid}")
    return SuccessResponse(
        success=True,
        message=f"Revoked super_admin from user {uid}",
        data={"uid": uid},
    )
