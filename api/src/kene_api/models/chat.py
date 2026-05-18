"""Pydantic models for the Chat component (CH-PRD-01 §4.1).

No cost fields anywhere in this module — per-session cost is out of scope
(subscription-level pricing is Billing's concern; Chat shows token counts only).
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def compute_name_casefold(name: str) -> str:
    """Derive the dedup key for a category name (Unicode-safe case folding)."""
    return name.strip().casefold()


class ChatSessionMetadata(BaseModel):
    """Side-table row mirroring an ADK session with product fields.

    Running state (is_agent_running) is derived at read time from
    last_agent_started_at / last_agent_stopped_at — no persistent boolean.
    """

    session_id: str
    user_id: str
    account_id: str
    organization_id: str
    adk_app_name: str = "ken_e_chatbot"

    # Title and category (user-editable)
    title: str | None = None
    category_id: str | None = None

    # Compaction summary (agent-authored, read-only for users)
    latest_summary: str | None = None
    summary_updated_at: datetime | None = None
    compaction_count: int = 0

    # Denormalized search text (casefold of title + category name + summary)
    search_text: str = ""

    # Timestamps
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)
    first_message_at: datetime | None = None
    last_user_message_at: datetime | None = None
    last_agent_message_at: datetime | None = None
    last_viewed_at: datetime | None = None

    # Agent-running state (derived at read time — no persistent boolean)
    last_agent_started_at: datetime | None = None
    last_agent_stopped_at: datetime | None = None

    # Cumulative token aggregates (for display only; no cost math)
    input_tokens_total: int = 0
    output_tokens_total: int = 0
    reasoning_tokens_total: int = 0

    # Context window meter (no pricing; denominator only)
    current_context_tokens: int = 0
    context_window_max: int = 0
    model_id: str = ""

    # Activity counters
    tool_call_count: int = 0
    artifact_count: int = 0
    message_count: int = 0  # +1 per user/model event; system/tool events excluded

    # Sidebar preview
    last_message_preview: str | None = None

    # Auto-title state (generator owned by CH-PRD-04; field declared here)
    # None = not yet attempted; non-None suppresses retry (at most one call per session)
    auto_title_attempted_at: datetime | None = None

    # Lifecycle
    deleted_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def title_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 120:
            raise ValueError("title must be 120 characters or fewer")
        return v


class ChatArtifactIndex(BaseModel):
    """Metadata row for one artifact stored by GcsArtifactService.

    No creator field — created_by_tool=None is reserved for future user uploads
    (no user-upload surface in v1). Non-null in v1 (agent-created artifacts only).
    """

    artifact_id: str  # sha256(session_id|filename|version)[:32]
    session_id: str
    filename: str
    mime_type: str
    size_bytes: int
    version: int  # ADK artifact version (0..N)
    gcs_path: (
        str  # gs://{bucket}/{app_name}/{user_id}/{session_id}/{filename}/{version}
    )
    created_by_tool: str | None = (
        None  # agent tool name; None = user upload (latent v2)
    )
    created_at: datetime = Field(default_factory=_now_utc)


class ChatCategoryDefinition(BaseModel):
    """Per-user category for organising chat sessions.

    name_casefold is the dedup key — must be set by the caller via
    compute_name_casefold(name) before persisting. The composite Firestore
    index (user_id ASC, name_casefold ASC) requires this field materialised
    at write time rather than computed on read.
    """

    category_id: str
    user_id: str
    name: str = Field(min_length=1, max_length=64)
    name_casefold: str  # caller must derive via compute_name_casefold(name)
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)


class TodoItem(BaseModel):
    """Single item in an agent-authored todo list (read-only for users)."""

    item_id: str
    text: str
    completed: bool = False
    completed_at: datetime | None = None


class TodoList(BaseModel):
    """Agent-authored todo list stored in session.state["todo_lists"][list_id].

    Read-only from the user's perspective — agent tools own all writes.
    """

    list_id: str
    title: str
    is_current: bool = False
    created_at: datetime = Field(default_factory=_now_utc)
    items: list[TodoItem] = Field(default_factory=list)


class ChatStatusDetail(BaseModel):
    """Composite response shape for GET /conversations/{id}/status-detail.

    Derived fields are computed server-side so client-side math never diverges.
    No cost fields — Chat shows token counts only.
    """

    metadata: ChatSessionMetadata
    artifacts: list[ChatArtifactIndex] = Field(default_factory=list)
    todo_lists: list[TodoList] = Field(default_factory=list)

    # Derived at the server from timestamps + registry
    is_agent_running: bool
    context_usage_percent: float  # current_context_tokens / context_window_max
    duration_seconds: int  # (last_agent_message_at or updated_at) - created_at
    activity_summary: str  # "12 tool calls • 2 compactions • 3 artifacts"
    total_tokens: int  # input + output + reasoning


class ModelContextWindowEntry(BaseModel):
    """Context-window size for a single model (no pricing fields)."""

    model_id: str
    context_window_max: int  # tokens


# NOTE: `BillableTokenCounts` is intentionally NOT defined here. It is the
# single canonical shape owned by Billing and lives at
# `app/adk/token_accounting.py` alongside the `extract_billable_tokens` helper
# that produces it. Declaring a copy here would create two divergent classes
# (the api copy previously lacked the `ge=0` validation the helper relies on).
# When an api-side consumer needs the type (CH-12 accumulator), that issue
# resolves the app↔api import boundary rather than duplicating the model.


# ---------------------------------------------------------------------------
# Request / response helpers used by multiple endpoints
# ---------------------------------------------------------------------------


class CreateCategoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class AssignCategoryRequest(BaseModel):
    category_id: str | None = None  # None → assign to Uncategorized


class DeleteSessionResponse(BaseModel):
    session_id: str
    deleted_at: datetime
    async_cleanup_task_id: str


class ListTodosResponse(BaseModel):
    todo_lists: list[TodoList]


class ListArtifactsResponseItem(BaseModel):
    artifact_index: ChatArtifactIndex
    signed_url: str
    signed_url_expires_at: datetime


class ListArtifactsResponse(BaseModel):
    items: list[ListArtifactsResponseItem]


# ---------------------------------------------------------------------------
# Internal OIDC bridge — CH-11
# ---------------------------------------------------------------------------


class InternalSideTableUpdateRequest(BaseModel):
    """Request body for POST /api/v1/internal/chat/side-table/update.

    delta values may include {"_increment": n} wire sentinels which the
    handler converts to firestore.Increment before writing.
    """

    session_id: str
    account_id: str
    delta: dict[str, Any]
    idempotency_key: str = Field(min_length=1, max_length=256)
