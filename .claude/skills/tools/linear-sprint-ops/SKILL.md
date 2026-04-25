# Tool SKILL: Linear Sprint Ops

## Purpose

This SKILL defines the common operations that SCRUM Master and Sprint Manager agents perform against the Linear API. It is loaded alongside the agent's workflow SKILL and provides reusable procedures for querying issues, computing dependency graphs, managing issue lifecycle, and communicating with the Product Owner.

## Authentication

Each agent has a dedicated Linear Personal API key injected as `LINEAR_ACCESS_TOKEN`. See `tools/secrets-and-auth` for provisioning details (GCP Secret Manager, token rotation, CSRF headers).

```typescript
import { LinearClient } from '@linear/sdk';
const client = new LinearClient({ accessToken: process.env.LINEAR_ACCESS_TOKEN });
```

**Note:** When using direct GraphQL calls instead of the SDK, include the `apollo-require-preflight: true` header (see `secrets-and-auth` for details).

## Operations

### 1. query-cycle-issues

Retrieve all issues in a Cycle with their relations, status, estimates, and parent linkage.

**When to use:** At sprint planning time, when re-evaluating the dependency graph, or when checking sprint progress.

**GraphQL query:**
```graphql
query CycleIssuesWithRelations($cycleId: String!) {
  cycle(id: $cycleId) {
    id
    name
    number
    startsAt
    endsAt
    issues {
      nodes {
        id
        identifier
        title
        description
        estimate
        priority
        state { name category }
        assignee { id name }
        parent { id identifier title }
        labels { nodes { name } }
        relations {
          nodes {
            type
            relatedIssue {
              id
              identifier
              title
              state { name category }
            }
          }
        }
        inverseRelations {
          nodes {
            type
            issue {
              id
              identifier
              title
              state { name category }
            }
          }
        }
      }
    }
  }
}
```

**Return:** Full issue list with blocking/blocked-by relations resolved in both directions.

---

### 2. compute-dependency-graph

Build a topological sort from blocking relations to determine execution order with parallelization groups.

**When to use:** After `query-cycle-issues`, at sprint start, and whenever a trigger event requires re-evaluation (see Trigger Table below).

**Algorithm:**

```
Input: Set of issues with their blocking relations (from query-cycle-issues)
Output: Ordered execution plan with parallelization groups

Steps:
1. Build a directed acyclic graph (DAG):
   - Each issue is a node
   - Each "blocks" relation creates a directed edge: blocker → blocked
   - Filter to only "blocks" type relations — ignore "duplicate" and "relatedTo"

2. Detect cycles:
   - Run cycle detection on the DAG
   - If cycles are found, report them and STOP — circular dependencies require
     human intervention. Post a comment on all affected issues and add the
     `escalation` label (for Linear-side filtering) and @mention each affected issue's PO (resolve per-issue via `resolve-po-for-issue`, operation 13).

3. Compute depth levels (topological sort by level):
   - Level 0: Issues with zero incoming edges (no blockers)
   - Level N: Issues whose ALL blockers are at levels 0..N-1
   - Issues at the same level can be executed in parallel

4. Filter by status:
   - Exclude issues already in "Done" or "Cancelled" status
   - Issues in "Testing Complete" are treated as resolved for dependency purposes
     (downstream issues can proceed), but they are NOT "Done" until PO approves
   - Issues in "Resolving Test Issues" are treated as UNRESOLVED — their
     downstream dependencies remain blocked

5. Output format:
   {
     "executionPlan": [
       {
         "level": 0,
         "issues": ["FUN-4", "FUN-5"],
         "note": "No dependencies — ready to delegate"
       },
       {
         "level": 1,
         "issues": ["FUN-6"],
         "note": "Blocked by FUN-4"
       }
     ],
     "cycles": [],
     "unreachable": [],
     "completedIssues": ["FUN-4"]
   }
```

**Trigger table for re-evaluation:**

| Trigger Event | Agent | Action |
|---------------|-------|--------|
| Issue status → "Testing Complete" | SCRUM Master | Mark resolved in graph, delegate next unblocked level |
| Issue status → "Resolving Test Issues" | SCRUM Master | Mark unresolved, pause downstream dependencies |
| Issue status → "Done" | SCRUM Master | Confirm resolved, check if all Cycle issues are Done |
| All issues → "Testing Complete" | SCRUM Master | Notify PO that Cycle is ready for Test Results review |
| All issues → "Done" | SCRUM Master | Set Cycle to "Complete" (triggers Sprint Manager) |
| Cycle status → "Complete" | Sprint Manager | Re-evaluate cross-component graph, delegate next Cycle |
| New issue added to Cycle | SCRUM Master | Re-compute graph with new issue included |

---

### 3. delegate-issue

Assign an issue to the component's Dev Team agent for execution.

**When to use:** When `compute-dependency-graph` identifies issues at the next ready level (all blockers resolved), or when an issue returns from "Resolving Test Issues" to "Ready for Testing."

**Steps:**
1. Verify all blockers for the issue are in "Testing Complete" or "Done" status
2. Set the issue's assignee to the Dev Team agent's user ID
3. Update the issue status to "Awaiting Assignment" (if coming from Scheduled) or the appropriate next status
4. Post a comment on the issue noting the delegation and which blockers were resolved

**GraphQL mutation:**
```graphql
mutation DelegateToAgent($issueId: String!, $agentUserId: String!) {
  issueUpdate(id: $issueId, input: { assigneeId: $agentUserId }) {
    success
    issue {
      id
      identifier
      assignee { name }
    }
  }
}
```

---

### 4. update-issue-status

Change an issue's workflow state.

**When to use:** At every status transition in the agent workflow.

**Steps:**
1. Look up the target state's ID by name (state IDs are team-specific)
2. Update the issue with the new state ID
3. Log the transition

**GraphQL mutation:**
```graphql
mutation UpdateIssueStatus($issueId: String!, $stateId: String!) {
  issueUpdate(id: $issueId, input: { stateId: $stateId }) {
    success
    issue {
      id
      identifier
      state { name }
    }
  }
}
```

**State lookup:** Use the team's workflow states to resolve state name → state ID. Cache this mapping per team since it doesn't change during a sprint.

```graphql
query TeamWorkflowStates($teamId: String!) {
  team(id: $teamId) {
    states {
      nodes {
        id
        name
        type
      }
    }
  }
}
```

**Valid status transitions (enforced by workflow SKILLs):**

| From | To | Triggered By |
|------|----|-------------|
| Scheduled | Awaiting Assignment | SCRUM Master (sprint planning) |
| Awaiting Assignment | Planning | Dev Team (begins work) |
| Planning | Awaiting Review | Dev Team (Implementation Plan ready) |
| Awaiting Review | Planning | PO feedback requires plan revision |
| Awaiting Review | In Progress | PO approves Implementation Plan |
| In Progress | In Review | Dev Team (draft PR created, automated review starting) |
| In Review | Ready for Testing | Dev Team (review + verify pass, Test Instructions posted) |
| Ready for Testing | Testing | Test Team (begins browser testing) |
| Ready for Testing | Resolving Test Issues | Test Team (Test Instructions missing or build fails) |
| Testing | Testing Complete | Test Team (all browser tests pass) |
| Testing | Resolving Test Issues | Test Team (browser test failures found) |
| Resolving Test Issues | In Progress | Dev Team (begins fixing test failures) |
| In Progress | In Review | Dev Team (fixes complete, review loop restarting) |
| Testing Complete | In Progress | PO rejects at Cycle review (feedback comment added) |
| Testing Complete | Done | PO approves at Cycle review → SCRUM Master merges draft PR |
| Triage | Backlog | PO accepts issue |
| Triage | Cancelled | PO rejects issue |
| Backlog | Scheduled | PO assigns to Cycle |

---

### 5. update-cycle-status

Set a Cycle's status to "Complete" or other lifecycle states.

**When to use:** When all issues in a Cycle reach "Done" status (SCRUM Master), or when the Sprint Manager needs to advance the sprint pipeline.

**GraphQL mutation:**
```graphql
mutation CompleteCycle($cycleId: String!) {
  cycleUpdate(id: $cycleId, input: { completedAt: "now" }) {
    success
    cycle {
      id
      name
      completedAt
    }
  }
}
```

**Pre-conditions before completing a Cycle:**
- ALL issues must be in "Done" or "Cancelled" status
- No issues in "Testing Complete" (PO must review and move to Done first)
- Post a Cycle summary comment listing all completed issues and their final status

---

### 6. post-comment

Add a structured comment to an issue for audit trail and agent-to-human communication.

**When to use:** At every significant lifecycle event — delegation, status changes, plan submissions, test results, escalations.

**GraphQL mutation:**
```graphql
mutation PostComment($issueId: String!, $body: String!) {
  commentCreate(input: { issueId: $issueId, body: $body }) {
    success
    comment {
      id
    }
  }
}
```

**Comment formatting standards:**

All agent comments must follow this structure:
```markdown
**[Agent Type] — [Action]**

[Content body]

---
_Agent: [agent name] | Status: [from] → [to] | Timestamp: [ISO 8601]_
```

**PO Action label convention:** When posting a comment that requires PO action (plan approval, triage gaps, wave merge request, escalation), also apply the `po-action` label using `apply-po-action-label` (operation 9). This ensures the issue appears in the PO's action queue view. See operation 9 for details on when agent-applied vs. automation-applied labeling is appropriate.

Example:
```markdown
**SCRUM Master — Issue Delegated**

FUN-4 has been assigned to the Dev Team agent. All blockers are resolved:
- FUN-2 (Testing Complete)
- FUN-3 (Done)

Next step: Dev Team will begin Planning and produce an Implementation Plan.

---
_Agent: scrum-master | Status: Scheduled → Awaiting Assignment | Timestamp: 2026-04-06T10:30:00Z_
```

---

### 7. validate-issue-completeness

Assess whether an issue has sufficient information for the Dev Team to begin work. This operation uses LLM reasoning (Claude API) to evaluate the issue content against the template requirements.

**When to use:** During sprint planning, before delegating an issue to the Dev Team. If validation fails, the SCRUM Master enters the Triage loop.

**Validation criteria:**

For User Stories, check:
- [ ] User Story statement present ("As a... I want... so that...")
- [ ] At least 3 Acceptance Criteria with Given/When/Then structure
- [ ] Context section with 1+ paragraphs of background
- [ ] Implementation Notes with specific file references
- [ ] Design References with at least 1 entry
- [ ] Estimate is set (non-zero)
- [ ] Priority is set

For Features, check:
- [ ] Description with 2+ paragraphs
- [ ] At least 3 Acceptance Criteria
- [ ] Design References with at least 1 entry
- [ ] Has child issues (User Stories) linked

For Bugs, check:
- [ ] Bug Description present
- [ ] Expected Behavior present
- [ ] Steps to Reproduce present (numbered)
- [ ] Actual Result present
- [ ] Impact assessment present

**Output:** Pass/fail with a list of missing or insufficient sections. If the issue fails, the SCRUM Master should:
1. Post a comment on the issue listing the gaps and @mentioning the issue's PO (resolve via `resolve-po-for-issue`, operation 13; Linear sends them a direct notification and the comment also appears in the team Slack channel)
2. Add the `escalation` label if the gaps are blocking sprint planning (for Linear-side filtering)
3. Set the status to "Triage"

---

### 8. draft-cycle-review-notification

Generate a summary of issues that need Product Owner review at Cycle end. Used when all issues in a Cycle reach "Testing Complete" status.

**When to use:** When the SCRUM Master detects that every issue in the Cycle is in "Testing Complete" (or "Done"/"Cancelled").

**Steps:**
1. Query all issues in the Cycle
2. For each issue in "Testing Complete":
   - Read the Test Results document (from issue comments or attachments)
   - Summarize: issue title, test pass rate, any flagged concerns
3. Post a comment on each "Testing Complete" issue with a review reminder (these reach Slack via Linear Asks)
4. Post a Linear project update on the Cycle summarizing all issues ready for review:

Before posting, call `resolve-pos-for-cycle` (operation 14) to get the deduplicated list of Project Leads across the cycle. @mention each distinct lead at the top of the notification. Do NOT append the workspace fallback — for cycle-level notifications, the set of Project Leads IS the audience.

```markdown
**SCRUM Master — Cycle Ready for Review**

All issues in Cycle "{name}" have completed testing. @{primary_pos[0]} @{primary_pos[1]} ... please review Test Results and move approved issues to Done.

| Issue | Tests | Action Needed |
|-------|-------|---------------|
| FUN-4 — Upgrade TailwindCSS | 7/7 pass | Review Test Results → Done |
| FUN-5 — Upgrade React Router | 5/5 pass | Review Test Results → Done |
| FUN-16 — Dark mode bug | 3/3 pass | Review Test Results → Done |

Once all issues are marked Done, the Cycle will be completed automatically.

---
_Agent: {component}-scrum-master | Timestamp: {ISO 8601}_
```

### 9. apply-po-action-label

Apply the `po-action` label to an issue that requires Product Owner action. This label powers the PO's saved Linear View — a persistent, always-current action queue across all components.

**When to use:** When an issue enters a state that requires PO input AND the labeling is conditional or context-dependent. Simple state-based labeling (TO "Awaiting Review", TO "Triage") is handled automatically by the webhook receiver — agents do NOT apply `po-action` at those transitions.

**Agent-applied (conditional — requires context):**

| Trigger | Applied By | Why Agent-Applied |
|---------|-----------|-------------------|
| Wave Completion detected | SCRUM Master | Only when the full wave is complete and the PR is ready — not every "Testing Complete" event |
| SLA escalation | SCRUM Master | Alongside `escalation` label at threshold |
| Integration branch failure | SCRUM Master | Only on failure, not on every integration attempt |
| Circular dependency | SCRUM Master | Applied to all issues in the cycle chain |

**Webhook-applied (state-based — handled by webhook receiver, no agent action needed):**

The webhook receiver (`agents/webhook-receiver/main.py`) automatically manages the `po-action` label on status transitions via the Linear API. This runs synchronously before agent VMs are created.

| Trigger | Action |
|---------|--------|
| Status changes TO "Awaiting Review" | Add `po-action` |
| Status changes TO "Triage" | Add `po-action` |
| Status changes FROM "Awaiting Review" | Remove `po-action` |
| Status changes FROM "Triage" | Remove `po-action` |
| Status changes FROM "Testing Complete" | Remove `po-action` |

**GraphQL mutation:**
```graphql
mutation AddLabelToIssue($issueId: String!, $labelId: String!) {
  issueAddLabel(id: $issueId, labelId: $labelId) {
    success
    issue { id identifier labels { nodes { name } } }
  }
}
```

**Label lookup:** Query the workspace labels to resolve the `po-action` label name to its ID. Cache the result for the session since label IDs don't change.

```graphql
query WorkspaceLabels {
  issueLabels(filter: { name: { eq: "po-action" } }) {
    nodes { id name }
  }
}
```

**Idempotency:** If the issue already has the `po-action` label, the mutation is a no-op. Do not treat this as an error.

---

### 10. lookup-dashboard-document

Find an existing PO Dashboard Document by project ID and title prefix.

**When to use:** At the start of any dashboard update sub-flow. Since agents are stateless, the document must be looked up on every invocation.

**GraphQL query:**
```graphql
query DashboardDocument($projectId: String!) {
  documents(filter: { project: { id: { eq: $projectId } } }) {
    nodes {
      id
      title
      updatedAt
      project { id name }
    }
  }
}
```

**Post-filter:** From the results, find the document whose title starts with `"PO Dashboard"`. There should be at most one per project.

**Return:** The document ID if found, `null` if not found (caller should create a new document using operation 11).

---

### 11. create-dashboard-document

Create a new PO Dashboard Document attached to a Linear Project.

**When to use:** When `lookup-dashboard-document` returns `null` — typically during the first Sprint Planning run or the first Daily Briefing.

**GraphQL mutation:**
```graphql
mutation CreateDashboardDocument($projectId: String!, $title: String!, $content: String!) {
  documentCreate(input: {
    projectId: $projectId,
    title: $title,
    content: $content
  }) {
    success
    document {
      id
      title
    }
  }
}
```

**Naming convention:**
- Component-level: `"PO Dashboard — {Component Name}"` (e.g., "PO Dashboard — Fun-E")
- Platform-level: `"PO Dashboard — KEN-E Platform"`

---

### 12. update-dashboard-document

Rewrite the content of an existing PO Dashboard Document.

**When to use:** At the end of every SCRUM Master handler (component dashboard) or Sprint Manager flow (platform dashboard). The entire document content is replaced — this is a full rewrite, not a patch.

**GraphQL mutation:**
```graphql
mutation UpdateDashboardDocument($documentId: String!, $content: String!) {
  documentUpdate(id: $documentId, input: { content: $content }) {
    success
    document {
      id
      title
      updatedAt
    }
  }
}
```

**Content templates:** See the SCRUM Master SKILL's "Update Component Dashboard" sub-flow and the Sprint Manager SKILL's "Update Platform Dashboard" sub-flow for the full document templates.

**Idempotency:** Updating a document with the same content is harmless. Do not skip updates based on content comparison — always rewrite to ensure the timestamp is current.

---

### 13. resolve-po-for-issue

Resolve the Linear usernames to @mention for a single issue's Product Owner notifications.

**When to use:** Before any agent posts a comment that @mentions the PO on a specific issue (plan approval reminder, SLA escalation, triage gap notification, integration failure, circular dependency, stale agent session, etc.). Use `resolve-pos-for-cycle` instead for cycle-wide notifications.

**Rules:**
- **PO** = the `displayName` of the Lead on the issue's Project.
- **Backup PO** = always `ken` (hardcoded workspace-level fallback).
- **Fallback** = if the issue has no Project, or the Project has no Lead, the PO falls back to `ken` (same as the backup).
- **De-duplication** = if the PO and backup PO resolve to the same handle, callers @mention once and omit any "please assist" / "cc backup" lines.

**GraphQL query:**
```graphql
query PoForIssue($id: String!) {
  issue(id: $id) {
    id
    identifier
    project {
      id
      name
      lead { id displayName }
    }
  }
}
```

> `displayName` is Linear's @mention handle (unique per workspace), not the full name field `name`; if the workspace sets a spaced display name, @mention will not resolve.

**Resolution logic:**
```
FALLBACK = "ken"

lead = issue.project?.lead?.displayName
primary_po = lead if lead else FALLBACK
backup_po = FALLBACK
is_same = (primary_po == backup_po)

if issue.project AND NOT lead:
    log.warning("Issue {identifier} is in project '{project.name}' but the project has no Lead set — defaulting to fallback PO")
```

**Return:**
```
{
  "primary_po": "<linear-username>",
  "backup_po": "ken",
  "is_same": <boolean>
}
```

**Usage in comment templates:**
- Single-PO @mentions (reminders, triage, integration failures, circular dependencies): use `@{primary_po}` only.
- Two-PO @mentions (SLA escalation, stale agent escalation): if `is_same`, emit only the `@{primary_po}` line; otherwise emit both `@{primary_po}` and `@{backup_po}` on their respective lines.

---

### 14. resolve-pos-for-cycle

Resolve the deduplicated set of Linear usernames to @mention for cycle-level notifications that span multiple issues across potentially multiple projects.

**When to use:** When posting a cycle-wide notification (Sprint Kickoff, Cycle Review, cross-component escalation on a Cycle). Use `resolve-po-for-issue` for single-issue comments.

**Rules:**
- Query every issue in the cycle and collect each issue's PO (per `resolve-po-for-issue`).
- Return the deduplicated set in insertion order.
- Do NOT automatically append the workspace fallback (`ken`) for cycle-level notifications — unlike issue-level escalation, cycle notifications only @mention the distinct Project Leads that own work in the cycle.
- If every issue falls back (no leads set anywhere), the result is `["ken"]`.

**GraphQL query:**
```graphql
query PosForCycle($cycleId: String!) {
  cycle(id: $cycleId) {
    issues {
      nodes {
        id
        identifier
        project {
          id
          lead { id displayName }
        }
      }
    }
  }
}
```

**Resolution logic:**
```
FALLBACK = "ken"
handles = []

for issue in cycle.issues:
    lead = issue.project?.lead?.displayName
    handles.append(lead if lead else FALLBACK)

return deduplicate(handles)  # preserves first-occurrence order
```

**Return:**
```
{
  "primary_pos": ["<linear-username>", ...]
}
```

**Usage in comment templates:**
- Emit `@{primary_pos[0]} @{primary_pos[1]} ...` at the top of cycle-level notifications.
- Do NOT add a separate backup / cc line — for cycle-level notifications, the set of Project Leads IS the audience.

---

### 15. resolve-pm

Resolve the Linear username to @mention for Project Completion Review notifications and PM SLA escalations.

**When to use:** Before any agent posts a comment that @mentions the PM (Project Completion hand-off, PM SLA reminder/escalation). Unlike the PO, the PM is a platform-wide role, not scoped per Project.

**Rules:**
- **PM** = always `ken` (hardcoded constant — the PM role is a single designated user at the platform level, not stored in any Linear workspace attribute).
- **No backup** — unlike the PO flow, there is no distinct backup PM. If the PM is unresponsive, the `escalation` label surfaces the Project in the standard Linear views and the @mention re-pings the PM.

No GraphQL query is required — the value is a compile-time constant.

**Resolution logic:**
```
PM = "ken"

return {"pm": PM}
```

**Return:**
```
{
  "pm": "ken"
}
```

**Usage in comment templates:**
- Emit `@{pm}` at the top of Project Completion Review hand-off comments and PM SLA escalations.

---

## Error Handling

All Linear API calls must handle these error cases:

- **Rate limiting (429):** Back off exponentially. Linear allows 1,500 requests per hour per OAuth token. If approaching the limit, batch queries where possible.
- **Not found (404):** The issue/cycle may have been deleted or the agent may not have access. Log and skip — do not retry.
- **Stale state:** Always re-query the issue's current status before performing a transition. Another agent or human may have changed the status since the last read.
- **Webhook replay:** If an operation was already performed (e.g., issue is already in the target status), skip gracefully and log. Do not treat as an error.
