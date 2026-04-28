# Skills — Product Requirements Document

> **Linear Team:** [KEN-E] Skills
> **Last Updated:** 2026-04-20
> **Status:** Active

## 1. Overview

The Skills component gives end-users a way to **capture and reuse their domain expertise** as modular, agent-loadable bundles. A **Skill** is a self-contained unit of instructions (plus optional reference files, assets, and scripts) that an agent loads via progressive disclosure to perform a specific task. Skills follow the open [agentskills.io specification](https://agentskills.io/specification) and integrate with Google ADK via `SkillToolset` (ADK v1.25.0+, experimental). A user authors a `SKILL.md` in the Workflows UI, saves it, and attaches it to a **custom specialist agent** built on the [AH-PRD-02](../agentic-harness/projects/AH-PRD-02-agent-factory.md) Agent Factory; when that agent runs, `SkillToolset` auto-generates discovery tools (`list_skills`, `load_skill`, `load_skill_resource`) so the agent loads only the skill it needs, when it needs it.

The component spans three architectural pillars — a **storage split** (metadata in Firestore `accounts/{account_id}/skills/{skill_id}`, content in GCS `gs://kene-skills-{env}/accounts/{account_id}/{skill_id}/{version}/…` keyed by `skill_id` so renames don't split version history), **progressive disclosure via `SkillToolset`** (L1 frontmatter hydrated at agent construction, L2 body on activation, L3 references/assets/scripts lazily streamed from GCS), and **gated script execution** (a skill's `scripts/` cannot run unless the owning agent is configured with `sandbox_code_executor_enabled=true`, which attaches `AgentEngineSandboxCodeExecutor` as the agent's `code_executor`). On top of those, a Skills tab under `/workflows/skills` and an Agent Builder skills-picker on `/workflows/agents` close the authoring + attachment loop. KEN-E also ships **system-owned predefined skills** (one placeholder `example-skill` in v1) attached to the root agent via [SK-PRD-05](./projects/SK-PRD-05-predefined-skill-foundation.md).

A developer reading only this section should understand: this component owns the `Skill` / `SkillVersion` data model, the `/api/v1/accounts/{account_id}/skills/*` API, the `kene-skills-{env}` GCS bucket (plus a `-trash` sibling with a 30-day lifecycle), the skill loader that hydrates ADK `Skill` objects with lazy L3 callables, the agent-factory wiring that constructs `SkillToolset` + sandbox `code_executor` from config, the Skills authoring UI, and the agent-builder controls that enforce attach-time validation. It rides on top of [AH-PRD-02](../agentic-harness/projects/AH-PRD-02-agent-factory.md) (Agent Factory) for the two `agent_configs` fields (`skill_ids`, `sandbox_code_executor_enabled`) that turn a config into a skill-bearing agent.

## 2. Architecture

```
┌─────────────────────┐                                       ┌────────────────────────┐
│  Frontend           │                                       │   KEN-E Backend         │
│  (/workflows)       │                                       │                         │
│                     │  POST /api/v1/accounts/{id}/skills    │  Firestore              │
│  ┌───────────────┐  │  GET  /api/v1/accounts/{id}/skills    │  ┌──────────────────┐   │
│  │ Skills tab    │──┼───────────────────────────────────────┼─▶│ accounts/{id}/   │   │
│  │ (author/edit) │  │  GET  .../{sid}/content               │  │   skills/{sid}   │   │
│  └───────────────┘  │  GET  .../{sid}/resources/{rel_path}  │  │   + versions/{n} │   │
│                     │  PUT  .../{sid}                       │  └──────────────────┘   │
│  ┌───────────────┐  │  DELETE .../{sid}                     │                         │
│  │ Agent Builder │  │                                       │  GCS                    │
│  │ (picker +     │──┼───────────────────────────────────────┼─▶  kene-skills-{env}/   │
│  │  sandbox      │  │  PUT /.../agent-configs/{cfg_id}      │   accounts/{id}/        │
│  │  toggle)      │  │   { skill_ids, sandbox_enabled }      │     {skill_id}/         │
│  └───────────────┘  │                                       │       {version}/        │
│                     │  POST .../agents/_ephemeral_chat      │         SKILL.md        │
│  ┌───────────────┐  │                                       │         references/     │
│  │ Test Drawer   │──┼───────────────────────────────────────┼─▶       assets/         │
│  └───────────────┘  │                                       │         scripts/*       │
└─────────────────────┘                                       │                         │
                                                              │  Agent Factory (2.2)    │
                                                              │  ┌────────────────────┐ │
                                                              │  │ build_agent(cfg,   │ │
                                                              │  │   account_id)      │ │
                                                              │  │   reads skill_ids  │─┼─┐
                                                              │  │   reads sandbox    │ │ │
                                                              │  └────────────────────┘ │ │
                                                              │            │            │ │
                                                              │            ▼            │ │
                                                              │  ┌────────────────────┐ │ │
                                                              │  │ SkillToolset       │◀┼─┘
                                                              │  │  [L1 metadata for  │ │
                                                              │  │   all attached]    │ │
                                                              │  └────────────────────┘ │
                                                              │            │            │
                                                              │            ▼            │
                                                              │  ┌────────────────────┐ │
                                                              │  │ LlmAgent           │ │
                                                              │  │  code_executor=    │ │
                                                              │  │   AgentEngine      │ │
                                                              │  │   Sandbox… *       │ │
                                                              │  │  tools=[…]         │ │
                                                              │  │  before_tool_cb =  │ │
                                                              │  │   allowed-tools    │ │
                                                              │  │   filter           │ │
                                                              │  └────────────────────┘ │
                                                              └─────────────────────────┘

*`scripts/` is uploaded unconditionally but can only execute when the owning
 agent's sandbox_code_executor_enabled=true. Attach-time validation (SK-PRD-04)
 rejects PUTs that pair a scripts-bearing skill with a non-sandbox agent.
```

### 2.1 Key Directories

| Path | Purpose |
|------|---------|
| `api/src/kene_api/models/skill_models.py` | `Skill`, `SkillVersion`, `SkillFrontmatter`, `SkillFileEntry`, `SkillStatus`, `SkillVisibility` (SK-PRD-01) |
| `api/src/kene_api/routers/skills.py` | `/api/v1/accounts/{account_id}/skills/*` — CRUD + content + resources + validate (SK-PRD-01) |
| `api/src/kene_api/routers/ephemeral_chat.py` | `POST /api/v1/accounts/{account_id}/agents/_ephemeral_chat` — backs the Test Drawer (SK-PRD-04) |
| `api/src/kene_api/routers/agent_configs.py` | **Existing (AH-PRD-02)** — SK-PRD-04 adds the three attach-time validation rules |
| `api/src/kene_api/services/skill_storage.py` | GCS read/write/delete + manifest generation (SK-PRD-01) |
| `api/src/kene_api/services/skill_validator.py` | Frontmatter + bundle validation (pure functions) (SK-PRD-01) |
| `api/src/kene_api/services/skill_loader.py` | Reads Firestore + GCS; returns ADK `Skill` with lazy L3 callables (SK-PRD-01) |
| `api/src/kene_api/services/skill_attach_validator.py` | `check_cap`, `check_skills_exist_in_account`, `check_scripts_require_sandbox` (SK-PRD-04) |
| `app/adk/agents/agent_factory.py` | **Existing (AH-PRD-02)** — SK-PRD-02 adds `_build_skill_toolset` + `_build_code_executor` |
| `app/adk/agents/skill_tool_filter.py` | `parse_allowed_tools`, `restrict_tools_for_skill`, `before_tool_callback` wiring (SK-PRD-02) |
| `frontend/src/app/pages/workflows/skills/` | List, Create, Edit pages + components (FrontmatterForm, SkillMdEditor, ReferenceFileUploader, ValidationPanel, VersionHistoryDrawer, TestSkillDrawer) (SK-PRD-03) |
| `frontend/src/app/pages/workflows/agents/components/SkillsPicker.tsx` | Multi-select picker with sandbox-aware disabling (SK-PRD-04) |
| `frontend/src/app/pages/workflows/agents/components/SandboxToggle.tsx` | Sandbox-enable control on the Agent Builder (SK-PRD-04) |
| `frontend/src/app/lib/api/skills.ts` | Typed API client + branded `SkillId` (SK-PRD-03) |
| `frontend/src/app/hooks/useSkills.ts` | React Query hooks (SK-PRD-03) |
| `frontend/src/app/lib/validation/skillFrontmatter.ts` | Client-side validator shared with backend rules (SK-PRD-03) |
| `deployment/terraform/gcs_skills_bucket.tf` | `kene-skills-{env}` + `-trash` buckets, CMEK, IAM, 30-day lifecycle (SK-PRD-01) |
| `deployment/terraform/firestore_indexes_skills.tf` | Collection-scope composite indexes on `accounts/*/skills` (SK-PRD-01) |
| `docs/spike-agent-engine-sandbox-findings.md` | Spike output — network egress, cost, resource limits, cross-skill state (SK-PRD-00) |
| `docs/skills-user-guide.md` | End-user authoring + attachment guide (SK-PRD-04) |

### 2.2 Data Flow

1. **Authoring (SK-PRD-03):** A user visits `/workflows/skills`, fills the frontmatter form, writes the `SKILL.md` body in a Monaco editor, and optionally uploads reference/asset/script files. Client-side validation mirrors the backend rules (name regex, size caps, 20-file cap on `references/` only). Clicking Save submits a multipart `POST /api/v1/accounts/{account_id}/skills` with `skill_md` + `files[]`.
2. **Persistence (SK-PRD-01):** The backend validates frontmatter, enforces size caps (SKILL.md ≤ 5 kB, individual file ≤ 100 kB, total bundle ≤ 2 MB; `references/` ≤ 20 files; `assets/` and `scripts/` constrained by total-bundle cap only), generates a manifest with sha256 checksums, allocates `skill_id` (UUID) and `version=1`, writes the bundle to `gs://kene-skills-{env}/accounts/{account_id}/{skill_id}/1/`, and writes the Firestore doc + `versions/1` subcollection doc in a single Firestore transaction (PUTs use a retry loop on `current_version` contention).
3. **Versioning (SK-PRD-01):** A `PUT /api/v1/accounts/{account_id}/skills/{skill_id}` creates a new immutable version under `…/{version+1}/`. Previous versions stay in GCS and can be read via `?version=N`. Soft-delete moves the skill's prefix to `gs://kene-skills-{env}-trash/…` with a 30-day lifecycle rule.
4. **Attachment (SK-PRD-04):** An admin opens `/workflows/agents/{config_id}`, the `SkillsPicker` fetches `GET /api/v1/accounts/{account_id}/skills`, and the admin selects up to 10 skills + toggles Sandbox. Submitting sends `PUT /api/v1/accounts/{account_id}/agent-configs/{config_id}` with the `skill_ids` + `sandbox_code_executor_enabled` fields. The router runs three attach-time checks: 10-skill cap, existence-in-this-account, and scripts-require-sandbox. Violations return 422 with a structured error body.
5. **Agent construction (SK-PRD-02):** When the agent factory builds an `LlmAgent`, `_build_skill_toolset(account_id, skill_ids)` calls `skill_loader.load_skill(account_id, sid)` for each attached skill (L1 frontmatter + L2 body eager, L3 resources lazy), constructs a `SkillToolset`, and attaches it to the agent's tools. If `sandbox_code_executor_enabled=true`, `_build_code_executor` attaches `AgentEngineSandboxCodeExecutor(...)` as the agent's `code_executor`.
6. **Invocation:** `SkillToolset` auto-generates three tools — `list_skills` (L1 discovery), `load_skill` (L2 body), `load_skill_resource` (L3 files). The LLM reads L1 descriptions, picks a skill, loads its body, then requests specific resources. A `before_tool_callback` reads the currently active skill's `allowed-tools` frontmatter and restricts the agent's available tools during that skill's invocation window — restriction only, never grant.
7. **Tracing:** Every skill interaction emits W&B Weave spans conforming to `docs/trace-structure-spec.md` — `skill.list`, `skill.load`, `skill.load_resource` — with `account_id`, `skill_id`, `skill_name`, `skill_version`, and byte counts. MER-E consumes these to score skill-triggered sessions.

### 2.3 API Contracts

Owned endpoints:

| Endpoint | Method | Owner | Schema |
|----------|--------|-------|--------|
| `/api/v1/accounts/{account_id}/skills` | POST | SK-PRD-01 | multipart (`skill_md` + `files[]`) → `Skill` |
| `/api/v1/accounts/{account_id}/skills` | GET | SK-PRD-01 | `PaginatedResponse<Skill>` (filters: `status[]`, `has_scripts`, cursor) |
| `/api/v1/accounts/{account_id}/skills/{skill_id}` | GET | SK-PRD-01 | `Skill` metadata |
| `/api/v1/accounts/{account_id}/skills/{skill_id}/content` | GET | SK-PRD-01 | `text/markdown` (SKILL.md body; `?version=N` to pin) |
| `/api/v1/accounts/{account_id}/skills/{skill_id}/resources/{rel_path}` | GET | SK-PRD-01 | L3 file content (path validated; `?version=N` to pin) |
| `/api/v1/accounts/{account_id}/skills/{skill_id}` | PUT | SK-PRD-01 | multipart → new version; `Skill` returned |
| `/api/v1/accounts/{account_id}/skills/{skill_id}` | DELETE | SK-PRD-01 | soft-archive (moves to trash bucket; 30-day TTL) |
| `/api/v1/accounts/{account_id}/skills/validate` | POST | SK-PRD-01 | dry-run validation (no state) |
| `/api/v1/accounts/{account_id}/agents/_ephemeral_chat` | POST | SK-PRD-04 | `{skill_ids, sandbox_code_executor_enabled, message}` → one-off agent reply |

Consumed/extended endpoints (owned by [AH-PRD-02](../agentic-harness/projects/AH-PRD-02-agent-factory.md)):

| Endpoint | Method | Extension | Schema |
|----------|--------|-----------|--------|
| `/api/v1/accounts/{account_id}/agent-configs/{config_id}` | PUT | SK-PRD-04 adds three attach-time validations | AH-PRD-02 owns base body; `skill_ids`, `sandbox_code_executor_enabled` are forward-compat pass-through until SK-PRD-04 lights them up |
| `/api/v1/accounts/{account_id}/agent-configs/` | POST | Same three validations on creation | Same |

Schema source of truth: `api/src/kene_api/models/skill_models.py` (Pydantic), mirrored as TypeScript branded types in `frontend/src/app/lib/api/skills.ts`. IDs use `SkillId = Brand<string, "SkillId">` per CLAUDE.md C-5.

### 2.4 Key Abstractions

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `Skill` / `SkillVersion` / `SkillFrontmatter` | `api/src/kene_api/models/skill_models.py` | Firestore doc + immutable per-version snapshot + parsed YAML frontmatter. Skills are **account-scoped** (owner = `{account_id}`); `created_by` captures the authoring user for audit. |
| `skill_loader.load_skill(account_id, skill_id, *, version=None)` | `api/src/kene_api/services/skill_loader.py` | Returns an ADK `Skill` object with L1/L2 materialized eagerly and L3 resources as lazy callables bound to the skill's GCS prefix. Validates `rel_path` against the bundle manifest — the LLM cannot escape the prefix. |
| `SkillToolset` | `google.adk.skills` (ADK v1.25.0+) | Auto-generates `list_skills`, `load_skill`, `load_skill_resource` tools. Hydrated by the agent factory from the user's `skill_ids`. |
| `AgentEngineSandboxCodeExecutor` | `google.adk.code_executors.agent_engine_sandbox_code_executor` | First-party ADK sandbox. Wired as `code_executor` on the constructed `LlmAgent` when `sandbox_code_executor_enabled=true`. |
| `parse_allowed_tools` / `restrict_tools_for_skill` | `app/adk/agents/skill_tool_filter.py` | Parses the space-separated `allowed-tools` string (exact + suffix-glob) and returns the subset of the agent's existing tools. **Never grants** a tool not already on the agent. |
| `skill_attach_validator` (pure funcs) | `api/src/kene_api/services/skill_attach_validator.py` | Unit-testable attach-time checks: `check_cap` (≤ 10), `check_skills_exist_in_account`, `check_scripts_require_sandbox`. Backends the three 422 cases on `PUT agent-configs`. |
| `has_scripts: bool` on `Skill` | SK-PRD-01 data model | Set to `true` on any version whose `scripts/` is non-empty. Consumed by SK-PRD-04's picker (disables the row when `sandboxEnabled=false`) and the attach-time validator (rejects save). |
| `skill_ids` / `sandbox_code_executor_enabled` on `AgentConfig` | AH-PRD-02 forward-compat fields | Config-driven `LlmAgent` assembly. SK-PRD-02 lights them up in the factory; SK-PRD-04 enforces them in the API. |

## 3. Component Dependencies

### 3.1 Depends On

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **Agentic Harness — Agent Factory ([AH-PRD-02](../agentic-harness/projects/AH-PRD-02-agent-factory.md))** | **Hard prerequisite for SK-PRD-02 and SK-PRD-04.** Delivers the config-driven `agent_factory.build_agent`, the Firestore `agent_configs/{config_id}` schema with the two forward-compat fields (`skill_ids`, `sandbox_code_executor_enabled`), the `PUT / POST agent-configs` endpoints that accept them as pass-through, and the `AgentEditView` + `AgentCreatePage` UIs with two placeholder rows SK-PRD-04 swaps for interactive controls. SK-PRD-01 and SK-PRD-03 do **not** depend on AH-PRD-02 and can ship in parallel. | [`../agentic-harness/projects/AH-PRD-02-agent-factory.md`](../agentic-harness/projects/AH-PRD-02-agent-factory.md) |
| **Data Management — DM-PRD-00 (Migration Foundation)** | **Hard prerequisite for SK-PRD-01.** Establishes the Shape B convention (`accounts/{account_id}/skills/…`) and ships the two `skills` collection-scope composite indexes (`status ASC, updated_at DESC` and `has_scripts ASC, updated_at DESC`) that the list endpoint consumes. | [`../data-management/projects/DM-PRD-00-migration-foundation.md`](../data-management/projects/DM-PRD-00-migration-foundation.md) |
| **Data Management — DM-PRD-05 (Deletion Sweep Rewrite)** | **Hard prerequisite for SK-PRD-01.** Rewrites the enumerated account-deletion sweep in `routers/accounts.py` as `firestore.recursive_delete(accounts/{account_id})` so the new `skills` + `skills/{id}/versions` subcollections are automatically covered on account deletion. The matching GCS prefix purge (`gs://kene-skills-{env}/accounts/{account_id}/…`) is added by SK-PRD-01 alongside the existing `storage_service.delete_account_documents` helper. | [`../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md`](../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md) |
| Google ADK v1.25.0+ | `SkillToolset`, `models.Skill`, `AgentEngineSandboxCodeExecutor`. Pinned at the start of SK-PRD-02; a thin wrapper isolates the import path so upstream API churn has one edit point. | [Google ADK Skills overview](https://adk.dev/skills/) |
| Google Cloud Storage | SK-PRD-01 provisions `kene-skills-{env}` + `kene-skills-{env}-trash` with uniform access, CMEK, and a 30-day lifecycle rule on the trash bucket. | `app/utils/gcs.py` |
| Vertex AI Agent Engine | SK-PRD-02's `AgentEngineSandboxCodeExecutor` config (resource name, network policy, CPU/mem limits) is informed by the SK-PRD-00 spike findings. | [Agent Engine Code Execution](https://adk.dev/integrations/code-exec-agent-engine/) |
| Account / Auth | `check_account_access` pattern (mirrors `check_strategy_access` in `routers/strategy.py`) gates every `/api/v1/accounts/{account_id}/skills/*` and `/agents/_ephemeral_chat` request. | `api/src/kene_api/auth/` |
| W&B Weave tracing | SK-PRD-02 extends `docs/trace-structure-spec.md` with three new spans (`skill.list`, `skill.load`, `skill.load_resource`); MER-E consumes them. | [`../../../trace-structure-spec.md`](../../../trace-structure-spec.md) |

### 3.2 Depended On By

| Component | Dependency |
|-----------|------------|
| Root / specialist agents (`app/adk/agents/`) | Custom specialist agents built via AH-PRD-02 (Agent Factory) gain skill-aware behavior once SK-PRD-02 ships. Root agent's system-owned skills (future) ride on the same loader and `SkillToolset` hydration path. |
| Agent Factory forms (`frontend/src/app/pages/workflows/agents/*`) | The Agent Builder UI depends on SK-PRD-03's skill list (via `useSkills()`) to populate the picker and SK-PRD-04 to wire and validate the controls. |
| MER-E evaluation pipeline | Consumes the three new Weave spans to score skill-triggered sessions. Poisoned or low-quality skills surface in quality metrics. |

## 4. Design System References

| Document | Sections | When to Read |
|----------|----------|--------------|
| Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) | Workflows page — Skills tab (list + editor); Agent Builder (picker + toggle rows) | When implementing SK-PRD-03 (authoring UI) or SK-PRD-04 (agent-builder controls). Design to be created if not yet present. |
| `frontend/CLAUDE.md` | CSS architecture, shadcn/ui component library, branded types | Before adding any new React component. |
| `frontend/src/app/pages/workflows/WorkflowsLayout.tsx` (AH-PRD-02) | Tab structure shared with Agents / Automations | Adding the Skills tab in SK-PRD-03. |
| `frontend/src/app/pages/workflows/agents/AgentEditView.tsx` (AH-PRD-02) | Existing placeholder rows SK-PRD-04 swaps for live controls | Starting SK-PRD-04. |
| Monaco editor docs ([`@monaco-editor/react`](https://github.com/suren-atoyan/monaco-react)) | Lazy loading, markdown language, char counter | Building the SKILL.md editor in SK-PRD-03 (new dependency — add to package.json). |

## 5. Project Index

The component's work is split across **6 independently shippable project PRDs** under [`projects/`](./projects/). The split follows team boundaries and a dependency arc that deliberately isolates the sandbox spike: its findings can reshape SK-PRD-02's scope, so it is pulled out as a sprint-0 artifact. SK-PRD-01 publishes the API contract every other sprint stubs against; SK-PRD-02 (only sprint requiring AH-PRD-02) lights up agent-factory wiring; SK-PRD-03 (authoring UI) runs in parallel against the contract; SK-PRD-04 closes the loop with the agent-builder controls + end-to-end test; SK-PRD-05 ships the system-owned-skill scaffolding plus a single `example-skill` placeholder so System Architecture §6's "predefined skills" promise is fulfilled.

### 5.1 Dependency graph

```
                  ┌─ SK-PRD-00 (Sandbox Spike) ──┐
(parallel ──────► │                              ├─┐
 to AH-PRD-02)    └─ SK-PRD-01 (Skills Backend) ─┘ │
                                                    │
                                                    ▼
                AH-PRD-02 (Agent Factory) ─────► SK-PRD-02 (Agent Integration) ──┐
                                                                                  │
                           SK-PRD-01 ──────────► SK-PRD-03 (Authoring UI) ────────┤
                                                                                  ▼
                                                                      SK-PRD-04 (Agent Builder
                                                                        Controls + E2E)
                                                                      (needs AH-PRD-02 + SK-PRDs 01 + 02 + 03)

                AH-PRD-02 + SK-PRD-01 + SK-PRD-02 ─► SK-PRD-05 (Predefined Skill Foundation)
                                                     (parallel with SK-PRDs 03, 04)
```

### 5.2 Projects

| # | Project PRD | Owner team | Blocked by | Parallel with | Est. |
|---|-------------|------------|------------|---------------|------|
| 00 | [Sandbox Spike](./projects/SK-PRD-00-skills-experiment.md) | Platform + Security | — | AH-PRD-02, SK-PRDs 01, 03 | 3–5 days |
| 01 | [Skills Backend — Storage, API, Loader](./projects/SK-PRD-01-skills-backend.md) | Backend | DM-PRD-00, DM-PRD-05 | AH-PRD-02, SK-PRDs 00, 03 | 6–8 days |
| 02 | [Agent Factory — Skills & Sandbox Integration](./projects/SK-PRD-02-agent-integration.md) | Agent Platform | AH-PRD-02, SK-PRD-00, SK-PRD-01 | SK-PRD-03 | 5–7 days |
| 03 | [Skills Authoring UI](./projects/SK-PRD-03-authoring-ui.md) | Frontend | SK-PRD-01 (contract) | AH-PRD-02, SK-PRD-02 | 6–8 days |
| 04 | [Agent Builder Controls + E2E](./projects/SK-PRD-04-agent-builder-controls.md) | Frontend + Backend | AH-PRD-02, SK-PRDs 01, 02, 03 | — | 4–5 days |
| 05 | [Predefined Skill Foundation](./projects/SK-PRD-05-predefined-skill-foundation.md) | Backend + Agent Platform | AH-PRD-02, SK-PRDs 01, 02 | SK-PRDs 03, 04 | 2–3 days |

### 5.3 Cross-PRD coordination points

Four touchpoints do not fit cleanly inside one PRD and need an owning team to consciously sync:

- **Agent config schema extensions (SK-PRD-02 ↔ AH-PRD-02 stories 2.2-1, 2.2-8):** AH-PRD-02 ships `skill_ids` and `sandbox_code_executor_enabled` as passive forward-compat placeholders (accepted, stored, pass-through). SK-PRD-02 lights up the factory's constructor wiring; SK-PRD-04 adds the attach-time validation on the API. Loop in the AH-PRD-02 team before either starts.
- **Agent builder form layout (SK-PRD-04 ↔ AH-PRD-02 stories 2.2-10, 2.2-11):** AH-PRD-02 reserves two disabled rows ("Skills" and "Sandbox code execution") in `AgentEditView` + `AgentCreatePage`. SK-PRD-04 swaps them for interactive controls — coordinate with whoever owns those page components.
- **Tracing spans (SK-PRD-02 ↔ `docs/trace-structure-spec.md`):** SK-PRD-02 appends three span entries. Extend the spec in the same PR that adds the spans so MER-E ingestion never sees spans without a spec row.
- **Sandbox spike findings feeding SK-PRD-02 (SK-PRD-00 ↔ SK-PRD-02):** If the spike returns a blocking answer (e.g., network egress cannot be restricted), SK-PRD-02's scope changes: scripts become read-only reference files only. Document the outcome in `DESIGN-REVIEW-LOG.md` and update this README's §7 conventions.

### 5.4 Recommended workflow

1. **Sprint 0 (parallel with AH-PRD-02):** Kick off SK-PRD-00 (spike) and SK-PRD-01 (backend) on day 1 — neither has blockers beyond DM-PRDs 00/05, which are ahead in Release 1. AH-PRD-02 runs its planned course. SK-PRD-01 publishes its Pydantic + API contract mid-sprint so SK-PRD-03 can stub against it.
2. **Sprint 1 (after AH-PRD-02 + SK-PRD-01 merge):** Start SK-PRD-02 (needs AH-PRD-02 + SK-PRD-01 + spike findings) and SK-PRD-03 (needs SK-PRD-01 only). Both run in parallel.
3. **Sprint 2 (close-out):** SK-PRD-04 ships the picker + toggle + attach-time validation + ephemeral chat endpoint + end-to-end Playwright test. Feature lands as a unit.

## 6. Global Document References

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| `docs/KEN-E-System-Architecture.md` | Agent construction, Tool discovery, Context loading | Skills piggyback on the tool-discovery path; read when wiring `SkillToolset` into the factory. |
| [`../agentic-harness/README.md`](../agentic-harness/README.md) | §2.4 Key Abstractions, §2.5 Tool-assignment model | The factory's overlay model and per-specialist ≤30-tool roster. |
| [`../agentic-harness/projects/AH-PRD-02-agent-factory.md`](../agentic-harness/projects/AH-PRD-02-agent-factory.md) | §4 Data contract, §5.2 Config-to-constructor mapping | Skills + sandbox are config-driven. SK-PRD-02 extends §5.2 with the `skill_ids` / `sandbox_code_executor_enabled` field behavior; SK-PRD-04 finalizes it. |
| [`../../../trace-structure-spec.md`](../../../trace-structure-spec.md) | Span table | SK-PRD-02 appends three span rows (`skill.list`, `skill.load`, `skill.load_resource`). |
| [`../data-management/README.md`](../data-management/README.md) | §2 (Architecture), §3 (Shape B conventions) | Firestore path convention + composite-index registry for the `skills` subcollection. |
| [`../data-management/multi-tenant-migration-plan.md`](../data-management/multi-tenant-migration-plan.md) | Phase 0 (indexes), Phase 5 (PRD + doc edits) | Confirms the Shape B paths SK-PRD-01 uses (`accounts/{account_id}/skills/...`). |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | 2026-04-20 entry (Multi-Tenant Shape B) | Rationale for the current `accounts/*/skills/*` layout. |
| `docs/skills-user-guide.md` | (authored by SK-PRD-04) | End-user authoring guide — link from the Skills tab empty-state. |

## 7. Conventions and Constraints

### Data model
- Skills are **account-scoped**, not user-scoped. `owner = {account_id}`; `created_by` captures the authoring user for audit only. A user with membership in multiple accounts sees a different skill set per account; skills do not follow users across accounts.
- `name` is kebab-case (`^[a-z0-9]+(-[a-z0-9]+)*$`), max 64 chars, **unique per account**. Different accounts may reuse the same `name`.
- `description` is 1–1024 chars. `compatibility` is ≤ 500 chars. SKILL.md body is ≤ 5 kB. Individual file ≤ 100 kB. Total bundle ≤ 2 MB. **`references/` ≤ 20 files** — `assets/` and `scripts/` have no separate file-count cap and are constrained by the total-bundle cap only.
- `visibility = "private"` in v1; the enum reserves `"org"` for v2 cross-account sharing. `SkillOwner.shared_with_accounts: list[str]` is persisted but ignored in v1.
- `status ∈ {"draft", "published", "archived"}`. Archived is soft-delete; 30-day GCS lifecycle purges the trash prefix.
- Each `PUT` creates a new **immutable version** under `…/{version+1}/`. Previous versions remain readable via `?version=N`.
- `has_scripts: bool` is set when a version's `scripts/` directory is non-empty. The picker (SK-PRD-04) disables the row when `sandboxEnabled=false`; the attach-time validator rejects the save.
- `current_version` is monotonically increasing; starts at 1. `skill_id` is a UUID.

### Firestore layout (Shape B)
- `accounts/{account_id}/skills/{skill_id}` — metadata doc
- `accounts/{account_id}/skills/{skill_id}/versions/{version}` — immutable per-version snapshot (file manifest, frontmatter, checksums)
- Composite indexes are **collection-scope** on `accounts/*/skills` (no collection-group index needed in v1). List-page queries use `(status, updated_at DESC)` and `(has_scripts, updated_at DESC)`.
- Account deletion uses `firestore.recursive_delete(accounts/{account_id})` — covered by DM-PRD-05.

### GCS layout
- `gs://kene-skills-{env}/accounts/{account_id}/{skill_id}/{version}/` (keyed by `skill_id` so renames don't split version history)
- `gs://kene-skills-{env}/_system/{skill_name}/{version}/` for system-owned predefined skills (SK-PRD-05; keyed by `skill_name` because system-skill names are globally unique and renames are operations events)
- Contents: `SKILL.md` (required), `references/` (optional, L3), `assets/` (optional, L3), `scripts/` (optional, L3, sandbox-gated), `.manifest.json` (generated on write).
- Soft-delete moves the prefix to `gs://kene-skills-{env}-trash/accounts/{account_id}/…`; a 30-day GCS lifecycle rule purges it. No human intervention to restore — document in the authoring UI that archive is effectively-permanent after 30 days.
- Uniform access, no public ACLs, CMEK with the project default key.

### Progressive disclosure (L1 / L2 / L3)
- **L1 (frontmatter, ~100 tokens/skill):** Loaded eagerly for all attached skills at agent construction. 10-skill cap → ~1 kB session overhead. Monitor in tracing; tighten the cap if real workloads push beyond budget.
- **L2 (SKILL.md body, ≤ 5 kB):** Loaded when the LLM calls `load_skill`. Materialized from GCS.
- **L3 (references / assets / scripts):** Loaded only when the LLM calls `load_skill_resource(rel_path)`. Implemented as closures in the loader that stream the file from GCS. `rel_path` is validated against the bundle manifest — the LLM cannot escape the prefix.

### `allowed-tools` semantics (restriction-only)
- Frontmatter `allowed-tools` is a space-separated string (e.g. `"Bash(git:*) Bash(jq:*) Read"`). Parsed into a set of patterns; exact match + suffix `*` only in v1. Full glob compliance is a v2 story.
- Honored as a **restriction filter**: when a skill is the active skill, the agent's `before_tool_callback` narrows the available tools to the intersection with `allowed-tools`. Never grants a tool not already on the agent.
- Applies to the **skill-activation window** (not the entire agent turn). The callback clears the restriction when a new turn starts without an active skill.

### Skill version pinning at attachment — latest-wins (v1)

Agents attach skills by `skill_id` only — there is **no per-attachment version pin** in v1. The skill loader resolves each ID to its `current_version` at agent-construction time. Editing a skill propagates to every attached agent on the next session, with no re-attach action. The trade-off:

- **Pro:** Authors can iterate quickly. A skill bugfix lands across all consuming agents immediately.
- **Con:** A breaking change in a new version silently affects every attached agent.

Mitigations in v1:
1. **SK-PRD-03 attachment-aware banner.** When a user begins editing a skill that is currently attached to ≥ 1 agents, the editor shows a sticky banner with the count.
2. **Save-confirmation dialog.** The "Save" / "Publish" confirm dialog repeats the count and links to the affected agents.
3. **Counts endpoint.** SK-PRD-04 ships `GET /api/v1/accounts/{account_id}/skills/{skill_id}/attached-agents-count` so the editor banner reflects current state.
4. **User guide.** `docs/skills-user-guide.md` (SK-PRD-04) has a "Skill versions and attached agents" section that calls this trade-off out prominently.

Per-attachment version pinning (`skill_ids: [{id, version}]` instead of `[id]`) is reserved for v2.

### System-owned predefined skills (SK-PRD-05)

Beyond user-authored skills, KEN-E ships predefined skills attached to the root agent and selected specialists. These are stored separately from per-account skills:

- **Firestore:** `system_skills/{skill_id}` (global, NOT under `accounts/`)
- **GCS:** `gs://kene-skills-{env}/_system/{skill_name}/{version}/` (sibling to `accounts/`)
- **Loader:** `skill_loader.load_skill(account_id, skill_id)` first checks `system_skills/{skill_id}`; on miss, falls back to the per-account path. `account_id` is still threaded through for tracing.
- **User-facing API isolation:** System skills are invisible from `GET /api/v1/accounts/{account_id}/skills` and direct GETs of system skill IDs return 404. There is no UI to author or edit them.
- **Operations:** System skills are written via Terraform (`deployment/terraform/system_skills_seed.tf`). Renames are operations events handled in Terraform diff — that's why the GCS prefix is keyed by `{skill_name}` (globally unique, ops-controlled), not `{skill_id}` (the per-account convention which absorbs arbitrary user renames).
- **Tracing:** The three skill spans (`skill.list` / `skill.load` / `skill.load_resource`) carry a `skill_owner_type: "account" | "system"` attribute so MER-E can distinguish system-skill use from user-skill use.

v1 ships exactly one placeholder system skill (`example-skill`) attached to the root agent. Real predefined-skill content (e.g., `kene-ga-attribution-checklist`) is the work of follow-up content PRDs; once SK-PRD-05 lands, those are content-only changes (one SKILL.md + one config update).

### User deletion impact (account-scoped storage)

Skills are account-scoped. When a user is deleted via DM-PRD-05's `delete_user_data(user_id)`, their `created_by` / `updated_by` IDs on `Skill` / `SkillVersion` docs become orphan references. This is acceptable — the IDs are audit-only and persist with the account. Skills does **not** register an `on_user_removed` hook (unlike Integrations). Account deletion *does* sweep `accounts/{account_id}/skills/*` via `firestore.recursive_delete` plus the matching GCS prefix purge (SK-PRD-01 AC #13).

### Audit substrate

Skills opts out of DM-PRD-07's six-audit-subcollection registry by design. Per-version `created_by` + `created_at` + `commit_message` on each `versions/{N}` doc is the audit trail. Add a dedicated audit subcollection only if v2 requirements surface (e.g., view tracking, non-version-bumping field edits).

### Sandbox gating (defense-in-depth)
- `scripts/` is **uploaded unconditionally** (SK-PRD-01 accepts the files; the `has_scripts` flag flips to `true`).
- `scripts/` can **execute** only when the owning agent has `sandbox_code_executor_enabled=true`, which attaches `AgentEngineSandboxCodeExecutor` as the agent's `code_executor`.
- Attach-time validation (SK-PRD-04) rejects `PUT/POST agent-configs` that pairs a scripts-bearing skill with a non-sandbox agent. The SkillsPicker disables scripts-bearing rows when `sandboxEnabled=false` as the first line of defense; the API enforcement is the source of truth.
- Sandbox config (network policy, resource limits, per-account vs per-session pooling) is set by the SK-PRD-00 spike findings and lives in `_build_code_executor`.
- **Test mode is NOT a sandbox.** Even dry-run / ephemeral-chat flows hit real agents, save real outputs, and incur real cost — the "test" framing is about validating outputs, not about safety. Document prominently in UX copy.

### Account scoping (enforced at every layer)
- Every `/api/v1/accounts/{account_id}/skills/*` request runs the account-access dependency — caller must be a member of `account_id`.
- Handlers additionally assert `skill.owner.account_id == path.account_id` (defense against inconsistent docs).
- Cross-account reads return 404 (not 403) to avoid leaking skill existence.
- `skill_loader.load_skill(account_id, skill_id)` requires `account_id` — never optional. The agent factory (SK-PRD-02) forwards the `account_id` it already has on `build_agent(config, account_id=...)`.

### Attach-time validation (SK-PRD-04)
Three pure functions in `skill_attach_validator.py`:
1. `check_cap(skill_ids)` — ≤ 10.
2. `check_skills_exist_in_account(requested, found)` — every id must be present in `accounts/{account_id}/skills`. Cross-account skills are simply invisible (no separate "not accessible" case).
3. `check_scripts_require_sandbox(skills, sandbox_enabled)` — if any skill has `has_scripts=true` and sandbox is off, reject with structured 422 `detail="scripts_require_sandbox"` + `offending_skill_ids`.

### Testing
- Integration tests use real Firestore (emulator OK) and real GCS (emulator or a test bucket) per CLAUDE.md T-5.
- Full CRUD round-trip: POST → GET list → GET detail → PUT v2 → GET `?version=1` → DELETE → GET list (archived excluded) → GET `?include_archived=true` (included).
- Path-traversal attempts on `GET /resources/{path}` (`..`, URL-encoded) all return 400. Covered in `test_skill_storage.py`.
- Cross-account isolation: member of both A and B cannot read a skill created in A via B's path (404); a user who is not a member returns 403 from the account-access dependency.
- End-to-end Playwright test (SK-PRD-04) covers: create skill → attach to custom agent → chat → assert response reflects the skill's instructions.
- Agent-factory integration test requires a live Gemini endpoint; marked `@pytest.mark.llm` for conditional CI execution.

### Standard shape for a project PRD in [`projects/`](./projects/)
Every PRD follows the shared 10-section structure used across the other components:

1. Context — problem this PRD solves
2. Scope — explicit in/out
3. Dependencies — other PRDs, files, services
4. Data contract — Pydantic / TypeScript types owned or consumed
5. Implementation outline — files to create / modify (table)
6. API contract — endpoints (where applicable)
7. Acceptance criteria — what "done" means
8. Test plan — unit / integration / E2E coverage
9. Risks & open questions
10. Reference — links back to sibling PRDs, AH-PRD-02 (Agent Factory), Figma

---

<!-- PRD MAINTENANCE NOTES

Updating this PRD:
- When a new feature-parent is created in Linear: add it to §5 Project Index
- When a feature-parent is completed: update its status in §5
- When architecture changes (new directories, new abstractions, new API endpoints): update §2
- When a new cross-component dependency is introduced: update §3
- When a new Figma spec or design doc section becomes relevant: update §4
- SK-PRD-00's spike findings (go / scoped-go / no-go) may revise §7 sandbox-gating and SK-PRD-02's scope — update both on receipt.

This PRD is read by the Dev Team agent during implementation planning. Keep it concise — every sentence should help a dev write better code or avoid mistakes.
-->
