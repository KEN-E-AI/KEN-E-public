"""Constants for knowledge graph operations.

Defines valid node types and their corresponding ID prefixes for the knowledge graph.
These constants are used for validation and to prevent Cypher injection attacks.
"""

# Valid node types for graph operations
# This whitelist prevents Cypher injection attacks by validating all node_type parameters
VALID_NODE_TYPES = frozenset(
    {
        # Business Strategy nodes (Phase 1)
        "ProductCategory",
        "Product",
        "ValueProposition",
        "Strength",
        "Weakness",
        "Opportunity",
        "Risk",
        "Goal",
        "SWOTAnalysis",
        # Core system nodes
        "Account",
        # Future phases: Competitive, Marketing, Brand strategy nodes will be added here
    }
)

# Mapping of node types to their ID prefixes
# Used for generating consistent node_id values
NODE_TYPE_TO_PREFIX: dict[str, str] = {
    "ProductCategory": "productcat",
    "Product": "prod",
    "ValueProposition": "valueprop",
    "Strength": "strength",
    "Weakness": "weakness",
    "Opportunity": "opportunity",
    "Risk": "risk",
    "Goal": "goal",
    "SWOTAnalysis": "swot",
    "Account": "acc",
}
