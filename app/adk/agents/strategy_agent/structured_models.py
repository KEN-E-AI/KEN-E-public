"""
Structured Pydantic models for Neo4j knowledge graph representation.
Based on the knowledge graph design document for business strategy.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ============================================================================
# Base Component Models
# ============================================================================


class SWOTItem(BaseModel):
    """Represents a single Strength, Weakness, Opportunity, or Risk."""

    id: str = Field(
        ...,
        description="A unique identifier for the item (e.g., 'strength-brand-reputation', 'risk-new-competitor')",
    )
    description: str = Field(
        ..., description="A clear and concise description of the SWOT item"
    )
    references: list[str] = Field(
        default=[],
        description="Source URLs where this information was found during research",
    )


class StrengthOpportunityLink(BaseModel):
    """Links a specific strength to one or more opportunities it enables."""

    strength: SWOTItem = Field(..., description="The specific internal strength")
    linked_opportunities: list[SWOTItem] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="A list of 1-5 external opportunities that can be exploited by this strength",
    )


class WeaknessRiskLink(BaseModel):
    """Links a specific weakness to one or more risks it exposes the business to."""

    weakness: SWOTItem = Field(..., description="The specific internal weakness")
    linked_risks: list[SWOTItem] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="A list of 1-5 external risks that are exacerbated by this weakness",
    )


class PESTELFactor(BaseModel):
    """Represents a single factor within the PESTEL analysis."""

    id: str = Field(
        ..., description="A unique identifier for the factor (e.g., 'tech-ai-adoption')"
    )
    description: str = Field(
        ..., description="Details about the factor and its potential impact"
    )
    trend: str = Field(
        ...,
        description="The direction of the trend's impact (e.g., 'Positive', 'Negative', 'Neutral')",
    )


class ValueProposition(BaseModel):
    """Represents a core value proposition of a product or service."""

    id: str = Field(
        ..., description="A unique identifier (e.g., 'valueprop-ease-of-use')"
    )
    display_name: str = Field(
        ..., description="A short, human-readable name (e.g., 'Superior Ease of Use')"
    )
    description: str = Field(
        ..., description="A detailed explanation of the value proposition"
    )
    references: list[str] = Field(
        default=[],
        description="Source URLs where this information was found during research",
    )


class ProductService(BaseModel):
    """Details a specific product or service offered by the company."""

    id: str = Field(
        ...,
        description="A unique identifier for the product (e.g., 'product-main-platform')",
    )
    display_name: str = Field(..., description="The name of the product or service")
    description: str = Field(
        ..., description="A summary of the product's features and purpose"
    )
    value_propositions: list[ValueProposition] = Field(
        ..., description="The core value propositions this product delivers"
    )
    references: list[str] = Field(
        default=[],
        description="Source URLs where this information was found during research",
    )


class ProductCategory(BaseModel):
    """A category of products offered by the company."""

    category_name: str = Field(
        ...,
        description="The name of the product category (e.g., 'Cloud Services', 'Consumer Electronics')",
    )
    value_propositions: list[ValueProposition] = Field(
        ...,
        description="The core value propositions delivered by products in this category",
    )
    products: list[ProductService] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="A list of 1-5 products within this category",
    )


class MarketSize(BaseModel):
    """Represents the size of a market, e.g., TAM."""

    value: float = Field(..., description="The estimated value of the market")
    currency: str = Field(..., description="The currency of the value (e.g., 'USD')")
    year: int = Field(..., description="The year the estimate is for")
    source: str | None = Field(None, description="The source of the market size data")


class IndustryTrend(BaseModel):
    """Represents a significant trend affecting the industry."""

    id: str = Field(
        ...,
        description="A unique identifier for the trend (e.g., 'trend-ai-in-analytics')",
    )
    display_name: str = Field(..., description="A short name for the trend")
    description: str = Field(
        ..., description="A detailed description of the trend and its implications"
    )


class RevenueStream(BaseModel):
    """A source of revenue for the business."""

    id: str = Field(
        ..., description="A unique identifier (e.g., 'revstream-subscriptions')"
    )
    display_name: str = Field(..., description="The name of the revenue stream")


class CostStructureItem(BaseModel):
    """A component of the business's cost structure."""

    id: str = Field(..., description="A unique identifier (e.g., 'cost-cloud-hosting')")
    display_name: str = Field(..., description="The name of the cost item")


class StrategicGoal(BaseModel):
    """A strategic goal for the business."""

    id: str = Field(
        ...,
        description="A unique identifier for the goal (e.g., 'goal-increase-smb-market-share')",
    )
    display_name: str = Field(..., description="A clear, concise statement of the goal")
    description: str = Field(..., description="More detailed context about the goal")
    references: list[str] = Field(
        default=[],
        description="Source URLs where this information was found during research",
    )


# ============================================================================
# Section Models
# ============================================================================


class SWOTAnalysis(BaseModel):
    """A strategic planning tool to identify internal strengths/weaknesses and external opportunities/risks."""

    strengths_and_opportunities: list[StrengthOpportunityLink] = Field(
        ...,
        min_length=3,
        max_length=10,
        description="Identify at least 3 (preferably 5-10) core internal strengths (e.g., strong brand, unique tech, operational efficiency, market position) and link each to the external opportunities it unlocks (e.g., new markets, favorable trends, partnerships)",
    )
    weaknesses_and_risks: list[WeaknessRiskLink] = Field(
        ...,
        min_length=3,
        max_length=10,
        description="Identify at least 3 (preferably 5-10) key internal weaknesses (e.g., high debt, outdated tech, limited resources, skill gaps) and link each to the external risks it exposes the business to (e.g., new competitors, changing regulations, market disruption)",
    )


class PESTELAnalysis(BaseModel):
    """Complete PESTEL analysis structure."""

    political: list[PESTELFactor]
    economic: list[PESTELFactor]
    social: list[PESTELFactor]
    technological: list[PESTELFactor]
    environmental: list[PESTELFactor]
    legal: list[PESTELFactor]


class MarketAndIndustryAnalysis(BaseModel):
    """Market and industry analysis structure."""

    market_description: str = Field(
        ...,
        description="A narrative overview of the industry where the company competes",
    )
    total_addressable_market: MarketSize | None = None
    industry_trends: list[IndustryTrend]


class InternalOperationsAndBusinessModel(BaseModel):
    """Internal operations and business model structure."""

    business_model_name: str = Field(..., description="e.g., 'SaaS Subscription Model'")
    revenue_streams: list[RevenueStream]
    cost_structure: list[CostStructureItem]


# ============================================================================
# Main Structured Business Strategy Model
# ============================================================================


class StructuredBusinessStrategy(BaseModel):
    """
    Defines the structured output for a comprehensive business strategy document,
    designed for direct ingestion into a knowledge graph.
    """

    company_name: str = Field(
        ..., description="The official name of the company being analyzed"
    )
    company_overview_summary: str = Field(
        ...,
        description="A comprehensive narrative that introduces the company's identity and background",
    )
    business_value_propositions: list[ValueProposition] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="A list of 1-5 core value propositions that describe the business as a whole and how it creates value for its customers",
    )
    product_portfolio: list[ProductCategory] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="A list of 1-5 key product categories, each containing 1-5 flagship products/services",
    )
    swot_analysis: SWOTAnalysis
    strategic_goals: list[StrategicGoal] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="A list of 1-5 highest-level strategic goals that must be met to maintain and improve the health of the business",
    )
    final_summary: str = Field(
        ...,
        description="A high-level summary of the company's situation and key recommendations, written last",
    )


# ============================================================================
# Update and Version Control Models
# ============================================================================


class StrategyUpdateRequest(BaseModel):
    """Request model for strategy updates."""

    account_id: str = Field(..., description="Account identifier")
    update_trigger: str = Field(
        ...,
        description="What triggered this update (e.g., 'market_change', 'user_request', 'competitor_action')",
    )
    target_sections: list[str] = Field(..., description="Which sections need updating")
    update_context: dict[str, Any] = Field(
        ..., description="Additional context for the update"
    )
    user_id: str | None = Field(None, description="User requesting the update")
    justification: str = Field(..., description="Reason for the update")


class StrategyDelta(BaseModel):
    """Represents changes between strategy versions."""

    node_id: str = Field(..., description="ID of the node being updated")
    node_type: str = Field(..., description="Type of node (e.g., 'Goal', 'Strength')")
    operation: str = Field(
        ..., description="Operation type: 'create', 'update', 'delete'"
    )
    old_values: dict[str, Any] | None = Field(
        None, description="Previous values (for updates)"
    )
    new_values: dict[str, Any] = Field(..., description="New values")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the change was made"
    )
    changed_by: str = Field(..., description="Who made the change")
    reason: str = Field(..., description="Why the change was made")


class StrategyVersion(BaseModel):
    """Version information for strategy documents."""

    version_number: int = Field(..., description="Sequential version number")
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = Field(..., description="User or system that created this version")
    change_summary: str = Field(..., description="Summary of changes in this version")
    deltas: list[StrategyDelta] = Field(
        ..., description="List of all changes in this version"
    )
    previous_version: int | None = Field(None, description="Previous version number")


# ============================================================================
# Simplified Models for Initial Testing
# ============================================================================


class SimpleBusinessStrategy(BaseModel):
    """Simplified version for backward compatibility with existing agents."""

    businessStrategySummary: str = Field(
        ..., description="Executive summary of the business strategy"
    )
    companyOverview: str = Field(
        ..., description="Comprehensive overview of the company"
    )
    marketAnalysis: str = Field(..., description="In-depth analysis of the market")


# ============================================================================
# Helper Functions for Model Transformation
# ============================================================================


def transform_simple_to_structured(
    simple_strategy: dict[str, Any], company_name: str, extract_structured: bool = True
) -> StructuredBusinessStrategy:
    """
    Transform a simple business strategy to structured format.
    This is a placeholder that would use AI to extract structured data.

    Args:
        simple_strategy: Simple strategy dictionary
        company_name: Company name
        extract_structured: Whether to extract structured components (requires AI)

    Returns:
        StructuredBusinessStrategy instance
    """
    # This would typically use an AI agent to extract structured components
    # For now, return a minimal structured version
    return StructuredBusinessStrategy(
        company_name=company_name,
        company_overview_summary=simple_strategy.get("companyOverview", ""),
        business_value_propositions=[
            ValueProposition(
                id="vp-main",
                display_name="Core Value",
                description="Primary value proposition",
            )
        ],
        product_portfolio=[
            ProductCategory(
                category_name="Main Products",
                value_propositions=[],
                products=[
                    ProductService(
                        id="product-main",
                        display_name="Main Product",
                        description="Primary product offering",
                        value_propositions=[],
                    )
                ],
            )
        ],
        swot_analysis=SWOTAnalysis(
            strengths_and_opportunities=[], weaknesses_and_risks=[]
        ),
        strategic_goals=[],
        final_summary=simple_strategy.get("businessStrategySummary", ""),
    )
