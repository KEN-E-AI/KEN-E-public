"""Unit tests for ``models.user_deletion`` and the ``user_deletion_service``
registry constants.

All tests are pure-logic: no I/O, no fixtures, no mocks.

AC-1  Happy-path ``UserDeletionResult(user_id=...)`` produces expected defaults.
AC-2  All-fields construction round-trips through ``model_dump()``.
AC-3  ``member_rows_deleted``, ``integrations_hook_fired``, ``gcs_prefixes_purged``
      reject non-coercible string input and negative values (ge=0).
AC-4  ``user_doc_deleted`` rejects non-bool input.
AC-5  ``errors`` rejects non-list / non-str-list input.
AC-6  Two instances have independent ``errors`` lists (default_factory guard).
AC-7  ``USER_SUBCOLLECTIONS`` is exactly the canonical three-entry list.
AC-8  ``USER_GCS_PREFIXES`` is an empty list.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from src.kene_api.models.user_deletion import UserDeletionResult
from src.kene_api.services.user_deletion_service import (
    USER_GCS_PREFIXES,
    USER_SUBCOLLECTIONS,
)

# ---------------------------------------------------------------------------
# AC-1: Happy-path default construction
# ---------------------------------------------------------------------------


class TestHappyPathConstruction:
    """AC-1: Minimal construction produces all-zero / False / empty defaults."""

    def test_defaults_are_zero_and_false(self) -> None:
        result = UserDeletionResult(user_id="u_carol")

        assert result.model_dump() == {
            "user_id": "u_carol",
            "member_rows_deleted": 0,
            "integrations_hook_fired": 0,
            "user_doc_deleted": False,
            "gcs_prefixes_purged": 0,
            "errors": [],
        }

    def test_user_id_is_required(self) -> None:
        with pytest.raises(ValidationError):
            UserDeletionResult()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# AC-2: All-fields round-trip through model_dump()
# ---------------------------------------------------------------------------


class TestAllFieldsRoundTrip:
    """AC-2: A fully-populated instance survives model_dump() unmodified."""

    def test_full_construction_round_trips(self) -> None:
        result = UserDeletionResult(
            user_id="u_carol",
            member_rows_deleted=5,
            integrations_hook_fired=3,
            user_doc_deleted=True,
            gcs_prefixes_purged=2,
            errors=["integrations_hook[acc_a]: timeout"],
        )
        dumped = result.model_dump()

        assert dumped == {
            "user_id": "u_carol",
            "member_rows_deleted": 5,
            "integrations_hook_fired": 3,
            "user_doc_deleted": True,
            "gcs_prefixes_purged": 2,
            "errors": ["integrations_hook[acc_a]: timeout"],
        }


# ---------------------------------------------------------------------------
# AC-3: Integer-field type rejection
# ---------------------------------------------------------------------------


class TestIntegerFieldRejection:
    """AC-3: Numeric count fields reject non-coercible string values.

    Pydantic v2 lax mode coerces digit strings (e.g. "3") to int.  These
    tests verify that alphabetic non-numeric strings are rejected, which is
    the contract guaranteed by the model's int type annotation.
    """

    def test_member_rows_deleted_rejects_string(self) -> None:
        with pytest.raises(ValidationError):
            UserDeletionResult(user_id="u", member_rows_deleted="x")  # type: ignore[arg-type]

    def test_integrations_hook_fired_rejects_string(self) -> None:
        with pytest.raises(ValidationError):
            UserDeletionResult(user_id="u", integrations_hook_fired="x")  # type: ignore[arg-type]

    def test_gcs_prefixes_purged_rejects_string(self) -> None:
        with pytest.raises(ValidationError):
            UserDeletionResult(user_id="u", gcs_prefixes_purged="x")  # type: ignore[arg-type]

    def test_member_rows_deleted_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            UserDeletionResult(user_id="u", member_rows_deleted=-1)

    def test_integrations_hook_fired_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            UserDeletionResult(user_id="u", integrations_hook_fired=-1)

    def test_gcs_prefixes_purged_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            UserDeletionResult(user_id="u", gcs_prefixes_purged=-1)


# ---------------------------------------------------------------------------
# AC-4: Bool-field type rejection
# ---------------------------------------------------------------------------


class TestBoolFieldRejection:
    """AC-4: user_doc_deleted rejects non-bool values that Pydantic cannot
    coerce."""

    def test_user_doc_deleted_rejects_arbitrary_object(self) -> None:
        with pytest.raises(ValidationError):
            UserDeletionResult(user_id="u", user_doc_deleted=object())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AC-5: errors list-of-str type rejection
# ---------------------------------------------------------------------------


class TestErrorsFieldRejection:
    """AC-5: errors rejects non-list and non-str-list values."""

    def test_errors_rejects_plain_string(self) -> None:
        with pytest.raises(ValidationError):
            UserDeletionResult(user_id="u", errors="not a list")  # type: ignore[arg-type]

    def test_errors_rejects_list_of_ints(self) -> None:
        with pytest.raises(ValidationError):
            UserDeletionResult(user_id="u", errors=[1, 2, 3])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AC-6: Independent errors lists between instances (default_factory guard)
# ---------------------------------------------------------------------------


class TestErrorsListIndependence:
    """AC-6: Two instances constructed without an explicit errors list do not
    share the same list object."""

    def test_two_instances_have_independent_errors_lists(self) -> None:
        a = UserDeletionResult(user_id="u_a")
        b = UserDeletionResult(user_id="u_b")

        a.errors.append("something went wrong")

        assert b.errors == []


# ---------------------------------------------------------------------------
# AC-7: USER_SUBCOLLECTIONS canonical value
# ---------------------------------------------------------------------------


class TestUserSubcollectionsRegistry:
    """AC-7: USER_SUBCOLLECTIONS is the canonical registry from PRD §4.2 + DM-52 additions."""

    def test_user_subcollections_exact(self) -> None:
        assert USER_SUBCOLLECTIONS == [
            "notification_status",
            "preferences",
            "chat_categories",
            "notifications",
            "security",
        ]


# ---------------------------------------------------------------------------
# AC-8: USER_GCS_PREFIXES is empty in v1
# ---------------------------------------------------------------------------


class TestUserGcsPrefixesRegistry:
    """AC-8: USER_GCS_PREFIXES is an empty list in v1."""

    def test_user_gcs_prefixes_empty(self) -> None:
        assert USER_GCS_PREFIXES == []
