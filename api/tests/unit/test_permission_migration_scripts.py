"""Tests for permission migration scripts."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from migrate_user_permissions import PermissionMigrator
from rollback_permissions_migration import PermissionRollback
from verify_permissions_migration import PermissionVerifier


class TestPermissionMigrator:
    """Test PermissionMigrator class."""

    @pytest.fixture
    def mock_firestore(self):
        """Create mock Firestore service."""
        mock = MagicMock()
        mock.initialize.return_value = True
        mock.health_check.return_value = True
        mock.get_client.return_value = MagicMock()
        return mock

    @pytest.fixture
    def migrator(self, mock_firestore):
        """Create PermissionMigrator with mocked Firestore."""
        with patch(
            "migrate_user_permissions.FirestoreService", return_value=mock_firestore
        ):
            return PermissionMigrator(dry_run=True)

    def test_migrate_user_with_old_permissions_only(self, migrator):
        """Test migrating user with only old permissions."""
        user_id = "user_123"
        user_data = {
            "uid": user_id,
            "email": "test@example.com",
            "permissions": {
                "accounts": {"acc_1": "edit", "acc_2": "view"},
                "organizations": {"org_1": "admin"},
            },
        }

        result = migrator._migrate_user_permissions(user_id, user_data)

        assert result is True
        assert migrator.stats["migrated"] == 0

    def test_migrate_user_with_both_old_and_new_permissions(self, migrator):
        """Test migrating user with both old and new permissions (new takes precedence)."""
        user_id = "user_123"
        user_data = {
            "uid": user_id,
            "email": "test@example.com",
            "permissions": {
                "accounts": {"acc_1": "view"},
                "account_permissions": {"acc_1": "edit", "acc_2": "view"},
                "organizations": {"org_1": "admin"},
            },
        }

        result = migrator._migrate_user_permissions(user_id, user_data)

        assert result is True

    def test_migrate_user_with_no_old_permissions(self, migrator):
        """Test that user without old permissions is skipped."""
        user_id = "user_123"
        user_data = {
            "uid": user_id,
            "email": "test@example.com",
            "permissions": {
                "account_permissions": {"acc_1": "edit"},
                "organizations": {"org_1": "admin"},
            },
        }

        result = migrator._migrate_user_permissions(user_id, user_data)

        assert result is False

    def test_migrate_user_with_empty_permissions(self, migrator):
        """Test that user with empty permissions gets account_permissions field added."""
        user_id = "user_123"
        user_data = {
            "uid": user_id,
            "email": "test@example.com",
            "permissions": {},
        }

        result = migrator._migrate_user_permissions(user_id, user_data)

        # Should migrate to add missing account_permissions field
        assert result is True

    def test_initialize_firestore_success(self, mock_firestore):
        """Test successful Firestore initialization."""
        with patch(
            "migrate_user_permissions.FirestoreService", return_value=mock_firestore
        ):
            migrator = PermissionMigrator()
            result = migrator.initialize_firestore()

            assert result is True
            mock_firestore.initialize.assert_called_once()
            mock_firestore.health_check.assert_called_once()

    def test_initialize_firestore_failure(self):
        """Test failed Firestore initialization."""
        mock_firestore = MagicMock()
        mock_firestore.initialize.return_value = False

        with patch(
            "migrate_user_permissions.FirestoreService", return_value=mock_firestore
        ):
            migrator = PermissionMigrator()
            result = migrator.initialize_firestore()

            assert result is False

    @pytest.mark.asyncio
    async def test_migrate_all_users_with_mixed_data(self, migrator, mock_firestore):
        """Test migrating all users with mixed permission structures."""
        users = [
            {
                "uid": "user_1",
                "email": "user1@example.com",
                "permissions": {
                    "accounts": {"acc_1": "edit"},
                    "organizations": {"org_1": "admin"},
                },
            },
            {
                "uid": "user_2",
                "email": "user2@example.com",
                "permissions": {
                    "account_permissions": {"acc_2": "view"},
                    "organizations": {"org_2": "view"},
                },
            },
            {
                "uid": "user_3",
                "email": "user3@example.com",
                "permissions": {
                    "accounts": {"acc_3": "view"},
                    "account_permissions": {"acc_3": "edit"},
                    "organizations": {"org_3": "admin"},
                },
            },
        ]

        mock_firestore.list_documents.return_value = users
        migrator.firestore = mock_firestore

        stats = await migrator.migrate_all_users()

        assert stats["total_users"] == 3
        assert stats["migrated"] == 2
        assert stats["skipped"] == 1
        assert stats["errors"] == 0


class TestPermissionVerifier:
    """Test PermissionVerifier class."""

    @pytest.fixture
    def mock_firestore(self):
        """Create mock Firestore service."""
        mock = MagicMock()
        mock.initialize.return_value = True
        mock.health_check.return_value = True
        return mock

    @pytest.fixture
    def verifier(self, mock_firestore):
        """Create PermissionVerifier with mocked Firestore."""
        with patch(
            "verify_permissions_migration.FirestoreService", return_value=mock_firestore
        ):
            return PermissionVerifier()

    def test_verify_user_with_old_structure(self, verifier):
        """Test that user with old structure is flagged."""
        user_id = "user_123"
        user_data = {
            "uid": user_id,
            "email": "test@example.com",
            "permissions": {
                "accounts": {"acc_1": "edit"},
                "account_permissions": {},
                "organizations": {},
            },
        }

        verifier._verify_user_permissions(user_id, user_data)

        assert verifier.stats["users_with_old_structure"] == 1
        assert user_id in verifier.users_with_old_structure

    def test_verify_user_without_new_structure(self, verifier):
        """Test that user without new structure is flagged."""
        user_id = "user_123"
        user_data = {
            "uid": user_id,
            "email": "test@example.com",
            "permissions": {
                "organizations": {},
            },
        }

        verifier._verify_user_permissions(user_id, user_data)

        assert verifier.stats["users_without_new_structure"] == 1
        assert user_id in verifier.users_without_new_structure

    def test_verify_user_with_correct_structure(self, verifier):
        """Test that correctly migrated user passes verification."""
        user_id = "user_123"
        user_data = {
            "uid": user_id,
            "email": "test@example.com",
            "permissions": {
                "account_permissions": {"acc_1": "edit"},
                "organizations": {"org_1": "admin"},
            },
        }

        verifier._verify_user_permissions(user_id, user_data)

        assert verifier.stats["users_with_old_structure"] == 0
        assert verifier.stats["users_without_new_structure"] == 0
        assert verifier.stats["users_with_permissions"] == 1

    def test_verify_super_admin_detection(self, verifier):
        """Test that super admins are correctly identified."""
        user_id = "admin_123"
        user_data = {
            "uid": user_id,
            "email": "admin@ken-e.ai",
            "permissions": {
                "account_permissions": {},
                "organizations": {},
            },
        }

        verifier._verify_user_permissions(user_id, user_data)

        assert verifier.stats["super_admins"] == 1

    def test_verify_all_users_success(self, verifier, mock_firestore):
        """Test successful verification of all users."""
        users = [
            {
                "uid": "user_1",
                "email": "user1@example.com",
                "permissions": {
                    "account_permissions": {"acc_1": "edit"},
                    "organizations": {"org_1": "admin"},
                },
            },
            {
                "uid": "user_2",
                "email": "user2@example.com",
                "permissions": {
                    "account_permissions": {},
                    "organizations": {"org_2": "view"},
                },
            },
        ]

        mock_firestore.list_documents.return_value = users
        verifier.firestore = mock_firestore

        result = verifier.verify_all_users()

        assert result is True
        assert verifier.stats["total_users"] == 2
        assert verifier.stats["users_with_old_structure"] == 0
        assert verifier.stats["users_without_new_structure"] == 0

    def test_verify_all_users_failure(self, verifier, mock_firestore):
        """Test failed verification when users have issues."""
        users = [
            {
                "uid": "user_1",
                "email": "user1@example.com",
                "permissions": {
                    "accounts": {"acc_1": "edit"},
                    "organizations": {"org_1": "admin"},
                },
            },
        ]

        mock_firestore.list_documents.return_value = users
        verifier.firestore = mock_firestore

        result = verifier.verify_all_users()

        assert result is False
        assert verifier.stats["users_with_old_structure"] == 1


class TestPermissionRollback:
    """Test PermissionRollback class."""

    @pytest.fixture
    def mock_firestore(self):
        """Create mock Firestore service."""
        mock = MagicMock()
        mock.initialize.return_value = True
        mock.health_check.return_value = True
        mock.get_client.return_value = MagicMock()
        return mock

    @pytest.fixture
    def rollback(self, mock_firestore):
        """Create PermissionRollback with mocked Firestore."""
        with patch(
            "rollback_permissions_migration.FirestoreService",
            return_value=mock_firestore,
        ):
            return PermissionRollback(dry_run=True)

    def test_rollback_user_with_account_permissions(self, rollback):
        """Test rolling back user with account_permissions."""
        user_id = "user_123"
        user_data = {
            "uid": user_id,
            "email": "test@example.com",
            "permissions": {
                "account_permissions": {"acc_1": "edit", "acc_2": "view"},
                "organizations": {"org_1": "admin"},
            },
        }

        result = rollback._rollback_user_permissions(user_id, user_data)

        assert result is True

    def test_rollback_user_without_account_permissions(self, rollback):
        """Test that user without account_permissions is skipped."""
        user_id = "user_123"
        user_data = {
            "uid": user_id,
            "email": "test@example.com",
            "permissions": {
                "organizations": {"org_1": "admin"},
            },
        }

        result = rollback._rollback_user_permissions(user_id, user_data)

        assert result is False

    def test_rollback_user_with_empty_account_permissions(self, rollback):
        """Test that user with empty account_permissions is skipped."""
        user_id = "user_123"
        user_data = {
            "uid": user_id,
            "email": "test@example.com",
            "permissions": {
                "account_permissions": {},
                "organizations": {"org_1": "admin"},
            },
        }

        result = rollback._rollback_user_permissions(user_id, user_data)

        assert result is False
