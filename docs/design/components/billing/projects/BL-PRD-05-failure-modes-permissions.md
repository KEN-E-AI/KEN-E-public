# BL-PRD-05 — Failure Modes + Permissions

**Status:** Not started
**Owner team:** Billing component team (backend) + Platform team (rate limiting + ops tooling)
**Blocked by:** [BL-PRD-03](./BL-PRD-03-stripe-checkout-subscription-lifecycle.md)
**Parallel with:** [BL-PRD-04](./BL-PRD-04-subscription-settings-ui-integration.md) — UI work and backend hardening don't block each other; BL-PRD-04 ships against the BL-PRD-03 endpoints with no admin gate and BL-PRD-05 layers DM-PRD-07's `OrgRole.ADMIN` gate on later
**Blocks:** BL-PRD-06
**Estimated effort:** 3 days backend (≈1.5 admin-gate wiring + manual override, ≈1 outage + rate-limit, ≈0.5 webhook replay tooling)

---

## 1. Context

By the end of BL-PRD-03 + BL-PRD-04, the entire happy path works: orgs can self-serve checkout, upgrade, downgrade, and cancel through a UI wired to Stripe. This PRD adds the safety rails the system needs before going to production with paying customers.

Five hardening surfaces ship here:

1. **Org-admin authorization** on every state-changing billing endpoint (upgrade, downgrade, cancel, customer portal, sales handoff). Org members get read access only. Authorization rides on DM-PRD-07's `OrgRole` enum (`admin | member`) and `require_role(OrgRole.ADMIN, scope="org")` dependency — Billing does not maintain its own role enum.
2. **Manual override admin endpoint** for internal staff to credit-back tokens, temporarily uplift the cap, or force a downgrade — every action mandatorily writes a `BillingAuditEntry` with a reason field.
3. **Stripe outage handling** — explicit assertion (with tests) that no enforcement decision ever calls Stripe live; gating decisions read only the materialized `OrganizationStatus`. Outage degrades upgrade flow only, not active customers.
4. **Webhook replay tooling** — operator command to re-process a date range from `billing_stripe_events` by re-invoking the relevant handler. Used when a handler bug is fixed and we need to re-apply stuck events.
5. **Rate limits** on `/checkout-session` and `/sales-handoff` to prevent abuse (cheap to call, expensive to ignore; sales-handoff in particular touches a CRM ticket).

This PRD also formalizes the "non-admin attempting to upgrade" UX in the frontend: BL-PRD-04 didn't gate the button visually, so the backend rejection here triggers a UI hint that the upgrade requires an org admin.

> **Role-model decision:** earlier drafts of this PRD proposed a 3-value Billing-specific enum (`owner / admin / member`) with `owner`-only cancel/downgrade and a `BILLING_ALLOW_ADMIN_UPGRADE` env-var fallback. With KEN-E pre-production and DM-PRD-07's `OrgRole` only carrying two values (`admin / member`), Billing collapses to a single `admin` role for all state-changing actions. Multi-admin orgs coordinate destructive actions out-of-band; the audit trail (DM-PRD-07) gives ops the data to detect when this becomes a problem and re-introduce an `owner` tier. The `BILLING_ALLOW_ADMIN_UPGRADE` env var is removed.

## 2. Scope

### In scope
- **Org-admin authorization** (via DM-PRD-07's `require_role(OrgRole.ADMIN, scope="org")`) on:
  - `POST /api/v1/billing/{org_id}/checkout-session`
  - `POST /api/v1/billing/{org_id}/subscription/change`
  - `POST /api/v1/billing/{org_id}/subscription/cancel`
  - `POST /api/v1/billing/{org_id}/customer-portal-session`
  - `POST /api/v1/billing/{org_id}/sales-handoff` (BL-PRD-06 contract; permission landed here)
- **Read-only access** for any user with org membership: `GET /profile`, `GET /usage/current`, `GET /usage/daily`, `GET /pricing-tiers`, `GET /bff/billing/status/{org_id}` — open to all members (uses `require_role(OrgRole.MEMBER, scope="org")`). Pricing-tiers is fully public.
- **Permission-denied response shape** — 403 with `{error: "billing_role_required", required_role: "admin", actor_role: "<role>"}`. Frontend uses this to render a "Ask your org admin to upgrade" inline message + reveal a "Notify admin" button (sends an in-app notification to the org's admins; future polish, contract exposed here).
- **Manual override admin endpoint** — `POST /api/v1/internal/billing/{org_id}/manual-override`. OIDC-authed, restricted to a hard-coded internal-staff allow-list (group claim or service-account-with-staff-claim). Body:
  ```json
  {
    "action": "credit_tokens" | "uplift_cap" | "force_downgrade" | "force_status",
    "params": { ... },
    "reason": "Customer reported double-charge on incident #1234"
  }
  ```
  Mandatory `reason` ≥ 20 characters. Every call writes a `manual_override` audit entry capturing the actor, action, params, and reason. Actions:
  - `credit_tokens`: subtract N from current `MonthlyUsageWindow.tokens_used`; if status was `inactive_overage` and new usage <100%, flip back to `active`.
  - `uplift_cap`: temporarily raise `MonthlyUsageWindow.allowance_at_period_start` by N tokens for the current month only (resets to `BillingProfile.monthly_token_allowance` on next monthly reset).
  - `force_downgrade`: end the Stripe Subscription immediately (proration credits flow per Stripe defaults) and revert the org to Free.
  - `force_status`: set `OrganizationStatus.status` to a specific value with a custom `reason_message`. Used for incident response (e.g. "force everyone to active during a Stripe outage we caused").
- **Stripe outage hardening** — code-review gate + integration tests that assert no enforcement-path code reaches `stripe.*` calls. The list of allowed `stripe.*` callsites is whitelisted in `api/src/kene_api/billing/_stripe_callsites.py` and a CI lint enforces no other module imports the Stripe SDK directly. Status reads always go through `billing.check_status` → materialized doc → never Stripe.
- **Stripe outage degradation** — explicit error handling on `/checkout-session`, `/subscription/change`, `/customer-portal-session`: on any `stripe.error.APIConnectionError` or 5xx from Stripe, return 503 with `{error: "stripe_unavailable", retry_after_seconds: 60}`. Frontend renders "Try again in a moment". No state mutated.
- **Webhook replay tooling** — `api/scripts/replay_billing_webhooks.py --from YYYY-MM-DD --to YYYY-MM-DD [--event-type ...] [--org-id ...] [--dry-run]`. Reads `billing_stripe_events` rows in the date range, re-invokes the appropriate handler (handlers are already idempotent per BL-PRD-03), reports outcomes. Used after a handler bug fix.
- **Rate limits** — middleware applied per (org_id, endpoint):
  - `/checkout-session`: 10 / hour / org
  - `/subscription/change`: 20 / hour / org (allow rapid slider play before commit isn't an issue since each click is a separate Stripe call only after confirm)
  - `/sales-handoff`: 3 / day / org
  - `/customer-portal-session`: 10 / hour / org
  - Implementation: existing rate-limit middleware (if present) or a small Firestore-backed counter. Returns 429 with `{retry_after_seconds}`.
- **Audit completeness** — verification test that every state-changing endpoint produces a `BillingAuditEntry` with the actor's `user_id` (or `system:webhook`, `system:manual_override`); endpoints without an audit fail CI.
- **Two-secret webhook signing rotation support** — `STRIPE_WEBHOOK_SECRET_PRIMARY` + `STRIPE_WEBHOOK_SECRET_SECONDARY` env vars (per `../implementation-plan.md` §9 risk row). Webhook handler tries both during a rotation window. Documented in runbook.
- **Runbook updates**:
  - `runbooks/manual-override.md` — when and how internal staff use it.
  - `runbooks/stripe-outage-response.md` — what to do, what to communicate, how to resume.
  - `runbooks/webhook-replay.md` — when to use the replay tool.
  - `runbooks/webhook-secret-rotation.md` — two-secret rotation process.

### Out of scope
- Sales-handoff implementation — BL-PRD-06 (this PRD only secures the endpoint and rate-limits it).
- Finance dashboards / MRR reporting — BL-PRD-06.
- Customer-facing refund UX — refunds are an ops process via manual override + Stripe Dashboard refund.
- SSO / enterprise auth — out of scope for billing; uses whatever the existing auth substrate provides.
- Anti-fraud beyond rate limits (CAPTCHAs, behavioral signals) — out of scope.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[BL-PRD-03](./BL-PRD-03-stripe-checkout-subscription-lifecycle.md)** | All state-changing endpoints; `billing_stripe_events` journal; webhook handlers (already idempotent). | This component |
| **[BL-PRD-02](./BL-PRD-02-token-meter-monthly-enforcement.md)** | `MonthlyUsageWindow`, `OrganizationStatus`, `invalidate_status_cache`. Used by manual-override actions. | This component |
| **DM-PRD-07 (Roles + Audit substrate)** | `OrgRole` enum (`admin \| member`) + `require_role(OrgRole.ADMIN, scope="org")` FastAPI dependency. Reads `organizations/{org_id}/members/{user_id}.role`. Billing's permission middleware is a thin wrapper around this. | `../../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md` §4.1, §6 |
| **Internal-staff allow-list** | Either a Firestore-backed list (`internal_staff/{user_id}`) or a group claim from the auth provider. Decided in §9 Q1. | TBD |
| **Existing rate-limit middleware** | If present, reuse. If not, ship a thin Firestore-backed limiter scoped to billing endpoints only (low traffic, OK to be naive). | `api/src/kene_api/middleware/` |
| **Notifications** | `Org Owner Action Required` category for "Notify owner" button (frontend wiring deferred; contract exposed here). | Existing notifications service |

## 4. Data contract

### No new persisted shapes

Changes are middleware + endpoints + audit-entry conventions. The `BillingAuditEntry.event` Literal (defined in BL-PRD-01) already includes `manual_override`; this PRD wires it to a real endpoint.

### Manual-override request body

```python
class ManualOverrideRequest(BaseModel):
    action: Literal["credit_tokens", "uplift_cap", "force_downgrade", "force_status"]
    params: dict                              # action-specific; validated per action below
    reason: str                               # min 20 chars; max 500
```

Per-action `params`:

| Action | Params |
|---|---|
| `credit_tokens` | `{tokens: int}` (positive) |
| `uplift_cap` | `{tokens: int}` (positive); applies to current month only |
| `force_downgrade` | `{}` (empty) |
| `force_status` | `{status: OrganizationStatus.status, reason_message: str}` |

### Permission model (enforced)

| Endpoint | Required role (DM-PRD-07's `OrgRole`) |
|---|---|
| `GET /pricing-tiers` | (public) |
| `GET /profile`, `GET /usage/*`, `GET /bff/billing/status/{org_id}` | any org member (`OrgRole.MEMBER`) |
| `POST /checkout-session`, `POST /subscription/change` | `OrgRole.ADMIN` |
| `POST /subscription/cancel` | `OrgRole.ADMIN` |
| `POST /customer-portal-session` | `OrgRole.ADMIN` |
| `POST /sales-handoff` | `OrgRole.ADMIN` |
| `POST /internal/billing/{org_id}/manual-override` | internal staff only (`@ken-e.ai` claim) |

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Modify | `api/src/kene_api/routers/billing.py` — apply DM-PRD-07's `require_role(OrgRole.ADMIN, scope="org")` to every state-changing endpoint; `require_role(OrgRole.MEMBER, scope="org")` to read endpoints; add `/internal/billing/{org_id}/manual-override` |
| Create | `api/src/kene_api/billing/manual_override.py` — handler + per-action validators |
| Create | `api/src/kene_api/billing/_stripe_callsites.py` — registry of allowed Stripe-import modules |
| Create | `api/scripts/lint/check_stripe_imports.py` — CI lint enforcing the registry |
| Create | `api/src/kene_api/billing/rate_limit.py` — billing-specific Firestore-backed limiter (or wrapper over existing middleware) |
| Modify | `api/src/kene_api/billing/webhooks.py` — multi-secret signature verification |
| Create | `api/scripts/replay_billing_webhooks.py` |
| Create | `docs/design/components/billing/runbooks/manual-override.md` |
| Create | `docs/design/components/billing/runbooks/stripe-outage-response.md` |
| Create | `docs/design/components/billing/runbooks/webhook-replay.md` |
| Create | `docs/design/components/billing/runbooks/webhook-secret-rotation.md` |
| Create | `api/tests/unit/billing/test_manual_override.py`, `test_rate_limit.py` (permission tests live in DM-PRD-07's `test_rbac_role_gate.py`) |
| Create | `api/tests/integration/billing/test_admin_only_endpoints.py`, `test_manual_override_audit.py`, `test_webhook_two_secret_rotation.py`, `test_stripe_outage_degradation.py`, `test_webhook_replay_tool.py` |

### 5.2 Permission middleware (thin wrapper over DM-PRD-07)

```python
from kene_api.dependencies.rbac import require_role
from kene_api.models.role_models import OrgRole

# Applied as a Depends(...) on each route. No Billing-specific role enum;
# all gating goes through DM-PRD-07's require_role.
require_org_admin = require_role(OrgRole.ADMIN, scope="org")
require_org_member = require_role(OrgRole.MEMBER, scope="org")
```

DM-PRD-07's `require_role(...)` raises `HTTPException(403, detail={"error": "billing_role_required", "required_role": "admin", "actor_role": "<role>"})` on rejection (the `error` key is component-specific and parameterized by the calling component). Billing has no separate middleware to maintain.

### 5.3 Manual override flow

```text
POST /internal/billing/{org_id}/manual-override:
  1. Verify caller is in internal-staff allow-list. Else 403.
  2. Validate body: action ∈ Literal; params per action; reason ≥20 chars.
  3. Dispatch action:
     - credit_tokens(tokens):
         atomically: window.tokens_used = max(0, window.tokens_used - tokens)
         if status was "inactive_overage" and new usage <100%:
           status.status = "active"; reason_message = ""
           invalidate_status_cache(org_id)
     - uplift_cap(tokens):
         atomically: window.allowance_at_period_start += tokens
         if status was "inactive_overage" and new usage <100%:
           status.status = "active"; ...
     - force_downgrade():
         call subscription/cancel logic with cancel_at_period_end=False (immediate)
         BillingProfile → free; allowance → 500K
     - force_status(status, reason_message):
         status.status = status; status.reason_message = reason_message
         invalidate_status_cache(org_id)
  4. write_billing_audit(
       event="manual_override",
       actor_id=staff_user.id,
       metadata={action, params, reason, prior_state: ...}
     )
  5. Return 204.
```

Every action reads prior state into the audit metadata so an investigation can reconstruct what changed.

### 5.4 Stripe-import lint

```python
# _stripe_callsites.py
ALLOWED_STRIPE_IMPORTS = {
    "api/src/kene_api/billing/stripe_client.py",
    "api/src/kene_api/billing/checkout.py",
    "api/src/kene_api/billing/subscription.py",
    "api/src/kene_api/billing/portal.py",
    "api/src/kene_api/billing/webhooks.py",
}
```

CI lint walks the codebase, finds every `import stripe` or `from stripe import …`, and fails if the file isn't in the allow-list. Adding a new caller requires updating the registry, which forces a code review.

### 5.5 Webhook two-secret signature verification

```python
def verify_signature(raw_body: bytes, signature: str) -> stripe.Event:
    primary = secrets.get("stripe-webhook-secret-primary-{env}")
    secondary = secrets.get("stripe-webhook-secret-secondary-{env}", default=None)
    for secret in [primary, secondary]:
        if not secret:
            continue
        try:
            return stripe.Webhook.construct_event(raw_body, signature, secret)
        except stripe.error.SignatureVerificationError:
            continue
    raise SignatureVerificationError("no valid signature")
```

During rotation: ops adds the new secret as `secondary`, configures Stripe to start sending with the new key, waits for the rollover window (24h), then promotes secondary→primary and deletes the old.

### 5.6 Rate limit shape

Firestore-backed sliding window (per (org, endpoint)) is sufficient given low traffic:

```text
billing_rate_limits/{org_id}/{endpoint}:
  events: [timestamp, timestamp, ...]   (capped to last N within window)
```

On each request: append now; trim out-of-window; if count exceeds limit, return 429 with `retry_after_seconds = window - (now - oldest)`.

## 6. API contract

### Public

| Method | Path | Change |
|---|---|---|
| `POST /checkout-session`, `/subscription/change`, `/subscription/cancel`, `/customer-portal-session`, `/sales-handoff` | Add `Depends(require_role(OrgRole.ADMIN, scope="org"))` per role table. 403 + structured body on rejection. 429 on rate-limit. 503 on Stripe outage. |

### Internal

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/internal/billing/{org_id}/manual-override` | OIDC + internal-staff allow-list. Mandatory `reason`. Audit on every call. |

No new public contracts; this PRD layers permission + failure-mode behavior on existing endpoints.

## 7. Acceptance criteria

1. **Org-admin enforced** — non-admin POST to `/checkout-session`, `/subscription/change`, `/subscription/cancel`, `/customer-portal-session`, `/sales-handoff` → 403 with `{error: "billing_role_required", required_role: "admin", actor_role: "member"}`. Admin POST → 200 / 204.
2. **Read-only endpoints open to all members** — member GET `/profile`, `/usage/*` → 200; non-member → 403.
3. **(slot retained for future role-tier reintroduction; intentionally empty)**
4. *(slot retained — see #3)*
5. **Manual override succeeds with audit** — internal-staff POST `/manual-override action="credit_tokens"` → 204; audit entry written with `event="manual_override"`, full `metadata.action/params/reason/prior_state`. Non-staff caller → 403.
6. **Manual override `reason` validation** — request with `reason="too short"` → 400 `{error: "reason_too_short"}`.
7. **Manual override `credit_tokens` reactivates** — seed org `inactive_overage` at 110%; credit 20% worth of tokens; status flips to `active`; cache invalidated; subsequent chat returns 200.
8. **Manual override `force_downgrade`** — paid org → force_downgrade → Stripe Subscription canceled immediately; org plan = free; allowance = 500K; audit captured.
9. **Stripe-import lint** — adding `import stripe` to a non-allowlisted file fails CI.
10. **Stripe outage degradation** — `StubStripe` set to raise `stripe.error.APIConnectionError` on `checkout.Session.create`; frontend POST → 503 with `{error: "stripe_unavailable", retry_after_seconds: 60}`. Existing customers' chat unaffected (no Stripe call on the read path; verified by trace).
11. **Webhook two-secret rotation** — request signed with secondary secret accepted while primary is set; primary-then-secondary fallback path verified.
12. **Webhook replay tool** — replay a date range → handlers re-invoked → idempotency journal reflects re-processing → state unchanged for already-processed events; state corrected for events that previously failed.
13. **Rate limit on `/checkout-session`** — 11th call within an hour for the same org → 429 with `retry_after_seconds`.
14. **Rate limit on `/sales-handoff`** — 4th call within a day for the same org → 429.
15. **Audit completeness** — automated test enumerates every state-changing endpoint; for each, makes a successful call; asserts a corresponding `BillingAuditEntry` row exists with non-empty `actor_id`.

## 8. Test plan

### Unit
- (Role-gate unit tests live in DM-PRD-07's `test_rbac_role_gate.py` — Billing inherits behavior; integration tests below verify wiring.)
- Manual-override per-action validators (param shape, reason length).
- Each manual-override action's pure logic (state transitions independent of Firestore).
- Stripe-import lint against synthetic fixtures.
- Rate-limit window math: under, at, over the threshold; window expiry.

### Integration
- Org-admin enforcement on every state-changing endpoint (AC #1, #2).
- Manual override end-to-end (AC #5, #6, #7, #8).
- Stripe outage degradation (AC #10) — uses `StubStripe` fault injection.
- Webhook two-secret verification (AC #11).
- Webhook replay (AC #12).
- Rate limits (AC #13, #14).
- Audit completeness sweep (AC #15).

### Manual verification
- Run replay tool against staging for a known recent date range; confirm idempotent behavior in audit.
- Trigger a synthetic Stripe outage by pointing the SDK at an unreachable URL; confirm 503 surface in the UI without breaking active sessions.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Internal-staff allow-list misconfigured, allowing manual-override to non-staff | Allow-list source is single-sourced per env; staging vs. prod isolation; deploy-time check that the list is non-empty and references real users. |
| Manual override accidentally permanent | All actions write a full prior-state snapshot; ops doc covers reversal. |
| Sole admin leaves the company; no remaining admin to upgrade | Org-admin promotion (managed via DM-PRD-07's member-CRUD API, not here) is the recovery path. Super-admin (`@ken-e.ai`) can also use `/internal/billing/{org_id}/manual-override` to keep the org running while a new admin is appointed. |
| Rate limits trip a legitimate sales-handoff retry | 3/day is generous for a single contact event; documented in runbook. Internal staff can use manual override to bypass via `force_status` if needed (extreme). |
| Two-secret rotation window leaves a stale secondary indefinitely | Rotation runbook mandates secondary deletion within 7 days; reminder in runbook + Cloud Scheduler alarm if both are populated for >14 days. |
| Webhook replay tool re-fires emails / notifications | Handlers' notification + email side effects need to be replay-safe. Design choice: on replay, suppress side effects via a `--no-side-effects` flag; default is to replay everything (matches the "fix bug, recover state" use case). Documented. |
| Stripe-import lint becomes annoying for legitimate new callsites | Adding a file to the allow-list is a one-line PR; reviewers gate. |
| 403 response shape leaks role info to a hostile actor | Role disclosure is limited to org members (auth required to even reach the 403); acceptable. |
| Cross-region latency on Firestore-backed rate limit | Rate-limit doc lives in same region as API; no cross-region reads. |

### Open questions
- **Q:** Internal-staff allow-list source — Firestore (`internal_staff/{user_id}`) or auth-provider group claim? → **Proposal:** auth-provider group claim if available; else Firestore allow-list with rotation runbook. Decide before coding the dependency.
- **Q:** Should we re-introduce an `OrgRole.OWNER` tier for cancel-protection at some future scale? → **Defer.** Track via the audit-trail signal — if multi-admin orgs become common and an accidental cancel is observed, add the tier in a follow-up DM-PRD update + a Billing PRD update.
- **Q:** Should manual override `force_downgrade` be available, or always go through the customer's own cancel flow? → **Proposal:** keep it for incident response (e.g. payment processor said "stop charging this customer"). Audit + reason ensure traceability.
- **Q:** Rate-limit storage — Firestore is fine for low-traffic billing endpoints, but if existing middleware uses Redis or a similar in-memory store, prefer that. → Spike before coding.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Upstream: [BL-PRD-03](./BL-PRD-03-stripe-checkout-subscription-lifecycle.md)
- Parallel: [BL-PRD-04](./BL-PRD-04-subscription-settings-ui-integration.md)
- Downstream: [BL-PRD-06](./BL-PRD-06-integration-testing-go-live.md)
- Stripe docs: [Webhook signature verification](https://stripe.com/docs/webhooks/signatures)
- CLAUDE.md rules in scope: PY-1, PY-3, PY-7; D-5; C-2, C-4, C-7; T-3, T-4, T-5
