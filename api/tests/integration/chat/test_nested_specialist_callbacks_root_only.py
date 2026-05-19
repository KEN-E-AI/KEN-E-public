"""Integration tests: root-only guard in ADK chat callbacks (AC-19).

Verifies that chat_before_agent_callback and chat_after_agent_callback
only call _post_side_table_update when invoked at the root agent level
(parent_agent is None). Specialist sub-agents must be silently skipped.

CH-PRD-01 §7 AC-19.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "app"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

import adk.agents.chat_callbacks as cb_module
from adk.agents.chat_callbacks import (
    chat_after_agent_callback,
    chat_before_agent_callback,
)


def _make_ctx(parent_agent=None, session_id="sess_ac19", account_id="acc_ac19", invocation_id="inv_ac19"):
    """Build a minimal mock CallbackContext."""
    session = SimpleNamespace(id=session_id, events=[])
    inv_ctx = SimpleNamespace(
        agent=SimpleNamespace(parent_agent=parent_agent),
        session=session,
        invocation_id=invocation_id,
    )
    return SimpleNamespace(
        _invocation_context=inv_ctx,
        state={"account_id": account_id},
    )


class TestRootOnlyGuardBefore:
    def test_root_agent_posts_started_at(self, monkeypatch):
        """Root agent (parent_agent=None): before_callback posts last_agent_started_at."""
        posted: list[dict] = []
        monkeypatch.setattr(cb_module, "_post_side_table_update", lambda **kw: posted.append(kw))

        result = chat_before_agent_callback(_make_ctx(parent_agent=None))
        assert result is None
        assert len(posted) == 1
        assert "last_agent_started_at" in posted[0]["delta"]
        assert "before-agent:inv_ac19" in posted[0]["idempotency_key"]

    def test_specialist_skips_before(self, monkeypatch):
        """Specialist (parent_agent set): before_callback returns None silently."""
        posted: list[dict] = []
        monkeypatch.setattr(cb_module, "_post_side_table_update", lambda **kw: posted.append(kw))

        parent = SimpleNamespace()
        result = chat_before_agent_callback(_make_ctx(parent_agent=parent))
        assert result is None
        assert posted == []


class TestRootOnlyGuardAfter:
    def test_root_agent_posts_delta(self, monkeypatch):
        """Root agent (parent_agent=None): after_callback posts a full delta."""
        posted: list[dict] = []
        monkeypatch.setattr(cb_module, "_post_side_table_update", lambda **kw: posted.append(kw))

        result = chat_after_agent_callback(_make_ctx(parent_agent=None))
        assert result is None
        assert len(posted) == 1
        delta = posted[0]["delta"]
        # Must include stop timestamp and all counter fields
        assert "last_agent_stopped_at" in delta
        assert "input_tokens_total" in delta
        assert "after-agent:inv_ac19" in posted[0]["idempotency_key"]

    def test_specialist_skips_after(self, monkeypatch):
        """Specialist (parent_agent set): after_callback returns None silently."""
        posted: list[dict] = []
        monkeypatch.setattr(cb_module, "_post_side_table_update", lambda **kw: posted.append(kw))

        parent = SimpleNamespace()
        result = chat_after_agent_callback(_make_ctx(parent_agent=parent))
        assert result is None
        assert posted == []
