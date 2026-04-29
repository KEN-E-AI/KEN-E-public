#!/usr/bin/env python3
"""Seed a realistic Shape B test account for local dev.

Seeds `accounts/{account_id}/...` with deterministic, idempotent fixtures.
Used by DM-PRD-01-DM-PRD-04 verification and by feature teams writing against
a known Shape B starting state.

Usage:
    python api/scripts/seed_shape_b_fixtures.py
    python api/scripts/seed_shape_b_fixtures.py --account-id custom_acc_id
    python api/scripts/seed_shape_b_fixtures.py --yes-i-know-its-not-dev  # bypass dev guard

Exit codes: 0 success, 1 failure.
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path so kene_api imports resolve
sys.path.append(str(Path(__file__).parent.parent))

from src.kene_api.firestore import get_firestore_service

# ---------------------------------------------------------------------------
# Seed payload constants — deterministic timestamps so re-runs are byte-for-byte
# identical. The account_id placeholder "{account_id}" in collection paths is
# substituted at write time by build_seed_paths().
# ---------------------------------------------------------------------------

FIXED_TS = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
FIXED_TS2 = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

# Parent account doc — provides organization_id back-reference (Shape D-aware).
# Written at accounts/{account_id}.
PARENT_ACCOUNT_SEED: dict = {
    "organization_id": "org_fixture_acme",
    "display_name": "Fixture Account (Seed)",
    "created_at": FIXED_TS,
    "updated_at": FIXED_TS,
    "is_fixture": True,
}

# strategy_docs current-version doc.
# Matches StrategyDocument field set so StrategyDocument(**payload) parses cleanly.
STRATEGY_DOCS_SEED: dict = {
    "doc_type": "business_strategy",
    "content": {
        "executive_summary": "Seed fixture — placeholder business strategy.",
        "objectives": ["Grow revenue by 20%", "Expand to new market segments"],
        "initiatives": ["Digital marketing uplift", "Partner channel activation"],
    },
    "version": 2,
    "created_at": FIXED_TS,
    "created_by": "user_seed_fixture",
    "updated_at": FIXED_TS2,
    "updated_by": "user_seed_fixture",
    "account_id": "PLACEHOLDER",  # overwritten in build_seed_payloads()
    "title": "Business Strategy 2026",
    "description": "Seed fixture for Shape B migration testing.",
    "tags": ["fixture", "seed"],
    "is_active": True,
}

# Version history payloads — two versions so has_versions=True integration tests pass.
STRATEGY_DOCS_VERSIONS_SEEDS: list[dict] = [
    {
        "doc_type": "business_strategy",
        "content": {
            "executive_summary": "Version 1 — initial draft.",
            "objectives": ["Grow revenue by 10%"],
        },
        "version": 1,
        "created_at": FIXED_TS,
        "created_by": "user_seed_fixture",
        "updated_at": FIXED_TS,
        "updated_by": "user_seed_fixture",
        "account_id": "PLACEHOLDER",
        "title": "Business Strategy 2026 — v1",
        "tags": ["fixture"],
        "is_active": False,
    },
    {
        "doc_type": "business_strategy",
        "content": {
            "executive_summary": "Version 2 — updated strategy.",
            "objectives": ["Grow revenue by 20%", "Expand to new market segments"],
        },
        "version": 2,
        "created_at": FIXED_TS2,
        "created_by": "user_seed_fixture",
        "updated_at": FIXED_TS2,
        "updated_by": "user_seed_fixture",
        "account_id": "PLACEHOLDER",
        "title": "Business Strategy 2026 — v2",
        "tags": ["fixture"],
        "is_active": True,
    },
]

# strategy_audit entries — two docs so list/query tests have ≥ 1 result.
# Matches StrategyAuditEntry field set.
STRATEGY_AUDIT_SEEDS: list[dict] = [
    {
        "action": "created",
        "user_id": "user_seed_fixture",
        "user_email": "seed@fixture.dev",
        "timestamp": FIXED_TS,
        "doc_type": "business_strategy",
        "doc_id": "business_strategy",
        "version": 1,
        "request_id": "req_seed_001",
    },
    {
        "action": "updated",
        "user_id": "user_seed_fixture",
        "user_email": "seed@fixture.dev",
        "timestamp": FIXED_TS2,
        "doc_type": "business_strategy",
        "doc_id": "business_strategy",
        "version": 2,
        "fields_modified": ["content", "title"],
        "request_id": "req_seed_002",
    },
]

# skills — minimal realistic shape.  SK-PRD-01 will redefine this payload when
# the Skills model ships; for now, this schema is documented here as the source
# of truth for the fixture until that point.
SKILLS_SEED: dict = {
    "skill_id": "skill_seed_outreach_v1",
    "name": "Outreach Playbook v1",
    "description": "Seed fixture skill for Shape B migration testing.",
    "version": 2,
    "is_active": True,
    "created_at": FIXED_TS,
    "created_by": "user_seed_fixture",
    "updated_at": FIXED_TS2,
    "updated_by": "user_seed_fixture",
    "tags": ["fixture", "outreach"],
}

SKILLS_VERSIONS_SEEDS: list[dict] = [
    {
        "skill_id": "skill_seed_outreach_v1",
        "version": 1,
        "name": "Outreach Playbook v1 — draft",
        "description": "Initial draft.",
        "is_active": False,
        "created_at": FIXED_TS,
        "created_by": "user_seed_fixture",
    },
    {
        "skill_id": "skill_seed_outreach_v1",
        "version": 2,
        "name": "Outreach Playbook v1 — published",
        "description": "Published version.",
        "is_active": True,
        "created_at": FIXED_TS2,
        "created_by": "user_seed_fixture",
    },
]


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def is_dev_project(project_id: str) -> bool:
    """Return True only when project_id ends with '-dev' (strict suffix match).

    Examples:
        is_dev_project("ken-e-dev")     → True
        is_dev_project("foo-dev")       → True
        is_dev_project("ken-e-staging") → False
        is_dev_project("ken-e-prod")    → False
        is_dev_project("dev-bucket")    → False  # 'dev' not a suffix after '-'
    """
    return project_id.endswith("-dev")


def build_seed_paths(account_id: str) -> list[tuple[str, str, dict]]:
    """Return a list of (collection_path, document_id, data) tuples to write.

    All paths are rooted under accounts/{account_id}/ — no Shape A, no Shape C.
    """
    # Resolve account_id placeholder in strategy_docs payloads
    strategy_doc = {**STRATEGY_DOCS_SEED, "account_id": account_id}
    strategy_doc_v1 = {**STRATEGY_DOCS_VERSIONS_SEEDS[0], "account_id": account_id}
    strategy_doc_v2 = {**STRATEGY_DOCS_VERSIONS_SEEDS[1], "account_id": account_id}

    base = f"accounts/{account_id}"

    return [
        # Parent account doc
        ("accounts", account_id, PARENT_ACCOUNT_SEED),
        # strategy_docs current version
        (f"{base}/strategy_docs", "business_strategy", strategy_doc),
        # strategy_docs version history
        (f"{base}/strategy_docs/business_strategy/versions", "1", strategy_doc_v1),
        (f"{base}/strategy_docs/business_strategy/versions", "2", strategy_doc_v2),
        # strategy_audit entries
        (f"{base}/strategy_audit", "audit_seed_1", STRATEGY_AUDIT_SEEDS[0]),
        (f"{base}/strategy_audit", "audit_seed_2", STRATEGY_AUDIT_SEEDS[1]),
        # skills current version
        (f"{base}/skills", "skill_seed_outreach_v1", SKILLS_SEED),
        # skills version history
        (
            f"{base}/skills/skill_seed_outreach_v1/versions",
            "1",
            SKILLS_VERSIONS_SEEDS[0],
        ),
        (
            f"{base}/skills/skill_seed_outreach_v1/versions",
            "2",
            SKILLS_VERSIONS_SEEDS[1],
        ),
    ]


# ---------------------------------------------------------------------------
# Core seeder
# ---------------------------------------------------------------------------


def seed_account(account_id: str) -> bool:
    """Write all fixture documents for account_id. Returns True on success."""
    firestore_service = get_firestore_service()

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "unknown")
    database_id = os.getenv("FIRESTORE_DATABASE_ID", "(default)")

    print(f"project_id   : {project_id}")
    print(f"database_id  : {database_id}")
    print(f"account_id   : {account_id}")
    print()

    if not firestore_service.health_check():
        print("ERROR: Firestore health check failed — cannot seed fixtures.")
        return False

    paths = build_seed_paths(account_id)
    written: list[str] = []

    for collection, doc_id, data in paths:
        try:
            firestore_service.create_document(
                collection=collection,
                document_id=doc_id,
                data=data,
            )
            full_path = f"{collection}/{doc_id}"
            written.append(full_path)
            print(f"  OK  {full_path}")
        except Exception as exc:
            print(f"  ERR {collection}/{doc_id}: {exc}")
            return False

    print()
    print(f"Seeded {len(written)} documents under accounts/{account_id}/")
    print(f"project_id={project_id}  database_id={database_id}  status=OK")
    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed a realistic Shape B test account for local dev."
    )
    parser.add_argument(
        "--account-id",
        default="test_acc_fixture",
        help="Account ID to seed under. Default: test_acc_fixture",
    )
    parser.add_argument(
        "--yes-i-know-its-not-dev",
        action="store_true",
        default=False,
        help="Bypass the -dev project guard (use with caution).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "")

    if not is_dev_project(project_id) and not args.yes_i_know_its_not_dev:
        print(
            f"ERROR: GOOGLE_CLOUD_PROJECT_ID={project_id!r} does not end with '-dev'.\n"
            "Fixtures are intended for local dev only. If you really want to run\n"
            "against this project, pass --yes-i-know-its-not-dev."
        )
        return 1

    if args.yes_i_know_its_not_dev and not is_dev_project(project_id):
        print(
            f"WARNING: Running against non-dev project {project_id!r}. "
            "Proceeding because --yes-i-know-its-not-dev was passed.\n"
        )

    print("=== seed_shape_b_fixtures ===")
    success = seed_account(args.account_id)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
