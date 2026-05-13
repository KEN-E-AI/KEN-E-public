"""
Unit tests for app.adk.agents.agent_factory.config_loader.

All Firestore I/O is mocked at the import boundary so these tests run without
any GCP credentials.
"""

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# In-memory Firestore stand-in (used by test_load_with_stateful_fake_firestore)
# ---------------------------------------------------------------------------


class FakeFirestoreDb:
    """In-memory Firestore stand-in that routes .collection().document().get() and .list_documents()."""

    def __init__(self, docs: dict) -> None:
        self._docs = docs

    def collection(self, col: str) -> "FakeCollection":
        return FakeCollection(self._docs, (col,))


class FakeCollection:
    def __init__(self, docs: dict, path: tuple) -> None:
        self._docs = docs
        self._path = path

    def document(self, doc_id: str) -> "FakeDocument":
        return FakeDocument(self._docs, (*self._path, doc_id))

    def list_documents(self) -> list:
        prefix = self._path
        results = []
        for path, _data in self._docs.items():
            if path[: len(prefix)] == prefix and len(path) == len(prefix) + 1:
                results.append(FakeDocRef(path))
        return results


class FakeDocument:
    def __init__(self, docs: dict, path: tuple) -> None:
        self._docs = docs
        self._path = path

    def get(self) -> "FakeSnapshot":
        data = self._docs.get(self._path)
        return FakeSnapshot(data)

    def collection(self, col: str) -> FakeCollection:
        return FakeCollection(self._docs, (*self._path, col))


class FakeDocRef:
    def __init__(self, path: tuple) -> None:
        self.id = path[-1]


class FakeSnapshot:
    def __init__(self, data: dict | None) -> None:
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict:
        return self._data or {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GLOBAL_DOC = {
    "instruction": "You are a global assistant.",
    "model": "gemini-2.5-pro",
    "description": "Global agent",
    "temperature": 0.3,
    "metadata": {"version": "v1.0.0"},
}

_OVERLAY_DOC = {
    "instruction": "You are a custom assistant.",
    "model": "gemini-2.5-flash",
    "based_on_version": 2,
}


def _make_mock_db(
    global_data: dict | None = None,
    overlay_data: dict | None = None,
    account_id: str = "acc_123",
    config_id: str = "test_agent",
) -> MagicMock:
    """Build a mock Firestore db whose collection/document/get chain returns
    the supplied data dicts (or a not-found snapshot when None)."""

    def make_snapshot(data: dict | None) -> MagicMock:
        snap = MagicMock()
        snap.exists = data is not None
        snap.to_dict.return_value = data or {}
        return snap

    global_snap = make_snapshot(global_data)
    overlay_snap = make_snapshot(overlay_data)

    global_doc_ref = MagicMock()
    global_doc_ref.get.return_value = global_snap

    overlay_doc_ref = MagicMock()
    overlay_doc_ref.get.return_value = overlay_snap

    global_collection = MagicMock()
    global_collection.document.return_value = global_doc_ref

    overlay_collection = MagicMock()
    overlay_collection.document.return_value = overlay_doc_ref

    account_doc = MagicMock()
    account_doc.collection.return_value = overlay_collection

    accounts_collection = MagicMock()
    accounts_collection.document.return_value = account_doc

    def collection_side_effect(name: str) -> MagicMock:
        if name == "agent_configs":
            return global_collection
        if name == "accounts":
            return accounts_collection
        raise ValueError(f"Unexpected collection: {name}")

    db = MagicMock()
    db.collection.side_effect = collection_side_effect
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConfigLoader:
    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_load_global_only_no_account_id(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import load_agent_config

        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(global_data=_GLOBAL_DOC)

        result = load_agent_config("test_agent")

        assert result.instruction == _GLOBAL_DOC["instruction"]
        assert result.model == _GLOBAL_DOC["model"]
        assert result.customization_status == "default"
        assert result.based_on_version is None

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_load_global_with_overlay_shallow_merge(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import load_agent_config

        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(
            global_data=_GLOBAL_DOC, overlay_data=_OVERLAY_DOC
        )

        result = load_agent_config("test_agent", account_id="acc_123")

        assert result.instruction == _OVERLAY_DOC["instruction"]
        assert result.model == _OVERLAY_DOC["model"]
        assert result.customization_status == "customized"
        assert result.based_on_version == 2

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_load_custom_only_no_global_counterpart(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import load_agent_config

        overlay_only = {
            "instruction": "Custom only agent.",
            "model": "gemini-2.5-flash",
            "based_on_version": 5,
        }
        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(
            global_data=None, overlay_data=overlay_only
        )

        result = load_agent_config("test_agent", account_id="acc_123")

        assert result.instruction == overlay_only["instruction"]
        assert result.model == overlay_only["model"]
        assert result.customization_status == "custom_agent"
        assert result.based_on_version == 5

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_load_neither_exists_raises_config_not_found(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import (
            ConfigNotFoundError,
            load_agent_config,
        )

        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(
            global_data=None, overlay_data=None
        )

        with pytest.raises(ConfigNotFoundError):
            load_agent_config("test_agent", account_id="acc_123")

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_load_with_account_id_but_only_global_exists(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import load_agent_config

        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(
            global_data=_GLOBAL_DOC, overlay_data=None
        )

        result = load_agent_config("test_agent", account_id="acc_123")

        assert result.customization_status == "default"
        assert result.based_on_version is None

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_forward_compat_field_defaults(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import load_agent_config

        minimal_doc = {"instruction": "Hello.", "model": "gemini-2.5-pro"}
        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(global_data=minimal_doc)

        result = load_agent_config("test_agent")

        assert result.skill_ids == []
        assert result.sandbox_code_executor_enabled is False
        assert result.response_schema is None

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_load_missing_required_field_raises_config_validation_error(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import (
            ConfigValidationError,
            load_agent_config,
        )

        # Doc is missing the required `model` field.
        invalid_doc = {"instruction": "Hello."}
        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(global_data=invalid_doc)

        with pytest.raises(ConfigValidationError):
            load_agent_config("test_agent")

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_overlay_wins_per_field_not_deep_merged(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        """AH-40: shallow-merge semantics on flat ``temperature`` / ``max_output_tokens``.

        The overlay's flat fields replace the global's per-field, with no
        deep-merge into a nested structure.
        """
        from app.adk.agents.agent_factory.config_loader import load_agent_config

        global_data = {
            "instruction": "Global.",
            "model": "gemini-2.5-pro",
            "temperature": 0.3,
            "max_output_tokens": 2500,
        }
        overlay_data = {
            "instruction": "Overlay.",
            "model": "gemini-2.5-flash",
            "temperature": 0.9,
            # Overlay does NOT set max_output_tokens; global value flows through.
            "based_on_version": 1,
        }
        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(
            global_data=global_data, overlay_data=overlay_data
        )

        result = load_agent_config("test_agent", account_id="acc_123")

        assert result.temperature == 0.9
        assert result.max_output_tokens == 2500

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_extra_forbid_rejects_legacy_nested_block(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        """AH-40 AC-6: ``MergedAgentConfig`` (factory) rejects a stray
        ``generate_content_config`` so backfill misses fail loud here too."""
        from app.adk.agents.agent_factory.config_loader import (
            ConfigValidationError,
            load_agent_config,
        )

        legacy_doc = {
            "instruction": "Legacy nested doc.",
            "model": "gemini-2.5-pro",
            "generate_content_config": {"temperature": 0.3},
        }
        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(global_data=legacy_doc)

        with pytest.raises(ConfigValidationError):
            load_agent_config("test_agent")

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_storage_internal_fields_stripped_before_validate(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        """``name`` / ``title`` / ``created_at`` / ``updated_at`` / ``created_by``
        live on storage docs but not on the factory's ``MergedAgentConfig``
        (extra="forbid"). They must be stripped before validation."""
        from app.adk.agents.agent_factory.config_loader import load_agent_config

        global_data = {
            "name": "Dave",
            "title": "Business Researcher",
            "instruction": "Hello.",
            "model": "gemini-2.5-pro",
            "temperature": 0.5,
            "max_output_tokens": 4096,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "created_by": "seed@ken-e.ai",
        }
        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(global_data=global_data)

        result = load_agent_config("test_agent")

        assert result.temperature == 0.5
        assert result.max_output_tokens == 4096
        assert not hasattr(result, "name")
        assert not hasattr(result, "title")

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_pre_ah_prd_02_legacy_fields_stripped(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        """``canonical_id`` and ``legacy_agent_name`` are pre-AH-PRD-02 seed
        metadata on a handful of agent_configs docs (business_researcher,
        business_formatter, competitive_analyst, marketing_strategist). The
        factory must strip them; otherwise loading any of those agents fails
        with ``extra="forbid"``."""
        from app.adk.agents.agent_factory.config_loader import load_agent_config

        global_data = {
            "instruction": "Researches business strategy.",
            "model": "gemini-2.5-pro",
            "canonical_id": "business_strategy",
            "legacy_agent_name": "Business Researcher",
        }
        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(global_data=global_data)

        result = load_agent_config("business_researcher")

        assert result.model == "gemini-2.5-pro"
        assert not hasattr(result, "canonical_id")
        assert not hasattr(result, "legacy_agent_name")

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_mer_e_deployment_status_field_stripped(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        """MER-E (sister repo) writes ``deployment_status`` onto shared
        agent_configs docs. The factory doesn't consume it but must not
        reject docs that carry it."""
        from app.adk.agents.agent_factory.config_loader import load_agent_config

        global_data = {
            "instruction": "Hello.",
            "model": "gemini-2.5-pro",
            "temperature": 0.5,
            "deployment_status": None,
        }
        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(global_data=global_data)

        result = load_agent_config("test_agent")

        assert result.temperature == 0.5

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_based_on_version_passes_through(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import load_agent_config

        overlay = {
            "instruction": "Custom.",
            "model": "gemini-2.5-flash",
            "based_on_version": 3,
        }
        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(
            global_data=_GLOBAL_DOC, overlay_data=overlay
        )

        result = load_agent_config("test_agent", account_id="acc_123")

        assert result.based_on_version == 3

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_based_on_version_none_when_no_overlay(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import load_agent_config

        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(global_data=_GLOBAL_DOC)

        result = load_agent_config("test_agent")

        assert result.based_on_version is None

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_list_account_agent_configs_unions_global_and_overlay(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import (
            list_account_agent_configs,
        )

        global_refs = [
            MagicMock(id="agent_alpha"),
            MagicMock(id="agent_beta"),
            MagicMock(id="agent_gamma"),
        ]
        account_refs = [
            MagicMock(id="agent_gamma"),
            MagicMock(id="agent_delta"),
        ]

        global_collection = MagicMock()
        global_collection.list_documents.return_value = global_refs

        overlay_collection = MagicMock()
        overlay_collection.list_documents.return_value = account_refs

        account_doc = MagicMock()
        account_doc.collection.return_value = overlay_collection

        accounts_collection = MagicMock()
        accounts_collection.document.return_value = account_doc

        def collection_side_effect(name: str) -> MagicMock:
            if name == "agent_configs":
                return global_collection
            if name == "accounts":
                return accounts_collection
            raise ValueError(f"Unexpected collection: {name}")

        db = MagicMock()
        db.collection.side_effect = collection_side_effect

        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = db

        result = list_account_agent_configs("acc_123")

        assert result == sorted({"agent_alpha", "agent_beta", "agent_gamma", "agent_delta"})

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_list_account_agent_configs_empty_account(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import (
            list_account_agent_configs,
        )

        global_refs = [MagicMock(id="agent_one"), MagicMock(id="agent_two")]
        account_refs: list = []

        global_collection = MagicMock()
        global_collection.list_documents.return_value = global_refs

        overlay_collection = MagicMock()
        overlay_collection.list_documents.return_value = account_refs

        account_doc = MagicMock()
        account_doc.collection.return_value = overlay_collection

        accounts_collection = MagicMock()
        accounts_collection.document.return_value = account_doc

        def collection_side_effect(name: str) -> MagicMock:
            if name == "agent_configs":
                return global_collection
            if name == "accounts":
                return accounts_collection
            raise ValueError(f"Unexpected collection: {name}")

        db = MagicMock()
        db.collection.side_effect = collection_side_effect

        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = db

        result = list_account_agent_configs("acc_empty")

        assert result == ["agent_one", "agent_two"]

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_load_uses_explicit_project_id_when_provided(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import load_agent_config

        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(global_data=_GLOBAL_DOC)

        load_agent_config("test_agent", project_id="ken-e-staging")

        args, kwargs = mock_client.call_args
        project_passed = kwargs.get("project") or (args[0] if args else None)
        assert project_passed == "ken-e-staging"

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_load_falls_back_to_env_var_when_no_project_id(
        self, mock_client: MagicMock, mock_auth: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import load_agent_config

        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT_ID", "ken-e-test")
        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(global_data=_GLOBAL_DOC)

        load_agent_config("test_agent")

        args, kwargs = mock_client.call_args
        project_passed = kwargs.get("project") or (args[0] if args else None)
        assert project_passed == "ken-e-test"

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_load_firestore_connection_error_wraps_underlying_exception(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import (
            FirestoreConnectionError,
            load_agent_config,
        )

        mock_auth.return_value = (MagicMock(), None)
        mock_client.side_effect = Exception("connection refused")

        with pytest.raises(FirestoreConnectionError):
            load_agent_config("test_agent")

    def test_load_with_stateful_fake_firestore(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.adk.agents.agent_factory import config_loader

        global_doc = {
            "instruction": "You are the base assistant.",
            "model": "gemini-2.5-pro",
            "temperature": 0.3,
        }
        overlay_doc = {
            "instruction": "You are the custom assistant.",
            "model": "gemini-2.5-flash",
            "based_on_version": 7,
        }

        docs = {
            ("agent_configs", "my_agent"): global_doc,
            ("accounts", "acct_abc", "agent_configs", "my_agent"): overlay_doc,
        }
        fake_db = FakeFirestoreDb(docs)

        monkeypatch.setattr(
            config_loader,
            "google_auth_default",
            lambda: (None, None),
        )
        monkeypatch.setattr(
            config_loader.firestore,
            "Client",
            lambda project, credentials: fake_db,
        )

        result = config_loader.load_agent_config("my_agent", account_id="acct_abc")

        assert result.instruction == "You are the custom assistant."
        assert result.model == "gemini-2.5-flash"
        assert result.customization_status == "customized"
        assert result.based_on_version == 7


    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_phase3_flags_default_to_true_when_absent(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import load_agent_config

        minimal_doc = {"instruction": "Hello.", "model": "gemini-2.5-pro"}
        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(global_data=minimal_doc)

        result = load_agent_config("test_agent")

        assert result.available_to_copy is True
        assert result.automatically_available is True
        assert result.visible_in_frontend is True

    @patch("app.adk.agents.agent_factory.config_loader.google_auth_default")
    @patch("app.adk.agents.agent_factory.config_loader.firestore.Client")
    def test_phase3_flags_round_trip_false_values(
        self, mock_client: MagicMock, mock_auth: MagicMock
    ) -> None:
        from app.adk.agents.agent_factory.config_loader import load_agent_config

        doc_with_flags = {
            "instruction": "Hello.",
            "model": "gemini-2.5-pro",
            "available_to_copy": False,
            "automatically_available": False,
            "visible_in_frontend": False,
        }
        mock_auth.return_value = (MagicMock(), None)
        mock_client.return_value = _make_mock_db(global_data=doc_with_flags)

        result = load_agent_config("test_agent")

        assert result.available_to_copy is False
        assert result.automatically_available is False
        assert result.visible_in_frontend is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
