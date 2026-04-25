# IN-PRD-05 — Re-auth Lifecycle

**Status:** Not started
**Owner team:** Integrations component team (backend + thin frontend)
**Blocked by:** [IN-PRD-02](./IN-PRD-02-google-oauth-flow.md) (connections that can go expired); [IN-PRD-03](./IN-PRD-03-connection-management-ui.md) (page for the notification deep-link to land on)
**Parallel with:** [IN-PRD-04](./IN-PRD-04-meta-mailchimp-platforms.md) — re-auth treats all platforms identically; no coupling
**Blocks:** [IN-PRD-06](./IN-PRD-06-integration-testing-cleanup.md)
**Estimated effort:** 2 days (backend + integration with existing notification system + a small amount of frontend)

---

## 1. Context

Tokens expire. Users revoke access at the platform. Users get removed from the KEN-E account. This project delivers the **re-auth lifecycle**: how Integrations detects that a connection has gone bad, how users learn about it, and how reconnection restores service for every downstream consumer.

The core idea is a single notification category, `"Integration Needs Re-auth"`, routed by Integrations on three triggers:

1. **Refresh failure** — the refresh sweeper (IN-PRD-02) can't get a new access token.
2. **401 from a downstream consumer** — Data Pipeline or Agent Factory calls credential-read, gets a valid token, uses it against the platform, gets a 401, and calls back to Integrations to mark the connection expired. This handles cases where Google decides a token is invalid before its expiry (user revoked at Google).
3. **User removal from account** — when a KEN-E user is removed from their account, every connection they authored is revoked + deleted, and a notification goes to remaining account admins telling them to reconnect under a different user.

Downstream consumers handle re-auth uniformly: on a credential-read 409 `needs_reauth`, they fail the current task with a `needs_reauth` status; the task surfaces the existing re-auth notification (dedup-safe), and the task retries automatically once the connection is back.

This PRD also lights up a low-priority watchdog — if a connection has been in `status=expired` for more than 7 days, an internal alert fires to PagerDuty / Slack so the product team can nudge the customer.

## 2. Scope

### In scope
- **`mark-expired` detection hook** — `POST /api/v1/internal/integrations/connections/{connection_id}/mark-expired` (OIDC). Called by consumers on a 401. Transitions `status` to `expired`, writes `reauth_requested` audit entry, enqueues a re-auth notification (deduped per connection per 24h). Tolerates being called on already-expired connections (idempotent).
- **Notification emission** — new `NotificationCategory.INTEGRATION_NEEDS_REAUTH` registered in the existing notification system. Payload: `{account_id, connection_id, platform_id, platform_display_name, reason}`. Deep-link URL: `/settings/integrations/{connection_id}`.
- **Notification dedup** — per `(account_id, connection_id)` dedup window: no more than one re-auth notification per 24 hours, to avoid storming users when a downstream consumer retries.
- **Refresh-failure hook** — `refresh_connection()` (IN-PRD-02) calls `mark-expired` on refresh failure rather than duplicating the transition logic. Preserves a single source of truth for the `connected → expired` transition.
- **User-removal handler** — `POST /api/v1/internal/integrations/on-user-removed {account_id, user_id}` (OIDC). Wired to be called from whatever flow removes a user from an account. Iterates `accounts/{account_id}/platform_connections/*` where `connected_by_user_id == user_id`; for each:
  - Best-effort revoke at the platform.
  - `firestore.recursive_delete(...)` of the connection + its tokens.
  - Audit entry: `{event: "revoked", actor_id: "system:user_removed", metadata: {removed_user_id}}`.
  - Emits one notification per revoked connection to **remaining account admins** (category `INTEGRATION_NEEDS_REAUTH`, reason `"connected_by_user_removed"`).
- **Pre-emptive refresh completion** — IN-PRD-02 shipped the sweeper; this PRD ensures its failure path wires correctly into `mark-expired` and notifications.
- **Stuck-expired watchdog** — daily Cloud Scheduler cron sweeps connections with `status=expired` older than 7 days; emits a single internal alert per batch (PagerDuty / Slack, channel already exists for other system alerts). Not user-facing.
- **Deep-link behavior** — notification click lands on `/settings/integrations/{connection_id}` (implemented in IN-PRD-03); this PRD just ensures the notification payload includes the correct URL template.
- **Notification deep-link template helper** — a reusable helper other consumers can use to format their own `integrations-related` deep-links consistently.
- **Feature flag** — `integrations_reauth_lifecycle_enabled` — if off, `mark-expired` becomes a no-op (the status transition still happens but no notifications emit). Useful during IN-PRD-06 E2E bring-up if notifications misbehave.

### Out of scope
- Real-time "invalidation propagation" to running workers — acceptable that a workflow in-flight with cached credentials continues to its next retry boundary before hitting re-auth. The implementation-plan §9 risk table explicitly accepts this.
- HITL flows around re-auth (user chooses what to retry) — current design: retry is automatic via the normal Project Tasks revision loop once a connection is back.
- Cross-account notification routing — stays within the affected account.
- Per-user notification preferences specifically for integrations — inherits whatever the global notification preferences provide.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[IN-PRD-02](./IN-PRD-02-google-oauth-flow.md)** | `refresh_connection` failure path; `status=expired` transition; audit writer. | This component |
| **[IN-PRD-03](./IN-PRD-03-connection-management-ui.md)** | `/settings/integrations/{connection_id}` deep-link target page (pulse-animation + Reconnect focus behavior). | This component |
| **Notification system** (existing) | `create_notification(account_id, category, payload, ...)` + `NotificationCategory` enum. This PRD adds a category and uses the existing routing (in-app bell, email-digest subscription if configured). | `api/src/kene_api/notifications/` |
| Account-member service | User-removal flow calls our `on-user-removed` hook. Wiring edits: the existing `DELETE /api/v1/accounts/{account_id}/members/{user_id}` handler (or equivalent) appends a POST to `on-user-removed` after successful removal, transactionally or via a post-commit hook. | `api/src/kene_api/routers/accounts.py` or `organizations.py` |
| Feature Flags | `integrations_reauth_lifecycle_enabled`. | [FF-PRD-01](../../feature-flags/projects/FF-PRD-01-data-model-evaluation-api.md) |
| Cloud Scheduler | One additional job: `integrations-stuck-expired-watchdog` (daily). | `deployment/terraform/` |
| Internal alerting channel | Existing PagerDuty / Slack routing for system alerts. Runbook: `operations/integrations-watchdog.md` (new). | Operations |

## 4. Data contract

No new collections. This PRD extends behavior over existing shapes. Two transient bookkeeping additions:

```python
# New audit event values (already present in the Literal, just clarifying usage):
ConnectionAuditEntry.event: Literal[
  "connected", "refreshed", "revoked",
  "reauth_requested",          # emitted by mark-expired + by user-removal-handler per connection
  "used", "error"
]

# Dedup bookkeeping: stored on the connection doc, not a new collection:
PlatformConnection.last_reauth_notification_sent_at: datetime | None = None
```

Per-connection dedup lives on the doc so it's atomic with the status transition (single-document transaction).

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Modify | `api/src/kene_api/models/integrations.py` — add `last_reauth_notification_sent_at` field |
| Create | `api/src/kene_api/integrations/reauth.py` — `mark_expired(connection_id, reason)` transactional helper; notification emission + 24h dedup |
| Create | `api/src/kene_api/integrations/user_removal.py` — `on_user_removed(account_id, user_id)` handler |
| Modify | `api/src/kene_api/routers/integrations.py` — wire `POST /internal/.../mark-expired` and `POST /internal/.../on-user-removed`; both OIDC |
| Modify | `api/src/kene_api/integrations/refresh.py` — replace inline `status=expired` transition with a call to `mark_expired(..., reason="refresh_failed")` |
| Modify | `api/src/kene_api/notifications/categories.py` — add `INTEGRATION_NEEDS_REAUTH` |
| Modify | `api/src/kene_api/notifications/templates.py` (or equivalent) — copy + deep-link URL for the new category |
| Modify | `api/src/kene_api/routers/accounts.py` (or `organizations.py`) — post-commit call to `on_user_removed` after a member removal |
| Create | `api/src/kene_api/integrations/workers/stuck_expired_watchdog.py` + Cloud Scheduler handler route |
| Modify | `deployment/terraform/` — the new Cloud Scheduler job |
| Create | `docs/design/components/integrations/operations/integrations-watchdog.md` |
| Modify | `frontend/src/app/pages/settings/integrations/IntegrationsTab.tsx` — on deep-link, pulse + auto-focus Reconnect CTA (delivered by IN-PRD-03; this PRD just verifies the behavior with an E2E test) |
| Create | `api/tests/unit/integrations/test_mark_expired.py` |
| Create | `api/tests/unit/integrations/test_user_removal.py` |
| Create | `api/tests/unit/integrations/test_notification_dedup.py` |
| Create | `api/tests/integration/integrations/test_reauth_e2e.py` — full lifecycle with a consumer posting 401 feedback |
| Create | `api/tests/integration/integrations/test_user_removal_e2e.py` |

### 5.2 `mark_expired` transaction

```text
mark_expired(connection_id, reason):
  Firestore transaction on accounts/{account_id}/platform_connections/{connection_id}:
    Load connection.
    If status already in {"expired","revoked"} and reason != "refresh_failed":
      return (idempotent no-op).
    Set status="expired", error_message=reason, last_reauth_notification_sent_at logic:
      If last_reauth_notification_sent_at is within 24h:
        skip notification
      Else:
        last_reauth_notification_sent_at = now
        emit_notification = True.
  (outside transaction)
  write_connection_audit(event="reauth_requested", actor_id=caller_or_"system", metadata={reason})
  if emit_notification:
    create_notification(
      account_id,
      category=INTEGRATION_NEEDS_REAUTH,
      payload={connection_id, platform_id, platform_display_name, reason},
      deep_link=f"/settings/integrations/{connection_id}",
    )
```

### 5.3 `on_user_removed` handler

```text
on_user_removed(account_id, user_id):
  Iterate accounts/{account_id}/platform_connections where connected_by_user_id == user_id:
    For each connection:
      best-effort revoke at platform (reuse IN-PRD-02's revoke helper).
      firestore.recursive_delete(connection_path).
      write_connection_audit(event="revoked", actor_id="system:user_removed", metadata={removed_user_id: user_id}).
      For each remaining account admin:
        create_notification(
          account_id,
          category=INTEGRATION_NEEDS_REAUTH,
          payload={
            connection_id_deleted: <original_id>,
            platform_id, platform_display_name,
            reason: "connected_by_user_removed",
            removed_user_id: user_id,
          },
          deep_link="/settings/integrations",   # connection is deleted, so no per-connection target
        )
```

Note: the deep-link for removed-user revocations points to the Integrations tab generally, not to a (now-deleted) connection. IN-PRD-03's empty-state / non-connected card for the platform handles the landing well.

### 5.4 Downstream consumer protocol

Published as a contract in the component README (not a new API doc). Consumers (Data Pipeline, Agent Factory) follow this:

1. Call `GET /internal/integrations/credentials/{account_id}/{platform_id}`.
2. Use the returned `access_token` against the platform.
3. On 401 (or platform-specific equivalent): `POST /internal/integrations/connections/{connection_id}/mark-expired {reason: "consumer_401"}`.
4. Fail the current task/run with `needs_reauth` status; the existing task revision loop pauses until the connection returns.

Consumers don't need to know anything else — IN-PRD-05 handles notifications + user-visibility.

### 5.5 Stuck-expired watchdog

Daily cron at 09:00 UTC:

```text
query accounts/{*}/platform_connections where status == "expired" and last_reauth_notification_sent_at < now - 7d:
  for each, append to alert batch.
if alert batch non-empty:
  single PagerDuty / Slack message with the count + list of {account_id, platform_id}.
```

Threshold, cadence, and batch size are all constants in `stuck_expired_watchdog.py` — easy to tune without config changes.

## 6. API contract

### Internal (OIDC)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/internal/integrations/connections/{connection_id}/mark-expired` | Transition to `expired` + notification (deduped). Body: `{account_id, reason}`. |
| `POST` | `/api/v1/internal/integrations/on-user-removed` | Revoke + delete all connections authored by the removed user; notify remaining admins. Body: `{account_id, user_id}`. |
| `POST` | `/api/v1/internal/integrations/stuck-expired-watchdog` | Cloud Scheduler handler; emits a single batched alert. |

No user-facing API changes.

## 7. Acceptance criteria

1. **Notification category registered** — `NotificationCategory.INTEGRATION_NEEDS_REAUTH` exists with copy + deep-link template; the notification bell renders it correctly.
2. **`mark-expired` happy path** — posting to `mark-expired` on a `connected` connection transitions it to `expired`, writes a `reauth_requested` audit entry, and emits exactly one notification deep-linking to `/settings/integrations/{connection_id}`.
3. **Dedup within 24h** — three `mark-expired` calls in quick succession produce one notification, not three. `last_reauth_notification_sent_at` reflects the first call.
4. **Dedup window expires** — a second `mark-expired` 24+ hours later re-emits a notification.
5. **Idempotent on already-expired** — `mark-expired` on an `expired` connection is a no-op (no duplicate audit, no notification).
6. **Refresh-failure integration** — simulated refresh failure in IN-PRD-02's sweeper calls `mark_expired` and produces a notification.
7. **Consumer-401 integration** — a test consumer calls credential-read, gets a valid token, then posts `mark-expired`; notification fires; subsequent credential-reads return 409 `needs_reauth`.
8. **User-removal end-to-end** — removing a user who authored two Google connections results in: (a) both connections revoked at the platform (best-effort), (b) both recursive-deleted, (c) two `revoked` audit entries with `actor_id="system:user_removed"`, (d) one notification per connection per remaining admin (e.g., one admin × two connections = two notifications).
9. **Reconnect restores service** — after reconnect on the `/settings/integrations/{connection_id}` page, downstream consumers' next credential-read succeeds; no stale `expired` state remains.
10. **Stuck-expired watchdog** — a seeded connection with `status=expired` for 8 days triggers exactly one batched alert; a freshly-expired connection does not.
11. **Deep-link behavior** — clicking the in-app notification bell's re-auth entry navigates to `/settings/integrations/{connection_id}`; the matching card pulses and auto-focuses Reconnect (verified by an E2E test).
12. **Feature flag gate** — with `integrations_reauth_lifecycle_enabled=false`, `mark-expired` still transitions status but emits no notification; the user-removal handler still revokes but emits no notifications.
13. **Contract doc published** — the component README gains a "Consumer protocol for re-auth" section documenting the four-step flow in §5.4.

## 8. Test plan

### Unit
- `mark_expired` transactional logic: happy path; dedup window; idempotent on already-expired; status transition atomic with dedup field update.
- Notification payload construction: correct category, payload, deep-link.
- `on_user_removed`: iteration over connections; per-connection revoke + delete + notify; handles zero-connection accounts.
- Stuck-expired watchdog: selector query boundary conditions (exactly 7d, 6d, 8d).

### Integration
- `test_reauth_e2e.py`: connect via StubPlatform → consumer reads credential → consumer posts `mark-expired` → notification created → reconnect → consumer next read succeeds.
- `test_user_removal_e2e.py`: seed account with user A + B (admin), A authors two connections → remove A → assertions per AC #8.
- Refresh-failure integration: force refresh to fail in a test harness → `mark_expired` invoked → notification emitted.
- Dedup: three sequential `mark-expired` calls → one notification.

### Manual verification
- Dev-env: connect Google, wait for token to near expiry, manually mangle the stored refresh_token to force refresh failure → verify notification appears in UI + email (if configured) + clicking it lands on `/settings/integrations/{connection_id}` with pulse.
- User-removal: remove a test user who authored a connection; verify admin sees the notification and the connection disappears from the Integrations tab.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Notification storm if a consumer retries rapidly on a dead connection | 24h dedup per connection; AC #3 test. |
| Race between user-removal and the member-removal DB commit | On-user-removed is posted post-commit from the member-removal flow; if it fails, a background reconciler (minimal — out of scope here) could sweep orphaned connections. Fast-follow PRD if this becomes real. |
| Stuck-expired watchdog alert fatigue | Batched into one alert/day/batch; tune threshold + cadence as constants. |
| In-flight jobs use cached credentials after revoke | Accepted per implementation-plan §9. First retry boundary hits re-auth; at most one failed task per consumer per connection per revoke event. |
| Notification category added but not rendered by the bell UI | Integration test renders the bell with a seeded notification of this category. |
| `last_reauth_notification_sent_at` drift if mark-expired is called from multiple services simultaneously | Single-document Firestore transaction guarantees atomicity. |

### Open questions
- **Q:** Should user-removal also try to transfer ownership (rebind `connected_by_user_id` to the admin performing the removal) instead of revoking? → No. A user's OAuth grant is *their* grant; transferring would misrepresent the audit trail. Revoke + force reconnect is cleaner and honest.
- **Q:** Email digest vs. immediate email? → Inherit whatever the notification system's default is for this user. Out of scope to change.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Upstream: [IN-PRD-02](./IN-PRD-02-google-oauth-flow.md), [IN-PRD-03](./IN-PRD-03-connection-management-ui.md)
- Downstream: [IN-PRD-06](./IN-PRD-06-integration-testing-cleanup.md)
- Notification system: `api/src/kene_api/notifications/README.md` (if present) or the notifications package source
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; D-1, D-5; C-2, C-4; T-1, T-3, T-4, T-5
