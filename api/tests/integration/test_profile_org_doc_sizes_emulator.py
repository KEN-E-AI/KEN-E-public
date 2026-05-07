"""Integration tests for profile_org_doc_sizes.py against the Firestore emulator.

These tests are skipped by default and only run when ``FIRESTORE_EMULATOR_HOST``
is set, e.g.:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/test_profile_org_doc_sizes_emulator.py -v

Covers DM-PRD-03 §6.AC-1:
- Profiling logic streams real emulator docs via _iter_org_docs()
- ProfileSummary fields are correctly computed (total_orgs, total_accounts,
  max_funnel_depth_overall, percentiles, byte_size_methodology)
- JSON output is valid and contains expected totals
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Skip gate — mirror pattern from test_migration_script_against_emulator.py
# ---------------------------------------------------------------------------
FIRESTORE_EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST")

pytestmark = pytest.mark.skipif(
    not FIRESTORE_EMULATOR_HOST,
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

# ---------------------------------------------------------------------------
# Path bootstrap — add scripts/ so profile_org_doc_sizes can be imported
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Helpers — mirror pattern from test_migration_script_against_emulator.py
# ---------------------------------------------------------------------------


def _firestore_client() -> Any:
    """Build a Firestore client that talks to the emulator."""
    from google.cloud import firestore  # type: ignore[import]

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return firestore.Client(project=project)


def _seed_doc(
    client: Any,
    collection: str,
    doc_id: str,
    data: dict[str, Any],
) -> None:
    """Seed a single document at ``{collection}/{doc_id}`` in the emulator."""
    client.collection(collection).document(doc_id).set(data)


def _delete_org_docs(client: Any, *doc_ids: str) -> None:
    """Best-effort delete of named documents from the organizations collection."""
    for doc_id in doc_ids:
        try:
            client.collection("organizations").document(doc_id).delete()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def run_id() -> str:
    """Unique suffix per test run to prevent cross-test pollution."""
    return uuid.uuid4().hex[:8]


@pytest.fixture()
def emulator_client() -> Any:
    return _firestore_client()


@pytest.fixture(autouse=True)
def cleanup_org_docs(emulator_client: Any, run_id: str) -> Generator[None, None, None]:
    """Delete test-owned organization documents after each test."""
    yield
    _delete_org_docs(
        emulator_client,
        f"org_realistic_{run_id}",
        f"org_minimal_{run_id}",
    )


# ---------------------------------------------------------------------------
# Realistic org fixture data
# ---------------------------------------------------------------------------


def _realistic_org_data() -> dict[str, Any]:
    return {
        "name": "Realistic Org",
        "agency": "Acme Agency",
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "accounts": {
            "acc_alpha": {
                "account_settings": {"overview_kpis": {"income_kpi": "m_123"}},
                "funnels": {
                    "organization": {
                        "1": {
                            "name": "Awareness",
                            "channels": {
                                "google_ads": {"tactics": {"paid_search": {}}}
                            },
                        },
                        "2": {"name": "Consideration"},
                    },
                    "big_bets": {
                        "bet_1": {
                            "1": {
                                "name": "Launch",
                                "channels": {
                                    "meta_ads": {"tactics": {"retargeting": {}}}
                                },
                            },
                            "2": {"name": "Scale"},
                            "3": {"name": "Optimize"},
                        },
                        "bet_2": {
                            "1": {"name": "Pilot"},
                        },
                    },
                },
            },
            "acc_beta": {
                "account_settings": {},
                "funnels": {"organization": {"1": {"name": "Awareness"}}},
            },
        },
    }


def _minimal_org_data() -> dict[str, Any]:
    return {
        "name": "Minimal Org",
        "created_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
        "accounts": {
            "acc_gamma": {
                "account_settings": {},
                "funnels": {},
            },
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_profile_summary_counts(emulator_client: Any, run_id: str) -> None:
    """Seed two org docs and verify ProfileSummary aggregates are correct (AC-1).

    Checks:
    - total_orgs == 2
    - total_accounts == 3 (2 from realistic + 1 from minimal)
    - both org IDs appear in summary.orgs
    - max_funnel_depth_overall >= 3 (big_bets subtree)
    - total_size_p50 > 0
    - byte_size_methodology is non-empty
    - model_dump_json() is valid JSON containing "total_orgs": 2
    """
    from profile_org_doc_sizes import (
        BYTE_SIZE_METHODOLOGY,
        OrgProfile,
        ProfileSummary,
        _iter_org_docs,
        approx_doc_bytes,
        max_funnel_depth,
        percentile,
    )

    realistic_id = f"org_realistic_{run_id}"
    minimal_id = f"org_minimal_{run_id}"

    _seed_doc(emulator_client, "organizations", realistic_id, _realistic_org_data())
    _seed_doc(emulator_client, "organizations", minimal_id, _minimal_org_data())

    # Replicate the profiling logic from main() using the real emulator client
    profiles: list[OrgProfile] = []
    all_account_byte_sizes: list[int] = []

    for org_id, doc_dict in _iter_org_docs(emulator_client):
        # Only process the docs seeded by this test run
        if org_id not in (realistic_id, minimal_id):
            continue

        byte_size = approx_doc_bytes(doc_dict)
        accounts_map: dict[str, Any] = doc_dict.get("accounts", {})
        if not isinstance(accounts_map, dict):
            accounts_map = {}

        account_count = len(accounts_map)
        per_acc_sizes: list[int] = []
        org_max_funnel_depth = 0

        for _account_id, acc_data in accounts_map.items():
            if not isinstance(acc_data, dict):
                acc_data = {}
            acc_size = approx_doc_bytes(acc_data)
            per_acc_sizes.append(acc_size)
            all_account_byte_sizes.append(acc_size)

            funnels = acc_data.get("funnels", {})
            if not isinstance(funnels, dict):
                funnels = {}
            depth = max_funnel_depth(funnels)
            if depth > org_max_funnel_depth:
                org_max_funnel_depth = depth

        max_account_byte_size = max(per_acc_sizes) if per_acc_sizes else 0

        profiles.append(
            OrgProfile(
                org_id=org_id,
                byte_size=byte_size,
                account_count=account_count,
                max_account_byte_size=max_account_byte_size,
                max_funnel_depth=org_max_funnel_depth,
            )
        )

    org_byte_sizes = [p.byte_size for p in profiles]

    _KIB_500 = 500 * 1024
    _KIB_750 = 750 * 1024

    summary = ProfileSummary(
        total_orgs=len(profiles),
        total_accounts=sum(p.account_count for p in profiles),
        total_size_p50=percentile(org_byte_sizes, 0.50),
        total_size_p95=percentile(org_byte_sizes, 0.95),
        total_size_p99=percentile(org_byte_sizes, 0.99),
        per_account_size_p50=percentile(all_account_byte_sizes, 0.50),
        per_account_size_p95=percentile(all_account_byte_sizes, 0.95),
        per_account_size_p99=percentile(all_account_byte_sizes, 0.99),
        orgs_over_500_kib=sum(1 for s in org_byte_sizes if s > _KIB_500),
        orgs_over_750_kib=sum(1 for s in org_byte_sizes if s > _KIB_750),
        accounts_over_500_kib=sum(1 for s in all_account_byte_sizes if s > _KIB_500),
        accounts_over_750_kib=sum(1 for s in all_account_byte_sizes if s > _KIB_750),
        max_funnel_depth_overall=max((p.max_funnel_depth for p in profiles), default=0),
        byte_size_methodology=BYTE_SIZE_METHODOLOGY,
        orgs=profiles,
    )

    # --- AC assertions ---

    assert summary.total_orgs == 2, (
        f"expected 2 orgs, got {summary.total_orgs}"
    )

    assert summary.total_accounts == 3, (
        f"expected 3 accounts (2 realistic + 1 minimal), got {summary.total_accounts}"
    )

    profiled_ids = {p.org_id for p in summary.orgs}
    assert realistic_id in profiled_ids, (
        f"{realistic_id!r} missing from summary.orgs: {profiled_ids}"
    )
    assert minimal_id in profiled_ids, (
        f"{minimal_id!r} missing from summary.orgs: {profiled_ids}"
    )

    assert summary.max_funnel_depth_overall >= 3, (
        f"expected max_funnel_depth_overall >= 3 (big_bets subtree), "
        f"got {summary.max_funnel_depth_overall}"
    )

    assert summary.total_size_p50 > 0, (
        "expected non-zero total_size_p50"
    )

    assert summary.byte_size_methodology, (
        "byte_size_methodology must not be empty"
    )

    # Verify JSON output is valid and contains the expected org count
    json_output = summary.model_dump_json(indent=2)
    parsed = json.loads(json_output)
    assert parsed["total_orgs"] == 2, (
        f"JSON output does not contain total_orgs==2: {json_output[:200]}"
    )
