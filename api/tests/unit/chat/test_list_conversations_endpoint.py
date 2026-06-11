"""Unit tests for the two-branch GET /conversations handler (CH-14).

Tests are purely in-process — they mock is_feature_enabled,
get_chat_side_table_service, and agent_client.get_user_conversations so
neither Firestore nor Vertex AI is contacted.

Run:
    cd api && uv run pytest tests/unit/chat/test_list_conversations_endpoint.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.kene_api.auth.models import UserContext
from src.kene_api.models.chat import (
    ChatSessionMetadata,
    ChatSessionSidebarItem,
    ListChatSessionsResponse,
)
from src.kene_api.routers.chat import (
    ConversationInfo,
    ConversationListResponse,
    _metadata_to_conversation_info,
)

_NOW = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)

_ACCOUNT_ID = "acc_1234567890"
_USER_ID = "user_abc"
_ORG_ID = "org_xyz"


def _make_user_context(
    account_ids: list[str] | None = None,
    *,
    super_admin: bool = False,
    org_admin: bool = False,
) -> UserContext:
    """Build a minimal UserContext for tests."""
    if account_ids is None:
        account_ids = [_ACCOUNT_ID]
    perms = dict.fromkeys(account_ids, "edit")
    org_perms = {_ORG_ID: "admin"} if org_admin else {}
    ctx = UserContext(
        user_id=_USER_ID,
        email="user@test.com",
        organization_permissions=org_perms,
        account_permissions=perms,
        roles=["super_admin"] if super_admin else [],
    )
    return ctx


def _make_metadata(
    session_id: str = "sess_001",
    title: str | None = "Test session",
    message_count: int = 3,
    last_message_preview: str | None = "Hello there",
) -> ChatSessionMetadata:
    return ChatSessionMetadata(
        session_id=session_id,
        user_id=_USER_ID,
        account_id=_ACCOUNT_ID,
        organization_id=_ORG_ID,
        model_id="gemini-2.5-flash",
        title=title,
        message_count=message_count,
        last_message_preview=last_message_preview,
        created_at=_NOW,
        updated_at=_NOW,
        last_agent_started_at=_NOW,
        last_agent_stopped_at=_NOW,
        last_viewed_at=_NOW,
    )


# ---------------------------------------------------------------------------
# _metadata_to_conversation_info mapping
# ---------------------------------------------------------------------------


class TestMetadataToConversationInfo:
    def test_title_mapped_to_conversation_name(self) -> None:
        m = _make_metadata(title="My title")
        info = _metadata_to_conversation_info(m)
        assert info.conversation_name == "My title"

    def test_null_title_passed_through(self) -> None:
        """Null title must reach the frontend as None (PRD-02 §4.1)."""
        m = _make_metadata(title=None)
        info = _metadata_to_conversation_info(m)
        assert info.conversation_name is None

    def test_timestamps_pass_through(self) -> None:
        m = _make_metadata()
        info = _metadata_to_conversation_info(m)
        assert info.last_agent_started_at == _NOW
        assert info.last_agent_stopped_at == _NOW
        assert info.last_viewed_at == _NOW

    def test_message_count_and_preview(self) -> None:
        m = _make_metadata(message_count=7, last_message_preview="hi")
        info = _metadata_to_conversation_info(m)
        assert info.message_count == 7
        assert info.preview == "hi"

    def test_returns_conversation_info_instance(self) -> None:
        m = _make_metadata()
        assert isinstance(_metadata_to_conversation_info(m), ConversationInfo)


# ---------------------------------------------------------------------------
# Handler: flag-on branch
# ---------------------------------------------------------------------------


class TestListConversationsFlagOn:
    """When chat_v2_enabled=True, the handler uses the side-table service."""

    async def _run(
        self,
        metadata_rows: list[ChatSessionMetadata],
        next_cursor: str | None,
        user_context: UserContext,
        *,
        cursor: str | None = None,
        category_id: str | None = None,
        query: str | None = None,
        limit: int = 20,
        account_id: str | None = None,
        resolver_org_id: str = _ORG_ID,
    ) -> ListChatSessionsResponse | ConversationListResponse:
        """Drive the handler via AsyncMock + patch.

        resolver_org_id: the org returned by the owning-org resolver. Defaults to
        _ORG_ID which the default _make_user_context() user has edit access to.
        """
        from src.kene_api.routers.chat import list_conversations

        mock_svc = MagicMock()
        mock_svc.list_for_user.return_value = (metadata_rows, next_cursor)

        with (
            patch(
                "src.kene_api.routers.chat.is_feature_enabled",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "src.kene_api.routers.chat.get_chat_side_table_service",
                return_value=mock_svc,
            ),
            patch(
                "src.kene_api.auth.account_org.resolve_owning_organization_id",
                new=AsyncMock(return_value=resolver_org_id),
            ),
        ):
            return await list_conversations(
                cursor=cursor,
                category_id=category_id,
                query=query,
                limit=limit,
                account_id=account_id,
                user_context=user_context,
            )

    @pytest.mark.asyncio
    async def test_happy_path_returns_side_table_rows(self) -> None:
        rows = [_make_metadata("s1"), _make_metadata("s2")]
        resp = await self._run(rows, None, _make_user_context())
        assert isinstance(resp, ListChatSessionsResponse)
        assert len(resp.items) == 2
        assert resp.items[0].session_id == "s1"
        assert resp.items[1].session_id == "s2"
        assert resp.next_cursor is None

    @pytest.mark.asyncio
    async def test_next_cursor_propagated(self) -> None:
        rows = [_make_metadata()]
        resp = await self._run(rows, "cursor_xyz", _make_user_context())
        assert resp.next_cursor == "cursor_xyz"

    @pytest.mark.asyncio
    async def test_items_are_sidebar_items(self) -> None:
        rows = [_make_metadata()]
        resp = await self._run(rows, None, _make_user_context())
        assert isinstance(resp, ListChatSessionsResponse)
        assert all(isinstance(item, ChatSessionSidebarItem) for item in resp.items)

    @pytest.mark.asyncio
    async def test_explicit_account_id_forwarded_to_service(self) -> None:
        from src.kene_api.routers.chat import list_conversations

        mock_svc = MagicMock()
        mock_svc.list_for_user.return_value = ([], None)

        with (
            patch(
                "src.kene_api.routers.chat.is_feature_enabled",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "src.kene_api.routers.chat.get_chat_side_table_service",
                return_value=mock_svc,
            ),
            patch(
                "src.kene_api.auth.account_org.resolve_owning_organization_id",
                new=AsyncMock(return_value=_ORG_ID),
            ),
        ):
            await list_conversations(
                cursor=None,
                category_id="cat_abc",
                query="revenue",
                limit=5,
                account_id=_ACCOUNT_ID,
                user_context=_make_user_context(),
            )

        mock_svc.list_for_user.assert_called_once_with(
            user_id=_USER_ID,
            account_id=_ACCOUNT_ID,
            cursor=None,
            category_id="cat_abc",
            query="revenue",
            limit=5,
        )

    @pytest.mark.asyncio
    async def test_no_account_id_defaults_to_first_accessible(self) -> None:
        from src.kene_api.routers.chat import list_conversations

        mock_svc = MagicMock()
        mock_svc.list_for_user.return_value = ([], None)

        with (
            patch(
                "src.kene_api.routers.chat.is_feature_enabled",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "src.kene_api.routers.chat.get_chat_side_table_service",
                return_value=mock_svc,
            ),
            patch(
                "src.kene_api.auth.account_org.resolve_owning_organization_id",
                new=AsyncMock(return_value=_ORG_ID),
            ),
        ):
            await list_conversations(
                cursor=None,
                category_id=None,
                query=None,
                limit=20,
                account_id=None,
                user_context=_make_user_context(["acc_first_one", "acc_second"]),
            )

        call_kwargs = mock_svc.list_for_user.call_args.kwargs
        assert call_kwargs["account_id"] == "acc_first_one"

    @pytest.mark.asyncio
    async def test_no_account_id_and_no_accessible_accounts_returns_empty(
        self,
    ) -> None:
        resp = await self._run(
            [],
            None,
            _make_user_context(account_ids=[]),
            account_id=None,
        )
        assert isinstance(resp, ListChatSessionsResponse)
        assert resp.items == []
        assert resp.next_cursor is None

    @pytest.mark.asyncio
    async def test_cross_account_access_raises_403(self) -> None:
        """Access denied (404 per IN-2 anti-enumeration contract) when account belongs to a different org."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            # User has access to _ACCOUNT_ID in _ORG_ID; "acc_other" belongs to "org_other"
            await self._run(
                [],
                None,
                _make_user_context([_ACCOUNT_ID]),
                account_id="acc_other_9876543210",
                resolver_org_id="org_other",  # account belongs to a different org
            )

        # IN-2: denial is 404 (anti-enumeration) not 403
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Handler: flag-off branch (legacy path)
# ---------------------------------------------------------------------------


class TestListConversationsFlagOff:
    """When chat_v2_enabled=False, the legacy in-memory + ADK path runs."""

    async def _run_legacy(
        self,
        legacy_convs: list[ConversationInfo],
        *,
        cursor: str | None = "cursor_ignored",
        category_id: str | None = "cat_ignored",
        query: str | None = "query_ignored",
        limit: int = 5,
        account_id: str | None = "acc_ignored_0123456789",
    ) -> ConversationListResponse:
        from src.kene_api.routers.chat import list_conversations

        with (
            patch(
                "src.kene_api.routers.chat.is_feature_enabled",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "src.kene_api.routers.chat.agent_client.get_user_conversations",
                new=AsyncMock(return_value=legacy_convs),
            ),
        ):
            return await list_conversations(
                cursor=cursor,
                category_id=category_id,
                query=query,
                limit=limit,
                account_id=account_id,
                user_context=_make_user_context(),
            )

    def _make_conv_info(self, session_id: str = "legacy_s1") -> ConversationInfo:
        return ConversationInfo(
            session_id=session_id,
            conversation_name=f"Chat {session_id[-8:]}",
            created_at=_NOW,
            last_updated=_NOW,
            message_count=1,
        )

    @pytest.mark.asyncio
    async def test_legacy_path_returns_all_conversations(self) -> None:
        convs = [self._make_conv_info("s1"), self._make_conv_info("s2")]
        resp = await self._run_legacy(convs)
        assert len(resp.conversations) == 2

    @pytest.mark.asyncio
    async def test_legacy_path_next_cursor_is_none(self) -> None:
        resp = await self._run_legacy([self._make_conv_info()])
        assert resp.next_cursor is None

    @pytest.mark.asyncio
    async def test_legacy_path_ignores_new_query_params(self) -> None:
        """New params must not cause errors on the legacy path."""
        resp = await self._run_legacy(
            [],
            cursor="some_cursor",
            category_id="cat_123",
            query="anything",
            limit=99,
            account_id="acc_ignored_0123456789",
        )
        assert resp.next_cursor is None
