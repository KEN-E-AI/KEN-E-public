"""
Shared OpenAI formatting utility for all strategy agents.
Provides fallback when Gemini formatter fails with complex schemas.
"""

import json
import logging
import os
from typing import Any

import weave
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _get_openai_key() -> str:
    """Load OpenAI API key using shared secrets utility."""
    from shared.secrets import get_env_or_secret

    api_key = get_env_or_secret("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment or Secret Manager")
    return api_key


@weave.op(name="openai_formatter")
def format_with_openai(
    research_data: str,
    model_class: type[BaseModel],
    strategy_type: str,
    source_urls: list | None = None,
    custom_instructions: str | None = None,
) -> dict[str, Any]:
    """
    Use OpenAI to format research data into structured strategy.

    OpenAI's beta.chat.completions.parse handles complex Pydantic schemas
    more reliably than Gemini, especially with nested structures.

    Args:
        research_data: Unstructured research text from researcher agent
        model_class: Pydantic model class to format into
        strategy_type: Type of strategy (for logging/prompting)
        source_urls: List of source URLs from grounding metadata
        custom_instructions: Optional custom instructions from Firestore config.
                           If provided, these will be used instead of hardcoded instructions.

    Returns:
        Dictionary matching the Pydantic model schema
    """
    from openai import OpenAI as OpenAIClient

    api_key = _get_openai_key()

    # Use context manager to ensure proper cleanup of httpx connections
    with OpenAIClient(api_key=api_key) as client:
        # Build user prompt with source URLs
        urls_section = ""
        if source_urls:
            urls_section = "\n\nSource URLs from research:\n" + "\n".join(
                f"- {url}" for url in source_urls
            )

        # Use custom instructions if provided (from Firestore), otherwise use hardcoded fallback
        if custom_instructions:
            system_content = custom_instructions
            logger.info(
                f"Using custom instructions from Firestore for {strategy_type} OpenAI fallback"
            )
        else:
            system_content = (
                f"You are a {strategy_type} formatter. Format the research into a structured "
                f"{strategy_type} document matching the provided schema exactly. "
                f"IMPORTANT: For each node with descriptive information from web research, "
                f"populate the 'references' field with relevant URLs from the provided source list."
            )
            logger.warning(
                f"No custom instructions available, using hardcoded fallback for {strategy_type}"
            )

        # Use OpenAI's structured output parsing
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {
                    "role": "system",
                    "content": system_content,
                },
                {
                    "role": "user",
                    "content": f"Format this research into structured {strategy_type}. Populate 'references' fields with relevant URLs:{urls_section}\n\n{research_data}",
                },
            ],
            response_format=model_class,
        )

        # Return parsed response
        if completion.choices[0].message.parsed:
            return completion.choices[0].message.parsed.model_dump()
        else:
            # Fallback to JSON parsing
            return json.loads(completion.choices[0].message.content)
