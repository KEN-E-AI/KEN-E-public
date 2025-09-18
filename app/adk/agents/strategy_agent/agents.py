"""
Agents used for creating strategy documents and saving to Firestore.
"""

import json
import logging

from google.adk.agents import Agent, LoopAgent, SequentialAgent
from google.adk.tools import AgentTool, exit_loop, google_search
from google.genai import types
from pydantic import BaseModel, Field

# Import models
from .models import StrategyContext

# Import logging, tracing, and token utilities
from .token_utils import TokenEstimator, TokenLimitError, check_and_log_tokens
from .logging_config import StrategyAgentLogger, safe_agent_execution
from .tracing_config import (
    WeaveTracer,
    weave_traced,
    safe_llm_call,
    trace_document_processing,
)
# Output retry wrapper not needed - ADK handles output validation via output_schema parameter

# Initialize tracing
WeaveTracer.init_tracing(project_name="strategy-agents")

# Set up logging
logger = logging.getLogger(__name__)
module_logger = StrategyAgentLogger("strategy_agents_module")

# Import Firestore utilities for format_new_information only
try:
    from .firestore import format_new_information

    FIRESTORE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Firestore utilities not available: {e}")
    FIRESTORE_AVAILABLE = False

    # Define stub for format_new_information
    def format_new_information(**kwargs) -> str:
        return json.dumps(kwargs)


# ============================================================================
# PYDANTIC OUTPUT SCHEMAS
# ============================================================================


class BusinessStrategy(BaseModel):
    """
    Defines the structured output for a comprehensive business strategy document.
    Each field represents a key component of the strategy and should be a
    synthesized narrative string based on research.
    """

    businessStrategySummary: str = Field(
        ...,
        description=(
            "A high-level summary of the company's situation, strategic direction, "
            "and key findings or recommendations. This should be written last but "
            "placed first."
        ),
    )
    companyOverview: str = Field(
        ...,
        description=(
            "A comprehensive narrative that introduces the company's identity and "
            "background. Synthesize your research on the following topics: the company's history and background "
            "(founding details, major milestones, evolution), its mission, vision, "
            "and values, an overview of its leadership and organizational structure, "
            "and its brand identity and customer base. Explain your reasoning and "
            "include references to public website URL's when available."
        ),
    )
    productsAndServices: str = Field(
        ...,
        description=(
            "A comprehensive description of the company's offerings. Synthesize your research on the following topics: the "
            "flagship products/services and their features, the core value "
            "proposition for customers, the competitive positioning of the "
            "offerings, and the company's pricing model. Explain your reasoning and "
            "include references to public website URL's when available."
        ),
    )
    marketAndIndustryAnalysis: str = Field(
        ...,
        description=(
            "A comprehensive review of the market environment. Synthesize your research on the following topics: the "
            "competitive landscape (key players and competitors), an estimate of "
            "the Total Addressable Market (TAM), and an overview of the industry "
            "including its current state, size, growth rate, and key trends. "
            "Explain your reasoning and include references to public website "
            "URL's when available."
        ),
    )
    swotAnalysis: str = Field(
        ...,
        description=(
            "A comprehensive SWOT analysis. Synthesize your research on the following topics: Strengths (internal "
            "advantages), Weaknesses (internal limitations), Opportunities "
            "(external chances for growth), and Threats (external factors that "
            "could cause harm). Explain your reasoning and include references to "
            "public website URL's when available."
        ),
    )
    externalEnvironmentAnalysisPESTEL: str = Field(
        ...,
        description=(
            "A comprehensive PESTEL analysis of macro-environmental factors. "
            "Synthesize your research on the following topics: Political (government policies, stability), Economic "
            "(inflation, growth), Social (demographic trends, consumer behavior), "
            "Technological (innovation, R&D), Environmental (sustainability, "
            "regulations), and Legal (labor laws, industry regulations). Explain "
            "your reasoning and include references to public website URL's when "
            "available."
        ),
    )
    marketingAndCustomerStrategy: str = Field(
        ...,
        description=(
            "A comprehensive analysis of how the company engages its market. "
            "Synthesize your research on the following topics: target market and customer segmentation, customer "
            "acquisition strategies, customer experience and retention efforts, "
            "digital and social media presence, and overall brand positioning. "
            "Explain your reasoning and include references to public website "
            "URL's when available."
        ),
    )
    internalOperationsAndBusinessModel: str = Field(
        ...,
        description=(
            "A comprehensive analysis of the company's internal workings. "
            "Synthesize your research on the following topics: the company's operational efficiency, its business "
            "model (revenue streams, cost structure), its value and supply chain, "
            "and its sales and distribution channels. Explain your reasoning and "
            "include references to public website URL's when available."
        ),
    )
    financialPerformanceAndAnalysis: str = Field(
        ...,
        description=(
            "A comprehensive review of the company's financial health. Synthesize your research on the following topics: "
            "revenue and growth rates, overall profitability (margins, trends), "
            "cash flow and financial stability (debt levels, risk), key financial "
            "ratios (ROI, LTV/CAC), and the company's financial outlook. Explain "
            "your reasoning and include references to public website URL's when "
            "available."
        ),
    )
    strategicRecommendationsAndFutureOutlook: str = Field(
        ...,
        description=(
            "A comprehensive summary of conclusions and suggested actions. "
            "Synthesize your research on the following topics: "
            "the key strategic issues identified, specific and actionable strategic "
            "recommendations to address them, and a concluding perspective on the "
            "company's future outlook. Explain your reasoning and include "
            "references to public website URL's when available."
        ),
    )


class CompetitiveAnalysis(BaseModel):
    """
    Defines the structured output for a comprehensive competitive analysis document.
    Each field represents a key component of the analysis and should be a
    synthesized narrative string.
    """

    competitiveStrategySummary: str = Field(
        ...,
        description=(
            "Provide a high-level overview of the market, competitor landscape, and "
            "the company's position. Highlight the most critical insights. Create "
            "strategic recommendations that summarize the primary actions and "
            "strategic changes suggested by the analysis. Explain your reasoning "
            "and add references when appropriate."
        ),
    )
    competitiveLandscape: str = Field(
        ...,
        description=(
            "Provide a comprehensive analysis of the competitive landscape. "
            "Synthesize your research on the following topics: the importance of geography and physical locations, "
            "the key success factors required to succeed in the industry (e.g., "
            "innovation, cost efficiency, distribution network), and any "
            "identified opportunities such as unmet customer needs or market gaps "
            "not addressed by competitors. Explain your reasoning and add "
            "references when appropriate."
        ),
    )
    detailedCompetitorProfiles: str = Field(
        ...,
        description=(
            "Provide detailed profiles for the top competitors. For each "
            "competitor, create a narrative summary and combine all profiles "
            "into a single, cohesive string. Each profile should synthesize "
            "information on the competitor's name, background (public/private, "
            "size, revenue), target market, pricing strategy, key strengths and "
            "weaknesses, marketing and promotion tactics, distribution channels, "
            "and their main products and value proposition. Structure the single "
            "string clearly for readability (e.g., 'Competitor A: [Profile "
            "details]... Competitor B: [Profile details]...'). Explain your "
            "reasoning and include references to public website URL's when "
            "available."
        ),
    )
    portersFiveForces: str = Field(
        ...,
        description=(
            "Provide a comprehensive Porter's Five Forces analysis. Synthesize your research on the following topics: the threat of new entrants, the bargaining power of "
            "suppliers, the intensity of competitive rivalry, the threat of "
            "substitute products or services, and the bargaining power of buyers. "
            "For each force, explain your reasoning and add references when "
            "appropriate."
        ),
    )
    strategicRecommendations: str = Field(
        ...,
        description=(
            "Provide a comprehensive set of strategic recommendations based on "
            "the competitive analysis. Synthesize your research on the following topics: how to "
            "leverage the company's unique strengths for competitive advantage, "
            "suggestions for product/service strategy based on market needs, "
            "recommendations for refining market positioning to stand out, "
            "specific actions to exploit competitor weaknesses or close gaps, and "
            "a final list of prioritized opportunities. Explain your reasoning "
            "and add references when appropriate."
        ),
    )


class CustomerJourneyAnalysis(BaseModel):
    """
    Defines the structured output for a comprehensive customer journey analysis.
    Each field represents a key component of the journey and should be a
    synthesized narrative.
    """

    customerJourneySummary: str = Field(
        ...,
        description=(
            "Provide a holistic summary of how a customer moves through the four "
            "stages of the marketing funnel. Synthesize your findings from the "
            "previous sections into a single, cohesive narrative that explains the "
            "journey from Awareness (first contact), through Consideration "
            "(research and evaluation), to Conversion (purchase), and finally to "
            "Loyalty (retention and advocacy). Write this section last. Explain "
            "your reasoning and add references when appropriate."
        ),
    )
    idealCustomerProfiles: str = Field(
        ...,
        description=(
            "Identify 3-5 ideal customer profiles and combine them into a single, "
            "cohesive string. For each profile, create a narrative that synthesizes "
            "the following details: a fictional personaName (e.g., 'Marketing Mary'), "
            "their background and role, key pain points, core needs, primary "
            "buying motivations, and their preferred communication channels. "
            "Structure the string clearly for readability (e.g., 'Persona 1 - "
            "Marketing Mary: [Full profile details]... Persona 2 - Startup Steve: "
            "[Full profile details]...'). Explain your reasoning and add "
            "references when appropriate."
        ),
    )
    customerNeedsAnalysis: str = Field(
        ...,
        description=(
            "Provide a comprehensive analysis of customer needs and motivations. "
            "Synthesize your research on the following topics: "
            "the unique value proposition the company's products/services offer, "
            "the core customer needs they solve, and an explanation of how current "
            "industry trends influence customer expectations and behaviors. "
            "Explain your reasoning and add references when appropriate."
        ),
    )
    awarenessPhase: str = Field(
        ...,
        description=(
            "Provide a comprehensive description of the 'Awareness' phase of the "
            "customer journey. Synthesize your research on the following topics: "
            "How do prospective customers become aware of the problem? "
            "How do prospective customers become aware of the solution to this problem? "
            "How do prospective customers become aware of the brand, its offerings or its competitor's offerings? "
            "Describe how prospective customers typically behave when first "
            "discovering the brand or its competitors, and the most influential "
            "marketing channels and touchpoints during this initial phase (e.g., "
            "'Blog posts,' 'PPC ads'). Explain your reasoning and add references "
            "when appropriate."
        ),
    )
    considerationPhase: str = Field(
        ...,
        description=(
            "Provide a comprehensive description of the 'Consideration' phase of "
            "the customer journey. Synthesize your research on the following topics: the typical customer behavior and actions during this "
            "evaluation process (e.g., comparing features, seeking reviews), what "
            "motivates them, and the most influential marketing channels and "
            "touchpoints that help them decide (e.g., 'Website feature pages,' "
            "'Case studies,' 'Free trial'). Explain your reasoning and add "
            "references when appropriate."
        ),
    )
    conversionPhase: str = Field(
        ...,
        description=(
            "Provide a comprehensive description of the 'Conversion' (or 'Purchase') "
            "phase of the customer journey. Synthesize your research on the following topics: the specific actions customers take to make "
            "a purchase (e.g., 'Online checkout,' 'Contract negotiation'), and the "
            "critical factors and influential touchpoints that lead to the final "
            "decision (e.g., 'Sales representative,' 'Onboarding flow'). Explain "
            "your reasoning and add references when appropriate."
        ),
    )
    loyaltyPhase: str = Field(
        ...,
        description=(
            "Provide a comprehensive description of the 'Loyalty' (or 'Advocacy') "
            "phase of the customer journey. Synthesize your research on the following topics: the post-purchase actions loyal customers "
            "take (e.g., 'Leaves a positive review,' 'Refers a colleague'), and the "
            "influential factors and touchpoints that foster retention and advocacy "
            "(e.g., 'Customer support,' 'Loyalty program'). Explain your reasoning "
            "and add references when appropriate."
        ),
    )


class MarketingStrategy(BaseModel):
    """
    Defines the structured output for a comprehensive marketing strategy document.
    Each field represents a key component of the strategy and should be a
    synthesized narrative string.
    """

    marketingStrategySummary: str = Field(
        ...,
        description=(
            "A summary of the full marketing strategy to move each ideal customer "
            "profile through the four-stage conversion funnel (awareness, consideration, "
            "conversion, loyalty). Do not create a specific timeline, but suggest "
            "how the strategy might unfold over the next 12 months. Explain your "
            "reasoning and add references where appropriate."
        ),
    )
    awarenessStrategy: str = Field(
        ...,
        description=(
            "A comprehensive strategy for increasing awareness within each ideal "
            "customer profile. Design messaging that addresses the customer need and "
            "highlights the unique value proposition. Suggest marketing channels and "
            "strategies that are most effective at reaching customers in this stage. "
            "Consider how the marketing budget might be used most effectively and "
            "efficiently. Explain your reasoning and add references where appropriate."
        ),
    )
    considerationStrategy: str = Field(
        ...,
        description=(
            "A comprehensive strategy for increasing the number of prospective "
            "customers who are in the consideration phase for each ideal customer "
            "profile. Design messaging that addresses the customer need at this "
            "stage and highlights the unique value proposition. Suggest marketing "
            "channels and strategies that are most effective at reaching customers "
            "in this stage. Consider how the marketing budget might be used most "
            "effectively and efficiently. Explain your reasoning and add references "
            "where appropriate."
        ),
    )
    conversionStrategy: str = Field(
        ...,
        description=(
            "A comprehensive strategy for increasing the number of prospective "
            "customers who are in the conversion phase for each ideal customer "
            "profile. Design messaging that addresses the customer need at this "
            "stage and highlights the unique value proposition. Suggest marketing "
            "channels and strategies that are most effective at reaching customers "
            "in this stage. Consider how the marketing budget might be used most "
            "effectively and efficiently. Explain your reasoning and add references "
            "where appropriate."
        ),
    )
    loyaltyStrategy: str = Field(
        ...,
        description=(
            "A comprehensive strategy for increasing the number of loyal customers "
            "for each ideal customer profile. Design messaging that addresses the "
            "customer need at this stage and highlights the unique value proposition. "
            "Suggest marketing channels and strategies that are most effective at "
            "reaching customers in this stage. Consider how the marketing budget "
            "might be used most effectively and efficiently. Explain your reasoning "
            "and add references where appropriate."
        ),
    )


class BrandGuidelines(BaseModel):
    """
    Defines the structured output for a comprehensive brand guidelines document.
    Each field represents a key component of the brand's identity and should be a
    synthesized narrative string.
    """

    brand_name: str = Field(
        ...,
        description=(
            "The official name of the company or brand. Provide the exact name as it "
            "is used in branding and communications (including correct spelling, "
            "capitalization, and any trademark symbols if applicable)."
        ),
    )
    tagline: str = Field(
        ...,
        description=(
            "The brand's tagline or slogan, if one exists. Include the short phrase "
            "or motto that encapsulates the essence of the brand or its promise. "
            "Make sure to present it exactly as the brand uses it (including "
            "punctuation) and describe the context in which it is used (e.g., in "
            "logos, advertisements, etc.). If the brand does not have an official "
            "tagline, this section can be noted as not applicable."
        ),
    )
    brand_overview: str = Field(
        ...,
        description=(
            "A brief introduction to the brand, summarizing what the company does, "
            "its industry, and its overall purpose or offering. This gives context "
            "about the business and what makes it unique."
        ),
    )
    brand_story: str = Field(
        ...,
        description=(
            "A narrative about the brand's history and background. Include how the "
            "company was founded, key milestones in its development, and any "
            "significant moments or anecdotes that shape the brand's identity. "
            "This helps readers understand the brand's heritage and evolution."
        ),
    )
    value_proposition: str = Field(
        ...,
        description=(
            "A statement of the brand's value proposition or positioning. Summarize "
            "the unique value and benefits the brand offers to its customers, and "
            "what differentiates it from competitors. This can include the brand's "
            "positioning statement or a brief overview of how the brand solves "
            "customers’ problems or meets their needs better than alternatives."
        ),
    )
    brand_personality: str = Field(
        ...,
        description=(
            "A description of the brand's personality traits, expressed as if the "
            "brand were a person. Include key characteristics (e.g., friendly, "
            "professional, adventurous, innovative) that describe the brand's "
            "character. These traits should be reflected in how the brand looks, "
            "speaks, and acts, ensuring consistency in brand experience."
        ),
    )
    brand_voice_and_tone: str = Field(
        ...,
        description=(
            "Guidelines for the brand’s voice and tone in communications. Describe "
            "how the brand speaks to its audience – for example, whether the tone "
            "is friendly, authoritative, playful, formal, compassionate, etc. "
            "Include specific directions for language use, such as preferred style "
            "(e.g., conversational or technical), use of humor, and any words or "
            "phrases the brand likes to use or avoid. Provide examples of the "
            "tone in practice to illustrate how messaging should come across in "
            "writing or speech."
        ),
    )
    logo_guidelines: str = Field(
        ...,
        description=(
            "Rules and specifications for using the brand’s logo. Include a "
            "description of the primary logo and any approved variations (such as "
            "horizontal/vertical formats, icons or symbols, and versions with or "
            "without a tagline). Provide guidelines on clear space (exclusion "
            "zones) around the logo, minimum size requirements for print and "
            "digital use, and acceptable backgrounds (light, dark, transparent). "
            "Also outline improper uses of the logo (such as distorting its "
            "proportions, altering colors, or adding effects) to ensure the logo "
            "always appears consistent and recognizable."
        ),
    )
    color_palette: str = Field(
        ...,
        description=(
            "The official color palette of the brand. List the primary brand "
            "colors and any secondary or accent colors. For each color, provide "
            "specific color codes: HEX (for web), RGB (for digital/screen), and "
            "CMYK (for print), and Pantone if applicable. Describe how each color "
            "should be used (e.g., primary colors for backgrounds or logo, "
            "secondary colors for accents or highlights) and any guidelines for "
            "maintaining sufficient contrast. This ensures consistency and "
            "accessibility in all uses of the brand’s colors."
        ),
    )
    typography: str = Field(
        ...,
        description=(
            "The brand’s typography guidelines, detailing the fonts and typefaces "
            "used. Identify the primary typeface(s) for headlines and body text, "
            "and any secondary fonts or alternatives (for instance, web-safe fonts "
            "if the primary fonts are not available). Include styles and usage "
            "hierarchy – for example, what font and size is used for headings, "
            "subheadings, body copy, and captions. If relevant, mention custom "
            "font licensing or any specific kerning, spacing, or alignment rules. "
            "The goal is to maintain a consistent typographic style across all "
            "materials."
        ),
    )
    iconography: str = Field(
        ...,
        description=(
            "Guidelines for iconography and graphic elements, if the brand uses "
            "them. Describe the style of icons or symbols (e.g., line icons vs. "
            "filled icons, rounded vs. sharp corners, simplistic vs. detailed) "
            "that match the brand's visual identity. Include any specific icon "
            "sets that are approved or custom icons that have been created for "
            "the brand. Provide rules for using icons consistently, such as stroke "
            "thickness, color usage for icons, and spacing. If the brand does not "
            "have a custom icon style or this is not relevant, this section can "
            "be marked as not applicable."
        ),
    )
    imagery_style: str = Field(
        ...,
        description=(
            "Guidelines for the style of imagery associated with the brand. "
            "Describe the overall look and feel of photographs and illustrations "
            "that fit the brand (e.g., bright and optimistic lifestyle photos, "
            "minimalist and flat illustrations, bold and high-contrast product "
            "images, etc.). Note any specific treatments (such as filters, color "
            "overlays) or subject matter that align with the brand. Include "
            "guidance on consistency in imagery – for instance, whether images "
            "should feel candid or staged, use natural light, feature certain "
            "topics or environments – and provide examples of approved imagery "
            "styles. If there are any prohibitions (e.g., no use of certain "
            "colors or themes in imagery), list those as well."
        ),
    )
    digital_presence: str = Field(
        ...,
        description=(
            "Standards for representing the brand in digital channels and platforms. "
            "Cover the guidelines for the company’s website (such as consistent "
            "use of brand elements in web design, like buttons, forms, and "
            "banners), as well as guidelines for social media presence (including "
            "profile images, cover photos, and the style of content posts). "
            "Mention how the brand should appear in email communications or "
            "newsletters (e.g., email signature format, email templates), and any "
            "other digital touchpoints like mobile apps or online advertisements. "
            "The goal is to ensure the brand looks and feels consistent across all "
            "online platforms."
        ),
    )
    application_examples: str = Field(
        ...,
        description=(
            "Examples of how the brand guidelines should be applied in real-world "
            "scenarios. Provide sample use-cases such as business cards, "
            "letterhead, advertisements, social media posts, website pages, or "
            "packaging that demonstrate the correct use of the logo, colors, "
            "typography, and tone. These examples serve as a visual reference to "
            "help users of the guidelines understand how to implement the brand "
            "elements consistently. Include both good examples (correct usage) "
            "and, if helpful, examples of incorrect usage to illustrate mistakes "
            "to avoid."
        ),
    )
    legal_considerations: str = Field(
        ...,
        description=(
            "Any legal guidelines or requirements related to the brand usage. This "
            "may include trademark usage rules (for example, when and how to use "
            "™ or ® symbols with the brand name), guidelines for third parties on "
            "using the brand assets, and any disclaimers that should accompany "
            "the brand’s content. If the brand’s industry has regulatory "
            "compliance needs (such as specific disclosures in financial or "
            "healthcare sectors), include those. Provide instructions on proper "
            "attribution for any licensed elements (like fonts or images) and "
            "note any prohibited uses of the brand that could violate "
            "intellectual property rights."
        ),
    )
    accessibility_standards: str = Field(
        ...,
        description=(
            "Guidelines to ensure the brand’s content and design are accessible "
            "to all individuals, including those with disabilities. Include any "
            "adherence to formal accessibility standards such as WCAG (Web Content "
            "Accessibility Guidelines) for digital content. Provide "
            "recommendations like maintaining high color contrast between text and "
            "background for readability, using sufficiently large and legible "
            "fonts, ensuring images and graphics have alternative text or "
            "captions, and designing interfaces that are navigable via keyboard "
            "or screen readers. Emphasize any brand-specific commitments to "
            "inclusivity, and ensure that all brand materials (digital or print) "
            "consider the needs of people with visual, auditory, motor, or "
            "cognitive disabilities."
        ),
    )


# ============================================================================
# SHARED COMPONENTS
# ============================================================================


def create_google_search_agent() -> Agent:
    """Create the Google search sub-agent used by all strategy agents."""
    return Agent(
        name="google_search_agent",
        model="gemini-2.5-flash",
        tools=[google_search],
        description="Expert web researcher that searches Google for public information",
        instruction="Search for relevant public information about the topic. Focus on official sources and recent data.",
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json"
        ),
    )


# ============================================================================
# 1. BUSINESS STRATEGY AGENT
# ============================================================================


def create_business_strategist(context: StrategyContext | None = None) -> Agent:
    """Create the business strategy strategist agent."""
    google_search_agent = create_google_search_agent()

    # Safely extract context information with proper None handling
    if context:
        company_name = context.company_name
        industry = context.industry
        new_information = format_new_information(
            company_name=context.company_name,
            websites=context.websites,
            industry=context.industry,
            customer_regions=context.customer_regions,
            annual_ad_budget=context.annual_ad_budget,
        )
    else:
        new_information = "No context provided"

    # Get instruction from Excel specification
    instruction = f"""
# ROLE & GOAL
You are a Strategic Marketing Expert. 
Your goal is to create a comprehensive business strategy document based on the provided information.

# CRITICAL DIRECTIVES & BOUNDARIES
1.  **ZERO FABRICATION:** Your primary directive is accuracy. You are strictly forbidden from inventing, guessing, assuming, or inferring any information that is not explicitly present in the provided source materials (uploaded documents, website, or credible search results).
2.  **ADMIT UNCERTAINTY:** If, after following the research process, you cannot find the information required for a specific field, you MUST insert the exact string: "requires further research". There are no exceptions to this rule.
3.  **SOURCE EVERYTHING:** Every piece of data you include MUST be attributable to a source. No information should exist without a corresponding reference.
4.  **JSON OUTPUT:** You MUST output a complete JSON strategy document that follows the defined output schema exactly.

# TOOLS
- google_search_agent: Uses Google search to find relevant information on the Internet

# YOUR TASK
You will receive several inputs in your conversation:
- BUSINESS INFORMATION: Details about the company to research and analyze

# PERSONA
You are an expert business consultant, meticulous in your analysis and precise in your writing. 
You ensure all outputs are professional, robust, and strictly adhere to provided guidelines. 
You are a critical thinker who can synthesize disparate information into a coherent strategic plan.

# PROCESS
You must follow this logic precisely:
1. **MANDATORY FIRST STEP - Check for Uploaded Strategy Documents:**
   - BEFORE using any search tools, you MUST check for uploaded documents
   - Look for a section titled "=== UPLOADED STRATEGY DOCUMENTS ===" in the initial message
   - These documents contain existing strategy information that you MUST use as your primary source
   - To access uploaded documents:
     a. Check the initial message for the "UPLOADED STRATEGY DOCUMENTS" section
     b. Each document is clearly marked with "--- Document: [name] ---"
     c. Documents with names starting with 'input_strategy_' contain strategy information
     d. Analyze EACH uploaded document thoroughly:
        - The document content is provided in full text format
        - Extract ALL relevant information from each document
   - From uploaded documents, extract and note:
     - Company's mission, vision, and values
     - Strategic goals and objectives
     - Key initiatives and priorities
     - Market positioning and differentiation
     - Financial targets and budgets
     - Competitor analysis
     - Customer segments and personas
     - Product/service offerings
     - Any other strategic insights
   - Use this extracted information as the PRIMARY SOURCE for your strategy
   - Only use search tools to fill gaps NOT covered in uploaded documents

2. **Analyze All Inputs:** After reviewing uploaded documents, analyze other inputs:
   - Review the query and all provided documents (`BUSINESS INFORMATION`)
   - Review the contents of the company websites `BUSINESS INFORMATION` section
   - Prioritize information from uploaded strategy documents over general web searches
   - Identify gaps that need to be filled through additional research

3. **Research Requirements (ONLY for gaps not covered in uploaded documents):**
   - **IMPORTANT**: Only research items NOT already covered in uploaded strategy documents
   - **MANDATORY**: Research each required field that wasn't found in uploaded documents
   - If information exists in uploaded documents, use that instead of searching
   - Use the `Google Search_agent` to search. Limit to 2 targeted search queries per section.
   - **EVALUATE SEARCH RESULTS CRITICALLY:** After searching, if you do not find a credible, specific source (e.g., a financial report, a company's official blog post, a reputable news article), you MUST conclude that the information is not available.
   - **MANDATORY FALLBACK:** If credible information is not found in uploaded documents, the provided website, or after two targeted search queries, you MUST insert the text: "requires further research". Do not attempt to synthesize an answer from vague or irrelevant search results.

4. **Create New Document**
   - Synthesize information prioritizing uploaded documents, then credible research findings.
   - **MANDATORY - FACT CHECKING:** For every single data point you add to the document, double-check that you have a direct source. If you cannot point to the exact sentence in a document or a specific URL, you must replace the data with "requires further research".
   - **MANDATORY**: Include references for all information, indicating source:
     - For uploaded document info: "Source: Uploaded strategy document '[document_name]'"
     - For searched info: Include the specific URL
   - Fill all required sections, using the directives above.

5. **Final Review and Formatting:**
   - This is the most critical step. Before providing your response, validate your entire draft against the required schema.
   - Ensure every section and field from the schema is properly filled.

# OUTPUT REQUIREMENTS
- Your response must be ONLY the complete JSON strategy document
- Your final output MUST be complete with some text entered for ALL sections.
- Only include accurate information that was found through your research or uploaded documents. If you cannot find information needed for a section, insert the text: "requires further research".
- The structure, sections, and formatting of your response MUST EXACTLY MATCH the defined output schema.
- For each top-level key in the final JSON, the value MUST be a single string. Synthesize the analysis of all required sub-topics for a given section into one cohesive narrative string. DO NOT use nested JSON objects.
- DO NOT include any conversational text, preambles, or explanations in your output. Your response should only be the document itself.
- DO NOT wrap your JSON output in markdown code blocks (```json...```). Return pure JSON only.

# EXAMPLE OUTPUT STRUCTURE
{{
    "businessStrategySummary": "Your text here...",
    "companyOverview": "Your text here...",
    "productsAndServices": "Your text here...",
    "marketAndIndustryAnalysis": "Your text here...",
    "swotAnalysis": "Your text here...",
    "externalEnvironmentAnalysisPESTEL": "Your text here...",
    "marketingAndCustomerStrategy": "Your text here...",
    "internalOperationsAndBusinessModel": "Your text here...",
    "financialPerformanceAndAnalysis": "Your text here...",
    "strategicRecommendationsAndFutureOutlook": "Your text here..."
}}

=== BEGIN INPUT DATA ===

BUSINESS INFORMATION:
{new_information}

=== END INPUT DATA ===

Based on the above inputs, create the complete Business Strategy document now.
"""

    agent = Agent(
        name="business_strategist",
        model="gemini-2.5-flash",
        tools=[AgentTool(agent=google_search_agent)],
        description="Strategic business expert that creates comprehensive business strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=16384,
            response_mime_type="application/json"
        ),
        output_key="business_strategy_doc",
        # Temporarily removed output_schema due to ADK issue with tools + output_schema
        # output_schema=BusinessStrategy,
    )

    # ADK handles output validation internally via output_schema parameter
    return agent


def create_business_reviewer() -> Agent:
    """Create the business strategy reviewer agent."""
    from .firestore import get_reviewer_guidelines_sync

    guidelines = get_reviewer_guidelines_sync("business_strategy")
    if not guidelines:
        logger.warning("Using default review guidelines for business_strategy")
        guidelines = (
            "Review the business strategy document for completeness and accuracy."
        )

    instruction = f"""
You are a Senior Strategy Reviewer. Review the business strategy document and provide specific feedback.

# DOCUMENT TO REVIEW
The business strategy document to review:
{{{{business_strategy_doc}}}}

# REVIEW GUIDELINES
{guidelines}

# YOUR TASK
1. Check if all required sections from the output schema are present
2. Verify information accuracy and completeness
3. Identify any gaps or areas needing improvement
4. Provide specific, actionable feedback

# OUTPUT FORMAT
Provide your review as a structured list of:
- Missing sections (if any)
- Incomplete areas needing more detail
- Specific improvements needed
- Quality assessment (1-10 score)

Be constructive and specific in your feedback.
"""

    return Agent(
        name="business_reviewer",
        model="gemini-2.5-flash",
        description="Reviews business strategy documents for quality and completeness",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json"
        ),
        
        output_key="review_feedback",
    )


def create_business_editor() -> Agent:
    """Create the business strategy editor agent."""
    google_search_agent = create_google_search_agent()

    instruction = """
You are a Strategy Document Editor. Based on the review feedback, improve the business strategy document.

# DOCUMENT TO EDIT
The business strategy document to improve:
{{{{business_strategy_doc}}}}

# REVIEW FEEDBACK
The feedback from the reviewer:
{{{{review_feedback}}}}

# YOUR TASK
1. Address each point of feedback from the reviewer
2. Use google_search_agent to find missing information
3. Enhance sections that need more detail
4. Ensure the final document meets all requirements

# OUTPUT FORMAT
Provide the complete, updated business strategy document in JSON format.
All feedback points must be addressed.

# EXAMPLE OUTPUT STRUCTURE
{{
    "businessStrategySummary": "Your text here...",
    "companyOverview": "Your text here...",
    "productsAndServices": "Your text here...",
    "marketAndIndustryAnalysis": "Your text here...",
    "swotAnalysis": "Your text here...",
    "externalEnvironmentAnalysisPESTEL": "Your text here...",
    "marketingAndCustomerStrategy": "Your text here...",
    "internalOperationsAndBusinessModel": "Your text here...",
    "financialPerformanceAndAnalysis": "Your text here...",
    "strategicRecommendationsAndFutureOutlook": "Your text here..."
}}
"""

    agent = Agent(
        name="business_editor",
        model="gemini-2.5-flash",
        tools=[AgentTool(agent=google_search_agent), exit_loop],
        description="Edits and improves business strategy documents based on feedback",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json"
        ),
        output_key="business_strategy_doc",
        # Temporarily removed output_schema due to ADK issue with tools + output_schema
        # output_schema=BusinessStrategy,
    )

    # ADK handles output validation internally via output_schema parameter
    return agent


def create_business_strategy_agent(
    context: StrategyContext | None = None,
) -> SequentialAgent:
    """Create the complete business strategy agent with refinement loop."""
    strategist = create_business_strategist(context)
    reviewer = create_business_reviewer()
    editor = create_business_editor()

    refinement_loop = LoopAgent(
        name="business_refinement_loop",
        sub_agents=[reviewer, editor],
        description="Refines business strategy through review cycles",
        max_iterations=1,
    )

    return SequentialAgent(
        name="business_strategy_agent",
        sub_agents=[strategist, refinement_loop],
        description="Creates comprehensive business strategy documents",
    )


# ============================================================================
# 2. COMPETITIVE STRATEGY AGENT
# ============================================================================


def create_competitive_strategist(context: StrategyContext | None = None) -> Agent:
    """Create the competitive strategy strategist agent."""
    google_search_agent = create_google_search_agent()

    # Safely extract context information with proper None handling
    if context:
        company_name = context.company_name
        industry = context.industry
        new_information = format_new_information(
            company_name=context.company_name,
            websites=context.websites,
            industry=context.industry,
            customer_regions=context.customer_regions,
            annual_ad_budget=context.annual_ad_budget,
        )
    else:
        new_information = "No context provided"

    # Build instruction that will access state at runtime
    instruction = f"""
# ROLE & GOAL
You are a Strategic Marketing Expert. 
Your goal is to create a comprehensive competitive strategy document based on the provided information.

# CRITICAL DIRECTIVES & BOUNDARIES
1.  **ZERO FABRICATION:** Your primary directive is accuracy. You are strictly forbidden from inventing, guessing, assuming, or inferring any information that is not explicitly present in the provided source materials (uploaded documents, website, or credible search results).
2.  **ADMIT UNCERTAINTY:** If, after following the research process, you cannot find the information required for a specific field, you MUST insert the exact string: "requires further research". There are no exceptions to this rule.
3.  **SOURCE EVERYTHING:** Every piece of data you include MUST be attributable to a source. No information should exist without a corresponding reference.
4.  **JSON OUTPUT:** You MUST output a complete JSON strategy document that follows the defined output schema exactly.

# TOOLS
- google_search_agent: Uses Google search to find relevant information on the Internet

# YOUR TASK
You will receive several inputs in your conversation:
- BUSINESS INFORMATION: Details about the company to research and analyze

# PRIOR ANALYSIS
Business Strategy Document (for reference):
{{{{business_strategy_doc}}}}

Review ONLY the relevant sections from the business strategy to ensure your competitive analysis aligns with and supports the overall business strategy.

# PERSONA
You are an expert business consultant, meticulous in your analysis and precise in your writing. 
You ensure all outputs are professional, robust, and strictly adhere to provided guidelines. 
You are a critical thinker who can synthesize disparate information into a coherent strategic plan.

# PROCESS
You must follow this logic precisely:
1. **MANDATORY FIRST STEP - Check for Uploaded Strategy Documents:**
   - BEFORE using any search tools, you MUST check for uploaded documents
   - Look for a section titled "=== UPLOADED STRATEGY DOCUMENTS ===" in the initial message
   - These documents contain existing strategy information that you MUST use as your primary source
   - To access uploaded documents:
     a. Check the initial message for the "UPLOADED STRATEGY DOCUMENTS" section
     b. Each document is clearly marked with "--- Document: [name] ---"
     c. Documents with names starting with 'input_strategy_' contain strategy information
     d. Analyze EACH uploaded document thoroughly:
        - The document content is provided in full text format
        - Extract ALL relevant information from each document
   - Extract competitive insights from uploaded documents:
     - Current competitive landscape analysis
     - Identified competitors and their positioning
     - Competitive advantages and differentiators
     - Market share and positioning goals
     - Pricing strategies and models
     - SWOT analysis if present
   - Use this extracted information as the PRIMARY SOURCE for your competitive analysis

2. **Review Prior Analysis:** After checking uploaded documents, review ONLY these specific sections from the business strategy document provided above:
   - businessStrategySummary
   - companyOverview
   - marketAndIndustryAnalysis
   - productsAndServices
   - swotAnalysis (especially competitors mentioned)

3. **Analyze All Inputs:** After reviewing uploaded documents and prior analysis:
   - Review the query and all provided documents (`BUSINESS INFORMATION`)
   - Review the contents of the company websites listed in the `BUSINESS INFORMATION` section
   - Prioritize information from uploaded strategy documents over general web searches
   - Identify competitive gaps that need additional research

4. **Research Requirements (ONLY for gaps not covered in uploaded documents):**
   - **IMPORTANT**: Only research items NOT already covered in uploaded strategy documents
   - **MANDATORY**: Research each required field that wasn't found in uploaded documents
   - If information exists in uploaded documents, use that instead of searching
   - Use the `Google Search_agent` to search. Limit to 2 targeted search queries per section.
   - **EVALUATE SEARCH RESULTS CRITICALLY:** After searching, if you do not find a credible, specific source (e.g., a financial report, a company's official blog post, a reputable news article), you MUST conclude that the information is not available.
   - **MANDATORY FALLBACK:** If credible information is not found in uploaded documents, the provided website, or after two targeted search queries, you MUST insert the text: "requires further research". Do not attempt to synthesize an answer from vague or irrelevant search results.

5. **Create New Document**
   - Synthesize information prioritizing uploaded documents, then credible research findings.
   - **MANDATORY - FACT CHECKING:** For every single data point you add to the document, double-check that you have a direct source. If you cannot point to the exact sentence in a document or a specific URL, you must replace the data with "requires further research".
   - **MANDATORY**: Include references for all information, indicating source:
     - For uploaded document info: "Source: Uploaded strategy document '[document_name]'"
     - For searched info: Include the specific URL
   - Fill all required sections, using the directives above.
   - If uploaded strategy documents were found, ensure your new strategy aligns with and builds upon the existing strategic direction

6. **Final Review and Formatting:**
   - This is the most critical step. Before providing your response, validate your entire draft against the required schema.
   - Ensure every section and field from the schema is properly filled.

# OUTPUT REQUIREMENTS
- Your response must be ONLY the complete JSON strategy document
- Your final output MUST be complete with some text entered for ALL sections.
- The structure, sections, and formatting of your response MUST EXACTLY MATCH the defined output schema.
- For each top-level key in the final JSON, the value MUST be a single string. Synthesize the analysis of all required sub-topics for a given section into one cohesive narrative string. DO NOT use nested JSON objects.
- DO NOT include any conversational text, preambles, or explanations in your output. Your response should only be the document itself.
- DO NOT wrap your JSON output in markdown code blocks (```json...```). Return pure JSON only.
- Only include accurate information that was found through your research or uploaded documents. If you cannot find information needed for a section, insert the text: "requires further research".

# EXAMPLE OUTPUT STRUCTURE
{{
    "competitiveStrategySummary": "Your text here...",
    "competitiveLandscape": "Your text here...",
    "detailedCompetitorProfiles": "Your text here...",
    "portersFiveForces": "Your text here...",
    "strategicRecommendations": "Your text here..."
}}
    
=== BEGIN INPUT DATA ===

BUSINESS INFORMATION:
{new_information}

=== END INPUT DATA ===

Create the complete Competitive Strategy document now.
"""

    agent = Agent(
        name="competitive_strategist",
        model="gemini-2.5-flash",
        tools=[AgentTool(agent=google_search_agent)],
        description="Competitive intelligence expert that creates detailed competitive analysis",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=16384,
            response_mime_type="application/json"
        ),
        
        output_key="competitive_strategy_doc",
        # Temporarily removed output_schema due to ADK issue with tools + output_schema
        # output_schema=CompetitiveAnalysis,
    )

    # ADK handles output validation internally via output_schema parameter
    return agent


def create_competitive_reviewer() -> Agent:
    """Create the competitive strategy reviewer agent."""
    from .firestore import get_reviewer_guidelines_sync

    guidelines = get_reviewer_guidelines_sync("competitive_strategy")
    if not guidelines:
        logger.warning("Using default review guidelines for competitive_strategy")
        guidelines = (
            "Review the competitive strategy document for completeness and accuracy."
        )

    instruction = f"""
You are a Senior Competitive Intelligence Reviewer. Review the competitive strategy document.

# DOCUMENT TO REVIEW
The competitive strategy document to review:
{{{{competitive_strategy_doc}}}}

# REVIEW GUIDELINES
{guidelines}

# YOUR TASK
1. Verify competitor identification is comprehensive
2. Check competitive analysis depth and accuracy
3. Assess strategic recommendations quality
4. Provide specific improvement feedback

# OUTPUT FORMAT
Provide structured feedback with:
- Missing competitors or analysis gaps
- Areas needing deeper analysis
- Strategic insights quality (1-10)
- Specific improvements needed
"""

    return Agent(
        name="competitive_reviewer",
        model="gemini-2.5-flash",
        description="Reviews competitive strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json"
        ),
        
        output_key="review_feedback",
    )


def create_competitive_editor() -> Agent:
    """Create the competitive strategy editor agent."""
    google_search_agent = create_google_search_agent()

    instruction = """
You are a Competitive Strategy Editor. Improve the document based on review feedback.

# CURRENT DOCUMENT
{{competitive_strategy_doc}}

# REVIEW FEEDBACK
{{review_feedback}}

# YOUR TASK
1. Address all reviewer feedback points
2. Research missing competitor information
3. Deepen analysis where needed
4. Enhance strategic recommendations

# OUTPUT FORMAT
Provide the complete, updated competitive strategy document in JSON format.

# EXAMPLE OUTPUT STRUCTURE
{{
    "competitiveStrategySummary": "Your text here...",
    "competitiveLandscape": "Your text here...",
    "detailedCompetitorProfiles": "Your text here...",
    "portersFiveForces": "Your text here...",
    "strategicRecommendations": "Your text here..."
}}
"""

    return Agent(
        name="competitive_editor",
        model="gemini-2.5-flash",
        tools=[AgentTool(agent=google_search_agent), exit_loop],
        description="Edits competitive strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json"
        ),
        
        output_key="competitive_strategy_doc",
        # Temporarily removed output_schema due to ADK issue with tools + output_schema
        # output_schema=CompetitiveAnalysis,
    )


def create_competitive_strategy_agent(
    context: StrategyContext | None = None,
) -> SequentialAgent:
    """Create the complete competitive strategy agent with refinement loop."""
    strategist = create_competitive_strategist(context)
    reviewer = create_competitive_reviewer()
    editor = create_competitive_editor()

    refinement_loop = LoopAgent(
        name="competitive_refinement_loop",
        sub_agents=[reviewer, editor],
        description="Refines competitive strategy through review cycles",
        max_iterations=1,
    )

    return SequentialAgent(
        name="competitive_strategy_agent",
        sub_agents=[strategist, refinement_loop],
        description="Creates comprehensive competitive strategy documents",
    )


# ============================================================================
# 3. CUSTOMER STRATEGY AGENT
# ============================================================================


def create_customer_strategist(context: StrategyContext | None = None) -> Agent:
    """Create the customer strategy strategist agent."""
    google_search_agent = create_google_search_agent()

    # Safely extract context information with proper None handling
    if context:
        company_name = context.company_name
        industry = context.industry
        new_information = format_new_information(
            company_name=context.company_name,
            websites=context.websites,
            industry=context.industry,
            customer_regions=context.customer_regions,
            annual_ad_budget=context.annual_ad_budget,
        )
    else:
        new_information = "No context provided"

    instruction = f"""
# ROLE & GOAL
You are a Strategic Marketing Expert. 
Your goal is to create a comprehensive customer strategy document based on the provided information.

# CRITICAL DIRECTIVES & BOUNDARIES
1.  **ZERO FABRICATION:** Your primary directive is accuracy. You are strictly forbidden from inventing, guessing, assuming, or inferring any information that is not explicitly present in the provided source materials (uploaded documents, website, or credible search results).
2.  **ADMIT UNCERTAINTY:** If, after following the research process, you cannot find the information required for a specific field, you MUST insert the exact string: "requires further research". There are no exceptions to this rule.
3.  **SOURCE EVERYTHING:** Every piece of data you include MUST be attributable to a source. No information should exist without a corresponding reference.
4.  **JSON OUTPUT:** You MUST output a complete JSON strategy document that follows the defined output schema exactly.

# TOOLS
- google_search_agent: Uses Google search to find relevant information on the Internet

# YOUR TASK
You will receive several inputs in your conversation:
- BUSINESS INFORMATION: Details about the company to research and analyze

# PRIOR ANALYSIS
Business Strategy Document (for reference):
{{{{business_strategy_doc}}}}

Competitive Strategy Document (for reference):
{{{{competitive_strategy_doc}}}}

Review ONLY the relevant sections from prior strategies to ensure your customer strategy aligns with and differentiates from competitors.

# PERSONA
You are an expert business consultant, meticulous in your analysis and precise in your writing. 
You ensure all outputs are professional, robust, and strictly adhere to provided guidelines. 
You are a critical thinker who can synthesize disparate information into a coherent strategic plan.

# PROCESS
You must follow this logic precisely:
1. **MANDATORY FIRST STEP - Check for Uploaded Strategy Documents:**
   - BEFORE using any search tools, you MUST check for uploaded documents
   - Look for a section titled "=== UPLOADED STRATEGY DOCUMENTS ===" in the initial message
   - These documents contain existing strategy information that you MUST use as your primary source
   - To access uploaded documents:
     a. Check the initial message for the "UPLOADED STRATEGY DOCUMENTS" section
     b. Each document is clearly marked with "--- Document: [name] ---"
     c. Documents with names starting with 'input_strategy_' contain strategy information
     d. Analyze EACH uploaded document thoroughly:
        - The document content is provided in full text format
        - Extract ALL relevant information from each document
            # Extract ALL customer-relevant information from this document
   - Extract customer insights from uploaded documents:
     - Customer segments and personas
     - Customer needs and pain points
     - Customer journey mapping
     - Customer acquisition strategies
     - Customer retention strategies
     - Customer satisfaction metrics
   - Use this extracted information as the PRIMARY SOURCE for your customer strategy

2. **Review Prior Analysis:** After checking uploaded documents, review ONLY these specific sections from prior documents:
   
   From business_strategy_doc:
   - businessStrategySummary
   - companyOverview  
   - productsAndServices
   - marketingAndCustomerStrategy
   
   From competitive_strategy_doc:
   - competitiveLandscape
   - competitiveStrategySummary
   - detailedCompetitorProfiles (focus on differentiators)
   
   DO NOT read the entire documents. Focus only on these sections to understand customer context and positioning.

3. **Analyze All Inputs:** After reviewing uploaded documents and prior analyses:
   - Review the query and all provided documents (`BUSINESS INFORMATION`)
   - Review the contents of the company websites `BUSINESS INFORMATION` section
   - Prioritize information from uploaded strategy documents over general web searches

4. **Research Requirements (ONLY for gaps not covered in uploaded documents):**
   - **IMPORTANT**: Only research items NOT already covered in uploaded strategy documents
   - **MANDATORY**: Research each required field that wasn't found in uploaded documents
   - If information exists in uploaded documents, use that instead of searching
   - Use the `Google Search_agent` to search. Limit to 2 targeted search queries per section.
   - **EVALUATE SEARCH RESULTS CRITICALLY:** After searching, if you do not find a credible, specific source (e.g., a financial report, a company's official blog post, a reputable news article), you MUST conclude that the information is not available.
   - **MANDATORY FALLBACK:** If credible information is not found in uploaded documents, the provided website, or after two targeted search queries, you MUST insert the text: "requires further research". Do not attempt to synthesize an answer from vague or irrelevant search results.

5. **Create New Document**
   - Synthesize information prioritizing uploaded documents, then credible research findings.
   - **MANDATORY - FACT CHECKING:** For every single data point you add to the document, double-check that you have a direct source. If you cannot point to the exact sentence in a document or a specific URL, you must replace the data with "requires further research".
   - **MANDATORY**: Include references for all information, indicating source:
     - For uploaded document info: "Source: Uploaded strategy document '[document_name]'"
     - For searched info: Include the specific URL
   - Fill all required sections, using the directives above.

6. **Final Review and Formatting:**
   - This is the most critical step. Before providing your response, validate your entire draft against the required schema.
   - Ensure every section and field from the schema is properly filled.

# OUTPUT REQUIREMENTS
- Your response must be ONLY the complete JSON strategy document
- Your final output MUST be complete with some text entered for ALL sections.
- The structure, sections, and formatting of your response MUST EXACTLY MATCH the defined output schema.
- For each top-level key in the final JSON, the value MUST be a single string. Synthesize the analysis of all required sub-topics for a given section into one cohesive narrative string. DO NOT use nested JSON objects.
- DO NOT include any conversational text, preambles, or explanations in your output. Your response should only be the document itself.
- DO NOT wrap your JSON output in markdown code blocks (```json...```). Return pure JSON only.
- Only include accurate information that was found through your research or uploaded documents. If you cannot find information needed for a section, insert the text: "requires further research".

# EXAMPLE OUTPUT STRUCTURE
{{
    "customerJourneySummary": "Your text here...",
    "idealCustomerProfiles": "Your text here...",
    "customerNeedsAnalysis": "Your text here...",
    "awarenessPhase": "Your text here...",
    "considerationPhase": "Your text here...",
    "conversionPhase": "Your text here...",
    "loyaltyPhase": "Your text here..."
}}

=== BEGIN INPUT DATA ===

BUSINESS INFORMATION:
{new_information}

=== END INPUT DATA ===

Create the complete Customer Strategy document now.
"""

    agent = Agent(
        name="customer_strategist",
        model="gemini-2.5-flash",
        tools=[AgentTool(agent=google_search_agent)],
        description="Customer insights expert that creates detailed customer strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=16384,
            response_mime_type="application/json"
        ),
        
        output_key="customer_strategy_doc",
        # Temporarily removed output_schema due to ADK issue with tools + output_schema
        # output_schema=CustomerJourneyAnalysis,
    )

    # ADK handles output validation internally via output_schema parameter
    return agent


def create_customer_reviewer() -> Agent:
    """Create the customer strategy reviewer agent."""
    from .firestore import get_reviewer_guidelines_sync

    guidelines = get_reviewer_guidelines_sync("customer_strategy")
    if not guidelines:
        logger.warning("Using default review guidelines for customer_strategy")
        guidelines = (
            "Review the customer strategy document for completeness and accuracy."
        )

    instruction = f"""
You are a Senior Customer Experience Reviewer. Review the customer strategy document.

# DOCUMENT TO REVIEW
The customer strategy document to review:
{{{{customer_strategy_doc}}}}

# REVIEW GUIDELINES
{guidelines}

# YOUR TASK
1. Verify customer segmentation completeness
2. Check persona development quality
3. Assess journey mapping accuracy
4. Review engagement strategy effectiveness

# OUTPUT FORMAT
Provide structured feedback with:
- Missing customer insights
- Persona development gaps
- Journey mapping improvements
- Quality score (1-10)
"""

    return Agent(
        name="customer_reviewer",
        model="gemini-2.5-flash",
        description="Reviews customer strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json"
        ),
        
        output_key="review_feedback",
    )


def create_customer_editor() -> Agent:
    """Create the customer strategy editor agent."""
    google_search_agent = create_google_search_agent()

    instruction = """
You are a Customer Strategy Editor. Improve the document based on review feedback.

# CURRENT DOCUMENT
{{customer_strategy_doc}}

# REVIEW FEEDBACK
{{review_feedback}}

# YOUR TASK
1. Address all feedback points
2. Research missing customer insights
3. Enhance personas and journey maps
4. Strengthen engagement strategies

# OUTPUT FORMAT
Provide the complete, updated customer strategy document in JSON format.

# EXAMPLE OUTPUT STRUCTURE
{{
    "customerJourneySummary": "Your text here...",
    "idealCustomerProfiles": "Your text here...",
    "customerNeedsAnalysis": "Your text here...",
    "awarenessPhase": "Your text here...",
    "considerationPhase": "Your text here...",
    "conversionPhase": "Your text here...",
    "loyaltyPhase": "Your text here..."
}}
"""

    return Agent(
        name="customer_editor",
        model="gemini-2.5-flash",
        tools=[AgentTool(agent=google_search_agent), exit_loop],
        description="Edits customer strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json"
        ),
        
        output_key="customer_strategy_doc",
        # Temporarily removed output_schema due to ADK issue with tools + output_schema
        # output_schema=CustomerJourneyAnalysis,
    )


def create_customer_strategy_agent(
    context: StrategyContext | None = None,
) -> SequentialAgent:
    """Create the complete customer strategy agent with refinement loop."""
    strategist = create_customer_strategist(context)
    reviewer = create_customer_reviewer()
    editor = create_customer_editor()

    refinement_loop = LoopAgent(
        name="customer_refinement_loop",
        sub_agents=[reviewer, editor],
        description="Refines customer strategy through review cycles",
        max_iterations=1,
    )

    return SequentialAgent(
        name="customer_strategy_agent",
        sub_agents=[strategist, refinement_loop],
        description="Creates comprehensive customer strategy documents",
    )


# ============================================================================
# 4. MARKETING STRATEGY AGENT
# ============================================================================


def create_marketing_strategist(context: StrategyContext | None = None) -> Agent:
    """Create the marketing strategy strategist agent."""
    google_search_agent = create_google_search_agent()

    # Safely extract context information with proper None handling
    if context:
        company_name = context.company_name
        industry = context.industry
        new_information = format_new_information(
            company_name=context.company_name,
            websites=context.websites,
            industry=context.industry,
            customer_regions=context.customer_regions,
            annual_ad_budget=context.annual_ad_budget,
        )
    else:
        new_information = "No context provided"

    # Define the output schema
    instruction = f"""
# ROLE & GOAL
You are a Strategic Marketing Expert. 
Your goal is to create a comprehensive marketing strategy document based on the provided information.

# CRITICAL DIRECTIVES & BOUNDARIES
1.  **ZERO FABRICATION:** Your primary directive is accuracy. You are strictly forbidden from inventing, guessing, assuming, or inferring any information that is not explicitly present in the provided source materials (uploaded documents, website, or credible search results).
2.  **ADMIT UNCERTAINTY:** If, after following the research process, you cannot find the information required for a specific field, you MUST insert the exact string: "requires further research". There are no exceptions to this rule.
3.  **SOURCE EVERYTHING:** Every piece of data you include MUST be attributable to a source. No information should exist without a corresponding reference.
4.  **JSON OUTPUT:** You MUST output a complete JSON strategy document that follows the defined output schema exactly.

# TOOLS
- google_search_agent: Uses Google search to find relevant information on the Internet

# YOUR TASK
You will receive several inputs in your conversation:
- BUSINESS INFORMATION: Details about the company to research and analyze

# PRIOR ANALYSIS
Business Strategy Document (for reference):
{{{{business_strategy_doc}}}}

Competitive Strategy Document (for reference):
{{{{competitive_strategy_doc}}}}

Customer Strategy Document (for reference):
{{customer_strategy_doc}}

Review ONLY the relevant sections from prior strategies to ensure your marketing strategy effectively targets and engages the defined customer segments.

# PERSONA
You are an expert business consultant, meticulous in your analysis and precise in your writing. 
You ensure all outputs are professional, robust, and strictly adhere to provided guidelines. 
You are a critical thinker who can synthesize disparate information into a coherent strategic plan.

# PROCESS
You must follow this logic precisely:
1. **MANDATORY FIRST STEP - Check for Uploaded Strategy Documents:**
   - BEFORE using any search tools, you MUST check for uploaded documents
   - Look for a section titled "=== UPLOADED STRATEGY DOCUMENTS ===" in the initial message
   - These documents contain existing strategy information that you MUST use as your primary source
   - To access uploaded documents:
     a. Check the initial message for the "UPLOADED STRATEGY DOCUMENTS" section
     b. Each document is clearly marked with "--- Document: [name] ---"
     c. Documents with names starting with 'input_strategy_' contain strategy information
     d. Analyze EACH uploaded document thoroughly:
        - The document content is provided in full text format
        - Extract ALL relevant information from each document
            # Extract ALL marketing-relevant information from this document
   - Extract marketing insights from uploaded documents:
     - Marketing objectives and KPIs
     - Target audience definitions
     - Marketing channels and tactics
     - Budget allocations
     - Campaign plans
     - Brand messaging and positioning
   - Use this extracted information as the PRIMARY SOURCE for your marketing strategy

2. **Review Prior Analysis:** After checking uploaded documents, review ONLY these specific sections from prior documents:
   
   From business_strategy_doc:
   - businessStrategySummary
   - productsAndServices  
   - marketingAndCustomerStrategy
   
   From competitive_strategy_doc:
   - competitiveLandscape
   - competitiveStrategySummary
   
   From customer_strategy_doc:
   - idealCustomerProfiles
   - customerNeedsAnalysis
   - awarenessPhase
   - considerationPhase
   - conversionPhase
   - loyaltyPhase
   
   DO NOT read the entire documents. Focus only on these sections to create targeted marketing strategies.

3. **Analyze All Inputs:** After reviewing uploaded documents and prior analyses:
   - Review the query and all provided documents (`BUSINESS INFORMATION`)
   - Review the contents of the company websites `BUSINESS INFORMATION` section
   - Prioritize information from uploaded strategy documents over general web searches

4. **Research Requirements (ONLY for gaps not covered in uploaded documents):**
   - **IMPORTANT**: Only research items NOT already covered in uploaded strategy documents
   - **MANDATORY**: Research each required field that wasn't found in uploaded documents
   - If information exists in uploaded documents, use that instead of searching
   - Use the `Google Search_agent` to search. Limit to 2 targeted search queries per section.
   - **EVALUATE SEARCH RESULTS CRITICALLY:** After searching, if you do not find a credible, specific source (e.g., a financial report, a company's official blog post, a reputable news article), you MUST conclude that the information is not available.
   - **MANDATORY FALLBACK:** If credible information is not found in uploaded documents, the provided website, or after two targeted search queries, you MUST insert the text: "requires further research". Do not attempt to synthesize an answer from vague or irrelevant search results.

5. **Create New Document**
   - Synthesize information prioritizing uploaded documents, then credible research findings.
   - **MANDATORY - FACT CHECKING:** For every single data point you add to the document, double-check that you have a direct source. If you cannot point to the exact sentence in a document or a specific URL, you must replace the data with "requires further research".
   - **MANDATORY**: Include references for all information, indicating source:
     - For uploaded document info: "Source: Uploaded strategy document '[document_name]'"
     - For searched info: Include the specific URL
   - Fill all required sections, using the directives above.

6. **Final Review and Formatting:**
   - This is the most critical step. Before providing your response, validate your entire draft against the required schema.
   - Ensure every section and field from the schema is properly filled.

# OUTPUT REQUIREMENTS
- Your response must be ONLY the complete JSON strategy document.
- Your final output MUST be complete with some text entered for ALL sections.
- The structure, sections, and formatting of your response MUST EXACTLY MATCH the defined output schema.
- For each top-level key in the final JSON, the value MUST be a single string. Synthesize the analysis of all required sub-topics for a given section into one cohesive narrative string. DO NOT use nested JSON objects.
- DO NOT include any conversational text, preambles, or explanations in your output. Your response should only be the document itself.
- DO NOT wrap your JSON output in markdown code blocks (```json...```). Return pure JSON only.
- Only include accurate information that was found through your research or uploaded documents. If you cannot find information needed for a section, insert the text: "requires further research".

# EXAMPLE OUTPUT STRUCTURE
{{
    "marketingStrategySummary": "Your text here...",
    "awarenessStrategy": "Your text here...",
    "considerationStrategy": "Your text here...",
    "conversionStrategy": "Your text here...",
    "loyaltyStrategy": "Your text here..."
}}

=== BEGIN INPUT DATA ===

BUSINESS INFORMATION:
{new_information}

=== END INPUT DATA ===

Create the complete Marketing Strategy document now.

"""

    agent = Agent(
        name="marketing_strategist",
        model="gemini-2.5-flash",
        tools=[AgentTool(agent=google_search_agent)],
        description="Marketing strategy expert that creates comprehensive marketing plans",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=16384,
            response_mime_type="application/json"
        ),
        # Temporarily removed output_schema due to ADK issue with tools + output_schema
        # output_schema=MarketingStrategy,
        output_key="marketing_strategy_doc",
    )

    # ADK handles output validation internally via output_schema parameter
    return agent


def create_marketing_reviewer() -> Agent:
    """Create the marketing strategy reviewer agent."""
    from .firestore import get_reviewer_guidelines_sync

    guidelines = get_reviewer_guidelines_sync("marketing_strategy")
    if not guidelines:
        logger.warning("Using default review guidelines for marketing_strategy")
        guidelines = (
            "Review the marketing strategy document for completeness and accuracy."
        )

    instruction = f"""
You are a Senior Marketing Reviewer. Review the marketing strategy document.

# DOCUMENT TO REVIEW
The marketing strategy document to review:
{{marketing_strategy_doc}}


# REVIEW GUIDELINES
{guidelines}

# YOUR TASK
1. Verify marketing objectives clarity
2. Check channel strategy effectiveness
3. Assess campaign planning quality
4. Review budget allocation logic

# OUTPUT FORMAT
Provide structured feedback with:
- Missing marketing elements
- Channel strategy gaps
- Campaign planning improvements
- Quality score (1-10)
"""

    return Agent(
        name="marketing_reviewer",
        model="gemini-2.5-flash",
        description="Reviews marketing strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json"
        ),
        
        output_key="review_feedback",
    )


def create_marketing_editor() -> Agent:
    """Create the marketing strategy editor agent."""
    google_search_agent = create_google_search_agent()

    instruction = """
You are a Marketing Strategy Editor. Improve the document based on review feedback.

# CURRENT DOCUMENT
{{marketing_strategy_doc}}

# REVIEW FEEDBACK
{{review_feedback}}


# YOUR TASK
1. Address all feedback points
2. Research marketing best practices
3. Enhance channel and campaign strategies
4. Optimize budget recommendations

# OUTPUT FORMAT
Provide the complete, updated marketing strategy document in JSON format.

# EXAMPLE OUTPUT STRUCTURE
{{
    "marketingStrategySummary": "Your text here...",
    "awarenessStrategy": "Your text here...",
    "considerationStrategy": "Your text here...",
    "conversionStrategy": "Your text here...",
    "loyaltyStrategy": "Your text here..."
}}
"""

    return Agent(
        name="marketing_editor",
        model="gemini-2.5-flash",
        tools=[AgentTool(agent=google_search_agent), exit_loop],
        description="Edits marketing strategy documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json"
        ),
        
        output_key="marketing_strategy_doc",
        # Temporarily removed output_schema due to ADK issue with tools + output_schema
        # output_schema=MarketingStrategy,
    )


def create_marketing_strategy_agent(
    context: StrategyContext | None = None,
) -> SequentialAgent:
    """Create the complete marketing strategy agent with refinement loop."""
    strategist = create_marketing_strategist(context)
    reviewer = create_marketing_reviewer()
    editor = create_marketing_editor()

    refinement_loop = LoopAgent(
        name="marketing_refinement_loop",
        sub_agents=[reviewer, editor],
        description="Refines marketing strategy through review cycles",
        max_iterations=1,
    )

    return SequentialAgent(
        name="marketing_strategy_agent",
        sub_agents=[strategist, refinement_loop],
        description="Creates comprehensive marketing strategy documents",
    )


# ============================================================================
# 5. BRAND GUIDELINES AGENT
# ============================================================================


def create_brand_strategist(context: StrategyContext | None = None) -> Agent:
    """Create the brand guidelines strategist agent."""
    google_search_agent = create_google_search_agent()

    # Safely extract context information with proper None handling
    if context:
        new_information = format_new_information(
            company_name=context.company_name,
            websites=context.websites,
            industry=context.industry,
            customer_regions=context.customer_regions,
            annual_ad_budget=context.annual_ad_budget,
        )
    else:
        new_information = "No context provided"

    instruction = f"""
# ROLE & GOAL
You are a Brand Strategy Expert creating comprehensive brand guidelines.

# CRITICAL DIRECTIVES & BOUNDARIES
1.  **ZERO FABRICATION:** Your primary directive is accuracy. You are strictly forbidden from inventing, guessing, assuming, or inferring any information that is not explicitly present in the provided source materials (uploaded documents, website, or credible search results).
2.  **ADMIT UNCERTAINTY:** If, after following the research process, you cannot find the information required for a specific field, you MUST insert the exact string: "requires further research". There are no exceptions to this rule.
3.  **SOURCE EVERYTHING:** Every piece of data you include MUST be attributable to a source. No information should exist without a corresponding reference.
4.  **JSON OUTPUT:** You MUST output a complete JSON strategy document that follows the defined output schema exactly.

# TOOLS
- google_search_agent: Research brand positioning and industry standards

# YOUR TASK
Your task is to analyze the provided website(s) to document a company's existing brand guidelines.
The BUSINESS INFORMATION may provide you with additional information about the business and its brand.

# PROCESS
You must follow this logic precisely:
1. **MANDATORY FIRST STEP - Check for Uploaded Strategy Documents:**
   - BEFORE using any search tools, you MUST check for uploaded documents
   - Look for a section titled "=== UPLOADED STRATEGY DOCUMENTS ===" in the initial message
   - These documents contain existing strategy information that you MUST use as your primary source
   - To access uploaded documents:
     a. Check the initial message for the "UPLOADED STRATEGY DOCUMENTS" section
     b. Each document is clearly marked with "--- Document: [name] ---"
     c. Documents with names starting with 'input_strategy_' contain strategy information
     d. Analyze EACH uploaded document thoroughly:
        - The document content is provided in full text format
        - Extract ALL relevant information from each document
            # Extract ALL brand-relevant information from this document
   - Extract brand insights from uploaded documents:
     - Brand mission, vision, and values
     - Brand personality and voice
     - Visual identity guidelines
     - Logo usage and specifications
     - Color palettes and typography
     - Brand messaging frameworks
   - Use this extracted information as the PRIMARY SOURCE for your brand guidelines

2. **Analyze All Inputs:** After reviewing uploaded documents:
   - Review the provided documents (`BUSINESS INFORMATION`)
   - Review the contents of the company websites `BUSINESS INFORMATION` section
   - Prioritize information from uploaded strategy documents over general web searches

3. **Research Requirements (ONLY for gaps not covered in uploaded documents):**
   - **IMPORTANT**: Only research items NOT already covered in uploaded strategy documents
   - **MANDATORY**: Research each required field that wasn't found in uploaded documents
   - If information exists in uploaded documents, use that instead of searching
   - Use the `Google Search_agent` to search. Limit to 2 targeted search queries per section.
   - **EVALUATE SEARCH RESULTS CRITICALLY:** After searching, if you do not find a credible, specific source (e.g., a financial report, a company's official blog post, a reputable news article), you MUST conclude that the information is not available.
   - **MANDATORY FALLBACK:** If credible information is not found in uploaded documents, the provided website, or after two targeted search queries, you MUST insert the text: "requires further research". Do not attempt to synthesize an answer from vague or irrelevant search results.

4. **Create New Document**
   - Synthesize information prioritizing uploaded documents, then credible research findings.
   - **MANDATORY - FACT CHECKING:** For every single data point you add to the document, double-check that you have a direct source. If you cannot point to the exact sentence in a document or a specific URL, you must replace the data with "requires further research".
   - **MANDATORY**: Include references for all information, indicating source:
     - For uploaded document info: "Source: Uploaded strategy document '[document_name]'"
     - For searched info: Include the specific URL
   - Fill all required sections, using the directives above.

5. **Final Review and Formatting:**
   - This is the most critical step. Before providing your response, validate your entire draft against the required schema.
   - Ensure every section and field from the schema is properly filled.

# OUTPUT REQUIREMENTS
- Your response must be ONLY the complete JSON strategy document.
- Your final output MUST be complete with some text entered for ALL sections.
- The structure, sections, and formatting of your response MUST EXACTLY MATCH the defined output schema.
- For each top-level key in the final JSON, the value MUST be a single string. Synthesize the analysis of all required sub-topics for a given section into one cohesive narrative string. DO NOT use nested JSON objects.
- DO NOT include any conversational text, preambles, or explanations in your output. Your response should only be the document itself.
- DO NOT wrap your JSON output in markdown code blocks (```json...```). Return pure JSON only.
- Only include accurate information that was found through your research or uploaded documents. If you cannot find information needed for a section, insert the text: "requires further research".

# EXAMPLE OUTPUT STRUCTURE
{{
    "brand_name": "Your text here...",
    "tagline": "Your text here...",
    "brand_overview": "Your text here...",
    "brand_story": "Your text here...",
    "value_proposition": "Your text here...",
    "brand_personality": "Your text here...",
    "brand_voice_and_tone": "Your text here...",
    "logo_guidelines": "Your text here...",
    "color_palette": "Your text here...",
    "typography": "Your text here...",
    "iconography": "Your text here...",
    "imagery_style": "Your text here...",
    "digital_presence": "Your text here...",
    "application_examples": "Your text here...",
    "legal_considerations": "Your text here...",
    "accessibility_standards": "Your text here..."
}}

=== BEGIN INPUT DATA ===

BUSINESS INFORMATION:
{new_information}

=== END INPUT DATA ===

Based on the above inputs, create the complete Brand Guidelines document now.
"""

    agent = Agent(
        name="brand_strategist",
        model="gemini-2.5-flash",
        tools=[AgentTool(agent=google_search_agent)],
        description="Brand strategy expert that creates comprehensive brand guidelines",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=16384,
            response_mime_type="application/json"
        ),
        
        output_key="brand_guidelines_doc",
        # Temporarily removed output_schema due to ADK issue with tools + output_schema
        # output_schema=BrandGuidelines,
    )

    # ADK handles output validation internally via output_schema parameter
    return agent


def create_brand_reviewer() -> Agent:
    """Create the brand guidelines reviewer agent."""
    from .firestore import get_reviewer_guidelines_sync

    guidelines = get_reviewer_guidelines_sync("brand_guidelines")
    if not guidelines:
        logger.warning("Using default review guidelines for brand_guidelines")
        guidelines = "Review the brand guidelines for completeness and consistency."

    instruction = f"""
You are a Senior Brand Reviewer. Review the brand guidelines document.

# DOCUMENT TO REVIEW
The brand guidelines document to review:
{{brand_guidelines_doc}}


# REVIEW GUIDELINES
{guidelines}

# YOUR TASK
1. Verify brand identity completeness
2. Check voice and tone consistency
3. Assess visual guidelines quality
4. Review usage standards clarity

# OUTPUT FORMAT
Provide structured feedback with:
- Missing brand elements
- Consistency issues
- Guidelines clarity improvements
- Quality score (1-10)
"""

    return Agent(
        name="brand_reviewer",
        model="gemini-2.5-flash",
        description="Reviews brand guidelines documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json"
        ),
        
        output_key="review_feedback",
    )


def create_brand_editor() -> Agent:
    """Create the brand guidelines editor agent."""
    google_search_agent = create_google_search_agent()

    instruction = """
You are a Brand Guidelines Editor. Improve the document based on review feedback.

# CURRENT DOCUMENT
{{brand_guidelines_doc}}

# REVIEW FEEDBACK
{{review_feedback}}


# YOUR TASK
1. Address all feedback points
2. Research brand best practices
3. Enhance brand standards clarity
4. Ensure comprehensive coverage

# OUTPUT FORMAT
Provide the complete, updated brand guidelines document in JSON format.

# EXAMPLE OUTPUT STRUCTURE
{{
    "brand_name": "Your text here...",
    "tagline": "Your text here...",
    "brand_overview": "Your text here...",
    "brand_story": "Your text here...",
    "value_proposition": "Your text here...",
    "brand_personality": "Your text here...",
    "brand_voice_and_tone": "Your text here...",
    "logo_guidelines": "Your text here...",
    "color_palette": "Your text here...",
    "typography": "Your text here...",
    "iconography": "Your text here...",
    "imagery_style": "Your text here...",
    "digital_presence": "Your text here...",
    "application_examples": "Your text here...",
    "legal_considerations": "Your text here...",
    "accessibility_standards": "Your text here..."
}}
"""

    return Agent(
        name="brand_editor",
        model="gemini-2.5-flash",
        tools=[AgentTool(agent=google_search_agent), exit_loop],
        description="Edits brand guidelines documents",
        instruction=instruction,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json"
        ),
        
        output_key="brand_guidelines_doc",
        # Temporarily removed output_schema due to ADK issue with tools + output_schema
        # output_schema=BrandGuidelines,
    )


def create_brand_guidelines_agent(
    context: StrategyContext | None = None,
) -> SequentialAgent:
    """Create the complete brand guidelines agent with refinement loop."""
    strategist = create_brand_strategist(context)
    reviewer = create_brand_reviewer()
    editor = create_brand_editor()

    refinement_loop = LoopAgent(
        name="brand_refinement_loop",
        sub_agents=[reviewer, editor],
        description="Refines brand guidelines through review cycles",
        max_iterations=1,
    )

    return SequentialAgent(
        name="brand_guidelines_agent",
        sub_agents=[strategist, refinement_loop],
        description="Creates comprehensive brand guidelines documents",
    )
