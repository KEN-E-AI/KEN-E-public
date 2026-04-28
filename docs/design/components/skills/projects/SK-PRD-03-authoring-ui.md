# Sprint 2.6-C — Skills Authoring UI

**Status:** Blocked on API contract (Sprint 2.6-A mid-sprint)
**Owner team:** Frontend
**Blocked by:** 2.6-A (for real API); can stub against contract day 1
**Parallel with:** AH-PRD-02, 2.6-0, 2.6-B
**Blocks:** 2.6-D (picker needs skills to attach)
**Estimated effort:** 6–8 days

---

## 1. Context

This PRD delivers the user-facing authoring experience: a new **Skills tab** under `/workflows/skills` where users create, edit, test, version, and archive their own skills. The tab sits alongside the Agents tab (AH-PRD-02 story 2.2-9) and Automations tab inside the `WorkflowsLayout`.

Users author a skill by filling out a form with frontmatter fields (name, description, etc.) and the SKILL.md body in a Markdown editor, optionally uploading reference/asset/script files. Live validation surfaces spec violations before submit. A "Test with agent" drawer lets the user attach the skill temporarily to a test agent and issue a single prompt to sanity-check behavior.

## 2. Scope

### In scope
- New route `/workflows/skills` (list) and `/workflows/skills/{skill_id}` (edit)
- New route `/workflows/skills/create` (create form)
- Skills list page: tabular list with name, description, version, status, updated_at, actions
- Skill editor:
  - Frontmatter form (name, description, license, compatibility, allowed-tools, metadata as key/value)
  - Monaco-based Markdown editor for SKILL.md body with live char counter
  - Reference/asset/script file uploader (drag-drop + click-to-browse)
  - Live validation panel showing spec violations
- Version history drawer — list previous versions, view SKILL.md at that version, no restore in v1
- Archive (soft-delete) action with confirmation
- Test drawer — one-off chat with a skill-bound test agent (see §4 for exact semantics)
- Wiring to the API (Sprint 2.6-A) via a typed React Query hook layer
- Empty-state illustration + first-skill copy

### Out of scope
- Attaching skills to agents — Sprint 2.6-D ships the skill picker in the agent builder
- Restore-from-archive — archive is effectively permanent; the trash bucket's 30-day GCS lifecycle purges the bundle and v1 ships no UI to restore. Users see this prominently on the archive-confirmation dialog.
- Sharing UI (v2)
- Skill-import-from-URL UI (v2)
- Live preview of L1 metadata as it would appear to an agent (stretch)
- Mobile responsive beyond basic readability
- Per-attachment skill version pinning (v2 — see §4 latest-wins note)

## 3. Dependencies

- **Sprint 2.6-A:** REST API published under `/api/v1/accounts/{account_id}/skills/*`. Skills team owes frontend a finalized OpenAPI schema by mid-sprint.
- **AH-PRD-02 (Agent Factory) — soft:** `WorkflowsLayout` exists with Agents / Automations tabs; this PRD adds the Skills tab to the same shared nav. No hard dependency on story 2.2-9 completion — the tab can ship independently and slot in.
- **Existing files to study:**
  - `frontend/src/app/pages/workflows/` — layout, existing tab pages
  - `frontend/src/app/components/ui/` — shadcn/ui primitives
  - `frontend/src/app/hooks/useQuery*.ts` — React Query patterns
  - `frontend/src/app/lib/api/` — API client generation
- **External:**
  - `monaco-editor` or `@monaco-editor/react` (not yet in deps — add)
  - `js-yaml` (frontmatter parsing client-side for live validation)
  - `react-dropzone` (file uploader)

## 4. Data contract

No new Firestore/GCS state. All reads/writes go through the Sprint 2.6-A API.

### API base path

All endpoints are **account-scoped** under `/api/v1/accounts/{account_id}/skills/*` (mirrors agent-configs and the existing strategy router). The authoring UI reads the current `account_id` from the standard account-context provider used elsewhere in the frontend (e.g., same hook as Agents / Automations tabs) — no prop drilling. The `useSkills` hook and the typed API client in `frontend/src/app/lib/api/skills.ts` take `account_id` from context automatically; component code never constructs the URL manually.

### TypeScript types (generated from Pydantic)

```ts
// frontend/src/app/lib/api/skills.ts

export type SkillOwner = {
  account_id: string;
  shared_with_accounts: string[]; // always [] in v1; reserved for v2 cross-account sharing
};

export type SkillVisibility = "private";
export type SkillStatus = "draft" | "published" | "archived";

export type SkillSource =
  | { type: "authored" }
  | { type: "github"; repo: string; sha: string; license?: string };

export interface Skill {
  skill_id: string;
  owner: SkillOwner;                       // skills are account-scoped (SK-PRD-01)
  name: string;
  description: string;
  current_version: number;
  visibility: SkillVisibility;
  status: SkillStatus;
  source: SkillSource;
  has_scripts: boolean;
  created_at: string;   // ISO 8601
  created_by: string;   // user_id of the authoring user (display-only)
  updated_at: string;
  updated_by: string;   // user_id of the user who last edited
}

export interface SkillFrontmatter {
  name: string;
  description: string;
  license?: string;
  compatibility?: string;
  metadata?: Record<string, string>;
  "allowed-tools"?: string;
}
```

All IDs use branded string types per CLAUDE.md C-5:
```ts
export type SkillId = Brand<string, "SkillId">;
```

### Live validation (client-side, before submit)

The editor runs the same validation rules as the backend:
- `name` matches `/^[a-z0-9]+(-[a-z0-9]+)*$/`, ≤ 64 chars
- `description`: 1–1024 chars
- `compatibility`: ≤ 500 chars
- SKILL.md body ≤ 5000 bytes (counted as UTF-8)
- Files in `references/` ≤ 100 kB each, **≤ 20 total** files in `references/`. `assets/` and `scripts/` have no separate file-count cap and are constrained by the total-bundle cap (≤ 2 MB) only.
- Total bundle ≤ 2 MB

On submit, the backend re-validates. If client-side missed something (e.g., allowed-but-unusual YAML), the error surfaces in the top banner.

### Latest-wins skill version semantics (UX requirement)

Skills are attached to agents by `skill_id` only — agents always load the **current_version**. Editing a skill propagates immediately to every agent that has it attached, with no re-attach required. There is no per-attachment version pinning in v1.

The editor MUST surface this when a user begins editing a skill that is currently attached to one or more agents:

- **Attachment-aware banner:** When loading the editor for an existing skill, fetch the count of agent configs whose `skill_ids` contain this skill (via a backend helper, e.g., `GET /api/v1/accounts/{account_id}/skills/{id}/attached-agents-count` — owned by SK-PRD-04). If the count is ≥ 1, show a sticky banner above the editor:
  > "This skill is attached to **N agent(s)**. Saving a new version updates them immediately — there is no per-attachment version pinning in v1."
- **Save-confirmation dialog:** When the user clicks "Save draft" or "Publish" on a previously-attached skill, the confirm dialog repeats the count and includes a one-click way to view the affected agents' names (drawer or popover).

The `attached-agents-count` endpoint is delivered by SK-PRD-04 alongside the picker work. SK-PRD-03 stubs against the contract and renders a non-blocking placeholder if the endpoint is not yet live.

### Test drawer semantics

The test drawer is a **thin wrapper over the existing chat endpoint**, not a new endpoint. Under the hood:
1. The Skills team does NOT own the chat endpoint. Instead, invoke the existing `/api/v1/chat` with an ephemeral agent config (a handle that causes the agent factory to build a one-off agent with just this skill attached — see Sprint 2.6-D for the ephemeral-agent concept).
2. For Sprint 2.6-C, if that mechanism isn't ready, the test drawer is behind a feature flag `VITE_SKILLS_TEST_DRAWER=true` and defaults OFF.

### Monaco configuration

- Language: `markdown`
- Theme: match the existing code-editor theme in the frontend
- Height: 60% viewport, resizable
- Features enabled: line numbers, word-wrap, char counter in bottom bar

## 5. Implementation outline

| Action | File |
|---|---|
| Create | `frontend/src/app/pages/workflows/skills/SkillsListPage.tsx` |
| Create | `frontend/src/app/pages/workflows/skills/SkillEditPage.tsx` |
| Create | `frontend/src/app/pages/workflows/skills/SkillCreatePage.tsx` |
| Create | `frontend/src/app/pages/workflows/skills/components/FrontmatterForm.tsx` |
| Create | `frontend/src/app/pages/workflows/skills/components/SkillMdEditor.tsx` (Monaco wrapper) |
| Create | `frontend/src/app/pages/workflows/skills/components/ReferenceFileUploader.tsx` |
| Create | `frontend/src/app/pages/workflows/skills/components/ValidationPanel.tsx` |
| Create | `frontend/src/app/pages/workflows/skills/components/VersionHistoryDrawer.tsx` |
| Create | `frontend/src/app/pages/workflows/skills/components/TestSkillDrawer.tsx` (flag-gated) |
| Create | `frontend/src/app/lib/api/skills.ts` — typed API client |
| Create | `frontend/src/app/hooks/useSkills.ts` — React Query hooks |
| Create | `frontend/src/app/lib/validation/skillFrontmatter.ts` — client-side validator (shared logic) |
| Modify | `frontend/src/app/pages/workflows/WorkflowsLayout.tsx` — add Skills tab |
| Modify | Routing config — register the three new routes |
| Create | `*.test.tsx` for every new component (colocated, per T-2) |

### Page structure (list)

```
┌──────────────────────────────────────────────────────────┐
│ Workflows                                                 │
│ ┌──────────┬────────────┬──────────┬──────────────┐       │
│ │ Agents   │ Automations│ Skills 🟢│ ...          │       │
│ └──────────┴────────────┴──────────┴──────────────┘       │
│                                                           │
│  Your Skills                     [ + New Skill ] [⚙︎]     │
│  ┌──────────────────────────────────────────────────┐     │
│  │ Name            Description        v    Status    │     │
│  ├──────────────────────────────────────────────────┤     │
│  │ seo-checklist   SEO optimizat…    3   Published  │     │
│  │ blog-outliner   Draft blog outl…  1   Draft      │     │
│  │ …                                                 │     │
│  └──────────────────────────────────────────────────┘     │
│                                                           │
│  Empty state:                                             │
│  "Skills package instructions for your agents. Make       │
│   your first one to save your team's playbooks."          │
│   [ Create a skill ]    [ Read the guide ↗ ]              │
└──────────────────────────────────────────────────────────┘
```

### Page structure (editor)

```
┌──────────────────────────────────────────────────────────┐
│ ← Skills / seo-checklist · v3 · Draft                     │
│ ┌───────────────┐ ┌──────────────────────────────────┐   │
│ │ Frontmatter   │ │  SKILL.md body                   │   │
│ │               │ │  ┌────────────────────────────┐   │   │
│ │ Name          │ │  │ (Monaco editor, markdown) │   │   │
│ │ [seo-check…]  │ │  │                            │   │   │
│ │ (kebab, ≤64)  │ │  │                            │   │   │
│ │               │ │  │                            │   │   │
│ │ Description   │ │  │                            │   │   │
│ │ [SEO opt…]    │ │  └────────────────────────────┘   │   │
│ │ 218 / 1024    │ │  📏 3,421 bytes / 5,000 limit    │   │
│ │               │ │                                  │   │
│ │ License       │ │  Reference files                 │   │
│ │ [Apache-2.0]  │ │  ┌─────────────────────────────┐ │   │
│ │               │ │  │ references/style-guide.md   │ │   │
│ │ allowed-tools │ │  │ assets/tone-matrix.png  [×] │ │   │
│ │ [Read create_ │ │  │ + Drag or click to upload   │ │   │
│ │  visualization│ │  └─────────────────────────────┘ │   │
│ │ ]             │ │                                  │   │
│ └───────────────┘ └──────────────────────────────────┘   │
│                                                           │
│  ▼ Validation — 1 warning                                 │
│    • allowed-tools references "write_file" which is not   │
│      available to your agents (restriction will be empty) │
│                                                           │
│  [ Save draft ]  [ Publish ]  [ Test with agent ▸ ]       │
└──────────────────────────────────────────────────────────┘
```

## 6. API contract

All endpoints owned by Sprint 2.6-A. This PRD only consumes them via the React Query hook layer.

## 7. Acceptance criteria

1. **Tab present:** `/workflows/skills` is reachable from the Workflows layout; shows the Skills tab alongside Agents and Automations.
2. **Create a skill:** User fills the create form, uploads SKILL.md + 1 reference, clicks "Save draft". Skill appears in the list with status "Draft".
3. **Live validation:** Typing an uppercase letter in `name` shows an inline error ("lowercase only"); submitting is blocked until fixed. Body >5 kB surfaces a warning on the char counter and blocks submit.
4. **Edit a skill:** Clicking a row opens the editor with current content. Making a change and saving creates version 2 (current_version increments in the UI). Previous version is visible in the Version History drawer.
5. **allowed-tools warning:** If `allowed-tools` references a tool name that doesn't exist in the known tool registry, a warning is shown but the skill can still be saved. Rationale: tool availability is agent-specific; warning, not blocker.
6. **Scripts warning:** Uploading a file under `scripts/` shows an info callout: "Scripts only run when the target agent has sandbox code execution enabled. Learn more ↗." The file is still accepted.
7. **Archive:** Clicking Archive opens a confirm dialog explicitly stating "Archive is permanent — the bundle is moved to a 30-day trash bucket and there is no UI to restore." On confirm, the skill's status becomes "Archived" and it's hidden from the default list view. An "Include archived" toggle reveals it.
7a. **Attachment-aware editor banner:** Editing an existing skill attached to ≥ 1 agents shows the latest-wins banner above the editor. The save-confirmation dialog repeats the count with a "View affected agents" affordance.
8. **Empty state:** A user with 0 skills sees the first-skill onboarding copy and a single CTA.
9. **Test drawer (flag-gated):** Behind `VITE_SKILLS_TEST_DRAWER=true`, clicking "Test with agent" opens a drawer with a chat textarea; submitting calls the existing chat endpoint with the skill attached to a one-off agent; the response renders. OFF by default until Sprint 2.6-D lands the ephemeral-agent mechanism.
10. **Accessibility basics:** All form fields have labels; the Monaco editor has a `aria-label`; color contrast meets WCAG AA on the validation panel.
11. **All frontend tests pass** (`npm test`); type check passes (`npm run typecheck`); format fix passes (`npm run format.fix`).

## 8. Test plan

### Component tests (colocated, `*.test.tsx`)

- `FrontmatterForm.test.tsx`: name regex enforcement, description length counter, metadata key/value CRUD
- `SkillMdEditor.test.tsx`: char counter accuracy on UTF-8 (emoji, multi-byte chars)
- `ReferenceFileUploader.test.tsx`: 20-file limit on `references/` enforced; `assets/` and `scripts/` accept >20 files (constrained only by the total-bundle cap); >100 kB per-file rejected uniformly across all three directories; drag-drop works; scripts/ path triggers info callout
- `ValidationPanel.test.tsx`: shows server errors surfaced from a failed POST; clears on successful re-submit
- `SkillsListPage.test.tsx`: empty state renders when list is empty; archive toggle filters correctly
- `VersionHistoryDrawer.test.tsx`: renders all versions; clicking a row shows that version's SKILL.md

### Integration (Playwright, stretch if time)

- `skills-author-flow.spec.ts`: user visits `/workflows/skills`, clicks "New Skill", fills form, saves, sees the skill in the list

### API hook tests

- `useSkills.test.ts`: mocks the API, verifies the hook returns the expected data shape; cache invalidation after a PUT refreshes the list

## 9. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| Monaco bundle size inflates the frontend build | Lazy-load the editor route — don't bundle Monaco on unrelated pages |
| Client-side validation drifts from backend | Share validation rules via a typed schema module (`skillFrontmatter.ts`); regenerate from the Pydantic schema if available |
| User uploads a .env or credentials file as a reference | Block by extension; show an explicit error listing disallowed extensions (.env, .pem, .p12, .key) |
| Test drawer depends on ephemeral-agent concept not yet built | Feature-flag OFF by default; land in 2.6-D when the mechanism exists |
| Large version history hurts editor page load | Version history lazy-loads on drawer open, not on page mount |

### Open questions

- **Q:** Should deleting the last version of a skill be possible, or only archive? → **v1: archive-only.** No version deletion UI; preserves audit trail.
- **Q:** Should we add a "duplicate skill" action in v1? → **Defer.** Low-cost to add in v1.1; not on the critical path.

## 10. Reference

- Parent plan: [`../skills-implementation-plan.md`](../skills-implementation-plan.md) §2 (Architecture)
- Sister sprint: [`SK-PRD-01-skills-backend.md`](./SK-PRD-01-skills-backend.md) (API contract)
- Sister sprint: [`SK-PRD-04-agent-builder-controls.md`](./SK-PRD-04-agent-builder-controls.md) (picker that consumes the list this page creates)
- Figma: [KEN-E UI V2 — Soft Maximalism](https://www.figma.com/make/fhkgWZyTHdKtvDNRoQrcMT/KEN-E-UI-V2---Soft-Maximalism) (Workflows > Skills; design to be created if not yet present)
- `frontend/CLAUDE.md` — CSS architecture, component library conventions
- CLAUDE.md rules in scope: C-5, C-6, C-8; T-2, T-5; G-2, G-3
