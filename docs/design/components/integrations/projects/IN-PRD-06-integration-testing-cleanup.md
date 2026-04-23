# IN-PRD-06 — Integration Testing + Legacy Cleanup

**Status:** Not started
**Owner team:** Integrations component team (backend + cross-component code sweep)
**Blocked by:** [IN-PRD-01](./IN-PRD-01-core-model-encryption.md), [IN-PRD-02](./IN-PRD-02-google-oauth-flow.md), [IN-PRD-03](./IN-PRD-03-connection-management-ui.md), [IN-PRD-04](./IN-PRD-04-meta-mailchimp-platforms.md), [IN-PRD-05](./IN-PRD-05-reauth-lifecycle.md)
**Parallel with:** None — this is the capstone that validates the full substrate and retires the legacy pattern.
**Blocks:** — (terminal project in the Integrations chain)
**Estimated effort:** 2 days

---

## 1. Context

The prior five PRDs deliver the Integrations substrate end-to-end. This project closes out the component by (a) running a full E2E verification suite that exercises every piece in a realistic flow, (b) validating KMS key rotation with a live rotation test against dev, and (c) retiring the `_make_header_provider(auth_type)` pattern from AH-PRD-02 / AH-PRD-03, which reads OAuth tokens from ADK session state, in favor of the Integrations internal credential-read endpoint.

Two reasons this is a standalone project and not bundled into IN-PRD-02 or IN-PRD-05:

1. The legacy-cleanup edit spans the Agentic Harness component. Doing it in IN-PRD-02 would couple the Integrations milestone to the Agent Factory's Firestore agent configs, which is the wrong ordering. Landing Integrations first, then sweeping Agentic Harness once the substrate is proven, keeps ownership clean.
2. KMS rotation runbook validation requires a stable substrate. Rotating the key before the refresh lifecycle + audit flow is proven would confound incident response. Running rotation last against a seasoned substrate gives confident rollback criteria.

After this project, `grep -rn '_make_header_provider\|ga_credentials\[\|google_ads_credentials\[' api/src/` and `app/` yield zero matches. KEN-E's OAuth story is wholly owned by Integrations.

## 2. Scope

### In scope
- **End-to-end verification suite** — single `@pytest.mark.e2e` test spanning: new account → connect Google via UI popup flow → Data Pipeline GA job runs (pulls credentials via Integrations internal endpoint) → force token near-expiry → auto-refresh fires → user revokes via UI → downstream task fails with `needs_reauth` → re-auth notification appears → user reconnects → task retries + succeeds. Runs in staging against real Google OAuth (gated by `RUN_E2E_INTEGRATION_TESTS=1`); hermetic variant runs in CI with StubPlatform.
- **KMS key-rotation playbook + live rotation test** —
  - Document the rotation runbook (`operations/kms-key-rotation.md`): trigger rotation in Cloud KMS, immediately kick off the re-wrap sweeper, monitor `kms_key_version` distribution, disable old key version after 24h, destroy after 30d.
  - **Re-wrap sweeper** — the background worker that IN-PRD-01 declared but did not implement. Iterates `EncryptedToken` rows with old `kms_key_version`, decrypts, re-encrypts under the current version, persists. Capped at 500 tokens/tick, cadence hourly post-rotation until drain.
  - Live-rotation test in dev: rotate the dev KMS key; confirm zero token-read failures during the rotation window (measured by the `integrations.credential_read` error counter); confirm the sweeper drains all old-version tokens within 24h.
- **Legacy `_make_header_provider` removal** — sweep across AH-PRD-02's `agent_factory/header_provider.py` and AH-PRD-03's Google Analytics Specialist:
  - Replace the session-state read with an async fetch to `GET /api/v1/internal/integrations/credentials/{account_id}/{platform_id}` (OIDC-internal).
  - Update the `auth_type` → `platform_id` mapping: `"ga_oauth"` → `"google"` (or however Google was seeded in IN-PRD-02), `"google_ads_oauth"` → `"google"` (same shared OAuth app), `"hubspot_oauth"` → `"hubspot"` (once HubSpot lands), `"meta_ads_oauth"` → `"meta"`.
  - The closure returned by `_make_header_provider` keeps its existing signature so ADK's `header_provider=` plumbing remains untouched; only the body changes.
  - Remove session-state credential keys (`ga_credentials`, `google_ads_credentials`, etc.) from anywhere they're written — typically the chat router's session-initialization step.
- **Documentation sweep** — every component README that references Integrations as the credentials source gets a short prose update:
  - `docs/design/components/agentic-harness/README.md` — section on tool authentication points at Integrations.
  - `docs/design/components/data-pipeline/README.md` — same.
  - `docs/KEN-E-System-Architecture.md` §1.6 — Integrations component row finalized (remove any `[PLANNED]` tags, collapse current-vs-planned).
  - `docs/design/DESIGN-REVIEW-LOG.md` — new entry documenting the Integrations substrate + the AH-PRD-02 header-provider retrofit.
- **Observability dashboard** — a simple dashboard (or markdown-documented Weave query) covering `integrations.credential_read` volume + error rate, `integrations.refresh` success/failure, `integrations.revoke` count, and `kms_key_version` distribution. Non-blocking but useful for ongoing ops.
- **Verification report** — appended to `docs/design/components/integrations/README.md` summarizing: what shipped, E2E outcomes, rotation-test outcomes, legacy-cleanup grep results.
- **Feature-flag cleanup** — after verification, `integrations_enabled` and `integrations_ui_enabled` default to `true` in prod (remove allowlist gating); `integrations_reauth_lifecycle_enabled` same. Per-platform flags (`integration_google_enabled`, etc.) remain as platform-level kill switches.

### Out of scope
- New features on top of the substrate (inbound webhooks, service-account JSON, HubSpot) — their own future PRDs.
- Cross-account connection sharing — deferred per implementation-plan §8.
- Replacing the legacy pattern in Data Pipeline — DP-PRD-02 was written to use Integrations from day one, so nothing to sweep there.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **IN-PRD-01..05** | Everything. | This component |
| **[AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md)** | `_make_header_provider` body replaced by a credential-read call. Closure signature + `header_provider=` plumbing unchanged; only the token source moves. | AH-PRD-02 §5.3 + its own forward-reference to this PRD |
| **[AH-PRD-03](../../agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md)** | `ga_credentials` session-state reads removed; the specialist fetches via Integrations at tool-invocation time. | AH-PRD-03 credential-loading section |
| Cloud KMS | Key rotation trigger + rotated state persistence; IAM binding permits the re-wrap sweeper (same service account as IN-PRD-01's encrypt/decrypt). | `deployment/terraform/` |
| Staging env | E2E test runs against staging GA + staging OAuth app. | Existing env |
| Weave / observability | Existing dashboards platform; this PRD adds a dashboard or Weave query document. | `app/adk/tracking/` |

## 4. Data contract

No new shapes. This PRD uses IN-PRD-01's `kms_key_version` field for the re-wrap sweeper.

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create | `api/src/kene_api/integrations/workers/kms_rewrap_sweeper.py` + Cloud Scheduler handler route |
| Modify | `deployment/terraform/` — add the re-wrap sweeper Cloud Scheduler job (disabled by default; enabled post-rotation via IaC toggle or manual gcloud) |
| Create | `docs/design/components/integrations/operations/kms-key-rotation.md` — the playbook |
| Modify | `app/adk/agents/agent_factory/header_provider.py` — replace session-state read with Integrations credential-read |
| Modify | `app/adk/agents/agent_factory/config_loader.py` (or equivalent) — drop the `auth_type` → session-state key map; replace with `auth_type` → `platform_id` map |
| Modify | `api/src/kene_api/routers/chat.py` (or wherever session-state is seeded) — stop writing `ga_credentials` / `google_ads_credentials` / `hubspot_credentials` / `meta_ads_credentials` keys |
| Modify | `app/adk/agents/strategy_agent/google_analytics_agent_v4.py` — either delete (if AH-PRD-03 has already obsoleted it) or strip out the session-state cred path |
| Modify | `docs/design/components/agentic-harness/README.md` — tool-authentication section points at Integrations |
| Modify | `docs/design/components/data-pipeline/README.md` — tool-authentication section points at Integrations |
| Modify | `docs/KEN-E-System-Architecture.md` §1.6 — finalize Integrations row |
| Modify | `docs/design/DESIGN-REVIEW-LOG.md` — append review entry |
| Modify | `docs/design/components/integrations/README.md` — append verification-report section |
| Create | `api/tests/e2e/integrations/test_full_lifecycle.py` — the full E2E (hermetic and real-Google variants) |
| Create | `api/tests/integration/integrations/test_kms_rewrap_sweeper.py` |
| Create | `api/tests/integration/integrations/test_legacy_removed.py` — asserts `grep` hits zero matches against `_make_header_provider` legacy body (regression-proof) |

### 5.2 E2E test outline

```text
new_account_fresh_oauth_lifecycle (hermetic with StubPlatform):
  1. Seed a new account + admin user + a non-admin user.
  2. Non-admin connects "stub" platform via the initiate/callback flow.
  3. Seed a Data Pipeline job with platform="stub"; run it; assert credential-read returns decrypted token and job completes.
  4. Manipulate the stored EncryptedToken to have expires_at = now + 60s (inside refresh window).
  5. Invoke credential-read; assert a refresh happened (audit + updated expires_at).
  6. Admin revokes the connection via UI simulation (DELETE /connections/{id}).
  7. Trigger another job run; assert it fails with needs_reauth status and a notification is queued for the non-admin + admin.
  8. Non-admin reconnects; next credential-read succeeds; job retries + completes.

staging_e2e_real_google (behind RUN_E2E_INTEGRATION_TESTS=1):
  Same flow against real Google OAuth in staging, using a test Google account.
  Skipped in default CI.
```

### 5.3 Re-wrap sweeper

```text
Cloud Scheduler handler (disabled by default; enabled post-rotation):
  query EncryptedToken where kms_key_version != CURRENT:
    limit 500
    for each:
      decrypt with KMS (KMS auto-resolves by version)
      encrypt with current version
      persist with updated kms_key_version + updated_at
  emit integrations.kms_rewrap Weave span with {rewrapped_count, remaining_estimate}
  if remaining_estimate == 0:
    disable self (IaC toggle or Cloud Scheduler pause)
```

Cadence: hourly during drain. Drain duration estimate: ~500 tokens/hour × 24 hours = 12,000 tokens/day. Sufficient for KEN-E's projected scale.

### 5.4 Legacy-removal scope

The sweep touches three call sites:

1. **AH-PRD-02 `header_provider.py`** — replace the `context.state.get(state_key, {})` read with an async `httpx.get("/internal/integrations/credentials/...")` wrapped in a cache-per-tool-invocation so a single turn's multiple tool calls share a fetch.
2. **AH-PRD-03 GA specialist tool-invocation** — ensure the tool's `before_agent_callback` no longer expects `ga_credentials` in state; Integrations's credential-read is called directly.
3. **Chat router session initialization** — delete the block that fetches tokens and writes them to session state; becomes obsolete.

The `auth_type` → `platform_id` mapping is published in a new constant at `app/adk/agents/agent_factory/integrations_mapping.py`:

```python
AUTH_TYPE_TO_PLATFORM_ID = {
    "ga_oauth": "google",
    "google_ads_oauth": "google",
    "hubspot_oauth": "hubspot",
    "meta_ads_oauth": "meta",
    "mailchimp_oauth": "mailchimp",
}
```

### 5.5 KMS rotation runbook (summary)

Full doc lives at `operations/kms-key-rotation.md`. Summary:

1. **Pre-rotation (T-1d)**: verify the re-wrap sweeper has never run (or is cleanly drained); verify current `kms_key_version` distribution is uniform via dashboard.
2. **Rotate (T0)**: `gcloud kms keys versions create --location=us --keyring=integrations --key=token-encryption` (via Terraform preferred).
3. **Enable sweeper (T0+5m)**: enable the Cloud Scheduler job; watch first tick.
4. **Monitor (T0 → T+24h)**: dashboard shows `kms_key_version=NEW` climbing; `integrations.credential_read` error rate flat.
5. **Disable old version (T+24h)**: `gcloud kms keys versions disable <OLD_VERSION>`; if any read fails, re-enable immediately.
6. **Destroy (T+30d)**: `gcloud kms keys versions destroy <OLD_VERSION>`.

Rollback: if `integrations.credential_read` error rate spikes, disable the sweeper, re-enable the old key version, pause. Re-wrap sweeper design tolerates disabling mid-drain — it picks up where it left off.

## 6. API contract

No new public endpoints. One new internal OIDC endpoint:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/internal/integrations/kms-rewrap-sweeper` | Cloud Scheduler handler; runs one sweep batch. Returns `{rewrapped_count, remaining_estimate}`. |

## 7. Acceptance criteria

1. **Full E2E (hermetic)** passes green in CI covering the 8-step flow in §5.2.
2. **Full E2E (real Google)** passes on demand (`RUN_E2E_INTEGRATION_TESTS=1`) in staging; verification report includes the run output.
3. **KMS re-wrap sweeper** — tokens with old `kms_key_version` are re-wrapped by the sweeper; integration test seeds 50 old-version tokens, runs the sweeper handler, asserts all are at the new version and `integrations.kms_rewrap` Weave span is emitted.
4. **Live rotation test (dev)** — documented run: rotate dev key, monitor 24h, zero `credential_read` errors attributable to rotation, all dev-env tokens re-wrapped.
5. **Legacy `_make_header_provider` body replaced** — header-provider closures fetch credentials via the Integrations internal endpoint; no `context.state.get("ga_credentials", ...)` or similar remains in `app/` or `api/`.
6. **Grep check** — `grep -rn 'ga_credentials\[\|google_ads_credentials\[\|hubspot_credentials\[\|meta_ads_credentials\[' api/src/ app/` returns zero matches. `grep -rn '_make_header_provider' api/src/ app/` still matches (the helper is kept; only its body changed), but inspection confirms no session-state reads.
7. **`AUTH_TYPE_TO_PLATFORM_ID` mapping** — new constant exists; factory uses it at build time to map `agent_configs` `auth_type` values to Integrations platform IDs.
8. **Session-state cred cleanup** — chat router no longer writes `ga_credentials` / `google_ads_credentials` / `hubspot_credentials` / `meta_ads_credentials` to session state. Integration test asserts these keys are absent from a fresh session's state dump.
9. **Documentation sweep applied** — component READMEs (agentic-harness, data-pipeline) and System Architecture §1.6 reference Integrations as the credentials source; DESIGN-REVIEW-LOG has a new entry dated this PRD's completion.
10. **Observability** — the Integrations dashboard (or documented Weave queries) covers credential-read volume + error rate, refresh success/failure, revoke count, and `kms_key_version` distribution.
11. **Feature-flag defaults updated** — `integrations_enabled`, `integrations_ui_enabled`, `integrations_reauth_lifecycle_enabled` default `true` in prod after verification. Per-platform flags remain.
12. **Verification report appended** — `docs/design/components/integrations/README.md` ends with a "Verification (2026-MM-DD)" section capturing E2E, rotation, and grep results.
13. **Regression guard** — `test_legacy_removed.py` runs `grep` as a subprocess and fails CI if legacy patterns return. Becomes part of `make lint` or equivalent gate.

## 8. Test plan

### Unit
- Re-wrap sweeper: selector boundary (mixed old + new versions); 500-limit respected; error during re-encrypt aborts the batch cleanly; emits correct Weave span.
- `AUTH_TYPE_TO_PLATFORM_ID` coverage: all known `auth_type` values map; unknown raises at factory build time.

### Integration
- Full E2E (hermetic) per §5.2.
- Re-wrap sweeper over seeded fixture (AC #3).
- Legacy-absent grep (AC #6, via subprocess).
- Session-state cleanup (AC #8).

### Manual verification
- Staging: run the real-Google E2E; capture output in the verification report.
- Dev: run the KMS rotation drill per the runbook; capture dashboard screenshots showing the `kms_key_version` transition without error-rate spikes.
- Read-through of the three updated READMEs + DESIGN-REVIEW-LOG for tone/accuracy.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Real-Google E2E flaky due to upstream OAuth hiccups | Gated behind `RUN_E2E_INTEGRATION_TESTS`; not in the default CI lane. Hermetic variant is authoritative for merge gating. |
| KMS rotation causes credential-read errors mid-window | Runbook has immediate rollback (disable new version, keep old enabled); 24h soak before destroying old version. |
| Legacy-cleanup edit breaks AH-PRD-02's in-flight features | Coordinated via the `# TODO(IN-PRD-06)` markers IN-PRD-02 dropped at call sites. Factory closure signature is preserved, so the blast radius is the closure body only. Integration tests for each specialist exercise the new path before merge. |
| Re-wrap sweeper loops forever on a corrupt token | Per-token try/except; failed tokens logged with `connection_id` + `kind` and excluded from re-wrap with an audit entry (`event="error", metadata={reason: "rewrap_failed"}`). Runbook instructs manual inspection. |
| Dashboards platform churn | Document Weave queries + metric names in the README so even if the dashboard UI changes, the recipe survives. |

### Open questions
- **Q:** Should the re-wrap sweeper run continuously (even between rotations) to defend against stale `kms_key_version` entries caused by bugs? → No. It's disabled-by-default between rotations; a dashboard metric (`tokens_with_stale_version`) alerts if drift exceeds 1% outside a rotation window.
- **Q:** Do we publish a "deprecation warning" period before deleting the session-state cred reads, or swap cleanly? → Swap cleanly. No external consumers depend on the internal session-state shape; coordinated internal change.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Upstream: [IN-PRD-01](./IN-PRD-01-core-model-encryption.md), [IN-PRD-02](./IN-PRD-02-google-oauth-flow.md), [IN-PRD-03](./IN-PRD-03-connection-management-ui.md), [IN-PRD-04](./IN-PRD-04-meta-mailchimp-platforms.md), [IN-PRD-05](./IN-PRD-05-reauth-lifecycle.md)
- Cross-component cleanup: [AH-PRD-02 §5.3](../../agentic-harness/projects/AH-PRD-02-agent-factory.md#53-header-provider-factory), [AH-PRD-03](../../agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md)
- Operations runbook (new): `operations/kms-key-rotation.md`
- Architecture updates: `docs/KEN-E-System-Architecture.md` §1.6, `docs/design/DESIGN-REVIEW-LOG.md`
- CLAUDE.md rules in scope: PY-1, PY-5, PY-7; D-5; T-1, T-3, T-4, T-5; G-1
