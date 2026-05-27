"""Tests for review_pipeline_tracing.py — AH-7 Weave span helpers.

Covers:
- _truncate_output: boundary behaviour at 4096 bytes
- emit_iteration_span: no-op when WEAVE_AVAILABLE=False; exception isolation
- set_pipeline_attrs: exit_reason logic; summary writes; no-op when WEAVE_AVAILABLE=False;
  exception isolation

Patching convention: ``patch.object(tracing_module, ...)`` is used throughout
rather than string-based ``patch("path.to.module.attr")`` to avoid ambiguity
between ``app.adk.agents.utils`` and ``adk.agents.utils`` when the test is
collected with pythonpath="." (workspace root) making the module path start
with ``app.``).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from . import review_pipeline_tracing as _tracing
from .review_pipeline_tracing import (
    WEAVE_AVAILABLE,
    _truncate_output,
    emit_iteration_span,
    set_pipeline_attrs,
)

# ── _truncate_output boundary tests ──────────────────────────────────────────


class TestTruncateOutput:
    """_truncate_output returns str for ≤4096 bytes, dict sentinel for >4096."""

    def test_short_text_passthrough(self):
        """Text well under the limit returns the original string unchanged."""
        assert _truncate_output("hello") == "hello"

    def test_empty_string_passthrough(self):
        assert _truncate_output("") == ""

    def test_exactly_4096_bytes_passthrough(self):
        """Text of exactly 4096 ASCII bytes (= 4096 chars) returns the original string."""
        text = "a" * 4096
        result = _truncate_output(text)
        assert result == text

    def test_4097_bytes_returns_truncated_dict(self):
        """One byte over the limit triggers the truncated-dict sentinel."""
        text = "a" * 4097
        result = _truncate_output(text)
        assert isinstance(result, dict)
        assert result["_truncated"] is True
        assert result["size_bytes"] == 4097
        assert isinstance(result["preview"], str)

    def test_large_text_size_bytes_accurate(self):
        """size_bytes in the sentinel dict reflects the actual encoded byte count."""
        text = "x" * 5000
        result = _truncate_output(text)
        assert result["size_bytes"] == 5000

    def test_preview_is_at_most_4096_bytes_decoded(self):
        """preview must be decodable and represent at most the first 4096 bytes."""
        text = "z" * 10000
        result = _truncate_output(text)
        assert len(result["preview"].encode("utf-8")) <= 4096

    def test_multibyte_utf8_exactly_at_boundary_passthrough(self):
        """2048 two-byte chars (= 4096 bytes) passes through as a string."""
        text = "é" * 2048  # each é is 2 bytes in UTF-8
        result = _truncate_output(text)
        assert result == text

    def test_multibyte_utf8_over_boundary_returns_dict(self):
        """2049 two-byte chars (= 4098 bytes) triggers truncation."""
        text = "é" * 2049
        result = _truncate_output(text)
        assert isinstance(result, dict)
        assert result["_truncated"] is True
        assert result["size_bytes"] == 2049 * 2

    def test_multibyte_utf8_preview_no_unicode_decode_error(self):
        """Truncating at a byte boundary mid-char uses errors='replace'; no UnicodeDecodeError."""
        text = "é" * 2100  # 4200 bytes; boundary falls mid-char for many positions
        result = _truncate_output(text)
        assert isinstance(result, dict)
        # preview is a str; if UnicodeDecodeError were raised it would propagate
        assert isinstance(result["preview"], str)


# ── emit_iteration_span — WEAVE_AVAILABLE=False no-op ────────────────────────


class TestEmitIterationSpanNoWeave:
    """emit_iteration_span is a no-op when WEAVE_AVAILABLE=False."""

    def test_returns_none_when_weave_unavailable(self):
        with patch.object(_tracing, "WEAVE_AVAILABLE", False):
            result = emit_iteration_span(1, "specialist output", "reviewer feedback")
        assert result is None

    def test_does_not_raise_when_weave_unavailable(self):
        with patch.object(_tracing, "WEAVE_AVAILABLE", False):
            emit_iteration_span(1, "output", "feedback")  # must not raise


# ── emit_iteration_span — exception isolation ─────────────────────────────────


class TestEmitIterationSpanExceptionIsolation:
    """Exceptions inside _emit_iteration_span_inner must never propagate to the caller."""

    def test_inner_exception_does_not_propagate(self):
        """If _emit_iteration_span_inner raises, emit_iteration_span swallows the exception."""
        if not WEAVE_AVAILABLE:
            pytest.skip(
                "Weave not available; exception-isolation path is not exercised"
            )

        with patch.object(
            _tracing,
            "_emit_iteration_span_inner",
            side_effect=RuntimeError("Weave connection lost"),
        ):
            emit_iteration_span(1, "output", "feedback")  # must not raise


# ── set_pipeline_attrs — exit_reason logic ───────────────────────────────────


class TestSetPipelineAttrsExitReason:
    """exit_reason is 'approved' when feedback == '', 'max_iterations' otherwise."""

    def _call_and_capture_summary(
        self,
        final_state: dict,
        prefix: str = "p",
    ) -> dict:
        """Call set_pipeline_attrs with a mock Weave call and return the written summary dict."""
        summary: dict = {}
        mock_call = MagicMock()
        mock_call.summary = summary

        mock_weave = MagicMock()
        mock_weave.get_current_call.return_value = mock_call

        with (
            patch.object(_tracing, "WEAVE_AVAILABLE", True),
            patch.object(_tracing, "_weave", mock_weave),
        ):
            set_pipeline_attrs("criteria", final_state, prefix, 1)

        return summary

    def test_empty_feedback_gives_approved(self):
        """final_state[prefix_feedback] == '' → exit_reason == 'approved'."""
        summary = self._call_and_capture_summary({"p_feedback": ""})
        assert summary["exit_reason"] == "approved"

    def test_nonempty_feedback_gives_max_iterations(self):
        """Non-empty feedback → exit_reason == 'max_iterations'."""
        summary = self._call_and_capture_summary(
            {"p_feedback": "criteria not met"}, prefix="p"
        )
        assert summary["exit_reason"] == "max_iterations"

    def test_missing_feedback_key_defaults_to_approved(self):
        """Absent feedback key → get() returns '' → exit_reason == 'approved'."""
        summary = self._call_and_capture_summary({})
        assert summary["exit_reason"] == "approved"


# ── set_pipeline_attrs — summary writes ──────────────────────────────────────


class TestSetPipelineAttrsSummaryWrites:
    """All four AC#9 attributes are written to call.summary."""

    def test_all_four_attributes_written(self):
        """acceptance_criteria, exit_reason, total_iterations, output_key_prefix all present."""
        summary: dict = {}
        mock_call = MagicMock()
        mock_call.summary = summary
        mock_weave = MagicMock()
        mock_weave.get_current_call.return_value = mock_call

        with (
            patch.object(_tracing, "WEAVE_AVAILABLE", True),
            patch.object(_tracing, "_weave", mock_weave),
        ):
            set_pipeline_attrs("my criteria", {"p_feedback": ""}, "p", 2)

        assert summary == {
            "acceptance_criteria": "my criteria",
            "exit_reason": "approved",
            "total_iterations": 2,
            "output_key_prefix": "p",
        }

    def test_total_iterations_reflects_argument(self):
        summary: dict = {}
        mock_call = MagicMock()
        mock_call.summary = summary
        mock_weave = MagicMock()
        mock_weave.get_current_call.return_value = mock_call

        with (
            patch.object(_tracing, "WEAVE_AVAILABLE", True),
            patch.object(_tracing, "_weave", mock_weave),
        ):
            set_pipeline_attrs("crit", {"p_feedback": "reject"}, "p", 3)

        assert summary["total_iterations"] == 3

    def test_prefix_written_to_summary(self):
        summary: dict = {}
        mock_call = MagicMock()
        mock_call.summary = summary
        mock_weave = MagicMock()
        mock_weave.get_current_call.return_value = mock_call

        with (
            patch.object(_tracing, "WEAVE_AVAILABLE", True),
            patch.object(_tracing, "_weave", mock_weave),
        ):
            set_pipeline_attrs("crit", {"news_review_feedback": ""}, "news_review", 1)

        assert summary["output_key_prefix"] == "news_review"


# ── set_pipeline_attrs — WEAVE_AVAILABLE=False no-op ─────────────────────────


class TestSetPipelineAttrsNoWeave:
    """set_pipeline_attrs is a no-op when WEAVE_AVAILABLE=False."""

    def test_returns_none_when_weave_unavailable(self):
        with patch.object(_tracing, "WEAVE_AVAILABLE", False):
            result = set_pipeline_attrs("crit", {"p_feedback": ""}, "p", 1)
        assert result is None

    def test_does_not_raise_when_weave_unavailable(self):
        with patch.object(_tracing, "WEAVE_AVAILABLE", False):
            set_pipeline_attrs("crit", {}, "p", 0)  # must not raise


# ── set_pipeline_attrs — exception isolation ──────────────────────────────────


class TestSetPipelineAttrsExceptionIsolation:
    """Weave exceptions inside set_pipeline_attrs must not propagate to the caller."""

    def test_get_current_call_exception_does_not_propagate(self):
        mock_weave = MagicMock()
        mock_weave.get_current_call.side_effect = RuntimeError("Weave unavailable")

        with (
            patch.object(_tracing, "WEAVE_AVAILABLE", True),
            patch.object(_tracing, "_weave", mock_weave),
        ):
            set_pipeline_attrs("crit", {}, "p", 1)  # must not raise

    def test_summary_write_exception_does_not_propagate(self):
        """If writing to call.summary raises, the exception is swallowed."""
        # Use a MagicMock where .summary raises on attribute access
        mock_call = MagicMock()

        def _raise_on_summary_access(*args, **kwargs):
            raise RuntimeError("summary broken")

        type(mock_call).summary = property(_raise_on_summary_access)

        mock_weave = MagicMock()
        mock_weave.get_current_call.return_value = mock_call

        with (
            patch.object(_tracing, "WEAVE_AVAILABLE", True),
            patch.object(_tracing, "_weave", mock_weave),
        ):
            set_pipeline_attrs("crit", {}, "p", 1)  # must not raise


# ── set_delegate_attrs tests deleted in AH-75 ────────────────────────────────
# set_delegate_attrs wrote AH-67's delegate_to_specialist span attributes
# (specialist_name, cache_hit). Approach 1 deletes the delegate_to_specialist
# function tool entirely — there is no delegate-span to attach attributes to.
# MER-E now extracts per-specialist metrics from the native transfer_to_agent
# sub-agent span tree, which mirrors the deploy-time AH-PRD-02 trace shape.
