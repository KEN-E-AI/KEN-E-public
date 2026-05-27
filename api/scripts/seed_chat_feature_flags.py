#!/usr/bin/env python3
"""Seed the three Chat-component feature flags into Firestore.

Registers exactly the flags listed in CH-PRD-01 §5.6.  Two flags explicitly
scoped out of v1 (chat_manual_compaction_enabled,
chat_permissions_and_tools_ui_enabled) are named in CHAT_FLAGS_SCOPED_OUT_OF_V1
so any future contributor trying to add them via this script is forced to update
the enumeration — a silent omission would be hard to catch in review.

Usage:
    python api/scripts/seed_chat_feature_flags.py
    python api/scripts/seed_chat_feature_flags.py --dry-run
    python api/scripts/seed_chat_feature_flags.py --yes-i-know-its-not-dev  # bypass dev guard

Exit codes: 0 success, 1 failure.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path bootstrap so kene_api imports resolve when run as a script
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kene_api.models.feature_flag_models import FeatureFlagWriteRequest
from src.kene_api.services.feature_flag_service import (
    DuplicateFeatureFlagError,
    FeatureFlagService,
)

# ---------------------------------------------------------------------------
# Flag registry: exactly the three flags from PRD §5.6
# ---------------------------------------------------------------------------

CHAT_FLAGS_TO_REGISTER: list[FeatureFlagWriteRequest] = [
    FeatureFlagWriteRequest(
        key="chat_v2_enabled",
        description=(
            "Master kill switch for the Chat component (sidebar, status view, "
            "categories, todos, artifacts). When False, all new Chat endpoints "
            "return 404; existing endpoints remain functional."
        ),
        default_enabled=False,
        is_active=True,
        bucketing_entity="account",
        owner="chat-team@ken-e.ai",
    ),
    FeatureFlagWriteRequest(
        key="chat_status_detail_enabled",
        description=(
            "Gates the session status view endpoint + Session Status toggle "
            "button. Depends on chat_v2_enabled being on."
        ),
        default_enabled=False,
        is_active=True,
        bucketing_entity="account",
        owner="chat-team@ken-e.ai",
    ),
    FeatureFlagWriteRequest(
        key="chat_categories_enabled",
        description=(
            "Gates category CRUD + sidebar filter + status-view assign dropdown. "
            "Depends on chat_v2_enabled being on."
        ),
        default_enabled=False,
        is_active=True,
        bucketing_entity="account",
        owner="chat-team@ken-e.ai",
    ),
]

# These are intentionally NOT in CHAT_FLAGS_TO_REGISTER (scoped out of v1).
# Naming them explicitly here forces a contributor adding one of them to make a
# deliberate choice rather than silently skipping the enumeration.
CHAT_FLAGS_SCOPED_OUT_OF_V1: frozenset[str] = frozenset(
    {
        "chat_manual_compaction_enabled",  # Compact-now deferred beyond v1
        "chat_permissions_and_tools_ui_enabled",  # Permissions Approved card not rendered in v1
    }
)

# Disjointness guard — evaluated at import time so any accidental overlap is
# caught immediately rather than at runtime.
_registered_keys = frozenset(f.key for f in CHAT_FLAGS_TO_REGISTER)
_overlap = _registered_keys & CHAT_FLAGS_SCOPED_OUT_OF_V1
if _overlap:
    raise ValueError(
        f"CHAT_FLAGS_TO_REGISTER and CHAT_FLAGS_SCOPED_OUT_OF_V1 must be disjoint; "
        f"overlap: {_overlap}"
    )

_ACTOR_EMAIL = "system+ch-19-seed@ken-e.ai"


# ---------------------------------------------------------------------------
# Core seed logic
# ---------------------------------------------------------------------------


async def _seed_flags(db: object, dry_run: bool) -> dict[str, str]:
    """Create the three Chat flags.  Returns {key: outcome} where outcome is
    'created', 'already_exists', or 'dry_run'."""
    service = FeatureFlagService(db=db)
    results: dict[str, str] = {}
    for req in CHAT_FLAGS_TO_REGISTER:
        if dry_run:
            print(f"  [DRY RUN] would create: {req.key!r} (default_enabled=False)")
            results[req.key] = "dry_run"
            continue
        try:
            await service.create_flag(req, actor_email=_ACTOR_EMAIL)
            print(f"  CREATED  {req.key!r}")
            results[req.key] = "created"
        except DuplicateFeatureFlagError:
            print(f"  EXISTS   {req.key!r} (already exists — skipping)")
            results[req.key] = "already_exists"
    return results


# ---------------------------------------------------------------------------
# Dev-project guard (mirrors seed_shape_b_fixtures.py)
# ---------------------------------------------------------------------------


def _is_dev_project(project_id: str) -> bool:
    return project_id.endswith("-dev") or project_id in {"test-project", ""}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed Chat-component feature flags into Firestore (idempotent)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print planned writes without touching Firestore. Exit 0.",
    )
    parser.add_argument(
        "--yes-i-know-its-not-dev",
        action="store_true",
        default=False,
        help="Bypass the -dev project guard (use with caution).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "")

    if not _is_dev_project(project_id) and not args.yes_i_know_its_not_dev:
        print(
            f"ERROR: GOOGLE_CLOUD_PROJECT_ID={project_id!r} does not end with '-dev'.\n"
            "This script is intended for local dev and controlled migrations.\n"
            "If you really want to run against this project, pass --yes-i-know-its-not-dev."
        )
        return 1

    if args.yes_i_know_its_not_dev and not _is_dev_project(project_id):
        confirm = os.getenv("KENE_SEED_NON_DEV_CONFIRM", "")
        if confirm != project_id:
            print(
                f"ERROR: --yes-i-know-its-not-dev requires KENE_SEED_NON_DEV_CONFIRM "
                f"to be set to the target project ID to prevent accidental runs.\n"
                f"  export KENE_SEED_NON_DEV_CONFIRM={project_id}\n"
                f"  # then re-run"
            )
            return 1
        print(
            f"WARNING: Running against non-dev project {project_id!r}. "
            "Proceeding because --yes-i-know-its-not-dev was passed.\n"
        )

    print("=== seed_chat_feature_flags ===")
    print(f"project_id : {project_id or '(not set)'}")
    print(f"dry_run    : {args.dry_run}")
    print(f"flags      : {[f.key for f in CHAT_FLAGS_TO_REGISTER]}")
    print(f"scoped_out : {sorted(CHAT_FLAGS_SCOPED_OUT_OF_V1)}")
    print()

    from src.kene_api.dependencies import get_firestore_client

    db = get_firestore_client()

    try:
        results = asyncio.run(_seed_flags(db=db, dry_run=args.dry_run))
    except Exception as exc:
        print(f"\nERROR: unexpected exception during seeding: {exc}")
        return 1

    print()
    created = sum(1 for v in results.values() if v == "created")
    existing = sum(1 for v in results.values() if v == "already_exists")
    dry = sum(1 for v in results.values() if v == "dry_run")
    print(
        f"Done. created={created}  already_exists={existing}  dry_run={dry}  "
        f"total={len(results)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
