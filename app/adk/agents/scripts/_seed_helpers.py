"""Shared seed-script utilities for ``agent_configs/*`` (AH-41 follow-up).

Provides:

* ``AUDIT_FIELDS`` — the canonical 8-field set the AH-41 audit added.
  Single source of truth referenced by every seed script and test.
* ``AUDIT_FIELDS_RESEARCHER`` / ``AUDIT_FIELDS_FORMATTER`` — profile dicts
  with the matrix-decided default values for each agent class.
* ``upsert_agent_config`` — the one idempotent Firestore upsert function
  used by all four seed scripts (was previously duplicated four times).

Behavior contract (AH-41 PR review follow-up):

* ``set(config, merge=True)`` semantics — keys present in ``config`` are
  written and overwrite any prior value; keys NOT in ``config`` are
  preserved. **Re-running a script overwrites the fields the script
  manages.** This is intentional: the script files are the source of
  truth for those fields.
* If the doc does not yet exist AND the supplied config writes only the
  audit fields (i.e. no ``model`` / ``instruction`` / ``name``), emit a
  warning that the created doc is sparse and will not boot a real agent
  without a follow-up seed. This guards the audit-fields-only seed entries
  in ``upload_baseline_configs.py`` (competitive / marketing / brand pairs)
  against accidental clean-env runs.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# The 8 audited fields AH-41 added. Order matches the decision matrix
# columns in the PR description.
AUDIT_FIELDS: tuple[str, ...] = (
    "code_execution_enabled",
    "mcp_servers",
    "skill_ids",
    "sandbox_code_executor_enabled",
    "response_schema",
    "available_to_copy",
    "automatically_available",
    "visible_in_frontend",
)


# Default profile for researchers and user-facing specialists (chatbot,
# news, GA, business/competitive/marketing/brand researchers). Visible in
# the Workflows > Agents UI and forkable. Individual seeds override
# specific fields (e.g. GA flips code_execution_enabled + mcp_servers;
# the root chatbot flips available_to_copy=False).
AUDIT_FIELDS_RESEARCHER: dict[str, Any] = {
    "code_execution_enabled": False,
    "mcp_servers": [],
    "skill_ids": [],
    "sandbox_code_executor_enabled": False,
    "response_schema": None,
    "available_to_copy": True,
    "automatically_available": True,
    "visible_in_frontend": True,
}


# Profile for the 4 internal review-loop formatters
# (business / competitive / marketing / brand formatters). Hidden from the
# Workflows > Agents UI and not forkable: they're internal pipeline
# stages that take researcher output and emit structured JSON via a
# Python ``output_schema``.
AUDIT_FIELDS_FORMATTER: dict[str, Any] = {
    "code_execution_enabled": False,
    "mcp_servers": [],
    "skill_ids": [],
    "sandbox_code_executor_enabled": False,
    "response_schema": None,
    "available_to_copy": False,
    "automatically_available": True,
    "visible_in_frontend": False,
}


def upsert_agent_config(
    config: dict[str, Any],
    doc_id: str,
    project_id: str,
    *,
    dry_run: bool = False,
    db: Any | None = None,
) -> bool:
    """Idempotently upsert an ``agent_configs/{doc_id}`` document.

    Uses ``set(config, merge=True)`` so re-running the caller writes only
    the keys present in ``config`` and preserves anything else on the
    existing doc (e.g. fields added later via the admin UI that are not
    part of the seed's source-of-truth set).

    Args:
        config: Configuration dictionary to upsert. Fields present in this
            dict overwrite existing values; fields absent are preserved.
        doc_id: ``agent_configs/{doc_id}`` document identifier.
        project_id: GCP project ID (used only when ``db`` is not provided).
        dry_run: If True, log the intended action and return without
            writing.
        db: Pre-built Firestore client (for testing / dependency
            injection). When ``None`` a real client is created from
            ``project_id``.

    Returns:
        True on successful upsert (or successful dry-run); False if a
        Firestore exception was raised.
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would upsert '{doc_id}':")
        logger.info(f"  fields: {sorted(config.keys())}")
        return True

    try:
        if db is None:
            from google.cloud import firestore

            db = firestore.Client(project=project_id)

        doc_ref = db.collection("agent_configs").document(doc_id)
        existed = doc_ref.get().exists

        # AH-41 review follow-up: warn loudly when a clean-env run would
        # create a sparse audit-fields-only doc. The 6 strategy agents
        # in upload_baseline_configs.py (competitive/marketing/brand
        # researcher+formatter) only write audit fields — they rely on
        # an existing live doc to have model/instruction/temperature.
        if not existed and set(config.keys()) <= set(AUDIT_FIELDS):
            logger.warning(
                f"Creating sparse audit-fields-only doc for '{doc_id}' — "
                "no name/model/instruction in this seed. The doc will not "
                "boot a real agent until those fields are seeded separately."
            )

        doc_ref.set(config, merge=True)
        action = "Updated" if existed else "Created"
        logger.info(f"✅ {action} config '{doc_id}'")
        return True

    except Exception as exc:
        logger.error(f"❌ Failed to upsert config '{doc_id}': {exc}")
        return False
