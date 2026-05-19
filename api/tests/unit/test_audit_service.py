"""Unit tests for audit_service.py Shape B path assertions (DM-70).

Locks the four strategy-audit write/read functions in services/audit_service.py to the
Shape B Firestore path ``accounts/{account_id}/strategy_audit/...``.  Any regression that
reverts a path to the legacy Shape A prefix (``strategy_audit_{account_id}/``) will
cause the matching test to fail immediately.

These are pure-unit tests: ``audit_service.db`` is replaced with a ``MagicMock``
via ``monkeypatch`` (function-scoped), so no Firestore connection is required.

Explicitly out of scope: ``db.collection_group("strategy_audit")`` — that cross-account
query path is covered by the emulator integration test
``test_strategy_audit_cross_account.py`` (DM-16).
"""

import re
from unittest.mock import MagicMock

import pytest
from src.kene_api.auth.models import UserContext
from src.kene_api.services import audit_service

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_ACCOUNT_ID = "acc_test"
_DOC_TYPE = "business_strategy"


@pytest.fixture
def mock_user() -> UserContext:
    return UserContext(
        user_id="u_test",
        email="tester@example.com",
        organization_permissions={},
        account_permissions={_ACCOUNT_ID: "edit"},
    )


@pytest.fixture
def mock_db(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace the module-level ``db`` in audit_service with a MagicMock."""
    db = MagicMock()
    monkeypatch.setattr(audit_service, "db", db)
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuditServiceShapeBPaths:
    """Assert that every strategy-audit read/write targets the Shape B collection path."""

    async def test_log_strategy_action_writes_to_shape_b_path(
        self, mock_db: MagicMock, mock_user: UserContext
    ) -> None:
        """log_strategy_action writes the audit doc to accounts/{account_id}/strategy_audit/."""
        audit_id = await audit_service.log_strategy_action(
            account_id=_ACCOUNT_ID,
            doc_type=_DOC_TYPE,
            action="created",
            user=mock_user,
        )

        # Function returns the audit_id on success.
        assert audit_id, "Expected a non-empty audit_id on success"

        # The document path passed to db.document(...) must start with the Shape B prefix.
        document_call_arg: str = mock_db.document.call_args.args[0]
        expected_prefix = f"accounts/{_ACCOUNT_ID}/strategy_audit/"
        assert document_call_arg.startswith(expected_prefix), (
            f"audit doc path {document_call_arg!r} does not start with "
            f"Shape B prefix {expected_prefix!r}"
        )

        # The suffix follows the {doc_type}_{iso_ts}_{uuid8} pattern.
        suffix = document_call_arg[len(expected_prefix) :]
        assert re.match(
            r"^[a-z_]+_[\d\-T:.+]+_[0-9a-f]{8}$",
            suffix,
        ), f"audit_id suffix {suffix!r} does not match expected pattern"

        # The audit document was persisted via .set().
        mock_db.document.return_value.set.assert_called_once()

    async def test_get_recent_actions_reads_from_shape_b_collection(
        self, mock_db: MagicMock, mock_user: UserContext
    ) -> None:
        """get_recent_actions queries accounts/{account_id}/strategy_audit."""
        # Configure the full query chain: collection → order_by → limit → stream.
        (
            mock_db.collection.return_value.order_by.return_value.limit.return_value.stream.return_value
        ) = []

        result = await audit_service.get_recent_actions(
            account_id=_ACCOUNT_ID,
            user_id=None,
            doc_type=None,
            limit=5,
        )

        assert result == [], "Expected empty list for empty mock stream"

        mock_db.collection.assert_called_once_with(
            f"accounts/{_ACCOUNT_ID}/strategy_audit"
        )

    async def test_get_document_history_reads_from_shape_b_collection(
        self, mock_db: MagicMock
    ) -> None:
        """get_document_history queries accounts/{account_id}/strategy_audit."""
        # Configure the full query chain: collection → where → where → order_by → limit → stream.
        (
            mock_db.collection.return_value.where.return_value.where.return_value.order_by.return_value.limit.return_value.stream.return_value
        ) = []

        result = await audit_service.get_document_history(
            account_id=_ACCOUNT_ID,
            doc_type=_DOC_TYPE,
            doc_id="doc_xyz",
            limit=10,
        )

        assert result == [], "Expected empty list for empty mock stream"

        mock_db.collection.assert_called_once_with(
            f"accounts/{_ACCOUNT_ID}/strategy_audit"
        )

    async def test_cleanup_old_audit_logs_queries_shape_b_collection(
        self, mock_db: MagicMock
    ) -> None:
        """cleanup_old_audit_logs queries accounts/{account_id}/strategy_audit
        and issues batch.delete for each returned doc.
        """
        # Provide one stub document so the batch-delete branch executes.
        stub_doc = MagicMock()
        stub_doc.reference = MagicMock()
        mock_db.collection.return_value.where.return_value.stream.return_value = [
            stub_doc
        ]

        deleted = await audit_service.cleanup_old_audit_logs(
            account_id=_ACCOUNT_ID, days_to_keep=90
        )

        assert deleted == 1, "Expected 1 deletion for the one stub doc"

        mock_db.collection.assert_called_once_with(
            f"accounts/{_ACCOUNT_ID}/strategy_audit"
        )

        # Batch delete was invoked for the stub document.
        mock_db.batch.return_value.delete.assert_called_once_with(stub_doc.reference)
