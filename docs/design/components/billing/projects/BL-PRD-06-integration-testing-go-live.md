# BL-PRD-06 — Integration Testing + Sales Handoff + Go-Live

**Status:** Not started
**Owner team:** Billing component team (backend) + Frontend team (sales handoff form polish) + Ops/Finance (rollout coordination)
**Blocked by:** [BL-PRD-01](./BL-PRD-01-core-model-stripe-foundation.md), [BL-PRD-02](./BL-PRD-02-token-meter-monthly-enforcement.md), [BL-PRD-03](./BL-PRD-03-stripe-checkout-subscription-lifecycle.md), [BL-PRD-04](./BL-PRD-04-subscription-settings-ui-integration.md), [BL-PRD-05](./BL-PRD-05-failure-modes-permissions.md)
**Parallel with:** none — this is the integration + go-live phase
**Blocks:** —
**Estimated effort:** 4 days (≈1.5 E2E + reconciliation, ≈1 sales handoff implementation, ≈1 rollout playbook + finance dashboard scaffold, ≈0.5 runbook polish)

---

## 1. Context

By the end of BL-PRD-05, every component is implemented in isolation. This PRD is the integration phase: full-stack E2E coverage of all six state-machine transitions, the actual sales-handoff implementation (the BL-PRD-04 form posts to a contract this PRD fulfills), the production rollout playbook (observe-only meter for 30 days → enforcement for early-access orgs → general availability), the daily reconciliation report graduating from synthetic to real production data, and a minimum viable finance dashboard.

Three things ship that previous PRDs deferred:

1. **Sales handoff implementation** — the BL-PRD-04 form posts to `/sales-handoff`; this PRD lands the actual destination (per `../implementation-plan.md` §10 Q2: choose between HubSpot ticket, email-to-sales, Slack webhook, or a combination). v1 default proposal: email + Slack webhook (cheapest, fastest); HubSpot integration deferred to a follow-up if needed.
2. **Production rollout playbook** — written, reviewed, executed. Defines: observe-only window (30 days), early-access cohort (first 10 design-partner orgs), monitoring criteria for promoting to GA, rollback triggers.
3. **Finance dashboard scaffold** — minimum viable: a Looker Studio (or equivalent) view backed by a SQL view over the `billing_audit` + `billing_stripe_events` collections. Surfaces MRR, churn, conversion-from-Free, refunds-this-month. Single dashboard URL shared with finance.

This PRD also produces the verification report demonstrating production readiness, runs reconciliation for 30 consecutive days, and onboards at least one paying customer entirely through the production UI without manual intervention as the launch acceptance gate.

## 2. Scope

### In scope
- **Full-stack E2E test suite** — covers every state transition end-to-end against the Stripe test-mode account, exercising the production frontend (in CI via Playwright). Scenarios:
  - Free org → checkout → paid (tier 0) → mid-cycle upgrade (tier 5) → mid-cycle downgrade (tier 2, scheduled at period end) → cancel → period rollover → Free.
  - Paid org → exceed allowance → status flips to `inactive_overage` → upgrade tier → status flips to `active` within seconds.
  - Paid org → simulated payment failure (Stripe test-mode invoice retry path) → grace period → exhaustion → `inactive_past_due` → manual card update via Customer Portal → recovery via `invoice.payment_succeeded` → `active`.
  - Free org → exceed allowance → `inactive_overage` → monthly reset → `active`.
  - Slider lands on max → sales-handoff form submitted → sales receives notification → ops uplifts allowance via manual override → `active`.
  - Webhook delivery delayed by 30s → status converges within 60s of delivery.
- **Sales-handoff implementation** — `POST /api/v1/billing/{org_id}/sales-handoff` endpoint:
  - Validates body (per BL-PRD-04 contract).
  - Sends an email via SendGrid to the `sales@ken-e.ai` distribution list (template captured in `sm://billing-sales-handoff-template-id-{env}`), including org name, requesting user, contact email, estimated tokens, anticipated start date, notes.
  - Posts to a Slack webhook (`sm://billing-sales-handoff-slack-{env}`) with the same payload, formatted for an internal-channel surface.
  - Writes a `BillingAuditEntry` with `event="enterprise_handoff_initiated"`, `metadata` containing the request body.
  - Returns 204.
  - Rate-limited (3/day/org) per BL-PRD-05.
- **Daily reconciliation in production** — `reconcile_billing_meter.py` from BL-PRD-02 runs nightly via Cloud Scheduler against the previous day's data, writes a per-day report to `organizations/{org_id}/billing_reconciliation/{date}`, and alerts to Slack on >0.5% drift. This PRD verifies the script runs cleanly for 30 consecutive days as a launch criterion.
- **Finance dashboard scaffold** — minimum viable v1:
  - A SQL view (BigQuery, federating Firestore exports) named `billing_kpis_v1` aggregating MRR (sum of `monthly_price_usd` across `BillingProfile.plan="paid"`), MRR delta (vs. last month), churn rate (canceled in month / paid at start of month), conversion rate (Free→paid in month / Free at start of month), refunds (`manual_override` events with `action="credit_tokens"`), and total tokens consumed.
  - A Looker Studio (or equivalent) dashboard sourced from this view; URL shared with finance.
  - Documented in `docs/design/components/billing/runbooks/finance-dashboard.md`.
- **Production rollout playbook** — `docs/design/components/billing/runbooks/rollout.md`. Phases:
  - **Day 0 (deploy)**: BL-PRD-01..05 deployed; `billing_enabled=true`; `billing_enforce_limits=false` (observe-only); `billing_show_subscription_ui=false` (UI hidden). Meter runs; reconciliation runs nightly; no user-visible behavior change.
  - **Days 1–7 (verify)**: Daily reconciliation reviewed; drift <0.5%; manual chat sessions across staff orgs verified to register correct token counts.
  - **Days 8–30 (extended observe)**: Continue observing; address any reconciliation drift; refine token-extraction helper if needed.
  - **Day 31 (early access)**: `billing_show_subscription_ui=true` for early-access cohort (10 design-partner orgs, allow-listed via flag targeting); `billing_enforce_limits=true` for the same cohort.
  - **Days 31–60 (early-access window)**: Monitor support tickets, billing audit; iterate on UX based on customer feedback.
  - **Day 61 (GA)**: Flip `billing_show_subscription_ui` and `billing_enforce_limits` to all orgs.
- **Rollback triggers + runbook** — `docs/design/components/billing/runbooks/rollback.md`. Defines: what triggers a rollback (e.g. >2% reconciliation drift, >5 customer-reported billing complaints / day, Stripe webhook backlog >5 min), how to execute (flip `billing_enforce_limits=false` first; `billing_show_subscription_ui=false` if UI-side issue; `billing_enabled=false` only as nuclear option since it disables `/internal/status` reads).
- **Verification report** — `docs/design/components/billing/projects/BL-PRD-06-verification-report.md` written after 30 days of clean reconciliation + ≥1 paying customer onboarded. Captures: reconciliation drift over the window, customer count, MRR, incidents (if any), open follow-ups.
- **Runbook polish** — review/update every runbook from BL-PRDs 01–05; ensure they are current with shipped behavior; add cross-references; landing index at `docs/design/components/billing/runbooks/README.md`.

### Out of scope
- HubSpot or Salesforce CRM integration for sales handoff — defer to a follow-up PRD if v1 email + Slack proves insufficient (proposal in §9 Q1).
- Self-serve enterprise invoice billing — handled today by ops setting up Stripe Invoicing manually; full self-serve flow deferred to a future BL-PRD-07.
- Annual billing / discounts / promo codes — non-goals (`../implementation-plan.md` §8).
- Customer-facing API (programmatic access to usage) — out of scope.
- Reseller / partner billing — out of scope.
- Pricing-tier v2 migration — see `../implementation-plan.md` §10 Q11; this PRD launches v1 only.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **All BL-PRDs 01–05** | Every endpoint, handler, and runbook from previous phases. | This component |
| **W&B Weave** | Reconciliation source-of-truth for token counts (already wired in BL-PRD-02). | `docs/trace-structure-spec.md` |
| **SendGrid** | Sales-handoff email template and `sales@ken-e.ai` distribution list. | `api/CLAUDE.md` Email Service Setup |
| **Slack** | `sm://billing-sales-handoff-slack-{env}` webhook for #sales-handoffs internal channel. | Secret Manager |
| **BigQuery + Firestore export** | Daily Firestore export → BigQuery dataset feeding the `billing_kpis_v1` SQL view. | `deployment/terraform/` |
| **Looker Studio (or equivalent)** | Finance dashboard hosted there; shared with finance via Google Workspace group. | TBD |
| **Cloud Scheduler** | Nightly reconciliation job (already provisioned in BL-PRD-02; this PRD verifies in production). | `deployment/terraform/cloud_scheduler.tf` |
| **Feature Flags** | `billing_enabled`, `billing_enforce_limits`, `billing_show_subscription_ui` — already registered; this PRD operates them per the rollout playbook. | `feature-flags/` component |

## 4. Data contract

### No new persisted shapes

This PRD ships no new Pydantic models or Firestore collections. All shapes already exist from BL-PRDs 01–05.

### Sales-handoff request body (defined in BL-PRD-04, fulfilled here)

```python
class SalesHandoffRequest(BaseModel):
    estimated_monthly_tokens: int            # ≥ 81_000_000
    billing_contact_email: EmailStr
    anticipated_start_date: date | None
    notes: str                               # ≤ 2000 chars
```

### Finance KPI SQL view (`billing_kpis_v1`)

```sql
-- One row per (period_yyyy_mm). Refreshed daily.
SELECT
  FORMAT_DATE('%Y-%m', period_start) AS period_yyyy_mm,
  -- MRR: sum of monthly prices for paid orgs at end of period
  SUM(IF(plan = 'paid', monthly_price_usd, 0)) AS mrr_usd,
  -- Conversion: Free at start → paid by end
  SUM(IF(plan_at_period_start = 'free' AND plan = 'paid', 1, 0))
    / NULLIF(SUM(IF(plan_at_period_start = 'free', 1, 0)), 0) AS free_to_paid_conversion,
  -- Churn: paid at start → free by end
  SUM(IF(plan_at_period_start = 'paid' AND plan = 'free', 1, 0))
    / NULLIF(SUM(IF(plan_at_period_start = 'paid', 1, 0)), 0) AS churn_rate,
  -- Refunds via manual override
  (SELECT COUNT(*) FROM billing_audit
    WHERE event = 'manual_override' AND JSON_EXTRACT_SCALAR(metadata, '$.action') = 'credit_tokens'
    AND timestamp BETWEEN period_start AND period_end) AS refunds_in_period,
  SUM(tokens_used) AS total_tokens_consumed
FROM (
  -- per-org daily snapshots from billing_profile + usage_windows joined
  ...
)
GROUP BY period_yyyy_mm
```

The exact view DDL is captured in `runbooks/finance-dashboard.md` and the Terraform-managed BigQuery view is part of this PRD's deliverables.

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create | `api/src/kene_api/billing/sales_handoff.py` — endpoint handler + email + Slack post |
| Modify | `api/src/kene_api/routers/billing.py` — wire `/sales-handoff` to the new handler |
| Modify | `deployment/terraform/secret_manager.tf` — populate `billing-sales-handoff-template-id-{env}` and `billing-sales-handoff-slack-{env}` |
| Create | `deployment/terraform/bigquery.tf` (or add to existing) — `billing_kpis_v1` SQL view + scheduled query |
| Create | `docs/design/components/billing/runbooks/README.md` — runbook index |
| Create | `docs/design/components/billing/runbooks/rollout.md` |
| Create | `docs/design/components/billing/runbooks/rollback.md` |
| Create | `docs/design/components/billing/runbooks/finance-dashboard.md` |
| Create | `docs/design/components/billing/runbooks/customer-overbilled.md` — handles "I was charged the wrong amount" |
| Create | `docs/design/components/billing/runbooks/webhook-outage.md` — "Stripe webhooks aren't arriving" |
| Create | `docs/design/components/billing/projects/BL-PRD-06-verification-report.md` — populated post-launch |
| Update | every prior runbook (`manual-override.md`, `stripe-outage-response.md`, `webhook-replay.md`, `webhook-secret-rotation.md`, `webhook-debugging.md`, `stripe-portal-config.md`, `stripe-dev-setup.md`) for cross-references and current accuracy |
| Create | `api/tests/integration/billing/test_sales_handoff_e2e.py` |
| Create | `api/tests/e2e/billing/test_full_lifecycle_playwright.py` (or wherever Playwright suites live) — six scenarios from §2 |

### 5.2 Sales-handoff handler

```text
POST /api/v1/billing/{org_id}/sales-handoff:
  1. Permission check: `OrgRole.ADMIN` (per BL-PRD-05 §1 — owner/admin distinction collapsed).
  2. Rate-limit check: 3/day/org (per BL-PRD-05).
  3. Validate body.
  4. Resolve org name and requesting user from auth context.
  5. Send email:
     - To: sales@ken-e.ai
     - Subject: "Enterprise inquiry: {org_name} — {estimated_monthly_tokens:,} tokens/mo"
     - Body: structured fields from request + org/user context
     - Template: billing-sales-handoff-template-id-{env}
  6. POST to Slack webhook with formatted message.
  7. write_billing_audit(
       event="enterprise_handoff_initiated",
       actor_id=requesting_user.id,
       metadata={
         "estimated_monthly_tokens": ...,
         "billing_contact_email": ...,
         "anticipated_start_date": ...,
         "notes_excerpt": notes[:200],
       },
     )
  8. Return 204.
```

If either email or Slack fails, log the failure but do not fail the request — the audit entry is the source-of-truth backup. (A retry job, if needed, can pull failures from audit.)

### 5.3 Production rollout sequence (operational)

```text
Day 0 (deploy):
  - feature flag: billing_enabled=true (all orgs)
  - feature flag: billing_enforce_limits=false (all orgs)
  - feature flag: billing_show_subscription_ui=false (all orgs)
  - meter runs in observe-only; UI hidden
  - reconciliation script scheduled nightly

Days 1–7:
  - daily review of reconciliation reports (manual; checked into a shared doc)
  - investigate any drift >0.5%; fix root cause; re-baseline

Days 8–30:
  - continue observe-only; gather token-consumption distribution per org
  - finance reviews KPI dashboard (no real revenue yet; sanity-check shape)

Day 31:
  - identify 10 design-partner orgs; add to early-access flag-target group
  - feature flag: billing_show_subscription_ui=true (early-access targets)
  - feature flag: billing_enforce_limits=true (early-access targets)
  - support team on standby; daily standup for the first week

Days 31–60:
  - track: support tickets, abandoned-checkout rate, time-to-first-paid-conversion
  - if >5 unresolved billing complaints/day → pause expansion; rollback if necessary

Day 61 (GA):
  - feature flag: billing_show_subscription_ui=true (all orgs)
  - feature flag: billing_enforce_limits=true (all orgs)
  - announce in product changelog
  - finance dashboard live in weekly business review
```

### 5.4 Verification report criteria (BL-PRD-06-verification-report.md)

The launch is "done" when the report can affirm:

- 30 consecutive nights of reconciliation drift <0.5%.
- ≥1 paying customer onboarded entirely self-serve (no manual override required).
- Zero PCI findings in the launch security review.
- All P0 / P1 bugs from the early-access window resolved.
- Finance dashboard reviewed and signed off in a finance team meeting.
- Rollback runbook executed in dry-run at least once (table-top exercise; no real rollback).

## 6. API contract

### Public

| Method | Path | Status |
|---|---|---|
| `POST` | `/api/v1/billing/{org_id}/sales-handoff` | Implementation — contract per BL-PRD-04 §4. |

No new endpoints beyond `/sales-handoff`; this PRD is mostly testing, runbooks, and rollout work.

## 7. Acceptance criteria

1. **Six E2E scenarios pass** — Playwright suite covers every scenario in §2; runs in CI on every commit; runs against Stripe test mode.
2. **Sales-handoff endpoint works** — org `admin` POSTs valid form → email sent (verified via SendGrid event log fixture) → Slack message posted (verified via webhook-mock fixture) → audit entry written with `event="enterprise_handoff_initiated"`. Non-admin (org `member`) → 403. Over rate limit → 429. Invalid body (e.g. tokens <81M) → 400.
3. **Reconciliation runs nightly in production** — Cloud Scheduler invokes the script; report appears in `organizations/{org_id}/billing_reconciliation/{date}` for every active org; alert fires on >0.5% drift.
4. **30-day clean reconciliation** — verification report shows 30 consecutive nights with all-org max drift <0.5%. (Launch acceptance gate, not coded gate.)
5. **Finance dashboard live** — `billing_kpis_v1` BigQuery view exists; Looker Studio dashboard shared with the finance team; populated with at least one full month of data before GA.
6. **Rollout playbook executed** — phase-by-phase, with documented checkpoints; the early-access cohort is enabled exactly per the playbook; expansion to GA gated on the playbook's criteria.
7. **Rollback runbook table-top exercise complete** — team walks through a hypothetical rollback; runbook is updated with any gaps found.
8. **All runbooks reviewed and current** — every runbook from BL-PRDs 01–05 is reviewed; any drift from shipped behavior corrected; runbook index landing page exists.
9. **Verification report written + signed off** — `BL-PRD-06-verification-report.md` populated and reviewed by Billing team lead, Finance lead, and Engineering manager.
10. **First self-serve paying customer onboarded** — at least one customer completes Free → checkout → paid → uses tokens → receives invoice without any manual intervention. Captured in the verification report.

## 8. Test plan

### Integration / E2E
- Playwright (or equivalent) suite covering the six scenarios in §2.
- Sales-handoff endpoint integration test (AC #2).
- Reconciliation script integration test using a synthetic Weave fixture (AC #3); verifies report shape, alert path, idempotency for re-runs of the same date.

### Operational
- Rollback table-top exercise (AC #7) — schedule a 1-hour session; document.
- Finance dashboard review (AC #5) — formal sign-off.
- Runbook walk-through (AC #8) — each runbook executed end-to-end at least once in staging.

### Manual verification
- Submit a real sales-handoff form in staging; confirm email lands at sales address; confirm Slack message in the configured channel.
- Run the rollout playbook in staging end-to-end; confirm flag transitions take effect; verify UX at each phase.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Reconciliation drift discovered after enforcement is enabled | Observe-only window is exactly to surface this. Drift >0.5% blocks the early-access flip; >2% during early-access triggers immediate rollback to observe-only. |
| Sales-handoff backlog: no one acks the email/Slack | Sales team owner named in the runbook; SLA: 1 business day. Escalation path documented. |
| Finance dashboard query is slow / expensive on BigQuery | Scheduled query refreshes daily, not on-demand; cost monitored; optimize the view if it exceeds ~$10/month. |
| Early-access cohort not representative of GA traffic | Cohort selection criteria documented in rollout playbook (mix of org sizes, geographies, usage patterns). Expand cohort progressively before GA, not in one jump. |
| Rollback flips `billing_enforce_limits=false` but customers have already been charged | Rollback only stops *new* enforcement; previously-charged invoices stand. Refund flow is via `manual_override` `credit_tokens` (already implemented in BL-PRD-05). |
| Verification report becomes a vanity exercise vs. real diligence | Sign-off requires three roles (lead, finance, engineering); each has independent acceptance criteria; missing any blocks GA. |
| Pricing-tier v2 needed soon after launch | Per `../implementation-plan.md` §10 Q11: existing subscriptions stay on v1; new subscribers see v2; UI prompts opt-in. Out of scope for v1 GA; flagged for follow-up. |
| HubSpot integration becomes urgent (sales team can't process inbound from Slack/email) | Defer to a follow-up PRD; the substrate (audit + structured request body) makes adding a CRM integration straightforward. |

### Open questions
- **Q:** Sales-handoff destination — the `../implementation-plan.md` §10 Q2 proposal is "email + Slack webhook" for v1. Confirm vs. HubSpot. → **Proposal:** ratify email + Slack for v1 to ship faster; revisit at first sign of friction.
- **Q:** Sales-handoff form fields — final shape per `../implementation-plan.md` §10 Q9. The schema in BL-PRD-04 §4 covers (estimated_tokens, billing_contact, anticipated_start_date, notes). → Ratify before shipping the production form.
- **Q:** Finance dashboard tool — Looker Studio (free, basic) vs. existing BI stack. → Decide based on what finance already uses.
- **Q:** Early-access cohort size — 10 orgs proposed. Could be 5 or 20. → Decide based on support team bandwidth at launch.
- **Q:** GA announcement copy + changelog wording → defer to product/marketing.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Upstream: [BL-PRD-01](./BL-PRD-01-core-model-stripe-foundation.md), [BL-PRD-02](./BL-PRD-02-token-meter-monthly-enforcement.md), [BL-PRD-03](./BL-PRD-03-stripe-checkout-subscription-lifecycle.md), [BL-PRD-04](./BL-PRD-04-subscription-settings-ui-integration.md), [BL-PRD-05](./BL-PRD-05-failure-modes-permissions.md)
- Downstream: — (final phase)
- Stripe docs: [Test mode](https://stripe.com/docs/testing), [Smart Retries](https://stripe.com/docs/billing/revenue-recovery/smart-retries)
- Email service: `api/CLAUDE.md` Email Service Setup
- Trace contract: `docs/trace-structure-spec.md`
- CLAUDE.md rules in scope: PY-1, PY-3, PY-7; D-3, D-5; C-2, C-4; T-3, T-4, T-5
