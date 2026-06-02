"""Unit tests for token revocation service."""

from datetime import datetime
from unittest import mock

import pytest
from src.kene_api.auth.token_revocation import TokenRevocationService


class TestTokenRevocationService:
    """Test token revocation service functionality."""

    @pytest.fixture
    def revocation_service(self):
        """Create a token revocation service for testing."""
        with mock.patch("src.kene_api.redis_client.get_redis_service") as mock_redis:
            mock_redis_service = mock.Mock()
            mock_redis.return_value = mock_redis_service
            service = TokenRevocationService()
            service._redis = mock_redis_service
            return service

    @pytest.mark.asyncio
    async def test_revoke_token(self, revocation_service):
        """Test revoking a single token."""
        # Mock dependencies
        with mock.patch(
            "src.kene_api.auth.token_revocation.get_firestore_service"
        ) as mock_firestore:
            with mock.patch(
                "src.kene_api.auth.token_revocation.get_audit_logger"
            ) as mock_audit:
                # Setup mocks
                mock_fs_service = mock.Mock()
                mock_client = mock.Mock()
                mock_collection = mock.Mock()
                mock_doc = mock.Mock()

                mock_firestore.return_value = mock_fs_service
                mock_fs_service.get_client.return_value = mock_client
                mock_client.collection.return_value = mock_collection
                mock_collection.document.return_value = mock_doc

                revocation_service.redis.is_available.return_value = True

                mock_audit_logger = mock.AsyncMock()
                mock_audit.return_value = mock_audit_logger

                # Revoke token
                await revocation_service.revoke_token(
                    token_id="token123",
                    user_id="user456",
                    reason="Security concern",
                    revoked_by="admin",
                )

                # Verify Firestore write
                mock_collection.document.assert_called_once_with("token123")
                mock_doc.set.assert_called_once()
                stored_data = mock_doc.set.call_args[0][0]
                assert stored_data["token_id"] == "token123"
                assert stored_data["user_id"] == "user456"
                assert stored_data["reason"] == "Security concern"
                assert stored_data["revoked_by"] == "admin"

                # Verify Redis cache
                revocation_service.redis.set.assert_called_once_with(
                    "revoked_token:token123", "1", ttl=3600
                )

                # Verify audit log
                mock_audit_logger.log_token_revoked.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(self, revocation_service):
        """Test revoking all tokens for a user."""
        with mock.patch(
            "src.kene_api.auth.token_revocation.get_firestore_service"
        ) as mock_firestore:
            with mock.patch(
                "src.kene_api.auth.token_revocation.get_audit_logger"
            ) as mock_audit:
                # Setup mocks
                mock_fs_service = mock.Mock()
                mock_client = mock.Mock()
                mock_collection = mock.Mock()
                mock_doc = mock.Mock()

                mock_firestore.return_value = mock_fs_service
                mock_fs_service.get_client.return_value = mock_client
                mock_client.collection.return_value = mock_collection
                mock_collection.document.return_value = mock_doc

                revocation_service.redis.is_available.return_value = True

                mock_audit_logger = mock.AsyncMock()
                mock_audit.return_value = mock_audit_logger

                # Revoke all tokens
                await revocation_service.revoke_all_user_tokens(
                    user_id="user456",
                    reason="Account compromised",
                    revoked_by="user456",
                )

                # Verify Firestore write
                mock_client.collection.assert_called_with("revoked_tokens_all")
                mock_collection.document.assert_called_with("user456")
                mock_doc.set.assert_called_once()

                # Verify Redis cache
                assert revocation_service.redis.set.called
                cache_key = revocation_service.redis.set.call_args[0][0]
                assert cache_key == "revoked_all_tokens:user456"

                # Verify audit log
                mock_audit_logger.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_token_revoked_specific_token(self, revocation_service):
        """Test checking if a specific token is revoked."""
        # Test with Redis cache hit
        revocation_service.redis.is_available.return_value = True
        revocation_service.redis.get.return_value = "1"

        result = await revocation_service.is_token_revoked("token123", "user456")
        assert result is True
        revocation_service.redis.get.assert_called_with("revoked_token:token123")

    @pytest.mark.asyncio
    async def test_is_token_revoked_all_tokens(self, revocation_service):
        """Test checking if token is revoked when all user tokens are revoked."""
        # Test with all tokens revoked
        revocation_service.redis.is_available.return_value = True
        revocation_service.redis.get.side_effect = [
            None,  # Specific token not found
            "2024-01-01T12:00:00",  # All tokens revoked at this time
        ]

        # Token issued before revocation time
        issued_at = datetime(2024, 1, 1, 11, 0, 0).timestamp()
        result = await revocation_service.is_token_revoked(
            "token123", "user456", issued_at
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_is_token_revoked_not_revoked(self, revocation_service):
        """Test checking token that is not revoked."""
        # Redis returns None for both checks
        revocation_service.redis.is_available.return_value = True
        revocation_service.redis.get.side_effect = [None, None]

        # Firestore also returns no documents
        with mock.patch(
            "src.kene_api.auth.token_revocation.get_firestore_service"
        ) as mock_firestore:
            mock_fs_service = mock.Mock()
            mock_client = mock.Mock()
            mock_collection = mock.Mock()
            mock_doc = mock.Mock()
            mock_doc.exists = False

            mock_firestore.return_value = mock_fs_service
            mock_fs_service.get_client.return_value = mock_client
            mock_client.collection.return_value = mock_collection
            mock_collection.document.return_value.get.return_value = mock_doc

            result = await revocation_service.is_token_revoked("token123", "user456")
            assert result is False

    # -------------------------------------------------------------------------
    # Empty-token_id invariants — `is_token_revoked("", ...)` must skip both
    # the per-token Redis lookup and the per-token Firestore document path
    # (Firestore rejects the empty doc id with InvalidArgument), while still
    # honoring `revoke_all_user_tokens`. `revoke_token("", ...)` must raise
    # rather than write to that invalid path. The tests below lock the guard
    # in place against future refactors.
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_is_token_revoked_empty_token_id_redis_available_skips_per_token_lookup(
        self, revocation_service
    ):
        """Empty token_id + Redis up + no revoke_all → False, no per-token Redis lookup."""
        revocation_service.redis.is_available.return_value = True
        revocation_service.redis.get.return_value = None  # no revoke_all entry

        result = await revocation_service.is_token_revoked("", "user456")

        assert result is False
        # Per-token cache key MUST NOT be queried with an empty token_id —
        # `revoked_token:` is a poisoned key that could match unrelated entries
        # if anything ever wrote there. Only the all-tokens key should be hit.
        for call in revocation_service.redis.get.call_args_list:
            queried_key = call.args[0]
            assert not queried_key.startswith("revoked_token:"), (
                f"Per-token lookup leaked with empty token_id: {queried_key}"
            )

    @pytest.mark.asyncio
    async def test_is_token_revoked_empty_token_id_redis_down_skips_firestore_doc(
        self, revocation_service
    ):
        """Empty token_id + Redis down → no Firestore document("") call (the bug)."""
        revocation_service.redis.is_available.return_value = False

        with mock.patch(
            "src.kene_api.auth.token_revocation.get_firestore_service"
        ) as mock_firestore:
            mock_fs_service = mock.Mock()
            mock_client = mock.Mock()
            mock_collection = mock.Mock()
            mock_firestore.return_value = mock_fs_service
            mock_fs_service.get_client.return_value = mock_client
            mock_client.collection.return_value = mock_collection

            # No issued_at → user-wide check skipped too → returns False without
            # ever touching the per-token Firestore doc path.
            result = await revocation_service.is_token_revoked("", "user456")

            assert result is False
            # The per-token `collection("revoked_tokens").document("")` call is
            # what Firestore rejects with InvalidArgument — assert it never ran.
            for call in mock_client.collection.call_args_list:
                if call.args and call.args[0] == "revoked_tokens":
                    pytest.fail("Per-token Firestore lookup leaked with empty token_id")

    @pytest.mark.asyncio
    async def test_is_token_revoked_empty_token_id_still_honors_revoke_all(
        self, revocation_service
    ):
        """Empty token_id + revoke_all set + issued_at predates revoke → True (security fallback)."""
        revocation_service.redis.is_available.return_value = True
        # First/only get() call is for revoked_all_tokens:user456 since per-token
        # lookup is skipped for empty token_id.
        revocation_service.redis.get.return_value = "2024-01-01T12:00:00"

        # Token issued one hour before the all-tokens revocation timestamp.
        issued_at = datetime(2024, 1, 1, 11, 0, 0).timestamp()

        result = await revocation_service.is_token_revoked("", "user456", issued_at)

        # Critical: a JWT with no jti must still be killed by revoke_all_user_tokens,
        # otherwise blanket revocation would silently fail for malformed-but-valid tokens.
        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_token_empty_token_id_raises_value_error(
        self, revocation_service
    ):
        """revoke_token("", ...) raises ValueError without side effects."""
        with mock.patch(
            "src.kene_api.auth.token_revocation.get_firestore_service"
        ) as mock_firestore:
            with mock.patch(
                "src.kene_api.auth.token_revocation.get_audit_logger"
            ) as mock_audit:
                mock_audit_logger = mock.AsyncMock()
                mock_audit.return_value = mock_audit_logger

                with pytest.raises(ValueError, match="token_id is required"):
                    await revocation_service.revoke_token(
                        token_id="", user_id="user456"
                    )

                # No Firestore write and no audit log should have happened —
                # the guard fires before any side-effect.
                mock_firestore.assert_not_called()
                mock_audit_logger.log_token_revoked.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_expired_revocations(self, revocation_service):
        """Test cleaning up expired token revocations."""
        with mock.patch(
            "src.kene_api.auth.token_revocation.get_firestore_service"
        ) as mock_firestore:
            # Setup mocks
            mock_fs_service = mock.Mock()
            mock_client = mock.Mock()
            mock_collection = mock.Mock()
            mock_batch = mock.Mock()

            # Create mock documents
            mock_docs = []
            for i in range(5):
                mock_doc = mock.Mock()
                mock_doc.reference = f"doc_ref_{i}"
                mock_docs.append(mock_doc)

            mock_firestore.return_value = mock_fs_service
            mock_fs_service.get_client.return_value = mock_client
            mock_client.collection.return_value = mock_collection
            mock_collection.where.return_value.stream.return_value = mock_docs
            mock_client.batch.return_value = mock_batch

            # Run cleanup
            count = await revocation_service.cleanup_expired_revocations()

            # Verify results
            assert count == 5
            assert mock_batch.delete.call_count == 5
            mock_batch.commit.assert_called()
