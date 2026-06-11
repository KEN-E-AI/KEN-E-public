"""Integration tests for chat API authorization checks.

Tests that account_id parameter is properly validated and unauthorized
access attempts are rejected. In IN-2, the response code changed from 403 to 404
(anti-enumeration, consistent with the IN-1 contract).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.auth.models import UserContext
from src.kene_api.routers.chat import agent_client

_RESOLVER = "src.kene_api.auth.account_org.resolve_owning_organization_id"


@pytest.mark.asyncio
async def test_chat_completion_rejects_unauthorized_account():
    """Should return 404 when user tries to access an account in a different org (IN-2)."""
    user_context = UserContext(
        user_id="user_123",
        email="test@example.com",
        organization_permissions={"org_A": "admin"},
        account_permissions={},
    )

    with patch.object(agent_client, "chat_completion", new_callable=AsyncMock) as mock_chat:
        from src.kene_api.routers.chat import ChatMessage, ChatRequest, chat_completion

        request = ChatRequest(
            messages=[ChatMessage(role="user", content="test")],
            account_id="acc_org_b_xyz",  # Belongs to org_B — user is admin of org_A only
        )

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc_info:
                await chat_completion(request, user_context)

        assert exc_info.value.status_code == 404
        mock_chat.assert_not_called()


@pytest.mark.asyncio
async def test_chat_completion_allows_authorized_account():
    """Should allow access when user is admin of the account's owning org."""
    user_context = UserContext(
        user_id="user_123",
        email="test@example.com",
        organization_permissions={"org_A": "admin"},
        account_permissions={},
    )

    with patch.object(agent_client, "chat_completion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = ("Response", "session_123", False)

        from src.kene_api.routers.chat import ChatMessage, ChatRequest, chat_completion

        request = ChatRequest(
            messages=[ChatMessage(role="user", content="test")],
            account_id="acc_org_a_xyz",  # Belongs to org_A
        )

        with patch(_RESOLVER, AsyncMock(return_value="org_A")):
            response = await chat_completion(request, user_context)

        assert mock_chat.called
        call_kwargs = mock_chat.call_args.kwargs
        assert call_kwargs["account_id"] == "acc_org_a_xyz"


@pytest.mark.asyncio
async def test_create_conversation_rejects_unauthorized_account():
    """Should return 404 when creating conversation for cross-org account (IN-2)."""
    user_context = UserContext(
        user_id="user_123",
        email="test@example.com",
        organization_permissions={"org_A": "admin"},
        account_permissions={},
    )

    with patch.object(agent_client, "create_conversation", new_callable=AsyncMock) as mock_create:
        from src.kene_api.routers.chat import CreateConversationRequest, create_conversation

        request = CreateConversationRequest(
            conversation_name="Test",
            account_id="acc_org_b_xyz",
        )

        with patch(_RESOLVER, AsyncMock(return_value="org_B")):
            with pytest.raises(HTTPException) as exc_info:
                await create_conversation(request, user_context)

        assert exc_info.value.status_code == 404
        mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_super_admin_can_access_any_account():
    """Super admins should have access to all accounts (resolver is not called)."""
    user_context = UserContext(
        user_id="admin_123",
        email="admin@ken-e.ai",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )

    assert user_context.is_super_admin is True

    with patch.object(agent_client, "create_conversation", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = "session_123"

        from src.kene_api.routers.chat import CreateConversationRequest, create_conversation

        request = CreateConversationRequest(account_id="any_account_id")

        with patch(_RESOLVER, AsyncMock(side_effect=AssertionError("must not be called"))):
            result = await create_conversation(request, user_context)

        await agent_client._pending_sessions[result.session_id]
        assert mock_create.called


@pytest.mark.asyncio
async def test_org_admin_can_access_org_accounts():
    """Organization admins should have access to their org's accounts."""
    user_context = UserContext(
        user_id="user_123",
        email="user@company.com",
        organization_permissions={"org_abc": "admin"},
        account_permissions={},
    )

    assert user_context.has_account_permission("any_account_in_org", "org_abc", "edit") is True

    with patch.object(agent_client, "create_conversation", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = "session_123"

        from src.kene_api.routers.chat import CreateConversationRequest, create_conversation

        request = CreateConversationRequest(account_id="account_in_org")

        with patch(_RESOLVER, AsyncMock(return_value="org_abc")):
            result = await create_conversation(request, user_context)

        await agent_client._pending_sessions[result.session_id]
        assert mock_create.called
