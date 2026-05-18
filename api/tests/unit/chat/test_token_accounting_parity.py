"""Parity anchor for the Chat / Billing token-accounting contract.

This file implements AC-12 from CH-PRD-01 §7:

    `extract_billable_tokens` lands at `app/adk/token_accounting.py`
    under Billing ownership. Parity test passes — identical output on a
    fixed fixture, with CI assertion of identity between Chat and Billing
    test copies.

CANONICAL FIXTURE (do not change without Billing coordination):
  prompt_token_count        = 1250
  candidates_token_count    =  380
  thoughts_token_count      =    0   (non-reasoning model)
  cached_content_token_count=  200

EXPECTED OUTPUT:
  input          = 1250 - 200  = 1050
  output         =              380
  reasoning      =                0
  total_billable = 1050 + 380 + 0 = 1430

When BL-PRD-02 ships, the Billing team will create
`api/tests/unit/billing/test_token_accounting_parity.py` as a symlink or
verbatim copy of this file anchored on the same canonical fixture numbers.
If either copy diverges from these expected counts, both tests fail
simultaneously — divergence is detected at the first CI run after any
helper change.

Owner: Chat (CH-10 / CH-PRD-01) until BL-PRD-02 merges, then Billing.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "app", "adk"))

from token_accounting import BillableTokenCounts, extract_billable_tokens

# ---------------------------------------------------------------------------
# Canonical fixture — must match BL-PRD-02's duplicated copy verbatim.
# ---------------------------------------------------------------------------
_CANONICAL_PROMPT_TOKEN_COUNT = 1250
_CANONICAL_CANDIDATES_TOKEN_COUNT = 380
_CANONICAL_THOUGHTS_TOKEN_COUNT = 0
_CANONICAL_CACHED_TOKEN_COUNT = 200

_EXPECTED = BillableTokenCounts(input=1050, output=380, reasoning=0)
_EXPECTED_TOTAL_BILLABLE = 1430


def _build_canonical_event() -> SimpleNamespace:
    meta = SimpleNamespace(
        prompt_token_count=_CANONICAL_PROMPT_TOKEN_COUNT,
        candidates_token_count=_CANONICAL_CANDIDATES_TOKEN_COUNT,
        thoughts_token_count=_CANONICAL_THOUGHTS_TOKEN_COUNT,
        cached_content_token_count=_CANONICAL_CACHED_TOKEN_COUNT,
    )
    return SimpleNamespace(usage_metadata=meta)


class TestTokenAccountingParity:
    def test_canonical_fixture_produces_expected_counts(self) -> None:
        """The canonical fixture must always produce exactly the expected counts.

        This is the parity contract: BL-PRD-02's duplicated test must produce
        the same result on the same input. Any helper change that alters this
        output trips both the Chat copy and the Billing copy simultaneously.
        """
        result = extract_billable_tokens(_build_canonical_event())
        assert result == _EXPECTED

    def test_total_billable_matches_expected(self) -> None:
        """total_billable on the canonical fixture must equal 1430."""
        result = extract_billable_tokens(_build_canonical_event())
        assert result.total_billable == _EXPECTED_TOTAL_BILLABLE
