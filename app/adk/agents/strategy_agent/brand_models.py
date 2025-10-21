"""
Pydantic models for brand guidelines.
Based on the knowledge graph design document for brand guidelines.
"""

from pydantic import BaseModel, Field


class BrandGuidelines(BaseModel):
    """A Pydantic model to structure and validate a company's brand guidelines."""

    brand_identity: str = Field(
        ...,
        description="A brief introduction to the brand and its reason for existence beyond profit. Include any existing taglines if applicable.",
    )

    brand_personality: str = Field(
        ...,
        description="A description of the brand's personality traits, expressed as if the brand were a person (e.g., friendly, professional, adventurous).",
    )

    voice_and_tone: str = Field(
        ...,
        description="Describes how the brand speaks to its audience, including tone, style, and specific language to use or avoid.",
    )

    color_palette: str = Field(
        ...,
        description="The official brand color palette, including HEX, RGB, CMYK, and Pantone codes with usage guidelines.",
    )

    typography: str = Field(
        ...,
        description="Guidelines for fonts and typefaces, including hierarchy for headlines, body text, and other elements.",
    )

    image_style: str = Field(
        ...,
        description="Guidelines for the style of photography and illustrations, including look, feel, and subject matter.",
    )

    mission_and_values: str = Field(
        ...,
        description="Defines the underlying principles and purpose of the company that guide its actions and messaging.",
    )

    references: list[str] = Field(
        default=[],
        description="Source URLs where brand guideline information was found during research",
    )
