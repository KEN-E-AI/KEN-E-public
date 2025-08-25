# Strategy Agent V2 Integration Plan

## Overview
The strategy agent has already been fully ported from the notebook and is deployed to Vertex AI Agent Engine. This plan focuses on integrating the existing agent with the KEN-E system to automatically generate and maintain strategic knowledge bases for each account through the three user stories.

## User Stories (Requirements)

### User Story 1:

As a new marketer, I want to provide my company's website URL during account creation and have the system automatically research and build my strategic knowledge base, So that the application can learn about my business and provide personalized recommendations without manual data entry.

#### Acceptance Criteria
- Given a new marketer is creating an account, When they submit the 'create account' form containing a website URL, Then a background process is initiated to create the six strategy documents (Business, Competitive, Customer, Marketing, Measurement, Brand).
- Given the knowledge base creation process has not completed, When the marketer lands on the homepage, Then the page should be in a non-interactive state and display a message indicating the process is running and may take up to one hour.
- Given the knowledge base creation process has successfully completed, When the marketer is on the application homepage, Then the "in-progress" message is removed and the full interactivity of the page is enabled.
- Given the knowledge base creation process has successfully completed, When the process finishes, Then the marketer should receive an email notification confirming their account is ready.
- Given the knowledge base is ready and the homepage is interactive, When the user first views the interactive page, Then a product tour should be initiated.

#### Definition of Done
- Verify that submitting a valid URL during account creation triggers the backend AI agent process.
- Verify that the user is immediately shown a non-interactive homepage with the correct "in-progress" message.
- Verify that after the backend process completes, the homepage message is removed and UI elements become interactive.
- Verify that an email is successfully sent to the user upon completion.
- Verify that the product tour starts automatically after the page becomes interactive for the first time.
- Test the edge case: What happens if an invalid URL (e.g., dead link, non-existent domain) is provided? (Note: This may require a separate story for error handling).

### User Story 2:

As a marketer, I want to upload a document (e.g., a business plan) through the KEN-E chat interface, So that I can provide the AI with specific, pre-existing information to improve the accuracy of its recommendations.

#### Acceptance Criteria
- Given I am interacting with the chat interface, When I use the file upload option, Then I should be able to select a supported file (PDF, .docx, etc) from my local system.
- Given I have successfully uploaded a document, When the system begins processing it, Then the document is sent to the 'iterative_strategy_agent' to update the relevant knowledge base documents.
- Given a document has been uploaded for processing, When the user is in the chat interface, Then they should receive a confirmation message acknowledging the upload and that the information is being reviewed.

#### Definition of Done
- Verify that a file upload button/mechanism is present in the chat interface.
- Verify that a user can successfully upload a file.
- Verify that attempting to upload an unsupported file type results in a clear error message.
- Verify that after a successful upload, the backend 'iterative_strategy_agent' receives the file.
- Verify that the user sees a confirmation message in the chat window post-upload.

### User Story 3:

As a marketer, I want to tell KEN-E when information it has is incorrect, So that I can easily correct the AI's understanding and refine my strategic knowledge base.

#### Acceptance Criteria
- Given I am having a conversation with the chat agent, When I provide direct textual feedback indicating a piece of information is incorrect (e.g., "That's not my competitor"), Then my feedback is sent to the 'iterative_strategy_agent' for processing.
- Given I have submitted corrective feedback, When my feedback is successfully received by the system, Then the chat interface should display a confirmation message, such as "Thank you for the feedback. I will update my records."

#### Definition of Done
- Verify that a specific chat input (e.g., "Information X is wrong") is correctly identified and routed to the 'iterative_strategy_agent'.
- Verify that upon successful routing of the feedback, the user immediately receives a confirmation message in the chat.
- Simulate a failure in the backend agent and verify that the user receives an appropriate error message

## Current Status ✅

### Already Implemented
- **Complete Strategy Agent**: `app/simple_company_chatbot/agents/strategy_agent/`
  - Iterative strategy agent with strategist, reviewer, editor sub-agents
  - Google search and Vertex AI search capabilities
  - Refinement loop with up to 3 iterations
  - Async/sync invocation with observability
- **Multi-Agent Integration**: Strategy agent integrated into supervisor
- **Vertex AI Deployment**: Agent deployed and accessible via Agent Engine
- **Chat Interface**: Basic chat functionality with Agent Engine

## Integration Requirements

### User Story 1: Account Creation Strategy Generation
**Goal**: Auto-generate strategy docs during account creation using existing website URL field

**What's Needed**:
- Trigger strategy generation after successful account creation
- Use existing `websites` field from account data
- Store results in Firestore  
- **NEW**: Add `setup_status` field to Account model ("pending", "processing", "ready")
- **NEW**: Non-interactive homepage state with progress message
- **NEW**: Status polling mechanism to check completion
- **NEW**: Email notification when strategy generation completes
- **NEW**: Product tour trigger on first interactive homepage view

### User Story 2: Document Upload Integration  
**Goal**: Update strategy docs when users upload business documents via chat

**What's Needed**:
- File upload capability in chat interface
- Document parsing (PDF, DOCX, TXT)
- Strategy update triggers with document content

### User Story 3: Feedback-Based Updates
**Goal**: Update strategy docs based on user corrections in chat

**What's Needed**:
- Pattern detection for user corrections
- Strategy update triggers with feedback
- Acknowledgment responses

## Implementation Components

### 1. Account Creation Integration

#### A. Modify Account Creation (`api/src/kene_api/routers/accounts.py`)
```python
# After successful account creation
if account_created_successfully:
    # Set account setup_status to "processing"
    await update_account_setup_status(new_account.account_id, "processing")
    
    # Trigger background strategy generation
    await queue_strategy_generation_task(
        account_id=new_account.account_id,
        company_name=request.account_name,
        websites=request.websites,
        industry=request.industry,
        regions=request.region
    )
```

#### B. Account Model Updates (`api/src/kene_api/models/kene_models.py`)
```python
class Account(BaseModel):
    # ... existing fields ...
    setup_status: Optional[str] = "pending"  # "pending", "processing", "ready"
    setup_started_at: Optional[datetime] = None
    setup_completed_at: Optional[datetime] = None
```

#### C. Background Task Handler (`api/src/kene_api/tasks/strategy_tasks.py`)
```python
async def generate_initial_strategies(
    account_id: str,
    company_name: str, 
    websites: List[str],
    industry: str,
    regions: List[str]
):
    """Generate all 6 strategy documents for new account."""
    strategy_types = [
        "business_strategy", "competitive_strategy", "customer_strategy",
        "marketing_strategy", "measurement_plan", "brand_strategy"
    ]
    
    for doc_type in strategy_types:
        # Call existing strategy agent
        result = await invoke_strategy_agent(
            query=f"Create a comprehensive {doc_type} document...",
            account_id=account_id,
            strategy_params={
                'doc_type': doc_type,
                'new_information': f"""
                COMPANY TO ANALYZE: {company_name}
                Website: {websites[0] if websites else 'N/A'}
                Industry: {industry}
                Customer Regions: {', '.join(regions)}
                """,
                'best_practices': get_best_practices(doc_type),
                'reviewer_guidelines': get_reviewer_guidelines(doc_type)
            }
        )
        
        # Save to Firestore
        await save_strategy_document(account_id, doc_type, result)
    
    # Mark account as ready when all strategies are complete
    await update_account_setup_status(account_id, "ready")
    
    # Send email notification (optional - future enhancement)
    # await send_setup_complete_email(account_id)
```

#### D. Frontend Homepage Integration (`frontend/src/pages/Home.tsx`)
```tsx
export function Home() {
    const { user } = useAuth();
    const [setupStatus, setSetupStatus] = useState<"pending" | "processing" | "ready">("ready");
    const [showProductTour, setShowProductTour] = useState(false);
    
    useEffect(() => {
        // Check setup status for user's accounts
        const checkSetupStatus = async () => {
            const accounts = await getUserAccounts();
            const processingAccounts = accounts.filter(acc => acc.setup_status !== "ready");
            
            if (processingAccounts.length > 0) {
                setSetupStatus("processing");
                // Poll every 30 seconds for status updates
                const pollInterval = setInterval(async () => {
                    const updatedAccounts = await getUserAccounts();
                    const stillProcessing = updatedAccounts.filter(acc => acc.setup_status !== "ready");
                    
                    if (stillProcessing.length === 0) {
                        setSetupStatus("ready");
                        setShowProductTour(true); // Show product tour on first completion
                        clearInterval(pollInterval);
                    }
                }, 30000);
                
                return () => clearInterval(pollInterval);
            }
        };
        
        checkSetupStatus();
    }, []);
    
    if (setupStatus === "processing") {
        return <SetupProgressPage />;
    }
    
    return (
        <>
            <NormalHomePage />
            {showProductTour && <ProductTour />}
        </>
    );
}
```

#### E. Setup Progress Component (`frontend/src/components/setup/SetupProgressPage.tsx`)
```tsx
export function SetupProgressPage() {
    const [elapsedTime, setElapsedTime] = useState(0);
    
    useEffect(() => {
        const interval = setInterval(() => {
            setElapsedTime(prev => prev + 1);
        }, 1000);
        
        return () => clearInterval(interval);
    }, []);
    
    return (
        <div className="min-h-screen flex items-center justify-center bg-background">
            <Card className="w-full max-w-md p-6 text-center">
                <div className="mb-4">
                    <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4 text-primary" />
                    <h2 className="text-2xl font-semibold mb-2">Building Your Strategic Knowledge Base</h2>
                    <p className="text-muted-foreground">
                        We're analyzing your company and creating personalized strategy documents. 
                        This process may take up to one hour.
                    </p>
                </div>
                
                <div className="space-y-2 text-sm text-muted-foreground">
                    <div className="flex justify-between">
                        <span>Elapsed time:</span>
                        <span>{Math.floor(elapsedTime / 60)}:{String(elapsedTime % 60).padStart(2, '0')}</span>
                    </div>
                    <div className="flex justify-between">
                        <span>Expected completion:</span>
                        <span>~{Math.max(0, 60 - Math.floor(elapsedTime / 60))} minutes</span>
                    </div>
                </div>
                
                <Progress value={Math.min(100, (elapsedTime / 3600) * 100)} className="mt-4" />
                
                <p className="text-xs text-muted-foreground mt-4">
                    You can close this page - we'll email you when your account is ready.
                </p>
            </Card>
        </div>
    );
}
```

### 2. Document Upload Integration

#### A. File Upload Endpoint (`api/src/kene_api/routers/chat.py`)
```python
@router.post("/upload")
async def upload_document(
    file: UploadFile,
    account_id: str,
    user: UserContext = Depends(get_current_user)
):
    """Handle document upload for strategy updates."""
    # Validate file type
    if file.content_type not in SUPPORTED_TYPES:
        raise HTTPException(400, "Unsupported file type")
    
    # Extract content
    content = await extract_document_content(file)
    
    # Queue strategy update
    await queue_strategy_update_task(
        account_id=account_id,
        user_id=user.user_id,
        update_type='document',
        new_information=content
    )
    
    return {"message": "Thank you, I'll review this document"}
```

#### B. Document Parser (`api/src/kene_api/utils/document_parser.py`)
```python
async def extract_document_content(file: UploadFile) -> str:
    """Extract text content from uploaded documents."""
    if file.content_type == 'application/pdf':
        return extract_pdf_text(file)
    elif 'word' in file.content_type:
        return extract_docx_text(file)
    else:
        return (await file.read()).decode('utf-8')
```

#### C. Frontend File Upload (`frontend/src/components/home/HomeChatArea.tsx`)
```tsx
// Add file upload button to existing chat interface
<Button
  variant="ghost"
  size="sm"
  onClick={() => fileInputRef.current?.click()}
>
  <Paperclip className="h-4 w-4" />
</Button>
<input
  ref={fileInputRef}
  type="file"
  accept=".pdf,.doc,.docx,.txt"
  onChange={handleFileUpload}
  className="hidden"
/>
```

### 3. Feedback Detection Integration

#### A. Chat Response Processing (`api/src/kene_api/routers/chat.py`)
```python
async def detect_and_handle_feedback(
    message: str,
    account_id: str,
    user_id: str
) -> Optional[str]:
    """Detect user corrections and trigger strategy updates."""
    correction_patterns = [
        r"that's (wrong|incorrect|not right)",
        r"actually (we|our company)",
        r"not my competitor",
        r"we don't (do|have|offer)",
        r"incorrect.*information"
    ]
    
    for pattern in correction_patterns:
        if re.search(pattern, message.lower()):
            # Queue strategy update with feedback
            await queue_strategy_update_task(
                account_id=account_id,
                user_id=user_id,
                update_type='feedback',
                new_information=message
            )
            return "Thank you for the clarification. I'll update my understanding."
    
    return None
```

#### B. Strategy Update Task (`api/src/kene_api/tasks/strategy_tasks.py`)
```python
async def update_strategies_with_feedback(
    account_id: str,
    user_id: str,
    feedback: str
):
    """Update strategy documents based on user feedback."""
    # Determine which strategy types might be affected
    affected_strategies = analyze_feedback_context(feedback)
    
    for doc_type in affected_strategies:
        # Get existing strategy
        existing_doc = await get_strategy_document(account_id, doc_type)
        
        # Call strategy agent for update
        result = await invoke_strategy_agent(
            query=f"Update the existing {doc_type} document based on user feedback",
            account_id=account_id,
            strategy_params={
                'doc_type': doc_type,
                'existing_document': existing_doc,
                'new_information': feedback,
                'best_practices': get_best_practices(doc_type),
                'reviewer_guidelines': get_reviewer_guidelines(doc_type)
            }
        )
        
        # Save updated document
        await save_strategy_document(account_id, doc_type, result)
```

### 4. Firestore Integration

#### A. Strategy Storage (`api/src/kene_api/services/strategy_service.py`)
```python
async def save_strategy_document(
    account_id: str,
    doc_type: str,
    content: str
) -> str:
    """Save strategy document to Firestore."""
    try:
        # Parse JSON content from strategy agent
        strategy_data = json.loads(content)
        
        # Add metadata
        doc_data = {
            'content': strategy_data,
            'doc_type': doc_type,
            'account_id': account_id,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'version': 1
        }
        
        # Save to account-specific collection
        doc_ref = db.document(f"strategy_docs_{account_id}/{doc_type}")
        doc_ref.set(doc_data)
        
        # Log to audit trail
        await log_strategy_action(
            account_id=account_id,
            doc_type=doc_type,
            action='created',
            user=system_user,
            doc_id=doc_type
        )
        
        return doc_ref.id
    
    except Exception as e:
        logger.error(f"Failed to save strategy document: {e}")
        raise
```

#### B. Context Injection for Chat (`api/src/kene_api/routers/chat.py`)
```python
async def inject_strategy_context(
    account_id: str,
    conversation_topic: str
) -> str:
    """Load relevant strategy docs as context for chat."""
    relevant_docs = await get_relevant_strategy_docs(account_id, conversation_topic)
    
    if not relevant_docs:
        return ""
    
    context = "INTERNAL CONTEXT (do not expose to user):\n"
    for doc_type, content in relevant_docs.items():
        context += f"\n{doc_type.upper()}:\n{json.dumps(content, indent=2)}\n"
    
    return context
```

### 5. Database Schema

#### Firestore Collections

**Strategy Documents (Account-Specific)**
```
strategy_docs_{account_id}/           # Account-specific strategy collection
├── business_strategy                 # Document structure:
│   ├── content: {JSON strategy document from agent}
│   ├── doc_type: "business_strategy"
│   ├── account_id: "{account_id}"
│   ├── created_at: timestamp
│   ├── updated_at: timestamp
│   └── version: number
├── competitive_strategy              # Same structure as above
├── customer_strategy                 # Same structure as above
├── marketing_strategy                # Same structure as above
├── measurement_plan                  # Same structure as above
└── brand_strategy                    # Same structure as above
```

**Templates Collection (Global)**
```
strategy_templates/                   # Templates extracted from notebook
├── business_strategy_best_practices          # Document structure:
│   ├── content: "{VERBATIM JSON schema from notebook}"
│   ├── doc_type: "business_strategy"
│   ├── template_type: "best_practices"
│   └── source: "notebook_migration"
├── business_strategy_reviewer_guidelines    # Document structure:
│   ├── content: "{VERBATIM guidelines text from notebook}"
│   ├── doc_type: "business_strategy"
│   ├── template_type: "reviewer_guidelines"
│   └── source: "notebook_migration"
├── competitive_strategy_best_practices      # Same structure pattern
├── competitive_strategy_reviewer_guidelines # Same structure pattern
├── customer_strategy_best_practices         # Same structure pattern (if exists)
├── customer_strategy_reviewer_guidelines    # Same structure pattern (if exists)
├── marketing_strategy_best_practices        # Same structure pattern (if exists)
├── marketing_strategy_reviewer_guidelines   # Same structure pattern (if exists)
├── measurement_plan_best_practices          # Same structure pattern (if exists)
├── measurement_plan_reviewer_guidelines     # Same structure pattern (if exists)
├── brand_strategy_best_practices            # Same structure pattern (if exists)
└── brand_strategy_reviewer_guidelines       # Same structure pattern (if exists)
```

**Audit Trail (Account-Specific)**
```
strategy_audit_{account_id}/         # Using existing audit service
└── {audit_entries}                  # Standard audit format
```

## Implementation Timeline

### Phase 0: Template Migration (Day 1) - CRITICAL FIRST STEP
**MUST BE COMPLETED BEFORE ANY OTHER WORK**

The strategy agent requires specific `best_practices` and `reviewer_guidelines` templates that currently only exist in the Jupyter notebook. These MUST be extracted and stored before the agent can work properly.

#### Extract from Notebook (`KEN_E____ADK____Iterative_Strategy_Agent.ipynb`)
**Location in notebook**: Look for cells containing mock Firestore data with variables:
- `best_practices` - JSON schema defining document structure (for business_strategy, competitive_strategy, etc.)
- `reviewer_guidelines` - Validation rules for the reviewer agent

**What to extract**:
1. **Business Strategy Templates** (from business strategy test section):
   - `best_practices` variable - large JSON schema 
   - `reviewer_guidelines` variable - validation instructions
   
2. **Competitive Strategy Templates** (from competitive strategy test section):
   - `best_practices` variable - different JSON schema for competitive docs
   - `reviewer_guidelines` variable - validation rules for competitive docs
   
3. **Other Strategy Types**: The notebook may contain templates for all 6 types:
   - business_strategy, competitive_strategy, customer_strategy
   - marketing_strategy, measurement_plan, brand_strategy

#### Storage in Firestore
Store each template as a separate Firestore document:
```
strategy_templates/
├── business_strategy_best_practices (JSON schema from notebook)
├── business_strategy_reviewer_guidelines (validation rules from notebook)  
├── competitive_strategy_best_practices (JSON schema from notebook)
├── competitive_strategy_reviewer_guidelines (validation rules from notebook)
├── customer_strategy_best_practices (if exists in notebook)
├── customer_strategy_reviewer_guidelines (if exists in notebook)
├── marketing_strategy_best_practices (if exists in notebook)  
├── marketing_strategy_reviewer_guidelines (if exists in notebook)
├── measurement_plan_best_practices (if exists in notebook)
├── measurement_plan_reviewer_guidelines (if exists in notebook)
├── brand_strategy_best_practices (if exists in notebook)
└── brand_strategy_reviewer_guidelines (if exists in notebook)
```

#### Create Template Functions
```python
async def get_best_practices(doc_type: str) -> str:
    """Retrieve best practices JSON schema from Firestore."""
    doc_ref = firestore_db.collection("strategy_templates").document(f"{doc_type}_best_practices")
    doc = await doc_ref.get()
    return doc.get("content") if doc.exists else None

async def get_reviewer_guidelines(doc_type: str) -> str:
    """Retrieve reviewer guidelines from Firestore.""" 
    doc_ref = firestore_db.collection("strategy_templates").document(f"{doc_type}_reviewer_guidelines")
    doc = await doc_ref.get()
    return doc.get("content") if doc.exists else None
```

**CRITICAL**: Do NOT create new templates. Copy the exact text VERBATIM from the notebook variables.

### Phase 1: Firestore Integration (Days 2-3)
- Create strategy storage service
- Implement context injection for chat
- Test template retrieval system

### Phase 2: Account Creation Hook (Day 3)
- Add background task trigger to account creation
- Implement strategy generation task handler
- Test with new account creation

### Phase 3: Document Upload (Days 4-5)
- Add file upload endpoint and parsing
- Create frontend upload component
- Implement update task handling

### Phase 4: Feedback Detection (Days 6-7)
- Add pattern matching for corrections
- Implement feedback update workflow
- Test correction scenarios

### Phase 5: Testing & Integration (Days 8-9)
- End-to-end testing of all workflows
- Performance optimization
- Error handling improvements

## Key Files to Create/Modify

### New Files
- `api/src/kene_api/services/strategy_service.py`
- `api/src/kene_api/tasks/strategy_tasks.py`
- `api/src/kene_api/utils/document_parser.py`
- `frontend/src/components/setup/SetupProgressPage.tsx`
- `frontend/src/components/tour/ProductTour.tsx` (if not exists)
- `tests/integration/test_strategy_integration.py`

### Modified Files
- `api/src/kene_api/models/kene_models.py` (add setup_status fields to Account)
- `api/src/kene_api/routers/accounts.py` (add task trigger, setup status)
- `api/src/kene_api/routers/chat.py` (add upload endpoint, feedback detection, context injection)
- `frontend/src/pages/Home.tsx` (add setup status checking and product tour)
- `frontend/src/components/home/HomeChatArea.tsx` (add file upload button)
- `frontend/src/queries/accounts.ts` (add setup status queries)

## Success Criteria (Definition of Done)

### User Story 1 ✅
- **Verify that submitting a valid URL during account creation triggers the backend AI agent process**
- **Verify that the user is immediately shown a non-interactive homepage with the correct "in-progress" message**
- **Verify that after the backend process completes, the homepage message is removed and UI elements become interactive**
- **Verify that an email is successfully sent to the user upon completion** (Future Enhancement)
- **Verify that the product tour starts automatically after the page becomes interactive for the first time**
- **Test the edge case: What happens if an invalid URL (e.g., dead link, non-existent domain) is provided?** (Future Enhancement)

### User Story 2 ✅  
- **Verify that a file upload button/mechanism is present in the chat interface**
- **Verify that a user can successfully upload a file**
- **Verify that attempting to upload an unsupported file type results in a clear error message**
- **Verify that after a successful upload, the backend 'iterative_strategy_agent' receives the file**
- **Verify that the user sees a confirmation message in the chat window post-upload**

### User Story 3 ✅
- **Verify that a specific chat input (e.g., "Information X is wrong") is correctly identified and routed to the 'iterative_strategy_agent'**
- **Verify that upon successful routing of the feedback, the user immediately receives a confirmation message in the chat**
- **Simulate a failure in the backend agent and verify that the user receives an appropriate error message**

## Important Notes

1. **Strategy Agent is Ready**: The existing strategy agent at `app/simple_company_chatbot/agents/strategy_agent/` is production-ready and handles all the complex strategy generation logic.

2. **Focus on Integration**: This plan focuses purely on connecting the existing agent to the three user story workflows.

3. **Zero User Visibility**: Strategy documents remain completely internal - users never see them or know they exist.

4. **Existing Infrastructure**: Leverages existing audit service, Firestore setup, and Agent Engine deployment.

5. **Templates Must Be Migrated**: Best practices and reviewer guidelines exist in the Jupyter notebook and must be copied VERBATIM to Firestore before any strategy generation can work properly.

6. **Use Cloud Tasks**: For background processing, use Google Cloud Tasks (GCP-native) rather than simple async approaches for robust, scalable task management.

7. **Multiple Account Handling**: Users may have access to multiple accounts. When creating strategy docs during account creation, check if strategies already exist to avoid duplicate generation.