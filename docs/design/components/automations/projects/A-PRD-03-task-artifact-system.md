# A-PRD-3 — Task Artifact System

**Status:** Ready for development (after A-PRD-1, PR-PRD-02, and PR-PRD-04 merge)
**Owner team:** Backend + Agent
**Blocked by:** A-PRD-1; PR-PRD-02 (ADK agent-tool plumbing — `attach_task_artifact` registers here); PR-PRD-04 (`TaskOrchestrator` — extended here to inject upstream-artifact prompt sections)
**Parallel with:** A-PRDs 2, 5, 6
**Estimated effort:** 3–4 days

**Forward-coordination — [DP-PRD-03](../../data-pipeline/projects/DP-PRD-03-task-system-integration.md):** the `DataPipelineDispatcher` writes pipeline output as a `TaskArtifact` via this PRD's `artifact_store.create()` Python API (§5 Non-agent creation path) using `created_by="data_pipeline:{job_id}"`. A-PRD-03 ships the API surface + the broadened `created_by` semantics described below; DP-PRD-03 calls it. No changes to the ADK tool path.

---

## 1. Context

When an automation runs, agent tasks generate outputs — ad copy, hero images, short product videos, structured JSON. Today these outputs disappear into the chat response with no persistent record. For automations to be testable, auditable, and chainable (downstream agents must consume upstream outputs), the system needs a structured artifact layer.

This PRD builds it: a GCS-backed storage tier for task outputs, an ADK tool agents call to attach artifacts to a task, an orchestrator extension that injects upstream-artifact references into downstream agent prompts, and the API endpoints the Outputs tab (A-PRD-6) consumes.

## 2. Scope

### In scope
- Dedicated GCS bucket `kene-task-artifacts-{env}` with a 30-day lifecycle deletion rule
- Artifact metadata model + Firestore sub-collection under each `PlanRun`
- 100MB per-artifact size cap (enforced at upload, rejected with 413)
- New ADK tool `attach_task_artifact` for agents to register outputs
- Orchestrator extension: when dispatching a downstream agent task, build a prompt section listing upstream artifacts (filename, mime type, signed URL with 1-hour expiry; for small text artifacts, inline content)
- API endpoints to list and download artifacts (signed URLs)
- Audit log entry on every artifact created
- Unit + integration tests; bucket lifecycle verification

### Out of scope
- Test-mode behavior (A-PRD-4) — though test runs DO save artifacts via this system
- Frontend rendering of artifacts (A-PRD-6)
- Artifact analytics / cost dashboards (future)

## 3. Dependencies

- **A-PRD-1:** `PlanRun` model + `accounts/{account_id}/plan_runs` subcollection (artifact sub-collection lives under each run)
- **Calendar PRD-2:** ADK tool registry, agent dispatch path; this PRD adds a tool that agents call from inside their execution
- **Calendar PRD-4:** `TaskOrchestrator` — the prompt-building helper for downstream dispatches lives here; this PRD adds upstream-artifact injection into that helper
- **DM-PRD-07 (Roles, Members, Audit Substrate):** hard prerequisite. The `attach_task_artifact` tool calls `write_audit(...)` on every artifact upload. **Coordination point:** DM-PRD-07's `project_plan_audit` registry currently lists `resource_types ⊇ {project_plan, plan_task, campaign, orphan_task, plan_run}` and `actions ⊇ {…, run_start, run_complete}`. This PRD requires an additive update to extend the registry with `resource_type="task_artifact"` and `action="attach_artifact"`. Land the registry update as a small additive PR against DM-PRD-07's `audit_registry.py` (no new audit subcollection; `project_plan_audit` already covers it). The list-artifacts and download endpoints are pure reads and do not write audit.
- **DM-PRD-05 (Deletion Sweep Rewrite):** soft coordination. DM-PRD-05's `firestore.recursive_delete(accounts/{account_id})` covers artifact metadata in Firestore but not the underlying GCS objects. v1 relies on the 30-day GCS lifecycle rule to sweep orphans; see §9 risks for the rationale and the future-enhancement path.
- **External:** Google Cloud Storage, signed URL generation
- **Existing files to study:**
  - `app/utils/gcs.py` (existing GCS helpers)
  - `app/adk/tools/registry/` (tool registration pattern)
  - `app/adk/agents/utils/dispatch_handlers.py` (agent prompt construction)

## 4. Data contract

> **Revised 2026-04-20** — Firestore paths for artifact metadata follow the Shape B layout (`accounts/{account_id}/plan_runs/{run_id}/artifacts/{artifact_id}`). See [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) for rationale.

### `TaskArtifact` (Pydantic + Firestore)

```
artifact_id: str                            # UUID
run_id: str
task_id: str
filename: str                               # original name; sanitized
mime_type: str                              # e.g., "text/markdown", "image/png", "video/mp4"
size_bytes: int                             # validated <= 100 MB
gcs_uri: str                                # gs://bucket/path
created_at: datetime
created_by: str                             # creator id — see "Creator identity" below
sha256: str                                 # for downstream content addressing
```

#### Creator identity

`created_by` is a string identifier of who created the artifact. Validation accepts any of:

| Prefix | Example | Source |
|---|---|---|
| `agent:<name>` | `agent:project_planning` | Agent name from the ADK registry. Default for the `attach_task_artifact` ADK tool path (§5 Upload flow). |
| `data_pipeline:<job_id>` | `data_pipeline:ga.transactions_by_date` | The `DataPipelineDispatcher` (DP-PRD-03) writing pipeline output through the non-agent creation path. `job_id` matches `^[a-z0-9_]+\.[a-z0-9_]+$` per DP-PRD-01. |
| `human:<email>` | `human:owner@acct.example` | Reserved for future human-uploaded artifacts. Not produced in v1. |

Validation rule: `created_by` MUST match `^(agent|data_pipeline|human):[\w@.\-]+$`. The ADK tool sets the `agent:<name>` prefix automatically from `tool_context.state["agent_name"]`; non-agent callers (the dispatcher) pass the full prefixed string explicitly.

### GCS layout

```
gs://kene-task-artifacts-{env}/
  {account_id}/{plan_id}/{run_id}/{task_id}/{artifact_id}_{sanitized_filename}
```

### Bucket lifecycle (Terraform)

```hcl
lifecycle_rule {
  condition { age = 30 }      # days since object creation
  action    { type = "Delete" }
}
```

### ADK tool: `attach_task_artifact`

```python
attach_task_artifact(
    filename: str,
    content_base64: str,           # binary content, base64-encoded
    mime_type: str,
) -> dict:
    """
    Returns:
      {"status": "success",
       "artifact_id": "...",
       "gcs_uri": "...",
       "signed_url": "https://...",
       "expires_at": "2026-04-20T14:00:00Z"}
    or:
      {"status": "error",
       "error": "size_limit_exceeded" | "invalid_mime_type" | ...}
    """
```

The tool resolves `account_id`, `plan_id`, `run_id`, `task_id` from `tool_context.state` (set by the dispatch handler when the orchestrator invokes the agent). Sets `created_by="agent:{tool_context.state['agent_name']}"`.

### Non-agent creation path: `artifact_store.create()`

```python
async def artifact_store_create(
    *,
    account_id: str,
    plan_id: str,
    run_id: str,
    task_id: str,
    filename: str,
    content: bytes,                # raw bytes — no base64 round-trip for non-agent callers
    mime_type: str,
    created_by: str,               # "data_pipeline:<job_id>" / "human:<email>" / "agent:<name>"
) -> TaskArtifact: ...
```

Same upload pipeline as the ADK tool (size check, sanitize filename, sha256, upload, Firestore write, audit log) — only the entry point differs. Used by the `DataPipelineDispatcher` (DP-PRD-03) to persist pipeline output as a `TaskArtifact`; future non-agent producers (e.g., scheduled exports) call the same function. Idempotency by `(account_id, run_id, task_id, sha256)`: a second create with identical content returns the existing artifact rather than writing a duplicate.

### Inline-vs-link threshold for downstream prompts

When the orchestrator builds a downstream agent's prompt:
- Text artifacts (`text/*`, `application/json`) under **64 KB** → inline content directly into the prompt
- Anything else → include filename, mime type, and a fresh signed URL (1-hour expiry)

```
Inputs from upstream tasks:

[Task: Generate ad copy]
ad_copy.md (text/markdown, 3.2 KB):
---
# Spring Sale — 30% Off Everything
...
---

[Task: Render hero image]
hero.png (image/png, 1.4 MB)
Download: https://storage.googleapis.com/...?signed=...
```

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | `api/src/kene_api/services/artifact_store.py` — GCS upload, signed URL, size validation. Exposes `create(...)` as the non-agent creation path; the ADK tool wraps it. |
| Create | `api/src/kene_api/models/task_artifact_models.py` — Pydantic `TaskArtifact` with `created_by` validator (`^(agent\|data_pipeline\|human):[\w@.\-]+$`). |
| Create | `api/src/kene_api/repositories/firestore_artifact_repository.py` |
| Create | `api/src/kene_api/routers/artifacts.py` (list + download endpoints) |
| Modify | `api/src/kene_api/main.py` — register router |
| Create | `app/adk/tools/builtin/attach_task_artifact.py` — thin wrapper around `artifact_store.create(...)` that resolves `created_by="agent:{agent_name}"` from `tool_context.state`. |
| Modify | `app/adk/tools/registry/config/tools.yaml` — register tool under `artifacts` category |
| Modify | `app/adk/agents/registry.py` — add `artifacts` capability to all agents that produce output (project_planning, others as needed) |
| Modify | `api/src/kene_api/services/task_orchestrator.py` (Calendar PRD-4) — `_build_downstream_prompt` injects upstream artifacts |
| Create | `deployment/terraform/gcs_task_artifacts.tf` (bucket + lifecycle + IAM) |
| Create | `api/tests/unit/test_artifact_store.py` — covers both the ADK-tool entry and the direct `artifact_store.create()` entry; asserts `created_by` validator rejects unprefixed names. |
| Create | `api/tests/unit/test_attach_artifact_tool.py` |
| Create | `api/tests/integration/test_artifacts_router.py` |
| Create | `api/tests/integration/test_artifact_lifecycle.py` (uses a 1-day lifecycle test bucket) |

### Upload flow

```
agent calls attach_task_artifact(...)         non-agent caller (e.g., DataPipelineDispatcher)
  │  resolves account_id/plan_id/run_id        │  passes ids + created_by="data_pipeline:<job_id>"
  │  task_id from tool_context.state           │  directly
  │  base64-decodes content                    │
  │  sets created_by="agent:<name>"            │
  ▼                                            ▼
                  artifact_store.create(account_id, plan_id, run_id, task_id, content, created_by, ...)
                    ├─ validate created_by prefix
                    ├─ size check (<= 100 MB) → reject with 413 if over
                    ├─ sanitize filename
                    ├─ compute sha256
                    ├─ idempotency check (existing artifact with same (run_id, task_id, sha256) → return it)
                    ├─ upload to GCS
                    ├─ write Firestore metadata doc
                    ├─ write audit log entry
                    └─ return TaskArtifact + signed_url (1-hour expiry)
```

### Downstream prompt injection (extends Calendar PRD-4)

When the orchestrator dispatches an agent task whose `depends_on` is non-empty:

```python
def _build_downstream_prompt(run, task) -> str:
    upstream_artifacts = []
    for upstream_task_id in task.depends_on:
        artifacts = artifact_repo.list_for_task(run.run_id, upstream_task_id)
        upstream_artifacts.extend((upstream_task_id, a) for a in artifacts)
    return prompt_template.render(
        task=task,
        project_goal=run.template_goal,
        upstream_artifacts=_format_artifacts(upstream_artifacts),
        revision_comment=task.revision_comment,
    )
```

`_format_artifacts` applies the inline-vs-link rule (64 KB threshold for text).

### Signed URL strategy

- Signed URLs are generated **per request** (not stored), with 1-hour expiry
- Agent prompts contain fresh URLs every dispatch — no stale-URL issues
- Frontend Outputs tab (A-PRD-6) calls the download endpoint each time the user clicks → fresh URL

### Cost model

A 100MB artifact consumed by 5 downstream agent tasks = ~500MB egress per run. At GCP pricing (~$0.12/GB egress), that's ~$0.06 per run. Hot automations firing every 15 minutes = ~$5/day. **Document this in the Risks section.** Mitigation: inline small text artifacts so only large/binary outputs cost egress.

### Audit events

Every successful `attach_task_artifact` call writes an audit entry via DM-PRD-07's `write_audit(...)` helper:

| Field | Value |
|-------|-------|
| `parent_kind` | `"account"` |
| `parent_id` | `{account_id}` |
| `audit_subcollection` | `"project_plan_audit"` |
| `resource_type` | `"task_artifact"` *(new — requires the additive registry update described in §3)* |
| `action` | `"attach_artifact"` *(new)* |
| metadata | `{artifact_id, run_id, plan_id, task_id, filename, mime_type, size_bytes, sha256, created_by_agent}` |

Failed uploads (size cap, mime allowlist, base64 decode) do **not** write audit — they're rejected before the metadata doc is created. The list-artifacts and download endpoints are pure reads and do not write audit.

## 6. API contract

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/automations/{account_id}/{plan_id}/runs/{run_id}/tasks/{task_id}/artifacts` | List artifacts for one task in one run |
| `GET` | `/api/v1/automations/{account_id}/{plan_id}/tasks/{task_id}/artifacts/recent` | List artifacts across last N runs (for the Outputs tab); query: `limit` (default 20), `is_test` filter |
| `GET` | `/api/v1/automations/{account_id}/{plan_id}/runs/{run_id}/artifacts/{artifact_id}/download` | Returns a fresh 1-hour signed URL (302 redirect or JSON `{url}`) |

All endpoints reuse the access-control dependency from A-PRD-1.

## 7. Acceptance criteria

1. An agent calling `attach_task_artifact` with a 1MB file returns success and the file is in GCS; the persisted `TaskArtifact.created_by` is `"agent:<agent_name>"` resolved from `tool_context.state["agent_name"]`.
2. Calling with a 150MB file returns `{"status": "error", "error": "size_limit_exceeded"}` and nothing is written
3. The file metadata appears in Firestore `accounts/{account_id}/plan_runs/{run_id}/artifacts/`
4. An audit log entry is created for every artifact
5. A downstream agent task receives upstream artifacts in its prompt — text under 64KB inlined, larger as a signed URL
6. `GET .../tasks/{task_id}/artifacts/recent` returns artifacts from the last 20 runs (configurable), most recent first
7. `GET .../artifacts/{artifact_id}/download` returns a fresh signed URL valid for 1 hour
8. The bucket lifecycle rule is configured in Terraform; an integration test against a 1-day-lifecycle test bucket confirms deletion after the rule's TTL elapses (mocked clock OK)
9. Cross-account access on any endpoint returns 403
10. `artifact_store.create()` accepts a non-agent caller passing `created_by="data_pipeline:ga.transactions_by_date"`, persists the artifact, and the prompt-builder treats it identically to agent-produced artifacts when injecting upstream context. `created_by` values not matching `^(agent|data_pipeline|human):[\w@.\-]+$` raise `ValidationError` at model construction.
11. Idempotency: two `artifact_store.create()` calls with the same `(account_id, run_id, task_id, sha256)` produce one Firestore doc and one GCS object; the second call returns the existing `TaskArtifact`.
12. All tests pass

## 8. Test plan

**Unit tests** (`test_artifact_store.py`):
- Upload: success path, 100MB exact (allowed), 100MB+1 byte (rejected)
- Filename sanitization: `"../etc/passwd"` → `"etc_passwd"`; unicode preserved
- SHA256 computation deterministic
- Mime type allowlist (text/*, application/json, image/*, video/mp4, application/pdf — any others?)
- Signed URL has 1-hour expiry

**Unit tests** (`test_attach_artifact_tool.py`):
- Tool resolves account_id/plan_id/run_id/task_id from tool_context.state
- Tool error response for missing context (no run_id → "tool used outside automation context")
- Base64 decode failure → clear error

**Integration tests** (`test_artifacts_router.py`):
- Upload via tool, list via endpoint, download via endpoint — full round-trip
- List recent across multiple runs, ordering correct
- `is_test` filter on recent endpoint excludes test-run artifacts when false, includes when true
- Cross-account: artifact uploaded under account A is invisible to account B (404, not 403, to prevent existence leak)

**Integration tests** (`test_artifact_lifecycle.py`):
- Spin up a test bucket with a 1-day lifecycle rule (or mock GCS lifecycle behavior)
- Upload an artifact, fast-forward 2 days, verify the object is gone
- Verify the Firestore metadata doc remains (with a `gcs_status: "deleted"` flag) — or is also cleaned up; **decision to confirm during implementation** (lean toward keeping the metadata as a tombstone for the audit trail)

## 9. Risks & open questions

| Risk / question | Mitigation |
|-----------------|------------|
| Egress cost runaway from large artifacts × many downstream tasks | Document in §5 cost model. Inline small text. Add a per-account egress dashboard in v2. |
| Mime type allowlist vs. open | Start with text/json/image/video/pdf. Reject unknown types initially; expand on user request. |
| Signed URLs leak via prompt logging | URLs expire in 1 hour. Don't log full prompt bodies in production traces — redact URLs in Weave. |
| Firestore metadata orphaned after GCS lifecycle deletion | Decision: keep metadata as tombstone with `gcs_status="deleted"` flag — preserves audit trail. Frontend grays out download button when tombstoned. |
| Concurrent uploads to the same task by the same agent | Each `attach_task_artifact` call generates a fresh `artifact_id`; multiple artifacts per task is supported and intentional. |
| Agents with binary outputs hitting base64 transport limits | Base64 inflates payloads ~33%. For 100MB max output, the agent tool call payload is ~133MB — verify ADK transport handles this. If not, switch to a presigned-PUT flow where the agent uploads directly to GCS. |
| Test-mode artifacts pollute the recent-artifacts list | The `is_test` filter in the recent endpoint defaults to `false`. Test-run artifacts are visible only when explicitly requested. |
| **Account deletion does not immediately purge GCS objects.** DM-PRD-05's `firestore.recursive_delete(accounts/{account_id})` clears Firestore (artifact metadata + audit), but the underlying GCS objects under `gs://kene-task-artifacts-{env}/{account_id}/...` are not deleted synchronously. | The 30-day GCS lifecycle rule sweeps orphaned objects within 30 days of upload; since artifacts always belong to a specific account, no cross-account leakage is possible during that window (signed URLs require server-side authorization to mint, and the serving endpoints reject queries on a deleted account_id). For accelerated cleanup, a future enhancement can add a `delete_account_artifacts(account_id)` GCS sweep hook called from DM-PRD-05's deletion path — track as a follow-up. v1 ships with lifecycle-only cleanup. |

## 10. Reference

- Parent plan: [`../README.md`](../README.md) §2 (Architectural pillar 3)
- Foundation: [A-PRD-1](./A-PRD-01-data-model-and-api.md), [Calendar PRD-4](../../project-tasks/projects/PR-PRD-04-event-driven-orchestrator.md)
- Pattern files: `app/utils/gcs.py`, `app/adk/tools/registry/config/tools.yaml`
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; D-2, D-5; T-1, T-3, T-4, T-5, T-6
