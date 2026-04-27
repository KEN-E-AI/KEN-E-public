# PR-PRD-09 — Planning Agent Multi-Category Update

**Status:** Blocked — resumes once PR-PRD-02, PR-PRD-07, and PR-PRD-08 ship
**Owner team:** Agent / ML
**Blocked by:** PR-PRD-02 (the Firestore `agent_configs/project_planning` doc + the three tool functions); PR-PRD-07 (multi-category `PlanTask` extensions and orphan-task lifecycle); PR-PRD-08 (`Campaign` entity + per-objective generic fallback)
**Parallel with:** PR-PRD-05 (closing-out tests can run alongside this update)
**Estimated effort:** 1–2 days

---

## 1. Context

PR-PRD-02 publishes the `project_planning` specialist agent and its instruction. PR-PRD-07 extends `PlanTask` with `category` (`task` / `promotion` / `holiday` / `event`), task-level recurrence, an `unscheduled` flag, an `owner_email` distinct from `assignee_name`, and category-specific sparse fields (e.g., `promotion_type`, `holiday_type`). PR-PRD-08 introduces first-class `Campaign` entities with a four-value `objective` enum and on-the-fly creation from the activity drawer.

After all three ship, the planning agent's instruction (the version authored in PR-PRD-02) still describes only the v1 task model — it does not know about activity categories, sparse fields, recurrence, owner_email, or campaigns. Without this update, every plan the agent produces collapses to `category="task"`, no recurrence, no campaign assignment — undercutting the value of PR-PRDs 07 and 08.

This PRD updates the agent's Firestore config + tool input contracts so the specialist can produce categorized activities, set recurrence, distinguish owner from assignee, and assign campaigns (creating one inline when nothing matches).

## 2. Scope

### In scope
- Update `agent_configs/project_planning.instruction` to cover the four categories and the corresponding sparse-field requirements (deploy-time Firestore write; no code change required for the instruction itself)
- Extend the `save_project_plan` tool input contract to validate the multi-category schema (the tool already calls `ProjectPlan.model_validate` — verify the post-PR-PRD-07 model rejects under-specified categories cleanly and surface the validator's error to the agent for self-correction)
- Add a fourth tool function `resolve_or_create_campaign(account_id, name, objective) -> {campaign_id}` that wraps `GET /api/v1/campaigns/{account_id}` (search by name) + `POST /api/v1/campaigns/{account_id}` (create if missing). Mirrors the Calendar page's inline-create flow so the agent does not have to choose between writing a plan with a fabricated id or asking the user
- Register the new tool in `tools.yaml` under the existing `planning` category
- Update PR-PRD-02's CAPABILITY block in `_BASE_INSTRUCTION` to mention the broader scope
- 8 golden-path evaluation prompts under `tests/evals/project_planning/` covering: a single-task plan, a promotion launch, a holiday-pinned campaign, a recurring weekly activity, an unscheduled task, an explicit campaign assignment, an inline-create campaign assignment, and a mixed plan combining several categories

### Out of scope
- Any change to the data model or API endpoints (PR-PRD-07 / PR-PRD-08 own those)
- Any frontend change (PR-PRD-03 already wires the multi-category UI)
- Any review-loop / acceptance-criteria changes (AH-PRD-01)
- Migration of existing plans (no data shape change)

## 3. Dependencies

- **PR-PRD-02:** owns the Firestore config doc this PRD modifies and the three Python tool functions; this PRD adds a fourth tool and updates the instruction string
- **PR-PRD-07:** ships the multi-category `PlanTask` validators that the agent must respect
- **PR-PRD-08:** ships the `Campaign` entity + `get_generic_campaign_id` helper + `POST /campaigns`; this PRD's new `resolve_or_create_campaign` tool wraps those endpoints
- **AH-PRD-02 (Agent Factory):** the factory rebuilds the specialist on the next deploy after the Firestore config edit; no factory changes in scope
- **MER-E:** golden-path eval scores tracked there; this PRD adds the prompts but does not modify the scoring framework
- **Existing files to study:**
  - `app/adk/agents/project_planning_tools.py` (PR-PRD-02 — add fourth tool here)
  - Firestore `agent_configs/project_planning` (PR-PRD-02 — update instruction here)
  - `app/adk/tools/registry/config/tools.yaml` (PR-PRD-02 — add fourth tool entry)
  - `tests/evals/` (existing golden-path harness pattern — copy)

## 4. Data contract

### `resolve_or_create_campaign(account_id: str, name: str, objective: str) -> dict`

- Input:
  - `account_id`: the active account
  - `name`: campaign name as the user described it (free text)
  - `objective`: one of `"Problem Awareness" | "Brand Awareness" | "Consideration" | "Conversion"` (PR-PRD-08 enum). When the user has not implied an objective, the agent passes the closest match per its instruction (defaults to `"Brand Awareness"` for ambiguous "general" campaigns).
- Output: `{"status": "success", "campaign_id": str, "created": bool}` (`created=true` when a `POST /campaigns` was issued; `false` when an existing match was found) or `{"status": "error", "error": str}`.

The lookup is case-insensitive (per PR-PRD-08's uniqueness rule). When a generic-fallback campaign would be the right answer (e.g., the user says "no specific campaign, just a general awareness push"), the agent calls `get_generic_campaign_id` instead — the resolver does not auto-pick a generic to avoid silent overrides.

### Tool input shapes — unchanged

`save_project_plan(plan_data: dict) -> dict` and `update_task_status(...)` keep their PR-PRD-02 signatures. The validator on the receiving side (the API) now enforces PR-PRD-07's category rules; tool errors surface back to the agent for self-correction.

## 5. Implementation outline

| Action | File / target |
|--------|---------------|
| Modify | Firestore `agent_configs/project_planning.instruction` — see §6 below for the new content |
| Modify | `app/adk/agents/project_planning_tools.py` — add `resolve_or_create_campaign(...)` |
| Modify | `app/adk/tools/registry/config/tools.yaml` — register `resolve_or_create_campaign` under `planning` |
| Modify | `app/adk/agents/ken_e_agent.py` `_BASE_INSTRUCTION` — light edit to the existing CAPABILITY N block to mention the broadened scope |
| Create | `tests/evals/project_planning/multi_category_plans.yaml` (or equivalent) — 8 golden-path prompts |
| Modify | `tests/unit/agents/test_project_planning_tools.py` — unit-test `resolve_or_create_campaign`'s found / created / error paths |
| Modify | `tests/integration/test_project_planning_factory_build.py` — assert the planning specialist's tool roster contains four tools after this PRD ships |

## 6. Agent instruction (key behaviors to add)

The instruction string (stored on the `agent_configs/project_planning` Firestore doc) must additionally guide the model to:

1. **Choose an activity category for every task.** Default to `task`; pick `promotion` for any discount / offer / bundle / launch-offer, `holiday` for date-pinned cultural / religious / public observances, `event` for one-off branded moments. The category drives which sparse fields are required.
2. **Fill required sparse fields.** When `category="promotion"`, set `promotion_type`, optionally `discount_details` / `end_date` / `region` / `promo_url`. When `category="holiday"`, set `holiday_type`; flip `recurring=true` for annual repetitions. Event has no extras in v1.
3. **Distinguish owner from assignee.** `owner_email` is the human responsible for the outcome; `assignee_name` is who *executes* (agent / automation target / human). Both can coexist on a single task.
4. **Set recurrence on tasks that genuinely repeat.** `recurrence_enabled=true` requires a valid 5-field `recurrence_cron` and a sane `recurrence_timezone` (default `UTC`). Do not mark one-off launches as recurring.
5. **Use `unscheduled=true` only when the user is explicit.** When `unscheduled=true`, omit `due_date` and `launch_time_utc`; the activity surfaces in the Calendar's Unscheduled Tasks panel.
6. **Assign a campaign for every activity that fits one.** Call `resolve_or_create_campaign` first if the user named or implied a campaign; otherwise call `get_generic_campaign_id(...)` for the closest objective. Never fabricate a `campaign_id`.
7. **Respect the model validators.** A category mismatch (e.g., `category="promotion"` without `promotion_type`) returns a 422 from `save_project_plan`; the agent must self-correct rather than surfacing the error to the user.

The CAPABILITY block in `ken_e_agent.py` `_BASE_INSTRUCTION` gains one bullet: *"Planning a campaign with promotions, holidays, or recurring activities"*.

## 7. Acceptance criteria

1. After deploying the updated Firestore config, `agent_factory.build_hierarchy()` rebuilds the `project_planning` specialist with the new instruction (verifiable by reading `agent_configs/project_planning.instruction` and confirming the new content)
2. `save_project_plan` accepts a multi-category plan (mix of `task`, `promotion`, `holiday`, `event`) and persists; the API returns the new `plan_id`
3. The agent emits `category` correctly for at least 7 / 8 golden-path prompts (one tolerated miss for variance — re-run if regressed)
4. `resolve_or_create_campaign` returns `{created: false, campaign_id: <existing id>}` when the campaign exists; returns `{created: true, campaign_id: <new id>}` when it does not; surfaces errors transparently
5. Tool roster integration test asserts four tools (`save_project_plan`, `update_task_status`, `get_project_plan`, `resolve_or_create_campaign`) on the planning specialist
6. The agent never returns a fabricated `campaign_id` (golden-path probe — assert every emitted `campaign_id` round-trips through `GET /api/v1/campaigns/{account_id}/{campaign_id}`)
7. The agent never sets `unscheduled=true` together with `due_date` (checked against PR-PRD-07's validator, which would otherwise 422)
8. All new unit tests + golden-path evals pass; `make lint` clean

## 8. Test plan

**Unit tests** (`test_project_planning_tools.py` — extended):
- `resolve_or_create_campaign`: existing match returns `created=false`; missing match issues `POST /campaigns` and returns `created=true`; API error propagates as `{"status": "error", ...}`
- Tool registration: tools.yaml entry for `resolve_or_create_campaign` is correct (model name, description, schema)

**Factory integration tests** (`test_project_planning_factory_build.py` — extended):
- After re-seeding Firestore config + tools.yaml, `build_hierarchy()` produces a planning specialist with the four-tool roster

**Golden-path evals** (`tests/evals/project_planning/multi_category_plans.yaml`, 8 prompts):
1. *"Plan a single content task to publish a blog post next Tuesday."* → 1-task plan, `category="task"`
2. *"Run a 7-day Spring Promo discount across Meta and Google Ads starting May 1."* → multi-task plan with `category="promotion"`, `promotion_type="Discount"`, `end_date` set
3. *"Coordinate our Memorial Day campaign with a holiday banner."* → mixed plan: a `holiday` task pinned to the date + downstream `task` activities
4. *"Set up a recurring Monday-morning newsletter."* → 1-task plan with `recurrence_enabled=true`, `recurrence_cron="0 9 * * MON"`
5. *"Capture a backlog idea: try a TikTok influencer angle, no specific date yet."* → 1-task plan with `unscheduled=true`, no `due_date`
6. *"Plan the Black Friday sale across all channels and tie it to the Black Friday campaign."* → activities tagged with `campaign_id` resolving to a campaign named `Black Friday` (created if missing)
7. *"Schedule a Q3 brand-awareness push, no specific campaign."* → activities tagged with `campaign_id = get_generic_campaign_id(account_id, "Brand Awareness")`
8. *"Plan a product launch: a launch-offer promotion, a press event, a recurring weekly check-in for the next 4 weeks, and a holiday pin for Cyber Monday."* → mixed plan exercising all four categories + recurrence + multiple campaigns

Eval scoring: structural correctness (validates against `ProjectPlan.model_validate`) + per-prompt rubric (campaign present, sparse fields populated where required, no `due_date` when `unscheduled`).

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Agent over-classifies as `promotion` because the instruction emphasizes promotions | Keep examples in the instruction balanced across all four categories; rebalance after eval-3 review |
| Agent fabricates campaign ids despite the rule | `resolve_or_create_campaign` is the only way to get an id; emphasize "never fabricate" in the instruction; AC #6 catches regressions |
| Eval flakiness from LLM nondeterminism | Allow 1 / 8 misses per run; require two consecutive clean runs to gate merge |
| Instruction drift between this PRD and PR-PRD-02 | Treat the `agent_configs/project_planning.instruction` field as a single source of truth; this PRD's update lands as one Firestore write; subsequent edits go through the standard config-edit review |
| The fourth tool inflates the specialist's roster — risk of pushing past the AH-PRD-02 ≤30-tool cap | Planning specialist is currently at 3 tools; adding 1 brings it to 4. Well within the cap |

## 10. Reference

- Updated specialist: [PR-PRD-02 — Planning Agent & Tools](./PR-PRD-02-planning-agent-and-tools.md)
- Multi-category contract: [PR-PRD-07 — Calendar Activities](./PR-PRD-07-calendar-activities.md)
- Campaign contract: [PR-PRD-08 — Campaign Management](./PR-PRD-08-campaign-management.md)
- Factory: [AH-PRD-02 — Agent Factory](../../agentic-harness/projects/AH-PRD-02-agent-factory.md)
- Pattern files: `app/adk/agents/project_planning_tools.py`, Firestore `agent_configs/project_planning`, `tests/evals/`
- CLAUDE.md rules in scope: PY-1, PY-2 (Python); T-1, T-4, T-6 (testing); C-2, C-4 (naming/composition)
