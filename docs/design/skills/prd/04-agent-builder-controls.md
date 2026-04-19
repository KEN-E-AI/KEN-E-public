# Sprint 2.6-D — Agent Builder Controls + End-to-End

**Status:** Blocked (requires Sprint 9, 2.6-A, 2.6-B, 2.6-C)
**Owner team:** Frontend + Backend (joint)
**Blocked by:** Sprint 9 (agent builder UI in place), 2.6-A (Skills API), 2.6-B (factory wiring), 2.6-C (users need skills to attach)
**Parallel with:** —
**Blocks:** —
**Estimated effort:** 4–5 days

---

## 1. Context

After Sprint 9, the Agent Builder UI at `/workflows/agents` lets an admin customize or create specialist agents. Two fields exist in the agent config as passive placeholders (`skill_ids`, `sandbox_code_executor_enabled`); Sprint 2.6-B wired them in the factory; this sprint **wires them into the UI**.

This sprint also delivers the **attach-time validation** logic: a user can't attach a skill with `scripts/` to an agent that doesn't have sandbox enabled. And it closes the feature with an **end-to-end test** that proves: user creates a skill → attaches to a custom agent → runs the agent → response reflects the skill's instructions.

## 2. Scope

### In scope
- Swap the Sprint 9 placeholder rows in `AgentEditView` and `AgentCreatePage` for interactive controls:
  - **Skills picker** — multi-select over the user's published skills, max 10, with search + filter by `has_scripts`
  - **Sandbox code execution toggle** — boolean with help text + a link to the authoring guide
- Wire the controls to the existing `PUT /api/v1/accounts/{account_id}/agent-configs/{config_id}` and `POST /api/v1/accounts/{account_id}/agent-configs/` endpoints (Sprint 9 story 2.2-8). The endpoints already accept the fields as passive pass-through (Sprint 9 forward-compat ask); this sprint adds UI bindings.
- **Backend: attach-time validation on agent-config writes:**
  - Reject PUT/POST when `skill_ids` contains a skill that the caller does not own.
  - Reject PUT/POST when any skill in `skill_ids` has `has_scripts=true` and `sandbox_code_executor_enabled` on the target agent is `false`. Return a structured 422 naming the offending skill and the required toggle.
  - Reject PUT/POST when `skill_ids` is longer than 10.
- **Ephemeral-agent endpoint** — a new `POST /api/v1/agents/_ephemeral_chat` (or similar) that accepts `(skill_ids, message)` and returns the agent's response, used by the Sprint 2.6-C Test Drawer. The ephemeral agent is built with a fixed system instruction + just those skills; not persisted.
- **End-to-end Playwright test** covering the full user journey.
- **Documentation:** update Feature 2.2's `agent-hierarchy.md` §8 and add a user-facing guide to `docs/skills-user-guide.md`.

### Out of scope
- Advanced skill-picker UX (tags, sort-by-usage) — defer to 2.6.1
- Per-agent token-budget preview based on attached skills' L1 metadata — stretch goal
- Undo / version history for agent-config edits — already Sprint 9's concern
- Skill sharing / org visibility — v2

## 3. Dependencies

- **Sprint 9:** `AgentEditView.tsx`, `AgentCreatePage.tsx` exist with the two placeholder rows; `PUT /api/v1/accounts/{account_id}/agent-configs/{config_id}` accepts `skill_ids` and `sandbox_code_executor_enabled` in the body (pass-through).
- **Sprint 2.6-A:** `GET /api/v1/skills` returns a paginated list the picker populates from. `GET /api/v1/skills/{id}` returns `has_scripts` which the attach-time validator reads.
- **Sprint 2.6-B:** Agent factory wiring is live; setting `skill_ids` on an agent actually takes effect.
- **Sprint 2.6-C:** The Skills Tab exists so users CAN create skills to attach. Unblocks the e2e test.
- **Existing files to study:**
  - `frontend/src/app/pages/workflows/agents/AgentEditView.tsx` (Sprint 9 output)
  - `frontend/src/app/pages/workflows/agents/AgentCreatePage.tsx` (Sprint 9 output)
  - `api/src/kene_api/routers/agent_configs.py` (Sprint 9 output)
  - `api/src/kene_api/services/skill_storage.py` (Sprint 2.6-A)
  - `app/adk/agents/agent_factory.py` (Sprint 2.6-B)

## 4. Data contract

No new persisted fields. The contract changes are:

### Request/response bodies — agent-config endpoints (Sprint 9 owned, Sprint 2.6-D enforced)

```ts
type AgentConfigPatchBody = {
  // existing fields from Sprint 9 (instruction, temperature, model, description)
  skill_ids?: string[];
  sandbox_code_executor_enabled?: boolean;
};
```

Server-side validation added this sprint:
- `skill_ids.length <= 10` → 422 "at most 10 skills per agent"
- Every `skill_id` exists and is owned by the caller → 422 "skill {id} not found" / "skill {id} not accessible"
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
POST /api/v1/agents/_ephemeral_chat

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

- Same auth as the main chat endpoint.
- Rate limit: 10 req/min per user (stricter than the main chat) to discourage abuse.
- Attach-time validation is identical to the agent-config endpoint — scripts without sandbox is rejected.
- The ephemeral agent is built on-the-fly via the Sprint 2.6-B factory with a fixed minimal system instruction ("You are a test agent. Use the attached skill and respond to the user's message.").

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
| Create | `api/src/kene_api/routers/ephemeral_chat.py` — `POST /api/v1/agents/_ephemeral_chat` |
| Create | `api/src/kene_api/services/skill_attach_validator.py` — pure validation functions (`check_owner`, `check_scripts_require_sandbox`, `check_cap`) |
| Modify | `api/src/kene_api/main.py` — register ephemeral chat router |
| Create | `docs/skills-user-guide.md` — end-user authoring + attachment guide |
| Modify | `docs/design/agent-hierarchy.md` — §8.3 config table gains final skill fields row |
| Create | `frontend/e2e/skills-attach-and-run.spec.ts` — Playwright e2e |
| Create | `*.test.tsx` for picker, toggle; `test_ephemeral_chat.py` for the new router; `test_skill_attach_validator.py` unit tests |

### Attach-time validation flow

```
PUT /api/v1/accounts/{account_id}/agent-configs/{config_id}
  body: { skill_ids, sandbox_code_executor_enabled, ... }
    │
    ▼
  check_cap(skill_ids)             → 422 if > 10
    │
    ▼
  fetch each skill's metadata from Firestore
    │
    ▼
  check_owner(skills, caller)      → 422 if any not owned
    │
    ▼
  check_scripts_require_sandbox(
    skills, sandbox_enabled)       → 422 with offending_skill_ids if mismatch
    │
    ▼
  persist override doc
    │
    ▼
  200 OK
```

Validation is pure — `skill_attach_validator.py` contains plain functions that take in a list of `Skill` objects and a boolean, and return either `None` or a `ValidationError` instance. This keeps them unit-testable without DB/API mocks.

## 6. API contract

### Modified — `PUT /api/v1/accounts/{account_id}/agent-configs/{config_id}`
See §4 — adds three rejection cases.

### Modified — `POST /api/v1/accounts/{account_id}/agent-configs/`
Same three rejection cases apply to custom agent creation.

### New — `POST /api/v1/agents/_ephemeral_chat`
See §4 for shape.

## 7. Acceptance criteria

1. **Picker works in Create:** On `/workflows/agents/create`, the admin can pick up to 10 skills from their own library. A counter shows "X / 10". Submitting creates the agent with `skill_ids` populated; the agent detail view shows them.
2. **Picker works in Edit:** On `/workflows/agents/{id}`, the admin can add/remove skills and save; the change persists.
3. **Sandbox toggle:** Toggling "Sandbox code execution" ON enables attachment of skills with `has_scripts=true`; toggling OFF while scripts-bearing skills are attached shows a warning and blocks save until resolved.
4. **Skills with scripts, no sandbox — frontend:** When `sandboxEnabled=false`, a skill with `has_scripts=true` is disabled in the picker with a tooltip "Requires sandbox code execution".
5. **Skills with scripts, no sandbox — backend:** A PUT with `skill_ids=["sk_scripts"]` + `sandbox_code_executor_enabled=false` returns 422 with `detail="scripts_require_sandbox"` and the offending skill id. The Firestore doc is not updated.
6. **10-skill cap enforced backend-side:** PUT with `skill_ids` of length 11 returns 422 "at most 10 skills per agent"; the client-side cap prevents selecting an 11th.
7. **Owner check:** User A owns skill X. User B (different account/user) with admin rights cannot attach X to one of their agents — PUT returns 422 "skill not accessible".
8. **Ephemeral chat:** POST `/api/v1/agents/_ephemeral_chat` with a valid skill_id and message returns a response within 30s. Attach-time validation identical to agent-config endpoint.
9. **Test drawer ON:** With Sprint 2.6-C's test drawer now enabled, a user can select a skill from their list, click "Test", type a prompt, and see the agent's reply — all without navigating away from the skill editor.
10. **End-to-end:** Playwright test passes: create skill → create agent with skill attached → visit chat page → send a prompt that triggers skill use → assert the response contains content matching the skill's instructions.
11. **User guide:** `docs/skills-user-guide.md` exists, covers authoring, attachment, sandbox, allowed-tools, and skill limits.
12. **agent-hierarchy.md updated.**
13. **All tests pass;** lint, typecheck, format all clean.

## 8. Test plan

### Unit tests

**`test_skill_attach_validator.py`:**
- `check_cap([], ...)` → OK
- `check_cap(list_of_11, ...)` → error
- `check_owner([skill_owned_by_A], caller=A)` → OK
- `check_owner([skill_owned_by_A], caller=B)` → error
- `check_scripts_require_sandbox([skill_with_scripts], sandbox=False)` → error, names the skill
- `check_scripts_require_sandbox([skill_with_scripts], sandbox=True)` → OK
- `check_scripts_require_sandbox([skill_no_scripts], sandbox=False)` → OK

### Integration tests

**`test_agent_configs_attach_validation.py`:**
- Seed Firestore with a skill owned by user A and an agent config accessible to user A.
- PUT variations: cap exceeded, wrong owner, scripts w/o sandbox, all OK. Each returns the documented status + error body.
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
| Users attach skills and expect them to apply to system/root agents too | Copy on the picker clarifies: "Skills attach to this custom agent only"; attempts to attach to system agents are blocked at the API layer (system agents return 403 on PUT per Sprint 9) |

### Open questions

- **Q:** Should the ephemeral-agent endpoint support the existing chat's streaming response shape? → **v1: non-streaming** (simpler; test drawer just waits). Streaming is easy to add later.
- **Q:** If a user tries to save an agent with a soft-archived skill in `skill_ids`, reject or silently drop? → **Reject with 422.** Silent drops hide mistakes.

## 10. Reference

- Parent plan: [`../skills-implementation-plan.md`](../skills-implementation-plan.md) §6 (Sprint breakdown), §7 (Sprint 9 asks)
- Sister sprints: [`01-skills-backend.md`](./01-skills-backend.md), [`02-agent-integration.md`](./02-agent-integration.md), [`03-authoring-ui.md`](./03-authoring-ui.md)
- Upstream sprint: Feature 2.2 (Sprint 9) — Agent Factory
- Design doc: [`../../agent-hierarchy.md`](../../agent-hierarchy.md) §8 (config-to-constructor mapping)
- CLAUDE.md rules in scope: C-5, C-6, C-8; PY-1, PY-2, PY-7; T-1, T-2, T-3, T-4, T-5; G-1, G-2, G-3
