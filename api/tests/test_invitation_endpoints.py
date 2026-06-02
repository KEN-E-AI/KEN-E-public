"""Tests for invitation-related endpoints in the Firestore router."""

import os
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from src.kene_api.email_service import EmailService, get_email_service
from src.kene_api.firestore import FirestoreService, get_firestore_service
from src.kene_api.main import app

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRESTORE_EMULATOR_HOST"),
    reason="Requires Firebase/Firestore emulator — unblocked by DM-84",
)


class TestInvitationEndpoints:
    """Test cases for invitation endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_firestore(self):
        """Create a mock Firestore service."""
        mock = Mock(spec=FirestoreService)
        mock.health_check.return_value = True
        return mock

    @pytest.fixture
    def mock_email_service(self):
        """Create a mock email service."""
        mock = Mock(spec=EmailService)
        mock.send_invitation_email.return_value = True
        mock.send_invitation_accepted_notification.return_value = True
        return mock

    def test_invite_member_existing_user(
        self, client, mock_firestore, mock_email_service
    ):
        """Test inviting an existing user to organization."""
        # Mock existing user
        mock_firestore.query_documents.return_value = [
            {"id": "user123", "profile": {"email": "existing@example.com"}}
        ]
        mock_firestore.get_document.return_value = {
            "permissions": {"organizations": {}}
        }
        mock_firestore.set_nested_field.return_value = True

        # Override dependencies
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore
        app.dependency_overrides[get_email_service] = lambda: mock_email_service

        try:
            response = client.post(
                "/api/v1/firestore/organizations/org123/members/invite",
                json={"email": "existing@example.com", "access_level": "admin"},
                params={
                    "current_user_id": "inviter123",
                    "current_user_name": "John Doe",
                    "organization_name": "Test Org",
                },
            )

            assert response.status_code == 200
            assert response.json()["success"] is True
            mock_firestore.set_nested_field.assert_called_once()
            mock_email_service.send_invitation_email.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    def test_invite_member_new_user(self, client, mock_firestore, mock_email_service):
        """Test inviting a new user (not in system) to organization."""
        # Mock no existing user
        mock_firestore.query_documents.return_value = []
        mock_firestore.create_document.return_value = "inv123"  # Return document ID
        mock_email_service.send_invitation_email.return_value = True

        # Override dependencies
        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore
        app.dependency_overrides[get_email_service] = lambda: mock_email_service

        try:
            response = client.post(
                "/api/v1/firestore/organizations/org123/members/invite",
                json={"email": "newuser@example.com", "access_level": "view"},
                params={
                    "current_user_id": "inviter123",
                    "current_user_name": "John Doe",
                    "organization_name": "Test Org",
                },
            )

            assert response.status_code == 200
            assert response.json()["success"] is True

            # Verify invitation was created
            mock_firestore.create_document.assert_called_once()
            create_call = mock_firestore.create_document.call_args
            assert create_call.kwargs["collection"] == "invitations"
            assert create_call.kwargs["data"]["email"] == "newuser@example.com"
            assert create_call.kwargs["data"]["access_level"] == "view"
            assert create_call.kwargs["data"]["status"] == "pending"

            # Verify email was sent
            mock_email_service.send_invitation_email.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    def test_get_organization_invitations(self, client, mock_firestore):
        """Test retrieving organization invitations."""
        mock_invitations = [
            {
                "id": "inv1",
                "email": "test1@example.com",
                "organization_id": "org123",
                "organization_name": "Test Org",
                "invited_by": "user123",
                "inviter_name": "John Doe",
                "access_level": "admin",
                "status": "pending",
                "invited_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                "invitation_token": "token1",
            },
            {
                "id": "inv2",
                "email": "test2@example.com",
                "organization_id": "org123",
                "organization_name": "Test Org",
                "invited_by": "user123",
                "inviter_name": "John Doe",
                "access_level": "view",
                "status": "accepted",
                "invited_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                "invitation_token": "token2",
            },
        ]
        mock_firestore.query_documents.return_value = mock_invitations

        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore

        try:
            response = client.get(
                "/api/v1/firestore/organizations/org123/invitations",
                params={"account_id": "user123"},
            )

            if response.status_code != 200:
                print(f"Response: {response.status_code}")
                print(f"Response body: {response.text}")
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert len(data["invitations"]) == 2
            assert data["invitations"][0]["email"] == "test1@example.com"
        finally:
            app.dependency_overrides.clear()

    def test_get_organization_invitations_with_status_filter(
        self, client, mock_firestore
    ):
        """Test retrieving organization invitations with status filter."""
        pending_invitations = [
            {
                "id": "inv1",
                "email": "test@example.com",
                "status": "pending",
                "organization_id": "org123",
                "organization_name": "Test Org",
                "invited_by": "user123",
                "inviter_name": "John Doe",
                "access_level": "admin",
                "invited_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                "invitation_token": "token123",
            }
        ]
        mock_firestore.query_documents.return_value = pending_invitations

        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore

        try:
            response = client.get(
                "/api/v1/firestore/organizations/org123/invitations",
                params={"account_id": "user123", "status": "pending"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["invitations"][0]["status"] == "pending"

            # Verify query was called
            mock_firestore.query_documents.assert_called()
        finally:
            app.dependency_overrides.clear()

    def test_verify_invitation_token_valid(self, client, mock_firestore):
        """Test verifying a valid invitation token."""
        mock_invitation = {
            "id": "inv123",
            "email": "test@example.com",
            "organization_id": "org123",
            "organization_name": "Test Org",
            "invited_by": "user123",
            "inviter_name": "John Doe",
            "access_level": "admin",
            "status": "pending",
            "invitation_token": "valid-token-123",
            "invited_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }
        mock_firestore.query_documents.return_value = [mock_invitation]

        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore

        try:
            response = client.get(
                "/api/v1/firestore/invitations/verify/valid-token-123"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "test@example.com"
            assert data["organization_name"] == "Test Org"
            assert data["status"] == "pending"
        finally:
            app.dependency_overrides.clear()

    def test_verify_invitation_token_not_found(self, client, mock_firestore):
        """Test verifying a non-existent invitation token."""
        mock_firestore.query_documents.return_value = []

        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore

        try:
            response = client.get(
                "/api/v1/firestore/invitations/verify/invalid-token-123"
            )

            assert response.status_code == 404
            # Check for either error message
            error_detail = response.json()["detail"]
            assert (
                "Invitation not found" in error_detail
                or "Invalid invitation token" in error_detail
            )
        finally:
            app.dependency_overrides.clear()

    def test_verify_invitation_token_expired(self, client, mock_firestore):
        """Test verifying an expired invitation token."""
        mock_invitation = {
            "id": "inv123",
            "email": "test@example.com",
            "organization_id": "org123",
            "status": "pending",
            "invitation_token": "expired-token-123",
            "invited_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() - timedelta(days=1)).isoformat(),
        }
        mock_firestore.query_documents.return_value = [mock_invitation]

        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore

        try:
            response = client.get(
                "/api/v1/firestore/invitations/verify/expired-token-123"
            )

            assert response.status_code == 400
            assert "Invitation has expired" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_accept_invitation_success(
        self, client, mock_firestore, mock_email_service
    ):
        """Test accepting an invitation successfully."""
        mock_invitation = {
            "id": "inv123",
            "email": "test@example.com",
            "organization_id": "org123",
            "organization_name": "Test Org",
            "access_level": "admin",
            "status": "pending",
            "invitation_token": "valid-token-123",
            "invited_by": "inviter123",
            "inviter_name": "John Doe",
            "invited_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }

        # Mock invitation lookup
        mock_firestore.query_documents.return_value = [mock_invitation]

        inviter_doc = {"id": "inviter123", "profile": {"email": "inviter@example.com"}}
        mock_firestore.get_document.side_effect = [
            inviter_doc,  # First call for inviter
        ]

        # Mock updates
        mock_firestore.update_document.return_value = True
        mock_firestore.set_nested_field.return_value = True

        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore
        app.dependency_overrides[get_email_service] = lambda: mock_email_service

        try:
            response = client.post(
                "/api/v1/firestore/invitations/accept/valid-token-123",
                json={
                    "user_id": "user123",
                    "user_email": "test@example.com",
                    "user_name": "Test User",
                },
            )

            assert response.status_code == 200
            assert response.json()["success"] is True

            # Verify invitation was updated
            mock_firestore.update_document.assert_called()
            update_call = mock_firestore.update_document.call_args
            assert update_call.kwargs["data"]["status"] == "accepted"

            # Verify user permissions were updated
            mock_firestore.set_nested_field.assert_called_once()

            # Verify notification email was sent
            mock_email_service.send_invitation_accepted_notification.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    def test_accept_invitation_email_mismatch(self, client, mock_firestore):
        """Test accepting an invitation with mismatched email."""
        mock_invitation = {
            "id": "inv123",
            "email": "invited@example.com",
            "organization_id": "org123",
            "status": "pending",
            "invitation_token": "valid-token-123",
            "invited_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat(),
        }
        mock_firestore.query_documents.return_value = [mock_invitation]

        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore

        try:
            response = client.post(
                "/api/v1/firestore/invitations/accept/valid-token-123",
                json={
                    "user_id": "user123",
                    "user_email": "different@example.com",
                    "user_name": "Test User",
                },
            )

            assert response.status_code == 400
            assert "does not match" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_cancel_invitation_success(self, client, mock_firestore):
        """Test cancelling an invitation successfully."""
        mock_invitation = {
            "id": "inv123",
            "status": "pending",
        }
        mock_firestore.get_document.return_value = mock_invitation
        mock_firestore.update_document.return_value = True

        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore

        try:
            response = client.delete(
                "/api/v1/firestore/invitations/inv123",
                params={"account_id": "user123"},
            )

            assert response.status_code == 200
            assert response.json()["success"] is True

            # Verify invitation was updated
            mock_firestore.update_document.assert_called_once()
            update_call = mock_firestore.update_document.call_args
            assert update_call.kwargs["data"]["status"] == "cancelled"
        finally:
            app.dependency_overrides.clear()

    def test_cancel_invitation_already_accepted(self, client, mock_firestore):
        """Test cancelling an already accepted invitation."""
        mock_invitation = {
            "id": "inv123",
            "status": "accepted",
        }
        mock_firestore.get_document.return_value = mock_invitation

        app.dependency_overrides[get_firestore_service] = lambda: mock_firestore

        try:
            response = client.delete(
                "/api/v1/firestore/invitations/inv123",
                params={"account_id": "user123"},
            )

            assert response.status_code == 400
            assert "Cannot cancel" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()
