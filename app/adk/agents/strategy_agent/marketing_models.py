"""
Pydantic models for marketing strategy and customer intelligence.
Based on the knowledge graph design document for marketing strategy.
"""

from pydantic import BaseModel, Field, conlist


class IdealCustomerProfile(BaseModel):
    """
    A detailed profile of an ideal customer for a specific product category.
    """

    narrative: str = Field(
        ...,
        description=(
            "A narrative synthesizing the persona's name, background, pain points, "
            "core needs, buying motivations, and preferred communication channels."
        ),
    )
    problem_awareness_strategy: str = Field(
        ...,
        max_length=4000,
        description=(
            "A detailed strategy for making this persona aware of the problem the "
            "product solves, including key channels and touchpoints."
        ),
    )
    brand_awareness_strategy: str = Field(
        ...,
        max_length=4000,
        description=(
            "A detailed strategy for making this persona aware of the company's brand "
            "and products, demonstrating the value proposition."
        ),
    )
    consideration_strategy: str = Field(
        ...,
        max_length=4000,
        description=(
            "A strategy to persuade this persona to evaluate the company's offerings, "
            "detailing their evaluation process and key marketing touchpoints."
        ),
    )
    conversion_strategy: str = Field(
        ...,
        max_length=4000,
        description=(
            "A strategy to convert this persona into a paying customer, identifying "
            "critical factors and influential touchpoints in the purchasing decision."
        ),
    )
    loyalty_strategy: str = Field(
        ...,
        max_length=4000,
        description=(
            "A strategy to foster loyalty and advocacy from this persona post-purchase, "
            "outlining influential factors and touchpoints for retention."
        ),
    )
    references: list[str] = Field(
        default=[],
        description="Source URLs where information about this customer profile was found during research",
    )


class ProductCategory(BaseModel):
    """
    Contains the research findings for a specific product category.
    """

    category_name: str = Field(
        ..., description="The name of the product or service category being analyzed."
    )
    ideal_customer_profiles: conlist(
        IdealCustomerProfile, min_length=2, max_length=5
    ) = Field(
        ...,
        description="A list of 2 to 5 ideal customer profiles for this product category.",
    )


class MarketingResearchReport(BaseModel):
    """
    The root model for the marketing research report, containing a list of findings
    for each product category.
    """

    product_categories: list[ProductCategory] = Field(
        ...,
        description="A list of product categories with ideal customer profiles for each",
    )
