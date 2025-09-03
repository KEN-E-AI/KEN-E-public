"""Token estimation and management utilities for strategy agents.

This module provides utilities for estimating token counts, checking token limits,
and preventing token overflow errors in LLM calls.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class TokenLimitError(Exception):
    """Raised when token count exceeds allowed limits."""

    pass


class TokenEstimator:
    """Estimates token counts for various content types.

    Uses a character-based approximation since tiktoken is not available in Agent Engine.
    Approximation: 1 token ≈ 4 characters (conservative estimate for safety).
    """

    # Gemini 2.5 Pro limits
    MAX_INPUT_TOKENS = 2_097_152  # 2M context window
    MAX_OUTPUT_TOKENS = 32_768  # Configured max output
    WARNING_THRESHOLD = 0.8  # Warn at 80% usage

    # Conservative token estimation (1 token ≈ 4 chars)
    CHARS_PER_TOKEN = 4

    @classmethod
    def estimate_tokens(cls, content: Any) -> int:
        """Estimate token count for any content type.

        Args:
            content: Content to estimate tokens for (str, dict, list, etc.)

        Returns:
            Estimated token count
        """
        try:
            if content is None:
                return 0
            elif isinstance(content, str):
                return len(content) // cls.CHARS_PER_TOKEN
            elif isinstance(content, (dict, list)):
                # Convert to JSON string for estimation
                json_str = json.dumps(content, default=str)
                return len(json_str) // cls.CHARS_PER_TOKEN
            else:
                # Convert to string for other types
                return len(str(content)) // cls.CHARS_PER_TOKEN
        except Exception as e:
            logger.warning(f"Error estimating tokens: {e}, using fallback estimation")
            # Fallback: use string representation
            return len(str(content)) // cls.CHARS_PER_TOKEN

    @classmethod
    def check_input_limit(
        cls, content: Any, raise_on_exceed: bool = True
    ) -> Dict[str, Any]:
        """Check if content is within input token limits.

        Args:
            content: Content to check
            raise_on_exceed: Whether to raise an exception if limit is exceeded

        Returns:
            Dictionary with token count and status information

        Raises:
            TokenLimitError: If content exceeds limit and raise_on_exceed is True
        """
        estimated_tokens = cls.estimate_tokens(content)
        percentage = (estimated_tokens / cls.MAX_INPUT_TOKENS) * 100

        result = {
            "estimated_tokens": estimated_tokens,
            "max_tokens": cls.MAX_INPUT_TOKENS,
            "percentage": percentage,
            "within_limit": estimated_tokens <= cls.MAX_INPUT_TOKENS,
            "warning": percentage >= (cls.WARNING_THRESHOLD * 100),
            "error": estimated_tokens > cls.MAX_INPUT_TOKENS,
        }

        # Log warning if approaching limit
        if result["warning"] and not result["error"]:
            logger.warning(
                f"Token usage at {percentage:.1f}% of limit "
                f"({estimated_tokens:,} / {cls.MAX_INPUT_TOKENS:,} tokens)"
            )

        # Raise error if exceeding limit
        if result["error"] and raise_on_exceed:
            raise TokenLimitError(
                f"Input tokens ({estimated_tokens:,}) exceed limit "
                f"({cls.MAX_INPUT_TOKENS:,} tokens, {percentage:.1f}% usage)"
            )

        return result

    @classmethod
    def estimate_agent_input(
        cls,
        state: Dict[str, Any],
        best_practices: Optional[str] = None,
        business_info: Optional[Dict] = None,
        documents: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Estimate total tokens for a strategy agent input.

        Args:
            state: Current agent state
            best_practices: Best practices document content
            business_info: Business information dictionary
            documents: List of document dictionaries

        Returns:
            Dictionary with detailed token breakdown
        """
        breakdown = {
            "state": cls.estimate_tokens(state) if state else 0,
            "best_practices": cls.estimate_tokens(best_practices)
            if best_practices
            else 0,
            "business_info": cls.estimate_tokens(business_info) if business_info else 0,
            "documents": 0,
            "total": 0,
        }

        # Estimate document tokens
        if documents:
            doc_tokens = []
            for doc in documents:
                tokens = cls.estimate_tokens(doc)
                doc_tokens.append(tokens)
            breakdown["documents"] = sum(doc_tokens)
            breakdown["document_details"] = doc_tokens  # type: ignore

        # Calculate total
        breakdown["total"] = sum(
            [
                breakdown["state"],
                breakdown["best_practices"],
                breakdown["business_info"],
                breakdown["documents"],
            ]
        )

        # Add percentage and status
        breakdown["percentage"] = (breakdown["total"] / cls.MAX_INPUT_TOKENS) * 100  # type: ignore
        breakdown["within_limit"] = breakdown["total"] <= cls.MAX_INPUT_TOKENS

        logger.info(f"Token estimation breakdown: {breakdown}")

        return breakdown

    @classmethod
    def chunk_content(cls, content: str, max_chunk_tokens: int = 500_000) -> List[str]:
        """Split content into chunks that fit within token limits.

        Args:
            content: Content to chunk
            max_chunk_tokens: Maximum tokens per chunk

        Returns:
            List of content chunks
        """
        if not content:
            return []

        # Estimate total tokens
        total_tokens = cls.estimate_tokens(content)

        if total_tokens <= max_chunk_tokens:
            return [content]

        # Calculate chunk size in characters
        max_chunk_chars = max_chunk_tokens * cls.CHARS_PER_TOKEN

        # Split content into chunks
        chunks = []
        current_pos = 0

        while current_pos < len(content):
            # Get chunk
            chunk_end = min(current_pos + max_chunk_chars, len(content))

            # Try to find a good break point (newline or sentence end)
            if chunk_end < len(content):
                # Look for newline
                newline_pos = content.rfind("\n", current_pos, chunk_end)
                if newline_pos > current_pos:
                    chunk_end = newline_pos + 1
                else:
                    # Look for sentence end
                    for sep in [". ", "! ", "? "]:
                        sep_pos = content.rfind(sep, current_pos, chunk_end)
                        if sep_pos > current_pos:
                            chunk_end = sep_pos + len(sep)
                            break

            # Add chunk
            chunk = content[current_pos:chunk_end]
            chunks.append(chunk)
            current_pos = chunk_end

        logger.info(f"Split content into {len(chunks)} chunks")

        return chunks


def check_and_log_tokens(
    content: Any, context: str, raise_on_exceed: bool = True
) -> Dict[str, Any]:
    """Convenience function to check tokens and log the result.

    Args:
        content: Content to check
        context: Context string for logging (e.g., "business_strategy_agent_input")
        raise_on_exceed: Whether to raise an exception if limit is exceeded

    Returns:
        Token check result dictionary
    """
    result = TokenEstimator.check_input_limit(content, raise_on_exceed)

    logger.info(
        f"[TOKEN_CHECK] {context}: {result['estimated_tokens']:,} tokens "
        f"({result['percentage']:.1f}% of limit)"
    )

    return result
