"""Pydantic models for knowledge graph CRUD operations.

All models for Business, Competitive, Marketing, and Brand strategy nodes.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..validators import CompetitorValidators, KeywordValidators, URLValidators

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
    """Response model for product.

    Note: product_detail_page is optional (None) because:
    - Legacy data may not have this field populated
    - Some products may not have dedicated detail pages
    - Field is validated for URL format when present
    """

    product_name: str
    description: str
    references: list[str]
    product_detail_page: str | None = None
    category_node_id: str

    @field_validator("product_detail_page")
    @classmethod
    def validate_product_detail_page_url(cls, v: str | None) -> str | None:
        """Validate product_detail_page is a valid URL if provided."""
        if v is not None and v.strip():
            v = v.strip()
            if not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("product_detail_page must be a valid HTTP(S) URL")
        return v


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
        ...,
        description="Parent node ID (Product, ProductCategory, Account, SubstituteProduct, or Competitor)",
    )
    parent_node_type: str = Field(
        ...,
        description="Type of parent: Product, ProductCategory, Account, SubstituteProduct, or Competitor",
    )


class ValuePropositionUpdate(BaseModel):
    """Request model for updating a value proposition."""

    display_name: str | None = Field(None, max_length=60)
    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class ValuePropositionResponse(NodeBase):
    """Response model for value proposition.

    Note: parent_node_id and parent_node_type are optional (None) because:
    - Some GET operations don't include parent relationship data in queries
    - Backward compatibility with existing API responses
    - When present, both fields must be populated together (validated)
    - Valid parent types: Product, ProductCategory, Account, SubstituteProduct, Competitor

    Semantic note: ValuePropositions SHOULD always have a parent in the database,
    but the response model is flexible to accommodate various query patterns.
    """

    display_name: str
    description: str
    references: list[str]
    parent_node_id: str | None = None
    parent_node_type: str | None = None

    @field_validator("parent_node_type")
    @classmethod
    def validate_parent_node_type(cls, v: str | None, info) -> str | None:
        """Validate parent_node_type is a valid type and consistent with parent_node_id.

        Both parent_node_id and parent_node_type should be present together or both None.
        """
        if v is not None:
            # Validate it's a known parent type
            valid_parent_types = {
                "Product",
                "ProductCategory",
                "Account",
                "SubstituteProduct",
                "Competitor",
            }
            if v not in valid_parent_types:
                raise ValueError(
                    f"parent_node_type must be one of {valid_parent_types}, got: {v}"
                )

            # Check that parent_node_id is also present
            parent_node_id = info.data.get("parent_node_id")
            if parent_node_id is None or (
                isinstance(parent_node_id, str) and not parent_node_id.strip()
            ):
                raise ValueError(
                    "parent_node_type is set but parent_node_id is missing or empty. "
                    "Both fields must be present together or both None."
                )

        return v

    @field_validator("parent_node_id")
    @classmethod
    def validate_parent_node_id(cls, v: str | None) -> str | None:
        """Validate parent_node_id is non-empty if provided."""
        if v is not None and isinstance(v, str):
            v = v.strip()
            if not v:
                # Empty string should be treated as None
                return None
        return v


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
    """Request model for creating an opportunity.

    Opportunities can be created from either:
    - Strength nodes (business SWOT analysis)
    - CompetitorWeakness nodes (competitive analysis)
    """

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
    strength_node_id: str | None = Field(
        None, description="Parent Strength node_id (for business SWOT opportunities)"
    )
    weakness_node_id: str | None = Field(
        None,
        description="Parent CompetitorWeakness node_id (for competitive opportunities)",
    )

    @model_validator(mode="after")
    def validate_exactly_one_parent(self) -> "OpportunityCreate":
        """Ensure exactly one parent is provided."""
        has_strength = self.strength_node_id is not None
        has_weakness = self.weakness_node_id is not None

        if not has_strength and not has_weakness:
            raise ValueError(
                "Either strength_node_id or weakness_node_id must be provided"
            )
        if has_strength and has_weakness:
            raise ValueError(
                "Only one of strength_node_id or weakness_node_id can be provided"
            )

        return self


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
    strength_node_id: str | None = None  # For business SWOT opportunities
    weakness_node_id: str | None = None  # For competitive opportunities


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
    weakness_node_id: str | None = Field(
        None, description="Parent Weakness node_id (business SWOT)"
    )
    strength_node_id: str | None = Field(
        None, description="Parent CompetitorStrength node_id (competitive analysis)"
    )

    @model_validator(mode="after")
    def validate_exactly_one_parent(self):
        """Ensure exactly one parent is provided."""
        has_weakness = self.weakness_node_id is not None
        has_strength = self.strength_node_id is not None

        if not has_weakness and not has_strength:
            raise ValueError(
                "Either weakness_node_id or strength_node_id must be provided"
            )
        if has_weakness and has_strength:
            raise ValueError(
                "Only one of weakness_node_id or strength_node_id can be provided"
            )

        return self


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
    weakness_node_id: str | None = None  # For business SWOT risks
    strength_node_id: str | None = (
        None  # For competitive risks (from CompetitorStrength)
    )


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
                    "website": "https://molekule.com",
                    "keywords": ["molekule", "peco technology", "air purifier"],
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
    website: str | None = Field(
        default=None, description="Competitor website URL for news monitoring"
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Keywords for news monitoring system (auto-populated with competitor name if empty)",
    )

    @field_validator("display_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate competitor name."""
        return CompetitorValidators.validate_competitor_name(v)

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: str | None) -> str | None:
        """Validate competitor website URL."""
        return URLValidators.validate_website_url(v)

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, v: list[str]) -> list[str]:
        """Validate keywords list."""
        return KeywordValidators.validate_keyword_list(v)


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
    website: str | None = None


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


# ==================== MARKETING STRATEGY MODELS ====================
# Steps 4 & 5 Implementation


class CustomerProfileCreate(BaseModel):
    """Request model for creating a customer profile."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "display_name": "Marketing Mary",
                    "description": "Marketing Mary is a 35-year-old marketing director at a mid-sized SaaS company. She struggles with attribution tracking across multiple channels and needs tools that integrate with her existing martech stack. She prefers learning through webinars and case studies.",
                    "references": ["https://example.com/customer-research"],
                }
            ]
        }
    )

    display_name: str = Field(
        ...,
        max_length=200,
        description="Short, unique persona name (e.g., 'Marketing Mary')",
    )
    description: str = Field(
        ...,
        max_length=4000,
        description="Full persona narrative including background, pain points, needs, and communication preferences",
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )


class CustomerProfileUpdate(BaseModel):
    """Request model for updating a customer profile."""

    display_name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class CustomerProfileResponse(NodeBase):
    """Response model for customer profile."""

    display_name: str
    description: str = ""  # Default to empty string for backward compatibility
    references: list[str] = []


class CustomerProfileListResponse(BaseModel):
    """Response model for list of customer profiles."""

    customer_profiles: list[CustomerProfileResponse]
    total_count: int


class ProblemAwarenessStrategyCreate(BaseModel):
    """Request model for creating a problem awareness strategy."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "description": "Marketing Mary becomes aware of attribution problems through industry reports, LinkedIn discussions, and conversations with peers who struggle with multi-channel tracking. Target her through marketing automation blogs and webinars.",
                    "references": ["https://example.com/research"],
                    "customer_profile_node_id": "icp_abc123",
                    "product_category_node_id": "productcat_xyz789",
                }
            ]
        }
    )

    description: str = Field(
        ...,
        max_length=4000,
        description="Strategy for making profile aware of the problem",
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )
    customer_profile_node_id: str = Field(
        ..., description="CustomerProfile this strategy applies to"
    )
    product_category_node_id: str = Field(
        ..., description="ProductCategory this strategy applies to"
    )


class ProblemAwarenessStrategyUpdate(BaseModel):
    """Request model for updating a problem awareness strategy."""

    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class ProblemAwarenessStrategyResponse(NodeBase):
    """Response model for problem awareness strategy.

    Note: customer_profile_node_id and product_category_node_id are required
    for individual strategies but optional for rollup strategies.
    """

    description: str
    references: list[str]
    customer_profile_node_id: str | None = None
    product_category_node_id: str | None = None


class ProblemAwarenessStrategyListResponse(BaseModel):
    """Response model for list of problem awareness strategies."""

    problem_awareness_strategies: list[ProblemAwarenessStrategyResponse]
    total_count: int


class BrandAwarenessStrategyCreate(BaseModel):
    """Request model for creating a brand awareness strategy."""

    description: str = Field(
        ...,
        max_length=4000,
        description="Strategy for making profile aware of the brand",
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )
    customer_profile_node_id: str = Field(
        ..., description="CustomerProfile this strategy applies to"
    )
    product_category_node_id: str = Field(
        ..., description="ProductCategory this strategy applies to"
    )


class BrandAwarenessStrategyUpdate(BaseModel):
    """Request model for updating a brand awareness strategy."""

    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class BrandAwarenessStrategyResponse(NodeBase):
    """Response model for brand awareness strategy.

    Note: customer_profile_node_id and product_category_node_id are required
    for individual strategies but optional for rollup strategies.
    """

    description: str
    references: list[str]
    customer_profile_node_id: str | None = None
    product_category_node_id: str | None = None


class BrandAwarenessStrategyListResponse(BaseModel):
    """Response model for list of brand awareness strategies."""

    brand_awareness_strategies: list[BrandAwarenessStrategyResponse]
    total_count: int


class ConsiderationStrategyCreate(BaseModel):
    """Request model for creating a consideration strategy."""

    description: str = Field(
        ...,
        max_length=4000,
        description="Strategy for persuading profile to consider our brand",
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )
    customer_profile_node_id: str = Field(
        ..., description="CustomerProfile this strategy applies to"
    )
    product_category_node_id: str = Field(
        ..., description="ProductCategory this strategy applies to"
    )


class ConsiderationStrategyUpdate(BaseModel):
    """Request model for updating a consideration strategy."""

    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class ConsiderationStrategyResponse(NodeBase):
    """Response model for consideration strategy.

    Note: customer_profile_node_id and product_category_node_id are required
    for individual strategies but optional for rollup strategies.
    """

    description: str
    references: list[str]
    customer_profile_node_id: str | None = None
    product_category_node_id: str | None = None


class ConsiderationStrategyListResponse(BaseModel):
    """Response model for list of consideration strategies."""

    consideration_strategies: list[ConsiderationStrategyResponse]
    total_count: int


class ConversionStrategyCreate(BaseModel):
    """Request model for creating a conversion strategy."""

    description: str = Field(
        ...,
        max_length=4000,
        description="Strategy for converting profile to paying customer",
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )
    customer_profile_node_id: str = Field(
        ..., description="CustomerProfile this strategy applies to"
    )
    product_category_node_id: str = Field(
        ..., description="ProductCategory this strategy applies to"
    )


class ConversionStrategyUpdate(BaseModel):
    """Request model for updating a conversion strategy."""

    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class ConversionStrategyResponse(NodeBase):
    """Response model for conversion strategy.

    Note: customer_profile_node_id and product_category_node_id are required
    for individual strategies but optional for rollup strategies.
    """

    description: str
    references: list[str]
    customer_profile_node_id: str | None = None
    product_category_node_id: str | None = None


class ConversionStrategyListResponse(BaseModel):
    """Response model for list of conversion strategies."""

    conversion_strategies: list[ConversionStrategyResponse]
    total_count: int


class LoyaltyStrategyCreate(BaseModel):
    """Request model for creating a loyalty strategy."""

    description: str = Field(
        ..., max_length=4000, description="Strategy for building loyalty and advocacy"
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )
    customer_profile_node_id: str = Field(
        ..., description="CustomerProfile this strategy applies to"
    )
    product_category_node_id: str = Field(
        ..., description="ProductCategory this strategy applies to"
    )


class LoyaltyStrategyUpdate(BaseModel):
    """Request model for updating a loyalty strategy."""

    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class LoyaltyStrategyResponse(NodeBase):
    """Response model for loyalty strategy.

    Note: customer_profile_node_id and product_category_node_id are required
    for individual strategies but optional for rollup strategies.
    """

    description: str
    references: list[str]
    customer_profile_node_id: str | None = None
    product_category_node_id: str | None = None


class LoyaltyStrategyListResponse(BaseModel):
    """Response model for list of loyalty strategies."""

    loyalty_strategies: list[LoyaltyStrategyResponse]
    total_count: int


class MarketingStrategyResponse(BaseModel):
    """Aggregated response for complete marketing strategy graph.

    Returns all marketing nodes in a structured format for easy consumption by frontend.
    This avoids making separate queries for each related node type.
    """

    account_id: str
    customer_profiles: list[CustomerProfileResponse]
    problem_awareness_strategies: list[ProblemAwarenessStrategyResponse]
    brand_awareness_strategies: list[BrandAwarenessStrategyResponse]
    consideration_strategies: list[ConsiderationStrategyResponse]
    conversion_strategies: list[ConversionStrategyResponse]
    loyalty_strategies: list[LoyaltyStrategyResponse]


# ==================== ROLLUP MARKETING STRATEGY MODELS ====================


class RollupMarketingStrategyBase(BaseModel):
    """Base model for RollupMarketingStrategy hub node."""

    description: str = Field(..., description="Overall marketing strategy description")


class RollupMarketingStrategyCreate(RollupMarketingStrategyBase):
    """Create model for RollupMarketingStrategy."""

    pass


class RollupMarketingStrategyUpdate(BaseModel):
    """Update model for RollupMarketingStrategy."""

    description: str | None = None


class RollupMarketingStrategyResponse(NodeBase):
    """Response model for RollupMarketingStrategy."""

    description: str
    rollup_strategies: dict[str, str] | None = Field(
        None, description="Map of stage name to rollup strategy node_id"
    )


class RollupMarketingStrategyListResponse(BaseModel):
    """List response for RollupMarketingStrategy."""

    items: list[RollupMarketingStrategyResponse]
    total: int
    skip: int
    limit: int | None


# ==================== Brand Strategy Models ====================


class BrandIdentityUpdate(BaseModel):
    """Request model for updating brand identity hub (no create - auto-created)."""

    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class BrandIdentityResponse(NodeBase):
    """Response model for brand identity hub."""

    description: str
    references: list[str]


class BrandPersonalityCreate(BaseModel):
    """Request model for creating brand personality."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "description": "Innovative, approachable, and forward-thinking. We're the friend who always has the latest tech but explains it in a way everyone can understand.",
                    "references": ["https://example.com/brand-guidelines"],
                }
            ]
        }
    )

    description: str = Field(
        ..., max_length=4000, description="Brand personality traits"
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )


class BrandPersonalityUpdate(BaseModel):
    """Request model for updating brand personality."""

    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class BrandPersonalityResponse(NodeBase):
    """Response model for brand personality."""

    description: str
    references: list[str]
    brand_identity_node_id: str


class BrandPersonalityListResponse(BaseModel):
    """Response model for list of brand personalities."""

    brand_personalities: list[BrandPersonalityResponse]
    total_count: int


class VoiceAndToneCreate(BaseModel):
    """Request model for creating voice and tone."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "description": "Conversational yet professional. We use active voice, contractions, and clear language. Avoid jargon unless explaining it. Tone is optimistic and empowering.",
                    "references": ["https://example.com/voice-guide"],
                }
            ]
        }
    )

    description: str = Field(
        ..., max_length=4000, description="Voice and tone guidelines"
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )


class VoiceAndToneUpdate(BaseModel):
    """Request model for updating voice and tone."""

    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class VoiceAndToneResponse(NodeBase):
    """Response model for voice and tone."""

    description: str
    references: list[str]
    brand_identity_node_id: str


class VoiceAndToneListResponse(BaseModel):
    """Response model for list of voice and tone."""

    voice_and_tones: list[VoiceAndToneResponse]
    total_count: int


class ColorPaletteCreate(BaseModel):
    """Request model for creating color palette."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "description": "Primary: Navy Blue (#1A2B3C, RGB 26,43,60, CMYK 100,65,0,76). Secondary: Sky Blue (#4A90E2). Accent: Coral (#FF6B6B). Use navy for headings, sky blue for interactive elements, coral sparingly for CTAs.",
                    "references": ["https://example.com/color-guide"],
                }
            ]
        }
    )

    description: str = Field(
        ..., max_length=4000, description="Color palette specifications"
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )


class ColorPaletteUpdate(BaseModel):
    """Request model for updating color palette."""

    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class ColorPaletteResponse(NodeBase):
    """Response model for color palette."""

    description: str
    references: list[str]
    brand_identity_node_id: str


class ColorPaletteListResponse(BaseModel):
    """Response model for list of color palettes."""

    color_palettes: list[ColorPaletteResponse]
    total_count: int


class TypographyCreate(BaseModel):
    """Request model for creating typography."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "description": "Headlines: Inter Bold 32-48pt. Body: Inter Regular 16pt, line height 1.5. Captions: Inter Regular 14pt. Maintain 60-75 characters per line for readability.",
                    "references": ["https://example.com/typography-guide"],
                }
            ]
        }
    )

    description: str = Field(..., max_length=4000, description="Typography guidelines")
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )


class TypographyUpdate(BaseModel):
    """Request model for updating typography."""

    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class TypographyResponse(NodeBase):
    """Response model for typography."""

    description: str
    references: list[str]
    brand_identity_node_id: str


class TypographyListResponse(BaseModel):
    """Response model for list of typography."""

    typographies: list[TypographyResponse]
    total_count: int


class ImageStyleCreate(BaseModel):
    """Request model for creating image style."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "description": "Clean, minimalist product photography on white backgrounds. Lifestyle images should feel authentic and diverse. Use natural lighting. Avoid heavy filters. Images should be high-resolution (min 1920px wide).",
                    "references": ["https://example.com/image-guide"],
                }
            ]
        }
    )

    description: str = Field(..., max_length=4000, description="Image style guidelines")
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )


class ImageStyleUpdate(BaseModel):
    """Request model for updating image style."""

    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class ImageStyleResponse(NodeBase):
    """Response model for image style."""

    description: str
    references: list[str]
    brand_identity_node_id: str


class ImageStyleListResponse(BaseModel):
    """Response model for list of image styles."""

    image_styles: list[ImageStyleResponse]
    total_count: int


class MissionAndValuesCreate(BaseModel):
    """Request model for creating mission and values."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "description": "Mission: Empower businesses to make data-driven decisions. Values: Transparency, Innovation, Customer Success, Continuous Learning, Collaboration.",
                    "references": ["https://example.com/mission-values"],
                }
            ]
        }
    )

    description: str = Field(
        ..., max_length=4000, description="Mission and values statement"
    )
    references: list[str] = Field(
        default_factory=list, description="Source URLs or references"
    )


class MissionAndValuesUpdate(BaseModel):
    """Request model for updating mission and values."""

    description: str | None = Field(None, max_length=4000)
    references: list[str] | None = None


class MissionAndValuesResponse(NodeBase):
    """Response model for mission and values."""

    description: str
    references: list[str]
    brand_identity_node_id: str


class MissionAndValuesListResponse(BaseModel):
    """Response model for list of mission and values."""

    mission_and_values: list[MissionAndValuesResponse]
    total_count: int


class BrandStrategyResponse(BaseModel):
    """Aggregated response for complete brand strategy graph.

    Returns all brand nodes in a structured format for easy consumption by frontend.
    This avoids making separate queries for each related node type.
    """

    account_id: str
    brand_identity: BrandIdentityResponse | None
    brand_personalities: list[BrandPersonalityResponse]
    voice_and_tones: list[VoiceAndToneResponse]
    color_palettes: list[ColorPaletteResponse]
    typographies: list[TypographyResponse]
    image_styles: list[ImageStyleResponse]
    mission_and_values: list[MissionAndValuesResponse]
