"""
Customer Profile Scorers

Scorers for evaluating ideal customer profile narrative quality.
"""

import json
import logging
import os
from pydantic import BaseModel
import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel
import weave

logger = logging.getLogger(__name__)


class ScorerAssessment(BaseModel):
    """Schema for general scorer assessment"""

    passes: str
    reasoning: str


class CustomerProfileLengthScorer(weave.Scorer):
    """Scores customer profile narrative based on character count (2000-6000 chars)."""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        Score based on character count.

        Args:
            output: Model output dict containing 'narrative'

        Returns:
            dict with score (1 if in range, 0 otherwise)
        """
        try:
            narrative = output.get('narrative', '')
            char_count = len(narrative)
            score = 1 if 2000 <= char_count <= 6000 else 0

            return {'score': score, 'char_count': char_count}

        except Exception as e:
            logger.error(f"Error in customer profile length scorer: {e}")
            return {'score': 0, 'error': str(e)}


class CustomerProfilePainPointsScorer(weave.Scorer):
    """LLM judge: Does narrative include bulleted list of pain points?"""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        LLM judge: Does narrative include bulleted list of painful problems?

        Args:
            output: Model output dict containing 'narrative'

        Returns:
            dict with score (1 for yes, 0 for no) and reasoning
        """
        try:
            narrative = output.get('narrative', '')

            if not narrative:
                return {'score': 0, 'reasoning': 'Empty or missing narrative'}

            vertexai.init(
                project=os.getenv('GOOGLE_CLOUD_PROJECT', 'ken-e-dev'),
                location=os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1'),
            )

            model = GenerativeModel('gemini-2.5-pro')

            prompt = f"""You are evaluating a customer profile narrative.

Your task: Determine if the narrative includes a bulleted or clearly listed set of pain points/problems that are painful for this persona.

Customer Profile Narrative:
{narrative}

Question: Does this narrative include a bulleted list or clear listing of specific pain points/problems?

PASS criteria:
- Contains bulleted list of pain points
- Lists specific frustrations or problems
- Example: "- Frustration with legacy banks: difficult UIs, slow service"

FAIL criteria:
- Pain points mentioned but not in list format
- No pain points mentioned at all
- Too vague or generic

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
            logger.error(f"Error in pain points scorer: {e}")
            return {'score': 0, 'error': str(e)}


class CustomerProfileMotivationsScorer(weave.Scorer):
    """LLM judge: Does narrative describe purchase motivations?"""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        LLM judge: Does narrative describe what motivates purchases?

        Args:
            output: Model output dict containing 'narrative'

        Returns:
            dict with score (1 for yes, 0 for no) and reasoning
        """
        try:
            narrative = output.get('narrative', '')

            if not narrative:
                return {'score': 0, 'reasoning': 'Empty or missing narrative'}

            vertexai.init(
                project=os.getenv('GOOGLE_CLOUD_PROJECT', 'ken-e-dev'),
                location=os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1'),
            )

            model = GenerativeModel('gemini-2.5-pro')

            prompt = f"""You are evaluating a customer profile narrative.

Your task: Determine if the narrative describes what motivates this persona to make a purchase to solve their problems.

Customer Profile Narrative:
{narrative}

Question: Does this narrative explain purchase motivations or drivers?

PASS criteria:
- Describes motivations or goals that drive purchases
- Explains why they would buy
- Example: "Digital convenience and control", "Desire to leverage expert resources"

FAIL criteria:
- No mention of motivations
- Only describes what they need, not why they buy

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
            logger.error(f"Error in motivations scorer: {e}")
            return {'score': 0, 'error': str(e)}


class CustomerProfileChannelsScorer(weave.Scorer):
    """LLM judge: Does narrative list communication channels?"""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        LLM judge: Does narrative list effective communication channels?

        Args:
            output: Model output dict containing 'narrative'

        Returns:
            dict with score (1 for yes, 0 for no) and reasoning
        """
        try:
            narrative = output.get('narrative', '')

            if not narrative:
                return {'score': 0, 'reasoning': 'Empty or missing narrative'}

            vertexai.init(
                project=os.getenv('GOOGLE_CLOUD_PROJECT', 'ken-e-dev'),
                location=os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1'),
            )

            model = GenerativeModel('gemini-2.5-pro')

            prompt = f"""You are evaluating a customer profile narrative.

Your task: Determine if the narrative identifies a list of communication channels effective for reaching this persona.

Customer Profile Narrative:
{narrative}

Question: Does this narrative list specific communication channels or methods?

PASS criteria:
- Lists specific channels (e.g., "Push notifications", "Email", "Social media", "Mobile app")
- Can be bulleted or in narrative form
- Identifies HOW to reach this persona

FAIL criteria:
- No mention of communication channels
- Too vague (e.g., "digital channels" without specifics)

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
            logger.error(f"Error in channels scorer: {e}")
            return {'score': 0, 'error': str(e)}


class CustomerProfileDemographicsScorer(weave.Scorer):
    """LLM judge: Does narrative include bulleted list of demographics?"""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        LLM judge: Does narrative include demographic characteristics?

        Args:
            output: Model output dict containing 'narrative'

        Returns:
            dict with score (1 for yes, 0 for no) and reasoning
        """
        try:
            narrative = output.get('narrative', '')

            if not narrative:
                return {'score': 0, 'reasoning': 'Empty or missing narrative'}

            vertexai.init(
                project=os.getenv('GOOGLE_CLOUD_PROJECT', 'ken-e-dev'),
                location=os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1'),
            )

            model = GenerativeModel('gemini-2.5-pro')

            prompt = f"""You are evaluating a customer profile narrative.

Your task: Determine if the narrative includes a bulleted list of demographic characteristics.

Customer Profile Narrative:
{narrative}

Question: Does this narrative include demographic details such as age, geography, gender, education, income?

PASS criteria:
- Contains bulleted list or clear section on demographics
- Includes multiple demographic factors (age, gender, location, income, education, etc.)
- Example: "- Age: 25-40 years old\n- Gender: All genders\n- Location: Urban markets"

FAIL criteria:
- No demographics mentioned
- Demographics mentioned but not in list/structured format
- Only 1-2 demographic factors (need comprehensive coverage)

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
            logger.error(f"Error in demographics scorer: {e}")
            return {'score': 0, 'error': str(e)}


class CustomerProfilePsychographicsScorer(weave.Scorer):
    """LLM judge: Does narrative include bulleted list of psychographics?"""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        LLM judge: Does narrative include psychographic characteristics?

        Args:
            output: Model output dict containing 'narrative'

        Returns:
            dict with score (1 for yes, 0 for no) and reasoning
        """
        try:
            narrative = output.get('narrative', '')

            if not narrative:
                return {'score': 0, 'reasoning': 'Empty or missing narrative'}

            vertexai.init(
                project=os.getenv('GOOGLE_CLOUD_PROJECT', 'ken-e-dev'),
                location=os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1'),
            )

            model = GenerativeModel('gemini-2.5-pro')

            prompt = f"""You are evaluating a customer profile narrative.

Your task: Determine if the narrative includes a bulleted list of psychographic characteristics.

Customer Profile Narrative:
{narrative}

Question: Does this narrative include psychographic details such as values, culture, interests, activities, opinions, hobbies?

PASS criteria:
- Contains bulleted list or clear section on psychographics
- Includes multiple psychographic factors (values, culture, interests, activities, opinions, hobbies)
- Example: "- Values: Convenience, speed, digital-first\n- Culture: Busy lifestyle\n- Interests: Fintech, investing"

FAIL criteria:
- No psychographics mentioned
- Psychographics mentioned but not in list/structured format
- Only 1-2 factors (need comprehensive coverage)

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
            logger.error(f"Error in psychographics scorer: {e}")
            return {'score': 0, 'error': str(e)}


class CustomerProfileCompleteThoughtsScorer(weave.Scorer):
    """LLM judge: Does narrative include only complete thoughts?"""

    @weave.op()
    def score(self, output: dict) -> dict:
        """
        LLM judge: Does content include only complete thoughts?

        Args:
            output: Model output dict containing 'narrative'

        Returns:
            dict with score (1 for yes, 0 for no) and reasoning
        """
        try:
            narrative = output.get('narrative', '')

            if not narrative:
                return {'score': 0, 'reasoning': 'Empty or missing narrative'}

            vertexai.init(
                project=os.getenv('GOOGLE_CLOUD_PROJECT', 'ken-e-dev'),
                location=os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1'),
            )

            model = GenerativeModel('gemini-2.5-pro')

            prompt = f"""You are evaluating a customer profile narrative.

Your task: Determine if the content includes only complete thoughts that can be understood without any other context.

Customer Profile Narrative:
{narrative}

Question: Does this content include only complete thoughts that can be understood without needing additional context or references?

Examples of complete thoughts (PASS):
- "Age: 25-40 years old, tech-savvy millennials"
- "Values convenience and digital-first experiences"

Examples of incomplete thoughts (FAIL):
- "As mentioned above..." (references external content)
- "See the previous section for details" (requires context)
- Undefined acronyms or references without explanation

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
            logger.error(f"Error in complete thoughts scorer: {e}")
            return {'score': 0, 'error': str(e)}
