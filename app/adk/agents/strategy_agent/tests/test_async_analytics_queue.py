"""Unit tests for AsyncAnalyticsQueue and AsyncAnalyticsAdapter."""

import atexit
from unittest.mock import MagicMock, patch

import pytest

from ..async_analytics_queue import AsyncAnalyticsAdapter, AsyncAnalyticsQueue

# gemini-2.5-flash pricing constants (mirrored from AnalyticsService.MODEL_PRICING)
_FLASH_PROMPT_RATE = 0.075  # USD per 1M prompt tokens
_FLASH_RESP_RATE = 0.30  # USD per 1M response tokens


def _flash_cost(prompt_tokens: int, response_tokens: int) -> float:
    return (
        prompt_tokens * _FLASH_PROMPT_RATE + response_tokens * _FLASH_RESP_RATE
    ) / 1_000_000


@pytest.fixture
def mock_firestore_client():
    """Patch google.cloud.firestore.Client so no real connection is made.

    Uses the same patch target as test_analytics_service.py. Both modules do
    `from google.cloud import firestore` then call `firestore.Client(...)`, so
    patching `google.cloud.firestore.Client` reaches the same class object via
    the shared namespace-package module reference.
    """
    with patch("google.cloud.firestore.Client") as mock_client:
        mock_analytics_db = MagicMock()

        def client_side_effect(project=None, database=None):
            return mock_analytics_db

        mock_client.side_effect = client_side_effect
        yield mock_analytics_db


@pytest.fixture
def queue_no_worker(mock_firestore_client):
    """AsyncAnalyticsQueue with background worker disabled.

    Teardown unregisters the atexit handler that AsyncAnalyticsQueue always
    registers in __init__, preventing handler accumulation across the test session.
    """
    q = AsyncAnalyticsQueue(
        account_id="test_account",
        project_id="test_project",
        enable_background_worker=False,
    )
    q.analytics_db = mock_firestore_client
    yield q
    atexit.unregister(q.shutdown)
    q.shutdown_event.set()


@pytest.fixture
def adapter(mock_firestore_client):
    """AsyncAnalyticsAdapter with background worker patched out.

    Teardown unregisters the atexit handler registered by the inner
    AsyncAnalyticsQueue during AsyncAnalyticsAdapter.__init__.
    """
    with patch.object(AsyncAnalyticsQueue, "_start_worker"):
        a = AsyncAnalyticsAdapter(
            account_id="test_account",
            project_id="test_project",
        )
        a.queue.analytics_db = mock_firestore_client
    yield a
    atexit.unregister(a.queue.shutdown)
    a.queue.shutdown_event.set()


# ---------------------------------------------------------------------------
# Group A — AsyncAnalyticsAdapter rollup via get_execution_summary()
# ---------------------------------------------------------------------------


def test_adapter_single_call_shape(adapter):
    """Single track_agent_execution call produces a correctly-shaped rollup bucket."""
    adapter.track_agent_execution(
        agent_name="agent_a",
        prompt_tokens=1000,
        response_tokens=500,
        model="gemini-2.5-flash",
        execution_time=2.0,
        success=True,
    )

    summary = adapter.get_execution_summary()
    agent_metrics = summary["agent_metrics"]

    assert "agent_a" in agent_metrics
    bucket = agent_metrics["agent_a"]
    assert bucket["executions"] == 1
    assert bucket["total_tokens"] == 1500
    assert bucket["total_time"] == pytest.approx(2.0)
    assert bucket["errors"] == 0
    assert bucket["total_cost"] == pytest.approx(_flash_cost(1000, 500))


def test_adapter_same_agent_accumulation(adapter):
    """Two calls for the same agent accumulate into the same bucket."""
    adapter.track_agent_execution(
        agent_name="agent_a",
        prompt_tokens=1000,
        response_tokens=500,
        model="gemini-2.5-flash",
        execution_time=1.5,
        success=True,
    )
    adapter.track_agent_execution(
        agent_name="agent_a",
        prompt_tokens=2000,
        response_tokens=1000,
        model="gemini-2.5-flash",
        execution_time=3.0,
        success=True,
    )

    summary = adapter.get_execution_summary()
    bucket = summary["agent_metrics"]["agent_a"]

    assert bucket["executions"] == 2
    assert bucket["total_tokens"] == 4500
    assert bucket["total_time"] == pytest.approx(4.5)
    assert bucket["errors"] == 0
    assert bucket["total_cost"] == pytest.approx(
        _flash_cost(1000, 500) + _flash_cost(2000, 1000)
    )


def test_adapter_different_agents_are_isolated(adapter):
    """Calls for different agents land in separate buckets."""
    adapter.track_agent_execution(
        agent_name="agent_a",
        prompt_tokens=500,
        response_tokens=250,
        model="gemini-2.5-flash",
        execution_time=1.0,
        success=True,
    )
    adapter.track_agent_execution(
        agent_name="agent_b",
        prompt_tokens=800,
        response_tokens=400,
        model="gemini-2.5-flash",
        execution_time=2.0,
        success=True,
    )

    summary = adapter.get_execution_summary()
    agent_metrics = summary["agent_metrics"]

    assert set(agent_metrics.keys()) == {"agent_a", "agent_b"}
    assert agent_metrics["agent_a"]["executions"] == 1
    assert agent_metrics["agent_b"]["executions"] == 1
    assert agent_metrics["agent_a"]["total_tokens"] == 750
    assert agent_metrics["agent_b"]["total_tokens"] == 1200


def test_adapter_errors_branch_on_failure(adapter):
    """errors counter increments only when success=False."""
    # Successful call — errors must stay 0
    adapter.track_agent_execution(
        agent_name="agent_a",
        prompt_tokens=100,
        response_tokens=50,
        model="gemini-2.5-flash",
        execution_time=0.5,
        success=True,
    )
    summary_after_success = adapter.get_execution_summary()
    assert summary_after_success["agent_metrics"]["agent_a"]["errors"] == 0

    # Failed call — errors must become 1
    adapter.track_agent_execution(
        agent_name="agent_a",
        prompt_tokens=100,
        response_tokens=50,
        model="gemini-2.5-flash",
        execution_time=0.5,
        success=False,
        error_message="timeout",
    )
    summary_after_failure = adapter.get_execution_summary()
    assert summary_after_failure["agent_metrics"]["agent_a"]["errors"] == 1
    assert summary_after_failure["agent_metrics"]["agent_a"]["executions"] == 2


# ---------------------------------------------------------------------------
# Group B — AsyncAnalyticsQueue._flush_batch Shape B path
# ---------------------------------------------------------------------------


def test_flush_batch_writes_to_shape_b_path(queue_no_worker, mock_firestore_client):
    """_flush_batch writes to accounts/{account_id}/agent_analytics — Shape B path."""
    mock_batch = MagicMock()
    mock_firestore_client.batch.return_value = mock_batch
    mock_collection = MagicMock()
    mock_firestore_client.collection.return_value = mock_collection

    event_1 = {"event_id": "e1", "account_id": "test_account", "data": {}}
    event_2 = {"event_id": "e2", "account_id": "test_account", "data": {}}

    queue_no_worker._flush_batch([event_1, event_2])

    # Path must be the Shape B literal
    mock_firestore_client.collection.assert_called_with(
        "accounts/test_account/agent_analytics"
    )
    # One doc ref + set per event
    assert mock_collection.document.call_count == 2
    assert mock_batch.set.call_count == 2
    # Exactly one commit for the whole batch
    mock_batch.commit.assert_called_once()


def test_flush_batch_empty_is_noop(queue_no_worker, mock_firestore_client):
    """_flush_batch([]) does not call collection() or commit()."""
    queue_no_worker._flush_batch([])

    mock_firestore_client.collection.assert_not_called()
    mock_firestore_client.batch.assert_not_called()
