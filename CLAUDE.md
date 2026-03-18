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

## Quick Start Commands

### First Time Setup (Local Development)

```bash
# Run the setup script to configure GCP authentication and secrets
./api/scripts/setup_local_dev.sh
```

This script will:
- Authenticate you with Google Cloud
- Verify Secret Manager access
- Test email service configuration
- Check Python environment

### API Service (Python/FastAPI)
```bash
# Development server (recommended - avoids reload issues)
cd api && uv run uvicorn src.kene_api.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
cd api && pytest tests/

# Switch environment
cd api && ./scripts/set_environment.sh [development|staging|production]
```

### Frontend (React/TypeScript)
```bash
# Development server (port 8080)
cd frontend && npm run dev:[development|staging|production]

# Build & test
cd frontend && npm run build
cd frontend && npm test
cd frontend && npm run typecheck
cd frontend && npm run format.fix

# Switch environment
cd frontend && ./scripts/set_environment.sh [development|staging|production]
```

### Root Level Commands
```bash
make install  # Install dependencies
make test     # Run all tests
make lint     # Run code quality checks
make backend  # Deploy to Agent Engine
```

## Core Architecture

- **Agent System** (`app/`): LangGraph orchestration with CrewAI agents (KEN-E, BET-E, VIK-E)
- **API** (`api/`): FastAPI with Neo4j graph DB and Firestore
- **Frontend** (`frontend/`): React 18 + TypeScript, TailwindCSS, Radix UI
- **Infrastructure**: GCP (Vertex AI, Cloud Run, Firebase)

## Key Environment Variables

### API
- `GOOGLE_CLOUD_PROJECT`: GCP project ID for Secret Manager (required for local dev)
- `GOOGLE_CLOUD_PROJECT_ID`: GCP project ID for Firestore
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`: Graph database
- `VERTEX_AI_LOCATION`, `VERTEX_AI_AGENT_ENGINE_ID`: Agent Engine config
- `SENDGRID_API_KEY`: SendGrid API key (supports `sm://secret-name` format)
- `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME`: Email sender configuration
- `APP_BASE_URL`: Frontend URL for generating invitation links
- `ENVIRONMENT`: development|staging|production

### Frontend
- `VITE_API_BASE_URL`: Backend API URL
- `VITE_FIREBASE_*`: Firebase configuration
- `VITE_ENVIRONMENT`: Environment indicator
- All frontend env vars must be prefixed with `VITE_`

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

## Email Service Setup (Local Development)

The API uses SendGrid for sending invitation emails. To enable this locally:

### Automatic Setup (Recommended)
```bash
./api/scripts/setup_local_dev.sh
```

### Manual Setup

1. **Authenticate with Google Cloud:**
   ```bash
   gcloud auth application-default login
   ```

2. **Set your GCP project:**
   ```bash
   export GOOGLE_CLOUD_PROJECT=ken-e-dev
   # Or add to api/.env: GOOGLE_CLOUD_PROJECT=ken-e-dev
   ```

3. **Verify Secret Manager access:**
   ```bash
   gcloud secrets versions access latest --secret="sendgrid-api-key" --project=ken-e-dev
   ```

4. **Test the setup:**
   ```bash
   python api/scripts/diagnose_email_service.py
   ```

   You should see: `✅ Email service appears to be configured correctly`

### Alternative: Direct API Key (Without GCP Auth)

If you prefer not to use Secret Manager locally:

1. Get the SendGrid API key from Secret Manager or create a dev key at https://app.sendgrid.com/settings/api_keys

2. Add to `api/.env`:
   ```bash
   SENDGRID_API_KEY=SG.your-actual-key-here  # NOT sm://
   ```

3. Restart the API server

### Troubleshooting

- **"SendGrid API key not found"**: Run `./api/scripts/setup_local_dev.sh` or set `GOOGLE_CLOUD_PROJECT`
- **"Failed to fetch secret"**: Check that you're authenticated with `gcloud auth application-default login`
- **"Permission denied"**: Ensure you have the `roles/secretmanager.secretAccessor` role

## Common Issues & Solutions

1. **Port Conflicts**: Frontend runs on 8080, API on 8000
2. **Database Connections**: Ensure Neo4j and Firestore credentials are set
3. **Build Errors**: Check all environment variables are configured
4. **Type Errors**: Some TypeScript strict checks are disabled in frontend
5. **API Server Reload Loop**:
   - Use `uv run` WITHOUT the `--active` flag (recommended)
   - Alternative: `cd api && python -m uvicorn src.kene_api.main:app --reload`
6. **Invitation Emails Not Sending**: See "Email Service Setup" section above

## Vertex AI Agent Engine API Endpoints

### POST `/api/v1/chat/completions`
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
  "content": "Response text",
  "session_id": "chat_1234567890_abc123def"
}
```

### GET `/api/v1/chat/health`
Check Agent Engine connectivity and status.

## Design Documentation & Architecture Decisions

### Documentation Model

The project uses a two-tier documentation model:

- **`docs/` directory** — Architecture reference documents describing both the current implementation and planned extensions. Features marked `[PLANNED]` are not yet built. When a planned feature is deployed, update the docs to collapse the current-vs-planned distinction (remove `[PLANNED]` tags, merge diagrams, update status columns). Do not use `docs/` to record decision rationale or alternatives considered.
- **Notion Design Decisions database** — The source of truth for *why* architectural choices were made. Each significant decision is recorded using the ADR format (Title, Status, Context, Decision, Consequences). Search the Notion workspace for "Design Decisions" to find the database, or use the Notion MCP tools.

### Workflow for New Design Decisions

When a significant architectural choice is made or revised during development:

1. **Document the decision in Notion** — Create a new entry in the Design Decisions database (data source ID: `a88ce7c8-1ebb-4634-a422-2c1abcd2daf9`) with fields: Title, Status, Context, Decision, Consequences, Products (link to KEN-E product page).
2. **Update `docs/` files** — Modify the relevant design docs to reflect the new architecture. If the change implements a previously `[PLANNED]` feature, collapse the current-vs-planned distinction: remove `[PLANNED]` tags, merge "current" and "planned" sections/diagrams, and update status columns to "Implemented".
3. **Add a brief Notion reference** — Where the change was made in the docs, add a short inline callout referencing the Notion decision URL so readers can find the rationale. Format: `> **Revised [date]** — [brief description]. See [Decision N: Title](notion-url) for rationale.`
4. **Log the change in DESIGN-REVIEW-LOG.md** — Add an entry documenting what changed in which files, with a reference to the Notion decision.

### When to Create a Design Decision

Create a Notion Design Decision entry when:
- Choosing between multiple valid architectural approaches
- Adopting, replacing, or deprecating a technology or pattern
- Making a deliberate choice to defer or not build something
- Revising a previous architectural decision based on new information

Do NOT create a Design Decision for:
- Bug fixes or implementation details
- Routine code changes that don't affect architecture
- Configuration changes within an existing architectural pattern

### Design Docs in `docs/`

| File | Purpose | Reference when... |
|------|---------|-------------------|
| `docs/KEN-E-Agentic-Harness-Design.md` | Root design document. Agent architecture, context loading, tool discovery, session management, multi-channel support, error handling, security, cost model, workflow management. | Working on any agent system component, understanding overall architecture, or planning new features. |
| `docs/design/mcp-architecture.md` | MCP internals, platform integration decisions, token budget strategy, `tool_filter` architecture, MCPServerManager disposition. | Working on MCP server integration, tool management, or platform connections. |
| `docs/design/agent-hierarchy.md` | Agent tree structure, dispatch pattern, InstructionProvider, ToolRegistry role, agent factory design, review loop & workflow orchestration. | Working on agent routing, adding new specialists, modifying dispatch logic, or implementing review loops. |
| `docs/design/api-gateway-multi-channel.md` | API architecture, channel-agnostic design, planned Slack and Voice channel approaches. | Working on the API layer, adding new channels, or modifying the chat endpoint. |
| `docs/design/DESIGN-REVIEW-LOG.md` | Changelog of design doc revisions with Notion decision references. Tracks what changed, when, and why (via Notion links). | Understanding the history of design changes or adding a new review entry after updating docs. |
| `docs/design/review-loop-implementation-plan.md` | Implementation plan for review loops and workflow orchestration. 13 stories across 5 phases with dependency graph, verification checklist, and risk assessment. | Planning sprints for review loop implementation, creating user stories, or understanding the implementation roadmap. |
| `docs/design/data-visualization.md` | Data visualization & artifacts design — Vega-Lite artifact model, `create_visualization()` tool, ChatResponse extension, review loop integration, frontend rendering, channel considerations. | Working on data visualization, chart rendering, artifact delivery, or extending ChatResponse. |
| `docs/KEN-E-Self-Improving-Evaluation-Framework-Design.md` | MER-E evaluation framework design — scoring, feedback loops, self-improvement. | Working on evaluation, quality metrics, or the MER-E system. 
| `docs/KEN-E_User_Stories.md` | The three guiding user stories that will be enabled by this product. These are used to define the future state of the product and its capabilities. | Understanding the key goals and objectives of this product. |
| `docs/trace-structure-spec.md` | W&B Weave span structure specification — tracing contract between KEN-E and MER-E. | Working on tracing, observability, or the evaluation pipeline. |

## Additional Documentation

For detailed information about:
- **Troubleshooting**: See `TROUBLESHOOTING.md` for historical issues and fixes
- **Deployment**: See deployment files in `deployment/` directory
- **Frontend specifics**: See `frontend/CLAUDE.md` for CSS architecture details