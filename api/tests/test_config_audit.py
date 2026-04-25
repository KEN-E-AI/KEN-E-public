"""Unit tests for the config audit helper.

Covers Sprint 6 Story 1.1.4-3 AC-7 and Sprint 6 Decision C — every
successful PUT to ``/api/v1/agent-configs/{id}`` or
``/api/v1/mcp-server-configs/{id}`` writes a ``ConfigAuditEntry`` to the
per-config history subcollection at ``{collection}/{doc_id}/history/{audit_id}``.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pytest
from src.kene_api.auth import UserContext
from src.kene_api.models.agent_config_models import ConfigAuditEntry
from src.kene_api.services.audit_service import log_config_action


class _FakeDocRef:
    def __init__(self, doc_id: str, store: dict[str, Any]) -> None:
        self.id = doc_id
        self._store = store

    def set(self, data: dict[str, Any]) -> None:
        self._store[self.id] = data


class _FakeSubcollection:
    def __init__(self, store: dict[str, Any]) -> None:
        self._store = store

    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(doc_id, self._store)


class _FakeParentDocRef:
    def __init__(self, parent: FakeFirestoreClient, doc_id: str) -> None:
        self._parent = parent
        self._doc_id = doc_id

    def collection(self, name: str) -> _FakeSubcollection:
        key = (self._parent.last_collection, self._doc_id, name)
        self._parent.subcollections.setdefault(key, {})
        return _FakeSubcollection(self._parent.subcollections[key])


class _FakeCollection:
    def __init__(self, parent: FakeFirestoreClient, name: str) -> None:
        self._parent = parent
        self._name = name

    def document(self, doc_id: str) -> _FakeParentDocRef:
        self._parent.last_collection = self._name
        return _FakeParentDocRef(self._parent, doc_id)


class FakeFirestoreClient:
    """Hermetic stand-in for google.cloud.firestore.Client.

    Tracks writes to ``{collection}/{doc_id}/history/{audit_id}`` in
    ``subcollections[(collection, doc_id, "history")][audit_id] = payload``.
    """

    def __init__(self) -> None:
        self.subcollections: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.last_collection: str | None = None

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(self, name)

    def history_for(self, collection: str, doc_id: str) -> dict[str, Any]:
        return self.subcollections.get((collection, doc_id, "history"), {})


class RaisingFirestoreClient:
    def collection(self, name: str) -> Any:
        raise RuntimeError("Firestore unavailable")


@pytest.fixture
def admin_user() -> UserContext:
    return UserContext(
        user_id="admin-uid-1",
        email="admin@ken-e.ai",
        organization_permissions={},
        account_permissions={},
    )


@pytest.fixture
def fake_db() -> FakeFirestoreClient:
    return FakeFirestoreClient()


class TestLogConfigActionPath:
    """Audit entries land at the correct subcollection path per Decision C."""

    @pytest.mark.asyncio
    async def test_writes_under_agent_configs_history(
        self, fake_db: FakeFirestoreClient, admin_user: UserContext
    ) -> None:
        audit_id = await log_config_action(
            db=fake_db,
            doc_type="agent_config",
            doc_id="business_researcher",
            action="updated",
            user=admin_user,
            version_after="v1.0.1",
        )

        assert audit_id != ""
        history = fake_db.history_for("agent_configs", "business_researcher")
        assert audit_id in history

    @pytest.mark.asyncio
    async def test_writes_under_mcp_server_configs_history(
        self, fake_db: FakeFirestoreClient, admin_user: UserContext
    ) -> None:
        audit_id = await log_config_action(
            db=fake_db,
            doc_type="mcp_server_config",
            doc_id="hubspot_mcp",
            action="updated",
            user=admin_user,
            version_after="v1.0.1",
        )

        history = fake_db.history_for("mcp_server_configs", "hubspot_mcp")
        assert audit_id in history

    @pytest.mark.asyncio
    async def test_audit_id_format_is_iso_timestamp_plus_uuid(
        self, fake_db: FakeFirestoreClient, admin_user: UserContext
    ) -> None:
        """Format matches log_strategy_action: {iso_ts}_{uuid8}."""
        audit_id = await log_config_action(
            db=fake_db,
            doc_type="agent_config",
            doc_id="ken_e_chatbot",
            action="updated",
            user=admin_user,
            version_after="v1.0.1",
        )

        # ISO-8601 timestamp followed by _<8 hex chars>
        assert re.match(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:\+00:00|Z)?_[0-9a-f]{8}$",
            audit_id,
        ), f"audit_id {audit_id!r} doesn't match expected format"


class TestLogConfigActionPayload:
    """Audit entries carry the ConfigAuditEntry shape."""

    @pytest.mark.asyncio
    async def test_captures_user_identity(
        self, fake_db: FakeFirestoreClient, admin_user: UserContext
    ) -> None:
        audit_id = await log_config_action(
            db=fake_db,
            doc_type="agent_config",
            doc_id="ken_e_chatbot",
            action="updated",
            user=admin_user,
            version_after="v1.0.1",
        )

        entry = fake_db.history_for("agent_configs", "ken_e_chatbot")[audit_id]
        assert entry["user_id"] == "admin-uid-1"
        assert entry["user_email"] == "admin@ken-e.ai"

    @pytest.mark.asyncio
    async def test_captures_action_and_doc_identity(
        self, fake_db: FakeFirestoreClient, admin_user: UserContext
    ) -> None:
        audit_id = await log_config_action(
            db=fake_db,
            doc_type="agent_config",
            doc_id="ken_e_chatbot",
            action="updated",
            user=admin_user,
            version_after="v1.0.1",
        )

        entry = fake_db.history_for("agent_configs", "ken_e_chatbot")[audit_id]
        assert entry["action"] == "updated"
        assert entry["doc_type"] == "agent_config"
        assert entry["doc_id"] == "ken_e_chatbot"

    @pytest.mark.asyncio
    async def test_captures_versions(
        self, fake_db: FakeFirestoreClient, admin_user: UserContext
    ) -> None:
        audit_id = await log_config_action(
            db=fake_db,
            doc_type="agent_config",
            doc_id="ken_e_chatbot",
            action="updated",
            user=admin_user,
            version_before="v1.0.0",
            version_after="v1.0.1",
        )

        entry = fake_db.history_for("agent_configs", "ken_e_chatbot")[audit_id]
        assert entry["version_before"] == "v1.0.0"
        assert entry["version_after"] == "v1.0.1"

    @pytest.mark.asyncio
    async def test_captures_fields_changed_and_changes(
        self, fake_db: FakeFirestoreClient, admin_user: UserContext
    ) -> None:
        audit_id = await log_config_action(
            db=fake_db,
            doc_type="agent_config",
            doc_id="ken_e_chatbot",
            action="updated",
            user=admin_user,
            version_after="v1.0.1",
            fields_changed=["temperature", "instruction"],
            changes={
                "temperature": {"before": 0.3, "after": 0.5},
                "instruction": {"before": "old", "after": "new"},
            },
        )

        entry = fake_db.history_for("agent_configs", "ken_e_chatbot")[audit_id]
        assert entry["fields_changed"] == ["temperature", "instruction"]
        assert entry["changes"]["temperature"] == {"before": 0.3, "after": 0.5}
        assert entry["changes"]["instruction"] == {"before": "old", "after": "new"}

    @pytest.mark.asyncio
    async def test_defaults_empty_fields_changed(
        self, fake_db: FakeFirestoreClient, admin_user: UserContext
    ) -> None:
        """Callers may omit fields_changed/changes (e.g., for a plain action log)."""
        audit_id = await log_config_action(
            db=fake_db,
            doc_type="agent_config",
            doc_id="ken_e_chatbot",
            action="viewed",
            user=admin_user,
            version_after="v1.0.0",
        )

        entry = fake_db.history_for("agent_configs", "ken_e_chatbot")[audit_id]
        assert entry["fields_changed"] == []
        assert entry["changes"] == {}

    @pytest.mark.asyncio
    async def test_iso_timestamp_is_utc(
        self, fake_db: FakeFirestoreClient, admin_user: UserContext
    ) -> None:
        audit_id = await log_config_action(
            db=fake_db,
            doc_type="agent_config",
            doc_id="ken_e_chatbot",
            action="updated",
            user=admin_user,
            version_after="v1.0.1",
        )

        entry = fake_db.history_for("agent_configs", "ken_e_chatbot")[audit_id]
        ts = entry["timestamp"]
        # Should round-trip through ConfigAuditEntry validation
        assert ConfigAuditEntry(**entry).timestamp == ts
        assert "T" in ts  # ISO-8601


class TestRequestIdPropagation:
    """X-Request-Id from contextvars flows through to the audit entry."""

    @pytest.mark.asyncio
    async def test_captures_request_id_from_contextvar(
        self, fake_db: FakeFirestoreClient, admin_user: UserContext
    ) -> None:
        from shared.structured_logging import _request_id_ctx

        token = _request_id_ctx.set("req-abc-123")
        try:
            audit_id = await log_config_action(
                db=fake_db,
                doc_type="agent_config",
                doc_id="ken_e_chatbot",
                action="updated",
                user=admin_user,
                version_after="v1.0.1",
            )
        finally:
            _request_id_ctx.reset(token)

        entry = fake_db.history_for("agent_configs", "ken_e_chatbot")[audit_id]
        assert entry["request_id"] == "req-abc-123"

    @pytest.mark.asyncio
    async def test_empty_request_id_becomes_none(
        self, fake_db: FakeFirestoreClient, admin_user: UserContext
    ) -> None:
        """Outside a request context, get_request_id() returns '' — persist as None."""
        audit_id = await log_config_action(
            db=fake_db,
            doc_type="agent_config",
            doc_id="ken_e_chatbot",
            action="updated",
            user=admin_user,
            version_after="v1.0.1",
        )

        entry = fake_db.history_for("agent_configs", "ken_e_chatbot")[audit_id]
        assert entry["request_id"] is None


class TestFailSafe:
    """Audit failures must not block the main operation."""

    @pytest.mark.asyncio
    async def test_firestore_write_failure_returns_empty_string(
        self, admin_user: UserContext, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.ERROR)

        audit_id = await log_config_action(
            db=RaisingFirestoreClient(),
            doc_type="agent_config",
            doc_id="ken_e_chatbot",
            action="updated",
            user=admin_user,
            version_after="v1.0.1",
        )

        assert audit_id == ""
        assert any(
            "audit" in r.message.lower()
            for r in caplog.records
            if r.levelno >= logging.ERROR
        )


class TestCollectionResolution:
    """Collection path derived from doc_type — no callers should hard-code it."""

    @pytest.mark.asyncio
    async def test_unknown_doc_type_raises(
        self, fake_db: FakeFirestoreClient, admin_user: UserContext
    ) -> None:
        with pytest.raises(ValueError, match="doc_type"):
            await log_config_action(
                db=fake_db,
                doc_type="unknown_thing",  # type: ignore[arg-type]
                doc_id="whatever",
                action="updated",
                user=admin_user,
                version_after="v1.0.1",
            )
