"""Structured logging utilities for KEN-E application.

This module provides structured logging that integrates with Google Cloud Logging.
It follows GCP best practices for structured logs with JSON payloads.

Usage:
    from shared.structured_logging import get_structured_logger, LogContext

    logger = get_structured_logger(__name__)
    logger.info("Processing request", extra=LogContext(
        component="campaign_context",
        account_id="abc123",
        action="inject",
    ).to_dict())
"""

import contextvars
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, ClassVar

# Re-export a module-level ContextVar so callers outside the API can still set
# a request_id (e.g. background workers).  The API middleware sets the same var.
_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)

# Check if running in Google Cloud environment
_IS_CLOUD_ENVIRONMENT = bool(
    os.getenv("K_SERVICE")  # Cloud Run
    or os.getenv("GAE_APPLICATION")  # App Engine
)


@dataclass
class LogContext:
    """Structured context for log entries.

    Provides consistent metadata fields for Google Cloud Logging integration.
    Fields map to Cloud Logging's special JSON fields where applicable.

    Example:
        >>> ctx = LogContext(
        ...     component="tool_discovery",
        ...     action="search",
        ...     query="analytics",
        ...     results_count=5
        ... )
        >>> logger.info("Search completed", extra=ctx.to_dict())
    """

    # Core identifiers
    component: str = ""  # e.g., "campaign_context", "tool_discovery", "compaction"
    action: str = ""  # e.g., "inject", "search", "trigger", "complete"

    # Request context
    account_id: str = ""
    session_id: str = ""
    request_id: str = ""

    # Operation details
    query: str = ""
    tool_name: str = ""
    category: str = ""

    # Metrics
    token_count: int = 0
    message_count: int = 0
    results_count: int = 0
    duration_ms: float = 0.0

    # Status
    success: bool = True
    error_message: str = ""

    # Additional custom fields
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for logging extra parameter.

        Returns dict with 'json_fields' key for Cloud Logging structured payload.
        """
        data = {k: v for k, v in asdict(self).items() if v or v == 0}

        # Flatten extra into main dict
        if "extra" in data:
            extra = data.pop("extra")
            data.update(extra)

        return {"json_fields": data}


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging in Google Cloud.

    Outputs logs in a format that Cloud Logging automatically parses
    into structured log entries with queryable fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON for Cloud Logging."""
        # Base log entry
        log_entry: dict[str, Any] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "logger": record.name,
        }

        # Add source location for debugging
        log_entry["logging.googleapis.com/sourceLocation"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Auto-inject request_id from contextvars when present
        rid = _request_id_ctx.get()
        if rid:
            log_entry["request_id"] = rid

        # Add structured fields from LogContext
        if hasattr(record, "json_fields"):
            log_entry.update(record.json_fields)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class ConsoleFormatter(logging.Formatter):
    """Human-readable formatter for local development.

    Uses color coding and structured output for easy reading.
    """

    COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET: ClassVar[str] = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors and structured fields."""
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET

        # Base message
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        base = f"{color}{timestamp} [{record.levelname:8}]{reset} {record.name}: {record.getMessage()}"

        # Add structured fields if present
        if hasattr(record, "json_fields") and record.json_fields:
            fields = record.json_fields
            field_str = " | ".join(f"{k}={v}" for k, v in fields.items() if v or v == 0)
            if field_str:
                base += f"\n    {color}>{reset} {field_str}"

        # Add exception if present
        if record.exc_info:
            base += f"\n{self.formatException(record.exc_info)}"

        return base


def configure_logging(
    level: int = logging.INFO,
    force_json: bool = False,
    force_console: bool = False,
) -> None:
    """Configure logging for the application.

    Automatically detects Cloud environment and uses appropriate formatter.

    Args:
        level: Logging level (default INFO)
        force_json: Force JSON output even in local environment
        force_console: Force console output even in Cloud environment
    """
    # Determine formatter based on environment
    use_json = (force_json or _IS_CLOUD_ENVIRONMENT) and not force_console

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    if use_json:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(ConsoleFormatter())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for existing_handler in root_logger.handlers[:]:
        root_logger.removeHandler(existing_handler)

    root_logger.addHandler(handler)

    # Configure ADK logger specifically
    adk_logger = logging.getLogger("google.adk")
    adk_logger.setLevel(level)

    # Log configuration
    root_logger.info(
        "Logging configured",
        extra=LogContext(
            component="logging",
            action="configure",
            extra={
                "level": logging.getLevelName(level),
                "formatter": "json" if use_json else "console",
                "environment": "cloud" if _IS_CLOUD_ENVIRONMENT else "local",
            },
        ).to_dict(),
    )


def get_structured_logger(name: str) -> logging.Logger:
    """Get a logger configured for structured logging.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Convenience function for creating log context
def log_context(**kwargs: Any) -> dict[str, Any]:
    """Create log context dict for the extra parameter.

    Shorthand for LogContext(...).to_dict().  Automatically fills ``request_id``
    from the current contextvars value when not explicitly provided.

    Example:
        >>> logger.info("Message", extra=log_context(component="test", action="run"))
    """
    if "request_id" not in kwargs or not kwargs["request_id"]:
        rid = get_request_id()
        if rid:
            kwargs["request_id"] = rid
    return LogContext(**kwargs).to_dict()


def get_request_id() -> str:
    """Return the current request's correlation ID (empty string if not set).

    Works both inside the API (via ``RequestIdMiddleware``) and in any context
    where ``_request_id_ctx`` has been set.
    """
    return _request_id_ctx.get()
