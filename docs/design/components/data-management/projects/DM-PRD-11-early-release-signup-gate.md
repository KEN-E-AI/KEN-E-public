# DM-PRD-11 — Early Release Signup Gate

**Status:** Ready to start — all dependencies shipped
**Owner team:** Data Management (backend + data model). Frontend issues filed under UI; flag registration under Feature Flags.
**Blocked by:** None. Builds on already-shipped primitives: the Feature Flags SDK (`is_feature_enabled` + `useFeatureFlag`), the invitation system (`routers/firestore.py`), the super-admin gate (`require_super_admin`), the org-creation endpoint, and the `recaptcha` rate-limiter.
**Blocks:** Nothing else depends on it. It is a self-contained gate that can ship and be toggled independently.
**Estimated effort:** ~8–10 days across 9 issues (backend + frontend), two dependency waves.

---

## 1. Context

Today **any** visitor to app.ken-e.ai can create a fully-usable account. Signup is 100% client-side: `frontend/src/pages/Authentication.tsx` calls Firebase `createUserWithEmailAndPassword()` (`handleSignUp`, ~L429) or Google `signInWithPopup()` (`handleGoogleSignInSuccess`, ~L589) directly, then writes the `users/{uid}` profile via the generic `POST /api/v1/firestore/documents`. **There is no backend signup gate.** A brand-new user lands with zero organizations and is bounced to `/create-organization` (`SelectOrganizationPage.tsx:231-248`), where `POST /api/v1/organizations/` (`routers/organizations.py:459`) is the first authenticated, meaningful server write.

We want to close open signup so a person can only obtain a usable account if they either:

1. were **invited** — the existing org-invitation flow (they accept an invite and join an existing org), or
2. enter a valid **Early Release access code** — a single shared secret the team distributes to early-access participants.

This must be **reversible at runtime** (flip back to public signup without a deploy) and must never lock out existing users or the KEN-E team.

### Design decisions (confirmed with PO)

- **One shared Early Release code**, not a per-user code collection. A single secret value, rotatable/disable-able by super-admins. This collapses the data model to one config document plus a lightweight redemption log.
- **"Invited" = the existing org-invitation flow only.** No new allowlist. Invited users accept an invite → already have an org → **never reach the org-creation gate**. The invitation path therefore needs no new backend work; only the signup *form* must continue to let an `?invitation=…` arrival through.
- **Pragmatic enforcement, not Firebase blocking functions.** Firebase Identity Platform / `beforeUserCreated` is not configured (no GCIP, no Cloud Functions deploy lane — verified). We do not introduce it. Instead we gate the one authenticated server write that turns a Firebase user into a usable account: **organization creation**. An org-less Firebase user is inert.
- **The feature flag is the on/off switch only.** Per `feature-flags/README.md` §7.6, flags must not *own* security-sensitive decisions. The decision lives in a server-side predicate; the flag only governs whether that predicate runs.

It lives under Data Management because the durable artifacts are a new server-owned Firestore collection, a server-side enforcement point, and a deletion-cleanup obligation — all platform-data concerns. UI (signup page, admin page) and Feature Flags (the registered flag) are consumers.

## 2. Scope

### In scope

**Early Release code config + redemption (backend, Data Management)**
- A singleton config document `app_config/early_release` holding the current shared code, `is_active`, optional `expires_at`, and audit fields (§4.1).
- An `EarlyReleaseService` with `get_config`, `set_code` / `rotate`, `set_active`, `validate(code)` (constant-time compare), and `record_redemption(user_id, email, org_id)` (§4.5).
- A redemption log `early_release_redemptions/{user_id}` (§4.2) — idempotent, keyed by user, for conversion analytics and "who came in via the code."

**Enforcement (backend, Data Management)**
- The `caller_may_onboard(user, access_code)` predicate (§4.3) enforced inside `create_organization`, applied only when `invite_only_signup` is ON and `organization_creation_permission == "all"`.
- Optional `access_code: str | None` added to `OrganizationRequest`.

**Public + admin API (backend, Data Management)**
- Public, rate-limited `POST /api/v1/early-release/validate` (does not consume) and `GET /api/v1/auth/signup-policy` (so the pre-auth signup page can decide whether to show the code field).
- Super-admin `GET/PUT /api/v1/admin/early-release-code` and `GET /api/v1/admin/early-release-code/redemptions`.

**Feature flag (Feature Flags)**
- Register `invite_only_signup` as a clean global boolean (no targeting rules — see §4.4), seeded `is_active=true`, `default_enabled=false` (ships dark). Add the key to the frontend flag registry.

**Frontend (UI)**
- Flag-aware signup-page states + access-code entry field (§E in DM-PRD-11 plan; reuse the existing invitation banner).
- Forwarding the validated code from signup → `/create-organization` → the gated org-create call, surfacing the server 403 as a friendly "early access required" state.
- A `/admin/early-release` super-admin page to view/rotate/disable the code and see the redemption count.

**Tests**
- Unit (validate/rotate/expiry, constant-time compare); integration (org-create gate matrix, admin auth boundary, public-validate rate limit); frontend component (signup states, admin page); cross-surface e2e invariants.

### Out of scope

- Changing Firebase Auth itself (no blocking functions / Identity Platform upgrade).
- A per-user / capped / multi-code system (explicitly deferred — one shared code for v1).
- Any change to the invitation system (consumed as-is).
- Emailing the code to invitees (admins distribute the shared code out of band).
- A global cap on total early-release signups (today's redemption log is record-only, not a transactional counter; add later if a hard cap is needed).
- Sweeping orphan Firebase users (auth records created but never onboarded) — see §9; an optional cleanup job is noted, not built here.

## 3. Dependencies

- **Feature Flags (shipped):** `is_feature_enabled(flag_key, ctx, default=False)` in `services/feature_flag_service.py`; `useFeatureFlag` + `registry.ts` in the frontend (FF-PRD-03). The gate and the `signup-policy` endpoint call the helper; the signup page reads `signup-policy` (the page is pre-auth, where `useFeatureFlag` cannot evaluate an authenticated context).
- **Invitation system (shipped):** `routers/firestore.py` — `Invitation` model, public `GET /invitations/verify/{token}`, `POST /invitations/accept/{token}`; frontend `pages/AcceptInvitation.tsx`, `data/teamApi.ts`, and the `?invitation=` pre-fill in `Authentication.tsx`. Consumed unchanged.
- **Super-admin gate (shipped):** `require_super_admin` in `auth/dependencies.py`; the admin-page + nav pattern (`pages/admin/FeatureFlagsPage.tsx`, `SuperAdminsPage.tsx`, `components/admin/*/registration.ts`, `components/layout/super-admin-nav-registry.ts`).
- **Org-creation endpoint (shipped):** `routers/organizations.py:459` `create_organization`, including the existing `settings.organization_creation_permission` check (`config.py`) the gate layers onto.
- **Rate-limiter (shipped):** the `recaptcha` / `auth` limiter family (`auth/rate_limiting.py`, see `api/CLAUDE.md` → Rate Limiting) — clone a pre-auth IP-keyed limiter for `validate`.
- **Audit pattern (shipped):** `routers/admin_feature_flags.py` emits audit events on every mutation; mirror that for code rotations.
- **Existing files to study:** `routers/organizations.py` (gate insertion point), `routers/admin_feature_flags.py` (super-admin CRUD + audit template), `routers/firestore.py` (public-verify template + invitation lookup), `services/feature_flag_service.py` (service + Firestore conflict-safe write pattern), `pages/Authentication.tsx` + `pages/auth/CreateAccountView.tsx` (signup), `pages/CreateOrganization.tsx` + `pages/SelectOrganizationPage.tsx` (org-create hop).

## 4. Data contract

### 4.1 Early Release config (singleton)

```
app_config/early_release          # one global document
    code: str                     # the shared secret, plaintext (admin must read it to distribute)
    is_active: bool               # false = no code currently accepted (kill switch)
    expires_at: str | None        # ISO-8601; null = no expiry
    updated_by: str               # super-admin user_id of the last writer
    updated_at: str               # ISO-8601
```

Stored plaintext deliberately: the admin needs to retrieve the current code to hand it out, and the code is **not a data-access boundary** — it only gates org creation. Brute-force resistance comes from the rate-limiter (§6) plus a constant-time compare (`secrets.compare_digest`) on `validate`. `app_config` is a new global (non-account-scoped) singleton collection; `early_release` is its only document in v1.

### 4.2 Redemption log

```
early_release_redemptions/{user_id}     # keyed by user_id → idempotent
    user_id: str
    email: str
    org_id: str                          # the org they created via the code
    redeemed_at: str                     # ISO-8601
```

Record-only (no decrement): the shared code is uncapped, so a redemption simply records that this user onboarded via the code. The admin redemption count is the size of this collection. Keyed by `user_id` so a retry is a no-op overwrite.

### 4.3 The onboarding predicate (the security boundary)

Enforced inside `create_organization`, **only** when `invite_only_signup` is ON (and `organization_creation_permission == "all"` — see §4.6 for precedence):

```python
async def caller_may_onboard(user: UserContext, access_code: str | None) -> bool:
    # 1. Super-admin always passes (role-based bypass). Email domain is NOT
    #    trusted: Firebase signup is open, so an "@ken-e.ai" email string is not
    #    an authorization signal. This mirrors auth/models.py::is_super_admin,
    #    from which the email-domain check was removed in DM-80/DM-81.
    if user.is_super_admin:
        return True
    # 2. Existing users (already in an org) and invited users (joined an org,
    #    or have a pending invitation for their email) are never blocked.
    if await user_has_any_org_membership(user.user_id):
        return True
    if await has_pending_invitation(user.email):
        return True
    # 3. Early Release path: a valid, active, unexpired shared code.
    if access_code and await early_release_service.validate(access_code):
        return True
    return False
```

This predicate **structurally guarantees** the invariants in §7: existing users and invited users carry an org membership (or a pending invite) and pass clause 2 before the code is ever considered; only a true net-new self-serve signup with no code is stopped. When clause 3 grants access, the caller writes a redemption record (§4.2) for the new org.

> Note: invited users join via `accept_invitation`, which does not call `create_organization`, so clause 2's invitation check is a belt-and-suspenders allowance for the rare case where an invited user later creates their *own* second workspace.

### 4.4 The feature flag (clean global boolean — no targeting)

`invite_only_signup` is registered with **no targeting rules**. In the flag evaluator a matching targeting rule *grants* the flag (i.e. would turn invite-only **ON** for the matched users) — so an `email_domains=["ken-e.ai"]` rule would enforce invite-only on staff, the opposite of a bypass. The super-admin bypass therefore lives **only** in the §4.3 predicate, never in flag targeting.

```
key:             "invite_only_signup"
description:      "When ON, new users can only onboard via an org invitation or a valid Early Release code."
is_active:        true            # registered live; the kill switch
default_enabled:  false           # ships dark — open signup until an admin flips it on
targeting_rules:  (none)
owner:            <eng owner email>
```

To enable invite-only globally, a super-admin flips `default_enabled → true` in `/admin/feature-flags`. The gate and `signup-policy` evaluate with `default=False`, so a flag-service outage **reopens** signup (fail-open for signups) rather than locking out legitimate code-holders.

### 4.5 Service surface

```python
class EarlyReleaseService:
    async def get_config(self) -> EarlyReleaseConfig | None: ...
    async def set_code(self, code: str, *, actor_id: str,
                       expires_at: str | None = None) -> EarlyReleaseConfig: ...
    async def set_active(self, is_active: bool, *, actor_id: str) -> EarlyReleaseConfig: ...
    async def validate(self, code: str) -> bool:
        """True iff config exists, is_active, not expired, and
        secrets.compare_digest(submitted, stored)."""
    async def record_redemption(self, *, user_id: str, email: str, org_id: str) -> None: ...
    async def count_redemptions(self) -> int: ...
```

### 4.6 Precedence vs. `organization_creation_permission`

The existing `settings.organization_creation_permission` (`none | super_admin | all`, default `all`) is evaluated **first** and unchanged:
- `none` → org creation disabled for everyone (early-release gate moot).
- `super_admin` → only super-admins (gate moot; they bypass anyway).
- `all` (default) → the §4.3 predicate applies **on top** when `invite_only_signup` is ON; when the flag is OFF, behavior is today's open creation.

## 5. Implementation outline

| Action | File | Issue |
|--------|------|-------|
| Create | `api/src/kene_api/models/early_release_models.py` — `EarlyReleaseConfig`, request/response models, branded code type | 1 |
| Create | `api/src/kene_api/services/early_release_service.py` — service per §4.5 (Firestore singleton + redemption log) | 1 |
| Create | `api/tests/unit/test_early_release_service.py` — validate/rotate/expiry/compare | 1 |
| Create | `api/src/kene_api/routers/admin_early_release.py` — super-admin GET/PUT code + GET redemptions (clone `admin_feature_flags.py`, audited) | 2 |
| Modify | `api/src/kene_api/main.py` — register the admin router | 2 |
| Create | `api/src/kene_api/routers/early_release.py` — public `POST /early-release/validate` (rate-limited) | 3 |
| Modify | `api/src/kene_api/routers/auth.py` — add public `GET /auth/signup-policy` | 3 |
| Modify | `api/src/kene_api/auth/rate_limiting.py` — add an `early_release` IP limiter (clone `recaptcha`) | 3 |
| Modify | `api/scripts/seed_feature_flags.py` — register `invite_only_signup` (§4.4) | 4 |
| Modify | `frontend/src/lib/featureFlags/registry.ts` — add the key | 4 |
| Modify | `api/src/kene_api/routers/organizations.py` — `caller_may_onboard` gate + redemption in `create_organization`; add `access_code` to `OrganizationRequest` | 5 |
| Create | `api/tests/integration/test_org_creation_gate.py` — the gate matrix | 5 |
| Create | `frontend/src/data/earlyReleaseApi.ts` — validate + signup-policy clients | 6 |
| Modify | `frontend/src/pages/auth/CreateAccountView.tsx` — code field + "early access required" panel (reuse invitation banner) | 6 |
| Modify | `frontend/src/pages/Authentication.tsx` — signup-policy gate, validate-on-blur, stash code (no `@ken-e.ai` client exemption — see §4.3) | 6 |
| Modify | `frontend/src/pages/CreateOrganization.tsx` — forward `access_code` in the org-create payload | 7 |
| Modify | `frontend/src/pages/SelectOrganizationPage.tsx` — verify the code survives the no-org → `/create-organization` hop | 7 |
| Create | `frontend/src/pages/admin/EarlyReleasePage.tsx` + `components/admin/earlyRelease/` (clone `SuperAdminsPage.tsx`) | 8 |
| Create | `frontend/src/components/admin/earlyRelease/registration.ts` + route in `App.tsx` | 8 |
| Create | `frontend/src/queries/earlyRelease.ts` — TanStack hooks | 8 |
| Create | `api/tests/integration/test_early_release_invariants.py` — cross-surface ACs | 9 |
| Modify | `docs/design/components/data-management/README.md`, `DESIGN-REVIEW-LOG.md`, `PROJECT-PLANNER.md`; cross-link FF + UI READMEs | 9 |

## 6. API contract

| Method | Path | Auth | Body / params | Response |
|--------|------|------|---------------|----------|
| `POST` | `/api/v1/early-release/validate` | Public, IP rate-limited (`early_release` limiter) | `{ "code": str }` | `{ "valid": bool }` — uniform on invalid/expired/inactive (no enumeration leak). Never consumes/records. |
| `GET` | `/api/v1/auth/signup-policy` | Public | — | `{ "invite_only": bool }` — `is_feature_enabled("invite_only_signup", anon_ctx, default=False)`. |
| `GET` | `/api/v1/admin/early-release-code` | Super-admin | — | `{ code, is_active, expires_at, updated_by, updated_at, redemption_count }`. |
| `PUT` | `/api/v1/admin/early-release-code` | Super-admin | `{ code?, is_active?, expires_at? }` | Updated config. Audited (mirrors `admin_feature_flags`). |
| `GET` | `/api/v1/admin/early-release-code/redemptions` | Super-admin | pagination | `{ redemptions: [{user_id, email, org_id, redeemed_at}], total }`. |
| `POST` | `/api/v1/organizations/` | Authenticated (existing) | existing body **+ optional `access_code`** | Existing response; returns `403 {detail:"early_access_required"}` when the §4.3 predicate denies. |

## 7. Acceptance criteria

1. With `invite_only_signup` **ON**, an un-invited user with no code **cannot create an org** — `POST /organizations/` returns `403 early_access_required` — and the signup form blocks at the code field.
2. An **invited** user (valid pending `invitation`, or already a member of an org) signs up and joins/creates their org without entering a code.
3. A **valid shared code** lets a net-new user sign up and create their own workspace; a redemption record is written to `early_release_redemptions/{user_id}`.
4. A **rotated, disabled (`is_active=false`), or expired** code is rejected at both `validate` and the org-create gate.
5. **Super-admins always bypass (role-based)** — the server predicate passes any caller holding the `super_admin` role, regardless of flag state or code. Email domain confers no bypass on the client or the server: an `@ken-e.ai` email sees the same code field as anyone, and non-super-admin staff onboard via the shared code or an invitation. (Rationale: open Firebase signup makes an email string untrustworthy; see DESIGN-REVIEW-LOG 2026-06-08.)
6. With the flag **OFF**, signup and org creation are byte-for-byte today's behavior (the gate early-returns; no code field shown).
7. **Existing users are never locked out** — the gate fires only on `create_organization`, which a user with an org never re-enters; sign-in is untouched. An integration test signs in a pre-existing user with the flag ON and confirms full normal operation.
8. `POST /early-release/validate` is IP rate-limited and returns a uniform `{valid:false}` for wrong/expired/inactive codes (no distinction that aids enumeration); exceeding the limit returns `429`.
9. `GET /auth/signup-policy` returns `{invite_only:true}` when the flag is on and `{invite_only:false}` when off or on flag-service error (fail-open).
10. The `/admin/early-release` page (super-admin only) shows the current code, supports rotate / set-expiry / disable, and displays an accurate redemption count; a non-super-admin receives `403` on the admin endpoints and cannot see the nav entry.
11. Code rotations emit an audit event (mirroring `FEATURE_FLAG_CHANGED`).
12. All unit, integration, and frontend tests pass; `make lint`, `npm run typecheck`, and `npm run format.fix` are clean; `lychee` passes for the doc changes.

## 8. Test plan

**Unit** (`test_early_release_service.py`): `validate` true only when active + unexpired + exact match; constant-time compare used; expired/inactive → false; `record_redemption` idempotent on the same `user_id`; `count_redemptions` correct.

**Integration** (`test_org_creation_gate.py`): the matrix {flag OFF, flag ON} × {super-admin (role bypass), `@ken-e.ai` email without the role (blocked), user-with-existing-org, user-with-pending-invitation, valid code, invalid/no code} — asserting `201` vs `403` per §4.3, and that a redemption is written exactly on the valid-code path. Precedence cases: `organization_creation_permission ∈ {none, super_admin}` short-circuit before the gate.

**Integration** (admin + public): super-admin CRUD auth boundary (super-admin `200`, normal user `403`); `validate` rate-limit returns `429` past the cap and uniform `{valid:false}` below it; `signup-policy` reflects flag state and fails open on a forced service error.

**Frontend component:** signup states (flag OFF = open; flag ON + no code = blocked with code field; flag ON + `?invitation=` = unchanged pre-fill; flag ON + valid code = proceed; `@ken-e.ai` email = code field still shown, no client exemption); `/admin/early-release` page render + rotate/disable actions (mocked API).

**E2E invariants** (`test_early_release_invariants.py`): the §7 invariants end to end — existing-user-not-locked-out, super-admin-bypass, invited-still-works, code-allows-own-workspace, flag-off-is-open. Auth paths use the existing test bypass (`VITE_AUTH_BYPASS` / `API_TEST_BYPASS_TOKEN`).

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Orphan Firebase users (auth record created at the form, but blocked at org-create) | Accepted trade-off of the pragmatic gate. The client entry-gate stops most before Firebase is called; an org-less user is inert. Optional later: a Cloud Scheduler sweep of doc-less aged auth users (out of scope here). |
| Brute-forcing the shared code | Pre-auth IP rate-limiter on `validate` (clone of `recaptcha`, `fail_open=False`) + constant-time compare + uniform response. The code gates only org creation, not data access. |
| Flag-service outage direction | Chosen **fail-open for signups** (`default=False`): an outage reopens signup rather than locking out legitimate code-holders. Documented; revisit if abuse observed. |
| Flag targeting inversion | Resolved (§4.4): the flag is a clean global boolean with no targeting; the super-admin bypass is in the predicate, not the flag. |
| Precedence with `organization_creation_permission` | Documented (§4.6): the setting is evaluated first; the gate layers on only under `all`. Covered by tests. |
| Plaintext shared code in Firestore | Acceptable — not an authz boundary; admin must read it to distribute. Access to the config doc is super-admin-only via the API; Firestore is default-deny to clients. |
| Google-OAuth signups can't pre-validate a password | Handled uniformly: both email/password and Google users hit the same server org-create gate; the client form's code requirement applies to both before the popup as well. |

### Open questions

- **Q:** Is there Figma for the flag-ON "early access required" signup state and the `/admin/early-release` page? → **None today.** UI issues (6, 8) should raise a design ask or follow the closest existing pattern (invitation banner; `SuperAdminsPage`). Flag-OFF state matches today's signup exactly.
- **Q:** Should the redemption log ever enforce a global cap on total early-release accounts? → **No for v1** (record-only). Add a transactional counter later if a hard cap is needed.
- **Q:** Rotate-and-grandfather — when the code rotates, existing redeemers keep their accounts (they already have orgs and pass clause 2). Confirmed: rotation affects only *future* validations.

## 10. Reference

- Feature flag policy: [`feature-flags/README.md`](../../feature-flags/README.md) §7.6 (flags must not own security gates) + the evaluation order.
- CRUD + audit template: `api/src/kene_api/routers/admin_feature_flags.py`.
- Invitation system + public-verify template: `api/src/kene_api/routers/firestore.py` (`Invitation`, `verify_invitation_token`).
- Enforcement insertion point: `api/src/kene_api/routers/organizations.py:459` (`create_organization`, existing permission check at L496-509).
- Inert org-less user: `frontend/src/pages/SelectOrganizationPage.tsx:231-248`.
- Signup flow: `frontend/src/pages/Authentication.tsx` (`handleSignUp` ~L429), `frontend/src/pages/auth/CreateAccountView.tsx`.
- Rate-limiter family: `api/CLAUDE.md` → Rate Limiting (`recaptcha` limiter as the template).
- Admin-page + nav pattern: `frontend/src/pages/admin/SuperAdminsPage.tsx`, `frontend/src/components/admin/*/registration.ts`, `frontend/src/components/layout/super-admin-nav-registry.ts`.
- CLAUDE.md rules in scope: C-1, C-2, C-5, C-6; D-1, D-2, D-5; PY-1, PY-2, PY-7; T-1, T-3, T-4, T-5, T-8; G-1, G-2, G-3.
