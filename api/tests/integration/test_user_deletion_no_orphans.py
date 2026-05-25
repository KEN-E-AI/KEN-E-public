"""Integration test: user-data purge leaves no orphaned docs (DM-PRD-05 AC-9, AC-10).

Proves that ``DELETE /api/v1/users/{user_id}`` — powered by the
``delete_user_data(user_id, actor=...)`` orchestrator shipped in DM-52 —
sweeps cross-account/org ``members`` rows, fires the IN-PRD-05
``on_user_removed`` hook the right number of times, and purges
``users/{user_id}`` plus every registered user-scoped subcollection.

Acceptance criteria covered:
  DM-PRD-05 §6 AC-9  — 2-org x 3-account sweep + hook count + residue check
  DM-PRD-05 §6 AC-10 — idempotent re-run returns zero counts + empty errors

Fixture topology (all IDs carry a per-run suffix to prevent cross-test pollution):

    organizations/
        org_acme_{run_id}/members/u_carol_{run_id}     (role=member)
        org_widgets_{run_id}/members/u_carol_{run_id}  (role=admin)
    accounts/
        acc_acme_a_{run_id}/members/u_carol_{run_id}   (role=editor)
        acc_acme_b_{run_id}/members/u_carol_{run_id}   (role=viewer)
        acc_widgets_main_{run_id}/members/u_carol_{run_id} (role=admin)
        acc_acme_a_{run_id}/platform_connections/conn_ga   (stub token)
        acc_acme_b_{run_id}/platform_connections/conn_ga
        acc_widgets_main_{run_id}/platform_connections/conn_ga
    users/
        u_carol_{run_id}                               (root doc)
        u_carol_{run_id}/notification_status/n_1, n_2
        u_carol_{run_id}/preferences/notifications
        u_carol_{run_id}/chat_categories/cat_research, cat_outreach, cat_admin

Architecture decisions (see Implementation Plan comment on DM-54):
* Patch ``src.kene_api.services.user_deletion_service._on_user_removed`` and
  ``src.kene_api.services.user_deletion_service._write_audit`` at module
  attribute scope — those are the exact symbols the orchestrator reads at
  call time.
* Real Firestore emulator for collection-group queries and recursive_delete;
  everything else mocked (no Neo4j or GCS involvement in user deletion).
* platform_connections rows are NOT asserted-as-deleted — IN-PRD-05's real
  hook owns that; this test only asserts the hook fired with the right args.
* Audit assertion is mock-call inspection (not Firestore-doc lookup) because
  _write_audit is None until DM-PRD-07 ships; the patched AsyncMock captures
  the call args as a proxy for the eventual doc shape.

Enable by setting the ``FIRESTORE_EMULATOR_HOST`` environment variable:

    gcloud emulators firestore start --host-port=127.0.0.1:8090 &
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8090 \\
    GOOGLE_CLOUD_PROJECT_ID=test-project \\
    pytest api/tests/integration/test_user_deletion_no_orphans.py -v
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import src.kene_api.services.user_deletion_service as _svc_module
from fastapi.testclient import TestClient
from src.kene_api.auth.dependencies import get_current_user
from src.kene_api.auth.models import UserContext
from src.kene_api.firestore import get_firestore_service
from src.kene_api.main import app
from src.kene_api.services.user_deletion_service import USER_SUBCOLLECTIONS

# CH-9 invariant: chat_categories must be in USER_SUBCOLLECTIONS so the
# user-deletion sweep covers it. This assertion runs at import time and fails
# loudly if a future refactor removes the entry from the registry.
assert "chat_categories" in USER_SUBCOLLECTIONS, (
    "chat_categories must be registered in USER_SUBCOLLECTIONS "
    "(api/src/kene_api/services/user_deletion_service.py) — "
    "removing it would orphan users/{user_id}/chat_categories/* on user deletion"
)

# ---------------------------------------------------------------------------
# Skip gate — identical to test_account_deletion_no_orphans.py
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


def _list_docs_at(db: Any, *path_parts: str) -> list[Any]:
    """Return all doc refs at the collection path given by alternating path parts.

    path_parts must be an even number of (collection, document) pairs except
    for the final collection segment:
      ("users", "u_carol", "notification_status")  → lists users/u_carol/notification_status/*
    """
    ref: Any = db
    for i, part in enumerate(path_parts):
        if i % 2 == 0:
            ref = ref.collection(part)
        else:
            ref = ref.document(part)
    return list(ref.list_documents())


def _recursive_delete_emulator(db: Any, collection: str, doc_id: str) -> None:
    """Best-effort two-level recursive delete for a single doc + subcollections.

    Handles root → subcollection → sub-subcollection depth (sufficient for test
    cleanup).  Does NOT call Firestore's server-side ``recursive_delete`` — this
    is a client-side loop used only for emulator cleanup between test runs.
    """
    root_ref = db.collection(collection).document(doc_id)
    for sub_col in root_ref.collections():
        for doc_ref in list(sub_col.list_documents()):
            for nested in doc_ref.collections():
                for nested_doc in list(nested.list_documents()):
                    nested_doc.delete()
            doc_ref.delete()
    root_ref.delete()


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
def user_id(run_id: str) -> str:
    return f"u_carol_{run_id}"


@pytest.fixture
def org_acme_id(run_id: str) -> str:
    return f"org_acme_{run_id}"


@pytest.fixture
def org_widgets_id(run_id: str) -> str:
    return f"org_widgets_{run_id}"


@pytest.fixture
def acc_acme_a_id(run_id: str) -> str:
    return f"acc_acme_a_{run_id}"


@pytest.fixture
def acc_acme_b_id(run_id: str) -> str:
    return f"acc_acme_b_{run_id}"


@pytest.fixture
def acc_widgets_main_id(run_id: str) -> str:
    return f"acc_widgets_main_{run_id}"


@pytest.fixture(autouse=True)
def cleanup_emulator(
    emulator_db: Any,
    user_id: str,
    org_acme_id: str,
    org_widgets_id: str,
    acc_acme_a_id: str,
    acc_acme_b_id: str,
    acc_widgets_main_id: str,
) -> Generator[None, None, None]:
    """Best-effort cleanup of all test-owned Firestore data before and after each test.

    The pre-test pass removes any stale data from a previous failed run so that
    fixture seeding starts from a clean slate.  The post-test pass removes data
    left behind by a test that ended early (e.g. assertion failure before the
    DELETE request).
    """
    _cleanup_docs = [
        ("users", user_id),
        ("organizations", org_acme_id),
        ("organizations", org_widgets_id),
        ("accounts", acc_acme_a_id),
        ("accounts", acc_acme_b_id),
        ("accounts", acc_widgets_main_id),
    ]
    # Pre-test: clear any stale state from a prior failed run
    for col, doc_id in _cleanup_docs:
        try:
            _recursive_delete_emulator(emulator_db, col, doc_id)
        except Exception:
            pass

    yield

    for col, doc_id in _cleanup_docs:
        try:
            _recursive_delete_emulator(emulator_db, col, doc_id)
        except Exception as exc:
            import warnings

            warnings.warn(
                f"cleanup_emulator failed for {col}/{doc_id}: {exc}", stacklevel=2
            )


@pytest.fixture
def mock_on_user_removed() -> AsyncMock:
    """AsyncMock for the integrations on_user_removed hook."""
    return AsyncMock(return_value=None)


@pytest.fixture
def mock_write_audit() -> AsyncMock:
    """AsyncMock for the DM-PRD-07 write_audit helper."""
    return AsyncMock(return_value=None)


@pytest.fixture
def _app_overrides(
    emulator_db: Any,
    mock_on_user_removed: AsyncMock,
    mock_write_audit: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[dict[str, Any], None, None]:
    """Wire emulator Firestore + mocked auth + patched module-level hooks.

    The orchestrator reads ``_on_user_removed`` and ``_write_audit`` from
    its own module namespace at call time.  Patching the module attributes
    is the correct seam — patching the original import locations has no
    effect because the module already bound those names at import time.
    """
    # Patch module-level hook aliases in user_deletion_service.
    # Must be done before the app processes any request.
    monkeypatch.setattr(_svc_module, "_on_user_removed", mock_on_user_removed)
    monkeypatch.setattr(_svc_module, "_write_audit", mock_write_audit)

    # Patch get_firestore_client — the orchestrator resolves this LRU-cached singleton
    # directly at service.py:336 (``db = get_firestore_client()``), NOT through FastAPI
    # dependency injection, so overriding the DI dep has no effect on it.  Patching the
    # module attribute is the correct seam.
    monkeypatch.setattr(_svc_module, "get_firestore_client", lambda: emulator_db)

    # Wire FirestoreService to use the emulator client (for any router-layer usages).
    mock_fs_service = MagicMock()
    mock_fs_service.get_client.return_value = emulator_db

    app.dependency_overrides[get_firestore_service] = lambda: mock_fs_service

    async def _super_admin() -> UserContext:
        return _super_admin_user()

    app.dependency_overrides[get_current_user] = _super_admin

    yield {
        "on_user_removed": mock_on_user_removed,
        "write_audit": mock_write_audit,
    }

    for dep in (get_firestore_service, get_current_user):
        app.dependency_overrides.pop(dep, None)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_user_doc_and_subcollections(
    db: Any,
    user_id: str,
    run_id: str,
) -> None:
    """Seed users/{user_id} root doc + all registered user-scoped subcollections."""
    user_ref = db.collection("users").document(user_id)
    user_ref.set({"email": f"{user_id}@example.com", "seeded_for": "DM-54"})

    # notification_status — firestore_notification_repository.py
    notif = user_ref.collection("notification_status")
    notif.document(f"n_1_{run_id}").set({"type": "mention", "read": False})
    notif.document(f"n_2_{run_id}").set({"type": "comment", "read": True})

    # preferences — firestore_notification_repository.py
    user_ref.collection("preferences").document("notifications").set(
        {"email_enabled": True, "push_enabled": False}
    )

    # chat_categories — CH-PRD-03
    cats = user_ref.collection("chat_categories")
    cats.document(f"cat_research_{run_id}").set({"name": "Research"})
    cats.document(f"cat_outreach_{run_id}").set({"name": "Outreach"})
    cats.document(f"cat_admin_{run_id}").set({"name": "Admin"})

    # notifications — routers/users.py NotificationSettings seed
    user_ref.collection("notifications").document("settings").set(
        {"muted": False, "seeded_for": "DM-54"}
    )

    # security — routers/users.py SecuritySettings seed
    user_ref.collection("security").document("settings").set(
        {"two_fa_enabled": False, "seeded_for": "DM-54"}
    )

    # Drift guard: seed a sentinel doc into EVERY registered user-scoped
    # subcollection, driven from USER_SUBCOLLECTIONS itself. Without this, a
    # future PR that appends a name to the registry without extending the sweep
    # would still pass the post-deletion residue check — the new subcollection
    # would be trivially empty because nothing ever seeded it.
    for subcol_name in USER_SUBCOLLECTIONS:
        user_ref.collection(subcol_name).document(f"sentinel_{run_id}").set(
            {"registry_sentinel": True}
        )


def _seed_org_member(
    db: Any,
    org_id: str,
    user_id: str,
    role: str,
) -> None:
    """Seed organizations/{org_id}/members/{user_id}."""
    db.collection("organizations").document(org_id).collection("members").document(
        user_id
    ).set({"user_id": user_id, "role": role, "parent_kind": "organization"})


def _seed_account_member(
    db: Any,
    account_id: str,
    user_id: str,
    role: str,
) -> None:
    """Seed accounts/{account_id}/members/{user_id}."""
    db.collection("accounts").document(account_id).collection("members").document(
        user_id
    ).set({"user_id": user_id, "role": role, "parent_kind": "account"})


def _seed_platform_connection(
    db: Any,
    account_id: str,
    connection_id: str,
) -> None:
    """Seed a stub platform_connections doc (survives deletion — owned by IN-PRD-05 hook)."""
    db.collection("accounts").document(account_id).collection(
        "platform_connections"
    ).document(connection_id).set(
        {"platform": "google_ads", "status": "active", "seeded_for": "DM-54"}
    )


def _seed_full_fixture(
    db: Any,
    user_id: str,
    run_id: str,
    org_acme_id: str,
    org_widgets_id: str,
    acc_acme_a_id: str,
    acc_acme_b_id: str,
    acc_widgets_main_id: str,
) -> None:
    """Seed the complete DM-PRD-05 §7 user-deletion fixture set."""
    _seed_user_doc_and_subcollections(db, user_id, run_id)
    _seed_org_member(db, org_acme_id, user_id, "member")
    _seed_org_member(db, org_widgets_id, user_id, "admin")
    _seed_account_member(db, acc_acme_a_id, user_id, "editor")
    _seed_account_member(db, acc_acme_b_id, user_id, "viewer")
    _seed_account_member(db, acc_widgets_main_id, user_id, "admin")
    # platform_connections — stub tokens (reaped by the hook, not the orchestrator)
    _seed_platform_connection(db, acc_acme_a_id, "conn_ga")
    _seed_platform_connection(db, acc_acme_b_id, "conn_ga")
    _seed_platform_connection(db, acc_widgets_main_id, "conn_ga")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUserDeletionNoOrphans:
    """Integration tests: DELETE /api/v1/users/{user_id} leaves no Firestore orphans.

    AC-9: full sweep (2 orgs x 3 accounts, chat categories, notifications, hook count).
    AC-10: idempotent re-run returns zero counts and an empty errors list.
    """

    def test_user_deletion_full_sweep_no_orphans(
        self,
        emulator_db: Any,
        run_id: str,
        user_id: str,
        org_acme_id: str,
        org_widgets_id: str,
        acc_acme_a_id: str,
        acc_acme_b_id: str,
        acc_widgets_main_id: str,
        client: TestClient,
        _app_overrides: dict[str, Any],
    ) -> None:
        """Happy path: every seeded fixture is gone after DELETE, hook fired 3 times.

        DM-PRD-05 §6 AC-9.
        """
        _seed_full_fixture(
            emulator_db,
            user_id,
            run_id,
            org_acme_id,
            org_widgets_id,
            acc_acme_a_id,
            acc_acme_b_id,
            acc_widgets_main_id,
        )

        # --- Act ---
        resp = client.delete(f"/api/v1/users/{user_id}")

        # --- Assert: response body ---
        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "user_id": user_id,
            "member_rows_deleted": 5,
            "integrations_hook_fired": 3,
            "user_doc_deleted": True,
            "gcs_prefixes_purged": 0,
            "errors": [],
        }, f"Unexpected response body: {body}"

        # --- Assert: on_user_removed fired exactly 3 times with correct account_ids ---
        mock = _app_overrides["on_user_removed"]
        assert mock.await_count == 3, (
            f"Expected on_user_removed to be called 3 times, got {mock.await_count}"
        )
        called_account_ids = {c.kwargs["account_id"] for c in mock.await_args_list}
        assert called_account_ids == {
            acc_acme_a_id,
            acc_acme_b_id,
            acc_widgets_main_id,
        }, f"on_user_removed called with unexpected account_ids: {called_account_ids}"
        # Each account fires exactly once
        for c in mock.await_args_list:
            assert c.kwargs.get("user_id") == user_id, (
                f"on_user_removed called with wrong user_id: {c.kwargs}"
            )

        # --- Assert: write_audit fired once for the org-level audit ---
        audit_mock = _app_overrides["write_audit"]
        assert audit_mock.await_count == 1, (
            f"Expected write_audit called once, got {audit_mock.await_count}"
        )
        audit_call = audit_mock.await_args_list[0]
        assert audit_call.kwargs.get("parent_kind") == "organization", (
            f"Expected parent_kind='organization', got: {audit_call.kwargs}"
        )
        # parent_id is non-deterministic: the orchestrator picks the first org returned by
        # the collection-group query (``org_refs[0]``).  Firestore does not guarantee order,
        # so we assert membership in the expected org set rather than an exact value.
        assert audit_call.kwargs.get("parent_id") in {org_acme_id, org_widgets_id}, (
            f"Expected parent_id in org set, got: {audit_call.kwargs.get('parent_id')}"
        )
        assert audit_call.kwargs.get("audit_subcollection") == "account_member_audit", (
            f"Expected audit_subcollection='account_member_audit', got: {audit_call.kwargs}"
        )
        assert audit_call.kwargs.get("action") == "remove", (
            f"Expected action='remove', got: {audit_call.kwargs.get('action')}"
        )

        # --- Assert: users/{user_id} root doc is gone ---
        root = emulator_db.collection("users").document(user_id).get()
        assert not root.exists, (
            f"Root users/{user_id} document still exists after DELETE"
        )

        # --- Assert: all user-scoped subcollections are empty ---
        remaining_user_subcols: dict[str, list[str]] = {}
        for subcol_name in USER_SUBCOLLECTIONS:
            docs = _list_docs_at(emulator_db, "users", user_id, subcol_name)
            if docs:
                remaining_user_subcols[subcol_name] = [d.id for d in docs]
        assert remaining_user_subcols == {}, (
            f"recursive_delete left orphaned docs in user subcollections: {remaining_user_subcols}"
        )

        # --- Assert: org members rows are gone ---
        remaining_org_members: dict[str, bool] = {}
        for org_id in (org_acme_id, org_widgets_id):
            docs = _list_docs_at(emulator_db, "organizations", org_id, "members")
            matching = [d for d in docs if d.id == user_id]
            if matching:
                remaining_org_members[org_id] = True
        assert remaining_org_members == {}, (
            f"org member rows remain after DELETE: {remaining_org_members}"
        )

        # --- Assert: account member rows are gone ---
        remaining_account_members: dict[str, bool] = {}
        for acc_id in (acc_acme_a_id, acc_acme_b_id, acc_widgets_main_id):
            docs = _list_docs_at(emulator_db, "accounts", acc_id, "members")
            matching = [d for d in docs if d.id == user_id]
            if matching:
                remaining_account_members[acc_id] = True
        assert remaining_account_members == {}, (
            f"account member rows remain after DELETE: {remaining_account_members}"
        )

    def test_user_deletion_idempotent_on_purged_user(
        self,
        emulator_db: Any,
        run_id: str,
        user_id: str,
        org_acme_id: str,
        org_widgets_id: str,
        acc_acme_a_id: str,
        acc_acme_b_id: str,
        acc_widgets_main_id: str,
        client: TestClient,
        _app_overrides: dict[str, Any],
    ) -> None:
        """Re-running DELETE on an already-purged user is a zero-count no-op.

        DM-PRD-05 §6 AC-10.
        """
        _seed_full_fixture(
            emulator_db,
            user_id,
            run_id,
            org_acme_id,
            org_widgets_id,
            acc_acme_a_id,
            acc_acme_b_id,
            acc_widgets_main_id,
        )

        # First call — drains all state
        resp1 = client.delete(f"/api/v1/users/{user_id}")
        assert resp1.status_code == 200

        # Record on_user_removed call count after first call; second call must not add more
        mock = _app_overrides["on_user_removed"]
        count_after_first = mock.await_count

        # Second call — all data already gone
        resp2 = client.delete(f"/api/v1/users/{user_id}")

        # --- Assert: second call response ---
        assert resp2.status_code == 200
        body = resp2.json()
        assert body == {
            "user_id": user_id,
            "member_rows_deleted": 0,
            "integrations_hook_fired": 0,
            "user_doc_deleted": True,
            "gcs_prefixes_purged": 0,
            "errors": [],
        }, f"Idempotent re-run returned unexpected body: {body}"

        # --- Assert: hook not fired again on second call ---
        assert mock.await_count == count_after_first, (
            f"on_user_removed was called again on idempotent re-run: "
            f"count before={count_after_first}, count after={mock.await_count}"
        )

        # --- Assert: Firestore still has no residue after second call ---
        root = emulator_db.collection("users").document(user_id).get()
        assert not root.exists, (
            f"users/{user_id} root doc re-appeared after idempotent re-run"
        )
        still_present: dict[str, list[str]] = {}
        for subcol_name in USER_SUBCOLLECTIONS:
            docs = _list_docs_at(emulator_db, "users", user_id, subcol_name)
            if docs:
                still_present[subcol_name] = [d.id for d in docs]
        assert still_present == {}, (
            f"User subcollections still contain docs after idempotent re-run: {still_present}"
        )

    def test_non_admin_cannot_delete_user(
        self,
        user_id: str,
        client: TestClient,
        _app_overrides: dict[str, Any],
    ) -> None:
        """Authorization: a non-super-admin caller receives 403.

        Pins the single authorization gate at users.py ``require_super_admin`` dep
        and the ``if not actor.is_super_admin`` check in user_deletion_service.py:327.
        If either check is removed or weakened, this test fails.

        DM-PRD-05 §4.3 AC-8.
        """
        regular_user = UserContext(
            user_id="attacker-uid",
            email="attacker@external.com",
            organization_permissions={},
            account_permissions={},
        )
        # Temporarily override auth to a non-super-admin; leave other mocks active.
        app.dependency_overrides[get_current_user] = lambda: regular_user
        try:
            resp = client.delete(f"/api/v1/users/{user_id}")
            assert resp.status_code == 403
            assert resp.json() == {"error": "super_admin_required"}
        finally:
            # Restore the super-admin override so teardown sees the right auth.
            async def _super_admin() -> UserContext:
                return _super_admin_user()

            app.dependency_overrides[get_current_user] = _super_admin

    def test_user_deletion_partial_hook_failure(
        self,
        emulator_db: Any,
        run_id: str,
        user_id: str,
        org_acme_id: str,
        org_widgets_id: str,
        acc_acme_a_id: str,
        acc_acme_b_id: str,
        acc_widgets_main_id: str,
        client: TestClient,
        _app_overrides: dict[str, Any],
    ) -> None:
        """One of three on_user_removed calls raises; the purge still completes.

        The orchestrator captures the hook failure into result.errors and keeps
        going — member rows and the user doc are still purged, and the two
        non-failing hooks still count. This is the most realistic production
        failure mode: a single account's integration teardown timing out.
        """
        _seed_full_fixture(
            emulator_db,
            user_id,
            run_id,
            org_acme_id,
            org_widgets_id,
            acc_acme_a_id,
            acc_acme_b_id,
            acc_widgets_main_id,
        )

        # Middle hook call raises; first and third succeed.
        mock = _app_overrides["on_user_removed"]
        mock.side_effect = [None, RuntimeError("integration teardown boom"), None]

        resp = client.delete(f"/api/v1/users/{user_id}")

        assert resp.status_code == 200
        body = resp.json()
        # Two hooks succeeded; the failed one is recorded, not counted.
        assert body["integrations_hook_fired"] == 2, body
        # The member sweep is independent of the hook step — all 5 rows gone.
        assert body["member_rows_deleted"] == 5, body
        assert body["user_doc_deleted"] is True, body
        # Exactly one structured hook error captured, carrying the raised message.
        hook_errors = [e for e in body["errors"] if e.startswith("integrations_hook[")]
        assert len(hook_errors) == 1, body["errors"]
        assert "integration teardown boom" in hook_errors[0]

        # Root user doc is gone despite the partial hook failure.
        root = emulator_db.collection("users").document(user_id).get()
        assert not root.exists, (
            f"users/{user_id} root doc survived a partial hook failure"
        )
