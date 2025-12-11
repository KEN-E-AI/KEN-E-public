"""Constants for knowledge graph operations.

Defines valid node types and their corresponding ID prefixes for the knowledge graph.
These constants are used for validation and to prevent Cypher injection attacks.
"""

from typing import Literal, TypedDict

# Valid node types for graph operations
# This whitelist prevents Cypher injection attacks by validating all node_type parameters
VALID_NODE_TYPES = frozenset(
    {
        # Business Strategy nodes (Step 1)
        "ProductCategory",
        "Product",
        "ValueProposition",
        "Strength",
        "Weakness",
        "Opportunity",
        "Risk",
        "Goal",
        "SWOTAnalysis",
        # Competitive Strategy nodes (Steps 2 & 3)
        "CompetitiveEnvironment",
        "Competitor",
        "CompetitorTactic",
        "CompetitorStrength",
        "CompetitorWeakness",
        "SubstituteProduct",
        # Marketing Strategy nodes (Steps 4 & 5)
        "CustomerProfile",
        "ProblemAwarenessStrategy",
        "BrandAwarenessStrategy",
        "ConsiderationStrategy",
        "ConversionStrategy",
        "LoyaltyStrategy",
        # Brand Strategy nodes (Steps 6 & 7)
        "BrandIdentity",
        "BrandPersonality",
        "VoiceAndTone",
        "ColorPalette",
        "Typography",
        "ImageStyle",
        "MissionAndValues",
        # Core system nodes
        "Account",
    }
)

# Valid marketing strategy types for rollup operations
# This whitelist prevents Cypher injection attacks in rollup strategy queries
VALID_MARKETING_STRATEGY_TYPES = frozenset(
    {
        "ProblemAwarenessStrategy",
        "BrandAwarenessStrategy",
        "ConsiderationStrategy",
        "ConversionStrategy",
        "LoyaltyStrategy",
    }
)

# Mapping of node types to their ID prefixes
# Used for generating consistent node_id values
NODE_TYPE_TO_PREFIX: dict[str, str] = {
    # Business Strategy
    "ProductCategory": "productcat",
    "Product": "prod",
    "ValueProposition": "valueprop",
    "Strength": "strength",
    "Weakness": "weakness",
    "Opportunity": "opportunity",
    "Risk": "risk",
    "Goal": "goal",
    "SWOTAnalysis": "swot",
    # Competitive Strategy
    "CompetitiveEnvironment": "competitiveenv",
    "Competitor": "competitor",
    "CompetitorTactic": "tactic",
    "CompetitorStrength": "compstrength",
    "CompetitorWeakness": "compweakness",
    "SubstituteProduct": "substitute",
    # Marketing Strategy
    "CustomerProfile": "icp",
    "ProblemAwarenessStrategy": "problemaware",
    "BrandAwarenessStrategy": "brandaware",
    "ConsiderationStrategy": "consideration",
    "ConversionStrategy": "conversion",
    "LoyaltyStrategy": "loyalty",
    # Brand Strategy
    "BrandIdentity": "brand",
    "BrandPersonality": "personality",
    "VoiceAndTone": "voicetone",
    "ColorPalette": "colors",
    "Typography": "typography",
    "ImageStyle": "imagestyle",
    "MissionAndValues": "mission",
    # System
    "Account": "acc",
}

# Resource limits per account (Competitive Strategy)
# These limits prevent database bloat and ensure reasonable UI performance
MAX_COMPETITORS_PER_ACCOUNT = 5
MAX_TACTICS_PER_COMPETITOR = 5
MAX_STRENGTHS_PER_COMPETITOR = 5
MAX_WEAKNESSES_PER_COMPETITOR = 5
MAX_SUBSTITUTE_PRODUCTS_PER_COMPETITOR = 10


class NodeTypeConfig(TypedDict):
    """Configuration for a knowledge graph node type.

    Used by generic CRUD endpoint factory to handle different node types consistently.
    """

    neo4j_label: str
    url_path: str
    firestore_doc_type: Literal[
        "business_strategy",
        "competitive_strategy",
        "marketing_strategy",
        "brand_strategy",
    ]
    prefix: str
    max_per_account: int | None
    list_field_name: str
    human_readable: str
    has_parent_filter: bool
    parent_filter_param: str | None
    is_hub_node: bool


# Comprehensive node type registry for all 28 knowledge graph node types
# Used by generic CRUD endpoints to eliminate code duplication
NODE_TYPE_REGISTRY: dict[str, NodeTypeConfig] = {
    # ==================== BUSINESS STRATEGY (9 types) ====================
    "ProductCategory": {
        "neo4j_label": "ProductCategory",
        "url_path": "product-categories",
        "firestore_doc_type": "business_strategy",
        "prefix": "productcat",
        "max_per_account": None,
        "list_field_name": "categories",
        "human_readable": "product category",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "Product": {
        "neo4j_label": "Product",
        "url_path": "products",
        "firestore_doc_type": "business_strategy",
        "prefix": "prod",
        "max_per_account": None,
        "list_field_name": "products",
        "human_readable": "product",
        "has_parent_filter": True,
        "parent_filter_param": "category_node_id",
        "is_hub_node": False,
    },
    "ValueProposition": {
        "neo4j_label": "ValueProposition",
        "url_path": "value-propositions",
        "firestore_doc_type": "business_strategy",
        "prefix": "valueprop",
        "max_per_account": None,
        "list_field_name": "value_propositions",
        "human_readable": "value proposition",
        "has_parent_filter": True,
        "parent_filter_param": "parent_node_id",
        "is_hub_node": False,
    },
    "Strength": {
        "neo4j_label": "Strength",
        "url_path": "strengths",
        "firestore_doc_type": "business_strategy",
        "prefix": "strength",
        "max_per_account": None,
        "list_field_name": "strengths",
        "human_readable": "strength",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "Weakness": {
        "neo4j_label": "Weakness",
        "url_path": "weaknesses",
        "firestore_doc_type": "business_strategy",
        "prefix": "weakness",
        "max_per_account": None,
        "list_field_name": "weaknesses",
        "human_readable": "weakness",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "Opportunity": {
        "neo4j_label": "Opportunity",
        "url_path": "opportunities",
        "firestore_doc_type": "business_strategy",
        "prefix": "opportunity",
        "max_per_account": None,
        "list_field_name": "opportunities",
        "human_readable": "opportunity",
        "has_parent_filter": True,
        "parent_filter_param": "strength_node_id",
        "is_hub_node": False,
    },
    "Risk": {
        "neo4j_label": "Risk",
        "url_path": "risks",
        "firestore_doc_type": "business_strategy",
        "prefix": "risk",
        "max_per_account": None,
        "list_field_name": "risks",
        "human_readable": "risk",
        "has_parent_filter": True,
        "parent_filter_param": "weakness_node_id",
        "is_hub_node": False,
    },
    "Goal": {
        "neo4j_label": "Goal",
        "url_path": "goals",
        "firestore_doc_type": "business_strategy",
        "prefix": "goal",
        "max_per_account": None,
        "list_field_name": "goals",
        "human_readable": "goal",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "SWOTAnalysis": {
        "neo4j_label": "SWOTAnalysis",
        "url_path": "swot-analysis",
        "firestore_doc_type": "business_strategy",
        "prefix": "swot",
        "max_per_account": 1,
        "list_field_name": "swot_analysis",
        "human_readable": "SWOT analysis",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": True,
    },
    # ==================== COMPETITIVE STRATEGY (6 types) ====================
    "Competitor": {
        "neo4j_label": "Competitor",
        "url_path": "competitors",
        "firestore_doc_type": "competitive_strategy",
        "prefix": "competitor",
        "max_per_account": 5,
        "list_field_name": "competitors",
        "human_readable": "competitor",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "CompetitorTactic": {
        "neo4j_label": "CompetitorTactic",
        "url_path": "competitor-tactics",
        "firestore_doc_type": "competitive_strategy",
        "prefix": "tactic",
        "max_per_account": None,
        "list_field_name": "competitor_tactics",
        "human_readable": "competitor tactic",
        "has_parent_filter": True,
        "parent_filter_param": "competitor_node_id",
        "is_hub_node": False,
    },
    "CompetitorStrength": {
        "neo4j_label": "CompetitorStrength",
        "url_path": "competitor-strengths",
        "firestore_doc_type": "competitive_strategy",
        "prefix": "compstrength",
        "max_per_account": None,
        "list_field_name": "competitor_strengths",
        "human_readable": "competitor strength",
        "has_parent_filter": True,
        "parent_filter_param": "competitor_node_id",
        "is_hub_node": False,
    },
    "CompetitorWeakness": {
        "neo4j_label": "CompetitorWeakness",
        "url_path": "competitor-weaknesses",
        "firestore_doc_type": "competitive_strategy",
        "prefix": "compweakness",
        "max_per_account": None,
        "list_field_name": "competitor_weaknesses",
        "human_readable": "competitor weakness",
        "has_parent_filter": True,
        "parent_filter_param": "competitor_node_id",
        "is_hub_node": False,
    },
    "SubstituteProduct": {
        "neo4j_label": "SubstituteProduct",
        "url_path": "substitute-products",
        "firestore_doc_type": "competitive_strategy",
        "prefix": "substitute",
        "max_per_account": None,
        "list_field_name": "substitute_products",
        "human_readable": "substitute product",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "CompetitiveEnvironment": {
        "neo4j_label": "CompetitiveEnvironment",
        "url_path": "competitive-environment",
        "firestore_doc_type": "competitive_strategy",
        "prefix": "competitiveenv",
        "max_per_account": 1,
        "list_field_name": "competitive_environment",
        "human_readable": "competitive environment",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": True,
    },
    # ==================== MARKETING STRATEGY (6 types) ====================
    "CustomerProfile": {
        "neo4j_label": "CustomerProfile",
        "url_path": "customer-profiles",
        "firestore_doc_type": "marketing_strategy",
        "prefix": "icp",
        "max_per_account": None,
        "list_field_name": "customer_profiles",
        "human_readable": "customer profile",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "ProblemAwarenessStrategy": {
        "neo4j_label": "ProblemAwarenessStrategy",
        "url_path": "problem-awareness-strategies",
        "firestore_doc_type": "marketing_strategy",
        "prefix": "problemaware",
        "max_per_account": None,
        "list_field_name": "problem_awareness_strategies",
        "human_readable": "problem awareness strategy",
        "has_parent_filter": True,
        "parent_filter_param": "customer_profile_node_id",
        "is_hub_node": False,
    },
    "BrandAwarenessStrategy": {
        "neo4j_label": "BrandAwarenessStrategy",
        "url_path": "brand-awareness-strategies",
        "firestore_doc_type": "marketing_strategy",
        "prefix": "brandaware",
        "max_per_account": None,
        "list_field_name": "brand_awareness_strategies",
        "human_readable": "brand awareness strategy",
        "has_parent_filter": True,
        "parent_filter_param": "customer_profile_node_id",
        "is_hub_node": False,
    },
    "ConsiderationStrategy": {
        "neo4j_label": "ConsiderationStrategy",
        "url_path": "consideration-strategies",
        "firestore_doc_type": "marketing_strategy",
        "prefix": "consideration",
        "max_per_account": None,
        "list_field_name": "consideration_strategies",
        "human_readable": "consideration strategy",
        "has_parent_filter": True,
        "parent_filter_param": "customer_profile_node_id",
        "is_hub_node": False,
    },
    "ConversionStrategy": {
        "neo4j_label": "ConversionStrategy",
        "url_path": "conversion-strategies",
        "firestore_doc_type": "marketing_strategy",
        "prefix": "conversion",
        "max_per_account": None,
        "list_field_name": "conversion_strategies",
        "human_readable": "conversion strategy",
        "has_parent_filter": True,
        "parent_filter_param": "customer_profile_node_id",
        "is_hub_node": False,
    },
    "LoyaltyStrategy": {
        "neo4j_label": "LoyaltyStrategy",
        "url_path": "loyalty-strategies",
        "firestore_doc_type": "marketing_strategy",
        "prefix": "loyalty",
        "max_per_account": None,
        "list_field_name": "loyalty_strategies",
        "human_readable": "loyalty strategy",
        "has_parent_filter": True,
        "parent_filter_param": "customer_profile_node_id",
        "is_hub_node": False,
    },
    # ==================== BRAND STRATEGY (7 types) ====================
    "BrandPersonality": {
        "neo4j_label": "BrandPersonality",
        "url_path": "brand-personalities",
        "firestore_doc_type": "brand_strategy",
        "prefix": "personality",
        "max_per_account": None,
        "list_field_name": "brand_personalities",
        "human_readable": "brand personality",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "VoiceAndTone": {
        "neo4j_label": "VoiceAndTone",
        "url_path": "voice-and-tone",
        "firestore_doc_type": "brand_strategy",
        "prefix": "voicetone",
        "max_per_account": None,
        "list_field_name": "voice_and_tone",
        "human_readable": "voice and tone",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "ColorPalette": {
        "neo4j_label": "ColorPalette",
        "url_path": "color-palettes",
        "firestore_doc_type": "brand_strategy",
        "prefix": "colors",
        "max_per_account": None,
        "list_field_name": "color_palettes",
        "human_readable": "color palette",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "Typography": {
        "neo4j_label": "Typography",
        "url_path": "typography",
        "firestore_doc_type": "brand_strategy",
        "prefix": "typography",
        "max_per_account": None,
        "list_field_name": "typography",
        "human_readable": "typography",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "ImageStyle": {
        "neo4j_label": "ImageStyle",
        "url_path": "image-styles",
        "firestore_doc_type": "brand_strategy",
        "prefix": "imagestyle",
        "max_per_account": None,
        "list_field_name": "image_styles",
        "human_readable": "image style",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "MissionAndValues": {
        "neo4j_label": "MissionAndValues",
        "url_path": "mission-and-values",
        "firestore_doc_type": "brand_strategy",
        "prefix": "mission",
        "max_per_account": None,
        "list_field_name": "mission_and_values",
        "human_readable": "mission and values",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": False,
    },
    "BrandIdentity": {
        "neo4j_label": "BrandIdentity",
        "url_path": "brand-identity",
        "firestore_doc_type": "brand_strategy",
        "prefix": "brand",
        "max_per_account": 1,
        "list_field_name": "brand_identity",
        "human_readable": "brand identity",
        "has_parent_filter": False,
        "parent_filter_param": None,
        "is_hub_node": True,
    },
}
