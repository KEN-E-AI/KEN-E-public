"""Unit tests for ChatSessionSideTableService (CH-PRD-01 §7 AC-5)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.kene_api.chat.side_table import (
    ChatSessionSideTableService,
    _doc_path,
    recompute_search_text,
)
from src.kene_api.models.chat import ChatSessionMetadata


def _make_db() -> MagicMock:
    return MagicMock()


class TestDocPath:
    def test_shape_b_layout(self) -> None:
        path = _doc_path("acc_123", "sess_abc")
        assert path == "accounts/acc_123/chat_sessions/sess_abc"


class TestCreate:
    def test_returns_metadata_with_correct_fields(self) -> None:
        db = _make_db()
        doc_ref = MagicMock()
        db.document.return_value = doc_ref

        svc = ChatSessionSideTableService(db=db)
        result = svc.create(
            session_id="sess_1",
            user_id="user_1",
            account_id="acc_1",
            organization_id="org_1",
            model_id="gemini-2.5-flash",
        )

        assert result.session_id == "sess_1"
        assert result.user_id == "user_1"
        assert result.account_id == "acc_1"
        assert result.organization_id == "org_1"
        assert result.model_id == "gemini-2.5-flash"

    def test_calls_doc_create(self) -> None:
        db = _make_db()
        doc_ref = MagicMock()
        db.document.return_value = doc_ref

        svc = ChatSessionSideTableService(db=db)
        svc.create(
            session_id="sess_1",
            user_id="user_1",
            account_id="acc_1",
            organization_id="org_1",
            model_id="gemini-2.5-flash",
        )

        db.document.assert_called_once_with("accounts/acc_1/chat_sessions/sess_1")
        doc_ref.create.assert_called_once()

    def test_context_window_max_set_from_registry(self) -> None:
        db = _make_db()
        db.document.return_value = MagicMock()

        svc = ChatSessionSideTableService(db=db)
        result = svc.create(
            session_id="s",
            user_id="u",
            account_id="a",
            organization_id="o",
            model_id="gemini-2.5-flash",
        )

        assert result.context_window_max > 0


class TestGet:
    def test_returns_none_when_not_found(self) -> None:
        db = _make_db()
        snapshot = MagicMock()
        snapshot.exists = False
        db.document.return_value.get.return_value = snapshot

        svc = ChatSessionSideTableService(db=db)
        result = svc.get(account_id="acc_1", session_id="sess_missing")

        assert result is None

    def test_returns_metadata_when_found(self) -> None:
        db = _make_db()
        snapshot = MagicMock()
        snapshot.exists = True
        snapshot.to_dict.return_value = {
            "session_id": "sess_1",
            "user_id": "user_1",
            "account_id": "acc_1",
            "organization_id": "org_1",
            "model_id": "gemini-2.5-flash",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        db.document.return_value.get.return_value = snapshot

        svc = ChatSessionSideTableService(db=db)
        result = svc.get(account_id="acc_1", session_id="sess_1")

        assert result is not None
        assert result.session_id == "sess_1"


class TestUpdateFromDelta:
    def test_calls_firestore_update(self) -> None:
        db = _make_db()
        doc_ref = MagicMock()
        db.document.return_value = doc_ref

        svc = ChatSessionSideTableService(db=db)
        svc.update_from_delta(
            account_id="acc_1",
            session_id="sess_1",
            delta={"message_count": 5, "updated_at": datetime.now(timezone.utc)},
        )

        doc_ref.update.assert_called_once()

    def test_noop_on_empty_delta(self) -> None:
        db = _make_db()
        doc_ref = MagicMock()
        db.document.return_value = doc_ref

        svc = ChatSessionSideTableService(db=db)
        svc.update_from_delta(account_id="acc_1", session_id="sess_1", delta={})

        doc_ref.update.assert_not_called()


class TestTombstone:
    def test_sets_deleted_at_and_updated_at(self) -> None:
        db = _make_db()
        doc_ref = MagicMock()
        db.document.return_value = doc_ref

        svc = ChatSessionSideTableService(db=db)
        deleted_at = svc.tombstone(account_id="acc_1", session_id="sess_1")

        assert isinstance(deleted_at, datetime)
        call_kwargs = doc_ref.update.call_args[0][0]
        assert "deleted_at" in call_kwargs
        assert "updated_at" in call_kwargs
        assert call_kwargs["deleted_at"] == deleted_at


def _base_row(
    *,
    session_id: str = "sess_1",
    user_id: str = "user_1",
    account_id: str = "acc_1",
    organization_id: str = "org_1",
    model_id: str = "gemini-2.5-flash",
    deleted_at: datetime | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "session_id": session_id,
        "user_id": user_id,
        "account_id": account_id,
        "organization_id": organization_id,
        "model_id": model_id,
        "created_at": now,
        "updated_at": now,
        "deleted_at": deleted_at,
    }


def _make_collection_group_result(rows: list[dict]) -> MagicMock:
    """Return a db mock whose collection_group().where().where().limit().get() chain
    yields the given rows as document snapshots."""
    db = MagicMock()

    snapshots = []
    for row in rows:
        snap = MagicMock()
        snap.exists = True
        snap.to_dict.return_value = row
        snapshots.append(snap)

    # Chain: db.collection_group(...).where(...).where(...).limit(...).get()
    query_chain = MagicMock()
    query_chain.where.return_value = query_chain
    query_chain.limit.return_value = query_chain
    query_chain.get.return_value = snapshots
    db.collection_group.return_value = query_chain

    return db


class TestFindSessionForUser:
    def test_returns_metadata_when_found(self) -> None:
        row = _base_row(session_id="sess_1", user_id="user_1")
        db = _make_collection_group_result([row])

        svc = ChatSessionSideTableService(db=db)
        result = svc.find_session_for_user(user_id="user_1", session_id="sess_1")

        assert result is not None
        assert result.session_id == "sess_1"
        assert result.user_id == "user_1"
        assert result.account_id == "acc_1"

    def test_returns_none_when_no_rows(self) -> None:
        db = _make_collection_group_result([])

        svc = ChatSessionSideTableService(db=db)
        result = svc.find_session_for_user(user_id="user_1", session_id="sess_missing")

        assert result is None

    def test_returns_none_for_tombstoned_session(self) -> None:
        row = _base_row(deleted_at=datetime.now(timezone.utc))
        db = _make_collection_group_result([row])

        svc = ChatSessionSideTableService(db=db)
        result = svc.find_session_for_user(user_id="user_1", session_id="sess_1")

        assert result is None

    def test_queries_collection_group_with_correct_filters(self) -> None:
        row = _base_row()
        db = _make_collection_group_result([row])

        svc = ChatSessionSideTableService(db=db)
        svc.find_session_for_user(user_id="user_1", session_id="sess_1")

        db.collection_group.assert_called_once_with("chat_sessions")
        # Two where() calls chained
        assert db.collection_group.return_value.where.call_count == 2

    def test_returns_none_when_snapshot_not_exists(self) -> None:
        snap = MagicMock()
        snap.exists = False

        query_chain = MagicMock()
        query_chain.where.return_value = query_chain
        query_chain.limit.return_value = query_chain
        query_chain.get.return_value = [snap]

        db = MagicMock()
        db.collection_group.return_value = query_chain

        svc = ChatSessionSideTableService(db=db)
        result = svc.find_session_for_user(user_id="user_1", session_id="sess_1")

        assert result is None


# ---------------------------------------------------------------------------
# recompute_search_text — pure-function unit tests
# ---------------------------------------------------------------------------


def _make_metadata(
    *,
    title: str | None = None,
    latest_summary: str | None = None,
    session_id: str = "sess_1",
    user_id: str = "user_1",
    account_id: str = "acc_1",
    organization_id: str = "org_1",
    model_id: str = "gemini-2.5-flash",
) -> ChatSessionMetadata:
    return ChatSessionMetadata(
        session_id=session_id,
        user_id=user_id,
        account_id=account_id,
        organization_id=organization_id,
        model_id=model_id,
        title=title,
        latest_summary=latest_summary,
    )


class TestRecomputeSearchText:
    def test_all_none_returns_empty_string(self) -> None:
        meta = _make_metadata(title=None, latest_summary=None)
        result = recompute_search_text(meta, category_name=None)
        assert result == ""

    def test_title_only_returns_casefolded_title(self) -> None:
        meta = _make_metadata(title="Q3 Campaigns")
        result = recompute_search_text(meta, category_name=None)
        assert result == "q3 campaigns"

    def test_title_and_category_casefolded_with_space(self) -> None:
        meta = _make_metadata(title="Strategy Build")
        result = recompute_search_text(meta, category_name="Paid Media")
        assert result == "strategy build paid media"

    def test_title_category_and_summary_all_included(self) -> None:
        meta = _make_metadata(title="T", latest_summary="Sum")
        result = recompute_search_text(meta, category_name="Cat")
        assert result == "t cat sum"

    def test_category_none_excludes_category(self) -> None:
        meta = _make_metadata(title="Title", latest_summary="Summary")
        result = recompute_search_text(meta, category_name=None)
        assert result == "title summary"

    def test_uses_casefold_not_lower_german_ss(self) -> None:
        # German ß: casefold → "ss", lower → "ß" (no change on some platforms)
        meta = _make_metadata(title="Straße")
        result = recompute_search_text(meta, category_name=None)
        assert result == "strasse"

    def test_uses_casefold_not_lower_turkish_dotted_i(self) -> None:
        # str.casefold() folds İ (U+0130) to "i̇"; lower() leaves it unchanged
        meta = _make_metadata(title="İstanbul")
        result = recompute_search_text(meta, category_name=None)
        assert result == "İstanbul".casefold()

    def test_summary_truncated_to_2048_chars_before_concat(self) -> None:
        long_summary = "x" * 4096
        meta = _make_metadata(title="T", latest_summary=long_summary)
        result = recompute_search_text(meta, category_name=None)
        # "t " prefix + 2048 x's
        assert result == "t " + "x" * 2048

    def test_idempotent_pure_function_no_side_effects(self) -> None:
        meta = _make_metadata(title="Hello", latest_summary="World")
        r1 = recompute_search_text(meta, category_name="Cat")
        r2 = recompute_search_text(meta, category_name="Cat")
        assert r1 == r2

    def test_empty_title_excluded_from_result(self) -> None:
        # title="" is falsy — should not contribute a leading space
        meta = _make_metadata(title="", latest_summary=None)
        result = recompute_search_text(meta, category_name=None)
        assert result == ""

    def test_empty_category_excluded_from_result(self) -> None:
        meta = _make_metadata(title="Title")
        result = recompute_search_text(meta, category_name="")
        assert result == "title"

    def test_raw_dict_all_fields_present(self) -> None:
        result = recompute_search_text(
            {"title": "Q3 Plan", "latest_summary": "draft summary"},
            "Campaign",
        )
        assert result == "q3 plan campaign draft summary"

    def test_raw_dict_none_category_and_missing_summary(self) -> None:
        result = recompute_search_text({"title": "Foo"}, None)
        assert result == "foo"

    def test_raw_dict_all_empty_returns_empty_string(self) -> None:
        result = recompute_search_text({}, None)
        assert result == ""

    def test_raw_dict_order_is_title_category_summary(self) -> None:
        result = recompute_search_text(
            {"title": "TITLE", "latest_summary": "SUMMARY"},
            "CATEGORY",
        )
        assert result == "title category summary"


# ---------------------------------------------------------------------------
# resolve_session_for_user — unit tests (CH-70)
# ---------------------------------------------------------------------------


def _make_adk_session(state: dict) -> MagicMock:
    sess = MagicMock()
    sess.state = state
    return sess


def _make_session_service_mock(
    state: dict | None = None,
    *,
    raises: Exception | None = None,
    return_none: bool = False,
) -> MagicMock:
    svc = MagicMock()
    if raises is not None:
        svc.get_session = AsyncMock(side_effect=raises)
    elif return_none:
        svc.get_session = AsyncMock(return_value=None)
    else:
        session = _make_adk_session(state if state is not None else {"account_id": "acc_1"})
        svc.get_session = AsyncMock(return_value=session)
    return svc


async def _org_resolver_ok(account_id: str) -> str | None:
    return "org_1"


async def _org_resolver_none(account_id: str) -> str | None:
    return None


async def _drain_tasks(coro: Any) -> Any:
    """Run a coroutine and drain all tasks it schedules (e.g., heal tasks).

    resolve_session_for_user fires a heal task via asyncio.create_task. Without
    draining, asyncio.run() cancels the task before it executes and assertions
    on its side-effects (logs, create() calls) would be unreliable.
    """
    result = await coro
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    return result


class TestResolveSessionForUser:
    """Unit tests for ChatSessionSideTableService.resolve_session_for_user (CH-70)."""

    # (a) Side-table hit — returns the existing row, no ADK call.
    def test_fast_path_returns_existing_row(self) -> None:
        row = _base_row(session_id="sess_1", user_id="user_1")
        db = _make_collection_group_result([row])
        svc = ChatSessionSideTableService(db=db)
        session_service = _make_session_service_mock(state={"account_id": "acc_1"})

        result = asyncio.run(
            svc.resolve_session_for_user(
                user_id="user_1",
                session_id="sess_1",
                session_service=session_service,
                app_name="ken_e_chatbot",
            )
        )

        assert result is not None
        assert result.session_id == "sess_1"
        assert result.account_id == "acc_1"
        # ADK get_session should NOT have been called
        session_service.get_session.assert_not_called()

    # (b) Side-table miss + ADK has session → returns synthesised metadata with account_id
    #     AND the heal task calls create() with the resolved org_id.
    def test_fallback_returns_synthesised_metadata_with_account_id(self) -> None:
        db = _make_collection_group_result([])  # side-table miss
        svc = ChatSessionSideTableService(db=db)
        # Stub out create so the heal task doesn't hit Firestore
        svc.create = MagicMock(return_value=MagicMock())
        session_service = _make_session_service_mock(state={"account_id": "acc_adk"})

        result = asyncio.run(
            _drain_tasks(
                svc.resolve_session_for_user(
                    user_id="user_1",
                    session_id="sess_adk",
                    session_service=session_service,
                    app_name="ken_e_chatbot",
                    org_id_resolver=_org_resolver_ok,
                )
            )
        )

        assert result is not None
        assert result.account_id == "acc_adk"
        assert result.session_id == "sess_adk"
        assert result.user_id == "user_1"
        session_service.get_session.assert_called_once()
        # Heal task should have called create() — verifies the heal actually ran
        svc.create.assert_called_once()

    # (c) Side-table miss + ADK has no session → returns None.
    def test_fallback_returns_none_when_adk_has_no_session(self) -> None:
        db = _make_collection_group_result([])
        svc = ChatSessionSideTableService(db=db)
        session_service = _make_session_service_mock(return_none=True)

        result = asyncio.run(
            svc.resolve_session_for_user(
                user_id="user_1",
                session_id="sess_missing",
                session_service=session_service,
                app_name="ken_e_chatbot",
            )
        )

        assert result is None

    # (d) Side-table miss + ADK has session but state lacks account_id → returns None.
    def test_fallback_returns_none_when_state_has_no_account_id(self) -> None:
        db = _make_collection_group_result([])
        svc = ChatSessionSideTableService(db=db)
        session_service = _make_session_service_mock(state={})  # no account_id

        result = asyncio.run(
            svc.resolve_session_for_user(
                user_id="user_1",
                session_id="sess_no_account",
                session_service=session_service,
                app_name="ken_e_chatbot",
            )
        )

        assert result is None

    # (d2) Path-traversal guard: account_id containing "/" is rejected.
    def test_fallback_returns_none_when_account_id_contains_path_separator(self) -> None:
        db = _make_collection_group_result([])
        svc = ChatSessionSideTableService(db=db)
        # Crafted account_id that could be used for Firestore path traversal
        session_service = _make_session_service_mock(
            state={"account_id": "acc_victim/../injected"}
        )

        result = asyncio.run(
            svc.resolve_session_for_user(
                user_id="user_1",
                session_id="sess_traversal",
                session_service=session_service,
                app_name="ken_e_chatbot",
            )
        )

        assert result is None

    # (e) Heal-write failure → still returns synthesised metadata and emits WARN.
    def test_fallback_returns_metadata_even_when_heal_write_fails(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        db = _make_collection_group_result([])
        svc = ChatSessionSideTableService(db=db)
        svc.create = MagicMock(side_effect=RuntimeError("Firestore unavailable"))
        session_service = _make_session_service_mock(state={"account_id": "acc_heal_fail"})

        with caplog.at_level("WARNING"):
            result = asyncio.run(
                _drain_tasks(
                    svc.resolve_session_for_user(
                        user_id="user_1",
                        session_id="sess_heal_fail",
                        session_service=session_service,
                        app_name="ken_e_chatbot",
                        org_id_resolver=_org_resolver_ok,
                    )
                )
            )

        assert result is not None
        assert result.account_id == "acc_heal_fail"
        # heal-write failure is logged as a warning; message contains "self-heal"
        heal_warns = [r.getMessage() for r in caplog.records if "self-heal" in r.getMessage()]
        assert any("failed" in m or "skipped" in m for m in heal_warns)

    # (f) ADK raises an exception → returns None (no error propagated).
    def test_fallback_returns_none_when_adk_raises(self) -> None:
        db = _make_collection_group_result([])
        svc = ChatSessionSideTableService(db=db)
        session_service = _make_session_service_mock(raises=ValueError("ADK error"))

        result = asyncio.run(
            svc.resolve_session_for_user(
                user_id="user_1",
                session_id="sess_error",
                session_service=session_service,
                app_name="ken_e_chatbot",
            )
        )

        assert result is None

    # (g) No org_id_resolver → heal is skipped but synthesised metadata is returned.
    def test_no_resolver_skips_heal_but_returns_metadata(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        db = _make_collection_group_result([])
        svc = ChatSessionSideTableService(db=db)
        svc.create = MagicMock()
        session_service = _make_session_service_mock(state={"account_id": "acc_no_resolver"})

        with caplog.at_level("WARNING"):
            result = asyncio.run(
                _drain_tasks(
                    svc.resolve_session_for_user(
                        user_id="user_1",
                        session_id="sess_no_resolver",
                        session_service=session_service,
                        app_name="ken_e_chatbot",
                        # No org_id_resolver — heal is skipped
                    )
                )
            )

        assert result is not None
        assert result.account_id == "acc_no_resolver"
        # create should NOT have been called since resolver is None
        svc.create.assert_not_called()
        # A warning should be emitted for the skip; message contains "self-heal"
        heal_warns = [r.getMessage() for r in caplog.records if "self-heal" in r.getMessage()]
        assert len(heal_warns) >= 1

    # (h) Org resolver returns None → heal is skipped but synthesised metadata is returned.
    def test_none_org_id_skips_heal_returns_metadata(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        db = _make_collection_group_result([])
        svc = ChatSessionSideTableService(db=db)
        svc.create = MagicMock()
        session_service = _make_session_service_mock(state={"account_id": "acc_no_org"})

        with caplog.at_level("WARNING"):
            result = asyncio.run(
                _drain_tasks(
                    svc.resolve_session_for_user(
                        user_id="user_1",
                        session_id="sess_no_org",
                        session_service=session_service,
                        app_name="ken_e_chatbot",
                        org_id_resolver=_org_resolver_none,
                    )
                )
            )

        assert result is not None
        assert result.account_id == "acc_no_org"
        svc.create.assert_not_called()
        # A warning should be emitted for the skip; message contains "self-heal"
        heal_warns = [r.getMessage() for r in caplog.records if "self-heal" in r.getMessage()]
        assert len(heal_warns) >= 1

    # (i) Tombstoned side-table row present + ADK still has the session →
    #     deny (None) and do NOT fall back to ADK (CH-70 leak guard).
    def test_tombstoned_row_denies_without_adk_fallback(self) -> None:
        row = _base_row(deleted_at=datetime.now(timezone.utc))
        db = _make_collection_group_result([row])
        svc = ChatSessionSideTableService(db=db)
        session_service = _make_session_service_mock(state={"account_id": "acc_1"})

        result = asyncio.run(
            svc.resolve_session_for_user(
                user_id="user_1",
                session_id="sess_1",
                session_service=session_service,
                app_name="ken_e_chatbot",
            )
        )

        assert result is None
        # The ADK fallback must never run for a tombstoned session, or a
        # soft-deleted conversation would re-surface during the grace window.
        session_service.get_session.assert_not_called()

    # (j) ADK get_session RAISES ValueError on cross-user access (google-adk
    #     2.0.0 does NOT return None). The broad except MUST convert it to None
    #     (→ 404); this pins the security boundary against a future except-narrow.
    def test_resolve_denies_cross_user_when_adk_raises_value_error(self) -> None:
        db = _make_collection_group_result([])
        svc = ChatSessionSideTableService(db=db)
        session_service = _make_session_service_mock(
            raises=ValueError("Session sess_x does not belong to user user_1.")
        )

        result = asyncio.run(
            svc.resolve_session_for_user(
                user_id="user_1",
                session_id="sess_x",
                session_service=session_service,
                app_name="ken_e_chatbot",
            )
        )

        assert result is None

    # (k) Hardening: a non-str account_id in ADK state must not raise (the
    #     path-traversal guard would TypeError on ``"/" in <int>``) — return None.
    def test_fallback_returns_none_when_account_id_not_str(self) -> None:
        db = _make_collection_group_result([])
        svc = ChatSessionSideTableService(db=db)
        session_service = _make_session_service_mock(state={"account_id": 123})

        result = asyncio.run(
            svc.resolve_session_for_user(
                user_id="user_1",
                session_id="sess_bad_account",
                session_service=session_service,
                app_name="ken_e_chatbot",
            )
        )

        assert result is None
