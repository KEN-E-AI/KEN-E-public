"""Tests for the Sprint 6 query corpus."""

from __future__ import annotations

from collections import Counter

from tests.integration.stability.query_corpus import (
    EXPECTED_AGENT_TYPES,
    QUERIES,
    QueryCategory,
    queries_by_category,
)


def test_corpus_has_at_least_25_entries() -> None:
    assert len(QUERIES) >= 25


def test_each_category_has_at_least_5_entries() -> None:
    counts = Counter(q.category for q in QUERIES)
    missing = {cat for cat in QueryCategory if counts[cat] < 5}
    assert not missing, f"Categories under quota: {missing} (counts: {dict(counts)})"


def test_expected_agent_types_are_in_known_set() -> None:
    bad = [q for q in QUERIES if q.expected_agent_type not in EXPECTED_AGENT_TYPES]
    assert not bad, (
        f"Unknown expected_agent_type values: { {q.expected_agent_type for q in bad} }"
    )


def test_queries_by_category_filters_correctly() -> None:
    for cat in QueryCategory:
        filtered = queries_by_category(cat)
        assert filtered, f"{cat} returned empty"
        assert all(q.category is cat for q in filtered)
