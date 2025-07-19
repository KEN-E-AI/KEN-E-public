"""Tests for the email service."""

import os
from unittest.mock import Mock, patch

from src.kene_api.email_service import EmailService


class TestEmailService:
    """Test cases for EmailService."""

    def test_init_with_api_key(self):
        """Test initialization with API key present."""
        with patch.dict(os.environ, {"SENDGRID_API_KEY": "test-key"}):
            service = EmailService()
            assert service.api_key == "test-key"
            assert service.client is not None
            assert service.from_email == "noreply@ken-e.ai"
            assert service.from_name == "KEN-E Team"

    def test_init_without_api_key(self):
        """Test initialization without API key."""
        with patch.dict(os.environ, {}, clear=True):
            service = EmailService()
            assert service.api_key is None
            assert service.client is None

    def test_init_with_custom_values(self):
        """Test initialization with custom environment values."""
        with patch.dict(
            os.environ,
            {
                "SENDGRID_API_KEY": "test-key",
                "EMAIL_FROM_ADDRESS": "custom@example.com",
                "EMAIL_FROM_NAME": "Custom Team",
                "APP_BASE_URL": "https://app.example.com",
            },
        ):
            service = EmailService()
            assert service.from_email == "custom@example.com"
            assert service.from_name == "Custom Team"
            assert service.app_base_url == "https://app.example.com"

    @patch("src.kene_api.email_service.SendGridAPIClient")
    def test_send_invitation_email_success(self, mock_sendgrid):
        """Test successful invitation email sending."""
        # Setup mock
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 202
        mock_client.send.return_value = mock_response
        mock_sendgrid.return_value = mock_client

        with patch.dict(os.environ, {"SENDGRID_API_KEY": "test-key"}):
            service = EmailService()

            result = service.send_invitation_email(
                to_email="test@example.com",
                inviter_name="John Doe",
                organization_name="Test Org",
                access_level="admin",
                invitation_token="test-token-123",
            )

            assert result is True
            mock_client.send.assert_called_once()

            # Verify the email was constructed correctly
            call_args = mock_client.send.call_args[0][0]
            assert (
                str(call_args.subject.subject)
                == "You've been invited to join Test Org on KEN-E"
            )
            assert len(call_args.personalizations) == 1
            assert call_args.personalizations[0].tos[0]["email"] == "test@example.com"

    @patch("src.kene_api.email_service.SendGridAPIClient")
    def test_send_invitation_email_no_client(self, mock_sendgrid):
        """Test sending email when client is not initialized."""
        with patch.dict(os.environ, {}, clear=True):
            service = EmailService()

            result = service.send_invitation_email(
                to_email="test@example.com",
                inviter_name="John Doe",
                organization_name="Test Org",
                access_level="admin",
                invitation_token="test-token",
            )

            assert result is False

    @patch("src.kene_api.email_service.SendGridAPIClient")
    def test_send_invitation_email_api_error(self, mock_sendgrid):
        """Test handling SendGrid API errors."""
        from python_http_client.exceptions import HTTPError

        mock_client = Mock()
        mock_client.send.side_effect = HTTPError(
            Mock(status_code=400, body=b"Bad Request")
        )
        mock_sendgrid.return_value = mock_client

        with patch.dict(os.environ, {"SENDGRID_API_KEY": "test-key"}):
            service = EmailService()

            result = service.send_invitation_email(
                to_email="test@example.com",
                inviter_name="John Doe",
                organization_name="Test Org",
                access_level="admin",
                invitation_token="test-token",
            )

            assert result is False

    @patch("src.kene_api.email_service.SendGridAPIClient")
    def test_send_invitation_email_generic_error(self, mock_sendgrid):
        """Test handling generic errors."""
        mock_client = Mock()
        mock_client.send.side_effect = Exception("Network error")
        mock_sendgrid.return_value = mock_client

        with patch.dict(os.environ, {"SENDGRID_API_KEY": "test-key"}):
            service = EmailService()

            result = service.send_invitation_email(
                to_email="test@example.com",
                inviter_name="John Doe",
                organization_name="Test Org",
                access_level="admin",
                invitation_token="test-token",
            )

            assert result is False

    @patch("src.kene_api.email_service.SendGridAPIClient")
    def test_send_invitation_accepted_notification_success(self, mock_sendgrid):
        """Test successful acceptance notification email."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.status_code = 202
        mock_client.send.return_value = mock_response
        mock_sendgrid.return_value = mock_client

        with patch.dict(os.environ, {"SENDGRID_API_KEY": "test-key"}):
            service = EmailService()

            result = service.send_invitation_accepted_notification(
                to_email="inviter@example.com",
                to_name="John Doe",
                accepter_name="Jane Smith",
                accepter_email="jane@example.com",
                organization_name="Test Org",
                access_level="admin",
            )

            assert result is True
            mock_client.send.assert_called_once()

            # Verify the email was constructed correctly
            call_args = mock_client.send.call_args[0][0]
            assert str(call_args.subject.subject) == "Jane Smith has joined Test Org"

    @patch("src.kene_api.email_service.SendGridAPIClient")
    def test_send_invitation_accepted_notification_no_client(self, mock_sendgrid):
        """Test sending notification when client is not initialized."""
        with patch.dict(os.environ, {}, clear=True):
            service = EmailService()

            result = service.send_invitation_accepted_notification(
                to_email="inviter@example.com",
                to_name="John Doe",
                accepter_name="Jane Smith",
                accepter_email="jane@example.com",
                organization_name="Test Org",
                access_level="admin",
            )

            assert result is False

    @patch("src.kene_api.email_service.SendGridAPIClient")
    def test_send_invitation_accepted_notification_error(self, mock_sendgrid):
        """Test handling errors in acceptance notification."""
        mock_client = Mock()
        mock_client.send.side_effect = Exception("API Error")
        mock_sendgrid.return_value = mock_client

        with patch.dict(os.environ, {"SENDGRID_API_KEY": "test-key"}):
            service = EmailService()

            result = service.send_invitation_accepted_notification(
                to_email="inviter@example.com",
                to_name="John Doe",
                accepter_name="Jane Smith",
                accepter_email="jane@example.com",
                organization_name="Test Org",
                access_level="admin",
            )

            assert result is False

    def test_get_email_service_function(self):
        """Test the get_email_service function returns the global instance."""
        from src.kene_api.email_service import email_service, get_email_service

        service = get_email_service()
        assert service is email_service
