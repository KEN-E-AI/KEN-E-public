"""Unit tests for _metadata_to_sidebar_item (CH-30).

Covers:
- 8-state is_agent_running parametrized table (driven by derive_is_agent_running)
- Field-passthrough assertions for every PRD §4.1 field
- category_name always None (CH-PRD-03 deferred)

Run:
    cd api && uv run pytest tests/unit/chat/test_sidebar_item_mapper.py -v
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from src.kene_api.models.chat import ChatSessionMetadata, ChatSessionSidebarItem
from src.kene_api.routers.chat import _metadata_to_sidebar_item

_NOW = datetime(2026, 5, 21, 12, 0, 0, tzinfo=timezone.utc)
_USER_ID = "user_abc"
_ACCOUNT_ID = "acc_1234567890"
_ORG_ID = "org_xyz"


def _make_metadata(
    *,
    session_id: str = "sess_001",
    title: str | None = "Test session",
    category_id: str | None = None,
    last_message_preview: str | None = "Hello there",
    last_agent_message_at: datetime | None = None,
    last_viewed_at: datetime | None = None,
    last_agent_started_at: datetime | None = None,
    last_agent_stopped_at: datetime | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> ChatSessionMetadata:
    return ChatSessionMetadata(
        session_id=session_id,
        user_id=_USER_ID,
        account_id=_ACCOUNT_ID,
        organization_id=_ORG_ID,
        model_id="gemini-2.5-flash",
        title=title,
        category_id=category_id,
        message_count=3,
        last_message_preview=last_message_preview,
        created_at=created_at or _NOW,
        updated_at=updated_at or _NOW,
        last_agent_started_at=last_agent_started_at,
        last_agent_stopped_at=last_agent_stopped_at,
        last_agent_message_at=last_agent_message_at,
        last_viewed_at=last_viewed_at,
    )


# ---------------------------------------------------------------------------
# is_agent_running — 8-state parametrized table
# ---------------------------------------------------------------------------

_THRESHOLD = timedelta(minutes=10)


@pytest.mark.parametrize(
    "started_at,stopped_at,expected",
    [
        # 1. Never started
        (None, None, False),
        # 2. Running fresh (< threshold)
        (_NOW - timedelta(minutes=5), None, True),
        # 3. Stuck (>= threshold, no stop)
        (_NOW - timedelta(minutes=11), None, False),
        # 4. Stopped normally (stopped_at >= started_at)
        (_NOW - timedelta(minutes=5), _NOW - timedelta(minutes=3), False),
        # 5. Stop predates last start — treated as running (< threshold)
        (_NOW - timedelta(minutes=5), _NOW - timedelta(minutes=6), True),
        # 6. Stop predates start AND stuck (>= threshold)
        (_NOW - timedelta(minutes=11), _NOW - timedelta(minutes=13), False),
        # 7. Naive (no tz) started_at — normalised and treated as running
        (
            datetime(2026, 5, 21, 11, 56, 0),  # naive, 4 min before _NOW
            None,
            True,
        ),
        # 8. started_at=None with a stopped_at set — stopped_at is irrelevant
        (None, _NOW - timedelta(minutes=2), False),
    ],
)
def test_is_agent_running_states(
    started_at: datetime | None,
    stopped_at: datetime | None,
    expected: bool,
) -> None:
    """_metadata_to_sidebar_item delegates is_agent_running to derive_is_agent_running."""
    from unittest.mock import patch

    m = _make_metadata(
        last_agent_started_at=started_at,
        last_agent_stopped_at=stopped_at,
    )
    # Freeze 'now' so the stuck-threshold assertions are deterministic.
    # Only mock_dt.now.return_value is needed — derive_is_agent_running never
    # calls datetime(...) directly, so no side_effect on the class is required.
    with patch("src.kene_api.chat.side_table.datetime") as mock_dt:
        mock_dt.now.return_value = _NOW
        result = _metadata_to_sidebar_item(m)

    assert result.is_agent_running is expected


# ---------------------------------------------------------------------------
# Field passthrough
# ---------------------------------------------------------------------------


class TestMetadataToSidebarItemFields:
    def test_returns_sidebar_item_instance(self) -> None:
        assert isinstance(
            _metadata_to_sidebar_item(_make_metadata()), ChatSessionSidebarItem
        )

    def test_session_id_passes_through(self) -> None:
        m = _make_metadata(session_id="sess_xyz")
        assert _metadata_to_sidebar_item(m).session_id == "sess_xyz"

    def test_title_passes_through(self) -> None:
        assert (
            _metadata_to_sidebar_item(_make_metadata(title="My chat")).title
            == "My chat"
        )

    def test_null_title_passes_through(self) -> None:
        assert _metadata_to_sidebar_item(_make_metadata(title=None)).title is None

    def test_category_id_passes_through(self) -> None:
        m = _make_metadata(category_id="cat_abc")
        assert _metadata_to_sidebar_item(m).category_id == "cat_abc"

    def test_null_category_id_passes_through(self) -> None:
        assert _metadata_to_sidebar_item(_make_metadata()).category_id is None

    def test_category_name_always_none(self) -> None:
        """CH-PRD-03 deferred: category_name is never resolved yet."""
        assert _metadata_to_sidebar_item(_make_metadata()).category_name is None

    def test_last_message_preview_passes_through(self) -> None:
        m = _make_metadata(last_message_preview="hi there")
        assert _metadata_to_sidebar_item(m).last_message_preview == "hi there"

    def test_timestamps_pass_through(self) -> None:
        ts = datetime(2026, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
        m = _make_metadata(created_at=ts, updated_at=ts)
        result = _metadata_to_sidebar_item(m)
        assert result.created_at == ts
        assert result.updated_at == ts

    def test_last_agent_message_at_passes_through(self) -> None:
        ts = datetime(2026, 3, 1, 8, 0, 0, tzinfo=timezone.utc)
        m = _make_metadata(last_agent_message_at=ts)
        assert _metadata_to_sidebar_item(m).last_agent_message_at == ts

    def test_null_last_agent_message_at_passes_through(self) -> None:
        assert _metadata_to_sidebar_item(_make_metadata()).last_agent_message_at is None

    def test_last_viewed_at_passes_through(self) -> None:
        ts = datetime(2026, 4, 10, 7, 0, 0, tzinfo=timezone.utc)
        m = _make_metadata(last_viewed_at=ts)
        assert _metadata_to_sidebar_item(m).last_viewed_at == ts

    def test_null_last_viewed_at_passes_through(self) -> None:
        assert _metadata_to_sidebar_item(_make_metadata()).last_viewed_at is None
