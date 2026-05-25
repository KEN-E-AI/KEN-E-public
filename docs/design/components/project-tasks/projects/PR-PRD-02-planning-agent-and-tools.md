# PRD-2 — Project Planning Agent & Tools

**Status:** Ready for development (after PRD-1 merges **and AH-PRD-02 + AH-PRD-09 Phase 2 ship**)
**Owner team:** Agent / ML
**Blocked by:** PRD-1 (consumes `ProjectPlan` Pydantic schema); **[AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) — Agent Factory** (config schema); **[AH-PRD-09](../../agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md) Phase 2** (runtime resolver — `specialist_runtime.resolve_config` reads `agent_configs/project_planning` per turn; `delegate_to_specialist` is how the root reaches the planning specialist)
**Parallel with:** PRDs 3, 4, 6
**Estimated effort:** 1–2 days (reduced post-factory; config + tool functions only)

> **Prerequisites — Agent Factory + Per-Turn Dispatch.** AH-PRD-02 publishes the Firestore `agent_configs/{config_id}` schema (with `description` for description-based routing, `model`, `instruction`, `temperature`, `tools`, `mcp_servers`, `code_execution_enabled`, `skill_ids`, `sandbox_code_executor_enabled`, etc.) and the build-time ToolRegistry catalog. AH-PRD-09 Phase 2 replaces AH-PRD-02's deploy-time factory with a runtime resolver: every turn, `specialist_runtime.resolve_config(name, account_id)` reads the per-account-merged config from Firestore (cached ~60 s) and `specialist_runtime.resolve_agent(config)` constructs the `LlmAgent`. The deployed root carries one tool: `delegate_to_specialist(name, query, acceptance_criteria=None)` — it routes by LLM reasoning over each specialist's `description` rendered into a per-turn "Available Specialists" block. **There is no auto-generated `dispatch_to_project_planning()` anymore**, and the root has **no per-specialist `create_project_plan` tool wrapper** — both are obsolete under AH-PRD-09 Phase 2. **This PRD's scope:** write the Firestore config doc + Python tool functions; the runtime resolver does everything else. Do NOT hand-write an `LlmAgent`, an `AgentEntry`, a `dispatch_to_project_planning` handler, or a `_BASE_INSTRUCTION` edit on `ken_e_agent.py`.

---

## 1. Context

When a user asks KEN-E to "create a project plan for an Instagram ad campaign," the root agent dispatches via `delegate_to_specialist("project_planning", query, acceptance_criteria)` to a specialist that knows how to decompose marketing goals into structured tasks with dependencies, assignees, platforms, and timing — and then persists the result via PRD-1's API.

Post-AH-PRD-09 Phase 2, this PRD adds the specialist by authoring its Firestore config doc and tool functions. `specialist_runtime.resolve_config` reads the config per turn; `specialist_runtime.resolve_agent` constructs the `LlmAgent`; `delegate_to_specialist` wraps the specialist in a review pipeline (when criteria present) and invokes it through the inner Runner. Description-based routing (agentic-harness README §2.5) means the root picks this specialist by LLM reasoning over `agent_configs/project_planning.description` — no hand-edited `_BASE_INSTRUCTION` block, no auto-generated `dispatch_to_*` function.

## 2. Scope

### In scope
- Firestore `agent_configs/project_planning` config doc (model, instruction, temperature, **a routing-friendly `description`** that lets the root pick this specialist via the per-turn "Available Specialists" block, tools, factory flags)
- Three Python tool functions: `save_project_plan`, `update_task_status`, `get_project_plan`
- Tool registration in `tools.yaml` under a new `planning` category — the build-time ToolRegistry catalog the runtime resolver consults when assembling the specialist's roster (per AH-PRD-02 §2.5 / agentic-harness README §2.5, ToolRegistry is metadata-only at runtime)
- Unit tests for tools + a runtime-resolution integration test asserting `specialist_runtime.resolve_agent` builds the planning specialist correctly from the seeded config

### Out of scope (handled by Agent Factory / Per-Turn Dispatch runtime)
- Hand-writing an `LlmAgent` or `project_planning_agent.py` file
- Adding an `AgentEntry` to `registry.py` (runtime resolver discovers from Firestore at turn time via `available_specialists_provider`)
- Writing a `dispatch_to_project_planning` function (does not exist post-AH-PRD-09 Phase 2 — root reaches the specialist via `delegate_to_specialist("project_planning", …)`)
- Editing `_BASE_INSTRUCTION` on `ken_e_agent.py` to add a CAPABILITY block (the root's per-turn "Available Specialists" block rendered by `specialist_runtime.available_specialists_provider` carries the equivalent guidance, sourced from the config doc's `description`)
- Wiring the standard Weave tracing callbacks (runtime resolver does it; the dispatch span is `@safe_weave_op(name="delegate_to_specialist")` from AH-PRD-09)

### Out of scope (handled by other PRDs)
- The orchestration logic that runs *after* `update_task_status` is called (PRD-4)
- Any frontend display of the plan (PRD-3)
- The CRUD endpoints the tools call (PRD-1)

## 3. Dependencies

- **PRD-1:** uses `ProjectPlan` and `PlanTask` Pydantic models for tool input validation; calls `POST /api/v1/plans/{account_id}` and `PATCH /api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}`
- **[AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) — Agent Factory:** publishes the Firestore `agent_configs/{config_id}` config schema (including `description` for routing), `InstructionProvider` wrapping, the build-time ToolRegistry catalog, and the ≤30-tool roster discipline (agentic-harness README §2.5).
- **[AH-PRD-09](../../agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md) Phase 2:** provides `specialist_runtime.resolve_config`, `specialist_runtime.resolve_agent`, `delegate_to_specialist`, and `available_specialists_provider`. This PRD's planning specialist is resolved per-turn under that runtime.
- **Existing files to study:**
  - `app/adk/agents/agent_factory/specialist_runtime.py` (AH-PRD-09 Phase 2 — `resolve_config` / `resolve_agent` / `available_specialists_provider`) — **read this first**
  - `app/adk/agents/agent_factory/` (config schema, header providers, MCP toolset construction)
  - Any already-shipped specialist's Firestore `agent_configs/{config_id}` doc (e.g., `google_analytics_specialist` from AH-PRD-03) to see the config shape in practice
  - `app/adk/tools/registry/` (ToolRegistry — the build-time metadata catalog the runtime resolver reads to resolve specialist tool rosters; not a runtime filter)
- **Coordination:** PRD-4 will call `update_task_status` from its orchestrator, so the tool's response shape must include enough info for the orchestrator to determine what to dispatch next.

## 4. Data contract

### Tool inputs/outputs

`save_project_plan(plan_data: dict) -> dict`
- Input: dict matching `ProjectPlan` schema (validated via `ProjectPlan.model_validate`)
- Output: `{"status": "success", "plan_id": str, "message": str}` or `{"status": "error", "error": str}`

`update_task_status(plan_id: str, task_id: str, new_status: str, completion_notes: str | None = None, revision_comment: str | None = None) -> dict`
- Input: as listed
- Output: `{"status": "success", "task": {...updated task...}, "newly_unblocked_tasks": [...task_ids...]}` (the unblock list is computed by the orchestrator in PRD-4; in PRD-2 the tool can return an empty list as a placeholder until PRD-4 wires it up)

`get_project_plan(plan_id: str) -> dict`
- Input: `plan_id`
- Output: full `ProjectPlan` dict or `{"status": "error", "error": "not_found"}`

### Dispatch return shape
Post-AH-PRD-09 Phase 2, the root invokes the planning specialist via `delegate_to_specialist("project_planning", query, acceptance_criteria)`. The standard shape (assistant message string + Weave span chain `delegate_to_specialist → load_config_from_firestore → review loop → specialist + reviewer`) is established by AH-PRD-09 and reused unchanged here. This PRD does not redefine it; PRD-4's orchestrator consumes the specialist's tool-call output (`update_task_status` return) the same way it would under any dispatch model.

## 5. Implementation outline

| Action | File / target |
|--------|---------------|
| Create | `app/adk/agents/project_planning_tools.py` — the three Python tool functions |
| Create | Firestore `agent_configs/project_planning` config doc (seed via deploy or admin script). The `description` field must be rich enough to drive description-based routing — see §6 |
| Modify | `app/adk/tools/registry/config/tools.yaml` — add `planning` category with the three tools so the runtime resolver picks them up when assembling the planning specialist's roster |
| Create | `tests/unit/agents/test_project_planning_tools.py` — tool unit tests |
| Create | `tests/integration/test_project_planning_runtime_resolution.py` — seed the Firestore config; call `specialist_runtime.resolve_config("project_planning", account_id)` + `specialist_runtime.resolve_agent(config)`; assert the constructed `LlmAgent` carries the expected model, instruction, three tools, and standard callbacks |

**Files NOT modified by this PRD** (owned by AH-PRD-02 / AH-PRD-09):
- `app/adk/agents/ken_e_agent.py` — deleted by AH-PRD-09 Phase 5 once verified unused; no `_BASE_INSTRUCTION` CAPABILITY block added. Routing guidance lives in the planning config doc's `description` field.
- `app/adk/agents/utils/dispatch_handlers.py` — no `dispatch_to_project_planning` function exists post-AH-PRD-09 Phase 2. The root reaches the planning specialist via `delegate_to_specialist("project_planning", ...)`.

### Agent config doc (Firestore `agent_configs/project_planning`)
Follows the Agent Factory's config schema from AH-PRD-02. Required fields:
- `config_id`: `"project_planning"`
- `model`: `gemini-2.0-flash`
- `instruction`: see §6 below (the factory wraps this in `InstructionProvider` for `organization_context` injection at runtime)
- `temperature`: `0.3` (planning benefits from determinism; tune in eval)
- `tools`: `["save_project_plan", "update_task_status", "get_project_plan"]`
- `code_execution`: `false`
- `description`: `"Specialist agent for creating and managing project plans"`
- `capabilities`: `["planning", "project_management"]`
- `available_to_copy`: `true` (per AH-PRD-02 story 2.2-7 — users can fork this into a custom agent)
- `automatically_available`: `true` (all accounts get it by default)
- `visible_in_frontend`: `true` (shows on Workflows → Agents page)

Because this is a config doc in global scope, accounts may override specific fields via `accounts/{account_id}/agent_configs/project_planning` (shallow-merge overlay, AH-PRD-02 story 2.2-8). No work required in this PRD beyond authoring the global doc.

### Routing guidance (in the config doc's `description`)
Under AH-PRD-09 Phase 2, the root agent picks specialists by LLM reasoning over each specialist's `description` rendered into a per-turn "Available Specialists" block by `specialist_runtime.available_specialists_provider`. No `_BASE_INSTRUCTION` edits are needed. The planning specialist's description should make routing obvious:

```
description: |
  Specialist agent for creating and managing project plans. Use for queries
  about: creating a project plan, work breakdown, or task list; planning a
  marketing campaign, product launch, or initiative; organizing work across
  team members and agents; breaking down complex goals into actionable steps.
```

Equivalent guidance to the legacy CAPABILITY block, but stored in the config doc rather than hand-edited into a Python file — admin edits propagate to the next chat turn within ~60 s without redeploy (per AH-PRD-09 AC #5).

## 6. Agent instruction (key behaviors)

The instruction provider must guide the model to:
1. Ask clarifying questions when the request is ambiguous (goal, audience, budget, timeline)
2. Define a measurable goal and acceptance criteria
3. Decompose into discrete tasks; for each task set: `assignee_type` + `assignee_name`, `platform` (if applicable), `cost` (if applicable), `due_date`, `launch_time_utc` (if execution timing matters), `depends_on`
4. Validate `assignee_name` against the agent registry when `assignee_type == "agent"` (the `_validate_agent_assignee` helper from PRD-2 should consult `app.adk.agents.registry`)
5. Optionally assign `campaign` and `tags`
6. Emit JSON matching the `ProjectPlan` schema
7. Call `save_project_plan` to persist
8. Respond to the user with a confirmation containing a clickable deep link `/calendar?project={plan_id}` (rendered by frontend per PRD-3)

The instruction string is stored on the `agent_configs/project_planning` Firestore doc. At specialist-construction time (`specialist_runtime.resolve_agent`, AH-PRD-09 Phase 2) the runtime resolver wraps it in an `InstructionProvider` closure that injects `organization_context` from `tool_context.state` — this PRD does not need to write its own loader or provider.

## 7. Acceptance criteria

1. **Runtime resolution:** With the Firestore config seeded, `specialist_runtime.resolve_config("project_planning", account_id)` returns a `MergedAgentConfig` matching the seeded shape, and `specialist_runtime.resolve_agent(config)` constructs an `LlmAgent` with the expected model, instruction (wrapped in `InstructionProvider`), temperature, and the three tools bound.
2. **Reachable via `delegate_to_specialist`:** Within ~60 s of the Firestore write, the runtime `available_specialists_provider` renders `project_planning` into the root's "Available Specialists" block. The root reaches the planning specialist via `delegate_to_specialist("project_planning", query, acceptance_criteria)`. No `dispatch_to_project_planning()` exists; no per-specialist root tool wrapper exists.
3. **End-to-end routing:** Sending a chat message "create a project plan for a new product launch" produces a Weave trace with the expected hierarchy: root → `delegate_to_specialist` span → `load_config_from_firestore` → review-loop iterations (if criteria) → planning specialist → tool calls.
4. The agent produces a JSON object that validates against `ProjectPlan.model_validate` (no schema errors).
5. `save_project_plan` writes a plan to the API and returns the `plan_id`.
6. `update_task_status` writes to the API; the response shape is what PRD-4 expects (even if `newly_unblocked_tasks` is empty in this PRD).
7. Agent instruction warns the model away from cycles and from non-existent agent assignees.
8. All new unit and integration tests pass.

## 8. Test plan

**Unit tests:**
- Each tool: success path, validation failure, API error propagation
- Instruction content: the config doc's instruction string contains the required keywords ("acceptance criteria", "depends_on", "assignee_name")

**Runtime-resolution integration tests (new):**
- Seed the Firestore `agent_configs/project_planning` doc (fixture); call `specialist_runtime.resolve_config("project_planning", account_id)` + `specialist_runtime.resolve_agent(config)` — assert the constructed `LlmAgent` carries the expected model, instruction (wrapped in `InstructionProvider`), the three tools, the standard Weave tracing callbacks, and `description` matching the seeded value.
- `available_specialists_provider(account_id)` includes the planning specialist's name + description in its rendered block within the ~60 s cache TTL after the Firestore write.
- `delegate_to_specialist("project_planning", query, criteria)` invokes the resolved specialist via the inner Runner, wraps in `build_review_pipeline()` when criteria present, and returns the standard assistant-message + Weave span shape.

**End-to-end** (deferred to PRD-5, smoke test here):
- chat message → root → `delegate_to_specialist` → resolved planning specialist → `save_project_plan` → API → Firestore (mock the API client or use the real one against a test account).

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Agent emits invalid JSON or violates DAG | PRD-1's Pydantic validator rejects; `save_project_plan` returns the error so the agent can self-correct (re-prompt loop is built into ADK) |
| Agent assigns tasks to non-existent specialist agents | `_validate_agent_assignee` helper consults registry; tool returns clear error so model retries with a valid name |
| Long planning sessions hit token limits | `gemini-2.0-flash` 1M context handles this for v1; evaluate if user reports truncation |
| Instruction drift across model versions | Firestore config doc allows quick iteration without redeploy; eval scores tracked in MER-E |

## 10. Reference

- Parent plan: [`../../../project-planning-implementation-plan.md`](../../../project-planning-implementation-plan.md) §Agent Design, §ADK Tools, §Implementation Phases (Phase 2)
- Blocking prerequisite: [AH-PRD-02 — Agent Factory](../../agentic-harness/projects/AH-PRD-02-agent-factory.md)
- Pattern to mirror: `app/adk/agents/agent_factory/` (factory + config schema); any already-factoryized specialist's `agent_configs/{config_id}` config doc
- CLAUDE.md rules in scope: PY-1, PY-2 (Python); T-1, T-4, T-6 (testing); C-2, C-4 (naming/composition)
