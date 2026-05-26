"""ChatCategoryService — per-user session-category CRUD (CH-PRD-03 §4.1, §4.2, §5.4).

Foundation issue CH-31 lands create_category + list_categories.
delete_category (CH-32) and assign_category (CH-33) extend this class later.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from uuid import uuid4

from google.cloud import firestore

from ..dependencies import get_firestore_client
from ..models.chat import ChatCategoryDefinition, compute_name_casefold


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


def _new_category_id() -> str:
    """Generate a category_id with a human-readable prefix and a 24-hex-char random suffix."""
    return f"cat_{uuid4().hex[:24]}"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


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

        # Dedup: single-collection query scoped to this user.
        # PRD §4.2: name_casefold equality collision → 409.
        # No composite index needed for single-collection equality filters;
        # Firestore auto-indexes single fields.
        existing_docs = list(
            self._db.collection(_collection_path(user_id))
            .where(filter=firestore.FieldFilter("name_casefold", "==", new_casefold))
            .limit(1)
            .get()
        )
        if existing_docs:
            existing_id = existing_docs[0].id
            raise CategoryExistsError(
                f"A category with name_casefold='{new_casefold}' already exists",
                existing_id=existing_id,
            )

        category_id = _new_category_id()
        now = _now_utc()
        definition = ChatCategoryDefinition(
            category_id=category_id,
            user_id=user_id,
            name=stripped,
            name_casefold=new_casefold,
            created_at=now,
            updated_at=now,
        )
        self._db.document(_doc_path(user_id, category_id)).create(definition.model_dump())
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


@lru_cache(maxsize=1)
def get_chat_category_service() -> ChatCategoryService:
    """Process-wide singleton for ChatCategoryService.

    Mirrors the get_chat_side_table_service() pattern at side_table.py:199-202.
    The service is stateless modulo the injected Firestore client (itself a
    process-wide singleton), so caching is safe.
    """
    return ChatCategoryService(db=get_firestore_client())
