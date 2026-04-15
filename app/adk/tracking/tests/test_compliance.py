"""Tests for trace compliance validation.

Mirrors the MER-E validator at
mer_e/adapters/ken_e/trace_instrumentation/validation.py — interface and
field rules must stay in sync.
"""

from __future__ import annotations

from typing import Any

import pytest


def _valid_trace() -> dict[str, Any]:
    """Return a fully compliant trace metadata dict."""
    return {
        "agent_id": "business_researcher",
        "agent_version": "v1.2.3",
        "account_id": "acc_abc123",
        "session_id": "sess_xyz456",
        "experiment_id": "baseline",
        "variant_name": "baseline",
        "environment": "development",
        "rollout_percentage": 100,
    }


class TestRequiredFields:
    """Required fields must be present and valid."""

    def test_valid_trace_is_compliant(self) -> None:
        from app.adk.tracking.compliance import validate_trace_compliance

        result = validate_trace_compliance(_valid_trace())
        assert result.is_compliant is True
        assert result.issues == []

    @pytest.mark.parametrize(
        "missing_field",
        ["agent_id", "agent_version", "account_id", "session_id"],
    )
    def test_missing_required_field_is_non_compliant(self, missing_field: str) -> None:
        from app.adk.tracking.compliance import validate_trace_compliance

        trace = _valid_trace()
        del trace[missing_field]
        result = validate_trace_compliance(trace)

        assert result.is_compliant is False
        assert any(issue.field == missing_field for issue in result.issues)

    def test_empty_string_required_field_fails(self) -> None:
        from app.adk.tracking.compliance import validate_trace_compliance

        trace = _valid_trace()
        trace["agent_id"] = ""
        result = validate_trace_compliance(trace)

        assert result.is_compliant is False
        assert any(issue.field == "agent_id" for issue in result.issues)


class TestSemverValidation:
    """agent_version must match the semver pattern."""

    @pytest.mark.parametrize(
        "version",
        ["v1.0.0", "v1.2.3", "1.0.0", "v1.0.0-beta.1", "v2.1.0-rc1", "v10.20.30"],
    )
    def test_valid_semver_accepted(self, version: str) -> None:
        from app.adk.tracking.compliance import validate_trace_compliance

        trace = _valid_trace()
        trace["agent_version"] = version
        result = validate_trace_compliance(trace)
        assert result.is_compliant is True

    @pytest.mark.parametrize(
        "version",
        ["latest", "v1", "v1.0", "1.0", "abc", "v1.0.0.", "v.1.0.0"],
    )
    def test_invalid_semver_rejected(self, version: str) -> None:
        from app.adk.tracking.compliance import validate_trace_compliance

        trace = _valid_trace()
        trace["agent_version"] = version
        result = validate_trace_compliance(trace)
        assert result.is_compliant is False
        assert any(
            issue.field == "agent_version" for issue in result.issues
        )


class TestFieldsWithDefaults:
    """Fields with defaults produce warnings (not failures) when missing."""

    @pytest.mark.parametrize(
        "field",
        ["experiment_id", "variant_name", "environment", "rollout_percentage"],
    )
    def test_missing_field_with_default_is_warning(self, field: str) -> None:
        from app.adk.tracking.compliance import validate_trace_compliance

        trace = _valid_trace()
        del trace[field]
        result = validate_trace_compliance(trace)

        # Missing defaulted field is a warning, not a failure
        assert result.is_compliant is True
        assert any(warning.field == field for warning in result.warnings)

    def test_invalid_environment_is_failure(self) -> None:
        from app.adk.tracking.compliance import validate_trace_compliance

        trace = _valid_trace()
        trace["environment"] = "qa"  # not in enum
        result = validate_trace_compliance(trace)

        assert result.is_compliant is False
        assert any(issue.field == "environment" for issue in result.issues)

    @pytest.mark.parametrize("bad_value", [-1, 101, 150])
    def test_rollout_percentage_out_of_range_is_failure(self, bad_value: int) -> None:
        from app.adk.tracking.compliance import validate_trace_compliance

        trace = _valid_trace()
        trace["rollout_percentage"] = bad_value
        result = validate_trace_compliance(trace)

        assert result.is_compliant is False
        assert any(issue.field == "rollout_percentage" for issue in result.issues)


class TestOptionalFields:
    """Optional fields are only validated if present."""

    def test_missing_optional_is_compliant(self) -> None:
        from app.adk.tracking.compliance import validate_trace_compliance

        trace = _valid_trace()  # No optional fields set
        result = validate_trace_compliance(trace)
        assert result.is_compliant is True

    @pytest.mark.parametrize("temp", [0.0, 0.5, 1.0, 2.0])
    def test_valid_temperature_accepted(self, temp: float) -> None:
        from app.adk.tracking.compliance import validate_trace_compliance

        trace = _valid_trace()
        trace["temperature"] = temp
        result = validate_trace_compliance(trace)
        assert result.is_compliant is True

    @pytest.mark.parametrize("temp", [-0.1, 2.1, 5.0])
    def test_invalid_temperature_is_failure(self, temp: float) -> None:
        from app.adk.tracking.compliance import validate_trace_compliance

        trace = _valid_trace()
        trace["temperature"] = temp
        result = validate_trace_compliance(trace)
        assert result.is_compliant is False
        assert any(issue.field == "temperature" for issue in result.issues)

    def test_zero_max_output_tokens_is_failure(self) -> None:
        from app.adk.tracking.compliance import validate_trace_compliance

        trace = _valid_trace()
        trace["max_output_tokens"] = 0
        result = validate_trace_compliance(trace)
        assert result.is_compliant is False
        assert any(issue.field == "max_output_tokens" for issue in result.issues)


class TestComplianceReport:
    """generate_compliance_report aggregates results across multiple traces."""

    def test_all_compliant_gives_100_percent(self) -> None:
        from app.adk.tracking.compliance import generate_compliance_report

        report = generate_compliance_report([_valid_trace(), _valid_trace()])
        assert report.total_traces == 2
        assert report.compliant_traces == 2
        assert report.non_compliant_traces == 0
        assert report.compliance_percentage == 100.0

    def test_mixed_compliance_report(self) -> None:
        from app.adk.tracking.compliance import generate_compliance_report

        bad = _valid_trace()
        del bad["agent_id"]
        report = generate_compliance_report([_valid_trace(), bad])
        assert report.total_traces == 2
        assert report.compliant_traces == 1
        assert report.non_compliant_traces == 1
        assert report.compliance_percentage == 50.0

    def test_empty_report(self) -> None:
        from app.adk.tracking.compliance import generate_compliance_report

        report = generate_compliance_report([])
        assert report.total_traces == 0
        assert report.compliance_percentage == 0.0


class TestIssueFieldDetails:
    """AC-3: failure must include the specific field name."""

    def test_missing_agent_id_surfaces_field_name(self) -> None:
        from app.adk.tracking.compliance import validate_trace_compliance

        trace = _valid_trace()
        del trace["agent_id"]
        result = validate_trace_compliance(trace)
        failures_for_agent_id = [
            issue for issue in result.issues if issue.field == "agent_id"
        ]
        assert len(failures_for_agent_id) == 1
        assert failures_for_agent_id[0].message  # non-empty message

    def test_trace_id_is_passed_through(self) -> None:
        from app.adk.tracking.compliance import validate_trace_compliance

        result = validate_trace_compliance(_valid_trace(), trace_id="span_123")
        assert result.trace_id == "span_123"
