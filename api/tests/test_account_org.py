"""Unit tests for the account → organization resolver."""

import logging
import time
from unittest.mock import AsyncMock, patch

import pytest

_RESOLVER = "src.kene_api.auth.account_org"


@pytest.fixture(autouse=True)
def reset_account_org_globals():
    """Restore cache and time provider after every test."""
    from src.kene_api.auth.account_org import _clear_cache, _set_time_provider

    _clear_cache()
    yield
    _clear_cache()
    _set_time_provider(time.monotonic)


class TestResolveOwningOrganizationId:
    """Tests for resolve_owning_organization_id."""

    @pytest.mark.asyncio
    async def test_happy_path_returns_org_id(self):
        """Returns the organization_id when a :BELONGS_TO edge exists."""
        from src.kene_api.auth.account_org import resolve_owning_organization_id

        mock_result = [{"organization_id": "org_abc"}]
        with patch(
            f"{_RESOLVER}.neo4j_service.execute_query",
            AsyncMock(return_value=mock_result),
        ):
            result = await resolve_owning_organization_id("acc_123")

        assert result == "org_abc"

    @pytest.mark.asyncio
    async def test_no_match_returns_none(self):
        """Returns None when the account has no owning organization."""
        from src.kene_api.auth.account_org import resolve_owning_organization_id

        with patch(
            f"{_RESOLVER}.neo4j_service.execute_query",
            AsyncMock(return_value=[]),
        ):
            result = await resolve_owning_organization_id("acc_unknown")

        assert result is None

    @pytest.mark.asyncio
    async def test_neo4j_exception_returns_none_and_logs_warning(self, caplog):
        """Returns None and logs a WARNING when Neo4j raises."""
        from src.kene_api.auth.account_org import resolve_owning_organization_id

        with patch(
            f"{_RESOLVER}.neo4j_service.execute_query",
            AsyncMock(side_effect=RuntimeError("connection refused")),
        ):
            with caplog.at_level(logging.WARNING, logger="src.kene_api.auth.account_org"):
                result = await resolve_owning_organization_id("acc_123")

        assert result is None
        assert any(
            "resolve_owning_organization_id" in rec.message for rec in caplog.records
        )


class TestResolveOwningOrganizationIdCache:
    """Tests for the TTL cache behaviour of resolve_owning_organization_id."""

    @pytest.mark.asyncio
    async def test_second_call_within_ttl_hits_cache(self):
        """Repeated calls within TTL issue exactly one Neo4j query."""
        from src.kene_api.auth.account_org import (
            _set_time_provider,
            resolve_owning_organization_id,
        )

        now = 1_000.0
        _set_time_provider(lambda: now)

        mock_query = AsyncMock(return_value=[{"organization_id": "org_x"}])
        with patch(f"{_RESOLVER}.neo4j_service.execute_query", mock_query):
            for _ in range(5):
                result = await resolve_owning_organization_id("acc_cache")

        assert result == "org_x"
        assert mock_query.call_count == 1

    @pytest.mark.asyncio
    async def test_call_after_ttl_expires_re_issues_query(self):
        """After the TTL window expires the resolver queries Neo4j again."""
        import src.kene_api.auth.account_org as _mod
        from src.kene_api.auth.account_org import (
            _set_time_provider,
            resolve_owning_organization_id,
        )

        tick = [0.0]

        def fake_time() -> float:
            return tick[0]

        _set_time_provider(fake_time)
        ttl = _mod._DEFAULT_TTL

        mock_query = AsyncMock(return_value=[{"organization_id": "org_y"}])
        with patch(f"{_RESOLVER}.neo4j_service.execute_query", mock_query):
            # First call — cold cache.
            await resolve_owning_organization_id("acc_ttl")
            assert mock_query.call_count == 1

            # Advance time past the TTL.
            tick[0] = ttl + 1.0

            # Second call — cache expired.
            await resolve_owning_organization_id("acc_ttl")
            assert mock_query.call_count == 2

    @pytest.mark.asyncio
    async def test_transient_neo4j_error_not_cached(self):
        """A transient Neo4j exception is not cached; next call retries."""
        from src.kene_api.auth.account_org import (
            _set_time_provider,
            resolve_owning_organization_id,
        )

        now = 1_000.0
        _set_time_provider(lambda: now)

        error_then_ok = AsyncMock(
            side_effect=[
                RuntimeError("Neo4j down"),
                [{"organization_id": "org_z"}],
            ]
        )
        with patch(f"{_RESOLVER}.neo4j_service.execute_query", error_then_ok):
            # First call — exception, returns None, NOT cached.
            result1 = await resolve_owning_organization_id("acc_err")
            assert result1 is None

            # Second call at same timestamp — cache miss because error was not cached.
            result2 = await resolve_owning_organization_id("acc_err")
            assert result2 == "org_z"

        assert error_then_ok.call_count == 2

    @pytest.mark.asyncio
    async def test_confirmed_none_miss_not_cached_by_default(self):
        """By default (MISS_TTL=0) a confirmed account-not-found is NOT cached."""
        from src.kene_api.auth.account_org import (
            _set_time_provider,
            resolve_owning_organization_id,
        )

        now = 1_000.0
        _set_time_provider(lambda: now)

        mock_query = AsyncMock(return_value=[])
        with patch(f"{_RESOLVER}.neo4j_service.execute_query", mock_query):
            for _ in range(3):
                result = await resolve_owning_organization_id("acc_missing")

        assert result is None
        # Default MISS_TTL is 0 — each call should re-query Neo4j.
        assert mock_query.call_count == 3

    @pytest.mark.asyncio
    async def test_confirmed_none_miss_cached_when_miss_ttl_set(self):
        """When MISS_TTL > 0, confirmed misses are cached."""
        import src.kene_api.auth.account_org as _mod
        from src.kene_api.auth.account_org import (
            _set_time_provider,
            resolve_owning_organization_id,
        )

        original_miss_ttl = _mod._MISS_TTL
        _mod._MISS_TTL = 60.0
        try:
            now = 1_000.0
            _set_time_provider(lambda: now)

            mock_query = AsyncMock(return_value=[])
            with patch(f"{_RESOLVER}.neo4j_service.execute_query", mock_query):
                for _ in range(3):
                    result = await resolve_owning_organization_id("acc_miss_cached")

            assert result is None
            assert mock_query.call_count == 1
        finally:
            _mod._MISS_TTL = original_miss_ttl


class TestComputeAccountAccessLevel:
    """Tests for the compute_account_access_level helper."""

    @pytest.fixture
    def super_admin(self):
        from src.kene_api.auth.models import UserContext

        return UserContext(
            user_id="sa1",
            email="sa@ken-e.ai",
            organization_permissions={},
            account_permissions={},
            roles=["super_admin"],
        )

    @pytest.fixture
    def org_admin(self):
        from src.kene_api.auth.models import UserContext

        return UserContext(
            user_id="oa1",
            email="admin@org-a.com",
            organization_permissions={"org_A": "admin"},
            account_permissions={},
        )

    @pytest.fixture
    def account_editor(self):
        from src.kene_api.auth.models import UserContext

        return UserContext(
            user_id="e1",
            email="editor@org-a.com",
            organization_permissions={},
            account_permissions={"acc_a": "edit"},
        )

    @pytest.fixture
    def account_viewer(self):
        from src.kene_api.auth.models import UserContext

        return UserContext(
            user_id="v1",
            email="viewer@org-a.com",
            organization_permissions={},
            account_permissions={"acc_a": "view"},
        )

    @pytest.fixture
    def no_access_user(self):
        from src.kene_api.auth.models import UserContext

        return UserContext(
            user_id="n1",
            email="nobody@example.com",
            organization_permissions={},
            account_permissions={},
        )

    @pytest.mark.asyncio
    async def test_super_admin_returns_admin_without_resolver(self, super_admin):
        """Super-admin returns 'admin' without calling the resolver."""
        from src.kene_api.auth.account_org import compute_account_access_level

        with patch(
            f"{_RESOLVER}.neo4j_service.execute_query",
            AsyncMock(side_effect=AssertionError("resolver must not be called")),
        ):
            result = await compute_account_access_level(super_admin, "any_acc")

        assert result == "admin"

    @pytest.mark.asyncio
    async def test_org_admin_returns_edit(self, org_admin):
        """Org admin of the owning org returns 'edit'."""
        from src.kene_api.auth.account_org import compute_account_access_level

        with patch(
            f"{_RESOLVER}.neo4j_service.execute_query",
            AsyncMock(return_value=[{"organization_id": "org_A"}]),
        ):
            result = await compute_account_access_level(org_admin, "acc_a")

        assert result == "edit"

    @pytest.mark.asyncio
    async def test_explicit_editor_returns_edit(self, account_editor):
        """Explicit edit permission returns 'edit'."""
        from src.kene_api.auth.account_org import compute_account_access_level

        with patch(
            f"{_RESOLVER}.neo4j_service.execute_query",
            AsyncMock(return_value=[{"organization_id": "org_X"}]),
        ):
            result = await compute_account_access_level(account_editor, "acc_a")

        assert result == "edit"

    @pytest.mark.asyncio
    async def test_view_only_returns_view(self, account_viewer):
        """View-only permission returns 'view'."""
        from src.kene_api.auth.account_org import compute_account_access_level

        with patch(
            f"{_RESOLVER}.neo4j_service.execute_query",
            AsyncMock(return_value=[{"organization_id": "org_X"}]),
        ):
            result = await compute_account_access_level(account_viewer, "acc_a")

        assert result == "view"

    @pytest.mark.asyncio
    async def test_no_access_returns_none(self, no_access_user):
        """User with no permissions returns None."""
        from src.kene_api.auth.account_org import compute_account_access_level

        with patch(
            f"{_RESOLVER}.neo4j_service.execute_query",
            AsyncMock(return_value=[{"organization_id": "org_A"}]),
        ):
            result = await compute_account_access_level(no_access_user, "acc_a")

        assert result is None

    @pytest.mark.asyncio
    async def test_resolver_miss_returns_none(self, org_admin):
        """Returns None when the account's org cannot be resolved."""
        from src.kene_api.auth.account_org import compute_account_access_level

        with patch(
            f"{_RESOLVER}.neo4j_service.execute_query",
            AsyncMock(return_value=[]),
        ):
            result = await compute_account_access_level(org_admin, "acc_unknown")

        assert result is None

    @pytest.mark.asyncio
    async def test_reuses_cache_no_second_neo4j_call(self, account_editor):
        """Two calls in a row use the cache; only one Neo4j query fires."""
        from src.kene_api.auth.account_org import (
            _set_time_provider,
            compute_account_access_level,
        )

        now = 1_000.0
        _set_time_provider(lambda: now)

        mock_query = AsyncMock(return_value=[{"organization_id": "org_X"}])
        with patch(f"{_RESOLVER}.neo4j_service.execute_query", mock_query):
            r1 = await compute_account_access_level(account_editor, "acc_a")
            r2 = await compute_account_access_level(account_editor, "acc_a")

        assert r1 == "edit"
        assert r2 == "edit"
        assert mock_query.call_count == 1
