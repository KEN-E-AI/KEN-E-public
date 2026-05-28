"""
Product Portfolio Scorers

Scorers for evaluating product category descriptions.

Original scorer implementations by Yafet Tamene.
Downloaded from W&B Weave and adapted for local use.
"""

import json
import logging
import os

import vertexai
import weave
from pydantic import BaseModel
from vertexai.generative_models import GenerationConfig, GenerativeModel

logger = logging.getLogger(__name__)


class ScorerAssessment(BaseModel):
    """Schema for general scorer assessment"""

    passes: str
    reasoning: str


class ProductCategoryLengthScorer(weave.Scorer):
    """Scores product category description based on character count (200-1000 chars)."""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        Score based on character count.

        Weave passes the full model output dict to `output` parameter.
        We extract the description from it.

        Args:
            output: Model output dict containing product category description

        Returns:
            dict with score (1 if in range, 0 otherwise)
        """
        try:
            # Extract description from model output
            description = output.get("product_category_description") or output.get(
                "description", ""
            )

            char_count = len(description)
            score = 1 if 200 <= char_count <= 1000 else 0

            return {"score": score, "char_count": char_count}

        except Exception as e:
            logger.error(f"Error in product category length scorer: {e}")
            return {"score": 0, "error": str(e)}


class ProductCategoryDescriptionAgreementScorer(weave.Scorer):
    """Compares human vs LLM score for category description quality."""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        Compare human vs LLM score for category description quality.

        Args:
            output: {'human_scores': {...}, 'llm_scores': {...}}

        Returns:
            dict with score=1 (agree) or score=0 (disagree)
        """
        human_scores = output.get("human_scores", {})
        llm_scores = output.get("llm_scores", {})

        factor_name = "category-description"
        human_data = human_scores.get(factor_name, {})
        llm_data = llm_scores.get(factor_name, {})

        human_score = (
            human_data.get("score") if isinstance(human_data, dict) else human_data
        )
        llm_score = llm_data.get("score") if isinstance(llm_data, dict) else llm_data

        if human_score is None or llm_score is None:
            return {"score": 0}

        agrees = human_score == llm_score

        return {"score": 1 if agrees else 0}


class ProductCategoryLengthAgreementScorer(weave.Scorer):
    """Compares human vs LLM score for category description length."""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        Compare human vs LLM score for category description length.

        Args:
            output: {'human_scores': {...}, 'llm_scores': {...}}

        Returns:
            dict with score=1 (agree) or score=0 (disagree)
        """
        human_scores = output.get("human_scores", {})
        llm_scores = output.get("llm_scores", {})

        factor_name = "category-description-character-length"
        human_data = human_scores.get(factor_name, {})
        llm_data = llm_scores.get(factor_name, {})

        human_score = (
            human_data.get("score") if isinstance(human_data, dict) else human_data
        )
        llm_score = llm_data.get("score") if isinstance(llm_data, dict) else llm_data

        if human_score is None or llm_score is None:
            return {"score": 0}

        agrees = human_score == llm_score

        return {"score": 1 if agrees else 0}


class ProductCategoryDescriptionScorer(weave.Scorer):
    """LLM judge: Does text describe a category of products/services?"""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        LLM judge: Does text describe a category of products/services?

        Args:
            output: Model output dict containing product category description

        Returns:
            dict with score (1 for yes, 0 for no) and reasoning
        """
        try:
            # Extract description from model output
            description = output.get("product_category_description") or output.get(
                "description", ""
            )

            if not description:
                return {"score": 0, "reasoning": "Empty or missing description"}

            vertexai.init(
                project=os.getenv("GOOGLE_CLOUD_PROJECT", "ken-e-dev"),
                location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            )

            model = GenerativeModel("gemini-2.5-pro")

            prompt = f"""You are evaluating a product category description.

Your task: Determine if the description describes a CATEGORY by naming or describing the specific products/services it contains, not just a single product.

Product Category Description:
{description}

Question: Does this describe a category by listing/explaining what products or services are included?

PASS - Category with specifics:
- "Includes checking accounts, savings accounts, credit cards, and personal loans" (lists products)
- "Retirement accounts such as Traditional IRAs, Roth IRAs, and 401(k)s" (names types)
- "Real estate investment products including rental properties, REITs, and land investments" (specific offerings)

FAIL - Too vague or single product:
- "Comprehensive suite of financial products" (WHAT products? Too vague)
- "Range of banking services" (no specifics given)
- "Products and services to help customers" (generic, no detail)
- "The Universal IRA account" (single product, not category)

Requirement: Must describe a category by naming or explaining the specific products/services within it. Generic phrases like "suite of", "range of", "products and services" without specifics are insufficient.

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

            response = model.generate_content(
                prompt, generation_config=generation_config
            )
            assessment = json.loads(response.text)

            score = 1 if assessment["passes"] == "yes" else 0

            return {"score": score, "reasoning": assessment["reasoning"]}

        except Exception as e:
            logger.error(f"Error in product category description scorer: {e}")
            return {"score": 0, "error": str(e)}
