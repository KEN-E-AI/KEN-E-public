# Strategy Agent Implementation Documentation

## Overview

The Strategy Agent is an iterative AI-powered system for creating and refining marketing strategy documents. It integrates with the KEN-E platform to provide intelligent strategy generation with proper access control, audit trails, and cost tracking through Weights & Biases (W&B) integration.

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend                             │
│                    (React + TypeScript)                      │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTPS
┌─────────────────────▼───────────────────────────────────────┐
│                      API Layer                               │
│                  (FastAPI + Auth)                            │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │  Strategy    │ │    Usage     │ │    Audit     │        │
│  │   Router     │ │   Router     │ │   Service    │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                   Agent Layer (ADK)                          │
│  ┌──────────────────────────────────────────────────┐       │
│  │           Supervisor Agent (Router)               │       │
│  │  ┌────────┐ ┌────────┐ ┌─────────────────┐     │       │
│  │  │  News  │ │   GA   │ │    Strategy     │     │       │
│  │  │  Tool  │ │  Tool  │ │      Tool       │     │       │
│  │  └────────┘ └────────┘ └────────┬────────┘     │       │
│  └──────────────────────────────────┼───────────────┘       │
│                                     │                        │
│  ┌──────────────────────────────────▼───────────────┐       │
│  │         Iterative Strategy Agent                  │       │
│  │  ┌──────────────┐                                │       │
│  │  │  Strategist  │ → Creates initial document     │       │
│  │  └──────────────┘                                │       │
│  │  ┌──────────────────────────────────┐           │       │
│  │  │    Refinement Loop (≤3 iterations)│           │       │
│  │  │  ┌──────────┐  ┌──────────┐     │           │       │
│  │  │  │ Reviewer │→ │  Editor  │     │           │       │
│  │  │  └──────────┘  └──────────┘     │           │       │
│  │  └──────────────────────────────────┘           │       │
│  └──────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                    Storage Layer                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │  Firestore   │ │   W&B/Weave  │ │   Secret     │        │
│  │  (Documents) │ │   (Traces)   │ │   Manager    │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
└──────────────────────────────────────────────────────────────┘
```

### Agent Design

The Strategy Agent follows the **Tool Pattern**, not a sub-agent pattern:
- The supervisor maintains control of the conversation thread
- Strategy generation is a synchronous, blocking operation
- Results are returned to the supervisor for presentation
- This ensures consistent user experience and error handling

## Features

### 1. Strategy Document Types

The system supports six types of strategy documents:
- **Business Strategy**: Overall business strategic planning
- **Competitive Strategy**: Competitive analysis and positioning
- **Customer Strategy**: Customer segmentation and engagement
- **Marketing Strategy**: Marketing objectives and tactics
- **Measurement Plan**: KPIs and analytics framework
- **Brand Strategy**: Brand positioning and identity

### 2. Iterative Refinement Process

```
1. Strategist Agent creates initial document
   ↓
2. Reviewer Agent evaluates against guidelines
   ↓
3. If not approved: Editor Agent refines
   ↓
4. Loop up to 3 times or until approved
   ↓
5. Save final document to Firestore
```

### 3. Access Control

#### Permission Levels
- **Super Admin**: Full access to all accounts (KEN-E team)
- **Organization Admin**: Full access to organization accounts
- **Account Editor**: Can create/update documents for specific accounts
- **Account Viewer**: Can only view documents for specific accounts

#### Access Rules
```python
# Super admins always have access
if user.is_super_admin:
    return True

# Organization admins have implicit account access
if user.organization_permissions.get(org_id) == "admin":
    return True

# Check explicit account permissions
if user.account_permissions.get(account_id) in required_roles:
    return True
```

### 4. Audit Trail

Every document operation is logged with:
- **User Attribution**: Who performed the action
- **Timestamp**: When it occurred
- **IP Address**: Where from (for security)
- **Changes**: Before/after for updates
- **Session ID**: Link to chat conversation
- **Version**: Document version number

### 5. Cost Tracking & Observability

#### W&B Integration
```python
# Initialize Weave tracing
weave.init(project_name="quickstart_playground")

# Track token usage
track_token_usage(
    agent_name="strategy_agent",
    user_id=user_id,
    account_id=account_id,
    prompt_tokens=1000,
    response_tokens=2000,
    model="gemini-1.5-pro-002"
)
```

#### Pricing Model
| Model | Prompt Cost (per 1M) | Response Cost (per 1M) |
|-------|---------------------|------------------------|
| Gemini 2.0 Flash | $0.075 | $0.30 |
| Gemini 1.5 Pro | $3.50 | $10.50 |
| Gemini 1.5 Flash | $0.075 | $0.30 |

## API Endpoints

### Strategy Documents

#### List Documents
```http
GET /api/v1/strategy/{account_id}/documents
Authorization: Bearer {token}

Response:
{
  "documents": [...],
  "total_count": 5,
  "access_level": "edit"
}
```

#### Get Document
```http
GET /api/v1/strategy/{account_id}/documents/{doc_type}
Authorization: Bearer {token}

Response:
{
  "document": {...},
  "access_level": "edit",
  "can_edit": true,
  "can_delete": false
}
```

#### Create/Update Document
```http
POST /api/v1/strategy/{account_id}/documents/{doc_type}
Authorization: Bearer {token}
Content-Type: application/json

{
  "content": {...},
  "title": "Q1 2025 Strategy",
  "description": "Quarterly strategic plan"
}
```

#### Get Audit Log
```http
GET /api/v1/strategy/{account_id}/history/{doc_type}
Authorization: Bearer {token}

Response:
{
  "entries": [...],
  "total_count": 25,
  "date_from": "2025-01-01T00:00:00",
  "date_to": "2025-01-31T23:59:59"
}
```

### Usage & Costs

#### Get User Costs
```http
GET /api/v1/usage/user/{user_id}/costs
Authorization: Bearer {token}

Response:
{
  "user_id": "user_001",
  "email": "user@example.com",
  "summary": {
    "total_tokens": 50000,
    "total_cost": 0.175,
    "by_agent": {...}
  }
}
```

#### Get Account Costs (Admin Only)
```http
GET /api/v1/usage/account/{account_id}/costs
Authorization: Bearer {token}

Response:
{
  "account_id": "account_001",
  "summary": {...},
  "by_user": {...}
}
```

## Firestore Structure

```
/strategy_docs_{account_id}/
  {doc_type}/                    # Current document
    - content: {}
    - version: 1
    - created_at: timestamp
    - created_by: user_id
    - updated_at: timestamp
    - updated_by: user_id
    
  {doc_type}/versions/{version}/ # Version history
    - [full document snapshot]

/strategy_audit_{account_id}/
  {audit_id}/
    - action: "created|updated|deleted|viewed"
    - user_id: "firebase_uid"
    - user_email: "user@example.com"
    - timestamp: datetime
    - ip_address: "192.168.1.1"
    - changes: {before: {...}, after: {...}}
    - version: 1
    - session_id: "chat_session_id"

/usage_records/
  {record_id}/
    - user_id: "firebase_uid"
    - account_id: "account_001"
    - agent: "strategy_agent"
    - model: "gemini-1.5-pro-002"
    - prompt_tokens: 1000
    - response_tokens: 2000
    - total_cost: 0.0145
    - timestamp: datetime
```

## Environment Configuration

### Required Environment Variables

```bash
# Google Cloud
GOOGLE_CLOUD_PROJECT_ID=ken-e-staging
VERTEX_AI_LOCATION=us-central1
VERTEX_AI_AGENT_ENGINE_ID=projects/.../reasoningEngines/...

# Vertex AI Search (for strategy research)
VERTEX_AI_SEARCH_ENGINE_ID=strategy-docs-datastore

# W&B Integration
WANDB_API_KEY=your_api_key
WANDB_PROJECT=quickstart_playground
WANDB_ENTITY=your_team

# Firebase (for auth)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

### Development Setup

1. **Install Dependencies**
   ```bash
   cd /path/to/ken-e
   uv add weave wandb
   ```

2. **Configure W&B**
   ```bash
   wandb login
   export WANDB_API_KEY=your_key
   export WANDB_PROJECT=quickstart_playground
   ```

3. **Run Tests**
   ```bash
   pytest tests/unit/test_strategy_access_control.py
   pytest tests/unit/test_audit_service.py
   ```

## Usage Examples

### Via Chatbot

```
User: "Create a business strategy for Intellipure"

Supervisor → Strategy Tool → Iterative Agent:
1. Strategist researches and creates document
2. Reviewer checks against guidelines
3. Editor refines if needed
4. Document saved to Firestore
5. Response returned to user
```

### Via API

```python
import requests

# Create strategy document
response = requests.post(
    "https://api.ken-e.ai/api/v1/strategy/account_001/documents/business_strategy",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "content": strategy_content,
        "title": "2025 Business Strategy",
        "description": "Annual strategic plan"
    }
)

# Check audit trail
audit = requests.get(
    "https://api.ken-e.ai/api/v1/strategy/account_001/history/business_strategy",
    headers={"Authorization": f"Bearer {token}"}
)
```

## Security Considerations

### Data Protection
- **PII Sanitization**: All sensitive data is sanitized before W&B logging
- **Credential Isolation**: API keys stored in Secret Manager
- **HTTPS Only**: All API communication encrypted
- **Token Validation**: Firebase auth tokens validated on every request

### Compliance Features
- **Complete Audit Trail**: SOC2/ISO compliance ready
- **Version Control**: Full document history with rollback capability
- **Access Logging**: All access attempts logged with IP/user agent
- **Data Retention**: Configurable audit log retention (default 90 days)

## Monitoring & Alerts

### Key Metrics to Monitor
- **Token Usage**: Track costs per user/account
- **API Response Times**: Strategy generation latency
- **Error Rates**: Failed generation attempts
- **Access Violations**: Unauthorized access attempts

### W&B Dashboard
Access the W&B dashboard at: https://wandb.ai/{entity}/quickstart_playground

Monitor:
- Agent execution traces
- Token usage trends
- Cost breakdowns by user/account
- Performance metrics

## Troubleshooting

### Common Issues

1. **"Strategy agent not responding"**
   - Check VERTEX_AI_AGENT_ENGINE_ID is set
   - Verify service account has Vertex AI permissions
   - Check agent deployment status in GCP Console

2. **"Access denied" errors**
   - Verify user has correct account permissions
   - Check organization permissions are set
   - Ensure Firebase token is valid

3. **"Document not saving"**
   - Check Firestore permissions
   - Verify collection name format: `strategy_docs_{account_id}`
   - Check audit logs for errors

4. **"W&B traces not appearing"**
   - Verify WANDB_API_KEY is set
   - Check project name matches
   - Ensure weave.init() succeeded

## Future Enhancements

1. **Real-time Collaboration**: Multiple users editing simultaneously
2. **Template Library**: Pre-built strategy templates by industry
3. **Export Formats**: PDF, PowerPoint, Word generation
4. **Approval Workflows**: Multi-step approval process
5. **Strategy Analytics**: Performance tracking against goals
6. **AI Insights**: Automated strategy recommendations
7. **Integration APIs**: Connect with CRM, ERP systems

## Support

For issues or questions:
- GitHub Issues: https://github.com/KEN-E-AI/ken-e/issues
- Documentation: https://docs.ken-e.ai
- Support Email: support@ken-e.ai

---

*Last Updated: January 2025*
*Version: 1.0.0*