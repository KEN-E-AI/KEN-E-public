"""Dedicated test for the message_count increment rule — AC-9.

CH-PRD-01 §7 AC-9: Unit test constructs events with authors 'user', 'model',
'system', 'tool' in a mixed sequence; asserts `message_count` increments
ONLY on 'user'/'model'.

The rule is case-sensitive exact-string match.  'User', 'USER', 'assistant',
'agent', and '' all return 0.

References: CH-PRD-01 §7 AC-9, §5.2 (message_count_delta rule).
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

from google.cloud.firestore_v1.transforms import Increment

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from kene_api.chat.accumulator import SessionTurnAccumulator


def _author_event(author: str) -> SimpleNamespace:
    return SimpleNamespace(
        usage_metadata=None,
        type=None,
        author=author,
        is_final_text=False,
        text="",
        content=None,
    )


class TestMessageCountRule:
    def test_full_mixed_sequence_counts_four(self) -> None:
        """user → model → system → tool → user → model → tool → system → model.

        Expected delta = 5 (three 'model' events + two 'user' events).
        """
        a = SessionTurnAccumulator()
        sequence = ["user", "model", "system", "tool", "user", "model", "tool", "system", "model"]
        for author in sequence:
            a.add_event(_author_event(author))
        delta = a.build_delta()
        assert isinstance(delta["message_count"], Increment)
        assert delta["message_count"].value == 5

    def test_system_only_sequence_count_zero(self) -> None:
        a = SessionTurnAccumulator()
        for _ in range(3):
            a.add_event(_author_event("system"))
        assert a.build_delta()["message_count"].value == 0

    def test_tool_only_sequence_count_zero(self) -> None:
        a = SessionTurnAccumulator()
        for _ in range(5):
            a.add_event(_author_event("tool"))
        assert a.build_delta()["message_count"].value == 0

    def test_unknown_author_count_zero(self) -> None:
        a = SessionTurnAccumulator()
        for author in ("agent", "root", "assistant", "bot"):
            a.add_event(_author_event(author))
        assert a.build_delta()["message_count"].value == 0

    def test_case_sensitivity_upper_u_is_not_counted(self) -> None:
        """'User' with capital U must NOT count — exact match required."""
        a = SessionTurnAccumulator()
        a.add_event(_author_event("User"))
        assert a.build_delta()["message_count"].value == 0

    def test_case_sensitivity_upper_m_is_not_counted(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_author_event("Model"))
        assert a.build_delta()["message_count"].value == 0

    def test_empty_author_not_counted(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_author_event(""))
        assert a.build_delta()["message_count"].value == 0

    def test_none_author_not_counted(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_author_event(None))  # type: ignore[arg-type]
        assert a.build_delta()["message_count"].value == 0

    def test_user_only_counts(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_author_event("user"))
        a.add_event(_author_event("user"))
        assert a.build_delta()["message_count"].value == 2

    def test_model_only_counts(self) -> None:
        a = SessionTurnAccumulator()
        a.add_event(_author_event("model"))
        assert a.build_delta()["message_count"].value == 1
