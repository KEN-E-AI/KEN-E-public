# Agentic Harness — Product Requirements Document

> **Linear Team:** [KEN-E] Agentic Harness
> **Last Updated:** 2026-04-20
> **Status:** Active

## 1. Overview

The Agentic Harness is the core agent framework that makes KEN-E work — the root agent, the specialist layer below it, the dispatch pattern that routes work to specialists, the review-loop quality gate wrapped around every specialist call, and the config-driven factory that assembles the whole hierarchy at deploy time. Every user chat turn flows through this component: the root agent reads the user's message, decides which specialist can answer, generates acceptance criteria, dispatches to the specialist inside a review pipeline, and returns the approved draft.

The component owns three architectural pillars. **The review loop framework** (Generator–Critic pattern via ADK `LoopAgent`) wraps every specialist delegation in a verify-before-return iteration cycle, preventing the root agent from relaying unreviewed drafts to the user. **The agent factory** reads Firestore `agent_configs/{config_id}` and `mcp_servers/{server_id}` documents at deploy time and assembles the full hierarchy — `LlmAgent` instances with correct model, instruction, `McpToolset`s, OAuth header providers, curated ≤30-tool rosters per specialist, and auto-generated `dispatch_to_{specialist}()` functions on the root. **Narrow specialists** (the first being Google Analytics) are the domain agents that actually call MCP/SDK tools and run code execution on the user's data; they are the terminal leaves that the review loop wraps and the factory constructs.

After this component's Release 1 projects complete, adding a new specialist is a Firestore config change rather than a code change, every specialist delegation gets a quality gate for free, and every account can customize its agents without affecting other accounts. This platform is what the Skills, Project Tasks, and Knowledge Graph components build on — they all run on agents assembled by the factory, with review loops wrapping their dispatches.

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Frontend chat                                                              │
│    POST /api/v1/accounts/{account_id}/chat                                  │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│  Root Agent (ken_e)                                                         │
│    ├── InstructionProvider (closure reading session state)                  │
│    ├── Tools: auto-generated dispatch functions                             │
│    │     search_company_news(query, acceptance_criteria, tool_context)      │
│    │     query_google_analytics(query, acceptance_criteria, tool_context)   │
│    │     … N more per the factory                                           │
│    └── Callbacks: Weave tracing + ADK before/after hooks                    │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ dispatch_to_{specialist}()
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Dispatch handler                                                           │
│    @safe_weave_op()                                                         │
│    if acceptance_criteria:                                                  │
│      pipeline = build_review_pipeline(specialist, criteria, prefix)         │
│      run pipeline → approved draft                                          │
│    else:                                                                    │
│      invoke_agent_sync(specialist)     (single-pass legacy path)            │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────────┐
│  Review pipeline (LoopAgent, max_iterations=3)                              │
│    ├── specialist (LlmAgent, output_key="{prefix}_draft")                   │
│    │     instruction: task + criteria + {prefix}_feedback?                  │
│    │     tools: McpToolset(s) + function tools + code_execution             │
│    └── reviewer (LlmAgent, gemini-2.0-flash, include_contents='none')       │
│          instruction: evaluate {prefix}_draft vs criteria                   │
│          tools: [exit_loop]                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

                            Agent Factory (deploy-time)

┌─────────────────────────────────────────────────────────────────────────────┐
│  Firestore                                                                  │
│    agent_configs/{config_id}            (global, per-specialist)            │
│    mcp_servers/{server_id}              (global, with specialist_categories)│
│    accounts/{account_id}/agent_configs/{config_id}   (per-account overlay + │
│                                                       custom agents)        │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼
                         agent_factory.build_hierarchy(account_id=None)
                                   │
                                   ├── load global configs
                                   ├── shallow-merge per-account overlays
                                   ├── create McpToolset per server
                                   │     header_provider=_make_header_provider(auth_type)
                                   ├── resolve each specialist's tool roster (≤30 tools, curated)
                                   ├── create LlmAgent per config
                                   ├── generate dispatch_to_{name}() per specialist
                                   │     (each calls build_review_pipeline when criteria present)
                                   └── return root agent with all dispatches wired

  Root agent routes via specialist descriptions (read from each agent_config);
  specialists see a fixed ≤30-tool list — no per-turn tool_filter.
  (See §2.5 Tool-assignment & routing model.)
```

### 2.1 Key Directories

| Path | Purpose |
|------|---------|
| `app/adk/agents/ken_e_agent.py` | Root agent definition + InstructionProvider + tool wrappers. Updated by AH-PRD-01 (adds `acceptance_criteria` parameter) and by AH-PRD-03 (GA tool wrapper dispatches to factory-generated function). |
| `app/adk/agents/utils/review_pipeline.py` | `build_review_pipeline()` factory + `extract_pipeline_result()`. Created by AH-PRD-01. |
| `app/adk/agents/utils/dispatch_handlers.py` | Dispatch functions. Updated by AH-PRD-01 (adds `acceptance_criteria` parameter). AH-PRD-02 adds the auto-generated `dispatch_to_{name}()` variants alongside legacy ones. |
| `app/adk/agents/utils/supervisor_utils.py` | `invoke_agent_sync()` + pipeline-result extraction. Updated by AH-PRD-01. |
| `app/adk/agents/agent_factory/` | Config-driven assembly: `build_hierarchy()`, `build_agent()`, config loader with overlay merge, MCP toolset creation, header provider factory, dispatch generator. Created by AH-PRD-02. |
| `app/adk/agents/registry.py` | Existing lazy-loading registry + capability search. Preserved; factory populates it. |
| `app/adk/agents/google_analytics_agent_v4.py` | Transitional (R1.0) hand-wired GA agent. Marked deprecated by AH-PRD-03; removed in a follow-up once no callers remain. |
| `app/adk/agents/company_news_chatbot/agent.py` | Transitional news agent. Wraps well inside a review loop; remains as a transitional agent until a long-term replacement is scoped. |
| `app/adk/agents/create_strategy_docs_supervisor.py` | Strategy document supervisor. Separate entry point — not dispatched from root; not part of the narrow-specialist path. **Long-term disposition TBD** — KG-PRD-05 refactors only the four downstream graph builders the supervisor invokes (write path → `GraphSyncService`); the supervisor itself is not factory-migrated and remains a parallel Agent Engine entry point. A future PRD will scope its replacement once the planning specialist (PR-PRD-02) and KG learning loop (KG-PRD-04) prove out the post-strategy-supervisor flow. |
| `app/adk/tools/registry/tool_registry.py` | ToolRegistry — **build-time metadata catalog** the factory reads to assemble specialist rosters. Not a runtime routing index; root-agent routing is specialist-description-based. See §2.5. |
| `api/src/kene_api/routers/agent_configs.py` | `/api/v1/accounts/{account_id}/agent-configs/` CRUD. Created by AH-PRD-02. |
| `frontend/src/app/pages/workflows/agents/` | Workflows > Agents list, detail/customization, AgentCreatePage. Created by AH-PRD-02. |
| `deploy_ken_e.py` | Agent Engine deploy entry point. Switched from hardcoded imports to `agent_factory.build_hierarchy()` by AH-PRD-02. |

### 2.2 Data Flow

1. **Deploy-time hierarchy build (AH-PRD-02):** `deploy_ken_e.py` calls `agent_factory.build_hierarchy()`. The factory reads `agent_configs/*` and `mcp_servers/*` from Firestore, applies any per-account overlay for the deploying account (default: no overlay — global config only), creates `McpToolset` instances with OAuth header providers, resolves each specialist's curated tool roster (≤30 tools, per §2.5) using the ToolRegistry metadata catalog, and generates `dispatch_to_{specialist}()` functions on the root. The root agent is handed to Agent Engine as usual.
2. **Per-turn dispatch (AH-PRD-01 + AH-PRD-02):** A user message hits the root agent. The root picks a specialist by LLM reasoning over each specialist's description (sourced from `agent_configs/{id}.description`), generates 2–4 measurable acceptance criteria, and calls the dispatch tool function with `query` + `acceptance_criteria`. The dispatch handler wraps the specialist in a review pipeline via `build_review_pipeline(specialist, acceptance_criteria, output_key_prefix)`.
3. **Review-loop iteration:** The specialist drafts a response using its (fixed) tool roster. The reviewer (`gemini-2.0-flash`, `include_contents='none'`) reads the draft and acceptance criteria, calls `exit_loop` if all criteria are met, or writes feedback to `{prefix}_feedback` for the next iteration. Max iterations = 3 by default.
4. **Multi-tenant config overlay (AH-PRD-02):** An account admin can customize a specialist's instruction, model, or temperature by writing to `accounts/{account_id}/agent_configs/{config_id}`. The config loader shallow-merges the overlay onto the global config. Admins can also create fully custom agents (`custom_*` prefixed `config_id`) scoped to their account only.
5. **Tracing:** Every dispatch is wrapped in `@safe_weave_op()`. Review-loop iterations appear as sub-spans; acceptance criteria live in the pipeline span's attributes; exit condition (approved vs. max_iterations) is captured. MER-E consumes these spans for quality scoring.

### 2.3 API Contracts

Owned endpoints (AH-PRD-02):

| Endpoint | Method | Owner | Schema |
|----------|--------|-------|--------|
| `/api/v1/accounts/{account_id}/agent-configs/` | GET | AH-PRD-02 | List merged configs (global + overlay + custom), filtered by `visible_in_frontend` |
| `/api/v1/accounts/{account_id}/agent-configs/{config_id}` | GET | AH-PRD-02 | `MergedAgentConfig` (global + overlay merged) |
| `/api/v1/accounts/{account_id}/agent-configs/` | POST | AH-PRD-02 | Create custom agent (`custom_` prefix applied server-side) |
| `/api/v1/accounts/{account_id}/agent-configs/{config_id}` | PUT | AH-PRD-02 | Upsert overlay — stores only changed fields, with `based_on_version` tracking |
| `/api/v1/accounts/{account_id}/agent-configs/{config_id}` | DELETE | AH-PRD-02 | Revert overlay (for non-custom); full delete (for `custom_*`) |

Schema source of truth: `api/src/kene_api/models/agent_config_models.py` (Pydantic), mirrored in `frontend/src/app/lib/api/agentConfigs.ts` as TypeScript branded `AgentConfigId`. URL paths use kebab-case (`agent-configs`); Firestore collection uses snake_case (`agent_configs`).

This component does **not** own the chat endpoint or the session-management API — those live in `api/src/kene_api/routers/chat.py` and `api/src/kene_api/services/session_service.py` respectively. The harness consumes the session via `tool_context.state`.

### 2.4 Key Abstractions

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `build_review_pipeline(specialist, criteria, prefix, max_iterations)` | `app/adk/agents/utils/review_pipeline.py` | Factory producing a `LoopAgent` with specialist + reviewer as direct sub-agents. No `SequentialAgent` wrapper (would swallow `escalate`). Reviewer is `gemini-2.0-flash` with `include_contents='none'`. (AH-PRD-01) |
| `agent_factory.build_hierarchy(account_id=None)` | `app/adk/agents/agent_factory/__init__.py` | Deploy-time assembly: reads Firestore, applies overlay, creates specialists + MCP toolsets + dispatch functions, returns root agent. (AH-PRD-02) |
| `_make_header_provider(auth_type)` | `app/adk/agents/agent_factory/header_provider.py` | Closure factory mapping `ga_oauth` / `google_ads_oauth` / `meta_ads_oauth` / `mailchimp_oauth` → session-state credential key → HTTP headers. Fail-fast on unknown `auth_type`. (AH-PRD-02 §5.3) |
| `MergedAgentConfig` | `api/src/kene_api/models/agent_config_models.py` | Pydantic view over global + overlay, with a `customization_status: "default" \| "customized" \| "custom_agent"` discriminator and `based_on_version` for customized/custom. (AH-PRD-02) |
| `InstructionProvider` (existing) | `app/adk/agents/ken_e_agent.py` | Closure-based dynamic instruction injection reading `organization_context` from session state. Preserved; factory wraps every specialist with it. |
| `ToolRegistry` (existing) | `app/adk/tools/registry/tool_registry.py` | **Build-time metadata catalog** the factory reads to assemble each specialist's ≤30-tool roster. Not a runtime router; root-agent routing is specialist-description-based (see §2.5). Also consumed by admin UI + docs. |
| `@safe_weave_op()` (existing) | `app/adk/tracking/` | Decorator on every dispatch function; preserved in factory-generated dispatches. |

### 2.5 Tool-assignment & routing model

> **Reference:** the move away from the per-turn `tool_filter` mechanism is captured in [Review 9 in DESIGN-REVIEW-LOG](../../DESIGN-REVIEW-LOG.md#review-9-experiment-4--tool_filter-integration-pattern-resolution) (originally Notion User Story 2.2.4 — historical archive). The specialist-description routing below is a refinement: scope-ambiguity (two specialists sharing a tool) is resolved at the specialist level, not via a tool-level index.

Two concerns, two mechanisms:

#### Tool assignment (specialist → tools)

Each specialist receives a **fixed curated tool roster of ≤30 tools** at construction time, resolved from its `mcp_servers` references plus any function tools (e.g., `create_visualization`, Gemini code execution). There is **no per-turn `tool_filter`**. A previous design iteration wired `ToolRegistry.search()` into each specialist's `before_agent_callback` and used `tool_filter_state` + `McpToolset.tool_filter` lambdas to whittle ~30 tools down to ~5–10 per turn. That mechanism is retired:

- **The 30-tool cap is the scope discipline.** If a specialist needs more than 30 tools, it's too broad and should be split (motivating the narrow-per-platform roadmap in §2.6).
- **The ToolRegistry is a build-time metadata catalog**, not a runtime filter. The factory reads it to construct each specialist's roster. Admin UI and docs also consume it.
- **Factory implication:** No `tool_filter_callback.py`. Specialists are constructed with a final tool list; the factory validates the list is ≤30 and fails at build time otherwise.

#### Routing (root agent → specialist)

The root agent picks a specialist by **LLM reasoning over specialist descriptions** — not by tool-index lookup. Each `agent_configs/{id}` document carries a `description` field that answers "what does this specialist do, and when should the root pick it?" The root's system instruction lists all active specialists (name + description) and the dispatch tool functions the factory generated. Standard LLM tool-calling handles the selection.

Why description-based, not tool-index-based:

- **Shared tools don't imply shared scope.** Two narrow specialists may legitimately carry the same tool — e.g., a future Google Ads Specialist and a future Mailchimp Specialist might both carry a generic `create_visualization()` tool, and a Google Ads Specialist and a Meta Ads Specialist might both expose campaign-level metric reads even though they target different platforms. A tool-level router would be ambiguous in those cases — a description-level router isn't, because scope ("Google Ads optimization" vs. "Mailchimp campaign management") lives naturally at the specialist level.
- **Narrow specialists are few and distinct.** With ~5–10 specialists each sized at ~5–15 tools, specialist descriptions fit comfortably in the root's context and are easier for the LLM to reason over than a tool search.
- **The specialist's tool roster stays an implementation detail.** Callers don't need to know; routing stays stable even when a specialist's tools change.

**Factory implication:** the dispatch-function generator (`dispatch.py`) emits one `dispatch_to_{name}()` per specialist. The root's instruction (built at factory time) includes a "Available specialists" section sourced from each `agent_configs/{id}.description`.

#### Downstream consequences

- **AH-PRD-02** builds the curated rosters; AC #5 is the ≤30-tool cap, not per-turn filtering. The description-based routing is assembled by the dispatch generator.
- **Skills (SK-PRD-02)** attach via `skill_ids` → `SkillToolset` → counted against the specialist's 30-tool cap.
- **New specialists** in §2.6 are sized at ~5–15 tools each, well under the cap, with descriptions crafted for routing.

### 2.6 Specialist roadmap

The specialist catalog is narrow per-platform, not broad per-capability. Release 1 ships one specialist (Google Analytics, AH-PRD-03) through the factory. Release 5 adds additional narrow specialists — each a separate Firestore `agent_configs/*` document + optional `mcp_servers/*` registration, following the pattern established in AH-PRD-03.

| Specialist | Platform | Release | Status |
|------------|----------|---------|--------|
| Google Analytics | GA4 MCP | R1 | [AH-PRD-03](./projects/AH-PRD-03-google-analytics-specialist.md) |
| Google Ads | Google Ads MCP/SDK | R5 | Not yet scoped |
| Meta Ads | Meta Ads (facebook-business) SDK | R5 | Not yet scoped |
| Mailchimp | Mailchimp SDK | R5 | Not yet scoped |

**Not planned:** The broad "Content Specialist," "Execution Specialist," and "Automation Specialist" rolls-ups that appeared in earlier design drafts are superseded by this narrow-per-platform model. A narrow specialist has a sharper scope (fewer tools, clearer instruction, cleaner review criteria) and stays well under the ≤30-tool cap in §2.5.

Transitional agents (`google_analytics_agent_v4.py`, `company_news_chatbot/agent.py`) remain in place until a narrow specialist supersedes them; see §2.1 Key Directories.

## 3. Component Dependencies

### 3.1 Depends On

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[Data Management — DM-PRD-00 (Migration Foundation)](../data-management/projects/DM-PRD-00-migration-foundation.md)** | **Hard prerequisite for AH-PRD-02.** Documents the Shape B convention in `api/CLAUDE.md` and ships `seed_shape_b_fixtures.py`. AH-PRD-02 is the first feature to land directly on Shape B via the per-account overlay at `accounts/{account_id}/agent_configs/{config_id}` — no legacy Shape A intermediate step. | `../data-management/README.md` §2.2 |
| **[Data Management — DM-PRD-05 (Deletion Sweep Rewrite)](../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md)** | **Soft prerequisite — recommended before AH-PRD-02 ships.** Replaces the enumerated deletion sweep with `firestore.recursive_delete(accounts/{account_id})`, which automatically covers the new `accounts/{account_id}/agent_configs/*` subcollection. AH-PRD-02 includes an interim extension to the enumerated sweep as a bridge if DM-PRD-05 has not shipped yet (see AH-PRD-02 §9 risk + AC #15). | `../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md` |
| Existing Firestore config pattern | Current per-agent `load_config_from_firestore(config_doc_id)` pattern in `app/adk/agents/ken_e_agent.py`, `google_analytics_agent_v4.py`, and the strategy supervisor. AH-PRD-02 generalizes it. | AH-PRD-02 §5.2 (config-to-constructor mapping) |
| Existing `ToolRegistry` | Build-time metadata catalog the factory reads to assemble specialist rosters (§2.5). Already operational — no changes required. | [Review 22 in DESIGN-REVIEW-LOG](../../DESIGN-REVIEW-LOG.md#review-22-backfill--decisions-7--8-token-budget-strategy--toolregistry-as-build-time-catalog) |
| Existing MCP servers | Referenced by `mcp_servers/{server_id}` Firestore docs. This component does not build or host MCP servers. | `app/adk/mcp_config/config/mcp_servers.yaml` (seed) |
| Gemini code execution (for AH-PRD-03) | Built-in via `Tool(code_execution=ToolCodeExecution())`. Google-managed sandbox — no infrastructure. | AH-PRD-03 §2 Phase 2 (code execution) |
| W&B Weave tracing | Every dispatch + review-loop iteration emits spans per `docs/trace-structure-spec.md`. MER-E consumes them. | `../../../trace-structure-spec.md` |
| Account / Auth | Account-admin authorization on `/api/v1/accounts/{account_id}/agent-configs/*`. Reuses the existing `has_account_access` + role check pattern. | `api/src/kene_api/auth/` |

### 3.2 Depended On By

| Component | Dependency |
|-----------|------------|
| **[Skills](../skills/README.md)** | SK-PRD-02 adds `SkillToolset` + sandbox `code_executor` wiring into the factory. SK-PRD-04 replaces the disabled placeholder rows ("Skills", "Sandbox code execution") that AH-PRD-02's AgentEditView + AgentCreatePage reserve, and adds attach-time validation on `PUT /agent-configs`. |
| **[Project Tasks](../project-tasks/README.md)** | PR-PRD-02 (Planning Agent & Tools) writes a Firestore `agent_configs/project_planning` document and the agent factory from AH-PRD-02 assembles the `LlmAgent`. The factory's auto-generated `dispatch_to_project_planning()` replaces any hand-written dispatch. |
| **[Knowledge Graph](../knowledge-graph/README.md)** | KG-PRD-05 (Research-on-Creation Refactor) refactors strategy-agent research builders to use `GraphSyncService`; those builders still run inside the review-loop dispatch owned here. KG-PRD-03's ADK read tools are registered with the ToolRegistry that the harness consumes. |
| **[Automations](../automations/README.md)** | Consumes factory-assembled agents indirectly — the orchestrator calls `AgentEngineClient` which invokes whatever hierarchy `deploy_ken_e.py` built. No direct integration; transitive only. |
| Future narrow-specialist sprints | Google Ads, Meta Ads, Mailchimp (R5, planned per §2.6) — each is a Firestore `agent_configs/*` document and optional `mcp_servers/*` registration. The pattern established in AH-PRD-03 is the template; AH-PRD-04 ensures every new specialist automatically receives `create_visualization()` via the factory's default function-tool roster. |

## 4. Design System References

| Document | Sections | When to Read |
|----------|----------|--------------|
| Figma: KEN-E UI V2 — Soft Maximalism | Workflows > Agents list, Agent detail/edit view, AgentCreatePage | When implementing AH-PRD-02 Phase 3 (admin UI). Same Workflows layout as Automations and Skills tabs. |
| `frontend/CLAUDE.md` | CSS architecture, shadcn/ui component library, branded types | Before adding any new React component. |
| `frontend/src/app/pages/workflows/WorkflowsLayout.tsx` (introduced by AH-PRD-02) | Tab structure shared with Automations, Skills | Adding subsequent tabs (Automations / Skills) must match the pattern established here. |

## 5. Project Index

The component's work is split across **6 project PRDs** under [`projects/`](./projects/). The first three (AH-PRD-01 → AH-PRD-02 → AH-PRD-03) form a strictly serial Release 1 chain because each layer is a prerequisite for the next. AH-PRD-04 (Data Visualization) and AH-PRD-05 (Multi-Step Workflow Orchestration) both land in Release 3 / Expertise and sit on top of the R1 trio — AH-PRD-04 adds chart-artifact output, AH-PRD-05 adds the multi-step workflow primitive (`build_workflow_pipeline` + `execute_workflow` + approval-via-conversation-turns) deferred from AH-PRD-01 §2. AH-PRD-06 (Per-Agent Tool Mapping) layers individual-tool selection onto the agent factory built by AH-PRD-02, replacing today's coarse server-level attachment. Future per-platform specialist PRDs (Google Ads, Meta Ads, Mailchimp — see §2.6) land as AH-PRD-07+, consuming the pattern established in AH-PRD-03 and automatically inheriting `create_visualization()` via the factory's default function-tool roster (see AH-PRD-04).

### 5.1 Dependency graph

```
DM-PRD-00 (Migration Foundation) ──┐
                                    │
                                    ▼
AH-PRD-01 (Review Loop) ──────────► AH-PRD-02 (Agent Factory) ─────► AH-PRD-03 (GA Specialist) ─────► AH-PRD-04 (Data Visualization) ─────► AH-PRD-05 (Multi-Step Workflows)
                                         │   ▲
                                         │   │
                                         │   (soft) DM-PRD-05 (Deletion Sweep Rewrite)
                                         │
                                         └─► AH-PRD-06 (Per-Agent Tool Mapping)
```

### 5.2 Projects

| # | Project PRD | Owner team | Blocked by | Parallel with | Est. |
|---|-------------|------------|------------|---------------|------|
| 01 | [Review Loop Framework](./projects/AH-PRD-01-review-loop-framework.md) | Core AI | — | DM-PRD-00–04 | 2–3 days |
| 02 | [Agent Factory](./projects/AH-PRD-02-agent-factory.md) | Core AI (backend + frontend) | AH-PRD-01, DM-PRD-00 | Data-migration projects | ~8–11 days |
| 03 | [Google Analytics Specialist](./projects/AH-PRD-03-google-analytics-specialist.md) | Core AI | AH-PRD-01, AH-PRD-02 | Data-migration projects, SK-PRDs | 5–7 days |
| 04 | [Data Visualization](./projects/AH-PRD-04-data-visualization.md) | Core AI (backend + frontend) | AH-PRD-01, AH-PRD-02, AH-PRD-03 | UI-PRD-01/02, KG / PR / Automations projects | 5–7 days |
| 05 | [Multi-Step Workflow Orchestration](./projects/AH-PRD-05-multi-step-workflows.md) | Core AI | AH-PRD-01, AH-PRD-02, AH-PRD-03, AH-PRD-04 | KG-PRDs, SK-PRDs, Performance / SAR-E projects | 3–5 days |
| 06 | [Per-Agent Tool Mapping](./projects/AH-PRD-06-tool-mapping.md) | Core AI (backend + frontend) | AH-PRD-02 | SK-PRD-02 / SK-PRD-04 (shared form rows + ≤30-tool cap) | 5–7 days |

### 5.3 Cross-PRD coordination points

Three touchpoints do not fit cleanly inside one PRD and need an owning team to consciously sync:

- **Dispatch generator consuming review-loop factory (AH-PRD-01 ↔ AH-PRD-02):** Story 2.2-5 imports `build_review_pipeline` from AH-PRD-01. If AH-PRD-01 reshapes the signature, AH-PRD-02 must follow. Agree on the signature in AH-PRD-01 code review; lock it before AH-PRD-02 starts.
- **AgentCreatePage placeholder rows (AH-PRD-02 ↔ SK-PRD-04):** AH-PRD-02 delivers `AgentEditView` and `AgentCreatePage` with two disabled rows ("Skills" and "Sandbox code execution") and a tooltip pointing at Feature 2.6. SK-PRD-04 swaps them for interactive controls. Both teams should review each other's designs before either ships; both cite `docs/design/components/skills/skills-implementation-plan.md` §7.
- **Per-account agent-config deletion (AH-PRD-02 ↔ DM-PRD-05):** AH-PRD-02 introduces `accounts/{account_id}/agent_configs/*`. Until DM-PRD-05 ships `recursive_delete`, AH-PRD-02 includes an interim extension to the enumerated sweep (AH-PRD-02 AC #15). When DM-PRD-05 lands, the extension is removed in its final PR. Coordinate the removal with the DM team.
- **Tool picker vs. Skills rows (AH-PRD-06 ↔ SK-PRD-04):** AH-PRD-06's `AgentToolPicker` lands in `AgentCreatePage` and `AgentEditView` between the existing form fields and the two disabled "Skills" / "Sandbox code execution" placeholder rows. SK-PRD-04 swaps the disabled rows for interactive controls and the combined `tool_ids` + `skill_ids` count is gated by the same `MAX_TOOLS_PER_SPECIALIST` cap. Both PRDs reference the cap; if they ship in the same release window, the Create/Update validator must check the combined length, not either field alone.

### 5.4 Recommended workflow

1. **Day 1:** Core AI kicks off AH-PRD-01 (no blockers). DM-PRD-00 should already be merged or very close to merging (the `accounts/{account_id}/agent_configs/` subcollection pattern relies on the Shape B convention being documented).
2. **Day ~3 (AH-PRD-01 merged):** AH-PRD-02 kickoff. Backend and frontend can parallelize once the Phase 1 config loader lands — Phase 2 (backend-heavy: MCP + dispatch generation) and Phase 3 (frontend-heavy: UI + API) are largely independent once the Pydantic contract is published.
3. **Day ~11 (AH-PRD-02 merged):** AH-PRD-03 kickoff. Small project; mostly config + tests. Deprecation banner on `google_analytics_agent_v4.py`; full removal is a follow-up once no callers remain.
4. **Release 1 exit:** Review loop, factory, and first specialist all working in staging. MER-E consuming Weave spans. Ready for downstream components (Skills, Project Tasks, KG-PRD-05) to pick up.
5. **Release 3 (Expertise):** AH-PRD-04 kickoff once AH-PRD-03 is in staging. Phase 1 (Pydantic model → `create_visualization()` tool → `ChatResponse` extension → frontend renderer) can parallelize between backend and frontend once the `Artifact` model ships; Phase 2 (reviewer template + E2E against the GA specialist) requires Phase 1 in place.
6. **Release 3 (Expertise) — multi-step:** AH-PRD-05 kickoff once AH-PRD-04 is in staging (or in parallel once `Artifact` lands and the artifact session-state convention is stable; the workflow factory threads `<step_id>_artifacts` through the same path). Single Core AI track; the four stories (4.1–4.4) are largely sequential within a 3–5-day window. After this lands, the harness has a complete review-loop story across single-step and multi-step composition.

## 6. Global Document References

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| `docs/KEN-E-System-Architecture.md` | §2.2 (Component responsibilities), §2.3.2 (Request flow with review loop), §4.3 (Tool type taxonomy), §4.4 (Code execution), §4.6 (Review Loop Pattern), §8.1–8.4 (Multi-step workflow, ADK pitfalls, LLM cost & latency) | Root design document for the agent system. Read before any change to the harness. |
| [`./mcp-architecture.md`](./mcp-architecture.md) | §2 ADK internals, §4 Platform integration decisions, §6 Firestore config schema, §7 MCPServerManager disposition, §8 Read-only limitations | MCP-specific reference for this component — consumed by the factory and the GA specialist PRD. |
| [`../../review-loop-implementation-plan.md`](../../review-loop-implementation-plan.md) | Phase 1–3 (drive AH-PRD-01), Phase 4 (Multi-Step Workflow Support — deferred to Release 3), §3.1 (Building Block architecture), §7 (Verification Checklist) | Parent implementation plan for AH-PRD-01 and the eventual R3 multi-step workflow PRD. |
| `docs/trace-structure-spec.md` | Span table | Every dispatch + review-loop iteration emits spans matching this spec. MER-E ingestion depends on it. |
| [`../data-management/README.md`](../data-management/README.md) | §2.2 Data Flow, §7.1 Shape B path convention | Shape B layout for `accounts/{account_id}/agent_configs/{config_id}`. |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | 2026-04-20 Multi-Tenant Shape B entry | Rationale for the current per-account overlay path layout. |
| [Review 6 in DESIGN-REVIEW-LOG](../../DESIGN-REVIEW-LOG.md#review-6-task-delegation-with-review-loops) | Entire entry | Full rationale for the Generator-Critic review-loop pattern (originally Notion Decision 21). |
| [Review 5 in DESIGN-REVIEW-LOG](../../DESIGN-REVIEW-LOG.md#review-5-architecture-accuracy-pass--harness-doc-v22--v23) | Entire entry | Rationale for the config-driven narrow-specialist pattern proven by AH-PRD-03. |

## 7. Conventions and Constraints

### Agent construction
- All specialists assembled by the factory (AH-PRD-02) at deploy time — **no dynamic runtime sub-agent creation**. Runtime ephemeral agents for focused sub-tasks use the `Runner` pattern (AH-PRD-02 §5.4); they do not mutate the persistent tree.
- `agent_configs/*` and `mcp_servers/*` are **global** collections per the Shape B carve-out. Per-account customization lives at `accounts/{account_id}/agent_configs/{config_id}` and is a shallow-merge overlay onto the global config.
- `config_id` naming: global specialists use descriptive names (`google_analytics_specialist`, `project_planning`); user-authored custom agents use a `custom_` prefix + UUID.
- Each specialist's tool roster is capped at **≤30 tools** at construction (see §2.5). Build fails fast if exceeded.

### Review loop (AH-PRD-01)
- Specialist and reviewer are **direct children** of `LoopAgent`. No `SequentialAgent` wrapper — `SequentialAgent` would swallow `escalate` from `exit_loop`.
- Reviewer: `gemini-2.0-flash`, `include_contents='none'`, `exit_loop` in tools.
- Each review pipeline uses a unique `output_key_prefix` to isolate state between concurrent pipelines in the same session.
- `{prefix}_feedback?` (with `?` suffix) — optional template variable; first iteration resolves to empty string instead of `KeyError`.
- `exit_loop` is a tool call with no text — if the agent also has `output_key`, that key is overwritten to `""` on exit. The reviewer (not the specialist) holds `exit_loop`; specialist's `{prefix}_draft` is the approved result.
- Default `max_iterations=3`. On exhaustion: last draft retained, no exception.

### Firestore layout (Shape B + carve-outs)
- `agent_configs/{config_id}` — global (non-account-scoped; Shape B carve-out).
- `mcp_servers/{server_id}` — global (non-account-scoped; Shape B carve-out).
- `accounts/{account_id}/agent_configs/{config_id}` — Shape B subcollection for per-account overlay + custom agents.
- Account deletion: covered by `firestore.recursive_delete(accounts/{account_id})` once DM-PRD-05 ships. Until then, AH-PRD-02 extends the enumerated sweep to include `agent_configs`.

### Dispatch & tracing
- Every dispatch function is decorated with `@safe_weave_op()` — the factory-generated variants preserve this.
- Criteria-provided path wraps the specialist in `build_review_pipeline()`; `acceptance_criteria=None/""` preserves single-pass legacy behavior.
- Weave trace hierarchy: root agent → dispatch span → review-loop iterations as sub-spans → specialist + reviewer sub-spans. Acceptance criteria live in the pipeline span's attributes.

### Deprecation discipline
- Transitional agents (`google_analytics_agent_v4.py`, `company_news_chatbot/agent.py`) are marked deprecated before removal. They remain importable until a follow-up story removes them once no callers exist. Do not delete and leave dangling imports.

### Testing
- Unit tests for `build_review_pipeline` and the factory use mock ADK agents and mock Firestore.
- Integration tests use Firestore emulator for the factory; `@pytest.mark.llm` marker for the E2E tests against a live Gemini endpoint (GA specialist in AH-PRD-03).
- Review-loop regression guard: `acceptance_criteria=None` must produce identical behavior to pre-AH-PRD-01 code. This is an explicit AC on AH-PRD-01.

### Standard shape for a project PRD in [`projects/`](./projects/)
Every PRD follows the shared 10-section structure used across sibling components:

1. Context — problem this PRD solves
2. Scope — explicit in/out
3. Dependencies — other PRDs, files, services
4. Data contract — Pydantic / TypeScript types owned or consumed
5. Implementation outline — files to create / modify (table)
6. API contract — endpoints (where applicable)
7. Acceptance criteria — what "done" means
8. Test plan — unit / integration / E2E coverage
9. Risks & open questions
10. Reference — links back to sibling PRDs, upstream design docs

---

<!-- PRD MAINTENANCE NOTES

Updating this PRD:
- When a new specialist PRD is authored (e.g. AH-PRD-05 Google Ads Specialist, per the §2.6 roadmap): add it to §5.2 Projects and to §3.2 Depended On By if anything downstream changes.
- When a transitional agent is fully removed (e.g. google_analytics_agent_v4.py): update §2.1 Key Directories to remove the row.
- When architecture changes (new directories, new abstractions, new API endpoints): update §2.
- When a new cross-component dependency is introduced: update §3.
- Review loop and agent factory are the two permanent pillars — changes to either ripple across every downstream component. Open a DESIGN-REVIEW-LOG entry before significant modifications.

This PRD is read by the Dev Team agent during implementation planning (CLAUDE.md §Context Loading Sequence, Step 1). Keep it concise — every sentence should help a dev write better code or avoid mistakes.
-->
