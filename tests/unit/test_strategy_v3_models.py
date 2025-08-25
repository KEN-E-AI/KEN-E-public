#!/usr/bin/env python
"""Unit tests for V3 Strategy Agent models and utilities - no ADK dependencies"""

import pytest
from datetime import datetime
import sys
import os

# Add specific module paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))


def test_strategy_context():
    """Test StrategyContext model and methods"""
    from app.simple_company_chatbot.agents.strategy_agent.models import StrategyContext
    
    # Test initialization
    context = StrategyContext(
        account_id='test_account',
        company_name='Test Corp',
        websites=['https://test.com'],
        industry='Technology',
        customer_regions=['USA']
    )
    
    assert context.account_id == 'test_account'
    assert context.company_name == 'Test Corp'
    assert context.current_stage == 'business_strategy'
    assert len(context.stages_remaining) == 5
    assert context.stages_completed == []
    assert context.business_strategy is None
    assert context.competitive_strategy is None
    
    # Test marking stage complete
    business_doc = {
        "businessStrategySummary": "Test summary",
        "coreValueProposition": "Test value",
        "strategicObjectives": ["Obj1", "Obj2"],
        "swotAnalysis": {"strengths": ["S1"], "weaknesses": ["W1"]},
        "revenueStreams": ["Stream1"],
        "growthOpportunities": ["Opp1"]
    }
    
    context.mark_stage_complete('business_strategy', business_doc)
    
    assert context.business_strategy == business_doc
    assert 'business_strategy' in context.stages_completed
    assert 'business_strategy' not in context.stages_remaining
    assert context.current_stage == 'competitive_strategy'


def test_context_passing():
    """Test context passing between agents"""
    from app.simple_company_chatbot.agents.strategy_agent.models import StrategyContext
    
    context = StrategyContext(
        account_id='test',
        company_name='Test',
        websites=['https://test.com'],
        industry='Tech',
        customer_regions=['USA']
    )
    
    # Set up business strategy
    business_doc = {
        "businessStrategySummary": "Summary",
        "coreValueProposition": "Value",
        "strategicObjectives": ["Obj1"],
        "swotAnalysis": {"strengths": ["S1"]},
        "revenueStreams": ["Revenue1"],
        "growthOpportunities": ["Growth1"]
    }
    context.business_strategy = business_doc
    
    # Get outputs for competitive strategy
    outputs = context.get_previous_outputs('competitive_strategy')
    
    assert 'business_strategy.businessStrategySummary' in outputs
    assert outputs['business_strategy.businessStrategySummary'] == "Summary"
    assert 'business_strategy.coreValueProposition' in outputs
    assert outputs['business_strategy.coreValueProposition'] == "Value"
    assert len(outputs) == 6  # All 6 business strategy fields


def test_all_stages_progression():
    """Test completing all stages in sequence"""
    from app.simple_company_chatbot.agents.strategy_agent.models import StrategyContext
    
    context = StrategyContext(
        account_id='test',
        company_name='Test',
        websites=['https://test.com'],
        industry='Tech',
        customer_regions=['USA']
    )
    
    stages = [
        'business_strategy',
        'competitive_strategy',
        'customer_strategy',
        'marketing_strategy',
        'brand_guidelines'
    ]
    
    for i, stage in enumerate(stages):
        # Verify current state before completing
        assert context.current_stage == stage
        assert len(context.stages_completed) == i
        assert len(context.stages_remaining) == 5 - i
        
        # Complete the stage
        context.mark_stage_complete(stage, {f"{stage}_data": f"test_{i}"})
    
    # Verify final state
    assert context.current_stage == 'completed'
    assert len(context.stages_completed) == 5
    assert len(context.stages_remaining) == 0
    assert context.completed_at is not None


def test_parse_json_response():
    """Test JSON parsing utility"""
    from app.simple_company_chatbot.agents.strategy_agent.utils import parse_json_response
    
    # Test direct JSON
    json_str = '{"key": "value", "number": 42}'
    result = parse_json_response(json_str)
    assert result is not None
    assert result['key'] == 'value'
    assert result['number'] == 42
    
    # Test JSON embedded in text
    response = 'Here is the result: {"status": "success", "data": [1, 2, 3]} Done!'
    result = parse_json_response(response)
    assert result is not None
    assert result['status'] == 'success'
    assert result['data'] == [1, 2, 3]
    
    # Test invalid JSON
    result = parse_json_response('This is not JSON')
    assert result is None
    
    # Test empty input
    result = parse_json_response('')
    assert result is None


def test_format_new_information():
    """Test formatting new information for prompt"""
    from app.simple_company_chatbot.agents.strategy_agent.utils import format_new_information
    
    info = format_new_information(
        company_name='Test Corp',
        websites=['https://test.com', 'https://blog.test.com'],
        industry='Technology',
        customer_regions=['USA', 'Europe', 'Asia'],
        annual_ad_budget=2500000.0,
        supporting_documents=['doc1.pdf', 'doc2.xlsx']
    )
    
    assert 'Company to analyze: Test Corp' in info
    assert 'Company websites: [' in info
    assert 'https://test.com' in info
    assert 'Industry: Technology' in info
    assert 'Customer regions: USA, Europe, Asia' in info
    assert 'Estimated annual ad budget: $2,500,000.00' in info
    assert 'Supporting documents: [' in info


def test_strategy_generation_request():
    """Test StrategyGenerationRequest model"""
    from app.simple_company_chatbot.agents.strategy_agent.models import StrategyGenerationRequest
    
    # Test minimal request
    request = StrategyGenerationRequest(
        account_id='test_account',
        company_name='Test Corp',
        websites=['https://test.com'],
        industry='Technology',
        customer_regions=['USA']
    )
    
    assert request.account_id == 'test_account'
    assert request.company_name == 'Test Corp'
    assert request.start_from_stage is None  # Default value
    assert request.user_id is None  # Optional field
    
    # Test with all fields
    request2 = StrategyGenerationRequest(
        account_id='test2',
        company_name='Test2',
        websites=['https://test2.com'],
        industry='Tech',
        customer_regions=['Global'],
        start_from_stage='competitive_strategy',
        user_id='user123',
        annual_ad_budget=1000000.0,
        supporting_documents=['doc.pdf']
    )
    
    assert request2.start_from_stage == 'competitive_strategy'
    assert request2.user_id == 'user123'
    assert request2.annual_ad_budget == 1000000.0
    assert len(request2.supporting_documents) == 1


def test_strategy_generation_response():
    """Test StrategyGenerationResponse model"""
    from app.simple_company_chatbot.agents.strategy_agent.models import StrategyGenerationResponse
    
    response = StrategyGenerationResponse(
        success=True,
        account_id='test_account',
        stages_completed=['business_strategy', 'competitive_strategy'],
        stages_remaining=['customer_strategy', 'marketing_strategy', 'brand_guidelines'],
        current_stage='customer_strategy',
        errors=[],
        started_at=datetime.utcnow(),
        completed_at=None
    )
    
    assert response.success is True
    assert len(response.stages_completed) == 2
    assert len(response.stages_remaining) == 3
    assert response.current_stage == 'customer_strategy'
    assert len(response.errors) == 0
    assert response.completed_at is None
    
    # Test with errors
    response2 = StrategyGenerationResponse(
        success=False,
        account_id='test_account',
        stages_completed=[],
        stages_remaining=['business_strategy'],
        current_stage='business_strategy',
        errors=['Error 1', 'Error 2'],
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    
    assert response2.success is False
    assert len(response2.errors) == 2
    assert response2.completed_at is not None


def test_context_accumulation():
    """Test that context accumulates correctly through all stages"""
    from app.simple_company_chatbot.agents.strategy_agent.models import StrategyContext
    
    context = StrategyContext(
        account_id='test',
        company_name='Test',
        websites=['https://test.com'],
        industry='Tech',
        customer_regions=['USA']
    )
    
    # Simulate completing stages with minimal data
    context.business_strategy = {"businessStrategySummary": "BS"}
    context.competitive_strategy = {"competitiveAnalysis": "CA"}
    context.customer_strategy = {"targetAudience": "TA"}
    
    # Test that marketing strategy gets all previous outputs
    marketing_outputs = context.get_previous_outputs('marketing_strategy')
    
    assert 'business_strategy.businessStrategySummary' in marketing_outputs
    assert marketing_outputs['business_strategy.businessStrategySummary'] == "BS"
    assert 'competitive_strategy.competitiveAnalysis' in marketing_outputs
    assert marketing_outputs['competitive_strategy.competitiveAnalysis'] == "CA"
    assert 'customer_strategy.targetAudience' in marketing_outputs
    assert marketing_outputs['customer_strategy.targetAudience'] == "TA"
    
    # Test that brand guidelines gets everything
    context.marketing_strategy = {"marketingChannels": "MC"}
    brand_outputs = context.get_previous_outputs('brand_guidelines')
    
    assert 'business_strategy.businessStrategySummary' in brand_outputs
    assert 'competitive_strategy.competitiveAnalysis' in brand_outputs
    assert 'customer_strategy.targetAudience' in brand_outputs
    assert 'marketing_strategy.marketingChannels' in brand_outputs
    assert brand_outputs['marketing_strategy.marketingChannels'] == "MC"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])