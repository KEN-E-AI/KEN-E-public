"""Usage tracking service for tool execution analytics.

This module provides comprehensive tracking of tool executions for:
- Cost monitoring and billing
- Usage analytics and reporting
- Performance optimization insights
- Audit trail for compliance

Events are stored in Firestore with efficient aggregation queries.
Batched writes improve performance for high-volume scenarios.

Design Reference: Story 1.2.4 - Usage Tracking
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from shared.structured_logging import get_structured_logger, log_context

if TYPE_CHECKING:
    from google.cloud import firestore

logger = get_structured_logger(__name__)


class ExecutionStatus(str, Enum):
    """Status of a tool execution."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMITED = "rate_limited"


class UsageEvent(BaseModel):
    """A single tool usage event.

    Attributes:
        event_id: Unique identifier for this event
        timestamp: When the event occurred
        tool_name: Name of the tool executed
        mcp_server: MCP server that provided the tool (if applicable)
        user_id: User who executed the tool
        account_id: Account context
        organization_id: Optional organization context
        status: Execution status (success, failure, etc.)
        duration_ms: Execution duration in milliseconds
        error_message: Error message if execution failed
        input_tokens: Estimated input tokens used
        output_tokens: Estimated output tokens used
        metadata: Additional metadata for analysis
    """

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tool_name: str
    mcp_server: str | None = None
    user_id: str
    account_id: str
    organization_id: str | None = None
    status: ExecutionStatus
    duration_ms: int | None = None
    error_message: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolBreakdown(BaseModel):
    """Per-tool usage breakdown with success/failure rates."""

    calls: int
    success: int
    failure: int
    success_rate: float
    avg_duration_ms: float | None


class UserBreakdown(BaseModel):
    """Per-user usage breakdown."""

    calls: int
    success: int
    failure: int
    success_rate: float


class UsageAggregation(BaseModel):
    """Aggregated usage statistics for a time period."""

    period_start: datetime
    period_end: datetime
    total_calls: int
    success_count: int
    failure_count: int
    success_rate: float
    avg_duration_ms: float | None
    total_tokens: int
    by_tool: dict[str, ToolBreakdown]
    by_user: dict[str, UserBreakdown]
    by_status: dict[str, int]


class UsageTracker:
    """Tracks tool usage for analytics and billing.

    Features:
    - Event batching for performance
    - Async event recording (non-blocking)
    - Aggregation queries for reporting
    - Firestore integration for persistence

    Usage:
        tracker = get_usage_tracker()
        event_id = await tracker.track_execution(
            tool_name="get_ga4_report",
            user_id="user123",
            account_id="acct456",
            status=ExecutionStatus.SUCCESS,
            duration_ms=150,
        )

    For production, events are stored in Firestore's `tool_usage_events` collection.
    In-memory fallback is provided for environments without Firestore.
    """

    COLLECTION_NAME = "tool_usage_events"
    BATCH_SIZE = 100
    FLUSH_INTERVAL_SECONDS = 30

    def __init__(self, firestore_client: firestore.Client | None = None):
        """Initialize the usage tracker.

        Args:
            firestore_client: Optional Firestore client. If not provided,
                             will attempt lazy initialization from kene_api.
        """
        self._client = firestore_client
        self._batch: list[UsageEvent] = []
        self._batch_lock = asyncio.Lock()
        self._in_memory_store: list[UsageEvent] = []  # Fallback for testing
        self._flush_task: asyncio.Task[None] | None = None
        self._use_firestore = True  # Will be set to False if Firestore unavailable

    @property
    def is_using_firestore(self) -> bool:
        """Whether Firestore backend is active."""
        return self._use_firestore

    @property
    def client(self) -> firestore.Client | None:
        """Lazy-load Firestore client.

        Uses direct google.cloud.firestore with ADC so it works both in the
        local API process and when running on Vertex AI Agent Engine.
        """
        if self._client is None and self._use_firestore:
            try:
                from google.auth import default as auth_default
                from google.cloud import firestore as fs

                credentials, project = auth_default()
                self._client = fs.Client(
                    project=project, credentials=credentials
                )
            except Exception as e:
                logger.warning(
                    f"Firestore unavailable, using in-memory storage: {e}"
                )
                self._use_firestore = False
        return self._client

    async def track_execution(
        self,
        tool_name: str,
        user_id: str,
        account_id: str,
        status: ExecutionStatus,
        mcp_server: str | None = None,
        organization_id: str | None = None,
        duration_ms: int | None = None,
        error_message: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Track a tool execution event.

        Events are batched for performance and flushed periodically or
        when the batch size is reached.

        Args:
            tool_name: Name of the executed tool
            user_id: User who executed the tool
            account_id: Account context
            status: Execution status
            mcp_server: Optional MCP server name
            organization_id: Optional organization context
            duration_ms: Execution duration in milliseconds
            error_message: Error message if failed
            input_tokens: Estimated input tokens
            output_tokens: Estimated output tokens
            metadata: Additional metadata

        Returns:
            Event ID for the tracked event
        """
        event = UsageEvent(
            tool_name=tool_name,
            mcp_server=mcp_server,
            user_id=user_id,
            account_id=account_id,
            organization_id=organization_id,
            status=status,
            duration_ms=duration_ms,
            error_message=error_message,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            metadata=metadata or {},
        )

        # Add to batch
        async with self._batch_lock:
            self._batch.append(event)

            # Flush if batch is full
            if len(self._batch) >= self.BATCH_SIZE:
                await self._flush_batch()

        logger.debug(
            "Tool usage tracked",
            extra=log_context(
                component="usage_tracker",
                action="track",
                tool_name=tool_name,
                extra={
                    "user_id": user_id,
                    "account_id": account_id,
                    "status": status.value,
                    "event_id": event.event_id,
                },
            ),
        )

        return event.event_id

    async def _flush_batch(self) -> None:
        """Flush batched events to storage."""
        if not self._batch:
            return

        events_to_flush = self._batch.copy()
        self._batch = []

        if self.client and self._use_firestore:
            try:
                batch = self.client.batch()
                collection = self.client.collection(self.COLLECTION_NAME)

                for event in events_to_flush:
                    doc_ref = collection.document(event.event_id)
                    batch.set(doc_ref, event.model_dump(mode="json"))

                batch.commit()
                logger.info(f"Flushed {len(events_to_flush)} usage events to Firestore")
            except Exception as e:
                logger.error(f"Failed to flush usage events: {e}")
                # Store in memory as fallback
                self._in_memory_store.extend(events_to_flush)
        else:
            # In-memory storage (testing or Firestore unavailable)
            self._in_memory_store.extend(events_to_flush)

    async def flush(self) -> None:
        """Manually flush any pending events."""
        async with self._batch_lock:
            await self._flush_batch()

    async def start_auto_flush(self) -> None:
        """Start background auto-flush task."""
        if self._flush_task is not None:
            return

        self._flush_task = asyncio.create_task(self._auto_flush_loop())
        logger.info("Usage tracker auto-flush started")

    async def stop_auto_flush(self) -> None:
        """Stop background auto-flush task."""
        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None

        # Final flush
        await self.flush()
        logger.info("Usage tracker auto-flush stopped")

    async def _auto_flush_loop(self) -> None:
        """Background loop for periodic flushing."""
        while True:
            try:
                await asyncio.sleep(self.FLUSH_INTERVAL_SECONDS)
                async with self._batch_lock:
                    await self._flush_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-flush error: {e}")

    async def get_usage_aggregation(
        self,
        start_date: datetime,
        end_date: datetime,
        account_id: str | None = None,
        organization_id: str | None = None,
    ) -> UsageAggregation:
        """Get aggregated usage statistics for a time period.

        Args:
            start_date: Start of period
            end_date: End of period
            account_id: Optional account filter (omit for all accounts)
            organization_id: Optional org filter

        Returns:
            Aggregated usage statistics
        """
        # Ensure pending events are flushed first
        await self.flush()

        events = await self._query_events(
            start_date, end_date, account_id, organization_id
        )

        return self._aggregate_events(events, start_date, end_date)

    async def _query_events(
        self,
        start_date: datetime,
        end_date: datetime,
        account_id: str | None,
        organization_id: str | None,
    ) -> list[dict[str, Any]]:
        """Query events from storage.

        Args:
            start_date: Start of period
            end_date: End of period
            account_id: Optional account filter
            organization_id: Optional org filter

        Returns:
            List of event dictionaries
        """
        if self.client and self._use_firestore:
            try:
                collection = self.client.collection(self.COLLECTION_NAME)

                query = collection.where(
                    "timestamp", ">=", start_date.isoformat()
                )
                query = query.where(
                    "timestamp", "<=", end_date.isoformat()
                )

                if account_id:
                    query = query.where("account_id", "==", account_id)

                if organization_id:
                    query = query.where("organization_id", "==", organization_id)

                docs = query.stream()
                return [doc.to_dict() for doc in docs]
            except Exception as e:
                logger.error(f"Firestore query failed: {e}")

        # Fall back to in-memory
        return self._query_in_memory(start_date, end_date, account_id, organization_id)

    def _query_in_memory(
        self,
        start_date: datetime,
        end_date: datetime,
        account_id: str | None,
        organization_id: str | None,
    ) -> list[dict[str, Any]]:
        """Query events from in-memory store.

        Args:
            start_date: Start of period
            end_date: End of period
            account_id: Optional account filter
            organization_id: Optional org filter

        Returns:
            List of matching event dictionaries
        """
        results = []
        for event in self._in_memory_store:
            if event.timestamp < start_date or event.timestamp > end_date:
                continue
            if account_id and event.account_id != account_id:
                continue
            if organization_id and event.organization_id != organization_id:
                continue
            results.append(event.model_dump(mode="json"))
        return results

    def _aggregate_events(
        self,
        events: list[dict[str, Any]],
        start_date: datetime,
        end_date: datetime,
    ) -> UsageAggregation:
        """Aggregate a list of events into statistics.

        Args:
            events: List of event dictionaries
            start_date: Period start
            end_date: Period end

        Returns:
            Aggregated statistics
        """
        total_calls = len(events)
        success_count = 0
        failure_count = 0
        total_duration = 0
        duration_count = 0
        total_tokens = 0
        by_status: dict[str, int] = {}

        tool_stats: dict[str, dict[str, Any]] = {}
        user_stats: dict[str, dict[str, int]] = {}

        for event in events:
            status = event.get("status", "unknown")
            is_success = status == ExecutionStatus.SUCCESS.value
            by_status[status] = by_status.get(status, 0) + 1

            if is_success:
                success_count += 1
            else:
                failure_count += 1

            dur = event.get("duration_ms")
            if dur:
                total_duration += dur
                duration_count += 1

            tokens = (event.get("input_tokens") or 0) + (event.get("output_tokens") or 0)
            total_tokens += tokens

            tool = event.get("tool_name", "unknown")
            ts = tool_stats.setdefault(
                tool, {"calls": 0, "success": 0, "failure": 0, "dur_total": 0, "dur_count": 0}
            )
            ts["calls"] += 1
            ts["success" if is_success else "failure"] += 1
            if dur:
                ts["dur_total"] += dur
                ts["dur_count"] += 1

            user = event.get("user_id", "unknown")
            us = user_stats.setdefault(user, {"calls": 0, "success": 0, "failure": 0})
            us["calls"] += 1
            us["success" if is_success else "failure"] += 1

        by_tool = {
            name: ToolBreakdown(
                calls=s["calls"],
                success=s["success"],
                failure=s["failure"],
                success_rate=s["success"] / s["calls"] if s["calls"] > 0 else 0.0,
                avg_duration_ms=s["dur_total"] / s["dur_count"] if s["dur_count"] > 0 else None,
            )
            for name, s in tool_stats.items()
        }

        by_user = {
            uid: UserBreakdown(
                calls=s["calls"],
                success=s["success"],
                failure=s["failure"],
                success_rate=s["success"] / s["calls"] if s["calls"] > 0 else 0.0,
            )
            for uid, s in user_stats.items()
        }

        return UsageAggregation(
            period_start=start_date,
            period_end=end_date,
            total_calls=total_calls,
            success_count=success_count,
            failure_count=failure_count,
            success_rate=success_count / total_calls if total_calls > 0 else 0.0,
            avg_duration_ms=(
                total_duration / duration_count if duration_count > 0 else None
            ),
            total_tokens=total_tokens,
            by_tool=by_tool,
            by_user=by_user,
            by_status=by_status,
        )

    def get_pending_count(self) -> int:
        """Get number of events pending flush.

        Returns:
            Number of pending events
        """
        return len(self._batch)

    def get_stored_count(self) -> int:
        """Get number of events in in-memory store (for testing).

        Returns:
            Number of stored events
        """
        return len(self._in_memory_store)


# Singleton instance
_tracker: UsageTracker | None = None


def get_usage_tracker() -> UsageTracker:
    """Get the singleton usage tracker.

    Returns:
        Shared UsageTracker instance
    """
    global _tracker
    if _tracker is None:
        _tracker = UsageTracker()
    return _tracker


async def reset_usage_tracker() -> None:
    """Reset the usage tracker singleton (for testing).

    Stops auto-flush and clears the singleton.
    """
    global _tracker
    if _tracker is not None:
        await _tracker.stop_auto_flush()
        _tracker = None
