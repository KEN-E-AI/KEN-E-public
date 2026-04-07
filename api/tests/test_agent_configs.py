"""Tests for agent configuration endpoints."""

import pytest
from fastapi import HTTPException
from unittest.mock import Mock, patch, MagicMock

from src.kene_api.routers.agent_configs import (
    update_agent_config,
    get_agent_config,
    list_agent_configs,
    ALLOWED_CONFIG_IDS,
    _increment_version,
    _sanitize_updated_by,
    _build_firestore_updates,
    AgentConfigUpdate,
)
from src.kene_api.auth import UserContext


@pytest.fixture
def admin_user():
    """Create mock super admin user."""
    return UserContext(
        user_id="admin123",
        email="admin@ken-e.ai",
        organization_permissions={},
        account_permissions={},
    )


@pytest.fixture
def regular_user():
    """Create mock regular user."""
    return UserContext(
        user_id="user123",
        email="user@example.com",
        organization_permissions={},
        account_permissions={},
    )


@pytest.fixture
def mock_firestore_db():
    """Create mock Firestore client."""
    return MagicMock()


@pytest.fixture
def sample_config_data():
    """Sample agent configuration data."""
    return {
        "name": "business_researcher",
        "model": "gemini-2.0-flash",
        "description": "Test description",
        "instruction": "Test instruction for the agent",
        "generate_content_config": {"temperature": 0.3, "max_output_tokens": 2500},
        "metadata": {
            "version": "v1.0",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
            "updated_by": "test@example.com",
            "variant_name": "baseline",
            "experiment_id": "baseline",
            "notes": "",
        },
    }


class TestAuthentication:
    """Test authentication and authorization."""

    @pytest.mark.asyncio
    async def test_non_admin_cannot_list_configs(
        self, regular_user, mock_firestore_db
    ):
        """Non-admin users should receive 403 when listing configs."""
        with pytest.raises(HTTPException) as exc_info:
            await list_agent_configs(user=regular_user, db=mock_firestore_db)

        assert exc_info.value.status_code == 403
        assert "super administrator" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_non_admin_cannot_read_config(self, regular_user, mock_firestore_db):
        """Non-admin users should receive 403 when reading configs."""
        with pytest.raises(HTTPException) as exc_info:
            await get_agent_config(
                "business_researcher", user=regular_user, db=mock_firestore_db
            )

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_non_admin_cannot_update_config(
        self, regular_user, mock_firestore_db
    ):
        """Non-admin users should receive 403 when updating configs."""
        update = AgentConfigUpdate(
            instruction="New instruction for malicious purposes",
            updated_by="hacker@evil.com",
        )

        with pytest.raises(HTTPException) as exc_info:
            await update_agent_config(
                "business_researcher", update, user=regular_user, db=mock_firestore_db
            )

        assert exc_info.value.status_code == 403


class TestInputValidation:
    """Test input validation and security."""

    @pytest.mark.asyncio
    async def test_invalid_config_id_rejected(self, admin_user, mock_firestore_db):
        """Config IDs not in allowlist should be rejected."""
        invalid_ids = [
            "../etc/passwd",  # Path traversal
            "malicious_config",  # Not in allowlist
            "business_researcher; DROP TABLE",  # SQL injection attempt
        ]

        for invalid_id in invalid_ids:
            with pytest.raises(HTTPException) as exc_info:
                await get_agent_config(invalid_id, user=admin_user, db=mock_firestore_db)

            assert exc_info.value.status_code == 400
            assert invalid_id not in ALLOWED_CONFIG_IDS

    def test_instruction_too_long_rejected(self):
        """Instruction exceeding max length should be rejected."""
        with pytest.raises(ValueError):
            AgentConfigUpdate(
                instruction="x" * 50001,  # Exceeds 50000 limit
                updated_by="test@example.com",
            )

    def test_invalid_model_rejected(self):
        """Invalid model ID should be rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="not supported"):
            AgentConfigUpdate(
                model="gpt-4",  # Not in supported models list
                updated_by="test@example.com",
            )

    def test_invalid_version_format_rejected(self):
        """Invalid version format should be rejected."""
        with pytest.raises(ValueError):
            AgentConfigUpdate(
                version="1.0",  # Missing 'v' prefix
                updated_by="test@example.com",
            )

    def test_updated_by_not_email_rejected(self):
        """updated_by must be valid email."""
        with pytest.raises(ValueError, match="valid email"):
            AgentConfigUpdate(
                instruction="New instruction",
                updated_by="not-an-email",
            )

    def test_temperature_out_of_range_rejected(self):
        """Temperature must be between 0 and 1."""
        with pytest.raises(ValueError):
            AgentConfigUpdate(
                temperature=1.5,  # > 1.0
                updated_by="test@example.com",
            )

    def test_max_tokens_too_high_rejected(self):
        """Max tokens must be <= 65535."""
        with pytest.raises(ValueError):
            AgentConfigUpdate(
                max_output_tokens=100000,  # > 65535
                updated_by="test@example.com",
            )


class TestVersionIncrement:
    """Test version auto-increment logic (semver patch bump)."""

    def test_semver_patch_increment(self):
        """Semver 3-part: should bump patch."""
        assert _increment_version("v1.0.0") == "v1.0.1"
        assert _increment_version("v1.2.3") == "v1.2.4"
        assert _increment_version("v2.0.0") == "v2.0.1"

    def test_legacy_two_part_upgrades_to_semver(self):
        """Legacy 2-part: treated as vX.Y.0, bumps to vX.Y.1."""
        assert _increment_version("v1.0") == "v1.0.1"
        assert _increment_version("v1.5") == "v1.5.1"
        assert _increment_version("v10.50") == "v10.50.1"

    def test_invalid_version_raises(self):
        """Invalid formats should raise ValueError, not silently fallback."""
        invalid_versions = ["v1", "version1.0", "", "vABC.123"]

        for invalid_version in invalid_versions:
            with pytest.raises(ValueError):
                _increment_version(invalid_version)

    def test_without_v_prefix(self):
        """Should handle versions without v prefix."""
        assert _increment_version("1.0.0") == "v1.0.1"
        assert _increment_version("1.2") == "v1.2.1"

    def test_prerelease_version_increment(self):
        """Prerelease suffix stripped before incrementing."""
        assert _increment_version("v1.0.0-beta.1") == "v1.0.1"
        assert _increment_version("v2.1.3-rc1") == "v2.1.4"


class TestSanitization:
    """Test input sanitization functions."""

    def test_sanitize_updated_by_removes_dots(self):
        """Dots should be replaced with underscores."""
        result = _sanitize_updated_by("user.name@example.com")
        assert "." not in result
        assert "_" in result

    def test_sanitize_updated_by_removes_dollars(self):
        """Dollar signs should be replaced with underscores."""
        result = _sanitize_updated_by("evil$inject@test.com")
        assert "$" not in result
        assert "_" in result

    def test_sanitize_updated_by_truncates_long_emails(self):
        """Emails longer than 100 chars should be truncated."""
        long_email = "a" * 150 + "@example.com"
        result = _sanitize_updated_by(long_email)
        assert len(result) == 100

    def test_sanitize_updated_by_handles_empty_string(self):
        """Empty string should return 'unknown'."""
        assert _sanitize_updated_by("") == "unknown"


class TestBuildFirestoreUpdates:
    """Test type-safe update builder function."""

    def test_builds_instruction_update(self):
        """Should build update dict with instruction."""
        updates = _build_firestore_updates(instruction="New instruction")
        assert updates == {"instruction": "New instruction"}

    def test_builds_model_update(self):
        """Should build update dict with model."""
        updates = _build_firestore_updates(model="gemini-2.5-pro")
        assert updates == {"model": "gemini-2.5-pro"}

    def test_builds_gen_config_update(self):
        """Should build update dict with generation config."""
        current_gen_config = {"temperature": 0.3, "max_output_tokens": 2500}
        updates = _build_firestore_updates(
            temperature=0.5, current_gen_config=current_gen_config
        )

        assert updates["generate_content_config"] == {
            "temperature": 0.5,
            "max_output_tokens": 2500,
        }

    def test_builds_metadata_updates(self):
        """Should build update dict with metadata fields."""
        updates = _build_firestore_updates(
            version="v1.5",
            updated_at="2025-01-15T00:00:00Z",
            updated_by="admin@ken-e.ai",
            variant_name="test",
            experiment_id="exp001",
            notes="Test notes",
        )

        assert updates["metadata.version"] == "v1.5"
        assert updates["metadata.updated_at"] == "2025-01-15T00:00:00Z"
        assert updates["metadata.updated_by"] == "admin@ken-e.ai"
        assert updates["metadata.variant_name"] == "test"
        assert updates["metadata.experiment_id"] == "exp001"
        assert updates["metadata.notes"] == "Test notes"

    def test_ignores_none_values(self):
        """Should not include fields with None values."""
        updates = _build_firestore_updates(
            instruction=None, model="gemini-2.0-flash", description=None
        )

        assert "instruction" not in updates
        assert "description" not in updates
        assert updates["model"] == "gemini-2.0-flash"


class TestErrorHandling:
    """Test error handling paths."""

    @pytest.mark.asyncio
    async def test_config_not_found_returns_404(
        self, admin_user, mock_firestore_db, sample_config_data
    ):
        """Non-existent config should return 404."""
        mock_doc = Mock()
        mock_doc.exists = False

        mock_firestore_db.collection.return_value.document.return_value.get.return_value = (
            mock_doc
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_agent_config(
                "business_researcher", user=admin_user, db=mock_firestore_db
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_firestore_error_returns_500(self, admin_user):
        """Firestore errors should return 500."""
        mock_db = Mock()
        mock_db.collection.side_effect = Exception("Firestore unavailable")

        with pytest.raises(HTTPException) as exc_info:
            await list_agent_configs(user=admin_user, db=mock_db)

        assert exc_info.value.status_code == 500


class TestFirestoreDependency:
    """Test Firestore dependency injection."""

    def test_firestore_client_is_singleton(self):
        """Verify Firestore client is cached and reused."""
        from src.kene_api.dependencies import get_firestore_client

        client1 = get_firestore_client()
        client2 = get_firestore_client()

        # Should return exact same instance
        assert client1 is client2


class TestAllowlistDerivedFromRegistry:
    """Test that ALLOWED_CONFIG_IDS is derived from the agent registry."""

    def test_allowed_config_ids_matches_registry(self):
        """ALLOWED_CONFIG_IDS should equal registry.get_all_config_doc_ids()."""
        from app.adk.agents.registry import get_registry

        assert ALLOWED_CONFIG_IDS == get_registry().get_all_config_doc_ids()
