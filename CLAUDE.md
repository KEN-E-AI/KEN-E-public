# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

KEN-E is a multi-agent AI system for marketing analysis built on Google Cloud Platform. It uses Google's Agent Development Kit (ADK) deployed on Vertex AI Agent Engine, integrated with a modern React frontend to provide comprehensive marketing insights and analytics.

## Project Structure

```
ken-e/
├── app/                    # ADK agent system
│   ├── adk/               # Agent Development Kit implementation
│   │   ├── agents/        # Agent definitions and strategy logic
│   │   ├── tools/         # Tool discovery and registry
│   │   ├── security/      # Authentication and authorization
│   │   ├── session/       # Session management
│   │   ├── mcp_config/    # MCP server configuration
│   │   └── tracking/      # Observability and tracing
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

- **Agent System** (`app/adk/`): ADK agent system on Vertex AI Agent Engine
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

### 7 — Git

- **GH-1 (MUST)** Use Conventional Commits format when writing commit messages: https://www.conventionalcommits.org/en/v1.0.0
- **GH-2 (SHOULD NOT)** Refer to Claude or Anthropic in commit messages.
- **GH-3 (SHOULD)** Branch naming: `feat/`, `fix/`, `docs/`, `chore/`, `test/`, `refactor/` + kebab-case description.

---

### 8 — Skills

| Skill | Purpose |
|-------|---------|
| `/qstart` | Understand best practices, validate plan, implement with verification |
| `/qreview` | Skeptical code review: functions, tests, UX, best practices |
| `/qgit` | Stage, commit (Conventional Commits), and push |
| `/start-session` | Start a development session for a user story |
| `/run-tests` | Run test phase for a user story |
| `/end-session` | Close session, update logs, commit, push, PR check |

---

## Design Documents

| Document | Topic |
|----------|-------|
| `docs/KEN-E-Agentic-Harness-Design.md` | Agentic harness architecture and design |
| `docs/trace-structure-spec.md` | Trace structure specification |
| `docs/KEN-E-Self-Improving-Evaluation-Framework-Design.md` | Self-improving evaluation framework |
| `docs/Release-1-Optimization-Strategy.md` | Release 1 optimization strategy |
| `docs/spike-adk-reasoning-capture.md` | ADK reasoning capture spike |
| `docs/spike-otel-pydantic-findings.md` | OTEL and Pydantic findings spike |

## Common Issues & Solutions

1. **Port Conflicts**: Frontend runs on 8080, API on 8000
2. **Database Connections**: Ensure Neo4j and Firestore credentials are set
3. **Build Errors**: Check all environment variables are configured
4. **Type Errors**: TypeScript strict mode is OFF in frontend (see `frontend/tsconfig.app.json`)
5. **API Server Reload Loop**:
   - Use `uv run` WITHOUT the `--active` flag (recommended)
   - Alternative: `cd api && python -m uvicorn src.kene_api.main:app --reload`
6. **Invitation Emails Not Sending**: See `api/CLAUDE.md` Email Service Setup section

## Additional Documentation

- **API specifics**: See `api/CLAUDE.md` for architecture patterns, email setup, and endpoints
- **Frontend specifics**: See `frontend/CLAUDE.md` for CSS architecture and component library
- **Code review rules**: See `REVIEW.md` for review checklist
- **Design documents**: See `docs/` directory (indexed above)
- **Deployment**: See deployment files in `deployment/` directory
