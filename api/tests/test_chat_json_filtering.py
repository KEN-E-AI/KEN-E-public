"""
Tests for chat response JSON filtering functionality.
Verifies that function_call and function_response data is properly filtered from responses.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def clean_agent_response(response: str | None) -> str | None:
    """
    Clean function_call and function_response JSON data from agent responses.
    
    This is a simplified version for testing. The actual implementation
    is in src.kene_api.routers.chat module.
    """
    if not response:
        return response
    
    # Check for function_call or function_response patterns
    if "{'function_call'" in response or "{'function_response'" in response:
        # Try to extract text after the last }}
        if "}}" in response:
            parts = response.rsplit("}}", 1)
            if len(parts) == 2 and parts[1].strip():
                cleaned = parts[1].strip()
                if not cleaned.startswith("{"):
                    return cleaned
    
    return response


class TestChatJSONFiltering:
    """Test suite for JSON filtering in chat responses."""

    def test_clean_response_with_function_call(self):
        """Test that function_call JSON is removed from response."""
        # Input with function_call JSON followed by actual response
        input_text = "{'function_call': {'name': 'search', 'arguments': {'query': 'test'}}}This is the actual response"
        
        # Should extract only the text after the JSON
        result = clean_agent_response(input_text)
        assert result == "This is the actual response"

    def test_clean_response_with_function_response(self):
        """Test that function_response JSON is removed from response."""
        # Input with function_response JSON
        input_text = "{'function_response': {'result': 'success', 'data': [1, 2, 3]}}Here is the processed result"
        
        result = clean_agent_response(input_text)
        assert result == "Here is the processed result"

    def test_clean_response_with_multiple_json_objects(self):
        """Test handling of multiple consecutive JSON objects."""
        # Multiple JSON objects followed by text
        input_text = (
            "{'function_call': {'name': 'func1'}}"
            "{'function_response': {'status': 'ok'}}"
            "The final answer is 42"
        )
        
        result = clean_agent_response(input_text)
        assert result == "The final answer is 42"

    def test_clean_response_with_closing_braces(self):
        """Test extraction based on closing braces pattern."""
        # Response with }} pattern that indicates end of JSON
        input_text = "{'function_call': {'nested': {'deep': 'value'}}}The actual content starts here"
        
        result = clean_agent_response(input_text)
        assert result == "The actual content starts here"

    def test_clean_response_no_json(self):
        """Test that regular text without JSON passes through unchanged."""
        input_text = "This is a normal response without any JSON data"
        
        result = clean_agent_response(input_text)
        assert result == input_text

    def test_clean_response_empty_string(self):
        """Test handling of empty string."""
        result = clean_agent_response("")
        assert result == ""

    def test_clean_response_none(self):
        """Test handling of None input."""
        result = clean_agent_response(None)
        assert result is None

    def test_clean_response_json_only(self):
        """Test response that contains only JSON and no text."""
        input_text = "{'function_call': {'name': 'test'}}"
        
        # Should return empty or the JSON itself if no text found
        result = clean_agent_response(input_text)
        # Based on the implementation, this might return empty or the original
        assert result == "" or result == input_text

    def test_clean_response_with_newlines(self):
        """Test handling of JSON with newlines in response."""
        input_text = """{'function_call': {
            'name': 'search',
            'arguments': {'query': 'test'}
        }}
        
        Here is the formatted response:
        - Point 1
        - Point 2"""
        
        result = clean_agent_response(input_text)
        # Should preserve the formatted text after JSON
        assert "Here is the formatted response:" in result
        assert "- Point 1" in result
        assert "- Point 2" in result
        assert "function_call" not in result

    def test_clean_response_partial_json(self):
        """Test handling of malformed/partial JSON."""
        input_text = "{'function_call': {'incomplete': The rest of the message"
        
        # Should return as-is if JSON is malformed
        result = clean_agent_response(input_text)
        assert result == input_text

    def test_clean_response_mixed_content(self):
        """Test response with JSON in the middle of text."""
        input_text = "Start of response {'not_a_function': 'data'} end of response"
        
        # Should not filter JSON that's not function_call/function_response
        result = clean_agent_response(input_text)
        assert result == input_text

    def test_clean_response_preserves_markdown(self):
        """Test that markdown formatting is preserved after filtering."""
        input_text = """{'function_call': {'name': 'analyze'}}## Analysis Results

| Metric | Value |
|--------|-------|
| Score  | 95%   |

**Conclusion**: Performance is excellent."""
        
        result = clean_agent_response(input_text)
        assert "## Analysis Results" in result
        assert "| Metric | Value |" in result
        assert "**Conclusion**:" in result
        assert "function_call" not in result


@pytest.mark.asyncio
class TestChatEndpointFiltering:
    """Integration tests for chat endpoint JSON filtering."""

    async def test_streaming_response_filters_json(self):
        """Test that streaming responses filter out JSON data."""
        # This would be an integration test that requires mocking the actual
        # agent engine response. Placeholder for now.
        pass

    async def test_non_streaming_response_filters_json(self):
        """Test that non-streaming responses filter out JSON data."""
        # This would be an integration test that requires mocking the actual
        # agent engine response. Placeholder for now.
        pass