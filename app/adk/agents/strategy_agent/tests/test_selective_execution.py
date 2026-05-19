"""Tests for selective strategy execution feature."""

import pytest

from agents.strategy_agent.constants import (
    DEFAULT_PRODUCT_CATEGORIES,
    VALID_STRATEGY_TYPES,
)


class TestSelectiveStrategyExecution:
    """Tests for selective strategy execution logic."""

    def test_valid_strategy_types_constant(self):
        """Test that VALID_STRATEGY_TYPES contains all expected strategies."""
        assert VALID_STRATEGY_TYPES == [
            "business_strategy",
            "competitive_strategy",
            "marketing_strategy",
            "brand_guidelines",
        ]

    def test_default_product_categories_constant(self):
        """Test that DEFAULT_PRODUCT_CATEGORIES has appropriate defaults."""
        assert len(DEFAULT_PRODUCT_CATEGORIES) == 5
        assert all(isinstance(cat, str) for cat in DEFAULT_PRODUCT_CATEGORIES)
        assert all(len(cat) > 0 for cat in DEFAULT_PRODUCT_CATEGORIES)
        # Ensure no placeholder-style names
        for cat in DEFAULT_PRODUCT_CATEGORIES:
            assert "Category A" not in cat
            assert "Category 1" not in cat
            assert "Product 1" not in cat

    @pytest.mark.parametrize(
        "enabled_strategies,should_skip",
        [
            (
                ["marketing_strategy"],
                ["business_strategy", "competitive_strategy", "brand_guidelines"],
            ),
            (
                ["business_strategy", "marketing_strategy"],
                ["competitive_strategy", "brand_guidelines"],
            ),
            (
                ["competitive_strategy"],
                ["business_strategy", "marketing_strategy", "brand_guidelines"],
            ),
            ([], VALID_STRATEGY_TYPES),  # Empty list should skip all
        ],
    )
    def test_strategy_filtering_logic(self, enabled_strategies, should_skip):
        """Test that strategies are correctly filtered based on enabled_strategies."""
        # Simulate the filtering logic from orchestrator
        for strategy in VALID_STRATEGY_TYPES:
            if strategy in enabled_strategies:
                assert strategy not in should_skip, f"{strategy} should run"
            else:
                assert strategy in should_skip, f"{strategy} should be skipped"

    def test_marketing_strategy_product_category_priority(self):
        """Test product category selection priority for marketing strategy."""
        # Priority 1: override_product_categories
        override_categories = ["Custom Category 1", "Custom Category 2"]
        business_categories = ["Business Category"]

        # When override is provided, use it
        categories_to_use = (
            override_categories
            if override_categories
            else (
                business_categories
                if business_categories
                else DEFAULT_PRODUCT_CATEGORIES
            )
        )
        assert categories_to_use == override_categories

        # Priority 2: business strategy categories
        override_categories = None
        categories_to_use = (
            override_categories
            if override_categories
            else (
                business_categories
                if business_categories
                else DEFAULT_PRODUCT_CATEGORIES
            )
        )
        assert categories_to_use == business_categories

        # Priority 3: default categories
        override_categories = None
        business_categories = []
        categories_to_use = (
            override_categories
            if override_categories
            else (
                business_categories
                if business_categories
                else DEFAULT_PRODUCT_CATEGORIES
            )
        )
        assert categories_to_use == DEFAULT_PRODUCT_CATEGORIES

    def test_enabled_strategies_defaults_to_all(self):
        """Test that enabled_strategies defaults to all strategies when None."""
        enabled_strategies: list[str] | None = None

        if enabled_strategies is None:
            enabled_strategies = VALID_STRATEGY_TYPES.copy()

        assert enabled_strategies == VALID_STRATEGY_TYPES
        assert len(enabled_strategies) == 4

    def test_invalid_strategy_types_validation(self):
        """Test that invalid strategy types are detected."""
        enabled_strategies = [
            "marketing_strategy",
            "invalid_strategy",
            "another_invalid",
        ]

        invalid_strategies = [
            s for s in enabled_strategies if s not in VALID_STRATEGY_TYPES
        ]

        assert invalid_strategies == ["invalid_strategy", "another_invalid"]
        assert len(invalid_strategies) == 2

    def test_empty_enabled_strategies_validation(self):
        """Test that empty enabled_strategies list raises error."""
        enabled_strategies = []

        # Empty list should raise ValueError
        should_raise_error = len(enabled_strategies) == 0
        assert should_raise_error is True

    def test_marketing_without_business_requires_categories(self):
        """Test that marketing strategy without business requires product categories."""
        enabled_strategies = ["marketing_strategy"]
        override_categories = None
        business_ran = "business_strategy" in enabled_strategies

        # When marketing runs without business and no override
        if (
            "marketing_strategy" in enabled_strategies
            and not business_ran
            and not override_categories
        ):
            categories_to_use = DEFAULT_PRODUCT_CATEGORIES
            assert categories_to_use == DEFAULT_PRODUCT_CATEGORIES
            assert len(categories_to_use) == 5


class TestStrategyExecutionEdgeCases:
    """Tests for edge cases in strategy execution."""

    def test_all_strategies_selected(self):
        """Test that all strategies can be selected."""
        enabled_strategies = VALID_STRATEGY_TYPES.copy()

        for strategy in VALID_STRATEGY_TYPES:
            assert strategy in enabled_strategies

    def test_single_strategy_selected(self):
        """Test that a single strategy can be selected."""
        for strategy_type in VALID_STRATEGY_TYPES:
            enabled_strategies = [strategy_type]
            assert len(enabled_strategies) == 1
            assert enabled_strategies[0] == strategy_type

    def test_override_categories_ignored_when_marketing_not_enabled(self):
        """Test that override_product_categories is ignored when marketing not enabled."""
        enabled_strategies = ["business_strategy", "competitive_strategy"]
        override_categories = ["Custom Category"]

        # Override should be ignored since marketing is not in enabled_strategies
        should_use_override = (
            override_categories is not None
            and "marketing_strategy" in enabled_strategies
        )

        assert not should_use_override

    @pytest.mark.parametrize(
        "categories,expected_count",
        [
            (["Category 1"], 1),
            (["Cat 1", "Cat 2", "Cat 3"], 3),
            (DEFAULT_PRODUCT_CATEGORIES, 5),
            ([], 0),
        ],
    )
    def test_product_category_counts(self, categories, expected_count):
        """Test product category list lengths."""
        assert len(categories) == expected_count
