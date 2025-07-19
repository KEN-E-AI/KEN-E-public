"""Tests for the template loader utility."""

from datetime import datetime

import pytest
from src.kene_api.templates.template_loader import TemplateLoader, template_loader


class TestTemplateLoader:
    """Test cases for TemplateLoader."""

    def test_singleton_instance(self):
        """Test that template_loader is a singleton instance."""
        assert isinstance(template_loader, TemplateLoader)
        # Verify it's the same instance
        from src.kene_api.templates.template_loader import template_loader as loader2

        assert template_loader is loader2

    def test_render_template_with_context(self):
        """Test rendering a template with context variables."""
        loader = TemplateLoader()

        # Test that we can load and render the base template
        context = {"subject": "Test Subject", "content": "Test content here"}

        # Since base.html uses blocks, we'll test a simple render
        # This will test that the template system is working
        try:
            result = loader.render_template(
                "email/invitation.html",
                {
                    "subject": "Test",
                    "inviter_name": "John",
                    "organization_name": "TestOrg",
                    "access_level": "admin",
                    "invitation_url": "http://test.com",
                },
            )
            assert "John" in result
            assert "TestOrg" in result
            assert "admin" in result
            assert "http://test.com" in result
        except Exception as e:
            pytest.fail(f"Template rendering failed: {e!s}")

    def test_get_invitation_email_html(self):
        """Test generating invitation email HTML."""
        loader = TemplateLoader()

        html = loader.get_invitation_email_html(
            inviter_name="John Doe",
            organization_name="Acme Corp",
            access_level="admin",
            invitation_url="https://app.example.com/invite/abc123",
        )

        # Verify key content is present
        assert "John Doe" in html
        assert "Acme Corp" in html
        assert "admin" in html
        assert "https://app.example.com/invite/abc123" in html
        assert "Accept Invitation" in html
        assert "KEN-E" in html
        assert str(datetime.now().year) in html  # Current year in footer

    def test_get_invitation_accepted_email_html(self):
        """Test generating invitation accepted email HTML."""
        loader = TemplateLoader()

        html = loader.get_invitation_accepted_email_html(
            inviter_name="John Doe",
            organization_name="Acme Corp",
            accepted_by_name="Jane Smith",
            accepted_by_email="jane@example.com",
            access_level="view",
            organization_url="https://app.example.com/settings/organization",
        )

        # Verify key content is present
        assert "John Doe" in html
        assert "Acme Corp" in html
        assert "Jane Smith" in html
        assert "jane@example.com" in html
        assert "view" in html
        assert "https://app.example.com/settings/organization" in html
        assert "View Team Members" in html
        assert datetime.now().strftime("%B %d, %Y") in html

    def test_template_autoescape(self):
        """Test that HTML is properly escaped in templates."""
        loader = TemplateLoader()

        # Test with HTML in user input
        html = loader.get_invitation_email_html(
            inviter_name="<script>alert('xss')</script>",
            organization_name="Test & Co.",
            access_level="admin",
            invitation_url="https://app.example.com/invite/abc",
        )

        # Verify HTML is escaped
        assert "<script>" not in html
        assert "&lt;script&gt;" in html or "&#x3C;script&#x3E;" in html
        assert "Test &amp; Co." in html or "Test &#x26; Co." in html

    def test_template_globals(self):
        """Test that global template variables are available."""
        loader = TemplateLoader()

        # Current year should be available in all templates
        current_year = datetime.now().year

        html = loader.get_invitation_email_html(
            inviter_name="Test",
            organization_name="Test",
            access_level="admin",
            invitation_url="http://test.com",
        )

        assert str(current_year) in html

    def test_render_nonexistent_template(self):
        """Test handling of non-existent template."""
        loader = TemplateLoader()

        with pytest.raises(Exception):  # Jinja2 will raise TemplateNotFound
            loader.render_template("nonexistent.html", {})

    def test_template_inheritance(self):
        """Test that template inheritance works properly."""
        loader = TemplateLoader()

        # Both invitation templates should inherit from base.html
        invitation_html = loader.get_invitation_email_html(
            inviter_name="Test",
            organization_name="Test Org",
            access_level="admin",
            invitation_url="http://test.com",
        )

        accepted_html = loader.get_invitation_accepted_email_html(
            inviter_name="Test",
            organization_name="Test Org",
            accepted_by_name="User",
            accepted_by_email="user@test.com",
            access_level="admin",
            organization_url="http://test.com",
        )

        # Both should have the base template structure
        for html in [invitation_html, accepted_html]:
            assert '<div class="header">' in html
            assert "<h1>KEN-E</h1>" in html
            assert '<div class="content">' in html
            assert '<div class="footer">' in html
            assert "All rights reserved" in html
