# Notifications — Component Implementation Plan

> **Status:** Design — not yet broken into project PRDs
> **Last Updated:** 2026-04-20
> **Proposed component prefix:** `N-PRD-NN`
> **Proposed Linear team:** [TBD] Notifications
> **Release bucket:** Pre-GA hardening (must ship before the first production customer)

## 1. Overview

The Notifications component is KEN-E's **dependable, multi-channel delivery system** for events users care about — a task is ready for review, an automation completed, a data-pipeline run failed, a platform credential expired. It exists because the current implementation is partial (Email and Slack channels are stubs; the frontend never receives real-time updates; business events in Project Tasks and Data Pipeline do not emit notifications at all), and because the product roadmap cannot move into production with a customer-facing control loop that silently drops events. The rebuild replaces the current `notifications/*` flat global collection with a Shape B layout, an event-driven trigger contract, a durable delivery queue, and per-channel adapters for UI, Email, Slack, and Microsoft Teams.

Architecturally, the component owns three things: an **event contract** that every other component emits against (`NotificationEvent`), a **router** that resolves each event into one or more `Notification` records with a recipient set and preferred channel list, and a **dispatcher** that fans out to channel adapters with retry and dead-letter semantics. Users interact with the component in two places — a preferences page where they toggle each category against each channel, and an automation subscription control inline in the automation configuration page for opting into notifications from a specific automation instance. All other surfaces (in-app sidebar, bell icon, channel messages) are rendered from the same `Notification` records.

A developer reading only this section should understand: this component owns the event → notification → channel delivery pipeline and nothing about the business events themselves. Project Tasks, Data Pipeline, Automations, and the Agentic Harness emit `NotificationEvent`s at well-defined lifecycle points; this component converts those events into delivered messages while respecting per-user preferences and per-account scope. It does **not** own business logic (what counts as "task ready"), it does **not** own authentication (it reuses `accounts/{account_id}/users` membership for account-scoped fan-out), and it does **not** own the Slack or Teams app identities (they are registered as first-class platform OAuth apps alongside the existing integrations).

## 2. Current state & why rebuild

The existing system under `api/src/kene_api/services/notification_service_v2.py`, `routers/notifications_v2.py`, and `frontend/src/components/notifications/` ships:

- A working CRUD pipeline for in-app notifications stored at `notifications/{id}` (flat, not Shape B) with per-user status at `users/{user_id}/notification_statuses/{id}`.
- A preferences model with 7 categories and 3 channels (UI/EMAIL/SLACK) persisted at `users/{user_id}/preferences`.
- A frontend sidebar (`NotificationSidebar`) and preferences page (`NotificationPreferences`) that talk to those endpoints.
- A separate alert-manager in `app/adk/agents/strategy_agent/alert_manager.py` for token-usage warnings, with its own FIRESTORE/EMAIL/WEBHOOK code path independent of the user-facing service.

What is broken or missing:

| Gap | Impact |
|-----|--------|
| **Email channel is a stub** (`alert_manager._send_email_alert` line 535; no SendGrid template integration in `notification_service_v2` at all) | Email preferences in the UI do nothing. |
| **Slack channel is a declared enum value with no implementation** | Same — UI lets users click but nothing sends. |
| **No Microsoft Teams channel** | Enterprise buyers expect Teams parity with Slack. |
| **No business-event emitters** — `TaskOrchestrator`, `DataPipelineDispatcher`, `AutomationRunEngine` do not call any notification creation path on task/run completion | The most valuable notification moments in the product never fire. The "gap for data-pipeline design" flagged in that component's §5 open questions is a direct symptom of this. |
| **No real-time sync** — the sidebar refetches on open; Firestore listeners are not wired | Users must open the sidebar to see new items; unread counts stale. |
| **Flat collection (`notifications/{id}`)** violates the Shape B convention used elsewhere | Account-deletion sweeps (DM-PRD-05's `recursive_delete`) do not cover notifications; cross-account queries require `account_id` filtering on every call. |
| **No durable delivery queue** — delivery happens inline on the request thread | A SendGrid or Slack outage blocks the triggering write; failures are lost. |
| **No per-automation subscription** | Users cannot opt into notifications for one specific automation without receiving all automations in that category. |

The rebuild is additive at the UI level (the existing sidebar and preferences page are reused with data-model migration), but it is a full replacement for the service, repository, and delivery layers. Existing in-flight notifications migrate via a one-shot backfill job during the first deployment of `N-PRD-01`.

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Event sources                                                                │
│    TaskOrchestrator (PR-PRD-04)   DataPipelineDispatcher (DP-PRD-03)          │
│    AutomationRunEngine (A-PRD-02)   Specialist re-auth (AH-PRD-03)            │
│    AlertManager (token usage)   Invitation flow (existing)                    │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │ emit_event(NotificationEvent)
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  NotificationRouter (API, sync)                                               │
│    1. Resolve event.category + event.subject → template                      │
│    2. Resolve recipients:                                                    │
│         audience=account → list users with access to account_id              │
│         audience=user    → the single user                                   │
│         plus explicit subscribers (per-automation, per-project)              │
│    3. For each (recipient, channel) where preferences allow:                 │
│         enqueue NotificationDelivery(recipient, channel, notification_id)    │
│    4. Write one Notification record (Firestore, Shape B) for audit + UI      │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │ Cloud Tasks queue
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  NotificationDispatcher (Cloud Run service, async workers)                    │
│    Channel adapters:                                                         │
│      UIChannel         → Firestore write only (picked up by listener)        │
│      EmailChannel      → SendGrid dynamic template                           │
│      SlackChannel      → chat.postMessage to user's DM or configured channel │
│      TeamsChannel      → Graph API chatMessage to user's 1:1 chat            │
│    Each adapter: retry (exp backoff), surface errors to DLQ, write receipt   │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │ delivery receipts
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Per-delivery records + UI render                                             │
│    accounts/{account_id}/notifications/{id}               (base record)      │
│    accounts/{account_id}/notifications/{id}/deliveries/*  (per-channel)      │
│    users/{user_id}/notification_statuses/{id}             (per-user status)  │
│    Frontend: NotificationSidebar + bell count via Firestore snapshot()       │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Key abstractions (proposed)

| Abstraction | Purpose |
|-------------|---------|
| `NotificationEvent` (Pydantic) | Event contract emitted by every source. Fields: `event_type`, `account_id`, `subject_user_id?`, `category`, `payload: dict`, `dedupe_key?`, `emitted_at`, `source_component`. Opaque to the component emitting it — payload schema is per `event_type`. |
| `Notification` (Pydantic + Firestore) | Canonical record — `notification_id`, `account_id`, `category`, `audience: Literal["account", "user"]`, `user_id?` (when audience=user), `subject` / `body` / `cta_url`, `data: dict`, `source_event_type`, `created_at`, `archived_at?`. |
| `NotificationDelivery` (Pydantic + Firestore subcollection) | Per-channel delivery receipt — `recipient_user_id`, `channel`, `status: queued/sending/delivered/failed/skipped`, `attempts`, `last_error?`, `delivered_at?`, `provider_message_id?`. One per recipient × channel. |
| `NotificationSubscription` | Explicit subscriber records for per-automation opt-in — `user_id`, `scope: Literal["automation", "project"]`, `scope_id` (plan_id), `account_id`, `categories: list[NotificationCategory]?` (null = all categories from this source). |
| `UserNotificationPreferences` | Rebuild of the existing model — `{category: {channel: bool}}` matrix + `defaults` override for new categories. Persisted at `users/{user_id}/notification_preferences`. |
| `NotificationTemplate` | Per `event_type` definition — title template, body template, CTA URL builder, default category, default channel set. Registered in code (not Firestore) so that a failing import is a deploy-time error. |
| `NotificationChannelAdapter` (Protocol) | Interface each channel implements: `async def deliver(notification, recipient, delivery_id) -> DeliveryOutcome`. `UIChannelAdapter`, `EmailChannelAdapter`, `SlackChannelAdapter`, `TeamsChannelAdapter`. |
| `NotificationRouter` | Event → recipients → channels → queue. Synchronous; returns quickly so callers are never blocked on delivery. |
| `NotificationDispatcher` | Cloud Tasks worker that pulls from the queue, calls the channel adapter, writes the delivery record, retries or DLQs. |

### 3.2 Data model

```python
class NotificationEvent(BaseModel):
    event_type: str                                # e.g. "task.ready_for_review"
    account_id: str
    subject_user_id: str | None = None             # audience=user when set
    category: NotificationCategory
    payload: dict                                  # shape per event_type
    dedupe_key: str | None = None                  # suppress exact-duplicate fan-out
    emitted_at: datetime
    source_component: Literal["project_tasks", "data_pipeline",
                              "automations", "agentic_harness",
                              "alert_manager", "accounts"]

class Notification(BaseModel):
    notification_id: str
    account_id: str
    category: NotificationCategory
    audience: Literal["account", "user"]
    user_id: str | None = None                     # set when audience="user"
    source_event_type: str
    source_scope: Literal["automation", "project", "task",
                          "pipeline_run", "session", "platform"] | None
    source_scope_id: str | None                    # plan_id | run_id | task_id | ...
    subject: str
    body: str                                      # markdown, max 4 KB
    cta_url: str | None                            # deep link into the app
    data: dict                                     # structured payload for the UI
    created_at: datetime
    archived_at: datetime | None = None            # 30-day auto-archive

class NotificationDelivery(BaseModel):
    delivery_id: str
    notification_id: str
    recipient_user_id: str
    channel: Literal["ui", "email", "slack", "teams"]
    status: Literal["queued", "sending", "delivered", "failed", "skipped"]
    attempts: int
    last_error: str | None
    queued_at: datetime
    delivered_at: datetime | None
    provider_message_id: str | None
    skipped_reason: str | None                     # "preference_off" | "channel_not_configured"

class NotificationSubscription(BaseModel):
    subscription_id: str
    account_id: str
    user_id: str
    scope: Literal["automation", "project"]
    scope_id: str                                  # plan_id
    categories: list[NotificationCategory] | None  # None = all from this scope
    created_at: datetime

class UserNotificationPreferences(BaseModel):
    user_id: str
    matrix: dict[NotificationCategory, dict[Literal["ui","email","slack","teams"], bool]]
    channel_defaults: dict[Literal["ui","email","slack","teams"], bool]  # for new categories
    updated_at: datetime
```

### 3.3 Firestore layout (Shape B)

| Path | Scope | Notes |
|------|-------|-------|
| `accounts/{account_id}/notifications/{notification_id}` | Per-account | Canonical record; replaces the current flat `notifications/{id}` collection |
| `accounts/{account_id}/notifications/{notification_id}/deliveries/{delivery_id}` | Per-account, nested | One per recipient × channel; covered by `recursive_delete` on account deletion |
| `accounts/{account_id}/notification_subscriptions/{subscription_id}` | Per-account | Per-automation / per-project opt-in subscriptions |
| `users/{user_id}/notification_preferences` | Per-user | Rebuilt preferences document (replaces the existing `users/{user_id}/preferences`) |
| `users/{user_id}/notification_statuses/{notification_id}` | Per-user | Per-user read/archive state — kept as-is; the `notification_id` is unique across accounts |
| `users/{user_id}/integrations/slack` | Per-user | OAuth tokens for Slack delivery (new) |
| `users/{user_id}/integrations/teams` | Per-user | OAuth tokens for Teams delivery (new) |
| `accounts/{account_id}/_notification_dlq/{delivery_id}` | Per-account | Dead-letter queue for permanently failed deliveries; inspected by admin UI and ops |

### 3.4 Targeting model

Two audience modes:

- **`audience="account"`** — fan-out to every user with `accounts/{account_id}/users/{user_id}` membership. Used for account-wide events (automation completed, data-pipeline run failed, new KPI threshold crossed). Per-user preferences determine which channels each recipient receives.
- **`audience="user"`** — a single `user_id` is the recipient. Used for user-specific events (your task is ready for review, your invitation was accepted, your Slack re-auth required).

Explicit subscriptions are additive on top of the audience rules:

- When `NotificationSubscription` records exist for `scope="automation", scope_id=plan_id`, subscribers receive every event whose `source_scope="automation"` and `source_scope_id=plan_id` regardless of whether they would normally be in the account fan-out. This supports "I want Slack pings from exactly this one automation" without changing account-level preferences.
- Subscriptions filter by `categories` when set — a user can subscribe to only `AUTOMATION_FAILED` events from one automation and ignore success events.

Deduplication uses `NotificationEvent.dedupe_key` — when set, the router suppresses a second event with the same key within a 60-second window (configurable). This protects against orchestrator retries creating duplicate "task ready" notifications.

### 3.5 Channel architecture

| Channel | Adapter | Delivery path | Configuration |
|---------|---------|---------------|---------------|
| **UI** | `UIChannelAdapter` | Writes `NotificationDelivery` with `status=delivered` immediately; frontend picks it up via Firestore `onSnapshot` listener on `users/{user_id}/notification_statuses` and joins to `accounts/{account_id}/notifications` by id. | Always on; no config. |
| **Email** | `EmailChannelAdapter` | SendGrid Dynamic Template per category. Reuses existing `email_service.py` SendGrid client + `sm://sendgrid-api-key` Secret Manager resolution. Per-user verified email from the identity profile. | Opt-in per category in preferences; SendGrid API key at the platform level. |
| **Slack** | `SlackChannelAdapter` | OAuth install per user (`users.identity` scope + `chat:write`). Delivers to the user's DM with the KEN-E bot by default; per-account override to a shared channel is a §9 open question. | User-initiated OAuth via `/api/v1/integrations/slack/connect`; tokens at `users/{user_id}/integrations/slack`. |
| **Teams** | `TeamsChannelAdapter` | Microsoft Graph `chatMessage` into the user's 1:1 chat with the KEN-E Teams app. Bot Framework / Graph hybrid — message send via Graph, app registration via the Azure Bot Service. | User-initiated OAuth via `/api/v1/integrations/teams/connect`; tokens at `users/{user_id}/integrations/teams`. |

All channel adapters implement the same protocol and the router is channel-agnostic — adding a future channel (SMS, Discord) is one adapter class plus one column in the preferences matrix.

### 3.6 Event emission / triggers

Emitters import a thin client (`notifications_client.emit_event(event)`) that posts to the `NotificationRouter` service. Emission is fire-and-forget from the caller's perspective; the router returns within ~50ms after writing the notification record and enqueuing deliveries.

Initial event types (registered in `NotificationTemplate` registry):

| Source | Event type | Default audience | Default category |
|--------|------------|------------------|------------------|
| Project Tasks (PR-PRD-04) | `task.ready_for_review` | user (assignee) | Task Activity |
| Project Tasks (PR-PRD-04) | `task.completed` | account | Task Activity |
| Project Tasks (PR-PRD-04) | `task.failed` | account | Task Activity |
| Project Tasks (PR-PRD-04) | `task.revision_requested` | user (assignee) | Task Activity |
| Data Pipeline (DP-PRD-03) | `pipeline_run.completed` | account | Automation Activity |
| Data Pipeline (DP-PRD-03) | `pipeline_run.failed` | account | Automation Activity |
| Data Pipeline (DP-PRD-03) | `pipeline_credentials_expired` | account admins | Platform Health |
| Automations (A-PRD-02) | `automation.run_completed` | account | Automation Activity |
| Automations (A-PRD-02) | `automation.run_failed` | account | Automation Activity |
| Automations (A-PRD-04) | `automation.test_run_ready` | user (triggerer) | Automation Activity |
| Agentic Harness (AH-PRD-03) | `specialist_credentials_expired` | account admins | Platform Health |
| Alert Manager (existing) | `token_budget.warning` / `.critical` | account admins | Platform Health |
| Accounts (existing) | `invitation.accepted` | user (inviter) | Account Activity |

The emission contract is the single integration surface — a component ships its events once, and gains email/Slack/Teams delivery for free as those channels land across later PRDs.

### 3.7 Delivery reliability

- **Queue:** Cloud Tasks queue per channel (`notifications-ui`, `notifications-email`, `notifications-slack`, `notifications-teams`). Per-channel isolation prevents a Slack outage from blocking email.
- **Retries:** exponential backoff, max 5 attempts over ~30 minutes. Retryable errors (5xx, rate limits, timeouts) loop; non-retryable errors (invalid token, user not found) go straight to DLQ.
- **DLQ:** permanent failures land in `accounts/{account_id}/_notification_dlq/{delivery_id}` with the last error. Surfaced on an admin page under `/settings/notifications/delivery-health`.
- **Observability:** every delivery emits a Weave span `notification.deliver` with `{channel, category, status, attempts, provider_message_id, latency_ms}`. Per-channel dashboards track delivery rate, P95 latency, retry rate.
- **Idempotency:** the router writes the `Notification` record and enqueues deliveries inside a single Firestore transaction to guarantee that a record exists iff its deliveries are queued. The dispatcher uses `delivery_id` as the idempotency key for the provider call.

## 4. Integration with other components

### 4.1 Project Tasks (PR-PRDs) — closes two today-missing hooks

- **PR-PRD-04 (Event-Driven Orchestrator):** the `TaskOrchestrator` gains `notifications_client.emit_event(...)` calls at four lifecycle points — `on_task_status_change` transitions to `ready_for_review`, `completed`, `failed`, and `revision_requested`. These calls are already the natural fan-out points inside the orchestrator; adding the emission is a ~5 line patch per branch. The orchestrator does not own category or channel logic — it owns the fact that the event happened.
- **PR-PRD-01 (Data Model & API):** unchanged; notifications do not mutate the plan schema.
- **PR-PRD-03 (Calendar Frontend):** the existing in-app sidebar continues to render; CTA URLs on task-related notifications deep-link to `/calendar?plan={plan_id}&task={task_id}` (preserving current navigation).

### 4.2 Data Pipeline (DP-PRDs) — closes the gap flagged in that component's §9

The `data-pipeline.md` backlog explicitly notes: "Re-auth signaling: how does a pipeline run report 'the account's GA token expired'? Proposal: write a notification via the existing notification system." This component formalizes the mechanism.

- **DP-PRD-03 (Task System Integration):** `DataPipelineDispatcher` emits `pipeline_run.completed` and `pipeline_run.failed` after writing the run record, before returning to the `TaskOrchestrator`. This is the direct answer to "a notification emits when a TaskOrchestrator dispatch completes" — every data-pipeline task-completion path fires a notification by contract.
- **DP-PRD-02 (GA Connector) + future connectors:** connector-level auth failures surface as `pipeline_credentials_expired` events so users get re-auth prompts in the same place they review pipeline runs.

### 4.3 Automations (A-PRDs) — per-automation subscription

- **A-PRD-02 (Recurring Scheduler):** `AutomationRunEngine.complete_run` emits `automation.run_completed` / `automation.run_failed` with `source_scope="automation"`, `source_scope_id=plan_id`.
- **A-PRD-06 (Automation Details Page):** the details page adds a **"Notify me"** control that creates/deletes a `NotificationSubscription` record for `(user_id, scope="automation", scope_id=plan_id)`. The control optionally exposes category sub-filters ("only failures", "all activity"). This is the UI entry point for the user requirement "subscribe to receive notifications from an individual automation in the automation configuration page."
- **A-PRD-04 (Test Mode):** test-run events carry `is_test=true` in the payload so notification templates can badge them ("Test run of Weekly KPI Refresh completed").

### 4.4 Agentic Harness (AH-PRDs)

- **AH-PRD-03 (GA Specialist):** the existing `_requires_reauth` signal becomes a `specialist_credentials_expired` event. No new UX surface — it routes through the same preferences and channels as everything else.
- **Future specialists:** inherit the same emission pattern.
- **Session-end notifications:** optional; out of scope for v1. A future `session.completed` event type can be added without schema changes.

### 4.5 Identity / Accounts

- **Recipient resolution:** the router queries `accounts/{account_id}/users` to expand `audience="account"` events. No new account surface is needed — the membership list already exists.
- **User identity for Email/Slack/Teams:** email pulled from the verified profile; Slack and Teams require per-user OAuth completed via the new `/api/v1/integrations/{slack,teams}/connect` endpoints.
- **Invitation emails:** the existing invitation-email flow continues to use `email_service.py` directly (not through this component) because invitations go to users who do not yet exist in the system and cannot have preferences. A future consolidation is a §9 open question.

## 5. Categories & default routing

The rebuild replaces the current 7-category enum with a smaller, source-aligned set. Migration maps old categories to new via a one-shot backfill.

| Category | Description | Default channels (new user) | Primary emitters |
|----------|-------------|-----------------------------|------------------|
| `TASK_ACTIVITY` | Task ready / completed / failed / revision-requested | UI | Project Tasks |
| `AUTOMATION_ACTIVITY` | Automation or pipeline run completed/failed | UI + Email | Automations, Data Pipeline |
| `PLATFORM_HEALTH` | Credentials expired, token budget warnings, system alerts | UI + Email | Agentic Harness, Alert Manager, Data Pipeline |
| `ACCOUNT_ACTIVITY` | Invitation accepted, role changed, account-level admin events | UI + Email | Accounts |
| `DATA_QUALITY` | KPI thresholds, data drift, quality alerts (today's 7-category "Data Quality Alert" rolled in) | UI | Future (Knowledge Graph) |
| `PRODUCT_UPDATES` | New features, releases, platform announcements | UI | Platform (manual broadcasts) |

Slack and Teams are opt-in per category — no category defaults them on, because both require OAuth setup that the user has not yet performed at account creation.

## 6. Non-goals

- **Replacing the Alert Manager's internal logic** — `app/adk/agents/strategy_agent/alert_manager.py` remains the source of token-budget thresholds and circuit-breaker behavior; it becomes a notification *emitter*, not a separate delivery path. The duplicate email/webhook code paths inside it are removed in `N-PRD-01`.
- **A generic event bus** — `NotificationEvent` is not Pub/Sub. Emitters call the router synchronously; the queue lives only on the delivery side. A future event bus can subscribe to the router's write-log if needed.
- **User-to-user messaging / chat** — notifications are one-way system → user. Collaboration features are a separate component.
- **Rich HTML composition in email** — emails use SendGrid Dynamic Templates authored separately; the `Notification.body` remains markdown. No inline HTML in the notification record.
- **SMS / voice / push to mobile apps** — the channel protocol admits them, but initial scope is UI/Email/Slack/Teams only. Roadmap entries only.
- **Localization / i18n** — English-only at v1; template keys are defined so localization is additive later.
- **Broadcast channels owned by an account (shared Slack channel, Teams channel)** — v1 delivers to user DMs only. Shared-channel delivery is a §9 open question.

## 7. Proposed project decomposition

Eight candidate projects (`N-PRD-01` … `N-PRD-08`). The foundation PRD unblocks everything; the three channel PRDs (Email, Slack, Teams) run in parallel once the event contract lands; the preferences + subscription UI integrates across them.

### Phase 1 — Foundation & Rebuild (`N-PRD-01`)
- Shape B data model — `Notification`, `NotificationDelivery`, `NotificationSubscription`, `UserNotificationPreferences` (new matrix form).
- Firestore repositories + `recursive_delete` coverage.
- `NotificationRouter` service + in-process `UIChannelAdapter`.
- Rebuilt `/api/v1/notifications/*` endpoints against the new schema; legacy routes removed.
- Frontend — `NotificationSidebar` migrated to Firestore `onSnapshot` listener on `users/{user_id}/notification_statuses` for real-time unread counts; category filters updated to the new enum.
- One-shot backfill: migrate `notifications/{id}` → `accounts/{account_id}/notifications/{id}`, map old categories to new.
- Alert Manager refactored to emit events rather than deliver directly.
- **Exit criteria:** every existing in-app notification surface works on the new data model; real-time unread counts update without a page refresh; legacy `notifications/{id}` collection is empty.

### Phase 2 — Event contract & emitter integration (`N-PRD-02`)
- `NotificationEvent` model + `NotificationTemplate` registry + `notifications_client.emit_event(...)` shared library.
- Emitter patches in four components: `TaskOrchestrator` (PR-PRD-04), `DataPipelineDispatcher` (DP-PRD-03), `AutomationRunEngine` (A-PRD-02), specialist re-auth paths (AH-PRD-03).
- Deduplication window + `dedupe_key` handling.
- **Exit criteria:** every event in §3.6 fires end-to-end with a `Notification` record visible in the sidebar. Closes the data-pipeline §9 gap.

### Phase 3 — Email channel (`N-PRD-03`)
- `EmailChannelAdapter` — SendGrid Dynamic Template per category; templates authored and version-controlled as JSON beside the adapter.
- Per-user email delivery using the verified profile email; no cross-user leakage.
- Cloud Tasks `notifications-email` queue + retry policy + DLQ plumbing.
- **Exit criteria:** toggling Email for any category delivers real SendGrid emails in a staging environment; DLQ captures a forced-failure test.

### Phase 4 — Slack channel (`N-PRD-04`)
- Slack app registration (KEN-E workspace app), scopes `users:read`, `chat:write`, `im:write`.
- `/api/v1/integrations/slack/connect` (OAuth) + `/disconnect` + token refresh.
- `SlackChannelAdapter` — `chat.postMessage` to the user's DM; message format using Block Kit for CTA button.
- Preferences UI surfaces "Connect Slack" CTA when the user toggles a Slack channel without an installed integration.
- **Exit criteria:** a user installs Slack, toggles Slack for a category, and receives a working CTA-linked message on the next triggering event.

### Phase 5 — Microsoft Teams channel (`N-PRD-05`)
- Teams app registration (Azure Bot Service + Graph API app) — mirrors Slack in shape but uses Graph `POST /chats/{chatId}/messages` against the user's 1:1 chat with the KEN-E bot.
- `/api/v1/integrations/teams/connect` OAuth flow.
- `TeamsChannelAdapter` with Adaptive Card rendering for CTA.
- **Exit criteria:** feature parity with Slack — install, toggle, deliver, retry, DLQ.

### Phase 6 — Preferences & per-automation subscription (`N-PRD-06`)
- Preferences page rebuild — 4-channel × N-category matrix, with inline "Connect Slack" / "Connect Teams" CTAs when a channel is toggled without an integration.
- Defaults for new categories (`channel_defaults` field) settable in the same page.
- **Per-automation subscription UI** on `AutomationDetailsPage` (A-PRD-06) — "Notify me" toggle + optional category filter. Creates `NotificationSubscription` records.
- Subscription list on the preferences page — "Automations you're subscribed to" with unsubscribe.
- **Exit criteria:** a user can compose a preferences matrix, connect Slack and Teams, subscribe to one automation, and receive the expected events across all enabled channels.

### Phase 7 — Delivery reliability (`N-PRD-07`)
- Cloud Tasks queues per channel (already scaffolded in `N-PRD-01/03/04/05`; this PRD hardens them).
- DLQ admin UI at `/settings/notifications/delivery-health` for ops + account admins.
- Weave span coverage end-to-end + a Looker / Grafana dashboard tracking per-channel delivery rate and P95 latency.
- Load test — 10× peak sustained emission rate with no drops and retries absorbed.
- **Exit criteria:** verified delivery SLA — 99% of notifications delivered to UI < 2s, Email < 60s, Slack/Teams < 30s at 10× peak load.

### Phase 8 — Integration testing & polish (`N-PRD-08`)
- End-to-end tests covering every event type × every channel × preference combination.
- Cross-component smoke tests: project-task completion → email+Slack delivery with correct deep link; data-pipeline failure → account-admin fan-out across enabled channels.
- Runbook: channel outages, DLQ inspection, backfill re-issuance.
- Documentation sweep — `api/CLAUDE.md`, `frontend/CLAUDE.md`, component README updates; DESIGN-REVIEW-LOG entry for the Shape B migration and channel additions.
- **Exit criteria:** verification report appended to this README; component marked GA; production customer launch unblocked.

### Candidate dependency graph

```
N-PRD-01 (Foundation & Rebuild) ─┬─► N-PRD-02 (Event contract) ─┬─► N-PRD-03 (Email) ──┐
                                 │                              ├─► N-PRD-04 (Slack) ──┤
                                 │                              └─► N-PRD-05 (Teams) ──┤
                                 │                                                     │
                                 └─► N-PRD-07 (Reliability) ◄─────────────────────────┤
                                                                                       │
                                     N-PRD-06 (Preferences + subscription UI) ◄───────┤
                                                                                       ▼
                                                                          N-PRD-08 (Integration & Polish)
```

## 8. Dependencies on other components

### Hard prerequisites (must ship before Notifications begins)

| Component | What's needed | Reference |
|-----------|---------------|-----------|
| **DM-PRD-00 (Migration Foundation)** | Shape B convention for the new `accounts/{account_id}/notifications/*` and `notification_subscriptions/*` collections; composite indexes. | [`../data-management/projects/DM-PRD-00-migration-foundation.md`](../data-management/projects/DM-PRD-00-migration-foundation.md) |
| **DM-PRD-05 (Deletion Sweep Rewrite)** | `recursive_delete(accounts/{account_id})` covers the new subcollections including `notifications/{id}/deliveries/*`. | [`../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md`](../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md) |
| **Accounts / Auth (existing)** | `accounts/{account_id}/users` membership for account-scoped fan-out; verified user email from the profile. | `api/src/kene_api/auth/` |
| **Secret Manager + SendGrid (existing)** | `sm://sendgrid-api-key` resolution already in place for invitations. | `api/src/kene_api/shared/secrets.py` |

### Soft prerequisites (strongly recommended)

| Component | Why it helps | Reference |
|-----------|--------------|-----------|
| **PR-PRD-04 (Event-Driven Orchestrator)** | N-PRD-02 emitter patch lives here. If PR-PRD-04 has not shipped, task events cannot fire. | [`../project-tasks/projects/PR-PRD-04-event-driven-orchestrator.md`](../project-tasks/projects/PR-PRD-04-event-driven-orchestrator.md) |
| **A-PRD-02 (Recurring Scheduler)** | Automation completion events originate here. | [`../automations/README.md`](../automations/README.md) |
| **A-PRD-06 (Automation Details Page)** | Hosts the per-automation subscription UI — N-PRD-06 lands the control on this page. | [`../automations/README.md`](../automations/README.md) |
| **DP-PRD-03 (Task System Integration)** | Data-pipeline completion events originate here. Without it, the data-pipeline gap remains open. | [`./backlog/data-pipeline.md`](../data-pipeline/README.md) |
| **AH-PRD-03 (GA Specialist)** | Re-auth events originate from specialist OAuth failures. | [`../agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md`](../agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md) |

### Downstream consumers

- **All future feature components** — any component with user-visible lifecycle events (Knowledge Graph session-end, Skills run results, Strategy Agent scoring) emits events into this router. Adding a new emitter is a one-line `notifications_client.emit_event(...)` call plus a template registration.

## 9. Open questions (resolve before N-PRD-01)

1. **Shared-channel Slack/Teams delivery:** in addition to per-user DMs, should an account admin be able to configure a shared Slack channel or Teams channel that receives all account-scoped notifications? This increases delivery reliability for shared ops rotations but adds a second OAuth scope and a per-account configuration surface. First-pass: defer to a later PRD; v1 ships DM-only.
2. **Invitation email consolidation:** today's invitation flow bypasses the notification system (recipient does not yet have an account). Should post-acceptance activity (onboarding reminders, first-login walkthrough) go through notifications, or stay in the invitation module? Leaning: notifications for anything post-first-login.
3. **Dedupe window tuning:** 60s default for `dedupe_key`. Specific events — e.g. `task.ready_for_review` when a task bounces through a revision loop — may need longer. Per-event-type override vs global constant?
4. **Email digest mode:** should `AUTOMATION_ACTIVITY` email delivery support an opt-in daily digest instead of per-event? High-value for users running many automations; adds template complexity. Defer to §3 Phase after Email channel ships cleanly.
5. **Preference matrix migration:** old preferences store `categories: list` + `channels: list` (flat). New shape is a full matrix. Backfill strategy: (a) map each old category × each old channel = true, or (b) use new `channel_defaults` and reset per-category overrides. Leaning (a) to minimize user surprise.
6. **DLQ retention:** 30 days? Longer for compliance? Per-account override? First-pass: 30 days, admin-configurable in a later PRD.
7. **Per-project (not per-automation) subscriptions:** the requirement is explicit about per-automation subscriptions. Should the same control ship for regular (non-automation) projects? The subscription model supports it (`scope="project"` is defined). Leaning: ship scope=project support in the model; surface the UI only for automations in v1; add project UI later if asked.
8. **Teams app distribution:** single-tenant app (customers install from a link) vs Microsoft AppSource submission (longer review, broader discoverability). First-pass: single-tenant with a self-service install flow; AppSource later.
9. **Real-time listener cost envelope:** moving to `onSnapshot` listeners on `users/{user_id}/notification_statuses` increases Firestore read costs per active session. Measure in N-PRD-01 against the existing polling pattern; cap open listeners per tab.
10. **Unsubscribe link compliance:** Email deliveries must include a one-click unsubscribe. Does it revoke all Email notifications (CAN-SPAM minimum) or open the preferences page? First-pass: revoke the specific category that triggered the email + link to full preferences.

## 10. Reference

- [`../project-tasks/README.md`](../project-tasks/README.md) — `PlanTask`, `TaskOrchestrator` (event-emission integration point)
- [`../project-tasks/projects/PR-PRD-04-event-driven-orchestrator.md`](../project-tasks/projects/PR-PRD-04-event-driven-orchestrator.md) — orchestrator dispatch lifecycle, where task events fire
- [`../automations/README.md`](../automations/README.md) — `AutomationRunEngine`, `AutomationDetailsPage` (per-automation subscription UI host)
- [`../data-pipeline/README.md`](../data-pipeline/README.md) §9 item 5 — the re-auth / completion signaling gap this component closes
- [`../agentic-harness/README.md`](../agentic-harness/README.md) — specialist OAuth + re-auth signaling patterns
- [`../agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md`](../agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md) — `_requires_reauth` signal that becomes `specialist_credentials_expired`
- [`../data-management/README.md`](../data-management/README.md) — Shape B convention, migration framework
- [`../PROJECT-PLANNER.md`](../PROJECT-PLANNER.md) — add `N-PRD-NN` rows here when PRDs are authored
- `api/src/kene_api/services/notification_service_v2.py` — existing service replaced by `N-PRD-01`
- `api/src/kene_api/routers/notifications_v2.py` — existing routes replaced by `N-PRD-01`
- `frontend/src/components/notifications/` — existing sidebar + preferences UI migrated in `N-PRD-01` / `N-PRD-06`
- `app/adk/agents/strategy_agent/alert_manager.py` — existing alert manager refactored to emit events in `N-PRD-01`

---

<!-- IMPLEMENTATION PLAN NOTES

This document is a component implementation plan — the precursor to project PRDs under `projects/`. When work begins:

1. Author `N-PRD-NN` files under `docs/design/components/notifications/projects/` using the 10-section project-PRD shape established by sibling components (see `automations/projects/` for reference).
2. Port §1-5 of this doc into a README.md refactor that matches the active-component shape of `automations/README.md` (Project Index table, dependency graph, standard PRD shape).
3. Add each new PRD row to `PROJECT-PLANNER.md` with `blocked_by` populated.
4. Promote this plan's §9 Open Questions into each PRD's §9 Risks section as they are resolved.

Open questions in §9 must all be resolved (at least tentatively) before N-PRD-01 drafting begins; unresolved questions become risks in the PRD §9. Production launch is gated on N-PRD-08 exit criteria being met.
-->
