"""Enhanced JSON parser for handling messy LLM outputs."""

import json
import logging
import re
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class EnhancedJsonParser:
    """
    Parser that uses advanced cleaning techniques to extract
    structured JSON from messy LLM outputs.
    
    This handles common issues like:
    - JSON wrapped in markdown code blocks
    - Extra narrative text around the JSON
    - Unescaped quotes and newlines
    - Missing quotes on keys
    - Trailing commas
    """
    
    def __init__(self):
        """Initialize the enhanced parser."""
        pass
        
    def parse_json(
        self, 
        raw_output: str, 
        schema: Optional[Type[BaseModel]] = None
    ) -> Dict[str, Any]:
        """
        Parse potentially messy JSON output from an LLM.
        
        Args:
            raw_output: The raw LLM output that may contain JSON
            schema: Optional Pydantic schema to validate against
            
        Returns:
            Parsed JSON as a dictionary
            
        Raises:
            ValueError: If parsing fails after all attempts
        """
        if not raw_output:
            raise ValueError("Empty output provided")
            
        # First try standard JSON parsing (fast path)
        try:
            data = json.loads(raw_output)
            if schema:
                return schema.model_validate(data).model_dump()
            return data
        except (json.JSONDecodeError, ValueError):
            pass
            
        # Use enhanced parsing for messy outputs
        try:
            # Enhanced parser handles:
            # 1. Stripping markdown code blocks
            # 2. Removing extra text
            # 3. Fixing common JSON issues
            parsed = self._parse_with_enhanced(raw_output, schema)
            
            if parsed:
                logger.info("Successfully parsed JSON using enhanced parser")
                return parsed
                
        except Exception as e:
            logger.warning(f"Enhanced parsing failed: {e}")
            
        # Fallback to our original cleaner as last resort
        from .json_cleaner import clean_json_output, safe_parse_json
        
        try:
            if schema:
                return safe_parse_json(raw_output, schema).model_dump()
            else:
                cleaned = clean_json_output(raw_output)
                return json.loads(cleaned)
        except Exception as e:
            logger.error(f"All parsing attempts failed: {e}")
            raise ValueError(f"Unable to parse JSON from output: {e}")
            
    def _parse_with_enhanced(
        self, 
        raw_output: str, 
        schema: Optional[Type[BaseModel]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Internal method to use enhanced parsing capabilities.
        
        Args:
            raw_output: Raw text to parse
            schema: Optional schema for validation
            
        Returns:
            Parsed dictionary or None if parsing fails
        """
        try:
            # Step 1: Strip markdown code blocks
            content = raw_output
            
            # Remove ```json...``` blocks
            markdown_pattern = r'```(?:json)?\s*\n?([\s\S]*?)\n?```'
            matches = re.findall(markdown_pattern, content)
            if matches:
                content = matches[0]
            
            # Additional markdown pattern for just ```...```
            if content.strip().startswith('```') and content.strip().endswith('```'):
                lines = content.strip().split('\n')
                if lines[0].strip() == '```':
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                content = '\n'.join(lines)
            
            # Step 2: Find JSON object in the text
            # Look for content between { and }
            json_pattern = r'\{[\s\S]*\}'
            json_matches = re.findall(json_pattern, content)
            if json_matches:
                # Take the largest match (likely the complete JSON)
                content = max(json_matches, key=len)
            
            # Step 3: Clean up common JSON issues
            # Remove trailing commas
            content = re.sub(r',\s*([}\]])', r'\1', content)
            
            # Fix unquoted keys (simple cases)
            content = re.sub(r'([\{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)', r'\1"\2"\3', content)
            
            # Handle escaped newlines and tabs
            content = content.replace('\\n', '\n').replace('\\t', '\t')
            
            # Remove any BOM or zero-width characters
            content = content.encode('utf-8', 'ignore').decode('utf-8-sig')
            
            # Step 4: Try multiple parsing strategies
            # Strategy 1: Direct parse
            try:
                result = json.loads(content)
                if schema and result:
                    validated = schema.model_validate(result)
                    return validated.model_dump()
                return result
            except json.JSONDecodeError:
                pass
            
            # Strategy 2: Remove all whitespace outside quotes and retry
            try:
                import re
                # This regex preserves whitespace within quotes
                cleaned = re.sub(r'(?<!\\)"[^"]*"(*SKIP)(*FAIL)|\s+', '', content)
                result = json.loads(cleaned)
                if schema and result:
                    validated = schema.model_validate(result)
                    return validated.model_dump()
                return result
            except:
                pass
            
            # Strategy 3: If it looks like it might be double-encoded, try decoding
            if '\\\\' in content or '\\"' in content:
                try:
                    # Unescape the string
                    unescaped = content.encode().decode('unicode_escape')
                    result = json.loads(unescaped)
                    if schema and result:
                        validated = schema.model_validate(result)
                        return validated.model_dump()
                    return result
                except:
                    pass
            
            # If all strategies fail, log more details for debugging
            logger.warning(f"All parsing strategies failed. Content preview: {content[:200]}...")
            return None
            
        except Exception as e:
            logger.debug(f"Enhanced parsing error: {e}")
            logger.debug(f"Raw output preview: {raw_output[:200]}...")
            return None


# Singleton instance for reuse
_parser_instance: Optional[EnhancedJsonParser] = None


def get_parser() -> EnhancedJsonParser:
    """Get or create the singleton parser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = EnhancedJsonParser()
    return _parser_instance


def parse_strategy_output(raw_output: str, model_class: Type[BaseModel]) -> BaseModel:
    """
    Parse strategy agent output using enhanced JSON parser.
    
    Args:
        raw_output: Raw output from the strategy agent
        model_class: Pydantic model class for the expected structure
        
    Returns:
        Validated Pydantic model instance
        
    Raises:
        ValueError: If parsing or validation fails
    """
    parser = get_parser()
    
    try:
        # Parse and validate
        data = parser.parse_json(raw_output, model_class)
        
        # Return as model instance
        return model_class.model_validate(data)
        
    except Exception as e:
        logger.error(f"Failed to parse strategy output: {e}")
        logger.debug(f"Raw output preview: {raw_output[:500]}...")
        raise ValueError(f"Failed to parse strategy output: {e}")