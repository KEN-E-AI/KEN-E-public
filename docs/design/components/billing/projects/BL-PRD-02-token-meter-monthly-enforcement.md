# BL-PRD-02 — Token Meter + Monthly Enforcement

**Status:** Not started
**Owner team:** Billing component team (backend) + Agentic Harness team (integration point)
**Blocked by:** [BL-PRD-01](./BL-PRD-01-core-model-stripe-foundation.md)
**Parallel with:** [BL-PRD-03](./BL-PRD-03-stripe-checkout-subscription-lifecycle.md) — both depend only on BL-PRD-01 and have no cross-dependency in v1
**Blocks:** BL-PRD-04
**Estimated effort:** 5 days backend (≈3 in Billing, ≈2 in Agentic Harness integration + Cloud Scheduler)

---

## 1. Context

This project turns the BL-PRD-01 substrate into a working meter. It wires `billing.meter_increment` into the Agentic Harness LLM-call path, builds the `OrganizationStatus` state machine and 30-second status cache, lands the daily/monthly counter writes via Firestore transactions, and stands up the monthly-reset Cloud Scheduler job. It also introduces the 75% and exceeded notifications.

The most important design point: the meter ships in **observe-only** mode by default. The `billing_enforce_limits` feature flag controls whether status transitions actually gate downstream behavior. For 30 days post-launch, the meter runs alongside Weave token-counting spans without affecting any user — we reconcile the two daily, fix any drift, and only then flip the enforcement flag for early-access orgs. This avoids the failure mode where a meter bug locks paying customers out of their accounts.

When `billing_enforce_limits=true`, an org that crosses 100% of its allowance has `OrganizationStatus.status` flipped to `inactive_overage` synchronously inside the increment that crossed the threshold, and the **next** request to a gated endpoint returns HTTP 402 Payment Required. In-flight requests complete normally — we don't kill streams mid-response.

## 2. Scope

### In scope
- **`billing.meter_increment(org_id, account_id, user_id, tokens, trace_id)`** — synchronous Firestore-transactional increment of the org's monthly counter, the account's daily counter, and the per-user breakdown inside the daily counter. Idempotency keyed on `trace_id` (re-submitting the same trace is a no-op).
- **`billing.check_status(org_id) -> OrganizationStatus`** — read-side helper with a 30s in-process LRU cache. Cache keyed by `org_id`; invalidated by `billing.invalidate_status_cache(org_id)` (called from the meter when status flips, and from BL-PRD-03 webhook handlers).
- **State machine** for `OrganizationStatus.status`: `active` → `approaching_limit` (≥75%) → `inactive_overage` (≥100%); reverse transitions on monthly reset and (in BL-PRD-03) on plan upgrade. The two `inactive_past_due` and `inactive_canceled` states exist in the Literal but are owned by BL-PRD-03 webhook handlers (no transitions wired here).
- **Agentic Harness integration** — `billing.check_status` called at the start of every LLM-consuming agent invocation; on `inactive_*`, raise `BillingInactiveError` (typed exception that the API layer maps to HTTP 402 + structured body). `billing.meter_increment` called after every successful LLM call with the provider-reported token count.
- **HTTP 402 mapping** — exception handler in the API layer translates `BillingInactiveError` into `{status: 402, body: {error: "billing_inactive", reason: "<human copy>", upgrade_url: "/settings/organization/subscription"}}`. The `reason` string is sourced from `OrganizationStatus.reason_message` and is what the frontend banner copy renders.
- **Daily/monthly transactional write** — single Firestore transaction touches three docs: `usage_windows/{YYYY-MM}` (org monthly counter), `accounts/{account_id}/usage_daily/{YYYY-MM-DD}` (account daily counter + by_user dict), and `status/current` (only if status transitions this increment). Distributed-counter pattern (10 sub-counters per doc) keeps write contention bounded.
- **Monthly-reset Cloud Scheduler** — Cloud Scheduler hits `POST /api/v1/internal/billing/monthly-reset` at `00:05 UTC` on the 1st of every month. Idempotent per `YYYY-MM`. Resets every `OrganizationStatus` whose status is `inactive_overage` back to `active`; creates the new `MonthlyUsageWindow` with the current `BillingProfile.monthly_token_allowance` snapshotted as `allowance_at_period_start`; clears notification flags on the *previous* window for record-keeping.
- **Notifications** — emit `Approaching Token Limit` when `tokens_used / allowance` crosses 0.75 in the current window (`notification_75_sent` flag prevents repeat); emit `Token Limit Exceeded` when it crosses 1.0 (`notification_exceeded_sent` flag prevents repeat).
- **`/usage/current` and `/usage/daily` endpoints** — read-only consumer endpoints for the figma-export Subscription tab. `current` returns this month's `MonthlyUsageWindow`. `daily` returns aggregated `AccountUsageDaily` rows for a date range with optional `breakdown=none|account|user`.
- **Reconciliation script** — `api/scripts/reconcile_billing_meter.py` queries W&B Weave for the previous day's spans (filtered to LLM-consumption spans), aggregates per `(org_id, account_id, user_id, date)`, and diffs against the meter. Outputs a discrepancy report; alerts via Slack webhook if drift >0.5%.
- **Observe-only mode** — when `billing_enforce_limits=false`, status flips still happen and notifications still fire (so we can verify timing in real traffic), but the API layer's 402 mapping is bypassed and chat / scheduled tasks proceed normally. Logged for audit (`metadata.observe_only=true` on every status_changed audit entry during this period).
- **Weave spans** — `billing.meter_increment` (`{org_id_hash, account_id_hash, tokens, transition?, observe_only}`), `billing.check_status` (`{org_id_hash, status, cache_hit, latency_ms}`), `billing.monthly_reset` (`{period: YYYY-MM, orgs_processed, orgs_reactivated, latency_ms}`).

### Out of scope
- Stripe Subscription lifecycle / past-due / canceled state transitions — BL-PRD-03.
- Anything that creates a paid subscription — BL-PRD-03.
- Manual override admin endpoint — BL-PRD-05.
- UI consumption of `/usage/*` endpoints — BL-PRD-04 (endpoints exist here as the contract).
- Retroactive backfilling token counts from historical Weave spans — explicitly not done (we accept the meter starts at zero on launch).
- Sales handoff and enterprise-invoice handling — BL-PRD-06.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[BL-PRD-01](./BL-PRD-01-core-model-stripe-foundation.md)** | All Pydantic shapes; Firestore layout; `OrganizationStatus` doc; `write_billing_audit`; status-cache scaffold; `/internal/status/{org_id}` contract. | This component |
| **Agentic Harness** (existing) | LLM-call wrapper that reports token counts after each call. Hook point: `app/adk/agents/...` — single helper to call `billing.meter_increment` after the LLM SDK returns. The exact symbol depends on current code; spike required. | `app/adk/` |
| **W&B Weave** (existing) | Reconciliation reads from Weave's exported span store. Weave already captures token counts in the span structure documented in `docs/trace-structure-spec.md`. | `docs/trace-structure-spec.md` |
| **Notifications** (existing) | `create_notification(category, org_id, user_ids, ...)`. New categories: `Approaching Token Limit`, `Token Limit Exceeded`. | Existing notifications service |
| **Cloud Scheduler** | One scheduled job per env hitting `POST /api/v1/internal/billing/monthly-reset` at `0 5 1 * *`. OIDC auth. | `deployment/terraform/` |
| **Slack** | Reconciliation alert webhook (`sm://billing-reconciliation-slack-{env}`). | Secret Manager |

## 4. Data contract

### Schema additions (existing shapes from BL-PRD-01 unchanged)

The state machine is encoded in helper code, not in a new Pydantic shape. The transitions:

```text
on increment that crosses ≥75% (and current status == "active"):
  status → "approaching_limit"; notify; audit.
on increment that crosses ≥100% (and billing_enforce_limits OR observe-only):
  status → "inactive_overage"; notify; audit; invalidate cache.
on monthly reset:
  for each org whose status == "inactive_overage":
    status → "active"; clear notification flags on previous window; audit.
```

### Firestore writes per increment (transactional)

```text
TX:
  read organizations/{org_id}/usage_windows/{YYYY-MM}      (create if absent)
  read organizations/{org_id}/accounts/{account_id}/usage_daily/{YYYY-MM-DD}  (create if absent)
  read organizations/{org_id}/status/current

  if increment_seen_for_trace_id: return  (idempotency)

  window.tokens_used += tokens
  daily.tokens_used += tokens
  daily.by_user[user_id] += tokens
  mark trace_id seen (TTL 24h)

  if window.tokens_used / window.allowance_at_period_start ≥ 1.0
     and status.status != "inactive_overage":
    status.status = "inactive_overage"
    status.reason_message = "Token limit exceeded — resets {next reset date}"
    status.updated_at = now()
    notify_overage = true

  elif window.tokens_used / window.allowance_at_period_start ≥ 0.75
       and status.status == "active":
    status.status = "approaching_limit"
    status.reason_message = "Approaching token limit"
    notify_75 = true

  commit TX

post-TX (no Firestore lock held):
  if notify_overage and not window.notification_exceeded_sent:
    create_notification("Token Limit Exceeded", ...); set flag.
    invalidate_status_cache(org_id)
  if notify_75 and not window.notification_75_sent:
    create_notification("Approaching Token Limit", ...); set flag.
```

The trace-id idempotency record is kept in `organizations/{org_id}/usage_windows/{YYYY-MM}/seen_traces/{trace_id}` with a 24-hour TTL. Bounded growth, automatic cleanup.

### Distributed counter shape

`MonthlyUsageWindow.tokens_used` and `AccountUsageDaily.tokens_used` are written via 10 sub-counters per doc (`shards/{0..9}.tokens_used`); read aggregates them. Standard Firestore distributed-counter pattern; supports >100 writes/sec per doc.

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create | `api/src/kene_api/billing/meter.py` — `meter_increment`, `check_status`, `invalidate_status_cache` |
| Create | `api/src/kene_api/billing/state_machine.py` — pure transition functions (testable without Firestore) |
| Create | `api/src/kene_api/billing/counters.py` — distributed-counter read/write helpers |
| Create | `api/src/kene_api/billing/notifications.py` — `Approaching Token Limit` / `Token Limit Exceeded` factories |
| Create | `api/src/kene_api/billing/monthly_reset.py` — reset job entry point |
| Create | `api/src/kene_api/billing/exceptions.py` — `BillingInactiveError` |
| Modify | `api/src/kene_api/routers/billing.py` — add `/usage/current`, `/usage/daily`, `/internal/meter-increment`, `/internal/monthly-reset` |
| Modify | `api/src/kene_api/main.py` — register `BillingInactiveError` exception handler returning 402 |
| Modify | `app/adk/agents/...` — call `billing.check_status` at run start; call `billing.meter_increment` after each LLM SDK response |
| Create | `api/scripts/reconcile_billing_meter.py` |
| Modify | `deployment/terraform/cloud_scheduler.tf` — monthly-reset job + OIDC SA binding |
| Modify | `deployment/terraform/firestore.tf` — TTL policy on `seen_traces` (24h); composite index on `usage_daily` (`organization_id, date DESC`) |
| Create | `api/tests/unit/billing/test_state_machine.py`, `test_counters.py`, `test_meter.py` |
| Create | `api/tests/integration/billing/test_meter_end_to_end.py`, `test_monthly_reset.py`, `test_402_mapping.py` |
| Create | `api/tests/integration/billing/test_observe_only_mode.py` |

### 5.2 Agentic Harness integration

Single hook in the LLM-call wrapper:

```python
async def invoke_agent(org_id, account_id, user_id, prompt, ...):
    status = billing.check_status(org_id)         # 30s cache; <1ms typical
    if status.status.startswith("inactive"):
        raise BillingInactiveError(status.reason_message)

    response = await llm_provider.invoke(...)     # existing path
    billing.meter_increment(
        org_id=org_id,
        account_id=account_id,
        user_id=user_id,
        tokens=response.token_count,              # input + output + reasoning (per Q1 in implementation plan)
        trace_id=current_trace_id(),
    )
    return response
```

For BL-PRD-02 we adopt the proposal in `../implementation-plan.md` §10 Q1: `tokens = input + output + reasoning, *exclusive* of cached-input discount`. That decision is reflected in the helper that extracts `response.token_count` per provider.

### 5.3 Monthly-reset job

```text
monthly_reset(period_yyyy_mm):
  if reset_already_run_for(period): return  (idempotent — checked via a per-period marker doc)
  for each org in organizations/*:
    profile = read billing_profile/profile
    new_window = MonthlyUsageWindow(
      organization_id=org_id,
      period_start=first_of_month_utc(period),
      period_end=first_of_next_month_utc(period),
      tokens_used=0,
      allowance_at_period_start=profile.monthly_token_allowance,
      overage_triggered_at=None,
      notification_75_sent=False,
      notification_exceeded_sent=False,
    )
    write organizations/{org_id}/usage_windows/{period} = new_window
    if status.status == "inactive_overage":
      status.status = "active"; status.reason_message = ""
      invalidate_status_cache(org_id)
      audit "status_changed", metadata={from: "inactive_overage", to: "active", trigger: "monthly_reset"}
  mark reset_already_run_for(period)
```

Per-period marker stored at `billing_monthly_reset_marker/{YYYY-MM}` so re-invocation by Cloud Scheduler retry is a no-op.

### 5.4 Reconciliation script

Run daily via Cloud Scheduler (separate job from monthly reset):

```text
reconcile(date_yyyy_mm_dd):
  weave_total = query Weave for spans on date with attribute "billing.kind=llm_call",
                grouped by (org_id, account_id, user_id), sum(tokens)
  meter_total = read all organizations/*/accounts/*/usage_daily/{date},
                project to (org_id, account_id, by_user[user_id])
  diff = compare(weave_total, meter_total)
  if max(abs(diff)) / weave_total > 0.005:
    post Slack alert with top-10 divergent (org, account, user)
  write organizations/{org_id}/billing_reconciliation/{date} = { weave_total, meter_total, diff_pct }
```

The 0.5% threshold matches the 99.5% accuracy success criterion in the implementation plan §11.

## 6. API contract

### Public

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/billing/{org_id}/usage/current` | Returns `{tokens_used, allowance, period_start, period_end, status}`. Auth: any user with org access. |
| `GET` | `/api/v1/billing/{org_id}/usage/daily?from=YYYY-MM-DD&to=YYYY-MM-DD&breakdown=none\|account\|user` | Returns row array `[{date, tokens, account?, user?}]` ready for the chart. Auth: any user with org access. |

### Internal (OIDC)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/internal/billing/meter-increment` | Body: `{org_id, account_id, user_id, tokens, trace_id}`. Used by the Agentic Harness only — exposed as an endpoint (not just an in-process helper) so future non-Python LLM-calling services can also report. |
| `POST` | `/api/v1/internal/billing/monthly-reset` | Cloud Scheduler-triggered. Idempotent per `YYYY-MM`. |
| `GET` | `/api/v1/internal/billing/status/{org_id}` | Replaces BL-PRD-01's stub with the real implementation backed by `OrganizationStatus`. 30s cache. |

The `/usage/*` endpoints are gated by `billing_show_subscription_ui`. The internal endpoints are unconditional once `billing_enabled` is on.

## 7. Acceptance criteria

1. **Meter increments correctly** — unit test on `meter_increment` with `StubStripe` verifies window/daily/by_user counters all increase by `tokens` for the correct org/account/user/date.
2. **Idempotency on trace_id** — calling `meter_increment` twice with the same `trace_id` in a 24h window mutates state exactly once.
3. **State transitions land at the right thresholds** — pure-function unit tests cover: <75%, =75%, >75%, =100%, >100% boundaries; verify transition + reason_message + notification trigger flags.
4. **30s status cache** — integration test asserts ≤1 Firestore read per org per 30s under load (1000 sequential `check_status` calls). Cache invalidates on overage transition; the very next call after the transition reads fresh.
5. **HTTP 402 mapping** — chat endpoint test: enforce flag on, org over limit → 402 with `{error: "billing_inactive", reason: "...", upgrade_url: "..."}`. Enforce flag off → 200 (observe-only path).
6. **Observe-only mode** — integration test asserts that with `billing_enforce_limits=false`: counter increments, status flips to `inactive_overage`, notification fires, but chat call returns 200 not 402; audit entry has `metadata.observe_only=true`.
7. **75% notification fires once** — cross-the-line test: increment crosses 0.75 → notification sent → flag set → next increment also above 0.75 → no second notification.
8. **Exceeded notification fires once** — same pattern at 1.0 boundary.
9. **Monthly reset is idempotent** — invoke `monthly-reset` for the same period twice; second call is a no-op (marker present); window count unchanged; no duplicate audit entries.
10. **Monthly reset reactivates** — seed an org in `inactive_overage`; run reset; status `active`, reason `""`, cache invalidated, audit `status_changed` written.
11. **Distributed counter under load** — 100 concurrent `meter_increment` calls for the same org sum to the expected total within 1% (intentional Firestore eventual-consistency tolerance, well within meter accuracy budget).
12. **In-flight requests not killed** — integration test: start a streaming chat response; mid-stream a separate increment crosses the limit; the streaming response completes; the *next* request returns 402.
13. **Reconciliation script catches drift** — synthetic test: write a known-divergent meter row; run reconciliation; assert diff_pct reported correctly and alert webhook called when threshold exceeded.
14. **`/usage/current` + `/usage/daily` shapes** — endpoint contract tests; `breakdown` query parameter behaves correctly (`none` returns one row per date; `account` adds account; `user` adds user).
15. **Cloud Scheduler wiring** — Terraform-applied resource exists; OIDC SA can call `/internal/monthly-reset`; manual trigger runs successfully in dev.

## 8. Test plan

### Unit
- State-machine pure functions: every threshold case + every reset case.
- Distributed-counter helpers: write/read round-trip, shard rotation under contention (mocked).
- `BillingInactiveError` → 402 mapping in the API exception handler.
- Notification factories: correct category, correct user fan-out, correct deep-link.
- Trace-id idempotency: re-submission within window is no-op; outside TTL is a fresh increment.

### Integration
- Full meter loop (AC #1 + #2): submit synthetic LLM responses through the Agentic Harness hook; verify counters + status transitions + audit.
- 402 enforcement vs observe-only (AC #5 + #6).
- Notification-once-per-window (AC #7 + #8).
- Monthly reset idempotency + reactivation (AC #9 + #10).
- Concurrency stress (AC #11): 100 parallel increments via the API layer.
- In-flight request not killed (AC #12).
- Reconciliation drift detection (AC #13) — uses a `StubWeave` for the Weave query side.
- Endpoint contracts (AC #14).

### Manual verification
- Dev: run a real chat session through the Agentic Harness in observe-only mode; confirm counters increment in Firestore console; flip enforce flag on; confirm next chat returns 402.
- Trigger monthly reset manually in dev and confirm reactivation.
- Run reconciliation script for yesterday's date; verify report shows zero drift on a clean dev environment.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Meter under-counts (consumer leak: an LLM call is made without going through the Agentic Harness wrapper) | Reconciliation script catches it within 24h; pre-launch we audit every LLM SDK call site and add the wrapper if missing. Code-search lint as part of `make lint`. |
| Meter over-counts (idempotency miss; same trace_id seen twice but TTL evicted record) | TTL is 24h, well above any expected retry window; if drift observed, raise TTL or move to a deterministic dedup key (e.g. hash of `trace_id + span_id`). |
| Status cache stale across multiple API instances | 30s TTL is the upper bound on staleness. Acceptable per `../implementation-plan.md` §9 risk. Consumers (chat, scheduler) tolerate it. Webhook handlers in BL-PRD-03 will explicitly invalidate to avoid the upgrade-staleness UX problem. |
| Cloud Scheduler missed firing | Marker-doc design means a delayed firing still works; alarm if no marker exists by 02:00 UTC on the 1st. |
| In-flight long stream lets an org go far over the limit | Accept. Worst case = 1 large response over the cap. We don't kill streams. If real-world data shows this gets abused, future revisit (BL-PRD-08?) could add per-stream pre-check + budget reservation. |
| Distributed counter shard hot-spot (one shard taking all traffic) | Sub-counter index is hashed from `trace_id`; even distribution proven in load test (AC #11). |
| `OrganizationStatus.reason_message` ends up in user-facing copy that becomes outdated when product copy changes | Reason messages live in a constants file (`billing/messages.py`); single edit point. |
| Notifications spam during a long inactive window | Single notification per category per window (AC #7 + #8). The "you're inactive" banner in the UI (BL-PRD-04) is the persistent surface; notifications fire only on transition. |

### Open questions
- **Q:** What counts as a "token" — confirmed in `../implementation-plan.md` §10 Q1 as `input + output + reasoning, exclusive of cached-input discount`. Decision needed before coding the token-extraction helper. **Proposal:** ratify Q1 proposal in this PRD.
- **Q:** Should the meter increment include tool-use tokens (e.g. tokens spent inside MCP tool execution that go through the LLM)? → **Proposal:** yes, all LLM tokens are counted regardless of caller role; tool-use tokens are LLM tokens. Decide before BL-PRD-04.
- **Q:** Reconciliation alert frequency — daily? Weekly? **Proposal:** daily for the first 30 days post-launch, then weekly once accuracy is proven.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Upstream: [BL-PRD-01](./BL-PRD-01-core-model-stripe-foundation.md)
- Parallel: [BL-PRD-03](./BL-PRD-03-stripe-checkout-subscription-lifecycle.md)
- Downstream: [BL-PRD-04](./BL-PRD-04-subscription-settings-ui-integration.md)
- Trace contract: `docs/trace-structure-spec.md`
- Notifications service: existing
- Distributed counter pattern: [Firestore docs](https://cloud.google.com/firestore/docs/solutions/counters)
- CLAUDE.md rules in scope: PY-1, PY-3, PY-5, PY-7; D-1, D-3, D-4; C-2, C-4; T-1, T-3, T-4, T-5, T-6
