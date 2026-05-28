# AH-PRD-09 — Per-Turn Dispatch Agent

**Status:** Proposed
**Owner team:** Core AI / Agent Platform (backend; coordinates with Skills, Integrations, Chat, Billing, MER-E)
**Blocked by:** [AH-PRD-01](./AH-PRD-01-review-loop-framework.md) (review pipeline is invoked inside `delegate_to_specialist`), [AH-PRD-02](./AH-PRD-02-agent-factory.md) (this PRD supersedes its deploy-time factory model), [DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md) (Shape B convention)
**Soft prerequisite:** [SK-PRD-02](../../skills/projects/SK-PRD-02-agent-integration.md) `SandboxPool` — PRD §7 AC #23 verification depends on this shipping (confirmed Done in SK-23 + SK-26 + SK-37).
**Phase 4 only (deferred to R2):** IN-PRD-01 / IN-PRD-02 / IN-PRD-03 — Zapier hybrid MCP cannot ship without the Integrations component
**Parallel with:** SK-PRD-00, SK-PRD-01, SK-PRD-02 (all R1; SandboxPool design mirrors `McpToolsetPool`)
**Blocks:** Future per-platform specialist PRDs (AH-PRD-10+) consume the runtime resolver
**Estimated effort:** 7–10 engineering weeks across 6 phases (4–6 calendar weeks with two engineers from Phase 2 onward)
**Release:** 1 (Foundation) — Phases 0–3 + 5; **Phase 4 (Zapier hybrid MCP) deferred to R2** alongside the Integrations component

> **Reading order.** This PRD is the implementation contract. The architectural design and rationale live in [`docs/design/per-turn-dispatch-rfc.md`](../../../per-turn-dispatch-rfc.md) — read the RFC first for the "why" and the cross-component contracts; come back here for "what to build."

---

## 1. Context

KEN-E's product requirement is that an admin who creates or edits an agent (instructions, model, temperature, max output tokens, and tools) gets that agent **immediately available** in chat — no engineer in the loop, no redeploy. [AH-PRD-02](./AH-PRD-02-agent-factory.md) reads every agent config from Firestore once at deploy time and bakes the full specialist hierarchy into a Python object tree shipped to Vertex AI Agent Engine. Every field except `instruction` is frozen at that point, and even `instruction` is frozen on the deployed factory path because the hot-reload cache from Sprint 6 Decision B (`app/adk/agents/utils/config_cache.py`) is never read by the factory's instruction provider ([`builder.py:33`](../../../../../app/adk/agents/agent_factory/builder.py)). The result: every config change — including new agents — requires a redeploy of the Agent Engine, and `instruction` edits regress silently (the PUT endpoint accepts them but they never reach the deployed agent).

This PRD ships a successor architecture — the **Per-Turn Dispatch Agent**. The deployed root becomes a thin dispatcher whose only tool is `delegate_to_specialist(name, query, acceptance_criteria=None)`. Specialists are no longer constructed at deploy time; instead a runtime resolver (`specialist_runtime`) reads the current config from Firestore (cached with TTL + content-hash invalidation, per-key striped locking), constructs the `LlmAgent` lazily, caches it for reuse, and runs it through an inner ADK Runner. Editing or creating a specialist Firestore document propagates to the next chat turn within ~60 s of the write (or immediately on cache miss). Only the root agent and the small set of root-level configuration remain deploy-time-bound.

The PRD also introduces a **hybrid MCP model** via an open `McpServerKind` enum (`cloud_run` | `zapier`). `cloud_run` is today's KEN-E-owned-server path; `zapier` routes long-tail integrations through a single shared connection per account, collapsing the per-platform engineering cost from "build a Cloud Run service" to "write a Firestore agent config." A new `McpToolsetPool` reuses connections across runtime specialist rebuilds with LRU + idle-TTL eviction and `aclose()`-on-eviction discipline. Phase 4 (Zapier first-class integration) defers to R2 alongside the Integrations component; Phases 0–3 + 5 ship in R1 as the `cloud_run`-only runtime resolver.

The combination — runtime specialist resolution + hybrid MCP — meets the immediate-availability product requirement, restores Sprint 6 Decision B's spirit, and unlocks future integration platforms behind the same `McpServerKind` abstraction.

## 2. Scope

### In scope

**Phase 0 — Zapier MCP feasibility spike (1–2 weeks; hard gate for Phase 4).** Capability / auth / performance / cost / protocol probes against Zapier MCP; `McpServerKind` data-model proposal; throwaway prototype. Spike report at `docs/spike-zapier-mcp-feasibility.md`. Exit criteria: p95 ≤ 3× owned-MCP latency, per-account isolation confirmed, capability coverage on 3 probe integrations, cost projection within budget. **No-go pivots Phase 4 to a future PRD; R1 ships `cloud_run`-only.**

**Phase 1 — Cache-backed instruction wiring (1 week; independent of Phase 0).** Extend `_make_factory_instruction_provider` in `builder.py:33` to read from `config_cache.get_cached_config(doc_id)` per turn. Apply to the root + every factory-built specialist. Decorate `config_cache.get_cached_config` with `@safe_weave_op(name="load_config_from_firestore")` so the MER-E eval contract returns. **Quick win that ships value before Phases 2+ land.**

**Phase 2 — Single-dispatch root + specialist runtime (1.5–2 weeks).** New `app/adk/agents/agent_factory/specialist_runtime.py` (`resolve_config`, `resolve_agent`, `run`, `available_specialists_provider`). New `app/adk/agents/agent_factory/dispatch.py` (`delegate_to_specialist`). `build_hierarchy()` reduced to build the root only. Per-account overlay merge moved from deploy-time to runtime. Inner Runner wiring inside `delegate_to_specialist`. `_REDEPLOY_REQUIRED_FIELDS` shrinks to the empty set for specialists; `MergedAgentConfig.warnings` marked `deprecated=true`. **Chat + Billing parity tests are merge blockers** (see [RFC §4.9](../../../per-turn-dispatch-rfc.md#49-cross-component-contracts-preserved)).

**Phase 3 — `McpToolsetPool` + hybrid kinds (1.5–2 weeks).** New `app/adk/agents/agent_factory/mcp_pool.py` with kind-specific keying, LRU + idle-TTL eviction, `aclose()`-on-eviction, 60 s background sweep. Extend `build_toolset_for_doc` with a `kind` branch (`cloud_run` existing path now goes through the pool; `zapier` new path). Add `kind` field to `mcp_servers/{server_id}` schema with migration script defaulting existing docs to `cloud_run`. Port AH-PRD-06 PR-C's `default_global` function-tool injection into the runtime resolver. **1-hour sustained-load SSE-leak stress test is a merge blocker.**

**Phase 4 — Zapier-backed Integrations component work (1–1.5 weeks; DEFERRED TO R2).** `accounts/{account_id}/integrations/zapier` document + Zapier OAuth flow + `/settings/integrations` "Connect Zapier" tile + connection status UI. Requires the Integrations component (IN-PRDs 01/02/03), which sits behind DM-PRD-07 → PR-PRD-01. Cannot ship in R1 without cascading half the planner; deferred per the RFC §7.2 no-go pivot.

**Phase 5 — Cleanup, observability, rollout (1 week).** Decommission unreachable legacy code paths (see AH-66); `generate_dispatch_functions` already deleted in AH-66 (see DESIGN-REVIEW-LOG Review 39); delete `_make_factory_instruction_provider`'s baked-text path; delete legacy `create_ken_e_agent()` if no callers remain; Cloud Trace / Weave dashboards (cache hit rate, MCP pool size, Zapier latency p50/p95, dispatch error rate); DESIGN-REVIEW-LOG entry; operator runbooks. **Cutover gate: MER-E eval suite passes against the new trace shape.**

> **Revision (AH-66, 2026-05-28):** The per-turn dispatch feature flag was dropped. KEN-E has no production users; the per-turn dispatch path is unconditional. FF-PRD-01, Terraform flag file, and AC #20 removed. SandboxPool gate (AC #23) verified by `test_sandbox_pool_runtime_rebuild.py`.

### Out of scope

- **Hot-reloading root-agent settings** (root `model`, root `temperature`, root direct tools beyond `delegate_to_specialist`). Root remains deploy-time-bound; root changes are rare.
- **Strategy supervisor and its downstream specialists** (`marketing_researcher` / `marketing_formatter` / etc.). Per [AH-PRD-08](./AH-PRD-08-hide-strategy-pipeline-specialists.md), these are account-creation-only and hidden from chat; they continue to use the legacy `strategy_agent/config_loader.py` path unchanged.
- **Replacing all owned MCP servers with Zapier.** Hybrid by design — GA MCP and future flagships stay on owned infrastructure unless a separate decision moves them.
- **Multi-channel work** (Slack, Voice). Out of scope per [Architecture §7.3](../../../../KEN-E-System-Architecture.md#73-planned-additional-channels).
- **Changes to Skills, Project Tasks, or Automations runtime models.** They compose on top of the harness; this PRD affects how the harness assembles specialists, not how upstream features use them. Skills coordinates via SK-PRD-02's `SandboxPool` (a Skills-owned addition, not AH-PRD-09 work).
- **Removing the agent factory concept.** "Factory" remains the right name; it just runs every turn instead of once at deploy.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[AH-PRD-01](./AH-PRD-01-review-loop-framework.md)** | `build_review_pipeline()` is called inside `delegate_to_specialist` exactly as it was inside the generated dispatchers. | This component |
| **[AH-PRD-02](./AH-PRD-02-agent-factory.md)** | This PRD supersedes AH-PRD-02's deploy-time factory model. Reuses `MergedAgentConfig`, `_make_header_provider`, `build_toolset_for_doc`, dispatch.py, builder.py with modifications. AH-PRD-02 retains its narrative as "what shipped first"; AH-PRD-09 ships the runtime successor. | This component |
| **[DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md)** | Shape B convention. No new Firestore subcollections in this PRD beyond what AH-PRD-02 already established. | `../../data-management/README.md` |
| **[SK-PRD-02](../../skills/projects/SK-PRD-02-agent-integration.md) — soft prerequisite** | PRD §7 AC #23 verification depends on this shipping (confirmed Done in SK-23 + SK-26 + SK-37). Without it, sandbox-attached specialists respawn their sandbox every turn under the runtime resolver. Pool design intentionally mirrors `McpToolsetPool`. | `../../skills/README.md` §3.2 |
| **Integrations component (Phase 4 only — deferred to R2)** | IN-PRD-01 (encrypted token store), IN-PRD-02 (OAuth flows pattern), IN-PRD-03 (Connection-Management UI) needed for Zapier first-class integration. Not in R1 scope. | `../../integrations/README.md` |
| **Chat ([CH-PRD-01](../../chat/projects/CH-PRD-01-session-metadata-substrate.md)) — coordination dep** | `SessionTurnAccumulator` extracts tokens from every ADK event. Inner-Runner dispatch must preserve event propagation. **Phase 2 parity test is a merge blocker.** | RFC §4.9 |
| **Billing ([BL-PRD-02](../../billing/projects/BL-PRD-02-token-meter-monthly-enforcement.md)) — coordination dep** | `extract_billable_tokens(event)` at `shared/token_accounting.py`. Same parity-test contract as Chat. **Phase 2 parity test is a merge blocker.** | RFC §4.9 |
| **MER-E (sister repo) — coordination dep** | Trace shape changes from N `dispatch_to_*` spans to a single `delegate_to_specialist` span with nested inner-Runner children. MER-E extractors validate against the post-AH-75 trace fixture. **Cutover gate.** | RFC §9.1 |
| **[AH-PRD-06](./AH-PRD-06-tool-mapping.md) PR-C** | Wires `default_global` function tools through `hierarchy.py:325`. Phase 3 ports this into the runtime resolver. Schedule PR-C to land before or alongside Phase 2 to avoid merge conflict. | RFC §9.2 #9 |

## 4. Data contract

> **Full design lives in [RFC §4](../../../per-turn-dispatch-rfc.md#4-proposed-architecture).** This section captures the contract surface the dev team builds against.

### 4.1 New abstractions

> **AH-75 update (Approach 1).** The function-tool dispatch surface (`delegate_to_specialist` + `specialist_runtime.run`) was replaced with ADK's native `transfer_to_agent` + runtime-managed `sub_agents`. The resolver (`resolve_config` / `resolve_agent`) is unchanged; only the dispatch surface changed. See [§4.6 Dispatch surface — AH-75](#46-dispatch-surface--ah-75-approach-1) below for the rationale and the ADK-source evidence that drove the change.

| Symbol | Location | Responsibility |
|---|---|---|
| `attach_specialists_before_agent_callback` | `app/adk/agents/agent_factory/sub_agent_attacher.py` | ADK `before_agent_callback` wired onto the root. Reads `account_id` from session state and calls `attach_account_specialists` so `root.sub_agents` reflects the visible specialists for the current turn. (AH-75) |
| `attach_account_specialists(root_agent, account_id)` | (same module) | Idempotent runtime sync of `root.sub_agents`: appends specialists missing from the list, drops entries whose name is no longer visible or whose instance changed (content-hash drift), manages the `parent_agent` invariant manually since `BaseAgent.__set_parent_agent_for_sub_agents` only runs at construction. Wraps work in the existing `block_lock_for(account_id)` stripe lock so concurrent turns serialise per-account. (AH-75) |
| `specialist_runtime.resolve_config(name, account_id)` | `app/adk/agents/agent_factory/specialist_runtime.py` | Returns a `MergedAgentConfig` for `(name, account_id)`. Cached by `config_cache` with TTL + content-hash. Per-account overlay merge moved to runtime. |
| `specialist_runtime.resolve_agent(config)` | (same module) | Returns a specialist `BaseAgent` constructed from `config` — either a raw `LlmAgent`, or a `LoopAgent` (review-pipeline-wrapped, renamed back to the specialist doc_id so `transfer_to_agent` resolves it) when `config.default_acceptance_criteria` is set. Cached by `(name, account_id, content_hash)`. |
| `MergedAgentConfig.default_acceptance_criteria` | `app/adk/agents/agent_factory/config_loader.py` | Optional config field that opts the specialist into a review pipeline at build time. Replaces the per-call `acceptance_criteria` argument from the deleted `delegate_to_specialist`. (AH-75) |
| `available_specialists_provider(account_id) -> str` | `app/adk/agents/agent_factory/specialist_runtime.py` | Renders the "Available Specialists" block from current Firestore state per turn. Called by the root's instruction provider. |
| `McpServerKind` | `app/adk/agents/agent_factory/mcp.py` | Open enum: `cloud_run`, `zapier`, and future kinds. Persisted as `mcp_servers/{server_id}.kind`. |
| `McpToolsetPool` | `app/adk/agents/agent_factory/mcp_pool.py` | Process-wide pool of `McpToolset` instances; kind-specific keying; LRU + idle TTL + `aclose()`-on-eviction. |

> **Deleted in AH-75 (preserved here for traceability):** `delegate_to_specialist` (function tool), `specialist_runtime.run` (inner-Runner dispatch), `specialist_runtime.resolve_agent_with_hit` (cache_hit observable that backed the deleted Weave span), `review_pipeline_tracing.set_delegate_attrs` (the Weave-span attribute writer for the deleted span). None of these can be ADK-natively made to forward inner-Runner events to the outer Runner's stream — see §4.6 for the source-line evidence.

### 4.2 Cache key shapes

All caches use per-key striped locking (`hash(key) % 32`). See [RFC §4.2.1](../../../per-turn-dispatch-rfc.md#421-cache-key-shapes) for the full table:

| Cache | Key | Value | Invalidation |
|---|---|---|---|
| `config_cache` (extended) | `(doc_id, account_id \| None)` | `(MergedAgentConfig, metadata, extensions)` | TTL (~60 s) + content-hash on re-fetch |
| `agent_cache` | `(name, account_id \| None, content_hash)` | `LlmAgent` | Implicit via content_hash; LRU 256 |
| `available_specialists_cache` | `account_id \| None` | rendered block | TTL (~60 s) + fast-path invalidation |
| `mcp_pool.cloud_run` | `(server_id, account_id, sha256(auth_credentials))` | `McpToolset` | LRU 128 + idle TTL 10 min; `aclose()` |
| `mcp_pool.zapier` | `(account_id, sha256(zapier_token))` | `McpToolset` | Same |

### 4.3 Firestore schema additions

| Path | Field | Type | Default | Notes |
|---|---|---|---|---|
| `mcp_servers/{server_id}` | `kind` | `McpServerKind` (StrEnum) | `cloud_run` | Migration script backfills existing docs to `cloud_run` |
| `accounts/{account_id}/integrations/zapier` | new doc | per Integrations IN-PRD-01 shape | — | Phase 4 only (deferred to R2) |

### 4.4 What stays the same

- `agent_configs/{config_id}` document schema. Same `MergedAgentConfig` model. **No migration of existing global configs required.**
- Per-account overlay model (`accounts/{account_id}/agent_configs/{config_id}` shallow merge). Same semantics, executed at runtime.
- Review loop ([AH-PRD-01](./AH-PRD-01-review-loop-framework.md)) — `build_review_pipeline()` called inside `delegate_to_specialist`.
- ≤30-tool roster discipline (README §2.5).
- Description-based routing via the dynamic "Available Specialists" block.
- The agent-builder UI from AH-PRD-02 Phase 3.

### 4.5 Cross-component contracts preserved

See [RFC §4.9](../../../per-turn-dispatch-rfc.md#49-cross-component-contracts-preserved) for the full contract table covering Chat, Billing, MER-E, Project Tasks, Skills, and strategy-supervisor agents. Each has a Phase 2 acceptance criterion that verifies it before flag flip.

> **AH-75 update.** The Chat token-accumulator + Billing token-meter contracts (§7 ACs #9 and #10) are now satisfied via ADK's native transfer-to-agent event propagation rather than via a custom inner-Runner-to-outer-stream forwarding mechanism. Specialist LLM-response events (carrying `usage_metadata`) appear in the outer Runner's stream natively. The MER-E trace contract is also simplified: no `delegate_to_specialist` span; the trace shape mirrors the legacy AH-PRD-02 form (root → sub-agent), which MER-E's older extractors already supported. See `app/adk/tracking/tests/fixtures/transfer_to_specialist_trace.json` for the canonical post-AH-75 fixture.

### 4.6 Dispatch surface — AH-75 (Approach 1)

The PR #697 review uncovered that the originally-planned inner-Runner event propagation (Phase 2 §7 ACs #9, #10) is **structurally impossible** in pinned ADK without modifying ADK itself. Verified against the source:

- `FunctionTool.run_async` (`function_tool.py:160`) collapses to a single return value.
- `AgentTool.run_async` (`agent_tool.py:190+`) iterates an inner Runner internally and discards everything except `state_delta` and the last content — ADK's own "agent-as-tool" pattern explicitly does **not** propagate events.
- `__build_response_event` (`functions.py:1114`) constructs the function_response Event without `usage_metadata`; no `after_tool_callback` hook can set it.
- `EventActions` has no "emit extra events" field.
- The only ADK-native mechanism for sub-agent events appearing in the outer stream is `transfer_to_agent` (`llm_agent.py:805–818`), and ADK's transfer-detection logic literally requires `function_response.name == 'transfer_to_agent'`.

**AH-75 (Approach 1)** drops `delegate_to_specialist` as a function tool and switches the root to ADK's native `transfer_to_agent` + a runtime-managed `sub_agents` list. The AH-PRD-09 wins (Firestore-resolved-per-turn, ≤60 s admin-edit propagation, no redeploy) come from the resolver (`specialist_runtime.resolve_config` + `resolve_agent`), not the dispatch surface — the resolver stays; only the surface changes.

Concrete shape change:

| Aspect | Pre-AH-75 (PR #697 baseline) | Post-AH-75 |
|---|---|---|
| Root tool list | `[delegate_to_specialist]` | `[]` |
| Root `before_agent_callback` | (none specific to dispatch) | `+ attach_specialists_before_agent_callback` |
| How specialists are reachable | LLM calls `delegate_to_specialist(name=...)` as a function tool → `specialist_runtime.run` spins up an inner Runner | LLM calls ADK's built-in `transfer_to_agent(agent_name=...)` → ADK looks up `root.find_agent(name)`, finds the specialist attached by the before-agent callback, transfers control natively |
| Acceptance criteria | Per-call `acceptance_criteria` arg | Config-driven via `MergedAgentConfig.default_acceptance_criteria` — `resolve_agent` wraps the LlmAgent in a `LoopAgent` review pipeline at build time when set. The per-call override was a PO-confirmed simplification (see [DESIGN-REVIEW-LOG]). |
| Trace shape | `delegate_to_specialist` span (AH-67) | Same as legacy AH-PRD-02: root → `transfer_to_agent` action → specialist sub-agent → (if wrapped) worker + reviewer iteration spans |
| Inner-event propagation | **Broken** (PR #697 sentinel xfail) | **Native** (ADK's `transfer_to_agent` flow) |

The Chat / Billing parity tests at `app/adk/agents/agent_factory/tests/test_chat_billing_parity.py` (10 trials each, 20 total) pass under both Mode A (deploy-time `sub_agents=[specialist]`) and Mode B (runtime-attached `sub_agents` via `attach_specialists_before_agent_callback`) — confirming the contract is preserved across both dispatch shapes.

> **PRD evolution note.** §4.1 above was rewritten to reflect the new abstractions. §4.5 (cross-component contracts) is unchanged in intent but satisfied via a different mechanism. §7 Phase 2 ACs #9 and #10 are now satisfied via `transfer_to_agent` rather than via the function-tool dispatch. §11 Risk "ADK Runner internals" is retired — we now use ADK's most-supported path, not a custom one.

## 5. Implementation outline

### 5.1 File inventory (consolidated across phases)

| Action | File | Phase |
|---|---|---|
| Modify | `app/adk/agents/agent_factory/builder.py` — `_make_factory_instruction_provider` reads `config_cache` | 1 |
| Modify | `app/adk/agents/utils/config_cache.py` — `@safe_weave_op(name="load_config_from_firestore")` decorator + extend keys to `(doc_id, account_id)` | 1, 2 |
| Create | `app/adk/agents/agent_factory/specialist_runtime.py` — `resolve_config`, `resolve_agent`, `run`, `available_specialists_provider` | 2 |
| Create | `app/adk/agents/agent_factory/dispatch.py` — `delegate_to_specialist` (replaces generated per-specialist dispatchers) | 2 |
| Modify | `app/adk/agents/agent_factory/hierarchy.py` — `build_hierarchy()` reduced to build the root only; specialist construction moves to `specialist_runtime` | 2 |
| Modify | `app/adk/agents/agent_factory/mcp.py` — `build_toolset_for_doc` gains a `kind` branch (`cloud_run` / `zapier`) | 3 |
| Create | `app/adk/agents/agent_factory/mcp_pool.py` — process-wide `McpToolsetPool` with kind-specific keying | 3 |
| Create | `api/scripts/migrate_mcp_servers_add_kind.py` — backfills `kind="cloud_run"` on existing docs | 3 |
| Modify | `app/adk/agents/agent_factory/hierarchy.py:325` — port `default_global` function-tool injection into the runtime resolver (was AH-PRD-06 PR-C) | 3 |
| Create | `api/src/kene_api/routers/integrations/zapier.py` — Zapier connect/disconnect endpoints | 4 (deferred to R2) |
| Create | `frontend/src/pages/settings/integrations/*` — "Connect Zapier" tile + connection status | 4 (deferred to R2) |
| Modify | `api/src/kene_api/routers/agent_configs.py:82` — `_REDEPLOY_REQUIRED_FIELDS` emptied; `warnings` field marked `deprecated=true` in OpenAPI | 2 |
| Delete | `app/adk/agents/ken_e_agent.py` — `create_ken_e_agent` and `_make_instruction_provider` deleted once verified unused | 5 |
| ~~Delete~~ (done AH-66) | `generate_dispatch_functions` deleted in AH-66; `_make_factory_instruction_provider`'s baked-text path remaining Phase 5 work | 5 |
| Update | Cloud Trace / Weave dashboards | 5 |

See [RFC §10 Appendix](../../../per-turn-dispatch-rfc.md#10-appendix--code-paths-affected) for the complete code-path table including doc edits.

### 5.2 Phase dependencies

```
Phase 0 (Zapier spike) ──gate──► Phase 4 (Zapier integration)  [R2]
                          │
Phase 1 (cache instruction) ──parallel──► (independent — ships value immediately)
                          │
                          ▼
                  Phase 2 (single-dispatch root + specialist runtime)
                          │
                          ▼
                  Phase 3 (McpToolsetPool + hybrid kinds)
                          │
                          ▼
                  Phase 5 (cleanup + rollout)
                          │
                          ▲
                          │ (hard gate)
                  SK-PRD-02 SandboxPool
```

## 6. API contract

### Changes to existing endpoints

| Endpoint | Change |
|---|---|
| `PUT /api/v1/accounts/{account_id}/agent-configs/{config_id}` (router: `api/src/kene_api/routers/agent_configs.py`) | `_REDEPLOY_REQUIRED_FIELDS` shrinks from `{model, temperature, max_output_tokens}` to the empty set for specialists. `MergedAgentConfig.warnings: list[str]` becomes vestigial — kept for backwards compatibility with older clients but always returned empty. Marked `deprecated=true` in the OpenAPI schema in Phase 2; slated for removal one release after Phase 5 rollout. |
| `POST /api/v1/accounts/{account_id}/agent-configs/` | Same — no "redeploy required" warnings on creation. |

### New endpoints (Phase 4 — deferred to R2)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/accounts/{account_id}/integrations/zapier/connect` | OAuth / API-key initiate per [IN-PRD-01](../../integrations/projects/IN-PRD-01-core-model-encryption.md) shape |
| `DELETE` | `/api/v1/accounts/{account_id}/integrations/zapier` | Disconnect; surfaces UX on dependent Zapier-kind specialists |

## 7. Acceptance criteria

ACs are organized by phase. Each phase merges only when its criteria are met.

### Phase 1 — Cache-backed instruction (R1)

1. An admin edit to `agent_configs/{config_id}.instruction` (or any factory-built specialist's instruction) propagates to the next chat turn within ~60 s **without redeploy**.
2. The `load_config_from_firestore` Weave span appears on every chat turn for the root agent (and every dispatched specialist).
3. Existing AH-PRD-01 review-loop tests still pass.

### Phase 2 — Single-dispatch root + specialist runtime (R1)

4. An admin creating a new specialist Firestore doc sees it appear in the root's Available Specialists block within ~60 s and can dispatch to it on the next chat turn.
5. Admin edits to `model`, `temperature`, `max_output_tokens`, and `tools` on a specialist take effect within ~60 s.
6. `_REDEPLOY_REQUIRED_FIELDS` is empty in `api/src/kene_api/routers/agent_configs.py:82`.
7. All AH-PRD-01 review-loop tests pass; review pipeline still wraps every dispatch.
8. p95 dispatch latency on a warm cache ≤ 1.2× the current p95.
9. **Chat per-turn token accumulator parity test passes** — token aggregates under inner-Runner dispatch match the deploy-time baseline (CH-PRD-01 contract preserved; see [RFC §4.9](../../../per-turn-dispatch-rfc.md#49-cross-component-contracts-preserved)). **Merge blocker.**
10. **Billing token meter parity test passes** — per-org billing totals under inner-Runner dispatch match the deploy-time baseline (BL-PRD-02 contract preserved; same test fixture as Chat). **Merge blocker.**
11. `MergedAgentConfig.warnings` marked `deprecated=true` in the OpenAPI schema; always returned empty.

### Phase 3 — `McpToolsetPool` + hybrid kinds (R1; `cloud_run` only — Zapier branch shipped behind a feature flag)

12. Pool keeps p95 specialist cold-start ≤ 200 ms across kinds.
13. **No SSE connection leak after a 1-hour sustained-load stress test** — specialists rebuilt > 1000 times across many `(account_id, server_id)` keys, MCP pool entries evicted, Cloud Run instance recycled — open SSE session count returns to baseline. **Merge blocker.**
14. **`default_global` function tools (`create_visualization`)** reach every runtime-resolved specialist without per-specialist config edits. _Implemented in `specialist_runtime._build_specialist` (`app/adk/agents/agent_factory/specialist_runtime.py:340–358`); test coverage in `test_specialist_runtime.py::TestSpecialistRuntimeDefaultGlobalTools` and `TestSpecialistRuntimeRosterCap` (AH-64). The current default_global set is `create_visualization`, `set_todo_list`, and `update_todo_list`. `create_visualization` callable registration is owned by AH-PRD-04 — until that ships, production traces will log a "no callable registered" warning for `create_visualization` and skip it, per `function_tool_registry.resolve_default_global_tools` design._
15. Pool eviction (LRU and TTL) calls `McpToolset.aclose()` before dropping the reference. Unit test asserts cleanup hook invoked.
16. No regression on existing GA MCP traffic.

### Phase 4 — Zapier-backed Integrations (DEFERRED TO R2)

17. An admin can connect Zapier in ≤ 1 minute (clicks: enable → grant → done).
18. Disconnecting Zapier surfaces a clear UX state on any Zapier-kind specialists that depended on it.
19. E2E test: connect Zapier → create a Zapier-backed specialist → chat → meaningful response.

### Phase 5 — Cleanup + rollout (R1)

20. All documentation reflects the new architecture; `[PLANNED]` tags collapsed where work shipped.
21. **MER-E eval suite passes against the new trace shape** — every prior eval set still scores correctly under `delegate_to_specialist` span structure. **Cutover gate.**
22. **SK-PRD-02 `SandboxPool` has shipped** — verified by `test_sandbox_pool_runtime_rebuild.py` (AH-66) that a sandbox-attached specialist does not respawn its sandbox across runtime rebuilds.
23. Legacy `generate_dispatch_functions` deleted (completed in AH-66; see DESIGN-REVIEW-LOG Review 39); remaining unused paths deleted in AH-68.
24. `MergedAgentConfig.warnings` field scheduled for removal one release after this rollout (not blocking Phase 5).

## 8. Test plan

### Unit
- `config_cache` extended: per-`(doc_id, account_id)` keying; striped lock contention; serve-stale-on-error preserved.
- `specialist_runtime.resolve_config` / `resolve_agent`: hit, miss, content-hash invalidation, LRU eviction at the documented caps.
- `delegate_to_specialist`: criteria-provided path wraps the specialist in `build_review_pipeline()`; `acceptance_criteria=None` preserves single-pass behavior.
- `available_specialists_provider`: per-account block rendering; TTL invalidation.
- `McpToolsetPool`: pool correctness under concurrent access; LRU + TTL eviction; `aclose()` invocation; re-auth on failure; both kinds.
- `McpServerKind` migration script: idempotent backfill; preserves existing fields.

### Integration
- End-to-end runtime resolution: seed Firestore with a fresh specialist → chat turn → resolver constructs and caches → span hierarchy includes `load_config_from_firestore` + `build_specialist_agent` (on cache miss).
- Cache invalidation: write to Firestore → wait for TTL → next turn sees updated config.
- Per-account overlay: seed global + account overlay → resolved config matches expected merge.
- **Chat parity test**: replay a deterministic chat turn under both deploy-time and runtime models; assert `extract_billable_tokens(event)` aggregates are identical. Phase 2 merge blocker.
- **Billing parity test**: same fixture; assert per-org totals identical. Phase 2 merge blocker.
- **MCP pool stress test**: 1-hour sustained load; assert no SSE connection leak via metrics + manual `ss -t state established` count. Phase 3 merge blocker.
- **Zapier dev specialist E2E** (Phase 4, R2): connect Zapier → create specialist with Zapier kind → chat → meaningful response.

### MER-E coordination
- Contract diff document drafted at start of Phase 2 — enumerates span name changes (`delegate_to_specialist` replaces `dispatch_to_*`), new attributes (`specialist_name`, `cache_hit`, `mcp_pool_hit`), retired attributes, and inner-Runner nesting shape.
- MER-E extractors updated and tested against a staging trace fixture before Phase 2 merges.
- Phase 5 cutover gated on MER-E eval suite passing.

### Performance gates
- p95 dispatch latency on warm cache ≤ 1.2× current p95 (Phase 2 AC).
- p95 specialist cold-start ≤ 200 ms across kinds (Phase 3 AC).
- 1-hour sustained-load stress test: open SSE session count returns to baseline (Phase 3 AC).

## 9. Risks & open questions

> **Full risk catalog in [RFC §9](../../../per-turn-dispatch-rfc.md#9-risks--open-questions).** Summary below.

### 9.1 Risks

- **Zapier vendor risk.** Concentrating the long tail behind Zapier creates a tier-1 dependency. Mitigation: hybrid model — owned MCP unaffected by Zapier degradation; `McpServerKind` enum can accommodate alternatives (Composio, Pipedream) without re-architecting.
- **Latency on cold starts.** First dispatch to a fresh specialist pays build + MCP-pool cost. Mitigation: cache warming at root start; pool LRU sized for working set; observability for outliers.
- **Cache-invalidation correctness.** Stale cached `LlmAgent` serving old behavior after a Firestore write is the failure we most want to avoid. Mitigation: content-hash invalidation in addition to TTL; integration tests covering "write then read" within the cache window.
- **ADK Runner internals.** Inner-Runner wiring depends on ADK's session/context propagation. Mitigation: pin ADK version in Phases 2–3; document the Runner contract.
- **MER-E contract drift.** Trace shape changes require coordinated MER-E updates. Mitigation: concrete coordination plan in [RFC §9.1](../../../per-turn-dispatch-rfc.md#91-risks) — owner pairing by end of Phase 0, contract diff at start of Phase 2, MER-E extractors validate against the post-AH-75 trace fixture. **Cutover gate.**
- **Chat / Billing event-topology drift.** Inner-Runner dispatch produces a different event sequence. Mitigation: Phase 2 parity tests as merge blockers.

### 9.2 Open questions

See [RFC §9.2](../../../per-turn-dispatch-rfc.md#92-open-questions-for-product--dev-review) for the full list. Resolved items:

- **#1 Strategy supervisor scope — resolved.** Account-creation-only; AH-PRD-09 leaves them untouched per [AH-PRD-08](./AH-PRD-08-hide-strategy-pipeline-specialists.md).
- **#8 Skills sandbox lifecycle — resolved.** Option (a): pool by `(account_id, skill_id)` in a `SandboxPool` (SK-PRD-02 scope expansion; mirrors `McpToolsetPool` discipline).
- **#9 AH-PRD-06 PR-C interaction — resolved.** Port `default_global` injection into the runtime resolver in Phase 3.

Pending product / dev review:
- **#2 Hash-based invalidation vs TTL.** Recommendation: TTL in v1, hash invalidation as a fast-follow.
- **#3 Per-account specialist visibility.** Recommendation: yes — resolver already knows `account_id`.
- **#4 Zapier pricing model.** Part of Phase 0 deliverables.
- **#5 Cutover strategy.** Feature flag + soak + default-on (current proposal).
- **#6 `LlmAgent`-instance cache scope.** Process-wide with `account_id` baked into the cache key.
- **#7 Read-only `is_system` specialists.** Yes, enforced by the CRUD API as today.

## 10. Reference

- **Design doc (canonical):** [`docs/design/per-turn-dispatch-rfc.md`](../../../per-turn-dispatch-rfc.md)
- **Upstream PRDs:** [AH-PRD-01](./AH-PRD-01-review-loop-framework.md) (review pipeline), [AH-PRD-02](./AH-PRD-02-agent-factory.md) (superseded factory), [DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md) (Shape B)
- **Coordination PRDs:** [SK-PRD-02](../../skills/projects/SK-PRD-02-agent-integration.md) (SandboxPool — Phase 5 gate), [CH-PRD-01](../../chat/projects/CH-PRD-01-session-metadata-substrate.md) (token accumulator parity), [BL-PRD-02](../../billing/projects/BL-PRD-02-token-meter-monthly-enforcement.md) (billing meter parity)
- **Sibling PRDs:** [AH-PRD-06](./AH-PRD-06-tool-mapping.md) (default-global tools), [AH-PRD-08](./AH-PRD-08-hide-strategy-pipeline-specialists.md) (strategy supervisor — out of scope)
- **Component docs:** [`../README.md`](../README.md), [`../mcp-architecture.md`](../mcp-architecture.md), [`../../integrations/README.md`](../../integrations/README.md) (Phase 4 dep, deferred to R2)
- **System docs:** [`../../../../KEN-E-System-Architecture.md`](../../../../KEN-E-System-Architecture.md) §1.4 (decisions), §4 (agent definitions), §5 (MCP)
- **Tracing:** [`docs/trace-structure-spec.md`](../../../../trace-structure-spec.md)
- **CLAUDE.md rules in scope:** PY-1, PY-2, PY-3, PY-5, PY-7; D-1, D-2, D-5; C-2, C-4, C-7; T-1, T-3, T-4, T-5, T-6, T-8; O-1, O-2

---

<!-- PRD MAINTENANCE NOTES

Updating this PRD:
- Sync with `docs/design/per-turn-dispatch-rfc.md` — the RFC is canonical for design rationale; this PRD is canonical for what to build.
- When a phase ships, update the relevant ACs in §7 with `[SHIPPED]` markers; collapse `[PLANNED]` markers in upstream docs (System Architecture, agentic-harness README) per the RFC §5 phase-by-phase doc cadence.
- When the Phase 0 Zapier spike completes, paste its go/no-go recommendation into §1 and update Phase 4's status (proceed in R2 vs retire to a future PRD).
- When SK-PRD-02 ships, mark §3 SandboxPool dep as "shipped" and re-confirm Phase 5 gate AC #23.

This PRD is read by the Dev Team agent during implementation planning. Keep it concise — every sentence should help a dev write better code or avoid mistakes.
-->
