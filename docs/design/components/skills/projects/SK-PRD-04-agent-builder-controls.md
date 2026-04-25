# Sprint 2.6-D — Agent Builder Controls + End-to-End

**Status:** Blocked (requires AH-PRD-02, 2.6-A, 2.6-B, 2.6-C)
**Owner team:** Frontend + Backend (joint)
**Blocked by:** [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) (agent builder UI in place), 2.6-A (Skills API), 2.6-B (factory wiring), 2.6-C (users need skills to attach)
**Parallel with:** —
**Blocks:** —
**Estimated effort:** 4–5 days

---

## 1. Context

After [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md), the Agent Builder UI at `/workflows/agents` lets an admin customize or create specialist agents. Two fields exist in the agent config as passive placeholders (`skill_ids`, `sandbox_code_executor_enabled`); Sprint 2.6-B wired them in the factory; this sprint **wires them into the UI**.

This sprint also delivers the **attach-time validation** logic: a user can't attach a skill with `scripts/` to an agent that doesn't have sandbox enabled. And it closes the feature with an **end-to-end test** that proves: user creates a skill → attaches to a custom agent → runs the agent → response reflects the skill's instructions.

## 2. Scope

### In scope
- Swap the AH-PRD-02 placeholder rows in `AgentEditView` and `AgentCreatePage` for interactive controls:
  - **Skills picker** — multi-select over the user's published skills, max 10, with search + filter by `has_scripts`
  - **Sandbox code execution toggle** — boolean with help text + a link to the authoring guide
- Wire the controls to the existing `PUT /api/v1/accounts/{account_id}/agent-configs/{config_id}` and `POST /api/v1/accounts/{account_id}/agent-configs/` endpoints (AH-PRD-02 story 2.2-8). The endpoints already accept the fields as passive pass-through (AH-PRD-02 forward-compat ask); this sprint adds UI bindings.
- **Backend: attach-time validation on agent-config writes:**
  - Reject PUT/POST when any `skill_id` in `skill_ids` does not exist in `accounts/{account_id}/skills` (the path's account). Because skills are account-scoped (SK-PRD-01), "owned by the caller" reduces to "present in the target agent's account collection." Return 422 "skill {id} not found in this account."
  - Reject PUT/POST when any skill in `skill_ids` has `has_scripts=true` and `sandbox_code_executor_enabled` on the target agent is `false`. Return a structured 422 naming the offending skill and the required toggle.
  - Reject PUT/POST when `skill_ids` is longer than 10.
- **Ephemeral-agent endpoint** — a new `POST /api/v1/accounts/{account_id}/agents/_ephemeral_chat` that accepts `(skill_ids, message)` and returns the agent's response, used by the Sprint 2.6-C Test Drawer. Account-scoped for consistency with the skill and agent-config endpoints; the ephemeral agent is built with the caller's `account_id`, a fixed system instruction, and just those skills; not persisted.
- **End-to-end Playwright test** covering the full user journey.
- **Documentation:** update [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) §5.2 (final behavior of the skill/sandbox fields, replacing the forward-compat note) and add a user-facing guide to `docs/skills-user-guide.md`.

### Out of scope
- Advanced skill-picker UX (tags, sort-by-usage) — defer to 2.6.1
- Per-agent token-budget preview based on attached skills' L1 metadata — stretch goal
- Undo / version history for agent-config edits — already AH-PRD-02's concern
- Skill sharing / org visibility — v2

## 3. Dependencies

- **[AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) (Agent Factory):** `AgentEditView.tsx`, `AgentCreatePage.tsx` exist with the two placeholder rows; `PUT /api/v1/accounts/{account_id}/agent-configs/{config_id}` accepts `skill_ids` and `sandbox_code_executor_enabled` in the body (pass-through).
- **Sprint 2.6-A:** `GET /api/v1/accounts/{account_id}/skills` returns a paginated list the picker populates from (scoped to the same account as the agent being edited). `GET /api/v1/accounts/{account_id}/skills/{id}` returns `has_scripts` which the attach-time validator reads.
- **Sprint 2.6-B:** Agent factory wiring is live; setting `skill_ids` on an agent actually takes effect.
- **Sprint 2.6-C:** The Skills Tab exists so users CAN create skills to attach. Unblocks the e2e test.
- **Existing files to study:**
  - `frontend/src/app/pages/workflows/agents/AgentEditView.tsx` (AH-PRD-02 output)
  - `frontend/src/app/pages/workflows/agents/AgentCreatePage.tsx` (AH-PRD-02 output)
  - `api/src/kene_api/routers/agent_configs.py` (AH-PRD-02 output)
  - `api/src/kene_api/services/skill_storage.py` (Sprint 2.6-A)
  - `app/adk/agents/agent_factory.py` (Sprint 2.6-B)

## 4. Data contract

> **Revised 2026-04-20** — Skill existence checks read from the Shape B subcollection `accounts/{account_id}/skills/*`. See [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) for rationale.

No new persisted fields. The contract changes are:

### Request/response bodies — agent-config endpoints (AH-PRD-02 owned, Sprint 2.6-D enforced)

```ts
type AgentConfigPatchBody = {
  // existing fields from AH-PRD-02 (instruction, temperature, model, description)
  skill_ids?: string[];
  sandbox_code_executor_enabled?: boolean;
};
```

Server-side validation added this sprint:
- `skill_ids.length <= 10` → 422 "at most 10 skills per agent"
- Every `skill_id` exists in `accounts/{account_id}/skills` (the agent-config's account) → 422 "skill {id} not found in this account." A skill authored in a different account is never visible through this path; no separate "not accessible" case.
- If any skill has `has_scripts=true` and `sandbox_code_executor_enabled=false` → 422 with:
  ```json
  {
    "detail": "scripts_require_sandbox",
    "offending_skill_ids": ["sk_abc123"],
    "hint": "Enable 'Sandbox code execution' on this agent, or remove the skill(s) that contain scripts."
  }
  ```

### Ephemeral chat endpoint

```
POST /api/v1/accounts/{account_id}/agents/_ephemeral_chat

Request:
{
  "skill_ids": ["sk_abc123"],
  "sandbox_code_executor_enabled": false,
  "message": "Follow the SEO checklist on this paragraph: ..."
}

Response:
{
  "reply": "Reviewing against the SEO checklist...",
  "trace_id": "...",         // Weave trace for debug
  "used_skills": ["sk_abc123"]
}
```

- Same auth + account-access dependency as the account-scoped agent-config endpoints. The caller must be a member of `{account_id}`; otherwise 403.
- `skill_ids` are resolved against `accounts/{account_id}/skills` — skills from a different account are invisible here (matches the SK-PRD-01 isolation model).
- Rate limit: 10 req/min per user per account (stricter than the main chat) to discourage abuse.
- Attach-time validation is identical to the agent-config endpoint — scripts without sandbox is rejected.
- The ephemeral agent is built on-the-fly via the Sprint 2.6-B factory (which already takes `account_id`) with a fixed minimal system instruction ("You are a test agent. Use the attached skill and respond to the user's message.").

### Frontend components

```ts
// frontend/src/app/pages/workflows/agents/components/SkillsPicker.tsx
type Props = {
  value: SkillId[];
  onChange: (next: SkillId[]) => void;
  sandboxEnabled: boolean;   // gates scripts-bearing skills
  disabled?: boolean;
};
```

The picker:
- Fetches the current user's published skills via `useSkills()`.
- Disables (greyed out + tooltip) any skill with `has_scripts=true` when `sandboxEnabled=false`.
- Shows a char count: "3 / 10 selected".
- Text filter, no grouping in v1.

## 5. Implementation outline

| Action | File |
|---|---|
| Modify | `frontend/src/app/pages/workflows/agents/AgentEditView.tsx` — swap placeholders for live controls |
| Modify | `frontend/src/app/pages/workflows/agents/AgentCreatePage.tsx` — same |
| Create | `frontend/src/app/pages/workflows/agents/components/SkillsPicker.tsx` |
| Create | `frontend/src/app/pages/workflows/agents/components/SandboxToggle.tsx` |
| Modify | `frontend/src/app/pages/workflows/skills/components/TestSkillDrawer.tsx` — flip feature flag ON; wire to ephemeral chat endpoint |
| Modify | `api/src/kene_api/routers/agent_configs.py` — add attach-time validation (3 new rules) |
| Create | `api/src/kene_api/routers/ephemeral_chat.py` — `POST /api/v1/accounts/{account_id}/agents/_ephemeral_chat` |
| Create | `api/src/kene_api/services/skill_attach_validator.py` — pure validation functions (`check_skills_exist_in_account`, `check_scripts_require_sandbox`, `check_cap`) |
| Modify | `api/src/kene_api/main.py` — register ephemeral chat router |
| Create | `docs/skills-user-guide.md` — end-user authoring + attachment guide |
| Modify | [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) — §5.2 config-to-constructor mapping: finalize the `skill_ids` / `sandbox_code_executor_enabled` rows (replace forward-compat pass-through note with the final behavior) |
| Create | `frontend/e2e/skills-attach-and-run.spec.ts` — Playwright e2e |
| Create | `*.test.tsx` for picker, toggle; `test_ephemeral_chat.py` for the new router; `test_skill_attach_validator.py` unit tests |

### Attach-time validation flow

```
PUT /api/v1/accounts/{account_id}/agent-configs/{config_id}
  body: { skill_ids, sandbox_code_executor_enabled, ... }
    │
    ▼
  check_cap(skill_ids)                          → 422 if > 10
    │
    ▼
  fetch each skill's metadata from
  accounts/{account_id}/skills (the path's account)
    │
    ▼
  check_skills_exist_in_account(
    skill_ids, found_skills)                    → 422 "skill {id} not found in this account"
                                                  for any id not returned by the fetch
    │
    ▼
  check_scripts_require_sandbox(
    skills, sandbox_enabled)                    → 422 with offending_skill_ids if mismatch
    │
    ▼
  persist override doc
    │
    ▼
  200 OK
```

Validation is pure — `skill_attach_validator.py` contains plain functions that take in a list of `Skill` objects and a boolean, and return either `None` or a `ValidationError` instance. This keeps them unit-testable without DB/API mocks. The cross-account isolation comes for free from reading the single account-scoped collection (`accounts/{account_id}/skills`) — no separate owner check is needed.

## 6. API contract

### Modified — `PUT /api/v1/accounts/{account_id}/agent-configs/{config_id}`
See §4 — adds three rejection cases.

### Modified — `POST /api/v1/accounts/{account_id}/agent-configs/`
Same three rejection cases apply to custom agent creation.

### New — `POST /api/v1/accounts/{account_id}/agents/_ephemeral_chat`
See §4 for shape.

## 7. Acceptance criteria

1. **Picker works in Create:** On `/workflows/agents/create`, the admin can pick up to 10 skills from their own library. A counter shows "X / 10". Submitting creates the agent with `skill_ids` populated; the agent detail view shows them.
2. **Picker works in Edit:** On `/workflows/agents/{id}`, the admin can add/remove skills and save; the change persists.
3. **Sandbox toggle:** Toggling "Sandbox code execution" ON enables attachment of skills with `has_scripts=true`; toggling OFF while scripts-bearing skills are attached shows a warning and blocks save until resolved.
4. **Skills with scripts, no sandbox — frontend:** When `sandboxEnabled=false`, a skill with `has_scripts=true` is disabled in the picker with a tooltip "Requires sandbox code execution".
5. **Skills with scripts, no sandbox — backend:** A PUT with `skill_ids=["sk_scripts"]` + `sandbox_code_executor_enabled=false` returns 422 with `detail="scripts_require_sandbox"` and the offending skill id. The Firestore doc is not updated.
6. **10-skill cap enforced backend-side:** PUT with `skill_ids` of length 11 returns 422 "at most 10 skills per agent"; the client-side cap prevents selecting an 11th.
7. **Cross-account isolation:** Account A owns skill X. An admin in account B (who has no access to A) cannot attach X to a B-owned agent — PUT returns 422 "skill not found in this account." The picker on the B admin's agent-builder screen never shows X in the first place (it reads `GET /api/v1/accounts/B/skills`).
8. **Ephemeral chat:** POST `/api/v1/accounts/{account_id}/agents/_ephemeral_chat` with a valid skill_id and message returns a response within 30s. Callers who are not members of `{account_id}` receive 403. Attach-time validation identical to agent-config endpoint.
9. **Test drawer ON:** With Sprint 2.6-C's test drawer now enabled, a user can select a skill from their list, click "Test", type a prompt, and see the agent's reply — all without navigating away from the skill editor.
10. **End-to-end:** Playwright test passes: create skill → create agent with skill attached → visit chat page → send a prompt that triggers skill use → assert the response contains content matching the skill's instructions.
11. **User guide:** `docs/skills-user-guide.md` exists, covers authoring, attachment, sandbox, allowed-tools, and skill limits.
12. **AH-PRD-02 §5.2 updated** — `skill_ids` / `sandbox_code_executor_enabled` rows reflect the final behavior.
13. **All tests pass;** lint, typecheck, format all clean.

## 8. Test plan

### Unit tests

**`test_skill_attach_validator.py`:**
- `check_cap([], ...)` → OK
- `check_cap(list_of_11, ...)` → error
- `check_skills_exist_in_account(requested=["a","b"], found=[skill_a, skill_b])` → OK
- `check_skills_exist_in_account(requested=["a","b"], found=[skill_a])` → error naming `"b"`
- `check_scripts_require_sandbox([skill_with_scripts], sandbox=False)` → error, names the skill
- `check_scripts_require_sandbox([skill_with_scripts], sandbox=True)` → OK
- `check_scripts_require_sandbox([skill_no_scripts], sandbox=False)` → OK

### Integration tests

**`test_agent_configs_attach_validation.py`:**
- Seed Firestore with a skill in `skills_{account_A}` and an agent config in `account_A`'s agent-configs collection.
- PUT variations against account_A's config: cap exceeded, unknown skill_id (not in the account), scripts w/o sandbox, all OK. Each returns the documented status + error body.
- Cross-account: seed a skill in `skills_{account_B}`, attempt to attach it via account_A's PUT path → 422 "skill not found in this account."
- Confirm the Firestore agent-config doc is unchanged after each 422.

**`test_ephemeral_chat.py`:**
- Returns 422 for the same three cases above.
- Happy path returns 200 with a non-empty `reply` and a valid `trace_id`.

### Component tests

**`SkillsPicker.test.tsx`:**
- Renders all published skills for the current user
- 10-item cap enforced
- Scripts-bearing skills disabled when `sandboxEnabled=false`
- Search filter narrows the list

**`SandboxToggle.test.tsx`:**
- Toggling shows/hides contextual warning when scripts-bearing skills are currently attached

### End-to-end (Playwright)

**`skills-attach-and-run.spec.ts`:**
```
1. Login as an admin
2. Navigate to /workflows/skills → click "New Skill"
3. Fill frontmatter (name: "e2e-test-skill", description: "Testing end-to-end")
4. Fill SKILL.md body: "When asked about testing, respond with the word TESTPASS."
5. Publish
6. Navigate to /workflows/agents → click "New Agent"
7. Fill name, instruction, model; pick "e2e-test-skill"; save
8. Open chat with that agent; send "ask about testing"
9. Assert the response contains "TESTPASS"
10. (Teardown) Archive the skill and delete the agent
```

## 9. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| Ephemeral-agent endpoint becomes a free-tier-chat escape hatch | Rate-limit (10 req/min per user); log `test_drawer=true` in audit log; consider narrowing later if abuse emerges |
| The 422 error format for scripts-require-sandbox is ad-hoc | Define the shape once in a shared `ValidationErrorResponse` Pydantic model and reuse across the API |
| Adding the picker to both Edit and Create pages duplicates logic | Extract the form section into a shared `<AgentSkillsSection />` component used by both pages |
| Skill metadata drifts between the picker's cache and the attach-time check | Backend is the source of truth; the picker's UX is optimistic, errors surface via the 422 banner |
| Users attach skills and expect them to apply to system/root agents too | Copy on the picker clarifies: "Skills attach to this custom agent only"; attempts to attach to system agents are blocked at the API layer (system agents return 403 on PUT per AH-PRD-02) |
| Users who belong to multiple accounts expect their skills to follow them across accounts | Account-scoped skills is deliberate (SK-PRD-01). If this becomes a real ask, add a "Copy skill to another account" action — do not widen the ownership model. Surface this clearly in the authoring UI empty state copy. |

### Open questions

- **Q:** Should the ephemeral-agent endpoint support the existing chat's streaming response shape? → **v1: non-streaming** (simpler; test drawer just waits). Streaming is easy to add later.
- **Q:** If a user tries to save an agent with a soft-archived skill in `skill_ids`, reject or silently drop? → **Reject with 422.** Silent drops hide mistakes.

## 10. Reference

- Parent plan: [`../skills-implementation-plan.md`](../skills-implementation-plan.md) §6 (Sprint breakdown), §7 (AH-PRD-02 asks)
- Sister sprints: [`SK-PRD-01-skills-backend.md`](./SK-PRD-01-skills-backend.md), [`SK-PRD-02-agent-integration.md`](./SK-PRD-02-agent-integration.md), [`SK-PRD-03-authoring-ui.md`](./SK-PRD-03-authoring-ui.md)
- Upstream project: [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) (Agent Factory)
- Design doc: [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) §5.2 (config-to-constructor mapping)
- CLAUDE.md rules in scope: C-5, C-6, C-8; PY-1, PY-2, PY-7; T-1, T-2, T-3, T-4, T-5; G-1, G-2, G-3
