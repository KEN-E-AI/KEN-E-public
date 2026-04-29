# Feature 2.6 — User-Authored Skills: Implementation Plan

> ⚠️ **SUPERSEDED — DO NOT USE FOR NEW WORK.** This document is retained as historical record of the original Feature 2.6 design (April 2026). The authoritative spec is now:
> - [`README.md`](./README.md) — current architecture, conventions, project index
> - [`projects/SK-PRD-00`](./projects/SK-PRD-00-skills-experiment.md) through [`SK-PRD-05`](./projects/SK-PRD-05-predefined-skill-foundation.md) — six implementation PRDs
>
> Specifically, this plan reflects the legacy **user-scoped** storage model (`gs://kene-skills-{env}/users/{user_id}/{skill}/{ver}/`, root `skills/{skill_id}` Firestore collection). The current model is **account-scoped Shape B** (`accounts/{account_id}/skills/{skill_id}` Firestore subcollection + GCS prefix keyed by `skill_id`). See `README.md` and SK-PRD-01 for the live data model. Predefined system-owned skills are owned by SK-PRD-05.
>
> **For historical context only.** Do not edit or extend this file.

---

## Original (April 2026) header

> **Status (2026-04-19):** This plan is split into 5 independently shippable PRDs in [`projects/`](./projects/) for parallel execution by multiple dev teams. See [`README.md`](./README.md) for the dependency graph and team workflow.
>
> **Prerequisite:** [AH-PRD-02](../agentic-harness/projects/AH-PRD-02-agent-factory.md) (Agent Factory) must ship the **forward-compat schema fields** (`skill_ids`, `sandbox_code_executor_enabled`) before Sprint 2.6-B (Agent Integration) can start. All other Skills PRDs can run in parallel with AH-PRD-02.

---

## 1. Context

A **Skill** is a self-contained unit of instructions (and optional reference materials, assets, and scripts) that an agent loads via progressive disclosure to perform a specific task. Skills follow the open [agentskills.io specification](https://agentskills.io/specification) and are integrated into the Google ADK via `SkillToolset` (ADK v1.25.0+, experimental).

Today, a KEN-E specialist agent's instructions are baked into its Firestore `agent_configs` document. Any domain expertise that isn't universal must either bloat that instruction or be coded into a tool. Neither scales — the instruction field doesn't have the token budget, and every new tool needs engineering effort.

Feature 2.6 gives end-users a way to **capture and reuse their domain expertise** as modular, agent-loadable Skills. A user authors a SKILL.md file (with optional reference files and executable scripts) in the Workflows UI, saves it, and attaches it to a custom specialist agent in the Agent Builder (delivered by [AH-PRD-02](../agentic-harness/projects/AH-PRD-02-agent-factory.md) — Agent Factory). When that agent runs, the ADK's `SkillToolset` auto-generates discovery tools (`list_skills`, `load_skill`, `load_skill_resource`) so the agent loads only the skill it needs, when it needs it.

### What "Skills" is, and isn't

| Skills IS | Skills is NOT |
|---|---|
| A way for users to package instructions + references for their specialist agents | A way to add new tools to agents (tools are still code) |
| Progressive — L1 metadata at agent start, L2 body on activation, L3 on-demand | A replacement for the system prompt |
| Scoped per agent — each custom agent attaches a finite list of skills | A global prompt library |
| Sandboxed when `scripts/` are involved, via `AgentEngineSandboxCodeExecutor` | A general-purpose code execution feature |
| Personal in v1, with a forward-compat data model for future org sharing | A marketplace or cross-account import system |

## 2. Architectural overview

```
┌─────────────────────┐                                      ┌────────────────────────┐
│  Frontend           │                                      │   KEN-E Backend         │
│  (Workflows)        │                                      │                         │
│                     │                                      │  Firestore              │
│  ┌───────────────┐  │  POST /api/v1/skills                 │  ┌──────────────────┐   │
│  │ Skills tab    │──┼──────────────────────────────────────┼─▶│ skills/{skill_id}│   │
│  │ (author+edit) │  │  GET  /api/v1/skills                 │  │ metadata doc     │   │
│  └───────────────┘  │  GET  /api/v1/skills/{id}/content    │  └──────────────────┘   │
│                     │  GET  /api/v1/skills/{id}/res/{path} │                         │
│  ┌───────────────┐  │  PUT  /api/v1/skills/{id}            │  GCS                    │
│  │ Agent Builder │  │  DELETE /api/v1/skills/{id}          │  ┌──────────────────┐   │
│  │ (skill picker │──┼──────────────────────────────────────┼─▶│ kene-skills-{env}│   │
│  │  + sandbox    │  │                                      │  │  /users/{uid}/   │   │
│  │  toggle)      │  │                                      │  │    {skill}/      │   │
│  └───────────────┘  │                                      │  │      {ver}/      │   │
└─────────────────────┘                                      │  │        SKILL.md  │   │
                                                             │  │        refs/…    │   │
                                                             │  │        assets/…  │   │
                                                             │  │        scripts/…*│   │
                                                             │  └──────────────────┘   │
                                                             │                         │
                                                             │  Agent Factory          │
                                                             │  ┌──────────────────┐   │
                                                             │  │ build_agent(cfg) │   │
                                                             │  │  reads           │   │
                                                             │  │    skill_ids[] ──┼─┐ │
                                                             │  │  reads           │   │ │
                                                             │  │    sandbox_      │   │ │
                                                             │  │    code_exec     │   │ │
                                                             │  └──────────────────┘   │ │
                                                             │         │               │ │
                                                             │         ▼               │ │
                                                             │  ┌──────────────────┐   │ │
                                                             │  │ SkillToolset     │◀──┼─┘
                                                             │  │  [L1 metadata    │   │
                                                             │  │   for all skills │   │
                                                             │  │   attached]      │   │
                                                             │  └──────────────────┘   │
                                                             │         │               │
                                                             │         ▼               │
                                                             │  ┌──────────────────┐   │
                                                             │  │ LlmAgent         │   │
                                                             │  │  ├ code_executor=│   │
                                                             │  │  │  AgentEngine  │   │
                                                             │  │  │  Sandbox…*    │   │
                                                             │  │  ├ tools=[…]     │   │
                                                             │  │  └ allowed-tools │   │
                                                             │  │    filter        │   │
                                                             │  └──────────────────┘   │
                                                             └────────────────────────┘

*`scripts/` upload is only permitted when sandbox_code_executor_enabled=true on the
 specialist agent. See Phase 0 Decision 2.
```

### Three architectural pillars

1. **Storage split** — skill *metadata* (name, description, owner, version, status) lives in Firestore; skill *content* (SKILL.md + references + assets + scripts) lives in GCS with a per-version immutable layout. Metadata is queried on every agent session for L1 discovery; content is streamed on demand.
2. **Progressive disclosure via SkillToolset** — The ADK's `SkillToolset` auto-generates three tools (`list_skills`, `load_skill`, `load_skill_resource`). The agent navigates: scan L1 descriptions → load L2 body for a relevant skill → load L3 resources as the body cites them. Our job is to hydrate `SkillToolset` with the user's selected skills at agent-construction time and serve L3 content lazily from GCS.
3. **Gated execution** — `scripts/` cannot run unless the owning agent is configured with `sandbox_code_executor_enabled=true`, which wires a `code_executor=AgentEngineSandboxCodeExecutor(...)`. This makes code execution a deliberate, agent-level opt-in rather than a per-skill surprise.

## 3. Phase 0 decisions (settled)

| # | Decision | Outcome |
|---|---|---|
| 1 | **Scope boundary** | Personal-only in v1. Data model is sharing-ready (`owner`, `visibility`, `shared_with` fields exist; enum currently single-value). Sharing UI lands in v2. |
| 2 | **`scripts/` execution** | Gated on the owning agent's `sandbox_code_executor_enabled` flag, wired to `AgentEngineSandboxCodeExecutor`. Scripts upload is accepted by the API only when the skill is attached to an agent with sandbox enabled (enforced at attach-time, not upload-time — see Sprint 2.6-A §9). |
| 3 | **`allowed-tools` bridging** | Honored as a **restriction filter only**. A skill's `allowed-tools` can only narrow the set of tools the agent already has; it can never grant a new tool. |
| 4 | **Loading model** | Agent-scoped. Each specialist agent attaches up to **10** skills (hard cap). All attached skills' L1 metadata is loaded at session start (~1kB / skill). No session-wide or global loading. |
| 5 | **Agent placement** | Root agent has system-owned skills users cannot modify. User-authored skills may only be attached to **user-created custom specialist agents** (per [AH-PRD-02](../agentic-harness/projects/AH-PRD-02-agent-factory.md) §5.2). |
| 6 | **skills.sh import** | **Deferred to v2.** No skill import in v1 — users author skills natively. Import design will involve per-GitHub-repo licensing, attribution preservation, and prompt-injection content scanning. |

When SK-PRD-* implementation begins, decisions captured above are recorded as Review entries in [`docs/design/DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md).

## 4. Data model headlines

Full detail in [SK-PRD-01 — Skills Backend](./projects/SK-PRD-01-skills-backend.md). Headlines:

**Firestore `skills/{skill_id}`:**
- `skill_id: str` (UUID)
- `owner: {type: "user", id: str}`
- `name: str` (kebab-case, matches frontmatter)
- `description: str`
- `current_version: int`
- `visibility: Literal["private"]` (enum; `"org"` reserved for v2)
- `status: Literal["draft", "published", "archived"]`
- `source: {type: "authored"} | {type: "github", repo: str, sha: str, license: str} | None` (v2 fills `github` variant)
- `metadata: dict | None`
- `created_at`, `updated_at`, `created_by`, `updated_by`

**GCS layout:**
```
gs://kene-skills-{env}/
  users/{user_id}/{skill_name}/{version}/
    SKILL.md              # required; YAML frontmatter + Markdown body
    references/           # optional L3 files
    assets/               # optional L3 files
    scripts/              # optional L3 files; only usable when agent has sandbox
    .manifest.json        # generated: file list + checksums + size
```

**Agent config extensions (delivered by AH-PRD-02 forward-compat):**
- `skill_ids: list[str]` (default `[]`, max 10)
- `sandbox_code_executor_enabled: bool` (default `false`)

## 5. API surface summary

| Method | Path | PRD |
|---|---|---|
| `POST` | `/api/v1/skills` (multipart: `SKILL.md` + `files[]`) | 01 |
| `GET` | `/api/v1/skills` (list owner's skills, filters) | 01 |
| `GET` | `/api/v1/skills/{skill_id}` (metadata) | 01 |
| `GET` | `/api/v1/skills/{skill_id}/content` (SKILL.md body) | 01 |
| `GET` | `/api/v1/skills/{skill_id}/resources/{rel_path}` (L3 file) | 01 |
| `PUT` | `/api/v1/skills/{skill_id}` (new version) | 01 |
| `DELETE` | `/api/v1/skills/{skill_id}` (soft-archive) | 01 |
| `POST` | `/api/v1/skills/validate` (dry-run spec validation) | 01 |

The agent-config endpoints (`/api/v1/accounts/{account_id}/agent-configs/*`) are delivered by [AH-PRD-02](../agentic-harness/projects/AH-PRD-02-agent-factory.md) (story 2.2-8). Sprint 2.6-D extends them to accept `skill_ids` and `sandbox_code_executor_enabled` in request/response bodies.

## 6. Sprint breakdown

5 sprints, explicitly numbered to maximize parallelism:

| Sprint | Title | PRD | Team | Effort |
|---|---|---|---|---|
| **2.6-0** | Sandbox Spike | [SK-PRD-00](./projects/SK-PRD-00-skills-experiment.md) | Platform + Security | 3–5 days |
| **2.6-A** | Skills Backend — Storage, API, Loader | [SK-PRD-01](./projects/SK-PRD-01-skills-backend.md) | Backend | 6–8 days |
| **2.6-B** | Agent Factory — Skills & Sandbox Integration | [SK-PRD-02](./projects/SK-PRD-02-agent-integration.md) | Agent Platform | 5–7 days |
| **2.6-C** | Skills Authoring UI | [SK-PRD-03](./projects/SK-PRD-03-authoring-ui.md) | Frontend | 6–8 days |
| **2.6-D** | Agent Builder Controls + E2E | [SK-PRD-04](./projects/SK-PRD-04-agent-builder-controls.md) | Frontend + Backend | 4–5 days |

## 7. Dependencies on AH-PRD-02 (Agent Factory)

[AH-PRD-02](../agentic-harness/projects/AH-PRD-02-agent-factory.md) must absorb two small, additive schema changes **before Sprint 2.6-B can start**. Neither requires new UI or endpoint behavior from AH-PRD-02 — they are data-layer placeholders that Sprint 2.6-B, 2.6-C, and 2.6-D then light up.

### Ask 1 — Story 2.2-1 (Config-driven agent constructor)

**Add two fields to the agent config schema:**

```python
skill_ids: list[str] = Field(default_factory=list, max_length=10)
sandbox_code_executor_enabled: bool = False
```

**Constructor behavior:**
- Reads `skill_ids`; does not yet construct a `SkillToolset` (that wiring lands in 2.6-B). Emits a structured log if list is non-empty pre-2.6-B so operators know attached-but-unwired skills are being skipped.
- Reads `sandbox_code_executor_enabled`; when `true`, sets `code_executor=AgentEngineSandboxCodeExecutor(sandbox_resource_name=...)` on the constructed `LlmAgent`.
- The existing `code_execution_enabled` flag (Gemini's `ToolCodeExecution`) is **distinct** and remains for its existing purpose. The two flags may be set independently.

**Migration:** Every existing `agent_configs/{config_id}` document gains `skill_ids: []` and `sandbox_code_executor_enabled: false` via the same migration step used for `available_to_copy` / `automatically_available` / `visible_in_frontend` in story 2.2-7.

### Ask 2 — Story 2.2-10 (Customization UI) and Story 2.2-11 (AgentCreatePage)

**Add two read-only placeholder rows to the agent edit/create form:**
- "Skills: *(none)*" — disabled state, with a tooltip "Available in Feature 2.6"
- "Sandbox code execution: *disabled*" — disabled toggle, same tooltip

This reserves layout space so Sprint 2.6-D adds interactive controls without redesigning the form. No API calls, no state management.

### Ask 3 — Story 2.2-8 (Per-account agent config CRUD API)

**Accept (but ignore until 2.6-D) the two new fields in `PUT /api/v1/accounts/{account_id}/agent-configs/{config_id}` and `POST /api/v1/accounts/{account_id}/agent-configs/` request bodies.**

Pydantic validation passes the fields through to Firestore with defaults. Sprint 2.6-D adds the enforcement logic (attach-time sandbox-required-for-scripts check, skill ownership check).

## 8. Verification plan

A verification report appended to the bottom of this plan when all 5 PRDs ship. Each PRD's acceptance criteria → its verifying test.

## 9. Risks

| Risk | Mitigation |
|---|---|
| `SkillToolset` is experimental (ADK v1.25.0+) and its API may change | Pin the ADK version at the start of Sprint 2.6-B; isolate `SkillToolset` construction in one helper so upstream changes have a single edit point; build integration tests that exercise `list_skills` / `load_skill` / `load_skill_resource` end-to-end so breakage surfaces fast. |
| `AgentEngineSandboxCodeExecutor` network egress policy unknown — could be an exfil vector | Sprint 2.6-0 spike explicitly resolves this before Sprint 2.6-B commits to the wiring. |
| Per-session sandbox cost could be surprising | Sprint 2.6-0 spike measures real cost per session for representative workloads. |
| User skill descriptions are prompt-injection surface | Heuristic scan on save (reject obvious injections); all user-authored content is rendered to agents with a system-level wrapper noting the source is user-provided; MER-E evaluation framework tracks skill-triggered sessions so poisoned skills surface in quality metrics. |
| SkillToolset L1 metadata budget: 10 skills × ~100 tokens = ~1kB adds up across many sessions | 10-skill hard cap already in place (Phase 0 decision #4). Monitor actual L1 token count in tracing; tighten if needed. |
| Users attach a skill with `scripts/` to an agent without sandbox enabled, expecting them to run | Attach-time validation: the `PUT agent-configs` endpoint rejects a `skill_ids` list containing a skill with `scripts/` when the target agent has `sandbox_code_executor_enabled=false`. Clear error message names the offending skill and the required toggle. |
| A user transfers a custom specialist between accounts later (or we add it), and the attached skills go missing | Skills are attached by ID; the agent-config API rejects a PUT containing a `skill_id` the owner cannot access. Clean surface to extend to org-shared skills later. |

## 10. Reference

- Research — [Google ADK Skills overview](https://adk.dev/skills/)
- Research — [Developer's guide to ADK skills](https://developers.googleblog.com/developers-guide-to-building-adk-agents-with-skills/)
- Spec — [agentskills.io specification](https://agentskills.io/specification)
- Agent Engine Code Execution — [`adk.dev/integrations/code-exec-agent-engine`](https://adk.dev/integrations/code-exec-agent-engine/)
- Parent project — [AH-PRD-02](../agentic-harness/projects/AH-PRD-02-agent-factory.md) (Agent Factory)
- Sibling docs — [`../agentic-harness/README.md`](../agentic-harness/README.md) §2 Architecture, §2.5 Tool-assignment model; [AH-PRD-02](../agentic-harness/projects/AH-PRD-02-agent-factory.md) §4 Data contract, §5.2 Config-to-constructor mapping
- Figma — [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) (Workflows page, Agents tab)
