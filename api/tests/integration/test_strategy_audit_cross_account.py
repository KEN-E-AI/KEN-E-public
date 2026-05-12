"""Integration test: strategy_audit cross-account query via collection_group (DM-PRD-01 AC-3).

This test locks the ``collection_group("strategy_audit")`` query behaviour that goes live
in DM-PRD-01.  The query at ``audit_service.py:262`` was written for Shape B paths but
silently returned empty under Shape A.  DM-15 migrated the writers; this test asserts
the query returns all 6 entries across 2 accounts in strict timestamp-DESC order.

Note: the Firestore emulator does not enforce composite indexes, so this test passes
regardless of whether the production ``strategy_audit`` collection-group index
(``deployment/firestore.indexes.json``) is ``READY``.  The live cross-account query
with the real composite index is verified by DM-20 (dev data migration verification gate).

Enable by setting the ``FIRESTORE_EMULATOR_HOST`` environment variable:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/test_strategy_audit_cross_account.py -v
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import datetime
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Skip gate — mirrors test_migration_script_against_emulator.py:40-47 verbatim
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _firestore_client() -> Any:
    """Build a Firestore client that talks to the emulator."""
    from google.cloud import firestore  # type: ignore[import]

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return firestore.Client(project=project)


def _delete_collection(client: Any, col_ref: Any) -> None:
    """Recursively delete all docs in a collection (best-effort)."""
    try:
        for doc_ref in list(col_ref.list_documents()):
            for sub_col in doc_ref.collections():
                _delete_collection(client, sub_col)
            doc_ref.delete()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def run_id() -> str:
    """Unique suffix for each test run to prevent cross-test pollution."""
    return uuid.uuid4().hex[:8]


@pytest.fixture()
def emulator_client() -> Any:
    return _firestore_client()


@pytest.fixture(autouse=True)
def cleanup_store(emulator_client: Any, run_id: str) -> Generator[None, None, None]:
    """Delete test-owned accounts after each test.

    Targets only ``accounts/{account_id}`` documents whose ID contains ``run_id``
    so that concurrent tests and pre-existing emulator state are not disturbed.
    """
    yield

    try:
        for doc_ref in emulator_client.collection("accounts").list_documents():
            if run_id in doc_ref.id:
                for sub_col in doc_ref.collections():
                    _delete_collection(emulator_client, sub_col)
                doc_ref.delete()
    except Exception:
        pass  # Best-effort cleanup; never fail the test suite


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_get_user_activity_cross_account(
    emulator_client: Any,
    run_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``get_user_activity`` returns 6 entries across 2 accounts, sorted timestamp DESC.

    Satisfies DM-PRD-01 §6 AC-3: ``audit_service.get_user_activity(user_id)`` returns
    non-empty results for a seeded user with audit entries spread across ≥ 2 accounts.

    Timestamps are interleaved across both accounts (not all-of-A then all-of-B) to
    prove ``collection_group("strategy_audit")`` unifies both subcollections — not just
    one path.
    """
    from src.kene_api.services import audit_service

    # Rebind audit_service.db to the emulator client.  audit_service.py:20 binds
    # ``db = firestore.Client()`` at import time; if the module was imported before
    # FIRESTORE_EMULATOR_HOST was set the default binding would point at a live project.
    monkeypatch.setattr(audit_service, "db", emulator_client)

    user_id = f"user_{run_id}"
    account_a = f"acc_A_{run_id}"
    account_b = f"acc_B_{run_id}"

    # Six timestamps, interleaved: acc_A owns hours 2, 4, 6; acc_B owns hours 1, 3, 5.
    # Sorted DESC the expected order is: t6(A) > t5(B) > t4(A) > t3(B) > t2(A) > t1(B).
    base = datetime(2024, 6, 1, 0, 0, 0)
    t1 = base.replace(hour=1)
    t2 = base.replace(hour=2)
    t3 = base.replace(hour=3)
    t4 = base.replace(hour=4)
    t5 = base.replace(hour=5)
    t6 = base.replace(hour=6)

    def _seed(account_id: str, audit_id: str, ts: datetime) -> None:
        emulator_client.document(
            f"accounts/{account_id}/strategy_audit/{audit_id}"
        ).set(
            {
                "action": "viewed",
                "user_id": user_id,
                "user_email": f"{user_id}@test.example",
                "timestamp": ts,
                "doc_type": "business_strategy",
                "version": 1,
            }
        )

    # acc_A: hours 2, 4, 6
    _seed(account_a, f"aud_a1_{run_id}", t2)
    _seed(account_a, f"aud_a2_{run_id}", t4)
    _seed(account_a, f"aud_a3_{run_id}", t6)
    # acc_B: hours 1, 3, 5
    _seed(account_b, f"aud_b1_{run_id}", t1)
    _seed(account_b, f"aud_b2_{run_id}", t3)
    _seed(account_b, f"aud_b3_{run_id}", t5)

    result = await audit_service.get_user_activity(user_id, limit=100)

    # Firestore returns DatetimeWithNanoseconds (UTC-aware); seeded values are naive.
    # Strip tzinfo for a clean equality check.
    def _naive(ts: datetime) -> datetime:
        return ts.replace(tzinfo=None) if ts.tzinfo else ts

    # Single structural assertion (CLAUDE.md T-8): length, order, and user_id in one check.
    assert [(e.user_id, _naive(e.timestamp)) for e in result] == [
        (user_id, t6),  # acc_A, hour=6
        (user_id, t5),  # acc_B, hour=5
        (user_id, t4),  # acc_A, hour=4
        (user_id, t3),  # acc_B, hour=3
        (user_id, t2),  # acc_A, hour=2
        (user_id, t1),  # acc_B, hour=1
    ]
