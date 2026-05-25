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
    ``False``; ``errors`` defaults to an empty list.

    A re-run on an already-purged user returns an instance with all counts at
    zero and ``user_doc_deleted=True`` — recursive deletion of a missing
    document succeeds, so the idempotent no-op still reports the doc as gone.

    Disambiguating zero-counts: a per-step counter staying at 0 does not by
    itself mean "no work was needed" — the step may have *failed*. Because
    ``errors`` is a single flat list spanning all steps, consumers MUST match a
    step's structured error prefix (``discover_members:``,
    ``integrations_hook[…]:``, ``member_delete[…]:``, ``user_doc_purge:``,
    ``gcs_purge[…]:``) against its counter to tell "step failed, work
    unknowable" apart from "step succeeded, nothing to do".
    """

    user_id: str
    member_rows_deleted: int = Field(default=0, ge=0)
    integrations_hook_fired: int = Field(default=0, ge=0)
    user_doc_deleted: bool = False
    gcs_prefixes_purged: int = Field(default=0, ge=0)
    errors: list[str] = Field(default_factory=list)
