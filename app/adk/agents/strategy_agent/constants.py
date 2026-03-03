"""Constants for strategy agent configuration."""

# Valid strategy types that can be generated
VALID_STRATEGY_TYPES = [
    "business_strategy",
    "competitive_strategy",
    "marketing_strategy",
    "brand_guidelines",
]

# Default product categories to use when Marketing Strategy is generated
# without Business Strategy (which normally provides product categories)
DEFAULT_PRODUCT_CATEGORIES = [
    "Core Products & Services",
    "Premium Offerings",
    "Subscription Services",
    "Professional Solutions",
    "Digital Products",
]

# Semantic output_category labels for each strategy agent's phases.
# Used by Weave attributes for MER-E trace-rule matching.
OUTPUT_CATEGORIES: dict[str, dict[str, str]] = {
    "business_strategy": {
        "research": "business_strategy.google_search",
        "report": "business_strategy.research_report",
    },
    "competitive_strategy": {
        "research": "competitive_strategy.google_search",
        "report": "competitive_strategy.research_report",
    },
    "marketing_strategy": {
        "research": "marketing_strategy.google_search",
        "report": "marketing_strategy.research_report",
    },
    "brand_guidelines": {
        "research": "brand_guidelines.google_search",
        "report": "brand_guidelines.research_report",
    },
}
