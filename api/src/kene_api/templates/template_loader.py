"""
Template loader utility for email templates.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader


class TemplateLoader:
    """Loads and renders email templates using Jinja2."""

    def __init__(self):
        # Get the templates directory path
        templates_dir = Path(__file__).parent

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=True,  # Auto-escape HTML for security
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add global template variables
        self.env.globals.update({"current_year": datetime.now().year})

    def render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """
        Render a template with the given context.

        Args:
            template_name: Name of the template file (e.g., 'email/invitation.html')
            context: Dictionary of variables to pass to the template

        Returns:
            Rendered HTML string
        """
        template = self.env.get_template(template_name)
        return template.render(**context)

    def get_invitation_email_html(
        self,
        inviter_name: str,
        organization_name: str,
        access_level: str,
        invitation_url: str,
    ) -> str:
        """
        Generate invitation email HTML.

        Args:
            inviter_name: Name of the person sending the invitation
            organization_name: Name of the organization
            access_level: Access level being granted
            invitation_url: URL to accept the invitation

        Returns:
            Rendered HTML string
        """
        context = {
            "subject": f"Invitation to join {organization_name}",
            "inviter_name": inviter_name,
            "organization_name": organization_name,
            "access_level": access_level,
            "invitation_url": invitation_url,
        }
        return self.render_template("email/invitation.html", context)

    def get_invitation_accepted_email_html(
        self,
        inviter_name: str,
        organization_name: str,
        accepted_by_name: str,
        accepted_by_email: str,
        access_level: str,
        organization_url: str,
    ) -> str:
        """
        Generate invitation accepted notification email HTML.

        Args:
            inviter_name: Name of the person who sent the invitation
            organization_name: Name of the organization
            accepted_by_name: Name of the person who accepted
            accepted_by_email: Email of the person who accepted
            access_level: Access level granted
            organization_url: URL to the organization settings

        Returns:
            Rendered HTML string
        """
        context = {
            "subject": f"{accepted_by_name} has joined {organization_name}",
            "inviter_name": inviter_name,
            "organization_name": organization_name,
            "accepted_by_name": accepted_by_name,
            "accepted_by_email": accepted_by_email,
            "access_level": access_level,
            "accepted_date": datetime.now().strftime("%B %d, %Y"),
            "organization_url": organization_url,
        }
        return self.render_template("email/invitation_accepted.html", context)


# Create a singleton instance
template_loader = TemplateLoader()
