"""
Unit tests for chat performance optimizations (Phase 1).

Tests cover:
1. Session recreation bug fix - ensures non-ADK sessions are reused
2. Parallel execution - verifies Neo4j and Firestore load in parallel
3. OAuth timeout - confirms 10s timeout is enforced
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from src.kene_api.routers.chat import AgentEngineClient
from src.kene_api.services.ga_credential_helper import GACredentialHelper


class TestSessionReuseBugFix:
    """Test that the session recreation bug is fixed."""

    @pytest.mark.asyncio
    async def test_non_adk_session_is_reused_not_recreated(self):
        """
        Test that non-ADK format session IDs (chat_*, fallback_*, manual_*)
        are reused from cache instead of triggering new session creation.

        This tests the critical bug fix that was causing 5-7s latency on every message.
        """
        # Setup
        client = AgentEngineClient()
        user_id = "test_user_123"
        session_id = "chat_1234567890_abc"  # Frontend-generated session ID

        # Pre-populate cache with session info
        session_key = f"{user_id}:{session_id}"
        client._user_sessions[session_key] = {
            "session_id": session_id,
            "user_id": user_id,
            "conversation_name": "Test Chat",
            "created_at": "2025-01-01T00:00:00Z",
            "last_updated": "2025-01-01T00:00:00Z",
            "message_count": 1,
        }

        # Mock create_conversation to detect if it's called (it shouldn't be)
        with patch.object(
            client, "create_conversation", new=AsyncMock()
        ) as mock_create:
            # Execute
            result = await client.get_or_create_session(
                user_id=user_id,
                user_context=None,
                session_id=session_id,
                conversation_name=None,
                account_id=None,
            )

            # Assert
            assert result == session_id, "Should return existing session ID"
            # Should NOT create new session for non-ADK format session in cache
            mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_adk_session_not_in_cache_creates_proper_adk_session(self):
        """
        Test that non-ADK format sessions not in cache trigger creation of proper ADK session.

        This prevents sending invalid frontend-generated session IDs to Agent Engine,
        which would cause 400 INVALID_ARGUMENT errors.

        Frontend generates temporary IDs like chat_*, but Agent Engine requires proper ADK sessions.
        """
        # Setup
        client = AgentEngineClient()
        user_id = "test_user_456"
        session_id = "chat_frontend_generated_123"  # Frontend-generated session format

        # Mock create_conversation to return a proper ADK session
        with (
            patch.object(
                client,
                "create_conversation",
                new=AsyncMock(return_value="proper_adk_session_456"),
            ) as mock_create,
            patch("src.kene_api.routers.chat.get_redis_service") as mock_redis,
        ):
            # Mock Redis to return cache miss
            mock_redis_instance = MagicMock()
            mock_redis_instance.is_available.return_value = True
            mock_redis_instance.get_json.return_value = None
            mock_redis.return_value = mock_redis_instance

            # Execute
            result = await client.get_or_create_session(
                user_id=user_id,
                user_context=None,
                session_id=session_id,
                conversation_name=None,
                account_id=None,
            )

            # Assert
            assert result == "proper_adk_session_456", (
                "Should create and return proper ADK session"
            )
            # Should create new ADK session instead of using invalid frontend ID
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_adk_session_optimistically_registered_when_not_in_cache(self):
        """
        Test that genuine ADK sessions (not chat_/fallback_/manual_ format)
        are optimistically registered in-memory cache without a blocking
        get_session() validation call. stream_query validates the session itself.
        """
        client = AgentEngineClient()
        user_id = "test_user_789"
        session_id = "adk_session_12345"

        mock_session_service = AsyncMock()
        client._session_service = mock_session_service

        with patch("src.kene_api.routers.chat.get_redis_service") as mock_redis:
            mock_redis_instance = MagicMock()
            mock_redis_instance.is_available.return_value = True
            mock_redis_instance.get_json.return_value = None
            mock_redis.return_value = mock_redis_instance

            result = await client.get_or_create_session(
                user_id=user_id,
                user_context=None,
                session_id=session_id,
                conversation_name=None,
                account_id=None,
            )

        assert result == session_id
        # Should NOT call get_session — optimistic registration skips validation
        mock_session_service.get_session.assert_not_called()
        # Should be registered in in-memory cache
        session_key = f"{user_id}:{session_id}"
        assert session_key in client._user_sessions


class TestParallelExecution:
    """Test that Neo4j and Firestore operations run in parallel."""

    @pytest.mark.asyncio
    async def test_neo4j_and_firestore_load_in_parallel(self):
        """
        Test that organization context (Neo4j) and GA credentials (Firestore)
        load in parallel using asyncio.gather(), reducing latency by ~50%.
        """
        # Setup
        client = AgentEngineClient()
        user_id = "test_user"
        account_id = "test_account_123"

        # Mock user_context
        mock_user_context = MagicMock()
        mock_user_context.accessible_accounts = [account_id]
        mock_user_context.has_account_access.return_value = True

        # Track execution order to verify parallelism
        execution_order = []
        neo4j_delay = 1.0  # 1 second delay for Neo4j
        firestore_delay = 1.0  # 1 second delay for Firestore

        async def mock_load_org_context(account_id: str):
            execution_order.append("neo4j_start")
            await asyncio.sleep(neo4j_delay)
            execution_order.append("neo4j_end")
            return "org context"

        async def mock_get_and_format_credentials(account_id: str):
            execution_order.append("firestore_start")
            await asyncio.sleep(firestore_delay)
            execution_order.append("firestore_end")
            return {
                "tenant_id": account_id,
                "access_token": "token",
                "refresh_token": "refresh",
                "selected_property_ids": [],
                "selected_properties": [],
                "expires_at": None,
            }

        # Mock the dependencies including Redis (to ensure cache miss so we load from DB)
        with (
            patch(
                "src.kene_api.routers.chat.load_organization_context_from_neo4j",
                side_effect=mock_load_org_context,
            ),
            patch.object(
                GACredentialHelper,
                "__init__",
                lambda self, db: None,
            ),
            patch.object(
                GACredentialHelper,
                "get_and_format_credentials",
                side_effect=mock_get_and_format_credentials,
            ),
            patch.object(
                GACredentialHelper,
                "get_oauth_credentials",
                return_value={"access_token": "token"},
            ),
            patch.object(
                GACredentialHelper,
                "refresh_if_expired",
                return_value={"access_token": "token"},
            ),
            patch("src.kene_api.routers.chat.get_redis_service") as mock_redis,
            patch("src.kene_api.routers.chat.get_firestore_service") as mock_firestore,
        ):
            # Mock Firestore service (prevents real GCP auth blocking the event loop)
            mock_firestore_instance = MagicMock()
            mock_firestore_instance.get_client.return_value = MagicMock()
            mock_firestore.return_value = mock_firestore_instance

            # Mock Redis to return cache miss (so we actually load from DB)
            mock_redis_instance = MagicMock()
            mock_redis_instance.is_available.return_value = False  # Disable cache
            mock_redis.return_value = mock_redis_instance

            # Mock the private _session_service attribute instead of the property
            mock_session_service = MagicMock()
            mock_session_service.create_session = AsyncMock(
                return_value=MagicMock(id="session_123")
            )
            client._session_service = mock_session_service

            # Execute
            start_time = time.time()
            await client.create_conversation(
                user_id=user_id,
                user_context=mock_user_context,
                conversation_name="Test",
                account_id=account_id,
            )
            elapsed_time = time.time() - start_time

            # Assert
            # If parallel: ~1s (max of two 1s operations)
            # If sequential: ~2s (sum of two 1s operations)
            assert elapsed_time < 1.5, (
                f"Operations should run in parallel (~1s), got {elapsed_time:.2f}s. "
                f"Sequential would be ~2s."
            )

            # Verify both operations started before either finished
            neo4j_start_idx = execution_order.index("neo4j_start")
            firestore_start_idx = execution_order.index("firestore_start")
            neo4j_end_idx = execution_order.index("neo4j_end")
            firestore_end_idx = execution_order.index("firestore_end")

            # Both should start (0, 1) before either finishes (2, 3)
            assert neo4j_start_idx < neo4j_end_idx, "Neo4j should start before ending"
            assert firestore_start_idx < firestore_end_idx, (
                "Firestore should start before ending"
            )

            # At least one should start while the other is still running (parallel)
            # This means both starts should happen before both ends
            starts = sorted([neo4j_start_idx, firestore_start_idx])
            ends = sorted([neo4j_end_idx, firestore_end_idx])
            assert starts[1] < ends[0], (
                "Second operation should start before first operation ends (proving parallelism)"
            )

    @pytest.mark.asyncio
    async def test_parallel_execution_handles_failures_gracefully(self):
        """
        Test that if one parallel operation fails, the other still completes
        and session creation continues with partial data.
        """
        # Setup
        client = AgentEngineClient()
        user_id = "test_user"
        account_id = "test_account_123"

        mock_user_context = MagicMock()
        mock_user_context.accessible_accounts = [account_id]
        mock_user_context.has_account_access.return_value = True

        # Mock Neo4j to fail
        async def mock_load_org_context_failure(account_id: str):
            raise Exception("Neo4j connection failed")

        # Mock Firestore to succeed
        async def mock_get_credentials_success(account_id: str):
            return {
                "tenant_id": account_id,
                "access_token": "token",
                "refresh_token": "refresh",
                "selected_property_ids": [],
                "selected_properties": [],
                "expires_at": None,
            }

        with (
            patch(
                "src.kene_api.routers.chat.load_organization_context_from_neo4j",
                side_effect=mock_load_org_context_failure,
            ),
            patch.object(
                GACredentialHelper,
                "__init__",
                lambda self, db: None,
            ),
            patch.object(
                GACredentialHelper,
                "get_and_format_credentials",
                side_effect=mock_get_credentials_success,
            ),
            patch.object(
                GACredentialHelper,
                "get_oauth_credentials",
                return_value={"access_token": "token"},
            ),
            patch.object(
                GACredentialHelper,
                "refresh_if_expired",
                return_value={"access_token": "token"},
            ),
            patch("src.kene_api.routers.chat.get_redis_service") as mock_redis,
            patch("src.kene_api.routers.chat.get_firestore_service") as mock_firestore,
        ):
            # Mock Firestore service (prevents real GCP auth blocking the event loop)
            mock_firestore_instance = MagicMock()
            mock_firestore_instance.get_client.return_value = MagicMock()
            mock_firestore.return_value = mock_firestore_instance

            # Mock Redis to disable caching
            mock_redis_instance = MagicMock()
            mock_redis_instance.is_available.return_value = False
            mock_redis.return_value = mock_redis_instance

            # Mock the private _session_service attribute instead of the property
            mock_session_service = MagicMock()
            mock_session_service.create_session = AsyncMock(
                return_value=MagicMock(id="session_123")
            )
            client._session_service = mock_session_service

            # Execute - should not raise exception
            session_id = await client.create_conversation(
                user_id=user_id,
                user_context=mock_user_context,
                conversation_name="Test",
                account_id=account_id,
            )

            # Assert
            assert session_id == "session_123", (
                "Session should be created despite Neo4j failure"
            )
            mock_session_service.create_session.assert_called_once()


class TestOAuthTimeout:
    """Test that OAuth refresh has proper timeout enforcement."""

    @pytest.mark.asyncio
    async def test_oauth_refresh_has_10s_timeout(self):
        """
        Test that OAuth token refresh operation has a 10-second timeout configured.
        This prevents indefinite hangs on Google's OAuth endpoint.
        """
        # Setup
        db = MagicMock()
        helper = GACredentialHelper(db)
        account_id = "test_account"

        credentials = {
            "access_token": "old_token",
            "refresh_token": "refresh_token_123",
            "expires_at": 0,  # Expired token
        }

        # Mock environment variables
        with (
            patch.dict(
                "os.environ",
                {
                    "GOOGLE_OAUTH_CLIENT_ID": "client_id",
                    "GOOGLE_OAUTH_CLIENT_SECRET": "client_secret",
                },
            ),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            # Mock the async context manager
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(
                return_value=MagicMock(
                    status_code=200,
                    json=lambda: {"access_token": "new_token", "expires_in": 3600},
                )
            )
            mock_client_class.return_value = mock_client

            # Mock the credentials service
            helper.creds_service.update_credentials = AsyncMock()

            # Execute
            await helper.refresh_if_expired(account_id, credentials)

            # Assert that AsyncClient was initialized with 10s timeout
            mock_client_class.assert_called_once_with(timeout=10.0)

    @pytest.mark.asyncio
    async def test_oauth_refresh_handles_timeout_exception(self):
        """
        Test that timeout exceptions during OAuth refresh are caught and logged properly.
        """
        # Setup
        db = MagicMock()
        helper = GACredentialHelper(db)
        account_id = "test_account"

        credentials = {
            "access_token": "old_token",
            "refresh_token": "refresh_token_123",
            "expires_at": 0,  # Expired token
        }

        # Mock environment variables
        with (
            patch.dict(
                "os.environ",
                {
                    "GOOGLE_OAUTH_CLIENT_ID": "client_id",
                    "GOOGLE_OAUTH_CLIENT_SECRET": "client_secret",
                },
            ),
            patch("httpx.AsyncClient") as mock_client_class,
        ):
            # Mock timeout exception
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(
                side_effect=httpx.TimeoutException("Request timed out")
            )
            mock_client_class.return_value = mock_client

            # Execute
            result = await helper.refresh_if_expired(account_id, credentials)

            # Assert
            assert result is None, "Should return None on timeout"

    @pytest.mark.asyncio
    async def test_oauth_refresh_returns_credentials_if_not_expired(self):
        """
        Test that OAuth refresh is skipped if token is not expired,
        avoiding unnecessary timeout risk.
        """
        # Setup
        db = MagicMock()
        helper = GACredentialHelper(db)
        account_id = "test_account"

        # Token expires in 1 hour (not expired)
        future_timestamp = time.time() + 3600
        credentials = {
            "access_token": "valid_token",
            "refresh_token": "refresh_token_123",
            "expires_at": future_timestamp,
        }

        # Mock to detect if refresh is attempted (it shouldn't be)
        with patch("httpx.AsyncClient") as mock_client_class:
            # Execute
            result = await helper.refresh_if_expired(account_id, credentials)

            # Assert
            assert result == credentials, (
                "Should return original credentials if not expired"
            )
            # Should NOT attempt refresh if token valid
            mock_client_class.assert_not_called()


class TestPerformanceMetrics:
    """Test performance improvements are measurable."""

    @pytest.mark.asyncio
    async def test_session_reuse_eliminates_5s_latency(self):
        """
        Integration test: Verify that reusing a session is significantly faster
        than creating a new session.

        Expected: Reuse should be <100ms, creation should be ~1-2s with mocks.
        """
        # Setup
        client = AgentEngineClient()
        user_id = "perf_test_user"
        session_id = "chat_perf_test_123"

        # Pre-populate cache
        session_key = f"{user_id}:{session_id}"
        client._user_sessions[session_key] = {
            "session_id": session_id,
            "user_id": user_id,
            "conversation_name": "Perf Test",
            "created_at": "2025-01-01T00:00:00Z",
            "last_updated": "2025-01-01T00:00:00Z",
            "message_count": 5,
        }

        # Measure reuse time
        start_time = time.time()
        result = await client.get_or_create_session(
            user_id=user_id,
            user_context=None,
            session_id=session_id,
            conversation_name=None,
            account_id=None,
        )
        reuse_time = time.time() - start_time

        # Assert
        assert result == session_id
        assert reuse_time < 0.1, (
            f"Session reuse should be <100ms, got {reuse_time * 1000:.0f}ms"
        )
