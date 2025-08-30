# Strategy Agent Interaction Flow

## Overview
This diagram illustrates how the KEN-E Strategy Agent System creates comprehensive business strategy documents through a sequential pipeline of 5 specialized agents, each with internal refinement loops. The system uses an orchestrator pattern where `create_strategy_docs.py` routes requests to `orchestrator.py` which manages the sequential execution.

## Architecture Diagram

```mermaid
graph TB
    %% Style definitions
    classDef userNode fill:#e1f5fe,stroke:#01579b,stroke-width:3px
    classDef orchestratorNode fill:#fff3e0,stroke:#e65100,stroke-width:3px
    classDef strategyNode fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef loopNode fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    classDef toolNode fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef dataNode fill:#f5f5f5,stroke:#424242,stroke-width:2px
    classDef contextNode fill:#fff8e1,stroke:#f57c00,stroke-width:3px
    classDef routerNode fill:#e3f2fd,stroke:#0277bd,stroke-width:3px

    %% User Input
    User[User Request<br/>Company Info]:::userNode
    
    %% Main Router/Supervisor
    Supervisor[Strategy Supervisor<br/>create_strategy_docs.py<br/>Routes to orchestrator]:::routerNode
    
    %% Orchestrator
    Orchestrator[Strategy Orchestrator<br/>orchestrator.py<br/>execute_strategy_generation()]:::orchestratorNode
    
    %% Strategy Context
    Context[StrategyContext<br/>• company_name<br/>• websites<br/>• industry<br/>• customer_regions<br/>• annual_ad_budget]:::contextNode
    
    %% Firestore Collections
    Firestore[(Firestore<br/>• strategy_doc_guides<br/>• strategy_docs_accountid)]:::dataNode
    
    %% Tool Agents
    GoogleSearch[Google Search Agent<br/>google_search<br/>gemini-2.5-flash]:::toolNode
    
    %% State Management
    State[Conversation State<br/>• business_strategy_doc<br/>• competitive_strategy_doc<br/>• customer_strategy_doc<br/>• marketing_strategy_doc<br/>• brand_guidelines_doc]:::contextNode
    
    %% Sequential flow of strategy agents
    subgraph "1. Business Strategy Agent"
        BS_Seq[SequentialAgent]:::strategyNode
        BS_Loop[LoopAgent<br/>Max 3 iterations]:::loopNode
        BS_Strategist[Business Strategist<br/>gemini-2.5-pro<br/>Creates initial doc]:::strategyNode
        BS_Reviewer[Business Reviewer<br/>gemini-2.5-flash<br/>Reviews quality]:::strategyNode
        BS_Editor[Business Editor<br/>gemini-2.5-flash<br/>Refines doc]:::strategyNode
    end
    
    subgraph "2. Competitive Strategy Agent"
        CS_Seq[SequentialAgent]:::strategyNode
        CS_Loop[LoopAgent<br/>Max 3 iterations]:::loopNode
        CS_Strategist[Competitive Strategist<br/>gemini-2.5-pro<br/>Reviews business_strategy_doc<br/>Analyzes competition]:::strategyNode
        CS_Reviewer[Competitive Reviewer<br/>gemini-2.5-flash<br/>Reviews quality]:::strategyNode
        CS_Editor[Competitive Editor<br/>gemini-2.5-flash<br/>Refines doc]:::strategyNode
    end
    
    subgraph "3. Customer Strategy Agent"
        CU_Seq[SequentialAgent]:::strategyNode
        CU_Loop[LoopAgent<br/>Max 3 iterations]:::loopNode
        CU_Strategist[Customer Strategist<br/>gemini-2.5-pro<br/>Reviews prior 2 docs<br/>Creates personas]:::strategyNode
        CU_Reviewer[Customer Reviewer<br/>gemini-2.5-flash<br/>Reviews quality]:::strategyNode
        CU_Editor[Customer Editor<br/>gemini-2.5-flash<br/>Refines doc]:::strategyNode
    end
    
    subgraph "4. Marketing Strategy Agent"
        MS_Seq[SequentialAgent]:::strategyNode
        MS_Loop[LoopAgent<br/>Max 3 iterations]:::loopNode
        MS_Strategist[Marketing Strategist<br/>gemini-2.5-pro<br/>Reviews prior 3 docs<br/>Plans campaigns]:::strategyNode
        MS_Reviewer[Marketing Reviewer<br/>gemini-2.5-flash<br/>Reviews quality]:::strategyNode
        MS_Editor[Marketing Editor<br/>gemini-2.5-flash<br/>Refines doc]:::strategyNode
    end
    
    subgraph "5. Brand Guidelines Agent"
        BG_Seq[SequentialAgent]:::strategyNode
        BG_Loop[LoopAgent<br/>Max 3 iterations]:::loopNode
        BG_Strategist[Brand Strategist<br/>gemini-2.5-pro<br/>Defines guidelines]:::strategyNode
        BG_Reviewer[Brand Reviewer<br/>gemini-2.5-flash<br/>Reviews quality]:::strategyNode
        BG_Editor[Brand Editor<br/>gemini-2.5-flash<br/>Refines doc]:::strategyNode
    end
    
    %% Main Flow
    User --> Supervisor
    Supervisor --> Orchestrator
    Orchestrator --> Context
    Context --> BS_Seq
    
    %% Business Strategy Internal Flow
    BS_Seq --> BS_Loop
    BS_Loop --> BS_Strategist
    BS_Strategist --> BS_Reviewer
    BS_Reviewer --> BS_Editor
    BS_Editor -.->|Not Approved| BS_Strategist
    BS_Editor -->|Approved/<br/>exit_loop| BS_Seq
    BS_Seq -->|Save to State| State
    
    %% Sequential Dependencies with State Access
    BS_Seq ==>|business_strategy_doc<br/>saved to state| CS_Seq
    State -.->|Access prior doc| CS_Strategist
    
    %% Competitive Strategy Internal Flow
    CS_Seq --> CS_Loop
    CS_Loop --> CS_Strategist
    CS_Strategist --> CS_Reviewer
    CS_Reviewer --> CS_Editor
    CS_Editor -.->|Not Approved| CS_Strategist
    CS_Editor -->|Approved| CS_Seq
    CS_Seq -->|Save to State| State
    
    CS_Seq ==>|competitive_strategy_doc<br/>saved to state| CU_Seq
    State -.->|Access prior 2 docs| CU_Strategist
    
    %% Customer Strategy Internal Flow
    CU_Seq --> CU_Loop
    CU_Loop --> CU_Strategist
    CU_Strategist --> CU_Reviewer
    CU_Reviewer --> CU_Editor
    CU_Editor -.->|Not Approved| CU_Strategist
    CU_Editor -->|Approved| CU_Seq
    CU_Seq -->|Save to State| State
    
    CU_Seq ==>|customer_strategy_doc<br/>saved to state| MS_Seq
    State -.->|Access prior 3 docs| MS_Strategist
    
    %% Marketing Strategy Internal Flow
    MS_Seq --> MS_Loop
    MS_Loop --> MS_Strategist
    MS_Strategist --> MS_Reviewer
    MS_Reviewer --> MS_Editor
    MS_Editor -.->|Not Approved| MS_Strategist
    MS_Editor -->|Approved| MS_Seq
    MS_Seq -->|Save to State| State
    
    MS_Seq ==>|marketing_strategy_doc<br/>saved to state| BG_Seq
    State -.->|Access prior 4 docs| BG_Strategist
    
    %% Brand Guidelines Internal Flow
    BG_Seq --> BG_Loop
    BG_Loop --> BG_Strategist
    BG_Strategist --> BG_Reviewer
    BG_Reviewer --> BG_Editor
    BG_Editor -.->|Not Approved| BG_Strategist
    BG_Editor -->|Approved| BG_Seq
    BG_Seq -->|Save to State| State
    
    %% Tool Access (all strategists and editors can use search)
    BS_Strategist -.-> GoogleSearch
    BS_Editor -.-> GoogleSearch
    CS_Strategist -.-> GoogleSearch
    CS_Editor -.-> GoogleSearch
    CU_Strategist -.-> GoogleSearch
    MS_Strategist -.-> GoogleSearch
    BG_Strategist -.-> GoogleSearch
    
    %% Firestore Access
    Firestore -->|best_practices<br/>reviewer_guidelines| BS_Strategist
    Firestore -->|best_practices<br/>reviewer_guidelines| CS_Strategist
    Firestore -->|best_practices<br/>reviewer_guidelines| CU_Strategist
    Firestore -->|best_practices<br/>reviewer_guidelines| MS_Strategist
    Firestore -->|best_practices<br/>reviewer_guidelines| BG_Strategist
    
    %% Save Results
    Orchestrator ==>|process_and_save_documents()| Firestore
    
    %% Final Output
    BG_Seq ==> FinalDocs[Complete Strategy<br/>Documents]:::dataNode
    FinalDocs --> User
```

## Key Components

### 1. **Two-Layer Architecture**
- **Supervisor Layer** (`create_strategy_docs.py`): Routes strategy requests to the orchestrator
- **Orchestrator Layer** (`orchestrator.py`): Manages sequential agent execution using Runner class

### 2. **Sequential Pipeline with Cascading Context**
The system processes strategy documents in a strict order with each agent building on previous work:

| Order | Agent | Accesses Previous Docs | Key Focus |
|-------|-------|------------------------|-----------|
| 1 | **Business Strategy** | None | Company overview, market analysis, SWOT |
| 2 | **Competitive Strategy** | business_strategy_doc | Competition analysis, positioning |
| 3 | **Customer Strategy** | business + competitive docs | Personas, journey maps, insights |
| 4 | **Marketing Strategy** | business + competitive + customer docs | Campaigns, channels, metrics |
| 5 | **Brand Guidelines** | All previous docs (optional) | Identity, voice, visual standards |

### 3. **Internal Refinement Pattern**
Each strategy agent contains:
- **SequentialAgent**: Orchestrates the refinement process
- **LoopAgent**: Manages iterations (max 3)
- **Strategist**: Creates initial document using templates (gemini-2.5-pro)
- **Reviewer**: Evaluates against quality guidelines (gemini-2.5-flash)
- **Editor**: Refines based on review feedback (gemini-2.5-flash)

### 4. **Model Optimization**
- **Strategists** (5 agents): Use `gemini-2.5-pro` for high-quality document generation
- **Supporting agents** (reviewers, editors, search): Use `gemini-2.5-flash` for cost/speed optimization

### 5. **State Management**
Documents are saved to conversation state with unique output keys:
- `business_strategy_doc`
- `competitive_strategy_doc`
- `customer_strategy_doc`
- `marketing_strategy_doc`
- `brand_guidelines_doc`

### 6. **Enhanced Instructions**
Each agent's instructions now include:
- Mandatory research requirements with citations
- Specific search query examples
- Instructions to review prior strategy documents
- Process steps for document creation and validation

### 7. **Tool Access**
- **Google Search Agent**: External web research (all strategists/editors)
- **exit_loop**: Signals approval to exit refinement loop
- Note: Internal Search Agent removed for optimization

### 8. **Data Storage**
- **Input**: Templates from `strategy_doc_guides` collection
- **Output**: Final documents to `strategy_docs_{account_id}` collection
- **Immediate Saving**: Documents saved to Firestore as each agent completes

## File Locations

| Component | File | Purpose |
|-----------|------|---------|
| Main Supervisor | `create_strategy_docs.py` | Routes requests to orchestrator (renamed from agent_standalone.py) |
| Orchestrator | `orchestrator.py` | Manages sequential execution with Runner class |
| Agent Definitions | `agents.py` | Contains all 5 strategy agent definitions |
| Data Models | `models.py` | StrategyContext and data structures |
| Firestore Integration | `firestore.py` | Document storage and retrieval |
| Deployment Scripts | `deploy_with_execution.py` | Deploys to Vertex AI Agent Engine |

## Execution Flow

1. **Account Creation** triggers strategy generation via API
2. **Supervisor** (`create_strategy_docs.py`) receives request
3. **Orchestrator** (`orchestrator.py`) is invoked via `execute_strategy_generation()`
4. **Runner** class executes the SequentialAgent with all 5 sub-agents
5. **Events** are monitored and documents saved immediately upon completion
6. **Firestore** stores completed documents in `strategy_docs_{account_id}`

## Recent Updates

### Improvements Made:
1. **Renamed** `agent_standalone.py` → `create_strategy_docs.py` for clarity
2. **Integrated** orchestrator.py for proper sequential execution
3. **Fixed** agent execution using Runner class instead of manual invocation
4. **Optimized** model usage (Pro for strategists, Flash for support)
5. **Enhanced** instructions with mandatory citations and research
6. **Added** cascading document review between agents
7. **Implemented** immediate Firestore saving after each agent
8. **Fixed** W&B observability integration

## How to Modify

### To change agent behavior:
1. Edit instruction templates in `agents.py`
2. Modify best practices in Firestore
3. Update reviewer guidelines in Firestore

### To add new strategy types:
1. Create new agent function in `agents.py`
2. Add to sequential pipeline in `orchestrator.py`
3. Update `StrategyContext` in `models.py`
4. Add new output_key to state management

### To change data flow:
1. Update agent instructions to reference new state variables
2. Modify output_key assignments in agent definitions
3. Adjust DOCUMENT_KEY_MAPPING in orchestrator.py

## Deployment
This system deploys to Vertex AI Agent Engine using ADK (Agent Development Kit) and runs as a sequential pipeline that typically takes 3-5 minutes to generate all strategy documents with the optimized model configuration.

Current deployment: `create-strategy-docs-20250830-081338`  
Engine ID: `projects/525657242938/locations/us-central1/reasoningEngines/2451158863987081216`