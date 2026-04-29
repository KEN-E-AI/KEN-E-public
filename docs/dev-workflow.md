# Development Workflow

This document describes the full lifecycle of an issue from sprint intake to production merge. It is the **human-facing** reference for Product Owners, Product Managers, and developers reading the repo to understand how work moves through the pipeline.

> **Canonical source convention.** The autonomous-agent operational behavior — exact API calls, status transitions, decision rules — lives in the workflow SKILL files baked into the agent VM image (in the Fun-E repo: `.claude/skills/workflows/{dev-team,scrum-master,sprint-manager,test-team}-workflow/SKILL.md`). This doc is the human summary. **If the two disagree, the SKILL files are canonical for agent behavior and this doc is canonical for humans.** When changing the workflow, update the SKILL files first, then mirror the human-facing change here.

---

## Table of Contents

1. [Roles](#1-roles)
2. [Issue Lifecycle Overview](#2-issue-lifecycle-overview)
3. [Wave-Based Execution Model](#3-wave-based-execution-model)
4. [Phase 1: Sprint Planning](#4-phase-1-sprint-planning)
5. [Phase 2: Development](#5-phase-2-development)
6. [Phase 3: Testing](#6-phase-3-testing)
7. [Phase 4: Wave Integration and PO Review](#7-phase-4-wave-integration-and-po-review)
8. [Phase 5: Project Completion Review](#8-phase-5-project-completion-review)
9. [Phase 6: Cycle Completion](#9-phase-6-cycle-completion)
10. [Post-Launch Review Model](#10-post-launch-review-model)
11. [Error Scenarios and Recovery](#11-error-scenarios-and-recovery)
12. [SLA Enforcement](#12-sla-enforcement)
13. [PO and PM Visibility Tools](#13-po-and-pm-visibility-tools)
14. [Quick Reference Tables](#14-quick-reference-tables)

---

## 1. Roles

### Sprint Manager (agent)

Cross-component orchestrator. Monitors Cycle start and completion events across all Teams and computes cross-team dependency graphs. When a Cycle is started, the Sprint Manager evaluates all active Cycles and delegates any unblocked ones to the appropriate SCRUM Master (Flow 2: Initial Kickoff). When a Cycle completes, the Sprint Manager evaluates which downstream Cycles are now unblocked and delegates them (Flow 1: Cycle Completion Cascade). One Sprint Manager operates across the entire KEN-E platform.

### SCRUM Master (agent)

Sprint-level coordinator for a single component (e.g., Fun-E). Validates issue completeness, computes the intra-Cycle dependency graph, delegates issues to the Dev Team in wave order, monitors status transitions, enforces SLAs, and triggers wave/cycle completion flows. When a wave completes testing, the SCRUM Master creates the integration branch, merges all wave PRs, verifies the build, and creates the integration PR for PO review.

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
| Sprint Manager | No — Linear-only orchestrator | passes `repo=""` |
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

Every issue follows this status progression. Some statuses loop (test failures, PO rejections). The complete flow from intake to production:

```
                         Sprint Manager delegates Cycle
                                    |
                                    v
                        +---------------------+
                        |   SCRUM Master       |
                        |   Sprint Planning    |
                        +---------------------+
                            |             |
                    [valid]               [gaps found]
                            |             |
                            v             v
                    Awaiting          Triage
                    Assignment          |
                            |       [PO fixes gaps]
                            |             |
                            v             v
                    +---------------------+        Scheduled
                    |   Dev Team          |<----------+
                    |   Flow 1: Planning  |
                    +---------------------+
                            |
                            v
                    Planning
                            |
                    [plan posted]
                            |
                            v
                    Awaiting Review  <-------+
                            |                |
                    [PO approves]    [PO gives feedback]
                            |                |
                            v                |
                    In Progress        Planning
                            |
                    +---------------------+
                    |   Dev Team          |
                    |   Flow 2: Implement |
                    +---------------------+
                            |
                            v
                    In Review
                    [self-review, security, lint, test]
                            |
                    [all checks pass]
                            |
                            v
                    Ready for Testing
                            |
                    +---------------------+
                    |   Test Team         |
                    |   Playwright tests  |
                    +---------------------+
                        |             |
                [all pass]      [failures]
                        |             |
                        v             v
                Testing          Resolving Test
                Complete         Issues
                        |             |
                        |     [Dev fixes, up to 6x]
                        |             |
                        |             v
                        |        In Progress ---> In Review
                        |             |               |
                        |             +-------<-------+
                        |                             |
                        |                             v
                        |                    Ready for Testing
                        |                             |
                        |             +-------<-------+
                        |
                [all wave issues complete]
                        |
                        v
                Wave Completion
                and Integration
                        |
                [SCRUM Master creates integration branch + PR]
                [PO tests locally]
                [PO merges integration PR]
                        |
                        v
                    Done
                        |
                [SCRUM Master delegates next wave]
                        |
                [all project issues Done]
                        |
                        v
                Project Completion
                Review (PM)
                        |
                [PM verifies project-level ACs]
                        |
                        v
                Linear Project "Completed"
                        |
                [all cycle issues Done]
                        |
                        v
                Cycle Complete
                        |
                [Sprint Manager delegates next Cycles]
```

---

## 3. Wave-Based Execution Model

### What is a Wave?

The SCRUM Master computes a dependency graph for all issues in a Cycle using topological sort. Issues are grouped into **execution levels** called waves:

- **Wave 0 (Level 0):** Issues with no blocking dependencies. These start immediately.
- **Wave 1 (Level 1):** Issues whose blockers are all in Wave 0. These start after Wave 0 is approved by the PO.
- **Wave N (Level N):** Issues whose blockers are all in Waves 0 through N-1.

Issues within the same wave execute in parallel (no dependencies between them).

### Wave Completion Gate

A wave is **complete** when all issues at that execution level reach "Testing Complete," "Done," or "Cancelled."

When a wave completes, the SCRUM Master handles it differently based on wave size:

**Single-issue wave:**
1. The SCRUM Master marks the existing draft PR as ready for review (no integration branch needed)
2. The SCRUM Master runs build and test verification on the branch
3. The SCRUM Master posts a Wave Completion notification with the PR link and a wave status summary
4. The PO tests the PR locally, merges it, and sets the issue to "Done"

**Multi-issue wave:**
1. The SCRUM Master creates an integration branch from `main`, merges all wave PRs, resolves conflicts, and verifies the build
2. The SCRUM Master creates an integration PR and posts a Wave Completion notification with the PR link and a wave status summary
3. The PO tests the integration branch locally, merges the PR, and sets all wave issues to "Done"

Every Wave Completion notification includes a **wave status summary** showing the state of all waves in the Cycle, so the PO always knows: which waves are done, which wave is ready for review, and which waves still have issues in progress.

**Only "Done" unblocks the next wave.** "Testing Complete" does not resolve dependencies for delegation purposes. This ensures the PO has verified the integrated result before downstream work begins.

### Why Waves Matter

Without wave gating, the SCRUM Master would delegate Wave 1 issues as soon as Wave 0 issues pass testing — before the PO has verified the combined result and before the code is merged to `main`. Wave 1 Dev Teams would be working against a branch that hasn't been validated. The wave gate ensures:

- The PO verifies each batch of changes works together
- Code is merged to `main` before dependent work starts
- Dependent issues branch from a known-good state

---

## 4. Phase 1: Sprint Planning

**Trigger:** Sprint Manager assigns a Cycle's issues to the SCRUM Master.

### Issue Validation

For each issue in the Cycle, the SCRUM Master runs `validate-issue-completeness`:

| Issue Type | Required Fields |
|------------|----------------|
| User Story | Story statement, 3+ acceptance criteria, context, implementation notes, design references, estimate, priority |
| Feature | 2+ paragraph description, 3+ acceptance criteria, design references, child issues |
| Bug | Description, expected behavior, steps to reproduce, actual result, impact assessment |

**Pass:** Issue status set to "Awaiting Assignment."

**Fail:** Issue status set to "Triage." The SCRUM Master posts a comment listing the missing fields and @mentions the PO. One incomplete issue does not block the rest of the sprint.

### Dependency Graph Computation

The SCRUM Master computes the dependency graph:
1. Build a directed acyclic graph from blocking relations
2. Apply topological sort to determine execution levels (waves)
3. Check for circular dependencies (see [Error Scenarios](#circular-dependencies))

### Initial Delegation

All Wave 0 issues (no unresolved blockers) are delegated to the Dev Team simultaneously. The SCRUM Master posts a Sprint Kickoff summary as a project update listing:
- Wave 0 issues delegated
- Wave 1+ issues waiting on blockers
- Issues sent to Triage
- Total issue and point counts

---

## 5. Phase 2: Development

**Trigger:** SCRUM Master assigns an issue to the Dev Team agent.

### Flow 1: Planning and Approval

1. Dev Team loads component context, issue details, and architecture documentation
2. Status set to **"Planning"**
3. Dev Team creates a structured **Implementation Plan** containing:
   - Problem statement
   - Proposed approach
   - Architecture decisions
   - Sub-tasks with estimates
   - Files to be modified
   - Risk assessment
4. Implementation Plan posted as a Linear comment
5. Status set to **"Awaiting Review"**

**Human Checkpoint: PO reviews the Implementation Plan.**
- **Approve:** PO sets status to "In Progress" (triggers Flow 2)
- **Request changes:** PO sets status to "Planning" with feedback comment (Dev Team revises and resubmits)

This is the only human checkpoint within the development workflow itself.

### Flow 2: Implementation

1. Dev Team creates a working branch using Conventional Commits naming: `feat/`, `fix/`, `refactor/`, `test/`, `chore/`, `docs/`
2. Status set to **"In Progress"**
3. Code is implemented (may delegate to specialist sub-agents for frontend, API, database, or testing work)
4. **Review and Verify Loop** (iterates until clean):
   - Build, lint, and format checks
   - Unit test execution
   - Security review (hardcoded secrets, SQL injection, XSS, dangerouslySetInnerHTML, CORS wildcards, auth bypass paths, dependency safety)
   - Self-review against CLAUDE.md guidelines
5. Draft PR created on GitHub with structured body (summary, assumptions, business logic, test results, security review)
6. Status set to **"In Review"**
7. **Test Instructions** posted as a Linear comment with exact schema:
   - Branch and build setup (exact git + npm/uv commands)
   - What the Dev Team verified (automated checks)
   - Test cases (TC-1, TC-2, ...) with preconditions, steps, expected results, and AC mapping
   - Edge cases to test
   - Acceptance criteria mapping
   - Test Instructions focus on **visual/browser verification only** — not code internals
8. Status set to **"Ready for Testing"**

**Terminal-state rule.** Flow 2 always ends with the issue in `Ready for Testing`. The `In Review` status (set in step 6) is transient — it exists only during the self-review/lint/test loop and must be replaced by `Ready for Testing` once Test Instructions are posted. If the Dev Team session ever exits with the issue still in `In Review`, the Test Team webhook never fires and the issue stalls silently — Linear returns `success: true` for any valid state mutation, so the wrong terminal state is invisible to the agent's own exit handler. The Dev Team SKILL has a mandatory pre-exit verification step (re-query the issue, retry the mutation once, escalate to the PO with the `escalation` and `po-action` labels if still wrong), and the SCRUM Master runs a stalled-`In Review` watchdog every 15 minutes as defense in depth (see §11 *Stalled In Review*).

### Flow 3: Resolving Test Issues

**Trigger:** Test Team reports failures. Status set to "Resolving Test Issues."

1. Dev Team reads the Test Failure Report from the issue's comments
2. Creates a targeted fix plan
3. Implements fixes, runs the full Review and Verify Loop
4. Pushes changes to the existing branch
5. Evaluates whether Test Instructions need updating
6. Posts a comment noting what changed
7. Status set to **"Ready for Testing"** (returns to Test Team)

**Iteration limit: 6 rounds.** If the issue reaches a 7th test failure cycle, the Dev Team escalates to the SCRUM Master with a summary of all attempts. The SCRUM Master notifies the PO for a human decision.

### Flow 4: PO Rejection

**Trigger:** PO rejects the work during integration branch review. Status changes from "Testing Complete" to "In Progress" with feedback.

1. Dev Team reads the PO's feedback comment
2. Full rework cycle: implement fixes, run Review and Verify Loop, update Test Instructions
3. Status set to **"Ready for Testing"** (returns to Test Team for re-verification)

---

## 6. Phase 3: Testing

**Trigger:** Issue status set to "Ready for Testing." Webhook routes to Test Team agent on a GCE VM.

### Test Execution

1. Test Team reads **Test Instructions** from the most recent comment on the issue
2. Checks out the Dev Team's branch
3. Builds the frontend (`npm install && npm run dev`) and backend if applicable
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

Status set to **"Testing Complete."**

### Any Test Fails

The Test Team posts a structured **Test Failure Report**:
- Summary: overall result (FAIL), passed/failed/blocked counts
- Failed test cases: failure step, expected vs. actual (visual), screenshot evidence, severity (Critical/High/Medium), reproduction steps
- Passed test cases listed
- Blocked test cases with explanation
- Acceptance criteria impact

Status set to **"Resolving Test Issues"** (routes to both SCRUM Master and Dev Team).

### Authentication Handling

Firebase OAuth cannot be automated by Playwright. The Test Team:
- Checks for a test auth bypass (`VITE_AUTH_BYPASS=true` in `.env.local`)
- If no bypass exists: marks auth-dependent tests as **BLOCKED** and recommends the Dev Team add one
- Tests all non-auth-dependent functionality normally

### Error Conditions

All of the following result in status "Resolving Test Issues" with a descriptive comment:
- Test Instructions missing or incomplete
- Branch not found
- Build failure (npm install or npm run dev fails)
- Dev server unreachable
- Playwright runtime error

---

## 7. Phase 4: Wave Integration and PO Review

This phase begins when all issues in a wave reach "Testing Complete."

### Step 1: Wave Completion Detection

On each "Testing Complete" event, the SCRUM Master:
1. Re-queries all issues in the Cycle
2. Re-computes the dependency graph
3. Identifies the completed issue's execution level (wave)
4. Checks if ALL issues at that level are "Testing Complete," "Done," or "Cancelled"

If the wave is not yet complete, the SCRUM Master posts a comment listing remaining issues in the wave still in progress.

If the wave IS complete, the SCRUM Master runs the **Wave Completion and Integration** sub-flow.

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

1. Ensures local repo is on `main` and up to date
2. Creates a branch: `integration/cycle-{C}-wave-{N}`
3. Merges each wave PR branch in dependency order:
   - If merge is clean: continue to next branch
   - If conflict is in a package-manager lockfile (`package-lock.json`, `poetry.lock`, `uv.lock`, etc.): accept either side, run the repo's install command to regenerate the lockfile, commit
   - If conflict is in other files: attempt resolution (keep both sides where independent). If successful, commit.
   - **If conflict cannot be resolved:** abort, post a comment on the Cycle @mentioning the PO, and stop. See [Integration Branch Failure](#integration-branch-failure).
4. Runs full verification using the build/test commands named in the component PRD:
   - Frontend: `cd <frontend-path> && <install> && <test> && <build>`
   - Backend (if changes exist): `cd <backend-path> && <install> && <test>`
   - **If verification fails:** post a comment with error output @mentioning the PO, and stop. See [Integration Branch Failure](#integration-branch-failure).
5. Pushes the integration branch
6. Creates an integration PR via `gh pr create` with:
   - Title: `integration: Cycle {C} Wave {N} ({issue identifiers})`
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

2. **Test Instructions** (posted when issue moved to Ready for Testing)
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
git checkout integration/cycle-{C}-wave-{N}

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
1. PO sets the failing issue(s) to **"In Progress"** with a comment describing the problem
2. The integration PR is NOT merged — it is now stale
3. The passing issues remain in "Testing Complete" and wait
4. The failing issue re-enters the Dev Team pipeline (Flow 4: PO Rejection)
5. After rework and re-testing, the issue returns to "Testing Complete"
6. The SCRUM Master detects wave completion again and automatically creates a NEW integration branch
7. The PO re-tests the new integration branch

### What Happens After "Done"

When the PO sets wave issues to "Done", the SCRUM Master's Done handler fires for each:

1. Closes the issue's individual draft PR if still open (with a comment noting the integration PR)
2. Re-computes the dependency graph
3. Identifies any Wave N+1 issues now fully unblocked (all blockers are "Done" or "Cancelled")
4. Delegates newly unblocked issues to the Dev Team
5. Checks if all Cycle issues are now "Done" or "Cancelled" — if yes, triggers Cycle Completion

---

## 8. Phase 5: Project Completion Review

**Trigger:** All issues in a Linear Project reach "Done" or "Cancelled." The SCRUM Master detects this on each "Done" event by querying the issue's `project` field and checking whether any sibling issues remain in an active status.

This phase exists because the PO has merge authority per wave, so no single gate validates that the collection of issues in a Linear Project delivers the project-level acceptance criteria. The PM fills that gap by reviewing the completed Project as a whole before it is marked shipped.

### Step 1: Project Completion Detection

On each "Done" event, after the wave-completion check, the SCRUM Master:
1. Reads the issue's Linear Project
2. Queries all issues belonging to that Project (across any Cycles)
3. Checks whether every issue is "Done" or "Cancelled"
4. Skips if the Project is already marked "Completed"

If all issues are terminal and the Project is not yet Completed, the SCRUM Master runs the **Project Completion Review** sub-flow.

### Step 2: Hand-off to PM

The SCRUM Master:
1. Applies the `pm-action` label to the Linear Project
2. Posts a project update on the Linear Project summarizing:
   - All completed issues grouped by wave, with issue identifiers and titles
   - The Linear Project's acceptance criteria, each annotated with the issue(s) that delivered it
   - The `main` branch commit hash reflecting the final merged state
   - An explicit ask: "PM, please verify project-level ACs and mark this Project Completed or open rework issues."
3. @mentions the PM (resolved via `resolve-pm` — see §12 PM Assignment)

### Step 3: PM Review

The PM:
1. Reads the Linear Project description and acceptance criteria in full
2. Walks the SCRUM Master's AC-to-issue mapping, spot-checking that delivered work actually satisfies each AC
3. Optionally runs a holistic smoke test of the completed feature on `main`
4. Confirms the Project was appropriately scoped (8-12 issues; flag artificially narrow Projects)

### Step 4: Outcome

**If all project-level ACs are satisfied:**
1. PM marks the Linear Project as "Completed" (Linear sets `completedAt` automatically)
2. The SCRUM Master detects the Project state change, removes the `pm-action` label, and posts a closing comment
3. Proceeds to the Cycle Completion check (see §9)

**If gaps are found:**
1. PM opens one or more new rework issues describing the missing behavior, assigns them to the next Cycle, and references the original Project
2. PM does NOT mark the Linear Project as "Completed" — it remains in progress until the rework issues are Done
3. New rework issues enter the pipeline from Scheduled (the standard entry point) and are picked up by the SCRUM Master on the next Sprint Planning pass
4. When the rework issues are Done, Project Completion Detection re-fires and the PM re-reviews

**Rationale for new issues (not reopening merged ones):** Issues that have been merged to `main` remain "Done" as delivered — they did what was specified. New issues track the delta the PM identified. This keeps the Linear audit trail clean and avoids unwinding completed merges.

---

## 9. Phase 6: Cycle Completion

**Trigger:** All issues in the Cycle are "Done" or "Cancelled," and every Linear Project represented in the Cycle has been marked "Completed" by the PM.

### Pre-conditions

The SCRUM Master verifies:
- No issues remain in "Testing Complete" (all must be "Done" via integration PR merge)
- No issues remain in any active status ("In Progress," "In Review," "Testing," etc.)
- Every Linear Project touched by the Cycle has been marked "Completed" by the PM (Project Completion Review has run and passed for each)

### Completion Steps

1. Post a Cycle summary listing all completed issues, total estimate points delivered, and any cancellations with reasons
2. Set the Cycle status to **"Complete"**
3. This triggers the **Sprint Manager** to re-evaluate cross-component dependencies
4. The Sprint Manager checks if any downstream Cycles are now unblocked and delegates them to their SCRUM Masters

### Cross-Component Dependencies

The Sprint Manager maintains a cross-team dependency graph:
- **Cycle A blocks Cycle B** if any issue in Cycle A blocks any issue in Cycle B (same team or different team)
- A blocking Cycle must be "Complete" (or the specific blocking issues must be "Done") before the blocked Cycle can start
- Cycle dates are informational, not gates — readiness is determined by actual blocker resolution

---

## 10. Post-Launch Review Model

Fun-E does not yet have live users in production. The current workflow (described above) gives the PO merge authority per wave, and the PM reviews only at Linear Project Completion. This accepts some risk: a gap in an early wave will not be caught by the PM until the full Project completes. Because there are no live users, that risk is acceptable.

**Production launch target: 2026-09-22.**

When live users arrive, the review model tightens. Concretely, at launch:

1. **PM reviews every wave** (not just Project Completion). A new hand-off step is inserted in Phase 4 between **Step 5: PO Local Verification** and **Step 6: Merge or Reject**:
   - After PO local verification passes, the PO posts a "Ready for Release" comment on the integration PR and applies a new `release-ready` label
   - The PM performs a final check (reads the PO's approval, scans the PR diff, reviews Test Results) and either merges or rejects
2. A new row is added to §12: **Final Release Approval — 4 business hours (PM)**.
3. The Status Transitions table in §14 is updated so "Testing Complete → Done" is actioned by the PM, not the PO.
4. **Project Completion Review** (§8) remains in place as a secondary gate — it catches cross-wave integration gaps that per-wave reviews can miss.

This section should be converted into the active workflow (above) at launch. Until then, treat it as a forward-looking note so the switchover is predictable.

---

## 11. Error Scenarios and Recovery

### Test Failure Loop (up to 6 iterations)

When the Test Team reports failures:
1. Status set to "Resolving Test Issues"
2. Webhook triggers both SCRUM Master (handler) and Dev Team (Flow 3)
3. Dev Team reads the Failure Report, fixes the code, pushes changes
4. Status returns to "Ready for Testing" — Test Team re-tests
5. This loop can repeat up to **6 times**
6. On the 7th failure: Dev Team escalates to SCRUM Master with a summary of all attempts. SCRUM Master notifies the PO with the `escalation` label for a human decision.

### Integration Branch Failure

The SCRUM Master may fail to create or verify the integration branch. Failure modes:

**Unresolvable merge conflict:**
1. The SCRUM Master aborts the merge and posts a comment on each conflicting issue describing the conflict (file names, conflicting branches) and @mentions that issue's PO
2. The PO decides how to resolve: request the Dev Team to rebase one of the branches, or manually resolve the conflict
3. After resolution, the affected issue's branch is updated and the SCRUM Master retries integration on the next "Testing Complete" event (or the PO triggers a re-evaluation)

**Test or build failure on the integration branch:**
1. The SCRUM Master posts a comment on each wave issue with the error output and @mentions that issue's PO
2. The integration branch is NOT pushed and no PR is created
3. The PO investigates: the failure likely stems from an interaction between PRs that passed individually. The PO sets the responsible issue to "In Progress" with a description of the integration failure.
4. The Dev Team fixes the issue, Test Team re-verifies, and the SCRUM Master retries integration.

In both cases, the SCRUM Master adds the `escalation` label to the Cycle for visibility.

### PO Rejection During Integration Review

1. PO identifies problem(s) during local testing of the integration branch
2. PO sets the failing issue(s) to "In Progress" with feedback
3. SCRUM Master marks the issue as unresolved and notes the integration branch is stale
4. Dev Team reads PO feedback and begins rework (Flow 4)
5. After rework: Dev Team submits → Test Team re-tests → returns to "Testing Complete"
6. The SCRUM Master detects wave completion again and automatically creates a new integration branch
7. PO re-tests the new integration branch
8. Other passing issues in the wave remain in "Testing Complete" and wait

### PM Rejection at Project Completion

1. PM reviews the Linear Project's completed issues against project-level acceptance criteria and finds one or more gaps
2. PM opens one or more new rework issues in the next Cycle describing the missing behavior, and links them to the original Project
3. PM does NOT mark the Linear Project as "Completed" — it remains in its current state (typically Started) until rework is delivered
4. The SCRUM Master does not remove the `pm-action` label yet
5. Rework issues enter the pipeline from Scheduled and follow the standard Flow 1 → Flow 2 → Testing → Wave Integration
6. When all rework issues are Done, Project Completion Detection re-fires and the PM re-reviews
7. Merged-to-`main` work is NOT rolled back; the PM's rework issues add the missing behavior instead

### Circular Dependencies

If the SCRUM Master detects a circular dependency during graph computation:
1. Posts a comment on ALL affected issues listing the circular chain (e.g., "FUN-4 -> FUN-6 -> FUN-8 -> FUN-4")
2. @mentions each issue's PO on its respective comment (affected issues may belong to different Projects with different Leads)
3. Adds the `escalation` label to all affected issues
4. Does NOT delegate any issues in the circular group
5. Issues outside the circle proceed normally
6. When the PO breaks the cycle (by removing or reversing a blocking relation), the next status change event triggers a re-computation of the graph

The Sprint Manager performs the same check at the Cycle level for cross-component circular dependencies.

### Stale Agent Sessions

If a Dev Team agent appears unresponsive (issue stuck in "Planning" for more than 2 hours):
1. SCRUM Master posts a comment on the issue noting the stale session
2. Adds the `escalation` label
3. Attempts re-delegation to the Dev Team agent (creates a new GCE VM session)
4. If re-delegation also stalls: posts an escalation comment @mentioning the issue's PO and backup PO (deduped to one @mention if they resolve to the same user)

### Stalled In Review (Dev Team Flow 2 silent failure)

If an issue sits in `In Review` status for more than 30 minutes with no recent activity, a Cloud Scheduler-driven watchdog (every 15 minutes) detects it and dispatches the SCRUM Master in **Stalled-Issue Triage** mode. The watchdog exists because the most common Flow 2 failure mode is the Dev Team agent setting `In Review` instead of `Ready for Testing` as its terminal state — Linear returns `success: true` for the mutation, so the failure is invisible to the agent's own exit handler and the issue stalls silently (`In Review` is not in the webhook routing table).

The webhook receiver pre-filters cheaply (status + `updatedAt`) and only dispatches a SCRUM Master VM (per affected team) when at least one issue is genuinely stalled. Most ticks find nothing.

The SCRUM Master classifies each candidate into one of three buckets:

- **Bucket A — Likely Dev Team Flow 2 terminal-state failure.** Test Instructions are present on the issue and a PR is attached. The SCRUM Master applies `escalation` + `po-action`, @mentions the PO with a diagnostic comment, and recommends the PO verify the PR and promote the issue to `Ready for Testing` themselves. **No auto-promotion** — the PO confirms PR health before flipping state.
- **Bucket B — Mid-Flow-2 stall.** The issue is in `In Review` but no Test Instructions exist. The Dev Team session likely died during the review-and-verify loop. The SCRUM Master applies `escalation` + `po-action` and asks the PO to inspect Cloud Logging for the most recent Dev Team VM and either re-trigger the Dev Team or move the issue back to `In Progress`.
- **Bucket C — Active rework (false positive).** The most recent unresolved comment is from the PO (rejection feedback) or the Test Team (Test Failure Report) and the issue is iterating normally. **The SCRUM Master skips silently** — no labels, no comment. Repeated benign comments on an actively-iterating issue add noise.

After processing every candidate, the SCRUM Master posts a single Flow 3 summary on the team's most recent active Cycle showing per-issue bucket assignments and actions taken.

### Incomplete Issues at Sprint Start

If an issue fails `validate-issue-completeness` during Sprint Planning:
1. Issue set to "Triage" with a comment listing missing fields
2. PO fills in the gaps and sets the issue back to "Scheduled"
3. Webhook routes the "Scheduled" (from Triage) event to the SCRUM Master
4. SCRUM Master re-validates the issue:
   - If it passes: set to "Awaiting Assignment," check blockers, delegate if ready
   - If it still fails: send back to Triage (loop continues)
5. One incomplete issue does NOT block the rest of the sprint — other issues proceed

### Wave Revocation (Issue Returns from Testing Complete)

If an issue that was "Testing Complete" returns to "Resolving Test Issues" (or is rejected by PO back to "In Progress"):
1. The wave completion is revoked — it is no longer complete even if it was previously
2. Any integration branch that was created for that wave is now stale
3. The SCRUM Master posts a comment noting the revocation
4. After the issue is fixed and re-tested, the wave completion check re-triggers when it returns to "Testing Complete"

### Mid-Sprint Issue Addition

When a new issue is added to the Cycle mid-sprint:
1. SCRUM Master validates the issue using `validate-issue-completeness`
2. Re-computes the dependency graph with the new issue
3. If the issue has no unresolved blockers and passes validation: delegate immediately
4. Posts a comment noting the mid-sprint addition and any impact on the dependency graph

### Duplicate Webhook Events

Before performing any action, agents verify the issue is not already in the target state. If the issue has already been processed (e.g., already delegated, already in the expected status), the agent skips gracefully and logs. Duplicate events are not treated as errors.

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
- For **cycle-level notifications** (Sprint Kickoff, Cycle Review, cross-component escalations), the SCRUM Master/Sprint Manager @mentions the deduplicated set of Project Leads across issues in the cycle. The workspace fallback is NOT appended to cycle-level notifications — only the distinct Leads are addressed.

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
- Agents apply the `po-action` label when issues need PO input (wave completion, escalations, integration failures, circular dependencies)
- The webhook receiver automatically applies `po-action` when issues enter "Awaiting Review" or "Triage" status
- The webhook receiver automatically removes `po-action` when issues leave "Awaiting Review," "Triage," or "Testing Complete" status
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
- Wave-by-wave progress table for the active Cycle
- Dependency chain showing what PO actions advance the pipeline

**Platform Dashboard** — maintained by the Sprint Manager, attached to the platform-level Project. Shows:
- Consolidated action queue across all components
- Per-component health and progress summaries
- Cross-component dependencies and blocked Cycles

Both documents are rewritten on every agent trigger (status changes, wave completions, cycle events), so they are at most one event stale. POs should bookmark these documents for quick access.

### Daily Briefing (Morning Push Notification)

Every weekday at 9:00 AM ET, Cloud Scheduler triggers the Sprint Manager to post a project status update on the platform Project with a health indicator:

- **On Track** (green): No PO items pending > 2 business hours, no escalations
- **At Risk** (yellow): PO items pending > 2 business hours, or issues in Triage
- **Off Track** (red): Active escalation, integration failure, or circular dependency

The briefing includes the PO action queue, a component summary table, cross-component dependencies, and SLA status. It surfaces automatically in Slack via Linear Asks.

### Configuration

**Linear (manual setup):**
1. **Create workspace labels:** `po-action` and `pm-action` (distinct bright colors for visibility)
2. **Create saved Views:**
   - PO Action Queue: Filter `label = po-action`, sort by priority, group by status
   - PM Action Queue: Filter `label = pm-action`, group by component, sort by latest issue `completedAt`

**Infrastructure (Terraform variables / locals):**
- `po_action_label_id` — the Linear ID of the `po-action` label (from Linear workspace settings)
- `pm_action_label_id` — the Linear ID of the `pm-action` label
- `state_ids_by_team` (Terraform `local` in `infra/terraform/agents.tf`) — JSON-encoded map from `team_id` → `{awaiting_review, testing_complete, planning, triage, backlog}` state IDs. Drives all state-ID-dependent webhook routing (PO-approval routing, `po-action` labeling, Scheduled-from-Triage / Backlog detection). Validated at Cloud Function import time against `TEAM_REPO_MAP` — every mapped team must have an entry with all five state IDs, or the function fails to boot. To onboard a new team, add the team to `TEAM_REPO_MAP` + `TEAM_COMPONENT_MAP` AND its state IDs to `local.state_ids_by_team`, in the same change.

**Infrastructure (GCP secrets in `fun-e-business`):**
- `linear-token-webhook-receiver` — Linear API token for the webhook receiver (po-action label management)
- `linear-token-{agent-type}` — per-agent Linear API tokens (sprint-manager, scrum-master, dev-team, test-team)
- `claude-code-api-key` — Anthropic API key for the Claude Code CLI on agent VMs
- `github-pat-ken-e-ai` — fine-grained PAT for cloning + pushing to `KEN-E-AI/*` repos
- `github-pat-dive-team` — fine-grained PAT for cloning + pushing to `Dive-Team/*` repos

The agent VM service account (`fun-e-agent-vm@fun-e-business`) has a project-level `roles/secretmanager.secretAccessor` grant — adding a new secret to the project automatically gives the VMs read access; no per-secret IAM grant is needed.

The webhook receiver uses the state IDs to automatically add/remove the `po-action` label on issue status transitions. The SCRUM Master applies `pm-action` to Linear Projects on Project Completion Detection (see §8). No Linear Automation rules are needed.

---

## 14. Quick Reference Tables

### Status Transitions

| From | To | Triggered By | Notes |
|------|----|-------------|-------|
| (new) | Scheduled | PO assigns to Cycle | Entry point |
| Scheduled | Awaiting Assignment | SCRUM Master | After validation passes |
| Scheduled | Triage | SCRUM Master | Validation fails (missing fields) |
| Triage | Scheduled | PO | After filling gaps |
| Awaiting Assignment | Planning | Dev Team | Begins work |
| Planning | Awaiting Review | Dev Team | Implementation Plan posted |
| Awaiting Review | In Progress | PO | Approves plan |
| Awaiting Review | Planning | PO | Requests changes |
| In Progress | In Review | Dev Team | Code complete, review starting |
| In Review | Ready for Testing | Dev Team | Review passes, Test Instructions posted |
| Ready for Testing | Testing | Test Team | Begins test execution |
| Testing | Testing Complete | Test Team | All tests pass |
| Testing | Resolving Test Issues | Test Team | Any test fails |
| Resolving Test Issues | In Progress | Dev Team | Begins fixing |
| Testing Complete | Done | PO | Merges integration PR, approves in Linear |
| Testing Complete | In Progress | PO | Rejects during integration review |
| Done | (terminal) | - | SCRUM Master checks for wave, project, and cycle completion |
| Cancelled | (terminal) | PO | Issue removed from scope |

### Linear Project State Transitions

| From | To | Triggered By | Notes |
|------|----|-------------|-------|
| Started | (awaiting PM review) | SCRUM Master | All issues "Done" or "Cancelled" — applies `pm-action` label, posts hand-off comment |
| Started | Completed | PM | Project-level ACs verified, Linear sets `completedAt` automatically |
| Started | Started (with rework) | PM | Gaps found — PM opens new rework issues in next Cycle, Project stays Started until re-review |

### Webhook Routing

| Event | Condition | Routes To |
|-------|-----------|-----------|
| Cycle `startedAt` set | Was previously null | Sprint Manager (Flow 2: Initial Kickoff) |
| Cycle `completedAt` set | Was previously null | Sprint Manager (Flow 1: Cycle Completion Cascade) |
| Issue assignee changed | Assignee = SCRUM Master user | SCRUM Master |
| Issue assignee changed | Assignee = Dev Team user | Dev Team |
| Status -> "Planning" | Previous = Awaiting Review, Assignee = Dev Team user | Dev Team |
| Status -> "In Progress" | Assignee = Dev Team user | Dev Team |
| Status -> "Ready for Testing" | Any | Test Team |
| Status -> "Resolving Test Issues" | Any | SCRUM Master + Dev Team (dual dispatch) |
| Status -> "Testing Complete" | Any | SCRUM Master |
| Status -> "Done" | Any | SCRUM Master (wave + project + cycle completion checks) |
| Status -> "Scheduled" | Previous = Triage | SCRUM Master |
| Status -> "Scheduled" | Previous = Backlog | SCRUM Master |
| Linear Project state -> "Completed" | Any | SCRUM Master (removes `pm-action` label, checks for Cycle completion) |
| Cloud Scheduler (9 AM ET) | `/daily-summary` endpoint | Sprint Manager |
| Cloud Scheduler (every 15 min) | `/check-stalled-in-review` endpoint | SCRUM Master (per affected team) — Stalled-Issue Triage (see §11) |

The SCRUM Master's "Done" handler runs **Wave Completion Detection** (§7), **Project Completion Detection** (§8), and **Cycle Completion Detection** (§9) in order. No separate webhook is registered for project or cycle completion detection — they are sub-flows of the Done handler.

### Agent Summary

| Agent | Runs On | Lifecycle | Linear Account |
|-------|---------|-----------|----------------|
| Sprint Manager | GCE VM (ephemeral) | Runs to completion, self-deletes | `sprint-manager` |
| SCRUM Master | GCE VM (ephemeral) | Runs to completion, self-deletes | `scrum-master` |
| Dev Team | GCE VM (ephemeral) | Runs to completion, self-deletes | `dev-team` |
| Test Team | GCE VM (ephemeral) | Runs to completion, self-deletes | `test-team` |

All agents are stateless. They query Linear for fresh data on every trigger. No cached state is maintained between sessions. Orphan VMs are cleaned up every 2 hours (max age: 2 hours).

### Integration Branch Naming

```
integration/cycle-{cycle_number}-wave-{wave_number}
```

Examples:
- `integration/cycle-1-wave-1` (Cycle 1, Wave 0 issues)
- `integration/cycle-1-wave-2` (Cycle 1, Wave 1 issues)
- `integration/cycle-2-wave-1` (Cycle 2, Wave 0 issues)
