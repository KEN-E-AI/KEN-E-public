# Pipeline Error Recovery Specialist — Backlog

> **Status:** Backlog — defer until Data Pipeline has real failure-mode telemetry
> **Proposed prefix:** `PER-PRD-NN`
> **Estimated scope:** 1 component, 3–4 PRDs (~10–12 days effort)

---

## Why this is backlog, not active work

Data Pipeline tasks are deterministic: `sha256(account_id || job_id || canonical_json(inputs) || job.version)` is expected to produce a byte-identical artifact across runs. That guarantee underpins the cache, the audit model, and the downstream-consumer contract (SAR-E ingestion, Knowledge Graph observations, agent analysis tasks).

The review loop that Agent tasks use (up to 5 iterations of reviewer-driven revision) deliberately **does not apply** to pipeline tasks — a reviewer "rewriting" a deterministic extraction defeats the whole point.

But there is a failure class that neither "auto-retry transient errors" nor "fail loudly on semantic errors" handles well: **a platform API changes something that a small input tweak could recover from.** Real examples:

- An API requires `date` in `YYYY-MM-DD` that previously accepted `YYYY/MM/DD`.
- A deprecated metric name is removed; a renamed equivalent exists.
- A rate-limit response changes from `429` to `403` with a specific message; the job should wait-and-retry rather than escalate.
- A scope that used to cover a resource now requires a new one; the token is otherwise fine.

These are semantic 4xx failures today (Data Pipeline v1 fails + notifies). The tax: an admin has to triage every one, update the job catalog, and re-run. For recurring automations this can mean 24–48h of silent failure before someone notices.

A bounded specialist can shorten that loop without breaking determinism — but only if the *shape* of the recovery is constrained. This is non-trivial design work that benefits from seeing real failure traces before we commit to a UX.

## What it is

A single ADK specialist (`pipeline_error_recovery`) invoked on semantic 4xx pipeline failures. The specialist reads the error, the job catalog entry, the input schema, and recent successful runs, and proposes exactly one of:

- **Input tweak within schema** (e.g., change `date_format` from `%Y/%m/%d` to `%Y-%m-%d`). The specialist emits the proposed new `inputs` dict; the service re-runs; if it succeeds, the run is persisted as a normal run with a flag (`recovered: true`). If it fails, the task fails loudly.
- **Catalog escalation** (e.g., "The API renamed this metric; please update the job definition"). Creates an admin notification with a suggested `DataPipelineJob` patch. Does not auto-apply.
- **Give up** (e.g., "This is genuinely an account-specific config problem; a human must fix it"). Falls through to the existing fail-loud path.

## Hard design boundaries

1. **Determinism is preserved across successful runs.** A recovered run stores its `effective_inputs` separately from the `requested_inputs`; the cache key uses `effective_inputs` so a subsequent identical recovery is a cache hit. The first successful recovery of a given error class is uncached; subsequent runs with the same shape get the tweak for free.
2. **The specialist cannot expand schema.** Proposed input tweaks must validate against the job's `input_schema`. If the fix requires schema changes, it's a catalog escalation, not an auto-retry.
3. **Maximum one recovery attempt per task.** If the recovery attempt also fails, the task fails. No recursive recovery.
4. **Audit trail is explicit.** Every recovery writes a `DataPipelineRun` with `status=recovered` + the delta between `requested_inputs` and `effective_inputs` + the specialist's reasoning string.
5. **No recovery for 401 / 403 (auth).** Those route through Integrations' re-auth flow, not the specialist.

## Implementation sketch

- **PER-PRD-01:** Specialist config (Firestore `agents/pipeline_error_recovery` + tool functions); error-classification taxonomy (`transient` / `semantic_recoverable` / `auth` / `hard`); recovery-loop glue in `DataPipelineDispatcher`; audit extensions.
- **PER-PRD-02:** Eval harness — curated failure cases seeded from real Data Pipeline traces (once we have them). Golden-path + adversarial cases (specialist must NOT auto-resolve things that should escalate).
- **PER-PRD-03:** Admin UI for catalog-escalation notifications → suggested diff → one-click apply or dismiss.
- **PER-PRD-04:** Integration testing + rollout behind a feature flag (`pipeline_error_recovery_enabled`), per-account opt-in initially.

## When to promote out of backlog

Promote when **two conditions are both met**:

1. **Telemetry evidence** — Data Pipeline has been live for ≥30 days across ≥10 production accounts and we can point at a specific failure class accounting for ≥10% of semantic 4xx errors that a small input tweak would have resolved. Without data, we're designing against hypotheticals.
2. **Integrations component is stable** — IN-PRD-05 (re-auth lifecycle) is GA so the specialist only has to handle non-auth errors.

Until both are met, the v1 behavior (retry transient, fail + notify semantic) is acceptable. The notification routes to an admin; admins patch the catalog. Tax is real but bounded.

## What it is NOT

- **A reviewer loop.** The 5-iteration review pattern is for agents that emit text/code/artifacts to be critiqued. Pipelines emit deterministic data; there is nothing to critique.
- **A general "retry with different inputs" mechanism.** The specialist is scoped to *recovering from upstream API changes*, not brute-forcing inputs until something works. The latter would be a security and determinism disaster.
- **A substitute for catalog maintenance.** If an API changes fundamentally, the job catalog must be updated. The specialist can *propose* the update; it cannot *apply* it unilaterally.

## References

- [`../data-pipeline/implementation-plan.md`](../data-pipeline/implementation-plan.md) §3.3 (error handling), §10 (open questions)
- [`../agentic-harness/projects/AH-PRD-02-agent-factory.md`](../agentic-harness/projects/AH-PRD-02-agent-factory.md) — factory pattern this specialist follows
- [`../integrations/implementation-plan.md`](../integrations/implementation-plan.md) §5 — re-auth flow that covers the auth error class (out of scope for this specialist)
