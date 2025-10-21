"""Utility to clean JSON output from agents that wrap it in markdown."""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def clean_json_output(raw_output: str) -> str:
    """
    Clean JSON output that might be wrapped in markdown code blocks.

    Args:
        raw_output: The raw output from the agent that might contain markdown

    Returns:
        Clean JSON string without markdown wrappers
    """
    if not raw_output:
        return raw_output

    # If it's already valid JSON, return as-is
    try:
        json.loads(raw_output)
        return raw_output
    except (json.JSONDecodeError, TypeError):
        pass

    # Remove markdown code block wrappers
    # Pattern matches ```json ... ``` or ``` ... ```
    markdown_pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    match = re.match(markdown_pattern, raw_output.strip(), re.DOTALL)

    if match:
        cleaned = match.group(1).strip()
        logger.info("Removed markdown wrapper from JSON output")
        return cleaned

    # Try to find JSON within the text
    # Look for content between first { and last }
    json_pattern = r"\{.*\}"
    match = re.search(json_pattern, raw_output, re.DOTALL)

    if match:
        potential_json = match.group(0)
        try:
            # Validate it's actual JSON
            json.loads(potential_json)
            logger.info("Extracted JSON from text output")
            return potential_json
        except json.JSONDecodeError:
            pass

    # Return original if no cleaning was possible
    return raw_output


def safe_parse_json(raw_output: str, model_class: Any | None = None) -> dict[str, Any]:
    """
    Safely parse JSON output that might be wrapped in markdown.

    Args:
        raw_output: The raw output from the agent
        model_class: Optional Pydantic model class to validate against

    Returns:
        Parsed JSON as dictionary or validated Pydantic model

    Raises:
        ValueError: If JSON cannot be parsed even after cleaning
    """
    # Clean the output first
    cleaned = clean_json_output(raw_output)

    try:
        # Parse the JSON
        data = json.loads(cleaned)

        # If a model class is provided, validate against it
        if model_class:
            return model_class.model_validate(data)

        return data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON even after cleaning: {e}")
        logger.error(f"Cleaned output: {cleaned[:500]}...")
        raise ValueError(f"Invalid JSON output: {e}") from e
    except Exception as e:
        logger.error(f"Error validating JSON against model: {e}")
        raise


def wrap_agent_with_json_cleaner(agent_func):
    """
    Decorator to wrap an agent function and clean its JSON output.

    Usage:
        @wrap_agent_with_json_cleaner
        def my_agent():
            # Agent that might return markdown-wrapped JSON
            return agent
    """

    def wrapper(*args, **kwargs):
        agent = agent_func(*args, **kwargs)

        # Store original invoke method
        original_invoke = agent.invoke

        # Create wrapped invoke that cleans output
        def cleaned_invoke(prompt: str) -> str:
            result = original_invoke(prompt)

            # If result is a string, clean it
            if isinstance(result, str):
                return clean_json_output(result)

            # If result is a dict with 'content' key, clean that
            if isinstance(result, dict) and "content" in result:
                result["content"] = clean_json_output(result["content"])

            return result

        # Replace the invoke method
        agent.invoke = cleaned_invoke

        return agent

    return wrapper
