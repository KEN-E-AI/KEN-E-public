"""Email service for sending invitations using SendGrid."""

import logging
import os

from python_http_client.exceptions import HTTPError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, Email, Mail, To

from .secret_manager import get_env_var_or_secret
from .templates.template_loader import template_loader

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SendGrid."""

    def __init__(self):
        """Initialize the SendGrid client."""
        self.api_key = get_env_var_or_secret("SENDGRID_API_KEY")
        self.from_email = os.getenv("EMAIL_FROM_ADDRESS", "noreply@ken-e.ai")
        self.from_name = os.getenv("EMAIL_FROM_NAME", "KEN-E Team")
        self.app_base_url = os.getenv("APP_BASE_URL", "http://localhost:8080")

        if not self.api_key:
            logger.warning(
                "SendGrid API key not found. Email sending will be disabled."
            )
            self.client = None
        else:
            self.client = SendGridAPIClient(self.api_key)

    def send_invitation_email(
        self,
        to_email: str,
        inviter_name: str,
        organization_name: str,
        access_level: str,
        invitation_token: str,
    ) -> bool:
        """
        Send an invitation email to a new user.

        Args:
            to_email: Recipient email address
            inviter_name: Name of the person sending the invitation
            organization_name: Name of the organization
            access_level: Access level being granted (admin or view)
            invitation_token: Unique token for accepting the invitation

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.client:
            logger.error("SendGrid client not initialized. Cannot send email.")
            return False

        try:
            invitation_url = f"{self.app_base_url}/auth/signin?invitation={invitation_token}"

            # Create the email content using template
            subject = f"You've been invited to join {organization_name} on KEN-E"

            # Generate HTML content from template
            html_content = template_loader.get_invitation_email_html(
                inviter_name=inviter_name,
                organization_name=organization_name,
                access_level=access_level,
                invitation_url=invitation_url,
            )

            # Generate plain text content
            plain_text_content = f"""
You're Invited to KEN-E!

Hi there,

{inviter_name} has invited you to join {organization_name} on KEN-E with {access_level} access.

KEN-E is a multi-agent AI system for marketing analysis that provides comprehensive insights 
and analytics to help optimize your marketing strategies.

Click here to accept the invitation:
{invitation_url}

This invitation will expire in 7 days. If you have any questions, please contact the person who invited you.

Best regards,
The KEN-E Team
            """

            # Create the Mail object
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                plain_text_content=Content("text/plain", plain_text_content),
                html_content=Content("text/html", html_content),
            )

            # Send the email
            response = self.client.send(message)

            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"Invitation email sent successfully to {to_email}")
                return True
            else:
                logger.error(
                    f"Failed to send email. Status code: {response.status_code}"
                )
                return False

        except HTTPError as e:
            logger.error(f"SendGrid API error: {e.body}")
            return False
        except Exception as e:
            logger.error(f"Error sending invitation email: {e!s}")
            return False

    def send_invitation_accepted_notification(
        self,
        to_email: str,
        to_name: str,
        accepter_name: str,
        accepter_email: str,
        organization_name: str,
        access_level: str,
    ) -> bool:
        """
        Send a notification email when an invitation is accepted.

        Args:
            to_email: Email of the person who sent the invitation
            to_name: Name of the person who sent the invitation
            accepter_name: Name of the person who accepted
            accepter_email: Email of the person who accepted
            organization_name: Name of the organization
            access_level: Access level granted

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.client:
            logger.error("SendGrid client not initialized. Cannot send email.")
            return False

        try:
            subject = f"{accepter_name} has joined {organization_name}"
            organization_url = f"{self.app_base_url}/settings/organization"

            # Generate HTML content from template
            html_content = template_loader.get_invitation_accepted_email_html(
                inviter_name=to_name,
                organization_name=organization_name,
                accepted_by_name=accepter_name,
                accepted_by_email=accepter_email,
                access_level=access_level,
                organization_url=organization_url,
            )

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                html_content=html_content,
            )

            response = self.client.send(message)
            return response.status_code >= 200 and response.status_code < 300

        except Exception as e:
            logger.error(f"Error sending acceptance notification: {e!s}")
            return False


# Global instance
email_service = EmailService()


def get_email_service() -> EmailService:
    """Get the global email service instance."""
    return email_service
