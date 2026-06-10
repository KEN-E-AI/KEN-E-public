# AH-PRD-17 — Numerical Analyst Data Manipulation via BigQuery Pushdown

**Status:** Proposed (spec)
**Owner team:** Core AI / Agent Platform (backend) — cross-component with Data Pipeline + Data Management
**Blocked by:** Soft — the *scheduled-data* path reuses Data Pipeline's `bigquery_external_table` capability (designed, deferred to DP-PRD-06; `None` on all 8 GA jobs today — [DP-PRD-02 §… line 57](../../data-pipeline/projects/DP-PRD-02-google-analytics-connector.md)). The *live chat-time* path (this PRD's v1) does not depend on it. Per-account dataset layout coordinates with Data Management residency (DP-PRD-07 / SE-PRD-08).
**Blocks:** (1) the later optimization that routes cross-source joins direct specialist→analyst instead of through root; (2) a residual non-SQL compute fallback, only if telemetry shows demand.
**Release:** Later release — proposed **2 (Task Automation)** at the earliest. PO to confirm sequencing.
**Decision record:** origin — W&B trace `019eb275-be8a-7bdc-b07c-95c5281808ee` (ken-e-dev, 2026-06-10): the `numerical_analyst`'s built-in code executor re-emitted a ~50-row GA extract as a Python literal every retry, truncated at `max_output_tokens`, and looped (24→48→72 accumulated copies). **This PRD replaces an earlier "Sandboxed Code Executor (custom `BaseCodeExecutor`)" approach to the same problem** — a draft that was never committed as its own PRD; that approach is captured as §9 *Alternatives considered*. DESIGN-REVIEW-LOG entry to be added on acceptance.

> **Why this is its own PRD.** Today `numerical_analyst` runs on `BuiltInCodeExecutor()` — Gemini's network-isolated sandbox whose only data channel is the prompt. Any non-trivial dataset must be transcribed into tokens by the calling LLM and again by the executor LLM → lossy (truncation), expensive (data paid for as output tokens 2–3×), and hard-capped at the token limit. This PRD replaces code execution with **BigQuery pushdown**: data is staged once into a **per-account BigQuery dataset** (deterministically, never by an LLM), agents pass **table handles** (not rows), and the analyst manipulates the data by writing **SQL** that BigQuery executes. BigQuery *is* the sandbox and the scale engine — no Cloud Run service, no arbitrary host-code execution, and "any size" becomes real (GB–TB) instead of token-bounded. This is not a new substrate: the Data Pipeline component already lands per-account platform data as Parquet, already designed `bigquery_external_table` for SQL access over it, and already states that **"cross-platform joins happen in a downstream agent task, not inside the pipeline job"** ([data-pipeline/README](../../data-pipeline/README.md) :283–284). This PRD builds that downstream analyst.

---

## 1. Context

### 1.1 The failure being fixed

`numerical_analyst` is an isolated `AgentTool` whose leaf carries only `code_executor=BuiltInCodeExecutor()` (`app/adk/tools/agent_tools/numerical_analyst.py:125`). Isolation is required *today* because Gemini 2.5+ rejects combining the built-in `code_execution` tool with any function tool (`400 … all search tools`). When the GA specialist needed a per-channel aggregation over ~50 rows, it had no way to hand the data to the analyst except to paste it into the prompt as a Python literal; the analyst then re-pasted it into its own `executable_code` each retry, truncated, and looped. The data round-tripped through **two** LLM transcriptions — neither reliable, both billed as tokens.

### 1.2 Why SQL pushdown, not a better executor

The root problem is *moving structured data through LLM token streams*. Every fix has to make data flow **by reference**. The analyst then needs an engine that (a) manipulates data arbitrarily and (b) reads it by reference at any scale. BigQuery satisfies both, and uniquely among the options needs **no new compute infrastructure and runs no arbitrary host code**:

| Approach | Arbitrary manipulation | By-reference / any size | Isolation | New infra |
|---|---|---|---|---|
| `BuiltInCodeExecutor` (today) | Python ✅ | ❌ prompt-only → truncation | ✅ Google sandbox | none |
| `UnsafeLocalCodeExecutor` | Python ✅ | ✅ in-process | ❌ runs in Agent Engine proc w/ tenant creds | none |
| Custom `BaseCodeExecutor` → Cloud Run sandbox (old AH-PRD-17, §9) | Python ✅ | ✅ input files | ✅ remote, egress-denied | **new Cloud Run service** |
| **BigQuery pushdown (this PRD)** | **SQL** ✅ (joins/aggs/windows/pivots, any scale) | ✅ table handles | ✅ BQ is the sandbox; no host code | **none** (managed BQ) |

The ADK change is the smallest of all: the analyst stops being a code-executor leaf and becomes an ordinary `LlmAgent` with one **function tool** (`run_bigquery_sql`). Because there is no built-in `code_execution` tool in the request, the "all search tools" 400 no longer applies — the isolation invariant that shaped AH-PRD-15 simply dissolves.

### 1.3 What SQL does and does not cover (honest scope)

BigQuery SQL covers the **data-shaping** long tail — joins, aggregations, window functions, pivots, filtering — at any scale. It does **not** cover arbitrary computation (statistical modeling, ML, custom numeric algorithms, regex-heavy transforms). For KEN-E's marketing-analytics workload that data-shaping subset is the large majority; the genuine-compute residual (e.g. SAR-E-style VAR work) stays out of scope here and, if ever needed at chat time, is served by BQML / JS UDFs or the deferred Cloud Run fallback (§9). This PRD's claim is **"any SQL-expressible manipulation, at any scale,"** not "any computation."

## 2. Scope

### In scope

- **`run_bigquery_sql` function tool** — new `app/adk/tools/function_tools/run_bigquery_sql.py`. Accepts a **SELECT-only** statement, validates it, runs it in BigQuery with a tool-assigned destination table in the **current account's dataset**, and returns `{result_table, schema, row_count, preview, bytes_scanned, truncated}` — a *handle plus a capped preview*, never the full result rows.
- **Deterministic data staging** — an `after_tool_callback` on the live GA MCP data tools (`run_report_mt`, …) that loads the in-memory JSON result into a per-account BigQuery table via `client.load_table_from_json` and **rewrites the model-visible tool response** to `{staged_table, schema, row_count, preview}`. The rows never re-enter the model. (Scheduled-data path: activate Data Pipeline's `bigquery_external_table` so already-landed per-account Parquet is SQL-addressable — out of scope to *build*, in scope to *consume*.)
- **Per-account dataset + isolation invariant** — a per-account dataset (`<prefix>_<account_id>`) created on first use in the account's residency region, with a default table expiration of **2 days** (`defaultTableExpirationMs`). A **query-scope validator** dry-runs every statement, extracts referenced tables, and rejects any reference outside the current account's dataset *before* execution. `maximum_bytes_billed` caps cost per job.
- **Numerical-analyst rewire** — replace `BuiltInCodeExecutor()` with the `run_bigquery_sql` tool; update the leaf instruction to "write SQL over the staged table(s); never paste raw rows." Keep `capture_agent_tool_usage` for billing parity.
- **Root-mediated orchestration (v1)** — **every hop routes through the root agent**: a data specialist (e.g. GA) stages a table and reports the handle to root; root dispatches `numerical_analyst` with the table handle(s) + a manipulation description; the analyst returns the final table handle + preview to root; root presents it. (Direct specialist→analyst delegation for single-source work is a deferred optimization — §2 *Out of scope*.)
- **Build-time backend gate** — `system_settings/harness.analyst_backend` (`builtin` | `bigquery_sql`, Firestore-live with TTL, no redeploy), defaulting to `builtin` until cutover.
- **Output bridge** — small final results flow to the user through the existing `create_visualization` / `response_artifacts` path (`api/src/kene_api/chat/artifacts.py:335`); large intermediates stay in BigQuery as handles.

### Out of scope (deferred)

- **Conditional / direct routing.** v1 always routes through root (PO decision). Routing single-source work direct specialist→analyst, and reserving root only for cross-source joins, is a later enhancement.
- **The non-SQL compute tail** (stats/ML/custom algorithms): BQML / UDFs or the Cloud Run fallback (§9), only on demonstrated demand.
- **Building** `bigquery_external_table` provisioning (owned by Data Pipeline, DP-PRD-06).
- **A per-account UI rollout** via Feature Flags (build-time/request-time gap — §9-R7); v1 gates per-env via `system_settings`.
- **DML/DDL by the model.** The tool accepts SELECT only; destination tables are tool-managed.

## 3. Dependencies

| Dependency | Why |
|---|---|
| Data Pipeline `bigquery_external_table` (DP-PRD-06, deferred) + per-account Parquet artifacts (`gs://kene-task-artifacts-{env}/{account_id}/…`) | The scheduled-data path's SQL surface. |
| `numerical_analyst.py` + `agent_tool_registry` + `roster.py` (AH-PRD-15) | Where the backend is swapped and the leaf is built. |
| `system_settings/harness` + `system_settings.py` (AH-93) | TTL'd Firestore pattern for `analyst_backend`. |
| Per-account convention (`accounts/{account_id}/…`) + residency cells (DP-PRD-07 / SE-PRD-08, Data Management) | Per-account dataset layout + region. |
| Agent-Engine runtime SA → BigQuery (`roles/bigquery.dataEditor` + `roles/bigquery.jobUser` on account datasets) | The staging callback and `run_bigquery_sql` run **in-process** in the Agent Engine; no new service, no OIDC dance. |
| `register_artifact` + `response_artifacts` (AH-PRD-04) | Surface final results to the user. |
| `google-cloud-bigquery` client | New dependency in `app/adk` deploy trees (pin in both; add `verify_deploy_tree.py` import check). |
| Root dispatch machinery (AH-PRD-09 per-turn dispatch; `sub_agent_attacher`) | Make `numerical_analyst` root-dispatchable. ⚠️ touches KEN-E's task-mode dispatch (known sharp edges — §9-R8). |

## 4. Data Contract

### 4.1 Per-account dataset

- **Dataset:** `kene_analyst_<account_id>` (or env-prefixed), created on first use in the account's **residency region** (BQ datasets are region-bound; cross-region joins are impossible — co-location per account is mandatory).
- **Default TTL:** `defaultTableExpirationMs = 2 days`. Both staged inputs and results inherit it; no manual cleanup.
- **Table classes:** `stg_<source>_<uuid>` (staged inputs), `res_<uuid>` (analyst results). Names are tool-assigned, never model-authored.

### 4.2 Staged-input handle (returned to the model in place of rows)

```jsonc
{ "staged_table": "kene_analyst_<account_id>.stg_ga_<uuid>",
  "schema": [{"name":"date","type":"DATE"},{"name":"channel","type":"STRING"},{"name":"val","type":"INT64"}],
  "row_count": 52,
  "preview": [ {"date":"2026-05-01","channel":"Direct","val":3}, "...first 5 rows..." ] }
```

### 4.3 `run_bigquery_sql` tool I/O

```jsonc
// input
{ "sql": "SELECT channel, SUM(val) AS engaged FROM kene_analyst_<acct>.stg_ga_<uuid> GROUP BY channel" }
// output (success)
{ "result_table": "kene_analyst_<acct>.res_<uuid>",
  "schema": [...], "row_count": 6,
  "preview": [{"channel":"Direct","engaged":31}, "...≤ N rows..."],
  "bytes_scanned": 18342, "truncated": false }
// output (rejected — never raises into the flow)
{ "error": "scope_violation", "detail": "table 'other.tbl' is outside dataset kene_analyst_<acct>" }
```

### 4.4 `system_settings/harness` additions

```jsonc
{ "analyst_backend": "builtin",          // "builtin" | "bigquery_sql"
  "analyst_sql_max_bytes_billed": 1073741824,   // 1 GiB cost cap per job
  "analyst_dataset_ttl_days": 2,
  "analyst_preview_rows": 20 }
```

## 5. Implementation Outline

### 5.1 End-to-end flow (root-mediated, v1)

```
1. root → google_analytics_specialist: "pull engaged sessions by channel + date"
2. GA specialist runs run_report_mt (GA MCP) → JSON rows
   └─ after_tool_callback (trusted, in-process, NO LLM):
        • ensure dataset kene_analyst_<acct> (account region, 2-day TTL)
        • client.load_table_from_json(rows, "stg_ga_<uuid>")
        • REWRITE model-visible response → { staged_table, schema, row_count, preview(5) }
3. GA specialist → root: "staged at kene_analyst_<acct>.stg_ga_<uuid> (schema …, 52 rows)"
4. root → numerical_analyst: "aggregate engaged sessions per channel; table: kene_analyst_<acct>.stg_ga_<uuid>"
5. numerical_analyst writes SELECT … GROUP BY channel and calls run_bigquery_sql(sql):
        • validator: parse SELECT-only; DRY-RUN to (a) extract referenced tables, (b) estimate bytes
        • reject if any table ∉ dataset, if not SELECT, or if est. bytes > cap
        • run with destination = res_<uuid> (TTL inherited), maximum_bytes_billed, job labels {account_id,session_id,agent}
        • return { result_table, schema, row_count, preview, bytes_scanned }
6. numerical_analyst → root: "result at kene_analyst_<acct>.res_<uuid> — Direct 31, Organic Search 22, …"
7. root presents the preview to the user; if a chart is wanted, the small result → create_visualization → response_artifacts
```

The rows live in BigQuery the entire time. Only handles + small previews ever touch an LLM.

### 5.2 The SQL tool + validator (sketch)

```python
# app/adk/tools/function_tools/run_bigquery_sql.py
async def run_bigquery_sql(sql: str, tool_context) -> dict:
    acct = tool_context.state["account_id"]
    ds = _dataset_for(acct)                       # kene_analyst_<acct>, region-correct, TTL set
    if not _is_single_select(sql):                # sqlglot parse; reject DML/DDL/multi-statement
        return {"error": "not_select", "detail": "only a single SELECT is allowed"}
    dry = _client.query(sql, job_config=QueryJobConfig(dry_run=True, maximum_bytes_billed=_CAP))
    refs = _referenced_tables(dry)                # from the dry-run plan / sqlglot
    bad = [t for t in refs if not t.startswith(ds + ".")]
    if bad:
        return {"error": "scope_violation", "detail": f"{bad} outside {ds}"}
    if dry.total_bytes_processed > _CAP:
        return {"error": "cost_cap", "detail": f"{dry.total_bytes_processed} > {_CAP}"}
    dest = f"{ds}.res_{_uuid()}"
    job = _client.query(sql, job_config=QueryJobConfig(
        destination=dest, maximum_bytes_billed=_CAP, labels={"account_id": acct, ...}))
    rows = list(job.result(max_results=_PREVIEW))
    return {"result_table": dest, "schema": _schema(job), "row_count": job.num_dml... ,
            "preview": [dict(r) for r in rows], "bytes_scanned": job.total_bytes_billed}
```

Belt-and-suspenders isolation: SELECT-only parse + dry-run reference extraction + per-account default-dataset scoping + `maximum_bytes_billed`. The validator is the security boundary (§9-R1).

### 5.3 Staging callback

`after_tool_callback` registered on the GA MCP data tools: `(tool, args, tool_context, tool_response) -> dict | None`. It (a) materializes `tool_response` rows into `stg_<source>_<uuid>` via `load_table_from_json`, (b) returns the rewritten `{staged_table, schema, row_count, preview}` so the model never sees the rows, (c) appends the handle to `state["staged_tables"]` for root/analyst reference. **No LLM authors the load** — this is the single most important invariant; an LLM-authored `INSERT … VALUES` would reintroduce the truncation bug (§9-R3).

### 5.4 Analyst rewire + root dispatch

- `numerical_analyst`: drop `code_executor=BuiltInCodeExecutor()`, add `tools=[run_bigquery_sql]`, keep `capture_agent_tool_usage`, swap the instruction to SQL-authoring. It is now an ordinary `LlmAgent` with a function tool → no isolation constraint.
- Make it **root-dispatchable** (move from the GA specialist's `tool_ids` to a root-reachable analyst) so root mediates every hop. Reuse AH-PRD-09 per-turn dispatch; verify against the known task-mode dispatch edges with a real-LLM staging turn (§9-R8).
- Gate: `_select_analyst()` reads `system_settings/harness.analyst_backend`; `builtin` preserves today's behavior exactly until cutover.

### 5.5 Packaging

- New modules under `app/adk/tools/function_tools/` → packaged in both deploy trees; pin `google-cloud-bigquery` in both `app/adk` and the strategy tree; add a `verify_deploy_tree.py` import-resolution assertion (cf. `agent-engine-two-deploy-trees`, `agent-engine-requirements-adk-skew`).
- Grant the Agent-Engine runtime SA `roles/bigquery.dataEditor` + `roles/bigquery.jobUser` (scoped per env/project). Terraform under `deployment/terraform/`.

## 6. API Contract

- **`run_bigquery_sql(sql: str) -> dict`** — §4.3. SELECT-only; returns a handle + capped preview; never raises into the ADK flow (validation/cost/scope failures map to a structured `{error,…}` the model can read and react to).
- **GA MCP `after_tool_callback`** — rewrites the data tools' response to a handle + preview (§4.2); idempotent within a turn.
- **No public API change.** Chat/streaming surface unchanged; final results ride the existing `response_artifacts` → `ChatResponse.artifacts` path.

## 7. Acceptance Criteria

- **AC-1** With `analyst_backend="bigquery_sql"`, the `019eb275` per-channel aggregation returns a correct, complete result with **no full dataset inlined into any LLM request/response — only the capped preview (≤`analyst_preview_rows` rows) and table handles appear** (verified in the W&B trace); the GA result is staged to `kene_analyst_<acct>.stg_…`; the analyst's SQL is a `GROUP BY` SELECT; a `res_…` handle returns to root. No truncation loop.
- **AC-2** The GA result reaches BigQuery via the deterministic callback (`load_table_from_json`), **never** via an LLM-authored `INSERT`; the analyst's model output references only the staged-table handle.
- **AC-3** Query-scope isolation: a SELECT referencing a table outside the current account's dataset is rejected at dry-run *before* execution; returns a clean `scope_violation`; no cross-tenant read occurs.
- **AC-4** SELECT-only enforced: `DROP` / `DELETE` / `INSERT` / multi-statement scripts are rejected (`not_select`).
- **AC-5** Cost guard: every job sets `maximum_bytes_billed`; a query whose dry-run estimate exceeds the cap is rejected (`cost_cap`); no unbounded scan runs.
- **AC-6** TTL: staged + result tables carry ≤2-day expiration (verify `expirationTime`/dataset default).
- **AC-7** Every hop routes through root: the trace shows GA-specialist→root (handle), root→analyst (handle + instruction), analyst→root (final handle + preview). No direct specialist→analyst edge in v1.
- **AC-8** Residency: the dataset is created in the account's cell region; a reference to a table in another region is rejected.
- **AC-9** Backend flip via `system_settings/harness.analyst_backend` takes effect within the TTL with no redeploy; default `builtin` preserves current behavior (regression-safe).
- **AC-10** New modules import + unpickle in both deploy trees (`verify_deploy_tree.py`).

## 8. Test Plan

- **Unit (pure):** the SQL validator (SELECT-only via `sqlglot`; reference extraction from a fake dry-run plan; scope rejection; cost rejection); dataset/handle naming + TTL config; staging callback (`load_table_from_json` + response rewrite to handle+preview) against a fake BQ client. Colocated `test_run_bigquery_sql.py`, `test_ga_staging_callback.py`.
- **Integration (DB-touching, separated per T-4):** against a real sandbox BQ dataset — stage→query→destination table→TTL→`INFORMATION_SCHEMA` cost; a real cross-dataset reference rejected (AC-3); a DDL probe rejected (AC-4); a cost-bomb probe rejected (AC-5).
- **Real-LLM staging turn (mandatory — mirrors the `builtin_google_search` lesson):** replay the `019eb275` query on real Gemini with `analyst_backend="bigquery_sql"`; assert no full dataset is inlined (only capped previews + handles) in the W&B trace, correct numbers, and handles flowing through root (AC-1/2/7). Mocked-LLM ACs cannot prove the model stopped inlining data.
- **Security probes:** ask the analyst to read another account's dataset (→ `scope_violation`); ask it to `DROP`/`DELETE` (→ `not_select`).
- **Cost/latency:** confirm output-token drop vs the builtin baseline on the GA-aggregation turn; record per-query `bytes_scanned`.

## 9. Risks, Open Questions & Alternatives Considered

### Risks

- **R1 — Scope-escape / SQL injection.** Model-authored SQL could try to read another account's dataset. Mitigation is layered: SELECT-only parse + dry-run reference extraction + per-account default-dataset scoping + `maximum_bytes_billed`. The validator is the tenant boundary and must be airtight; treat it as security-critical code with adversarial tests. Open Q: parse-based reference extraction (`sqlglot`) vs trusting the dry-run plan — use both (defense in depth).
- **R2 — SQL ≠ all computation.** Covers data-shaping at any scale, not arbitrary stats/ML (§1.3). Residual served later by BQML/UDFs or the Cloud Run fallback; do not over-claim "any manipulation."
- **R3 — Getting data IN must stay deterministic.** The live-GA path *must* load via in-process code; an LLM-authored `INSERT` reintroduces truncation. Enforced by the staging callback + a lint/review rule that the analyst instruction never asks for row-level DML.
- **R4 — Cost.** Model SQL can scan a lot. `maximum_bytes_billed` + dry-run estimate gate + small staged tables + 2-day TTL; monitor via `INFORMATION_SCHEMA.JOBS` and a Cloud Monitoring alert. (Note the staging-Firestore-bill precedent — measure before prod.)
- **R5 — Latency (accepted for v1).** Routing every hop through root adds LLM turns; plus BQ job startup (sub-second–seconds). Accepted per PO decision; the cross-source-only routing optimization (§2 out-of-scope) is the relief valve.
- **R6 — Residency.** Per-account datasets are region-bound and cannot be joined across regions; the dataset must be created in the account's cell (DP-PRD-07 / SE-PRD-08). Coordinate the layout with Data Management.
- **R7 — Build-time vs request-time gating.** Backend is chosen at leaf construction; `is_feature_enabled` needs request scope. v1 gates per-env via `system_settings`; per-account UI rollout deferred.
- **R8 — Dispatch wiring.** Making `numerical_analyst` root-dispatchable touches KEN-E's task-mode dispatch, which has known sharp edges (FunctionCall-by-doc_id, `finish_task` output surfacing, per-turn `tools_dict` snapshotting). Needs the real-LLM staging test (AC-7) before prod, not just mocked ACs.
- **R9 — Deploy skew.** `google-cloud-bigquery` must be pinned in both deploy trees; the `verify_deploy_tree.py` check (AC-10) is the guard.

### Open questions

1. Scheduled path: consume Data Pipeline's `bigquery_external_table` (Parquet-backed external tables) vs. always-native loaded tables for uniformity? (Lean: external for already-landed scheduled data, native `load_table_from_json` for live GA — both in the same per-account dataset.)
2. Dataset granularity: one `kene_analyst_<account_id>` dataset vs. one shared dataset with per-account table prefixes? (Lean: per-account dataset — cleaner isolation + a natural residency + TTL boundary.)
3. Result handoff to the user for non-aggregated results larger than the preview cap — paginate a fetch tool, or always require the analyst to reduce to a presentable size? (Lean: latter; the analyst's job is to produce a small final answer.)

### Alternatives considered (the earlier sandboxed-executor approach is the first entry)

- **Custom `BaseCodeExecutor` → egress-denied Cloud Run sandbox** (the prior AH-PRD-17 design). *Pros:* arbitrary Python, full isolation, by-reference input files. *Cons:* a whole new `kene-code-sandbox-{env}` service + image + VPC-egress-deny + per-request process isolation; still memory-bounded (no real "any size"); runs untrusted model code (smaller blast radius than in-process, but non-zero). **Deferred** to a fallback for the non-SQL compute tail *if* telemetry shows demand. This approach was never committed as its own PRD; it is summarized here for the record.
- **`UnsafeLocalCodeExecutor`.** Rejected: `exec`s model code inside the Agent Engine process next to every tenant's `ga_credentials`/`meta_credentials`/KMS-decrypted tokens in `session.state`.
- **`BuiltInCodeExecutor` (status quo).** The truncation-loop failure this PRD fixes; retained as the `builtin` default behind the gate until cutover.

## 10. Reference

- W&B trace `019eb275-be8a-7bdc-b07c-95c5281808ee` (ken-e-dev) — the truncation-loop incident.
- [data-pipeline/README](../../data-pipeline/README.md) :82, :283–284 (per-account Parquet artifacts; `bigquery_external_table`; "cross-platform joins happen in a downstream agent task"); [DP-PRD-02](../../data-pipeline/projects/DP-PRD-02-google-analytics-connector.md) :57 (external-table provisioning deferred); [DP-PRD-07](../../data-pipeline/projects/DP-PRD-07-data-pipeline-residency.md) + [SE-PRD-08](../../sar-e/projects/SE-PRD-08-sar-e-performance-residency.md) (residency).
- [AH-PRD-15 — AgentTool migration cutover](./AH-PRD-15-agenttool-migration-cutover.md) §2 (the isolation invariant this PRD dissolves); [AH-PRD-09 — per-turn dispatch](./AH-PRD-09-per-turn-dispatch.md) (root dispatch); [AH-PRD-04 — data visualization](./AH-PRD-04-data-visualization.md) (`register_artifact` / `response_artifacts`).
- In-tree integration points: `app/adk/tools/agent_tools/numerical_analyst.py:125`, `app/adk/agents/agent_factory/roster.py`, `api/src/kene_api/chat/artifacts.py:335`, `system_settings.py` (AH-93).
