"""Unit tests for the delete_user_data orchestrator (DM-52).

Coverage matrix per the Implementation Plan:
  (a) happy path — 2 org-member refs + 3 account-member refs; all 6 steps fire
  (b) idempotent re-run — zero refs; recursive_delete is still called; counts=0
  (b2) step-1 failure — _resolve_member_rows raises; subsequent steps still run
  (c) single-step failure — step 4 raises; subsequent steps still run
  (d) no org membership — only account-scope refs; audit step is NOT called
  (e) hook absent — on_user_removed is None; no raise, integrations_hook_fired=0
  (f) write_audit absent — _write_audit is None; audit step is a no-op
  (g) hook raises — on_user_removed raises; errors recorded, deletion continues
  (h) non-super-admin actor raises SuperAdminRequiredError before any I/O

All tests are hermetic — no live Firestore connection.  The Firestore client
and StorageService are replaced with MagicMock / AsyncMock throughout.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import src.kene_api.services.user_deletion_service as svc
from src.kene_api.auth.dependencies import SuperAdminRequiredError
from src.kene_api.auth.models import UserContext
from src.kene_api.models.user_deletion import UserDeletionResult

# ---------------------------------------------------------------------------
# Module-level hermetic guard — prevents any test from reaching a real
# StorageService when USER_GCS_PREFIXES is non-empty in the future.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_get_storage_service():
    with patch.object(svc, "get_storage_service", return_value=MagicMock()):
        yield


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_actor(
    email: str = "admin@ken-e.ai", roles: list[str] | None = None
) -> UserContext:
    return UserContext(
        user_id="u_admin",
        email=email,
        organization_permissions={},
        account_permissions={},
        roles=roles if roles is not None else ["super_admin"],
    )


def _make_doc_ref(path: str) -> MagicMock:
    """Return a DocumentReference-like mock with .path, .delete(), and .parent.parent.id."""
    ref = MagicMock()
    ref.path = path
    ref.delete = MagicMock(return_value=None)

    # Build the parent chain: ref.parent.parent.id
    # For org members:     organizations/{org_id}/members/{user_id}
    # For account members: accounts/{account_id}/members/{user_id}
    parts = path.split("/")
    # parts[0] = collection root (organizations / accounts)
    # parts[1] = parent_id
    parent_id = parts[1] if len(parts) >= 2 else "unknown"

    grandparent = MagicMock()
    grandparent.id = parent_id
    parent = MagicMock()
    parent.parent = grandparent
    ref.parent = parent

    return ref


def _make_org_ref(org_id: str, user_id: str = "u_carol") -> MagicMock:
    return _make_doc_ref(f"organizations/{org_id}/members/{user_id}")


def _make_account_ref(account_id: str, user_id: str = "u_carol") -> MagicMock:
    return _make_doc_ref(f"accounts/{account_id}/members/{user_id}")


# ---------------------------------------------------------------------------
# (h) Non-super-admin actor raises SuperAdminRequiredError before any I/O
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_super_admin_raises_super_admin_required_error() -> None:
    """Non-@ken-e.ai actor raises SuperAdminRequiredError; no Firestore I/O performed.

    The service raises SuperAdminRequiredError (not PermissionError) so that if
    delete_user_data is ever called without the route's require_super_admin gate
    (defense-in-depth path), the global exception handler in main.py still
    converts it to a clean 403 rather than an unhandled 500.
    """
    actor = _make_actor(email="attacker@external.com", roles=[])
    mock_db = MagicMock()

    with (
        patch.object(svc, "get_firestore_client", return_value=mock_db),
    ):
        with pytest.raises(SuperAdminRequiredError):
            await svc.delete_user_data("u_carol", actor=actor)

    mock_db.collection.assert_not_called()
    mock_db.recursive_delete.assert_not_called()


# ---------------------------------------------------------------------------
# (a) Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_all_steps_fire() -> None:
    """Seed 2 org-member refs + 3 account-member refs; verify all 6 steps."""
    actor = _make_actor()
    org_refs = [_make_org_ref("org_acme"), _make_org_ref("org_widgets")]
    account_refs = [
        _make_account_ref("acc_acme_a"),
        _make_account_ref("acc_acme_b"),
        _make_account_ref("acc_widgets_main"),
    ]

    mock_db = MagicMock()
    mock_db.collection.return_value.document.return_value = MagicMock()
    mock_db.recursive_delete = MagicMock(return_value=None)

    hook_mock = AsyncMock(return_value=None)
    write_audit_mock = AsyncMock(return_value=None)

    with (
        patch.object(svc, "get_firestore_client", return_value=mock_db),
        patch.object(svc, "_on_user_removed", hook_mock),
        patch.object(svc, "_write_audit", write_audit_mock),
        patch.object(
            svc,
            "_resolve_member_rows",
            return_value=(org_refs, account_refs),
        ),
    ):
        result = await svc.delete_user_data("u_carol", actor=actor)

    assert isinstance(result, UserDeletionResult)
    assert result.user_id == "u_carol"
    assert result.member_rows_deleted == 5  # 2 org + 3 account
    assert result.integrations_hook_fired == 3  # once per account
    assert result.user_doc_deleted is True
    assert result.gcs_prefixes_purged == 0  # USER_GCS_PREFIXES is empty
    assert result.errors == []

    # on_user_removed called exactly 3 times (once per account ref)
    assert hook_mock.call_count == 3
    # write_audit called exactly once (best-effort audit with org_refs present)
    assert write_audit_mock.call_count == 1


# ---------------------------------------------------------------------------
# (b) Idempotent re-run (already-purged user)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotent_rerun_purged_user() -> None:
    """Zero member rows returned; recursive_delete is called; counts=0; user_doc_deleted=True."""
    actor = _make_actor()

    mock_db = MagicMock()
    mock_db.collection.return_value.document.return_value = MagicMock()
    mock_db.recursive_delete = MagicMock(return_value=None)

    with (
        patch.object(svc, "get_firestore_client", return_value=mock_db),
        patch.object(svc, "_on_user_removed", None),
        patch.object(svc, "_write_audit", None),
        patch.object(
            svc,
            "_resolve_member_rows",
            return_value=([], []),
        ),
    ):
        result = await svc.delete_user_data("u_already_gone", actor=actor)

    assert result.member_rows_deleted == 0
    assert result.integrations_hook_fired == 0
    assert result.user_doc_deleted is True  # PRD AC-10: True when no error raised
    assert result.gcs_prefixes_purged == 0
    assert result.errors == []
    # recursive_delete must still be called even when user no longer exists
    mock_db.recursive_delete.assert_called_once()


# ---------------------------------------------------------------------------
# (b2) Step-1 failure — _resolve_member_rows raises; subsequent steps still run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_step1_failure_subsequent_steps_still_run() -> None:
    """_resolve_member_rows raises; error recorded; steps 2-6 run with empty refs."""
    actor = _make_actor()

    mock_db = MagicMock()
    mock_db.collection.return_value.document.return_value = MagicMock()
    mock_db.recursive_delete = MagicMock(return_value=None)

    with (
        patch.object(svc, "get_firestore_client", return_value=mock_db),
        patch.object(svc, "_on_user_removed", None),
        patch.object(svc, "_write_audit", None),
        patch.object(
            svc,
            "_resolve_member_rows",
            side_effect=RuntimeError("index unavailable"),
        ),
    ):
        result = await svc.delete_user_data("u_carol", actor=actor)

    # step 1 error is recorded
    assert any("discover_members" in e for e in result.errors)
    assert any("index unavailable" in e for e in result.errors)
    # empty refs → no members to delete, no hook calls
    assert result.member_rows_deleted == 0
    assert result.integrations_hook_fired == 0
    # steps 4-5 still ran with empty org/account refs
    assert result.user_doc_deleted is True
    assert result.gcs_prefixes_purged == 0
    # no audit because org_refs is empty after step-1 failure
    mock_db.recursive_delete.assert_called_once()


# ---------------------------------------------------------------------------
# (c) Single-step failure — step 4 (_purge_user_doc) raises
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_step_failure_does_not_abort_subsequent_steps() -> None:
    """Inject failure inside step 4 via db.recursive_delete; steps 5+6 still run.

    The test triggers the failure from inside _purge_user_doc so that the
    internal try/except in the helper catches it and records the error,
    allowing the orchestrator to continue to steps 5 and 6.
    """
    actor = _make_actor()
    org_refs = [_make_org_ref("org_acme")]
    account_refs = [_make_account_ref("acc_acme_a")]

    write_audit_mock = AsyncMock(return_value=None)
    mock_db = MagicMock()
    # Make recursive_delete raise to trigger the internal try/except in _purge_user_doc
    mock_db.recursive_delete = MagicMock(
        side_effect=RuntimeError("recursive_delete exploded")
    )
    mock_db.collection.return_value.document.return_value = MagicMock()

    with (
        patch.object(
            svc,
            "_resolve_member_rows",
            return_value=(org_refs, account_refs),
        ),
        patch.object(svc, "get_firestore_client", return_value=mock_db),
        patch.object(svc, "_on_user_removed", None),
        patch.object(svc, "_write_audit", write_audit_mock),
    ):
        result = await svc.delete_user_data("u_carol", actor=actor)

    # step 3 (delete_members) still ran
    assert result.member_rows_deleted == 2  # 1 org + 1 account
    # step 4 error is recorded inside _purge_user_doc
    assert any("recursive_delete exploded" in e for e in result.errors)
    # step 4 exception must NOT have set user_doc_deleted (the helper didn't set it)
    assert result.user_doc_deleted is False
    # step 6 (write_audit) still ran — org_refs was discovered before step 4 failed
    assert write_audit_mock.call_count == 1


# ---------------------------------------------------------------------------
# (d) No org membership — only account-scope refs; audit step skipped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_org_membership_skips_audit() -> None:
    """Only account-scope refs returned; _write_audit must NOT be called."""
    actor = _make_actor()
    account_refs = [_make_account_ref("acc_x")]

    write_audit_mock = AsyncMock(return_value=None)
    mock_db = MagicMock()
    mock_db.recursive_delete = MagicMock(return_value=None)

    with (
        patch.object(
            svc,
            "_resolve_member_rows",
            return_value=([], account_refs),
        ),
        patch.object(svc, "get_firestore_client", return_value=mock_db),
        patch.object(svc, "_on_user_removed", None),
        patch.object(svc, "_write_audit", write_audit_mock),
    ):
        result = await svc.delete_user_data("u_no_orgs", actor=actor)

    assert result.member_rows_deleted == 1
    assert result.user_doc_deleted is True
    # write_audit must NOT have been called
    write_audit_mock.assert_not_called()


# ---------------------------------------------------------------------------
# (e) Hook absent — on_user_removed is None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hook_absent_on_user_removed_none() -> None:
    """_on_user_removed is None; no raise, integrations_hook_fired stays 0."""
    actor = _make_actor()
    account_refs = [_make_account_ref("acc_a"), _make_account_ref("acc_b")]
    mock_db = MagicMock()
    mock_db.recursive_delete = MagicMock(return_value=None)

    with (
        patch.object(
            svc,
            "_resolve_member_rows",
            return_value=([], account_refs),
        ),
        patch.object(svc, "get_firestore_client", return_value=mock_db),
        patch.object(svc, "_on_user_removed", None),
        patch.object(svc, "_write_audit", None),
    ):
        result = await svc.delete_user_data("u_carol", actor=actor)

    assert result.integrations_hook_fired == 0
    assert result.errors == []
    assert result.user_doc_deleted is True


# ---------------------------------------------------------------------------
# (f) write_audit absent — _write_audit is None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_audit_absent_is_noop() -> None:
    """_write_audit is None; audit step is silently skipped."""
    actor = _make_actor()
    org_refs = [_make_org_ref("org_acme")]
    mock_db = MagicMock()
    mock_db.recursive_delete = MagicMock(return_value=None)

    with (
        patch.object(
            svc,
            "_resolve_member_rows",
            return_value=(org_refs, []),
        ),
        patch.object(svc, "get_firestore_client", return_value=mock_db),
        patch.object(svc, "_on_user_removed", None),
        patch.object(svc, "_write_audit", None),
    ):
        result = await svc.delete_user_data("u_carol", actor=actor)

    # Orchestrator completed without error despite _write_audit=None
    assert result.errors == []
    assert result.user_doc_deleted is True


# ---------------------------------------------------------------------------
# (g) Hook raises — on_user_removed raises; error recorded, deletion continues
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hook_raises_error_recorded_deletion_continues() -> None:
    """on_user_removed raises; result.errors records failure; hook_fired=0; deletion runs."""
    actor = _make_actor()
    account_refs = [_make_account_ref("acc_boom")]
    mock_db = MagicMock()
    mock_db.recursive_delete = MagicMock(return_value=None)

    async def _raising_hook(account_id: str, user_id: str) -> None:
        raise ConnectionError("token revoke timeout")

    with (
        patch.object(
            svc,
            "_resolve_member_rows",
            return_value=([], account_refs),
        ),
        patch.object(svc, "get_firestore_client", return_value=mock_db),
        patch.object(svc, "_on_user_removed", _raising_hook),
        patch.object(svc, "_write_audit", None),
    ):
        result = await svc.delete_user_data("u_carol", actor=actor)

    # hook failure is captured
    assert result.integrations_hook_fired == 0
    assert any("token revoke timeout" in e for e in result.errors)
    # member deletion still completed (step 3 is independent)
    assert result.member_rows_deleted == 1
    # user doc still purged (step 4 is independent)
    assert result.user_doc_deleted is True
