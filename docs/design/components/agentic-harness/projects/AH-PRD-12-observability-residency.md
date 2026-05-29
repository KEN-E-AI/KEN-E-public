# AH-PRD-12 — Observability Residency

**Status:** Ready to start
**Owner team:** [KEN-E] Agentic Harness
**Initiative:** Data Residency (US + EU)
**Blocked by:** DM-PRD-09 (regional-cell foundation), AH-PRD-11 (agent reasoning + inference residency)
**Blocks:** —
**Estimated effort:** 3–4 days

> **Program context.** Data residency is **not** a new component — this is a slice homed in Agentic Harness, bound to the **Data Residency (US + EU)** Linear Initiative and the cross-component spec [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md). Read that doc's §1–§4 (esp. §2 decisions, §3.2 regional-cell table "Traces / logs" row, §4 posture table "W&B / traces / logs" row), §5 gap register (R-02, R-12), §6 cut-line, §7 homing before this PRD. This project closes **R-02** (the single most urgent content-egress blocker) and **R-12**. It reuses the `Region` / `CELLS` registry + `resolve_account_region(account_id)` resolver shipped by DM-PRD-09 (`shared/residency/`) — it does **not** redefine them.

---

## 1. Context

KEN-E's agent observability has two egress paths, both currently global:

1. **W&B Weave (US SaaS) with full message-content capture (R-02 — the most urgent blocker).** Agent tracing is wrapped by `init_weave_if_needed()`, which calls `weave.init(project_name=...)` against W&B's US-hosted SaaS (`app/utils/weave_observability.py:109-114`, default project `ken-e-dev`; invoked at `app/adk/security/hooks.py:209`). Independently, GCP Agent Engine telemetry ships **full prompt + response content** to its trace sink when `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`. That flag is set per-**environment**, not per-**region** (`app/adk/deploy_ken_e.py:367-370`): `_capture_content = "false" if os.getenv("_TARGET_ENV") == "prod" else "true"`. So prod content capture is already off, but **dev/staging capture content for every account regardless of region**, and Weave (US SaaS) receives traces in all environments — the most direct egress of regulated EU content.

2. **Cloud Trace / Cloud Logging + the >250 KB large-attribute GCS bucket are global (R-12).** `CloudTraceLoggingSpanExporter` builds its Logging and Storage clients from a single `self.project_id` and defaults the overflow bucket to `f"{self.project_id}-logs-data"` (`app/utils/tracing.py:55-60`); spans over 250 KB spill full attribute payloads into that one bucket (`tracing.py:130-137`). Structured application logs flow through `StructuredFormatter` to the same global Cloud Logging sink (`shared/structured_logging.py:95-129`). None of this is routed by `data_region`, so an EU account's trace/log telemetry — and any large-attribute overflow — lands in the US.

The reference pattern for the fix is `storage_service.py:_get_bucket_config(data_region)` (`api/src/kene_api/services/storage_service.py:31-72`): a `data_region → (resource, location)` map with a US default. This PRD applies that pattern to the observability sinks, reusing DM-PRD-09's resolver rather than reinventing it.

**Independent landing note.** R-02's content-capture-off half is **largely deploy-config** (one expression in `deploy_ken_e.py` + a Weave gate) and can land **early, independent of the EU cell** — it does not require AH-PRD-11. The EU-resident trace/log sink + EU large-attribute bucket (R-12) **do** need the EU cell (AH-PRD-11), hence the blocked-by.

See [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) §2 (D1–D6), §3.2 (regional-cell "Traces / logs" row), §4 (posture: "W&B / traces / logs"), §5 (R-02, R-12).

## 2. Scope

### In scope

- **Region-aware content-capture gate (R-02).** Make `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` resolve from `(environment, data_region)` rather than environment alone — content capture **OFF for the EU cell in all environments**, and additionally off in prod (current behavior preserved). The EU agent deploy never captures message content.
- **Weave disposition for EU (R-02).** Gate `init_weave_if_needed()` so the EU cell does **not** initialize Weave against the US SaaS, OR (pending **open Q2**) point it at an EU-hosted / self-hosted Weave tier. Default chosen for launch: **no Weave + content-capture off for EU** unless Q2 confirms an EU tier exists.
- **Region-resident trace/log sink + large-attribute bucket (R-12).** Resolve the `CloudTraceLoggingSpanExporter` Logging client, Storage client, and overflow bucket from the cell's `CellConfig` (`tracing.py:55-60`), so EU traces, logs, and >250 KB overflow (`tracing.py:130-137`) write to EU-resident sinks/bucket. Structured logs (`structured_logging.py:95-129`) emit into the EU cell's Cloud Logging.
- **A small pure resolver** `resolve_observability_config(environment, data_region) -> ObservabilityCellConfig` (capture flag + Weave disposition + trace/log project + overflow bucket), modeled on `_get_bucket_config` and on AH-PRD-11's `resolve_model_location`. Built on DM-PRD-09's `Region` / `CELLS`.
- **EU large-attribute bucket Terraform** — an EU-resident `{eu-project}-logs-data` bucket (mirror of the existing US default), provisioned in the EU cell created by DM-PRD-09 / AH-PRD-11.

### Out of scope

- **Regionalizing any store other than observability sinks** — Firestore (DM-PRD-09), Neo4j (KG-PRD-07), KMS (IN-PRD-08), model/Agent Engine reasoning/sandbox/session (AH-PRD-11), Redis/artifacts (CH-PRD-07), usage/BigQuery (BL-PRD-07).
- **Defining `Region` / `CELLS` / `resolve_account_region`** — owned by DM-PRD-09; this PRD imports them.
- **Standing up the EU Agent Engine and EU trace destination plumbing for reasoning** — AH-PRD-11 owns the EU cell's engine + trace endpoint; this PRD consumes it.
- **MER-E evaluation pipeline residency** — the evaluation framework's own data plane is a separate concern; this PRD only governs what content leaves the agent runtime.
- **Negotiating / procuring an EU Weave tier** — that is the business decision behind open Q2; this PRD wires whichever disposition Q2 returns.

## 3. Dependencies

- **DM-PRD-09 complete** — provides `shared/residency/regions.py` (`Region`, `CellConfig`, `CELLS`, `normalize_region`, `DEFAULT_REGION`) and `routing.py::resolve_account_region`. This PRD reuses them; the EU GCP project (where the EU trace/log sink + bucket live) is created here.
- **AH-PRD-11 complete (for the R-12 half)** — the EU Agent Engine + EU cell must exist before EU-resident trace/log sinks have a home. R-02's content-capture-off half does **not** depend on AH-PRD-11 and may ship first.
- Reference pattern: `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region` routing) — the shape this PRD copies for sinks.
- Existing observability call sites refactored: `app/utils/weave_observability.py:109-114`, `app/adk/security/hooks.py:209`, `app/adk/deploy_ken_e.py:366-373`, `app/utils/tracing.py:55-60,130-137`, `shared/structured_logging.py:95-129`.
- **External / open:** **Q2** (W&B EU tier) and **Q8** (legal: may trace/log *metadata* live in a US sink for EU accounts) — see §9. Q8 sets the R-12 bar.

## 4. Data contract

### 4.1 Observability cell config (resolver output)

```python
# app/utils/residency_observability.py  (agent-runtime side; mirrors residency.regions shape)
from dataclasses import dataclass

@dataclass(frozen=True)
class ObservabilityCellConfig:
    capture_message_content: bool   # OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT
    weave_enabled: bool             # init Weave for this cell?
    weave_project_name: str | None  # EU tier project if weave_enabled and Q2 confirms a tier
    trace_log_project_id: str       # CellConfig.gcp_project_id — Cloud Trace/Logging sink project
    large_attr_bucket: str          # f"{trace_log_project_id}-logs-data"

def resolve_observability_config(
    environment: str, data_region: str
) -> ObservabilityCellConfig:
    """Pure resolver. EU → capture_message_content=False and weave_enabled per Q2;
    prod (any region) → capture_message_content=False (preserves current behavior);
    dev/staging US → capture_message_content=True. trace_log_project_id and
    large_attr_bucket derive from CELLS[normalize_region(data_region)]."""
```

### 4.2 Capture / sink rules (`(environment, data_region)` → posture)

| Environment / cell | `capture_message_content` | Weave | Trace / log sink + overflow bucket |
|---|---|---|---|
| `development` / `staging`, **US** | `true` (unchanged — debugging + MER-E) | US SaaS | US cell project + `{us-project}-logs-data` |
| `prod`, **US** | `false` (unchanged) | US SaaS | US cell project + `{us-project}-logs-data` |
| **any env, EU** | **`false`** | **disabled** (or EU tier per Q2) | **EU cell project + `{eu-project}-logs-data`** |

- The capture flag is applied **in-process at agent startup** in the EU cell's deploy, the same mechanism AH-PRD-11 uses for `GOOGLE_CLOUD_LOCATION` (Agent Engine injects ambient env vars, so a baked `.env` value is inert under `load_dotenv(override=False)`).
- The EU sink and bucket carry **no message content** (capture is off); whether they may still hold **metadata** (account_id / user_id / session_id / tool names / durations / token counts) in a US sink is the Q8 gating question — if legal says metadata-in-US is acceptable for EU accounts, R-12 collapses to content-capture-off only; if not, the EU sink is mandatory.

## 5. Implementation outline

| Action | File |
|---|---|
| Create | `app/utils/residency_observability.py` — `ObservabilityCellConfig`, `resolve_observability_config`; imports `Region` / `CELLS` from `shared/residency/regions.py` |
| Modify | `app/adk/deploy_ken_e.py:366-373` — replace the env-only `_capture_content` expression with `resolve_observability_config(env, data_region).capture_message_content`; set the OTEL var in-process for the cell being deployed |
| Modify | `app/utils/weave_observability.py:109-114` — gate `weave.init(...)` on `ObservabilityCellConfig.weave_enabled`; use `weave_project_name` when an EU tier is configured (Q2) |
| Modify | `app/adk/security/hooks.py:209` — skip `init_weave_if_needed()` when the cell's `weave_enabled` is False |
| Modify | `app/utils/tracing.py:55-60` — resolve `logging_client`, `storage_client`, and `bucket_name` from `ObservabilityCellConfig` (cell project + `{project}-logs-data`) instead of bare `self.project_id` |
| Modify | `app/utils/tracing.py:130-137` — overflow store targets the cell's `large_attr_bucket` |
| Modify | `shared/structured_logging.py:95-129` — ensure structured logs route to the cell's Cloud Logging project (no message content added to log fields) |
| Modify | `deployment/terraform/` — EU `{eu-project}-logs-data` bucket (`europe-west1`); mirror of the US default, in the DM-PRD-09 EU project |
| Modify | [`../README.md`](../README.md) — note observability sinks follow the Regional Cell routing convention (DM-PRD-09 §7.8) |
| Create | `app/tests/unit/test_residency_observability.py` |
| Create | `app/tests/unit/test_tracing_regional_sink.py` |

## 6. API contract

No new public HTTP surface. This PRD adds an internal resolver contract and constrains the agent-deploy + tracing init paths.

| Contract | Consumed by | Source of truth |
|---|---|---|
| `resolve_observability_config(environment, data_region) -> ObservabilityCellConfig` (capture flag + Weave disposition + trace/log project + overflow bucket) | Agent deploy (`deploy_ken_e.py`), Weave init (`weave_observability.py`), trace exporter (`tracing.py`) | `app/utils/residency_observability.py` |
| `Region` / `CELLS` / `normalize_region` | reused, not redefined | `shared/residency/regions.py` (DM-PRD-09) |
| EU agent deploy never sets `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` and never inits US-SaaS Weave | EU cell deploy pipeline | `app/adk/deploy_ken_e.py`, `app/utils/weave_observability.py` |
| EU `CloudTraceLoggingSpanExporter` writes traces, logs, and >250 KB overflow to EU-resident sinks/bucket | EU agent runtime | `app/utils/tracing.py` |

## 7. Acceptance criteria

1. `resolve_observability_config(env, "EU")` returns `capture_message_content=False` for **every** environment (`development`, `staging`, `prod`); `resolve_observability_config("development"|"staging", "US")` returns `True`; `resolve_observability_config("prod", "US")` returns `False` (current behavior preserved).
2. `resolve_observability_config(env, "EU").weave_enabled` is `False` by default (no Weave for EU); it is `True` only when an EU Weave tier is explicitly configured (Q2), in which case `weave_project_name` is the EU project and never the US default `ken-e-dev`.
3. With `data_region="EU"`, the agent-deploy path never sets `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true` (asserted against the refactored `deploy_ken_e.py:366-373` expression); a US dev/staging deploy still sets it `true`.
4. `init_weave_if_needed()` is a no-op (does not call `weave.init`) when the resolved cell config has `weave_enabled=False` (EU); it still initializes for US cells.
5. `CloudTraceLoggingSpanExporter` for an EU cell builds its Logging client, Storage client, and `bucket_name` from the EU `CellConfig` — `bucket_name == f"{eu_project_id}-logs-data"` — and a US cell resolves to `{us_project_id}-logs-data` (one resolver, region-keyed).
6. A >250 KB span in the EU cell stores its overflow payload in the EU `{eu-project}-logs-data` bucket, not the US bucket (asserted via mocked storage client target in `tracing.py:130-137`).
7. `resolve_observability_config` reuses DM-PRD-09's `CELLS` / `normalize_region` (no second `Region` enum or cell map is defined in `app/utils/`); an unknown `data_region` is handled by `normalize_region`'s rules (US default / `ValueError` on unknown non-empty).
8. EU Terraform applies in dev: the EU `{eu-project}-logs-data` bucket exists in `europe-west1` (operator-verified; not gated in CI).
9. `make lint` passes. `pytest app/tests/unit/test_residency_observability.py app/tests/unit/test_tracing_regional_sink.py` passes.
10. `lychee --config lychee.toml .` passes for the touched docs.

## 8. Test plan

### Unit (`test_residency_observability.py`)

- `resolve_observability_config` table-driven over `{development, staging, prod} × {US, EU}` asserting the `capture_message_content` matrix (AC-1) and `weave_enabled` default-off-for-EU (AC-2).
- EU + an explicitly-configured Weave tier → `weave_enabled=True`, `weave_project_name` is the EU project, never `ken-e-dev` (AC-2).
- `trace_log_project_id` / `large_attr_bucket` derive from `CELLS[Region.EU]` vs `CELLS[Region.US]` (AC-5); unknown region routed through `normalize_region` (AC-7).
- Weave-init gate: with `weave_enabled=False`, `init_weave_if_needed()` does not call `weave.init` (mock `weave`) (AC-4).

### Unit (`test_tracing_regional_sink.py`)

- `CloudTraceLoggingSpanExporter` constructed for EU → Logging/Storage clients and `bucket_name` derive from the EU `CellConfig`; for US → US bucket (AC-5).
- A mocked >250 KB span stores overflow into the EU `large_attr_bucket` (AC-6).

### Deploy-path (mocked `os.environ`)

- The refactored `deploy_ken_e.py` capture-flag expression never yields `"true"` for `data_region="EU"` in any env; still `"true"` for US dev/staging (AC-3).

### Operator-verified (not CI)

- EU `{eu-project}-logs-data` bucket present in `europe-west1` after Terraform apply (AC-8).

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| A stray Weave `weave.init` or content-capture set bypasses the resolver and ships EU content to US SaaS | Centralize on `resolve_observability_config`; gate the two known entry points (`weave_observability.py:109-114`, `deploy_ken_e.py:366-370`); grep-based review checklist item for direct `weave.init(` / `CAPTURE_MESSAGE_CONTENT` literals (mirrors DM-PRD-09's control-plane-isolation guard). |
| EU large-attribute overflow silently falls back to the US bucket if EU bucket is missing | `tracing.py:store_in_gcs` already warns + no-ops on a missing bucket; AC-8 verifies the EU bucket exists before EU sign-ups open; the cell-verification gate (design §6.1) blocks launch until EU telemetry provably stays in-cell. |
| ADK injects ambient env vars, so a baked `.env` capture flag is inert (same trap as AH-PRD-11's `GOOGLE_CLOUD_LOCATION`) | Apply the resolved capture flag **in-process at agent startup** in the EU deploy, not via `.env`. |
| Metadata (account_id/user_id/session_id/tool names) still leaves the EU cell even with content off | This is the Q8 legal question (below) — it sets whether the EU sink is mandatory or content-capture-off suffices. Default to the stricter posture (EU sink) until legal rules otherwise. |

### Open questions (carry from design doc §8)

- **Q2 — W&B Weave residency.** Does W&B offer an EU-hosted / self-hosted tier, or is the launch decision simply *no Weave + content-capture off for EU*? Determines `weave_enabled` / `weave_project_name`. Default assumption for this PRD: **no EU Weave** until Q2 confirms a tier.
- **Q8 — "regulated content" for traces/logs (gating).** Confirm with legal whether trace/log **metadata** (account_id, user_id, session_id, tool names, durations, token counts — **no message content**) may live in a **US sink** for EU accounts. **This sets the R-12 bar:** if metadata-in-US is acceptable, R-12 collapses to content-capture-off + EU overflow bucket only; if not, the full EU trace/log sink is mandatory before EU sign-ups open. **Needed before the R-12 half is built.**

## 10. Reference

- Program spec: [`../../../data-residency-architecture.md`](../../../data-residency-architecture.md) — §2 decisions, §3.2 regional-cell "Traces / logs" row, §4 posture "W&B / traces / logs" row, §5 gap register (R-02, R-12), §6 cut-line, §7 homing, §8 open questions (Q2, Q8).
- Foundation PRD (reused, not redefined): [`../../data-management/projects/DM-PRD-09-regional-cell-foundation.md`](../../data-management/projects/DM-PRD-09-regional-cell-foundation.md) — `Region` / `CELLS` / `resolve_account_region`.
- Sibling Agentic-Harness slice: [`./AH-PRD-11-agent-reasoning-inference-residency.md`](./AH-PRD-11-agent-reasoning-inference-residency.md) — EU Agent Engine + `resolve_model_location`; shares the in-process env-var application mechanism.
- Reference implementation: `api/src/kene_api/services/storage_service.py:31-72` (GCS `data_region` routing).
- Refactor targets: `app/utils/weave_observability.py:109-114`, `app/adk/security/hooks.py:209`, `app/adk/deploy_ken_e.py:366-373`, `app/utils/tracing.py:55-60,130-137`, `shared/structured_logging.py:95-129`.
- CLAUDE.md rules in scope: PY-1, PY-2, PY-7; C-4; T-1, T-4, T-6.
