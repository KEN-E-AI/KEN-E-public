"""
Pytest configuration and fixtures for API tests.
"""

import os
from typing import Generator

import pytest
from unittest.mock import patch


@pytest.fixture(scope="session", autouse=True)
def initialize_prometheus_metrics():
    """
    Initialize Prometheus metrics once per test session.

    This fixture ensures that the oauth_metrics module is imported early
    in the test session, preventing duplicate metric registration errors
    when different tests import the module.
    """
    # Import the metrics module to register all metrics in the Prometheus registry
    from src.kene_api.metrics import oauth_metrics

    # Verify metrics are initialized
    assert oauth_metrics.oauth_auth_attempts is not None

    yield

    # Note: We don't unregister metrics because Prometheus REGISTRY is global
    # and attempting to unregister can cause issues with other tests


@pytest.fixture
def mock_engine_ids() -> Generator[dict, None, None]:
    """
    Fixture to provide test engine IDs for agent routing.

    Yields:
        Dictionary with test engine IDs
    """
    test_ids = {
        "KEN_E_ENGINE_ID": "projects/test/locations/us-central1/reasoningEngines/ken-e-test",
        "STRATEGY_SUPERVISOR_ENGINE_ID": "projects/test/locations/us-central1/reasoningEngines/strategy-test",
        "VERTEX_AI_AGENT_ENGINE_ID": "projects/test/locations/us-central1/reasoningEngines/fallback-test",
    }

    with patch.dict(os.environ, test_ids):
        yield test_ids


@pytest.fixture
def mock_ken_e_engine() -> Generator[dict, None, None]:
    """
    Fixture for KEN-E agent engine ID only.

    Yields:
        Dictionary with KEN-E engine ID
    """
    test_id = {
        "KEN_E_ENGINE_ID": "projects/test/locations/us-central1/reasoningEngines/ken-e-only"
    }

    with patch.dict(os.environ, test_id, clear=True):
        yield test_id


@pytest.fixture
def mock_strategy_engine() -> Generator[dict, None, None]:
    """
    Fixture for Strategy Supervisor agent engine ID only.

    Yields:
        Dictionary with Strategy Supervisor engine ID
    """
    test_id = {
        "STRATEGY_SUPERVISOR_ENGINE_ID": "projects/test/locations/us-central1/reasoningEngines/strategy-only"
    }

    with patch.dict(os.environ, test_id, clear=True):
        yield test_id


@pytest.fixture
def mock_fallback_engine() -> Generator[dict, None, None]:
    """
    Fixture for fallback Vertex AI agent engine ID only.

    Yields:
        Dictionary with fallback engine ID
    """
    test_id = {
        "VERTEX_AI_AGENT_ENGINE_ID": "projects/test/locations/us-central1/reasoningEngines/fallback-only"
    }

    with patch.dict(os.environ, test_id, clear=True):
        yield test_id


@pytest.fixture
def mock_tenant_context() -> dict:
    """
    Fixture for mock tenant context data.

    Returns:
        Dictionary with test tenant context
    """
    return {
        "tenant_id": "test-org-123",
        "account_id": "test-account-456",
        "user_id": "test-user-789",
        "project_id": "test-project",
        "tenant_credentials": "mock-credentials-xyz",
    }


@pytest.fixture
def mock_strategy_parameters() -> dict:
    """
    Fixture for mock strategy generation parameters.

    Returns:
        Dictionary with test strategy parameters
    """
    return {
        "company_name": "Test Company Inc.",
        "industry": "Technology",
        "websites": "https://test.com,https://example.com",
        "customer_regions": "North America,Europe",
        "account_id": "test-account-123",
        "user_id": "test-user-456",
        "annual_ad_budget": 100000.0,
        "project_id": "test-project",
        "uploaded_documents": [
            "gs://test-bucket/doc1.pdf",
            "gs://test-bucket/doc2.pdf",
        ],
    }
