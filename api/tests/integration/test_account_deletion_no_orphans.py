"""Integration test: recursive_delete leaves no orphaned Shape B subcollections (DM-PRD-05 AC-3/4/5).

Proves that ``DELETE /api/v1/accounts/{account_id}`` — powered by the single
``firestore.recursive_delete(accounts/{account_id})`` call shipped in DM-47 —
removes *every* Shape B subcollection.  Without this fan-out test, a future
PRD that adds an account-scoped collection outside ``accounts/{account_id}/...``
would silently orphan data on deletion (PRD §8 Risk 3).

DM-PRD-07 subcollections (``members``, ``project_plan_audit``,
``integrations_audit``) are seeded directly via the emulator client even though
no production app code writes them yet.  ``recursive_delete`` walks any
subcollection under ``accounts/{account_id}`` regardless of origin, so seeding
them now acts as a forward-looking regression guard.

Acceptance criteria covered:
  DM-PRD-05 §6 AC-3 — no Firestore documents remain under accounts/{account_id}/…
  DM-PRD-05 §6 AC-4 — GCS delete is invoked (mock-call assertion; real GCS lives in DM-55)
  DM-PRD-05 §6 AC-5 — Neo4j cascade queries run (mock-call assertion; real Neo4j lives in DM-55)

Enable by setting the ``FIRESTORE_EMULATOR_HOST`` environment variable:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/test_account_deletion_no_orphans.py -v
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.auth.models import UserContext
from src.kene_api.auth.user_context import get_current_user_context
from src.kene_api.database import get_neo4j_service
from src.kene_api.firestore import get_firestore_service
from src.kene_api.main import app
from src.kene_api.services.storage_service import get_storage_service

# ---------------------------------------------------------------------------
# Skip gate — mirrors test_agent_config_overlay.py:404-407 and
#             test_strategy_audit_cross_account.py:34-41 verbatim
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason=(
        "Firestore emulator integration tests skipped by default. "
        "Set FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 (and GOOGLE_CLOUD_PROJECT_ID=test-project) "
        "to enable. Run `gcloud emulators firestore start --host-port=127.0.0.1:8090`."
    ),
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# All Shape B subcollection names that should be reaped by recursive_delete.
# Ordered to match DM-PRD-05 §7 fixture list.
# DM-PRD-07 subcollections (members, project_plan_audit, integrations_audit) are
# seeded with minimal payloads — they will be reaped by recursive_delete regardless
# of the doc shape.  See module docstring.
_ALL_SUBCOLLECTIONS: list[str] = [
    # DM-PRD-01 — strategy suite
    "strategy_docs",
    "strategy_audit",
    "strategy_processing_state",
    # DM-PRD-02 — analytics suite
    "agent_analytics",
    "cost_aggregations",
    "performance_profiles",
    # DM-PRD-04 — shape B-like collapse
    "monitoring_topics",
    "alert_configurations",
    # DM-PRD-07 — roles / members / audit substrate (seeded as regression guard)
    "members",
    "project_plan_audit",
    "integrations_audit",
    # CH-PRD-01 — chat session side-table + artifact metadata index
    "chat_sessions",
]


def _emulator_client() -> Any:
    """Real Firestore client pointed at the local emulator."""
    from google.cloud import firestore as _fs

    project = os.environ.get("GOOGLE_CLOUD_PROJECT_ID", "test-project")
    return _fs.Client(project=project)


def _super_admin_user() -> UserContext:
    return UserContext(
        user_id="super-uid",
        email="ops@ken-e.ai",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )


def _list_subcollection_docs(db: Any, account_id: str, subcollection: str) -> list[Any]:
    """Return all doc refs under accounts/{account_id}/{subcollection}/."""
    return list(
        db.collection("accounts")
        .document(account_id)
        .collection(subcollection)
        .list_documents()
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="class")
def emulator_db() -> Any:
    """Real Firestore emulator client, shared across the test class."""
    return _emulator_client()


@pytest.fixture
def run_id() -> str:
    """Unique 8-hex suffix per test run to prevent cross-run pollution."""
    return uuid.uuid4().hex[:8]


@pytest.fixture
def account_id(run_id: str) -> str:
    """Scoped account_id: acc_orphan_{run_id}."""
    return f"acc_orphan_{run_id}"


@pytest.fixture(autouse=True)
def cleanup_emulator(emulator_db: Any, account_id: str) -> Generator[None, None, None]:
    """Best-effort cleanup of test-owned Firestore data after each test.

    Mirrors the cleanup pattern from test_strategy_audit_cross_account.py:84-100.
    Runs *after* the test so the DELETE endpoint's recursive_delete outcome is
    still verifiable inside the test body.
    """
    yield
    try:
        _recursive_delete_emulator(emulator_db, account_id)
    except Exception as exc:
        import warnings

        warnings.warn(
            f"cleanup_emulator failed for {account_id}: {exc}",
            stacklevel=2,
        )


def _recursive_delete_emulator(db: Any, account_id: str) -> None:
    """Walk and delete all docs under accounts/{account_id}/*, then the root doc."""
    account_ref = db.collection("accounts").document(account_id)
    for sub_col in account_ref.collections():
        for doc_ref in list(sub_col.list_documents()):
            # Recurse into nested subcollections (e.g. strategy_docs/swot/versions/)
            for nested in doc_ref.collections():
                for nested_doc in list(nested.list_documents()):
                    nested_doc.delete()
            doc_ref.delete()
    account_ref.delete()


@pytest.fixture
def _app_overrides(emulator_db: Any) -> Generator[dict[str, Any], None, None]:
    """Wire emulator Firestore + mocked Neo4j + mocked GCS into the FastAPI app.

    Yields a dict of the mock objects so tests can inspect call counts / args.
    Pattern mirrors TestAccountDeletionSweep._install_app_overrides in
    test_agent_config_overlay.py:423-464.
    """
    # --- Mock Neo4j ---
    # The endpoint calls: health_check(), execute_query() (account lookup),
    # and execute_write_operation() three times (cascade deletes).
    mock_neo4j = MagicMock()
    mock_neo4j.health_check = AsyncMock(return_value=True)
    # Account lookup — return one row so the endpoint does not 404.
    mock_neo4j.execute_query = AsyncMock(return_value=[{"data_region": "US"}])
    # Cascade deletes — return empty summaries (nothing deleted in Neo4j mock).
    mock_neo4j.execute_write_operation = AsyncMock(
        return_value={"nodes_deleted": 0, "relationships_deleted": 0}
    )

    async def _get_neo4j() -> Any:
        return mock_neo4j

    # --- Mock GCS ---
    mock_storage = MagicMock()
    mock_storage.delete_account_documents = AsyncMock(return_value=True)

    # --- Wire FirestoreService to use the emulator client ---
    mock_fs_service = MagicMock()
    mock_fs_service.get_client.return_value = emulator_db

    app.dependency_overrides[get_neo4j_service] = _get_neo4j
    app.dependency_overrides[get_storage_service] = lambda: mock_storage
    app.dependency_overrides[get_firestore_service] = lambda: mock_fs_service

    async def _super_admin() -> UserContext:
        return _super_admin_user()

    app.dependency_overrides[get_current_user_context] = _super_admin

    yield {"neo4j": mock_neo4j, "storage": mock_storage}

    for dep in (get_neo4j_service, get_storage_service, get_firestore_service, get_current_user_context):
        app.dependency_overrides.pop(dep, None)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_root_doc(db: Any, account_id: str) -> None:
    """Seed the accounts/{account_id} root document."""
    db.collection("accounts").document(account_id).set(
        {"account_name": "Orphan Test Account", "seeded_for": "DM-50"}
    )


def _seed_strategy_docs(db: Any, account_id: str, run_id: str) -> None:
    """Seed strategy_docs/swot + nested versions subcollection."""
    swot_ref = (
        db.collection("accounts")
        .document(account_id)
        .collection("strategy_docs")
        .document("swot")
    )
    swot_ref.set({"doc_type": "swot", "content": "SWOT content"})
    # versions subcollection — tests that recursive_delete descends one level deeper
    swot_ref.collection("versions").document(f"v1_{run_id}").set({"version": 1})
    swot_ref.collection("versions").document(f"v2_{run_id}").set({"version": 2})


def _seed_strategy_audit(db: Any, account_id: str, run_id: str) -> None:
    """Seed two strategy_audit documents."""
    base = db.collection("accounts").document(account_id).collection("strategy_audit")
    base.document(f"audit_1_{run_id}").set({"action": "viewed", "user_id": "u1"})
    base.document(f"audit_2_{run_id}").set({"action": "edited", "user_id": "u1"})


def _seed_strategy_processing_state(db: Any, account_id: str, run_id: str) -> None:
    db.collection("accounts").document(account_id).collection(
        "strategy_processing_state"
    ).document(f"state_1_{run_id}").set({"status": "pending"})


def _seed_agent_analytics(db: Any, account_id: str, run_id: str) -> None:
    base = db.collection("accounts").document(account_id).collection("agent_analytics")
    for i in (1, 2, 3):
        base.document(f"m_{i}_{run_id}").set({"metric": f"metric_{i}", "value": i})


def _seed_cost_aggregations(db: Any, account_id: str, run_id: str) -> None:
    db.collection("accounts").document(account_id).collection(
        "cost_aggregations"
    ).document(f"agg_1_{run_id}").set({"total_cost": 1.23})


def _seed_performance_profiles(db: Any, account_id: str, run_id: str) -> None:
    db.collection("accounts").document(account_id).collection(
        "performance_profiles"
    ).document(f"prof_1_{run_id}").set({"profile_name": "default"})


def _seed_monitoring_topics(db: Any, account_id: str) -> None:
    db.collection("accounts").document(account_id).collection(
        "monitoring_topics"
    ).document("default").set({"topics": [], "seeded_for": "DM-50"})


def _seed_alert_configurations(db: Any, account_id: str) -> None:
    db.collection("accounts").document(account_id).collection(
        "alert_configurations"
    ).document("default").set({"enabled": True, "seeded_for": "DM-50"})


def _seed_dm_prd_07_subcollections(db: Any, account_id: str, run_id: str) -> None:
    """Seed DM-PRD-07 subcollections with minimal payloads as a regression guard.

    Seeded with {"seeded_for": "DM-50 regression guard"} — the exact document
    shape DM-PRD-07 ships is irrelevant; recursive_delete walks the tree
    regardless of doc content.  See module docstring for rationale.
    """
    base = db.collection("accounts").document(account_id)
    # members — DM-PRD-07 §4.2
    base.collection("members").document(f"u_alice_{run_id}").set(
        {"user_id": f"u_alice_{run_id}", "seeded_for": "DM-50 regression guard"}
    )
    base.collection("members").document(f"u_bob_{run_id}").set(
        {"user_id": f"u_bob_{run_id}", "seeded_for": "DM-50 regression guard"}
    )
    # project_plan_audit — DM-PRD-07 §4.7
    base.collection("project_plan_audit").document(f"aud_1_{run_id}").set(
        {"action": "create", "seeded_for": "DM-50 regression guard"}
    )
    # integrations_audit — DM-PRD-07 §4.7
    base.collection("integrations_audit").document(f"aud_1_{run_id}").set(
        {"action": "connected", "seeded_for": "DM-50 regression guard"}
    )


def _seed_chat_sessions(db: Any, account_id: str, run_id: str) -> None:
    """Seed chat_sessions + nested artifacts subcollection (CH-PRD-01 regression guard).

    Verifies recursive_delete descends into accounts/{account_id}/chat_sessions/{id}/artifacts/*.
    """
    # CH-PRD-01
    session_ref = (
        db.collection("accounts")
        .document(account_id)
        .collection("chat_sessions")
        .document(f"sess_{run_id}")
    )
    session_ref.set(
        {"user_id": "u_test", "account_id": account_id, "seeded_for": "CH-9 regression guard"}
    )
    # Nested artifacts subcollection — proves recursive_delete descends two levels deep
    session_ref.collection("artifacts").document(f"art_{run_id}").set(
        {"filename": "test.pdf", "seeded_for": "CH-9 regression guard"}
    )


def _seed_full_account(db: Any, account_id: str, run_id: str) -> None:
    """Seed the complete DM-PRD-05 §7 fixture set under accounts/{account_id}."""
    _seed_root_doc(db, account_id)
    _seed_strategy_docs(db, account_id, run_id)
    _seed_strategy_audit(db, account_id, run_id)
    _seed_strategy_processing_state(db, account_id, run_id)
    _seed_agent_analytics(db, account_id, run_id)
    _seed_cost_aggregations(db, account_id, run_id)
    _seed_performance_profiles(db, account_id, run_id)
    _seed_monitoring_topics(db, account_id)
    _seed_alert_configurations(db, account_id)
    _seed_dm_prd_07_subcollections(db, account_id, run_id)
    _seed_chat_sessions(db, account_id, run_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAccountDeletionNoOrphans:
    """Integration tests: DELETE /api/v1/accounts/{id} leaves no Firestore orphans.

    Fires the real endpoint against the Firestore emulator (Neo4j + GCS mocked).
    Every Shape B subcollection from DM-PRD-01/02/03/04 plus the three
    DM-PRD-07-owned subcollections are seeded before each test.

    AC-3: no documents remain under accounts/{account_id}/… after DELETE.
    AC-4: GCS delete_account_documents was called with (account_id, "US").
    AC-5: Neo4j cascade execute_write_operation was called exactly 3 times.
    """

    def test_recursive_delete_clears_all_shape_b_subcollections_and_root(
        self,
        emulator_db: Any,
        account_id: str,
        run_id: str,
        client: TestClient,
        _app_overrides: dict[str, Any],
    ) -> None:
        """Happy path: every seeded Shape B subcollection is empty after DELETE.

        DM-PRD-05 §6 AC-3, AC-4, AC-5.
        """
        _seed_full_account(emulator_db, account_id, run_id)

        # Seed a sibling account before DELETE to verify isolation (checked below).
        sibling_ref = emulator_db.collection("accounts").document(f"acc_sibling_{run_id}")
        sibling_ref.set({"sentinel": True})

        # --- Act ---
        resp = client.delete(f"/api/v1/accounts/{account_id}")

        # --- Assert: response body (per PRD §7) ---
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data == {
            "account_id": account_id,
            "nodes_deleted": 0,
            "relationships_deleted": 0,
            "gcs_documents_deleted": 1,
            "firestore_account_deleted": True,
            "cleanup_errors": [],
            "data_region": "US",
        }, f"Unexpected response body: {data}"

        # --- Assert: all Shape B subcollections are empty (AC-3) ---
        remaining: dict[str, list[str]] = {}
        for subcollection in _ALL_SUBCOLLECTIONS:
            docs = _list_subcollection_docs(emulator_db, account_id, subcollection)
            if docs:
                remaining[subcollection] = [d.id for d in docs]

        # Single structural assertion (CLAUDE.md T-8)
        assert remaining == {}, (
            f"recursive_delete left orphaned docs in subcollections: {remaining}"
        )

        # Root account doc must also be gone
        root = emulator_db.collection("accounts").document(account_id).get()
        assert not root.exists, (
            f"Root accounts/{account_id} document still exists after DELETE"
        )

        # --- Assert: GCS was called (AC-4) ---
        # Real GCS verification lives in DM-55 (staging).  Here we verify the
        # endpoint passed the correct arguments to the delete helper.
        _app_overrides["storage"].delete_account_documents.assert_called_once_with(
            account_id, "US"
        )

        # --- Assert: Neo4j cascade ran (AC-5) ---
        # Real Neo4j verification lives in DM-55 (staging).  Here we verify the
        # three cascade write queries were issued against the mock.
        assert _app_overrides["neo4j"].execute_write_operation.call_count == 3, (
            f"Expected 3 Neo4j cascade writes, got "
            f"{_app_overrides['neo4j'].execute_write_operation.call_count}"
        )

        # --- Assert: sibling account is untouched ---
        # Guards against an over-broad recursive_delete that might walk the entire
        # `accounts/` collection instead of just `accounts/{account_id}/`.
        try:
            sibling_doc = sibling_ref.get()
            assert sibling_doc.exists, (
                "recursive_delete must not touch sibling accounts: "
                f"acc_sibling_{run_id} was deleted"
            )
        finally:
            sibling_ref.delete()

    def test_recursive_delete_on_empty_account_reports_success_with_no_errors(
        self,
        emulator_db: Any,
        account_id: str,
        client: TestClient,
        _app_overrides: dict[str, Any],
    ) -> None:
        """Regression: DELETE on a non-existent / empty account still reports success.

        Mirrors test_recursive_delete_with_no_account_data_reports_success in
        test_agent_config_overlay.py:569-579.  Pins the failure mode where
        recursive_delete raises on a non-existent root doc — the endpoint must
        still return 200 with firestore_account_deleted=True and cleanup_errors=[].
        """
        # Act — no seeding; account does not exist in Firestore
        resp = client.delete(f"/api/v1/accounts/{account_id}")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["firestore_account_deleted"] is True
        assert data["cleanup_errors"] == []

    def test_non_admin_cannot_delete_account(
        self,
        account_id: str,
        client: TestClient,
        _app_overrides: dict[str, Any],
    ) -> None:
        """Authorization: a non-super-admin caller receives 403.

        Pins the single authorization gate at accounts.py:928
        (``if not user.is_super_admin: raise HTTPException(403)``).
        If that check is removed or weakened, this test fails.
        """
        regular_user = UserContext(
            user_id="attacker-uid",
            email="attacker@external.com",
            organization_permissions={},
            account_permissions={},
        )
        # Override only the auth dependency; leave Neo4j/GCS/Firestore mocks active.
        app.dependency_overrides[get_current_user_context] = lambda: regular_user
        try:
            resp = client.delete(f"/api/v1/accounts/{account_id}")
            assert resp.status_code == 403
        finally:
            # Restore the super-admin override so teardown sees the right auth.
            async def _super_admin() -> UserContext:
                return _super_admin_user()

            app.dependency_overrides[get_current_user_context] = _super_admin
