#!/usr/bin/env python3
"""Seed feature flags into Firestore.

Registers platform-level feature flags. Currently includes:

- ``rate_limit_backend_override`` (AH-71): emergency rollback to in-process
  rate limiting when Redis is unavailable. Registered in
  ``SECURITY_CRITICAL_FLAGS`` (feature_flags/security_critical.py) so any
  write through the admin UI fires the AH-79 audit-log + Cloud Monitoring
  counter hooks automatically.

- ``invite_only_signup`` (DM-PRD-11): global toggle for the Early Release
  signup gate. Ships dark (``is_active=True, default_enabled=False``); flip
  ``default_enabled`` via the admin UI to enforce invite-only onboarding.

Usage:
    python api/scripts/seed_feature_flags.py
    python api/scripts/seed_feature_flags.py --dry-run
    python api/scripts/seed_feature_flags.py --yes-i-know-its-not-dev  # bypass dev guard

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
# Flag registry
# ---------------------------------------------------------------------------

FLAGS_TO_REGISTER: list[FeatureFlagWriteRequest] = [
    FeatureFlagWriteRequest(
        key="rate_limit_backend_override",
        description=(
            "Runtime override forcing all rate limiters onto LocalRateLimiter "
            "(per-instance memory) regardless of KENE_RATE_LIMIT_BACKEND. "
            "CRITICAL — flag-flip emits CRITICAL audit log + Cloud Monitoring counter. "
            "Use only as an emergency rollback when Redis is causing widespread 429s. "
            "Registered in SECURITY_CRITICAL_FLAGS (feature_flags/security_critical.py)."
        ),
        default_enabled=False,
        is_active=False,
        bucketing_entity="account",
        owner="agentic-harness@ken-e.ai",
    ),
    FeatureFlagWriteRequest(
        key="invite_only_signup",
        description=(
            "When ON, new users can only onboard via an org invitation or a valid "
            "Early Release code. Ships dark (default_enabled=False). Do NOT add "
            "targeting rules — staff bypass lives in the org-creation predicate, not "
            "here (see DM-PRD-11 §4.4 and feature-flags/README.md §7.6)."
        ),
        default_enabled=False,
        is_active=True,
        bucketing_entity="account",
        owner="data-management@ken-e.ai",
    ),
]

_ACTOR_EMAIL = "system+seed-feature-flags@ken-e.ai"


# ---------------------------------------------------------------------------
# Core seed logic
# ---------------------------------------------------------------------------


async def _seed_flags(db: object, dry_run: bool) -> dict[str, str]:
    """Create all registered feature flags.  Returns {key: outcome}."""
    service = FeatureFlagService(db=db)
    results: dict[str, str] = {}
    for req in FLAGS_TO_REGISTER:
        if dry_run:
            print(
                f"  [DRY RUN] would create: {req.key!r} "
                f"(default_enabled={req.default_enabled}, is_active={req.is_active})"
            )
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
# Dev-project guard (mirrors seed_chat_feature_flags.py)
# ---------------------------------------------------------------------------


def _is_dev_project(project_id: str) -> bool:
    return project_id.endswith("-dev") or project_id in {"test-project", ""}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed platform feature flags into Firestore (idempotent)."
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

    print("=== seed_feature_flags ===")
    print(f"project_id : {project_id or '(not set)'}")
    print(f"dry_run    : {args.dry_run}")
    print(f"flags      : {[f.key for f in FLAGS_TO_REGISTER]}")
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
