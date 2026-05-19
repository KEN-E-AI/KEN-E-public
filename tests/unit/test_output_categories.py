"""Unit tests for OUTPUT_CATEGORIES in strategy agent constants."""

import pytest

from app.adk.agents.strategy_agent.constants import (
    OUTPUT_CATEGORIES,
    VALID_STRATEGY_TYPES,
)

EXPECTED_AGENTS = {
    "business_strategy",
    "competitive_strategy",
    "marketing_strategy",
    "brand_guidelines",
}
EXPECTED_PHASES = {"research", "report"}


class TestOutputCategoriesStructure:
    """Verify OUTPUT_CATEGORIES has all 4 agents x 2 phases."""

    def test_contains_all_four_agents(self) -> None:
        assert set(OUTPUT_CATEGORIES.keys()) == EXPECTED_AGENTS

    def test_each_agent_has_research_and_report_phases(self) -> None:
        for agent_name, phases in OUTPUT_CATEGORIES.items():
            assert set(phases.keys()) == EXPECTED_PHASES, (
                f"Agent '{agent_name}' missing expected phases"
            )

    def test_agents_match_valid_strategy_types(self) -> None:
        assert set(OUTPUT_CATEGORIES.keys()) == set(VALID_STRATEGY_TYPES)


class TestOutputCategoriesNaming:
    """Verify output_category values follow the naming convention."""

    @pytest.mark.parametrize("agent_name", sorted(EXPECTED_AGENTS))
    def test_research_value_follows_pattern(self, agent_name: str) -> None:
        expected = f"{agent_name}.google_search"
        assert OUTPUT_CATEGORIES[agent_name]["research"] == expected

    @pytest.mark.parametrize("agent_name", sorted(EXPECTED_AGENTS))
    def test_report_value_follows_pattern(self, agent_name: str) -> None:
        expected = f"{agent_name}.research_report"
        assert OUTPUT_CATEGORIES[agent_name]["report"] == expected

    def test_all_values_are_unique(self) -> None:
        all_values = [
            v for phases in OUTPUT_CATEGORIES.values() for v in phases.values()
        ]
        assert len(all_values) == len(set(all_values))
