"""Pydantic models for knowledge graph CRUD operations.

All models for Business, Competitive, Marketing, and Brand strategy nodes.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ==================== BASE MODELS ====================


class NodeBase(BaseModel):
    """Base model for all graph nodes with standard audit fields."""

    node_id: str = Field(..., description="Unique node identifier")
    account_id: str = Field(..., description="Account this node belongs to")
    created_time: datetime
    last_modified: datetime
    created_by: str
    last_modified_by: str
    embedding: list[float] | None = Field(
        None, description="Vector embeddings for search"
    )


# ==================== BUSINESS STRATEGY MODELS ====================


class ProductCategoryCreate(BaseModel):
    """Request model for creating a product category."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "product_name": "Cloud Computing Services",
                    "description": "Enterprise-grade cloud infrastructure including compute, storage, and networking solutions for scalable business operations",
                }
            ]
        }
    )

    product_name: str = Field(
        ..., max_length=200, description="Name of the product category"
    )
    description: str = Field(
        ..., max_length=4000, description="Description of the category"
    )


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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "product_name": "Virtual Machine Instances",
                    "description": "Scalable compute capacity with customizable CPU, memory, and storage configurations. Supports multiple operating systems and automated scaling",
                    "references": [
                        "https://example.com/docs/vm-instances",
                        "https://example.com/pricing/compute",
                    ],
                    "product_detail_page": "https://example.com/products/vm-instances",
                    "category_node_id": "productcat_acc123_a1b2c3d4",
                }
            ]
        }
    )

    product_name: str = Field(..., max_length=200, description="Name of the product")
    description: str = Field(..., max_length=4000, description="Product description")
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )
    product_detail_page: str | None = Field(
        None, description="URL to product detail page"
    )
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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "display_name": "99.99% Uptime SLA",
                    "description": "Guaranteed service availability with automated failover, redundant infrastructure, and 24/7 monitoring to ensure business continuity",
                    "references": ["https://example.com/sla-terms"],
                    "parent_node_id": "prod_acc123_x9y8z7w6",
                    "parent_node_type": "Product",
                }
            ]
        }
    )

    display_name: str = Field(
        ..., max_length=60, description="Short name (under 60 chars)"
    )
    description: str = Field(..., max_length=4000, description="Full description")
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )
    parent_node_id: str = Field(
        ..., description="Parent node ID (Product, ProductCategory, or Account)"
    )
    parent_node_type: str = Field(
        ..., description="Type of parent: Product, ProductCategory, or Account"
    )


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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "display_name": "Market-leading AI/ML capabilities",
                    "description": "Proprietary machine learning algorithms with 95% accuracy rate, trained on 10+ years of industry data. Recognized as Gartner Leader in AI Platform category",
                    "references": ["https://example.com/analyst-reports/gartner-2024"],
                }
            ]
        }
    )

    display_name: str = Field(
        ..., max_length=60, description="Short name for the strength"
    )
    description: str = Field(
        ..., max_length=4000, description="Full description of the strength"
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )


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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "display_name": "Limited presence in APAC region",
                    "description": "Only 3 data centers in Asia-Pacific compared to competitors' 15+. Results in higher latency for regional customers and challenges meeting data residency requirements",
                    "references": ["https://example.com/infrastructure-map"],
                }
            ]
        }
    )

    display_name: str = Field(
        ..., max_length=60, description="Short name for the weakness"
    )
    description: str = Field(
        ..., max_length=4000, description="Full description of the weakness"
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )


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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "display_name": "Expand into healthcare AI market",
                    "description": "Leverage our AI capabilities to target $50B healthcare diagnostics market. Strong regulatory compliance expertise and existing partnerships with 3 major hospital networks provide competitive advantage",
                    "references": [
                        "https://example.com/market-research/healthcare-ai-2024"
                    ],
                    "strength_node_id": "strength_acc123_f5g6h7i8",
                }
            ]
        }
    )

    display_name: str = Field(
        ..., max_length=60, description="Short name for the opportunity"
    )
    description: str = Field(
        ..., max_length=4000, description="Full description of the opportunity"
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )
    strength_node_id: str = Field(
        ..., description="Parent Strength node_id that creates this opportunity"
    )


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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "display_name": "Customer churn in APAC markets",
                    "description": "High latency and limited local support driving 25% annual churn rate among APAC enterprise customers. Risk of losing $15M ARR to regional competitors if not addressed within 12 months",
                    "references": [
                        "https://example.com/customer-retention-analysis-q4"
                    ],
                    "weakness_node_id": "weakness_acc123_j9k0l1m2",
                }
            ]
        }
    )

    display_name: str = Field(..., max_length=60, description="Short name for the risk")
    description: str = Field(
        ..., max_length=4000, description="Full description of the risk"
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )
    weakness_node_id: str = Field(
        ..., description="Parent Weakness node_id that creates this risk"
    )


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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "display_name": "Achieve $500M ARR by 2026",
                    "description": "Grow annual recurring revenue from $250M to $500M through expansion in healthcare and financial services verticals, with 40% coming from new product lines and 60% from existing customer expansion",
                    "references": ["https://example.com/strategic-plan-2024-2026"],
                }
            ]
        }
    )

    display_name: str = Field(..., max_length=60, description="Short name for the goal")
    description: str = Field(
        ..., max_length=4000, description="Full description of the goal"
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )


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


# ==================== COMMON RESPONSE MODELS ====================


class DeleteResponse(BaseModel):
    """Standard response model for delete operations."""

    success: bool = True
    message: str
    deleted_node_id: str


# ==================== AGGREGATED VIEWS ====================


class BusinessStrategyResponse(BaseModel):
    """Aggregated view of complete business strategy graph.

    TODO: When implementing the aggregated endpoint for this model, use a single
    Cypher query with relationship traversal to avoid N+1 query problems.
    Example pattern:
        MATCH (a:Account {account_id: $account_id})
        OPTIONAL MATCH (a)-[:HAS_CATEGORY]->(pc:ProductCategory)
        OPTIONAL MATCH (pc)-[:INCLUDES_PRODUCT]->(p:Product)
        OPTIONAL MATCH (p)-[:HAS_VALUE_PROPOSITION]->(vp:ValueProposition)
        ...
        RETURN a, collect(DISTINCT pc), collect(DISTINCT p), collect(DISTINCT vp), ...

    This avoids making separate queries for each related node type.
    """

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


# ==================== COMPETITIVE STRATEGY MODELS ====================
# Steps 2 & 3 Implementation


class CompetitiveEnvironmentCreate(BaseModel):
    """Request model for creating a competitive environment hub."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "description": "Key competitors operate within the enterprise air purification market, targeting commercial buildings, healthcare facilities, and large office spaces. The market is characterized by high brand loyalty, technical certifications, and B2B sales channels.",
                }
            ]
        }
    )

    description: str = Field(
        ..., max_length=4000, description="Description of the competitive environment"
    )


class CompetitiveEnvironmentUpdate(BaseModel):
    """Request model for updating a competitive environment."""

    description: str | None = Field(None, max_length=4000)


class CompetitiveEnvironmentResponse(NodeBase):
    """Response model for competitive environment."""

    description: str


class CompetitiveEnvironmentListResponse(BaseModel):
    """Response model for list of competitive environments."""

    environments: list[CompetitiveEnvironmentResponse]
    total_count: int


class CompetitorCreate(BaseModel):
    """Request model for creating a competitor."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "display_name": "Molekule, Inc",
                    "description": "Premium air purifier manufacturer with patented PECO technology. Founded in 2014, serves residential and commercial markets with $50M+ annual revenue. Known for high-end positioning and direct-to-consumer sales strategy.",
                    "references": [
                        "https://molekule.com/about",
                        "https://crunchbase.com/organization/molekule",
                    ],
                }
            ]
        }
    )

    display_name: str = Field(..., max_length=200, description="Name of the competitor")
    description: str = Field(
        ..., max_length=4000, description="Detailed competitor analysis"
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )


class CompetitorUpdate(BaseModel):
    """Request model for updating a competitor."""

    display_name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class CompetitorResponse(NodeBase):
    """Response model for competitor."""

    display_name: str
    description: str
    references: list[str]


class CompetitorListResponse(BaseModel):
    """Response model for list of competitors."""

    competitors: list[CompetitorResponse]
    total_count: int


class CompetitorTacticCreate(BaseModel):
    """Request model for creating a competitor tactic."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "display_name": "Annual Clean Air Conference",
                    "description": "Molekule hosts an annual industry conference featuring air quality experts, product demonstrations, and networking events. Attracts 500+ attendees including facility managers and procurement officers.",
                    "references": ["https://cleanaircon.com/2024"],
                    "competitor_node_id": "competitor_acc123_a1b2c3d4",
                }
            ]
        }
    )

    display_name: str = Field(..., max_length=200, description="Name of the tactic")
    description: str = Field(
        ..., max_length=4000, description="Detailed tactic description"
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )
    competitor_node_id: str = Field(..., description="Parent Competitor node_id")


class CompetitorTacticUpdate(BaseModel):
    """Request model for updating a competitor tactic."""

    display_name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class CompetitorTacticResponse(NodeBase):
    """Response model for competitor tactic."""

    display_name: str
    description: str
    references: list[str]
    competitor_node_id: str


class CompetitorTacticListResponse(BaseModel):
    """Response model for list of competitor tactics."""

    tactics: list[CompetitorTacticResponse]
    total_count: int


class CompetitorStrengthCreate(BaseModel):
    """Request model for creating a competitor strength."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "display_name": "Recognized Brand in Healthcare",
                    "description": "Molekule has established strong brand recognition in healthcare facilities, with partnerships across 200+ hospitals and clinics. Their medical-grade certifications create significant competitive advantage.",
                    "references": ["https://brandvalue.com/molekule-healthcare"],
                    "competitor_node_id": "competitor_acc123_a1b2c3d4",
                }
            ]
        }
    )

    display_name: str = Field(..., max_length=200, description="Name of the strength")
    description: str = Field(
        ..., max_length=4000, description="Detailed strength description"
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )
    competitor_node_id: str = Field(..., description="Parent Competitor node_id")


class CompetitorStrengthUpdate(BaseModel):
    """Request model for updating a competitor strength."""

    display_name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class CompetitorStrengthResponse(NodeBase):
    """Response model for competitor strength."""

    display_name: str
    description: str
    references: list[str]
    competitor_node_id: str


class CompetitorStrengthListResponse(BaseModel):
    """Response model for list of competitor strengths."""

    strengths: list[CompetitorStrengthResponse]
    total_count: int


class CompetitorWeaknessCreate(BaseModel):
    """Request model for creating a competitor weakness."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "display_name": "High Price Point",
                    "description": "Molekule products are priced 2-3x higher than competitors, limiting market penetration in price-sensitive segments. Customer reviews frequently cite cost as barrier to purchase.",
                    "references": ["https://reviews.com/molekule-pricing-analysis"],
                    "competitor_node_id": "competitor_acc123_a1b2c3d4",
                }
            ]
        }
    )

    display_name: str = Field(..., max_length=200, description="Name of the weakness")
    description: str = Field(
        ..., max_length=4000, description="Detailed weakness description"
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )
    competitor_node_id: str = Field(..., description="Parent Competitor node_id")


class CompetitorWeaknessUpdate(BaseModel):
    """Request model for updating a competitor weakness."""

    display_name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class CompetitorWeaknessResponse(NodeBase):
    """Response model for competitor weakness."""

    display_name: str
    description: str
    references: list[str]
    competitor_node_id: str


class CompetitorWeaknessListResponse(BaseModel):
    """Response model for list of competitor weaknesses."""

    weaknesses: list[CompetitorWeaknessResponse]
    total_count: int


class SubstituteProductCreate(BaseModel):
    """Request model for creating a substitute product."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "product_name": "Molekule Air Pro",
                    "description": "Commercial-grade air purifier with PECO technology, covering up to 1000 sq ft. Features smart sensors, mobile app control, and HEPA pre-filter. Designed for offices and medical facilities.",
                    "references": ["https://molekule.com/air-pro"],
                    "product_detail_page": "https://molekule.com/air-pro",
                    "competitor_node_id": "competitor_acc123_a1b2c3d4",
                }
            ]
        }
    )

    product_name: str = Field(
        ..., max_length=200, description="Name of the substitute product"
    )
    description: str = Field(..., max_length=4000, description="Product description")
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )
    product_detail_page: str | None = Field(
        None, description="URL to product detail page"
    )
    competitor_node_id: str = Field(..., description="Parent Competitor node_id")


class SubstituteProductUpdate(BaseModel):
    """Request model for updating a substitute product."""

    product_name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None
    product_detail_page: str | None = None


class SubstituteProductResponse(NodeBase):
    """Response model for substitute product."""

    product_name: str
    description: str
    references: list[str]
    product_detail_page: str | None
    competitor_node_id: str


class SubstituteProductListResponse(BaseModel):
    """Response model for list of substitute products."""

    products: list[SubstituteProductResponse]
    total_count: int


class CompetitiveStrategyResponse(BaseModel):
    """Aggregated response for complete competitive strategy graph.

    Returns all competitive nodes in a structured format for easy consumption by frontend.
    This avoids making separate queries for each related node type.
    """

    account_id: str
    competitive_environment: CompetitiveEnvironmentResponse | None
    competitors: list[CompetitorResponse]
    competitor_tactics: list[CompetitorTacticResponse]
    competitor_strengths: list[CompetitorStrengthResponse]
    competitor_weaknesses: list[CompetitorWeaknessResponse]
    substitute_products: list[SubstituteProductResponse]
    # Note: Risks and Opportunities created by competitive SWOT are shared with business strategy
    # They can be queried separately if needed
