"""Smoke test: pre-migration fixture validates against MonitoringTopicsResponse model."""

import json
from pathlib import Path

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
    # Real dev account captured from ken-e-dev on 2026-05-12
    assert response.data.account_id == "acc_06c63ab1486a4443a7fc381a484f3b4b"
    assert response.data.organization_id == "org_05430a297f154c1e951d8ee203fe10d5"
    assert len(response.data.industry_keywords) == 15
    assert len(response.data.competitor_entries) == 1
    assert response.data.competitor_entries[0].name == "test corp"
