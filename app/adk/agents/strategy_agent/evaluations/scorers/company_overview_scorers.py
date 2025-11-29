"""
Company Overview Scorers

Scorers for evaluating company_overview_summary quality.

Original scorer implementations by Yafet Tamene.
Downloaded from W&B Weave and adapted for local use.
"""

import json
import logging
import os
from pydantic import BaseModel
import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel
import weave


logger = logging.getLogger(__name__)


class ProductServiceAssessment(BaseModel):
    """Schema for product/service assessment"""

    describes_product_or_service: str
    reasoning: str


class ScorerAssessment(BaseModel):
    """Schema for general scorer assessment"""

    passes: str
    reasoning: str


class CompanyOverviewLengthScorer(weave.Scorer):
    """Scores company overview based on character count (800-4000 chars)."""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        Score the output based on character count.

        Weave passes the full model output dict to `output` parameter.
        We extract 'company_overview_summary' from it.

        Args:
            output: Model output dict containing 'company_overview_summary'

        Returns:
            dict with score (1 if in range, 0 otherwise)
        """
        try:
            # Extract company_overview_summary from model output
            company_overview_summary = output.get('company_overview_summary', '')

            char_count = len(company_overview_summary)
            score = 1 if 800 <= char_count <= 4000 else 0

            return {
                'score': score,
                'char_count': char_count,
            }
        except Exception as e:
            logger.error(f"Error in length scorer: {e}")
            return {'score': 0, 'error': str(e)}


class ProductServiceDescriptionScorer(weave.Scorer):
    """LLM judge: Does the summary describe the product/service offered?"""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        LLM judge: Does the summary describe the product/service offered?

        Args:
            output: Model output dict containing 'company_overview_summary'

        Returns:
            dict with score (1 for yes, 0 for no)
        """
        try:
            # Extract company_overview_summary from model output
            company_overview_summary = output.get('company_overview_summary', '')

            # Skip if empty
            if not company_overview_summary:
                return {
                    'score': 0,
                    'assessment': 'no',
                    'reasoning': 'Empty or missing summary',
                }

            # Initialize Vertex AI (uses ADC automatically)
            vertexai.init(
                project=os.getenv('GOOGLE_CLOUD_PROJECT', 'ken-e-dev'),
                location=os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1'),
            )

            # Configure Gemini via Vertex AI
            model = GenerativeModel('gemini-2.5-pro')

            prompt = f"""You are evaluating a company overview summary.

Your task: Determine if the summary explicitly describes CURRENT products or services offered by the company.

Company Overview Summary:
{company_overview_summary}

Question: Does this summary explicitly state specific products/services the company CURRENTLY offers?

PASS criteria (any of these):
- Names specific products: "checking accounts, mortgages, credit cards"
- Lists multiple service categories: "wide range of banking, investment, and wealth management services"
- Describes concrete offerings: "cloud storage, machine learning APIs"

FAIL criteria:
- Single generic category only: "financial services", "technology solutions"
- Historical products no longer offered: "pioneered BankAmericard" (unless stated as current)
- Inferred from context: "operates branches" (doesn't explicitly state what products)
- Industry label only: "banking institution" with no product details

Requirement: Summary must EXPLICITLY mention current products/services with sufficient specificity (either named products OR multiple service categories).

Provide your assessment as JSON with:
- describes_product_or_service: "yes" or "no"
- reasoning: Brief explanation
"""

            generation_config = GenerationConfig(
                temperature=0.1,
                max_output_tokens=2500,
                response_mime_type="application/json",
                response_schema=ProductServiceAssessment.model_json_schema(),
            )

            response = model.generate_content(prompt, generation_config=generation_config)
            assessment = json.loads(response.text)

            # Convert yes/no to 1/0
            score = 1 if assessment['describes_product_or_service'] == 'yes' else 0

            return {
                'score': score,
                'reasoning': assessment['reasoning'],
            }

        except Exception as e:
            logger.error(f"Error in LLM judge scorer: {e}")
            return {'score': 0, 'error': str(e)}


class FoundingDateScorer(weave.Scorer):
    """LLM judge: Does the summary mention founding date or age?"""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        LLM judge: Does the summary mention founding date or age?

        Args:
            output: Model output dict containing 'company_overview_summary'

        Returns:
            dict with score (1 for yes, 0 for no) and reasoning
        """
        try:
            company_overview_summary = output.get('company_overview_summary', '')

            if not company_overview_summary:
                return {'score': 0, 'reasoning': 'Empty or missing summary'}

            vertexai.init(
                project=os.getenv('GOOGLE_CLOUD_PROJECT', 'ken-e-dev'),
                location=os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1'),
            )

            model = GenerativeModel('gemini-2.5-pro')

            prompt = f"""You are evaluating a company overview summary.

Your task: Determine if the summary mentions the company's founding date or age.

Company Overview Summary:
{company_overview_summary}

Question: Does this summary mention when the company was founded or how old it is?

Examples of acceptable mentions:
- "Founded in 1959"
- "Established in 2010"
- "Started 15 years ago"
- "Since 1985"

Provide your assessment as JSON with:
- passes: "yes" or "no"
- reasoning: Brief explanation of your assessment
"""

            generation_config = GenerationConfig(
                temperature=0.1,
                max_output_tokens=2500,
                response_mime_type="application/json",
                response_schema=ScorerAssessment.model_json_schema(),
            )

            response = model.generate_content(prompt, generation_config=generation_config)
            assessment = json.loads(response.text)

            score = 1 if assessment['passes'] == 'yes' else 0

            return {'score': score, 'reasoning': assessment['reasoning']}

        except Exception as e:
            logger.error(f"Error in founding date scorer: {e}")
            return {'score': 0, 'error': str(e)}


class MissionStatementScorer(weave.Scorer):
    """LLM judge: Does the summary include mission statement?"""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        LLM judge: Does the summary include mission statement?

        Args:
            output: Model output dict containing 'company_overview_summary'

        Returns:
            dict with score (1 for yes, 0 for no) and reasoning
        """
        try:
            company_overview_summary = output.get('company_overview_summary', '')

            if not company_overview_summary:
                return {'score': 0, 'reasoning': 'Empty or missing summary'}

            vertexai.init(
                project=os.getenv('GOOGLE_CLOUD_PROJECT', 'ken-e-dev'),
                location=os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1'),
            )

            model = GenerativeModel('gemini-2.5-pro')

            prompt = f"""You are evaluating a company overview summary.

Your task: Determine if the summary includes or describes the company's mission statement or purpose.

Company Overview Summary:
{company_overview_summary}

Question: Does this summary include the company's mission, vision, or purpose?

Examples of acceptable mentions:
- Explicit mission: "Our mission is to..."
- Implicit purpose: "We aim to transform..."
- Vision statement: "We envision a world where..."

Provide your assessment as JSON with:
- passes: "yes" or "no"
- reasoning: Brief explanation of your assessment
"""

            generation_config = GenerationConfig(
                temperature=0.1,
                max_output_tokens=2500,
                response_mime_type="application/json",
                response_schema=ScorerAssessment.model_json_schema(),
            )

            response = model.generate_content(prompt, generation_config=generation_config)
            assessment = json.loads(response.text)

            score = 1 if assessment['passes'] == 'yes' else 0

            return {'score': score, 'reasoning': assessment['reasoning']}

        except Exception as e:
            logger.error(f"Error in mission statement scorer: {e}")
            return {'score': 0, 'error': str(e)}


class BrandIdentityScorer(weave.Scorer):
    """LLM judge: Does the summary describe brand identity/positioning?"""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        LLM judge: Does the summary describe brand identity/positioning?

        Args:
            output: Model output dict containing 'company_overview_summary'

        Returns:
            dict with score (1 for yes, 0 for no) and reasoning
        """
        try:
            company_overview_summary = output.get('company_overview_summary', '')

            if not company_overview_summary:
                return {'score': 0, 'reasoning': 'Empty or missing summary'}

            vertexai.init(
                project=os.getenv('GOOGLE_CLOUD_PROJECT', 'ken-e-dev'),
                location=os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1'),
            )

            model = GenerativeModel('gemini-2.5-pro')

            prompt = f"""You are evaluating a company overview summary.

Your task: Determine if the summary describes CONCRETE brand elements (logo, tagline, visual identity) OR explicitly states that brand information requires additional research.

Company Overview Summary:
{company_overview_summary}

Question: Does this summary describe concrete brand elements OR state research is needed for brand info?

PASS criteria:
- Brand tagline: "Just Do It", "I'm Lovin' It"
- Logo/visual identity: "Golden arches", "Apple logo"
- Explicit positioning language: "Positioned as a premium luxury brand", "Markets itself as eco-friendly"
- Research needed statement: "Brand elements require additional research"

FAIL criteria:
- Market position only: "leading", "second-largest" (competitive ranking)
- Reputation: "well-known", "strong reputation" (not brand identity)
- Mission/values/aspirations: "aims to enhance lives", "committed to innovation" (corporate purpose, not brand)
- What company does: "focuses on customer service" (operational, not brand)

Requirement: Must describe tangible brand elements OR explicitly state research needed. Mission statements, values, and aspirations do NOT count as brand description.

Provide your assessment as JSON with:
- passes: "yes" or "no"
- reasoning: Brief explanation
"""

            generation_config = GenerationConfig(
                temperature=0.1,
                max_output_tokens=2500,
                response_mime_type="application/json",
                response_schema=ScorerAssessment.model_json_schema(),
            )

            response = model.generate_content(prompt, generation_config=generation_config)
            assessment = json.loads(response.text)

            score = 1 if assessment['passes'] == 'yes' else 0

            return {'score': score, 'reasoning': assessment['reasoning']}

        except Exception as e:
            logger.error(f"Error in brand identity scorer: {e}")
            return {'score': 0, 'error': str(e)}


class TargetCustomerScorer(weave.Scorer):
    """LLM judge: Does the summary identify target customers?"""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        LLM judge: Does the summary identify target customers?

        Args:
            output: Model output dict containing 'company_overview_summary'

        Returns:
            dict with score (1 for yes, 0 for no) and reasoning
        """
        try:
            company_overview_summary = output.get('company_overview_summary', '')

            if not company_overview_summary:
                return {'score': 0, 'reasoning': 'Empty or missing summary'}

            vertexai.init(
                project=os.getenv('GOOGLE_CLOUD_PROJECT', 'ken-e-dev'),
                location=os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1'),
            )

            model = GenerativeModel('gemini-2.5-pro')

            prompt = f"""You are evaluating a company overview summary.

Your task: Determine if the summary describes target customers with meaningful detail or characteristics.

Company Overview Summary:
{company_overview_summary}

Question: Does this summary describe customers with specific characteristics, demographics, or context?

PASS criteria:
- Customer characteristics: "working-class citizens", "high-net-worth individuals"
- With context/interests: "investors interested in alternative assets", "tech-savvy millennials"
- Demographic detail: "small business owners with 10-50 employees", "retirees"

FAIL criteria:
- Generic B2B/B2C labels only: "consumers and businesses", "individuals and corporations" (no characteristics)
- Count without detail: "70 million customers" (WHO specifically?)
- Inferred from service names: "offers consumer banking" (doesn't describe customers)
- Historical only: "founded to serve immigrants" (not current target unless stated)

Requirement: Customer description must include characteristics, demographics, or meaningful context beyond generic B2B/B2C labels.

Provide your assessment as JSON with:
- passes: "yes" or "no"
- reasoning: Brief explanation
"""

            generation_config = GenerationConfig(
                temperature=0.1,
                max_output_tokens=2500,
                response_mime_type="application/json",
                response_schema=ScorerAssessment.model_json_schema(),
            )

            response = model.generate_content(prompt, generation_config=generation_config)
            assessment = json.loads(response.text)

            score = 1 if assessment['passes'] == 'yes' else 0

            return {'score': score, 'reasoning': assessment['reasoning']}

        except Exception as e:
            logger.error(f"Error in target customer scorer: {e}")
            return {'score': 0, 'error': str(e)}


class CompleteThoughtsScorer(weave.Scorer):
    """LLM judge: Does content include only complete thoughts?"""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        LLM judge: Does content include only complete thoughts?

        Args:
            output: Model output dict containing 'company_overview_summary'

        Returns:
            dict with score (1 for yes, 0 for no) and reasoning
        """
        try:
            company_overview_summary = output.get('company_overview_summary', '')

            if not company_overview_summary:
                return {'score': 0, 'reasoning': 'Empty or missing summary'}

            vertexai.init(
                project=os.getenv('GOOGLE_CLOUD_PROJECT', 'ken-e-dev'),
                location=os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1'),
            )

            model = GenerativeModel('gemini-2.5-pro')

            prompt = f"""You are evaluating a company overview summary.

Your task: Determine if the content includes only complete thoughts that can be understood without any other context.

Company Overview Summary:
{company_overview_summary}

Question: Does this content include only complete thoughts that can be understood without needing additional context or references?

Examples of complete thoughts (PASS):
- "Founded in 1904, Bank of America is one of the largest financial institutions"
- "The company serves over 66 million customers with banking services"

Examples of incomplete thoughts (FAIL):
- "As mentioned above..." (references external content)
- "See the previous section for details" (requires context)
- Undefined acronyms or references without explanation

Provide your assessment as JSON with:
- passes: "yes" or "no"
- reasoning: Brief explanation of your assessment
"""

            generation_config = GenerationConfig(
                temperature=0.1,
                max_output_tokens=2500,
                response_mime_type="application/json",
                response_schema=ScorerAssessment.model_json_schema(),
            )

            response = model.generate_content(prompt, generation_config=generation_config)
            assessment = json.loads(response.text)

            score = 1 if assessment['passes'] == 'yes' else 0

            return {'score': score, 'reasoning': assessment['reasoning']}

        except Exception as e:
            logger.error(f"Error in complete thoughts scorer: {e}")
            return {'score': 0, 'error': str(e)}
