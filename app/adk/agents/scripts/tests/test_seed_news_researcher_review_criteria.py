"""Tests for seed_news_researcher_review_criteria.py (AH-87 / review-loop criteria seed).

Coverage map:
  (a) REVIEW_CRITERIA_TEXT constant matches the exact string from the issue.
  (b) main() writes exactly one key (default_acceptance_criteria) with the correct value.
  (c) Project-ID guard rejects non-dev project IDs with sys.exit(2).
  (d) Missing doc causes main() to return 1 without writing.
  (e) --dry-run returns 0 without constructing a Firestore client.
"""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import patch

import pytest

from app.adk.agents.scripts import seed_news_researcher_review_criteria as script
from app.adk.agents.scripts.tests._fake_firestore import FakeFirestoreClient

# ---------------------------------------------------------------------------
# (a) REVIEW_CRITERIA_TEXT verbatim match
# ---------------------------------------------------------------------------


def test_review_criteria_text_verbatim() -> None:
    """The constant must match the exact string agreed in the issue."""
    assert script.REVIEW_CRITERIA_TEXT == (
        "Response cites at least 3 distinct sources, each with a publication date;"
        " the summary is ≤ 200 words; no factual claim is made without a cited source."
    )


# ---------------------------------------------------------------------------
# (b) main() writes exactly {default_acceptance_criteria: REVIEW_CRITERIA_TEXT}
# ---------------------------------------------------------------------------


def test_seed_payload_is_single_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() must call upsert_agent_config with a config dict that has
    exactly one key — ``default_acceptance_criteria`` — whose value equals
    REVIEW_CRITERIA_TEXT.  No audit fields, no model/instruction fields."""
    captured: dict[str, Any] = {}

    def _fake_upsert(
        config: dict[str, Any],
        doc_id: str,
        project_id: str,
        *,
        dry_run: bool = False,
        db: Any | None = None,
    ) -> bool:
        captured["config"] = config
        captured["doc_id"] = doc_id
        captured["project_id"] = project_id
        captured["dry_run"] = dry_run
        return True

    # Pre-seed the fake store so the doc-existence guard passes.
    fake_db = FakeFirestoreClient(
        stores={
            "agent_configs": {
                "company_news_agent": {
                    "name": "company_news_agent",
                    "model": "gemini-2.5-pro",
                    "instruction": "existing instruction",
                }
            }
        }
    )

    monkeypatch.setattr(sys, "argv", ["script", "--project-id", "ken-e-dev"])

    with (
        patch(
            "app.adk.agents.scripts.seed_news_researcher_review_criteria.upsert_agent_config",
            side_effect=_fake_upsert,
        ),
        patch("google.cloud.firestore.Client", return_value=fake_db),
    ):
        result = script.main()

    assert result == 0
    assert set(captured["config"].keys()) == {"default_acceptance_criteria"}, (
        f"Expected exactly one key 'default_acceptance_criteria', "
        f"got: {sorted(captured['config'].keys())}"
    )
    assert captured["config"]["default_acceptance_criteria"] == script.REVIEW_CRITERIA_TEXT
    assert captured["doc_id"] == script.TARGET_DOC_ID
    assert captured["project_id"] == script.DEV_PROJECT_ID
    assert captured["dry_run"] is False


# ---------------------------------------------------------------------------
# (c) Project-ID guard — staging and production are rejected
# ---------------------------------------------------------------------------


def test_project_id_guard_rejects_staging(monkeypatch: pytest.MonkeyPatch) -> None:
    """sys.exit(2) must fire before any Firestore interaction."""
    monkeypatch.setattr(sys, "argv", ["script", "--project-id", "ken-e-staging"])

    firestore_constructed = []

    def _never_called(*args: object, **kwargs: object) -> None:
        firestore_constructed.append(True)
        raise AssertionError("google.cloud.firestore.Client must not be called for non-dev projects")

    with (
        patch("google.cloud.firestore.Client", side_effect=_never_called),
        pytest.raises(SystemExit) as exc_info,
    ):
        script.main()

    assert exc_info.value.code == 2
    assert firestore_constructed == [], "Firestore client was unexpectedly constructed"


def test_project_id_guard_rejects_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """sys.exit(2) must fire before any Firestore interaction."""
    monkeypatch.setattr(sys, "argv", ["script", "--project-id", "ken-e-production"])

    firestore_constructed = []

    def _never_called(*args: object, **kwargs: object) -> None:
        firestore_constructed.append(True)
        raise AssertionError("google.cloud.firestore.Client must not be called for non-dev projects")

    with (
        patch("google.cloud.firestore.Client", side_effect=_never_called),
        pytest.raises(SystemExit) as exc_info,
    ):
        script.main()

    assert exc_info.value.code == 2
    assert firestore_constructed == [], "Firestore client was unexpectedly constructed"


# ---------------------------------------------------------------------------
# (d) Missing doc returns 1 without writing
# ---------------------------------------------------------------------------


def test_missing_doc_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the company_news_agent doc does not exist, main() must return 1
    and must NOT call upsert_agent_config."""
    # Empty store — no agent_configs collection, no company_news_agent doc.
    fake_db = FakeFirestoreClient()

    monkeypatch.setattr(sys, "argv", ["script", "--project-id", "ken-e-dev"])

    upsert_calls: list[dict[str, Any]] = []

    def _spy_upsert(
        config: dict[str, Any],
        doc_id: str,
        project_id: str,
        *,
        dry_run: bool = False,
        db: Any | None = None,
    ) -> bool:
        upsert_calls.append({"config": config, "doc_id": doc_id})
        return True

    with (
        patch("google.cloud.firestore.Client", return_value=fake_db),
        patch(
            "app.adk.agents.scripts.seed_news_researcher_review_criteria.upsert_agent_config",
            side_effect=_spy_upsert,
        ),
    ):
        result = script.main()

    assert result == 1, "main() must return 1 when the target doc is absent"
    assert upsert_calls == [], "upsert_agent_config must not be called when pre-check fails"


# ---------------------------------------------------------------------------
# (e) --dry-run returns 0 without touching Firestore
# ---------------------------------------------------------------------------


def test_dry_run_returns_zero_without_firestore(monkeypatch: pytest.MonkeyPatch) -> None:
    """--dry-run must short-circuit before any Firestore Client construction
    and must return 0.  upsert_agent_config must be called with dry_run=True."""
    monkeypatch.setattr(sys, "argv", ["script", "--project-id", "ken-e-dev", "--dry-run"])

    upsert_calls: list[dict[str, Any]] = []

    def _fake_upsert(
        config: dict[str, Any],
        doc_id: str,
        project_id: str,
        *,
        dry_run: bool = False,
        db: Any | None = None,
    ) -> bool:
        upsert_calls.append({"config": config, "dry_run": dry_run, "db": db})
        return True

    with patch(
        "app.adk.agents.scripts.seed_news_researcher_review_criteria.upsert_agent_config",
        side_effect=_fake_upsert,
    ):
        # google.cloud.firestore is imported lazily inside `if not args.dry_run:`,
        # so it is never reached in dry-run mode — no patch needed.
        result = script.main()

    assert result == 0
    assert len(upsert_calls) == 1, "upsert_agent_config must be called exactly once in dry-run"
    call = upsert_calls[0]
    assert call["dry_run"] is True, "upsert_agent_config must receive dry_run=True"
    assert call["db"] is None, "db must be None in dry-run (no Firestore client constructed)"
