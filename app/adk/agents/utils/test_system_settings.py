"""Unit tests for :mod:`app.adk.agents.utils.system_settings` (AH-93).

Hermetic — no real Firestore I/O.  Every external call is mocked or stubbed.

Covers:
* ``harness_default_reviewer_model`` resolution and TTL caching.
* Stale-on-error semantics (mirrors :mod:`config_cache` behaviour).
* ``clear_system_settings_cache_for_tests`` drops the cached entry.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# autouse fixture — clean state between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_cache() -> Any:
    """Each test starts (and ends) with a clean system-settings cache."""
    from app.adk.agents.utils.system_settings import (
        clear_system_settings_cache_for_tests,
    )

    clear_system_settings_cache_for_tests()
    yield
    clear_system_settings_cache_for_tests()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snap(*, exists: bool, value: Any = None) -> MagicMock:
    """Minimal Firestore DocumentSnapshot stand-in."""
    snap = MagicMock()
    snap.exists = exists
    if exists:
        snap.to_dict.return_value = (
            {"default_reviewer_model": value} if value is not None else {}
        )
    else:
        snap.to_dict.return_value = None
    return snap


def _make_fake_db(snap: MagicMock) -> MagicMock:
    """Minimal Firestore client stand-in wired to return *snap*."""
    db = MagicMock()
    db.collection.return_value.document.return_value.get.return_value = snap
    return db


def _patch_firestore(snap: MagicMock) -> Any:
    """Patch ``google.cloud.firestore.Client`` to return *snap* on ``.get()``."""
    fake_db = _make_fake_db(snap)
    return patch(
        "app.adk.agents.utils.system_settings._firestore.Client",
        return_value=fake_db,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHarnessDefaultReviewerModel:
    def test_returns_none_when_doc_does_not_exist(self) -> None:
        """AC1: returns ``None`` when the Firestore document does not exist."""
        from app.adk.agents.utils import system_settings as ss

        snap = _make_snap(exists=False)
        with _patch_firestore(snap):
            result = ss.harness_default_reviewer_model()

        assert result is None

    def test_returns_stored_model_string(self) -> None:
        """AC2: returns the stored string when the doc has ``default_reviewer_model``."""
        from app.adk.agents.utils import system_settings as ss

        snap = _make_snap(exists=True, value="gemini-2.5-flash")
        with _patch_firestore(snap):
            result = ss.harness_default_reviewer_model()

        assert result == "gemini-2.5-flash"

    def test_returns_none_when_field_absent(self) -> None:
        """Doc exists but field is absent → returns ``None``."""
        from app.adk.agents.utils import system_settings as ss

        # _make_snap(exists=True, value=None) writes an empty dict.
        snap = _make_snap(exists=True, value=None)
        with _patch_firestore(snap):
            result = ss.harness_default_reviewer_model()

        assert result is None

    def test_returns_none_when_field_whitespace_only(self) -> None:
        """Whitespace-only ``default_reviewer_model`` value is treated as absent."""
        from app.adk.agents.utils import system_settings as ss

        snap = _make_snap(exists=True, value="   ")
        with _patch_firestore(snap):
            result = ss.harness_default_reviewer_model()

        assert result is None

    def test_second_call_within_ttl_does_not_re_issue_firestore_io(self) -> None:
        """AC3: within TTL, a second call does not re-issue Firestore I/O."""
        from app.adk.agents.utils import system_settings as ss

        snap = _make_snap(exists=True, value="gemini-2.5-flash")
        fake_db = _make_fake_db(snap)

        with patch(
            "app.adk.agents.utils.system_settings._firestore.Client",
            return_value=fake_db,
        ):
            r1 = ss.harness_default_reviewer_model(ttl_seconds=60)
            r2 = ss.harness_default_reviewer_model(ttl_seconds=60)

        assert r1 == r2 == "gemini-2.5-flash"
        # Only one Firestore round-trip despite two calls.
        assert fake_db.collection.return_value.document.return_value.get.call_count == 1

    def test_firestore_failure_on_first_call_reraises(self) -> None:
        """AC4a: on first-call Firestore failure (no cache) the exception is re-raised."""
        from app.adk.agents.utils import system_settings as ss

        fake_db = MagicMock()
        fake_db.collection.return_value.document.return_value.get.side_effect = (
            RuntimeError("Firestore unavailable")
        )

        with patch(
            "app.adk.agents.utils.system_settings._firestore.Client",
            return_value=fake_db,
        ):
            with pytest.raises(RuntimeError, match="Firestore unavailable"):
                ss.harness_default_reviewer_model()

    def test_firestore_failure_on_refresh_returns_stale_value(self) -> None:
        """AC4b: after a successful first call, a refresh failure returns the stale value."""
        from app.adk.agents.utils import system_settings as ss

        good_snap = _make_snap(exists=True, value="gemini-2.5-flash")
        good_db = _make_fake_db(good_snap)

        # Populate the cache.
        with patch(
            "app.adk.agents.utils.system_settings._firestore.Client",
            return_value=good_db,
        ):
            first = ss.harness_default_reviewer_model(ttl_seconds=0)  # TTL=0 → immediately expired

        assert first == "gemini-2.5-flash"

        # Force a second read that now raises.
        bad_db = MagicMock()
        bad_db.collection.return_value.document.return_value.get.side_effect = (
            RuntimeError("Firestore gone")
        )
        with patch(
            "app.adk.agents.utils.system_settings._firestore.Client",
            return_value=bad_db,
        ):
            stale = ss.harness_default_reviewer_model(ttl_seconds=0)

        assert stale == "gemini-2.5-flash"  # stale value returned, no exception

    def test_clear_cache_drops_cached_entry(self) -> None:
        """AC5: after clear, next call re-issues Firestore I/O."""
        from app.adk.agents.utils import system_settings as ss

        snap = _make_snap(exists=True, value="gemini-2.5-flash")
        fake_db = _make_fake_db(snap)

        with patch(
            "app.adk.agents.utils.system_settings._firestore.Client",
            return_value=fake_db,
        ):
            ss.harness_default_reviewer_model(ttl_seconds=60)  # prime cache
            ss.clear_system_settings_cache_for_tests()
            ss.harness_default_reviewer_model(ttl_seconds=60)  # should re-query

        # Two Firestore calls: one before clear, one after.
        assert fake_db.collection.return_value.document.return_value.get.call_count == 2

    def test_project_id_uses_env_var(self) -> None:
        """``GOOGLE_CLOUD_PROJECT_ID`` env var overrides the dev fallback."""
        from app.adk.agents.utils import system_settings as ss

        snap = _make_snap(exists=False)
        captured_projects: list[str] = []

        def _fake_client(project: str) -> MagicMock:
            captured_projects.append(project)
            return _make_fake_db(snap)

        with patch(
            "app.adk.agents.utils.system_settings._firestore.Client",
            side_effect=_fake_client,
        ), patch.dict(
            "os.environ", {"GOOGLE_CLOUD_PROJECT_ID": "ken-e-staging"}
        ):
            ss.harness_default_reviewer_model()

        assert captured_projects == ["ken-e-staging"]

    def test_project_id_fallback_to_dev(self) -> None:
        """Without ``GOOGLE_CLOUD_PROJECT_ID``, project falls back to ``"ken-e-dev"``."""
        import os

        from app.adk.agents.utils import system_settings as ss

        snap = _make_snap(exists=False)
        captured_projects: list[str] = []

        def _fake_client(project: str) -> MagicMock:
            captured_projects.append(project)
            return _make_fake_db(snap)

        # Remove the env var if it happens to be set.
        env_without_var = {k: v for k, v in os.environ.items() if k != "GOOGLE_CLOUD_PROJECT_ID"}

        with patch(
            "app.adk.agents.utils.system_settings._firestore.Client",
            side_effect=_fake_client,
        ), patch.dict("os.environ", env_without_var, clear=True):
            ss.harness_default_reviewer_model()

        assert captured_projects == ["ken-e-dev"]
