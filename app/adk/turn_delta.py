"""TurnDelta: typed wire model for per-turn side-table updates.

Bridges the ADK callback layer (app/adk/) and the internal FastAPI endpoint
(api/src/kene_api/chat/side_table_handlers.py).

Wire format (JSON over HTTP):
  datetime fields   → {"_isoformat": "..."}
  int counter fields → {"_increment": n}
  str fields         → plain string

Firestore-native format (.to_firestore_delta()):
  datetime fields   → datetime objects
  int counter fields → firestore.Increment(n)
  str fields         → plain string

CH-PRD-01 §5.1 / AC-3.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class TurnDelta(BaseModel):
    """Per-turn session-metadata delta: typed wire model.

    Use model_dump(mode="json", by_alias=True, exclude_none=True) to obtain
    the HTTP wire dict, or .to_firestore_delta() for Firestore-native types.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    # Timestamp fields — all required; derived from the same `now` snapshot.
    last_agent_stopped_at: datetime
    updated_at: datetime
    last_agent_message_at: datetime

    # Counter fields — always incremented, never overwritten.
    # Aliases align with the Firestore / wire field names.
    input_tokens_increment: int = Field(default=0, ge=0, alias="input_tokens_total")
    output_tokens_increment: int = Field(default=0, ge=0, alias="output_tokens_total")
    reasoning_tokens_increment: int = Field(default=0, ge=0, alias="reasoning_tokens_total")
    tool_call_count: int = Field(default=0, ge=0)
    message_count: int = Field(default=0, ge=0)
    current_context_tokens: int = Field(default=0, ge=0)

    # Scalar field — overwritten each turn (not an increment).
    last_message_preview: str = ""

    # Optional compaction fields written by SessionTurnAccumulator (CH-12).
    # Absent from normal turns; only present when a compaction happened.
    latest_summary: str | None = None
    summary_updated_at: datetime | None = None
    compaction_count: int | None = Field(default=None, ge=0)

    # ------------------------------------------------------------------
    # Field validators — parse wire sentinels into Python-native types
    # before Pydantic applies the declared field type.
    # ------------------------------------------------------------------

    @field_validator(
        "last_agent_stopped_at",
        "updated_at",
        "last_agent_message_at",
        "summary_updated_at",
        mode="before",
    )
    @classmethod
    def _parse_datetime_sentinel(cls, v: Any) -> Any:
        if isinstance(v, dict) and set(v.keys()) == {"_isoformat"}:
            return datetime.fromisoformat(v["_isoformat"])
        return v

    @field_validator(
        "input_tokens_increment",
        "output_tokens_increment",
        "reasoning_tokens_increment",
        "tool_call_count",
        "message_count",
        "current_context_tokens",
        "compaction_count",
        mode="before",
    )
    @classmethod
    def _parse_increment_sentinel(cls, v: Any) -> Any:
        if isinstance(v, dict) and set(v.keys()) == {"_increment"}:
            return v["_increment"]
        return v

    # ------------------------------------------------------------------
    # Field serializers — emit wire sentinels during JSON serialisation.
    # `when_used="json"` means Python-mode model_dump() returns native
    # Python types; only JSON-mode serialisation emits the sentinel dicts.
    # ------------------------------------------------------------------

    @field_serializer(
        "last_agent_stopped_at",
        "updated_at",
        "last_agent_message_at",
        when_used="json",
    )
    def _serialize_datetime(self, dt: datetime) -> dict[str, str]:
        return {"_isoformat": dt.isoformat()}

    @field_serializer("summary_updated_at", when_used="json")
    def _serialize_optional_datetime(self, dt: datetime | None) -> dict[str, str] | None:
        if dt is None:
            return None
        return {"_isoformat": dt.isoformat()}

    @field_serializer(
        "input_tokens_increment",
        "output_tokens_increment",
        "reasoning_tokens_increment",
        "tool_call_count",
        "message_count",
        "current_context_tokens",
        when_used="json",
    )
    def _serialize_increment(self, n: int) -> dict[str, int]:
        return {"_increment": n}

    @field_serializer("compaction_count", when_used="json")
    def _serialize_optional_increment(self, n: int | None) -> dict[str, int] | None:
        if n is None:
            return None
        return {"_increment": n}

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def to_wire_dict(self) -> dict[str, Any]:
        """Return the HTTP wire format dict (sentinel-encoded, alias-keyed)."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)

    def to_firestore_delta(self) -> dict[str, Any]:
        """Return a Firestore-native delta dict.

        Counter fields become firestore.Increment(n); timestamp fields are
        datetime objects. Absent optional fields are excluded.
        """
        from google.cloud import firestore

        delta: dict[str, Any] = {
            "last_agent_stopped_at": self.last_agent_stopped_at,
            "updated_at": self.updated_at,
            "last_agent_message_at": self.last_agent_message_at,
            "input_tokens_total": firestore.Increment(self.input_tokens_increment),
            "output_tokens_total": firestore.Increment(self.output_tokens_increment),
            "reasoning_tokens_total": firestore.Increment(self.reasoning_tokens_increment),
            "tool_call_count": firestore.Increment(self.tool_call_count),
            "message_count": firestore.Increment(self.message_count),
            "current_context_tokens": firestore.Increment(self.current_context_tokens),
            "last_message_preview": self.last_message_preview,
        }
        if self.latest_summary is not None:
            delta["latest_summary"] = self.latest_summary
        if self.summary_updated_at is not None:
            delta["summary_updated_at"] = self.summary_updated_at
        if self.compaction_count is not None:
            delta["compaction_count"] = firestore.Increment(self.compaction_count)
        return delta
