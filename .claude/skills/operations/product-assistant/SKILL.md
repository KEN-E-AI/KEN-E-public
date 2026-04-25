# Operation SKILL: Product Assistant

## Purpose

Interactive SKILL that helps Product Owners plan new features, update design documentation, and manage the product roadmap in Linear — all from a Claude Code terminal session. The PO describes what they want in natural language, and this SKILL orchestrates the analysis, doc updates, issue creation, and cross-reference propagation.

**Invoked by:** A Product Owner in a Claude Code terminal session. The PO may say things like:
- "I want to add a new export button to the dashboard. Use your product-assistant skill to plan this out, update the docs, and add it to Linear."
- "We need to change the funnel from 4 stages to 5. Update all the design docs and create the issues."
- "Move FUN-12 to the next sprint and reprioritize the backlog."
- "Update the PRD to reflect the new onboarding flow we discussed."

**Companion SKILLs used:**
- Component docs — the canonical design document(s) for the target component. Layout varies by repo (detect which):
  - **KEN-E-style (multi-PRD):** `docs/design/components/{component-name}/README.md` + `docs/design/components/{component-name}/projects/*.md`
  - **Fun-E-style (single-PRD):** `docs/components/{component-name}/PRD.md`
  When updating design docs, enumerate the appropriate directory (`ls docs/design/components/{name}/projects/` or `ls docs/components/{name}/`) and read every relevant `.md` before proposing changes.
- `tools/update-design-docs` — cross-document dependency tracking, Linear issue Design References propagation

**External tools used:**
- Linear MCP connector — for querying and updating issues, Cycles, projects, and relations
- Git — for committing doc changes or creating PRs

---

## Request Classification

When the PO describes their request, classify it into one or more of these categories. A single request may span multiple categories — for example, "add a new feature" involves all three.

| Category | Signals | Actions |
|----------|---------|---------|
| **Feature Planning** | "add a feature," "new button," "I want to build," "create a plan for" | Analyze scope → create Feature + User Story issues in Linear → update design docs |
| **Design Doc Update** | mentions a doc name, "update the PRD," "change the spec," "add to the methodology" | Read docs → apply changes → run update-design-docs propagation → commit/PR |
| **Roadmap Update** | "move issue," "reprioritize," "add to next sprint," "change the blocking order" | Query Linear state → assess impact → apply changes → report |

If the request is ambiguous, ask the PO for clarification in the terminal before proceeding. Do NOT guess — the wrong interpretation could modify documents or issues incorrectly.

---

## Flow 1: Feature Planning

**Entry:** The PO describes a new capability they want to add.

### Step 1 — Understand the Request

Through conversation with the PO, gather:
- **What** the feature does (user-facing behavior)
- **Why** it matters (business value, user need)
- **Where** it fits in the architecture (which component, which part of the UI/API)
- **How big** it is (rough scope — is this one story or multiple?)

If the PO's description is vague, ask targeted follow-up questions. For example: "Which users would interact with this?" or "Should this work within the existing dashboard page or as a new route?"

### Step 2 — Load Component Context

Read the component context SKILL for the relevant component. This gives you:
- Architecture docs to review
- Codebase layout
- Existing patterns and conventions
- Domain knowledge

Read the architecture docs referenced in the component context to understand how the new feature fits into the existing system.

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
- **Estimated complexity:** {Small (1 story) / Medium (2-3 stories) / Large (4+ stories)}

### User Stories
1. **{Story title}**
   As a {user type}, I want to {action} so that {benefit}.
   - AC: {key acceptance criteria}
   - Estimate: {points}

2. **{Story title}**
   ...

### Design Doc Impact
- {doc_1}: {what needs to change}
- {doc_2}: {what needs to change}
- No impact on: {docs that were reviewed but don't need changes}

### Dependency Assessment
- Blocks: {any existing issues this would block}
- Blocked by: {any existing issues this depends on}
- Suggested Cycle: {which Cycle this should be added to, or "New Cycle needed"}
```

### Step 4 — PO Review and Refinement

Present the plan to the PO and wait for their feedback. The PO may:
- **Approve as-is** → proceed to Step 5
- **Request changes** → revise the plan and present again
- **Reduce scope** → adjust stories, remove items, simplify
- **Cancel** → stop, no changes made

This is an interactive conversation. Iterate until the PO is satisfied.

### Step 5 — Execute the Plan

Once approved, execute all three actions:

**5a — Update Design Docs:**
1. Apply the design doc changes identified in the plan
2. Run the `update-design-docs` tool SKILL for cross-document and Linear issue propagation
3. Commit changes (minor) or create PR (significant)

**5b — Create Linear Issues:**
1. Create the Feature (parent) issue using the Feature template structure:
   - Description, Acceptance Criteria, Design References, Related Products
2. Create User Story (child) issues under the Feature using the User Story template:
   - User Story, Acceptance Criteria, Design References, Context, Implementation Notes
3. Set estimates, labels, and priority on each issue
4. Add blocking/blocked-by relations between stories if applicable
5. Assign to the appropriate Cycle (or leave in Backlog if no Cycle is specified)
6. Set parent-child relations between Feature and User Stories

**5c — Report Results:**
Report back to the PO in the terminal:
```
Done. Here's what was created:

Feature: {ISSUE_ID} — {title}
  ├── {STORY_ID} — {story title} ({points} pts, Cycle: {cycle})
  ├── {STORY_ID} — {story title} ({points} pts, Cycle: {cycle})
  └── {STORY_ID} — {story title} ({points} pts, Cycle: {cycle})

Design docs updated:
  - docs/{filename} — {change description}
  - docs/{filename} — {change description} (+ 3 downstream docs updated)

Commit: {hash} on dev branch (or PR: {link})
```

---

## Flow 2: Design Doc Update

**Entry:** The PO requests changes to architecture or design documents.

### Step 1 — Identify the Change

From the PO's description, extract:
- Which document(s) need to change
- What the change is (new content, modification, removal, restructure)
- Any rationale or context

If the PO references a doc by name but the name is ambiguous, list the matching files and ask them to confirm.

### Step 2 — Read and Analyze

1. Read the primary document from the `docs/` directory
2. Read the component context SKILL for related doc references
3. If the change is complex, present a summary of what will change and ask for confirmation before proceeding

### Step 3 — Apply Changes and Propagate

1. Apply the requested changes to the primary document
2. Run the `update-design-docs` tool SKILL which handles:
   - Cross-document dependency scanning
   - Downstream doc updates
   - Linear issue Design References propagation (path updates, section heading updates, notification comments)
3. Commit to `dev` (minor changes) or create PR (significant changes)

### Step 4 — Report Results

Report back to the PO in the terminal:
```
Design docs updated:

Primary: docs/{filename}
  - {description of change}

Downstream updates:
  - docs/{file_1} — {what changed}
  - docs/{file_2} — {what changed}

Linear issues updated: {count}
  - {ISSUE_ID}: Design References path updated
  - {ISSUE_ID}: Notification comment posted (content change)

Commit: {hash} on dev
```

---

## Flow 3: Roadmap Update

**Entry:** The PO requests changes to the Linear project structure — issues, Cycles, relations, or priorities.

### Step 1 — Identify the Change

From the PO's description, extract:
- What type of change (create, modify, move, reorder, delete)
- Which issues, Cycles, or relations are affected
- Any constraints (e.g., "don't break the dependency order")

### Step 2 — Query Current State

Query Linear via the MCP connector:
- All issues in the relevant Project with statuses, estimates, labels, relations, and Cycle assignments
- All Cycles with date ranges and issue counts
- Parent-child and blocking relations

### Step 3 — Assess Impact and Confirm

Analyze the requested change against the current state and present the impact to the PO:
- Which existing issues are affected
- Whether blocking relations need to change
- Whether Cycle composition or timing is affected
- Any downstream consequences (e.g., moving an issue affects the dependency graph)

**If the impact is larger than expected**, flag it explicitly:
```
Heads up — moving FUN-12 to Cycle 3 would also affect:
- FUN-14 (blocked by FUN-12, currently in Cycle 2)
- FUN-15 (blocked by FUN-14, currently in Cycle 3)

Should I move all three, or just FUN-12?
```

Wait for PO confirmation before applying changes.

### Step 4 — Apply Changes

Execute the roadmap changes via the Linear MCP connector:
- Create new issues (with proper template structure, labels, estimates, and relations)
- Update existing issues (descriptions, acceptance criteria, estimates, labels)
- Reassign Cycle memberships
- Update parent-child and blocking relations
- Reorder priorities within a Cycle

### Step 5 — Report Results

Report back to the PO in the terminal:
```
Roadmap updated:

Issues created:
  - {NEW_ID}: {title} (Cycle: {name}, {points} pts)

Issues modified:
  - {ID}: moved from Cycle "{old}" to Cycle "{new}"
  - {ID}: estimate changed from {old} to {new}

Relations updated:
  - {ID_A} now blocks {ID_B}

Dependency graph impact: {none / description of change}
```

---

## Composing Multiple Flows

When the PO's request spans multiple categories (e.g., "add a new feature, update the docs, and put it in the next sprint"), execute the flows in this order:

1. **Feature Planning** first — produces the plan, gets PO approval
2. **Design Doc Update** second — applies doc changes identified in the plan
3. **Roadmap Update** third — creates issues and assigns to Cycles

This order ensures each step has the outputs from the previous step. The final report to the PO combines all three:
```
Feature planning, doc updates, and roadmap changes are all complete.

{Combined report from all three flows}
```

---

## Interaction Principles

This is an interactive SKILL, not a fire-and-forget workflow. Key principles:

1. **Confirm before modifying.** Always present the plan/impact and get PO approval before writing to docs or Linear. The only exception is trivial changes where the PO has been explicit (e.g., "change the estimate on FUN-12 to 3 points").

2. **Report in the terminal, not just in Linear.** The PO is sitting in a Claude Code session. They should see results immediately, not have to go check Linear or GitHub.

3. **Ask, don't assume.** If the PO says "add a button" but doesn't specify where, which page, or what it does — ask. A wrong guess wastes more time than a clarifying question.

4. **Stay in scope.** If the PO's request implies changes to another component's docs or issues, flag it. Cross-component changes may need coordination with other POs.

5. **Use the Linear MCP connector** for all Linear operations (querying issues, creating issues, updating issues, listing Cycles, etc.) — not raw GraphQL.

---

## Error Handling

### Document Not Found
If a referenced document doesn't exist in `docs/`, tell the PO and ask whether to create a new one or if they meant a different file.

### Linear API Errors
If a change fails (e.g., creating a relation that would form a cycle), explain what failed and why, suggest an alternative, and wait for PO direction.

### Scope Escalation
If the change affects more than the PO's component (cross-team blocking relations, shared docs), flag it explicitly and ask for confirmation. The PO may need to coordinate with other POs first.

### Plan Rejection
If the PO rejects the feature plan entirely, stop cleanly. No docs modified, no issues created, no side effects.
