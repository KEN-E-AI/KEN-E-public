# Strategy Agent V3 Implementation Plan

## Executive Summary
This document outlines the evolution from V2's single strategy agent to V3's multi-agent sequential architecture. This builds upon `STRATEGY_AGENT_V2_IMPLEMENTATION.md` which contains the original single-agent implementation and integration requirements. V3 introduces five specialized strategy agents (business, competitive, customer, marketing, brand guidelines) working in sequence, each with its own refinement loop, building progressively on previous agents' outputs using ADK's Context/State management.

**Important**: This document incorporates and extends all requirements from `STRATEGY_AGENT_V2_IMPLEMENTATION.md`. Refer to that document for the complete V2 baseline implementation details.

## Related Documents
- **`STRATEGY_AGENT_V2_IMPLEMENTATION.md`**: The baseline V2 implementation with single strategy agent
- **`ken_e_agents_restructure.xlsx`**: Excel file with detailed specifications for each of the 5 strategy agents

## Architecture Evolution

### V2 Architecture (Current)
- **Single Agent**: One iterative strategy agent handling all document types
- **Simple Parameters**: Different strategy types selected via `doc_type` parameter
- **Isolated Documents**: Each strategy document created independently

### V3 Architecture (Target)
- **Multi-Agent Sequential**: 5 specialized agents in a defined sequence
- **Progressive Building**: Each agent builds on previous agents' outputs
- **Context Passing**: ADK State management for inter-agent communication
- **Specialized Loops**: Each agent has its own strategist-reviewer-editor refinement loop

## Sequential Agent Flow

```
Start 
  ↓
Business Strategy Agent (with refinement loop)
  ↓ (passes: summary, overview, market analysis, products, customer strategy, SWOT)
Competitive Strategy Agent (with refinement loop)  
  ↓ (passes: competitive landscape, strategy summary, recommendations)
Customer Strategy Agent (with refinement loop)
  ↓ (passes: customer profiles, journey maps, persona insights)
Marketing Strategy Agent (with refinement loop)
  ↓ (passes: channel strategies, campaigns, messaging)
Brand Guidelines Agent (with refinement loop)
  ↓
End
```

## User Stories (Requirements) - From V2

**Note**: These user stories are copied verbatim from `STRATEGY_AGENT_V2_IMPLEMENTATION.md` with V3 enhancements added. Refer to the V2 document for the original requirements.

### User Story 1: Auto-Generate During Account Creation

**As a new marketer**, I want to provide my company's website URL during account creation and have the system automatically research and build my strategic knowledge base, **So that** the application can learn about my business and provide personalized recommendations without manual data entry.

#### Acceptance Criteria
- Given a new marketer is creating an account, When they submit the 'create account' form containing a website URL, Then a background process is initiated to create the five strategy documents
- Given the knowledge base creation process has not completed, When the marketer lands on the homepage, Then the page should be in a non-interactive state and display a message indicating the process is running and may take up to one hour
- Given the knowledge base creation process has successfully completed, When the marketer is on the application homepage, Then the "in-progress" message is removed and the full interactivity of the page is enabled
- Given the knowledge base creation process has successfully completed, When the process finishes, Then the marketer should receive an email notification confirming their account is ready
- Given the knowledge base is ready and the homepage is interactive, When the user first views the interactive page, Then a product tour should be initiated

#### V3 Enhancement
- Progress indicator shows which agent is currently processing (1/5, 2/5, etc.)
- Estimated time updates based on which agent is running

### User Story 2: Document Upload Through Chat

**As a marketer**, I want to upload a document (e.g., a business plan) through the KEN-E chat interface, **So that** I can provide the AI with specific, pre-existing information to improve the accuracy of its recommendations.

#### Acceptance Criteria
- Given I am interacting with the chat interface, When I use the file upload option, Then I should be able to select a supported file (PDF, .docx, etc) from my local system
- Given I have successfully uploaded a document, When the system begins processing it, Then the document is sent to the appropriate strategy agent based on content analysis
- Given a document has been uploaded for processing, When the user is in the chat interface, Then they should receive a confirmation message acknowledging the upload and that the information is being reviewed

#### V3 Enhancement
- Document content is analyzed to determine which strategy agents need updating
- Multiple agents may be triggered if document contains relevant information for several strategies

### User Story 3: Feedback-Based Updates

**As a marketer**, I want to tell KEN-E when information it has is incorrect, **So that** I can easily correct the AI's understanding and refine my strategic knowledge base.

#### Acceptance Criteria
- Given I am having a conversation with the chat agent, When I provide direct textual feedback indicating a piece of information is incorrect, Then the feedback is routed to the appropriate strategy agent(s)
- Given I have submitted corrective feedback, When my feedback is successfully received by the system, Then the chat interface should display a confirmation message

#### V3 Enhancement
- System determines which strategy documents are affected by the correction
- Dependent strategies are automatically updated in sequence

## Agent Specifications (From Excel)

### 1. Business Strategy Agent

**Query/Instruction**:
```
Your task is to create a comprehensive business strategy document that follows the BEST PRACTICES for the company specified in the NEW INFORMATION.
This document will serve as the foundation for downstream tactical marketing plans.
Use your tool 'google_search_agent' to review the website provided in the NEW INFORMATION, and search for relevant information about the business on the Internet.

Some queries you can use to learn about the business strategy include:
- '{company name} industry'
- '{company name} competitors in the industry: {industry}'
```

**Inputs**:
- **New Information**: Company to analyze: {account name}, Company websites: [{websites}], Industry: {industry name and description}, Customer regions: {customer region}, Estimated annual ad budget: {estimated annual ad budget}, Supporting documents: {other business docs uploaded by the user}
- **Best Practices**: `<get from Firestore: /strategy_doc_guides/business_strategy_best_practices>`
- **Reviewer Guidelines**: `<get from Firestore: /strategy_doc_guides/business_strategy_reviewer_guidelines>`
- **Strategy Doc**: None (for first run) or existing document (for updates)

**Output Fields Required** (for downstream agents):
- `businessStrategySummary`: High-level summary of company's situation and strategic direction
- `companyOverview`: Comprehensive narrative of company identity and background
- `marketAndIndustryAnalysis`: Review of market environment and competitive landscape
- `productsAndServices`: Description of company offerings and value proposition
- `marketingAndCustomerStrategy`: Analysis of market engagement approach
- `swotAnalysis`: Complete SWOT analysis

### 2. Competitive Strategy Agent

**Query/Instruction**:
```
Your task is to create a comprehensive competitive strategy document that follows the BEST PRACTICES document for the company specified in the NEW INFORMATION provided.
This document will serve as the foundation for downstream tactical marketing plans.
You have been provided with the following information about the business:
[Lists all fields from business strategy agent output]

TOOLS: Use your tool 'google_search_agent' to conduct research on the business and its competitors using Google search.
```

**Inputs**:
- **From Previous Agent**: All 6 fields from business strategy agent
- **New Information**: Same as business strategy agent
- **Best Practices**: `<get from Firestore: /strategy_doc_guides/competitive_strategy_best_practices>`
- **Reviewer Guidelines**: `<get from Firestore: /strategy_doc_guides/competitive_strategy_reviewer_guidelines>`
- **Strategy Doc**: None or existing

**Output Fields Required**:
- `competitiveLandscape`: Analysis of competitive environment and opportunities
- `competitiveStrategySummary`: Overview of market and company position
- `strategicRecommendations`: Comprehensive strategic recommendations

### 3. Customer Strategy Agent

**Query/Instruction**:
```
Your task is to create a comprehensive customer strategy document that follows the BEST PRACTICES document for the company specified in the NEW INFORMATION provided.
Think carefully about the ideal customer profiles, and create 3-5 ideal customer profiles that showcase the different pain points and buyer motivation for each persona.
Consider how customers within each persona might become aware of the company, the critical information that they are looking for when considering making a purchase, and how they might become loyal return customers in the future.
```

**Inputs**:
- **From Business Strategy**: All 6 fields
- **From Competitive Strategy**: All 3 fields
- **New Information**: Same as previous agents
- **Best Practices**: `<get from Firestore: /strategy_doc_guides/customer_strategy_best_practices>`
- **Reviewer Guidelines**: `<get from Firestore: /strategy_doc_guides/customer_strategy_reviewer_guidelines>`

**Output Fields Required**:
- `customerProfiles`: 3-5 detailed ideal customer personas
- `customerJourneyMaps`: Journey maps for each persona
- `personaInsights`: Key insights about each customer segment

### 4. Marketing Strategy Agent

**Query/Instruction**:
```
Your task is to create a comprehensive marketing strategy document that follows the BEST PRACTICES document for the company specified in the NEW INFORMATION provided.
You must propose paid digital marketing campaigns for key channels such as Search, Youtube, Display and Gmail. For each campaign, describe the objective, audience, budget allocation, expected outcomes, expected CPM or CPC, and KPIs.
```

**Inputs**:
- **From Business Strategy**: 6 fields
- **From Competitive Strategy**: 3 fields  
- **From Customer Strategy**: 3 fields
- **New Information**: Same as previous
- **Best Practices**: `<get from Firestore: /strategy_doc_guides/marketing_strategy_best_practices>`
- **Reviewer Guidelines**: `<get from Firestore: /strategy_doc_guides/marketing_strategy_reviewer_guidelines>`

**Output Fields Required**:
- `channelStrategies`: Strategies for each marketing channel
- `campaignPlans`: Detailed campaign plans with budgets and KPIs
- `messagingFramework`: Core messaging and positioning

### 5. Brand Guidelines Agent

**Query/Instruction**:
```
Your task is to create a comprehensive brand guidelines document that follows the BEST PRACTICES document for the company specified in the NEW INFORMATION provided.
This document will serve as the foundation for all marketing communications and ensure brand consistency across all touchpoints.
```

**Inputs**:
- **From Business Strategy**: 5 fields (excluding SWOT)
- **From Competitive Strategy**: 2 fields (summary and recommendations)
- **From Customer Strategy**: All 3 fields
- **From Marketing Strategy**: All 3 fields
- **New Information**: Same as previous
- **Best Practices**: `<get from Firestore: /strategy_doc_guides/brand_guidelines_best_practices>`
- **Reviewer Guidelines**: `<get from Firestore: /strategy_doc_guides/brand_guidelines_reviewer_guidelines>`

**Output Fields Required**:
- `brandIdentity`: Core brand elements and values
- `visualGuidelines`: Visual identity standards
- `voiceAndTone`: Brand voice and communication guidelines
- `brandApplications`: How to apply brand across channels

## Technical Implementation

### 1. ADK Context/State Management

```python
from google.adk import Context, State
from typing import Dict, Any, Optional
from pydantic import BaseModel

class StrategyContext(BaseModel):
    """Context passed between strategy agents."""
    
    # Account information
    account_id: str
    user_id: Optional[str]
    
    # Input data
    company_name: str
    websites: List[str]
    industry: str
    customer_regions: List[str]
    annual_ad_budget: Optional[float]
    supporting_documents: Optional[List[str]]
    
    # Progressive strategy documents
    business_strategy: Optional[Dict[str, Any]] = None
    competitive_strategy: Optional[Dict[str, Any]] = None
    customer_strategy: Optional[Dict[str, Any]] = None
    marketing_strategy: Optional[Dict[str, Any]] = None
    brand_guidelines: Optional[Dict[str, Any]] = None
    
    # Processing metadata
    current_stage: str = "business_strategy"
    iteration_count: Dict[str, int] = {}
    processing_errors: List[str] = []
    
    def get_previous_outputs(self, for_agent: str) -> Dict[str, Any]:
        """Get relevant outputs from previous agents for the current agent."""
        outputs = {}
        
        if for_agent == "competitive_strategy":
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
            # Include business strategy outputs
            if self.business_strategy:
                outputs.update({
                    "business_strategy.businessStrategySummary": self.business_strategy.get("businessStrategySummary"),
                    # ... (all 6 fields)
                })
            # Include competitive strategy outputs
            if self.competitive_strategy:
                outputs.update({
                    "competitive_strategy.competitiveLandscape": self.competitive_strategy.get("competitiveLandscape"),
                    "competitive_strategy.competitiveStrategySummary": self.competitive_strategy.get("competitiveStrategySummary"),
                    "competitive_strategy.strategicRecommendations": self.competitive_strategy.get("strategicRecommendations")
                })
                
        # Similar patterns for marketing_strategy and brand_guidelines
        
        return outputs
```

### 2. Agent Factory Pattern

```python
class StrategyAgentFactory:
    """Factory for creating specialized strategy agents with proper context."""
    
    @staticmethod
    def create_business_strategy_agent(context: StrategyContext) -> SequentialAgent:
        """Create business strategy agent with its refinement loop."""
        
        strategist = Agent(
            name="business_strategist",
            model="gemini-2.0-flash",
            instruction=BUSINESS_STRATEGY_INSTRUCTION,
            tools=[google_search_agent, internal_search_agent]
        )
        
        reviewer = Agent(
            name="business_reviewer",
            model="gemini-2.0-flash",
            instruction=BUSINESS_REVIEWER_INSTRUCTION
        )
        
        editor = Agent(
            name="business_editor",
            model="gemini-2.0-flash",
            instruction=BUSINESS_EDITOR_INSTRUCTION,
            tools=[google_search_agent, internal_search_agent, exit_loop]
        )
        
        refinement_loop = LoopAgent(
            name="business_refinement_loop",
            sub_agents=[reviewer, editor],
            max_iterations=3
        )
        
        return SequentialAgent(
            name="business_strategy_agent",
            sub_agents=[strategist, refinement_loop]
        )
    
    # Similar methods for other 4 agents...
```

### 3. Main Orchestrator

```python
class StrategyOrchestrator:
    """Orchestrates the sequential execution of all strategy agents."""
    
    def __init__(self):
        self.agent_sequence = [
            "business_strategy",
            "competitive_strategy", 
            "customer_strategy",
            "marketing_strategy",
            "brand_guidelines"
        ]
        
    async def execute_strategy_generation(
        self,
        context: StrategyContext,
        start_from: Optional[str] = None
    ) -> StrategyContext:
        """Execute the full strategy generation sequence."""
        
        # Determine starting point
        start_index = 0
        if start_from and start_from in self.agent_sequence:
            start_index = self.agent_sequence.index(start_from)
        
        # Execute agents in sequence
        for agent_name in self.agent_sequence[start_index:]:
            context.current_stage = agent_name
            
            # Update UI/status
            await self.update_progress(context.account_id, agent_name)
            
            # Get agent
            agent = StrategyAgentFactory.create_agent(agent_name, context)
            
            # Prepare inputs
            inputs = self.prepare_agent_inputs(agent_name, context)
            
            # Execute agent
            result = await self.execute_agent(agent, inputs)
            
            # Store result in context
            setattr(context, agent_name, result)
            
            # Save to Firestore
            await self.save_strategy_document(
                context.account_id,
                agent_name,
                result
            )
        
        return context
```

## Implementation Phases

### Phase 0: Template Migration (Day 1) - CRITICAL FIRST STEP
**MUST BE COMPLETED BEFORE ANY OTHER WORK**

**Note**: This phase is identical to Phase 0 in `STRATEGY_AGENT_V2_IMPLEMENTATION.md` and must be completed for both V2 and V3 implementations.

Extract from notebook (`KEN_E____ADK____Iterative_Strategy_Agent.ipynb`):
1. Business strategy best practices and reviewer guidelines
2. Competitive strategy best practices and reviewer guidelines
3. Create templates for customer, marketing, and brand guidelines if not in notebook

Store in Firestore:
```
strategy_doc_guides/
├── business_strategy_best_practices
├── business_strategy_reviewer_guidelines
├── competitive_strategy_best_practices
├── competitive_strategy_reviewer_guidelines
├── customer_strategy_best_practices
├── customer_strategy_reviewer_guidelines
├── marketing_strategy_best_practices
├── marketing_strategy_reviewer_guidelines
├── brand_guidelines_best_practices
└── brand_guidelines_reviewer_guidelines
```

### Phase 1: Core Agent Development (Days 2-5)

#### 1.1 Create Agent Structure
```
app/simple_company_chatbot/agents/strategy_agent_v3/
├── __init__.py
├── models.py                      # Pydantic models for all strategies
├── context.py                     # StrategyContext implementation
├── agents/
│   ├── __init__.py
│   ├── business_strategy.py       # Business strategy agent
│   ├── competitive_strategy.py    # Competitive strategy agent
│   ├── customer_strategy.py       # Customer strategy agent
│   ├── marketing_strategy.py      # Marketing strategy agent
│   └── brand_guidelines.py        # Brand guidelines agent
├── orchestrator.py                # Main orchestrator
├── factory.py                     # Agent factory
└── utils.py                       # Helper functions
```

#### 1.2 Implement Each Agent
For each agent, implement:
- Strategist sub-agent with proper instruction from Excel
- Reviewer sub-agent with guidelines validation
- Editor sub-agent with refinement capabilities
- Exit loop condition checking

#### 1.3 Context Management
- Implement StrategyContext class
- Add methods for extracting relevant fields
- Implement state persistence between agents

### Phase 2: Integration with V2 User Stories (Days 6-8)

#### 2.1 Account Creation Hook
```python
# api/src/kene_api/routers/accounts.py
@router.post("/accounts")
async def create_account(request: AccountCreateRequest):
    # Create account
    account = await create_account_in_db(request)
    
    # Set initial status
    await update_account_setup_status(account.id, "processing")
    
    # Create strategy context
    context = StrategyContext(
        account_id=account.id,
        company_name=request.account_name,
        websites=request.websites,
        industry=request.industry,
        customer_regions=request.region,
        annual_ad_budget=request.estimated_annual_ad_budget
    )
    
    # Queue strategy generation with Cloud Tasks
    await queue_strategy_generation_v3(context)
    
    return account
```

#### 2.2 Progress Tracking
```python
# api/src/kene_api/models/kene_models.py
class Account(BaseModel):
    # ... existing fields ...
    setup_status: str = "pending"  # pending, processing, ready
    setup_stage: Optional[str] = None  # current agent being processed
    setup_progress: Optional[int] = None  # 0-100 or 1/5, 2/5, etc.
    setup_started_at: Optional[datetime] = None
    setup_completed_at: Optional[datetime] = None
```

#### 2.3 Frontend Progress Display
```tsx
// frontend/src/components/setup/SetupProgressPage.tsx
export function SetupProgressPage() {
    const [setupInfo, setSetupInfo] = useState<SetupInfo>();
    
    // Poll for updates
    useEffect(() => {
        const interval = setInterval(async () => {
            const info = await getSetupStatus();
            setSetupInfo(info);
            
            if (info.status === "ready") {
                clearInterval(interval);
                // Trigger product tour
            }
        }, 5000);
        
        return () => clearInterval(interval);
    }, []);
    
    return (
        <div className="setup-progress">
            <h2>Building Your Strategic Knowledge Base</h2>
            <div className="agent-progress">
                <ProgressStep 
                    name="Business Strategy" 
                    status={getStepStatus("business_strategy", setupInfo)} 
                />
                <ProgressStep 
                    name="Competitive Strategy" 
                    status={getStepStatus("competitive_strategy", setupInfo)} 
                />
                <ProgressStep 
                    name="Customer Strategy" 
                    status={getStepStatus("customer_strategy", setupInfo)} 
                />
                <ProgressStep 
                    name="Marketing Strategy" 
                    status={getStepStatus("marketing_strategy", setupInfo)} 
                />
                <ProgressStep 
                    name="Brand Guidelines" 
                    status={getStepStatus("brand_guidelines", setupInfo)} 
                />
            </div>
            <p>Current Stage: {setupInfo?.setup_stage || "Initializing..."}</p>
            <p>This process may take up to one hour.</p>
        </div>
    );
}
```

### Phase 3: Document Upload & Feedback Integration (Days 9-10)

#### 3.1 Document Upload Handler
```python
async def handle_document_upload(
    file: UploadFile,
    account_id: str,
    user_id: str
):
    """Process uploaded document and update relevant strategies."""
    
    # Extract content
    content = await extract_document_content(file)
    
    # Analyze content to determine affected strategies
    affected_strategies = analyze_document_relevance(content)
    
    # Create partial context with existing strategies
    context = await load_existing_context(account_id)
    context.supporting_documents = [content]
    
    # Execute only affected agents
    orchestrator = StrategyOrchestrator()
    await orchestrator.execute_strategy_generation(
        context,
        start_from=affected_strategies[0]  # Start from first affected
    )
```

#### 3.2 Feedback Processing
```python
async def process_user_feedback(
    feedback: str,
    account_id: str,
    user_id: str
):
    """Process user corrections and update strategies."""
    
    # Detect which strategies need updating
    affected = detect_affected_strategies(feedback)
    
    # Load context
    context = await load_existing_context(account_id)
    
    # Add feedback to context
    context.correction_feedback = feedback
    
    # Re-run affected agents and their dependents
    await orchestrator.execute_partial_update(
        context,
        affected_strategies=affected
    )
```

### Phase 4: Testing & Deployment (Days 11-12)

#### 4.1 Unit Tests
```python
# tests/unit/test_strategy_agents_v3.py
class TestStrategyAgentsV3:
    
    @pytest.mark.asyncio
    async def test_business_strategy_agent(self):
        """Test business strategy agent in isolation."""
        context = create_test_context()
        agent = StrategyAgentFactory.create_business_strategy_agent(context)
        result = await agent.execute(test_inputs)
        assert_valid_business_strategy(result)
    
    @pytest.mark.asyncio
    async def test_context_passing(self):
        """Test context passing between agents."""
        context = create_test_context()
        context.business_strategy = sample_business_strategy()
        
        competitive_inputs = context.get_previous_outputs("competitive_strategy")
        assert len(competitive_inputs) == 6
        assert "business_strategy.businessStrategySummary" in competitive_inputs
    
    @pytest.mark.asyncio
    async def test_full_sequence(self):
        """Test complete 5-agent sequence."""
        context = create_test_context()
        orchestrator = StrategyOrchestrator()
        
        final_context = await orchestrator.execute_strategy_generation(context)
        
        assert final_context.business_strategy is not None
        assert final_context.competitive_strategy is not None
        assert final_context.customer_strategy is not None
        assert final_context.marketing_strategy is not None
        assert final_context.brand_guidelines is not None
```

#### 4.2 Integration Tests
```python
# tests/integration/test_strategy_integration_v3.py
class TestStrategyIntegrationV3:
    
    @pytest.mark.asyncio
    async def test_account_creation_triggers_agents(self):
        """Test that account creation triggers sequential agent execution."""
        # Create account
        account = await create_test_account()
        
        # Wait for processing
        await wait_for_setup_completion(account.id, timeout=300)
        
        # Verify all strategies created
        strategies = await get_all_strategies(account.id)
        assert len(strategies) == 5
    
    @pytest.mark.asyncio
    async def test_document_upload_updates_strategies(self):
        """Test document upload triggers appropriate strategy updates."""
        # Upload document
        response = await upload_document(test_file, account_id)
        
        # Verify strategies updated
        updated_strategies = await get_updated_strategies(account_id)
        assert len(updated_strategies) > 0
```

### Phase 5: Deployment (Day 13)

#### 5.1 Deploy to Vertex AI Agent Engine
```python
# app/simple_company_chatbot/deploy_strategy_v3.py
def deploy_strategy_v3_agents():
    """Deploy the V3 strategy agent system."""
    
    deployer = AgentDeployer()
    
    return deployer.deploy_agent(
        display_name="strategy-orchestrator-v3",
        description="Multi-agent sequential strategy generation system",
        requirements=[
            "google-adk>=0.9.0",
            "pydantic>=2.0",
            "google-cloud-discoveryengine",
            "google-cloud-aiplatform",
            "google-cloud-firestore"
        ],
        agent_module="agents.strategy_agent_v3.orchestrator"
    )
```

## Database Schema

### Firestore Collections

#### Strategy Documents (Account-Specific)
```
strategy_docs_{account_id}/
├── business_strategy
│   ├── content: {JSON from agent}
│   ├── doc_type: "business_strategy"
│   ├── account_id: "{account_id}"
│   ├── created_at: timestamp
│   ├── updated_at: timestamp
│   ├── version: number
│   └── created_by_agent: "business_strategy_agent"
├── competitive_strategy
├── customer_strategy
├── marketing_strategy
└── brand_guidelines
```

#### Strategy Templates (Global)
```
strategy_doc_guides/
├── {doc_type}_best_practices
│   ├── content: {JSON schema from notebook}
│   ├── doc_type: "{doc_type}"
│   └── template_type: "best_practices"
└── {doc_type}_reviewer_guidelines
    ├── content: {guidelines text from notebook}
    ├── doc_type: "{doc_type}"
    └── template_type: "reviewer_guidelines"
```

#### Processing State (Account-Specific)
```
strategy_processing_state_{account_id}/
└── current_state
    ├── context: {Serialized StrategyContext}
    ├── current_stage: "marketing_strategy"
    ├── stages_completed: ["business_strategy", "competitive_strategy", "customer_strategy"]
    ├── stages_remaining: ["marketing_strategy", "brand_guidelines"]
    ├── started_at: timestamp
    └── last_updated: timestamp
```

## Success Criteria

### V3-Specific Success Criteria
- ✅ All 5 agents execute in sequence without errors
- ✅ Context successfully passes between agents
- ✅ Each agent can access outputs from previous agents
- ✅ Progress tracking shows current agent being processed
- ✅ Partial updates work when starting from middle of sequence
- ✅ Each agent's refinement loop works independently

### From V2 (User Stories)
- ✅ Account creation triggers full sequence
- ✅ Homepage shows non-interactive state during processing
- ✅ Document uploads trigger appropriate agent updates
- ✅ User feedback triggers strategy corrections
- ✅ Email notification sent on completion
- ✅ Product tour launches on first interactive view

## Migration Path from V2 to V3

**Note**: V2 implementation is fully documented in `STRATEGY_AGENT_V2_IMPLEMENTATION.md`. The V3 migration assumes V2 is already implemented or being implemented in parallel.

### Step 1: Parallel Development
- Develop V3 alongside existing V2 implementation (see `STRATEGY_AGENT_V2_IMPLEMENTATION.md`)
- V3 code in new directory structure (`strategy_agent_v3/`)
- No changes to existing V2 code initially

### Step 2: Testing Phase
- Run V3 in test environment
- Compare outputs with V2 for validation
- Ensure quality and completeness

### Step 3: Gradual Rollout
- Feature flag to switch between V2 and V3
- Start with small percentage of new accounts
- Monitor performance and quality

### Step 4: Full Migration
- Switch all new accounts to V3
- Migrate existing V2 documents to V3 format
- Deprecate V2 code

## Risk Mitigation

### Performance Risks
- **Risk**: 5 sequential agents take too long
- **Mitigation**: Parallel execution where possible, caching, timeout management

### Quality Risks
- **Risk**: Context degradation through sequence
- **Mitigation**: Validation at each step, rollback capability

### Integration Risks
- **Risk**: ADK Context/State management complexity
- **Mitigation**: Thorough testing, fallback to simpler approach if needed

## Monitoring & Observability

### Metrics to Track
- Time per agent execution
- Success rate per agent
- Total sequence completion time
- Error rates and types
- Context size growth
- Token usage per agent

### Logging Strategy
```python
logger.info(f"Starting {agent_name} for account {account_id}")
logger.info(f"Context size: {len(json.dumps(context.dict()))}")
logger.info(f"Previous outputs available: {list(context.get_previous_outputs(agent_name).keys())}")
logger.info(f"Agent completed in {elapsed_time}s")
```

## Appendix: Agent Instructions

### Business Strategy Agent Instruction
(Full instruction from Excel sheet row - already captured above)

### Competitive Strategy Agent Instruction  
(Full instruction from Excel sheet row - already captured above)

### Customer Strategy Agent Instruction
(Full instruction from Excel sheet row - already captured above)

### Marketing Strategy Agent Instruction
(Full instruction from Excel sheet row - already captured above)

### Brand Guidelines Agent Instruction
(Full instruction from Excel sheet row - already captured above)

## Next Steps

1. **Immediate**: Extract templates from notebook (Phase 0)
2. **Week 1**: Implement core agents and context management
3. **Week 2**: Integrate with user stories and test
4. **Week 3**: Deploy and monitor

This V3 implementation provides a robust, scalable, and maintainable architecture for progressive strategy document generation with clear separation of concerns and proper context management.