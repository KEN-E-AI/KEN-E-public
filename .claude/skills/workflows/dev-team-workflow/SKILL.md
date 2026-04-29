# Workflow SKILL: Dev Team

## Purpose

This SKILL defines the complete development workflow for Dev Team agents. Each component has a dedicated Dev Team agent that receives issue delegations from the SCRUM Master, produces Implementation Plans for Product Owner approval, implements the solution using specialist sub-agents, runs automated review and verification, creates Test Instructions for the Test Team, and handles test failure resolution.

**Runtime:** Claude Code session on GCE instance. Cloud Tasks dispatch triggers the agent trigger service, which starts a new Claude Code session.

**Component context:** The startup script resolves the issue's Linear team to a component name and pre-injects the component's `README.md` + every PRD in its `projects/` subdirectory at the top of the prompt (above the EVENT line). The injected text covers Levels 2 and 3 of the four-level context stack (see Step 1 below). It does **not** cover Level 1 (system architecture) or Level 4 (Linear issue + siblings) — those you must load yourself.

**Canonical component-docs layout (used by every repo):**

```
docs/
├── {Repo-Name}-System-Architecture.md   ← Level 1 — load yourself
└── design/
    └── components/
        └── {component-name}/
            ├── README.md                 ← Level 2 — pre-injected
            └── projects/
                ├── {PRD-1}.md            ← Level 3 — pre-injected (all PRDs concatenated)
                ├── {PRD-2}.md
                └── ...
```

Some components have no `projects/` directory yet (no project-level PRDs authored). In that case only the README is pre-injected; the SKILL handles missing Level 3 explicitly under Step 1 below.

**Re-read from disk anyway.** The pre-injected copy is a snapshot from VM boot; if you intend to cite a specific paragraph or use the file's contents to drive a decision, re-read from disk so you see the current state and can quote line numbers. Treat the prompt-injected copy as a reading aid, not a substitute for opening the file.

**Runtime mode:** `claude --print` (single-shot, non-interactive). Slash commands (e.g. `/review`), plugins (`ralph-loop`), and plan mode are **not available**. All verification runs as shell commands and via parallel `code-reviewer` / `security-auditor` agent delegation (see Step 6). Linear updates via curl with `LINEAR_ACCESS_TOKEN`.

**Reading issue comments:** When querying comments on a Linear issue, always include the `isResolved` field and **skip resolved comments**. Resolved comments are stale artifacts from prior runs or superseded content. Only read unresolved comments — they represent the current, authoritative state of the issue. Example query:

```graphql
query {
  issue(id: "ISSUE_ID") {
    comments(filter: { resolved: { eq: false } }) {
      nodes { id body createdAt user { name } }
    }
  }
}
```

If the `filter` argument is not supported, fetch all comments with `isResolved` and discard those where `isResolved: true` in your own logic.

## Triggers

The webhook receiver dispatches a fresh Claude Code session on each Linear event. Each dispatch injects an EVENT line into the agent's prompt that names the flow to execute. The table below lists every dispatch that reaches this agent; the "Event wording" column is the authoritative phrasing the agent will see.

| Linear transition | Event wording (excerpt) | Flow |
|-------------------|-------------------------|------|
| Issue assignee changed to Dev Team user | "delegated to Dev Team. Execute Flow 1: Planning & Approval." | Flow 1 |
| Status: Awaiting Review → Planning | "PO has requested changes to the Implementation Plan. Read the PO's feedback comment on the issue and revise the plan. Execute Flow 1: Planning & Approval." | Flow 1 (revision) |
| Status: Awaiting Review → In Progress | "PO has approved the Implementation Plan. Execute Flow 2: Implementation." | Flow 2 |
| Status: Planning → In Progress | "Dev Team auto-approved the Implementation Plan (no blocking questions identified). Execute Flow 2: Implementation." | Flow 2 |
| Status: Testing Complete → In Progress | "PO rejected this issue during Cycle review. Read the PO's rejection comment and execute Flow 4: PO Rejection (Post-Testing)." | Flow 4 |
| Status: → Resolving Test Issues | "has test failures. Execute Flow 3: Resolving Test Issues." | Flow 3 |

Transitions that are NOT dispatched to this agent (intentional, to avoid duplicate VMs when the agent itself changes status mid-session): Resolving Test Issues → In Progress (Flow 3 Step 10), any status change triggered within an active Dev Team session.

---

## Flow 1: Planning & Approval

**Entry:** Dispatched in two cases, distinguished by the EVENT line in the prompt:

- **Initial delegation** — the SCRUM Master (or webhook assignee-change) assigned the issue to the Dev Team. Issue is typically in "Awaiting Assignment." Begin from Step 1.
- **Plan revision request** — PO moved the issue from "Awaiting Review" back to "Planning" with feedback. Issue is already in "Planning." Skip the status change in Step 1, read the PO's most recent unresolved comment for feedback, and revise the existing plan rather than drafting from scratch.

In both cases, the output is a single Implementation Plan comment on the issue, followed by Step 3's routing decision.

### Step 1 — Set Status and Load Context

1. Set the issue status to "Planning" using the Linear API.
2. Read `CLAUDE.md` for repo-wide code guidelines (if not already in context).

Then load context in four levels, from broadest (the entire product) to most tactical (this single issue). Every level is mandatory — skipping one leads to plans that miss product intent, component architecture, project-level requirements, or issue scope. The **Project Context** section of the Implementation Plan (see Step 2) is the audit trail showing all four levels were consulted; the PO will reject plans whose Project Context does not cite project-specific content from each level.

The hierarchy:

| Level | What | Where | Pre-injected? |
|-------|------|-------|---------------|
| 1 | System architecture / product requirements | `docs/{Repo}-System-Architecture.md` (or repo's product-requirements doc) | No — load it |
| 2 | Component README | `docs/design/components/{component}/README.md` | Yes (re-read anyway) |
| 3 | Project PRD (the spec for this issue's Linear Project) | `docs/design/components/{component}/projects/{PRD-ID}*.md` | Yes (one of N PRDs concatenated above the EVENT line) — re-read the specific PRD anyway |
| 4 | Linear issue body + sibling-issue summaries | Linear API | No — query it |

#### Level 1 — System Architecture (highest)

Every repo has a single canonical system-architecture / product-requirements document at `docs/`. Read it end-to-end. It explains what the product is, who it is for, the major components and how they fit together, and the cross-cutting concerns (context management, orchestration, infrastructure, security). Without it, you will plan against a component in isolation and miss its place in the wider system.

Discovery:

```bash
# Preferred: the repo's CLAUDE.md names the canonical doc.
grep -nE "System.?Architecture|Product Requirements" /home/agent/workspace/CLAUDE.md | head -20

# Fallback: enumerate top-level docs/ for the architecture doc.
ls /home/agent/workspace/docs/*.md
```

Known canonical paths:
- **KEN-E** (`KEN-E-AI/KEN-E`) — `docs/KEN-E-System-Architecture.md`
- **Fun-E** (`KEN-E-AI/FUN-E`) — `docs/FUN-E-System-Architecture.md`

If the repo has neither pattern, the repo's `CLAUDE.md` will name the right doc under "Context Loading Sequence" or an equivalent section. If you cannot find one, note this under **Project Context** in the Implementation Plan and proceed — but flag it under **Questions for PO (Blocking)** since the absence of a system-level doc is suspicious.

#### Level 2 — Component README

Read `docs/design/components/{component}/README.md` end-to-end. This is the component's authoritative architecture doc — its key directories, data flow, API contracts, key abstractions, and dependencies on other components. Each Linear team owns exactly one component, so the README is the same on every issue in that team.

The startup script pre-injects the README into the prompt above the EVENT line. **Re-read it from disk** so you see the current state (the prompt-injected copy is a VM-boot snapshot) and can cite line numbers if needed.

The `{component}` directory name is the same as the value the startup script printed in its `=== Loading component context: ... ===` log line, and matches the entry for your Linear team in `Fun-E/agents/webhook-receiver/main.py` `TEAM_COMPONENT_MAP`. If the README does not exist at the canonical path, abort with a clear comment on the issue rather than guessing.

#### Level 3 — Project PRD (the spec for this issue's Linear Project)

Every issue belongs to a Linear Project, and every Linear Project maps **1:1 to a single PRD document** at `docs/design/components/{component}/projects/{PRD-ID}*.md`. The PRD is the spec — it defines the project's full acceptance criteria, data contracts, implementation outline, and test plan. The Linear Project description is a one-paragraph summary that points to the PRD, not a substitute for the PRD.

Linear Project naming convention (per `CLAUDE.md` §Linear Workflow Conventions): `<PRD-ID>: <PRD title>` — e.g., `A-PRD-01: Data Model and API` maps to `docs/design/components/automations/projects/A-PRD-01-data-model-and-api.md`.

Steps:

1. Fetch the Linear Project that owns this issue (the issue's `project` field):

   ```graphql
   query {
     issue(id: "ISSUE_ID") {
       project { id name description content }
     }
   }
   ```

2. Extract the PRD-ID prefix from the project name (e.g., `A-PRD-01` from `A-PRD-01: Data Model and API`).

3. Locate the PRD file by prefix and read it end-to-end:

   ```bash
   ls /home/agent/workspace/docs/design/components/{component}/projects/{PRD-ID}*.md
   ```

4. Compare the PRD against the Linear Project description. If the project description says something the PRD does not (e.g., a scope amendment added after the PRD was last edited), treat the project description as a delta on top of the PRD and call out the divergence under **Decisions & Assumptions** or **Questions for PO (Blocking)** depending on its impact.

**Why re-read the PRD even though it was pre-injected.** The startup script concatenates *every* PRD in the component's `projects/` directory into the prompt. For components with many PRDs that's a wall of text where the boundary between PRDs is easy to lose. Re-reading the specific PRD tied to your project keeps the right scope in focus — and lets you cite line numbers in the Implementation Plan.

**If no project PRD exists.** Some components (or new components) have no `projects/` subdirectory. If `ls` returns nothing, note this explicitly in **Project Context** ("Component has no project PRDs yet — using component README + Linear Project description as the spec") and proceed with the Linear Project description as the authoritative source. Do NOT block on this; new components legitimately have no PRDs yet.

**If the issue has no project.** If `issue.project` is null, note it under **Project Context** and flag it under **Questions for PO (Blocking)** — orphaned issues are unusual and usually unintentional.

#### Level 4 — Assigned Issue + Project Issue List (tactical)

1. Read the assigned issue's full description, acceptance criteria, labels, and estimate. Per `CLAUDE.md` §Linear Workflow Conventions, each issue captures one of the PRD's §7 acceptance criteria + its implementation scope, so cross-reference the issue's ACs against the PRD's §7 to confirm you have the right slice.
2. Query Linear for all other issues in the same Project. For each sibling, capture identifier, title, status, estimate, labels, and first-paragraph summary. **Do NOT read each sibling's full body** — summary-level awareness is the goal. Read a sibling in full only if it is an explicit blocker or design reference for the assigned issue.

   Example query:

   ```graphql
   query {
     project(id: "PROJECT_ID") {
       issues(first: 50) {
         nodes {
           identifier
           title
           state { name }
           estimate
           labels { nodes { name } }
           description
         }
       }
     }
   }
   ```

3. **If the issue modifies the frontend** (new or modified UI, layouts, components, styling, or pages) AND the repo has a `docs/figma-export/` directory, review the corresponding design there. Designs are authored in Figma Make and exported as a working code repository — when present, it is the authoritative source for visual intent, and frequently contains working reference implementations that should be adapted into the repo's frontend path rather than written from scratch.

   Key paths to check (when `docs/figma-export/` exists):
   - `docs/figma-export/src/app/layouts/` — page-level layouts (e.g., `LayoutC.tsx`)
   - `docs/figma-export/src/app/components/` — component reference implementations
   - `docs/figma-export/src/app/pages/` — page compositions
   - `docs/figma-export/src/styles/theme.css` — design tokens (CSS custom properties)
   - `docs/figma-export/guidelines/ken-e_design_guidelines.md` — parent design system guidelines

   If `docs/figma-export/` does not exist in this repo, rely on the design references named directly in the issue or component PRD.

   In the Implementation Plan, **explicitly list the specific files in `docs/figma-export/` that map to this issue's scope** (when applicable). The `frontend-engineer` specialist reads the plan first and is expected to start from those files rather than write from scratch.

4. Identify existing patterns and conventions in the repo's frontend and backend paths (named in the PRD) and — for frontend tasks — the Figma export when present.

### Step 2 — Create Implementation Plan
Analyze the issue and produce an Implementation Plan in the normal output flow (plan mode is not available in `--print`). Follow these steps:

1. Analyze the issue to understand the work that must be completed to ensure that all acceptance criteria are met
2. Create the list to tasks that must be completed, the appropriate specialist agent that should be assigned to complete each task (ex. frontend, API, database)
3. For each task, create a description a list of acceptance criteria, and verification instructions. Ensure that each task is complete and leaves the system in a working state. Example:
```markdown
#### Task [N]: [Short descriptive title]

**Description:** One paragraph explaining what this task accomplishes.

**Acceptance criteria:**
- [ ] [Specific, testable condition]
- [ ] [Specific, testable condition]

**Verification:**
- [ ] Tests pass: `<repo's test command> -- --grep "feature-name"` (e.g. `npm test` or `uv run pytest`)
- [ ] Build succeeds: `<repo's build command>` (e.g. `npm run build`)
- [ ] Manual check: [description of what to verify]

**Dependencies:** [Task numbers this depends on, or "None"]

**Parallelizable with:** [Task numbers whose **Files likely touched** do not overlap with this task's. Eligible for concurrent `Agent` dispatch. Default: "None (run sequentially)".]

**Figma export references:** [frontend tasks only; for non-frontend tasks or repos without `docs/figma-export/` write "N/A"]
- `docs/figma-export/src/app/components/Foo.tsx` — adapt directly into the repo's `<frontend-path>/components/Foo.tsx`
- `docs/figma-export/src/app/pages/Bar.tsx` — reference for page layout only (not a direct copy)
- (or "None — no matching reference exists in the export; build from scratch following the design guidelines")

**Files likely touched:**
- `src/path/to/file.ts`
- `tests/path/to/test.ts`

**Estimated scope:** [Small: 1-2 files | Medium: 3-5 files | Large: 5+ files]
```
4. Identify the dependency graph by mapping which tasks depends on each other
5. Organize tasks into waves that can be completed in parallel based on the dependency graph
6. Classify every unresolved question from the task breakdown into one of two categories. This classification determines whether the plan requires PO review (see Step 3).

   **Flag under "Questions for PO (Blocking)"** — the plan cannot proceed to implementation without an answer:
   - Acceptance criteria are ambiguous or conflict with each other
   - A design reference (Figma/PRD section) is missing for a material part of the UI
   - A cross-component dependency is undefined or disputed
   - The approach would cross architectural boundaries the component PRD does not sanction
   - Business logic has multiple reasonable interpretations with different user-visible impacts

   **Record under "Decisions & Assumptions"** — resolve autonomously and document the choice + rationale:
   - Minor naming, file organization, or stylistic choices
   - Implementation details with a reasonable default (e.g., debounce interval, cache TTL, retry count)
   - Ordering of sub-tasks within a wave
   - Test structure and coverage breadth
   - Local dev config values (ports, fixtures)

   Be honest: flagging a question as blocking when it isn't wastes the PO's time and stalls the Cycle. Failing to flag a genuinely ambiguous requirement wastes your own work when it surfaces later at integration review. Err on the side of resolving autonomously when a sensible default exists and documenting it under **Decisions & Assumptions** — the PO can still reject an assumption by reading the plan and responding.
7. Create checkpoints after every 1-3 tasks to confirm:
- [ ] All tests pass
- [ ] Application builds without errors
- [ ] Core user flow works end-to-end
8. Create the final Implementation Plan document to follow this schema exactly:

```markdown
# Implementation Plan: [Feature/Project Name]

### Problem Statement
[What this issue solves, derived from the user story and acceptance criteria]

### Proposed Approach
[High-level description of the solution — what will be built and how]

### Project Context
[Audit trail showing the plan was written with all four levels of context loaded. The PO uses this section to verify the Dev Team consulted the right context before planning. Cite specific content from each level — boilerplate that doesn't quote project-specific material is a failure.]
- **Level 1 — System Architecture:** {the doc you read, e.g., `docs/KEN-E-System-Architecture.md`} — {one sentence on the cross-component constraint or framing that applies to this work}
- **Level 2 — Component README:** {`docs/design/components/{component}/README.md`} — {one sentence on the component conventions, key abstractions, or API contracts that shape this work}
- **Level 3 — Project PRD:** {`docs/design/components/{component}/projects/{PRD-ID}*.md`} — {one sentence on the PRD's scope and the project ACs this issue contributes to, verbatim from §7}. If no PRD file exists, state that explicitly and cite the Linear Project description as the spec.
- **Linear Project:** {project name} — {one-line summary of the project's goal} {plus any deltas the project description adds on top of the PRD}
- **Position in project:** {e.g., "Issue 3 of 9 — depends on FUN-X (Done), parallel with FUN-Y (In Progress), unblocks FUN-Z"}
- **Related project issues of note:** {any 1-2 sibling issues whose scope materially informs this issue, or "None — this issue is independent within the project"}

### Architecture Decisions
[Key technical choices: patterns used, libraries selected, service boundaries affected]
- [Key decision 1 and rationale]
- [Key decision 2 and rationale]

## Task List

### Phase 1: Foundation
- [ ] Task 1: ...
- [ ] Task 2: ...

### Checkpoint: Foundation
- [ ] Tests pass, builds clean

### Phase 2: Core Features
- [ ] Task 3: ...
- [ ] Task 4: ...

### Checkpoint: Core Features
- [ ] End-to-end flow works

### Phase 3: Polish
- [ ] Task 5: ...
- [ ] Task 6: ...

### Checkpoint: Complete
- [ ] All acceptance criteria met
- [ ] Ready for review

## Risks and Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| [Risk] | [High/Med/Low] | [Strategy] |

### Files & Modules Affected
[List of files/directories that will be created or modified]

### Risk Assessment
[Anything that might go wrong, unknowns, dependencies on other issues or external systems]

## Decisions & Assumptions
[Autonomous resolutions made by the Dev Team — minor design choices, ordering, defaults, naming. For each item: what was decided, the rationale, and what would invalidate it. The PO can override any of these by rejecting the plan.]
- [Decision 1 — what / why / what would invalidate it]
- [Decision 2 — what / why / what would invalidate it]

## Questions for PO (Blocking)
[Questions the PO MUST answer before implementation can begin. Use the classification rubric in Step 2.6. Each item: what is unclear, why it blocks planning, and what answer would unblock it. **If this section is empty, the plan auto-advances to implementation in Step 3.**]
- [Blocking question 1 — what is unclear / why it blocks / what answer unblocks]
```

**Plan quality requirements:**
- [ ] The Problem Statement must connect directly to the user story's "so that..." clause
- [ ] The Proposed Approach must be specific enough that a reviewer can evaluate feasibility — no vague statements like "refactor the component"
- [ ] The **Project Context** section cites all four levels with specific content: names the Level 1 system-architecture doc and a relevant constraint, names the Level 2 component README and a relevant convention, names the Level 3 project PRD (or explicitly notes none exists) and at least one §7 AC this work delivers, and places the issue in the Linear Project's issue list (position + a named blocker or dependent sibling). Boilerplate that doesn't cite project-specific content from each level is a failure.
- [ ] Every task must have acceptance criteria
- [ ] Every task must have a verification step
- [ ] Task dependencies are identified and ordered correctly
- [ ] Every task's **Parallelizable with** field lists only tasks whose **Files likely touched** are verifiably disjoint from this task's — or "None". Do not mark tasks as parallelizable on the basis of dependency order alone.
- [ ] No task touches more than ~5 files unless absolutely necessary
- [ ] Checkpoints exist between major phases
- [ ] Architecture Decisions must reference existing patterns in the codebase (read the code first)
- [ ] Files & Modules must list actual file paths verified against the current codebase
- [ ] Risk Assessment must identify concrete risks, not generic ones
- [ ] Every frontend-modifying task has a **Figma export references** field populated — either with specific `docs/figma-export/` paths to adapt, or "None" with justification. Non-frontend tasks may write "N/A".
- [ ] Every assumption that affects scope, architecture, or user-visible behavior is listed under **Decisions & Assumptions** (resolved autonomously) or **Questions for PO (Blocking)** (requires PO answer) — nothing load-bearing is left implicit
- [ ] Any item under **Questions for PO (Blocking)** actually matches the blocking criteria in Step 2.6 — not a preference dressed up as a blocker

### Step 3 — Submit the Plan to Linear

1. Post the Implementation Plan as a comment on the Linear issue.

The next step depends on whether the plan has any items under **Questions for PO (Blocking)**.

#### Path A — Auto-Approve (no blocking questions)

**IF the plan's "Questions for PO (Blocking)" section is empty:**

2. Post a second comment on the issue containing the auto-approval audit note:

   > **No blocking questions identified.** Auto-proceeding to implementation. The plan's **Decisions & Assumptions** section documents the autonomous resolutions made during planning. If any assumption is incorrect, set status back to "Planning" with a feedback comment and a new agent session will revise the plan before any code is written.

3. Set the issue status to "In Progress"
4. Mark this Claude Code session as complete and exit

**Do not continue into Flow 2 in this session.** Agent sessions are stateless and ephemeral. The status change to "In Progress" will dispatch a fresh agent session via the webhook, and that session will execute Flow 2: Implementation. Continuing Flow 2 here would produce two concurrent sessions working on the same branch.

#### Path B — PO Review Required (blocking questions present)

**IF the plan has one or more items under "Questions for PO (Blocking)":**

2. Post a second comment on the issue @mentioning the issue's PO (resolve via `resolve-po-for-issue` from `linear-sprint-ops`; Linear Asks surfaces this in Slack). The comment should list each blocking question, why it blocks planning, and what answer would unblock it.
3. Set the issue status to "Awaiting Review"
4. Mark this Claude Code session as complete and exit

The PO's response arrives as a status change that dispatches a new agent session:

- **PO sets status to "Planning"** (with a feedback comment) — a new agent session will read the PO's feedback from the most recent unresolved comment, revise the plan to address it, and return to Step 3 (which re-evaluates the auto-approve gate against the revised plan).
- **PO sets status to "In Progress"** (approval) — a new agent session will execute Flow 2: Implementation.

---

## Flow 2: Implementation

**Entry:** Dispatched when the issue transitions to "In Progress" from either "Awaiting Review" (PO approved) or "Planning" (Dev Team auto-approved, no blocking questions). The EVENT line distinguishes the two for audit purposes, but Flow 2's behavior is identical in both cases: the most recent Implementation Plan comment on the issue is the authoritative plan, and any items under **Decisions & Assumptions** in that plan are treated as settled unless a PO comment contradicts them.

Testing Complete → In Progress is a separate case routed to Flow 4, not here.

### Step 3.5 — Reload Context

Flow 2 runs on a fresh VM with a fresh Claude Code session. None of the context loaded during Flow 1 is available — the new session starts with only the component README + project PRDs injected by the startup script (Levels 2 + 3) and the Linear issue identifier. Before writing any code, re-load the full 4-level context stack as in Flow 1 Step 1:

1. **Level 1 — System Architecture:** the repo's system-architecture / product-requirements document end-to-end (`docs/KEN-E-System-Architecture.md` for KEN-E, `docs/FUN-E-System-Architecture.md` for Fun-E, or whatever the repo's `CLAUDE.md` names).
2. **Level 2 — Component README:** `docs/design/components/{component}/README.md` end-to-end (re-read from disk even though it was pre-injected).
3. **Level 3 — Project PRD:** the single PRD at `docs/design/components/{component}/projects/{PRD-ID}*.md` matching the issue's Linear Project (project naming convention: `<PRD-ID>: <PRD title>`). Re-read end-to-end and compare against the Linear Project description for any deltas added after the PRD was last edited.
4. **Level 4 — Assigned Issue + Project Issue List:** read the assigned issue's full description, then query all other issues in the Project for summary-level awareness (identifier, title, status, estimate, first-paragraph summary — do NOT read every sibling's full body).

Also read the most recent **Implementation Plan** comment on the issue — this is the authoritative plan, approved by the PO (or auto-approved with no blocking questions). The plan's **Project Context**, **Decisions & Assumptions**, and **Task List** sections are settled unless a PO comment posted after the plan contradicts them.

**Framing — the plan is authoritative; the re-load is verification and substrate, not re-planning.** The purpose of this step is two-fold:

- **Verify the plan's context is still current.** Time has passed between planning approval and implementation dispatch — the project description may have been edited, a sibling issue may have been added, or a new component doc may have been committed. Compare the plan's Project Context section against what you just loaded.
- **Provide substrate for mid-implementation judgment calls.** Implementation raises questions the plan doesn't fully answer (which directory matches the existing pattern, which Pydantic model belongs where, whether a naming choice aligns with conventions elsewhere in the component). Having L1-L4 in context lets you resolve these against the full picture.

**If you find a material conflict with the approved plan** — e.g., the project description now lists an AC the plan doesn't address, or a sibling issue added since approval now overlaps with this work — **do not silently re-plan**. Post a decision-log comment on the issue describing the conflict and how you intend to handle it (proceed with the plan, adapt scope within the plan's boundaries, or pause for PO input). Then proceed to Step 4.

### Step 4 — Create Branch

```bash
git fetch origin dev
git checkout -b {prefix}/{issue-identifier}-short-description origin/dev
```

**Branch prefix** is derived from the issue type or labels, aligned with the Conventional Commits types in CLAUDE.md:

| Issue Type / Label | Branch Prefix | Example |
|--------------------|---------------|---------|
| Feature, User Story | `feat/` | `feat/FUN-4-upgrade-tailwind` |
| Bug | `fix/` | `fix/FUN-12-chart-tooltip-overflow` |
| Refactor | `refactor/` | `refactor/FUN-9-extract-data-layer` |
| Test | `test/` | `test/FUN-14-add-forecast-coverage` |
| Chore, Infrastructure | `chore/` | `chore/FUN-11-update-dependencies` |
| Documentation | `docs/` | `docs/FUN-16-api-spec-update` |

If the issue type is ambiguous, default to `feat/` for new functionality or `fix/` for corrections. The slug should be 2-4 words derived from the issue title.

### Step 5 — Implement

**Before mapping tasks to specialists**, run `ls .claude/agents/` and read any agent file that isn't covered by the table in the next sub-section. Repo-local specialists (e.g., `ai-engineer` in `KEN-E-AI/KEN-E`) only exist in their home repo and are easy to miss otherwise. Reading a specialist's file before delegating is also how you confirm scope — sub-agents have no `Agent` tool of their own, so a misrouted delegation can't re-route itself.

Execute the sub-tasks defined in the Implementation Plan. For each task, decide whether to implement it directly or delegate to a specialist sub-agent.

#### Available specialist sub-agents

Specialists are defined as files in `.claude/agents/`. Invoke them via the `Agent` tool, setting `subagent_type` to the agent's `name` field.

Specialists come from two sources, merged at boot per the no-clobber rule in `docs/dev-workflow.md` §"Skills + agents are baked into the VM image":

- **Image-baked** — defined in Fun-E `.claude/agents/`, baked into the VM image, available in every repo. The first four rows below.
- **Repo-local** — defined in the cloned repo's own `.claude/agents/`, present only when working in that repo. Wins over the image-baked version if the names collide.

Before delegating, **enumerate the actual `.claude/agents/` directory in the cloned workspace** (`ls .claude/agents/`) so you discover any repo-local specialists not listed below. The table is the cross-repo baseline, not a closed set.

| `subagent_type` | Use for | Available in | File |
|-----------------|---------|--------------|------|
| `frontend-engineer` | React components, hooks, pages, forms, React Query wiring, Tailwind styling, Recharts visualizations | All repos (image-baked) | `.claude/agents/frontend-engineer.md` |
| `backend-engineer` | FastAPI routes, Pydantic models, service layer, async I/O, Python data processing | All repos (image-baked) | `.claude/agents/backend-engineer.md` |
| `design-token-engineer` | CSS custom properties, token scales, WCAG contrast audits, dark mode variants, gradient definitions | All repos (image-baked) | `.claude/agents/design-token-engineer.md` |
| `test-engineer` | New Vitest / pytest files, axe-core a11y assertions, hypothesis property tests | All repos (image-baked) | `.claude/agents/test-engineer.md` |
| `ai-engineer` | Google ADK (`google-adk`) work in `app/adk/` — ADK Agents, sub-agent dispatch, tool registration, MCP server config, ADK callbacks (`before/after_tool`, `before/after_agent`, `after_model`), session state, Vertex AI Agent Engine deployment | `KEN-E-AI/KEN-E` only (repo-local) | `.claude/agents/ai-engineer.md` |

Each agent file defines what it owns, its conventions, and what it hands back. If you're unsure whether a task matches an agent, read the agent file before delegating.

#### When to delegate vs. implement directly

**Delegate when:**
- The task is clearly scoped to one specialist's domain
- The specialist's focused context adds value (e.g., `design-token-engineer` reads the design guidelines doc so you don't have to)
- Independent tasks can run in parallel (send multiple `Agent` calls in one turn)

**Implement directly when:**
- The task crosses domain boundaries in a way that would cause conflicts (e.g., a component needs a new token + the new token needs to be used by the component — delegate the token to `design-token-engineer`, then wire it up yourself)
- The task is trivial (one-line fix, rename, config tweak, import path update)
- The task is orchestration: branch setup, commits, PR body, Test Instructions, integrating results across sub-agents

#### Delegation mechanics

1. **Order tasks by dependency.** Tokens before components; backend models before frontend data-fetching; fixtures before tests that consume them.
2. **Parallelize only when file scopes are disjoint.** Send multiple `Agent` calls in one turn only when the tasks' **Files likely touched** lists do not overlap (e.g., one frontend task plus one backend task, or two frontend tasks in different directories). If two tasks might edit the same file — shared types, a common component, `package.json`, a route registry — run them sequentially. Sub-agents share the Dev Team's working tree; there are no per-agent worktrees, so any file overlap races. Use the plan's **Parallelizable with** field as the authoritative list; do not infer parallelism from dependency order alone.
3. **Give each sub-agent a self-contained prompt.** Sub-agents do not see this conversation. Include every file path, acceptance criterion, constraint, and piece of plan context the agent needs to act correctly.
4. **Sub-agents cannot re-delegate.** They have no `Agent` tool of their own. If a sub-agent task turns out to need a different specialty, the sub-agent will report back — reassign from here.
5. **Verify returned work.** Sub-agents report files changed plus a summary. Read the actual files to confirm the work matches the plan before moving on.
6. **Resolve conflicts yourself.** If two sub-agents touched overlapping files, you reconcile the results — don't send the conflict back.
7. **Commit frequently** in small increments with Conventional Commits messages (`type(scope): description`; see CLAUDE.md §Git Conventions).

#### Always handled by the Dev Team agent (never delegated)

- Branch creation and all `git` operations
- Reading and orchestrating the Implementation Plan's task list
- Cross-domain integration work (e.g., wiring a new backend endpoint into a new frontend hook as one task)
- PR body, Test Instructions, decision log entries
- Applying fixes found during the Review & Verify loop when the fix is confined to files the sub-agent already worked on (delegating back for a small fix is higher overhead than doing it yourself)

### Step 6 — Review & Verify Loop

After implementation, run automated checks, then delegate to external review agents, address their findings, and iterate until both the automated checks pass and the reviewers return clean reports. **The goal of this step is to catch bugs, security issues, and quality problems before the PR is opened — the normal outcome is one or more iterations, not a straight pass.** Zero iterations over multiple issues is a yellow flag; it usually means the reviewers were not given enough context, not that the code was perfect.

**6a — Automated verification (shell commands)**

Run the build, test, lint, and format commands named in the component PRD (or the repo's CLAUDE.md §Common Commands). The goal is: build passes, tests pass, lint/format clean, types clean.

Typical patterns by stack (use whatever the PRD names):

- JS/TS (npm + Vite/Vitest): `cd <frontend> && npm run build && npm test -- --run && npx prettier --check src/`
- Python (uv + pytest + ruff): `cd <backend> && uv run ruff check src/ && uv run pytest`
- Python (poetry + pytest): `cd <backend> && poetry run pytest && poetry run ruff check src/`

Any failure here is a hard stop — fix before moving to 6b. These checks are the fastest feedback loop; don't waste reviewer time on code that doesn't build.

**6b — External review (parallel delegation)**

Delegate to both review specialists in one turn — they are independent and run concurrently. Each enters with no knowledge of implementation decisions, which is the whole point: self-review by the Dev Team has been observed in practice to miss issues that these agents catch.

Fire both `Agent` calls in a single turn:

| `subagent_type` | What it returns | File |
|-----------------|-----------------|------|
| `code-reviewer` | Five-dimension review (correctness, readability, architecture, security, performance) with `APPROVE` or `REQUEST CHANGES` verdict and categorized findings | `.claude/agents/code-reviewer.md` |
| `security-auditor` | OWASP-grounded security audit with severity-classified findings and proof-of-concept for Critical/High items | `.claude/agents/security-auditor.md` |

Each delegation prompt must be self-contained and include:

- **The full diff.** Paste the output of `git diff main...HEAD` directly into the prompt. Do not tell the reviewer to run the command; reviewer tool sets may be restricted and asking them to run shell commands wastes their context budget.
- **The approved Implementation Plan.** The full Linear comment. Without this, reviewers cannot detect scope drift or identify missing acceptance criteria.
- **The issue's acceptance criteria.** What the user actually asked for, verbatim from the issue description.
- **Pointer to `CLAUDE.md` §Code Guidelines and §Security Rules** as the authoritative review criteria for this repository.
- **Explicit output instruction:** *"Return findings in the exact template specified in your system prompt, with file:line references. Do not return prose summaries in place of the template."*

**6c — Address findings**

Read both reports end-to-end before making any changes. Process findings by severity:

- **Critical** — fix immediately. No deferral permitted.
- **High** — fix immediately. No deferral permitted.
- **Medium** — fix, OR post a decision-log comment on the Linear issue with explicit reasoning for deferring (what was considered, why the cost outweighs the benefit, what would trigger revisiting). "Fix if straightforward" is not an accepted reason on its own.
- **Low / Info** — append to the PR body's review section. No code change required.

Commit the fixes as a single commit with message `fix(review): address review findings from iteration {N}`. This keeps the review-fix work traceable in the PR history.

**Sanity check on clean reports.** If both reviewers return zero Critical/High/Medium findings, do not accept at face value. Re-read the reports in full. Thin reports are a red flag:
- One-line summaries without file:line references
- Empty "Verification Story" section (for `code-reviewer`)
- Zero counts across all severities without specific observations or positive callouts
- Copy-paste template with no substantive content

If the reports look thin, re-delegate with this framing: *"Assume this code has at least one non-obvious bug. Read the diff against the Implementation Plan and find the most likely bug. Focus on edge cases, error paths, architectural mismatch with the Plan, and divergence from the conventions in `CLAUDE.md`."*

A genuine zero-finding report is possible but rare — it should be cited (specific observations from the report justifying the verdict), not assumed.

**6d — Iterate**

If any code changed in 6c, re-run from 6a. The loop exits only when all of:
- 6a is fully green (build, tests, lint, format)
- Both reviewers returned reports with zero Critical and zero High findings
- Every Medium finding is either fixed or documented with a deferral reason
- The most recent iteration produced no new code changes

**Expected normal case: 1-2 iterations.** Zero iterations over multiple issues is a yellow flag — investigate whether reviewers were given thin context or whether their reports were rubber-stamped. More than 3 iterations suggests the implementation has a structural issue; pause, reconsider the approach, and document the decision in the Linear issue before continuing.

**6e — Push and create draft PR**

1. Set the issue status to "In Review"
2. Push the working branch and create a **draft PR** targeting `main`
3. PR body must include:

```markdown
## Summary
[What changed and why — 1-3 bullets]

## Assumptions & Decisions
[Critical assumptions made during implementation and key decisions]

## Business Logic
[Domain knowledge embedded in the code that a reviewer should understand]

## Automated Test Results
[Build, test suite, lint/format — include pass/fail and counts]

## Code Review (from 6b — `code-reviewer` agent)
[Final verdict after iteration (APPROVE / REQUEST CHANGES). Counts by severity. For each Critical/High: what the finding was and how it was resolved. Any Medium deferrals with reasons. Low findings listed here.]

## Security Review (from 6b — `security-auditor` agent)
[Final verdict. Counts by severity. For each Critical/High: what the finding was and how it was resolved. Any Medium deferrals with reasons. Low/Info findings listed here.]
```

### Step 7 — Create Test Instructions & Hand Off

The Dev Team cannot verify the implementation in a browser — they run on GCE instances without display access. The Test Team runs on a Mac Mini with Claude Code CLI and Claude in Chrome for browser access. Therefore, the Dev Team must produce explicit, detailed Test Instructions that cover everything requiring visual or interactive verification.

**7a — Create Test Instructions**

Produce Test Instructions that focus on what can ONLY be verified by a human or agent looking at the actual UI in a browser. The Dev Team has already verified automated concerns (unit tests, type checking, linting, build) in the Step 6 Review & Verify Loop. The Test Instructions should cover: visual appearance, user interactions, responsive behavior, accessibility in practice, data rendering, navigation flows, and edge cases visible in the UI.

The document must follow this schema exactly:

```markdown
## Test Instructions

### Branch & Build Setup
- **Branch:** {branch-name}
- **PR:** #{pr-number} (draft)
- **Build steps:** (use the install/run commands named in the component PRD)
  1. `git fetch origin && git checkout {branch-name}`
  2. Frontend: install deps, start dev server (e.g. `cd <frontend-path> && npm install && npm run dev`)
  3. Backend (if applicable): install deps, start API server (e.g. `cd <backend-path> && uv sync && uv run uvicorn <app>:app --reload`)
  4. Open browser to the dev server URL named in the PRD (commonly `http://localhost:5173` for Vite)
- **Required accounts / test data:** [any prerequisite data or login credentials]

### What the Dev Team Already Verified
[Brief summary of automated checks that passed — unit tests, lint, type check, build.
This tells the Test Team what they do NOT need to re-verify.]

### Test Cases
#### TC-1: [Test case name]
- **What to verify:** [Specific UI behavior that requires browser access]
- **Precondition:** [Starting state — page to navigate to, data to have loaded]
- **Steps:**
  1. [Step 1 — be explicit: "Click the 'Export' button in the top-right corner"]
  2. [Step 2 — include what should visually happen: "A modal should appear with..."]
  3. [Step 3]
- **Expected Result:** [What the tester should SEE — visual state, not code state]
- **Acceptance Criterion:** [Which AC this verifies — e.g., "AC-2"]

#### TC-2: [Test case name]
...

### Edge Cases
[Additional browser-verifiable scenarios — empty states, long text truncation,
responsive breakpoints, keyboard navigation, screen reader behavior, error states
triggered by invalid input in the UI]

### Acceptance Criteria Mapping
[Map each acceptance criterion from the issue to the test case(s) that verify it]
- AC-1 → TC-1, TC-3
- AC-2 → TC-2
- AC-3 → TC-4, TC-5

[EVERY acceptance criterion must map to at least one test case.
If an AC was fully verified by automated tests, note that here:
"AC-4 → Verified by unit tests (no browser test needed)"]
```

**Test Instructions quality requirements:**
- Every acceptance criterion in the issue MUST map to at least one test case or be explicitly noted as verified by automated tests
- Test cases must focus on browser-verifiable behavior — visual state, user interaction, responsive layout, accessibility
- Branch & Build Setup must include the exact commands to check out the branch, install dependencies, and start the dev server
- Steps must be numbered, unambiguous, and reference specific UI elements by name and location (e.g., "the 'Save' button in the bottom-right of the modal")
- Expected Results must describe what the tester should SEE, not internal state
- Edge cases must include at minimum: empty state appearance, boundary text/data, responsive behavior at mobile breakpoint, and keyboard navigation

**7b — Post and Hand Off**

This is the **terminal** step of Flow 2. The issue's final status MUST be `Ready for Testing` — never `In Review`. The `In Review` status is transient (set in step 6e while the PR is being created) and must always be replaced by `Ready for Testing` once Test Instructions are posted. If the issue is left in `In Review` at the end of Flow 2, the Test Team webhook never fires and the issue stalls silently — Linear returns `success: true` for any valid state mutation, so the wrong terminal state does not surface within the Dev Team session itself.

A common failure mode is to look up both state IDs (`In Review` and `Ready for Testing`) at the start of step 7b and then pass the wrong one to `issueUpdate`. The two states are adjacent in the workflow and have similarly-shaped IDs; treat the `Ready for Testing` ID as the only valid terminal-state argument and double-check the variable being passed before issuing the mutation.

1. Post the Test Instructions as a comment on the Linear issue.
2. Set the issue status to **`Ready for Testing`** — the only valid terminal state for Flow 2. Pass the team's `Ready for Testing` state ID to `issueUpdate`, not the `In Review` ID.
3. Run the **Final State Verification** in step 7c.
4. Set the Claude Code session state to "complete".

**Important:** The draft PR remains open and unmerged. It will only be merged after testing passes AND the PO approves the final work at Cycle end.

**7c — Final State Verification (mandatory before exit)**

Before declaring Flow 2 complete, re-query the issue from Linear and confirm its status. This is a defensive check against silent state-mutation errors (wrong state ID passed, mutation succeeded but on the wrong issue, working-memory swap between similarly-named states):

```graphql
query {
  issue(id: "ISSUE_ID") {
    identifier
    state { name }
  }
}
```

**Required outcome:** `state.name == "Ready for Testing"`.

If the response shows any other state:

1. Retry the `issueUpdate` mutation once with the `Ready for Testing` state ID, being explicit about which ID is being passed.
2. Re-query and verify again.
3. If the state is still not `Ready for Testing`, do NOT mark the session complete. Post a comment on the issue:

   > **Dev Team — terminal-state verification failed.** Expected status `Ready for Testing`, observed `{actual}` after two attempts. Escalating to the PO; the issue may need a manual status correction before the Test Team can pick it up.

   Then apply the `escalation` and `po-action` labels, @mention the issue's PO (resolve via `resolve-po-for-issue` from the `linear-sprint-ops` skill), and exit. Do NOT silently mark the session complete — silent exit is the failure mode this verification exists to prevent.

This verification is not optional. The most common Flow 2 failure mode is the agent setting the wrong terminal state and exiting `success`. Without this check, the failure is invisible and only surfaces when a human notices the issue stuck in `In Review` hours later.

---

## Flow 3: Resolving Test Issues

**Entry:** The Test Team has set the issue status to "Resolving Test Issues" and posted a Test Failure Report as a comment on the issue.

**Dev-Test iteration limit:** This flow may cycle between the Dev Team and Test Team up to **6 times**. If after 6 rounds the tests still do not pass, the Dev Team must escalate to the SCRUM Master with a summary of what has been attempted, and the SCRUM Master will notify the PO (via Linear comment @mentioning the issue's PO resolved via `resolve-po-for-issue`, with `escalation` label for triage visibility) for human intervention.

### Step 8 — Load Context and Read Test Results

1. Re-load the 4-level context stack as in Flow 1 Step 1: Level 1 (system-architecture doc), Level 2 (component README), Level 3 (the project PRD matching the issue's Linear Project), Level 4 (assigned issue + sibling-issue summaries). Context can change between runs — a sibling issue may have been added, the Project description may have been edited, or a new component doc may have been committed. Do not shortcut to "the component README is enough."
2. Read the Test Team's failure report from the most recent comments on the issue
3. Read the original Implementation Plan, Test Instructions, and any prior failure reports for context
4. Count which Dev-Test iteration this is (check issue comments for prior failure reports)

### Step 9 — Create Fix Plan

Create a targeted fix plan based on the failure details. This is NOT a full Implementation Plan — it is a concise analysis of what failed and what needs to change.

If this is iteration 2 or 3, also review what was attempted in prior fix rounds and why it didn't resolve the issue.

### Step 10 — Implement Fixes and Return to Testing

1. Set the issue status to "In Progress"
2. Fetch the latest version of the working branch
3. Apply fixes based on the fix plan
4. Run the review & verify loop (same as Step 6: automated checks → parallel delegation to `code-reviewer` and `security-auditor` → address findings → iterate until clean)
5. Push the updated branch (the draft PR updates automatically)
6. Evaluate whether the Test Instructions need updating:
   - If the fix changed UI behavior, navigation paths, or expected visual results → update the Test Instructions and post a new comment on the issue noting what changed
   - If the fix was purely internal (logic bug, data issue) with no UI impact → no update needed, post a comment noting "Test Instructions unchanged — internal fix only"
7. Set the issue status to "Ready for Testing"
8. Set the Claude Code session state to "complete"

The Test Team will re-execute the Test Instructions (updated or original) when they pick up the issue.

### Step 11 — Escalation (after 6 failed iterations)

If the Dev Team is starting what would be iteration 7:

1. Do NOT attempt another fix
2. Post a comment summarizing all 3 prior attempts: what was tried, what the Test Team reported each time, and what the Dev Team believes is the root cause
3. Set the issue status to "Triage"
4. The SCRUM Master will notify the PO for human intervention

---

## Flow 4: PO Rejection (Post-Testing)

**Entry:** Dispatched when the issue transitions from "Testing Complete" to "In Progress." After all issues in the Cycle reach "Testing Complete," the PO reviews the integration branch; if they reject an issue, they add a rejection comment and set the issue back to "In Progress." The webhook disambiguates this from Flow 2 by checking the previous state — Testing Complete → In Progress routes here; Awaiting Review / Planning → In Progress routes to Flow 2.

### Step 12 — Read PO Feedback

1. Re-load the 4-level context stack as in Flow 1 Step 1: Level 1 (system-architecture doc), Level 2 (component README), Level 3 (the project PRD matching the issue's Linear Project), Level 4 (assigned issue + sibling-issue summaries). A PO rejection often surfaces because project-level intent drifted from the original plan — re-reading Levels 1 and 3 is especially important here.
2. Read the PO's rejection comment from the issue
3. Read the current Implementation Plan, Test Instructions, and Test Results for context

### Step 13 — Full Rework Cycle

The PO rejection triggers a full cycle — not just a targeted fix:

1. Fetch the latest version of the working branch
2. Implement the changes requested by the PO (same as Step 5)
3. Run the review & verify loop (same as Step 6: automated checks → parallel delegation to `code-reviewer` and `security-auditor` → address findings → iterate until clean)
4. Push the updated branch
5. Evaluate whether Test Instructions need updating (same criteria as Step 10 sub-step 6)
6. Set the issue status to "Ready for Testing"
7. The Test Team will re-verify the implementation
8. Set the Claude Code session state to "complete"

After the Test Team sets "Testing Complete" again, the SCRUM Master will notify the PO for another review.

---

## Autonomous Decision-Making

The Dev Team agent makes many decisions autonomously during implementation. The following categories of decisions can be made without human approval:

- File/module organization within established patterns
- Resource configuration for known module types
- Error handling approach for a specific endpoint
- Naming conventions following existing codebase style
- Test structure and coverage scope
- Config values for local dev (ports, dev credentials, etc.)
- Ordering of operations within a task
- Minor plan deviations that don't change scope

### Decision Logging

All non-obvious autonomous decisions must be logged. Add a decision log entry as a comment on the Linear issue when:
- The implementation deviates from the approved plan (even if the deviation is minor)
- An architectural choice was made between two reasonable alternatives
- A dependency or assumption in the Risk Assessment materialized
- The fix for a review finding changed the approach

Decision log format:
```markdown
**Dev Team — Decision Log**

| # | Decision | Rationale | Impact |
|---|----------|-----------|--------|
| 1 | Used X pattern instead of Y | Z reason, consistent with existing code in {file} | No scope change |
| 2 | Added error boundary for {scenario} | Discovered during testing that {condition} can occur | Added 1 test case |
```

---

## Human Checkpoints

There is **at most one** conditional human checkpoint within the Dev Team workflow itself:

1. **Implementation Plan approval** (Step 3) — **Conditional.** Required only when the plan contains one or more items under **Questions for PO (Blocking)**. Plans with no blocking questions auto-advance to implementation and the PO is not asked to review. When PO review IS required, the PO either approves ("In Progress") or requests changes ("Planning" with feedback comment).

When a plan auto-advances, the Dev Team posts an explicit audit comment stating "No blocking questions identified." The PO can still intervene by setting status back to "Planning" with feedback — this forces a revision before any code is written.

The PO's final review of completed work happens at the **Cycle level**, managed by the SCRUM Master — not per-issue during the Dev Team workflow. The PO only reviews after ALL issues in the Cycle reach "Testing Complete." If the PO rejects an issue at that point, it re-enters the Dev Team workflow via Flow 4.

**No code is merged until the PO sets the issue to "Done."** The draft PR remains open throughout the entire Dev-Test cycle. The merge occurs as the final step after PO approval — either by the PO directly or triggered by the "Done" status change.

---

## Multi-Issue Concurrency

A single Dev Team agent can manage 2-3 issues simultaneously, each at different stages. The SCRUM Master may delegate a second issue while the first is waiting on PO approval. When this happens:

- Each issue gets its own working branch and draft PR
- Context switching between issues is managed by the agent
- Issues at different stages (one waiting on plan approval, one in implementation, one in testing) can all be active
- If issues touch overlapping files, the agent must coordinate to avoid merge conflicts

---

## Status Transition Summary

| From | To | Trigger | Agent |
|------|----|---------|-------|
| Awaiting Assignment | Planning | Dev Team begins work (Step 1) | Dev Team |
| Planning | Awaiting Review | Plan posted with blocking questions — PO review required (Step 3, Path B) | Dev Team |
| Planning | In Progress | Plan posted with no blocking questions — auto-approved (Step 3, Path A) | Dev Team |
| Awaiting Review | Planning | PO requests plan revisions (Step 3) | PO |
| Awaiting Review | In Progress | PO approves plan (Step 3) | PO |
| In Progress | In Review | Draft PR created, automated review starting (Step 6) | Dev Team |
| In Review | Ready for Testing | Review passes, Test Instructions posted (Step 7) | Dev Team |
| Ready for Testing | Testing | Test Team begins execution | Test Team |
| Testing | Testing Complete | All browser tests pass | Test Team |
| Testing | Resolving Test Issues | Browser tests fail | Test Team |
| Resolving Test Issues | In Progress | Dev Team begins fixing (Step 10) | Dev Team |
| In Progress | In Review | Fixes complete, review loop restarting (Step 10) | Dev Team |
| In Review | Ready for Testing | Review passes, returned to testing (Step 10) | Dev Team |
| Testing Complete | In Progress | PO rejects at Cycle review (Flow 4) | PO |
| Testing Complete | Done | PO approves at Cycle review → PR merged | PO |
