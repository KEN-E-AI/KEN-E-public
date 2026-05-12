"""Tests for agent configuration endpoints."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import HTTPException
from src.kene_api.auth import UserContext
from src.kene_api.routers.agent_configs import (
    ALLOWED_CONFIG_IDS,
    AgentConfigUpdate,
    _build_firestore_updates,
    _increment_version,
    _sanitize_updated_by,
    get_agent_config,
    list_agent_configs,
    update_agent_config,
)


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
    """Sample agent configuration data (flat shape per AH-40)."""
    return {
        "name": "business_researcher",
        "model": "gemini-2.5-pro",
        "description": "Test description",
        "instruction": "Test instruction for the agent",
        "temperature": 0.3,
        "max_output_tokens": 2500,
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
    async def test_non_admin_cannot_list_configs(self, regular_user, mock_firestore_db):
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
                await get_agent_config(
                    invalid_id, user=admin_user, db=mock_firestore_db
                )

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

    def test_builds_temperature_update_flat(self):
        """temperature and max_output_tokens are written flat (AH-40)."""
        updates = _build_firestore_updates(temperature=0.5)

        assert updates == {"temperature": 0.5}
        assert "generate_content_config" not in updates

    def test_builds_max_output_tokens_update_flat(self):
        updates = _build_firestore_updates(max_output_tokens=4096)

        assert updates == {"max_output_tokens": 4096}

    def test_builds_combined_temperature_and_tokens_update(self):
        updates = _build_firestore_updates(temperature=0.5, max_output_tokens=4096)

        assert updates == {"temperature": 0.5, "max_output_tokens": 4096}
        assert "generate_content_config" not in updates

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
            instruction=None, model="gemini-2.5-pro", description=None
        )

        assert "instruction" not in updates
        assert "description" not in updates
        assert updates["model"] == "gemini-2.5-pro"


class TestMergeFromDataStripsStorageInternals:
    """AH-40: ``_merge_from_data`` strips storage-internal fields that aren't
    part of the ``MergedAgentConfig`` API contract before validation, so that
    ``extra="forbid"`` doesn't reject docs touched by sibling repos or
    carrying audit metadata."""

    def test_strips_metadata_and_audit_fields(self):
        from src.kene_api.routers.agent_configs import _merge_from_data

        global_data = {
            "name": "ken_e_chatbot",
            "instruction": "Hello.",
            "model": "gemini-2.5-pro",
            "temperature": 0.7,
            "metadata": {"version": "v1.0.0", "variant_name": "x"},
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
            "created_by": "seed@ken-e.ai",
        }

        merged = _merge_from_data("ken_e_chatbot", global_data, None)

        assert merged is not None
        assert merged.temperature == 0.7

    def test_strips_mer_e_deployment_status(self):
        """MER-E (sister repo) writes ``deployment_status`` onto shared
        agent_configs docs. The API doesn't surface it; the strip list
        keeps the doc validating cleanly."""
        from src.kene_api.routers.agent_configs import _merge_from_data

        global_data = {
            "instruction": "Hello.",
            "model": "gemini-2.5-pro",
            "temperature": 0.4,
            "deployment_status": None,
        }

        merged = _merge_from_data("ken_e_chatbot", global_data, None)

        assert merged is not None
        assert merged.temperature == 0.4


class TestErrorHandling:
    """Test error handling paths."""

    @pytest.mark.asyncio
    async def test_config_not_found_returns_404(
        self, admin_user, mock_firestore_db, sample_config_data
    ):
        """Non-existent config should return 404."""
        mock_doc = Mock()
        mock_doc.exists = False

        mock_firestore_db.collection.return_value.document.return_value.get.return_value = mock_doc

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


# ---------------------------------------------------------------------------
# Story 1.1.4-3 — Audit trail, warnings, and history endpoint
# ---------------------------------------------------------------------------


class TestAuditWriteOnUpdate:
    """PUT /api/v1/agent-configs/{id} writes a ConfigAuditEntry on success."""

    @pytest.mark.asyncio
    async def test_successful_update_calls_log_config_action(
        self, admin_user, sample_config_data
    ):
        """Happy-path PUT must invoke log_config_action exactly once."""
        from unittest.mock import AsyncMock

        from src.kene_api.routers import agent_configs as router_mod

        pre = dict(sample_config_data)
        pre["instruction"] = "Old instruction text used before update"
        pre["metadata"] = {**pre["metadata"], "version": "v1.0.0"}

        post = dict(pre)
        post["instruction"] = "New instruction text after update"
        post["metadata"] = {**pre["metadata"], "version": "v1.0.1"}

        mock_db = MagicMock()
        doc_ref = MagicMock()
        doc_ref.get.side_effect = [
            MagicMock(exists=True, to_dict=lambda: pre),
            MagicMock(exists=True, to_dict=lambda: post),
        ]
        mock_db.collection.return_value.document.return_value = doc_ref

        spy_audit = AsyncMock(return_value="audit-1")

        with patch.object(router_mod, "log_config_action", spy_audit):
            update = AgentConfigUpdate(
                instruction="New instruction text after update",
                updated_by="admin@ken-e.ai",
            )

            await router_mod.update_agent_config(
                "business_researcher", update, user=admin_user, db=mock_db
            )

        assert spy_audit.await_count == 1
        kw = spy_audit.await_args.kwargs
        assert kw["doc_type"] == "agent_config"
        assert kw["doc_id"] == "business_researcher"
        assert kw["action"] == "updated"
        assert "instruction" in kw["fields_changed"]
        assert kw["changes"]["instruction"] == {
            "before": "Old instruction text used before update",
            "after": "New instruction text after update",
        }
        assert kw["version_before"] == "v1.0.0"
        assert kw["version_after"] == "v1.0.1"


class TestWarningsOnRedeployRequiredFields:
    """Changes to model / temperature / max_output_tokens surface a
    redeploy-required warning (AC-6.25) because ADK Agent constructor bakes
    these into the SDK GenerateContentConfig at module-import time."""

    @pytest.mark.asyncio
    async def test_model_change_surfaces_redeploy_warning(
        self, admin_user, sample_config_data
    ):
        from unittest.mock import AsyncMock

        from src.kene_api.routers import agent_configs as router_mod

        pre = dict(sample_config_data)
        pre["model"] = "gemini-2.5-flash"
        pre["metadata"] = {**pre["metadata"], "version": "v1.0.0"}
        post = {**pre, "model": "gemini-2.5-pro"}
        post["metadata"] = {**pre["metadata"], "version": "v1.0.1"}

        mock_db = MagicMock()
        doc_ref = MagicMock()
        doc_ref.get.side_effect = [
            MagicMock(exists=True, to_dict=lambda: pre),
            MagicMock(exists=True, to_dict=lambda: post),
        ]
        mock_db.collection.return_value.document.return_value = doc_ref

        with patch.object(router_mod, "log_config_action", AsyncMock(return_value="a")):
            resp = await router_mod.update_agent_config(
                "business_researcher",
                AgentConfigUpdate(model="gemini-2.5-pro", updated_by="admin@ken-e.ai"),
                user=admin_user,
                db=mock_db,
            )

        assert hasattr(resp, "warnings"), (
            "update_agent_config must return AgentConfigUpdateResponse (config + warnings)"
        )
        assert any("redeploy" in w.lower() for w in resp.warnings), (
            f"Expected redeploy warning for model change; got warnings={resp.warnings}"
        )

    @pytest.mark.asyncio
    async def test_temperature_change_surfaces_redeploy_warning(
        self, admin_user, sample_config_data
    ):
        """Temperature is baked into the SDK GenerateContentConfig at ADK
        Agent construction time; ADK doesn't accept a callable for this
        field, so changes cannot propagate via the InstructionProvider
        cache. Must surface a redeploy-required warning."""
        from unittest.mock import AsyncMock

        from src.kene_api.routers import agent_configs as router_mod

        pre = dict(sample_config_data)
        pre["metadata"] = {**pre["metadata"], "version": "v1.0.0"}
        post = dict(pre)
        post["temperature"] = 0.5
        post["metadata"] = {**pre["metadata"], "version": "v1.0.1"}

        mock_db = MagicMock()
        doc_ref = MagicMock()
        doc_ref.get.side_effect = [
            MagicMock(exists=True, to_dict=lambda: pre),
            MagicMock(exists=True, to_dict=lambda: post),
        ]
        mock_db.collection.return_value.document.return_value = doc_ref

        with patch.object(router_mod, "log_config_action", AsyncMock(return_value="a")):
            resp = await router_mod.update_agent_config(
                "business_researcher",
                AgentConfigUpdate(temperature=0.5, updated_by="admin@ken-e.ai"),
                user=admin_user,
                db=mock_db,
            )

        assert any("redeploy" in w.lower() for w in resp.warnings), (
            f"Temperature change MUST trigger redeploy warning; got warnings={resp.warnings}"
        )

    @pytest.mark.asyncio
    async def test_instruction_change_does_not_surface_redeploy_warning(
        self, admin_user, sample_config_data
    ):
        """Instruction propagates via the 60 s InstructionProvider cache
        (Decision B) — no redeploy required."""
        from unittest.mock import AsyncMock

        from src.kene_api.routers import agent_configs as router_mod

        pre = dict(sample_config_data)
        pre["instruction"] = "Old instruction text"
        pre["metadata"] = {**pre["metadata"], "version": "v1.0.0"}
        post = dict(pre)
        post["instruction"] = "New instruction text for the agent"
        post["metadata"] = {**pre["metadata"], "version": "v1.0.1"}

        mock_db = MagicMock()
        doc_ref = MagicMock()
        doc_ref.get.side_effect = [
            MagicMock(exists=True, to_dict=lambda: pre),
            MagicMock(exists=True, to_dict=lambda: post),
        ]
        mock_db.collection.return_value.document.return_value = doc_ref

        with patch.object(router_mod, "log_config_action", AsyncMock(return_value="a")):
            resp = await router_mod.update_agent_config(
                "business_researcher",
                AgentConfigUpdate(
                    instruction="New instruction text for the agent",
                    updated_by="admin@ken-e.ai",
                ),
                user=admin_user,
                db=mock_db,
            )

        assert not any("redeploy" in w.lower() for w in resp.warnings), (
            f"Instruction change should NOT trigger redeploy warning; "
            f"got warnings={resp.warnings}"
        )

    @pytest.mark.asyncio
    async def test_max_output_tokens_change_surfaces_redeploy_warning(
        self, admin_user, sample_config_data
    ):
        from unittest.mock import AsyncMock

        from src.kene_api.routers import agent_configs as router_mod

        pre = dict(sample_config_data)
        pre["metadata"] = {**pre["metadata"], "version": "v1.0.0"}
        post = dict(pre)
        post["max_output_tokens"] = 5000
        post["metadata"] = {**pre["metadata"], "version": "v1.0.1"}

        mock_db = MagicMock()
        doc_ref = MagicMock()
        doc_ref.get.side_effect = [
            MagicMock(exists=True, to_dict=lambda: pre),
            MagicMock(exists=True, to_dict=lambda: post),
        ]
        mock_db.collection.return_value.document.return_value = doc_ref

        with patch.object(router_mod, "log_config_action", AsyncMock(return_value="a")):
            resp = await router_mod.update_agent_config(
                "business_researcher",
                AgentConfigUpdate(max_output_tokens=5000, updated_by="admin@ken-e.ai"),
                user=admin_user,
                db=mock_db,
            )

        assert any("redeploy" in w.lower() for w in resp.warnings)


class TestAgentConfigHistoryEndpoint:
    """GET /api/v1/agent-configs/{id}/history returns recent ConfigAuditEntry rows."""

    @pytest.mark.asyncio
    async def test_history_non_admin_forbidden(self, regular_user):
        from src.kene_api.routers.agent_configs import get_agent_config_history

        with pytest.raises(HTTPException) as exc:
            await get_agent_config_history(
                "business_researcher", user=regular_user, db=MagicMock()
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_history_returns_entries_desc(self, admin_user):
        from src.kene_api.routers.agent_configs import get_agent_config_history

        mock_db = MagicMock()

        entry_new = MagicMock()
        entry_new.to_dict.return_value = {
            "action": "updated",
            "doc_type": "agent_config",
            "doc_id": "business_researcher",
            "user_id": "admin-uid",
            "user_email": "admin@ken-e.ai",
            "timestamp": "2026-04-24T10:00:00+00:00",
            "version_before": "v1.0.0",
            "version_after": "v1.0.1",
            "fields_changed": ["instruction"],
            "changes": {"instruction": {"before": "old", "after": "new"}},
        }
        entry_old = MagicMock()
        entry_old.to_dict.return_value = {
            "action": "updated",
            "doc_type": "agent_config",
            "doc_id": "business_researcher",
            "user_id": "admin-uid",
            "user_email": "admin@ken-e.ai",
            "timestamp": "2026-04-23T10:00:00+00:00",
            "version_before": None,
            "version_after": "v1.0.0",
            "fields_changed": [],
            "changes": {},
        }

        subcol = MagicMock()
        subcol.order_by.return_value.limit.return_value.stream.return_value = iter(
            [entry_new, entry_old]
        )
        mock_db.collection.return_value.document.return_value.collection.return_value = subcol

        result = await get_agent_config_history(
            "business_researcher", user=admin_user, db=mock_db, limit=20
        )

        assert len(result) == 2
        assert result[0].timestamp > result[1].timestamp

    @pytest.mark.asyncio
    async def test_history_rejects_invalid_config_id(self, admin_user):
        from src.kene_api.routers.agent_configs import get_agent_config_history

        with pytest.raises(HTTPException) as exc:
            await get_agent_config_history(
                "../etc/passwd", user=admin_user, db=MagicMock()
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_history_limit_bounded(self, admin_user):
        from src.kene_api.routers.agent_configs import get_agent_config_history

        with pytest.raises(HTTPException) as exc:
            await get_agent_config_history(
                "business_researcher",
                user=admin_user,
                db=MagicMock(),
                limit=10000,
            )
        assert exc.value.status_code == 400
