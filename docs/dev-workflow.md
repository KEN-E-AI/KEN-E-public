# Development Workflow

This document describes the full lifecycle of an issue from sprint intake to production merge. It is the **human-facing** reference for Product Owners, Product Managers, and developers reading the repo to understand how work moves through the pipeline.

> **Canonical source convention.** The autonomous-agent operational behavior — exact API calls, status transitions, decision rules — lives in the workflow SKILL files baked into the agent VM image: nine workflow SKILLs under `.claude/skills/workflows/{project-kickoff,project-update,issue-triage,step-1-planning,step-1b-updating-plan,step-2-implementing,step-3-testing,step-3b-resolving-test-issues,step-3c-addressing-po-concerns}/SKILL.md`, plus the shared `.claude/skills/tools/agentic-shared/SKILL.md`. This doc is the human summary. **If the two disagree, the SKILL files are canonical for agent behavior and this doc is canonical for humans.** When changing the workflow, update the SKILL files first, then mirror the human-facing change here.

> **Refactor note (2026-05-08):** This doc reflects the skill-and-status refactor (12-status workflow, identity-based receiver routing, status-driven Step 1: Planning). Pre-refactor terminology (Flow 1/2/3/4, Awaiting Review, In Review, Ready for Testing, Resolving Test Issues, Sprint Planning) has been replaced throughout. The integration-branch naming convention still includes `cycle-{N}` because Linear Cycles continue to exist for velocity / calendar reporting — agents don't react to Cycle webhooks. For canonical workflow steps, read the relevant workflow SKILL under `.claude/skills/workflows/`.

---

## Table of Contents

1. [Roles](#1-roles)
2. [Issue Lifecycle Overview](#2-issue-lifecycle-overview)
3. [Wave-Based Execution Model](#3-wave-based-execution-model)
4. [Phase 1: Project Kickoff](#4-phase-1-project-kickoff)
5. [Phase 2: Development](#5-phase-2-development)
6. [Phase 3: Testing](#6-phase-3-testing)
7. [Phase 4: Wave Integration and PO Review](#7-phase-4-wave-integration-and-po-review)
8. [Phase 5: Project Completion Review](#8-phase-5-project-completion-review)
9. [Cross-Component Dependency Resolution](#9-cross-component-dependency-resolution)
10. [Post-Launch Review Model](#10-post-launch-review-model)
11. [Error Scenarios and Recovery](#11-error-scenarios-and-recovery)
12. [SLA Enforcement](#12-sla-enforcement)
13. [PO and PM Visibility Tools](#13-po-and-pm-visibility-tools)
14. [Quick Reference Tables](#14-quick-reference-tables)
15. [Manually Triggering Agents](#15-manually-triggering-agents)

---

## 1. Roles

### SCRUM Master (agent)

Project-scoped coordinator for a single component (e.g., Fun-E). Validates issue completeness, computes the intra-Project dependency graph, delegates issues to the Dev Team in wave order, monitors status transitions, enforces SLAs, and triggers wave / Project completion flows. When a wave completes testing, the SCRUM Master creates the integration branch, merges all wave PRs, verifies the build, and creates the integration PR for PO review. Cross-component dependency resolution is handled by the webhook receiver itself — when a Project transitions to `completed`, the receiver queries Linear for downstream Projects newly unblocked and dispatches one SCRUM Master VM per affected component.

### Dev Team (agent)

Implements issues. Creates Implementation Plans for PO approval, writes code on feature branches, creates draft PRs, runs self-review and security checks, and writes Test Instructions for the Test Team. Can manage 2-3 issues concurrently at different stages.

### Test Team (agent)

Verifies implementations using Playwright browser testing on GCE VMs. Writes and executes automated test scripts, captures screenshots as evidence, uploads results to Linear, and posts structured Test Results or Failure Reports.

### Product Owner (PO, human)

Operational decision-maker for day-to-day pipeline work. One PO is assigned per Linear Project (as the Project Lead). Responsible for:
- Approving or rejecting Implementation Plans
- Resolving Triage issues (filling gaps in issue descriptions)
- Reviewing agent work (Implementation Plan, Test Instructions, PR diff, Test Results) for each wave
- Testing integration branches locally before merge
- Merging wave integration PRs on GitHub
- Setting issues to "Done" in Linear after merge
- Breaking circular dependencies when escalated
- Resolving integration branch failures when escalated by the SCRUM Master

### Product Manager (PM, human)

Strategic decision-maker responsible for verifying that completed work delivers against the Linear Project's acceptance criteria. One PM serves the platform (all components). Responsible for:
- Final review at **Linear Project Completion**: confirming every project-level acceptance criterion is satisfied by the delivered issues
- Optional end-to-end smoke test on `main` after the final wave has merged
- Marking the Linear Project as "Completed," or opening new rework issues in the next Cycle when gaps are found
- Confirming each completed Project was appropriately scoped (not artificially narrow to inflate throughput — see the 8-12 issues-per-Project guideline in CLAUDE.md)

### Role sharing

The PO and PM roles may be held by the same person. When one person fills both roles, they perform both reviews in sequence on the same Project; no process changes. The two roles are distinguished here so the workflow is unambiguous when two people share the work.

### Multi-Repository Dispatch

Each Linear team maps to a `(repo, component)` pair. When a webhook event fires, the receiver looks up the team's mapping and dispatches a VM that clones the right repo and injects the right component context. Teams that aren't mapped fail loud (the dispatch is aborted with an error log; no VM is created).

The mapping is maintained in two parallel dicts in `agents/webhook-receiver/main.py`:

- `TEAM_COMPONENT_MAP[team_id] → component_name` — controls which component docs are injected into the agent's prompt.
- `TEAM_REPO_MAP[team_id] → "owner/repo"` — controls which GitHub repo the VM clones.

The two maps are validated at module-import time (`_validate_team_maps()`); if they ever drift out of sync the Cloud Function fails to boot. **Always update both maps in the same commit.**

#### Per-agent repo behavior

| Agent | Needs a repo? | Source |
|-------|---------------|--------|
| SCRUM Master | Yes — clones for wave-integration merges, build/test, PR creation | `TEAM_REPO_MAP[team_id]` |
| Dev Team | Yes — clones to read PRD, write code, push branches | `TEAM_REPO_MAP[team_id]` |
| Test Team | Yes — clones to check out the Dev Team's branch and run Playwright | `TEAM_REPO_MAP[team_id]` |

#### Component PRD layout

Every repo uses the same component-docs layout:

```
docs/
├── {Repo-Name}-System-Architecture.md   ← system-level architecture (Level 1)
└── design/
    └── components/
        └── {component-name}/
            ├── README.md                 ← component overview (Level 2)
            └── projects/
                ├── {PRD-1}.md            ← project PRDs (Level 3)
                ├── {PRD-2}.md
                └── ...
```

The startup script reads the component name from the dispatched VM's metadata, then prepends `docs/design/components/{name}/README.md` plus every `*.md` file under `docs/design/components/{name}/projects/` to the agent's prompt. Components with no `projects/` subdirectory have only the README injected.

If the named component directory does not exist, the startup script logs a warning and continues; the Dev Team SKILL instructs the agent to enumerate the docs directory itself via Read/Bash, so context loading degrades gracefully rather than failing.

The repo's system-architecture document (Level 1) is **not** pre-injected — agents load it themselves. The Dev Team SKILL names the canonical paths (`docs/KEN-E-System-Architecture.md` for KEN-E, `docs/FUN-E-System-Architecture.md` for Fun-E).

#### GitHub authentication

Agent VMs clone via HTTPS using org-scoped fine-grained PATs. The startup script picks the PAT based on the repo's owner prefix:

- `KEN-E-AI/*` repos → `github-pat-ken-e-ai` secret
- `Dive-Team/*` repos → `github-pat-dive-team` secret
- New orgs require a new secret + a new branch in the PAT-selector `case` in `agents/startup.sh`

PATs expire annually. Rotation runbook: `docs/ops/pat-rotation.md`.

#### Skills + agents are baked into the VM image

`.claude/skills/` and `.claude/agents/` are baked into the agent VM image at build time (from `KEN-E-AI/FUN-E` main, tagged as `skills-vX.Y.Z`). At boot, the startup script copies them into the cloned workspace's `.claude/`:

- **Skills are replaced wholesale** — the image version is authoritative.
- **Agents use no-clobber merge** — if the cloned repo defines `.claude/agents/<name>.md`, that repo-local version wins. Image-baked agents fill in any gaps.

To ship new skills or default agents: tag a release in Fun-E and rebuild the image (`agents/RELEASE.md`).

---

## 2. Issue Lifecycle Overview

Every issue follows this status progression under the 12-status workflow (see `.claude/skills/tools/agentic-shared/SKILL.md` §1 for the canonical table). Some statuses loop (test failures, PO rejections). The complete flow from intake to production:

```
            PO advances Linear Project to "Planned"
                              |
                              v
              +-------------------------------+
              |  SCRUM Master                 |
              |  Workflow 1: Project Kickoff  |
              +-------------------------------+
                    |             |
              [validated]    [gaps found]
                    |             |
                    |             v
                    |       Triage
                    |             |
                    |  [SCRUM Master Workflow 3
                    |   re-validates after PO
                    |   resolves gaps]
                    |             |
                    +<------------+
                    |
                    v
            [SCRUM Master sets status → Step 1: Planning
             AND assigns to Dev Team in one mutation;
             status change triggers Workflow 4]
                    |
                    v
              Step 1: Planning
              [Dev Team posts Implementation Plan]
                  |          |
            [no blocking  [blocking
             questions]   questions]
                  |          |
                  |          v
                  |   [PO action — moves to either]
                  |          |
                  |   +------+------+
                  |   |             |
                  |   v             v
                  | Step 1b:    Step 2:
                  | Updating    Implementing  <----+
                  | Plan          ^                |
                  |   |           |                |
                  |  [Dev Team    |                |
                  |   Workflow 5  |                |
                  |   revises]    |                |
                  |   |           |                |
                  +---+-----------+                |
                                  |                |
                                  v                |
                          [Dev Team Workflow 6     |
                           implements, opens       |
                           draft PR, posts         |
                           Test Instructions]      |
                                  |                |
                                  v                |
                          Step 3: Testing  <-------+
                                  |                |
                          [Test Team Workflow 7    |
                           runs Playwright]        |
                              |        |          ^
                       [all pass]  [failures]     |
                              |        |          |
                              v        v          |
                      Testing        Step 3b:     |
                      Complete       Resolving    |
                              |       Test Issues |
                              |        |          |
                              |  [Dev Team Workflow 8
                              |   fixes, up to 6 times]
                              |        |          |
                              |        +-->-------+
                              |
                       [PO action]
                            |          |
                       [approves]  [rejects]
                            |          |
                            v          v
                         Done    Step 3c:
                            |    Addressing
                            |    PO Concerns
                  [receiver auto-     |
                   completes project [Dev Team Workflow 9
                   when every issue   reworks, hands back
                   is terminal]       to Step 3: Testing]
                            |
                            v
                   Linear Project "Completed"
                            |
                  [receiver cascade fan-out
                   dispatches Workflow 1 for
                   newly-unblocked downstream
                   Projects]
```

> **One status name = one workflow.** The Linear board is the source of truth for "what's happening, what fires next." See `.claude/skills/tools/agentic-shared/SKILL.md` §1 for the canonical 10-status table (plus Cancelled as the 11th, no-trigger status).

---

## 3. Wave-Based Execution Model

### What is a Wave?

The SCRUM Master is dispatched per Linear Project on `Project.update`→`planned` and computes a dependency graph across all issues in that Project using topological sort. Each Project gets its own sequential wave stream — `{slug}-wave-1`, `{slug}-wave-2`, etc. Sibling Projects ship independently; a wave never mixes issues from two Projects, and an integration PR contains only one Project's work.

Within a single Project:
- **Wave 1:** That Project's issues with no unresolved blockers (intra- or cross-Project). These start immediately.
- **Wave 2:** That Project's next batch — issues that become unblocked once Wave 1's issues reach "Done."
- **Wave N:** That Project's Nth sequential batch.

Wave numbering is per-Project and starts at 1 for each Project — it is NOT the issue's global execution-level depth. Project X with issues at global levels {0, 0, 2, 5} produces three waves (X-wave-1, X-wave-2, X-wave-3), regardless of the gaps in the global numbering.

Issues within the same wave execute in parallel (no dependencies between them within that Project). Cross-Project blockers are still respected: if Project Y's wave-1 includes an issue blocked by a Project X issue, `delegate-issue` skips it until the upstream resolves, even if Y's other wave-1 issues are delegated.

### Wave Completion Gate

A wave is **complete** when all issues in that Project's wave reach "Testing Complete," "Done," or "Cancelled." Sibling Projects' waves are evaluated independently — completing Project X's wave-1 does not affect Project Y's wave evaluation.

When a wave completes, the SCRUM Master handles it differently based on wave size:

**Single-issue wave:**
1. The SCRUM Master marks the existing draft PR as ready for review (no integration branch needed)
2. The SCRUM Master runs build and test verification on the branch
3. The SCRUM Master posts a Wave Completion notification on the **Project** with the PR link and that Project's wave status summary
4. The PO tests the PR locally, merges it, and sets the issue to "Done"

**Multi-issue wave:**
1. The SCRUM Master creates a Project-scoped integration branch from `main` (`integration/cycle-{C}-{project-slug}-wave-{N}`), merges all wave PRs, resolves conflicts, and verifies the build
2. The SCRUM Master creates an integration PR and posts a Wave Completion notification on the Project with the PR link and that Project's wave status summary
3. The PO tests the integration branch locally, merges the PR, and sets all wave issues to "Done"

Every Wave Completion notification includes a **wave status summary** showing the state of that Project's waves, so the PO always knows where this specific PRD stands. The Cycle-wide picture (all Projects across all components) lives in the PO Dashboard Document, which the SCRUM Master rewrites at the end of every handler.

**Only "Done" unblocks the next wave.** "Testing Complete" does not resolve dependencies for delegation purposes. This ensures the PO has verified the integrated result before downstream work begins.

### Why Waves Matter

Without wave gating, the SCRUM Master would delegate Wave 2 issues as soon as Wave 1 issues pass testing — before the PO has verified the combined result and before the code is merged to `main`. Wave 2 Dev Teams would be working against a branch that hasn't been validated. The wave gate ensures:

- The PO verifies each batch of changes works together
- Code is merged to `main` before dependent work starts
- Dependent issues branch from a known-good state

### Why Per-Project Waves

Earlier versions of this workflow computed a single Cycle-wide wave per execution level, which mixed issues from different Projects into the same integration PR. That meant the PO had to test multiple Projects' acceptance criteria in a single review pass, and rejecting one Project's work blocked the other Project's progress. Per-Project waves keep PO review focused on one PRD at a time and let independent Projects ship in parallel.

---

## 4. Phase 1: Project Kickoff

**Trigger:** PO advances a Linear Project's status to "Planned." Linear emits a `Project.update` webhook; the receiver's `project-kickoff` rule (in `PROJECT_ROUTES`) fans out one SCRUM Master VM per mapped team in the Project's `teamIds`. The SCRUM Master runs Workflow 1 (`workflows/project-kickoff/SKILL.md`).

### Upstream Validation

The SCRUM Master first checks the Project's `blockedBy` relations. If any upstream Project is not in `completed` or `canceled` state, the SCRUM Master posts a "waiting on N upstream Projects" project update and exits without changing state. The Project remains in `planned` and will be re-evaluated when an upstream completes (the receiver's cascade fan-out, `_compute_project_cascade_dispatches`, dispatches another Project Kickoff for this Project at that point).

### Issue Validation

If unblocked, the SCRUM Master loads the Project's child issues and runs `validate-issue-completeness` on each:

| Issue Type | Required Fields |
|------------|----------------|
| User Story | Story statement, 3+ acceptance criteria, context, implementation notes, design references, estimate, priority |
| Feature | 2+ paragraph description, 3+ acceptance criteria, design references, child issues |
| Bug | Description, expected behavior, steps to reproduce, actual result, impact assessment |

**Pass:** Issue is eligible for delegation in this kickoff or a later wave; it stays in its current status (typically `Backlog`) until the SCRUM Master delegates it.

**Fail:** Issue status set to `Triage`. The SCRUM Master posts a comment listing the missing fields and @mentions the PO. One incomplete issue does not block the rest of the Project — Triaged issues are excluded from the wave plan and re-enter via Workflow 3 (Issue Triage) when the PO resolves the gaps.

### Dependency Graph Computation

The SCRUM Master computes the dependency graph for this Project's issues:
1. Build a directed acyclic graph from blocking relations
2. Apply topological sort to determine execution levels (waves)
3. Check for circular dependencies (see [Error Scenarios](#circular-dependencies))

### Initial Delegation

All Wave 1 issues (no unresolved blockers) are delegated to the Dev Team simultaneously. For each Wave 1 issue the SCRUM Master sets BOTH the issue's `stateId` (= `Step 1: Planning`) AND the issue's `assigneeId` (= Dev Team user) in a single `issueUpdate` mutation. The status change fires Workflow 4 (Step 1: Planning) on a Dev Team VM; the assignment is purely Linear-board sugar so a human glance shows who's on the issue.

The SCRUM Master then **explicitly sets the Project's status to "In Progress"** — Linear does not auto-advance Project status, so this step is required for the receiver's cascade to fire downstream when the Project later completes.

The SCRUM Master posts a Project Kickoff summary as a project update listing:
- Wave 1 issues delegated
- Wave 2+ issues waiting on blockers
- Issues sent to Triage
- Total issue and point counts

---

## 5. Phase 2: Development

The development phase consists of five Dev Team workflows, each triggered by a status change. Workflows 4 and 5 run on Opus 4.7 [1m]; Workflows 6, 8, and 9 run on Sonnet 4.6.

### Workflow 4: Step 1: Planning

**Trigger:** Issue status set to `Step 1: Planning`. The SCRUM Master sets this together with the Dev Team assignee when delegating; a human PO can also set it manually to (re-)trigger planning on a single issue.

1. Dev Team loads context Levels 1–4 (system architecture, component README, project PRD, issue + sibling summaries) per `agentic-shared/SKILL.md` §4
2. Dev Team creates a structured **Implementation Plan** containing:
   - Problem statement
   - Proposed approach
   - Project Context (audit trail showing all four levels were consulted)
   - Architecture decisions
   - Tasks grouped into waves, each with acceptance criteria and verification commands
   - Risks, files affected, decisions & assumptions, blocking questions
3. Implementation Plan posted as a Linear comment
4. **Path A (no blocking questions): auto-approve.** Dev Team posts an audit comment ("No blocking questions identified. Auto-proceeding to implementation") and sets the status to `Step 2: Implementing`. A fresh Dev Team session picks up Workflow 6.
5. **Path B (blocking questions exist):** Dev Team @mentions the PO with the questions and **leaves the issue in `Step 1: Planning`**. No status change.

**Human Checkpoint (Path B only): PO reviews the Implementation Plan.**
- **Approve:** PO sets status to `Step 2: Implementing` (triggers Workflow 6)
- **Request changes:** PO sets status to `Step 1b: Updating Plan` with a feedback comment (triggers Workflow 5)

### Workflow 5: Step 1b: Updating Plan

**Trigger:** Issue status set to `Step 1b: Updating Plan`. The PO sets this when they want changes to an existing plan.

1. Dev Team reads the PO's feedback comment and the existing Implementation Plan
2. Re-loads context Levels 1–4 (project state may have drifted since the original plan was posted)
3. Posts a revised Implementation Plan with a "Revision Notes" section summarizing what changed
4. Re-evaluates the auto-approve gate:
   - **No blocking questions remaining:** post the auto-approval audit note and set status to `Step 2: Implementing` (triggers Workflow 6)
   - **Blocking questions still present:** @mention the PO and set status back to `Step 1: Planning`. Step 1b is a transient state used only for the revision dispatch.

### Workflow 6: Step 2: Implementing

**Trigger:** Issue status set to `Step 2: Implementing`. Either the Dev Team auto-approved its own plan (Workflow 4 Path A or Workflow 5) or the PO approved manually.

1. Dev Team re-loads context Levels 1–4 on a fresh VM
2. Dev Team creates a working branch using Conventional Commits naming: `feat/`, `fix/`, `refactor/`, `test/`, `chore/`, `docs/`
3. Code is implemented (may delegate to specialist sub-agents for frontend, API, database, or testing work)
4. **Review and Verify Loop** (iterates until clean):
   - Build, lint, and format checks
   - Unit test execution
   - Parallel review delegation to `code-reviewer` and `security-auditor` sub-agents
   - Findings are addressed by severity (Critical/High → fix; Medium → fix or document deferral; Low → noted in PR body)
5. Draft PR pushed to GitHub with structured body (summary, assumptions, business logic, test results, code review, security review)
6. **Test Instructions** posted as a Linear comment with the schema in `step-2-implementing/SKILL.md` §5 (branch + build setup, test cases, edge cases, AC mapping)
7. Status set to **`Step 3: Testing`** (triggers Workflow 7 on a Test Team VM)

**Terminal-state rule.** Workflow 6 always ends with the issue in `Step 3: Testing`. The Dev Team SKILL has a mandatory pre-exit verification step (re-query the issue, retry the mutation once, escalate to the PO with the `escalation` and `po-action` labels if still wrong) — see `agentic-shared/SKILL.md` §3 for the canonical terminal-state contract.

### Workflow 8: Step 3b: Resolving Bugs

**Trigger:** Issue status set to `Step 3b: Resolving Bugs`. The Test Team sets this when Playwright tests fail or the build breaks.

1. Dev Team reads the Test Failure Report from the issue's comments
2. Re-loads context Levels 1–4 and counts the iteration (number of prior `## Test Failure Report` comments + 1)
3. Posts a wave-revocation comment if the issue's wave had previously reached `Testing Complete` (the integration PR is now stale)
4. Creates a targeted fix plan (NOT a full Implementation Plan)
5. Implements fixes, runs the Review and Verify Loop
6. Pushes changes to the existing branch
7. Evaluates whether Test Instructions need updating; posts a comment noting what changed (or noting "Test Instructions unchanged — internal fix only")
8. Status set to **`Step 3: Testing`** (returns to Test Team)

**Iteration limit: 6 rounds.** If the Dev Team would be entering a 7th iteration, it escalates instead: posts a summary of all prior attempts and sets the issue to `Triage` for SCRUM Master / human intervention.

### Workflow 9: Step 3c: PO Feedback

**Trigger:** Issue status set to `Step 3c: PO Feedback`. The PO sets this when reviewing a `Testing Complete` issue and rejecting it (with a feedback comment).

1. Dev Team re-loads context Levels 1–4 (PO rejection often surfaces because project-level intent drifted from the original plan)
2. Dev Team reads the PO's feedback comment and the current Implementation Plan / Test Instructions / Test Results
3. Full rework cycle: implement fixes, run Review and Verify Loop, push changes, update Test Instructions if behavior changed
4. Status set to **`Step 3: Testing`** (returns to Test Team for re-verification)

After the Test Team passes the re-test and sets `Testing Complete` again, the SCRUM Master's Workflow 2 (Project Update) re-engages the PO for review.

---

## 6. Phase 3: Testing

**Trigger:** Issue status set to `Step 3: Testing`. The receiver dispatches Workflow 7 on a Test Team GCE VM.

### Test Execution

1. Test Team reads **Test Instructions** from the most recent comment on the issue
2. Checks out the Dev Team's branch
3. Builds the frontend (`npm install && npm run dev`) and backend if applicable, with bounded health-check timeouts (90s backend / 60s frontend)
4. **Mandatory:** All testing is done via Playwright browser automation — no CSS inspection, no code analysis
5. Writes `test()` blocks for each test case (TC-1, TC-2, ...)
6. Uses accessible selectors: `getByRole`, `getByText`, `getByLabel`, `getByTestId`
7. Captures screenshots at: initial state, after key actions, final state
8. Includes axe-core accessibility checks where relevant
9. Executes tests: `npx playwright test`
10. Uploads screenshots to Linear via `fileUpload` GraphQL mutation

### All Tests Pass

The Test Team posts a structured **Test Results** comment:
- Summary: overall result (PASS), total/passed/failed counts
- Per-test-case results with screenshot evidence
- Acceptance criteria verification (checkbox mapping each AC to test case)
- Observations: UX notes, performance, visual polish, accessibility

Status set to **`Testing Complete`** and the issue is reassigned to the PO (the Project Lead, falling back to Ken if no Lead is set). The status change fires the SCRUM Master's Workflow 2 (Project Update), which checks whether the wave is complete and creates the integration PR if so. The receiver also adds the `po-action` label automatically — POs see incoming work via both their Linear "assigned to me" filter and the PO Action Queue saved view.

### Any Test Fails

The Test Team posts a structured **Test Failure Report**:
- Summary: overall result (FAIL), passed/failed/blocked counts
- Failed test cases: failure step, expected vs. actual (visual), screenshot evidence, severity (Critical/High/Medium), reproduction steps
- Passed test cases listed
- Blocked test cases with explanation
- Acceptance criteria impact

Status set to **`Step 3b: Resolving Bugs`**, which fires Workflow 8 on a single Dev Team VM. (Pre-refactor this status was a dual dispatch — both SCRUM Master and Dev Team. The wave-revocation responsibility moved into Workflow 8 so the receiver dispatches only one VM.)

### Authentication Handling

Firebase OAuth cannot be automated by Playwright. The Test Team:
- Checks for a test auth bypass (`VITE_AUTH_BYPASS=true` in `.env.local`)
- If no bypass exists: marks auth-dependent tests as **BLOCKED** and recommends the Dev Team add one
- Tests all non-auth-dependent functionality normally

### Error Conditions

All of the following result in status `Step 3b: Resolving Bugs` with a descriptive comment:
- Test Instructions missing or incomplete
- Branch not found
- Build failure (`npm install` or `npm run dev` fails)
- Dev server unreachable within the bounded health-check window
- Playwright runtime error

---

## 7. Phase 4: Wave Integration and PO Review

This phase begins when all issues in a wave reach "Testing Complete."

### Step 1: Wave Completion Detection

On each `Testing Complete` event, the receiver fires Workflow 2 (Project Update). The SCRUM Master:
1. Re-queries the issue's Project
2. Re-computes the dependency graph
3. Identifies the completed issue's wave (`projectId`, `waveNumber`)
4. Checks if EVERY issue in that wave is in `Testing Complete`, `Done`, or `Cancelled` (i.e. no issue is still in any active workflow status)

If the wave is not yet complete, the SCRUM Master posts a comment listing the wave's still-active issues and exits without creating an integration branch.

If the wave IS complete, the SCRUM Master proceeds to PR Preparation (Step 2).

### Step 2: PR Preparation (SCRUM Master)

The SCRUM Master prepares the wave's PR automatically. The approach depends on wave size.

**Single-issue wave (1 "Testing Complete" issue):**

1. The existing draft PR already contains all changes — no integration branch needed
2. Marks the draft PR as ready for review: `gh pr ready {PR_NUMBER}`
3. Runs verification by checking out the branch and running the build/test commands named in the component PRD (or the repo's `CLAUDE.md` §Common Commands). Typical pattern:
   - Frontend: `cd <frontend-path> && <install> && <test> && <build>`
   - Backend (if changes exist): `cd <backend-path> && <install> && <test>`
   - **If verification fails:** post a comment with error output @mentioning the PO, and stop. See [Integration Branch Failure](#integration-branch-failure).

**Multi-issue wave (2+ "Testing Complete" issues):**

Waves are scoped to a single Linear Project — sibling Projects in the same Cycle never share an integration PR. The branch and PR naming reflect this scoping (see [Integration Branch Naming](#integration-branch-naming) below for the full convention).

1. Ensures local repo is on `main` and up to date
2. Creates a branch: `integration/cycle-{C}-{project-slug}-wave-{N}` (e.g. `integration/cycle-7-ah-prd-02-wave-1`)
3. Merges each wave PR branch in dependency order:
   - If merge is clean: continue to next branch
   - If conflict is in a package-manager lockfile (`package-lock.json`, `poetry.lock`, `uv.lock`, etc.): accept either side, run the repo's install command to regenerate the lockfile, commit
   - If conflict is in other files: attempt resolution (keep both sides where independent). If successful, commit.
   - **If conflict cannot be resolved:** abort, post a comment on the Project @mentioning the PO, and stop. See [Integration Branch Failure](#integration-branch-failure).
4. Runs full verification using the build/test commands named in the component PRD:
   - Frontend: `cd <frontend-path> && <install> && <test> && <build>`
   - Backend (if changes exist): `cd <backend-path> && <install> && <test>`
   - **If verification fails:** post a comment with error output @mentioning the PO, and stop. See [Integration Branch Failure](#integration-branch-failure).
5. Pushes the integration branch
6. Creates an integration PR via `gh pr create` with:
   - Title: `integration: {project-slug} Cycle {C} Wave {N} ({issue identifiers})` — e.g. `integration: ah-prd-02 Cycle 7 Wave 1 (AH-4, AH-5)`
   - Summary listing all wave issues, PR numbers, and test results
   - Conflict resolution notes (if any)
   - Verification results (test count, build output)
   - PO testing checklist (one item per issue)
   - Post-merge steps
   - `closes #XX, closes #YY, ...` to auto-close individual draft PRs on merge

### Step 3: Wave Completion Notification

After preparing the PR, the SCRUM Master:
- Posts a project update on the Cycle with the wave summary and PR link (either the single draft PR or the integration PR)
- Includes a **wave status summary** showing all waves in the Cycle and their current state, so the PO always knows what's done, what's ready for review, and what's still in progress
- Posts a comment on each "Testing Complete" issue linking to the PR
- Does NOT delegate next-wave issues — the PO must merge and set issues to "Done" first

### Step 4: PO Agent Work Review

Before testing locally, the PO audits the agent work for each issue in the wave. This catches shallow implementations or incomplete testing before investing time in local verification.

**For each issue, open it in Linear and review these comments in order:**

#### Dev Team review

1. **Implementation Plan** (posted during Planning phase)
   - Does it address every acceptance criterion listed on the issue?
   - Are architecture decisions reasonable and consistent with the existing codebase?
   - Are risks identified and mitigated?

2. **Test Instructions** (posted by the Dev Team at the end of Workflow 6, just before the issue moves to `Step 3: Testing`)
   - Every acceptance criterion has at least one test case (TC-1, TC-2, ...) mapped to it
   - Steps are concrete and visual ("click the Submit button, verify the success toast appears") not vague ("check that it works")
   - Edge cases are covered: empty states, error states, boundary values, accessibility
   - Build setup instructions are exact (`git checkout {branch} && npm install && npm run dev`)

3. **Draft PR on GitHub** (linked from the issue or the integration PR)
   - PR body includes: summary, assumptions, business logic, test results (unit test count), and security review
   - Security review section explicitly states what was checked (not just "no issues found")
   - Code diff matches what the Implementation Plan proposed — no scope creep, no unnecessary changes
   - No commented-out code, TODO comments, or hardcoded values

#### Test Team review

4. **Test Results** (posted when issue moved to Testing Complete)
   - **Coverage check:** Compare against Test Instructions — every test case (TC-1, TC-2, ...) should have a corresponding result. If any are BLOCKED, is the reason valid?
   - **Screenshots:** Attached as images in the comment. Should show real browser state (not blank pages or error screens). Expect at minimum: initial state, after key interactions, final state — roughly 3+ screenshots per test case.
   - **AC verification:** The checkbox section should map every acceptance criterion to at least one test case. All should be checked or explicitly noted as blocked with justification.
   - **Observations:** Notes on UX, accessibility, performance, visual polish. An empty observations section may indicate surface-level testing.

#### Red flags

- Test Results that mirror Test Instructions word-for-word without adding evidence (copy-paste without actual testing)
- Screenshots that are identical across test cases or show error pages
- "PASS" on test cases that require authentication when no auth bypass was available
- Missing test cases for edge cases listed in Test Instructions
- Implementation Plan proposes modifying 5 files but the PR touches 15 (scope creep)
- Security review section is a single generic sentence

#### Quick audit (when time is limited)

If you cannot do a full review for every issue, check these three things per issue:

1. Count the ACs on the issue, then count the TCs in Test Instructions — at least 1 TC per AC
2. Count the screenshots in Test Results — at least 3 per TC (before, action, after)
3. Open the PR diff — files changed should match the Implementation Plan's file list

### Step 5: PO Local Verification

The PO checks out the wave's branch and runs the application locally using the dev-server commands named in the component PRD:

```bash
# For single-issue waves:
git checkout {branch}
# For multi-issue waves:
git checkout integration/cycle-{C}-{project-slug}-wave-{N}

# Run the frontend (and backend, if applicable) dev servers per the PRD's instructions.
# Typical pattern: cd <frontend-path> && <install> && <dev-server>
```

The PO verifies:
- Each issue's changes work correctly (guided by the Test Team's Test Results and screenshots)
- No regressions from the interaction between multiple PRs (multi-issue waves only)
- The combined application state is acceptable for production

The PO can refer to the Test Results posted on each issue in Linear for specific test cases and screenshots to guide their testing.

### Step 6: Merge or Reject

**If all issues pass PO review:**
1. PO merges the integration PR on GitHub
2. GitHub auto-closes the individual draft PRs (via `closes` references)
3. PO sets each wave issue to **"Done"** in Linear
4. If any wave PR modified `agents/startup.sh`: re-deploy to GCS
   ```bash
   gsutil cp agents/startup.sh gs://fun-e-business-function-source/agent-startup/startup.sh
   ```

**If any issue fails PO review:**
1. PO sets the failing issue(s) to **`Step 3c: PO Feedback`** with a comment describing the problem
2. The integration PR is NOT merged — it is now stale
3. The passing issues remain in `Testing Complete` and wait
4. The failing issue re-enters the Dev Team pipeline via Workflow 9 (Step 3c: PO Feedback)
5. After rework and re-testing, the issue returns to `Testing Complete`
6. The SCRUM Master's Workflow 2 fires again and automatically creates a NEW integration branch (or marks the existing draft PR ready for single-issue waves)
7. The PO re-tests the new integration branch

### What Happens After "Done"

When the PO sets a wave issue to `Done`, the receiver runs two checks in sequence:

1. **`_check_and_complete_project`** — queries the project's other issues. If every one is now `Done` / `Cancelled`, the receiver calls `projectUpdate` to mark the Project `Completed`. Linear emits a `Project.update`→`completed` webhook that re-enters the receiver's cascade fan-out (`_compute_project_cascade_dispatches`), which dispatches Workflow 1 (Project Kickoff) for any newly-unblocked downstream Projects.

2. **`_dispatch_wave_advance`** — only runs when the project did NOT just complete. Dispatches a SCRUM Master VM running Workflow 1 (Project Kickoff) in **wave-advance mode**, with `event_id = "wave-advance-{project_id}"` so multiple Done events on the same project (e.g. PO bulk-marking a wave's issues Done) collapse to one VM within the receiver's 15-minute dedup window. The agent's project-kickoff SKILL detects `status.type == "started"` in Step 1 and takes the wave-advance branch: re-computes the dependency graph, identifies any issue whose blockers are now all terminal but which has not been moved out of `Backlog` / `Triage`, and delegates each (sets `stateId = "Step 1: Planning"` + `assigneeId = Dev Team user`). If no issue is newly eligible, the agent posts a brief "no issues newly unblocked" comment and exits.

This restores the pre-refactor wave-to-wave delegation behavior. **Cross-Project unblocking (cascade) and intra-Project Wave-N → Wave-N+1 delegation (wave-advance) are both fully automatic** — no human intervention required for either.

If you want to manually re-evaluate a project's wave state (e.g., after editing a `blockedBy` relation outside the normal flow), see §15 — the receiver's `POST /kickoff` re-evaluates every Planned Project, and saving any `Done` issue's status re-triggers the wave-advance check for that project.

---

## 8. Phase 5: Project Completion Review

**Trigger:** All issues in a Linear Project reach `Done` or `Cancelled`. The receiver detects this on each `Done` event via `_check_and_complete_project` and marks the Project `Completed` automatically — no agent involved. The PM is notified separately (see Step 2 below).

This phase exists because the PO has merge authority per wave, so no single gate validates that the collection of issues in a Linear Project delivers the project-level acceptance criteria. The PM fills that gap by reviewing the completed Project as a whole before it is accepted as shipped.

### Step 1: Project Completion Detection

On each Issue.update with `state.name == "Done"`, the receiver's `_check_and_complete_project` helper:
1. Queries Linear for every issue in the issue's Project
2. Checks whether every issue is in a terminal `state.type` (`completed` or `canceled`)
3. Short-circuits if the Project is already marked terminal
4. If every issue is terminal and the Project is not, calls `projectUpdate` to set the Project `Completed`

The cascade fan-out then runs against any downstream Projects (see §9). The PM hand-off is a separate concern, currently handled manually:

### Step 2: Hand-off to PM

The PM monitors the **PM Action Queue Linear View** (filter on `pm-action` label) for Projects awaiting review. As of the skill-and-status refactor, no agent automatically applies `pm-action` on Project completion — the SCRUM Master's pre-refactor "Done" handler that did this is retired. Until a replacement workflow is added, the PM either:

- Watches the platform-level Linear Project for the cascade webhook's "Project X completed" event
- Manually applies `pm-action` to a Project they want to review (or the PO does so on their behalf)

The PM hand-off comment template (AC-to-issue mapping, `main` commit hash, explicit ask) lives in `linear-sprint-ops/SKILL.md` if a future agent needs to post it.

### Step 3: PM Review

The PM:
1. Reads the Linear Project description and acceptance criteria in full
2. Walks the AC-to-issue mapping (build it manually from the Linear Project's issue list if no agent posted it), spot-checking that delivered work actually satisfies each AC
3. Optionally runs a holistic smoke test of the completed feature on `main`
4. Confirms the Project was appropriately scoped (8-12 issues; flag artificially narrow Projects)

### Step 4: Outcome

**If all project-level ACs are satisfied:**
1. The Project is **already marked `Completed`** — the receiver advanced the state when the last issue went `Done`. The PM only needs to acknowledge the coverage; no manual status flip required.
2. The PM removes the `pm-action` label (if applied) and posts a closing comment.

**If gaps are found:**
1. PM opens one or more new rework issues describing the missing behavior, assigns them to the relevant Project (or a new Project), and references the original Project.
2. The original Project remains `Completed` — rework happens *against* a Completed Project rather than holding the Project open. "Completed with pending rework" is a valid intermediate state.
3. New rework issues enter the pipeline via the normal flow (set to `Triage` for SCRUM Master validation, or directly to `Step 1: Planning` to delegate).

**Rationale for new issues (not reopening merged ones):** Issues that have been merged to `main` remain `Done` as delivered — they did what was specified. New issues track the delta the PM identified. This keeps the Linear audit trail clean and avoids unwinding completed merges.

---

## 9. Cross-Component Dependency Resolution

**Trigger:** The webhook receiver observes a `Project.update` webhook with `data.status.type` newly = `completed`. After the skill-and-status refactor, this most commonly comes from the receiver's own `_check_and_complete_project` mutation (every issue in the Project is now terminal); the PO can also flip a Project to `Completed` manually.

The receiver itself fans out — there is no agent involved in cross-component coordination. When a Project completes:

1. The receiver queries Linear for downstream Projects (those whose `inverseRelations` reference the completed Project as a `dependency`).
2. For each downstream candidate, the receiver checks whether **every** upstream blocker is now in `completed` or `canceled` state. Downstream Projects with at least one non-terminal upstream are skipped.
3. The receiver also requires the downstream's own `status.type` to be `planned` — only Projects the PO has marked ready will be auto-kicked off.
4. For each (downstream Project × mapped team), the receiver dispatches one SCRUM Master VM running Workflow 1 (Project Kickoff). The SCRUM Master re-validates the unblock state in its own flow as defense in depth.

The dispatch graph is therefore: `last issue in Project X goes Done` → receiver auto-completes Project X → Linear webhook → receiver queries Linear → receiver dispatches SCRUM Master(s) for downstream Projects → each downstream Project goes through its own Project Kickoff flow.

Linear Cycles continue to exist as a passive grouping artifact for velocity / calendar reporting, but agents do not react to Cycle webhooks. Readiness is determined entirely by `Project.status` and `ProjectRelation` data.

For manual override (e.g., after the PO edits a Project's `blockedBy` relations and wants the receiver to re-evaluate without waiting for a webhook), `POST /kickoff` re-runs the unblock check across every Planned Project — see §15.

---

## 10. Post-Launch Review Model

Fun-E does not yet have live users in production. The current workflow (described above) gives the PO merge authority per wave, and the PM reviews only at Linear Project Completion. This accepts some risk: a gap in an early wave will not be caught by the PM until the full Project completes. Because there are no live users, that risk is acceptable.

**Production launch target: 2026-09-22.**

When live users arrive, the review model tightens. Concretely, at launch:

1. **PM reviews every wave** (not just Project Completion). A new hand-off step is inserted in Phase 4 between **Step 5: PO Local Verification** and **Step 6: Merge or Reject**:
   - After PO local verification passes, the PO posts a "Ready for Release" comment on the integration PR and applies a new `release-ready` label
   - The PM performs a final check (reads the PO's approval, scans the PR diff, reviews Test Results) and either merges or rejects
2. A new row is added to §12: **Final Release Approval — 4 business hours (PM)**.
3. The Status Transitions table in §14 is updated so `Testing Complete` → `Done` is actioned by the PM, not the PO.
4. **Project Completion Review** (§8) remains in place as a secondary gate — it catches cross-wave integration gaps that per-wave reviews can miss.

This section should be converted into the active workflow (above) at launch. Until then, treat it as a forward-looking note so the switchover is predictable.

---

## 11. Error Scenarios and Recovery

### Test Failure Loop (up to 6 iterations)

When the Test Team reports failures:
1. Status set to `Step 3b: Resolving Bugs`
2. Receiver dispatches Workflow 8 (Dev Team only — single VM, no SCRUM Master dual-dispatch)
3. Dev Team reads the Failure Report, fixes the code, pushes changes
4. Status set back to `Step 3: Testing` — Test Team re-tests
5. This loop can repeat up to **6 times**
6. On the 7th failure: the Dev Team posts a summary of all attempts and sets the issue to `Triage`. Workflow 3 (Issue Triage) fires the SCRUM Master, which @mentions the PO with the `escalation` label for a human decision.

### Integration Branch Failure

The SCRUM Master may fail to create or verify the integration branch in Workflow 2. Failure modes:

**Unresolvable merge conflict:**
1. The SCRUM Master aborts the merge and posts a comment on each conflicting issue describing the conflict (file names, conflicting branches) and @mentions that issue's PO
2. The PO decides how to resolve: request the Dev Team to rebase one of the branches, or manually resolve the conflict
3. After resolution, save `Testing Complete` on a wave issue (or move out and back) to re-fire Workflow 2

**Test or build failure on the integration branch:**
1. The SCRUM Master posts a comment on each wave issue with the error output and @mentions that issue's PO
2. The integration branch is NOT pushed and no PR is created
3. The PO investigates: the failure likely stems from an interaction between PRs that passed individually. The PO sets the responsible issue to `Step 3c: PO Feedback` with a description of the integration failure.
4. The Dev Team fixes the issue (Workflow 9), Test Team re-verifies (Workflow 7), and Workflow 2 re-fires when the issue returns to `Testing Complete`.

In both cases, the SCRUM Master adds the `escalation` label to the Project for visibility.

### PO Rejection During Integration Review

1. PO identifies problem(s) during local testing of the integration branch
2. PO sets the failing issue(s) to `Step 3c: PO Feedback` with a feedback comment
3. The receiver fires Workflow 9 (Dev Team)
4. After rework: Dev Team sets `Step 3: Testing` → Test Team re-tests → returns to `Testing Complete`
5. Workflow 2 re-fires and creates a new integration branch (or marks the existing draft PR ready for single-issue waves)
6. PO re-tests the new integration branch
7. Other passing issues in the wave remain in `Testing Complete` and wait

### PM Rejection at Project Completion

1. PM reviews the Linear Project's completed issues against project-level acceptance criteria and finds one or more gaps
2. PM opens one or more new rework issues describing the missing behavior, attaching them to the relevant Project
3. The original Linear Project is already marked `Completed` (the receiver advanced the state via `_check_and_complete_project` when the last issue went `Done`). PM does NOT roll the state back; rework issues add the missing behavior to an already-Completed Project.
4. Rework issues enter the pipeline via the standard flow: PM (or PO) sets each rework issue to `Triage` (fires Workflow 3 — SCRUM Master validates, attaches to a project, delegates) or directly to `Step 1: Planning` (fires Workflow 4 — Dev Team begins planning immediately).
5. When the rework issues are `Done`, the receiver re-runs `_check_and_complete_project`. Because the Project is already `Completed`, the helper short-circuits at the "already terminal" check and exits without re-flipping state.
6. PM re-reviews when the rework is shipped.
7. Merged-to-`main` work is NOT rolled back; the rework issues add the missing behavior instead.

### Circular Dependencies

If the SCRUM Master detects a circular dependency during graph computation (Workflow 1 or Workflow 3):
1. Posts a comment on ALL affected issues listing the circular chain (e.g., "FUN-4 → FUN-6 → FUN-8 → FUN-4")
2. @mentions each issue's PO on its respective comment (affected issues may belong to different Projects with different Leads)
3. Adds the `escalation` label to all affected issues
4. Does NOT delegate any issues in the circular group
5. Issues outside the circle proceed normally
6. When the PO breaks the cycle (by removing or reversing a blocking relation), the next status change event triggers a re-computation of the graph

Cross-component circular dependencies (Project A blocks Project B blocks Project A) are detected during Project Kickoff via Linear's `inverseRelations` graph; the receiver-side cascade also no-ops on a Project whose blockers are still active, so a circular chain naturally stalls until the PO breaks it.

### Stale Agent Sessions

If a Dev Team agent appears unresponsive (issue stuck in `Step 1: Planning` for more than 2 hours, with no Implementation Plan comment posted):
1. The PO sets the issue back to `Triage` (fires Workflow 3) — the SCRUM Master will re-validate and re-delegate, which spawns a fresh Dev Team session
2. Or the PO sets the issue to `Step 1: Planning` again (saves the same status); Linear emits a fresh webhook IF the status was changed via a status-change mutation (in practice, save the status by selecting it again from the dropdown)
3. If re-delegation also stalls, the PO @mentions the issue's PO and backup PO (deduped to one @mention if they resolve to the same user) with the `escalation` label

There is no scheduled watchdog for stale Dev Team sessions post-refactor. The pre-refactor `In Review` watchdog covered a different failure mode (wrong-terminal-state on Workflow 2 exit) that no longer exists — the terminal-state verification contract in `agentic-shared/SKILL.md` §3 catches wrong-state writes inside the agent before exit.

### Wave Revocation (Issue Returns from Testing Complete)

If an issue that was `Testing Complete` is moved back to an active status (typically `Step 3c: PO Feedback` from a PO rejection, or `Step 3b: Resolving Bugs` from a re-test failure):
1. The wave completion is revoked — it is no longer complete even if it was previously
2. Any integration branch that was created for that wave is now stale
3. Workflow 8 (the Dev Team agent handling Step 3b) explicitly checks for this and posts a wave-revocation comment if the rest of the wave was already at `Testing Complete`. Workflow 9 follows the same pattern via the Dev Team's standard rework flow.
4. After the issue is fixed and re-tested, Workflow 2 re-fires when the issue returns to `Testing Complete`

### Mid-Sprint Issue Addition

When a new issue is added mid-sprint that needs SCRUM Master attention:
1. The PO (or whoever creates the issue) sets it to `Triage`
2. Workflow 3 fires — the SCRUM Master validates, attaches it to the right Project (if not already), re-computes the dependency graph, and either delegates to the Dev Team (if all blockers terminal) or leaves it in `Triage` until upstream blockers resolve
3. Posts a comment summarizing the validation result

### Duplicate Webhook Events

Before performing any action, agents verify the issue is not already in the target state. If the issue has already been processed (e.g., already delegated, already in the expected status), the agent skips gracefully and logs. The receiver also has a 15-minute dedup window keyed on `agent_type | event_id | prompt-hash` that suppresses duplicate VM dispatches. Duplicate events are not treated as errors.

---

## 12. SLA Enforcement

The SCRUM Master tracks response times for human checkpoints and escalates when targets are at risk. SLA clocks only run during business hours (configurable per human, default 9:00 AM - 5:00 PM ET). Overnight requests start the clock at 9:00 AM the next business day.

| Activity | Actor | SLA | Reminder | Escalation |
|----------|-------|-----|----------|------------|
| Implementation Plan approval | PO | 4 business hours | @mention issue's PO at 2 hours | `escalation` label + @mention PO and backup PO at 4 hours |
| Wave Review (integration branch testing) | PO | 8 business hours | @mention issue's PO at 4 hours | `escalation` label + @mention PO and backup PO at 8 hours |
| Unblocking request (Triage gaps, questions) | PO | 2 business hours | @mention issue's PO at 1 hour | `escalation` label + @mention PO and backup PO at 2 hours |
| Project Completion Review | PM | 1 business day | @mention PM at 4 business hours | `escalation` label + @mention PM at 1 business day |

### PO Assignment

The PO for each issue is the **Linear Project Lead** on the issue's Project — set the Lead attribute in the Linear project sidebar to assign ownership. The backup PO is always **Ken** (workspace-level fallback, hardcoded). To reassign an issue's PO, change the Project Lead in Linear; no code deploy is required.

- If an issue has no Project, or the Project has no Lead set, the PO defaults to Ken (same as the backup).
- When the PO and backup PO resolve to the same user (Ken is the Lead), escalation comments @mention Ken once — not twice.
- For **Project-level notifications** (Project Kickoff summary, Project Completion review, cross-component escalations), the SCRUM Master @mentions the Project Lead. The workspace fallback is NOT appended to Project-level notifications — only the Lead is addressed.

Resolution is implemented via `resolve-po-for-issue` and `resolve-pos-for-cycle` in the `linear-sprint-ops` skill (operations 13 and 14).

### PM Assignment

The PM is always **Ken** — a hardcoded platform-wide constant. There is no separate backup PM; Ken is the sole PM, and SLA escalations re-@mention the PM when the response window elapses.

- The PM applies to all components and all Linear Projects — unlike the PO, the PM is not scoped per Project.
- For **Project Completion Reviews**, the SCRUM Master @mentions the PM on the Linear Project's update comment.

Resolution is implemented via `resolve-pm` in the `linear-sprint-ops` skill (operation 15) — a constant returning `ken`. No Linear query or workspace setting is involved.

### Escalation Process

1. At the reminder threshold: SCRUM Master resolves the relevant human (PO via `resolve-po-for-issue`, PM via `resolve-pm`) and posts a comment @mentioning them (Linear Asks surfaces this in Slack)
2. At the escalation threshold: SCRUM Master adds the `escalation` label and the appropriate action label (`po-action` for PO SLAs, `pm-action` for PM SLAs) and posts a comment @mentioning the responsible human(s) — for PO SLAs: the PO and, when distinct, the backup PO; for PM SLAs: just the PM (Linear sends them direct notifications)

---

## 13. PO and PM Visibility Tools

Four mechanisms give Product Owners and the Product Manager real-time visibility into pipeline status and a clear view of what needs their attention.

### PO Action Queue (Linear View)

A saved Linear View filtered on the `po-action` label provides an always-current list of issues requiring PO action. This is the PO's primary "inbox."

**How it works:**
- Agents apply the `po-action` label when issues need PO input (escalations, integration failures, circular dependencies)
- The webhook receiver automatically applies `po-action` when issues enter `Triage` or `Testing Complete` status
- The webhook receiver automatically removes `po-action` (best-effort, idempotent) on every other status transition
- The saved View sorts by priority and groups by status

**PO workflow:** Check this view to see everything waiting on you. Click into any issue for the full context (Implementation Plan, Test Results, etc.).

### PM Action Queue (Linear View)

A saved Linear View filtered on the `pm-action` label provides the PM's project-level inbox. It surfaces Linear Projects awaiting Project Completion Review.

**How it works:**
- The SCRUM Master applies `pm-action` to the Linear Project when all its issues reach "Done" or "Cancelled" (see §8)
- The Project Completion hand-off comment on the Project @mentions the PM (Linear Asks surfaces this in Slack)
- The label is removed when the PM marks the Project "Completed" (or remains applied if the PM opens rework issues)
- The saved View groups by component and sorts by the Project's most recent issue `completedAt`

**PM workflow:** Check this view to see every Project awaiting final review. Click into any Project for the full context (project description, acceptance criteria, completed issues, SCRUM Master's hand-off comment with AC-to-issue mapping).

### PO Dashboard Documents (Living Documents)

Two Linear Documents are automatically maintained by agents and give the PO a narrative view of status, action queue with dependency impact, and the wave/dependency chain.

**Component Dashboard** — maintained by the SCRUM Master, attached to the component's Project. Shows:
- Action queue with dependency impact ("merging this PR unblocks Wave 1")
- Wave-by-wave progress table for the active Project
- Dependency chain showing what PO actions advance the pipeline

The component dashboard is rewritten on every SCRUM Master trigger (status changes, wave completions, Project lifecycle events), so it is at most one event stale. POs should bookmark this document for quick access. The platform-level rollup is delivered by the Daily Briefing (next section); there is no continuously-rewritten platform dashboard document.

### Daily Briefing (Morning Push Notification)

Every weekday at 9:00 AM ET, Cloud Scheduler invokes the webhook receiver's `/daily-summary` endpoint. The receiver itself (no agent VM, no LLM) queries Linear, computes a deterministic health indicator, and posts a project update directly on the platform-level Project (`PLATFORM_PROJECT_ID` env var):

- **On Track** (green): No PO items pending > 48h on `Step 1: Planning`, no `Step 2: Implementing` > 5 days, no escalations
- **At Risk** (yellow): PO items aging past those thresholds, or any issue in `Triage`
- **Off Track** (red): Active escalation label on any issue

The briefing includes the PO action queue (sorted escalations-first, then oldest-first) and a per-Project summary table. The implementation is `agents/webhook-receiver/daily_briefing.py`. Behavior is fail-soft: a missing `PLATFORM_PROJECT_ID` or a transient Linear failure logs and returns 200 to Cloud Scheduler so it does not retry-storm.

> **Note:** the daily-briefing health classifier still references some pre-refactor status names internally and is being updated incrementally. Its output is a useful general signal but the specific aging thresholds may not yet match the new status names exactly.

### Configuration

**Linear (manual setup):**
1. **Create workspace labels:** `po-action` and `pm-action` (distinct bright colors for visibility)
2. **Create saved Views:**
   - PO Action Queue: Filter `label = po-action`, sort by priority, group by status
   - PM Action Queue: Filter `label = pm-action`, group by component, sort by latest issue `completedAt`

**Infrastructure (Terraform variables / locals):**
- `po_action_label_id` — the Linear ID of the `po-action` label (from Linear workspace settings)
- `pm_action_label_id` — the Linear ID of the `pm-action` label
- Onboarding a new team: add the team to `TEAM_REPO_MAP` + `TEAM_COMPONENT_MAP` in `agents/webhook-receiver/main.py`, in the same commit. (After the skill-and-status refactor, no per-team state IDs are required — routing matches on Linear status names verbatim.)

**Infrastructure (GCP secrets in `fun-e-business`):**
- `linear-token-webhook-receiver` — Linear API token for the webhook receiver (po-action label management, project auto-completion)
- `linear-token-{agent-type}` — per-agent Linear API tokens (scrum-master, dev-team, test-team)
- `claude-code-api-key` — Anthropic API key for the Claude Code CLI on agent VMs
- `github-pat-ken-e-ai` — fine-grained PAT for cloning + pushing to `KEN-E-AI/*` repos
- `github-pat-dive-team` — fine-grained PAT for cloning + pushing to `Dive-Team/*` repos

The agent VM service account (`fun-e-agent-vm@fun-e-business`) has a project-level `roles/secretmanager.secretAccessor` grant — adding a new secret to the project automatically gives the VMs read access; no per-secret IAM grant is needed.

The webhook receiver matches on status names alone to add/remove the `po-action` label and to dispatch workflows. No Linear Automation rules are needed.

---

## 14. Quick Reference Tables

### Status Transitions

The 10-status workflow plus Cancelled. Canonical reference: `.claude/skills/tools/agentic-shared/SKILL.md` §1.

| From | To | Triggered By | Notes |
|------|----|-------------|-------|
| (new) | Backlog | Linear default | Entry point |
| Backlog | Triage | PO or SCRUM Master | When SCRUM Master needs to validate or PO flags gaps |
| Triage | Step 1: Planning | SCRUM Master Workflow 3 | Validation passed, blockers terminal — SCRUM Master sets both `stateId` (Step 1: Planning) and `assigneeId` (Dev Team user) in one `issueUpdate` mutation; the status-change webhook fires Workflow 4 |
| Triage | (no change) | SCRUM Master Workflow 3 | Validation failed, no project, or blockers still active — issue waits in Triage |
| Step 1: Planning | (no change) | Dev Team Workflow 4 (Step 1) | Agent posts Implementation Plan as a Linear comment; issue stays in Step 1: Planning awaiting PO action (Path B) |
| Step 1: Planning | Step 2: Implementing | Dev Team Workflow 4 Path A | Auto-approve — no blocking questions |
| Step 1: Planning | Step 1b: Updating Plan | PO | Requests plan revisions |
| Step 1: Planning | Step 2: Implementing | PO | Approves the plan |
| Step 1b: Updating Plan | Step 1: Planning | Dev Team Workflow 5 | Revised plan still has blocking questions — back to PO |
| Step 1b: Updating Plan | Step 2: Implementing | Dev Team Workflow 5 | Revised plan auto-approves |
| Step 2: Implementing | Step 3: Testing | Dev Team Workflow 6 | Implementation done, draft PR opened, Test Instructions posted |
| Step 3: Testing | Testing Complete | Test Team Workflow 7 | All Playwright tests pass; issue reassigned to PO |
| Step 3: Testing | Step 3b: Resolving Bugs | Test Team Workflow 7 | Any test fails, build fails, or Test Instructions missing |
| Step 3b: Resolving Bugs | Step 3: Testing | Dev Team Workflow 8 | Fix complete, ready for re-test |
| Step 3b: Resolving Bugs | Triage | Dev Team Workflow 8 | 6-iteration cap exceeded — escalate for human intervention |
| Step 3c: PO Feedback | Step 3: Testing | Dev Team Workflow 9 | Rework complete, ready for re-test |
| Testing Complete | Done | PO | Merges integration PR, approves in Linear |
| Testing Complete | Step 3c: PO Feedback | PO | Rejects during integration review (with feedback comment) |
| Done | (terminal) | - | Receiver auto-completes Project when every issue is terminal |
| Cancelled | (terminal) | PO | Issue removed from scope |

### Linear Project State Transitions

| From | To | Triggered By | Notes |
|------|----|-------------|-------|
| Planned | Started | SCRUM Master Workflow 1 | First wave delegated; SCRUM Master calls `update-project-state` because Linear does not auto-advance |
| Started | Completed | Receiver (`_check_and_complete_project`) | Every child issue is `Done` / `Cancelled`; the receiver calls `projectUpdate` automatically. PM review of project-level ACs is a separate manual check (see §8) — finding gaps results in new rework issues, not a state rollback. |

### Webhook Routing

The dispatch logic lives in `ISSUE_STATUS_ROUTES` (one rule per status, identity-matched on `new_status`) and `PROJECT_ROUTES` (project-kickoff) in `agents/webhook-receiver/main.py`, plus three dynamic handlers: `_compute_project_cascade_dispatches` (cross-project completion cascade), `_check_and_complete_project` (project auto-completion when all issues are terminal), and `_dispatch_wave_advance` (intra-project Wave-N → Wave-N+1 delegation when the project is still active). Routing is **identity-based on `new_status`** — there are no `from_state_key`, `require_assignee`, or `extra_check` predicates, and assignment changes don't route to anything (every workflow trigger is a status change).

Every row below maps to a named rule. Grep `name="<rule-name>"` in `main.py` to jump to source. All routes dispatch on Sonnet 4.6 unless **[Opus 1M]** or **[DeepSeek]** is noted. (DeepSeek V4-Pro is served via DeepInfra → per-VM LiteLLM proxy at `127.0.0.1:8889`; see `agents/litellm-proxy/README.md` and `docs/ops/deepseek-v4-pro-swap.md` for the Sonnet→DeepSeek migration plan.)

| Event | Condition | Routes To | Rule |
|-------|-----------|-----------|------|
| `Project.update` | `data.status.type` newly = `planned` (i.e. `statusId` changed) | SCRUM Master Workflow 1: Project Kickoff (`workflows/project-kickoff/SKILL.md`) — one dispatch per mapped `data.teamIds[*]` | `project-kickoff` |
| `Project.update` | `data.status.type` newly = `completed` (i.e. `statusId` changed) | **Receiver-side cascade fan-out** (`_compute_project_cascade_dispatches`): queries Linear for downstream Projects newly unblocked, dispatches Workflow 1 for each. The completing Project itself triggers no agent dispatch. | (no static rule — receiver-internal) |
| Status → `Testing Complete` | Any | SCRUM Master Workflow 2: Project Update (wave PR creation / single-issue PR ready) | `project-update` |
| Status → `Triage` | Any | SCRUM Master Workflow 3: Issue Triage | `issue-triage` |
| Status → `Step 1: Planning` | Any | Dev Team Workflow 4: Step 1: Planning **[Opus 1M]** | `step-1-planning` |
| Status → `Step 1b: Updating Plan` | Any | Dev Team Workflow 5 (revise plan after PO feedback) **[Opus 1M]** | `step-1b-updating-plan` |
| Status → `Step 2: Implementing` | Any | Dev Team Workflow 6: Step 2: Implementing | `step-2-implementing` |
| Status → `Step 3: Testing` | Any | Test Team Workflow 7: Step 3: Testing **[DeepSeek]** | `step-3-testing` |
| Status → `Step 3b: Resolving Bugs` | Any | Dev Team Workflow 8: Step 3b: Resolving Bugs | `step-3b-resolving-test-issues` |
| Status → `Step 3c: PO Feedback` | Any | Dev Team Workflow 9: Step 3c: PO Feedback | `step-3c-addressing-po-concerns` |
| Status → `Done` | Any | **Receiver-side, two-pass:** (1) `_check_and_complete_project` — if every issue in the Project is now terminal, mark the Project Completed (the resulting `Project.update`→`completed` webhook re-enters the cascade above; no agent VM). (2) If the project is still active, `_dispatch_wave_advance` dispatches one SCRUM Master VM running Workflow 1 (Project Kickoff) in wave-advance mode, deduped per project — re-computes the dependency graph and delegates any Wave-N+1 issues whose blockers just cleared. | (no static rule — receiver-internal) |
| Status → `Backlog` / `Cancelled` / `Scheduled` | Any | **No dispatch.** None of these is a workflow entry point. Scheduled is a Linear platform-imposed status that can't be deleted. | (no match — INFO log) |
| `POST /kickoff` (no signature check) | Any | Receiver-internal: re-evaluates every `planned` Project and dispatches Workflow 1 for each whose blockedBy upstreams are all terminal — see §15 | `handle_webhook` |
| Cloud Scheduler (9 AM ET weekdays) | `POST /daily-summary` | **Receiver-generated Daily Briefing** (templated, no agent VM — see `agents/webhook-receiver/daily_briefing.py`). | `handle_webhook` |

Linear webhook events outside this table (`Issue.create`, `Comment.*`, `IssueLabel.*`, `Project.create`, `Project.delete`, `Project.update` for non-status edits, `Cycle.*`, etc.) are accepted, logged at INFO with their `type` and `action`, and produce no dispatch. The diagnostic log includes `data_keys` so unrouted-but-observed event classes can be diagnosed.

#### Dispatch deduplication

Every dispatch is hashed by `(agent_type, event_id, prompt)` into a 16-char `dedup-key` (`create_agent_vm` in `agents/webhook-receiver/main.py`). Before creating a VM, the receiver lists existing GCE instances filtered by that label and skips if a non-terminated VM was created within the last 15 minutes (`DEDUP_WINDOW_SECONDS = 900`).

Two important consequences:

- **Dedup is per-event.** Different `event_id`s never collide. For Issue events, `event_id` is the issue identifier (`UI-28`, `UI-29`, etc.) — so a bulk status change across 30 issues legitimately spawns 30 VMs, not one.
- **Dedup only applies while the previous VM is alive.** Once a VM is `TERMINATED`, the dedup stops covering it. If a webhook for the same `(agent_type, event_id)` arrives shortly after the previous VM exited, a new VM is created.

### Agent Summary

| Agent | Runs On | Lifecycle | Linear Account |
|-------|---------|-----------|----------------|
| SCRUM Master | GCE VM (ephemeral) | Runs to completion, self-deletes | `scrum-master` |
| Dev Team | GCE VM (ephemeral) | Runs to completion, self-deletes | `dev-team` |
| Test Team | GCE VM (ephemeral) | Runs to completion, self-deletes | `test-team` |

All agents are stateless. They query Linear for fresh data on every trigger. No cached state is maintained between sessions. Orphan VMs are cleaned up every 2 hours (max age: 2 hours).

### Integration Branch Naming

```
integration/cycle-{cycle_number}-{project_slug}-wave-{wave_number}
```

Waves are scoped per Linear Project — sibling Projects in the same Cycle never share an integration PR. The `{project_slug}` is derived from the Project name's `<PRD-ID>` prefix (per CLAUDE.md §Linear Issue Structure: project names follow the convention `<PRD-ID>: <PRD title>`), lowercased and slugified. For projects whose names don't follow that convention, the SCRUM Master falls back to Linear's `slugId` field.

Examples:
- `integration/cycle-1-ah-prd-02-wave-1` (Cycle 1, AH-PRD-02 first wave)
- `integration/cycle-1-ah-prd-02-wave-2` (Cycle 1, AH-PRD-02 second wave — ships after wave-1 PR is merged)
- `integration/cycle-1-ah-prd-03-wave-1` (Cycle 1, AH-PRD-03 first wave — runs in parallel with AH-PRD-02 if no cross-Project blockers)
- `integration/cycle-2-ah-prd-04-wave-1` (Cycle 2, AH-PRD-04 first wave)

Wave numbering is per-Project and sequential starting at 1 — the `wave_number` is NOT the issue's global execution-level depth. Project X with issues at global levels {0, 0, 2, 5} ships three sequential waves (X-wave-1, X-wave-2, X-wave-3), regardless of the gaps in global level numbers.

---

## 15. Manually Triggering Agents

Sometimes you need to fire an agent outside the normal flow — to retry a stuck issue, replay a missed event, or test a code change to the receiver. This section is the supported way to do that. It also documents the failure mode that's easy to hit by accident.

### Triggering matrix (one issue at a time)

| You want to... | Do this | What fires |
|---|---|---|
| Re-evaluate every Planned Project (after editing `blockedBy` relations) | `curl -X POST https://<receiver-url>/kickoff` | The receiver queries Linear for all `planned` Projects, drops any with non-terminal blockers, and dispatches one SCRUM Master VM per (newly-unblocked Project × mapped team). No agent VM if every Planned Project still has open blockers. `/kickoff` has no signature check today — anyone with the URL can hit it. |
| Re-run the Daily Briefing | `curl -X POST https://<receiver-url>/daily-summary` | The receiver queries Linear and posts a project update on `PLATFORM_PROJECT_ID` — no agent VM. |
| Run Project Kickoff for a single Project | Advance the Linear Project's status to "Planned" (or move from Planned → some other state and back) | One SCRUM Master VM per mapped team on the Project |
| Run a SCRUM Master against a triaged issue | Move the issue to `Triage` (or save the status if already there) | One SCRUM Master VM |
| Have the Dev Team begin planning a specific issue | Move the issue to `Step 1: Planning` (and assign to the Dev Team user for Linear-board visibility) | One Dev Team VM (Workflow 4) |
| Have the Dev Team revise an existing plan | Move the issue from `Step 1: Planning` → `Step 1b: Updating Plan` with a feedback comment | One Dev Team VM (Workflow 5) |
| Have the Dev Team begin implementation on an approved plan | Move the issue from `Step 1: Planning` → `Step 2: Implementing` | One Dev Team VM (Workflow 6) |
| Have the Test Team test an issue | Move the issue to `Step 3: Testing` | One Test Team VM (Workflow 7) |
| Have the Dev Team fix a test failure | Move the issue to `Step 3b: Resolving Bugs` | One Dev Team VM (Workflow 8) |
| Have the Dev Team rework after PO rejection | Move the issue from `Testing Complete` → `Step 3c: PO Feedback` with a feedback comment | One Dev Team VM (Workflow 9) |
| Re-run wave-completion / integration-PR creation | Save `Testing Complete` on a wave issue (or move out and back) | One SCRUM Master VM (Workflow 2) |

**One mental model:** every workflow trigger is a status change. There are no special-case assignment-based triggers. If you want a workflow to run, set the issue to the corresponding status — the Linear board always tells you what will fire next.

### Do NOT bulk-status-change

Every issue's status transition is a separate webhook → separate VM. There is no batching at the receiver.

If you bulk-move 30 issues to a triggering status, the receiver dispatches **30 VMs in seconds**, one per issue. The dedup mechanism does not protect against this because each VM has a different `event_id`. Use `POST /kickoff` (which fans out one VM per Planned Project) when you want to start fresh work across many issues.

### Triggers that don't fire

Statuses with no rule: `Backlog`, `Cancelled`, `Scheduled`. Setting an issue to any of these is a no-op at the receiver — INFO log only, no agent dispatched.

### Watching what fires

Two places to confirm a dispatch happened:

- **GCE Console / `gcloud compute instances list`** — VMs are named `agent-<agent-type>-<event-id>-<timestamp>` (e.g. `agent-dev-team-ui-28-1777901183`). The `<event-id>` for issue events is the issue identifier; for `/kickoff` it is `kickoff`; for `/daily-summary` it is `daily-briefing`. Filter by `labels.managed-by="fun-e-agent-pipeline"`.
- **Cloud Logging** — `resource.type="cloud_run_revision" AND resource.labels.service_name="fun-e-webhook-receiver-development"` shows webhook deliveries; `protoPayload.methodName="v1.compute.instances.insert"` on `gce_instance` shows successful VM dispatches.

If a status change you expected to fire produced no VM, the receiver almost certainly logged the reason (`Ignoring In Progress transition for ...`, `Ignoring Backlog→Scheduled for ...`, etc.). Filter Cloud Logging for the issue identifier in the same window.
