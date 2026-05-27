"""Usage tracking module for KEN-E tool execution analytics.

This module provides:
- UsageTracker: Records tool execution events
- Usage aggregation for reporting
- emit_sandbox_pool_span: Weave span helper for SandboxPool emit sites
"""

from .sandbox_pool_spans import emit_sandbox_pool_span
from .usage import (
    ExecutionStatus,
    UsageAggregation,
    UsageEvent,
    UsageTracker,
    get_usage_tracker,
)

__all__ = [
    "ExecutionStatus",
    "UsageAggregation",
    "UsageEvent",
    "UsageTracker",
    "emit_sandbox_pool_span",
    "get_usage_tracker",
]
