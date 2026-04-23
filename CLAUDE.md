# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

KEN-E is a multi-agent AI system for marketing analysis built on Google Cloud Platform. It uses Google's Agent Development Kit (ADK) deployed on Vertex AI Agent Engine, integrated with a modern React frontend to provide comprehensive marketing insights and analytics.

KEN-E's design is organized around **fourteen components** under [`docs/design/components/`](docs/design/components/): **Agentic Harness** (agent runtime + review loop + factory), **Knowledge Graph** (Neo4j + read tools + learning loop), **Project Tasks** (persistent plans + orchestration), **Automations** (re-executable templates + scheduler), **Dashboards** (canvas of widgets powered by plan artifacts), **Data Pipeline** (deterministic platform-API extraction jobs + sibling Cloud Run service), **Integrations** (OAuth credential substrate for third-party platforms), **SAR-E** (analytical backend — VAR forecasting, KPI ingestion, target derivation), **Performance** (marketing-measurement page that renders SAR-E outputs), **Skills** (user-authored expertise packs), **UI** (design system + React pages), **Data Management** (Shape B Firestore convention), **Billing** (Stripe-backed subscriptions + token meter + monthly enforcement), and **Feature Flags** (targeted rollouts). The cross-component architecture lives in [`docs/KEN-E-System-Architecture.md`](docs/KEN-E-System-Architecture.md).

## Context Loading Sequence

At the start of every new story, PR, or open-ended request, follow this order. This flow is designed to give you system-level orientation in ~5 minutes, then component-specific depth as needed.

### Step 1 — Scope the work

Identify which component(s) the story touches. If unsure, read [`docs/KEN-E-System-Architecture.md`](docs/KEN-E-System-Architecture.md) §1.6 Component Landscape — the authoritative map. Quick-reference:

| Component | Dir | Scope |
|-----------|-----|-------|
| Agentic Harness | `agentic-harness/` | Root agent, narrow specialists, review loop, agent factory, tool assignment, MCP |
| Knowledge Graph | `knowledge-graph/` | Neo4j schema, provenance, orchestrator read tools, session-end learning loop |
| Project Tasks | `project-tasks/` | `ProjectPlan` / `PlanTask`, `TaskOrchestrator`, triggers, calendar |
| Automations | `automations/` | `PlanRun` execution, recurring scheduler, artifacts, Automations UI |
| Dashboards | `dashboards/` | `type='dashboard'` plans, canvas placements, artifact resolver, Performance tab |
| Data Pipeline | `data-pipeline/` | Deterministic platform-API extraction — connectors, jobs, runs, cache; sibling `kene-data-pipeline-{env}` Cloud Run service; `assignee_type="data_pipeline"` task branch |
| Integrations | `integrations/` | OAuth flows per platform, KMS-encrypted token store, per-account connection sharing, re-auth lifecycle, `/settings/integrations` UI |
| SAR-E | `sar-e/` | Weekly KPI time series, VAR baseline forecasts, IRF scenarios, LLM target derivation, analytical query layer (Simulation and Recommendations Engine) |
| Performance | `performance/` | `/performance` page (Analysis / Simulations / Targets / Diagnostics / Configuration tabs + setup wizard), composite BFF endpoints |
| Skills | `skills/` | User-authored + predefined skills, sandbox code execution, authoring UI |
| UI | `ui/` | Soft Maximalism design system, global shell, React pages |
| Data Management | `data-management/` | Shape B Firestore convention, migrations, composite indexes |
| Billing | `billing/` | Stripe-backed subscriptions, 41-stop pricing tier table, internal token meter, org-status state machine, monthly enforcement, sales handoff |
| Feature Flags | `feature-flags/` | Targeted rollouts, kill switches, admin UI + SDKs |

### Step 2 — Orient with the System Architecture

Always read [`docs/KEN-E-System-Architecture.md`](docs/KEN-E-System-Architecture.md) §1 (Executive Summary) + §1.6 (Component Landscape) at the start of a story. It is the canonical high-level map. Scan other sections (§3 Context Management, §8 Multi-Step Orchestration, §10 Infrastructure, §11 Resilience/Security, etc.) only if your work touches those concerns.

### Step 3 — Read the relevant component README(s)

For each component your work touches, read its README at `docs/design/components/<component>/README.md`. Each component README gives: architecture diagram, key abstractions, API contracts, component dependencies, and the PRD index.

### Step 4 — If implementing a specific PRD, read it

If the story maps to a project PRD (e.g., `AH-PRD-02`, `KG-PRD-04`, `PR-PRD-01`), read it at `docs/design/components/<component>/projects/<prd>.md`. Each PRD follows a standard 10-section structure (context, scope, dependencies, data contract, implementation outline, API contract, acceptance criteria, test plan, risks, reference).

### When in doubt — diagnostic triggers

- **You don't understand a requirement** → re-read the component README + System Architecture §1.6 for cross-component context. If the requirement spans components, the System Architecture is where the cross-component story lives.
- **You don't know which component touches your work** → System Architecture §1.6 Component Landscape is the authoritative map.
- **You find a contradiction between docs** → [`docs/design/DESIGN-REVIEW-LOG.md`](docs/design/DESIGN-REVIEW-LOG.md) has the decision history.
- **You need to know what's shipped vs. planned** → project status is in [`docs/design/components/PROJECT-PLANNER.md`](docs/design/components/PROJECT-PLANNER.md); customer-facing release plan is in [`docs/product-roadmap.md`](docs/product-roadmap.md).
- **You hit an ADK- or MCP-specific question** → [`docs/design/components/agentic-harness/mcp-architecture.md`](docs/design/components/agentic-harness/mcp-architecture.md) has verified ADK internals + platform decisions.

## Design Documentation Index

One table, ordered from most general (start here) to most specific (consult for deep dives).

| Document | Read when... |
|----------|--------------|
| **— System-level —** | |
| [`docs/KEN-E-System-Architecture.md`](docs/KEN-E-System-Architecture.md) | Start of every story. Gives the canonical 14-component map + cross-cutting concerns (context management, orchestration, MER-E, infrastructure, resilience/security, feature flags). |
| [`docs/KEN-E_User_Stories.md`](docs/KEN-E_User_Stories.md) | Understanding the three guiding product scenarios. |
| [`docs/design/components/PROJECT-PLANNER.md`](docs/design/components/PROJECT-PLANNER.md) | Project sequencing across all components — what's blocked by what, what's ready to start, what release each targets. |
| [`docs/product-roadmap.md`](docs/product-roadmap.md) | Customer-facing release plan (1.1 → 6.0) with design-ref blockquotes into component docs. |
| **— Component READMEs —** | |
| [`docs/design/components/agentic-harness/README.md`](docs/design/components/agentic-harness/README.md) | Working on the agent runtime — root agent, specialists, review loop, agent factory, tool assignment, MCP. |
| [`docs/design/components/knowledge-graph/README.md`](docs/design/components/knowledge-graph/README.md) | Working on Neo4j, orchestrator read tools, session-end automation, or research-on-creation. |
| [`docs/design/components/project-tasks/README.md`](docs/design/components/project-tasks/README.md) | Working on project plans, the calendar UI, task orchestration, or the time-based scheduler. |
| [`docs/design/components/automations/README.md`](docs/design/components/automations/README.md) | Working on recurring automations, `PlanRun`, the artifact system, test-run mode, or the Automations UI. |
| [`docs/design/components/dashboards/README.md`](docs/design/components/dashboards/README.md) | Working on dashboards — canvas placements, widget renderers, the artifact resolver, or the Performance-page Dashboards tab. |
| [`docs/design/components/data-pipeline/README.md`](docs/design/components/data-pipeline/README.md) | Working on deterministic platform-API extraction — connectors, jobs, runs, cache, the sibling `kene-data-pipeline-{env}` Cloud Run service, or task-system integration (`assignee_type="data_pipeline"`). |
| [`docs/design/components/integrations/README.md`](docs/design/components/integrations/README.md) | Working on OAuth flows, the encrypted token store, per-account connection sharing, re-auth notifications, or the `/settings/integrations` UI. |
| [`docs/design/components/sar-e/README.md`](docs/design/components/sar-e/README.md) | Working on weekly KPI ingestion, VAR baselines, IRF scenarios, LLM target derivation, or any analytical query the Performance page renders. |
| [`docs/design/components/performance/README.md`](docs/design/components/performance/README.md) | Working on the `/performance` page — five tab surfaces, the setup wizard, BFF endpoints, or the Goal→Target terminology rename. |
| [`docs/design/components/skills/README.md`](docs/design/components/skills/README.md) | Working on skill authoring, attachment, sandbox code execution, or the Skills UI. |
| [`docs/design/components/ui/README.md`](docs/design/components/ui/README.md) | Working on any React page or the design system (Soft Maximalism). |
| [`docs/design/components/data-management/README.md`](docs/design/components/data-management/README.md) | Working on Firestore layout, migrations, composite indexes, or account-deletion cleanup. |
| [`docs/design/components/billing/README.md`](docs/design/components/billing/README.md) | Working on subscriptions, the token meter, monthly enforcement, the Subscription tab, the inactive banner, Stripe webhooks, manual override, or the sales-handoff flow. |
| [`docs/design/components/feature-flags/README.md`](docs/design/components/feature-flags/README.md) | Working on a targeted rollout or kill-switching a feature. |
| **— Specialist deep-dives —** | |
| [`docs/design/components/agentic-harness/mcp-architecture.md`](docs/design/components/agentic-harness/mcp-architecture.md) | ADK MCP internals, platform integration decisions, Firestore config schema, MCPServerManager disposition. |
| [`docs/design/components/agentic-harness/data-visualization.md`](docs/design/components/agentic-harness/data-visualization.md) | Vega-Lite artifacts, `create_visualization()` tool, chart rendering, channel considerations. |
| [`docs/design/components/backlog/api-gateway-multi-channel.md`](docs/design/components/backlog/api-gateway-multi-channel.md) | API architecture, channel-agnostic design, planned Slack/Voice approaches. (In backlog.) |
| [`docs/design/review-loop-implementation-plan.md`](docs/design/review-loop-implementation-plan.md) | Review loop phases, ADK patterns, cost analysis, multi-step workflow pattern. |
| [`docs/KEN-E-Self-Improving-Evaluation-Framework-Design.md`](docs/KEN-E-Self-Improving-Evaluation-Framework-Design.md) | MER-E evaluation framework — scoring, feedback, self-improvement. |
| [`docs/trace-structure-spec.md`](docs/trace-structure-spec.md) | W&B Weave span structure specification — tracing contract between KEN-E and MER-E. |
| [`docs/design/DESIGN-REVIEW-LOG.md`](docs/design/DESIGN-REVIEW-LOG.md) | History of design-doc revisions and architecture decisions. |
| **— Spikes & strategy —** | |
| [`docs/Release-1-Optimization-Strategy.md`](docs/Release-1-Optimization-Strategy.md) | Release 1 optimization targets. |
| [`docs/spike-adk-reasoning-capture.md`](docs/spike-adk-reasoning-capture.md) | ADK reasoning-capture spike. |
| [`docs/spike-otel-pydantic-findings.md`](docs/spike-otel-pydantic-findings.md) | OTEL and Pydantic findings. |

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

## Common Issues & Solutions

1. **Port Conflicts**: Frontend runs on 8080, API on 8000
2. **Database Connections**: Ensure Neo4j and Firestore credentials are set
3. **Build Errors**: Check all environment variables are configured
4. **Type Errors**: TypeScript strict mode is OFF in frontend (see `frontend/tsconfig.app.json`)
5. **API Server Reload Loop**:
   - Use `uv run` WITHOUT the `--active` flag (recommended)
   - Alternative: `cd api && python -m uvicorn src.kene_api.main:app --reload`
6. **Invitation Emails Not Sending**: See `api/CLAUDE.md` Email Service Setup section

## Documentation Model

Architecture reference documents live in the [`docs/`](docs/) directory — both current implementation and planned extensions. Features marked `[PLANNED]` are not yet built. When a planned feature ships, collapse the current-vs-planned distinction in its doc: remove `[PLANNED]` tags, merge "current" and "planned" sections/diagrams, update status columns to "Implemented."

Significant architectural changes are logged in [`docs/design/DESIGN-REVIEW-LOG.md`](docs/design/DESIGN-REVIEW-LOG.md) with the date, scope, list of affected files, and rationale. Add a new review entry at the top of that log whenever a design-doc change is non-trivial (structural reorganization, retired mechanism, new cross-component coupling, etc.).

## Additional Documentation

- **Component-level design**: See [`docs/design/components/`](docs/design/components/) — the landing directory for all fourteen components. Each has a `README.md` and a `projects/` subdirectory with project PRDs.
- **API specifics**: See `api/CLAUDE.md` for architecture patterns, email setup, and endpoints.
- **Frontend specifics**: See `frontend/CLAUDE.md` for CSS architecture and component library.
- **Code review rules**: See `REVIEW.md` for the review checklist.
- **Design documents**: See [`docs/`](docs/) and the Design Documentation Index near the top of this file.
- **Deployment**: See deployment files in the `deployment/` directory.
