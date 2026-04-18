# PRD-2 — Project Planning Agent & Tools

**Status:** Ready for development (after PRD-1 merges)
**Owner team:** Agent / ML
**Blocked by:** PRD-1 (consumes `ProjectPlan` Pydantic schema)
**Parallel with:** PRDs 3, 4, 6
**Estimated effort:** 2–3 days

---

## 1. Context

When a user asks KEN-E to "create a project plan for an Instagram ad campaign," the root agent (`ken_e_agent`) needs to dispatch the request to a specialist agent that knows how to decompose marketing goals into structured tasks with dependencies, assignees, platforms, and timing — and then persist the result via PRD-1's API.

This PRD adds that specialist agent and its tools, following the same pattern as existing dispatch handlers (`dispatch_to_company_news`, `dispatch_to_google_analytics`).

## 2. Scope

### In scope
- New `LlmAgent` for project planning, configured via Firestore agent config doc
- Three ADK tools: `save_project_plan`, `update_task_status`, `get_project_plan`
- Registry entry + dispatch handler
- Root agent integration (new tool function + new CAPABILITY block in `_BASE_INSTRUCTION`)
- Tool registration in tools YAML
- Unit tests for tools, dispatch wiring, and instruction prompt

### Out of scope
- The orchestration logic that runs *after* `update_task_status` is called (PRD-4)
- Any frontend display of the plan (PRD-3)
- The CRUD endpoints the tools call (PRD-1)

## 3. Dependencies

- **PRD-1:** uses `ProjectPlan` and `PlanTask` Pydantic models for tool input validation; calls `POST /api/v1/plans/{account_id}` and `PATCH /api/v1/plans/{account_id}/{plan_id}/tasks/{task_id}`
- **Existing files to study:**
  - `app/adk/agents/registry.py` (AgentEntry pattern)
  - `app/adk/agents/utils/dispatch_handlers.py` (specifically `dispatch_to_company_news`)
  - `app/adk/agents/ken_e_agent.py` (root agent tools + `_BASE_INSTRUCTION`)
  - `app/adk/agents/strategy_agent/config_loader.py` (Firestore config doc loading via `load_config_from_firestore`)
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

### Dispatch handler return shape (matches existing pattern)
```
{
  "status": "success" | "error",
  "query": str,
  "result": <agent output>,
  "source": "project_planning_specialist",
  "agent": "project_planning"
}
```

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `app/adk/agents/project_planning_agent.py` |
| Create | `app/adk/agents/project_planning_tools.py` |
| Modify | `app/adk/agents/registry.py` — add `AgentEntry` |
| Modify | `app/adk/agents/utils/dispatch_handlers.py` — add `dispatch_to_project_planning` |
| Modify | `app/adk/agents/ken_e_agent.py` — add `create_project_plan` tool + new CAPABILITY block |
| Modify | `app/adk/tools/registry/config/tools.yaml` — add `planning` category |
| Create | Firestore doc `agent_configs/project_planning_agent` (seed via deploy or admin script) |
| Create | `tests/unit/agents/test_project_planning_tools.py` |
| Create | `tests/unit/agents/test_project_planning_agent_wiring.py` |

### Agent config (Firestore `agent_configs/project_planning_agent`)
- `model`: `gemini-2.0-flash`
- `thinking_config`: `{"include_thoughts": true}` (matches root agent)
- `instruction`: see §6 below
- `tools`: `["save_project_plan", "update_task_status", "get_project_plan"]`
- `temperature`: 0.3 (planning benefits from determinism; tune in eval)

### Registry entry
```
AgentEntry(
    name="project_planning",
    module_path=".project_planning_agent",
    attr_name="project_planning_agent",
    description="Specialist agent for creating and managing project plans",
    capabilities=["planning", "project_management"],
    config_doc_id="project_planning_agent",
)
```

### Root agent integration (new CAPABILITY in `_BASE_INSTRUCTION`)
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

The instruction is loaded from the Firestore config doc via the existing `load_config_from_firestore("project_planning_agent")` mechanism, with an InstructionProvider closure that reads `organization_context` from `tool_context.state`.

## 7. Acceptance criteria

1. `get_registry().get("project_planning")` returns the agent without errors
2. Sending a chat message "create a project plan for a new product launch" routes through `dispatch_to_project_planning` (verified via Weave trace)
3. The agent produces a JSON object that validates against `ProjectPlan.model_validate` (no schema errors)
4. `save_project_plan` writes a plan to the API and returns the `plan_id`
5. `update_task_status` writes to the API; the response shape is what PRD-4 expects (even if `newly_unblocked_tasks` is empty in this PRD)
6. Agent instruction warns the model away from cycles and from non-existent agent assignees
7. All new unit tests pass

## 8. Test plan

**Unit tests:**
- Each tool: success path, validation failure, API error propagation
- `dispatch_to_project_planning`: org context injection, retry behavior, returned shape
- Registry: `get("project_planning")` returns the agent
- Agent wiring: tool list matches Firestore config doc; instruction string contains required keywords ("acceptance criteria", "depends_on", "assignee_name")

**Integration tests** (deferred to PRD-5 E2E suite, but a smoke test belongs here):
- End-to-end: chat message → dispatch → agent → `save_project_plan` → API → Firestore (mock the API client or use the real one against a test account)

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Agent emits invalid JSON or violates DAG | PRD-1's Pydantic validator rejects; `save_project_plan` returns the error so the agent can self-correct (re-prompt loop is built into ADK) |
| Agent assigns tasks to non-existent specialist agents | `_validate_agent_assignee` helper consults registry; tool returns clear error so model retries with a valid name |
| Long planning sessions hit token limits | `gemini-2.0-flash` 1M context handles this for v1; evaluate if user reports truncation |
| Instruction drift across model versions | Firestore config doc allows quick iteration without redeploy; eval scores tracked in MER-E |

## 10. Reference

- Parent plan: [`../project-planning-implementation-plan.md`](../project-planning-implementation-plan.md) §Agent Design, §ADK Tools, §Implementation Phases (Phase 2)
- Pattern to mirror: `app/adk/agents/utils/dispatch_handlers.py` (`dispatch_to_company_news`); `app/adk/agents/registry.py`; `app/adk/agents/ken_e_agent.py`
- Config loader: `app/adk/agents/strategy_agent/config_loader.py`
- CLAUDE.md rules in scope: PY-1, PY-2 (Python); T-1, T-4, T-6 (testing); C-2, C-4 (naming/composition)
