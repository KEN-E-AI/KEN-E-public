"""``account_id`` validation guard — DM-PRD-02 review follow-up.

``account_id`` is interpolated into Firestore *collection* path segments
(``accounts/{account_id}/{resource}``), so the analytics constructors must
reject anything outside ``^[a-zA-Z0-9_-]{1,128}$`` before building those paths.
"""

from unittest.mock import patch

import pytest

from shared.account_id_utils import validate_account_id

from ..alert_manager import AlertManager
from ..analytics_service import AnalyticsService
from ..async_analytics_queue import AsyncAnalyticsQueue
from ..optimization_analyzer import OptimizationAnalyzer
from ..performance_profiler import PerformanceProfiler

_GOOD_IDS = ["acc_abcdef0123456789", "test_account", "a", "A1_-2b", "a" * 128]
_BAD_IDS = [
    "acc/with/slash",
    "..",
    "../evil",
    "acc with spaces",
    "",
    "a" * 129,
    "acc.dot",
]


@pytest.mark.parametrize("good", _GOOD_IDS)
def test_validate_account_id_accepts_well_formed(good):
    assert validate_account_id(good) == good


@pytest.mark.parametrize("bad", _BAD_IDS)
def test_validate_account_id_rejects_malformed(bad):
    with pytest.raises(ValueError):
        validate_account_id(bad)


@pytest.mark.parametrize(
    "ctor",
    [AnalyticsService, PerformanceProfiler, AsyncAnalyticsQueue, OptimizationAnalyzer],
)
@pytest.mark.parametrize("bad", ["acc/with/slash", "..", ""])
def test_analytics_constructors_reject_bad_account_id(ctor, bad):
    # validate_account_id() runs as the first statement of each __init__, before any
    # Firestore client / background worker is touched, so a bad id fails fast.
    with pytest.raises(ValueError):
        ctor(account_id=bad, project_id="test_project")


@pytest.mark.parametrize("bad", _BAD_IDS)
def test_alert_manager_constructor_rejects_bad_account_id(bad):
    """AlertManager.__init__ calls validate_account_id before any Firestore access."""
    with patch("app.adk.agents.strategy_agent.alert_manager.firestore.Client"):
        with pytest.raises(ValueError):
            AlertManager(account_id=bad, project_id="test_project")
