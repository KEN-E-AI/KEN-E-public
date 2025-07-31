# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

KEN-E is a multi-agent AI system for marketing analysis built on Google Cloud Platform. It combines LangGraph orchestration, CrewAI multi-agent collaboration, and a modern React frontend to provide comprehensive marketing insights and analytics.

## Project Structure

```
ken-e/
├── app/                    # Main agent system (LangGraph & CrewAI)
│   ├── agent.py           # Core LangGraph orchestration
│   ├── agent_engine_app.py # Google Cloud Agent Engine deployment
│   ├── crew/              # CrewAI multi-agent configuration
│   └── utils/             # Utilities for GCS, tracing, typing
├── api/                   # FastAPI REST service
│   ├── src/kene_api/      # API source code
│   ├── tests/             # API test suite
│   └── docker files       # Containerization configs
├── frontend/              # React TypeScript application
│   ├── src/               # Frontend source code
│   └── public/            # Static assets
├── data_ingestion/        # Vertex AI data pipeline
│   └── data_ingestion_pipeline/
├── deployment/            # Infrastructure & CI/CD
│   ├── terraform/         # IaC for GCP resources
│   ├── ci/               # CI pipeline (PR checks)
│   └── cd/               # CD pipelines (staging/prod)
├── notebooks/             # Jupyter notebooks for prototyping
└── tests/                 # Testing suite
    ├── unit/             # Unit tests
    ├── integration/      # Integration tests
    └── load_test/        # Load testing with Locust
```

## Common Development Commands

### Root Level (Main Application)
- `make install` - Install all dependencies using uv package manager
- `make test` - Run unit and integration tests
- `make lint` - Run code quality checks (codespell, ruff, mypy)
- `make ken-e` - Launch local interface (Note: Currently misconfigured)
- `make backend` - Deploy agent to Google Cloud Agent Engine
- `uv run jupyter lab` - Launch Jupyter notebooks for prototyping

### API Service (api/) - Python/FastAPI
**Note:** The API is a Python project using `pyproject.toml`. Do NOT use npm commands here.
- `cd api && uv run --active -- uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000` - Run FastAPI development server
- `cd api && python run_dev.py` - Alternative dev server launcher
- `cd api && pytest tests/` - Run API tests
- `cd api && ./docker.sh dev` - Run API in Docker container
- `cd api && ./docker.sh test` - Run tests in Docker
- `cd api && ./scripts/set_environment.sh [development|staging|production]` - Switch API environment

### Frontend (frontend/) - React/TypeScript
**Note:** The frontend is a Node.js project using `package.json`. Use npm commands here.
- `cd frontend && npm run dev:development` - Start development server on port 8080 (development env)
- `cd frontend && npm run dev:staging` - Start development server on port 8080 (staging env)
- `cd frontend && npm run dev:production` - Start development server on port 8080 (production env)
- `cd frontend && npm run build` - Build for production
- `cd frontend && npm run build:staging` - Build for staging
- `cd frontend && npm run build:production` - Build for production
- `cd frontend && npm test` - Run Vitest tests
- `cd frontend && npm run typecheck` - Type checking
- `cd frontend && npm run format.fix` - Format with Prettier
- `cd frontend && ./scripts/set_environment.sh [development|staging|production]` - Switch frontend environment

**Important CSS Note**: The frontend's `src/App.css` file should be kept minimal or empty. Default Vite/React template styles (like `text-align: center` on `#root`) can break dashboard layouts. See frontend/CLAUDE.md for CSS architecture details.

### Data Ingestion (data_ingestion/)
- `cd data_ingestion && python data_ingestion_pipeline/submit_pipeline.py` - Submit pipeline to Vertex AI

## Architecture Overview

### Core Components

1. **Agent System** (`app/`):
   - **Main Agent** (`app/agent.py`): LangGraph-based orchestration using ChatVertexAI (Gemini 2.0 Flash)
   - **CrewAI Multi-Agent** (`app/crew/`): Three specialized agents:
     - **KEN-E**: Main execution agent
     - **BET-E**: Web scraping and data collection agent
     - **VIK-E**: Reporting and analysis agent
   - **Agent Engine App** (`app/agent_engine_app.py`): Deployment wrapper for Google Cloud Agent Engine
   - **Utilities**: GCS operations, OpenTelemetry tracing, type definitions

2. **API Service** (`api/`):
   - **FastAPI Application** (`api/src/kene_api/main.py`): RESTful API with async support
   - **Database Layer**: 
     - Neo4j for graph data and relationships
     - Firestore for document storage and user data
   - **Routers**: Modular endpoints for:
     - Metrics and KPIs
     - Activities and tasks
     - Insights and intuitions
     - Items and entities
     - Funnel reports
   - **Authentication**: Firebase Auth integration
   - **Docker Support**: Multiple compose configurations for dev/prod

3. **Frontend** (`frontend/`):
   - **React 18 + TypeScript**: Modern SPA built with Vite
   - **UI Components**: ~50 components based on Radix UI primitives
   - **Styling**: TailwindCSS with custom configuration
   - **Routing**: React Router 6 with protected routes
   - **State Management**: 
     - AuthContext for authentication
     - TanStack Query for server state
   - **Data Visualization**: Recharts and React Three Fiber

4. **Data Ingestion** (`data_ingestion/`):
   - **Vertex AI Pipeline**: Kubeflow-based pipeline
   - **Components**: Modular data processing stages
   - **Embedding Generation**: Vector embeddings for RAG

### Key Technologies

- **Python Stack**: 
  - LangGraph & LangChain for AI orchestration
  - CrewAI for multi-agent collaboration
  - FastAPI for REST API
  - Neo4j Python driver
  - Firebase Admin SDK
  - OpenTelemetry for tracing
  
- **JavaScript Stack**: 
  - React 18 with TypeScript
  - Vite for fast builds
  - TailwindCSS for styling
  - Radix UI for accessible components
  - React Hook Form + Zod for forms
  - Axios for API calls

- **Infrastructure**: 
  - Google Cloud Platform (primary)
  - Vertex AI for ML workloads
  - Cloud Run for containerized services
  - Firebase for auth and Firestore
  - Neo4j Aura for graph database
  - BigQuery for analytics

## Development Workflow

### Agent Development
1. Prototype agent logic in Jupyter notebooks (`notebooks/`)
2. Implement agent logic in `app/agent.py`
3. Configure CrewAI agents in `app/crew/config/`
4. Test locally with appropriate commands
5. Deploy with `make backend` to Agent Engine

### API Development
1. Define Pydantic models in `api/src/kene_api/models/`
2. Create routers in `api/src/kene_api/routers/`
3. Add tests in `api/tests/`
4. Test endpoints with auto-generated docs at `/docs`
5. Use `./docker.sh` for containerized development

### Frontend Development
1. Create components in `frontend/src/components/`
2. Define TypeScript types in `frontend/src/types/`
3. Add pages in `frontend/src/pages/`
4. Use existing UI components from `frontend/src/components/ui/`
5. Test with appropriate environment:
   - Development: `npm run dev:development` (port 8080)
   - Staging: `npm run dev:staging` (port 8080)
   - Production: `npm run dev:production` (port 8080)

### Data Pipeline Development
1. Define pipeline components in `data_ingestion/data_ingestion_pipeline/`
2. Test components locally
3. Submit to Vertex AI with `submit_pipeline.py`

## Testing Strategy

- **Unit Tests**: 
  - Python: pytest in `tests/unit/` and component directories
  - Frontend: Vitest with `.spec.ts` files
  
- **Integration Tests**: 
  - End-to-end testing in `tests/integration/`
  - Database integration tests in API
  
- **Load Testing**: 
  - Locust-based tests in `tests/load_test/`
  - Integrated into CI/CD pipeline
  - Results stored in GCS

- **Test Commands**:
  - Root: `make test`
  - API: `cd api && pytest tests/`
  - Frontend: `cd frontend && npm test`
  - Docker: `cd api && ./docker.sh test`

## Infrastructure & Deployment

### Terraform Infrastructure (`deployment/terraform/`)
- **Multi-environment**: Separate staging and production projects
- **Resources managed**:
  - API enablement (30+ Google Cloud APIs)
  - Cloud Build triggers
  - Cloud SQL (PostgreSQL) instances
  - IAM policies and service accounts
  - Storage buckets for artifacts
  - Log sinks for monitoring
  - Secret Manager for credentials

### CI/CD Pipelines

- **PR Checks** (`deployment/ci/pr_checks.yaml`):
  - Dependency installation with uv
  - Unit and integration tests
  - Code quality checks
  - Runs on every pull request

- **Staging Deployment** (`deployment/cd/staging.yaml`):
  - Deploys data pipeline to Vertex AI
  - Deploys agent to Agent Engine
  - Builds and deploys frontend to Cloud Run
  - Builds and deploys API to Cloud Run
  - Runs load tests
  - Triggers production deployment on success

- **Production Deployment** (`deployment/cd/deploy-to-prod.yaml`):
  - Requires manual approval
  - Mirrors staging deployment steps
  - Additional monitoring and alerts

### Environment Configuration

#### Switching Environments

**API Environment Switching:**
```bash
cd api
./scripts/set_environment.sh [development|staging|production]
```

**Frontend Environment Switching:**
```bash
cd frontend
./scripts/set_environment.sh [development|staging|production]
```

**Complete Environment Switch Workflow:**
```bash
# Switch API environment
cd api && ./scripts/set_environment.sh staging

# Switch frontend environment
cd frontend && ./scripts/set_environment.sh staging

# Restart services to pick up new environment
cd api && uv run --active -- uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000
cd frontend && npm run dev:staging  # or dev:development / dev:production
```

#### API Environment Variables:
- `DEBUG`: Enable debug mode
- `HOST`, `PORT`: Server configuration
- `CORS_ORIGINS`: Allowed origins
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`: Graph database
- `GOOGLE_CLOUD_PROJECT_ID`: GCP project ID
- `FIRESTORE_DATABASE_ID`: Firestore instance
- `LOG_LEVEL`: Logging configuration
- `ENVIRONMENT`: Environment indicator (development|staging|production)

#### Frontend Environment Variables:
- `VITE_API_BASE_URL`: Backend API URL
- `VITE_FIREBASE_*`: Firebase configuration
- `VITE_ENVIRONMENT`: Environment indicator (development|staging|production)
- All frontend env vars must be prefixed with `VITE_`

## Data Architecture

- **Neo4j**: Graph database for entity relationships
  - Marketing metrics relationships
  - Activity dependencies
  - Knowledge graph structure
  
- **Firestore**: Document storage
  - User profiles and preferences
  - Organization configurations
  - Session data
  
- **BigQuery**: Analytics and data warehouse
  - Event logs
  - Aggregated metrics
  - Historical data
  
- **Vertex AI Search**: RAG-enabled search
  - Document embeddings
  - Semantic search capabilities

## Monitoring & Observability

- **OpenTelemetry**: Distributed tracing across all services
- **Google Cloud Logging**: Centralized log aggregation
- **Cloud Monitoring**: Metrics and alerting
- **Health Endpoints**: 
  - API: `/health` endpoint
  - Frontend: Build-time health checks

## Development Tools

- **Package Management**:
  - Python: `uv` (modern, fast alternative to pip)
  - JavaScript: `npm`
  
- **Code Quality**:
  - Python: ruff (formatter & linter), mypy (type checking), codespell
  - JavaScript: Prettier, TypeScript compiler
  
- **Development Environment**:
  - Hot reload for both API and frontend
  - Docker support for consistent environments
  - Jupyter notebooks for experimentation

## Security Considerations

- **Authentication**: Firebase Auth across all services
- **API Security**: 
  - CORS configuration
  - Request validation
  - Rate limiting (planned)
  
- **Secrets Management**: 
  - Google Secret Manager for production
  - Environment files for local development
  - Never commit secrets to repository

## Common Issues & Solutions

1. **Port Conflicts**: Frontend runs on 8080, API on 8000
2. **Database Connections**: Ensure Neo4j and Firestore credentials are set
3. **Build Errors**: Check all environment variables are configured
4. **Type Errors**: Some TypeScript strict checks are disabled in frontend

## Best Practices

1. **Code Style**:
   - Follow existing patterns in each service
   - Run formatters before committing
   - Write meaningful commit messages
   
2. **Testing**:
   - Write tests for new features
   - Maintain test coverage above 80%
   - Use integration tests for complex flows
   
3. **Documentation**:
   - Update relevant CLAUDE.md files when adding features
   - Document API endpoints in OpenAPI format
   - Keep TypeScript types well-documented

4. **Performance**:
   - Use proper database indexes
   - Implement caching where appropriate
   - Monitor API response times

## Getting Started

1. Clone the repository
2. Install Python dependencies: `make install`
3. Install frontend dependencies: `cd frontend && npm install`
4. Copy environment files:
   - `cp api/.env.example api/.env`
   - Create `frontend/.env.local` with required vars
5. Start services:
   - API: `cd api && uvicorn src.kene_api.main:app --reload`
   - Frontend: `cd frontend && npm run dev:development` (or dev:staging/dev:production)
6. Access applications:
   - Frontend: http://localhost:8080
   - API Docs: http://localhost:8000/docs

## Implementation Best Practices

### 0 — Purpose  

These rules ensure maintainability, safety, and developer velocity. 
**MUST** rules are enforced by CI; **SHOULD** rules are strongly recommended.

---

### 1 — Before Coding

- **BP-1 (MUST)** Ask the user clarifying questions.
- **BP-2 (SHOULD)** Draft and confirm an approach for complex work.  
- **BP-3 (SHOULD)** If ≥ 2 approaches exist, list clear pros and cons.

---

### 2 — While Coding

- **C-1 (MUST)** Follow TDD: scaffold stub -> write failing test -> implement.
- **C-2 (MUST)** Name functions with existing domain vocabulary for consistency.  
- **C-3 (SHOULD NOT)** Introduce classes when small testable functions suffice.  
- **C-4 (SHOULD)** Prefer simple, composable, testable functions.
- **C-5 (MUST)** For TypeScript/Frontend: Prefer branded `type`s for IDs
  ```ts
  type UserId = Brand<string, 'UserId'>   // ✅ Good
  type UserId = string                    // ❌ Bad
  ```  
- **C-6 (MUST)** For TypeScript/Frontend: Use `import type { … }` for type-only imports.
- **C-7 (SHOULD NOT)** Add comments except for critical caveats; rely on self‑explanatory code.
- **C-8 (SHOULD)** For TypeScript/Frontend: Default to `type`; use `interface` only when more readable or interface merging is required. 
- **C-9 (SHOULD NOT)** Extract a new function unless it will be reused elsewhere, is the only way to unit-test otherwise untestable logic, or drastically improves readability of an opaque block.

### Python-Specific Practices

- **PY-1 (MUST)** Use type hints for all function arguments and return values.
- **PY-2 (MUST)** Use Pydantic models for data validation and serialization.
- **PY-3 (SHOULD)** Use async/await for I/O operations in FastAPI endpoints.
- **PY-4 (SHOULD)** Follow PEP 8 naming conventions (snake_case for functions/variables).
- **PY-5 (MUST)** Use context managers for database connections and file operations.
- **PY-6 (SHOULD)** Prefer f-strings over other string formatting methods.
- **PY-7 (MUST)** Handle exceptions explicitly; avoid bare except clauses.

---

### 3 — Testing

- **T-1 (MUST)** For Python functions, colocate unit tests in `test_*.py` files following pytest conventions.
- **T-2 (MUST)** For frontend components, colocate tests in `*.spec.ts` or `*.test.tsx` files.
- **T-3 (MUST)** For API changes, add/extend integration tests in `api/tests/`.
- **T-4 (MUST)** ALWAYS separate pure-logic unit tests from DB-touching integration tests.
- **T-5 (SHOULD)** Prefer integration tests over heavy mocking.
- **T-6 (SHOULD)** Unit-test complex algorithms thoroughly.
- **T-7 (SHOULD)** For Python, use pytest fixtures for test data and setup.
- **T-8 (SHOULD)** Test the entire structure in one assertion if possible
  ```python
  # Python example
  assert result == [expected_value]  # Good
  
  assert len(result) == 1  # Bad
  assert result[0] == expected_value  # Bad
  ```

---

### 4 — Database

- **D-1 (MUST)** Use Neo4j Python driver's session management properly - always use context managers.
- **D-2 (MUST)** Define Pydantic models for all database entities in `api/src/kene_api/models/`.
- **D-3 (SHOULD)** Use Firestore batch operations when updating multiple documents.
- **D-4 (SHOULD)** Create appropriate indexes in Neo4j for frequently queried properties.
- **D-5 (MUST)** Never hardcode database credentials; use environment variables.

---

### 5 — Code Organization

- **O-1 (MUST)** Keep agent logic in `app/`, API logic in `api/`, and frontend in `frontend/`.
- **O-2 (MUST)** Share types between frontend and API through well-defined interfaces.
- **O-3 (SHOULD)** Place reusable utilities in appropriate `utils/` directories.

---

### 6 — Tooling Gates

- **G-1 (MUST)** `make lint` passes (includes ruff, mypy, codespell).
- **G-2 (MUST)** `npm run format.fix` passes for frontend code.
- **G-3 (MUST)** `npm run typecheck` passes for frontend TypeScript.

---

### 7 - Git

- **GH-1 (MUST)** Use Conventional Commits format when writing commit messages: https://www.conventionalcommits.org/en/v1.0.0
- **GH-2 (SHOULD NOT)** Refer to Claude or Anthropic in commit messages.

---

## Writing Functions Best Practices

When evaluating whether a function you implemented is good or not, use this checklist:

1. Can you read the function and HONESTLY easily follow what it's doing? If yes, then stop here.
2. Does the function have very high cyclomatic complexity? (number of independent paths, or, in a lot of cases, number of nesting if if-else as a proxy). If it does, then it's probably sketchy.
3. Are there any common data structures and algorithms that would make this function much easier to follow and more robust? Parsers, trees, stacks / queues, etc.
4. Are there any unused parameters in the function?
5. Are there any unnecessary type casts that can be moved to function arguments?
6. Is the function easily testable without mocking core features (e.g. sql queries, redis, etc.)? If not, can this function be tested as part of an integration test?
7. Does it have any hidden untested dependencies or any values that can be factored out into the arguments instead? Only care about non-trivial dependencies that can actually change or affect the function.
8. Brainstorm 3 better function names and see if the current name is the best, consistent with rest of codebase.

IMPORTANT: you SHOULD NOT refactor out a separate function unless there is a compelling need, such as:
  - the refactored function is used in more than one place
  - the refactored function is easily unit testable while the original function is not AND you can't test it any other way
  - the original function is extremely hard to follow and you resort to putting comments everywhere just to explain it

## Writing Tests Best Practices

When evaluating whether a test you've implemented is good or not, use this checklist:

1. SHOULD parameterize inputs; never embed unexplained literals such as 42 or "foo" directly in the test.
2. SHOULD NOT add a test unless it can fail for a real defect. Trivial asserts (e.g., expect(2).toBe(2)) are forbidden.
3. SHOULD ensure the test description states exactly what the final expect verifies. If the wording and assert don't align, rename or rewrite.
4. SHOULD compare results to independent, pre-computed expectations or to properties of the domain, never to the function's output re-used as the oracle.
5. SHOULD follow the same lint, type-safety, and style rules as prod code (prettier, ESLint, strict types).
6. SHOULD express invariants or axioms (e.g., commutativity, idempotence, round-trip) rather than single hard-coded cases whenever practical. Use property-based testing libraries when appropriate.
7. Unit tests for a function should be grouped under `describe(functionName, () => ...` for JavaScript or class-based organization for Python.
8. Use appropriate matchers for the test framework (e.g., `expect.any(...)` for Jest, `pytest.approx()` for floating point comparisons).
9. ALWAYS use strong assertions over weaker ones e.g. `expect(x).toEqual(1)` instead of `expect(x).toBeGreaterThanOrEqual(1)`.
10. SHOULD test edge cases, realistic input, unexpected input, and value boundaries.
11. SHOULD NOT test conditions that are caught by the type checker.

## Remember Shortcuts

Remember the following shortcuts which the user may invoke at any time.

### QNEW

When I type "qnew", this means:

```
Understand all BEST PRACTICES listed in CLAUDE.md.
Your code SHOULD ALWAYS follow these best practices.
```

### QPLAN
When I type "qplan", this means:
```
Analyze similar parts of the codebase and determine whether your plan:
- is consistent with rest of codebase
- introduces minimal changes
- reuses existing code
```

## QCODE

When I type "qcode", this means:

```
Implement your plan and make sure your new tests pass.
Always run tests to make sure you didn't break anything else.
Always run formatting tools on the newly created files to ensure standard formatting.
Always run type checking to make sure typing is correct.
```

### QCHECK

When I type "qcheck", this means:

```
You are a SKEPTICAL senior software engineer.
Perform this analysis for every MAJOR code change you introduced (skip minor changes):

1. CLAUDE.md checklist Writing Functions Best Practices.
2. CLAUDE.md checklist Writing Tests Best Practices.
3. CLAUDE.md checklist Implementation Best Practices.
```

### QCHECKF

When I type "qcheckf", this means:

```
You are a SKEPTICAL senior software engineer.
Perform this analysis for every MAJOR function you added or edited (skip minor changes):

1. CLAUDE.md checklist Writing Functions Best Practices.
```

### QCHECKT

When I type "qcheckt", this means:

```
You are a SKEPTICAL senior software engineer.
Perform this analysis for every MAJOR test you added or edited (skip minor changes):

1. CLAUDE.md checklist Writing Tests Best Practices.
```

### QUX

When I type "qux", this means:

```
Imagine you are a human UX tester of the feature you implemented. 
Output a comprehensive list of scenarios you would test, sorted by highest priority.
```

### QGIT

When I type "qgit", this means:

```
Add all changes to staging, create a commit, and push to remote.

Follow this checklist for writing your commit message:
- SHOULD use Conventional Commits format: https://www.conventionalcommits.org/en/v1.0.0
- SHOULD NOT refer to Claude or Anthropic in the commit message.
- SHOULD structure commit message as follows:
<type>[optional scope]: <description>
[optional body]
[optional footer(s)]
- commit SHOULD contain the following structural elements to communicate intent: 
fix: a commit of the type fix patches a bug in your codebase (this correlates with PATCH in Semantic Versioning).
feat: a commit of the type feat introduces a new feature to the codebase (this correlates with MINOR in Semantic Versioning).
BREAKING CHANGE: a commit that has a footer BREAKING CHANGE:, or appends a ! after the type/scope, introduces a breaking API change (correlating with MAJOR in Semantic Versioning). A BREAKING CHANGE can be part of commits of any type.
types other than fix: and feat: are allowed, for example @commitlint/config-conventional (based on the Angular convention) recommends build:, chore:, ci:, docs:, style:, refactor:, perf:, test:, and others.
footers other than BREAKING CHANGE: <description> may be provided and follow a convention similar to git trailer format.
```

## Vertex AI Agent Engine Integration

This section documents the complete process and lessons learned from integrating the KEN-E frontend chatbot with a Vertex AI Agent Engine deployed on Google Cloud Platform.

### Overview

The integration connects existing frontend chatbot components (`HomeChatArea.tsx` and `ChatSidebar.tsx`) with a deployed ADK (Agent Development Kit) chatbot via Vertex AI Agent Engine, replacing simulated responses with real AI-powered responses.

### Architecture

```
Frontend (React) → API (FastAPI) → Vertex AI Agent Engine (GCP)
    ↓                  ↓                      ↓
chatService.ts   chat.py router      Deployed ADK Agent
```

### Key Components

1. **API Router**: `api/src/kene_api/routers/chat.py`
   - `AgentEngineClient` class for Agent Engine communication
   - `/api/v1/chat/completions` endpoint (POST)
   - `/api/v1/chat/health` endpoint (GET)

2. **Frontend Service**: `frontend/src/services/chatService.ts`
   - `ChatService` class with Firebase Auth integration
   - Methods: `sendMessage()`, `streamMessage()`, `checkHealth()`

3. **Test Scripts**: `api/scripts/`
   - `test_agent_chat.py` - Local testing without full API deployment
   - `test_reasoning_engine_methods.py` - Debug Agent Engine API methods

### Critical Lessons Learned

#### 1. **API Discovery Issue**
- **Problem**: Initially used `reasoning_engines` API
- **Solution**: Must use `agent_engines` API for deployed Agent Engines
- **Code**: 
  ```python
  from vertexai import agent_engines  # NOT reasoning_engines
  agent_engine = agent_engines.get(agent_engine_id)
  ```

#### 2. **Parameter Mismatch Issue**
- **Problem**: Agent expected `message` and `user_id`, we sent `input`
- **Error Log**: `TypeError: AdkApp.stream_query() missing 2 required keyword-only arguments: 'message' and 'user_id'`
- **Solution**: 
  ```python
  # WRONG
  agent_engine.stream_query(input=user_input)
  
  # CORRECT
  agent_engine.stream_query(message=user_input, user_id=user_id)
  ```

#### 3. **Response Structure Issue**
- **Problem**: Agent returns nested structure, not simple text
- **Agent Response Format**:
  ```python
  {
    'content': {
      'parts': [{'text': 'Actual response text here'}]
    },
    'grounding_metadata': {...},
    'usage_metadata': {...},
    'invocation_id': '...',
    'author': '...',
    'actions': [...],
    'id': '...',
    'timestamp': '...'
  }
  ```
- **Solution**: Parse nested structure to extract text:
  ```python
  if 'content' in chunk and isinstance(chunk['content'], dict):
      content = chunk['content']
      if 'parts' in content and isinstance(content['parts'], list):
          for part in content['parts']:
              if isinstance(part, dict) and 'text' in part:
                  response_parts.append(part['text'])
  ```

#### 4. **Authentication Configuration**
- **Development**: Use user credentials via `gcloud auth application-default login`
- **Production**: Use service account credentials via `GOOGLE_APPLICATION_CREDENTIALS`
- **Environment Variables**:
  ```bash
  GOOGLE_CLOUD_PROJECT_ID=ken-e-staging
  VERTEX_AI_LOCATION=us-central1
  VERTEX_AI_AGENT_ENGINE_ID=projects/ken-e-staging/locations/us-central1/reasoningEngines/YOUR_ID
  ```

### Debugging Agent Engine Issues

#### 1. **Check Agent Logs**
```bash
# Get recent logs for specific reasoning engine
gcloud logging read "resource.labels.reasoning_engine_id=\"YOUR_ENGINE_ID\"" \
  --project=YOUR_PROJECT --limit=20

# Search for specific errors
gcloud logging read "resource.labels.reasoning_engine_id=\"YOUR_ENGINE_ID\" AND textPayload:\"TypeError\"" \
  --project=YOUR_PROJECT --limit=10
```

#### 2. **Local Testing Scripts**
```bash
# Test integration without full API deployment
cd api
uv run -- python scripts/test_agent_chat.py

# Debug Agent Engine API methods and signatures
uv run -- python scripts/test_reasoning_engine_methods.py
```

#### 3. **Common Error Patterns**
- **400 Reasoning Engine Execution failed**: Check parameter names and types
- **TypeError: missing required keyword-only arguments**: Verify method signature
- **InvalidRequestError**: Check deployed agent configuration
- **Authentication errors**: Verify credentials and project access

### Environment Configuration

#### API Environment Variables (`.env.development`, `.env.staging`, `.env.production`)
```bash
# Required for Vertex AI Agent Engine
VERTEX_AI_LOCATION=us-central1
VERTEX_AI_AGENT_ENGINE_ID=projects/PROJECT/locations/LOCATION/reasoningEngines/ID
GOOGLE_CLOUD_PROJECT_ID=your-project-id

# Optional: Service account path (for production)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

#### Frontend Environment Variables
```bash
# No changes needed - uses existing API_BASE_URL
VITE_API_BASE_URL=http://localhost:8000
```

### Implementation Checklist

#### Backend (API)
- [x] Add `google-cloud-aiplatform>=1.90.0` to `pyproject.toml`
- [x] Create `AgentEngineClient` class in chat router
- [x] Use `agent_engines.get()` not `reasoning_engines`
- [x] Pass `message=user_input, user_id=user_id` parameters
- [x] Parse nested response structure `content.parts[].text`
- [x] Handle both streaming and non-streaming responses
- [x] Add proper error handling and logging

#### Frontend
- [x] Create `ChatService` class with Firebase Auth
- [x] Update chatbot components to use real API calls
- [x] Remove `setTimeout()` simulated responses
- [x] Add loading states and error handling

#### Testing
- [x] Create local test scripts for debugging (`api/scripts/`)
- [x] Test with user credentials (`gcloud auth application-default login`)
- [x] Verify response parsing extracts clean text
- [x] Test both streaming and non-streaming modes

### Deployment Considerations

1. **Service Account Setup**: Ensure proper IAM roles for Vertex AI access
2. **Environment Variables**: Configure all required variables in deployment (see Cloud Build configuration below)
3. **Error Monitoring**: Monitor logs for Agent Engine execution errors
4. **Session Management**: Agent Engine creates/manages sessions automatically
5. **Rate Limiting**: Consider implementing rate limiting for chat endpoints

#### Cloud Build Deployment Configuration

The Vertex AI Agent Engine environment variables have been added to both staging and production Cloud Build pipelines:

**Staging** (`deployment/cd/staging.yaml`):
- Environment variables: `VERTEX_AI_LOCATION=${_VERTEX_AI_LOCATION},VERTEX_AI_AGENT_ENGINE_ID=${_VERTEX_AI_AGENT_ENGINE_ID_STAGING}`
- Substitutions:
  ```yaml
  _VERTEX_AI_LOCATION: us-central1
  _VERTEX_AI_AGENT_ENGINE_ID_STAGING: ${_VERTEX_AI_AGENT_ENGINE_ID_STAGING}
  ```

**Production** (`deployment/cd/deploy-to-prod.yaml`):
- Environment variables: `VERTEX_AI_LOCATION=${_VERTEX_AI_LOCATION},VERTEX_AI_AGENT_ENGINE_ID=${_VERTEX_AI_AGENT_ENGINE_ID_PROD}`
- Substitutions:
  ```yaml
  _VERTEX_AI_LOCATION: us-central1
  _VERTEX_AI_AGENT_ENGINE_ID_PROD: ${_VERTEX_AI_AGENT_ENGINE_ID_PROD}
  ```

**Configuration Details:**

**Staging**: Uses the actual Agent Engine ID directly in the substitutions:
```
_VERTEX_AI_AGENT_ENGINE_ID_STAGING: projects/ken-e-staging/locations/us-central1/reasoningEngines/98331523895263232
```

**Production**: Requires Cloud Build trigger variable configuration:
- `_VERTEX_AI_AGENT_ENGINE_ID_PROD`: Must be set in the production Cloud Build trigger settings to the actual production Agent Engine ID

**How to Configure Cloud Build Trigger Variables:**
1. Go to Google Cloud Console → Cloud Build → Triggers
2. Edit the production deployment trigger
3. Under "Substitution variables", add:
   - Variable: `_VERTEX_AI_AGENT_ENGINE_ID_PROD`
   - Value: `projects/ken-e-production/locations/us-central1/reasoningEngines/YOUR_PROD_ENGINE_ID`

### Troubleshooting Common Issues

#### "No module named 'vertexai'" 
```bash
cd api && uv add google-cloud-aiplatform
```

#### "ReasoningEngine object has no attribute 'query'"
Switch from `reasoning_engines` to `agent_engines` API.

#### "TypeError: missing required keyword-only arguments"
Check deployed agent's expected parameters via logs. Use `message` and `user_id`, not `input`.

#### Response is raw dictionary string
Implement nested structure parsing for `{'content': {'parts': [{'text': '...'}]}}` format.

#### Authentication failures
Verify credentials: `gcloud auth application-default login` for development, service account for production.

### API Endpoint Documentation

#### POST `/api/v1/chat/completions`
**Request:**
```json
{
  "messages": [{"role": "user", "content": "Hello", "timestamp": "2025-01-31T12:00:00Z"}],
  "stream": false,
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "role": "assistant",
  "content": "Hi there! How can I help you with company news today?",
  "session_id": "chat_1234567890_abc123def"
}
```

#### GET `/api/v1/chat/health`
**Response:**
```json
{
  "status": "healthy",
  "agent_engine_status": "connected",
  "project_id": "ken-e-staging",
  "location": "us-central1"
}
```

This integration provides a robust, production-ready connection between the KEN-E frontend and Vertex AI Agent Engine, with comprehensive error handling, logging, and debugging capabilities.