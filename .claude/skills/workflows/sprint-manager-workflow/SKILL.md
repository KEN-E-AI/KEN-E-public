# Workflow SKILL: Sprint Manager

## Purpose

This SKILL defines the cross-component coordination workflow for the Sprint Manager agent. There is exactly one Sprint Manager for the entire KEN-E platform. It monitors Cycle completion events across all Teams, computes the cross-component dependency graph, determines which Cycles are ready to start, and delegates to the appropriate SCRUM Master agents.

**Runtime:** Cloud Run service with Anthropic SDK for LLM reasoning. Stateless — the cross-component dependency graph is recomputed on each trigger from Linear's current data.

**Companion SKILLs loaded alongside this one:**
- `tools/linear-sprint-ops` — shared Linear API operations (GraphQL queries, mutations, graph algorithm)
- `tools/secrets-and-auth` — credential provisioning and authentication details

## Triggers

| Source | Event | Action |
|--------|-------|--------|
| Cycle status → "Complete" | Cycle webhook (via Cloud Tasks) | Re-evaluate cross-component graph, delegate next ready Cycles |
| Manual invocation | Initial kickoff or recovery | Full evaluation of all Teams' Cycle readiness |
| Cloud Scheduler (9 AM ET, weekdays) | `/daily-summary` endpoint | Post PO daily briefing with health indicator, update Platform Dashboard |

---

## Flow 1: Cycle Completion Cascade

**Entry:** A SCRUM Master has set a Cycle to "Complete" (all issues in the Cycle are "Done" or "Cancelled").

### Step 1 — Query All Pending Cycles

Query all Teams for Cycles with status "Planned" or "Upcoming." These are the Cycles that are candidates for delegation.

**Cycle dates are informational, not gates.** The `startsAt` field on a Cycle is a planning estimate set by the PO — the Sprint Manager ignores it when evaluating readiness. A Cycle is ready to start when its cross-component blockers are resolved, regardless of its scheduled start date. This prevents unnecessary idle time between Cycles. (Linear's API does not support programmatic date updates, so the PO may adjust dates manually in the UI for reporting accuracy.)

```graphql
# Query all teams, then for each team query cycles with planned/upcoming status
# Use the query-cycle-issues operation from linear-sprint-ops for each candidate Cycle
```

### Step 2 — Query Cross-Cycle Blocking Relations

For issues in the candidate Cycles, query ALL blocking relations where the blocking issue is in a **different Cycle** than the blocked issue. This includes both cross-team AND intra-team cross-cycle dependencies.

**Important:** The Sprint Manager operates at the Cycle level, not the individual issue level. A Cycle is considered "blocked" if ANY issue in that Cycle is blocked by an issue in another Cycle that has not yet reached "Testing Complete" or "Done." This applies regardless of whether the blocking issue is in the same team or a different team.

### Step 3 — Compute Cross-Cycle Dependency Graph

Use the same topological sort algorithm from `compute-dependency-graph` (in `linear-sprint-ops`), but applied at the Cycle level:

- **Nodes:** Cycles (not individual issues)
- **Edges:** A Cycle A blocks Cycle B if any issue in Cycle A blocks any issue in Cycle B (regardless of team)
- **Resolved:** A blocking Cycle is considered resolved if it has status "Complete" or if the specific blocking issues within it are in "Testing Complete" or "Done"

**Output:** Ordered list of Cycles that are now ready (all cross-cycle blockers resolved).

**Cycle detection:** If circular dependencies exist between Cycles across Teams:
1. Post a comment on all affected issues involved in the cross-team cycle, @mentioning each issue's PO (resolve per-issue via `resolve-po-for-issue` from `linear-sprint-ops` — issues may belong to different Projects across different components)
2. Add the `escalation` label to all affected issues (for Linear-side filtering and triage)
3. Post a Linear project update describing the circular dependency chain, @mentioning each distinct Project Lead across the affected Cycles (resolve via `resolve-pos-for-cycle` for each Cycle, then deduplicate)
4. Do NOT delegate any Cycles in the circular group — human intervention required

### Step 4 — Delegate Ready Cycles

For each Cycle that is ready (all cross-component blockers resolved):

1. Identify the component's SCRUM Master agent
2. Pick a delegation target issue in the Cycle (prefer the first issue by identifier)
3. Delegate to the SCRUM Master using the **two-step assignment pattern** to guarantee a webhook fires:
   a. **Clear the assignee** on the target issue: call `issueUpdate` with `assigneeId: null`. This is necessary because the issue may already be assigned to the SCRUM Master from a prior sprint planning session. Linear only fires a webhook when the assignee value actually changes.
   b. **Wait 2 seconds** to ensure Linear processes the unassignment before the reassignment.
   c. **Assign the SCRUM Master** agent's user ID to the issue. This fires the `assigneeId` change webhook, which the webhook receiver routes to create a new SCRUM Master VM with "Execute Flow 1: Sprint Planning."
4. Post a comment on the delegated issue noting the delegation:
   ```markdown
   **Sprint Manager — Cycle Delegated**

   Cycle "{cycle_name}" has been delegated to the SCRUM Master.
   All cross-component blockers are resolved:
   - {blocker_cycle_1} (Complete)
   - {blocker_cycle_2} (Complete)

   SCRUM Master will begin Sprint Planning.

   ---
   _Agent: sprint-manager | Timestamp: {ISO 8601}_
   ```

**Important:** Always use the two-step assignment pattern (clear then set) for delegation. Never assume the issue is unassigned — a previous SCRUM Master session may have already been assigned to the issue during sprint planning validation.

### Step 5 — Post Delegation Summary

Post a Linear project update summarizing the delegation (Linear Asks surfaces this in Slack):

```markdown
**Sprint Manager — Cycle Delegation**

Triggered by: {completed_cycle_name} ({component}) marked Complete.

**Newly delegated Cycles:**
- {cycle_name_1} ({component_1}) — SCRUM Master notified
- {cycle_name_2} ({component_2}) — SCRUM Master notified

**Still blocked:**
- {cycle_name_3} ({component_3}) — waiting on {blocker_description}

No action needed — SCRUM Masters will begin Sprint Planning.

---
_Agent: sprint-manager | Timestamp: {ISO 8601}_
```

### Step 6 — Update Platform Dashboard Document

Execute the **Update Platform Dashboard** sub-flow to rewrite the living dashboard document with current cross-component state.

### Step 7 — Update Activity Log

Log the delegation event in the Sprint Manager's AgentSession activity log for audit purposes. Include: trigger event, Cycles evaluated, Cycles delegated, Cycles still blocked, and timestamp.

---

## Flow 2: Initial Kickoff

**Entry:** Manual invocation at system startup or after recovery from an outage.

This flow performs the same steps as Flow 1, but without being triggered by a specific Cycle completion. It evaluates ALL Teams' Cycles from scratch to ensure the system is in a consistent state.

### Steps

1. Query all Teams
2. For each Team, query all Cycles with status "Planned," "Upcoming," or "In Progress"
3. Verify that "In Progress" Cycles have an active SCRUM Master session — if not, re-delegate using the **two-step assignment pattern** from Step 4 of Flow 1 (clear the assignee, wait 2 seconds, then assign the SCRUM Master agent)
4. For "Planned" and "Upcoming" Cycles, run the full cross-component dependency evaluation (Steps 2-5 from Flow 1)
5. Post a system status summary as a Linear project update (Linear Asks surfaces in Slack):

```markdown
**Sprint Manager — System Status**

**Active Sprints:**
- {component_1}: Cycle "{name}" — In Progress ({X}/{Y} issues complete)
- {component_2}: Cycle "{name}" — In Progress ({X}/{Y} issues complete)

**Ready to Start:**
- {component_3}: Cycle "{name}" — Delegating to SCRUM Master
- {component_4}: Cycle "{name}" — Delegating to SCRUM Master

**Blocked:**
- {component_5}: Cycle "{name}" — Waiting on {blocker}

**No Active Cycles:**
- {component_6}, {component_7} — No planned Cycles

---
_Agent: sprint-manager | Timestamp: {ISO 8601}_
```

6. Execute the **Update Platform Dashboard** sub-flow to rewrite the living dashboard document with current cross-component state.

---

## Flow 3: Daily Briefing

**Entry:** Scheduled trigger via Cloud Scheduler → `/daily-summary` endpoint (9 AM ET, weekdays).

This flow produces a comprehensive PO briefing across all components, posted as a project status update with a health indicator on the platform-level Project. It also updates the Platform Dashboard Document (see Sub-flow: Update Platform Dashboard below).

### Step 1 — Query All Active Cycles

Query all Teams and their Cycles with status "In Progress," "Planned," or "Upcoming."

For each "In Progress" Cycle:
1. Use `query-cycle-issues` (from `linear-sprint-ops`) to retrieve all issues with statuses, relations, and timestamps
2. Compute the dependency graph to determine wave assignments
3. Identify the current wave (the lowest wave that has issues not yet "Done")

### Step 2 — Build PO Action Queue

Scan all issues across all Cycles for states that require PO input:

| Issue Status | Action Type | Priority |
|--------------|------------|----------|
| Awaiting Review | Approve Implementation Plan | High — blocks dev work |
| Triage | Fill missing fields | High — blocks sprint planning |
| Testing Complete (wave complete) | Merge PR + set Done | Critical — blocks next wave |
| Has `escalation` label | Resolve escalation | Critical — SLA breached |

For each action item, compute:
- **Elapsed time:** business hours since the issue entered the current state (using the issue's `updatedAt` timestamp and the PO's business hours config)
- **Dependency impact:** what gets unblocked when the PO acts (downstream issues, next wave, downstream Cycles)

Sort the action queue by: escalations first, then by elapsed time descending (oldest first).

### Step 3 — Compute Health Indicator

Evaluate overall platform health for the project status update:

- **`onTrack`** — No PO action items pending > 2 business hours, no escalations, no issues in Triage
- **`atRisk`** — Any PO action item pending > 2 business hours, OR any issue in Triage, OR any SLA reminder sent in the last 24 hours
- **`offTrack`** — Any active escalation (issue has `escalation` label and is not resolved), OR any integration branch failure, OR any circular dependency

Use the worst health across all components as the platform health.

### Step 4 — Post Daily Briefing Project Update

Post a project status update on the platform-level Project (`PROJECT_ID`) with the computed health indicator. Use the `save_status_update` operation with the `health` field set to `onTrack`, `atRisk`, or `offTrack`.

```markdown
**Sprint Manager — Daily Briefing**
_{date}_

**Health: {onTrack/atRisk/offTrack}**

## PO Action Queue ({count} items)
{if count > 0:}
1. **{ISSUE_ID}** ({component}) — {action type} — {elapsed_time} pending
   _Unblocks: {dependency impact}_
2. ...
{else:}
_No items requiring PO action._

## Component Summary
| Component | Cycle | Current Wave | Done | In Progress | Testing | Blocked |
|-----------|-------|-------------|------|-------------|---------|---------|
| {component} | {cycle_name} | Wave {N} | {done}/{total} | {in_progress} | {testing} | {blocked} |
| ... | ... | ... | ... | ... | ... | ... |

## Cross-Component Dependencies
{if any cross-cycle blockers:}
- {Cycle A} ({component_A}) blocks {Cycle B} ({component_B}) — {status of blocking issues}
{else:}
_No cross-component blockers._

## SLA Status
{if any SLA warnings:}
- **{ISSUE_ID}** ({component}) — {activity} SLA at {percentage}% ({time_remaining} remaining)
{else:}
_All SLA timers within thresholds._

---
_Agent: sprint-manager | Timestamp: {ISO 8601}_
```

### Step 5 — Update Platform Dashboard Document

Execute the **Update Platform Dashboard** sub-flow (see below) to rewrite the living dashboard document with current state.

---

## Cross-Cycle Dependency Rules

### What Constitutes a Cross-Cycle Blocker

A cross-cycle dependency exists when:
- Issue A has a "blocks" relation to Issue B
- Issue A and Issue B are in **different Cycles** (regardless of whether they are in the same team or different teams)
- Issue A's Cycle has not yet been completed

**Critical:** This includes intra-team cross-cycle dependencies. For example, if FUN-4 (Cycle 1) blocks FUN-8 (Cycle 2) and both are in the same team, Cycle 2 is still blocked by Cycle 1. The Sprint Manager must check ALL blocking relations, not just cross-team ones.

### Resolution Criteria

A cross-cycle blocker is considered resolved when:
- The blocking issue is in "Testing Complete" or "Done" status, OR
- The blocking Cycle has been marked "Complete"

### Sprint Completion Cascades

When a Cycle completes, it may unblock multiple downstream Cycles (within the same team or across teams). The Sprint Manager handles this by:
1. Processing all newly unblocked Cycles in a single evaluation pass
2. Delegating all ready Cycles simultaneously (they can be started in parallel)
3. Including all delegations in a single summary notification

---

## Sub-flow: Update Platform Dashboard

**Trigger:** Invoked at the end of Flow 1 (Cycle Completion Cascade), Flow 2 (Initial Kickoff), and Flow 3 (Daily Briefing). This ensures the platform-level dashboard is current after every Sprint Manager action.

This sub-flow maintains a living Linear Document attached to the platform-level Project (`PROJECT_ID`) that gives the PO a cross-component view of all active work, the consolidated action queue, and cross-component dependency status.

### Step 1 — Look Up or Create the Document

1. Use `lookup-dashboard-document` (from `linear-sprint-ops` operation 10) to find a document in the platform Project with title prefix `"PO Dashboard"`
2. If not found, create one using `create-dashboard-document` (operation 11) with title `"PO Dashboard — KEN-E Platform"`

### Step 2 — Query All Components

For each Team in `TEAM_IDS`:
1. Query active Cycles (status "In Progress") using `query-cycle-issues`
2. Compute the intra-cycle dependency graph to determine wave assignments
3. Determine the current wave and overall progress
4. Compute per-component health (same rules as Flow 3 Step 3)

### Step 3 — Build Cross-Component Action Queue

Aggregate PO action items from all components:
- Awaiting Review → "Approve Implementation Plan"
- Triage → "Fill missing fields"
- Testing Complete (wave complete) → "Merge PR + set Done"
- Escalation → "Resolve escalation"

Sort by: escalations first, then elapsed time descending.

### Step 4 — Write the Document

Use `update-dashboard-document` (operation 12) to rewrite the full document:

```markdown
# PO Dashboard — KEN-E Platform
_Last updated: {ISO 8601}_

## Action Queue (All Components)
1. **{ISSUE_ID}** ({component}) — {action needed} ({elapsed time} pending)
   _Impact: {what gets unblocked}_
2. ...

_No items requiring action._ ← (if queue is empty)

## Component Status

### {Component Name}
Cycle: {cycle_name} ({start_date} — {end_date}) | Health: {onTrack/atRisk/offTrack}

| Wave | Issues | Status |
|------|--------|--------|
| Wave 0 | {IDs} | {status} |
| Wave 1 | {IDs} | {status} |

Progress: {done}/{total} Done | Current wave: {N}
Next PO action: {description or "None — agents working"}

### {Next Component}
...

## Cross-Component Dependencies
{if any cross-cycle blockers:}
- {Cycle A} ({component_A}) blocks {Cycle B} ({component_B}) — {blocker status}
{else:}
_No cross-component blockers._

## Blocked Cycles
{if any:}
- {Cycle Name} ({component}) — waiting on {blocker description}
{else:}
_No blocked Cycles._
```

**Error handling:** If the document write fails, log the error and continue. Dashboard updates must not block the primary flow.

---

## Implementation Notes

### Pure Code vs. Claude API

Almost all Sprint Manager operations are pure code. Claude API is only used for ambiguous situations:

| Operation | Implementation |
|-----------|---------------|
| Query Linear for Cycle statuses | Pure code (GraphQL client) |
| Compute cross-component dependency graph | Pure code (topological sort algorithm) |
| Detect circular dependencies | Pure code (cycle detection in DAG) |
| Determine which Cycles are ready | Pure code (check all blockers resolved) |
| Delegate to SCRUM Master | Pure code (Linear API mutation) |
| Post notifications (via Linear comments/updates) | Pure code (Linear API) |
| **Handle ambiguous cross-component dependency** | **Claude API** (reason about the ambiguity, draft a message for Product Owners) |
| **Generate daily briefing** | **Claude API** (summarize cross-component status, compute dependency impact descriptions) |
| Update Platform Dashboard Document | Pure code (Linear API) + **Claude API** (generate dependency chain narrative) |

### State Management

The Sprint Manager is stateless. On every trigger:
1. Re-query all Teams and Cycles from Linear (source of truth)
2. Re-compute the cross-component dependency graph from current data
3. Determine the appropriate action
4. Execute

This design means the Sprint Manager can recover from any failure by simply re-processing the event or running the initial kickoff flow.

### Configuration

| Config Key | Description | Example |
|------------|-------------|---------|
| `SCRUM_MASTER_AGENT_IDS` | Map of component name → SCRUM Master Linear user ID | `{"fun-e": "abc123", ...}` |
| `TEAM_IDS` | Map of component name → Linear Team ID | `{"fun-e": "def456", ...}` |
| `PROJECT_ID` | Linear Project ID for cross-component updates | `proj_123` |

### Error Handling

- **Rate limiting:** The Sprint Manager queries multiple Teams and Cycles. Batch queries where possible and respect Linear's 1,500 requests/hour limit.
- **Stale Cycle data:** Always re-query before acting. A Cycle's status may have changed between the webhook event and the handler execution.
- **Partial delegation failure:** If delegation succeeds for some Cycles but fails for others, log the failure, post an escalation comment on each affected issue @mentioning that issue's PO (resolve per-issue via `resolve-po-for-issue` from `linear-sprint-ops`) with the `escalation` label, and retry the failed delegations on the next trigger.
- **Duplicate events:** Check if the Cycle is already "In Progress" or has an active SCRUM Master session before delegating. Skip gracefully if already handled.
