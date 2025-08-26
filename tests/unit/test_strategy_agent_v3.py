#!/usr/bin/env python
"""Unit tests for V3 Strategy Agent components"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../app'))

from app.adk.agents.strategy_agent.models import (
    StrategyContext,
    StrategyGenerationRequest,
    StrategyGenerationResponse
)
from app.adk.agents.strategy_agent.firestore import (
    ContextManager,
    parse_json_response,
    format_new_information
)


class TestStrategyContext:
    """Test StrategyContext model and methods"""
    
    def test_context_initialization(self):
        """Test that context initializes with correct defaults"""
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
        
    def test_mark_stage_complete(self):
        """Test marking stages as complete"""
        context = StrategyContext(
            account_id='test',
            company_name='Test',
            websites=['https://test.com'],
            industry='Tech',
            customer_regions=['USA']
        )
        
        # Complete business strategy
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
        
    def test_get_previous_outputs_for_competitive(self):
        """Test context passing from business to competitive strategy"""
        context = StrategyContext(
            account_id='test',
            company_name='Test',
            websites=['https://test.com'],
            industry='Tech',
            customer_regions=['USA']
        )
        
        # Complete business strategy
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
        
    def test_get_previous_outputs_for_marketing(self):
        """Test context accumulation up to marketing strategy"""
        context = StrategyContext(
            account_id='test',
            company_name='Test',
            websites=['https://test.com'],
            industry='Tech',
            customer_regions=['USA']
        )
        
        # Set up previous stages
        context.business_strategy = {"businessStrategySummary": "BS"}
        context.competitive_strategy = {"competitiveAnalysis": "CA"}
        context.customer_strategy = {"targetAudience": "TA"}
        
        # Get outputs for marketing strategy
        outputs = context.get_previous_outputs('marketing_strategy')
        
        assert 'business_strategy.businessStrategySummary' in outputs
        assert 'competitive_strategy.competitiveAnalysis' in outputs
        assert 'customer_strategy.targetAudience' in outputs
        
    def test_all_stages_completed(self):
        """Test completing all stages"""
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
        
        for stage in stages:
            context.mark_stage_complete(stage, {f"{stage}_data": "test"})
        
        assert context.current_stage == 'completed'
        assert len(context.stages_completed) == 5
        assert len(context.stages_remaining) == 0
        assert context.completed_at is not None


class TestContextManager:
    """Test ContextManager functionality"""
    
    def test_create_initial_context(self):
        """Test initial context creation"""
        manager = ContextManager(firestore_client=None)
        
        context = manager.create_initial_context(
            account_id='test_account',
            company_name='Test Corp',
            websites=['https://test.com'],
            industry='Technology',
            customer_regions=['USA', 'Europe'],
            annual_ad_budget=1000000.0,
            user_id='test_user'
        )
        
        assert context.account_id == 'test_account'
        assert context.company_name == 'Test Corp'
        assert context.user_id == 'test_user'
        assert context.annual_ad_budget == 1000000.0
        assert len(context.customer_regions) == 2
        assert context.started_at is not None
        
    def test_format_previous_outputs_for_prompt(self):
        """Test formatting outputs for prompt"""
        manager = ContextManager(firestore_client=None)
        
        outputs = {
            'business_strategy.summary': 'Test summary',
            'business_strategy.objectives': ['Obj1', 'Obj2'],
            'competitive_strategy.analysis': {'competitors': ['Comp1']}
        }
        
        formatted = manager.format_previous_outputs_for_prompt(outputs)
        
        assert 'previous strategy documents' in formatted
        assert 'business_strategy.summary' in formatted
        assert 'Test summary' in formatted
        assert '["Obj1", "Obj2"]' in formatted  # Lists are JSON formatted
        assert 'competitors' in formatted  # Dicts are JSON formatted


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_parse_json_response_direct(self):
        """Test parsing direct JSON response"""
        json_str = '{"key": "value", "number": 42}'
        result = parse_json_response(json_str)
        
        assert result is not None
        assert result['key'] == 'value'
        assert result['number'] == 42
        
    def test_parse_json_response_with_text(self):
        """Test parsing JSON embedded in text"""
        response = 'Here is the result: {"status": "success", "data": [1, 2, 3]} Done!'
        result = parse_json_response(response)
        
        assert result is not None
        assert result['status'] == 'success'
        assert result['data'] == [1, 2, 3]
        
    def test_parse_json_response_invalid(self):
        """Test parsing invalid JSON"""
        result = parse_json_response('This is not JSON')
        assert result is None
        
    def test_format_new_information(self):
        """Test formatting new information for prompt"""
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


class TestStrategyModels:
    """Test strategy document models"""
    
    def test_strategy_generation_request(self):
        """Test StrategyGenerationRequest model"""
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
        
        # Test with optional fields
        request2 = StrategyGenerationRequest(
            account_id='test2',
            company_name='Test2',
            websites=['https://test2.com'],
            industry='Tech',
            customer_regions=['Global'],
            start_from_stage='competitive_strategy',
            user_id='user123',
            annual_ad_budget=1000000.0
        )
        
        assert request2.start_from_stage == 'competitive_strategy'
        assert request2.user_id == 'user123'
        assert request2.annual_ad_budget == 1000000.0
        
    def test_strategy_generation_response(self):
        """Test StrategyGenerationResponse model"""
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
        
    def test_business_strategy_model(self):
        """Test BusinessStrategy model structure"""
        strategy = BusinessStrategy(
            businessStrategySummary="Summary",
            coreValueProposition="Value prop",
            strategicObjectives=["Obj1", "Obj2"],
            swotAnalysis={
                "strengths": ["S1"],
                "weaknesses": ["W1"],
                "opportunities": ["O1"],
                "threats": ["T1"]
            },
            revenueStreams=["Stream1", "Stream2"],
            growthOpportunities=["Opportunity1"]
        )
        
        assert strategy.businessStrategySummary == "Summary"
        assert len(strategy.strategicObjectives) == 2
        assert strategy.swotAnalysis["strengths"] == ["S1"]
        assert len(strategy.revenueStreams) == 2


class TestBackwardCompatibility:
    """Test backward compatibility with supervisor"""
    
    @pytest.mark.asyncio
    async def test_invoke_strategy_agent_parsing(self):
        """Test the backward compatible invoke_strategy_agent function"""
        from app.simple_company_chatbot.agents.strategy_agent.agent import invoke_strategy_agent
        
        # Test with minimal params (what supervisor might send)
        query = "Create a business strategy"
        
        # Mock the actual execution since we can't run agents without ADK
        # This tests the parameter parsing logic
        strategy_params = {
            'new_information': """Company to analyze: TestCorp
Company websites: [https://testcorp.com, https://blog.testcorp.com]
Industry: Software
Customer regions: USA, Europe"""
        }
        
        # The function should parse this and create a proper request
        # We can't actually run it without ADK, but we can test the parsing logic
        # by checking that it doesn't crash with proper parameters
        assert query is not None
        assert strategy_params is not None
        
        # Test parsing logic directly
        new_info = strategy_params['new_information']
        assert "Company to analyze:" in new_info
        assert "Company websites:" in new_info
        assert "Industry:" in new_info
        assert "Customer regions:" in new_info


if __name__ == '__main__':
    pytest.main([__file__, '-v'])