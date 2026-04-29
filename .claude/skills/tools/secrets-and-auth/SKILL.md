# Tool SKILL: Secrets & Auth

## Purpose

This SKILL documents how agent credentials are provisioned, stored, and injected into the runtime environment. All agents reference this SKILL for authentication setup — individual tool SKILLs (like `linear-sprint-ops`) document API *usage*, while this SKILL documents how the credentials *arrive*.

## Secret Storage: GCP Secret Manager

All secrets are stored in GCP Secret Manager within the `fun-e-business` project. Secrets are injected into agent runtimes as environment variables — agents never access Secret Manager directly at runtime.

### Injection by Runtime Type

| Runtime | Injection Method |
|---------|-----------------|
| Cloud Run (SCRUM Master, Sprint Manager) | Secret Manager → Cloud Run secret environment variables (configured in Terraform) |
| GCE Instance (Dev Team) | Secret Manager → instance metadata or startup script injection |
| Mac Mini (Test Team) | Secret Manager → pulled at session start via `gcloud secrets versions access` |

### Secret Naming Convention

All secrets follow the pattern: `{service}-token-{agent-name}`

| Secret Name | Agent | Service |
|-------------|-------|---------|
| `linear-token-dev-team` | Dev Team | Linear API |
| `linear-token-test-team` | Test Team | Linear API |
| `linear-token-scrum-master` | SCRUM Master | Linear API |
| `linear-token-sprint-manager` | Sprint Manager | Linear API |

These secrets are shared across all KEN-E components. The `dev-team`, `test-team`, and `scrum-master` Linear accounts are platform-level workspace members — every component's agent VM pulls the same bare-named secret at startup, and component context is injected via VM instance metadata (see `agents/startup.sh`). No new Linear members or secrets are created per component.

## Linear Authentication

### Token Type: Personal API Keys

Each agent has a dedicated Linear workspace member account with its own Personal API key. This approach was chosen over OAuth2 because:

- Linear's OAuth2 requires an authorization code flow (browser-based user consent), which doesn't work for headless agents
- Personal API keys don't expire, eliminating token refresh complexity
- Each agent needs its own Linear identity anyway (for issue assignment attribution and comment authorship)

### Agent Linear Accounts

| Linear Member Name | Purpose | Environment Variable |
|--------------------|---------|---------------------|
| `dev-team` | Assigned to issues during development, posts Implementation Plans and Test Instructions | `LINEAR_ACCESS_TOKEN` |
| `test-team` | Posts Test Results and failure reports | `LINEAR_ACCESS_TOKEN` |
| `scrum-master` | Manages sprint lifecycle, delegates issues, posts status updates | `LINEAR_ACCESS_TOKEN` |
| `sprint-manager` | Cross-component Cycle coordination | `LINEAR_ACCESS_TOKEN` |

All agents receive their token as `LINEAR_ACCESS_TOKEN`. The token value differs per agent — each agent's runtime environment is configured with its own secret.

### API Permissions

Linear Personal API keys have full workspace access scoped to the member's role. All agent accounts are configured as **Member** role, which provides:

- Read/write access to issues, comments, Cycles, and projects within their Team(s)
- Read access to other Teams (needed for cross-component dependency queries)
- Cannot modify workspace settings, billing, or member roles

### Token Rotation

Personal API keys do not expire, but should be rotated:

- **On compromise** — immediately revoke and regenerate
- **On agent decommission** — revoke the key and remove the Linear member
- **Periodically** — recommended quarterly rotation as a hygiene practice

Rotation procedure:
1. Generate a new Personal API key for the agent's Linear account
2. Update the secret in GCP Secret Manager: `gcloud secrets versions add {secret-name} --data-file=-`
3. Redeploy the agent's runtime to pick up the new secret version (Cloud Run redeploy, GCE restart, or Mac Mini session restart)
4. Verify the agent can authenticate by checking its next Linear API call succeeds
5. Revoke the old key in Linear (Settings → API → revoke)

### CSRF Header Requirement

Linear's GraphQL API requires a CSRF prevention header on all requests. When using direct HTTP calls (not the `@linear/sdk` client, which handles this automatically), include:

```
apollo-require-preflight: true
```

This header must be present alongside `Content-Type: application/json` and the `Authorization` header.

## Slack Notifications: Via Linear's Slack Integration

Agents do **not** have direct Slack API access. Notifications reach Slack through two mechanisms:

### Mechanism 1: Team Channel Notifications

Each Linear team is connected to a Slack channel via Linear's Slack integration (Settings → Integrations → Slack). When enabled, Linear forwards issue activity to the linked channel.

**Configuration per team:**
- Enable **"Comments to issues"** — agent comments appear in the team channel
- Enable **"New project update is posted"** — sprint summaries and cycle reviews appear

| Linear Team | Linked Slack Channel | Enabled Notifications |
|-------------|---------------------|----------------------|
| [FUN] FUN-E | Fun-E team channel | Comments to issues, New project update |

### Mechanism 2: Direct Notifications via @mentions

When an agent @mentions a user in a Linear comment, Linear sends that user a personal notification. If the user has Slack notifications enabled in their Linear settings (Settings → Notifications → Slack), this arrives as a Slack DM.

This is the primary mechanism for **escalations** and **PO action requests**. The `escalation` label is a visual filter in Linear's UI (for triaging escalated issues) but does not drive Slack channel routing.

### Implications for Agent Design

- Agents do not need `SLACK_CHANNEL_ID`, `ESCALATION_CHANNEL_ID`, or any Slack-specific config keys
- To send a notification, agents post a comment on the relevant Linear issue — the team Slack channel receives it automatically
- To escalate, agents add the `escalation` label (for Linear-side filtering) and @mention the PO/backup PO in the comment (Linear sends them a direct notification)
- To resolve which PO to @mention on an issue-level comment, agents call `resolve-po-for-issue` (operation 13 in `linear-sprint-ops`). The PO is the Linear Project Lead on the issue's Project; the backup PO is always `ken` (workspace-level fallback). For cycle-level notifications, `resolve-pos-for-cycle` (operation 14) returns the deduplicated set of Project Leads. For Project Completion Review @mentions, `resolve-pm` (operation 15) returns the PM — a hardcoded constant (`ken`) rather than a Linear workspace attribute.
- For non-issue notifications (daily summaries, Cycle delegation reports), agents post a Linear project update on the relevant Cycle or Project

### Failure Behavior

If a Linear comment fails to post (API error, rate limit), the agent must **block the workflow** and retry. Notifications are not fire-and-forget — they are part of the audit trail and the PO's review process. If retries exhaust (3 attempts with exponential backoff), the agent should log the failure and halt, leaving the issue in its current status for manual investigation.

## Onboarding a New Component

The `dev-team`, `test-team`, and `scrum-master` Linear accounts and their secrets are shared across all components — no new Linear members or secrets are created per component. When onboarding a new component to the KEN-E platform:

1. Add the new component's Linear Team ID to the Sprint Manager's `TEAM_IDS` config map
2. Configure the component's agent VM template with the `component` instance metadata attribute (see `agents/startup.sh`) so the agent knows which component context to load
3. In Linear's Slack integration, connect the new Team to its Slack channel and enable "Comments to issues" and "New project update is posted"
