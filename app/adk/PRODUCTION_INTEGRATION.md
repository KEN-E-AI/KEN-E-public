# Production Integration Guide: Multi-Agent Chatbot with KEN-E

This guide explains how to integrate the multi-agent chatbot (Company News + Google Analytics) with the KEN-E platform in production.

## Architecture Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   KEN-E Web     │────▶│  KEN-E API       │────▶│  Multi-Agent        │
│   Frontend      │     │  (FastAPI)       │     │  Supervisor         │
└─────────────────┘     └──────────────────┘     └──────┬───────────────┘
                                │                         │
                                │                    ┌────▼────┐  ┌────▼────┐
                        ┌───────▼────────┐          │  News   │  │   GA    │
                        │   Firebase     │          │  Agent  │  │  Agent  │
                        │   Auth         │          └─────────┘  └─────────┘
                        └────────────────┘

```

## Key Components

### 1. Multi-Agent Supervisor (`multi_agent_supervisor_production.py`)
- Routes queries between news and GA agents
- Handles session-based authentication
- Integrates with KEN-E's user context

### 2. Google Analytics Agent (`google_analytics_agent_production.py`)
- Accepts credentials through session context via `ga_session_manager`
- No credential parsing from query strings
- Tools receive session context to access credentials securely
- Clean queries without embedded authentication data

### 3. KEN-E Integration (`kene_integration.py`)
- Adapter between KEN-E and multi-agent system
- Manages credential extraction and session lifecycle
- Provides drop-in replacement for existing chat handler

## Integration Steps

### Step 1: Deploy the Multi-Agent System

1. **Deploy agents to Vertex AI:**
```bash
# Deploy supervisor
cd simple_company_chatbot
uv run adk deploy agents/multi_agent_supervisor_production.py \
  --project-id=$GOOGLE_CLOUD_PROJECT_ID \
  --region=us-central1

# Note the deployed agent ID
```

2. **Update environment variables:**
```bash
# In KEN-E's .env or Cloud Run environment
MULTI_AGENT_SUPERVISOR_ID="<deployed-agent-id>"
GA_MCP_SERVER_URL="https://google-analytics-mcp-395770269870.us-central1.run.app"
```

### Step 2: Modify KEN-E Chat Router

Update `/Users/dvalia/Code/python/KEN-E/api/src/kene_api/routers/chat.py`:

```python
# Add imports
from simple_company_chatbot.kene_integration import (
    KeneChatbotAdapter, 
    create_kene_chat_handler
)

# In AgentEngineClient.__init__:
self.chatbot_adapter = KeneChatbotAdapter()
self.enhanced_chat_handler = create_kene_chat_handler(self.chatbot_adapter)

# Replace the chat_completion method:
async def chat_completion(self, messages, user_context, session_id=None, conversation_name=None):
    # Use multi-agent system instead of single agent
    return await self.enhanced_chat_handler(
        messages=messages,
        user_context=user_context,
        session_id=session_id,
        conversation_name=conversation_name
    )
```

### Step 3: Implement Service Account Based Authentication (Per Account)

This approach creates a dedicated service account for each account in KEN-E, providing granular control and better security. All account data is stored in Neo4j following KEN-E's architecture.

#### 1. **Update Account Model in Neo4j**

First, update the Account model to include service account information:

```python
# In kene_models.py - Add to Account model
class Account(BaseModel):
    """Account entity model."""
    
    # Existing fields...
    account_id: str = Field(..., description="Unique identifier for the account")
    account_name: str = Field(..., description="Name of the account")
    organization_id: str = Field(..., description="ID of the organization this account belongs to")
    # ... other existing fields ...
    
    # New fields for service account integration
    service_account_email: str | None = Field(None, description="Service account email for integrations")
    integrations: dict[str, dict] | None = Field(
        default_factory=lambda: {
            "google_analytics": {"enabled": False, "properties": []},
            "bing_ads": {"enabled": False, "accounts": []},
            "meta_ads": {"enabled": False, "ad_accounts": []}
        },
        description="Integration status for various platforms"
    )
```

#### 2. **Automatic Service Account Creation**

Enhance the account creation endpoint to automatically provision a service account:

```python
# In accounts.py router - modify create_account function
async def create_account(
    request: AccountRequest,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
) -> Account:
    """Create a new account with automatic service account provisioning"""
    
    # ... existing validation logic ...
    
    # Generate unique account_id
    account_id = generate_unique_account_id()
    
    # Create service account
    service_account_email = await create_service_account_for_account(account_id)
    
    # Create account node with service account info
    create_query = """
    MATCH (org:Organization {organization_id: $organization_id})
    CREATE (acc:Account {
        account_id: $account_id,
        account_name: $account_name,
        organization_id: $organization_id,
        industry: $industry,
        status: $status,
        websites: $websites,
        timezone: $timezone,
        data_region: $data_region,
        region: $region,
        service_account_email: $service_account_email,
        integrations: $integrations
    })
    CREATE (acc)-[:BELONGS_TO]->(org)
    RETURN acc
    """
    
    params = {
        "account_id": account_id,
        "service_account_email": service_account_email,
        "integrations": {
            "google_analytics": {"enabled": False, "properties": []},
            "bing_ads": {"enabled": False, "accounts": []},
            "meta_ads": {"enabled": False, "ad_accounts": []}
        },
        # ... other params ...
    }
    
    result = await db.execute_write_query(create_query, params)
    # ... rest of implementation


async def create_service_account_for_account(account_id: str) -> str:
    """Create a dedicated service account for an account"""
    from google.cloud import iam_admin_v1
    
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
    iam_client = iam_admin_v1.IAMClient()
    
    # Create service account (truncate ID to meet 30 char limit)
    service_account_id = f"kene-{account_id.replace('acc_', '')}"[:30]
    
    service_account = iam_client.create_service_account(
        request={
            "name": f"projects/{project_id}/serviceAccounts/{service_account_id}",
            "account_id": service_account_id,
            "service_account": {
                "display_name": f"KEN-E Account {account_id}",
                "description": f"Service account for KEN-E account {account_id}"
            }
        }
    )
    
    # Generate and store key in Secret Manager
    key = iam_client.create_service_account_key(
        request={
            "name": service_account.name,
            "private_key_type": "TYPE_GOOGLE_CREDENTIALS_FILE"
        }
    )
    
    # Store in Secret Manager
    from .secret_manager import create_secret
    secret_id = f"account-{account_id}-credentials"
    create_secret(secret_id, key.private_key_data)
    
    return service_account.email
```

#### 3. **Integration Setup Endpoints**

Add endpoints to help users grant access to their resources:

```python
# New endpoint in accounts.py
@router.post("/{account_id}/integrations/google-analytics/setup")
async def setup_ga_integration(
    account_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
):
    """Get instructions for setting up Google Analytics integration"""
    
    # Verify user has access to account
    if not user.has_account_access(account_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get account with service account email from Neo4j
    query = """
    MATCH (acc:Account {account_id: $account_id})
    RETURN acc.service_account_email as service_account_email
    """
    
    result = await db.execute_query(query, {"account_id": account_id})
    if not result:
        raise HTTPException(status_code=404, detail="Account not found")
    
    service_account_email = result[0]["service_account_email"]
    
    return {
        "service_account_email": service_account_email,
        "instructions": {
            "google_analytics": [
                {
                    "step": 1,
                    "action": "Go to Google Analytics Admin",
                    "url": "https://analytics.google.com"
                },
                {
                    "step": 2,
                    "action": "Navigate to Account Access Management",
                    "details": "Select your account → Account Access Management"
                },
                {
                    "step": 3,
                    "action": "Click the '+' button to add users"
                },
                {
                    "step": 4,
                    "action": "Enter the service account email",
                    "value": service_account_email,
                    "copy_enabled": True
                },
                {
                    "step": 5,
                    "action": "Set role to 'Viewer'",
                    "details": "This gives read-only access to your analytics data"
                }
            ]
        }
    }
```

#### 4. **Verify Integration Status**

Add endpoint to verify and update integration status:

```python
@router.post("/{account_id}/integrations/google-analytics/verify")
async def verify_ga_integration(
    account_id: str,
    user: UserContext = Depends(get_current_user_context),
    db: Neo4jService = Depends(get_neo4j_service),
):
    """Verify Google Analytics integration and update status"""
    
    # Get service account credentials
    from .secret_manager import get_secret
    secret_id = f"account-{account_id}-credentials"
    credentials_json = get_secret(secret_id)
    
    try:
        # Test access by listing GA properties
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        
        credentials = service_account.Credentials.from_service_account_info(
            json.loads(credentials_json),
            scopes=['https://www.googleapis.com/auth/analytics.readonly']
        )
        
        ga_admin = build('analyticsadmin', 'v1beta', credentials=credentials)
        properties_response = ga_admin.properties().list().execute()
        properties = properties_response.get('properties', [])
        
        # Update integration status in Neo4j using JSON
        update_query = """
        MATCH (acc:Account {account_id: $account_id})
        SET acc.integrations = apoc.convert.fromJsonMap($integrations_json)
        RETURN acc
        """
        
        integrations = {
            "google_analytics": {
                "enabled": True,
                "properties": [
                    {"id": p["name"], "display_name": p.get("displayName", "")} 
                    for p in properties
                ],
                "last_verified": datetime.now().isoformat()
            }
        }
        
        await db.execute_write_query(update_query, {
            "account_id": account_id,
            "integrations_json": json.dumps(integrations)
        })
        
        return {
            "status": "success",
            "message": f"Successfully verified access to {len(properties)} GA properties",
            "properties_count": len(properties)
        }
        
    except Exception as e:
        logger.error(f"GA verification failed for account {account_id}: {e}")
        raise HTTPException(
            status_code=400,
            detail="Unable to verify Google Analytics access. Please ensure you've granted the service account Viewer permissions."
        )
```

#### 5. **Retrieve Credentials in KeneChatbotAdapter**

Update the adapter to retrieve credentials from Neo4j:

```python
# In kene_integration.py
async def extract_google_credentials(self, user_context: Dict[str, Any]) -> Optional[str]:
    """
    Extract service account credentials for the current account.
    Uses Neo4j to get account info and Secret Manager for credentials.
    """
    # Get current account ID from user context
    account_id = user_context.get("current_account_id")
    if not account_id:
        accessible_accounts = user_context.get("accessible_accounts", [])
        if accessible_accounts:
            account_id = accessible_accounts[0]
    
    if not account_id:
        logger.warning("No account found for user")
        return None
    
    try:
        # Get account info from Neo4j
        from ..database import neo4j_service
        
        query = """
        MATCH (acc:Account {account_id: $account_id})
        RETURN acc.integrations as integrations
        """
        
        result = await neo4j_service.execute_query(query, {"account_id": account_id})
        if not result:
            return None
            
        integrations = result[0].get("integrations", {})
        ga_integration = integrations.get("google_analytics", {})
        
        if not ga_integration.get("enabled"):
            logger.info(f"GA integration not enabled for account {account_id}")
            return None
        
        # Retrieve service account credentials from Secret Manager
        from ..secret_manager import get_secret
        secret_id = f"account-{account_id}-credentials"
        credentials = get_secret(secret_id)
        
        return base64.b64encode(credentials.encode()).decode()
        
    except Exception as e:
        logger.error(f"Failed to get credentials for account {account_id}: {e}")
        return None
```

#### 6. **Benefits of This Neo4j-Based Approach**

1. **Consistent Architecture**: All account data stored in Neo4j as per KEN-E design
2. **Graph Relationships**: Query which accounts have which integrations using Cypher
3. **Granular Control**: Each account has its own service account with specific permissions
4. **Multi-Product Support**: Same pattern works for Bing Ads, Meta Ads, etc.
5. **Audit Trail**: Track integration history with Neo4j temporal properties
6. **No OAuth Refresh Issues**: Service accounts don't expire
7. **Easy Revocation**: Users can revoke access from Google/Bing/Meta admin panels

### Step 4: Session Management

Update KEN-E to properly manage chatbot sessions:

```python
# In chat.py - end_session handling
@router.delete("/conversations/{session_id}")
async def delete_conversation(session_id: str, user_context: UserContext = Depends(get_current_user)):
    # Existing deletion logic...
    
    # Clean up chatbot session
    if hasattr(agent_client, 'chatbot_adapter'):
        agent_client.chatbot_adapter.end_session(session_id)
    
    return {"message": "Conversation deleted successfully"}
```

### Step 5: Error Handling and User Feedback

Enhance error messages for better user experience:

```python
# In KeneChatbotAdapter.process_chat_request
if not google_credentials and "analytics" in message.lower():
    return (
        "To access your Google Analytics data, please connect your Google account:\n"
        "1. Go to Settings → Integrations\n"
        "2. Click 'Connect Google Account'\n"
        "3. Grant access to Google Analytics\n"
        "Then try your query again!"
    )
```

## Security Considerations

### 1. Credential Encryption
- Always encrypt OAuth refresh tokens before storing
- Use Google Cloud KMS for encryption keys
- Rotate encryption keys regularly

### 2. Access Control
- Verify user has permission to access GA accounts
- Implement organization-level access controls
- Audit credential usage

### 3. Session Security
- Use secure session IDs (UUID v4)
- Implement session timeouts
- Clear credentials on logout

## Testing in Production

### 1. Staging Environment
```bash
# Deploy to staging
gcloud run deploy kene-api-staging \
  --set-env-vars MULTI_AGENT_SUPERVISOR_ID=<staging-agent-id>
```

### 2. Test Scenarios
- User without Google account connected
- User with valid GA access
- Session timeout handling
- Multiple concurrent sessions

### 3. Monitoring
```python
# Add logging for troubleshooting
logger.info(f"Chat request - User: {user_id}, Has GA: {bool(google_credentials)}")
logger.info(f"Routing to agent: {detected_agent}")
```

## Rollout Strategy

### Phase 1: Internal Testing
1. Deploy to staging environment
2. Test with internal users
3. Monitor performance and errors

### Phase 2: Beta Users
1. Enable for select beta users via feature flag
2. Gather feedback on routing accuracy
3. Refine agent instructions based on usage

### Phase 3: General Availability
1. Enable for all users
2. Monitor usage metrics
3. Iterate based on user feedback

## Configuration Reference

### Environment Variables
```bash
# Required
GOOGLE_CLOUD_PROJECT_ID=your-project-id
MULTI_AGENT_SUPERVISOR_ID=deployed-supervisor-id
GA_MCP_SERVER_URL=https://your-ga-mcp-server.run.app

# Optional
VERTEX_AI_LOCATION=us-central1
GA_CREDENTIAL_STORAGE=firestore  # or "secret_manager"
SESSION_TIMEOUT_MINUTES=60
```

### Firestore Schema
```
users/{userId}
├── uid: string
├── email: string
├── oauth_tokens
│   └── google
│       ├── refresh_token: string (encrypted)
│       ├── scopes: array
│       └── updated_at: timestamp
└── permissions
    └── analytics_accounts: array
```

## Troubleshooting

### Common Issues

1. **"No credentials found" for GA queries**
   - Check if user has connected Google account
   - Verify OAuth scopes include analytics.readonly
   - Check credential encryption/decryption

2. **Agent routing errors**
   - Review supervisor instructions
   - Check for ambiguous queries
   - Monitor routing decisions in logs

3. **Session management issues**
   - Verify session IDs are consistent
   - Check session timeout settings
   - Ensure proper cleanup on logout

### Debug Mode
```python
# Enable debug logging
import logging
logging.getLogger("kene_integration").setLevel(logging.DEBUG)
logging.getLogger("agents").setLevel(logging.DEBUG)
```

## Future Enhancements

1. **Additional Agents**
   - Social media analytics agent
   - SEO analysis agent
   - Email marketing agent

2. **Advanced Features**
   - Cross-agent insights (e.g., correlate news with traffic)
   - Scheduled reports
   - Custom alerts

3. **Performance Optimization**
   - Agent response caching
   - Parallel agent execution
   - Query intent caching