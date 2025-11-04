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
