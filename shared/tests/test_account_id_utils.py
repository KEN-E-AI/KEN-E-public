"""Pure-function tests for ``shared.account_id_utils.validate_account_id``.

Constructor-level tests (AnalyticsService, PerformanceProfiler,
AsyncAnalyticsQueue, AlertManager) live in
``app/adk/agents/strategy_agent/tests/test_account_id_validation.py``.
"""

import pytest

from shared.account_id_utils import validate_account_id

_GOOD_IDS = [
    "acc_abcdef0123456789",
    "test_account",
    "a",
    "A1_-2b",
    "a" * 128,
    "acc_12345678-1234-5678-1234-567812345678",
    "UPPER_CASE",
    "mix-AND_match",
]

_BAD_IDS = [
    "acc/with/slash",
    "..",
    "../evil",
    "acc with spaces",
    "",
    "a" * 129,
    "acc.dot",
    "acc@domain",
    "acc#hash",
    "acc$dollar",
    "acc%percent",
    "acc!bang",
]


@pytest.mark.parametrize("good", _GOOD_IDS)
def test_validate_account_id_accepts_well_formed(good: str) -> None:
    assert validate_account_id(good) == good


@pytest.mark.parametrize("bad", _BAD_IDS)
def test_validate_account_id_rejects_malformed(bad: str) -> None:
    with pytest.raises(ValueError):
        validate_account_id(bad)


def test_validate_account_id_returns_same_string() -> None:
    account_id = "acc_return_value_test"
    assert validate_account_id(account_id) is account_id


def test_validate_account_id_rejects_non_string() -> None:
    with pytest.raises(ValueError):
        validate_account_id(123)  # type: ignore[arg-type]
