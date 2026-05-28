"""Trace compliance validation for KEN-E agent traces.

Mirrors the MER-E validator at
``mer_e/adapters/ken_e/trace_instrumentation/validation.py``. The interface,
field specifications, and rule semantics are kept in sync so that any trace
that passes KEN-E's compliance check will also pass MER-E's ingest validator.

Usage::

    from app.adk.tracking.compliance import validate_trace_compliance

    result = validate_trace_compliance(trace_metadata_dict)
    if not result.is_compliant:
        for issue in result.issues:
            print(f"{issue.field}: {issue.message}")

See ``docs/trace-structure-spec.md`` §11 for the authoritative contract.
"""

from __future__ import annotations

import re
from collections import Counter
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class IssueType(str, Enum):
    """Categories of compliance issues."""

    MISSING_FIELD = "missing_field"
    INVALID_VALUE = "invalid_value"
    INVALID_TYPE = "invalid_type"
    INVALID_FORMAT = "invalid_format"


class TraceComplianceIssue(BaseModel):
    """A single compliance issue found in a trace."""

    field: str = Field(..., description="Name of the field with the issue")
    issue_type: IssueType = Field(..., description="Category of the issue")
    message: str = Field(..., description="Human-readable description of the issue")
    expected: str | None = Field(default=None, description="Expected value or format")
    actual: str | None = Field(default=None, description="Actual value found")

    def __str__(self) -> str:
        return f"[{self.issue_type.value}] {self.field}: {self.message}"


class TraceComplianceResult(BaseModel):
    """Result of validating a single trace."""

    is_compliant: bool = Field(
        ..., description="True if the trace meets all requirements"
    )
    issues: list[TraceComplianceIssue] = Field(
        default_factory=list, description="Compliance failures"
    )
    trace_id: str | None = Field(default=None, description="Optional trace identifier")
    warnings: list[TraceComplianceIssue] = Field(
        default_factory=list,
        description="Non-critical issues (missing defaulted fields)",
    )

    @property
    def error_count(self) -> int:
        return len(self.issues)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


class TraceComplianceReport(BaseModel):
    """Aggregated compliance report across multiple traces."""

    total_traces: int
    compliant_traces: int
    non_compliant_traces: int
    compliance_percentage: float
    results: list[TraceComplianceResult] = Field(default_factory=list)
    common_issues: list[tuple[str, int]] = Field(default_factory=list)
    field_compliance: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Field specifications — MUST match MER-E's validator
# ---------------------------------------------------------------------------

FieldSpec = dict[str, Any]

REQUIRED_FIELDS: dict[str, FieldSpec] = {
    "agent_id": {"type": str, "min_length": 1},
    "agent_version": {"type": str, "pattern": r"^v?\d+\.\d+\.\d+(-[\w.]+)?$"},
    "account_id": {"type": str, "min_length": 1},
    "session_id": {"type": str, "min_length": 1},
}

FIELDS_WITH_DEFAULTS: dict[str, FieldSpec] = {
    "experiment_id": {"type": str, "default": "baseline"},
    "variant_name": {"type": str, "default": "baseline"},
    "environment": {
        "type": str,
        "valid_values": ["development", "staging", "canary", "production"],
        "default": "production",
    },
    "rollout_percentage": {
        "type": (int, float),
        "min": 0,
        "max": 100,
        "default": 100,
    },
}

OPTIONAL_FIELDS: dict[str, FieldSpec] = {
    "user_id": {"type": str},
    "model_used": {"type": str},
    "temperature": {"type": (int, float), "min": 0.0, "max": 2.0},
    "max_output_tokens": {"type": int, "min": 1},
}


def _validate_field(
    field_name: str,
    value: Any,
    field_spec: FieldSpec,
    is_required: bool = True,
) -> list[TraceComplianceIssue]:
    """Validate a single field against its specification."""
    issues: list[TraceComplianceIssue] = []

    if value is None:
        if is_required:
            issues.append(
                TraceComplianceIssue(
                    field=field_name,
                    issue_type=IssueType.MISSING_FIELD,
                    message=f"Required field '{field_name}' is missing",
                    expected="non-null value",
                    actual="None",
                )
            )
        return issues

    expected_type = field_spec.get("type")
    if expected_type:
        if isinstance(expected_type, tuple):
            type_ok = isinstance(value, expected_type)
            type_names = " or ".join(t.__name__ for t in expected_type)
        else:
            type_ok = isinstance(value, expected_type)
            type_names = expected_type.__name__

        if not type_ok:
            issues.append(
                TraceComplianceIssue(
                    field=field_name,
                    issue_type=IssueType.INVALID_TYPE,
                    message=f"Field '{field_name}' has invalid type",
                    expected=type_names,
                    actual=type(value).__name__,
                )
            )
            return issues  # Skip further validation if type is wrong

    if isinstance(value, str):
        min_length = field_spec.get("min_length")
        if min_length is not None and len(value) < min_length:
            issues.append(
                TraceComplianceIssue(
                    field=field_name,
                    issue_type=IssueType.INVALID_VALUE,
                    message=f"Field '{field_name}' is too short",
                    expected=f"minimum {min_length} characters",
                    actual=f"{len(value)} characters",
                )
            )

        pattern = field_spec.get("pattern")
        if pattern and not re.match(pattern, value):
            issues.append(
                TraceComplianceIssue(
                    field=field_name,
                    issue_type=IssueType.INVALID_FORMAT,
                    message=f"Field '{field_name}' has invalid format",
                    expected=f"pattern: {pattern}",
                    actual=value,
                )
            )

        valid_values = field_spec.get("valid_values")
        if valid_values and value not in valid_values:
            issues.append(
                TraceComplianceIssue(
                    field=field_name,
                    issue_type=IssueType.INVALID_VALUE,
                    message=f"Field '{field_name}' has invalid value",
                    expected=f"one of: {', '.join(valid_values)}",
                    actual=value,
                )
            )

    if isinstance(value, (int, float)):
        min_val = field_spec.get("min")
        max_val = field_spec.get("max")

        if min_val is not None and value < min_val:
            issues.append(
                TraceComplianceIssue(
                    field=field_name,
                    issue_type=IssueType.INVALID_VALUE,
                    message=f"Field '{field_name}' is below minimum",
                    expected=f">= {min_val}",
                    actual=str(value),
                )
            )

        if max_val is not None and value > max_val:
            issues.append(
                TraceComplianceIssue(
                    field=field_name,
                    issue_type=IssueType.INVALID_VALUE,
                    message=f"Field '{field_name}' exceeds maximum",
                    expected=f"<= {max_val}",
                    actual=str(value),
                )
            )

    return issues


def validate_trace_compliance(
    trace_metadata: dict[str, Any],
    trace_id: str | None = None,
) -> TraceComplianceResult:
    """Validate a trace metadata dict against the KEN-E trace spec.

    Args:
        trace_metadata: Flat dict of trace metadata fields merged from the
            trace's span attributes.
        trace_id: Optional identifier for the trace (passed through to result).

    Returns:
        :class:`TraceComplianceResult` with ``is_compliant``, ``issues``, and
        ``warnings`` populated.

    See ``docs/trace-structure-spec.md`` §11 for field requirements.
    """
    issues: list[TraceComplianceIssue] = []
    warnings: list[TraceComplianceIssue] = []

    for field_name, field_spec in REQUIRED_FIELDS.items():
        value = trace_metadata.get(field_name)
        issues.extend(_validate_field(field_name, value, field_spec, is_required=True))

    for field_name, field_spec in FIELDS_WITH_DEFAULTS.items():
        value = trace_metadata.get(field_name)
        if value is None:
            warnings.append(
                TraceComplianceIssue(
                    field=field_name,
                    issue_type=IssueType.MISSING_FIELD,
                    message=f"Field '{field_name}' is missing, using default",
                    expected="explicit value",
                    actual=f"default: {field_spec.get('default')}",
                )
            )
        else:
            issues.extend(
                _validate_field(field_name, value, field_spec, is_required=False)
            )

    for field_name, field_spec in OPTIONAL_FIELDS.items():
        value = trace_metadata.get(field_name)
        if value is not None:
            issues.extend(
                _validate_field(field_name, value, field_spec, is_required=False)
            )

    return TraceComplianceResult(
        is_compliant=len(issues) == 0,
        issues=issues,
        trace_id=trace_id,
        warnings=warnings,
    )


def generate_compliance_report(
    traces: list[dict[str, Any]],
    trace_ids: list[str | None] | None = None,
) -> TraceComplianceReport:
    """Validate a batch of traces and aggregate the results.

    Args:
        traces: List of trace metadata dicts.
        trace_ids: Optional list of identifiers matching ``traces`` in order.

    Returns:
        :class:`TraceComplianceReport` with total/compliant counts, compliance
        percentage, per-trace results, most common issues, and per-field
        compliance rates for required fields.
    """
    if trace_ids is None:
        trace_ids = [None] * len(traces)

    results: list[TraceComplianceResult] = []
    all_issues: list[str] = []
    field_failures: Counter[str] = Counter()

    for trace, trace_id in zip(traces, trace_ids, strict=True):
        result = validate_trace_compliance(trace, trace_id=trace_id)
        results.append(result)

        for issue in result.issues:
            all_issues.append(f"{issue.field}: {issue.issue_type.value}")
            field_failures[issue.field] += 1

    total_traces = len(traces)
    compliant_traces = sum(1 for r in results if r.is_compliant)
    non_compliant_traces = total_traces - compliant_traces
    compliance_percentage = (
        (compliant_traces / total_traces * 100) if total_traces > 0 else 0.0
    )

    common_issues = Counter(all_issues).most_common(10)

    field_compliance: dict[str, float] = {}
    for field_name in REQUIRED_FIELDS:
        failures = field_failures.get(field_name, 0)
        if total_traces > 0:
            field_compliance[field_name] = (
                (total_traces - failures) / total_traces * 100
            )
        else:
            field_compliance[field_name] = 100.0

    return TraceComplianceReport(
        total_traces=total_traces,
        compliant_traces=compliant_traces,
        non_compliant_traces=non_compliant_traces,
        compliance_percentage=compliance_percentage,
        results=results,
        common_issues=common_issues,
        field_compliance=field_compliance,
    )
