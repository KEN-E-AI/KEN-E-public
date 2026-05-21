"""Correctness tests for the shared extract_billable_tokens helper.

Tests cover all branches documented in the CH-PRD-01 §5.4 spec and the
CH-10 implementation plan: cached-input exclusion, reasoning counting,
missing-field defaults, missing usage_metadata, total_billable arithmetic,
and the input floor-at-zero guard.
"""

from __future__ import annotations

from types import SimpleNamespace

from shared.token_accounting import BillableTokenCounts, extract_billable_tokens


def _make_event(
    prompt_token_count: int | None = None,
    candidates_token_count: int | None = None,
    thoughts_token_count: int | None = None,
    cached_content_token_count: int | None = None,
    usage_metadata: object | None = ...,  # type: ignore[assignment]
) -> SimpleNamespace:
    """Build a minimal synthetic ADK-event-like object for testing.

    Pass usage_metadata=None explicitly to simulate an event with no
    usage_metadata attribute populated.
    """
    if usage_metadata is ...:
        # Build from individual field kwargs
        meta_kwargs: dict[str, int] = {}
        if prompt_token_count is not None:
            meta_kwargs["prompt_token_count"] = prompt_token_count
        if candidates_token_count is not None:
            meta_kwargs["candidates_token_count"] = candidates_token_count
        if thoughts_token_count is not None:
            meta_kwargs["thoughts_token_count"] = thoughts_token_count
        if cached_content_token_count is not None:
            meta_kwargs["cached_content_token_count"] = cached_content_token_count
        usage_metadata = SimpleNamespace(**meta_kwargs)

    return SimpleNamespace(usage_metadata=usage_metadata)


class TestExtractBillableTokens:
    def test_full_happy_path(self) -> None:
        """All four metadata fields populated — baseline correctness check."""
        event = _make_event(
            prompt_token_count=1000,
            candidates_token_count=400,
            thoughts_token_count=50,
            cached_content_token_count=100,
        )
        result = extract_billable_tokens(event)
        assert result == BillableTokenCounts(input=900, output=400, reasoning=50)

    def test_cached_input_excluded_from_input(self) -> None:
        """cached_content_token_count must be subtracted from prompt_token_count."""
        event = _make_event(
            prompt_token_count=1000,
            candidates_token_count=200,
            cached_content_token_count=300,
        )
        result = extract_billable_tokens(event)
        assert result == BillableTokenCounts(input=700, output=200, reasoning=0)

    def test_reasoning_tokens_counted(self) -> None:
        """thoughts_token_count surfaces as the reasoning field."""
        event = _make_event(
            prompt_token_count=500,
            candidates_token_count=100,
            thoughts_token_count=150,
        )
        result = extract_billable_tokens(event)
        assert result == BillableTokenCounts(input=500, output=100, reasoning=150)

    def test_missing_fields_default_to_zero(self) -> None:
        """Metadata object with no attributes — all fields default to 0."""
        event = _make_event()  # no fields set on SimpleNamespace
        result = extract_billable_tokens(event)
        assert result == BillableTokenCounts(input=0, output=0, reasoning=0)

    def test_missing_usage_metadata_returns_all_zeros(self) -> None:
        """event.usage_metadata is None — helper must not raise."""
        event = _make_event(usage_metadata=None)
        result = extract_billable_tokens(event)
        assert result == BillableTokenCounts(input=0, output=0, reasoning=0)

    def test_total_billable_arithmetic(self) -> None:
        """total_billable == input + output + reasoning."""
        counts = BillableTokenCounts(input=100, output=200, reasoning=50)
        assert counts.total_billable == 350

    def test_input_floor_at_zero_when_cached_exceeds_prompt(self) -> None:
        """input must never be negative even if cached > prompt."""
        event = _make_event(
            prompt_token_count=100,
            candidates_token_count=80,
            cached_content_token_count=500,  # cached > prompt
        )
        result = extract_billable_tokens(event)
        assert result == BillableTokenCounts(input=0, output=80, reasoning=0)

    def test_event_without_usage_metadata_attribute(self) -> None:
        """Event object that has no usage_metadata attribute at all."""
        event = SimpleNamespace()  # no usage_metadata attr
        result = extract_billable_tokens(event)
        assert result == BillableTokenCounts(input=0, output=0, reasoning=0)
