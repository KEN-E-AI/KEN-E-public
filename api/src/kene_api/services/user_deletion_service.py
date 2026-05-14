"""Registry of user-scoped data that the deletion orchestrator iterates over.

This module owns the canonical list of user-scoped Firestore subcollections
(``USER_SUBCOLLECTIONS``) and GCS prefixes (``USER_GCS_PREFIXES``) purged by
``delete_user_data(user_id)`` (DM-PRD-05).

Registry-update contract (PRD §6 AC-11)
----------------------------------------
Any future PRD that adds a new ``users/{user_id}/{name}/`` subcollection write
**must** append the subcollection name to ``USER_SUBCOLLECTIONS`` in this
module.  Similarly, any user-scoped GCS prefix introduced after v1 must be
added to ``USER_GCS_PREFIXES``.

CI grep enforcement of this contract is owned by DM-PRD-06 §4.2.  Until that
ships, the contract is documentation-only; the module docstring establishes the
convention so future authors see it at the file head.

Orchestrator implementation lives in DM-52; endpoint wiring in DM-53.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# User-scoped Firestore subcollections
#
# Each entry is the bare subcollection name under users/{user_id}/.
# One comment per entry cites the owning PRD or source file per AC-11.
# ---------------------------------------------------------------------------

USER_SUBCOLLECTIONS: list[str] = [
    "notification_status",  # firestore_notification_repository.py
    "preferences",          # firestore_notification_repository.py
    "chat_categories",      # CH-PRD-03
]

# ---------------------------------------------------------------------------
# User-scoped GCS prefixes
#
# Empty in v1 — no user-scoped GCS data exists today.
# Add via separate PR when any future user-scoped GCS data is introduced.
# ---------------------------------------------------------------------------

USER_GCS_PREFIXES: list[str] = []
