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
        # --- staging → global (interim; Review 51) ---
        # gemini-3.1-pro-preview is served on the global endpoint only — not on
        # the us/eu multi-region endpoints — so every env serves from global for
        # now.  Reverts to us/eu per region once the model is multi-region-served.
        ("staging", None, "global"),
        ("staging", "US", "global"),
        ("staging", "United States", "global"),
        ("staging", "EU", "global"),
        ("staging", "Europe", "global"),
        # --- production → global (interim; Review 51) ---
        ("production", None, "global"),
        ("production", "US", "global"),
        ("production", "EU", "global"),
        # --- unknown env → global (interim; safe default, no exception) ---
        ("test", None, "global"),
        ("", None, "global"),
        # --- data_region currently ignored (all → global, interim) ---
        ("staging", "eu", "global"),
        ("production", "  EU  ", "global"),
        ("production", "  europe  ", "global"),
        ("staging", "APAC", "global"),
        ("staging", "unknown-region", "global"),
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


def test_apply_model_location_env_dev_sets_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Development environment must set GOOGLE_CLOUD_LOCATION=global."""
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    result = apply_model_location_env("development")
    assert result == "global"
    assert os.environ["GOOGLE_CLOUD_LOCATION"] == "global"


def test_apply_model_location_env_staging_sets_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Staging must set GOOGLE_CLOUD_LOCATION=global (interim; Review 51).

    gemini-3.1-pro-preview is served on the global endpoint only, so staging
    serves from global until the model reaches the multi-region endpoints.
    """
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")  # simulate stale
    result = apply_model_location_env("staging")
    assert result == "global"
    assert os.environ["GOOGLE_CLOUD_LOCATION"] == "global"


def test_apply_model_location_env_reads_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_apply_model_location_env_prod_sets_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production must override the platform-injected single region with global.

    Interim (Review 51): gemini-3.1-pro-preview is global-only.
    """
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")  # platform-injected
    result = apply_model_location_env("production")
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
    """EU data-region in staging routes to global in the interim (Review 51).

    data_region is currently ignored — all environments serve from global
    until gemini-3.1-pro-preview reaches the eu multi-region endpoint, at which
    point this must revert to ``eu`` (the REVERT TRIGGER in model_routing.py).
    """
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    result = apply_model_location_env("staging", data_region="EU")
    assert result == "global"
    assert os.environ["GOOGLE_CLOUD_LOCATION"] == "global"
