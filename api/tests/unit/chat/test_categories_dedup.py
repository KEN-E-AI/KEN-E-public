"""Unit tests for ChatCategoryService casefold dedup (CH-PRD-03 §4.2, §7 AC-2).

Pure-logic dedup tests using mocked Firestore. Each collision test sets up
the dedup query to return a fake existing document, then asserts the service
raises CategoryExistsError with the correct existing_id attribute.

Unicode casefold fixtures verified against Python 3 invariants:
  - Turkish: "İ".casefold() == "i̇" (capital I with dot above → small i + COMBINING DOT ABOVE)
  - German:  "STRASSE".casefold() == "strasse"  (ß casefolds to double-s)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from src.kene_api.chat.categories import CategoryExistsError, ChatCategoryService
from src.kene_api.models.chat import ChatCategoryDefinition

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_existing_doc(category_id: str) -> MagicMock:
    """Simulate a Firestore document snapshot that represents an existing category."""
    doc = MagicMock()
    doc.id = category_id
    doc.to_dict.return_value = {
        "category_id": category_id,
        "user_id": "u1",
        "name": "existing",
        "name_casefold": "existing",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    return doc


def _make_db_with_collision(existing_id: str = "cat_aabbccdd001122334455aabb") -> MagicMock:
    """Return a DB mock whose dedup query returns one existing document."""
    db = MagicMock()
    db.collection.return_value.where.return_value.limit.return_value.get.return_value = [
        _make_existing_doc(existing_id)
    ]
    return db


def _make_db_no_collision() -> MagicMock:
    """Return a DB mock whose dedup query returns an empty list (no collision)."""
    db = MagicMock()
    db.collection.return_value.where.return_value.limit.return_value.get.return_value = []
    db.document.return_value.create.return_value = None
    return db


# ---------------------------------------------------------------------------
# Collision — English case-variant
# ---------------------------------------------------------------------------


class TestEnglishCaseCollision:
    def test_lowercase_variant_collides_with_original(self) -> None:
        """'q3 campaigns' collides with 'Q3 Campaigns' (same casefold key)."""
        existing_id = "cat_aabbccdd001122334455aabb"
        db = _make_db_with_collision(existing_id)
        svc = ChatCategoryService(db=db)
        with pytest.raises(CategoryExistsError) as exc_info:
            svc.create_category("u1", "q3 campaigns")
        assert exc_info.value.existing_id == existing_id

    def test_uppercase_variant_collides(self) -> None:
        """'Q3 CAMPAIGNS' also collides."""
        existing_id = "cat_deadbeef000000000000000f"
        db = _make_db_with_collision(existing_id)
        svc = ChatCategoryService(db=db)
        with pytest.raises(CategoryExistsError) as exc_info:
            svc.create_category("u1", "Q3 CAMPAIGNS")
        assert exc_info.value.existing_id == existing_id

    def test_mixed_case_collides(self) -> None:
        """'q3 CamPaigns' collides."""
        existing_id = "cat_111111111111111111111111"
        db = _make_db_with_collision(existing_id)
        svc = ChatCategoryService(db=db)
        with pytest.raises(CategoryExistsError) as exc_info:
            svc.create_category("u1", "q3 CamPaigns")
        assert exc_info.value.existing_id == existing_id


# ---------------------------------------------------------------------------
# Collision — Turkish dotted-i
# ---------------------------------------------------------------------------


class TestTurkishDottedICollision:
    def test_capital_i_with_dot_above_casefolds_to_small_i_plus_combining_dot(self) -> None:
        """Python 3 invariant: 'İ'.casefold() == 'i̇' (i + COMBINING DOT ABOVE U+0307)."""
        # Sanity-check the Python invariant so the test fixture is self-documenting.
        capital_i_with_dot = "İ"  # İ — LATIN CAPITAL LETTER I WITH DOT ABOVE
        assert capital_i_with_dot.casefold() == "i̇", (
            "Python casefold invariant for Turkish İ has changed — review fixture"
        )

    def test_turkish_capital_i_variant_collides(self) -> None:
        """Creating 'İstanbul' (İ = U+0130) collides when the dedup query returns a hit."""
        existing_id = "cat_turkish000000000000000a"
        db = _make_db_with_collision(existing_id)
        svc = ChatCategoryService(db=db)
        # The dedup query is mocked to return a collision regardless of the exact
        # casefold value — this tests the service correctly raises on a non-empty result.
        with pytest.raises(CategoryExistsError) as exc_info:
            svc.create_category("u1", "İstanbul")
        assert exc_info.value.existing_id == existing_id


# ---------------------------------------------------------------------------
# Collision — German ß
# ---------------------------------------------------------------------------


class TestGermanEszettCollision:
    def test_ss_casefold_invariant(self) -> None:
        """Python 3 invariant: 'STRASSE' or 'STRAẞE' casefolds to 'strasse'."""
        # ß casefolds to 'ss' in Python 3; 'STRASSE'.casefold() → 'strasse'
        assert "STRASSE".casefold() == "strasse"
        assert "STRAße".casefold() == "strasse"

    def test_german_uppercase_collides(self) -> None:
        """Creating 'STRASSE' collides when the dedup query returns a hit."""
        existing_id = "cat_german0000000000000001"
        db = _make_db_with_collision(existing_id)
        svc = ChatCategoryService(db=db)
        with pytest.raises(CategoryExistsError) as exc_info:
            svc.create_category("u1", "STRASSE")
        assert exc_info.value.existing_id == existing_id

    def test_german_eszett_variant_collides(self) -> None:
        """Creating 'STRAße' collides when the dedup query returns a hit."""
        existing_id = "cat_german0000000000000002"
        db = _make_db_with_collision(existing_id)
        svc = ChatCategoryService(db=db)
        with pytest.raises(CategoryExistsError) as exc_info:
            svc.create_category("u1", "STRAße")
        assert exc_info.value.existing_id == existing_id


# ---------------------------------------------------------------------------
# Non-collision — different casefold succeeds
# ---------------------------------------------------------------------------


class TestNonCollision:
    def test_different_name_casefold_does_not_raise(self) -> None:
        """Dedup query returns empty → create_category succeeds."""
        db = _make_db_no_collision()
        svc = ChatCategoryService(db=db)
        result = svc.create_category("u1", "Completely Different Name")
        assert isinstance(result, ChatCategoryDefinition)
        assert result.name == "Completely Different Name"


# ---------------------------------------------------------------------------
# CategoryExistsError — attribute shape contract
# ---------------------------------------------------------------------------


class TestCategoryExistsErrorAttribute:
    def test_existing_id_accessible_as_attribute(self) -> None:
        """existing_id must be an attribute (not just in str(e)) so the router
        can translate directly: CategoryExistsError → HTTPException(409, detail=...)."""
        err = CategoryExistsError("collision", existing_id="cat_abc123")
        assert err.existing_id == "cat_abc123"

    def test_is_subclass_of_exception(self) -> None:
        assert issubclass(CategoryExistsError, Exception)

    def test_str_representation_includes_message(self) -> None:
        err = CategoryExistsError("test message", existing_id="cat_xyz")
        assert "test message" in str(err)
