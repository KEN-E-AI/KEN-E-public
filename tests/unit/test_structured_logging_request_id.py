"""Unit tests for request_id injection in StructuredFormatter and log_context."""

import json
import logging

import pytest

from shared.structured_logging import StructuredFormatter, log_context
from shared.structured_logging import _request_id_ctx


@pytest.fixture(autouse=True)
def _clean_request_id_ctx():
    """Ensure contextvars are reset between tests."""
    token = _request_id_ctx.set("")
    yield
    _request_id_ctx.reset(token)


class TestStructuredFormatterRequestId:
    """StructuredFormatter should auto-inject request_id from contextvars."""

    def _make_record(self, message: str = "test") -> logging.LogRecord:
        return logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )

    def test_includes_request_id_when_set(self) -> None:
        _request_id_ctx.set("abc-123")
        formatter = StructuredFormatter()
        record = self._make_record()
        output = json.loads(formatter.format(record))
        assert output["request_id"] == "abc-123"

    def test_omits_request_id_when_empty(self) -> None:
        formatter = StructuredFormatter()
        record = self._make_record()
        output = json.loads(formatter.format(record))
        assert "request_id" not in output

    def test_output_is_valid_json_with_expected_keys(self) -> None:
        _request_id_ctx.set("json-test")
        formatter = StructuredFormatter()
        record = self._make_record("hello world")
        output = json.loads(formatter.format(record))
        assert output["severity"] == "INFO"
        assert output["message"] == "hello world"
        assert "timestamp" in output
        assert "logger" in output


class TestLogContextRequestId:
    """log_context() should auto-populate request_id from contextvars."""

    def test_auto_populates_request_id(self) -> None:
        _request_id_ctx.set("auto-rid-789")
        ctx = log_context(component="test", action="run")
        assert ctx["json_fields"]["request_id"] == "auto-rid-789"

    def test_no_request_id_when_not_set(self) -> None:
        ctx = log_context(component="test", action="run")
        assert "request_id" not in ctx["json_fields"]

    def test_explicit_request_id_overrides_contextvars(self) -> None:
        _request_id_ctx.set("from-ctx")
        ctx = log_context(component="test", request_id="explicit-id")
        assert ctx["json_fields"]["request_id"] == "explicit-id"
