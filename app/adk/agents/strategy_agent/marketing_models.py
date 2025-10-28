"""
Pydantic models for marketing strategy and customer intelligence.
Based on the knowledge graph design document for marketing strategy.

Updated schema: Creates 2-5 master ideal customer profiles for the entire company.
Each product category defines marketing strategies for relevant customer profiles.
Marketing strategies are scoped to the combination of product category + customer profile.
"""

from pydantic import BaseModel, Field, conlist, field_validator


class MarketingStrategy(BaseModel):
    """
    A complete 5-stage marketing funnel strategy.

    This strategy is specific to a combination of product category and customer profile.
    It defines how to move a specific customer persona through the marketing funnel
    for a specific product category.
    """

    problem_awareness_strategy: str = Field(
        ...,
        max_length=4000,
        description=(
            "A detailed strategy for making this persona aware of the problem that "
            "this specific product category solves, including key channels and touchpoints."
        ),
    )
    brand_awareness_strategy: str = Field(
        ...,
        max_length=4000,
        description=(
            "A detailed strategy for making this persona aware of the company's brand "
            "and products within this specific product category, demonstrating the value proposition."
        ),
    )
    consideration_strategy: str = Field(
        ...,
        max_length=4000,
        description=(
            "A strategy to persuade this persona to evaluate the company's offerings "
            "within this product category, detailing their evaluation process and key marketing touchpoints."
        ),
    )
    conversion_strategy: str = Field(
        ...,
        max_length=4000,
        description=(
            "A strategy to convert this persona into a paying customer for this product category, "
            "identifying critical factors and influential touchpoints in the purchasing decision."
        ),
    )
    loyalty_strategy: str = Field(
        ...,
        max_length=4000,
        description=(
            "A strategy to foster loyalty and advocacy from this persona after purchasing "
            "from this product category, outlining influential factors and touchpoints for retention."
        ),
    )
    references: list[str] = Field(
        default=[],
        description="Source URLs where information about this marketing strategy was found during research",
    )


class MarketingStrategyForProfile(BaseModel):
    """
    Links a customer profile to its marketing strategy for a specific product category.

    Each product category can have 1-5 of these, one for each relevant customer profile.
    The marketing strategy is unique to this product category + customer profile combination.
    """

    customer_profile_name: str = Field(
        ...,
        description=(
            "Reference to the display_name of an IdealCustomerProfile from the master list. "
            "This identifies which customer persona this strategy targets."
        ),
    )
    strategy: MarketingStrategy = Field(
        ...,
        description=(
            "The complete 5-stage marketing strategy for this customer profile "
            "within this specific product category."
        ),
    )


class IdealCustomerProfile(BaseModel):
    """
    A master customer persona for the entire company.

    This represents a distinct customer segment that can be targeted across
    multiple product categories. The actual marketing strategies for each
    product category are defined separately in ProductCategoryMapping.

    IMPORTANT: This model does NOT contain marketing strategies. Strategies
    are scoped to product category + customer profile combinations.
    """

    display_name: str = Field(
        ...,
        description=(
            "A short and unique name for the customer profile (e.g., 'Marketing Manager Mary', "
            "'Technical Director Tom'). This is used as a reference key in product category mappings."
        ),
    )
    narrative: str = Field(
        ...,
        description=(
            "A narrative synthesizing the persona's name, background, pain points, "
            "core needs, buying motivations, and preferred communication channels. "
            "This narrative is product-agnostic and describes the persona holistically."
        ),
    )
    references: list[str] = Field(
        default=[],
        description="Source URLs where information about this customer profile was found during research",
    )


class ProductCategoryMapping(BaseModel):
    """
    Maps a product category to its customer profiles and their specific marketing strategies.

    Each product category defines 1-5 marketing strategies, one for each relevant customer profile.
    Each strategy is unique to the combination of this product category + that customer profile.
    """

    category_name: str = Field(
        ...,
        description="The name of the product or service category being analyzed.",
    )
    customer_strategies: conlist(
        MarketingStrategyForProfile, min_length=1, max_length=5
    ) = Field(
        ...,
        description=(
            "A list of 1 to 5 marketing strategies, one for each relevant customer profile. "
            "Each entry links a customer_profile_name (from the master list) to a complete "
            "5-stage marketing strategy specific to this product category + profile combination."
        ),
    )


class MarketingResearchReport(BaseModel):
    """
    The root model for the marketing research report.

    Contains a master list of 2-5 ideal customer profiles for the entire company,
    and product category mappings that define specific marketing strategies for
    each relevant customer profile within each product category.

    Key structure:
    - Master customer profiles: 2-5 profiles with display_name, narrative, references
    - Product mappings: For each category, 1-5 strategies (one per relevant profile)
    - Each strategy is scoped to the combination of product category + customer profile
    """

    ideal_customer_profiles: conlist(
        IdealCustomerProfile, min_length=2, max_length=5
    ) = Field(
        ...,
        description=(
            "A master list of 2 to 5 distinct ideal customer profiles for the entire company. "
            "Each profile should have a unique display_name that can be referenced in product category mappings. "
            "Profiles contain only identifying information (display_name, narrative, references) - "
            "NOT marketing strategies."
        ),
    )
    product_category_mappings: list[ProductCategoryMapping] = Field(
        ...,
        description=(
            "A list of product categories, each with 1-5 customer_strategies. "
            "Each customer_strategy links a customer_profile_name (from the master list) to a complete "
            "5-stage marketing strategy specific to that product category + profile combination."
        ),
    )

    @field_validator("product_category_mappings")
    @classmethod
    def validate_profile_references(
        cls, mappings: list[ProductCategoryMapping], info
    ) -> list[ProductCategoryMapping]:
        """
        Validate that all customer_profile_name references exist in the master list.

        Ensures data integrity by checking that every strategy references a valid
        customer profile from ideal_customer_profiles.
        """
        if "ideal_customer_profiles" not in info.data:
            return mappings

        valid_names = {
            profile.display_name for profile in info.data["ideal_customer_profiles"]
        }

        for mapping in mappings:
            for customer_strategy in mapping.customer_strategies:
                profile_name = customer_strategy.customer_profile_name
                if profile_name not in valid_names:
                    raise ValueError(
                        f"Profile reference '{profile_name}' in category '{mapping.category_name}' "
                        f"not found in master profile list. Valid profiles: {valid_names}"
                    )

        return mappings
