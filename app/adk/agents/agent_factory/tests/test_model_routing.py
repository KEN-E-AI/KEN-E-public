"""Unit tests for app.adk.agents.agent_factory.model_routing (AH-86).

Covers:
  - resolve_model_location: full decision-table (T-6 / T-8)
  - apply_model_location_env: os.environ side-effect + return value
  - apply_model_location_env: reads ENVIRONMENT from os.environ when arg omitted
  - apply_model_location_env: idempotent when location unchanged
"""

from __future__ import annotations

import os

import pytest

from app.adk.agents.agent_factory.model_routing import (
    apply_model_location_env,
    resolve_model_location,
)

# ---------------------------------------------------------------------------
# resolve_model_location — table-driven
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("environment", "data_region", "expected"),
    [
        # --- development / dev → global (AH-86 primary requirement) ---
        ("development", None, "global"),
        ("development", "US", "global"),
        ("development", "EU", "global"),
        ("dev", None, "global"),
        ("dev", "EU", "global"),
        # case / whitespace normalisation
        ("Development", None, "global"),
        ("DEVELOPMENT", None, "global"),
        ("  development  ", None, "global"),
        # --- staging → regional ---
        ("staging", None, "us-central1"),
        ("staging", "US", "us-central1"),
        ("staging", "United States", "us-central1"),
        ("staging", "EU", "europe-west1"),
        ("staging", "Europe", "europe-west1"),
        # --- production → regional ---
        ("production", None, "us-central1"),
        ("production", "US", "us-central1"),
        ("production", "EU", "europe-west1"),
        # --- unknown env falls back to regional (safe default, no exception) ---
        ("test", None, "us-central1"),
        ("", None, "us-central1"),
        # --- data_region case/whitespace normalisation ---
        ("staging", "eu", "europe-west1"),
        ("production", "  EU  ", "europe-west1"),
        ("production", "  europe  ", "europe-west1"),
        # --- unknown data_region → US default ---
        ("staging", "APAC", "us-central1"),
        ("staging", "unknown-region", "us-central1"),
    ],
)
def test_resolve_model_location(
    environment: str,
    data_region: str | None,
    expected: str,
) -> None:
    assert resolve_model_location(environment, data_region=data_region) == expected


# ---------------------------------------------------------------------------
# apply_model_location_env — side-effect and return value
# ---------------------------------------------------------------------------


def test_apply_model_location_env_dev_sets_global(monkeypatch: pytest.MonkeyPatch) -> None:
    """Development environment must set GOOGLE_CLOUD_LOCATION=global."""
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    result = apply_model_location_env("development")
    assert result == "global"
    assert os.environ["GOOGLE_CLOUD_LOCATION"] == "global"


def test_apply_model_location_env_staging_sets_regional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Staging environment must set GOOGLE_CLOUD_LOCATION=us-central1."""
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")  # simulate stale value
    result = apply_model_location_env("staging")
    assert result == "us-central1"
    assert os.environ["GOOGLE_CLOUD_LOCATION"] == "us-central1"


def test_apply_model_location_env_reads_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no explicit environment arg, ENVIRONMENT env var is consulted."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    result = apply_model_location_env()
    assert result == "global"
    assert os.environ["GOOGLE_CLOUD_LOCATION"] == "global"


def test_apply_model_location_env_default_is_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ENVIRONMENT env var is absent, defaults to development → global."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    result = apply_model_location_env()
    assert result == "global"
    assert os.environ["GOOGLE_CLOUD_LOCATION"] == "global"


def test_apply_model_location_env_overrides_platform_injected_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Must override a value previously written by the Agent Engine platform."""
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")  # platform-injected
    monkeypatch.setenv("ENVIRONMENT", "development")
    result = apply_model_location_env()
    assert result == "global"
    assert os.environ["GOOGLE_CLOUD_LOCATION"] == "global"


def test_apply_model_location_env_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling apply twice with the same env must leave the value unchanged."""
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")
    first = apply_model_location_env("development")
    second = apply_model_location_env("development")
    assert first == second == "global"
    assert os.environ["GOOGLE_CLOUD_LOCATION"] == "global"


def test_apply_model_location_env_eu_staging(monkeypatch: pytest.MonkeyPatch) -> None:
    """EU data-region in staging should route to europe-west1."""
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    result = apply_model_location_env("staging", data_region="EU")
    assert result == "europe-west1"
    assert os.environ["GOOGLE_CLOUD_LOCATION"] == "europe-west1"
