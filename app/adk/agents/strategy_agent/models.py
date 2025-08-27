"""
Models for Strategy Agent - Multi-agent sequential architecture.
Defines context and API models for strategy generation.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime, timezone


# ============================================================================
# Strategy Context Model
# ============================================================================

class StrategyContext(BaseModel):
    """
    Main context object passed between strategy agents.
    Stores company information and generated strategy documents.
    
    Note: Strategy documents are stored as Dict[str, Any] rather than 
    typed models for flexibility during agent generation.
    """
    
    # Basic company information
    account_id: str = Field(..., description="Unique account identifier")
    company_name: str = Field(..., description="Company name")
    websites: List[str] = Field(default_factory=list, description="Company websites")
    industry: str = Field(..., description="Company industry")
    customer_regions: List[str] = Field(default_factory=list, description="Customer regions")
    annual_ad_budget: Optional[float] = Field(None, description="Annual advertising budget")
    
    # Optional supporting documents and context
    supporting_documents: Optional[List[str]] = Field(None, description="Paths to supporting documents")
    user_id: Optional[str] = Field(None, description="User ID making the request")
    
    # Strategy documents (stored as dicts during generation)
    business_strategy: Optional[Dict[str, Any]] = None
    competitive_strategy: Optional[Dict[str, Any]] = None
    customer_strategy: Optional[Dict[str, Any]] = None
    marketing_strategy: Optional[Dict[str, Any]] = None
    brand_guidelines: Optional[Dict[str, Any]] = None
    
    # Tracking fields
    stages_completed: List[str] = Field(default_factory=list)
    stages_remaining: List[str] = Field(
        default_factory=lambda: [
            "business_strategy",
            "competitive_strategy", 
            "customer_strategy",
            "marketing_strategy",
            "brand_guidelines"
        ]
    )
    current_stage: str = Field(default="business_strategy")
    
    # Timestamps
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    
    # Error tracking
    errors: List[str] = Field(default_factory=list)
    
    def get_previous_outputs(self, for_agent: str) -> Dict[str, Any]:
        """
        Get the outputs from previous agents formatted for the current agent.
        Each agent needs specific fields from previous agents as defined in the V3 spec.
        
        Args:
            for_agent: The agent requesting previous outputs
            
        Returns:
            Dictionary of previous outputs formatted for the agent
        """
        outputs = {}
        
        # Always include basic context
        outputs["company_name"] = self.company_name
        outputs["industry"] = self.industry
        outputs["websites"] = self.websites
        outputs["customer_regions"] = self.customer_regions
        outputs["annual_ad_budget"] = self.annual_ad_budget
        
        # Add stage-specific previous outputs based on V3 requirements
        if for_agent == "competitive_strategy":
            # Competitive strategy needs all fields from business strategy
            if self.business_strategy:
                outputs.update({
                    "business_strategy.businessStrategySummary": self.business_strategy.get("businessStrategySummary"),
                    "business_strategy.companyOverview": self.business_strategy.get("companyOverview"),
                    "business_strategy.marketAndIndustryAnalysis": self.business_strategy.get("marketAndIndustryAnalysis"),
                    "business_strategy.productsAndServices": self.business_strategy.get("productsAndServices"),
                    "business_strategy.marketingAndCustomerStrategy": self.business_strategy.get("marketingAndCustomerStrategy"),
                    "business_strategy.swotAnalysis": self.business_strategy.get("swotAnalysis")
                })
                
        elif for_agent == "customer_strategy":
            # Customer strategy needs fields from both business and competitive
            if self.business_strategy:
                outputs.update({
                    "business_strategy.businessStrategySummary": self.business_strategy.get("businessStrategySummary"),
                    "business_strategy.companyOverview": self.business_strategy.get("companyOverview"),
                    "business_strategy.marketAndIndustryAnalysis": self.business_strategy.get("marketAndIndustryAnalysis"),
                    "business_strategy.productsAndServices": self.business_strategy.get("productsAndServices"),
                    "business_strategy.marketingAndCustomerStrategy": self.business_strategy.get("marketingAndCustomerStrategy"),
                    "business_strategy.swotAnalysis": self.business_strategy.get("swotAnalysis")
                })
            
            if self.competitive_strategy:
                outputs.update({
                    "competitive_strategy.competitiveLandscape": self.competitive_strategy.get("competitiveLandscape"),
                    "competitive_strategy.competitiveStrategySummary": self.competitive_strategy.get("competitiveStrategySummary"),
                    "competitive_strategy.strategicRecommendations": self.competitive_strategy.get("strategicRecommendations")
                })
                
        elif for_agent == "marketing_strategy":
            # Marketing strategy needs fields from business, competitive, and customer
            if self.business_strategy:
                outputs.update({
                    "business_strategy.businessStrategySummary": self.business_strategy.get("businessStrategySummary"),
                    "business_strategy.companyOverview": self.business_strategy.get("companyOverview"),
                    "business_strategy.marketAndIndustryAnalysis": self.business_strategy.get("marketAndIndustryAnalysis"),
                    "business_strategy.productsAndServices": self.business_strategy.get("productsAndServices"),
                    "business_strategy.marketingAndCustomerStrategy": self.business_strategy.get("marketingAndCustomerStrategy"),
                    "business_strategy.swotAnalysis": self.business_strategy.get("swotAnalysis")
                })
            
            if self.competitive_strategy:
                outputs.update({
                    "competitive_strategy.competitiveLandscape": self.competitive_strategy.get("competitiveLandscape"),
                    "competitive_strategy.competitiveStrategySummary": self.competitive_strategy.get("competitiveStrategySummary"),
                    "competitive_strategy.strategicRecommendations": self.competitive_strategy.get("strategicRecommendations")
                })
            
            if self.customer_strategy:
                outputs.update({
                    "customer_strategy.customerProfiles": self.customer_strategy.get("customerProfiles"),
                    "customer_strategy.customerJourneyMaps": self.customer_strategy.get("customerJourneyMaps"),
                    "customer_strategy.personaInsights": self.customer_strategy.get("personaInsights")
                })
                
        elif for_agent == "brand_guidelines":
            # Brand guidelines needs fields from all previous agents (excluding SWOT)
            if self.business_strategy:
                outputs.update({
                    "business_strategy.businessStrategySummary": self.business_strategy.get("businessStrategySummary"),
                    "business_strategy.companyOverview": self.business_strategy.get("companyOverview"),
                    "business_strategy.marketAndIndustryAnalysis": self.business_strategy.get("marketAndIndustryAnalysis"),
                    "business_strategy.productsAndServices": self.business_strategy.get("productsAndServices"),
                    "business_strategy.marketingAndCustomerStrategy": self.business_strategy.get("marketingAndCustomerStrategy")
                    # Note: SWOT is excluded for brand guidelines
                })
            
            if self.competitive_strategy:
                outputs.update({
                    "competitive_strategy.competitiveStrategySummary": self.competitive_strategy.get("competitiveStrategySummary"),
                    "competitive_strategy.strategicRecommendations": self.competitive_strategy.get("strategicRecommendations")
                    # Note: competitiveLandscape is excluded for brand guidelines
                })
            
            if self.customer_strategy:
                outputs.update({
                    "customer_strategy.customerProfiles": self.customer_strategy.get("customerProfiles"),
                    "customer_strategy.customerJourneyMaps": self.customer_strategy.get("customerJourneyMaps"),
                    "customer_strategy.personaInsights": self.customer_strategy.get("personaInsights")
                })
            
            if self.marketing_strategy:
                outputs.update({
                    "marketing_strategy.channelStrategies": self.marketing_strategy.get("channelStrategies"),
                    "marketing_strategy.campaignPlans": self.marketing_strategy.get("campaignPlans"),
                    "marketing_strategy.messagingFramework": self.marketing_strategy.get("messagingFramework")
                })
        
        return outputs
    
    def mark_stage_complete(self, stage: str, result: Dict[str, Any]):
        """Mark a stage as complete and update context."""
        # Store the result
        setattr(self, stage.replace("-", "_"), result)
        
        # Update tracking
        if stage not in self.stages_completed:
            self.stages_completed.append(stage)
        
        if stage in self.stages_remaining:
            self.stages_remaining.remove(stage)
        
        # Update current stage to next in sequence
        sequence = ["business_strategy", "competitive_strategy", "customer_strategy", "marketing_strategy", "brand_guidelines"]
        current_index = sequence.index(stage)
        if current_index < len(sequence) - 1:
            self.current_stage = sequence[current_index + 1]
        else:
            self.current_stage = "completed"
            self.completed_at = datetime.now(timezone.utc)


# ============================================================================
# Request/Response Models for API Integration
# ============================================================================

class StrategyGenerationRequest(BaseModel):
    """Request model for strategy generation."""
    account_id: str
    company_name: str
    websites: List[str] = Field(default_factory=list)
    industry: str
    customer_regions: List[str] = Field(default_factory=list)
    annual_ad_budget: Optional[float] = None
    supporting_documents: Optional[List[str]] = None
    user_id: Optional[str] = None
    start_from_stage: Optional[str] = None  # For resuming from a specific stage


class StrategyGenerationResponse(BaseModel):
    """Response model for strategy generation."""
    success: bool
    account_id: str
    stages_completed: List[str]
    stages_remaining: List[str]
    current_stage: str
    errors: List[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: Optional[datetime] = None