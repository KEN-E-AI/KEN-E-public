# PRD-2 — Project Planning Agent & Tools

**Status:** Ready for development (after PRD-1 merges **and AH-PRD-02 ships**)
**Owner team:** Agent / ML
**Blocked by:** PRD-1 (consumes `ProjectPlan` Pydantic schema); **[AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) — Agent Factory** (the agent is assembled from config, not hand-written)
**Parallel with:** PRDs 3, 4, 6
**Estimated effort:** 1–2 days (reduced post-factory; config + tool functions only)

> **Prerequisite — [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) (Agent Factory):** After AH-PRD-02 ships, specialist agents are assembled at deploy time by `agent_factory.build_hierarchy()` reading Firestore `agents/{agent_id}` docs. The factory auto-generates `dispatch_to_{specialist}()`, wraps the instruction in `InstructionProvider`, wires the four standard callbacks (including `before_agent_callback` → `ToolRegistry.search` for tool filtering), and registers the dispatch function as a root-agent tool. **This PRD's scope is therefore narrowed:** write the Firestore config doc + Python tool functions; the factory does everything else. Do NOT hand-write an `LlmAgent`, an `AgentEntry`, or a `dispatch_to_project_planning` handler.

---

## 1. Context

When a user asks KEN-E to "create a project plan for an Instagram ad campaign," the root agent (`ken_e_agent`) needs to dispatch the request to a specialist agent that knows how to decompose marketing goals into structured tasks with dependencies, assignees, platforms, and timing — and then persist the result via PRD-1's API.

Post-AH-PRD-02, this PRD adds the specialist by authoring its Firestore config doc and tool functions. The Agent Factory takes it from there: instantiating the `LlmAgent`, generating `dispatch_to_project_planning()`, wiring callbacks, and registering the dispatch as a root-agent tool.

## 2. Scope

### In scope
- Firestore `agents/project_planning` config doc (model, instruction, temperature, tools, callbacks, factory flags)
- Three Python tool functions: `save_project_plan`, `update_task_status`, `get_project_plan`
- Tool registration in `tools.yaml` under a new `planning` category (so `ToolRegistry.search` can surface them)
- New CAPABILITY block appended to `_BASE_INSTRUCTION` in `ken_e_agent.py` — the factory auto-registers the dispatch tool, but the root-agent narrative instruction that tells the model *when* to invoke `create_project_plan` is still hand-edited
- Unit tests for tools + a factory-integration test asserting the agent is assembled correctly from the seeded config

### Out of scope (handled by the Agent Factory)
- Hand-writing an `LlmAgent` or `project_planning_agent.py` file
- Adding an `AgentEntry` to `registry.py` (factory auto-discovers from Firestore)
- Writing a `dispatch_to_project_planning` function in `dispatch_handlers.py` (factory auto-generates it with `@safe_weave_op()` tracing)
- Wiring the four standard callbacks (factory does it)

### Out of scope (handled by other PRDs)
- The orchestration logic that runs *after* `update_task_status` is called (PRD-4)
- Any frontend display of the plan (PRD-3)
- The CRUD endpoints the tools call (PRD-1)

## 3. Dependencies

- **PRD-1:** uses `ProjectPlan` and `PlanTask` Pydantic models for tool input validation; calls `POST /api/v1/plans/{account_id}` and `PATCH /api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}`
- **[AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) — Agent Factory:** provides `agent_factory.build_hierarchy()`, the Firestore `agents/{agent_id}` config schema, auto-generated dispatch functions, `InstructionProvider` wrapping, and `ToolRegistry.search`-driven tool filtering. This PRD assumes all of the above has shipped and is the deploy-time default in `deploy_ken_e.py`.
- **Existing files to study:**
  - `app/adk/agents/agent_factory/` (the factory itself — config schema, build_hierarchy, dispatch generation) — **read this first**
  - `app/adk/agents/ken_e_agent.py` (root agent `_BASE_INSTRUCTION` — only the CAPABILITY block is hand-edited here)
  - Any already-factoryized specialist's Firestore `agents/{agent_id}` doc to see the config shape in practice
  - `app/adk/tools/registry/` (ToolRegistry — the tool filter mechanism the factory wires)
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

### Dispatch handler return shape
The factory-generated `dispatch_to_project_planning()` follows the standard shape already established by other factory-built specialists. This PRD does not redefine it; the orchestrator (PRD-4) consumes whatever the factory produces.

## 5. Implementation outline

| Action | File / target |
|--------|---------------|
| Create | `app/adk/agents/project_planning_tools.py` — the three Python tool functions |
| Create | Firestore `agents/project_planning` config doc (seed via deploy or admin script) |
| Modify | `app/adk/tools/registry/config/tools.yaml` — add `planning` category with the three tools so `ToolRegistry.search` can surface them |
| Modify | `app/adk/agents/ken_e_agent.py` `_BASE_INSTRUCTION` — append the CAPABILITY block below (factory registers the dispatch tool itself, but the narrative guidance that tells the model *when* to invoke it lives in this instruction) |
| Create | `tests/unit/agents/test_project_planning_tools.py` — tool unit tests |
| Create | `tests/integration/test_project_planning_factory_build.py` — assert `build_hierarchy()` produces the planning agent with the expected model, tools, callbacks, and dispatch wiring when the Firestore config is seeded |

### Agent config doc (Firestore `agents/project_planning`)
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

### Root agent instruction (new CAPABILITY block in `_BASE_INSTRUCTION`)
The factory auto-registers the dispatch function as a root-agent tool, but the narrative that tells the root model when to call it is hand-written in `_BASE_INSTRUCTION`:
```
**CAPABILITY N - Project Planning:**
Use `create_project_plan` for queries about:
- Creating a project plan, work breakdown, or task list
- Planning a marketing campaign, product launch, or initiative
- Organizing work across team members and agents
- Breaking down complex goals into actionable steps
```

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

The instruction string is stored on the `agents/project_planning` Firestore doc. At build time the Agent Factory (AH-PRD-02) wraps it in an `InstructionProvider` closure that injects `organization_context` from `tool_context.state` — this PRD does not need to write its own loader or provider.

## 7. Acceptance criteria

1. With the Firestore config seeded, `agent_factory.build_hierarchy()` produces a `project_planning` agent with the expected model, instruction (wrapped in `InstructionProvider`), temperature, and the three tools bound
2. The factory auto-generates `dispatch_to_project_planning()` and registers it as a root-agent tool (verified via the factory's existing integration test + a new per-PRD assertion)
3. Sending a chat message "create a project plan for a new product launch" routes through the auto-generated dispatch (verified via Weave trace)
4. The agent produces a JSON object that validates against `ProjectPlan.model_validate` (no schema errors)
5. `save_project_plan` writes a plan to the API and returns the `plan_id`
6. `update_task_status` writes to the API; the response shape is what PRD-4 expects (even if `newly_unblocked_tasks` is empty in this PRD)
7. Agent instruction warns the model away from cycles and from non-existent agent assignees
8. All new unit and integration tests pass

## 8. Test plan

**Unit tests:**
- Each tool: success path, validation failure, API error propagation
- Instruction content: the config doc's instruction string contains the required keywords ("acceptance criteria", "depends_on", "assignee_name")

**Factory integration tests (new):**
- Seed the Firestore `agents/project_planning` doc (fixture) and call `agent_factory.build_hierarchy()` — assert the returned hierarchy includes the planning specialist with the expected model, the three tools, the four standard callbacks, and an auto-generated `dispatch_to_project_planning()` registered as a root-agent tool
- Dispatch generation: calling the auto-generated dispatch returns the factory's standard return shape

**End-to-end** (deferred to PRD-5, smoke test here):
- chat message → factory-generated dispatch → agent → `save_project_plan` → API → Firestore (mock the API client or use the real one against a test account)

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
- Pattern to mirror: `app/adk/agents/agent_factory/` (factory + config schema); any already-factoryized specialist's `agents/{agent_id}` config doc
- CLAUDE.md rules in scope: PY-1, PY-2 (Python); T-1, T-4, T-6 (testing); C-2, C-4 (naming/composition)
