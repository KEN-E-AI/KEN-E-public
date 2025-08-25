"""
Models for V3 Strategy Agent System - Multi-agent sequential architecture.
Defines models for all 5 strategy document types and context management.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================================================
# Business Strategy Model
# ============================================================================

class BusinessStrategy(BaseModel):
    """Business strategy document model."""
    
    businessStrategySummary: str = Field(
        ...,
        description="A high-level summary of the company's situation, strategic direction, and key findings or recommendations."
    )
    
    companyOverview: str = Field(
        ...,
        description="A comprehensive narrative that introduces the company's identity and background."
    )
    
    marketAndIndustryAnalysis: str = Field(
        ...,
        description="A comprehensive review of the market environment including competitive landscape, TAM, and industry trends."
    )
    
    productsAndServices: str = Field(
        ...,
        description="A comprehensive description of the company's offerings, value proposition, and pricing model."
    )
    
    marketingAndCustomerStrategy: str = Field(
        ...,
        description="A comprehensive analysis of how the company engages its market, including segmentation and acquisition strategies."
    )
    
    swotAnalysis: str = Field(
        ...,
        description="A comprehensive SWOT analysis covering strengths, weaknesses, opportunities, and threats."
    )


# ============================================================================
# Competitive Strategy Model
# ============================================================================

class CompetitiveStrategy(BaseModel):
    """Competitive strategy document model."""
    
    competitiveStrategySummary: str = Field(
        ...,
        description="A high-level overview of the market, competitor landscape, and the company's position."
    )
    
    competitiveLandscape: str = Field(
        ...,
        description="A comprehensive analysis of the competitive landscape including geography, success factors, and opportunities."
    )
    
    strategicRecommendations: str = Field(
        ...,
        description="A comprehensive set of strategic recommendations based on the competitive analysis."
    )


# ============================================================================
# Customer Strategy Model
# ============================================================================

class CustomerStrategy(BaseModel):
    """Customer strategy document model."""
    
    customerProfiles: List[Dict[str, Any]] = Field(
        ...,
        description="3-5 detailed ideal customer personas with pain points and motivations."
    )
    
    customerJourneyMaps: List[Dict[str, Any]] = Field(
        ...,
        description="Journey maps for each persona showing awareness, consideration, and loyalty stages."
    )
    
    personaInsights: Dict[str, Any] = Field(
        ...,
        description="Key insights about each customer segment and their behaviors."
    )


# ============================================================================
# Marketing Strategy Model
# ============================================================================

class MarketingStrategy(BaseModel):
    """Marketing strategy document model."""
    
    channelStrategies: Dict[str, Any] = Field(
        ...,
        description="Strategies for each marketing channel (Search, YouTube, Display, Gmail)."
    )
    
    campaignPlans: List[Dict[str, Any]] = Field(
        ...,
        description="Detailed campaign plans with objectives, audiences, budgets, CPM/CPC, and KPIs."
    )
    
    messagingFramework: Dict[str, Any] = Field(
        ...,
        description="Core messaging, positioning, and value propositions for campaigns."
    )


# ============================================================================
# Brand Guidelines Model
# ============================================================================

class BrandGuidelines(BaseModel):
    """Brand guidelines document model."""
    
    brandIdentity: Dict[str, Any] = Field(
        ...,
        description="Core brand elements, values, mission, and vision."
    )
    
    visualGuidelines: Dict[str, Any] = Field(
        ...,
        description="Visual identity standards including colors, typography, and imagery."
    )
    
    voiceAndTone: Dict[str, Any] = Field(
        ...,
        description="Brand voice, tone guidelines, and communication principles."
    )
    
    brandApplications: Dict[str, Any] = Field(
        ...,
        description="How to apply brand across different channels and touchpoints."
    )


# ============================================================================
# Strategy Context Model (For passing data between agents)
# ============================================================================

class StrategyContext(BaseModel):
    """Context passed between strategy agents in the sequential flow."""
    
    # Project configuration
    project_id: str = Field(..., description="Google Cloud project ID")
    
    # Account information
    account_id: str = Field(..., description="Account ID for document scoping")
    user_id: Optional[str] = Field(None, description="User ID for attribution")
    
    # Input data from account creation
    company_name: str = Field(..., description="Company name to analyze")
    websites: List[str] = Field(default_factory=list, description="Company websites")
    industry: str = Field(..., description="Industry description")
    customer_regions: List[str] = Field(default_factory=list, description="Target regions")
    annual_ad_budget: Optional[float] = Field(None, description="Estimated annual advertising budget")
    supporting_documents: Optional[List[str]] = Field(None, description="Additional documents provided")
    
    # Progressive strategy documents (filled as agents complete)
    business_strategy: Optional[Dict[str, Any]] = Field(None, description="Completed business strategy")
    competitive_strategy: Optional[Dict[str, Any]] = Field(None, description="Completed competitive strategy")
    customer_strategy: Optional[Dict[str, Any]] = Field(None, description="Completed customer strategy")
    marketing_strategy: Optional[Dict[str, Any]] = Field(None, description="Completed marketing strategy")
    brand_guidelines: Optional[Dict[str, Any]] = Field(None, description="Completed brand guidelines")
    
    # Processing metadata
    current_stage: str = Field(default="business_strategy", description="Current processing stage")
    stages_completed: List[str] = Field(default_factory=list, description="Completed stages")
    stages_remaining: List[str] = Field(
        default_factory=lambda: ["business_strategy", "competitive_strategy", "customer_strategy", "marketing_strategy", "brand_guidelines"],
        description="Remaining stages"
    )
    iteration_counts: Dict[str, int] = Field(default_factory=dict, description="Iteration count per stage")
    processing_errors: List[str] = Field(default_factory=list, description="Any errors encountered")
    
    # Timestamps
    started_at: Optional[datetime] = Field(None, description="Processing start time")
    completed_at: Optional[datetime] = Field(None, description="Processing completion time")
    
    def get_previous_outputs(self, for_agent: str) -> Dict[str, Any]:
        """
        Get relevant outputs from previous agents for the current agent.
        Based on the Excel specifications for variable passing.
        """
        outputs = {}
        
        if for_agent == "competitive_strategy":
            # Competitive strategy needs all 6 fields from business strategy
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
        setattr(self, stage.replace("_", "_"), result)
        
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
            self.completed_at = datetime.utcnow()


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


# Backward compatibility exports (these will be removed after full migration)
StrategyDocument = BusinessStrategy  # Alias for backward compatibility
StrategyRequest = StrategyGenerationRequest  # Alias for backward compatibility