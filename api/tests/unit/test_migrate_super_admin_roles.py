"""Tests for the super-admin bootstrap migration (DM-81 Phase 4)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from migrate_super_admin_roles import SuperAdminRoleMigrator
from src.kene_api.auth.models import SUPER_ADMIN_ROLE


def _migrator(dry_run: bool = False) -> SuperAdminRoleMigrator:
    """Build a migrator with a mocked FirestoreService."""
    with patch("migrate_super_admin_roles.FirestoreService"):
        return SuperAdminRoleMigrator(dry_run=dry_run)


def _set_user_doc(migrator, *, exists: bool, roles: list[str] | None = None):
    """Wire the migrator's mock Firestore to return one users/{uid} doc."""
    snapshot = MagicMock()
    snapshot.exists = exists
    snapshot.to_dict.return_value = {"roles": list(roles or [])} if exists else None
    user_ref = MagicMock()
    user_ref.get.return_value = snapshot
    client = MagicMock()
    client.collection.return_value.document.return_value = user_ref
    migrator.firestore.get_client.return_value = client
    return user_ref


def _fb_user(uid: str, email: str, *, verified: bool) -> MagicMock:
    return MagicMock(uid=uid, email=email, email_verified=verified)


class TestSeedUser:
    """_seed_user handles the three doc states idempotently."""

    def test_creates_baseline_skeleton_when_doc_missing(self):
        migrator = _migrator()
        user_ref = _set_user_doc(migrator, exists=False)

        migrator._seed_user("staff-uid", "staff@ken-e.ai")

        user_ref.set.assert_called_once()
        assert user_ref.set.call_args[0][0]["roles"] == [SUPER_ADMIN_ROLE]
        user_ref.update.assert_not_called()
        assert migrator.stats["skeleton_created"] == 1

    def test_adds_role_when_doc_exists_without_it(self):
        migrator = _migrator()
        user_ref = _set_user_doc(migrator, exists=True, roles=[])

        migrator._seed_user("staff-uid", "staff@ken-e.ai")

        user_ref.update.assert_called_once()
        user_ref.set.assert_not_called()
        assert migrator.stats["role_added"] == 1

    def test_is_idempotent_when_role_already_present(self):
        migrator = _migrator()
        user_ref = _set_user_doc(migrator, exists=True, roles=[SUPER_ADMIN_ROLE])

        migrator._seed_user("staff-uid", "staff@ken-e.ai")

        user_ref.update.assert_not_called()
        user_ref.set.assert_not_called()
        assert migrator.stats["already_seeded"] == 1

    def test_dry_run_writes_nothing(self):
        migrator = _migrator(dry_run=True)
        user_ref = _set_user_doc(migrator, exists=False)

        migrator._seed_user("staff-uid", "staff@ken-e.ai")

        user_ref.set.assert_not_called()
        user_ref.update.assert_not_called()
        assert migrator.stats["skeleton_created"] == 1


class TestRunCandidateFiltering:
    """run() seeds only verified @ken-e.ai users."""

    def _run_with_users(self, migrator, users):
        page = MagicMock()
        page.iterate_all.return_value = users
        with patch("firebase_admin.auth.list_users", return_value=page):
            return migrator.run()

    def test_seeds_only_verified_ken_e_users(self):
        migrator = _migrator()
        users = [
            _fb_user("staff1", "staff1@ken-e.ai", verified=True),
            _fb_user("staff2", "staff2@KEN-E.AI", verified=True),
            _fb_user("attacker", "attacker@ken-e.ai", verified=False),
            _fb_user("customer", "customer@example.com", verified=True),
        ]

        with patch.object(migrator, "_seed_user") as mock_seed:
            stats = self._run_with_users(migrator, users)

        seeded_uids = {call.args[0] for call in mock_seed.call_args_list}
        assert seeded_uids == {"staff1", "staff2"}
        assert stats["candidates"] == 2
        assert stats["unverified_skipped"] == 1

    def test_records_per_user_errors_without_aborting(self):
        migrator = _migrator()
        users = [
            _fb_user("staff1", "staff1@ken-e.ai", verified=True),
            _fb_user("staff2", "staff2@ken-e.ai", verified=True),
        ]

        with patch.object(
            migrator, "_seed_user", side_effect=[RuntimeError("boom"), None]
        ):
            stats = self._run_with_users(migrator, users)

        assert stats["errors"] == 1
        assert stats["candidates"] == 2
