"""
Split agent architecture for brand guidelines.

Following ADK constraint workaround: Agents with output_schema cannot use tools.
- Researcher agent: Has tools (google_search), NO output_schema
- Formatter agent: NO tools, has output_schema with BrandGuidelines model
"""

import google.adk as adk
from google.genai.types import GenerateContentConfig
from google.adk.tools import AgentTool
from .brand_models import BrandGuidelines


def create_brand_researcher(google_search_agent):
    """
    Create researcher agent that gathers brand guidelines information.

    This agent:
    - HAS tools (google_search)
    - NO output_schema
    - Returns unstructured research data

    Args:
        google_search_agent: Google search tool agent

    Returns:
        ADK Agent for brand research
    """
    return adk.Agent(
        name="brand_researcher",
        description="Researches brand identity, personality, and guidelines",
        model="gemini-2.0-flash",
        tools=[AgentTool(agent=google_search_agent)],
        # NO output_schema - this allows tool usage
        generate_content_config=GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=4000  # Limit to prevent rate limit issues
        ),
        instruction="""You are a brand intelligence researcher. Your role is to:

1. Research the company's brand identity and guidelines
2. Gather comprehensive information about:
   - Brand Identity: The brand's reason for existence beyond profit, taglines
   - Brand Personality: Human-like traits (friendly, professional, adventurous, etc.)
   - Voice and Tone: How the brand speaks, tone, style, language guidelines
   - Color Palette: Official brand colors with HEX, RGB, CMYK, Pantone codes
   - Typography: Fonts, typefaces, hierarchy (headlines, body text, etc.)
   - Image Style: Photography and illustration guidelines, look and feel
   - Mission and Values: Underlying principles and purpose

3. Use web search to find:
   - Official brand guideline documents
   - Marketing materials demonstrating brand voice
   - Visual identity examples
   - Company mission and values statements
   - Brand positioning and messaging

4. Provide comprehensive, detailed research findings

Focus on actionable brand guidelines that help ensure consistent brand communication.
Provide detailed findings with specific examples from official sources when possible."""
    )


def create_brand_formatter():
    """
    Create formatter agent that structures research into BrandGuidelines schema.

    This agent:
    - NO tools
    - HAS output_schema (BrandGuidelines)
    - Converts unstructured research into structured JSON

    Returns:
        ADK Agent for formatting brand guidelines
    """
    return adk.Agent(
        name="brand_formatter",
        description="Formats brand research into structured guidelines",
        model="gemini-2.5-pro",  # Using 2.5 Pro for better schema handling
        tools=[],  # NO tools - required for output_schema
        generate_content_config=GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8000,
            response_mime_type="application/json"
        ),
        output_schema=BrandGuidelines,  # Enforces JSON structure
        instruction="""You are a brand guidelines formatter. Your role is to:

1. Take unstructured brand research
2. Extract and organize it into a structured BrandGuidelines format
3. Ensure all 7 required fields are populated with high-quality information

Guidelines for each field:

- brand_identity: Brief introduction to the brand, its reason for existence, taglines
- brand_personality: Describe as if brand were a person (friendly, professional, adventurous, etc.)
- voice_and_tone: How brand speaks, tone (friendly/formal/playful), style, specific language to use/avoid
- color_palette: List all colors with codes (HEX, RGB, CMYK, Pantone), usage guidelines
- typography: Primary/secondary fonts, hierarchy (headlines, body, captions), sizes, spacing rules
- image_style: Photography/illustration style (bright/minimalist/bold), treatments, subject matter guidelines
- mission_and_values: Underlying principles and purpose guiding actions and messaging

- Write detailed, comprehensive descriptions for each field
- Include specific examples and technical details (color codes, font names)
- Ensure guidelines are actionable for content creation

Output valid JSON matching the BrandGuidelines schema EXACTLY.
Ensure all required fields are populated with rich content."""
    )
