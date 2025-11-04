"""Pydantic models for knowledge graph CRUD operations.

All models for Business, Competitive, Marketing, and Brand strategy nodes.
"""

from datetime import datetime

from pydantic import BaseModel, Field

# ==================== BASE MODELS ====================


class NodeBase(BaseModel):
    """Base model for all graph nodes with standard audit fields."""

    node_id: str = Field(..., description="Unique node identifier")
    account_id: str = Field(..., description="Account this node belongs to")
    created_time: datetime
    last_modified: datetime
    created_by: str
    last_modified_by: str
    embedding: list[float] | None = Field(None, description="Vector embeddings for search")


# ==================== BUSINESS STRATEGY MODELS ====================


class ProductCategoryCreate(BaseModel):
    """Request model for creating a product category."""

    product_name: str = Field(..., max_length=200, description="Name of the product category")
    description: str = Field(..., max_length=4000, description="Description of the category")


class ProductCategoryUpdate(BaseModel):
    """Request model for updating a product category."""

    product_name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=4000)


class ProductCategoryResponse(NodeBase):
    """Response model for product category."""

    product_name: str
    description: str


class ProductCategoryListResponse(BaseModel):
    """Response model for list of product categories."""

    categories: list[ProductCategoryResponse]
    total_count: int


class ProductCreate(BaseModel):
    """Request model for creating a product."""

    product_name: str = Field(..., max_length=200, description="Name of the product")
    description: str = Field(..., max_length=4000, description="Product description")
    references: list[str] = Field(default_factory=list, description="Source URLs or references")
    product_detail_page: str | None = Field(None, description="URL to product detail page")
    category_node_id: str = Field(..., description="Parent ProductCategory node_id")


class ProductUpdate(BaseModel):
    """Request model for updating a product."""

    product_name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None
    product_detail_page: str | None = None


class ProductResponse(NodeBase):
    """Response model for product."""

    product_name: str
    description: str
    references: list[str]
    product_detail_page: str | None
    category_node_id: str


class ProductListResponse(BaseModel):
    """Response model for list of products."""

    products: list[ProductResponse]
    total_count: int


class ValuePropositionCreate(BaseModel):
    """Request model for creating a value proposition."""

    display_name: str = Field(..., max_length=60, description="Short name (under 60 chars)")
    description: str = Field(..., max_length=4000, description="Full description")
    references: list[str] = Field(default_factory=list, description="Source URLs or references")
    parent_node_id: str = Field(..., description="Parent node ID (Product, ProductCategory, or Account)")
    parent_node_type: str = Field(..., description="Type of parent: Product, ProductCategory, or Account")


class ValuePropositionUpdate(BaseModel):
    """Request model for updating a value proposition."""

    display_name: str | None = Field(None, max_length=60)
    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class ValuePropositionResponse(NodeBase):
    """Response model for value proposition."""

    display_name: str
    description: str
    references: list[str]
    parent_node_id: str
    parent_node_type: str


class ValuePropositionListResponse(BaseModel):
    """Response model for list of value propositions."""

    value_propositions: list[ValuePropositionResponse]
    total_count: int


class StrengthCreate(BaseModel):
    """Request model for creating a strength."""

    display_name: str = Field(..., max_length=60, description="Short name for the strength")
    description: str = Field(..., max_length=4000, description="Full description of the strength")
    references: list[str] = Field(default_factory=list, description="Source URLs or references")


class StrengthUpdate(BaseModel):
    """Request model for updating a strength."""

    display_name: str | None = Field(None, max_length=60)
    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class StrengthResponse(NodeBase):
    """Response model for strength."""

    display_name: str
    description: str
    references: list[str]


class StrengthListResponse(BaseModel):
    """Response model for list of strengths."""

    strengths: list[StrengthResponse]
    total_count: int


class WeaknessCreate(BaseModel):
    """Request model for creating a weakness."""

    display_name: str = Field(..., max_length=60, description="Short name for the weakness")
    description: str = Field(..., max_length=4000, description="Full description of the weakness")
    references: list[str] = Field(default_factory=list, description="Source URLs or references")


class WeaknessUpdate(BaseModel):
    """Request model for updating a weakness."""

    display_name: str | None = Field(None, max_length=60)
    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class WeaknessResponse(NodeBase):
    """Response model for weakness."""

    display_name: str
    description: str
    references: list[str]


class WeaknessListResponse(BaseModel):
    """Response model for list of weaknesses."""

    weaknesses: list[WeaknessResponse]
    total_count: int


class OpportunityCreate(BaseModel):
    """Request model for creating an opportunity."""

    display_name: str = Field(..., max_length=60, description="Short name for the opportunity")
    description: str = Field(..., max_length=4000, description="Full description of the opportunity")
    references: list[str] = Field(default_factory=list, description="Source URLs or references")
    strength_node_id: str = Field(..., description="Parent Strength node_id that creates this opportunity")


class OpportunityUpdate(BaseModel):
    """Request model for updating an opportunity."""

    display_name: str | None = Field(None, max_length=60)
    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class OpportunityResponse(NodeBase):
    """Response model for opportunity."""

    display_name: str
    description: str
    references: list[str]
    strength_node_id: str


class OpportunityListResponse(BaseModel):
    """Response model for list of opportunities."""

    opportunities: list[OpportunityResponse]
    total_count: int


class RiskCreate(BaseModel):
    """Request model for creating a risk."""

    display_name: str = Field(..., max_length=60, description="Short name for the risk")
    description: str = Field(..., max_length=4000, description="Full description of the risk")
    references: list[str] = Field(default_factory=list, description="Source URLs or references")
    weakness_node_id: str = Field(..., description="Parent Weakness node_id that creates this risk")


class RiskUpdate(BaseModel):
    """Request model for updating a risk."""

    display_name: str | None = Field(None, max_length=60)
    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class RiskResponse(NodeBase):
    """Response model for risk."""

    display_name: str
    description: str
    references: list[str]
    weakness_node_id: str


class RiskListResponse(BaseModel):
    """Response model for list of risks."""

    risks: list[RiskResponse]
    total_count: int


class GoalCreate(BaseModel):
    """Request model for creating a strategic goal."""

    display_name: str = Field(..., max_length=60, description="Short name for the goal")
    description: str = Field(..., max_length=4000, description="Full description of the goal")
    references: list[str] = Field(default_factory=list, description="Source URLs or references")


class GoalUpdate(BaseModel):
    """Request model for updating a goal."""

    display_name: str | None = Field(None, max_length=60)
    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class GoalResponse(NodeBase):
    """Response model for goal."""

    display_name: str
    description: str
    references: list[str]


class GoalListResponse(BaseModel):
    """Response model for list of goals."""

    goals: list[GoalResponse]
    total_count: int


class SWOTAnalysisResponse(NodeBase):
    """Response model for SWOT Analysis hub node."""

    display_name: str


# ==================== AGGREGATED VIEWS ====================


class BusinessStrategyResponse(BaseModel):
    """Aggregated view of complete business strategy graph."""

    account_id: str
    company_name: str
    company_overview: str
    product_categories: list[ProductCategoryResponse]
    products: list[ProductResponse]
    value_propositions: list[ValuePropositionResponse]
    swot_analysis: SWOTAnalysisResponse | None
    strengths: list[StrengthResponse]
    weaknesses: list[WeaknessResponse]
    opportunities: list[OpportunityResponse]
    risks: list[RiskResponse]
    goals: list[GoalResponse]
