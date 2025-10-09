"""
Pydantic models for competitive analysis and intelligence tracking.
Based on the updated knowledge graph design document for competitive strategy.
"""

from typing import List
from pydantic import BaseModel, Field, conlist


# ============================================================================
# Reusable & Sub-Models
# ============================================================================

class NamedDetail(BaseModel):
    """
    A generic model for an item that requires a short name and a
    longer, more detailed description.
    """
    name: str = Field(
        ...,
        description="A short, concise name or title for the item.",
    )
    description: str = Field(
        ...,
        description="A longer, more detailed description of the item."
    )
    references: List[str] = Field(default=[], description="Source URLs where this information was found during research")


class SubstituteProduct(BaseModel):
    """
    Defines a product or service from a competitor that can be
    seen as a substitute by customers.
    """
    name: str = Field(
        ...,
        description="The name of the substitute product or service.",
    )
    description: str = Field(
        ...,
        description="A description of the product and its positioning in the market."
    )
    value_proposition: NamedDetail = Field(
        ...,
        description="The key value proposition that explains why a customer might choose this substitute product."
    )
    references: List[str] = Field(default=[], description="Source URLs where this information was found during research")


# ============================================================================
# SWOT Sub-Models for Competitors
# ============================================================================

class StrengthWithRisks(BaseModel):
    """
    Describes a competitor's strength and the corresponding risks (threats) it
    creates for your company.
    """
    name: str = Field(
        ...,
        description="A short, concise name for the competitor's strength.",
    )
    description: str = Field(
        ...,
        description="A detailed description of the competitor's strength."
    )
    risks: conlist(NamedDetail, min_length=1, max_length=5) = Field(
        ...,
        description="A list of risks created for your company as a result of the competitor's strength."
    )
    references: List[str] = Field(default=[], description="Source URLs where information about this strength was found during research")


class WeaknessWithOpportunities(BaseModel):
    """
    Describes a competitor's weakness and the corresponding opportunities it
    creates for your company.
    """
    name: str = Field(
        ...,
        description="A short, concise name for the competitor's weakness.",
    )
    description: str = Field(
        ...,
        description="A detailed description of the competitor's weakness."
    )
    opportunities: conlist(NamedDetail, min_length=1, max_length=5) = Field(
        ...,
        description="A list of opportunities created for your company as a result of the competitor's weakness."
    )
    references: List[str] = Field(default=[], description="Source URLs where information about this weakness was found during research")


# ============================================================================
# Main Competitor Model
# ============================================================================

class Competitor(BaseModel):
    """
    Holds detailed information about a single competitor, including a SWOT analysis.
    """
    name: str = Field(
        ...,
        description="The name of the competitor.",
    )
    description: str = Field(
        ...,
        description=(
            "A summary of the competitor, including their history, company size, "
            "revenue, pricing strategy, distribution channels, and brand positioning."
        )
    )
    value_propositions: conlist(NamedDetail, min_length=1, max_length=5) = Field(
        ...,
        description="A list of 1-5 key value propositions explaining why customers choose this competitor."
    )
    marketing_tactics: conlist(NamedDetail, min_length=1, max_length=5) = Field(
        ...,
        description="A list of 1-5 specific tactics the competitor uses to bring products to market, such as social media campaigns, cold emails, events, or ads."
    )
    substitute_products: conlist(SubstituteProduct, min_length=1, max_length=5) = Field(
        ...,
        description="A list of 1-5 substitute products or services offered by the competitor."
    )
    strengths: conlist(StrengthWithRisks, min_length=1, max_length=10) = Field(
        ...,
        description="A SWOT analysis of the competitor's key strengths and the risks they pose."
    )
    weaknesses: conlist(WeaknessWithOpportunities, min_length=1, max_length=10) = Field(
        ...,
        description="A SWOT analysis of the competitor's weaknesses and the opportunities they create."
    )
    references: List[str] = Field(default=[], description="Source URLs where information about this competitor was found during research")


# ============================================================================
# Main Competitive Analysis Model
# ============================================================================

class CompetitiveAnalysis(BaseModel):
    """
    The main model to conduct a comprehensive competitive analysis for a business.
    """
    company_products: conlist(str, min_length=1, max_length=10) = Field(
        ...,
        description="A list of 1 to 10 of the company's top products or services being analyzed.",
    )
    competitive_environment_description: str = Field(
        ...,
        description=(
            "A description of the competitive environment and the strategy used to identify competitors. "
            "This should evaluate geography, physical location, company size, brand awareness, "
            "target customer segments, and potential substitute products or services."
        )
    )
    competitors: conlist(Competitor, min_length=1, max_length=10) = Field(
        ...,
        description=(
            "A list of the top competitors. To identify them, determine the importance of geography "
            "and brand recognition in the market. Identify other businesses with products or services "
            "that may be seen as direct substitutes by the target market."
        )
    )
