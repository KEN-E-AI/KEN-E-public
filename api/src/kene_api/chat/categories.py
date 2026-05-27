"""ChatCategoryService — per-user session-category CRUD (CH-PRD-03 §4.1, §4.2, §5.4).

Foundation issue CH-31 lands create_category + list_categories.
delete_category (CH-32) and assign_category (CH-33) extend this class.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore

from ..dependencies import get_firestore_client
from ..models.chat import (
    ChatCategoryDefinition,
    ChatSessionMetadata,
    compute_name_casefold,
)
from .side_table import ChatSessionSideTableService, recompute_search_text


@dataclass(frozen=True)
class DeleteCategoryResult:
    """Return shape for ChatCategoryService.delete_category.

    Internal service result — not a wire schema. The router (CH-35) translates
    to {sessions_reassigned: int} JSON.
    """

    category_id: str
    sessions_reassigned: int


class CategoryExistsError(Exception):
    """Raised when a category with the same casefold name already exists.

    existing_id is accessible as an attribute (not just via str(e)) so the
    router (CH-35) can translate: CategoryExistsError → HTTPException(409,
    detail={"error": "category_exists", "existing_category_id": e.existing_id}).
    """

    def __init__(self, message: str, existing_id: str) -> None:
        super().__init__(message)
        self.existing_id = existing_id


def _collection_path(user_id: str) -> str:
    return f"users/{user_id}/chat_categories"


def _doc_path(user_id: str, category_id: str) -> str:
    return f"{_collection_path(user_id)}/{category_id}"


def _deterministic_category_id(user_id: str, name_casefold: str) -> str:
    """Derive category_id from (user_id, name_casefold) so concurrent creates collide.

    A random UUID would let two simultaneous create_category() calls with the
    same (user_id, name_casefold) both succeed at different document paths,
    producing duplicate rows that violate the casefold-dedup invariant. By
    deriving the id from the dedup key, both calls converge on the same path —
    Firestore's atomic .create() then guarantees exactly one winner.
    """
    digest = hashlib.sha256(f"{user_id}|{name_casefold}".encode()).hexdigest()
    return f"cat_{digest[:24]}"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# Firestore transactions are capped at 500 operations. 400 updates + 1 fused
# tx.delete() on the last batch = 401 ops max — well within the limit.
_DELETE_CATEGORY_BATCH_SIZE = 400


@firestore.transactional
def _apply_delete_batch(
    tx: firestore.Transaction,
    batch: list[Any],
    is_last: bool,
    category_ref: Any,
    now: datetime,
) -> None:
    """Apply one batch of category-clearing updates inside a transaction.

    Defined at module level (not as a loop-local closure) so that the
    @firestore.transactional wrapper is created once and the SDK can manage
    retry state correctly across separate calls.
    """
    for snap in batch:
        new_search_text = recompute_search_text(snap.to_dict(), category_name=None)
        tx.update(
            snap.reference,
            {
                "category_id": firestore.DELETE_FIELD,
                "search_text": new_search_text,
                "updated_at": now,
            },
        )
    if is_last:
        tx.delete(category_ref)


class ChatCategoryService:
    """Service for per-user chat session categories.

    Firestore layout: users/{user_id}/chat_categories/{category_id}

    Dedup uses Unicode-safe casefold() (not lower()) per PRD §7.2 — handles
    Turkish dotted-i, German ß, Greek sigma variants, etc. correctly.

    Security contract: both public methods trust user_id to be the caller's
    authenticated identity. Callers MUST source user_id from UserContext.user_id
    (verified Firebase UID), never from request body or query parameters.
    """

    def __init__(self, db: firestore.Client) -> None:
        self._db = db

    def create_category(
        self,
        user_id: str,
        name: str,
    ) -> ChatCategoryDefinition:
        """Create a category for a user.

        Args:
            user_id: The authenticated user's ID.
            name: Display name (1-64 chars; leading/trailing whitespace is stripped).

        Returns:
            The newly created ChatCategoryDefinition.

        Raises:
            ValueError: If the stripped name is empty or exceeds 64 chars.
            CategoryExistsError: If a category with the same casefold name exists
                                 for this user. Exposes existing_id as an attribute.
        """
        stripped = name.strip()
        if not stripped:
            raise ValueError("Category name must not be empty after stripping whitespace")
        if len(stripped) > 64:
            raise ValueError("Category name must be 64 characters or fewer")

        new_casefold = compute_name_casefold(stripped)
        category_id = _deterministic_category_id(user_id, new_casefold)
        now = _now_utc()
        definition = ChatCategoryDefinition(
            category_id=category_id,
            user_id=user_id,
            name=stripped,
            name_casefold=new_casefold,
            created_at=now,
            updated_at=now,
        )
        try:
            self._db.document(_doc_path(user_id, category_id)).create(definition.model_dump())
        except AlreadyExists as exc:
            # The deterministic id collided — another row with this user's
            # name_casefold already exists. Surface it with the colliding id
            # (which equals what we just tried to write — the path IS the dedup
            # key, so the existing doc's id is structurally identical).
            raise CategoryExistsError(
                f"A category with name_casefold='{new_casefold}' already exists",
                existing_id=category_id,
            ) from exc
        return definition

    def list_categories(self, user_id: str) -> list[ChatCategoryDefinition]:
        """Return all categories for a user sorted alphabetically by name.

        Args:
            user_id: The authenticated user's ID.

        Returns:
            List of ChatCategoryDefinition sorted by name ASC (case-sensitive;
            consistent with how the dropdown renders them).
        """
        docs = list(
            self._db.collection(_collection_path(user_id))
            .order_by("name", direction=firestore.Query.ASCENDING)
            .get()
        )
        return [ChatCategoryDefinition(**doc.to_dict()) for doc in docs]

    def assign_category(
        self,
        user_id: str,
        session_id: str,
        category_id: str | None,
    ) -> ChatSessionMetadata:
        """Assign or clear a category on a session.

        Ownership is enforced on both the session and the category:
        - Session must belong to user_id, must not be tombstoned.
        - When category_id is non-null, that category must belong to user_id.

        Both ownership failures raise PermissionError so the router (CH-35)
        can translate to HTTPException(403). 404 is deliberately collapsed to
        403 to prevent ID probing (CH-PRD-03 §5.4, §7 AC-10).

        Args:
            user_id: The authenticated caller's ID.
            session_id: The ADK session ID to re-categorize.
            category_id: ID of the user's category to assign, or None to clear.

        Returns:
            The updated ChatSessionMetadata (with category_id and search_text
            already applied in-memory; the caller does not need to re-fetch).

        Raises:
            PermissionError: If the session does not belong to user_id, or if
                             category_id is non-null but does not belong to user_id.
                             Router (CH-35) maps this to HTTPException(403).
        """
        side_table_svc = ChatSessionSideTableService(db=self._db)
        metadata = side_table_svc.find_session_for_user(user_id, session_id)
        if metadata is None:
            raise PermissionError("Forbidden")

        category_name: str | None = None
        if category_id is not None:
            cat_doc = self._db.document(_doc_path(user_id, category_id)).get()
            doc_data = cat_doc.to_dict() or {}
            if not cat_doc.exists or not doc_data.get("name"):
                raise PermissionError("Forbidden")
            category_name = doc_data["name"]

        now = _now_utc()
        new_search_text = recompute_search_text(metadata, category_name)
        self._db.document(
            f"accounts/{metadata.account_id}/chat_sessions/{session_id}"
        ).update(
            {
                "category_id": category_id,
                "search_text": new_search_text,
                "updated_at": now,
            }
        )

        return metadata.model_copy(
            update={
                "category_id": category_id,
                "search_text": new_search_text,
                "updated_at": now,
            }
        )

    def delete_category(
        self,
        user_id: str,
        category_id: str,
    ) -> DeleteCategoryResult:
        """Delete a category and bulk-clear it from every affected session.

        Three-phase approach (PRD §4.3, issue body):

        Phase 1 — Discovery (outside transaction): query all chat_sessions docs
        belonging to user_id whose category_id matches the one being deleted.
        Reading outside the transaction is intentional and documented — the read
        may be large, and PRD §9 accepts that a concurrent assign_category that
        lands between Phase 1 and Phase 2 is silently cleared (last-writer-wins).

        Phase 2 — Batched transactions: chunk the affected snapshots into batches
        of _DELETE_CATEGORY_BATCH_SIZE (400). Each transaction calls tx.update()
        on every session in the batch, clearing category_id, recomputing
        search_text, and stamping updated_at.

        Phase 3 — Fused delete: the LAST batch's transaction also calls
        tx.delete() on the category document. When zero sessions are affected,
        a single transaction runs that only deletes the category doc.

        Idempotency: already-cleared sessions reach the same final state on
        retry. tx.delete() on a missing document is a no-op (Firestore SDK
        guarantee), so the overall call is safe to retry on partial failure.

        Args:
            user_id: The authenticated user's ID.
            category_id: The category to delete.

        Returns:
            DeleteCategoryResult with category_id + sessions_reassigned count.
        """
        category_ref = self._db.document(_doc_path(user_id, category_id))
        now = _now_utc()

        # Phase 1 — Discovery outside the transaction.
        # Tombstoned sessions (deleted_at set) are excluded: their updated_at
        # must not be dirtied and they should not inflate sessions_reassigned.
        affected: list[Any] = [
            snap
            for snap in self._db.collection_group("chat_sessions")
            .where("user_id", "==", user_id)
            .where("category_id", "==", category_id)
            .get()
            if snap.to_dict().get("deleted_at") is None
        ]

        # Split into chunks; when empty, chunks is [[]] so the last-batch
        # logic always runs exactly one transaction that only deletes the doc.
        chunks: list[list[Any]] = []
        if affected:
            for i in range(0, len(affected), _DELETE_CATEGORY_BATCH_SIZE):
                chunks.append(affected[i : i + _DELETE_CATEGORY_BATCH_SIZE])
        else:
            chunks = [[]]

        for batch_index, batch in enumerate(chunks):
            is_last = batch_index == len(chunks) - 1
            _apply_delete_batch(
                self._db.transaction(), batch, is_last, category_ref, now
            )

        return DeleteCategoryResult(
            category_id=category_id,
            sessions_reassigned=len(affected),
        )


@lru_cache(maxsize=1)
def get_chat_category_service() -> ChatCategoryService:
    """Process-wide singleton for ChatCategoryService.

    Mirrors the get_chat_side_table_service() pattern at side_table.py:199-202.
    The service is stateless modulo the injected Firestore client (itself a
    process-wide singleton), so caching is safe.
    """
    return ChatCategoryService(db=get_firestore_client())
