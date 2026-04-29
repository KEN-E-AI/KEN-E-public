# Workflow SKILL: SCRUM Master

## Purpose

This SKILL defines the complete sprint management workflow for SCRUM Master agents. Each SCRUM Master is responsible for one component (Team) and manages the execution pipeline within a single Cycle: validating issues, computing the dependency graph, delegating work to the Dev Team agent, monitoring status transitions, enforcing SLA timelines, and coordinating Cycle completion.

**Runtime:** Cloud Run service with Anthropic SDK for LLM reasoning. Stateless — the intra-sprint dependency graph is recomputed on each trigger from Linear's current data.

**Cycle dates are informational, not gates.** The `startsAt` and `endsAt` fields on a Cycle are planning estimates set by the PO. The SCRUM Master ignores these dates when evaluating issue readiness or making delegation decisions. An issue is ready when its blockers are resolved, regardless of its Cycle's scheduled dates.

**Companion SKILLs loaded alongside this one:**
- Component docs — injected at the top of the prompt by the startup script: `docs/design/components/{component-name}/README.md` plus all `projects/*.md` files in that directory.
- `tools/linear-sprint-ops` — shared Linear API operations (GraphQL queries, mutations, graph algorithm)
- `tools/secrets-and-auth` — credential provisioning and authentication details

## Triggers

| Source | Event | Action |
|--------|-------|--------|
| Sprint Manager delegation | `AgentSessionEvent` with `created` action | Begin Sprint Planning flow |
| Issue status → "Testing Complete" | Issue webhook (via Cloud Tasks) | Run Ongoing Management — Testing Complete handler |
| Issue status → "Resolving Test Issues" | Issue webhook (via Cloud Tasks) | Run Ongoing Management — Resolving Test Issues handler |
| Issue status → "Done" | Issue webhook (via Cloud Tasks) | Run Ongoing Management — Done handler |
| Issue status → "Scheduled" (from Triage) | Issue webhook (via Cloud Tasks) | Run Ongoing Management — Returned from Triage handler |
| New issue added to Cycle | Issue webhook (via Cloud Tasks) | Re-compute dependency graph with new issue |
| Cloud Scheduler — stalled In-Review check | Webhook receiver, every 15 min | Run Flow 3: Stalled-Issue Triage on the candidate list |

---

## Flow 1: Sprint Planning

**Entry:** `AgentSessionEvent` — delegated by the Sprint Manager to manage a specific Cycle.

### Step 1 — Query the Cycle

Use `query-cycle-issues` (from `linear-sprint-ops`) to retrieve all issues in the Cycle with their relations, statuses, and estimates.

### Step 2 — Validate Issue Completeness

For each issue in the Cycle, run `validate-issue-completeness` (from `linear-sprint-ops`). This uses Claude API reasoning to assess whether the issue has sufficient information for the Dev Team to begin work.

**If an issue passes validation:**
- Update its status to "Awaiting Assignment" using `update-issue-status`
- Post a comment confirming the issue is queued for delegation

**If an issue fails validation (Triage loop):**
1. Set the issue status to "Triage" using `update-issue-status`
2. Post a comment on the issue listing the specific gaps and @mentioning the issue's PO (resolve via `resolve-po-for-issue` from `linear-sprint-ops`; Linear Asks surfaces this in Slack)
3. Add the `escalation` label if the gaps are blocking sprint planning
4. The issue is excluded from the dependency graph until the PO resolves it and sets the status back to "Scheduled"

**Important:** Do not block the entire sprint for one incomplete issue. All issues that pass validation proceed to the dependency graph. Triaged issues re-enter the graph when resolved.

### Step 3 — Compute Dependency Graph

Use `compute-dependency-graph` (from `linear-sprint-ops`) on the validated issues.

**Cycle detection:** If the algorithm detects circular dependencies:
1. Post a comment on ALL affected issues describing the cycle and @mentioning each issue's PO (resolve per-issue via `resolve-po-for-issue` — affected issues may belong to different Projects with different Leads)
2. Add the `escalation` label to all affected issues (for Linear-side filtering and triage)
3. STOP — do not delegate any issues in the circular group. Issues outside the cycle can still proceed.

### Step 4 — Set Cycle In Progress

Once the graph is computed and Level 0 issues are identified, set the Cycle status to "In Progress."

### Step 5 — Delegate Level 0 Issues

For each issue at Level 0 (no unresolved blockers), use `delegate-issue` (from `linear-sprint-ops`) to assign it to the component's dedicated Dev Team agent.

**Delegation rules:**
- Delegate ALL Level 0 issues simultaneously — they can be worked in parallel
- The Dev Team agent manages multi-issue concurrency internally (up to 2-3 issues in flight at different stages)
- Post a comment on each delegated issue noting: which blockers were resolved (if any), and what the Dev Team's first action should be (begin Planning, produce an Implementation Plan)

### Step 6 — Post Sprint Kickoff Summary

Post a Linear project update on the Cycle summarizing the sprint (Linear Asks surfaces this in the team's Slack channel):

```markdown
**SCRUM Master — Sprint Kickoff**

Cycle "{cycle_name}" ({start_date} – {end_date}) is now In Progress.

**Delegated to Dev Team (Level 0):**
- {ISSUE_ID} — {title} ({estimate} pts)
- {ISSUE_ID} — {title} ({estimate} pts)

**Waiting on Dependencies (Level 1+):**
- {ISSUE_ID} — blocked by {blocker_ids}

**Sent to Triage:**
- {ISSUE_ID} — {gap_summary}

Total: {count} issues | {total_points} points

---
_Agent: {component}-scrum-master | Timestamp: {ISO 8601}_
```

---

## Flow 2: Ongoing Sprint Management

**Entry:** Issue status change webhook, dispatched via Cloud Tasks.

On every trigger, the SCRUM Master re-queries the current state of the Cycle before taking action. Never rely on cached state — another agent or human may have changed something since the last event.

**Scope:** All Flow 2 handlers operate exclusively on issues within the triggering issue's own Cycle. If the triggering issue is not assigned to any Cycle, skip in-cycle delegation steps — this issue's impact on other Cycles is handled by the Sprint Manager when the Cycle completes. Never delegate, comment on, or update the status of issues in a different Cycle. Cross-cycle coordination is the Sprint Manager's responsibility.

### Handler: Testing Complete

**Trigger:** An issue's status changes to "Testing Complete."

"Testing Complete" does NOT resolve dependencies for next-wave delegation. Only "Done" unblocks downstream issues. This ensures the PO verifies the integrated result of each wave before the next wave begins.

1. Re-query the Cycle using `query-cycle-issues`
2. Re-compute the dependency graph using `compute-dependency-graph`
3. Identify the completed issue's execution level (wave) in the graph
4. Check if ALL issues at the same execution level are now "Testing Complete," "Done," or "Cancelled":
   - If yes → run the **Wave Completion and Integration** sub-flow (see below)
   - If no → post a comment listing remaining issues in the wave still in progress
5. Do NOT delegate next-wave issues — delegation only happens when the "Done" handler fires (after PO merges the wave's PR)

### Handler: Resolving Test Issues

**Trigger:** An issue's status changes to "Resolving Test Issues."

1. Re-query the Cycle using `query-cycle-issues`
2. Re-compute the dependency graph
3. Mark the issue as UNRESOLVED — it is no longer in a terminal state
4. If the issue's wave had previously reached completion (all issues were "Testing Complete"), the wave is now incomplete again. Post a comment noting the wave completion is revoked and the integration branch (if created) is stale.
5. Post a comment on the affected issue acknowledging the status change and noting that the Dev Team will be re-engaged when testing resumes

### Handler: Done

**Trigger:** An issue's status changes to "Done" (set by Product Owner after merging the wave's integration PR).

**Scope:** This handler operates ONLY on issues within the triggering issue's own Cycle. If the triggering issue has no Cycle, skip steps 2-6 and proceed directly to step 7. If the dependency graph reveals that this Done event unblocks issues in a DIFFERENT Cycle, do NOT delegate or comment on those cross-cycle issues — the Sprint Manager handles cross-cycle delegation when the Cycle completes.

1. **Close the issue's draft PR** if it is still open. The wave PR (integration PR or the single-issue draft PR) has already merged these changes into `main`, so any remaining individual draft PRs are stale. Close with a comment: "Closed — changes merged via wave PR."
2. Re-query the Cycle (the triggering issue's own Cycle) using `query-cycle-issues`
3. Re-compute the dependency graph using `compute-dependency-graph` — include ONLY issues that belong to this Cycle
4. Identify any Level N+1 issues **within this Cycle** that are now fully unblocked (all their blockers are "Done" or "Cancelled")
5. Delegate newly unblocked issues **within this Cycle** to the Dev Team agent using `delegate-issue`
6. Post a comment on each newly delegated issue noting which blocker just cleared
7. Check if all issues **in this Cycle** are now "Done" or "Cancelled":
   - If yes → run the **Cycle Completion** sub-flow (see below)
   - If no → log the status change, no further action needed

### Handler: PO Rejection (Testing Complete → In Progress)

**Trigger:** An issue's status changes from "Testing Complete" to "In Progress" (PO rejected the work during integration branch review and added a comment with feedback).

1. Re-query the Cycle using `query-cycle-issues`
2. Re-compute the dependency graph
3. Mark the issue as UNRESOLVED — it is no longer in a terminal state
4. The wave is now incomplete. Post a comment noting the wave's integration branch is stale and a new one will be needed after the issue is reworked and re-tested.
5. The status change to "In Progress" will trigger the Dev Team agent to read the PO's feedback and begin Flow 4 (PO Rejection) of the dev-team-workflow
6. Post a comment on the issue acknowledging the PO rejection and noting the Dev Team will re-engage

### Handler: Returned from Triage

**Trigger:** An issue's status changes to "Scheduled" after being in "Triage."

1. Re-query the Cycle using `query-cycle-issues`
2. Re-compute the dependency graph with the returned issue included
3. Validate the issue again using `validate-issue-completeness`:
   - If it still fails → send it back to Triage (repeat the Triage loop from Sprint Planning Step 2)
   - If it passes → set status to "Awaiting Assignment"
4. Check if all the issue's blockers are resolved:
   - If yes → delegate immediately to the Dev Team agent
   - If no → the issue waits in the graph until its blockers clear

### Handler: New Issue Added to Cycle

**Trigger:** A new issue is added to the Cycle mid-sprint.

1. Validate the new issue using `validate-issue-completeness`
2. Re-compute the dependency graph with the new issue included
3. If the issue has no unresolved blockers and passes validation → delegate to Dev Team
4. Post a comment noting the mid-sprint addition and any impact on the dependency graph

---

## Flow 3: Stalled-Issue Triage

**Entry:** Dispatched by the webhook receiver's `/check-stalled-in-review` endpoint, which runs every 15 minutes via Cloud Scheduler. The endpoint pre-filters Linear for issues in `In Review` status with no activity for more than 30 minutes and groups the candidates by team. One SCRUM Master VM is dispatched per affected team, with the candidate-issue identifiers embedded in the EVENT line. Most ticks of the scheduler find nothing and dispatch no VMs at all — if you are running, at least one issue in your team's component is stalled.

**Why this flow exists.** The Dev Team's Flow 2 ends with the issue in `Ready for Testing` (the canonical terminal state). The most common Flow 2 failure mode is the agent setting `In Review` instead — Linear returns `success: true` for any valid state mutation, so the wrong destination is invisible to the agent's own exit handler, the Dev Team VM self-deletes, and `In Review` is not in the webhook routing table. Without this flow, the issue stalls silently until a human notices. The Dev Team SKILL has a Step 7c self-check that should catch this before the agent exits, but Flow 3 is the defense-in-depth layer for the case where the self-check itself is bypassed (skill-prompt drift, model variance, infra error mid-mutation).

**Scope.** Only the candidate issues listed in the EVENT line. Do NOT scan the rest of the cycle. Do NOT re-compute the dependency graph. This is a narrow triage pass, not a rebuild of cycle state.

### Step 1 — Read each candidate

For each issue identifier in the EVENT line, query Linear:

```graphql
query {
  issue(id: "<identifier>") {
    id identifier title state { name } updatedAt
    comments(filter: { resolved: { eq: false } }, orderBy: createdAt) {
      nodes { id body createdAt user { name } }
    }
    history(first: 10, orderBy: createdAt) {
      nodes { createdAt fromState { name } toState { name } }
    }
    attachments { nodes { url title } }
  }
}
```

Two checks before deciding to escalate:

- **Status sanity check.** If `state.name != "In Review"` (e.g., the issue was just promoted by a human in the seconds before this VM started), skip the issue. Log "skipped — status no longer In Review" and move on.
- **Activity sanity check.** If the most recent unresolved comment was created less than 30 minutes ago, skip the issue. The Cloud Function pre-filter uses `updatedAt`, but a human comment posted right before dispatch can race the filter.

### Step 2 — Classify each remaining candidate

Use Haiku-grade reasoning over the comments and history. Place each candidate into exactly one bucket:

- **Bucket A — Likely Dev Team Flow 2 terminal-state failure (the AH-4 pattern).** Indicators:
  - The most recent unresolved comment is a Test Instructions comment (matches the schema in `dev-team-workflow/SKILL.md` §7a — "Test Instructions" header, "Branch & Build Setup", "Test Cases", "Acceptance Criteria Mapping").
  - The issue has an attached PR (open, not merged).
  - The history shows a recent transition into `In Review` from `In Progress` and no transition out.
  - This is the highest-priority case — the Dev Team's work is done, the PR is healthy, and a one-step status promotion would unblock the Test Team.

- **Bucket B — Mid-Flow-2 stall (no Test Instructions yet).** Indicators:
  - The issue is in `In Review` but no Test Instructions comment exists.
  - The PR may or may not exist.
  - The Dev Team session likely died during the Step 6 review-and-verify loop or while writing Test Instructions.

- **Bucket C — Active rework (false positive).** Indicators:
  - The most recent unresolved comment is from the PO (rejection feedback) or a Test Failure Report from the Test Team.
  - The history shows the issue ping-ponging between `In Review` and `Resolving Test Issues` or `In Progress`.
  - The Dev Team is working through Flow 3 (test-failure resolution) or Flow 4 (PO rejection) and the `In Review` is a normal mid-cycle state.
  - **Action: skip with no escalation.** The pre-filter's 30-min window can over-report during long fix loops; do not waste PO attention on these.

If the evidence is genuinely ambiguous, default to Bucket B (escalate). Over-escalation costs one Linear notification; under-escalation leaves a real silent failure unhandled.

### Step 3 — Act per bucket

For each candidate, apply the action prescribed by its bucket. Do NOT auto-promote any issue's state — promotion is the PO's call, not the SCRUM Master's. (The Dev Team's intent is recoverable from comments, but a false read would silently dispatch the Test Team against a non-ready PR, which is worse than a one-step manual fix.)

**Bucket A:**
1. Apply the `escalation` and `po-action` labels using `apply-po-action-label` (from `linear-sprint-ops` operation 9) and the equivalent for `escalation`.
2. Resolve the issue's PO via `resolve-po-for-issue` and post the **Bucket A escalation comment** (see template below) — diagnostic, names the Dev Team Flow 2 terminal-state failure mode explicitly, and tells the PO the recommended one-step fix.

**Bucket B:**
1. Apply the `escalation` and `po-action` labels.
2. Post the **Bucket B escalation comment** — describes the stall, asks the PO to investigate Dev Team session output (or re-trigger the Dev Team via assignee change).

**Bucket C:**
1. Skip silently. Log the skip decision with the matched indicators so the next Flow 3 run can audit prior decisions if needed.
2. Do NOT post a comment. Do NOT apply labels. Repeated benign comments on an actively-iterating issue add noise.

### Step 4 — Post a single Flow 3 summary

After processing every candidate, post one project update on the team's most recent active Cycle (or skip if no active Cycle) summarizing what Flow 3 did this run:

```markdown
**SCRUM Master — Stalled-Issue Triage**

Flow 3 ran at {ISO 8601}. Examined {N} candidate(s) flagged by the In-Review watchdog.

| Issue | Bucket | Action |
|-------|--------|--------|
| {ID-1} | A (Dev Team terminal-state failure) | Escalated to PO |
| {ID-2} | C (active rework) | Skipped (false positive) |

---
_Agent: {component}-scrum-master | Flow: Stalled-Issue Triage | Timestamp: {ISO 8601}_
```

If every candidate was Bucket C (no escalations posted), still post the summary — the audit trail matters more than the noise floor.

### Comment Templates

**Bucket A escalation comment:**

```markdown
**SCRUM Master — Stalled In Review (likely Dev Team terminal-state failure)**

@{primary_po} — Issue {issue_id} has been in `In Review` for {elapsed_minutes} minutes. Test Instructions were posted at {test_instructions_timestamp}, which strongly suggests the Dev Team finished Flow 2 successfully but set the issue to `In Review` instead of `Ready for Testing` before exiting.

**Recommended action:**
1. Verify the attached PR is healthy (CI green, mergeable).
2. If yes, set this issue to `Ready for Testing` — the Test Team will pick it up automatically.
3. If the PR is not healthy, set the issue back to `In Progress` with a feedback comment instead.

Do NOT auto-promote — confirming PR health first is the safety check this watchdog cannot perform.

Reference: this is the failure mode covered by `dev-team-workflow/SKILL.md` §7c "Final State Verification". If you see this pattern recurring, raise it as a skill-level bug.

---
_Agent: {component}-scrum-master | Flow: Stalled-Issue Triage | Bucket: A | Timestamp: {ISO 8601}_
```

**Bucket B escalation comment:**

```markdown
**SCRUM Master — Stalled In Review (Dev Team session may have died mid-flow)**

@{primary_po} — Issue {issue_id} has been in `In Review` for {elapsed_minutes} minutes with no Test Instructions posted. The Dev Team session likely terminated during the Step 6 review-and-verify loop or before writing Test Instructions.

**Recommended action:**
1. Check Cloud Logging for the most recent Dev Team VM for this issue (filter on `agent-dev-team-{issue_id_lower}` in `gs://fun-e-business-agent-sessions/dev-team/`).
2. If the session crashed mid-flow, re-trigger the Dev Team by re-assigning the issue to the Dev Team user, OR move the issue to `In Progress` — both will dispatch a fresh session.
3. If the session completed but appears to have skipped writing Test Instructions, treat as a Dev Team SKILL bug and raise it.

---
_Agent: {component}-scrum-master | Flow: Stalled-Issue Triage | Bucket: B | Timestamp: {ISO 8601}_
```

The PO Resolution Rule (see "Notification Standards" below) applies — `is_same == true` means @mention `{primary_po}` once, not twice.

---

## Sub-flow: Wave Completion and Integration

**Trigger:** All issues at an execution level (wave) are "Testing Complete," "Done," or "Cancelled."

The SCRUM Master creates or promotes the wave's PR, verifies the build, and notifies the PO. The approach depends on how many issues are in the wave.

### Idempotency check — do this first

Before doing any work, verify that no other SCRUM Master run has already handled this wave:

```bash
gh pr list --state open --search 'in:title "integration: Cycle {C} Wave {N}"' --json number,headRefName
```

If the query returns **any** matching PR, another SCRUM Master instance has already created the wave integration PR (or is in the process of creating it). **Exit cleanly** — do not re-run the sub-flow, do not create another branch, do not push, do not post any Linear comments or project updates. Log the dedup decision and stop.

Two SCRUM Master VMs can run concurrently when the triggering webhook is duplicated (Linear delivery retry, rapid state-flip events, overlapping "Testing Complete" transitions on sibling issues). Without this guard, both runs race to create an integration PR and can arrive at *different* conflict resolutions for the same merge — a correctness hazard, not just a duplicate-PR annoyance.

### Gather wave context

1. Determine the wave number from the execution level in the dependency graph
2. Collect all draft PR numbers and branch names for "Testing Complete" issues in the wave
3. For each "Testing Complete" issue:
   - Read the Test Results from the issue's comments
   - Record: issue identifier, title, PR number, branch name, test pass rate, any flagged concerns
4. Build a **wave status summary** for all waves in the Cycle:
   - For each execution level: list its issues and their current status (Done, Testing Complete, in progress, etc.)
   - This summary is included in every notification so the PO always knows where things stand

### Single-issue wave (1 "Testing Complete" issue)

5. The existing draft PR already contains all the changes — no integration branch needed.
6. Mark the draft PR as ready for review: `gh pr ready {PR_NUMBER}`
7. Run verification by checking out the branch and running the frontend/backend test commands named in the component PRD (or the repo's CLAUDE.md §Common Commands):
   - Typical pattern: `git checkout {branch} && cd <frontend-path> && <install> && <test> && <build>`
   - Typical backend (when applicable): `cd <backend-path> && <install> && <test>`
   - **If verification fails:** apply the `po-action` label to the issue using `apply-po-action-label` (from `linear-sprint-ops` operation 9), post a comment with error output @mentioning the issue's PO (resolve via `resolve-po-for-issue`), and **stop**.
8. Skip to the **Notify** section below.

### Multi-issue wave (2+ "Testing Complete" issues)

5. Ensure the local repo is on `main` and up to date: `git checkout main && git pull`
6. Create the integration branch: `git checkout -b integration/cycle-{C}-wave-{N}`. **If the branch already exists on origin** (`git push` in step 9 will later fail with `error: src refspec ... matches more than one` or similar, or `git checkout -b` itself fails locally if you cloned fresh), another SCRUM Master run already created it. Exit cleanly. **Do NOT fall back to a suffixed branch name like `-v2`** — that produces a duplicate integration PR with potentially divergent conflict resolution. The idempotency check at the top of the sub-flow should have caught this case earlier; this is defense in depth.
7. For each "Testing Complete" issue's branch, in dependency order:
   - `git merge origin/{branch} --no-edit`
   - If merge succeeds cleanly: continue to next branch
   - If conflict is limited to a package-manager lockfile (e.g., `package-lock.json`, `poetry.lock`, `uv.lock`): accept either side, run the repo's install command to regenerate the lockfile, then `git add <lockfile> && git commit --no-edit`
   - If conflict is in other files: attempt resolution (the changes are typically independent — keep both sides). If successful, stage and commit.
   - **If conflict cannot be resolved:** abort the merge (`git merge --abort`), apply the `po-action` label to all conflicting issues using `apply-po-action-label` (from `linear-sprint-ops` operation 9), post a comment on each conflicting issue @mentioning that issue's PO (resolve per-issue via `resolve-po-for-issue`) describing the conflict, and **stop**. Do not proceed with remaining merges or PR creation.
8. Run verification using the build/test commands named in the component PRD (or the repo's CLAUDE.md §Common Commands):
   - Typical frontend pattern: `cd <frontend-path> && <install> && <test> && <build>`
   - Typical backend (when applicable): `cd <backend-path> && <install> && <test>`
   - **If verification fails:** apply the `po-action` label to all wave issues using `apply-po-action-label` (from `linear-sprint-ops` operation 9), post a comment on each wave issue with error output @mentioning that issue's PO (resolve per-issue via `resolve-po-for-issue`), and **stop**. Do not push or create a PR.
9. Push the integration branch: `git push -u origin integration/cycle-{C}-wave-{N}`
10. Create the integration PR via `gh pr create` with:
    - Title: `integration: Cycle {C} Wave {N} ({issue identifiers})`
    - Body containing:
      - Summary listing all wave issues, their PR numbers, and test results
      - Conflict resolution notes (if any)
      - Verification results (test count, build output)
      - PO testing checklist (one item per issue: what to verify)
      - Post-merge steps (deploy startup.sh if modified, set issues to "Done")
      - `closes #{PR1}, closes #{PR2}, ...` references to auto-close individual draft PRs on merge

### Notify

11. **Apply `po-action` label** to all "Testing Complete" issues in the wave using `apply-po-action-label` (from `linear-sprint-ops` operation 9). This surfaces them in the PO's action queue view.
12. Post a Wave Completion summary as a Linear project update on the Cycle, including:
    - Wave number and all issue identifiers with titles
    - Link to the PR for PO review (either the single draft PR or the integration PR)
    - Test pass rates and flagged concerns
    - The wave status summary (from step 4) so the PO sees the full Cycle picture
    - Action: "PO: review the PR, test locally, merge, then set all wave issues to Done in Linear."
13. Post a comment on each "Testing Complete" issue in the wave linking to the PR and noting PO review is needed
14. Do NOT delegate next-wave issues — the PO must merge the PR and set these issues to "Done" first

---

## Sub-flow: Cycle Review Notification

**Trigger:** All issues in the Cycle have reached "Testing Complete," "Done," or "Cancelled."

This is an informational summary posted when the entire Cycle reaches a terminal state. Individual wave reviews happen via the **Wave Completion Notification** above.

1. Use `draft-cycle-review-notification` (from `linear-sprint-ops`) to generate a summary of the full Cycle status
2. For each issue, include: identifier, title, current status, test pass rate
3. Post the formatted summary as a Linear project update on the Cycle (Linear Asks surfaces this in the team's Slack channel)

---

## Sub-flow: Cycle Completion

**Trigger:** All issues in the Cycle are "Done" or "Cancelled."

1. Verify pre-conditions:
   - No issues in "Testing Complete" (PO must merge the wave's integration PR and set to "Done" first)
   - No issues in any active status ("In Progress," "In Review," "Testing," etc.)
2. Post a Cycle summary comment listing:
   - All completed issues with their final status
   - Total estimate points delivered
   - Any issues that were cancelled and why
3. Set the Cycle status to "Complete" using `update-cycle-status`
4. This triggers the Sprint Manager to re-evaluate the cross-component dependency graph and potentially kick off the next Cycle

---

## Sub-flow: Update Component Dashboard

**Trigger:** Invoked at the end of every handler in Flow 1 and Flow 2 (Sprint Planning, Testing Complete, Done, Resolving Test Issues, Returned from Triage, Wave Completion, PO Rejection, Cycle Completion). This ensures the dashboard is always current.

This sub-flow maintains a living Linear Document that gives the PO a single-page view of the component's status, action queue, and dependency chain.

### Step 1 — Look Up or Create the Document

1. Use `lookup-dashboard-document` (from `linear-sprint-ops` operation 10) to find a document in the component's Project with title prefix `"PO Dashboard"`
2. If not found, create one using `create-dashboard-document` (operation 11) with title `"PO Dashboard — {Component Name}"`

### Step 2 — Query Current State

1. Re-query the Cycle using `query-cycle-issues` (already done by the parent handler — reuse the data)
2. Re-compute the dependency graph (already done — reuse)
3. For each wave (execution level), determine its status:
   - **Done** — all issues "Done" or "Cancelled"
   - **Testing Complete — PR ready** — all issues "Testing Complete"/"Done"/"Cancelled" and wave PR exists
   - **In Progress** — at least one issue actively being worked
   - **Blocked** — all issues waiting on upstream wave to reach "Done"

### Step 3 — Build Action Queue

Scan all issues in the Cycle for states requiring PO action:
- Status = "Awaiting Review" → "Approve Implementation Plan"
- Status = "Triage" → "Fill missing fields"
- Status = "Testing Complete" (and wave is complete) → "Merge PR + set Done"
- Has `escalation` label → "Resolve escalation"

For each item, compute elapsed time (business hours since `updatedAt`) and dependency impact (what gets unblocked).

### Step 4 — Build Dependency Chain

Render a text-based dependency chain showing all waves and the PO actions needed to advance:

```
Wave 0 (Done)
  → Wave 1 (Testing Complete — PR #47 ready)
    → [PO: merge PR #47, set FUN-12 + FUN-13 to Done]
      → Wave 2 (Blocked — 2 issues waiting)
```

### Step 5 — Write the Document

Use `update-dashboard-document` (operation 12) to rewrite the full document:

```markdown
# PO Dashboard — {Component Name}
_Last updated: {ISO 8601}_

## Action Queue
Items requiring your attention, ordered by priority:

1. **{ISSUE_ID}** — {action needed} ({status}, {elapsed time} pending)
   _Impact: {what gets unblocked}_
2. ...

_No items requiring action._ ← (if queue is empty)

## Active Cycle: {Cycle Name} ({start_date} — {end_date})

| Wave | Issues | Status |
|------|--------|--------|
| Wave 0 | {IDs} | {status summary} |
| Wave 1 | {IDs} | {status summary} |
| ... | ... | ... |

Progress: {done}/{total} Done | {testing_complete} Testing Complete | {in_progress} In Progress | {blocked} Blocked

## Dependency Chain
{dependency chain from Step 4}

## Previous Cycles
- {Cycle Name} — Complete ({date})
```

**Error handling:** If the document write fails (rate limit, permission), log the error and continue — dashboard updates are informational and must not block the primary handler's workflow.

---

## SLA Enforcement

The SCRUM Master is responsible for tracking human checkpoint response times and escalating when SLA targets are at risk.

### Response Time Targets

| Activity | SLA (Business Hours) | Reminder | Escalation |
|----------|---------------------|----------|------------|
| Plan Approval | 4 hours | Comment @mentioning issue's PO at 2 hours | Add `escalation` label + comment @mentioning PO and backup PO at 4 hours |
| Wave Review (integration branch testing) | 8 hours | Comment @mentioning issue's PO at 4 hours | Add `escalation` label + comment @mentioning PO and backup PO at 8 hours |
| Unblocking Request | 2 hours | Comment @mentioning issue's PO at 1 hour | Add `escalation` label + comment @mentioning PO and backup PO at 2 hours |

PO handles are resolved per-issue via `resolve-po-for-issue` from `linear-sprint-ops`. When `is_same == true` (the PO resolves to the workspace fallback, `ken`), the escalation comment @mentions the user only once — see the escalation template below.

**Business hours** are defined per Product Owner (configurable). SLA clocks pause outside business hours. For overnight requests, the clock starts at 9:00 AM the next business day.

### SLA Tracking Process

1. When an issue enters a state that requires human input (plan posted, PR opened, question asked), record the timestamp
2. Compute elapsed business hours since the checkpoint
3. At the reminder threshold → resolve the PO via `resolve-po-for-issue` and post a comment @mentioning `{primary_po}` (Linear Asks surfaces in Slack)
4. At the escalation threshold → add the `escalation` label AND the `po-action` label (using `apply-po-action-label` from `linear-sprint-ops` operation 9), then post the SLA escalation comment (see template below) — the resolver's `is_same` flag determines whether to @mention both the PO and backup PO or just the PO

### Product Owner Resolution

The PO for every issue-level @mention is the Linear Project Lead on the issue's Project. The backup PO is always `ken` (the workspace-level fallback, hardcoded in `resolve-po-for-issue`). If the issue has no Project, or the Project has no Lead, the PO defaults to `ken` — meaning the PO and backup PO are the same user. In that case, the dedup rule applies: @mention `ken` once, never twice in the same comment.

Use `resolve-po-for-issue` (operation 13 in `linear-sprint-ops`) for every issue-level comment. Use `resolve-pos-for-cycle` (operation 14) for cycle-level notifications (Sprint Kickoff, Cycle Review) — these @mention each distinct Project Lead in the cycle without appending the workspace fallback.

---

## Minimizing Idle Time

Even when human checkpoints are pending, the SCRUM Master actively minimizes pipeline idle time:

### Parallel Work Delegation

When a Dev agent is waiting on plan approval for Issue A, the SCRUM Master checks if another unblocked issue (Issue B) in the dependency graph can be started. If so, it delegates Issue B to the same Dev agent, which works on it in a separate branch. A single Dev agent can manage 2-3 issues in flight simultaneously, each at different stages (one waiting on approval, one in implementation, one in review).

### Daily Sprint Summary

The SCRUM Master posts a daily summary as a Linear project update on the Cycle (Linear Asks surfaces this in the team's Slack channel):
- Issues currently in progress (with current status and assignee)
- Issues waiting on human input (with elapsed wait time)
- Issues queued for next delegation (blocked by dependencies)
- Issues in Triage (awaiting PO resolution)
- Overall Cycle progress (X of Y issues complete)

---

## Notification Standards

All notifications are routed through Linear. The **Linear Asks** Slack integration surfaces issue comments and project updates in the linked Slack channels automatically. Agents do not post to Slack directly. See `tools/secrets-and-auth` for channel mapping details.

### Notification Mechanisms

| Notification Type | Linear Mechanism | Slack Surfacing |
|-------------------|-----------------|-----------------|
| Issue-level (plan approval, triage, test results) | Comment on the issue @mentioning the issue's PO (resolved via `resolve-po-for-issue`) | Linear Asks → team channel |
| Escalation | Comment @mentioning primary + backup (deduped if same) + `escalation` label | Linear personal notification (Slack DM) + label for Linear-side filtering |
| Sprint-level (kickoff, daily summary, cycle review) | Project update on the Cycle @mentioning each distinct Project Lead (resolved via `resolve-pos-for-cycle`) | Linear Asks → team channel |

### PO Resolution Rule

Every @mention of a Product Owner must be resolved at post time, not statically templated:

- **Issue-level comments:** call `resolve-po-for-issue(issue_id)` from `linear-sprint-ops` to get `{primary_po, backup_po, is_same}`. Substitute the `{primary_po}` and `{backup_po}` placeholders in the templates below with these values.
- **Cycle-level comments / project updates:** call `resolve-pos-for-cycle(cycle_id)` to get the deduplicated list of Project Leads across cycle issues. @mention each; do not append the workspace fallback.
- **Dedup rule for two-PO templates** (SLA escalation, stale agent escalation): if `is_same == true`, omit the `@{backup_po}` line entirely — do not @mention the same user twice in a single comment.

### Comment Templates

All agent comments must follow the standard structure defined in `linear-sprint-ops` operation 6 (`post-comment`). Key requirements:

1. **@mention the PO** when action is needed — resolve handles per the PO Resolution Rule above (Linear Asks translates to Slack @mention)
2. **Include the action needed** (approve plan / resolve gaps / review Test Results)
3. **Include SLA context** when applicable (time remaining or time overdue)
4. **Use the `escalation` label** for urgent items (enables Linear-side filtering; @mentions handle direct notification)

**SLA reminder comment:**
```markdown
**SCRUM Master — Action Needed**

@{primary_po} — Plan approval is pending for this issue.
SLA: {remaining_time} remaining ({deadline}).

Please review the Implementation Plan above and set status to "In Progress" (approve) or "Planning" (request changes).

---
_Agent: {component}-scrum-master | Timestamp: {ISO 8601}_
```

**SLA escalation comment:**

When `is_same == false` (primary lead is not `ken`):
```markdown
**SCRUM Master — Escalation**

Plan approval is overdue. @{primary_po} has not responded within the {sla_hours}-hour SLA.
@{backup_po} — please assist.

---
_Agent: {component}-scrum-master | Status: escalated | Timestamp: {ISO 8601}_
```

When `is_same == true` (primary lead IS the workspace fallback `ken`):
```markdown
**SCRUM Master — Escalation**

Plan approval is overdue. @{primary_po} has not responded within the {sla_hours}-hour SLA.

---
_Agent: {component}-scrum-master | Status: escalated | Timestamp: {ISO 8601}_
```

---

## Error Handling

### Circular Dependencies

If `compute-dependency-graph` detects cycles:
1. Post a comment on ALL affected issues listing the circular chain (e.g., "FUN-4 → FUN-6 → FUN-8 → FUN-4") and @mentioning each issue's PO (resolve per-issue via `resolve-po-for-issue` — affected issues may belong to different Projects with different Leads)
2. Add the `escalation` label AND the `po-action` label (using `apply-po-action-label` from `linear-sprint-ops` operation 9) to all affected issues
3. Do NOT delegate any issues in the circular group
4. Issues outside the cycle proceed normally
5. When the PO breaks the cycle (by removing or reversing a relation), the next status change event triggers a re-computation of the graph

### Stale Agent Sessions

If a Dev Team agent appears unresponsive (delegated issue has not progressed from "Planning" status within a configurable timeout, default 2 hours):
1. Post a comment on the issue noting the stale session
2. Add the `escalation` label and the `po-action` label (using `apply-po-action-label` from `linear-sprint-ops` operation 9) to the issue
3. Attempt re-delegation to the same Dev Team agent (creates a new session)
4. If re-delegation also stalls → resolve the PO via `resolve-po-for-issue` and post an escalation comment @mentioning `{primary_po}` and, if `is_same == false`, `{backup_po}` as well (Linear sends them a direct notification)

### Test Failure Re-entry

When an issue returns from "Resolving Test Issues" → "Ready for Testing":
- The SCRUM Master does NOT re-delegate to the Dev Team (the Dev Team already fixed the issue and pushed it back)
- The issue proceeds through the testing pipeline normally
- The SCRUM Master monitors for the next "Testing Complete" or "Resolving Test Issues" status change

### Webhook Replay / Duplicate Events

Before performing any action, verify the issue is not already in the target state. If the issue has already been processed (e.g., it's already delegated, or it's already in the expected status), skip gracefully and log. Do not treat duplicate events as errors.

---

## Implementation Notes

### Pure Code vs. Claude API

Most SCRUM Master operations are pure code (API calls, graph computation, status routing). Claude API is only used when LLM reasoning is needed:

| Operation | Implementation |
|-----------|---------------|
| Compute intra-sprint dependency graph | Pure code (topological sort) |
| Delegate issues to Dev agent | Pure code (Linear API mutation) |
| Post notifications (via Linear comments/updates) | Pure code (Linear API) |
| Enforce SLA timers and escalation | Pure code (track timestamps, send reminders) |
| Route incoming status changes | Pure code (switch on status value) |
| Check if all issues in Cycle reached target status | Pure code (query + compare) |
| Set Cycle status to "Complete" | Pure code (Linear API mutation) |
| **Validate issue completeness** | **Claude API** (reason about AC quality, design ref sufficiency) |
| **Resolve ambiguous blocking relationships** | **Claude API** (reason about ambiguity, draft question for PO) |
| **Create daily sprint summary** | **Claude API** (summarize progress in natural language) |
| **Draft Cycle-end review notification** | **Claude API** (summarize Test Results for PO review) |

### State Management

The SCRUM Master is stateless. On every trigger:
1. Re-query the Cycle from Linear (source of truth)
2. Re-compute the dependency graph from current data
3. Determine the appropriate action based on current state
4. Execute the action

This design means the SCRUM Master can recover from any failure by simply re-processing the event. There is no local state to corrupt or lose.

### Configuration

The following values are loaded from environment variables or a configuration file at startup:

| Config Key | Description | Example |
|------------|-------------|---------|
| `COMPONENT_NAME` | The component this SCRUM Master manages | `fun-e` |
| `TEAM_ID` | Linear Team ID for the component | `abc123` |
| `DEV_AGENT_USER_ID` | Linear user ID of the Dev Team agent | `def456` |
| `BUSINESS_HOURS_START` | Start of PO business hours (local time) | `09:00` |
| `BUSINESS_HOURS_END` | End of PO business hours (local time) | `17:00` |
| `BUSINESS_HOURS_TZ` | PO timezone | `America/New_York` |
| `STALE_SESSION_TIMEOUT_MINUTES` | Minutes before flagging a stale Dev session | `120` |
