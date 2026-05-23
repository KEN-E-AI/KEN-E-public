# AH-PRD-03 — Google Analytics Specialist

**Status:** Blocked
**Owner team:** Core AI / Agent Platform
**Blocked by:** AH-PRD-01 (review-loop framework), AH-PRD-02 (agent factory — config schema + `_make_header_provider`), [AH-PRD-09](./AH-PRD-09-per-turn-dispatch.md) **Phase 2** (single-dispatch root + `specialist_runtime`) and **Phase 3** (`McpToolsetPool` + `kind="cloud_run"` field on `mcp_servers/*`)
**Parallel with:** Data-management projects (DM-PRDs run on a separate path), Skills SK-PRDs, Project-Tasks PR-PRDs that don't touch GA
**Blocks:** Future narrow-specialist sprints (Google Ads, Meta Ads, Mailchimp — see [README §2.6](../README.md#26-specialist-roadmap)) — this project is their reference pattern
**Estimated effort:** 5 stories (originally Sprint 10). ≈ 5–7 days.

---

> **Credential-loading migration note.** This PRD consumes the `_make_header_provider("ga_oauth")` factory from AH-PRD-02 and the session-state `ga_credentials` key. Both are retrofitted by [Integrations](../../integrations/implementation-plan.md) **IN-PRD-06** to read credentials from the Integrations internal endpoint (`GET /api/v1/internal/integrations/credentials/{account_id}/google`) instead of session state. **Not a blocking dependency** — ship AH-PRD-03 as specified; the multi-tenant OAuth isolation in §2 acceptance criteria continues to hold after IN-PRD-06 because the per-account scoping moves from session-state keys to Integrations' per-account `PlatformConnection` records. The GA specialist's dispatch, review-loop integration, and code-execution behavior are unchanged by the migration.

## 1. Context

AH-PRD-02 delivered the config-driven agent factory and AH-PRD-09 ships the per-turn runtime successor that replaces deploy-time specialist construction with `specialist_runtime` + a single `delegate_to_specialist` root tool. This project validates the combined stack end-to-end by registering the **first** narrow specialist — the Google Analytics Specialist — entirely through the config-driven runtime path. By the end of this project KEN-E can query Google Analytics via the GA MCP server, perform accurate numerical analysis (percentages, trends, averages) using Gemini's built-in code execution instead of in-context arithmetic, and guarantee output quality through review-loop iteration. It also retires the transitional `google_analytics_agent_v4.py` that the R1.0 hardcoded pattern installed, migrating fully to the runtime-resolved narrow-specialist pattern.

The project has two phases. **Phase 1** creates the agent config document at `agent_configs/google_analytics_specialist` (model, instruction, `mcp_servers=["google_analytics_mcp"]`, `code_execution_enabled=true`) and patches the `mcp_servers/google_analytics_mcp` document so the runtime resolver picks GA up via the next chat turn's "Available Specialists" block and dispatches via `delegate_to_specialist("google_analytics_specialist", query, criteria)`. `google_analytics_agent_v4.py` is marked deprecated with a removal note. **Phase 2** validates the full stack: review-loop integration (reviewer evaluates data accuracy, completeness, and calculation correctness — `build_review_pipeline()` is invoked inside `delegate_to_specialist`), Gemini code execution for numerical analysis (`executable_code` + `code_execution_result` parts in responses), multi-tenant OAuth isolation via the `_make_header_provider("ga_oauth")` factory (preserved from AH-PRD-02, consumed by the AH-PRD-09 `McpToolsetPool`), and end-to-end tests with Weave trace structure verification.

This is the **proof point** for the full Release 1 harness stack: per-turn dispatch (AH-PRD-09) + review loop (AH-PRD-01) + code execution + multi-tenant auth, all working together against a real data source. The R5-planned specialists (Google Ads, Meta Ads, Mailchimp — see [README §2.6](../README.md#26-specialist-roadmap)) follow the pattern established here — `specialist_runtime` is the construction mechanism, the review loop is the quality gate, and this project sets the recipe.

## 2. Scope

### In scope
- **Phase 1: Agent definition & migration**
  - `agent_configs/google_analytics_specialist` Firestore document: model, instruction, temperature, description, `mcp_servers=["google_analytics_mcp"]`, `code_execution_enabled=true`. `specialist_runtime.resolve_agent` (AH-PRD-09 Phase 2) constructs the `LlmAgent` per turn; `specialist_runtime.resolve_config` reads this document via `config_cache`, and the runtime MCP path (AH-PRD-09 Phase 3) wires a `McpToolset` through `McpToolsetPool` with `header_provider=_make_header_provider("ga_oauth")`.
  - `mcp_servers/google_analytics_mcp` document updated with `kind="cloud_run"` (AH-PRD-09 Phase 3 schema), `specialist_categories=["analytics"]`, and `auth_type="ga_oauth"` if not already present.
  - Mark `google_analytics_agent_v4.py` deprecated with a banner comment + removal date. No root-agent code changes: the runtime resolver's `available_specialists_provider` renders GA into the root's "Available Specialists" block on the next chat turn, and the root reaches it via `delegate_to_specialist("google_analytics_specialist", query, acceptance_criteria)` — the single dispatch tool established by AH-PRD-09 Phase 2. Existing query patterns ("Show me traffic trends for the past week") route correctly under standard LLM tool-calling.
  - All GA tools visible on every turn (no per-turn `tool_filter` needed — specialist stays under ~30 tools).
- **Phase 2: Quality & capabilities**
  - Review-loop integration — when the Root Agent generates `acceptance_criteria`, `delegate_to_specialist` wraps the resolved specialist in `build_review_pipeline()` from AH-PRD-01 before invoking it through the inner `Runner`. The reviewer evaluates data accuracy, completeness, and calculation correctness.
  - Gemini code execution — enabled via `code_execution_enabled=true` at construction; `specialist_runtime.resolve_agent` adds `Tool(code_execution=ToolCodeExecution())` to `GenerateContentConfig.tools` when the flag is set. Instruction directs the LLM to use code execution for all numerical analysis (percentage changes, trend calculations, averages, sorting, comparisons). `executable_code` and `code_execution_result` parts appear in responses.
  - Code-execution error handling — on `OUTCOME_FAILED`, specialist retries with corrected code or reports the calculation error clearly to the user.
  - OAuth error handling — on expired GA OAuth token, `_requires_reauth` is set in session state and a clear error message is returned.
  - Multi-tenant isolation — two concurrent sessions with different `ga_credentials` each use their own OAuth tokens. The `McpToolsetPool` (AH-PRD-09 Phase 3) keys entries on `(server_id, account_id, sha256(auth_credentials))`, so each account's tokens flow through its own `header_provider` closure and pooled `McpToolset`.
  - End-to-end tests covering: happy path ("Show me traffic trends for the past week"), code-execution failures, OAuth error handling, multi-tenant concurrency, Weave trace verification (`delegate_to_specialist` span → `load_config_from_firestore` → review-loop iterations → specialist + reviewer sub-spans).

### Out of scope
- Google Ads, Meta Ads, Mailchimp specialists — deferred to future sprints (see [README §2.6](../README.md#26-specialist-roadmap)).
- Skill attachment — the GA specialist ships without skills; skills wiring is SK-PRD-02's job.
- Any change to the GA MCP server implementation itself — KEN-E consumes the existing SSE endpoint.
- Removal of `google_analytics_agent_v4.py` — deprecation banner only; removal happens in a follow-up once no callers remain.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[AH-PRD-01](./AH-PRD-01-review-loop-framework.md)** | `build_review_pipeline()` wraps the specialist when `acceptance_criteria` is provided. Review loop must ship first to enable AC #4. | This component |
| **[AH-PRD-02](./AH-PRD-02-agent-factory.md)** | Config schema (`agent_configs/*`, `mcp_servers/*`, `MergedAgentConfig`), `_make_header_provider("ga_oauth")` factory, multi-tenant overlay model. Dispatch generation and deploy-time specialist construction are superseded by AH-PRD-09 — see next row. | This component |
| **[AH-PRD-09](./AH-PRD-09-per-turn-dispatch.md)** | **Hard blocker.** Phase 2 provides `delegate_to_specialist` (the single root tool GA is reached through) and `specialist_runtime` (per-turn resolver that reads `agent_configs/google_analytics_specialist`, applies any per-account overlay, and builds the `LlmAgent` lazily). Phase 3 provides `McpToolsetPool` and the `kind="cloud_run"` schema field on `mcp_servers/*` — GA's `McpToolset` is checked out of the pool per turn. | This component |
| Existing GA MCP server | SSE endpoint + OAuth config. No new server work; reused unchanged through the `cloud_run` `kind` branch. | `app/adk/mcp_config/config/mcp_servers.yaml` |
| Gemini code execution | Built-in via `ToolCodeExecution()`. Google-managed sandbox — no infrastructure. | `docs/KEN-E-System-Architecture.md` §4.4 (Code execution) |
| `_ga_header_provider()` reference | Current pattern in `google_analytics_agent_v4.py` — AH-PRD-02 generalized it as `_make_header_provider("ga_oauth")`. | Deprecated by this project |
| W&B Weave tracing | `delegate_to_specialist` span, `load_config_from_firestore` span (AH-PRD-09 Phase 1), review-loop sub-spans, code-execution span. | `docs/trace-structure-spec.md` |
| [Integrations IN-PRD-06](../../integrations/implementation-plan.md#6-phasing) | **Forward migration target (non-blocking).** Retrofits `_make_header_provider("ga_oauth")` to fetch credentials via the Integrations internal endpoint instead of session state. No contract change for the GA specialist; multi-tenant isolation is preserved by the `McpToolsetPool` key including `sha256(auth_credentials)`. | Forward reference |

## 4. Data contract

No new Firestore collections. Two documents written in Phase 1:

| Path | Content |
|------|---------|
| `agent_configs/google_analytics_specialist` | `{model: "gemini-2.0-flash", instruction: <GA-focused system prompt>, temperature: 0.2, description: "…", mcp_servers: ["google_analytics_mcp"], code_execution_enabled: true, available_to_copy: true, automatically_available: true, visible_in_frontend: true, skill_ids: [], sandbox_code_executor_enabled: false}` |
| `mcp_servers/google_analytics_mcp` | Update existing (or create if missing): add `kind: "cloud_run"` (AH-PRD-09 Phase 3 `McpServerKind` enum), `specialist_categories: ["analytics"]`, `auth_type: "ga_oauth"`, `enabled: true`. If the AH-PRD-09 Phase 3 backfill (`api/scripts/migrate_mcp_servers_add_kind.py`) has already run, `kind` will be present — this PRD's migration script is idempotent on that field. |

Both are **global** collections (unchanged per Shape B carve-out for non-account-scoped configs). Per-account overrides are supported via the runtime overlay merge in `specialist_runtime.resolve_config` but not required for this project.

Runtime session state (in-memory only, no persistence):

| Key | Shape | Purpose |
|-----|-------|---------|
| `ga_credentials` | `{access_token, refresh_token, tenant_id, expires_at}` | Set at session creation by the auth layer; read per-turn by the GA specialist's `header_provider` |
| `_requires_reauth` | `bool` | Set when GA OAuth returns 401 — signals the frontend to prompt re-auth |

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | Migration script that writes `agent_configs/google_analytics_specialist` and patches `mcp_servers/google_analytics_mcp` (idempotent on `kind="cloud_run"`; follows the pattern in `app/adk/agents/scripts/migrate_ga_agent_to_firestore.py`). After the next chat turn, the AH-PRD-09 runtime resolver picks up the new config via `config_cache` (≤ 60 s TTL); no redeploy required. |
| Modify | `app/adk/agents/google_analytics_agent_v4.py` — add `@deprecated` banner comment + removal note. Keep the file in place until a follow-up removes it (no callers remain once the root reaches GA via `delegate_to_specialist("google_analytics_specialist", ...)`). |
| Create | `app/adk/agents/tests/test_google_analytics_specialist_e2e.py` — end-to-end tests (marked `@pytest.mark.llm` for live-model tests in CI). Tests dispatch through `delegate_to_specialist` on the post-AH-PRD-09-Phase-2 root. |
| Create | Instruction template for the GA specialist — embedded in the migration script; includes code-execution guidance (use code execution for percentages, trend calculations, averages, sorting, comparisons). |
| Update | [`../README.md`](../README.md) §2.1 Key Directories — mark `google_analytics_agent_v4.py` row as deprecated once this PRD merges; remove the row entirely when the file is deleted in the follow-up. Also remove any lingering `ken_e_agent.py` mention of a `query_google_analytics` tool wrapper (deleted by AH-PRD-09 Phase 5). |

**Note on `ken_e_agent.py` and `dispatch_handlers.py`:** AH-PRD-03 does **not** edit either file. The root agent's tool surface is owned by AH-PRD-09 (single `delegate_to_specialist` tool, deleted `query_*` wrappers, deleted factory-generated `dispatch_to_*` functions). GA reaches the user surface through the runtime resolver and the dynamic "Available Specialists" block — no per-specialist root-level code path exists.

## 6. API contract

No new HTTP endpoints. The root agent's tool surface is owned by AH-PRD-09 — a single `delegate_to_specialist(name, query, acceptance_criteria=None)` tool reaches every registered specialist. GA participates by name:

```python
# Under AH-PRD-09 Phase 2, the root invokes GA via the single dispatch tool.
# Standard LLM tool-calling: root sees "google_analytics_specialist" in the
# Available Specialists block (rendered per turn by
# specialist_runtime.available_specialists_provider) and calls:
delegate_to_specialist(
    name="google_analytics_specialist",
    query="<user question>",
    acceptance_criteria="<2-4 measurable criteria, e.g., 'session count is shown' …>",
)
```

Existing query patterns ("What were my sessions last week?", "Show me traffic trends for the past week") continue to route correctly because description-based routing (README §2.5) names the GA specialist clearly in its `agent_configs/google_analytics_specialist.description` field. AC #3 (backward compatibility) verifies this through the regression tests.

## 7. Acceptance criteria

1. **GA specialist runtime resolution:** Given a fresh chat turn, `specialist_runtime.resolve_config("google_analytics_specialist", account_id)` returns a `MergedAgentConfig` matching the seeded Firestore document; `specialist_runtime.resolve_agent(config)` constructs an `LlmAgent` with: a `McpToolset` checked out of `McpToolsetPool` for `google_analytics_mcp` (`kind="cloud_run"`, header provider `_make_header_provider("ga_oauth")`), `code_execution_enabled=true` materialized as `Tool(code_execution=ToolCodeExecution())` on `GenerateContentConfig`, and any factory `default_global` function tools (e.g., `create_visualization`). Total tool count under 30.
2. **GA specialist reachable from root:** The runtime `available_specialists_provider` renders `google_analytics_specialist` into the root's "Available Specialists" block within ~60 s of the Firestore write. The root reaches GA via `delegate_to_specialist("google_analytics_specialist", query, acceptance_criteria)`; no per-specialist root-level tool wrapper exists. `google_analytics_agent_v4.py` is marked deprecated with a removal note.
3. **Backward compatibility:** Existing query patterns ("What were my sessions last week?", "Show me traffic trends for the past week") continue to route to the GA specialist under standard LLM tool-calling. No regression in analytics query handling versus the pre-AH-PRD-09 baseline.
4. **Review-loop integration:** Given the Root Agent generates acceptance criteria and dispatches to the GA specialist, `delegate_to_specialist` wraps the resolved specialist in `build_review_pipeline()` before invoking it through the inner `Runner`. The reviewer evaluates data accuracy, completeness, and calculation correctness.
5. **Review iteration:** Given the specialist produces a draft with incorrect calculations, the reviewer rejects with feedback. The specialist iterates (using code execution to fix calculations) and the reviewer approves on the subsequent pass.
6. **Code execution:** Given a query requiring numerical analysis (percentages, trends, averages), the GA specialist uses Gemini code execution rather than in-context arithmetic. `executable_code` and `code_execution_result` parts appear in the response.
7. **Code-execution error handling:** Given a code-execution failure (`OUTCOME_FAILED`), the specialist retries with corrected code or reports the calculation error clearly to the user.
8. **E2E happy path:** A user query "Show me traffic trends for the past week" produces: `delegate_to_specialist` → `load_config_from_firestore` → GA `McpToolsetPool` checkout → GA MCP data retrieval → code execution for trend calculations → reviewer approval → text result in `ChatResponse`.
9. **OAuth error handling:** Given an expired OAuth token from GA MCP, `_requires_reauth` is set in session state and a clear error message is returned to the user.
10. **Multi-tenant isolation:** Two concurrent sessions with different `ga_credentials` each use their own OAuth tokens. `McpToolsetPool` keys entries on `(server_id, account_id, sha256(auth_credentials))` so no cross-account token leakage occurs; each session's `header_provider` closure resolves to its own credentials.
11. **Weave tracing:** The full E2E flow produces a Weave trace showing: root agent → `delegate_to_specialist` span → `load_config_from_firestore` sub-span → review-loop iterations → specialist (with tool calls and code execution) → reviewer → approved result.

## 8. Test plan

### Unit
- Config-document validity: schema matches the agent-config Pydantic model from AH-PRD-02; required fields present; enum values valid
- Migration-script idempotency: running twice produces the same Firestore state

### Integration (`test_google_analytics_specialist_e2e.py`, marked `@pytest.mark.llm`)
- Happy path ("Show me traffic trends for the past week") — root invokes `delegate_to_specialist("google_analytics_specialist", …)`; assert expected chain of events + final text
- Runtime resolution — seed Firestore with the GA config, send a chat turn, assert `specialist_runtime.resolve_config` + `resolve_agent` produce the expected `LlmAgent` shape (model, instruction, tools, code-execution flag)
- Review-loop iteration — seed a flawed draft; assert reviewer rejects; specialist iterates; second draft approved
- Code-execution invocation — assert `executable_code` + `code_execution_result` parts in the response for numerical queries
- Code-execution failure recovery — seed a `OUTCOME_FAILED` response; assert retry or clear error
- OAuth error — expire the token; assert `_requires_reauth` in session state + user-visible error
- Multi-tenant isolation — two concurrent sessions; assert each uses its own token; `McpToolsetPool` returns distinct entries keyed on `sha256(auth_credentials)`; no cross-talk
- Weave trace — after a full run, inspect trace structure: root → `delegate_to_specialist` → `load_config_from_firestore` → review-loop iterations → specialist + reviewer sub-spans

### Regression
- Existing query patterns from before the migration still work — pulled from chat history + tests covering `google_analytics_agent_v4`. Each pattern dispatches through `delegate_to_specialist("google_analytics_specialist", …)` post-migration.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Reviewer rubber-stamps draft with wrong calculations | Acceptance criteria should require showing the arithmetic (e.g., "Include the computed sessions count and the formula"). Weave traces expose rubber-stamping; iterate instruction. |
| Code execution sandbox times out or is rate-limited | Instruction guides the LLM to keep code short and fail back to a clear user error on timeout. `OUTCOME_FAILED` path tested. |
| GA MCP rate limits under concurrent sessions | Existing GA MCP quota applies; no change to server. Monitor via Weave for 429s. |
| Legacy `google_analytics_agent_v4.py` still loaded by some deploy path | The post-AH-PRD-09 root has no `query_google_analytics` tool wrapper — `google_analytics_agent_v4.py` is only reachable if a separate code path imports it. AC #3 regression test asserts that `delegate_to_specialist("google_analytics_specialist", ...)` handles every historical query pattern. Follow-up story removes the legacy file once a grep confirms no callers remain. |
| Per-account instruction overrides for GA accidentally break the runtime-resolved GA | AH-PRD-09's overlay tests cover the runtime merge in `specialist_runtime.resolve_config`; AH-PRD-03 just consumes the merged config. Integration test verifies a per-account `instruction` overlay reaches the resolved specialist within the cache TTL. |
| AH-PRD-09 cache TTL hides a fresh Firestore write longer than expected | Migration script is idempotent and the AH-PRD-09 cache key is content-hashed, so re-runs invalidate the cache on the next read. If a fresh seed is needed, manually evict the `config_cache` entry or wait one TTL window (~60 s). |

### Open questions
- **Q:** Should the GA specialist also be registered with `visible_in_frontend=true` so it appears on Workflows > Agents? → Yes (default on the factory); admins can view/customize just like any other specialist.
- **Q:** Does Gemini code execution have cost implications we should disclose in usage tracking? → Yes — track `code_execution_result` byte size in usage records (already on Shape C roadmap; no blocker here).

## 10. Reference

- Parent: Linear project for this PRD; design rationale captured in [Review 5 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-5-architecture-accuracy-pass--harness-doc-v22--v23) (Narrow Specialist Architecture)
- Upstream: [AH-PRD-01](./AH-PRD-01-review-loop-framework.md), [AH-PRD-02](./AH-PRD-02-agent-factory.md), [AH-PRD-09](./AH-PRD-09-per-turn-dispatch.md) (per-turn dispatch — Phase 2 and Phase 3 are hard blockers)
- Design docs: [`../README.md`](../README.md) §2 Architecture, §2.5 Tool-assignment model, §2.6 Specialist roadmap; [AH-PRD-09](./AH-PRD-09-per-turn-dispatch.md) §4 Data contract (specialist_runtime + McpToolsetPool); [`../mcp-architecture.md`](../mcp-architecture.md) §4 Platform integration decisions (Google Analytics row); [`../../../per-turn-dispatch-rfc.md`](../../../per-turn-dispatch-rfc.md) §4 Proposed architecture, §6 Relationship to existing AH PRDs (GA row)
- Harness design: `docs/KEN-E-System-Architecture.md` §4.4 (Code execution)
- Trace spec: `docs/trace-structure-spec.md`
- Deprecation target: `app/adk/agents/google_analytics_agent_v4.py`
- CLAUDE.md rules in scope: PY-1, PY-2, PY-7; C-2, C-4, C-7; T-1, T-3, T-5, T-6
