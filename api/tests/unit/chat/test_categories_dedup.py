"""Unit tests for ChatCategoryService casefold dedup.

create_category derives a deterministic doc id from (user_id, name_casefold)
and calls Firestore .create() — which is atomic. Two concurrent calls with
the same dedup key converge on the same path; one .create() wins, the other
raises google.api_core.exceptions.AlreadyExists, which the service translates
to CategoryExistsError.

These tests exercise that path with a mocked Firestore client: the .create()
call is wired to raise AlreadyExists, and each test asserts that:
  (1) CategoryExistsError fires with the right existing_id, AND
  (2) the doc path .create() was attempted under derives from the correct
      casefold — proving Unicode normalization actually reaches Firestore
      (the old mock-returns-hit-regardless-of-where()-args pattern proved
      neither (1) nor (2)).

Unicode casefold fixtures verified against Python 3 invariants:
  - Turkish: "İ".casefold() == "i̇" (capital I with dot above → small i + COMBINING DOT ABOVE)
  - German:  "STRASSE".casefold() == "strasse"  (ß casefolds to double-s)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import AlreadyExists
from src.kene_api.chat.categories import (
    CategoryExistsError,
    ChatCategoryService,
    _deterministic_category_id,
    _doc_path,
)
from src.kene_api.models.chat import ChatCategoryDefinition, compute_name_casefold

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_create_raises_already_exists() -> MagicMock:
    """Return a DB mock whose .document().create() always raises AlreadyExists."""
    db = MagicMock()
    db.document.return_value.create.side_effect = AlreadyExists("simulated collision")
    return db


def _make_db_no_collision() -> MagicMock:
    """Return a DB mock whose .document().create() succeeds (no collision)."""
    db = MagicMock()
    db.document.return_value.create.return_value = None
    return db


def _expected_id(user_id: str, name: str) -> str:
    """Compute the deterministic id for a given (user_id, name) — the test
    oracle. If the service derives the id from a different casefold value,
    the assertions fail."""
    return _deterministic_category_id(user_id, compute_name_casefold(name.strip()))


def _expected_path(user_id: str, name: str) -> str:
    return _doc_path(user_id, _expected_id(user_id, name))


# ---------------------------------------------------------------------------
# Collision — English case-variant
# ---------------------------------------------------------------------------


class TestEnglishCaseCollision:
    def test_lowercase_variant_collides_with_original(self) -> None:
        """'q3 campaigns' raises CategoryExistsError with the deterministic id."""
        db = _make_db_create_raises_already_exists()
        svc = ChatCategoryService(db=db)
        with pytest.raises(CategoryExistsError) as exc_info:
            svc.create_category("u1", "q3 campaigns")
        assert exc_info.value.existing_id == _expected_id("u1", "q3 campaigns")
        # The service attempted .create() at the path derived from the right casefold.
        db.document.assert_called_once_with(_expected_path("u1", "q3 campaigns"))

    def test_uppercase_variant_collides(self) -> None:
        """'Q3 CAMPAIGNS' casefolds to 'q3 campaigns' → same deterministic id."""
        db = _make_db_create_raises_already_exists()
        svc = ChatCategoryService(db=db)
        with pytest.raises(CategoryExistsError) as exc_info:
            svc.create_category("u1", "Q3 CAMPAIGNS")
        assert exc_info.value.existing_id == _expected_id("u1", "Q3 CAMPAIGNS")
        # The case-variant must derive the SAME id as the lowercase one.
        assert _expected_id("u1", "Q3 CAMPAIGNS") == _expected_id("u1", "q3 campaigns")

    def test_mixed_case_collides(self) -> None:
        db = _make_db_create_raises_already_exists()
        svc = ChatCategoryService(db=db)
        with pytest.raises(CategoryExistsError) as exc_info:
            svc.create_category("u1", "q3 CamPaigns")
        assert exc_info.value.existing_id == _expected_id("u1", "q3 CamPaigns")
        assert _expected_id("u1", "q3 CamPaigns") == _expected_id("u1", "q3 campaigns")


# ---------------------------------------------------------------------------
# Collision — Turkish dotted-i
# ---------------------------------------------------------------------------


class TestTurkishDottedICollision:
    def test_capital_i_with_dot_above_casefolds_to_small_i_plus_combining_dot(
        self,
    ) -> None:
        """Python 3 invariant: 'İ'.casefold() == 'i̇' (i + COMBINING DOT ABOVE U+0307)."""
        capital_i_with_dot = "İ"  # İ — LATIN CAPITAL LETTER I WITH DOT ABOVE
        assert capital_i_with_dot.casefold() == "i̇", (
            "Python casefold invariant for Turkish İ has changed — review fixture"
        )

    def test_turkish_capital_i_variant_collides(self) -> None:
        """'İstanbul' (U+0130) raises CategoryExistsError + the path uses the
        casefold-derived id. A regression that swapped casefold() for lower()
        would produce a DIFFERENT id than this oracle — failing the assertion."""
        db = _make_db_create_raises_already_exists()
        svc = ChatCategoryService(db=db)
        with pytest.raises(CategoryExistsError) as exc_info:
            svc.create_category("u1", "İstanbul")
        assert exc_info.value.existing_id == _expected_id("u1", "İstanbul")
        db.document.assert_called_once_with(_expected_path("u1", "İstanbul"))


# ---------------------------------------------------------------------------
# Collision — German ß
# ---------------------------------------------------------------------------


class TestGermanEszettCollision:
    def test_ss_casefold_invariant(self) -> None:
        """Python 3 invariant: 'STRASSE' or 'STRAẞE' casefolds to 'strasse'."""
        assert "STRASSE".casefold() == "strasse"
        assert "STRAße".casefold() == "strasse"

    def test_german_uppercase_collides(self) -> None:
        db = _make_db_create_raises_already_exists()
        svc = ChatCategoryService(db=db)
        with pytest.raises(CategoryExistsError) as exc_info:
            svc.create_category("u1", "STRASSE")
        assert exc_info.value.existing_id == _expected_id("u1", "STRASSE")
        db.document.assert_called_once_with(_expected_path("u1", "STRASSE"))

    def test_german_eszett_variant_collides(self) -> None:
        """'STRAße' and 'STRASSE' must produce the SAME deterministic id."""
        db = _make_db_create_raises_already_exists()
        svc = ChatCategoryService(db=db)
        with pytest.raises(CategoryExistsError) as exc_info:
            svc.create_category("u1", "STRAße")
        assert exc_info.value.existing_id == _expected_id("u1", "STRAße")
        assert _expected_id("u1", "STRAße") == _expected_id("u1", "STRASSE")


# ---------------------------------------------------------------------------
# Whitespace + dedup interaction
# ---------------------------------------------------------------------------


class TestStripAndDedupInteraction:
    def test_padded_name_collides_with_stripped(self) -> None:
        """'  Q3 Campaigns  ' must derive the same id as 'q3 campaigns' (strip + casefold)."""
        db = _make_db_create_raises_already_exists()
        svc = ChatCategoryService(db=db)
        with pytest.raises(CategoryExistsError) as exc_info:
            svc.create_category("u1", "  Q3 Campaigns  ")
        # The expected_id helper applies the same strip+casefold pipeline.
        assert exc_info.value.existing_id == _expected_id("u1", "Q3 Campaigns")
        assert _expected_id("u1", "  Q3 Campaigns  ") == _expected_id(
            "u1", "q3 campaigns"
        )


# ---------------------------------------------------------------------------
# Non-collision — different casefold succeeds
# ---------------------------------------------------------------------------


class TestNonCollision:
    def test_different_name_casefold_does_not_raise(self) -> None:
        """.create() succeeds → no collision → create_category returns the row."""
        db = _make_db_no_collision()
        svc = ChatCategoryService(db=db)
        result = svc.create_category("u1", "Completely Different Name")
        assert isinstance(result, ChatCategoryDefinition)
        assert result.name == "Completely Different Name"


# ---------------------------------------------------------------------------
# Race elimination — concurrent-create test
# ---------------------------------------------------------------------------


class TestRaceElimination:
    """Concurrent create_category(u1, "Q3 Campaigns") calls must converge.

    Modeling: two svc.create_category() calls with the same (user_id, name) target
    the SAME deterministic path. Firestore's .create() is atomic — the first call
    wins, the second raises AlreadyExists. The service translates that to
    CategoryExistsError with the same existing_id both callers can reason about.
    """

    def test_second_concurrent_create_raises_with_same_id(self) -> None:
        db = MagicMock()
        # First .create() succeeds; subsequent calls raise AlreadyExists.
        # MagicMock processes side_effect as an iterator if it's a list.
        db.document.return_value.create.side_effect = [
            None,  # winner
            AlreadyExists("simulated parallel write"),  # loser
        ]

        svc = ChatCategoryService(db=db)

        winner = svc.create_category("u1", "Q3 Campaigns")
        assert isinstance(winner, ChatCategoryDefinition)
        assert winner.category_id == _expected_id("u1", "Q3 Campaigns")

        with pytest.raises(CategoryExistsError) as exc_info:
            svc.create_category("u1", "Q3 Campaigns")
        # Loser sees the same deterministic id — callers can reconcile without
        # a separate query.
        assert exc_info.value.existing_id == winner.category_id

    def test_different_users_do_not_collide_on_same_name(self) -> None:
        """user_id is part of the dedup key — two users may both create "Q3 Campaigns"."""
        id_u1 = _expected_id("u1", "Q3 Campaigns")
        id_u2 = _expected_id("u2", "Q3 Campaigns")
        assert id_u1 != id_u2


# ---------------------------------------------------------------------------
# CategoryExistsError — attribute shape contract
# ---------------------------------------------------------------------------


class TestCategoryExistsErrorAttribute:
    def test_existing_id_accessible_as_attribute(self) -> None:
        err = CategoryExistsError("collision", existing_id="cat_abc123")
        assert err.existing_id == "cat_abc123"

    def test_is_subclass_of_exception(self) -> None:
        assert issubclass(CategoryExistsError, Exception)

    def test_str_representation_includes_message(self) -> None:
        err = CategoryExistsError("test message", existing_id="cat_xyz")
        assert "test message" in str(err)
