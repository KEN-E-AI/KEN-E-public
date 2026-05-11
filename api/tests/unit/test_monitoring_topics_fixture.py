"""Smoke test: pre-migration fixture validates against MonitoringTopicsResponse model."""

import json
from pathlib import Path

import pytest

from src.kene_api.models.monitoring_models import MonitoringTopicsResponse


FIXTURE_PATH = (
    Path(__file__).parent.parent
    / "integration"
    / "fixtures"
    / "monitoring_topics_pre_migration.json"
)


def test_fixture_validates_against_model() -> None:
    """monitoring_topics_pre_migration.json must parse as a valid MonitoringTopicsResponse."""
    raw = json.loads(FIXTURE_PATH.read_text())
    raw.pop("_fixture_meta", None)
    response = MonitoringTopicsResponse.model_validate(raw)
    assert response.success is True
    assert response.data is not None
    assert response.data.account_id == "acc_fixture_001"
    assert len(response.data.customer_concepts) == 1
    assert response.data.customer_concepts[0].keyword == "concept1"
    assert len(response.data.competitor_entries) == 2
