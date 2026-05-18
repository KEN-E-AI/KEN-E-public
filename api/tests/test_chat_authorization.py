"""Integration tests for chat API authorization checks.

Tests that account_id parameter is properly validated and unauthorized
access attempts are rejected with 403.
"""

import os

import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock, patch

from src.kene_api.routers.chat import agent_client
from src.kene_api.auth.models import UserContext

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator — unblocked by DM-84",
)


@pytest.mark.asyncio
async def test_chat_completion_rejects_unauthorized_account():
    """Should return 403 when user tries to access unauthorized account."""
    # Setup: User with access to account_1 only
    user_context = UserContext(
        user_id="user_123",
        email="test@example.com",
        organization_permissions={},
        account_permissions={"acc_authorized": "edit"},
    )

    # Mock the agent client to avoid actual API calls
    with patch.object(agent_client, "chat_completion", new_callable=AsyncMock) as mock_chat:
        # Try to access a different account
        from src.kene_api.routers.chat import ChatRequest, ChatMessage

        request = ChatRequest(
            messages=[ChatMessage(role="user", content="test")],
            account_id="acc_unauthorized",  # User doesn't have access to this
        )

        # Import and call the endpoint
        from src.kene_api.routers.chat import chat_completion

        with pytest.raises(HTTPException) as exc_info:
            await chat_completion(request, user_context)

        # Verify 403 Forbidden
        assert exc_info.value.status_code == 403
        assert "Access denied" in exc_info.value.detail
        assert "acc_unauthorized" in exc_info.value.detail

        # Verify chat_completion was NOT called (authorization failed before)
        mock_chat.assert_not_called()


@pytest.mark.asyncio
async def test_chat_completion_allows_authorized_account():
    """Should allow access when user has permission for account."""
    # Setup: User with access to account
    user_context = UserContext(
        user_id="user_123",
        email="test@example.com",
        organization_permissions={},
        account_permissions={"acc_authorized": "edit"},
    )

    with patch.object(
        agent_client, "chat_completion", new_callable=AsyncMock
    ) as mock_chat:
        mock_chat.return_value = ("Response", "session_123")

        from src.kene_api.routers.chat import ChatRequest, ChatMessage, chat_completion

        request = ChatRequest(
            messages=[ChatMessage(role="user", content="test")],
            account_id="acc_authorized",  # User HAS access
        )

        # Should not raise exception
        response = await chat_completion(request, user_context)

        # Verify chat_completion WAS called
        assert mock_chat.called
        # Verify account_id was passed through
        call_kwargs = mock_chat.call_args.kwargs
        assert call_kwargs["account_id"] == "acc_authorized"


@pytest.mark.asyncio
async def test_create_conversation_rejects_unauthorized_account():
    """Should return 403 when creating conversation for unauthorized account."""
    user_context = UserContext(
        user_id="user_123",
        email="test@example.com",
        organization_permissions={},
        account_permissions={"acc_authorized": "view"},
    )

    with patch.object(
        agent_client, "create_conversation", new_callable=AsyncMock
    ) as mock_create:
        from src.kene_api.routers.chat import (
            CreateConversationRequest,
            create_conversation,
        )

        request = CreateConversationRequest(
            conversation_name="Test",
            account_id="acc_unauthorized",
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_conversation(request, user_context)

        assert exc_info.value.status_code == 403
        assert "Access denied" in exc_info.value.detail

        # Verify conversation was NOT created
        mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_super_admin_can_access_any_account():
    """Super admins should have access to all accounts."""
    # Setup: Super admin user (@ken-e.ai email)
    user_context = UserContext(
        user_id="admin_123",
        email="admin@ken-e.ai",  # Super admin
        organization_permissions={},
        account_permissions={},  # No explicit account permissions
    )

    # Super admin should have access via has_account_access()
    assert user_context.is_super_admin is True
    assert user_context.has_account_access("any_account_id") is True

    with patch.object(
        agent_client, "create_conversation", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = "session_123"

        from src.kene_api.routers.chat import (
            CreateConversationRequest,
            create_conversation,
        )

        request = CreateConversationRequest(
            account_id="any_account_id",
        )

        # Should not raise exception
        result = await create_conversation(request, user_context)

        # Verify conversation WAS created
        assert mock_create.called


@pytest.mark.asyncio
async def test_org_admin_can_access_org_accounts():
    """Organization admins should have access to their org's accounts."""
    user_context = UserContext(
        user_id="user_123",
        email="user@company.com",
        organization_permissions={"org_abc": "admin"},  # Org admin
        account_permissions={},
    )

    # Org admin should have access via has_account_access()
    assert user_context.has_account_access("any_account_in_org") is True

    with patch.object(
        agent_client, "create_conversation", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = "session_123"

        from src.kene_api.routers.chat import (
            CreateConversationRequest,
            create_conversation,
        )

        request = CreateConversationRequest(
            account_id="account_in_org",
        )

        # Should not raise exception for org admin
        result = await create_conversation(request, user_context)

        assert mock_create.called
