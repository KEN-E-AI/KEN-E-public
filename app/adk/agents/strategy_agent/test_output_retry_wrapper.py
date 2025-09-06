"""Test suite for output retry wrapper functionality."""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch
from pydantic import BaseModel, Field, ValidationError
from typing import Optional

from .output_retry_wrapper import (
    OutputRetryConfig,
    retry_on_validation_error,
    create_robust_agent_wrapper
)


class SimpleTestSchema(BaseModel):
    """Simple test schema for validation."""
    title: str = Field(..., description="Title field")
    content: str = Field(..., description="Content field")
    score: int = Field(..., ge=0, le=100, description="Score between 0-100")
    optional_field: Optional[str] = Field(None, description="Optional field")


class ComplexBusinessStrategy(BaseModel):
    """Simplified version of BusinessStrategy for testing."""
    executive_summary: str
    company_overview: str
    market_analysis: str


class TestOutputRetryWrapper:
    """Test cases for the output retry wrapper."""
    
    def test_successful_first_attempt(self):
        """Test that valid JSON passes on first attempt."""
        # Create mock agent
        mock_agent = Mock()
        mock_agent.output_key = 'output'
        mock_agent.instruction = 'Test instruction'
        mock_agent.invoke = Mock(return_value={
            'output': json.dumps({
                'title': 'Test Title',
                'content': 'Test content',
                'score': 85
            })
        })
        
        # Test with retry wrapper
        config = OutputRetryConfig(max_retries=2)
        result = retry_on_validation_error(
            agent=mock_agent,
            input_data={'test': 'data'},
            output_schema=SimpleTestSchema,
            config=config
        )
        
        # Verify
        assert result['title'] == 'Test Title'
        assert result['score'] == 85
        assert mock_agent.invoke.call_count == 1
    
    def test_retry_on_invalid_json(self):
        """Test retry when agent returns invalid JSON."""
        # Create mock agent that returns plain text first, then valid JSON
        mock_agent = Mock()
        mock_agent.output_key = 'output'
        mock_agent.instruction = 'Test instruction'
        
        # First call returns invalid response, second returns valid
        mock_agent.invoke = Mock(side_effect=[
            {'output': 'This is not JSON, just plain text'},
            {'output': json.dumps({
                'title': 'Corrected Title',
                'content': 'Valid content',
                'score': 90
            })}
        ])
        
        # Test with retry wrapper
        config = OutputRetryConfig(max_retries=2)
        result = retry_on_validation_error(
            agent=mock_agent,
            input_data={'test': 'data'},
            output_schema=SimpleTestSchema,
            config=config
        )
        
        # Verify retry happened and succeeded
        assert result['title'] == 'Corrected Title'
        assert mock_agent.invoke.call_count == 2
        # Check that instruction was modified for retry
        assert 'CRITICAL' in mock_agent.instruction
    
    def test_retry_on_schema_validation_error(self):
        """Test retry when JSON is valid but doesn't match schema."""
        mock_agent = Mock()
        mock_agent.output_key = 'output'
        mock_agent.instruction = 'Test instruction'
        
        # First call has invalid score (> 100), second is valid
        mock_agent.invoke = Mock(side_effect=[
            {'output': json.dumps({
                'title': 'Test',
                'content': 'Content',
                'score': 150  # Invalid: exceeds max of 100
            })},
            {'output': json.dumps({
                'title': 'Test',
                'content': 'Content', 
                'score': 95  # Valid
            })}
        ])
        
        config = OutputRetryConfig(max_retries=2)
        result = retry_on_validation_error(
            agent=mock_agent,
            input_data={'test': 'data'},
            output_schema=SimpleTestSchema,
            config=config
        )
        
        assert result['score'] == 95
        assert mock_agent.invoke.call_count == 2
    
    def test_extract_json_from_markdown(self):
        """Test extraction of JSON from markdown code blocks."""
        mock_agent = Mock()
        mock_agent.output_key = 'output'
        mock_agent.instruction = 'Test instruction'
        
        # Response wrapped in markdown
        markdown_response = """Here is the JSON response:
        
```json
{
    "title": "Extracted Title",
    "content": "Extracted content",
    "score": 75
}
```

That's the response."""
        
        mock_agent.invoke = Mock(return_value={'output': markdown_response})
        
        config = OutputRetryConfig(max_retries=2)
        result = retry_on_validation_error(
            agent=mock_agent,
            input_data={'test': 'data'},
            output_schema=SimpleTestSchema,
            config=config
        )
        
        assert result['title'] == 'Extracted Title'
        assert result['score'] == 75
        assert mock_agent.invoke.call_count == 1
    
    def test_max_retries_exceeded(self):
        """Test that ValidationError is raised after max retries."""
        mock_agent = Mock()
        mock_agent.output_key = 'output'
        mock_agent.instruction = 'Test instruction'
        
        # Always return invalid response
        mock_agent.invoke = Mock(return_value={'output': 'Never valid JSON'})
        
        config = OutputRetryConfig(max_retries=2)
        
        with pytest.raises(ValidationError) as exc_info:
            retry_on_validation_error(
                agent=mock_agent,
                input_data={'test': 'data'},
                output_schema=SimpleTestSchema,
                config=config
            )
        
        assert 'Failed to get valid output after 3 attempts' in str(exc_info.value)
        assert mock_agent.invoke.call_count == 3  # Initial + 2 retries
    
    def test_complex_business_strategy_retry(self):
        """Test retry with complex business strategy schema."""
        mock_agent = Mock()
        mock_agent.output_key = 'business_strategy_doc'
        mock_agent.instruction = 'Create business strategy'
        
        # First attempt returns text, second returns valid JSON
        mock_agent.invoke = Mock(side_effect=[
            {'business_strategy_doc': """As a Strategy Document Expert, I need to provide
            a complete business strategy. Here's my analysis of the company..."""},
            {'business_strategy_doc': json.dumps({
                'executive_summary': 'Company is well-positioned for growth',
                'company_overview': 'Leading provider in the industry',
                'market_analysis': 'Market size is $10B with 15% CAGR'
            })}
        ])
        
        config = OutputRetryConfig(
            max_retries=2,
            include_error_feedback=True,
            include_schema_reminder=True
        )
        
        result = retry_on_validation_error(
            agent=mock_agent,
            input_data={'company': 'TestCorp'},
            output_schema=ComplexBusinessStrategy,
            config=config
        )
        
        assert 'Company is well-positioned' in result['executive_summary']
        assert mock_agent.invoke.call_count == 2
    
    def test_wrapper_function_integration(self):
        """Test the create_robust_agent_wrapper function."""
        mock_agent = Mock()
        mock_agent.output_key = 'output'
        mock_agent.instruction = 'Test'
        
        # Set up invoke to fail once then succeed
        call_count = {'count': 0}
        
        def mock_invoke(**kwargs):
            call_count['count'] += 1
            if call_count['count'] == 1:
                return {'output': 'Invalid JSON'}
            return {'output': json.dumps({
                'title': 'Success',
                'content': 'Valid',
                'score': 80
            })}
        
        mock_agent.invoke = mock_invoke
        
        # Wrap the agent
        wrapped_agent = create_robust_agent_wrapper(
            agent=mock_agent,
            output_schema=SimpleTestSchema,
            retry_config=OutputRetryConfig(max_retries=2)
        )
        
        # Call wrapped agent
        result = wrapped_agent.invoke(test='data')
        
        assert result['title'] == 'Success'
        assert call_count['count'] == 2
    
    def test_schema_reminder_in_retry(self):
        """Test that schema reminder is included in retry instruction."""
        mock_agent = Mock()
        mock_agent.output_key = 'output'
        original_instruction = 'Original instruction'
        mock_agent.instruction = original_instruction
        
        mock_agent.invoke = Mock(side_effect=[
            {'output': 'Not JSON'},
            {'output': json.dumps({
                'title': 'Valid',
                'content': 'Content',
                'score': 50
            })}
        ])
        
        config = OutputRetryConfig(
            max_retries=2,
            include_schema_reminder=True
        )
        
        retry_on_validation_error(
            agent=mock_agent,
            input_data={'test': 'data'},
            output_schema=SimpleTestSchema,
            config=config
        )
        
        # After successful retry, instruction should be restored
        assert mock_agent.instruction == original_instruction
        assert mock_agent.invoke.call_count == 2
    
    def test_no_retry_on_success(self):
        """Test that no retry occurs when first attempt succeeds."""
        mock_agent = Mock()
        mock_agent.output_key = 'output'
        mock_agent.instruction = 'Test'
        
        mock_agent.invoke = Mock(return_value={
            'output': {'title': 'Direct Dict', 'content': 'Content', 'score': 60}
        })
        
        config = OutputRetryConfig(max_retries=5)  # High retry count
        result = retry_on_validation_error(
            agent=mock_agent,
            input_data={'test': 'data'},
            output_schema=SimpleTestSchema,
            config=config
        )
        
        assert result['title'] == 'Direct Dict'
        assert mock_agent.invoke.call_count == 1  # No retries needed


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v'])