# AH-PRD-03 — Google Analytics Specialist

**Status:** Ready — foundation shipped (AH-PRD-01, AH-PRD-02, AH-PRD-09 Phases 0–3 + 5 are in R1; AH-PRD-06 PR-A merged, PR-B/PR-C landing)
**Owner team:** Core AI / Agent Platform
**Depends on (all shipped/landing):** AH-PRD-01 (review-loop framework — `build_review_pipeline`), AH-PRD-02 (agent factory — config schema + `_make_header_provider`), [AH-PRD-09](./AH-PRD-09-per-turn-dispatch.md) (per-turn runtime resolver: `specialist_runtime`, native `transfer_to_agent` dispatch, `McpToolsetPool`, `kind="cloud_run"`), [AH-PRD-06](./AH-PRD-06-tool-mapping.md) (per-agent `tool_ids` selection — optional for GA)
**Parallel with:** Data-management projects (DM-PRDs run on a separate path), Skills SK-PRDs, Project-Tasks PR-PRDs that don't touch GA
**Blocks:** Future narrow-specialist sprints (Google Ads, Meta Ads, Mailchimp — see [README §2.6](../README.md#26-specialist-roadmap)) — this project is their reference pattern
**Estimated effort:** 5 stories. ≈ 5–7 days. Mostly config + tests.

---

> **Architecture-refresh note (2026-06).** This PRD was originally written against the deploy-time factory + a `delegate_to_specialist(name, query, acceptance_criteria)` root function tool. Both are superseded. The live harness (AH-PRD-09 + AH-75) deploys a thin root carrying `tools=[]` and dispatches via ADK's **native `transfer_to_agent`**; specialists are resolved per turn by `specialist_runtime` and attached to `root.sub_agents` by `attach_specialists_before_agent_callback`. Consequently the review loop is **config-driven** (`default_acceptance_criteria` on the agent config, not a per-dispatch argument), code execution is wired via `LlmAgent.code_executor = BuiltInCodeExecutor()` (ADK 1.27+), and chat reachability is gated by `ken_e_sub_agent=True` (AH-82). This PRD has been updated to that runtime. See [README §2](../README.md#2-architecture) for the canonical picture.

> **Credential-loading migration note.** This PRD consumes the `_make_header_provider("ga_oauth")` factory from AH-PRD-02 and the session-state `ga_credentials` key. Both are retrofitted by [Integrations](../../integrations/implementation-plan.md) **IN-PRD-06** to read credentials from the Integrations internal endpoint (`GET /api/v1/internal/integrations/credentials/{account_id}/google`) instead of session state. **Not a blocking dependency** — ship AH-PRD-03 as specified; the multi-tenant OAuth isolation in §2 acceptance criteria continues to hold after IN-PRD-06 because the per-account scoping moves from session-state keys to Integrations' per-account `PlatformConnection` records. The GA specialist's dispatch, review-loop integration, and code-execution behavior are unchanged by the migration.

## 1. Context

AH-PRD-02 delivered the config-driven agent factory and AH-PRD-09 shipped the per-turn runtime successor that replaces deploy-time specialist construction with `specialist_runtime` + ADK-native `transfer_to_agent` dispatch. This project validates the combined stack end-to-end by registering the **first** narrow specialist — the Google Analytics Specialist — entirely through the config-driven runtime path. By the end of this project KEN-E can query Google Analytics via the GA MCP server, perform accurate numerical analysis (percentages, trends, averages) using Gemini's built-in code execution instead of in-context arithmetic, and guarantee output quality through review-loop iteration. It also retires the transitional `google_analytics_agent_v4.py` that the R1.0 hardcoded pattern installed, migrating fully to the runtime-resolved narrow-specialist pattern.

The project has two phases. **Phase 1** creates the agent config document at `agent_configs/google_analytics_specialist` (model, instruction, `mcp_servers=["google_analytics_mcp"]`, `code_execution_enabled=true`, `default_acceptance_criteria`, `ken_e_sub_agent=true`) and patches the `mcp_servers/google_analytics_mcp` document so the runtime resolver picks GA up on the next chat turn: `available_specialists_provider` renders it into the root's "Available Specialists" block and `attach_specialists_before_agent_callback` attaches it to `root.sub_agents`, where the root LLM reaches it via `transfer_to_agent(agent_name="google_analytics_specialist")`. `google_analytics_agent_v4.py` is marked deprecated with a removal note. **Phase 2** validates the full stack: review-loop integration (the resolver wraps the specialist in `build_review_pipeline()` when `default_acceptance_criteria` is set; the reviewer evaluates data accuracy, completeness, and calculation correctness), Gemini code execution for numerical analysis (`executable_code` + `code_execution_result` parts in responses), multi-tenant OAuth isolation via the `_make_header_provider("ga_oauth")` factory (preserved from AH-PRD-02, consumed by the AH-PRD-09 `McpToolsetPool`), and end-to-end tests with Weave trace structure verification.

This is the **proof point** for the full Release 1 harness stack: per-turn dispatch (AH-PRD-09) + review loop (AH-PRD-01) + code execution + multi-tenant auth, all working together against a real data source. The R5-planned specialists (Google Ads, Meta Ads, Mailchimp — see [README §2.6](../README.md#26-specialist-roadmap)) follow the pattern established here — `specialist_runtime` is the construction mechanism, the review loop is the quality gate, and this project sets the recipe.

## 2. Scope

### In scope
- **Phase 1: Agent definition & migration**
  - `agent_configs/google_analytics_specialist` Firestore document (full field set in §4): model, instruction, temperature, description, `mcp_servers=["google_analytics_mcp"]`, `code_execution_enabled=true`, `default_acceptance_criteria` (so the runtime wraps GA in a review pipeline), `ken_e_sub_agent=true` (so GA is delegatable from chat), optional `name`/`title` identity. `specialist_runtime.resolve_config` reads this document via `config_cache`; `specialist_runtime.resolve_agent` constructs the `LlmAgent` (or `LoopAgent` review pipeline) per turn, and the runtime MCP path wires a `McpToolset` through `McpToolsetPool` with `header_provider=_make_header_provider("ga_oauth")`.
  - `mcp_servers/google_analytics_mcp` document updated with `kind="cloud_run"` (AH-PRD-09 Phase 3 schema), `specialist_categories=["analytics"]`, and `auth_type="ga_oauth"` if not already present.
  - Mark `google_analytics_agent_v4.py` deprecated with a banner comment + removal date. No root-agent code changes: the root carries `tools=[]`, `available_specialists_provider` renders GA into the "Available Specialists" block on the next chat turn, and the root reaches it via ADK-native `transfer_to_agent(agent_name="google_analytics_specialist")`. Existing query patterns ("Show me traffic trends for the past week") route correctly under standard LLM specialist-selection.
  - All GA tools visible on every turn (`tool_ids=null` → the full `google_analytics_mcp` roster; the 8 GA tools are catalogued in `tools.yaml`). No per-turn `tool_filter` needed — specialist stays well under the ≤30-tool cap. Optionally, `tool_ids` can pin a subset per AH-PRD-06.
- **Phase 2: Quality & capabilities**
  - Review-loop integration — when `agent_configs/google_analytics_specialist.default_acceptance_criteria` is set, `specialist_runtime.resolve_agent` wraps the specialist in `build_review_pipeline()` from AH-PRD-01 (specialist + reviewer as a `LoopAgent`) before it is attached and invoked. The reviewer evaluates data accuracy, completeness, and calculation correctness; reviewer model is `DEFAULT_REVIEWER_MODEL` (`gemini-2.5-pro`) unless overridden by `reviewer_model` (AH-92).
  - Gemini code execution — enabled via `code_execution_enabled=true`; `specialist_runtime`/`builder` sets `LlmAgent.code_executor = BuiltInCodeExecutor()` (ADK 1.27+ — a `GenerateContentConfig.tools` `code_execution` entry is rejected for this purpose). Instruction directs the LLM to use code execution for all numerical analysis (percentage changes, trend calculations, averages, sorting, comparisons). `executable_code` and `code_execution_result` parts appear in responses.
  - Code-execution error handling — on `OUTCOME_FAILED`, specialist retries with corrected code or reports the calculation error clearly to the user.
  - OAuth error handling — on expired GA OAuth token, `_requires_reauth` is set in session state and a clear error message is returned.
  - Multi-tenant isolation — two concurrent sessions with different `ga_credentials` each use their own OAuth tokens. The `McpToolsetPool` (AH-PRD-09 Phase 3) keys entries on `(server_id, account_id, sha256(auth_credentials))`, so each account's tokens flow through its own `header_provider` closure and pooled `McpToolset`.
  - End-to-end tests covering: happy path ("Show me traffic trends for the past week"), code-execution failures, OAuth error handling, multi-tenant concurrency, Weave trace verification (`transfer_to_agent` dispatch → `load_config_from_firestore` config-resolution span → review-loop iterations → specialist + reviewer sub-spans).

### Out of scope
- Google Ads, Meta Ads, Mailchimp specialists — deferred to future sprints (see [README §2.6](../README.md#26-specialist-roadmap)).
- Skill attachment — the GA specialist ships without skills; skills wiring is SK-PRD-02's job.
- Any change to the GA MCP server implementation itself — KEN-E consumes the existing SSE endpoint.
- Removal of `google_analytics_agent_v4.py` — deprecation banner only; removal happens in a follow-up once no callers remain.
- New agent-builder UI work — AH-PRD-06 already ships the `AgentToolPicker`; this project only seeds the global GA config. (See §9 open questions for the user-built-GA-agent path that AH-PRD-06 enables.)

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[AH-PRD-01](./AH-PRD-01-review-loop-framework.md)** | `build_review_pipeline()` wraps the specialist when `default_acceptance_criteria` is set on the config. Review loop must ship first to enable AC #4. **Shipped.** | This component |
| **[AH-PRD-02](./AH-PRD-02-agent-factory.md)** | Config schema (`agent_configs/*`, `mcp_servers/*`, `MergedAgentConfig`), `_make_header_provider("ga_oauth")` factory, multi-tenant overlay model, `BuiltInCodeExecutor` wiring (`builder.py`). Deploy-time dispatch generation is superseded by AH-PRD-09 — see next row. **Shipped.** | This component |
| **[AH-PRD-09](./AH-PRD-09-per-turn-dispatch.md)** | The runtime path GA is constructed on: `specialist_runtime` (per-turn resolver that reads `agent_configs/google_analytics_specialist`, applies any per-account overlay, and builds the `LlmAgent`/`LoopAgent` lazily), ADK-native `transfer_to_agent` dispatch with `attach_specialists_before_agent_callback`, `McpToolsetPool`, and the `kind="cloud_run"` schema field on `mcp_servers/*`. **Shipped (R1, Phases 0–3 + 5).** | This component |
| **[AH-PRD-06](./AH-PRD-06-tool-mapping.md)** | Optional for GA: the per-agent `tool_ids` field + `AgentToolPicker`. With `tool_ids=null` GA gets every `google_analytics_mcp` tool; a subset can be pinned instead. Also the path by which a user can build a *custom* GA-tool-equipped agent. **PR-A merged; PR-B/PR-C landing.** | This component |
| Existing GA MCP server | SSE endpoint + OAuth config. No new server work; reused unchanged through the `cloud_run` `kind` branch. | `app/adk/mcp_config/config/mcp_servers.yaml` |
| Gemini code execution | Built-in via `BuiltInCodeExecutor()` on `LlmAgent.code_executor`. Google-managed sandbox — no infrastructure. | `docs/KEN-E-System-Architecture.md` §4.4 (Code execution); `app/adk/agents/agent_factory/builder.py` |
| `_ga_header_provider()` reference | Current pattern in `google_analytics_agent_v4.py` — AH-PRD-02 generalized it as `_make_header_provider("ga_oauth")`. | Deprecated by this project |
| W&B Weave tracing | `transfer_to_agent` dispatch, `load_config_from_firestore` span (AH-PRD-09 Phase 1 cache), review-loop sub-spans, code-execution parts. Reconcile exact span names/attributes against AH-PRD-09 §8 + `docs/trace-structure-spec.md`. | `docs/trace-structure-spec.md` |
| [Integrations IN-PRD-06](../../integrations/implementation-plan.md#6-phasing) | **Forward migration target (non-blocking).** Retrofits `_make_header_provider("ga_oauth")` to fetch credentials via the Integrations internal endpoint instead of session state. No contract change for the GA specialist; multi-tenant isolation is preserved by the `McpToolsetPool` key including `sha256(auth_credentials)`. | Forward reference |

## 4. Data contract

No new Firestore collections. Two documents written in Phase 1:

| Path | Content |
|------|---------|
| `agent_configs/google_analytics_specialist` | See field list below. |
| `mcp_servers/google_analytics_mcp` | Update existing (or create if missing): add `kind: "cloud_run"` (AH-PRD-09 Phase 3 `McpServerKind` enum), `specialist_categories: ["analytics"]`, `auth_type: "ga_oauth"`, `enabled: true`. If the AH-PRD-09 Phase 3 backfill (`api/scripts/migrate_mcp_servers_add_kind.py`) has already run, `kind` will be present — this PRD's migration script is idempotent on that field. |

`agent_configs/google_analytics_specialist` field set (matches the live `AgentConfig`/`MergedAgentConfig` model in `app/adk/agents/agent_factory/config_loader.py`):

```python
{
  # Identity (AH-84) — optional, user-editable. doc_id is the routing key.
  "name": "Aria",                          # optional human name surfaced in the Available Specialists block
  "title": "Analytics Specialist",         # optional role line

  "model": "gemini-2.0-flash",
  "instruction": "<GA-focused system prompt; includes code-execution guidance>",
  "temperature": 0.2,
  "description": "<routing description — what GA does + when the root should pick it>",

  "mcp_servers": ["google_analytics_mcp"],
  "tool_ids": None,                         # None = all tools from google_analytics_mcp (AH-PRD-06). Optionally pin a subset.

  "code_execution_enabled": True,          # → LlmAgent.code_executor = BuiltInCodeExecutor() (ADK 1.27+)
  "default_acceptance_criteria": "<2–4 measurable GA criteria>",  # set → resolve_agent wraps GA in a review LoopAgent (AH-85)
  "reviewer_model": None,                   # None = DEFAULT_REVIEWER_MODEL (gemini-2.5-pro); override per-specialist (AH-92)

  "ken_e_sub_agent": True,                  # delegation gate (AH-82) — MUST be true to be reachable from chat
  "available_to_copy": True,
  "automatically_available": True,
  "visible_in_frontend": True,             # Workflows > Agents list visibility only; orthogonal to ken_e_sub_agent

  "skill_ids": [],
  "sandbox_code_executor_enabled": False,
}
```

Both documents are **global** collections (unchanged per Shape B carve-out for non-account-scoped configs). Per-account overrides are supported via the runtime overlay merge in `specialist_runtime.resolve_config` but not required for this project.

> **Three orthogonal boolean flags (don't conflate them).** `ken_e_sub_agent` gates chat delegation (attach to `root.sub_agents` + appear in the Available Specialists block). `visible_in_frontend` gates the Workflows-page list only. `automatically_available` gates whether the global doc appears in an account's merged inventory at all. GA sets all three `True`. Omitting `ken_e_sub_agent` would still default to `True` (per the model), but the migration sets it **explicitly** so the routing intent is legible.

Runtime session state (in-memory only, no persistence):

| Key | Shape | Purpose |
|-----|-------|---------|
| `ga_credentials` | `{access_token, refresh_token, tenant_id, expires_at}` | Set at session creation by the auth layer; read per-turn by the GA specialist's `header_provider` |
| `_requires_reauth` | `bool` | Set when GA OAuth returns 401 — signals the frontend to prompt re-auth |

## 5. Implementation outline

| Action | File |
|--------|------|
| Create | Migration script that writes `agent_configs/google_analytics_specialist` (full field set per §4, including `default_acceptance_criteria` and `ken_e_sub_agent=true`) and patches `mcp_servers/google_analytics_mcp` (idempotent on `kind="cloud_run"`; follows the pattern in `app/adk/agents/scripts/migrate_ga_agent_to_firestore.py`). After the next chat turn, the AH-PRD-09 runtime resolver picks up the new config via `config_cache` (≤ 60 s TTL); no redeploy required. |
| Modify | `app/adk/agents/google_analytics_agent_v4.py` — add `@deprecated` banner comment + removal note. Keep the file in place until a follow-up removes it (no callers remain once the root reaches GA via `transfer_to_agent("google_analytics_specialist")`). |
| Create | `app/adk/agents/tests/test_google_analytics_specialist_e2e.py` — end-to-end tests (marked `@pytest.mark.llm` for live-model tests in CI). Tests issue queries through the root and assert GA is selected via `transfer_to_agent` on the post-AH-PRD-09 root. |
| Create | Instruction template for the GA specialist — embedded in the migration script; includes code-execution guidance (use code execution for percentages, trend calculations, averages, sorting, comparisons). |
| Update | [`../README.md`](../README.md) §2.1 Key Directories — mark `google_analytics_agent_v4.py` row as deprecated once this PRD merges; remove the row entirely when the file is deleted in the follow-up. |

**Note on `ken_e_agent.py`:** AH-PRD-03 does **not** edit the root agent. The root's tool surface is owned by AH-PRD-09 (root carries `tools=[]`; no `query_*` wrappers, no factory-generated dispatch functions). GA reaches the user surface through the runtime resolver, the dynamic "Available Specialists" block, and ADK-native `transfer_to_agent` — no per-specialist root-level code path exists.

## 6. API contract

No new HTTP endpoints. The root agent carries `tools=[]` and dispatches via ADK's native `transfer_to_agent` (AH-PRD-09 / AH-75) — there is **no** `delegate_to_specialist` function tool. GA participates by appearing in the per-turn "Available Specialists" block:

```text
# Per turn (AH-PRD-09):
#  1. attach_specialists_before_agent_callback resolves eligible specialists
#     (ken_e_sub_agent=True) and attaches them to root.sub_agents.
#  2. available_specialists_provider renders each into the root instruction's
#     "Available Specialists" block — human name + title + bold doc_id (AH-84).
#  3. The root LLM selects GA by reasoning over descriptions and emits:
transfer_to_agent(agent_name="google_analytics_specialist")
#  4. specialist_runtime.resolve_agent constructs the LlmAgent — wrapped in a
#     review LoopAgent because default_acceptance_criteria is set on the config.
```

Existing query patterns ("What were my sessions last week?", "Show me traffic trends for the past week") continue to route correctly because description-based routing (README §2.5) names the GA specialist clearly in its `agent_configs/google_analytics_specialist.description` field. AC #3 (backward compatibility) verifies this through the regression tests.

## 7. Acceptance criteria

1. **GA specialist runtime resolution:** Given a fresh chat turn, `specialist_runtime.resolve_config("google_analytics_specialist", account_id)` returns a `MergedAgentConfig` matching the seeded Firestore document; `specialist_runtime.resolve_agent(config)` constructs an `LlmAgent` with: a `McpToolset` checked out of `McpToolsetPool` for `google_analytics_mcp` (`kind="cloud_run"`, header provider `_make_header_provider("ga_oauth")`), `code_execution_enabled=true` materialized as `LlmAgent.code_executor = BuiltInCodeExecutor()`, and any factory `default_global` function tools (e.g., `create_visualization`). Total tool count under 30.
2. **GA specialist reachable from root:** The runtime `available_specialists_provider` renders `google_analytics_specialist` into the root's "Available Specialists" block within ~60 s of the Firestore write, and `attach_specialists_before_agent_callback` attaches it to `root.sub_agents` (gated by `ken_e_sub_agent=true`). The root reaches GA via ADK-native `transfer_to_agent(agent_name="google_analytics_specialist")`; no per-specialist root-level tool wrapper exists. `google_analytics_agent_v4.py` is marked deprecated with a removal note.
3. **Backward compatibility:** Existing query patterns ("What were my sessions last week?", "Show me traffic trends for the past week") continue to route to the GA specialist under standard LLM specialist-selection. No regression in analytics query handling versus the pre-AH-PRD-09 baseline.
4. **Review-loop integration:** Given `agent_configs/google_analytics_specialist.default_acceptance_criteria` is set, `specialist_runtime.resolve_agent` wraps the resolved specialist in `build_review_pipeline()` (specialist + reviewer as a `LoopAgent`). The reviewer evaluates data accuracy, completeness, and calculation correctness. With `default_acceptance_criteria` unset/empty, GA resolves to a single-pass `LlmAgent` (no review loop).
5. **Review iteration:** Given the specialist produces a draft with incorrect calculations, the reviewer rejects with feedback. The specialist iterates (using code execution to fix calculations) and the reviewer approves (via `exit_loop`) on the subsequent pass.
6. **Code execution:** Given a query requiring numerical analysis (percentages, trends, averages), the GA specialist uses Gemini code execution rather than in-context arithmetic. `executable_code` and `code_execution_result` parts appear in the response.
7. **Code-execution error handling:** Given a code-execution failure (`OUTCOME_FAILED`), the specialist retries with corrected code or reports the calculation error clearly to the user.
8. **E2E happy path:** A user query "Show me traffic trends for the past week" produces: `transfer_to_agent("google_analytics_specialist")` → `load_config_from_firestore` config resolution → GA `McpToolsetPool` checkout → GA MCP data retrieval → code execution for trend calculations → reviewer approval → text result in `ChatResponse`.
9. **OAuth error handling:** Given an expired OAuth token from GA MCP, `_requires_reauth` is set in session state and a clear error message is returned to the user.
10. **Multi-tenant isolation:** Two concurrent sessions with different `ga_credentials` each use their own OAuth tokens. `McpToolsetPool` keys entries on `(server_id, account_id, sha256(auth_credentials))` so no cross-account token leakage occurs; each session's `header_provider` closure resolves to its own credentials.
11. **Weave tracing:** The full E2E flow produces a Weave trace showing: root agent → `transfer_to_agent` dispatch → `load_config_from_firestore` config-resolution sub-span → review-loop iterations → specialist (with MCP tool calls and code-execution parts) → reviewer → approved result. Exact span names + attributes (`specialist_name`, `cache_hit`, `mcp_pool_hit`) are reconciled against AH-PRD-09 §8 and `docs/trace-structure-spec.md`.

## 8. Test plan

### Unit
- Config-document validity: schema matches the `AgentConfig`/`MergedAgentConfig` model in `config_loader.py`; required fields present; `default_acceptance_criteria` and `ken_e_sub_agent` set; enum values valid
- Migration-script idempotency: running twice produces the same Firestore state
- `resolve_agent` wiring: `code_execution_enabled=true` ⇒ `LlmAgent.code_executor` is a `BuiltInCodeExecutor`; `default_acceptance_criteria` set ⇒ the resolved agent is a review `LoopAgent`; unset ⇒ a plain `LlmAgent`

### Integration (`test_google_analytics_specialist_e2e.py`, marked `@pytest.mark.llm`)
- Happy path ("Show me traffic trends for the past week") — root selects GA via `transfer_to_agent`; assert expected chain of events + final text
- Runtime resolution — seed Firestore with the GA config, send a chat turn, assert `specialist_runtime.resolve_config` + `resolve_agent` produce the expected agent shape (model, instruction, tools, code-executor, review-loop wrapper)
- Review-loop iteration — seed a flawed draft; assert reviewer rejects; specialist iterates; second draft approved
- Code-execution invocation — assert `executable_code` + `code_execution_result` parts in the response for numerical queries
- Code-execution failure recovery — seed a `OUTCOME_FAILED` response; assert retry or clear error
- OAuth error — expire the token; assert `_requires_reauth` in session state + user-visible error
- Multi-tenant isolation — two concurrent sessions; assert each uses its own token; `McpToolsetPool` returns distinct entries keyed on `sha256(auth_credentials)`; no cross-talk
- Weave trace — after a full run, inspect trace structure: root → `transfer_to_agent` dispatch → `load_config_from_firestore` → review-loop iterations → specialist + reviewer sub-spans

### Regression
- Existing query patterns from before the migration still work — pulled from chat history + tests covering `google_analytics_agent_v4`. Each pattern routes to `google_analytics_specialist` via `transfer_to_agent` post-migration.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Reviewer rubber-stamps draft with wrong calculations | `default_acceptance_criteria` should require showing the arithmetic (e.g., "Include the computed sessions count and the formula"). Weave traces expose rubber-stamping; iterate the criteria/instruction. |
| Code execution sandbox times out or is rate-limited | Instruction guides the LLM to keep code short and fail back to a clear user error on timeout. `OUTCOME_FAILED` path tested. |
| GA MCP rate limits under concurrent sessions | Existing GA MCP quota applies; no change to server. Monitor via Weave for 429s. |
| GA seeded without `ken_e_sub_agent=true` or `default_acceptance_criteria` | The model defaults `ken_e_sub_agent=True`, but the migration sets it explicitly; without `default_acceptance_criteria` GA resolves single-pass and AC #4/#5 cannot be met. Migration-script unit test asserts both fields are present. |
| Legacy `google_analytics_agent_v4.py` still loaded by some deploy path | The post-AH-PRD-09 root has no `query_google_analytics` tool wrapper — `google_analytics_agent_v4.py` is only reachable if a separate code path imports it. AC #3 regression test asserts that `transfer_to_agent("google_analytics_specialist")` handles every historical query pattern. Follow-up story removes the legacy file once a grep confirms no callers remain. |
| Per-account instruction overrides for GA accidentally break the runtime-resolved GA | AH-PRD-09's overlay tests cover the runtime merge in `specialist_runtime.resolve_config`; AH-PRD-03 just consumes the merged config. Integration test verifies a per-account `instruction` overlay reaches the resolved specialist within the cache TTL. |
| AH-PRD-09 cache TTL hides a fresh Firestore write longer than expected | Migration script is idempotent and the AH-PRD-09 cache key is content-hashed, so re-runs invalidate the cache on the next read. If a fresh seed is needed, manually evict the `config_cache` entry or wait one TTL window (~60 s). |

### Open questions
- **Q:** Should the GA specialist also be registered with `visible_in_frontend=true` so it appears on Workflows > Agents? → Yes (default on the factory); admins can view/customize just like any other specialist. Note this is independent of `ken_e_sub_agent` (the chat-delegation gate).
- **Q:** Does Gemini code execution have cost implications we should disclose in usage tracking? → Yes — track `code_execution_result` byte size in usage records (already on Shape C roadmap; no blocker here).
- **Q (new):** With AH-PRD-06 shipped, a user can now build a *custom* agent in Workflows > Agents and attach the GA MCP tools individually via the `AgentToolPicker`. Should AH-PRD-03 add an E2E that exercises that user-built path (create custom agent → attach GA tools → live query)? → **Resolved: yes** — it's the most direct test of "a user equips an agent with the GA MCP." Tracked as a separate verification story (Linear **AH-95**), outside this PRD's core 5 stories.

> **Note — model is MER-E-optimizable.** Because the GA config lives in the global `agent_configs/google_analytics_specialist` document and the runtime resolver reads it per turn (`config_cache`, ≤ 60 s TTL), the `model` field is **directly optimizable without redeploy**. The Self-Improving Evaluation Framework (MER-E) classifies Model Selection, instruction, temperature, and `max_output_tokens` as Firestore-editable A/B-testable parameters and writes them through the versioned `PUT /api/eval/agents/{agent_id}/config` path (`agent_id` = the config doc_id `google_analytics_specialist`); see `docs/KEN-E-Self-Improving-Evaluation-Framework-Design.md` §1.3. Write single fields (not a full re-seed, which would revert `model`/`instruction`).

## 10. Reference

- Parent: Linear project for this PRD; design rationale captured in [Review 5 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-5-architecture-accuracy-pass--harness-doc-v22--v23) (Narrow Specialist Architecture)
- Upstream: [AH-PRD-01](./AH-PRD-01-review-loop-framework.md), [AH-PRD-02](./AH-PRD-02-agent-factory.md), [AH-PRD-09](./AH-PRD-09-per-turn-dispatch.md) (per-turn dispatch — the runtime path GA is built on), [AH-PRD-06](./AH-PRD-06-tool-mapping.md) (per-agent `tool_ids`, optional for GA)
- Design docs: [`../README.md`](../README.md) §2 Architecture, §2.5 Tool-assignment & routing model, §2.6 Specialist roadmap; [AH-PRD-09](./AH-PRD-09-per-turn-dispatch.md) §4 Data contract (`specialist_runtime` + `McpToolsetPool`), §8 (MER-E trace coordination); [`../mcp-architecture.md`](../mcp-architecture.md) §4 Platform integration decisions (Google Analytics row); [`../../../per-turn-dispatch-rfc.md`](../../../per-turn-dispatch-rfc.md) §4 Proposed architecture
- Harness design: `docs/KEN-E-System-Architecture.md` §4.4 (Code execution)
- Trace spec: `docs/trace-structure-spec.md`
- Code references: `app/adk/agents/agent_factory/config_loader.py` (config schema), `builder.py` (`BuiltInCodeExecutor` wiring), `specialist_runtime.py` (resolver + review-loop wrap + `tool_ids` allowlist), `sub_agent_attacher.py` (`transfer_to_agent` attach), `hierarchy.py` (root `tools=[]`)
- Deprecation target: `app/adk/agents/google_analytics_agent_v4.py`
- CLAUDE.md rules in scope: PY-1, PY-2, PY-7; C-2, C-4, C-7; T-1, T-3, T-5, T-6
