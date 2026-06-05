"""Unit tests for per-turn Google Analytics credential refresh + cache hygiene.

Covers the fix for the GA Specialist 401/"requires_reauth" bug: ga_credentials
was injected into ADK session state only at conversation creation, so a session
created before the user connected GA kept absent/stale credentials and the GA
MCP tool 401'd. The fix:

* ``_load_ga_credentials`` — shared loader; a cached token is only reused while
  fresh (stale cached token falls through to a Firestore load + refresh).
* ``_ensure_session_ga_credentials`` — injects fresh creds into an existing
  session's state per turn (idempotent, best-effort).
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.kene_api.routers.chat import AgentEngineClient

ACCOUNT_ID = "acc_ga_refresh_test"


def _fresh_creds(token: str = "tok") -> dict:
    return {"access_token": token, "expires_at": time.time() + 3600}


def _stale_creds(token: str = "old") -> dict:
    return {"access_token": token, "expires_at": time.time() - 10}


class TestGaTokenIsFresh:
    def test_fresh_token_is_fresh(self):
        assert AgentEngineClient._ga_token_is_fresh(_fresh_creds()) is True

    def test_expired_token_is_not_fresh(self):
        assert AgentEngineClient._ga_token_is_fresh(_stale_creds()) is False

    def test_missing_access_token_is_not_fresh(self):
        assert (
            AgentEngineClient._ga_token_is_fresh({"expires_at": time.time() + 3600})
            is False
        )

    def test_missing_expiry_is_not_fresh(self):
        assert AgentEngineClient._ga_token_is_fresh({"access_token": "t"}) is False


class TestGaTokenFingerprint:
    """Must be non-reversible, stable, and identical to the engine-side
    implementation (app/adk/security/hooks._ga_token_fingerprint) so the
    injection log and the tool-hook log correlate across deploy trees."""

    def test_absent_for_empty_token(self):
        assert AgentEngineClient._ga_token_fingerprint(None) == "absent"
        assert AgentEngineClient._ga_token_fingerprint("") == "absent"

    def test_matches_canonical_sha256_prefix(self):
        import hashlib

        token = "ya29.some-access-token"
        expected = hashlib.sha256(token.encode()).hexdigest()[:8]
        assert AgentEngineClient._ga_token_fingerprint(token) == expected
        assert len(AgentEngineClient._ga_token_fingerprint(token)) == 8


class TestLoadGaCredentials:
    @pytest.mark.asyncio
    async def test_fresh_cache_hit_skips_firestore(self):
        mock_redis = MagicMock()
        mock_redis.is_available.return_value = True
        mock_redis.get_json.return_value = _fresh_creds("cached")

        with (
            patch(
                "src.kene_api.routers.chat.get_redis_service", return_value=mock_redis
            ),
            patch(
                "src.kene_api.routers.chat.get_firestore_service"
            ) as mock_firestore,
        ):
            client = AgentEngineClient()
            result = await client._load_ga_credentials(ACCOUNT_ID)

        assert result["access_token"] == "cached"
        mock_firestore.assert_not_called()  # fresh cache → no Firestore round-trip

    @pytest.mark.asyncio
    async def test_stale_cache_hit_refreshes_from_firestore(self):
        mock_redis = MagicMock()
        mock_redis.is_available.return_value = True
        mock_redis.get_json.return_value = _stale_creds("old")

        ga_helper = MagicMock()
        ga_helper.get_and_format_credentials = AsyncMock(
            return_value={
                "tenant_id": ACCOUNT_ID,
                "selected_property_ids": [],
                "selected_properties": [],
            }
        )
        ga_helper.get_oauth_credentials = AsyncMock(
            return_value={
                "access_token": "refreshed",
                "refresh_token": "r",
                "expires_at": time.time() + 3600,
            }
        )
        ga_helper.refresh_if_expired = AsyncMock(
            side_effect=lambda _a, creds: creds
        )

        with (
            patch(
                "src.kene_api.routers.chat.get_redis_service", return_value=mock_redis
            ),
            patch("src.kene_api.routers.chat.get_firestore_service"),
            patch(
                "src.kene_api.routers.chat.GACredentialHelper", return_value=ga_helper
            ),
            patch(
                "src.kene_api.routers.chat.get_env_or_secret", return_value="secret"
            ),
        ):
            client = AgentEngineClient()
            result = await client._load_ga_credentials(ACCOUNT_ID)

        # Stale cache must not be served — the refreshed Firestore token wins.
        assert result["access_token"] == "refreshed"

    @pytest.mark.asyncio
    async def test_returns_none_and_caches_sentinel_when_not_connected(self):
        mock_redis = MagicMock()
        mock_redis.is_available.return_value = True
        mock_redis.get_json.return_value = None  # cache miss

        ga_helper = MagicMock()
        ga_helper.get_and_format_credentials = AsyncMock(return_value=None)

        with (
            patch(
                "src.kene_api.routers.chat.get_redis_service", return_value=mock_redis
            ),
            patch("src.kene_api.routers.chat.get_firestore_service"),
            patch(
                "src.kene_api.routers.chat.GACredentialHelper", return_value=ga_helper
            ),
        ):
            client = AgentEngineClient()
            result = await client._load_ga_credentials(ACCOUNT_ID)

        assert result is None
        # A negative sentinel is cached so the next turn skips Firestore.
        cached_value = mock_redis.set_json.call_args.args[1]
        assert cached_value == {"_ga_not_connected": True}

    @pytest.mark.asyncio
    async def test_not_connected_sentinel_cache_hit_skips_firestore(self):
        mock_redis = MagicMock()
        mock_redis.is_available.return_value = True
        mock_redis.get_json.return_value = {"_ga_not_connected": True}

        with (
            patch(
                "src.kene_api.routers.chat.get_redis_service", return_value=mock_redis
            ),
            patch(
                "src.kene_api.routers.chat.get_firestore_service"
            ) as mock_firestore,
        ):
            client = AgentEngineClient()
            result = await client._load_ga_credentials(ACCOUNT_ID)

        assert result is None
        mock_firestore.assert_not_called()


class TestEnsureSessionGaCredentials:
    def _client_with_session(self, state: dict) -> tuple[AgentEngineClient, MagicMock]:
        client = AgentEngineClient()
        session = MagicMock()
        session.state = state
        svc = MagicMock()
        svc.get_session = AsyncMock(return_value=session)
        svc.append_event = AsyncMock()
        client._session_service = svc
        return client, svc

    @pytest.mark.asyncio
    async def test_injects_credentials_into_existing_session(self):
        client, svc = self._client_with_session(state={})
        client._load_ga_credentials = AsyncMock(return_value=_fresh_creds("T"))

        await client._ensure_session_ga_credentials(
            "user1", "sess1", ACCOUNT_ID, user_context=None
        )

        svc.append_event.assert_awaited_once()
        _session_arg, event_arg = svc.append_event.await_args.args
        assert event_arg.actions.state_delta["ga_credentials"]["access_token"] == "T"
        # The Vertex Sessions API rejects an event with an empty invocation_id
        # (ADK defaults it to ""), which would silently no-op the whole refresh.
        assert event_arg.invocation_id, "injected event must carry an invocation_id"

    @pytest.mark.asyncio
    async def test_skips_write_when_token_already_current(self):
        client, svc = self._client_with_session(
            state={"ga_credentials": {"access_token": "T"}}
        )
        client._load_ga_credentials = AsyncMock(return_value=_fresh_creds("T"))

        await client._ensure_session_ga_credentials(
            "user1", "sess1", ACCOUNT_ID, user_context=None
        )

        svc.append_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_noop_when_ga_not_connected(self):
        client, svc = self._client_with_session(state={})
        client._load_ga_credentials = AsyncMock(return_value=None)

        await client._ensure_session_ga_credentials(
            "user1", "sess1", ACCOUNT_ID, user_context=None
        )

        svc.get_session.assert_not_awaited()
        svc.append_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_property_selection_change_propagates(self):
        """A Manage-Properties change (same token, different selected_property_ids)
        must re-inject into the existing session — the dedup keys on the full
        signature, not the access token alone."""
        client, svc = self._client_with_session(
            state={"ga_credentials": {"access_token": "T", "selected_property_ids": ["1"]}}
        )
        client._load_ga_credentials = AsyncMock(
            return_value={
                "access_token": "T",
                "selected_property_ids": ["1", "2"],
                "expires_at": time.time() + 3600,
            }
        )
        mock_redis = MagicMock()
        mock_redis.is_available.return_value = True
        mock_redis.get_json.return_value = None  # no marker → no fast-path skip

        with patch(
            "src.kene_api.routers.chat.get_redis_service", return_value=mock_redis
        ):
            await client._ensure_session_ga_credentials(
                "user1", "sess1", ACCOUNT_ID, user_context=None
            )

        svc.append_event.assert_awaited_once()
        _session_arg, event_arg = svc.append_event.await_args.args
        assert event_arg.actions.state_delta["ga_credentials"]["selected_property_ids"] == [
            "1",
            "2",
        ]
        # Marker updated to the new signature so future turns short-circuit.
        assert mock_redis.set_json.call_args.args[1] == {"sig": "T|1,2"}

    @pytest.mark.asyncio
    async def test_skips_write_when_token_and_properties_unchanged(self):
        client, svc = self._client_with_session(
            state={"ga_credentials": {"access_token": "T", "selected_property_ids": ["1"]}}
        )
        client._load_ga_credentials = AsyncMock(
            return_value={
                "access_token": "T",
                "selected_property_ids": ["1"],
                "expires_at": time.time() + 3600,
            }
        )
        mock_redis = MagicMock()
        mock_redis.is_available.return_value = True
        mock_redis.get_json.return_value = None

        with patch(
            "src.kene_api.routers.chat.get_redis_service", return_value=mock_redis
        ):
            await client._ensure_session_ga_credentials(
                "user1", "sess1", ACCOUNT_ID, user_context=None
            )

        svc.append_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_marker_fast_path_skips_get_session(self):
        """A Redis marker matching the loaded signature short-circuits before the
        Vertex get_session round-trip."""
        client, svc = self._client_with_session(state={})
        client._load_ga_credentials = AsyncMock(return_value=_fresh_creds("T"))
        mock_redis = MagicMock()
        mock_redis.is_available.return_value = True
        mock_redis.get_json.return_value = {"sig": "T|"}  # matches _fresh_creds("T")

        with patch(
            "src.kene_api.routers.chat.get_redis_service", return_value=mock_redis
        ):
            await client._ensure_session_ga_credentials(
                "user1", "sess1", ACCOUNT_ID, user_context=None
            )

        svc.get_session.assert_not_awaited()
        svc.append_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_marker_miss_writes_and_records_marker(self):
        client, svc = self._client_with_session(state={})
        client._load_ga_credentials = AsyncMock(return_value=_fresh_creds("T"))
        mock_redis = MagicMock()
        mock_redis.is_available.return_value = True
        mock_redis.get_json.return_value = None  # no marker

        with patch(
            "src.kene_api.routers.chat.get_redis_service", return_value=mock_redis
        ):
            await client._ensure_session_ga_credentials(
                "user1", "sess1", ACCOUNT_ID, user_context=None
            )

        svc.get_session.assert_awaited_once()
        svc.append_event.assert_awaited_once()
        assert mock_redis.set_json.call_args.args[1] == {"sig": "T|"}

    @pytest.mark.asyncio
    async def test_account_resolved_from_session_not_accessible_accounts(self):
        """When account_id is None, resolve the conversation's own account from
        session state — never user_context.accessible_accounts[0], which may be a
        different account than this conversation belongs to."""
        client, _svc = self._client_with_session(state={"account_id": "right_acc"})
        client._load_ga_credentials = AsyncMock(return_value=None)
        user_context = MagicMock()
        user_context.accessible_accounts = ["wrong_acc"]
        mock_redis = MagicMock()
        mock_redis.is_available.return_value = False

        with patch(
            "src.kene_api.routers.chat.get_redis_service", return_value=mock_redis
        ):
            await client._ensure_session_ga_credentials(
                "user1", "sess1", None, user_context=user_context
            )

        client._load_ga_credentials.assert_awaited_once_with("right_acc")
