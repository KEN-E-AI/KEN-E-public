"""Retry wrapper for handling structured output validation errors.

This module provides utilities to retry agent calls when structured output
validation fails, with improved instructions to the agent.
"""

import json
import logging
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, ValidationError
from google.adk.agents import Agent

logger = logging.getLogger(__name__)


class OutputRetryConfig:
    """Configuration for output retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 2,
        include_error_feedback: bool = True,
        include_schema_reminder: bool = True
    ):
        """Initialize retry configuration.
        
        Args:
            max_retries: Maximum number of retry attempts for validation errors
            include_error_feedback: Whether to include error details in retry prompt
            include_schema_reminder: Whether to include schema format in retry prompt
        """
        self.max_retries = max_retries
        self.include_error_feedback = include_error_feedback
        self.include_schema_reminder = include_schema_reminder


def retry_on_validation_error(
    agent: Agent,
    input_data: Dict[str, Any],
    output_schema: Type[BaseModel],
    config: Optional[OutputRetryConfig] = None
) -> Dict[str, Any]:
    """Execute agent with retry on output validation errors.
    
    Args:
        agent: The agent to execute
        input_data: Input data for the agent
        output_schema: Expected Pydantic schema for output
        config: Retry configuration
        
    Returns:
        Validated output data as dictionary
        
    Raises:
        ValidationError: If output validation fails after all retries
    """
    if config is None:
        config = OutputRetryConfig()
    
    last_error = None
    original_instruction = getattr(agent, 'instruction', '')
    
    for attempt in range(config.max_retries + 1):
        try:
            # Add retry context to instruction if this is a retry
            if attempt > 0:
                retry_instruction = f"""
{original_instruction}

CRITICAL: Your previous response failed validation. You MUST provide a valid JSON response.
"""
                if config.include_error_feedback and last_error:
                    retry_instruction += f"""
Previous error: {str(last_error)}
"""
                if config.include_schema_reminder:
                    # Get schema as JSON (use Pydantic v2 method)
                    schema_json = output_schema.model_json_schema()
                    retry_instruction += f"""
Required JSON structure:
{json.dumps(schema_json, indent=2)}

Your response MUST be ONLY valid JSON matching this exact structure.
Do NOT include any text before or after the JSON.
"""
                # Temporarily modify agent instruction
                agent.instruction = retry_instruction
            
            # Execute agent
            result = agent.invoke(**input_data)
            
            # Extract the output based on the output_key
            output_key = getattr(agent, 'output_key', 'output')
            raw_output = result.get(output_key)
            
            # Try to parse and validate the output
            if isinstance(raw_output, str):
                # Try to parse as JSON if it's a string
                try:
                    parsed_output = json.loads(raw_output)
                except json.JSONDecodeError as e:
                    # If it's not valid JSON, try to extract JSON from the text
                    # Look for JSON between triple backticks or curly braces
                    import re
                    
                    # Try to find JSON in code blocks
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_output, re.DOTALL)
                    if json_match:
                        parsed_output = json.loads(json_match.group(1))
                    else:
                        # Try to find raw JSON object
                        json_match = re.search(r'(\{.*\})', raw_output, re.DOTALL)
                        if json_match:
                            parsed_output = json.loads(json_match.group(1))
                        else:
                            raise e
            else:
                parsed_output = raw_output
            
            # Validate with Pydantic schema
            validated = output_schema(**parsed_output)
            
            # Success - log if this was a retry
            if attempt > 0:
                logger.info(
                    f"Output validation succeeded on attempt {attempt + 1}/{config.max_retries + 1}"
                )
            
            # Restore original instruction
            if attempt > 0:
                agent.instruction = original_instruction
            
            return validated.model_dump()
            
        except (ValidationError, json.JSONDecodeError) as e:
            last_error = e
            
            if attempt >= config.max_retries:
                logger.error(
                    f"Output validation failed after {config.max_retries + 1} attempts: {e}"
                )
                # Restore original instruction before raising
                if attempt > 0:
                    agent.instruction = original_instruction
                raise ValidationError(f"Failed to get valid output after {config.max_retries + 1} attempts: {e}")
            
            logger.warning(
                f"Output validation failed on attempt {attempt + 1}/{config.max_retries + 1}: {e}. Retrying..."
            )
    
    # Should never reach here
    if last_error:
        raise last_error


def create_robust_agent_wrapper(
    agent: Agent,
    output_schema: Type[BaseModel],
    retry_config: Optional[OutputRetryConfig] = None
) -> Agent:
    """Create a wrapper agent that handles output validation with retries.
    
    Args:
        agent: The original agent
        output_schema: Expected output schema
        retry_config: Retry configuration
        
    Returns:
        Wrapped agent with retry logic
    """
    original_invoke = agent.invoke
    
    def invoke_with_retry(**kwargs) -> Dict[str, Any]:
        """Invoke agent with retry on validation errors."""
        return retry_on_validation_error(
            agent=agent,
            input_data=kwargs,
            output_schema=output_schema,
            config=retry_config
        )
    
    # Replace the invoke method
    agent.invoke = invoke_with_retry
    
    return agent