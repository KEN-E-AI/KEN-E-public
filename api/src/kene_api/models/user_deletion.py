"""Pydantic response model for the user-deletion orchestrator.

This model is the return type of ``delete_user_data(user_id)`` and the
response body of ``DELETE /api/v1/users/{user_id}``.

Spec: docs/design/components/data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md §4.2
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class UserDeletionResult(BaseModel):
    """Summary of a completed user-data purge.

    All numeric fields default to 0; ``user_doc_deleted`` defaults to
    ``False``; ``errors`` defaults to an empty list.  A re-run on an
    already-purged user returns an instance with all counts at zero and
    ``user_doc_deleted=False`` — that is the idempotent no-op result.
    """

    user_id: str
    member_rows_deleted: int = 0
    integrations_hook_fired: int = 0
    user_doc_deleted: bool = False
    gcs_prefixes_purged: int = 0
    errors: list[str] = Field(default_factory=list)
