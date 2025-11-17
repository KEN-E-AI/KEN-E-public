"""Smoke tests for migration scripts against real Firestore (optional).

These tests are skipped by default and only run when explicitly enabled.
They validate that migration scripts can connect to and operate on real Firestore.

Usage:
    RUN_FIRESTORE_INTEGRATION_TESTS=true pytest api/tests/integration/test_migration_smoke.py
"""

import os
import sys
from pathlib import Path

import pytest

# Only run if explicitly enabled
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_FIRESTORE_INTEGRATION_TESTS") != "true",
    reason="Firestore integration tests disabled by default. "
    "Set RUN_FIRESTORE_INTEGRATION_TESTS=true to enable.",
)


@pytest.mark.integration
def test_migration_script_can_initialize_firestore():
    """Smoke test: Migration script can connect to Firestore."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from migrate_user_permissions import PermissionMigrator

    migrator = PermissionMigrator(dry_run=True)

    # Test: Can initialize Firestore
    result = migrator.initialize_firestore()

    assert result is True, "Failed to initialize Firestore service"
    assert migrator.firestore is not None
    assert migrator.firestore.get_client() is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migration_dry_run_on_real_firestore():
    """Smoke test: Can run dry-run migration against real Firestore."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from migrate_user_permissions import PermissionMigrator

    migrator = PermissionMigrator(dry_run=True)

    # Test: Can run full dry-run without errors
    if not migrator.initialize_firestore():
        pytest.skip("Could not initialize Firestore")

    stats = await migrator.migrate_all_users()

    # Verify stats structure
    assert "total_users" in stats
    assert "migrated" in stats
    assert "skipped" in stats
    assert "errors" in stats

    # Verify dry-run completed without errors
    assert stats["errors"] == 0, f"Dry run had {stats['errors']} errors"

    # Verify reasonable data (at least processed some users or found none)
    assert stats["total_users"] >= 0
    assert stats["migrated"] + stats["skipped"] <= stats["total_users"]


@pytest.mark.integration
def test_verification_script_can_run():
    """Smoke test: Verification script can analyze Firestore data."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from verify_permissions_migration import PermissionVerifier

    verifier = PermissionVerifier()

    # Test: Can initialize Firestore
    if not verifier.initialize_firestore():
        pytest.skip("Could not initialize Firestore")

    # Test: Can run verification
    result = verifier.verify_all_users()

    # Result should be bool (True if all migrated, False otherwise)
    assert isinstance(result, bool)

    # Verify stats were collected
    assert verifier.stats["total_users"] >= 0
    assert "users_with_old_structure" in verifier.stats
    assert "users_without_new_structure" in verifier.stats
    assert "super_admins" in verifier.stats


@pytest.mark.integration
def test_rollback_script_can_initialize():
    """Smoke test: Rollback script can initialize (but don't actually rollback)."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
    from rollback_permissions_migration import PermissionRollback

    rollback = PermissionRollback(dry_run=True)

    # Test: Can initialize Firestore
    result = rollback.initialize_firestore()

    assert result is True, "Failed to initialize Firestore service"
    assert rollback.firestore is not None


@pytest.mark.integration
def test_debug_script_functions_exist():
    """Smoke test: Debug script can be imported and has expected structure."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

    # Test: Can import debug script (it's a standalone script, not a module)
    debug_script_path = (
        Path(__file__).parent.parent.parent / "scripts" / "debug_user_permissions.py"
    )
    assert debug_script_path.exists(), "Debug script not found"

    # Verify script has expected content
    with open(debug_script_path) as f:
        content = f.read()
        assert "FirestoreService" in content
        assert "user_id" in content
        assert "permissions" in content
