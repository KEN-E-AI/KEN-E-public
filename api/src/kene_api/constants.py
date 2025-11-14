"""Constants for knowledge graph operations.

Defines valid node types and their corresponding ID prefixes for the knowledge graph.
These constants are used for validation and to prevent Cypher injection attacks.
"""

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
        # Core system nodes
        "Account",
        # Future phases: Brand strategy nodes will be added here
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
