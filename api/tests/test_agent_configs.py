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
    _reject_unknown_tool_ids,
    _sanitize_updated_by,
    get_agent_config,
    list_agent_configs,
    update_agent_config,
)


class TestRejectUnknownToolIds:
    """AH-98: the catalogue cross-check accepts the google_search agent tool."""

    def test_accepts_agent_google_search(self) -> None:
        # No raise — agent.google_search is in the real catalogue.
        _reject_unknown_tool_ids(["agent.google_search"])

    def test_accepts_agent_tool_mixed_with_function_tool(self) -> None:
        _reject_unknown_tool_ids(
            ["agent.google_search", "function.create_visualization"]
        )

    def test_rejects_unknown_agent_tool(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            _reject_unknown_tool_ids(["agent.bogus"])
        assert exc_info.value.status_code == 422

    def test_none_and_empty_are_noops(self) -> None:
        _reject_unknown_tool_ids(None)
        _reject_unknown_tool_ids([])


@pytest.fixture
def admin_user():
    """Create mock super admin user."""
    return UserContext(
        user_id="admin123",
        email="admin@ken-e.ai",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
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
        "name": None,
        "title": "Business Researcher",
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

    def test_name_and_title_not_in_helper_signature(self):
        """Nullable identity fields are intentionally not handled by the
        helper — see the helper's docstring. The handler writes them
        inline using ``model_fields_set`` so callers can distinguish
        ``{"name": null}`` from an omitted name."""
        import inspect

        params = inspect.signature(_build_firestore_updates).parameters
        assert "name" not in params
        assert "title" not in params


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

    def test_strips_mer_e_lifecycle_status(self):
        """MER-E also writes ``lifecycle_status`` onto shared agent_configs
        docs. Without stripping, ``extra="forbid"`` on ``MergedAgentConfig``
        causes the list endpoint to silently drop the doc — observed on
        staging where ``rud_e`` disappeared from /workflows/agents."""
        from src.kene_api.routers.agent_configs import _merge_from_data

        global_data = {
            "instruction": "Hello.",
            "model": "gemini-2.5-pro",
            "lifecycle_status": "active",
        }

        merged = _merge_from_data("rud_e", global_data, None)

        assert merged is not None
        assert merged.config_id == "rud_e"

    def test_exposes_name_and_title_on_merged_response(self):
        """Identity fields flow through to the MergedAgentConfig response so
        the frontend can render name primary / title secondary."""
        from src.kene_api.routers.agent_configs import _merge_from_data

        global_data = {
            "name": "Dave",
            "title": "Business Researcher",
            "instruction": "Hello.",
            "model": "gemini-2.5-pro",
        }

        merged = _merge_from_data("business_researcher", global_data, None)

        assert merged is not None
        assert merged.name == "Dave"
        assert merged.title == "Business Researcher"

    def test_strips_pre_ah_prd_02_legacy_fields(self):
        """``canonical_id`` and ``legacy_agent_name`` are pre-AH-PRD-02 seed
        metadata that lives on a handful of docs (business_researcher,
        business_formatter, competitive_analyst, marketing_strategist). They
        must be stripped before validation or the list endpoint silently
        drops those docs."""
        from src.kene_api.routers.agent_configs import _merge_from_data

        global_data = {
            "instruction": "Researches business strategy.",
            "model": "gemini-2.5-pro",
            "canonical_id": "business_strategy",
            "legacy_agent_name": "Business Researcher",
        }

        merged = _merge_from_data("business_researcher", global_data, None)

        assert merged is not None
        assert merged.config_id == "business_researcher"


class TestMergeFromDataToolIds:
    """AH-PRD-06 (review item #1): ``_merge_from_data`` must honor the
    documented null-clearing contract for ``tool_ids``.

    Contract: an overlay carrying ``tool_ids=None`` clears the merged
    response back to ``None`` (legacy behaviour). An overlay carrying
    ``tool_ids=[]`` produces ``tool_ids=[]`` (explicit "no tools"). An
    overlay carrying a list produces the list. Absent overlay falls back
    to the global value (or ``None`` when global doesn't set it).
    """

    def test_overlay_null_clears_global_tool_ids(self) -> None:
        from src.kene_api.routers.agent_configs import _merge_from_data

        global_data = {
            "instruction": "Hello.",
            "model": "gemini-2.5-pro",
            "tool_ids": ["function.create_visualization"],
        }
        overlay_data = {"tool_ids": None}

        merged = _merge_from_data("agent_x", global_data, overlay_data)

        assert merged is not None
        # Overlay-null wins via dict merge {**global, **overlay} — surfaces as
        # None on the response, matching the documented "legacy / all tools
        # from attached servers" semantics.
        assert merged.tool_ids is None

    def test_overlay_empty_list_persists_as_empty_list(self) -> None:
        from src.kene_api.routers.agent_configs import _merge_from_data

        global_data = {
            "instruction": "Hello.",
            "model": "gemini-2.5-pro",
            "tool_ids": ["function.create_visualization"],
        }
        overlay_data = {"tool_ids": []}

        merged = _merge_from_data("agent_x", global_data, overlay_data)

        assert merged is not None
        assert merged.tool_ids == []

    def test_overlay_list_overrides_global_list(self) -> None:
        from src.kene_api.routers.agent_configs import _merge_from_data

        global_data = {
            "instruction": "Hello.",
            "model": "gemini-2.5-pro",
            "tool_ids": ["function.create_visualization"],
        }
        overlay_data = {"tool_ids": ["google_analytics_mcp.run_report_mt"]}

        merged = _merge_from_data("agent_x", global_data, overlay_data)

        assert merged is not None
        assert merged.tool_ids == ["google_analytics_mcp.run_report_mt"]

    def test_absent_overlay_field_inherits_global(self) -> None:
        from src.kene_api.routers.agent_configs import _merge_from_data

        global_data = {
            "instruction": "Hello.",
            "model": "gemini-2.5-pro",
            "tool_ids": ["function.create_visualization"],
        }
        # Overlay touches a different field; tool_ids should inherit from global.
        overlay_data = {"temperature": 0.5}

        merged = _merge_from_data("agent_x", global_data, overlay_data)

        assert merged is not None
        assert merged.tool_ids == ["function.create_visualization"]


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


class TestAdminUpdateNullClearing:
    """Admin PUT must let callers clear nullable identity fields via {"name": null}.

    Without this, ``_build_firestore_updates(name=None, ...)`` would silently
    skip the field — indistinguishable from an omitted name. The handler uses
    ``model_fields_set`` to tell the two cases apart.
    """

    @pytest.mark.asyncio
    async def test_name_explicitly_set_to_null_writes_null(
        self, admin_user, sample_config_data
    ):
        from unittest.mock import AsyncMock

        from src.kene_api.routers import agent_configs as router_mod

        pre = dict(sample_config_data)
        pre["name"] = "Dave"
        pre["metadata"] = {**pre["metadata"], "version": "v1.0.0"}
        post = dict(pre)
        post["name"] = None
        post["metadata"] = {**pre["metadata"], "version": "v1.0.1"}

        mock_db = MagicMock()
        doc_ref = MagicMock()
        captured_updates: dict = {}

        def _capture(updates):
            captured_updates.update(updates)

        doc_ref.update.side_effect = _capture
        doc_ref.get.side_effect = [
            MagicMock(exists=True, to_dict=lambda: pre),
            MagicMock(exists=True, to_dict=lambda: post),
        ]
        mock_db.collection.return_value.document.return_value = doc_ref

        with patch.object(router_mod, "log_config_action", AsyncMock(return_value="a")):
            await router_mod.update_agent_config(
                "business_researcher",
                AgentConfigUpdate(name=None, updated_by="admin@ken-e.ai"),
                user=admin_user,
                db=mock_db,
            )

        assert "name" in captured_updates, (
            "Explicit {'name': null} must produce a Firestore write, not a no-op"
        )
        assert captured_updates["name"] is None

    @pytest.mark.asyncio
    async def test_name_omitted_is_not_written(self, admin_user, sample_config_data):
        """An update body without ``name`` must NOT include name in the write."""
        from unittest.mock import AsyncMock

        from src.kene_api.routers import agent_configs as router_mod

        pre = dict(sample_config_data)
        pre["metadata"] = {**pre["metadata"], "version": "v1.0.0"}
        post = {**pre, "instruction": "New instruction text after update"}
        post["metadata"] = {**pre["metadata"], "version": "v1.0.1"}

        mock_db = MagicMock()
        doc_ref = MagicMock()
        captured_updates: dict = {}

        def _capture(updates):
            captured_updates.update(updates)

        doc_ref.update.side_effect = _capture
        doc_ref.get.side_effect = [
            MagicMock(exists=True, to_dict=lambda: pre),
            MagicMock(exists=True, to_dict=lambda: post),
        ]
        mock_db.collection.return_value.document.return_value = doc_ref

        with patch.object(router_mod, "log_config_action", AsyncMock(return_value="a")):
            await router_mod.update_agent_config(
                "business_researcher",
                AgentConfigUpdate(
                    instruction="New instruction text after update",
                    updated_by="admin@ken-e.ai",
                ),
                user=admin_user,
                db=mock_db,
            )

        assert "name" not in captured_updates
        assert "title" not in captured_updates

    @pytest.mark.asyncio
    async def test_title_clear_audited_as_change(self, admin_user, sample_config_data):
        """The audit log must capture a null-clearing change to title."""
        from unittest.mock import AsyncMock

        from src.kene_api.routers import agent_configs as router_mod

        pre = dict(sample_config_data)
        pre["title"] = "Business Researcher"
        pre["metadata"] = {**pre["metadata"], "version": "v1.0.0"}
        post = dict(pre)
        post["title"] = None
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
            await router_mod.update_agent_config(
                "business_researcher",
                AgentConfigUpdate(title=None, updated_by="admin@ken-e.ai"),
                user=admin_user,
                db=mock_db,
            )

        kw = spy_audit.await_args.kwargs
        assert "title" in kw["fields_changed"]
        assert kw["changes"]["title"] == {
            "before": "Business Researcher",
            "after": None,
        }

    @pytest.mark.asyncio
    async def test_default_acceptance_criteria_change_audited(
        self, admin_user, sample_config_data
    ):
        """AH-91: setting ``default_acceptance_criteria`` via the global PUT
        writes the field and audits it in fields_changed / changes."""
        from unittest.mock import AsyncMock

        from src.kene_api.routers import agent_configs as router_mod

        criteria = "Cite at least 3 distinct sources; summary under 200 words."
        pre = dict(sample_config_data)
        pre.pop("default_acceptance_criteria", None)
        pre["metadata"] = {**pre["metadata"], "version": "v1.0.0"}
        post = dict(pre)
        post["default_acceptance_criteria"] = criteria
        post["metadata"] = {**pre["metadata"], "version": "v1.0.1"}

        mock_db = MagicMock()
        doc_ref = MagicMock()
        captured_updates: dict = {}

        def _capture(updates):
            captured_updates.update(updates)

        doc_ref.update.side_effect = _capture
        doc_ref.get.side_effect = [
            MagicMock(exists=True, to_dict=lambda: pre),
            MagicMock(exists=True, to_dict=lambda: post),
        ]
        mock_db.collection.return_value.document.return_value = doc_ref

        spy_audit = AsyncMock(return_value="audit-1")
        with patch.object(router_mod, "log_config_action", spy_audit):
            await router_mod.update_agent_config(
                "company_news_agent",
                AgentConfigUpdate(
                    default_acceptance_criteria=criteria,
                    updated_by="admin@ken-e.ai",
                ),
                user=admin_user,
                db=mock_db,
            )

        assert captured_updates["default_acceptance_criteria"] == criteria
        kw = spy_audit.await_args.kwargs
        assert "default_acceptance_criteria" in kw["fields_changed"]
        assert kw["changes"]["default_acceptance_criteria"] == {
            "before": None,
            "after": criteria,
        }


    @pytest.mark.asyncio
    async def test_reviewer_model_change_audited(
        self, admin_user, sample_config_data
    ):
        """AH-92: setting ``reviewer_model`` via the global PUT writes the field
        and audits it in fields_changed / changes."""
        from unittest.mock import AsyncMock

        from src.kene_api.routers import agent_configs as router_mod

        model = "gemini-2.5-flash"
        pre = dict(sample_config_data)
        pre.pop("reviewer_model", None)
        pre["metadata"] = {**pre["metadata"], "version": "v1.0.0"}
        post = dict(pre)
        post["reviewer_model"] = model
        post["metadata"] = {**pre["metadata"], "version": "v1.0.1"}

        mock_db = MagicMock()
        doc_ref = MagicMock()
        captured_updates: dict = {}

        def _capture(updates):
            captured_updates.update(updates)

        doc_ref.update.side_effect = _capture
        doc_ref.get.side_effect = [
            MagicMock(exists=True, to_dict=lambda: pre),
            MagicMock(exists=True, to_dict=lambda: post),
        ]
        mock_db.collection.return_value.document.return_value = doc_ref

        spy_audit = AsyncMock(return_value="audit-1")
        with patch.object(router_mod, "log_config_action", spy_audit):
            await router_mod.update_agent_config(
                "company_news_agent",
                AgentConfigUpdate(
                    reviewer_model=model,
                    updated_by="admin@ken-e.ai",
                ),
                user=admin_user,
                db=mock_db,
            )

        assert captured_updates["reviewer_model"] == model
        kw = spy_audit.await_args.kwargs
        assert "reviewer_model" in kw["fields_changed"]
        assert kw["changes"]["reviewer_model"] == {
            "before": None,
            "after": model,
        }


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
    """Redeploy warning behavior split by config type after AH-PRD-09 Phase 2:

    * **Specialists** — the per-turn ``specialist_runtime`` resolver hot-reloads
      every field within the 60 s TTL, so PUT responses for specialist edits
      ALWAYS return ``warnings == []``. Verified by the four
      ``test_*_no_redeploy_warning`` tests below.
    * **Root agent** (``ken_e_chatbot``) — still built once at deploy by
      ``build_hierarchy()``; ``model`` / ``temperature`` / ``max_output_tokens`` /
      ``tools`` edits silently no-op in the running process until
      ``make backend`` runs, so the PUT response surfaces a "redeploy
      required" warning. ``instruction`` on the root is cache-backed
      (AH-PRD-09 Phase 1) and does NOT warn. Verified by the four
      ``test_root_*`` tests below.
    """

    @pytest.mark.asyncio
    async def test_model_change_no_redeploy_warning(
        self, admin_user, sample_config_data
    ):
        """Per AH-PRD-09 Phase 2, the per-turn resolver picks up model changes
        within the 60 s cache TTL — no redeploy required, warnings always empty."""
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
        assert resp.warnings == [], (
            f"Per AH-PRD-09 Phase 2, warnings must always be empty; got {resp.warnings}"
        )

    @pytest.mark.asyncio
    async def test_temperature_change_no_redeploy_warning(
        self, admin_user, sample_config_data
    ):
        """Per AH-PRD-09 Phase 2, the per-turn resolver picks up temperature
        changes within the 60 s cache TTL — no redeploy required, warnings always empty."""
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

        assert resp.warnings == [], (
            f"Per AH-PRD-09 Phase 2, warnings must always be empty; got {resp.warnings}"
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

        assert resp.warnings == [], (
            f"Instruction change should NOT trigger any warning; "
            f"got warnings={resp.warnings}"
        )

    @pytest.mark.asyncio
    async def test_max_output_tokens_change_no_redeploy_warning(
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

        assert resp.warnings == [], (
            f"Per AH-PRD-09 Phase 2, warnings must always be empty; got {resp.warnings}"
        )

    # ------------------------------------------------------------------
    # Root-agent (``ken_e_chatbot``) redeploy warnings — AH-PRD-09 Phase 2
    # ------------------------------------------------------------------
    #
    # The root LlmAgent is still constructed once at deploy by
    # ``build_hierarchy()`` and shipped to Agent Engine; ADK binds ``model``
    # / ``temperature`` / ``max_output_tokens`` / ``tools`` at construction.
    # PUTs against ``ken_e_chatbot`` for those fields must surface a warning
    # so admins know the change will silently no-op until
    # ``make backend`` runs.

    async def _run_root_update(
        self,
        admin_user,
        sample_config_data,
        *,
        update: AgentConfigUpdate,
        pre_overrides: dict | None = None,
        post_overrides: dict,
    ):
        """Drive ``update_agent_config('ken_e_chatbot', ...)`` and return the response."""
        from unittest.mock import AsyncMock

        from src.kene_api.routers import agent_configs as router_mod

        pre = dict(sample_config_data)
        if pre_overrides:
            pre.update(pre_overrides)
        pre["metadata"] = {**pre["metadata"], "version": "v1.0.0"}

        post = dict(pre)
        post.update(post_overrides)
        post["metadata"] = {**pre["metadata"], "version": "v1.0.1"}

        mock_db = MagicMock()
        doc_ref = MagicMock()
        doc_ref.get.side_effect = [
            MagicMock(exists=True, to_dict=lambda: pre),
            MagicMock(exists=True, to_dict=lambda: post),
        ]
        mock_db.collection.return_value.document.return_value = doc_ref

        with patch.object(router_mod, "log_config_action", AsyncMock(return_value="a")):
            return await router_mod.update_agent_config(
                "ken_e_chatbot",
                update,
                user=admin_user,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_root_model_change_returns_redeploy_warning(
        self, admin_user, sample_config_data
    ):
        """Editing the root agent's ``model`` field must surface a redeploy
        warning — the root LlmAgent's model is bound at construction by ADK
        and silently no-ops in the running pod until ``make backend`` runs."""
        resp = await self._run_root_update(
            admin_user,
            sample_config_data,
            update=AgentConfigUpdate(
                model="gemini-2.5-pro", updated_by="admin@ken-e.ai"
            ),
            pre_overrides={"model": "gemini-2.5-flash"},
            post_overrides={"model": "gemini-2.5-pro"},
        )

        assert len(resp.warnings) == 1, (
            f"Expected exactly one warning, got {resp.warnings}"
        )
        msg = resp.warnings[0]
        assert "'model'" in msg, f"Warning must reference the model field: {msg!r}"
        assert "redeploy" in msg.lower(), f"Warning must mention redeploy: {msg!r}"

    @pytest.mark.asyncio
    async def test_root_temperature_change_returns_redeploy_warning(
        self, admin_user, sample_config_data
    ):
        """Editing the root agent's ``temperature`` — baked into
        ``GenerateContentConfig`` at construction — must warn."""
        resp = await self._run_root_update(
            admin_user,
            sample_config_data,
            update=AgentConfigUpdate(temperature=0.5, updated_by="admin@ken-e.ai"),
            post_overrides={"temperature": 0.5},
        )

        assert len(resp.warnings) == 1, (
            f"Expected exactly one warning, got {resp.warnings}"
        )
        assert "'temperature'" in resp.warnings[0]
        assert "redeploy" in resp.warnings[0].lower()

    @pytest.mark.asyncio
    async def test_root_max_output_tokens_change_returns_redeploy_warning(
        self, admin_user, sample_config_data
    ):
        """Editing the root agent's ``max_output_tokens`` — baked into
        ``GenerateContentConfig`` at construction — must warn."""
        resp = await self._run_root_update(
            admin_user,
            sample_config_data,
            update=AgentConfigUpdate(
                max_output_tokens=5000, updated_by="admin@ken-e.ai"
            ),
            post_overrides={"max_output_tokens": 5000},
        )

        assert len(resp.warnings) == 1, (
            f"Expected exactly one warning, got {resp.warnings}"
        )
        assert "'max_output_tokens'" in resp.warnings[0]
        assert "redeploy" in resp.warnings[0].lower()

    @pytest.mark.asyncio
    async def test_root_instruction_change_returns_no_warning(
        self, admin_user, sample_config_data
    ):
        """The root agent's ``instruction`` is cache-backed via the
        ``InstructionProvider`` closure (AH-PRD-09 Phase 1), so it
        hot-reloads within the 60 s TTL — no warning, even on the root."""
        resp = await self._run_root_update(
            admin_user,
            sample_config_data,
            update=AgentConfigUpdate(
                instruction="New instruction text for the root agent",
                updated_by="admin@ken-e.ai",
            ),
            pre_overrides={"instruction": "Old root instruction"},
            post_overrides={"instruction": "New instruction text for the root agent"},
        )

        assert resp.warnings == [], (
            f"Root instruction is cache-backed and must not warn; got {resp.warnings}"
        )

    @pytest.mark.asyncio
    async def test_specialist_model_change_returns_no_warning_regression_guard(
        self, admin_user, sample_config_data
    ):
        """Regression guard: a specialist (non-root) ``model`` edit must still
        return ``warnings == []`` after the warning function gained
        ``config_doc_id``. Mirrors ``test_model_change_no_redeploy_warning``
        but kept as an explicit guard against the warning gate inverting."""
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

        assert resp.warnings == [], (
            f"Specialist model edit must not warn (only root does); got {resp.warnings}"
        )


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
