"""Unit tests for api/src/kene_api/models/chat.py (CH-PRD-01 §7 AC-1)."""

from datetime import datetime

import pytest
from src.kene_api.models.chat import (
    ChatArtifactIndex,
    ChatCategoryDefinition,
    ChatSessionMetadata,
    ChatStatusDetail,
    ModelContextWindowEntry,
    TodoItem,
    TodoList,
    compute_name_casefold,
)

# ---------------------------------------------------------------------------
# ChatSessionMetadata
# ---------------------------------------------------------------------------


class TestChatSessionMetadata:
    def _minimal(self, **overrides: object) -> dict:
        base: dict = {
            "session_id": "sess_001",
            "user_id": "user_abc",
            "account_id": "acc_xyz",
            "organization_id": "org_001",
            "model_id": "gemini-2.5-pro",
            "context_window_max": 1_048_576,
        }
        base.update(overrides)
        return base

    def test_instantiates_with_required_fields(self) -> None:
        meta = ChatSessionMetadata(**self._minimal())
        assert meta.session_id == "sess_001"
        assert meta.user_id == "user_abc"

    def test_no_cost_usd_cents_field(self) -> None:
        meta = ChatSessionMetadata(**self._minimal())
        assert not hasattr(meta, "cost_usd_cents"), (
            "cost_usd_cents must not exist on ChatSessionMetadata"
        )

    def test_no_is_agent_running_field(self) -> None:
        meta = ChatSessionMetadata(**self._minimal())
        assert not hasattr(meta, "is_agent_running"), (
            "is_agent_running must not exist on ChatSessionMetadata — "
            "running state is derived from last_agent_started_at / last_agent_stopped_at"
        )

    def test_has_agent_timestamp_fields(self) -> None:
        meta = ChatSessionMetadata(**self._minimal())
        assert hasattr(meta, "last_agent_started_at")
        assert hasattr(meta, "last_agent_stopped_at")
        assert meta.last_agent_started_at is None
        assert meta.last_agent_stopped_at is None

    def test_default_counter_fields_are_zero(self) -> None:
        meta = ChatSessionMetadata(**self._minimal())
        assert meta.input_tokens_total == 0
        assert meta.output_tokens_total == 0
        assert meta.reasoning_tokens_total == 0
        assert meta.tool_call_count == 0
        assert meta.artifact_count == 0
        assert meta.message_count == 0
        assert meta.compaction_count == 0

    def test_deleted_at_defaults_to_none(self) -> None:
        meta = ChatSessionMetadata(**self._minimal())
        assert meta.deleted_at is None

    def test_auto_title_attempted_at_defaults_to_none(self) -> None:
        meta = ChatSessionMetadata(**self._minimal())
        assert meta.auto_title_attempted_at is None

    def test_title_max_length_valid(self) -> None:
        meta = ChatSessionMetadata(**self._minimal(title="A" * 120))
        assert meta.title is not None
        assert len(meta.title) == 120

    def test_title_max_length_exceeded_raises(self) -> None:
        with pytest.raises(ValueError):
            ChatSessionMetadata(**self._minimal(title="A" * 121))

    def test_created_at_defaults_to_now(self) -> None:
        meta = ChatSessionMetadata(**self._minimal())
        assert isinstance(meta.created_at, datetime)

    def test_adk_app_name_default(self) -> None:
        meta = ChatSessionMetadata(**self._minimal())
        assert meta.adk_app_name == "ken_e_chatbot"


# ---------------------------------------------------------------------------
# ChatArtifactIndex
# ---------------------------------------------------------------------------


class TestChatArtifactIndex:
    def _minimal(self, **overrides: object) -> dict:
        base: dict = {
            "artifact_id": "abc123",
            "session_id": "sess_001",
            "filename": "report.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1024,
            "version": 0,
            "gcs_path": "gs://bucket/app/user/sess/report.pdf/0",
        }
        base.update(overrides)
        return base

    def test_instantiates_with_required_fields(self) -> None:
        artifact = ChatArtifactIndex(**self._minimal())
        assert artifact.artifact_id == "abc123"

    def test_no_creator_field(self) -> None:
        artifact = ChatArtifactIndex(**self._minimal())
        assert not hasattr(artifact, "creator"), (
            "creator must not exist on ChatArtifactIndex — "
            "use created_by_tool: str | None instead"
        )

    def test_created_by_tool_defaults_to_none(self) -> None:
        artifact = ChatArtifactIndex(**self._minimal())
        assert artifact.created_by_tool is None

    def test_created_by_tool_accepts_string(self) -> None:
        artifact = ChatArtifactIndex(**self._minimal(created_by_tool="build_report"))
        assert artifact.created_by_tool == "build_report"

    def test_created_at_defaults_to_now(self) -> None:
        artifact = ChatArtifactIndex(**self._minimal())
        assert isinstance(artifact.created_at, datetime)


# ---------------------------------------------------------------------------
# ChatCategoryDefinition
# ---------------------------------------------------------------------------


class TestChatCategoryDefinition:
    def _minimal(self, **overrides: object) -> dict:
        base: dict = {
            "category_id": "cat_001",
            "user_id": "user_abc",
            "name": "Campaign Planning",
            "name_casefold": "campaign planning",
        }
        base.update(overrides)
        return base

    def test_instantiates_with_required_fields(self) -> None:
        cat = ChatCategoryDefinition(**self._minimal())
        assert cat.category_id == "cat_001"
        assert cat.name_casefold == "campaign planning"

    def test_has_name_casefold_field(self) -> None:
        cat = ChatCategoryDefinition(**self._minimal())
        assert hasattr(cat, "name_casefold")

    def test_name_min_length(self) -> None:
        with pytest.raises(ValueError):
            ChatCategoryDefinition(**self._minimal(name="", name_casefold=""))

    def test_name_max_length(self) -> None:
        with pytest.raises(ValueError):
            ChatCategoryDefinition(
                **self._minimal(name="A" * 65, name_casefold="a" * 65)
            )


# ---------------------------------------------------------------------------
# compute_name_casefold helper
# ---------------------------------------------------------------------------


class TestComputeNameCasefold:
    def test_ascii_lowercase(self) -> None:
        assert compute_name_casefold("hello") == "hello"

    def test_ascii_uppercase(self) -> None:
        assert compute_name_casefold("HELLO") == "hello"

    def test_mixed_case(self) -> None:
        assert compute_name_casefold("Campaign Planning") == "campaign planning"

    def test_strips_whitespace(self) -> None:
        assert compute_name_casefold("  hello  ") == "hello"

    def test_unicode_cafe(self) -> None:
        # casefold is Unicode-safe — handles accented characters
        result = compute_name_casefold("CAFÉ")
        assert result == "café"

    def test_unicode_german_ss(self) -> None:
        # German ß casefolds to ss
        assert compute_name_casefold("STRAßE") == "strasse"


# ---------------------------------------------------------------------------
# TodoItem and TodoList
# ---------------------------------------------------------------------------


class TestTodoItem:
    def test_instantiates(self) -> None:
        item = TodoItem(item_id="i1", text="Do something")
        assert item.item_id == "i1"
        assert item.completed is False
        assert item.completed_at is None


class TestTodoList:
    def test_instantiates(self) -> None:
        todo = TodoList(list_id="l1", title="Phase 1")
        assert todo.list_id == "l1"
        assert todo.items == []
        assert todo.is_current is False

    def test_with_items(self) -> None:
        items = [TodoItem(item_id="i1", text="Step 1")]
        todo = TodoList(list_id="l1", title="Phase 1", items=items, is_current=True)
        assert len(todo.items) == 1
        assert todo.is_current is True


# ---------------------------------------------------------------------------
# ModelContextWindowEntry
# ---------------------------------------------------------------------------


class TestModelContextWindowEntry:
    def test_instantiates(self) -> None:
        entry = ModelContextWindowEntry(
            model_id="gemini-2.5-pro", context_window_max=1_048_576
        )
        assert entry.context_window_max == 1_048_576

    def test_no_pricing_fields(self) -> None:
        entry = ModelContextWindowEntry(
            model_id="gemini-2.5-pro", context_window_max=1_048_576
        )
        assert not hasattr(entry, "cost_per_input_token")
        assert not hasattr(entry, "cost_per_output_token")
        assert not hasattr(entry, "price")


# ---------------------------------------------------------------------------
# ChatStatusDetail
# ---------------------------------------------------------------------------


class TestChatStatusDetail:
    def _make_metadata(self) -> ChatSessionMetadata:
        return ChatSessionMetadata(
            session_id="sess_001",
            user_id="user_abc",
            account_id="acc_xyz",
            organization_id="org_001",
            model_id="gemini-2.5-pro",
            context_window_max=1_048_576,
        )

    def test_instantiates(self) -> None:
        detail = ChatStatusDetail(
            metadata=self._make_metadata(),
            is_agent_running=False,
            context_usage_percent=0.42,
            duration_seconds=3600,
            activity_summary="5 tool calls • 1 compaction • 2 artifacts",
            total_tokens=12345,
        )
        assert detail.is_agent_running is False
        assert detail.context_usage_percent == pytest.approx(0.42)
        assert detail.total_tokens == 12345
        assert detail.artifacts == []
        assert detail.todo_lists == []

    def test_no_cost_fields(self) -> None:
        detail = ChatStatusDetail(
            metadata=self._make_metadata(),
            is_agent_running=False,
            context_usage_percent=0.0,
            duration_seconds=0,
            activity_summary="",
            total_tokens=0,
        )
        assert not hasattr(detail, "cost_usd_display")
        assert not hasattr(detail, "cost_usd_cents")
