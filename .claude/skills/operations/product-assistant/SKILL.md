---
name: product-assistant
description: Helps a Product Owner (or Product Manager) plan new features, author PRDs, manage Linear Projects and issues, propagate design-doc changes, and run Project Completion Review — all from a Claude Code terminal session. Use whenever the human says "plan a feature," "create a project / PRD," "update the docs," "reprioritize the backlog," "move issue X," or "review what's waiting on me as PO/PM."
---

# Operation SKILL: Product Assistant

## Purpose

Interactive SKILL that supports the Product Owner (PO) and Product Manager (PM) in the day-to-day product workflow defined in `docs/dev-workflow.md`. The human describes what they want in natural language; this SKILL orchestrates the analysis, doc updates, Linear Project / issue creation, cross-reference propagation, and PM-side completion review.

**Invoked by:** A PO or PM in a Claude Code terminal session. Examples:

- "I want to add a new export button to the dashboard. Use product-assistant to plan it, write a PRD, and create the Linear Project + issues."
- "We need to change the funnel from 4 stages to 5. Update all the design docs and create the issues."
- "Move FUN-12 to the next sprint and reprioritize the backlog."
- "What Linear Projects are waiting on me as PM?"
- "Mark Project A-PRD-03 as Completed — I just verified the ACs."
- "Update the PRD to reflect the new onboarding flow we discussed."

## When to Use

- The PO is starting a new initiative and needs to scope it into a Linear Project + PRD + child issues
- The PO needs to add, modify, reorder, or move issues across Cycles
- The PO needs to update a design document and propagate the change to dependent docs and Linear issues
- The PM needs to review Linear Projects awaiting Project Completion Review, mark them Completed, or open rework issues
- The PO/PM wants a status summary of their action queue

## When NOT to Use

- The PO is asking the SCRUM Master to redo dependency planning (use the SCRUM Master agent's Sprint Planning flow instead — `workflows/scrum-master-workflow`)
- The Dev Team is producing an Implementation Plan for an issue (that's `workflows/dev-team-workflow`, Flow 1 — not a PO activity)
- The user is asking to write code to satisfy an issue's acceptance criteria (delegate to the Dev Team workflow; do not implement from this SKILL)
- The user wants Test Team activity — Test Instructions, browser tests (delegate to `workflows/test-team-workflow`)

---

## Companion SKILLs and tools

- **`tools/linear-sprint-ops`** — All Linear API operations (issues, Projects, Cycles, labels, PO/PM resolution). Specifically used here:
  - Operation 6 (`post-comment`), 7 (`validate-issue-completeness`), 9 (`apply-po-action-label`), 13 (`resolve-po-for-issue`), 15 (`resolve-pm`), 16 (`query-project`), 17 (`apply-pm-action-label`), 18 (`update-project-state`), 19 (`audit-project-coverage`), 20 (`validate-project-completeness`), 21 (`query-pm-action-projects`), 22 (`create-project`)
- **`tools/update-design-docs`** — Cross-document dependency tracking and Linear issue propagation. Run after every design-doc change. Includes PRD-Specific Propagation (P1–P4) and Component README Propagation (R1–R3).
- **Linear MCP connector** — for ad-hoc Linear queries and updates not covered by `linear-sprint-ops`.
- **Git** — for committing doc changes or creating PRs.

## Component context

Every component in this repo follows the canonical layout:

```
docs/
├── {Repo-Name}-System-Architecture.md   ← Level 1
└── design/
    └── components/
        └── {component-name}/
            ├── README.md                 ← Level 2
            └── projects/
                ├── {PRD-1}.md            ← Level 3 (one PRD per Linear Project)
                ├── {PRD-2}.md
                └── ...
```

When updating design docs, enumerate the appropriate directory (`ls docs/design/components/{name}/projects/`) and read the relevant `.md` files before proposing changes.

The `{component}` value is resolved from the issue's Linear team via `TEAM_COMPONENT_MAP` in `Fun-E/agents/webhook-receiver/main.py`. The team → component mapping is also documented in this repo's `CLAUDE.md` (look for the Linear team / component table).

---

## Request Classification

When the PO/PM describes their request, classify it into one or more of these categories. A single request may span multiple — for example, "add a new feature" routes through Flows 1 + 2 + 3.

| Category | Signals | Flow |
|----------|---------|------|
| **Feature Planning** | "add a feature," "new button," "I want to build," "create a plan for" | Flow 1: Feature Planning |
| **Linear Project Creation** | "create a project," "scope out a wave of work," "8+ issues' worth," output of Flow 1 with Medium/Large complexity | Flow 2: Linear Project Creation |
| **Design Doc Update** | mentions a doc name, "update the PRD," "change the spec," "add to the methodology" | Flow 3: Design Doc Update |
| **Roadmap Update** | "move issue," "reprioritize," "add to next sprint," "change the blocking order" | Flow 4: Roadmap Update |
| **Project Completion Review** (PM) | "what's waiting on me as PM," "mark project X completed," "review project ACs" | Flow 5: Project Completion Review |

If the request is ambiguous, ask for clarification in the terminal before proceeding. Do NOT guess — the wrong interpretation could modify documents or Linear state incorrectly.

---

## Flow 1: Feature Planning

**Entry:** The PO describes a new capability they want to add.

### Step 1 — Understand the Request

Through conversation with the PO, gather:
- **What** the feature does (user-facing behavior)
- **Why** it matters (business value, user need)
- **Where** it fits in the architecture (which component)
- **How big** it is (rough scope — is this one issue, a few stories, or 8+ issues' worth that needs its own Linear Project + PRD?)

If the PO's description is vague, ask targeted follow-up questions ("Which users would interact with this?", "Should this work within the existing dashboard page or as a new route?").

### Step 2 — Load Component Context

Read the four levels of context relevant to the request (mirrors `dev-team-workflow` Step 1, scaled for product planning):

1. **Level 1 — System Architecture:** `docs/{Repo-Name}-System-Architecture.md` (e.g., `docs/FUN-E-System-Architecture.md`)
2. **Level 2 — Component README:** `docs/design/components/{component}/README.md`
3. **Level 3 — Existing PRDs:** enumerate `docs/design/components/{component}/projects/*.md` to understand what's already in flight and what the next available `<PRD-ID>` is
4. **Linear state:** query the active Cycles, current Linear Projects in the component, and existing Backlog / Triage / Scheduled issues that may already cover part of the request

### Step 3 — Create the Feature Plan

Produce a structured plan and present it to the PO in the terminal for review:

```markdown
## Feature Plan: {Feature Title}

### Problem Statement
{What user need or business problem this addresses}

### Proposed Approach
{High-level description of the solution}

### Scope
- **Component:** {component name}
- **Surfaces:** {frontend / backend / both}
- **Estimated complexity:** {Small (1–2 issues, fits an existing Project) / Medium (3–7 issues, fits an existing Project or warrants a new one) / Large (8–12 issues, requires new Linear Project + PRD per the CLAUDE.md guideline)}

### Linear Project Disposition
- {New Project required: `<PRD-ID>: <PRD title>` — recommends Flow 2}
- {Or: extend existing Project `<PRD-ID>: <name>` (link)}
- {Or: standalone issue, no Project change}

### §7 AC Mapping (if extending an existing Project)
- New AC delivered: {short AC text} → maps to PRD `<PRD-ID>` §7 as new AC-{N}, OR refines existing AC-{M}

### Issues to Create
1. **{Issue title}** ({Feature / User Story / Bug})
   {As-a / I-want / So-that, OR description for non-stories}
   - AC: {key acceptance criteria}
   - Estimate: {points}
   - Design References:
     - `docs/design/components/{component}/projects/{PRD-ID}-{slug}.md: §7.{N}`
     - `docs/design/components/{component}/README.md: §{relevant section}`
   - Figma export references (UI only): `docs/figma-export/...` or "N/A"

2. ...

### Design Doc Impact
- {doc_1}: {what needs to change}
- {doc_2}: {what needs to change}
- New PRD required: yes/no
- No impact on: {docs that were reviewed but don't need changes}

### Dependency Assessment
- Blocks: {any existing issues this would block}
- Blocked by: {any existing issues this depends on}
- Suggested Cycle: {Cycle name and date range, or "Backlog if no Cycle ready"}

### Decisions & Assumptions
- {Decision 1 — what / why / what would invalidate it}

### Questions for PO (Blocking)
- {Empty if none — flag this as a "self-approved" plan; otherwise list each question}
```

The plan deliberately mirrors the `dev-team-workflow` Implementation Plan structure (Decisions & Assumptions, Questions for PO (Blocking)) so the PO sees consistent terminology across product-side and engineering-side planning.

### Step 4 — PO Review and Refinement

Present the plan to the PO and wait for feedback. The PO may:
- **Approve as-is** → proceed to Step 5
- **Request changes** → revise the plan and present again
- **Reduce scope** → adjust issues, remove items, simplify
- **Cancel** → stop, no changes made

Iterate until the PO is satisfied.

### Step 5 — Execute the Plan

Once approved, execute the actions in this order:

**5a — If new Linear Project + PRD is needed:** route to Flow 2 (Linear Project Creation) with the plan as input. Flow 2 produces the Project ID and PRD path; return here for issue creation.

**5b — Update Design Docs:**
1. Apply the design-doc changes named in the plan
2. Run `tools/update-design-docs` for cross-document and Linear issue propagation (handles PRD-Specific and Component README propagation automatically based on the document type)
3. Commit changes (minor) or create PR (significant)

**5c — Create Linear Issues:**

For each issue in the plan:
1. Create the issue using `linear-sprint-ops` (Linear MCP connector for the underlying mutation), with:
   - Title and description following the appropriate template (User Story / Feature / Bug)
   - **Linear Project assignment** (the existing Project to extend, or the Project created in Flow 2)
   - **Design References section** in canonical format: `docs/design/components/[component]/[doc]: §[section]` — at minimum a reference to the parent PRD
   - **Acceptance Criteria** that map 1:1 to the parent PRD's §7 ACs (per `CLAUDE.md` §Linear Issue Structure)
   - Estimate, labels, priority
2. Set parent–child relations (User Stories under a Feature, if both exist)
3. Add blocking / blocked-by relations between issues
4. Set the entry status:
   - **Scheduled** if assigning to a Cycle (the SCRUM Master will validate and route to Awaiting Assignment)
   - **Backlog** if no Cycle is appropriate yet
   - **Triage** if the PO knows there are gaps to fill before the SCRUM Master picks it up

After creation, run `validate-issue-completeness` (operation 7) on each new issue. If any fail the universal checks (Project membership, Design References format), fix immediately rather than waiting for the SCRUM Master to flag them.

**5d — Self-Verification (run before reporting):**

- [ ] Every new issue has a Linear Project (`issue.project` non-null)
- [ ] Every new issue's Design References use the canonical format and include the parent PRD
- [ ] Every issue's primary AC maps 1:1 to a §7 AC in the parent PRD
- [ ] If a new Linear Project was created, `validate-project-completeness` (operation 20) passes
- [ ] Project Lead (= PO) is set
- [ ] Issue count for any new Project is 8–12 (warn if outside this range)
- [ ] All design-doc changes have been propagated via `tools/update-design-docs`

**5e — Report Results:**

```
Done. Here's what was created:

Linear Project: {PRD-ID}: {title} (link)
  Lead: @{po}
  PRD: docs/design/components/{component}/projects/{PRD-ID}-{slug}.md
  Coverage: {N/M} §7 ACs covered by created issues

Issues:
  ├── {ISSUE_ID} — {title} ({points} pts, Cycle: {cycle}) → covers §7.AC-1
  ├── {ISSUE_ID} — {title} ({points} pts, Cycle: {cycle}) → covers §7.AC-2
  └── ...

Design docs updated:
  - docs/{filename} — {change description}
  - docs/{filename} — {change description} (+ {N} downstream docs updated, {M} Linear issues notified)

Commit: {hash} on dev branch (or PR: {link})
```

---

## Flow 2: Linear Project Creation

**Entry:** Routed from Flow 1 Step 5a when a new Linear Project + PRD is required, OR invoked directly when the PO says "create a new project for X."

### Step 1 — Determine the next PRD-ID

Scan `docs/design/components/{component}/projects/` for existing `*-PRD-NN-*.md` files. Extract the highest `NN` and increment. The PRD-ID prefix uses the component's standard letter code (e.g., `A-PRD` for automations, `P-PRD` for performance). If the convention isn't clear from existing files, ask the PO.

### Step 2 — Draft the PRD

Create the PRD file at `docs/design/components/{component}/projects/{PRD-ID}-{slug}.md` with this canonical structure:

```markdown
# {PRD-ID}: {Title}

## 1. Overview
{One-paragraph problem statement, target users, and primary goal}

## 2. Scope
**In scope:** {bullet list}
**Out of scope:** {bullet list — explicit non-goals}

## 3. User Stories
{High-level — these will become Linear issues; list 8–12}

## 4. Data Contracts
{API schemas, data models, state shape — only what's specific to this project}

## 5. Implementation Outline
{High-level technical approach; the Dev Team's Implementation Plan goes deeper per issue}

## 6. Test Plan
{What verification looks like at the project level — beyond per-issue Test Instructions}

## 7. Acceptance Criteria
{Numbered, testable, 8–12 items. Each AC becomes one Linear issue per `CLAUDE.md` §Linear Issue Structure. Use Given / When / Then where appropriate.}
- AC-1: {criterion}
- AC-2: {criterion}
- ...

## 8. Dependencies
{Other Linear Projects, components, or external services this depends on}

## 9. Open Questions
{Anything unresolved that may surface during implementation}
```

Present the draft to the PO for review. Iterate until approved.

### Step 3 — Create the Linear Project

Use `linear-sprint-ops` operation 22 (`create-project`):

- **`name`** = `{PRD-ID}: {Title}` — must match the PRD filename's PRD-ID prefix
- **`description`** = one-paragraph summary that points to the PRD file:
  ```
  {One-paragraph summary of the project goal and scope.}

  PRD: docs/design/components/{component}/projects/{PRD-ID}-{slug}.md
  ```
- **`teamIds`** = the component's team(s)
- **`leadId`** = the PO's Linear user ID
- **`state`** = `"backlog"` or `"planned"`

### Step 4 — Self-Verify

Run `linear-sprint-ops` operation 20 (`validate-project-completeness`). The checks:
- Name follows `<PRD-ID>: <PRD title>` regex
- PRD file exists at the named path
- PRD has §7 with 3+ ACs
- Lead is set
- Description references the PRD path

If any check fails, fix before proceeding.

### Step 5 — Return to Caller

Return `{projectId, prdPath, prdId}` to Flow 1 Step 5c (issue creation continues there) OR, if invoked directly, prompt the PO whether to create the child issues now (which routes back into Flow 1 Step 5c).

---

## Flow 3: Design Doc Update

**Entry:** The PO requests changes to architecture or design documents.

### Step 1 — Identify the Change

From the PO's description, extract:
- Which document(s) need to change
- What the change is (new content, modification, removal, restructure)
- Any rationale or context

If the PO references a doc by name but the name is ambiguous, list matching files and ask them to confirm.

### Step 2 — Read and Analyze

1. Read the primary document
2. **Classify it** (per `tools/update-design-docs` Step 3):
   - System architecture (Level 1) → standard propagation
   - Component README (Level 2) → triggers Component README Propagation (R1–R3)
   - Project PRD (Level 3) → triggers PRD-Specific Propagation (P1–P4); §7 AC changes require PO confirmation before propagation
   - Other / cross-cutting → standard propagation
3. If the change is complex, present a summary of what will change and ask for confirmation before proceeding

**Special case — PRD §7 changes:** If the PO is modifying §7 of a PRD, surface the implications BEFORE applying:
- Modified ACs → notification on each child issue, no auto-edit
- Added ACs → coverage gap, new child issue needed
- Removed ACs → orphaned child issue, PO decides next steps

### Step 3 — Apply Changes and Propagate

1. Apply the requested changes to the primary document
2. Run `tools/update-design-docs` — it handles document-type classification, cross-doc propagation, PRD-Specific Propagation, Component README Propagation, and Linear issue Design References updates
3. Commit to `dev` (minor changes) or create PR (significant changes)

### Step 4 — Report Results

```
Design docs updated:

Primary: docs/{filename} (type: {Level 1 / Component README / PRD / cross-cutting})
  - {description of change}

Downstream doc updates:
  - docs/{file_1} — {what changed}
  - docs/{file_2} — {what changed}

Linear issues updated: {count}
  - {ISSUE_ID}: Design References path updated
  - {ISSUE_ID}: Notification comment posted (content change)

Linear Projects notified: {count}
  - {PROJECT}: §7 AC-{N} changed — issue {ISSUE_ID} needs PO review

Commit: {hash} on dev
```

---

## Flow 4: Roadmap Update

**Entry:** The PO requests changes to the Linear project structure — issues, Cycles, relations, priorities, Project Leads, or labels.

### Step 1 — Identify the Change

Extract:
- What type of change (create, modify, move, reorder, delete; reassign Lead; apply/remove label)
- Which issues, Cycles, Linear Projects, or relations are affected
- Any constraints ("don't break the dependency order")

### Step 2 — Query Current State

Use `linear-sprint-ops`:
- Operation 1 (`query-cycle-issues`) for Cycle-scoped queries
- Operation 16 (`query-project`) for Project-scoped queries
- Operation 21 (`query-pm-action-projects`) for the PM inbox view

For each affected issue: status, estimate, labels, relations, parent Linear Project, Cycle assignment.

### Step 3 — Assess Impact and Confirm

Analyze the change against current state and present the impact:
- Which existing issues are affected
- Whether blocking relations need to change
- Whether Cycle composition or timing shifts
- Whether Project size moves outside the 8–12 guideline (warn — see Red Flags)
- Downstream consequences (e.g., moving an issue affects the dependency graph, may invalidate a wave)

**If the impact is larger than expected**, flag it explicitly:
```
Heads up — moving FUN-12 to Cycle 3 would also affect:
- FUN-14 (blocked by FUN-12, currently in Cycle 2)
- FUN-15 (blocked by FUN-14, currently in Cycle 3)
And it would shrink Project A-PRD-02 from 10 issues to 9 (still within guideline).

Should I move all three, or just FUN-12?
```

Wait for PO confirmation before applying changes.

### Step 4 — Apply Changes

Operations available in this flow:

- **Issue:** create, update description / AC / estimate / priority / labels, reassign Cycle, set status, set parent, add/remove blocking relations, cancel
- **Linear Project:** reassign Lead (= reassign PO), apply/remove `po-action` / `pm-action` labels manually, update description, mark Completed (if invoked by PM — flag if invoked by PO), audit AC coverage via operation 19
- **Cycle:** add/remove issues, but do NOT mark a Cycle Complete from this flow — that's the SCRUM Master / Sprint Manager's job per `dev-workflow.md` §9

### Step 5 — Self-Verification

- [ ] All affected issues still have a parent Linear Project
- [ ] Any Project that lost issues still has 8–12 child issues (or a warning was logged)
- [ ] Project Leads are still set on all touched Projects
- [ ] No circular dependencies introduced (use `compute-dependency-graph` from `linear-sprint-ops` operation 2 if relations changed)

### Step 6 — Report Results

```
Roadmap updated:

Issues created:
  - {NEW_ID}: {title} (Project: {PRD-ID}, Cycle: {name}, {points} pts)

Issues modified:
  - {ID}: moved from Cycle "{old}" to Cycle "{new}"
  - {ID}: estimate changed from {old} to {new}

Project changes:
  - {PRD-ID}: Lead changed from @{old} to @{new}
  - {PRD-ID}: size now 10 issues (was 8) — within guideline

Relations updated:
  - {ID_A} now blocks {ID_B}

Dependency graph impact: {none / description of change}
```

---

## Flow 5: Project Completion Review (PM)

**Entry:** The PM (Ken) asks "what's waiting on me?" or "review project X" or "mark project X completed." This flow operationalizes `docs/dev-workflow.md` §8 from the PM's side.

### Step 1 — Show the PM Inbox

Run `linear-sprint-ops` operation 21 (`query-pm-action-projects`). Present the projects in the terminal, sorted by oldest `completedAt` first:

```
Projects awaiting your review (PM):

| Project           | Component   | Last Issue Completed | Issue Count |
|-------------------|-------------|----------------------|-------------|
| A-PRD-03: Foo Bar | automations | 2026-04-22           | 9           |
| P-PRD-05: Baz     | performance | 2026-04-25           | 11          |

Which would you like to review? (Enter PRD-ID, or "all")
```

### Step 2 — Walk the AC-to-Issue Mapping

For the chosen Project:
1. Run `linear-sprint-ops` operation 16 (`query-project`) to load full state
2. Run operation 19 (`audit-project-coverage`) to compute the AC-to-issue map
3. Read the PRD's §7 acceptance criteria from disk
4. Read the SCRUM Master's hand-off comment on the Project (the AC-to-issue mapping it posted at Project Completion Detection)
5. Present a side-by-side view to the PM:

```
Project: A-PRD-03: Foo Bar
PRD: docs/design/components/automations/projects/A-PRD-03-foo-bar.md

§7 Acceptance Criteria:
  AC-1: User can create a Foo                  → FUN-101 (Done)   ✓
  AC-2: Foo persists across sessions           → FUN-102 (Done)   ✓
  AC-3: Foo can be edited                      → FUN-103 (Done)   ✓
  ...
  AC-9: Foo respects rate limit                → FUN-109 (Done)   ✓

Coverage: 9/9 ACs delivered
Issue count: 9 (within 8–12 guideline)
Project size assessment: appropriately scoped

Optional: smoke-test on `main` before approving — branch is up to date.
```

### Step 3 — PM Decision

Present three options:

**A. Approve and mark Completed:**
- Confirm the PM has reviewed the AC mapping and (optionally) smoke-tested on `main`
- Run operation 18 (`update-project-state`) with `state: "completed"`
- The webhook will route to the SCRUM Master, which removes `pm-action` and runs the Cycle Completion check
- Report success in the terminal

**B. Open rework issues:**
- The PM identifies one or more gaps. For each:
  - Draft a new rework issue describing the missing behavior
  - Assign the rework issue to the **same Linear Project** as the original (set `projectId` to the original Project's ID). This is required so `audit-project-coverage` (operation 19) picks the rework up on the next PM review and re-evaluates AC coverage. A comment cross-reference on the original Project is a nice-to-have but not a substitute for Project membership.
  - Assign it to the next Cycle
  - Status: Scheduled (so the SCRUM Master picks it up next Sprint Planning)
- The original Project stays Started (do NOT mark Completed)
- The `pm-action` label remains until the rework is delivered and re-review passes

**C. Defer:**
- The PM wants more time. No changes — leave the Project labeled `pm-action`.

### Step 4 — Report Results

```
Project Completion Review: {PRD-ID}

Outcome: {Completed / Rework opened / Deferred}

If Completed:
  - State: completed (completedAt: {timestamp})
  - pm-action label removed by SCRUM Master webhook
  - Cycle Completion check triggered

If Rework opened:
  - {NEW_ID_1}: {title} (Cycle: {next}, {points} pts)
  - {NEW_ID_2}: {title} (Cycle: {next}, {points} pts)
  - Project remains Started; pm-action label retained
```

---

## Composing Multiple Flows

When a request spans multiple categories, route in this order:

1. **Feature Planning (Flow 1)** — produces the plan, gets PO approval
2. **Linear Project Creation (Flow 2)** — if the plan calls for a new Project + PRD
3. **Design Doc Update (Flow 3)** — applies any pre-existing doc changes the plan named (the new PRD itself was authored in Flow 2)
4. **Roadmap Update (Flow 4)** — creates issues, applies relations, assigns to Cycles
5. **(rarely combined)** Project Completion Review (Flow 5) is a PM-side flow and doesn't compose with the others

The final report combines the outputs of all flows that ran.

---

## Interaction Principles

1. **Confirm before modifying.** Always present the plan/impact and get human approval before writing to docs or Linear. Only exception: trivial changes the human has been explicit about ("change FUN-12's estimate to 3 points").

2. **Report in the terminal, not just in Linear.** The human is in a Claude Code session — they should see results immediately.

3. **Ask, don't assume.** If the PO says "add a button" without specifying where, which page, or what it does — ask. A wrong guess wastes more time than a clarifying question.

4. **Stay in scope.** If the request implies changes to another component's docs or issues, flag it. Cross-component changes may need coordination with that component's PO.

5. **Use `tools/linear-sprint-ops` for all Linear operations** — not raw GraphQL. Use the Linear MCP connector only for ad-hoc queries the SKILL doesn't cover.

6. **Trust the canonical workflow.** When unsure how a Project, issue, or status should look, defer to:
   - `docs/dev-workflow.md` (process)
   - `CLAUDE.md` §Linear Issue Structure and §Context Loading Sequence (structure)
   - `tools/linear-sprint-ops` (operations)

---

## Red Flags

Watch for these — they typically indicate a problem with how the PO wants to organize the work, and pushing back saves rework downstream:

- **PO asks to ship a single 1-issue Linear Project.** A Project is the unit at which the PM does completion review; a 1-issue Project doesn't justify the overhead. Push back: either bundle into an existing Project, or skip the Project layer and add as a standalone issue under no Project (acknowledging it skips PM Completion Review).
- **PO asks to skip writing a PRD.** Without a PRD, there's no Level 3 context for the Dev Team and no §7 ACs for the PM to review against. The Linear Project description is a *pointer* to the PRD, not a substitute. Push back: at minimum, draft a thin PRD with §7 ACs.
- **PO asks to create issues without a parent Linear Project.** Orphan issues skip Project Completion Review. Push back: which Project does this belong to?
- **PO asks to rename an existing PRD's PRD-ID.** This breaks the 1:1 mapping with the Linear Project name and the PRD filename. Don't do it without explicit confirmation; prefer a new PRD-ID for new content.
- **PO asks to mark a Linear Project Completed.** That's a PM action, not a PO action. Flag and route through Flow 5.
- **PRD has fewer than 3 §7 ACs or more than 15.** Below 3: the project is too small to justify a separate PRD. Above 15: the project is too large; recommend splitting into two PRDs. (Note: 8–12 is the *warn* range used by `validate-project-completeness` (operation 20); 3–15 here is the *hard reject* range. PRDs outside 3–15 must be split or merged before Project creation; PRDs inside 3–15 but outside 8–12 surface a warning and proceed.)
- **PRD §7 AC count doesn't match Linear issue count.** Coverage gap or over-scoping. Run `audit-project-coverage` and resolve before delegating.
- **Issues' Acceptance Criteria don't map back to PRD §7.** The 1:1 convention is broken. Either update the issue ACs to match, or update the PRD §7 (with caution — see PRD-Specific Propagation in `tools/update-design-docs`).
- **Component README is being modified for a single-Project change.** README changes have fan-out across every PRD in the component. Re-check whether the change really belongs at README level or in the PRD.

---

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "We don't need a PRD for this small change." | Then it doesn't need a Linear Project either. Add it to an existing Project, or create as a standalone issue. PRD ↔ Project is 1:1; if you skip the PRD, you skip the Project. |
| "I'll write the PRD later, just create the issues now." | The Dev Team will load the PRD as Level 3 context when planning. Without a PRD, plans degrade to using the Linear Project description as the spec — fine as a temporary fallback, brittle as a default. |
| "This Project only has 4 issues but each is large." | The 8–12 guideline is about scope coherence, not lines of code. 4 large issues are usually 4 too-coarse §7 ACs that should each split into 2–3 finer ones. |
| "I'll update the issue's ACs and skip updating the PRD §7." | Then the PRD becomes stale and the PM's Project Completion Review will compare against the wrong spec. Update both, in lockstep, via Flow 3. |
| "I'll skip the Project Lead — Ken is fallback anyway." | Then SLA escalation @mentions Ken twice (primary + backup), and the PO Action Queue saved view loses signal. Set the Lead. |
| "Mark the Project Completed myself; the PM will rubber-stamp it later." | The PM is the second pair of eyes for project-level coherence. POs marking their own Projects Completed defeats the gate. Flow 5 is the path. |

---

## Verification Checklist

Run before reporting completion to the human:

- [ ] All Linear changes match what the human approved (no scope drift)
- [ ] Every new issue has a Linear Project and Design References in canonical format
- [ ] Every new Project has a Lead and a matching PRD file
- [ ] `validate-issue-completeness` passes on every new issue
- [ ] `validate-project-completeness` passes on every new Project
- [ ] Design-doc changes have been propagated (`tools/update-design-docs` ran cleanly)
- [ ] Coverage check: every PRD §7 AC has a child issue (run `audit-project-coverage`)
- [ ] Project size is within 8–12 issues (or warning was reported to the human)
- [ ] No circular dependencies introduced (re-run `compute-dependency-graph` if relations changed)
- [ ] Commit is on `dev` branch (or PR is open) for any doc changes
- [ ] Final terminal report covers all created / modified / notified entities

---

## Error Handling

### Document Not Found
If a referenced document doesn't exist, ask the PO whether to create one or if they meant a different file.

### Linear API Errors
If a change fails (e.g., creating a relation that would form a cycle, naming a Project with a duplicate PRD-ID), explain what failed and why, suggest an alternative, and wait for direction.

### Scope Escalation
If a change affects more than the PO's component (cross-team blocking relations, shared docs, README-level changes), flag explicitly. Cross-component changes may need coordination with the other component's PO.

### Plan Rejection
If the PO rejects the feature plan entirely, stop cleanly. No docs modified, no issues created, no side effects.

### PM Tries to Mark Their Own Project Completed (PO is also PM)
When the PO and PM are the same person (Ken fills both roles per `dev-workflow.md` §1), Flow 5 is still the correct path — it preserves the audit trail showing the project went through Completion Review even when the same human did both reviews.

### `validate-project-completeness` Fails Mid-Flow
If validation fails after creating the Project (e.g., the PRD file write fails), DO NOT leave the Linear Project orphaned. Either complete the PRD authoring before creating the Project, or roll back the Project creation by setting it to `cancelled` state.
