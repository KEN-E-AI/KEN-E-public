"""Integration tests for MCP server configs admin endpoints + audit + reload.

Covers Sprint 6 Story 1.1.4-3 ACs:
    4. GET /api/v1/mcp-server-configs/ returns all MCP configs
    5. PUT /api/v1/mcp-server-configs/{id} writes + audit
    6. 422 on invalid config (bad URL, hosting/connection_type mismatch)
    7. Audit trail queryable via history endpoint
    8. 403 on non-admin

Plus Sprint 6 AC-6.11: MCPServerManager.reload() called on config change.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from src.kene_api.auth import UserContext
from src.kene_api.models.mcp_server_models import MCPServerConfigUpdate


@pytest.fixture
def admin_user() -> UserContext:
    return UserContext(
        user_id="admin-uid-1",
        email="admin@ken-e.ai",
        organization_permissions={},
        account_permissions={},
        roles=["super_admin"],
    )


@pytest.fixture
def regular_user() -> UserContext:
    return UserContext(
        user_id="user-uid-2",
        email="user@example.com",
        organization_permissions={},
        account_permissions={},
    )


def _make_sse_server_doc(
    name: str = "hubspot_mcp",
    description: str = "HubSpot CRM",
    enabled: bool = False,
    auth_type: str | None = None,
    url: str = "${HUBSPOT_MCP_URL}",
    version: str = "v1.0.0",
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "integration_type": "mcp",
        "hosting": "provider",
        "specialist_categories": ["crm"],
        "tool_count": 10,
        "estimated_tokens": 1500,
        "keywords": ["crm", "hubspot"],
        "connection": {
            "connection_type": "sse",
            "url": url,
            "headers": {"Authorization": "Bearer ${HUBSPOT_API_KEY}"},
            "timeout_seconds": 30,
        },
        "auth_type": auth_type,
        "enabled": enabled,
        "metadata": {
            "version": version,
            "variant_name": "baseline",
            "experiment_id": "baseline",
            "created_at": "2026-04-20T12:00:00+00:00",
            "updated_at": "2026-04-20T12:00:00+00:00",
            "updated_by": "migration_script",
            "notes": "",
        },
    }


def _make_stdio_server_doc() -> dict[str, Any]:
    return {
        "name": "slack_mcp",
        "description": "Slack messaging",
        "integration_type": "mcp",
        "hosting": "self",
        "specialist_categories": ["communication"],
        "tool_count": 5,
        "estimated_tokens": 900,
        "keywords": ["slack"],
        "connection": {
            "connection_type": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-slack"],
            "env": {"SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}"},
            "working_dir": None,
        },
        "auth_type": None,
        "enabled": False,
        "metadata": {
            "version": "v1.0.0",
            "variant_name": "baseline",
            "experiment_id": "baseline",
            "created_at": "2026-04-20T12:00:00+00:00",
            "updated_at": "2026-04-20T12:00:00+00:00",
            "updated_by": "migration_script",
            "notes": "",
        },
    }


@pytest.fixture
def mock_db(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """MagicMock Firestore client with helper to seed docs."""
    # Pin env so ${VAR} resolution during Pydantic validation succeeds
    monkeypatch.setenv("HUBSPOT_MCP_URL", "https://hub.example.com/mcp")
    monkeypatch.setenv("HUBSPOT_API_KEY", "hub-key")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "slack-bot")
    return MagicMock()


def _seed_doc(
    db: MagicMock, server_id: str, payload: dict[str, Any] | None
) -> MagicMock:
    """Wire db.collection('mcp_server_configs').document(server_id).get() to return payload."""
    mock_doc = MagicMock()
    mock_doc.exists = payload is not None
    mock_doc.to_dict.return_value = payload
    doc_ref = MagicMock()
    doc_ref.get.return_value = mock_doc
    db.collection.return_value.document.return_value = doc_ref
    return doc_ref


class TestAuth:
    @pytest.mark.asyncio
    async def test_non_admin_cannot_list(
        self, regular_user: UserContext, mock_db: MagicMock
    ) -> None:
        from src.kene_api.routers.mcp_server_configs import list_mcp_server_configs

        with pytest.raises(HTTPException) as exc:
            await list_mcp_server_configs(user=regular_user, db=mock_db)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_non_admin_cannot_get(
        self, regular_user: UserContext, mock_db: MagicMock
    ) -> None:
        from src.kene_api.routers.mcp_server_configs import get_mcp_server_config

        with pytest.raises(HTTPException) as exc:
            await get_mcp_server_config("hubspot_mcp", user=regular_user, db=mock_db)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_non_admin_cannot_update(
        self, regular_user: UserContext, mock_db: MagicMock
    ) -> None:
        from src.kene_api.routers.mcp_server_configs import update_mcp_server_config

        update = MCPServerConfigUpdate(
            description="hacked", updated_by="hacker@evil.com"
        )

        with pytest.raises(HTTPException) as exc:
            await update_mcp_server_config(
                "hubspot_mcp",
                update,
                user=regular_user,
                db=mock_db,
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_non_admin_cannot_reload(self, regular_user: UserContext) -> None:
        from src.kene_api.routers.mcp_server_configs import reload_mcp_server_configs

        with pytest.raises(HTTPException) as exc:
            await reload_mcp_server_configs(user=regular_user)
        assert exc.value.status_code == 403


class TestPathSafety:
    @pytest.mark.asyncio
    async def test_server_id_with_slash_rejected(
        self, admin_user: UserContext, mock_db: MagicMock
    ) -> None:
        from src.kene_api.routers.mcp_server_configs import get_mcp_server_config

        with pytest.raises(HTTPException) as exc:
            await get_mcp_server_config(
                "hubspot_mcp/../secret", user=admin_user, db=mock_db
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_server_id_with_dotdot_rejected(
        self, admin_user: UserContext, mock_db: MagicMock
    ) -> None:
        from src.kene_api.routers.mcp_server_configs import get_mcp_server_config

        with pytest.raises(HTTPException) as exc:
            await get_mcp_server_config("..hidden", user=admin_user, db=mock_db)
        assert exc.value.status_code == 400


class TestList:
    @pytest.mark.asyncio
    async def test_list_returns_sorted_server_ids(
        self, admin_user: UserContext, mock_db: MagicMock
    ) -> None:
        from src.kene_api.routers.mcp_server_configs import list_mcp_server_configs

        doc_a = MagicMock(id="notion_mcp")
        doc_b = MagicMock(id="hubspot_mcp")
        doc_c = MagicMock(id="slack_mcp")
        mock_db.collection.return_value.stream.return_value = iter(
            [doc_a, doc_b, doc_c]
        )

        result = await list_mcp_server_configs(user=admin_user, db=mock_db)

        assert result == ["hubspot_mcp", "notion_mcp", "slack_mcp"]
        mock_db.collection.assert_called_with("mcp_server_configs")


class TestGet:
    @pytest.mark.asyncio
    async def test_get_returns_full_config(
        self, admin_user: UserContext, mock_db: MagicMock
    ) -> None:
        from src.kene_api.routers.mcp_server_configs import get_mcp_server_config

        _seed_doc(mock_db, "hubspot_mcp", _make_sse_server_doc())

        result = await get_mcp_server_config("hubspot_mcp", user=admin_user, db=mock_db)

        # GET returns the raw Firestore dict (preserves ${VAR} literals per
        # the secret-materialization fix); fields accessed by key, not attr.
        assert result["name"] == "hubspot_mcp"
        assert result["hosting"] == "provider"
        assert result["connection"]["connection_type"] == "sse"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_404(
        self, admin_user: UserContext, mock_db: MagicMock
    ) -> None:
        from src.kene_api.routers.mcp_server_configs import get_mcp_server_config

        _seed_doc(mock_db, "nonexistent", None)

        with pytest.raises(HTTPException) as exc:
            await get_mcp_server_config("nonexistent", user=admin_user, db=mock_db)
        assert exc.value.status_code == 404


class TestUpdate:
    @pytest.mark.asyncio
    async def test_put_happy_path_writes_audit(
        self,
        admin_user: UserContext,
        mock_db: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from src.kene_api.routers import mcp_server_configs as router_mod

        pre = _make_sse_server_doc(description="old desc", version="v1.0.0")
        post = _make_sse_server_doc(description="new desc", version="v1.0.1")

        doc_ref = _seed_doc(mock_db, "hubspot_mcp", pre)
        # After update, the .get() should return the new doc
        updated_doc = MagicMock()
        updated_doc.exists = True
        updated_doc.to_dict.return_value = post
        doc_ref.get.side_effect = [
            MagicMock(exists=True, to_dict=lambda: pre),
            updated_doc,
        ]

        spy_audit = AsyncMock(return_value="audit-1")
        monkeypatch.setattr(router_mod, "log_config_action", spy_audit)

        spy_reload = AsyncMock()
        mock_manager = MagicMock()
        mock_manager.reload = spy_reload
        monkeypatch.setattr(
            "app.adk.mcp_config.manager.get_mcp_manager", lambda: mock_manager
        )

        update = MCPServerConfigUpdate(
            description="new desc", updated_by="admin@ken-e.ai"
        )
        resp = await router_mod.update_mcp_server_config(
            "hubspot_mcp", update, user=admin_user, db=mock_db
        )

        # Audit called once, with doc_type and fields_changed
        assert spy_audit.await_count == 1
        kw = spy_audit.await_args.kwargs
        assert kw["doc_type"] == "mcp_server_config"
        assert kw["doc_id"] == "hubspot_mcp"
        assert kw["action"] == "updated"
        assert "description" in kw["fields_changed"]
        assert kw["changes"]["description"] == {
            "before": "old desc",
            "after": "new desc",
        }
        assert kw["version_before"] == "v1.0.0"
        assert kw["version_after"].startswith("v1.0.")

        # Description-only change → reload NOT triggered
        spy_reload.assert_not_awaited()

        # Response payload exposes the updated config fields + warnings list
        assert resp["description"] == "new desc"
        assert resp["warnings"] == []

    @pytest.mark.asyncio
    async def test_put_connection_change_triggers_reload(
        self,
        admin_user: UserContext,
        mock_db: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from src.kene_api.models.mcp_server_models import SseConnectionConfig
        from src.kene_api.routers import mcp_server_configs as router_mod

        pre = _make_sse_server_doc()
        post = _make_sse_server_doc(version="v1.0.1")
        post["connection"]["timeout_seconds"] = 60

        doc_ref = _seed_doc(mock_db, "hubspot_mcp", pre)
        doc_ref.get.side_effect = [
            MagicMock(exists=True, to_dict=lambda: pre),
            MagicMock(exists=True, to_dict=lambda: post),
        ]

        monkeypatch.setattr(
            router_mod, "log_config_action", AsyncMock(return_value="audit-2")
        )
        spy_reload = AsyncMock()
        mock_manager = MagicMock()
        mock_manager.reload = spy_reload
        monkeypatch.setattr(
            "app.adk.mcp_config.manager.get_mcp_manager", lambda: mock_manager
        )

        new_conn = SseConnectionConfig(
            connection_type="sse",
            url="${HUBSPOT_MCP_URL}",
            headers={"Authorization": "Bearer ${HUBSPOT_API_KEY}"},
            timeout_seconds=60,
        )
        update = MCPServerConfigUpdate(connection=new_conn, updated_by="admin@ken-e.ai")

        resp = await router_mod.update_mcp_server_config(
            "hubspot_mcp", update, user=admin_user, db=mock_db
        )

        spy_reload.assert_awaited_once()
        # Response surfaces the reload action
        assert any("reload" in w.lower() for w in resp["warnings"])

    @pytest.mark.asyncio
    async def test_put_enabled_flip_triggers_reload(
        self,
        admin_user: UserContext,
        mock_db: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from src.kene_api.routers import mcp_server_configs as router_mod

        pre = _make_sse_server_doc(enabled=True)
        post = _make_sse_server_doc(enabled=False, version="v1.0.1")

        doc_ref = _seed_doc(mock_db, "hubspot_mcp", pre)
        doc_ref.get.side_effect = [
            MagicMock(exists=True, to_dict=lambda: pre),
            MagicMock(exists=True, to_dict=lambda: post),
        ]

        monkeypatch.setattr(
            router_mod, "log_config_action", AsyncMock(return_value="a")
        )
        spy_reload = AsyncMock()
        mock_manager = MagicMock()
        mock_manager.reload = spy_reload
        monkeypatch.setattr(
            "app.adk.mcp_config.manager.get_mcp_manager", lambda: mock_manager
        )

        update = MCPServerConfigUpdate(enabled=False, updated_by="admin@ken-e.ai")
        await router_mod.update_mcp_server_config(
            "hubspot_mcp", update, user=admin_user, db=mock_db
        )

        spy_reload.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_put_reload_failure_surfaces_non_fatal_warning(
        self,
        admin_user: UserContext,
        mock_db: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A reload exception must not fail the PUT; it's surfaced as a warning."""
        from src.kene_api.models.mcp_server_models import SseConnectionConfig
        from src.kene_api.routers import mcp_server_configs as router_mod

        pre = _make_sse_server_doc()
        post = _make_sse_server_doc(version="v1.0.1")

        doc_ref = _seed_doc(mock_db, "hubspot_mcp", pre)
        doc_ref.get.side_effect = [
            MagicMock(exists=True, to_dict=lambda: pre),
            MagicMock(exists=True, to_dict=lambda: post),
        ]

        monkeypatch.setattr(
            router_mod, "log_config_action", AsyncMock(return_value="a")
        )
        mock_manager = MagicMock()
        mock_manager.reload = AsyncMock(side_effect=RuntimeError("boom"))
        monkeypatch.setattr(
            "app.adk.mcp_config.manager.get_mcp_manager", lambda: mock_manager
        )

        update = MCPServerConfigUpdate(
            connection=SseConnectionConfig(
                connection_type="sse",
                url="${HUBSPOT_MCP_URL}",
                headers={"Authorization": "Bearer ${HUBSPOT_API_KEY}"},
                timeout_seconds=45,
            ),
            updated_by="admin@ken-e.ai",
        )

        resp = await router_mod.update_mcp_server_config(
            "hubspot_mcp", update, user=admin_user, db=mock_db
        )

        assert any(
            "reload" in w.lower() and ("failed" in w.lower() or "error" in w.lower())
            for w in resp["warnings"]
        )

    @pytest.mark.asyncio
    async def test_put_hosting_connection_mismatch_rejected(
        self, admin_user: UserContext, mock_db: MagicMock
    ) -> None:
        """Stdio connection + hosting='provider' is a schema invariant violation."""
        from pydantic import ValidationError
        from src.kene_api.models.mcp_server_models import StdioConnectionConfig

        # MCPServerConfigUpdate alone doesn't validate cross-field (hosting vs connection)
        # — the check runs on MCPServerFirestoreConfig at write-combine time. So the
        # 422 path has to trigger inside the router when it assembles the merged doc.
        stdio_conn = StdioConnectionConfig(
            connection_type="stdio", command="echo", args=[], env={}
        )
        update = MCPServerConfigUpdate(
            connection=stdio_conn,
            hosting="provider",  # wrong: stdio must be 'self'
            updated_by="admin@ken-e.ai",
        )

        # The test passes so long as MCPServerConfigUpdate accepts this (router
        # rejects at merge time) OR Pydantic already rejects it. Either way, the
        # combination must not reach Firestore.
        from src.kene_api.routers import mcp_server_configs as router_mod

        _seed_doc(mock_db, "hubspot_mcp", _make_sse_server_doc())

        with pytest.raises((HTTPException, ValidationError)):
            await router_mod.update_mcp_server_config(
                "hubspot_mcp", update, user=admin_user, db=mock_db
            )


class TestSecretMaterialization:
    """Regression tests for the Sprint 6 code-review secret-leak fix.

    Pre-fix, ``MCPServerFirestoreConfig(**merged).model_dump()`` ran the
    ``SseConnectionConfig.url`` / ``StdioConnectionConfig.env`` validators
    (``mode="before"``) which replaced ``${VAR}`` patterns with the
    resolved secret value via ``get_env_or_secret``. That resolved payload
    was then written to Firestore, returned in PUT responses, and
    captured in audit trail ``changes`` — leaking every secret.

    Post-fix, the router writes the raw ``merged`` dict (literals
    preserved) and uses ``response_model=None``. The throwaway
    ``MCPServerFirestoreConfig(**merged)`` call exists only to enforce
    cross-field invariants; its resolved output is discarded.

    These tests pin the invariant: ``${VAR}`` strings must stay literal
    in Firestore writes, GET responses, PUT responses, and audit
    ``changes`` — even when the env var resolves to a real value.
    """

    @pytest.mark.asyncio
    async def test_put_preserves_literal_var_in_firestore(
        self,
        admin_user: UserContext,
        mock_db: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from src.kene_api.models.mcp_server_models import SseConnectionConfig
        from src.kene_api.routers import mcp_server_configs as router_mod

        # Pin the env var so Pydantic resolves ${HUBSPOT_API_KEY} → a
        # non-empty "real secret". This is the condition that WOULD leak.
        monkeypatch.setenv("HUBSPOT_MCP_URL", "https://hub.example.com/mcp")
        monkeypatch.setenv("HUBSPOT_API_KEY", "SUPER-SECRET-DO-NOT-LEAK-123")

        pre = _make_sse_server_doc()
        doc_ref = _seed_doc(mock_db, "hubspot_mcp", pre)

        monkeypatch.setattr(
            router_mod, "log_config_action", AsyncMock(return_value="audit-id")
        )
        mock_manager = MagicMock()
        mock_manager.reload = AsyncMock(return_value={"unloaded": [], "kept": 0})
        monkeypatch.setattr(
            "app.adk.mcp_config.manager.get_mcp_manager", lambda: mock_manager
        )

        new_conn = SseConnectionConfig(
            connection_type="sse",
            url="${HUBSPOT_MCP_URL}",
            headers={"Authorization": "Bearer ${HUBSPOT_API_KEY}"},
            timeout_seconds=45,
        )
        update = MCPServerConfigUpdate(connection=new_conn, updated_by="admin@ken-e.ai")

        await router_mod.update_mcp_server_config(
            "hubspot_mcp", update, user=admin_user, db=mock_db
        )

        # Capture the dict handed to Firestore's .set()
        written_payload = doc_ref.set.call_args.args[0]

        # Literal ${VAR} must be in the stored doc, NOT the resolved secret
        assert written_payload["connection"]["url"] == "${HUBSPOT_MCP_URL}", (
            f"URL must be literal; got {written_payload['connection']['url']!r}"
        )
        assert (
            written_payload["connection"]["headers"]["Authorization"]
            == "Bearer ${HUBSPOT_API_KEY}"
        ), "Authorization header must preserve ${HUBSPOT_API_KEY} literal"
        assert "SUPER-SECRET-DO-NOT-LEAK-123" not in str(written_payload), (
            f"Resolved secret leaked into Firestore payload: {written_payload!r}"
        )

    @pytest.mark.asyncio
    async def test_put_response_preserves_literal_var(
        self,
        admin_user: UserContext,
        mock_db: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from src.kene_api.models.mcp_server_models import SseConnectionConfig
        from src.kene_api.routers import mcp_server_configs as router_mod

        monkeypatch.setenv("HUBSPOT_MCP_URL", "https://hub.example.com/mcp")
        monkeypatch.setenv("HUBSPOT_API_KEY", "SUPER-SECRET-DO-NOT-LEAK-456")

        pre = _make_sse_server_doc()
        _seed_doc(mock_db, "hubspot_mcp", pre)

        monkeypatch.setattr(
            router_mod, "log_config_action", AsyncMock(return_value="audit-id")
        )
        mock_manager = MagicMock()
        mock_manager.reload = AsyncMock(return_value={"unloaded": [], "kept": 0})
        monkeypatch.setattr(
            "app.adk.mcp_config.manager.get_mcp_manager", lambda: mock_manager
        )

        new_conn = SseConnectionConfig(
            connection_type="sse",
            url="${HUBSPOT_MCP_URL}",
            headers={"Authorization": "Bearer ${HUBSPOT_API_KEY}"},
            timeout_seconds=45,
        )
        update = MCPServerConfigUpdate(connection=new_conn, updated_by="admin@ken-e.ai")

        resp = await router_mod.update_mcp_server_config(
            "hubspot_mcp", update, user=admin_user, db=mock_db
        )

        assert resp["connection"]["url"] == "${HUBSPOT_MCP_URL}"
        assert (
            resp["connection"]["headers"]["Authorization"]
            == "Bearer ${HUBSPOT_API_KEY}"
        )
        assert "SUPER-SECRET-DO-NOT-LEAK-456" not in str(resp)

    @pytest.mark.asyncio
    async def test_get_returns_literal_var(
        self,
        admin_user: UserContext,
        mock_db: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from src.kene_api.routers.mcp_server_configs import get_mcp_server_config

        monkeypatch.setenv("HUBSPOT_MCP_URL", "https://hub.example.com/mcp")
        monkeypatch.setenv("HUBSPOT_API_KEY", "SUPER-SECRET-DO-NOT-LEAK-789")

        _seed_doc(mock_db, "hubspot_mcp", _make_sse_server_doc())

        resp = await get_mcp_server_config("hubspot_mcp", user=admin_user, db=mock_db)

        # GET must return the raw Firestore dict with ${VAR} literals
        assert resp["connection"]["url"] == "${HUBSPOT_MCP_URL}"
        assert (
            resp["connection"]["headers"]["Authorization"]
            == "Bearer ${HUBSPOT_API_KEY}"
        )
        assert "SUPER-SECRET-DO-NOT-LEAK-789" not in str(resp)

    @pytest.mark.asyncio
    async def test_audit_changes_record_literal_var_not_resolved(
        self,
        admin_user: UserContext,
        mock_db: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from src.kene_api.models.mcp_server_models import SseConnectionConfig
        from src.kene_api.routers import mcp_server_configs as router_mod

        monkeypatch.setenv("HUBSPOT_MCP_URL", "https://hub.example.com/mcp")
        monkeypatch.setenv("HUBSPOT_API_KEY", "SUPER-SECRET-DO-NOT-LEAK-999")

        pre = _make_sse_server_doc()
        _seed_doc(mock_db, "hubspot_mcp", pre)

        spy_audit = AsyncMock(return_value="audit-id")
        monkeypatch.setattr(router_mod, "log_config_action", spy_audit)
        mock_manager = MagicMock()
        mock_manager.reload = AsyncMock(return_value={"unloaded": [], "kept": 0})
        monkeypatch.setattr(
            "app.adk.mcp_config.manager.get_mcp_manager", lambda: mock_manager
        )

        new_conn = SseConnectionConfig(
            connection_type="sse",
            url="${HUBSPOT_MCP_URL}",
            headers={"Authorization": "Bearer ${HUBSPOT_API_KEY}"},
            timeout_seconds=60,  # differ from pre (30) so connection is in diff
        )
        update = MCPServerConfigUpdate(connection=new_conn, updated_by="admin@ken-e.ai")

        await router_mod.update_mcp_server_config(
            "hubspot_mcp", update, user=admin_user, db=mock_db
        )

        # Audit's changes.connection must contain literal ${VAR}s for both
        # before and after — the secret must NOT be in the history record.
        changes = spy_audit.await_args.kwargs["changes"]
        assert "connection" in changes, (
            f"Expected connection in audit changes; got keys={list(changes)}"
        )
        changes_str = str(changes["connection"])
        assert "${HUBSPOT_API_KEY}" in changes_str
        assert "SUPER-SECRET-DO-NOT-LEAK-999" not in changes_str, (
            f"Audit leaked resolved secret: {changes_str!r}"
        )


class TestUpdateValidation:
    def test_update_rejects_invalid_auth_type(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="auth_type"):
            MCPServerConfigUpdate(
                auth_type="hacker_oauth",  # not in CREDENTIAL_KEYS
                updated_by="admin@ken-e.ai",
            )

    def test_update_rejects_empty_specialist_categories(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            MCPServerConfigUpdate(
                specialist_categories=[],  # min_length=1
                updated_by="admin@ken-e.ai",
            )


class TestHistory:
    @pytest.mark.asyncio
    async def test_history_returns_entries_desc(
        self, admin_user: UserContext, mock_db: MagicMock
    ) -> None:
        from src.kene_api.routers.mcp_server_configs import (
            get_mcp_server_config_history,
        )

        # Seed doc exists (admin gated only; history endpoint checks server exists)
        _seed_doc(mock_db, "hubspot_mcp", _make_sse_server_doc())

        # Seed the history subcollection query to yield two entries
        entry_a = MagicMock()
        entry_a.to_dict.return_value = {
            "action": "updated",
            "doc_type": "mcp_server_config",
            "doc_id": "hubspot_mcp",
            "user_id": "admin-uid-1",
            "user_email": "admin@ken-e.ai",
            "timestamp": "2026-04-24T10:00:00+00:00",
            "version_before": "v1.0.0",
            "version_after": "v1.0.1",
            "fields_changed": ["description"],
            "changes": {"description": {"before": "a", "after": "b"}},
        }
        entry_b = MagicMock()
        entry_b.to_dict.return_value = {
            "action": "updated",
            "doc_type": "mcp_server_config",
            "doc_id": "hubspot_mcp",
            "user_id": "admin-uid-1",
            "user_email": "admin@ken-e.ai",
            "timestamp": "2026-04-24T09:00:00+00:00",
            "version_before": None,
            "version_after": "v1.0.0",
            "fields_changed": [],
            "changes": {},
        }

        history_query = MagicMock()
        history_query.stream.return_value = iter([entry_a, entry_b])
        mock_db.collection.return_value.document.return_value.collection.return_value.order_by.return_value.limit.return_value = history_query

        result = await get_mcp_server_config_history(
            "hubspot_mcp", user=admin_user, db=mock_db, limit=20
        )

        assert len(result) == 2
        assert result[0].timestamp == "2026-04-24T10:00:00+00:00"
        assert result[1].timestamp == "2026-04-24T09:00:00+00:00"

    @pytest.mark.asyncio
    async def test_history_limit_bounded(
        self, admin_user: UserContext, mock_db: MagicMock
    ) -> None:
        from src.kene_api.routers.mcp_server_configs import (
            get_mcp_server_config_history,
        )

        with pytest.raises(HTTPException) as exc:
            await get_mcp_server_config_history(
                "hubspot_mcp", user=admin_user, db=mock_db, limit=10000
            )
        assert exc.value.status_code == 400


class TestReloadEndpoint:
    @pytest.mark.asyncio
    async def test_reload_calls_manager(
        self, admin_user: UserContext, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.kene_api.routers import mcp_server_configs as router_mod

        spy_reload = AsyncMock(return_value={"unloaded": ["hubspot_mcp"], "kept": 5})
        mock_manager = MagicMock()
        mock_manager.reload = spy_reload
        monkeypatch.setattr(
            "app.adk.mcp_config.manager.get_mcp_manager", lambda: mock_manager
        )

        resp = await router_mod.reload_mcp_server_configs(user=admin_user)

        spy_reload.assert_awaited_once()
        assert resp["status"] == "ok"


class TestMCPServerManagerReload:
    """Unit tests for MCPServerManager.reload() itself."""

    @pytest.mark.asyncio
    async def test_reload_calls_loader_reload(self) -> None:
        from app.adk.mcp_config.manager import MCPServerManager

        manager = MCPServerManager()
        mock_loader = MagicMock()
        mock_loader.reload = MagicMock(return_value={})
        mock_loader.configs = {}
        manager._config_loader = mock_loader

        result = await manager.reload()

        mock_loader.reload.assert_called_once()
        assert "unloaded" in result

    @pytest.mark.asyncio
    async def test_reload_evicts_servers_with_changed_config(self) -> None:
        from datetime import datetime, timezone

        from app.adk.mcp_config.config import (
            MCPServerConfig,
            SseConnectionConfig,
        )
        from app.adk.mcp_config.manager import LoadedServer, MCPServerManager

        def _cfg(url: str) -> MCPServerConfig:
            return MCPServerConfig(
                name="hubspot_mcp",
                description="d",
                category="crm",
                connection=SseConnectionConfig(
                    connection_type="sse", url=url, headers={}, timeout_seconds=30
                ),
                enabled=True,
            )

        old_cfg = _cfg("https://old.example.com")
        new_cfg = _cfg("https://new.example.com")

        manager = MCPServerManager()
        manager._loaded_servers["hubspot_mcp"] = LoadedServer(
            name="hubspot_mcp",
            config=old_cfg,
            tools=[],
            loaded_at=datetime.now(timezone.utc),
            last_used=datetime.now(timezone.utc),
            token_estimate=1000,
        )

        mock_loader = MagicMock()
        mock_loader.reload = MagicMock()
        mock_loader.configs = {"hubspot_mcp": new_cfg}
        manager._config_loader = mock_loader

        result = await manager.reload()

        assert "hubspot_mcp" in result["unloaded"]
        assert "hubspot_mcp" not in manager._loaded_servers

    @pytest.mark.asyncio
    async def test_reload_keeps_servers_with_unchanged_config(self) -> None:
        from datetime import datetime, timezone

        from app.adk.mcp_config.config import (
            MCPServerConfig,
            SseConnectionConfig,
        )
        from app.adk.mcp_config.manager import LoadedServer, MCPServerManager

        cfg = MCPServerConfig(
            name="hubspot_mcp",
            description="d",
            category="crm",
            connection=SseConnectionConfig(
                connection_type="sse",
                url="https://stable.example.com",
                headers={},
                timeout_seconds=30,
            ),
            enabled=True,
        )

        manager = MCPServerManager()
        manager._loaded_servers["hubspot_mcp"] = LoadedServer(
            name="hubspot_mcp",
            config=cfg,
            tools=[],
            loaded_at=datetime.now(timezone.utc),
            last_used=datetime.now(timezone.utc),
            token_estimate=1000,
        )

        mock_loader = MagicMock()
        mock_loader.reload = MagicMock()
        # Same config, same content
        mock_loader.configs = {"hubspot_mcp": cfg}
        manager._config_loader = mock_loader

        result = await manager.reload()

        assert "hubspot_mcp" not in result["unloaded"]
        assert "hubspot_mcp" in manager._loaded_servers

    @pytest.mark.asyncio
    async def test_reload_unloads_servers_removed_from_firestore(self) -> None:
        from datetime import datetime, timezone

        from app.adk.mcp_config.config import (
            MCPServerConfig,
            SseConnectionConfig,
        )
        from app.adk.mcp_config.manager import LoadedServer, MCPServerManager

        cfg = MCPServerConfig(
            name="hubspot_mcp",
            description="d",
            category="crm",
            connection=SseConnectionConfig(
                connection_type="sse",
                url="https://x.example.com",
                headers={},
                timeout_seconds=30,
            ),
            enabled=True,
        )

        manager = MCPServerManager()
        manager._loaded_servers["hubspot_mcp"] = LoadedServer(
            name="hubspot_mcp",
            config=cfg,
            tools=[],
            loaded_at=datetime.now(timezone.utc),
            last_used=datetime.now(timezone.utc),
            token_estimate=1000,
        )

        mock_loader = MagicMock()
        mock_loader.reload = MagicMock()
        mock_loader.configs = {}  # hubspot_mcp was deleted from Firestore
        manager._config_loader = mock_loader

        result = await manager.reload()

        assert "hubspot_mcp" in result["unloaded"]
