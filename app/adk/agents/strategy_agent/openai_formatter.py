"""
Shared OpenAI formatting utility for all strategy agents.
Provides fallback when Gemini formatter fails with complex schemas.
"""

import json
import os
from typing import Any

from pydantic import BaseModel


def _get_openai_key() -> str:
    """Load OpenAI API key from env or Secret Manager."""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key

    # Load from Secret Manager
    try:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        name = "projects/ken-e-dev/secrets/OPENAI_API_KEY/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        raise ValueError(
            f"OPENAI_API_KEY not found in environment or Secret Manager: {e}"
        )


def format_with_openai(
    research_data: str,
    model_class: type[BaseModel],
    strategy_type: str,
    source_urls: list = None,
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

        # Use OpenAI's structured output parsing
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-2024-08-06",
            messages=[
                {
                    "role": "system",
                    "content": f"You are a {strategy_type} formatter. Format the research into a structured {strategy_type} document matching the provided schema exactly. IMPORTANT: For each node with descriptive information from web research, populate the 'references' field with relevant URLs from the provided source list.",
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
