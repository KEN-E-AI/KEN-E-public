# RFC: Per-Turn Dispatch Agent — Runtime Specialist Resolution with Hybrid MCP

**Status:** Proposed — awaiting product + dev review
**Author:** Agentic Harness team (drafted from a discovery thread, 2026-05-21)
**Audience:** Product Owner, Product Manager, Engineering leads (Agentic Harness, Integrations, Data Pipeline, MER-E)
**Supersedes (on approval):** [`AH-PRD-02 — Agent Factory`](components/agentic-harness/projects/AH-PRD-02-agent-factory.md)
**Related:** [`AH-PRD-01 — Review Loop Framework`](components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md), [`docs/KEN-E-System-Architecture.md`](../KEN-E-System-Architecture.md), [`docs/design/components/integrations/README.md`](components/integrations/README.md)

---

## 1. Executive summary

KEN-E's product requirement is that an admin who creates or edits an agent (instructions, model, temperature, max output tokens, and tools) gets that agent **immediately available** in chat — without an engineer in the loop. Our current architecture, locked in by [AH-PRD-02](components/agentic-harness/projects/AH-PRD-02-agent-factory.md), reads every agent config from Firestore once at deploy time and bakes the full specialist hierarchy into a Python object tree shipped to Vertex AI Agent Engine. Every field except `instruction` is frozen at that point, and even `instruction` is frozen on the deployed factory path because the hot-reload cache from Sprint 6 Decision B (`app/adk/agents/utils/config_cache.py`) is never read by the factory's instruction provider. The result: today, every config change — including new agents — requires a redeploy of the Agent Engine. The product promise is unmet.

This RFC proposes a successor architecture — the **Per-Turn Dispatch Agent**. The deployed root agent becomes a thin dispatcher whose only tool is `delegate_to_specialist(name, query, acceptance_criteria=None)`. Specialists are no longer constructed at deploy time. Instead, a runtime resolver reads the current specialist config from Firestore (cached, with hash-based invalidation), constructs the `LlmAgent` lazily, caches it for reuse, and runs it through an inner ADK Runner. Editing or creating a specialist Firestore document propagates to the next chat turn within ~60 s of the write (or immediately on cache miss). Only the root agent itself, plus the small set of root-level configuration, remains deploy-time-bound — and root changes are rare.

The proposal further introduces a **hybrid MCP model** to keep this tractable. Today, every specialist's tools bind to a KEN-E-owned MCP server on Cloud Run (per-platform: GA MCP, future Google Ads MCP, future Meta Ads MCP, etc.). Each new platform is a service to build, host, and maintain. We propose extending `mcp_servers/{server_id}` documents with a `kind` field — initially `cloud_run` (today's owned servers) or `zapier` (a single shared connection to Zapier's MCP endpoint that surfaces tools from whichever integrations the account has authorized in their Zapier workspace). For the long tail of integrations — Google Ads, Meta Ads, Mailchimp, HubSpot, the dozens of CRMs and marketing tools admins might want — Zapier MCP eliminates the per-platform service build and reduces the runtime MCP-pool problem from "N connections per account" to "one connection per account." Flagship, high-volume, or capability-heavy integrations stay on owned MCP servers via the same configurable enum.

The combination — runtime specialist resolution + hybrid MCP — meets the immediate-availability requirement, restores the spirit of Sprint 6 Decision B, dramatically shrinks the work to add a new integration, and shifts KEN-E's competitive surface from "we build MCP servers" to "we own the agent runtime that turns integrations into chat-driven workflows."

We recommend approving this direction subject to a **1–2 week Phase 0 spike** that proves Zapier MCP's capability, performance, auth model, and per-account isolation are acceptable before committing to the full implementation. The total scope is roughly 4–6 engineering weeks for one engineer (3–4 weeks with two), gated on the spike outcome.

---

## 2. Background — why we're proposing this change

### 2.1 The product requirement

> When a user creates a new agent and adds it to the agent factory they are asked to create instructions for the agent, choose a model, set the temperature, set the max output tokens, and decide which tools the agent will be able to access. The requirement is that this agent (with the configured model, temperature, max output tokens, and tools) will be available immediately, and that the user's configuration would be utilized.

This is a foundational expectation of KEN-E's agent factory product surface: admins configure agents in the UI; agents go live; users chat with them. No engineer involvement, no deploy.

### 2.2 What today's system actually delivers

Under [AH-PRD-02](components/agentic-harness/projects/AH-PRD-02-agent-factory.md), `agent_factory.build_hierarchy()` ([`app/adk/agents/agent_factory/hierarchy.py:137`](../../app/adk/agents/agent_factory/hierarchy.py)) is a 10-step pipeline that runs **once** during `deploy_ken_e.py`. It:

1. Reads every document under `agent_configs/{config_id}` and `mcp_servers/{server_id}`.
2. Applies per-account overlay (when `account_id` is supplied) by shallow-merging `accounts/{account_id}/agent_configs/{config_id}` onto each global config.
3. Builds one `McpToolset` per (specialist × server) using `build_toolset_for_doc` ([`app/adk/agents/agent_factory/mcp.py:327`](../../app/adk/agents/agent_factory/mcp.py)).
4. Resolves each specialist's ≤30-tool roster via `resolve_specialist_roster`.
5. Constructs each specialist as an `LlmAgent` (`builder.py:60` — bakes `instruction`, `model`, `temperature`, `max_output_tokens`, `tools`).
6. Generates `dispatch_to_<specialist>()` callables.
7. Renders an "Available Specialists" block into the root's instruction.
8. Constructs the root `LlmAgent` with those dispatchers as tools.
9. Returns the tree.

The tree is pickled, shipped to Agent Engine, and rehydrated there. From that moment forward, the entire tree is frozen Python state. ADK's `LlmAgent` constructor accepts callables for **only** the `instruction` field; `model`, `generate_content_config` (which carries `temperature` and `max_output_tokens`), and `tools` are all bound at construction.

The mapping from product requirement to today's reality:

| User changes | Takes effect when |
|---|---|
| Creates a new agent | After next `deploy_ken_e.py` run (10–15 min). |
| Edits an agent's `tools` (e.g., adds Google Ads to a research specialist) | After next deploy. |
| Edits `model` | After next deploy. PUT endpoint already returns a `redeploy required` warning (`api/src/kene_api/routers/agent_configs.py:82`). |
| Edits `temperature` | After next deploy. Same warning. |
| Edits `max_output_tokens` | After next deploy. Same warning. |
| Edits `instruction` | **Designed** to propagate within 60 s via Sprint 6 Decision B's cache, but **today** also requires a redeploy because the factory's `_make_factory_instruction_provider` ([`app/adk/agents/agent_factory/builder.py:33`](../../app/adk/agents/agent_factory/builder.py)) bakes the text into a closure and never reads the cache. |

The PUT endpoint at `api/src/kene_api/routers/agent_configs.py:300-310` returns operator warnings for the three GCC fields but cannot warn for `instruction` (it was supposed to hot-reload). Today admins editing `instruction` get silent regression — the change appears accepted but never reaches the deployed agent.

### 2.3 Why this regressed

When the factory was introduced (AH-PRD-02), the root agent's construction path switched from the legacy `create_ken_e_agent()` in `app/adk/agents/ken_e_agent.py` (which uses the cache-backed `_make_instruction_provider` at line 164) to the factory's `_make_factory_instruction_provider` (which doesn't). The legacy path is still in the codebase but not used by the deployed root. The Sprint 6 Decision B cache exists in code (`app/adk/agents/utils/config_cache.py`) and is well-tested, but no caller on the live request path reads from it.

This is recoverable, but not by a small patch. The underlying issue is architectural: the factory is fundamentally a deploy-time builder. Even fixing the instruction path leaves `model`, `temperature`, `max_output_tokens`, `tools`, and **new specialist creation** as redeploy-bound, which fails the product requirement.

### 2.4 The MCP scaling problem we'd otherwise inherit

If we converted the factory to a runtime resolver naively, we'd need to manage a pool of `McpToolset` connections across specialist rebuilds. Each toolset holds an SSE connection to a Cloud Run MCP server (or a stdio process for local MCP). Pooling would be keyed by `(server_id × auth_credentials × account_id)` — three dimensions, potentially many open connections per Cloud Run instance, with per-connection lifecycle (re-auth, reconnect, eviction). This is solvable but expensive.

The MCP scaling problem is also a **product** problem, not just a runtime one. Today, adding a new integration platform means building, deploying, and operating a new Cloud Run MCP server. That's weeks of engineering per platform, and it caps the rate at which KEN-E can support new integrations. Long-tail integrations (e.g., a single-tenant CRM, a regional ad platform, a niche analytics tool) are economically infeasible.

### 2.5 Zapier MCP as the relief valve

Zapier offers an MCP endpoint that exposes tools for every integration an account has authorized in their Zapier workspace. A single connection per account surfaces hundreds of potential integrations. For the long-tail use case, this collapses the engineering cost of "add a new platform" from "build a Cloud Run service" to "write a Firestore agent config that references Zapier tools." It also collapses the runtime MCP-pool problem from N-dimensional to one-dimensional: one connection per `(account_id, zapier_token)`.

Zapier's tradeoffs — vendor dependency, capability ceiling, latency, per-task pricing — are real and mean Zapier cannot be the *only* MCP. Flagship integrations (today's GA MCP; tomorrow's high-volume analytical or data-pipeline platforms) likely stay owned. This RFC proposes a **hybrid** so both can coexist behind a single specialist-runtime interface.

---

## 3. Goals & non-goals

### 3.1 Goals

1. **Immediate availability for admin-created agents.** A user creating or editing a specialist agent in the UI (instruction / model / temperature / max output tokens / tool roster) sees the change take effect on their next chat turn, or within ~60 s for cached reads.
2. **Restore Sprint 6 Decision B's spirit.** Hot-reloadable agent configuration is the default, with `_REDEPLOY_REQUIRED_FIELDS` shrinking from `{model, temperature, max_output_tokens}` to **the empty set** for specialists.
3. **Reduce the engineering cost of new integrations.** Adding a long-tail integration becomes a Firestore config write plus a Zapier OAuth grant — no Cloud Run deploy.
4. **Keep flagship integrations on owned infrastructure** where capability, latency, or cost demand it (today: GA MCP; future: anything Zapier can't serve adequately).
5. **Preserve the review loop and the ≤30-tool-roster scope discipline** from [AH-PRD-01](components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md) and [README §2.5](components/agentic-harness/README.md#25-tool-assignment--routing-model).
6. **Surface the change in MER-E traces.** Every chat turn emits a `load_config_from_firestore` span (or equivalent), restoring the eval contract that broke when the factory path stopped reading the cache.

### 3.2 Non-goals

- **Hot-reloading root-agent settings** (root `model`, root `temperature`, root direct tools beyond `delegate_to_specialist`). The root remains deploy-time-bound. Root changes are rare and will continue to require a redeploy.
- **Replacing all owned MCP servers with Zapier.** This is explicitly hybrid. The GA MCP and any future flagship platform stay where they are unless a separate decision moves them.
- **Multi-channel work** (Slack, Voice). Channel architecture is out of scope ([Architecture §7.3](../KEN-E-System-Architecture.md#73-planned-additional-channels)).
- **Changes to the Skills, Project Tasks, or Automations runtime model.** Those components compose on top of the harness; this RFC affects how the harness assembles specialists, not how upstream features use them.
- **Removing the agent factory concept.** "Factory" remains the right name for the assembly system — it just runs at every turn instead of once at deploy.

---

## 4. Proposed architecture

### 4.1 Conceptual shift

**Today (AH-PRD-02):**

```
                          deploy_ken_e.py runs once
                                    │
                                    ▼
                       build_hierarchy(account_id?)
                                    │
                ┌───────────────────┼────────────────────┐
                ▼                   ▼                    ▼
        agent_configs/*      mcp_servers/*       account overlay
                │                   │                    │
                └───────────────────┴────────────────────┘
                                    │
                                    ▼
              Build N specialists (LlmAgent each, baked GCC + tools)
                                    │
                                    ▼
            Build root LlmAgent (instruction = base + "Available Specialists" block;
                                  tools = [dispatch_to_specA, dispatch_to_specB, ...])
                                    │
                                    ▼
                            ship to Agent Engine (frozen)
```

After ship, every chat turn invokes the pre-built root, which calls a pre-bound `dispatch_to_<specialist>()`, which invokes a pre-built specialist.

**Proposed (Per-Turn Dispatch):**

```
                          deploy_ken_e.py runs once
                                    │
                                    ▼
                       build_root_only(root_config)
                                    │
                                    ▼
            Build root LlmAgent (instruction = base + InstructionProvider closure
                                  reading "Available Specialists" from cache per turn;
                                  tools = [delegate_to_specialist])
                                    │
                                    ▼
                            ship to Agent Engine
```

After ship, on each chat turn:

```
  Root LLM picks specialist by name → delegate_to_specialist(name, query, criteria?)
                                    │
                                    ▼
                          specialist_runtime.resolve(name, account_id)
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
       config_cache             agent_cache            mcp_pool
       (TTL ~60s, or            (keyed by config        (one entry per
       hash-invalidated)        content hash;           (account_id,
              │                  rebuilds on miss)      zapier_token) or
              ▼                                         (server_id, account_id)
       MergedAgentConfig                                 for owned MCP)
              │
              └─────────► build specialist LlmAgent
                                    │
                                    ▼
                          inner ADK Runner.run(query)
                                    │
                                    ▼
                     review pipeline (LoopAgent) if criteria
                                    │
                                    ▼
                          assistant message back to root
```

### 4.2 Key abstractions (new)

| Symbol | Location (proposed) | Responsibility |
|---|---|---|
| `delegate_to_specialist(name, query, acceptance_criteria=None)` | `app/adk/agents/agent_factory/dispatch.py` | The single root tool. Replaces all `dispatch_to_<specialist>()` callables. Validates `name`, calls `specialist_runtime.run(...)`, returns the assistant message. Stays `@safe_weave_op(name="delegate_to_specialist")` for tracing. |
| `specialist_runtime.run(name, query, criteria, context)` | `app/adk/agents/agent_factory/specialist_runtime.py` | Orchestrates resolve → build → run for one dispatch. The natural site for the `load_config_from_firestore` span (restoring MER-E's contract). |
| `specialist_runtime.resolve_config(name, account_id)` | (same module) | Returns a `MergedAgentConfig` for `(name, account_id)`. Cached by `config_cache` with TTL + content hash. Includes per-account overlay merge moved to runtime. |
| `specialist_runtime.resolve_agent(config)` | (same module) | Returns an `LlmAgent` constructed from `config`. Cached by `(name, content_hash)` so unchanged configs reuse one instance. |
| `available_specialists_provider(account_id) -> str` | (same module) | Renders the "Available Specialists" block from current Firestore state. Called by the root's instruction provider on every turn. Cached at the listing level. |
| `McpServerKind` | `app/adk/agents/agent_factory/mcp.py` | Open enum: `cloud_run`, `zapier`, and future kinds. Persisted as `mcp_servers/{server_id}.kind`. |
| `McpToolsetPool` | `app/adk/agents/agent_factory/mcp_pool.py` | Process-wide pool of `McpToolset` instances. Keys differ by `kind`: Zapier pools by `(account_id, zapier_token)`; Cloud Run pools by `(server_id, account_id, auth_credentials_hash)`. Handles connection reuse, re-auth, eviction (LRU + TTL). |
| `ZapierIntegration` (per account) | `accounts/{account_id}/integrations/zapier` | Stores the account's Zapier OAuth grant / API key. Owned by the Integrations component. |

#### 4.2.1 Cache key shapes

Each cache below has a specific key shape to prevent correctness bugs. All caches use **per-key striped locking** (`hash(key) % 32`) rather than today's process-wide `_cache_lock` — necessary because the new caches see N × M entries (specialists × accounts) where today's `config_cache` saw single-digit entries.

| Cache | Location | Key | Value | Invalidation |
|---|---|---|---|---|
| `config_cache` (extended) | `app/adk/agents/utils/config_cache.py` | `(doc_id, account_id \| None)` | `(MergedAgentConfig, metadata, extensions)` | TTL (~60 s) + content-hash on re-fetch; serve-stale-on-error preserved |
| `agent_cache` | `app/adk/agents/agent_factory/specialist_runtime.py` | `(name, account_id \| None, content_hash)` | `LlmAgent` | Implicit — a new `content_hash` produces a new cache entry; LRU eviction at 256 entries |
| `available_specialists_cache` | (same module) | `account_id \| None` | rendered "Available Specialists" block (string) | TTL (~60 s); fast-path invalidation on any `(doc_id, account_id)` write into `config_cache` |
| `mcp_pool.cloud_run` | `app/adk/agents/agent_factory/mcp_pool.py` | `(server_id, account_id, sha256(auth_credentials))` | `McpToolset` | LRU at 128 entries + idle TTL (10 min); `aclose()` on eviction (see §4.8) |
| `mcp_pool.zapier` | (same module) | `(account_id, sha256(zapier_token))` | `McpToolset` | Same |

The `content_hash` for `agent_cache` is `sha256(canonical_json(MergedAgentConfig))` — any field change invalidates the cached `LlmAgent`. This is what makes "edit any specialist field and see it on the next turn" work without per-field detection logic on the read side.

### 4.3 What stays the same

- `agent_configs/{config_id}` document schema. The same `MergedAgentConfig` model. No migration of existing global configs required.
- `mcp_servers/{server_id}` document schema, **plus** one new field `kind: "cloud_run" | "zapier"` (defaults to `cloud_run` for backwards compatibility).
- Per-account overlay model (`accounts/{account_id}/agent_configs/{config_id}` shallow merge). Same semantics, executed at runtime instead of deploy time.
- The review loop ([AH-PRD-01](components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md)) — `build_review_pipeline()` is called inside `delegate_to_specialist` exactly as it was inside the generated dispatchers.
- The ≤30-tool roster discipline ([README §2.5](components/agentic-harness/README.md#25-tool-assignment--routing-model)) — applied at specialist construction time, just at runtime now.
- Description-based routing — the root LLM picks specialists by reading the dynamic "Available Specialists" block. The block's format and content semantics are identical to today's; only the moment of rendering changes.
- The agent-builder UI from AH-PRD-02 Phase 3 (`Workflows > Agents` listing, detail view, `AgentCreatePage`).
- Weave tracing, MER-E contract (the `load_config_from_firestore`-equivalent span returns).

### 4.4 What changes — narrowly

- The root agent's `tools` list becomes `[delegate_to_specialist]` instead of `[dispatch_to_specA, dispatch_to_specB, ...]`.
- The root's instruction is rendered per turn (instruction provider closure reading from a cache) rather than baked at deploy.
- Specialist `LlmAgent` instances are built lazily on first dispatch and cached, instead of all built at deploy.
- `mcp_servers/{server_id}.kind` is read at toolset-build time to select between the existing `cloud_run` plumbing and a new `zapier` path.
- `_REDEPLOY_REQUIRED_FIELDS` (in `api/src/kene_api/routers/agent_configs.py:82`) becomes empty for non-root configs.

### 4.5 What still requires a redeploy

| Change | Why |
|---|---|
| Root `model` / `temperature` / `max_output_tokens` | Baked into the root `LlmAgent` at deploy. Root rebuilds are rare. |
| Root-level direct tools (anything beyond `delegate_to_specialist`) | Same — root tool list is baked. |
| Python / ADK version upgrades | Standard Agent Engine deploy. |
| New `McpServerKind` values | Adding a third kind (e.g., `composio`) is a code change in `mcp.py`. Configuring an existing kind is data-only. |
| Schema changes to `MergedAgentConfig` | Pydantic model. Most edits to existing fields are data-only; adding/removing fields is code. |

This is consistent with the product requirement: admins configure agents and their tools; admins do not configure the root agent or platform-level plumbing.

### 4.6 MCP hybrid — `McpServerKind` enum

`mcp_servers/{server_id}` documents gain a `kind` field:

```python
class McpServerKind(StrEnum):
    cloud_run = "cloud_run"   # Existing — KEN-E-owned MCP server on Cloud Run
    zapier    = "zapier"      # Single Zapier MCP endpoint per account
    # Future: composio, pipedream, custom_http, ...
```

- `cloud_run`: today's path. `build_toolset_for_doc` continues to construct an `McpToolset` from `connection.url`, `connection.auth_type`, etc. The pool keys by `(server_id, account_id, auth_credentials_hash)`.
- `zapier`: a new branch in `build_toolset_for_doc` that constructs an `McpToolset` pointed at Zapier's MCP endpoint, authenticated with the account's Zapier credentials from `accounts/{account_id}/integrations/zapier`. The pool keys by `(account_id, zapier_token)` — one entry per account.
- Specialist configs declare which server(s) they consume via the existing `mcp_servers: list[str]` field. A specialist can mix kinds (e.g., a "marketing operations" specialist might consume a Zapier server for HubSpot tools plus a Cloud Run server for KEN-E's data-pipeline tools).
- The Integrations UI for `cloud_run` integrations works as today (per-platform OAuth flows). The Integrations UI for `zapier` adds a single "Connect Zapier" action; once connected, the user manages individual integrations inside Zapier.
- Per-specialist tool filtering ([AH-PRD-06](components/agentic-harness/projects/AH-PRD-06-tool-mapping.md)) still applies — a specialist references a server and an allowlist of tool names. For Zapier-kind servers the tool names are Zapier's tool names; the allowlist scopes the specialist to (say) only Zapier's Google Ads tools, even though the underlying Zapier connection exposes hundreds.

### 4.7 Performance model

| Concern | Today | Proposed | Mitigation |
|---|---|---|---|
| Cold start on first specialist dispatch | None (pre-built) | ~50–200 ms agent construction + ~50–500 ms MCP connection if pool miss | Warm the cache on root start; pool MCP across specialist rebuilds. |
| Warm dispatch | ~immediate | ~5–20 ms cache lookup + agent reuse | None needed. |
| New specialist visible to the LLM | After redeploy | On the next turn (Available Specialists block re-renders) | None needed. |
| Specialist config edit propagation | Never (without redeploy) | ≤60 s (TTL) or instant (hash invalidation if we add a Firestore listener) | Optional Firestore listener as a future enhancement. |
| Concurrent dispatch to the same specialist | Serialized through one in-process agent | Same — `LlmAgent` is reused from cache | None needed. |
| Memory footprint | Bounded by N specialists | N specialists × cache hit rate + pool entries | LRU eviction in `specialist_runtime.resolve_agent` and `McpToolsetPool`. |
| Cache lock contention | Single process-wide `_cache_lock` (acceptable: ~1 active entry today) | Per-key striped locks (`hash(key) % 32`) across `config_cache`, `agent_cache`, `mcp_pool` | Independent specialist resolutions don't serialize; per-stripe contention bounded under expected workload (≤ 5 concurrent dispatches per stripe in p99) |

### 4.8 Failure modes

- **Specialist config missing in Firestore (after delete).** Root has stale Available Specialists block (within TTL). `delegate_to_specialist(name=...)` returns a structured error ("Specialist 'X' is no longer available"). Root surfaces a graceful message.
- **MCP connection failure (any kind).** `McpToolsetPool.get()` retries with backoff; on persistent failure, the specialist runs without that toolset and emits a Weave warning attribute (`mcp_degraded=true`). The Generator–Critic loop may still pass if the specialist can fulfill the criteria from remaining tools.
- **Zapier outage.** Every Zapier-kind specialist degrades simultaneously. Surfaced as a banner on the Integrations status page. Owned MCP specialists unaffected.
- **Agent rebuild failure (validation error).** The previous cached `LlmAgent` is served stale, with a warning log, until a successful rebuild. Matches the "serve-stale-on-error" pattern already in `config_cache.get_cached_config`.
- **McpToolset eviction.** LRU- or TTL-triggered pool eviction calls `McpToolset.aclose()` (or the equivalent async-context-manager `__aexit__`) before dropping the reference. ADK 1.27+ toolsets hold SSE sessions managed by async context managers; premature reference drops leak connections. A 60 s background sweep closes entries idle > 10 min in addition to per-access eviction. Verified by a Phase 3 stress test that asserts open SSE session count returns to baseline after 1 hour of sustained load.

### 4.9 Cross-component contracts preserved

The runtime resolver changes the *moment* and *shape* of dispatch (a single `delegate_to_specialist` tool with an inner Runner, instead of N pre-built `dispatch_to_*` callables) but must preserve the contracts other components depend on. Each contract below has a Phase 2 acceptance criterion (§7) that verifies it before flag flip.

| Contract | Owner | What it consumes today | What must remain true |
|---|---|---|---|
| **Chat per-turn token accumulator** (CH-PRD-01) | Chat | Every event emitted in a chat turn — `extract_billable_tokens(event)` reads input / output / reasoning fields. | Every event, including those emitted by the inner Runner inside `delegate_to_specialist`. ADK event propagation from inner to outer Runner must reach the accumulator. Parity test required (Phase 2 AC). |
| **Billing token meter** (BL-PRD-02) | Billing | Same `extract_billable_tokens(event)` helper at `shared/token_accounting.py`; per-org billing window enforcement wraps the chat-root invocation. | Same event stream, same totals. The `check_status` / `meter_increment` wrapper around the root invocation is unchanged — only the events it observes are flatter at the dispatch level. Shared parity test with Chat (Phase 2 AC). |
| **MER-E eval spans** ([`trace-structure-spec.md`](../trace-structure-spec.md)) | MER-E (sister repo) | Per-specialist `dispatch_to_*` spans + nested L2/L3 spans per the trace contract. | A single `delegate_to_specialist` span replaces the per-specialist dispatchers; inner-Runner spans appear as L2 children. MER-E extractors updated to match. Coordinated rollout — see §9.1. |
| **Project Tasks orchestrator** ([PR-PRD-02](components/project-tasks/projects/PR-PRD-02-planning-agent-and-tools.md)) | Project Tasks | `AgentEngineClient` invokes the deployed root agent with a session + a structured task input. | Unchanged. The root agent remains the entry point; runtime resolution happens inside `delegate_to_specialist`. The `project_planning` specialist becomes runtime-resolved like every other factory-built specialist, but the orchestrator's invocation contract is untouched. |
| **Skills sandbox lifecycle** ([SK-PRD-02](components/skills/projects/SK-PRD-02-agent-integration.md)) | Skills | `SkillToolset` constructed per specialist at deploy time; sandbox code-executor processes long-lived. | Per-turn specialist rebuild implies per-turn `SkillToolset` reconstruction. **Resolved by adding `SandboxPool` to Skills** — sandboxes pooled by `(account_id, skill_id)` decouple sandbox lifecycle from `agent_cache` reuse. SK-PRD-02 scope expansion; must land before AH-PRD-09 Phase 5 default-on. See §9.2 #8 for the design choice. |
| **Strategy supervisor downstream agents** ([AH-PRD-08](components/agentic-harness/projects/AH-PRD-08-hide-strategy-pipeline-specialists.md)) | Agentic Harness | `marketing_researcher` / `marketing_formatter` / `business_*` / `competitive_*` / `brand_*` constructed deploy-time via the legacy `strategy_agent/config_loader.py`; invoked exactly once per account during onboarding via `create_strategy_docs_supervisor.py`. Hidden from the chat picker (`visible_in_frontend=False`) per AH-PRD-08. | **No change.** These are account-creation-only and not chat-callable, so the "immediate availability" requirement does not apply. AH-PRD-09 leaves their construction path untouched — neither the runtime resolver nor Phase 1's instruction hot-reload is wired into the legacy loader. If a future UX makes them chat-callable, AH-PRD-08's hiding decision needs revisiting and AH-PRD-07's Option A / B analysis becomes relevant again. |

---

## 5. Changes to `docs/KEN-E-System-Architecture.md`

The System Architecture document is the canonical map and is loaded by every story's Context Loading Sequence. Approving this RFC requires the following edits. **None of these edits ship until the corresponding implementation phase lands** — the architecture doc is kept truthful by phase.

### 5.1 §4 Agent Definitions

- Update the bullet list of references to point at the **successor PRD** (e.g., AH-PRD-09 once filed) instead of AH-PRD-02 as the canonical agent factory. AH-PRD-02 gets a "Superseded by" frontmatter note linking forward.
- Add a one-paragraph callout at the top of §4 explicitly stating: "Specialists are resolved per turn from Firestore; the root agent is the only deploy-time agent. See AH-PRD-09 / `docs/design/per-turn-dispatch-rfc.md` for the runtime model."

### 5.2 §5 MCP Server Architecture

- Update bullet 4 (currently: *"MCP server connections are fixed at deploy time."*) to read: *"MCP server connections are pooled and resolved at runtime. A specialist's MCP toolsets are constructed lazily on first dispatch and cached across rebuilds via `McpToolsetPool`. `mcp_servers/{server_id}.kind` selects between `cloud_run` (KEN-E-owned) and `zapier` (shared third-party MCP aggregator) connection paths."*
- Add a new sub-section §5.x **Hybrid MCP via `McpServerKind`** with the enum definition, the two initial kinds, and the per-kind pool keying. Link out to the updated `mcp-architecture.md` for full details (see §5.4 below for that doc's changes).
- Add a one-line note in the *Headline properties* list: *"Long-tail integrations route through a single Zapier MCP connection per account; flagship integrations stay on owned Cloud Run servers."*

### 5.3 §2 Architecture Overview

- Update the agent-tree paragraph to show the root as a thin dispatcher with one tool (`delegate_to_specialist`).
- Update the agent-factory paragraph: "The agent factory runs at every turn for specialists; only the root agent is built at deploy time."

### 5.4 Component documents downstream of the architecture

- [`docs/design/components/agentic-harness/README.md`](components/agentic-harness/README.md)
  - §1 Overview: replace "the config-driven factory that assembles the whole hierarchy at deploy time" with "the runtime factory that assembles specialists per turn from Firestore."
  - §2 Architecture: redraw the agent tree diagram showing single-dispatch root + per-turn specialist resolution.
  - §2.5 Tool Assignment & Routing: keep the description-based routing model; add a note that the "Available Specialists" block is rendered per turn.
- [`docs/design/components/agentic-harness/mcp-architecture.md`](components/agentic-harness/mcp-architecture.md)
  - New §X Hybrid MCP Kinds: full `McpServerKind` enum spec, Zapier connection model, pool design, eviction policy.
  - Update the *MCPServerManager disposition* section: the pool replaces what little remains of the old manager.
- [`docs/design/components/integrations/README.md`](components/integrations/README.md)
  - New top-level section on the Zapier integration path: single OAuth/API-key per account, scope of permissions, how it relates to per-platform OAuth (which remains for `cloud_run` MCP servers).
- [`docs/design/components/chat/README.md`](components/chat/README.md)
  - §2.3 Token usage accounting: note that the per-turn `SessionTurnAccumulator` continues to extract tokens from every ADK event, but events now flow through an inner Runner inside `delegate_to_specialist`. The contract is preserved (see §4.9). A parity test against an inner-Runner trace fixture is added to verify per-turn input / output / reasoning aggregates remain correct.
- [`docs/design/components/billing/README.md`](components/billing/README.md)
  - §3 Token meter: confirm `extract_billable_tokens(event)` continues to produce correct per-org totals across the inner-Runner dispatch (parity test shared with Chat; both consumers share `shared/token_accounting.py`). The `check_status` / `meter_increment` enforcement wrapper around the chat-root invocation is unchanged.
- [`docs/design/components/project-tasks/README.md`](components/project-tasks/README.md)
  - §8.2 TaskOrchestrator note: `AgentEngineClient` invokes the deployed root unchanged. The `project_planning` specialist becomes runtime-resolved like every other factory-built specialist; admins can edit its config from the agent-builder UI and changes take effect on the next plan dispatch.
- [`docs/design/components/skills/README.md`](components/skills/README.md)
  - SK-PRD-02 integration: `SkillToolset` instances are constructed at the same moment as a specialist's `McpToolset`s, now per turn. The sandbox lifecycle implication is tracked as §9.2 #8.
- [`docs/design/components/agentic-harness/projects/AH-PRD-02-agent-factory.md`](components/agentic-harness/projects/AH-PRD-02-agent-factory.md): add frontmatter:

  ```
  > **Superseded by:** AH-PRD-09 — Per-Turn Dispatch Agent (`./AH-PRD-09-per-turn-dispatch.md`, sibling of AH-PRD-02) and `docs/design/per-turn-dispatch-rfc.md`. AH-PRD-02 describes the deploy-time factory as shipped; AH-PRD-09 ships the runtime successor. Read AH-PRD-09 for the live architecture.
  ```

- [`docs/design/DESIGN-REVIEW-LOG.md`](DESIGN-REVIEW-LOG.md): new entry documenting the architectural decision (date, scope, decision, consequences). Per CLAUDE.md, structural reorganization of this magnitude warrants a Review entry.

### 5.5 Operator-facing docs

- The PUT response shape from `api/src/kene_api/routers/agent_configs.py` simplifies: `_REDEPLOY_REQUIRED_FIELDS` shrinks to the empty set for specialists. The `warnings: list[str]` field becomes **vestigial** — kept on the API contract for backwards compatibility with older clients still inspecting it, but always returned empty under the new runtime model. Mark `deprecated=true` in the OpenAPI schema in Phase 2; slated for removal one release after Phase 5 rollout.
- Admin documentation (UI tooltips, help center copy): "Your changes take effect immediately. Reload the chat to see updates." The "Redeploy required" warning UI pattern goes away for specialist edits — coordinate a Figma update with the UI team to remove the warning slot from the AgentEdit page.

---

## 6. Relationship to existing AH PRDs

| PRD | Disposition under this RFC |
|---|---|
| [AH-PRD-01 — Review Loop Framework](components/agentic-harness/projects/AH-PRD-01-review-loop-framework.md) | **Unchanged.** `build_review_pipeline()` is called inside `delegate_to_specialist` exactly as it was inside the generated dispatchers. |
| [AH-PRD-02 — Agent Factory](components/agentic-harness/projects/AH-PRD-02-agent-factory.md) | **Superseded by AH-PRD-09 (new).** AH-PRD-02 retains its narrative as "what shipped first"; AH-PRD-09 ships the runtime successor. |
| [AH-PRD-03 — Google Analytics Specialist](components/agentic-harness/projects/AH-PRD-03-google-analytics-specialist.md) | **Unchanged at the spec level.** GA stays on `cloud_run` MCP (already shipped, high-value, capability-heavy). Its specialist config is resolved per turn under the new runtime. |
| [AH-PRD-04 — Data Visualization](components/agentic-harness/projects/AH-PRD-04-data-visualization.md) | **Unchanged.** `create_visualization` is a function tool, not MCP. |
| [AH-PRD-05 — Multi-Step Workflows](components/agentic-harness/projects/AH-PRD-05-multi-step-workflows.md) | **Unchanged at the spec level.** `build_workflow_pipeline` composes specialists; specialists are now resolved per turn but the composition is identical. |
| [AH-PRD-06 — Tool Mapping](components/agentic-harness/projects/AH-PRD-06-tool-mapping.md) | **Extended.** Per-tool allowlists work for both `cloud_run` and `zapier` kinds. The allowlist scopes Zapier's broad tool catalog down to a specialist's domain. |
| [AH-PRD-07 — Unify Strategy Agent Construction](components/agentic-harness/projects/AH-PRD-07-unify-strategy-agent-construction.md) | **Superseded by AH-PRD-08 — no impact on AH-PRD-09.** AH-PRD-07's original plan (unify strategy-agent construction with the factory) was replaced by AH-PRD-08, which hides the 8 strategy-pipeline specialists from the chat picker (`visible_in_frontend=False`) instead. The motivating insight: these specialists are **account-creation-only**, invoked exactly once via `create_strategy_docs_supervisor.py` during onboarding, never via the runtime chatbot — so the "immediate availability" requirement never applied. They continue to use the legacy `strategy_agent/config_loader.py` construction path unchanged. AH-PRD-09 leaves them entirely untouched; no sequencing coordination required. |
| [AH-PRD-08 — Hide Strategy Pipeline Specialists](components/agentic-harness/projects/AH-PRD-08-hide-strategy-pipeline-specialists.md) | **Unchanged.** Visibility flag still applies; the resolver respects it when rendering the Available Specialists block. |

**New PRD to file on RFC approval:** AH-PRD-09 — Per-Turn Dispatch Agent. The RFC body becomes the basis for its §1–§4. The phased plan (§7 of this RFC) becomes the work-breakdown structure inside AH-PRD-09's §5.

---

## 7. Phased implementation plan

Six phases. Phases 0 and 1 are gating: if Phase 0 fails to validate Zapier MCP, the rest of the plan rescopes around `cloud_run`-only and the architectural shift stands but the product velocity benefit shrinks.

### Phase 0 — Zapier MCP feasibility spike + `McpServerKind` design (1–2 weeks)

**Goal:** Prove that Zapier MCP can serve as the long-tail platform behind a `zapier` kind. Produce a written spike report and a `McpServerKind` data-model proposal.

**Work:**
- **Capability probe:** identify 3 representative target integrations (e.g., Google Ads campaign creation, HubSpot contact lookup, Slack message post). For each, confirm Zapier MCP exposes a tool that fits a specialist's natural calling pattern.
- **Auth probe:** verify Zapier MCP's auth model (OAuth vs API key), token lifecycle (refresh, revocation), and per-account isolation. Confirm a KEN-E account A cannot trigger actions on KEN-E account B's Zapier workspace.
- **Performance probe:** measure end-to-end latency from KEN-E dev → Zapier MCP → underlying API → response for a representative action and a representative read, at p50/p95.
- **Cost probe:** model expected Zapier task usage against per-account chat volume. Compare to Cloud Run + integration-API costs at the same volume.
- **Protocol probe:** confirm Zapier MCP's transport (HTTP+SSE? streamable HTTP?), tool-discovery semantics (push? poll?), and whether their server supports `tool_filter`-style scoping.
- **Data-model proposal:** draft the `McpServerKind` enum, the new `mcp_servers/{server_id}.kind` field, and migration sketch.
- **Prototype:** a throwaway `delegate_to_specialist_v0` that calls one Zapier-MCP-backed specialist end to end (no caching, no pool, no per-account overlay). Live in a feature-flagged dev endpoint; not shipped to production.

**Deliverables:**
- Spike report (markdown, lives at `docs/spike-zapier-mcp-feasibility.md`).
- A go / no-go recommendation with concrete numbers.
- `McpServerKind` proposal (PRD-shaped, lands as AH-PRD-09's §4 if approved).
- Throwaway prototype branch (not merged).

**Exit criteria:**
- p95 end-to-end latency for a representative action ≤ 3× the equivalent owned-MCP latency, OR a documented mitigation plan.
- Per-account isolation confirmed (manual test: account A grants Zapier, account B does not → account B's specialist sees no tools from A's workspace).
- Capability coverage: all 3 probe integrations expose tools acceptable for a v1 specialist.
- Cost projection within a tolerable envelope (define with finance).

**Owner:** 1 engineer (AH team).
**Risk:** Highest in the plan. If exit criteria fail, the project pivots to "`cloud_run`-only runtime resolver" — same architecture, smaller product win.

### Phase 1 — Foundation: cache-backed instruction on the existing factory path (1 week)

**Goal:** Restore Sprint 6 Decision B's intent for `instruction` on the deployed root, **without** changing the deployed-time factory model. This is a quick win that ships value before Phases 2+ land, and is the foundation for the runtime resolver.

**Work:**
- Extend `_make_factory_instruction_provider` in `app/adk/agents/agent_factory/builder.py` to accept a `config_doc_id` and read the current instruction from `config_cache.get_cached_config(doc_id)` per turn.
- Apply this at the root agent (`build_hierarchy` Step 10) so the root's instruction (including the "Available Specialists" block) live-reloads within 60 s of a Firestore write.
- Apply to each specialist's instruction too (each `build_agent(spec_config, ...)` call), so admin instruction edits on specialists also live-reload — even before Phase 2's runtime resolver lands.
- Decorate `config_cache.get_cached_config` with `@safe_weave_op(name="load_config_from_firestore")` so MER-E's eval contract is restored on every turn (this is the work that was attempted in the prior session and reverted as dead code; here it's wired to a live path).
- Add tests for the new cache wiring; verify the eval trace contains the span on cache hits.

**Deliverables:**
- PR landing the cache-wired instruction providers.
- A re-deploy to dev; smoke test in chat; confirm Weave trace shows the span on every turn.
- An MER-E rule update (if any) confirmed.

**Exit criteria:**
- An admin edit to `agent_configs/{config_id}.instruction` (or to any specialist's instruction) propagates to the next chat turn within ~60 s.
- The `load_config_from_firestore` span reappears on every turn in W&B Weave.

**Owner:** 1 engineer.
**Risk:** Low. The code shape is already understood. Touches one file (`builder.py`) plus the decorator on the cache.

### Phase 2 — Single-dispatch root + specialist runtime (1.5–2 weeks)

**Goal:** Replace the generated `dispatch_to_<specialist>()` tools with a single `delegate_to_specialist` and introduce the `specialist_runtime` module.

**Work:**
- New `app/adk/agents/agent_factory/specialist_runtime.py` with `resolve_config`, `resolve_agent`, `run`.
- New `app/adk/agents/agent_factory/dispatch.py` with `delegate_to_specialist(name, query, acceptance_criteria=None)`.
- Modify `build_hierarchy()` to build only the root (not specialists). Rename to `build_root()` (or keep the name for backward compatibility; deprecate the all-builds path).
- Move per-account overlay merge from `build_hierarchy`'s deploy-time loop to `specialist_runtime.resolve_config` at runtime, keyed by `account_id` from session state.
- Render the "Available Specialists" block per turn via `available_specialists_provider(account_id)`, called from the root's instruction provider (built on Phase 1's plumbing).
- The agent cache (`resolve_agent`) keyed by content hash so unchanged configs reuse one `LlmAgent`.
- Inner Runner wiring inside `delegate_to_specialist` to execute the specialist with the current session.
- Update Weave tracing: each dispatch emits `load_config_from_firestore` (already in Phase 1) plus a new `build_specialist_agent` span on cache miss.
- Update `_REDEPLOY_REQUIRED_FIELDS` to empty set in `api/src/kene_api/routers/agent_configs.py`; remove the "redeploy required" warnings.

**Deliverables:**
- PR (or PR series) landing the runtime resolver and the single-dispatch root.
- Updated unit tests; existing factory tests reshaped around runtime resolution.
- Updated documentation: AH-PRD-09 §5 finalized.

**Exit criteria:**
- An admin creating a new specialist Firestore doc sees it appear in the root's Available Specialists block within ~60 s, and can dispatch to it from the next chat turn.
- Admin edits to `model`, `temperature`, `max_output_tokens`, and `tools` on a specialist take effect within ~60 s.
- All AH-PRD-01 review-loop tests still pass.
- p95 dispatch latency on a warm cache ≤ 1.2× the current p95 (acceptable overhead).
- **Chat per-turn token accumulator parity test passes** — token aggregates under inner-Runner dispatch match the deploy-time baseline (CH-PRD-01 contract preserved; see §4.9). Merge blocker.
- **Billing token meter parity test passes** — per-org billing totals under inner-Runner dispatch match the deploy-time baseline (BL-PRD-02 contract preserved; same test fixture as Chat). Merge blocker.
- **`MergedAgentConfig.warnings`** marked `deprecated=true` in the OpenAPI schema; always returned empty.

**Owner:** 1–2 engineers.
**Risk:** Medium. ADK-internal — `Runner` semantics, callback wiring, and session-state flow need care. Cache invalidation correctness is the subtle bit.

### Phase 3 — `McpToolsetPool` + hybrid kinds (1.5–2 weeks)

**Goal:** Pool MCP connections so specialist rebuilds don't reopen them, and introduce `McpServerKind` with both `cloud_run` and `zapier` paths live.

**Work:**
- New `app/adk/agents/agent_factory/mcp_pool.py` — process-wide `McpToolsetPool` with kind-specific keying, TTL eviction, LRU cap, re-auth on failure.
- **Async cleanup on eviction.** Every eviction path (LRU, TTL, manual close) calls `McpToolset.aclose()` (or the equivalent async-context-manager `__aexit__`) before dropping the reference. ADK 1.27+ toolsets manage SSE sessions via async context managers; premature reference drops leak connections. A 60 s background sweep closes entries idle > 10 min in addition to per-access eviction.
- Extend `build_toolset_for_doc` in `mcp.py` with a `kind` branch:
  - `cloud_run`: existing path, now goes through the pool.
  - `zapier`: new path. Constructs an `McpToolset` pointed at Zapier's MCP endpoint, authenticated from `accounts/{account_id}/integrations/zapier`.
- Add `kind` field to `mcp_servers/{server_id}` schema (Pydantic + Firestore); migration script defaults existing docs to `cloud_run`.
- **Port AH-PRD-06 PR-C's `default_global` function-tool injection** into the runtime resolver — every runtime-resolved specialist must still receive `create_visualization` (and any future default-global tools) without per-specialist config edits. See §9.2 #9.
- Tests: pool correctness under concurrent access; eviction including async cleanup; re-auth; both kinds end to end; **1-hour sustained-load stress test that asserts no SSE connection leak**.

**Deliverables:**
- PR landing pool + Zapier kind.
- Migration script for `mcp_servers` schema.
- One Zapier-backed specialist live in dev as a demonstration (e.g., a "marketing operations" specialist using Zapier's HubSpot tools).

**Exit criteria:**
- Pool keeps p95 specialist cold-start ≤ 200 ms across kinds.
- **No SSE connection leak after a 1-hour sustained-load stress test** — specialists rebuilt > 1000 times across many `(account_id, server_id)` keys, MCP pool entries evicted, Cloud Run instance recycled — open SSE session count returns to baseline.
- **`default_global` function tools (`create_visualization`)** reach every runtime-resolved specialist without per-specialist config edits.
- The dev Zapier specialist functions end to end: admin creates the specialist, grants Zapier in the Integrations UI, chats with it, receives a meaningful response.
- No regression on existing GA MCP traffic.

**Owner:** 1 engineer (ideally one with MCP / ADK internals experience).
**Risk:** Medium-high. ADK's `McpToolset` lifecycle interacting with our pool is the trickiest piece. The Phase 0 spike de-risks part of it.

### Phase 4 — Zapier-backed Integrations component work (1–1.5 weeks, parallelizable with Phase 3)

**Goal:** Make Zapier a first-class integration alongside the existing per-platform OAuth flows.

**Work (Integrations component):**
- New `accounts/{account_id}/integrations/zapier` document and Firestore schema.
- Zapier OAuth / API-key flow (depends on Phase 0's auth probe outcome).
- `/settings/integrations` UI: "Connect Zapier" tile alongside the existing per-platform tiles. Once connected, deep-link into Zapier's workspace for managing individual integrations.
- Connection status surfaced on the Integrations status page; banner on Zapier outage.
- Documentation: `docs/design/components/integrations/README.md` updated with the Zapier section.

**Deliverables:**
- PR (Integrations team) landing the Zapier flow.
- End-to-end test: connect Zapier → create a Zapier-backed specialist → chat.

**Exit criteria:**
- An admin can connect Zapier in ≤ 1 minute (clicks: enable → grant → done).
- Disconnecting Zapier surfaces a clear UX state on any Zapier-kind specialists that depended on it.

**Owner:** 1 engineer (Integrations team).
**Risk:** Low-medium. Standard OAuth work shaped to Zapier's specifics.

### Phase 5 — Cleanup, observability, rollout (1 week)

**Goal:** Decommission the deploy-time factory's specialist build, finalize observability, ship behind a feature flag, cut over.

**Work:**
- Decommission unreachable legacy code paths.
- `generate_dispatch_functions` already deleted in AH-66 (see DESIGN-REVIEW-LOG Review 39); delete `_make_factory_instruction_provider`'s baked-text path (AH-68).
- Delete the legacy `create_ken_e_agent()` if no longer used (verify no callers outside the deprecated path).
- Update Cloud Trace / Weave dashboards: add panels for specialist cache hit rate, MCP pool size, Zapier latency p50/p95, dispatch error rate.
- Update docs and architecture diagrams per §5 above.
- DESIGN-REVIEW-LOG entry.

**Deliverables:**
- Feature-flag-driven rollout PR.
- Documentation PR (System Architecture + AH-PRD-02 supersession + AH-PRD-09 finalization + mcp-architecture.md + integrations README + DESIGN-REVIEW-LOG).
- Operations runbook for Zapier outage and per-account credential revocation.

**Exit criteria:**
- All documentation reflects the new architecture; `[PLANNED]` tags collapsed where work shipped.
- **MER-E eval suite passes against the new trace shape** — every prior eval set still scores correctly under `delegate_to_specialist` span structure. Verified in dev + staging before default-on; this is the **cutover gate** (see §9.1 MER-E coordination plan).
- **`MergedAgentConfig.warnings`** field scheduled for removal from the API contract one release after this rollout (does not block Phase 5).

**Owner:** 1 engineer (AH team) + writer review.
**Risk:** Low.

### 7.1 Total scope and sequencing

| Phase | Effort (eng-weeks) | Sequencing |
|---|---|---|
| 0. Zapier spike | 1–2 | Before everything. Hard gate. |
| 1. Cache-backed instruction | 1 | Independent of Phase 0. Can land in parallel with the spike. **Ships value immediately.** |
| 2. Single-dispatch + runtime resolver | 1.5–2 | After Phases 0 + 1. |
| 3. MCP pool + hybrid kinds | 1.5–2 | After Phase 2. Parallelizable with Phase 4. |
| 4. Integrations / Zapier UI | 1–1.5 | Parallelizable with Phase 3. |
| 5. Cleanup + rollout | 1 | After all of the above. |
| **Total** | **~7–10 eng-weeks** | **Calendar: 4–6 weeks with two engineers in parallel from Phase 2 onward.** |

### 7.2 Decision points

- **End of Phase 0:** go / no-go on Zapier. No-go pivots to `cloud_run`-only runtime resolver (Phases 1, 2, 3-narrowed, 5). Saves ~2 weeks; loses the long-tail product win.
- **Mid-Phase 2:** if cache invalidation correctness is harder than expected, fall back to TTL-only (drop hash invalidation as a v2 enhancement).
- **End of Phase 3:** if MCP pool stability is shaky under load, stress-test before rollout.

---

## 8. Why this is the right shape (not a refactor for its own sake)

Four threads converge on this proposal:

1. **The product requirement isn't deferrable.** Admin-created agents that aren't immediately available undermine the agent-builder UI's value proposition. We can either meet the requirement now (this RFC) or document that we can't (and adjust the product). The status quo silently breaks `instruction` edits, which is the worst of both.

2. **The factory was always going to need this.** Even without Zapier, the deploy-time-only model caps the rate at which we add specialists. Every new platform integration is a multi-week build. The runtime resolver is the architectural unlock that lets the agent-builder UI from AH-PRD-02 Phase 3 actually do what its UI promises.

3. **MCP is the bottleneck, and Zapier is a credible relief valve.** The N-dimensional MCP pool problem is real but mostly a long-tail problem. Concentrating the long tail behind one shared connection (Zapier) and keeping owned MCP for the flagships is the natural shape. We don't need to bet the whole product on Zapier — just the long tail.

4. **Sprint 6 Decision B's spirit deserves to be honored.** It exists in code, it's well-designed, it's well-tested, and it's currently dead. Phase 1 alone (cache-backed instruction) restores it and is a quick, high-value win even before Phases 2+ ship.

The cost is real — 7–10 eng-weeks — but it buys:
- Product-grade hot-reload for the agent-builder UI (the requirement).
- A 50–80% reduction in the engineering cost of adding new integration platforms (via Zapier).
- Restored MER-E eval coverage (load-config span on every turn).
- A clean architecture that the Skills, Project Tasks, and Knowledge Graph components build on cleanly — runtime specialist resolution is a better substrate for those components than a frozen tree.

---

## 9. Risks & open questions

### 9.1 Risks

- **Zapier vendor risk.** Concentrating the long tail behind Zapier creates a tier-1 dependency. Mitigation: the hybrid model keeps owned MCP available; if Zapier degrades, owned specialists are unaffected; if Zapier becomes unworkable, the `McpServerKind` enum can accommodate alternatives (Composio, Pipedream) without re-architecting.
- **Latency on cold starts.** First dispatch to a fresh specialist incurs build + MCP-pool cost. Mitigation: cache warming at root start, pool LRU sized for working set, observability so we catch outliers.
- **Cache-invalidation correctness.** A stale cached `LlmAgent` serving old behavior after a Firestore write is the failure we most want to avoid. Mitigation: content-hash invalidation in addition to TTL; integration tests covering "write then read" within the cache window.
- **ADK Runner internals.** Inner-Runner wiring inside `delegate_to_specialist` depends on ADK's session/context propagation. ADK is actively evolving. Mitigation: pin ADK version in Phases 2–3; document the Runner contract we depend on.
- **MER-E contract drift.** Trace shape changes (single `delegate_to_specialist` span instead of N `dispatch_to_*` spans; inner-Runner spans nested under the delegate span) require coordinated updates to the MER-E sister repo. **Concrete plan:**
  - **Owner pairing.** AH lead + MER-E lead identified by end of Phase 0 — named in the spike report alongside the Zapier go / no-go.
  - **Contract diff document.** Drafted at start of Phase 2 — enumerates span name changes, new attributes (`specialist_name`, `cache_hit`, `mcp_pool_hit`), retired attributes, and the new inner-Runner nesting shape.
  - **Dev verification.** MER-E extractors updated and tested against a staging trace fixture before Phase 2 merges to main.
  - **Cutover gate.** Phase 5 default-on is gated on the MER-E eval suite passing against the new trace shape (Phase 5 Exit criterion).
  - **Rollback.** If MER-E eval scores diverge unexpectedly after cutover, the contract diff is revisited before re-attempting.
- **Chat / Billing event-topology drift.** Inner-Runner dispatch produces a different event sequence than today's flat dispatchers. Two consumers — `SessionTurnAccumulator` (CH-PRD-01) and `extract_billable_tokens(event)` (BL-PRD-02) — depend on the event stream being complete and correctly attributed. Mitigation: Phase 2 parity tests against the deploy-time baseline; both are merge blockers for Phase 2 (see §4.9 and Phase 2 ACs).

### 9.2 Open questions for product / dev review

1. **Strategy supervisor scope — resolved.** The 8 strategy-pipeline specialists (`business_*`, `competitive_*`, `marketing_*`, `brand_*` researcher/formatter pairs) are **account-creation-only** — invoked exactly once via `create_strategy_docs_supervisor.py` during onboarding, never via the runtime chatbot. AH-PRD-07 (originally proposed to unify their construction) was **superseded by AH-PRD-08**, which hides them from the chat picker via `visible_in_frontend=False` instead. They continue to use the legacy `strategy_agent/config_loader.py` path unchanged. AH-PRD-09's runtime resolver does not apply to them and requires no coordination with this work. If a future "Refresh marketing strategy" UX ever makes them chat-callable, both AH-PRD-08 and the runtime-resolver scope need revisiting.
2. **Hash-based invalidation vs TTL.** TTL-only is simpler but admins waiting up to 60 s for a change to land feels worse than "instant on save." Worth the extra implementation cost? Recommendation: **TTL in v1**, hash invalidation as a fast-follow.
3. **Per-account specialist visibility on the root's Available Specialists block.** Today every account sees the same specialist set (plus their custom agents). Should the block be per-account-filtered at runtime (account A sees their custom agents only)? Recommendation: **yes, since the resolver already knows `account_id`** — it's a small addition and an obvious product feature.
4. **Zapier pricing model.** Need a real cost projection from finance based on expected chat volume per account. Recommendation: **part of Phase 0 deliverables**.
5. **Cutover strategy.** Big-bang behind a feature flag (current proposal), or gradual per-account migration? Recommendation: **feature-flag with explicit dev/QA accounts opted in for ~1 week, then default-on**.
   **Resolved (2026-05-28):** No production users; per-turn dispatch is the unconditional path. Feature flag dropped per AH-66 + PO decision.
6. **Should `LlmAgent`-instance cache be process-wide or per-session?** Process-wide is simpler and more efficient; per-session avoids any chance of cross-account state leaks. Recommendation: **process-wide, with account_id baked into the cache key** — the `LlmAgent` itself is stateless; session state lives in ADK's session, not on the agent.
7. **Read-only `is_system` specialists.** If we let admins edit specialist configs at runtime, do `is_system: true` (platform-seeded) specialists stay read-only? Recommendation: **yes, enforced by the CRUD API as today**.
8. **Skills sandbox lifecycle under per-turn specialist rebuild — Skills team alignment.** Today's SK-PRD-02 attaches a `SkillToolset` to a specialist at construction. Per-turn specialist rebuild implies per-turn `SkillToolset` reconstruction. Sandbox code-executor processes are heavyweight; respawning per turn would dominate latency. **Decision: option (a) — pool sandboxes by `(account_id, skill_id)`** in a `SandboxPool` abstraction analogous to `McpToolsetPool` (LRU + idle TTL + async cleanup on eviction; see §4.8 for the pattern). Pooling at the sandbox layer decouples sandbox lifecycle from `agent_cache` reuse, so a config edit that invalidates the cached `LlmAgent` does not force a sandbox cold-start — admins iterating on a specialist see no sandbox-respawn cost between edits. **Ownership: this is an SK-PRD-02 scope expansion** (a new pool abstraction inside the Skills component), not AH-PRD-09 work. **Coordination dependency:** SandboxPool must exist before AH-PRD-09's Phase 5 default-on, otherwise any specialist with attached skills would respawn its sandbox every turn under the new runtime. Skills team to amend SK-PRD-02 (or open SK-PRD-02a) ahead of Phase 5. Rejected alternative: **(b)** pin sandboxes to `LlmAgent` instances and ride `agent_cache` reuse — simpler but couples sandbox cold-start to every config edit, a noticeable UX regression when admins iterate.
9. **AH-PRD-06 PR-C interaction with the runtime resolver.** PR-C wires `default_global` function tools (currently `create_visualization`) through `hierarchy.py:325` at deploy time. With runtime resolution, the same injection must happen inside `specialist_runtime.resolve_agent`. Recommendation: **port the `default_global` injection into the runtime resolver as part of Phase 3**, so every runtime-resolved specialist still receives the default function tools. Schedule AH-PRD-06 PR-C to land before or alongside Phase 2 to avoid merge conflict.

### 9.3 What to validate explicitly in product review

- Is "≤ 60 s to propagate" (TTL-only v1) acceptable for the product requirement? Or does "immediate" mean "instant" (hash invalidation in v1)?
- Is Zapier acceptable as a named dependency in user-facing copy ("Connect Zapier to add 6,000+ integrations")? Or do we want to hide it as an implementation detail?
- For the cost model in Phase 0: what's the volume envelope per account at scale? Finance + product input needed before sizing the cost probe.

---

## 10. Appendix — code paths affected

| Path | Change |
|---|---|
| `app/adk/agents/agent_factory/hierarchy.py` | `build_hierarchy()` reduced to build the root only; specialist construction moves to `specialist_runtime`. |
| `app/adk/agents/agent_factory/builder.py` | `_make_factory_instruction_provider` wired to `config_cache` (Phase 1); kept as the LlmAgent construction primitive. |
| `app/adk/agents/agent_factory/mcp.py` | `build_toolset_for_doc` gains a `kind` branch (`cloud_run` / `zapier`). |
| `app/adk/agents/agent_factory/mcp_pool.py` | **New.** Process-wide `McpToolsetPool` with kind-specific keying. |
| `app/adk/agents/agent_factory/specialist_runtime.py` | **New.** `resolve_config`, `resolve_agent`, `run`, `available_specialists_provider`. |
| `app/adk/agents/agent_factory/dispatch.py` | **New.** `delegate_to_specialist`. Replaces generated per-specialist dispatchers. |
| `app/adk/agents/utils/config_cache.py` | Decorate `get_cached_config` with `@safe_weave_op(name="load_config_from_firestore")` (Phase 1). Extended for per-(name, account_id) keys (Phase 2). |
| `app/adk/agents/ken_e_agent.py` | `create_ken_e_agent` and `_make_instruction_provider` deleted in Phase 5 once verified unused. |
| `api/src/kene_api/routers/agent_configs.py` | `_REDEPLOY_REQUIRED_FIELDS` emptied. Warnings removed. |
| `api/src/kene_api/routers/integrations/zapier.py` | **New.** Zapier connect/disconnect endpoints (Phase 4). |
| `accounts/{account_id}/integrations/zapier` (Firestore) | **New** subcollection doc — stores Zapier credential. |
| `mcp_servers/{server_id}.kind` (Firestore) | **New** field. Migration defaults to `cloud_run`. |
| `frontend/src/pages/settings/integrations/*` | "Connect Zapier" tile + connection status (Phase 4). |
| `frontend/src/pages/workflows/agents/*` | Already exists from AH-PRD-02 Phase 3; verify the "changes effective immediately" UX copy lands. |
| `docs/KEN-E-System-Architecture.md` | §2, §4, §5 edits per §5 of this RFC. |
| `docs/design/components/agentic-harness/README.md` | §1, §2, §2.5 edits. |
| `docs/design/components/agentic-harness/mcp-architecture.md` | New §X Hybrid MCP Kinds. |
| `docs/design/components/agentic-harness/projects/AH-PRD-02-agent-factory.md` | Frontmatter supersession note. |
| `docs/design/components/agentic-harness/projects/AH-PRD-09-per-turn-dispatch.md` | **New** PRD; this RFC becomes its basis. |
| `docs/design/components/integrations/README.md` | New Zapier section. |
| `docs/design/DESIGN-REVIEW-LOG.md` | New Review entry. |
| `docs/spike-zapier-mcp-feasibility.md` | **New** spike report (Phase 0 deliverable). |

---

## 11. Document history

| Date | Author | Change |
|---|---|---|
| 2026-05-21 | Agentic Harness team | Initial draft. Status: Proposed, awaiting product + dev review. |
| 2026-05-22 | Agentic Harness team | v2 revision following review feedback. Added §4.2.1 (cache key shapes + per-key striped locking), §4.7 row on lock contention, §4.8 bullet on McpToolset async cleanup, new §4.9 (cross-component contracts preserved). Expanded §5.4 with Chat / Billing / Project Tasks / Skills doc edits. Updated §5.5 to mark `MergedAgentConfig.warnings` vestigial. Updated §6 AH-PRD-07 row with sequencing recommendation. Added Chat/Billing parity tests and MER-E eval gate to Phase 2 / 3 / 5 acceptance criteria. Expanded §9.1 MER-E risk into a concrete coordination plan and added a Chat / Billing event-topology risk. Added §9.2 #8 (Skills sandbox lifecycle) and #9 (AH-PRD-06 PR-C interaction). |
| 2026-05-22 | Agentic Harness team | v2.1 follow-up. **AH-PRD-07 confirmed superseded by AH-PRD-08**, not completed — the 8 strategy-pipeline specialists are account-creation-only (single onboarding invocation via `create_strategy_docs_supervisor.py`) and hidden from the chat picker. No AH-PRD-09 coordination required; legacy `strategy_agent/config_loader.py` path stays unchanged. Updated §6 AH-PRD-07 row, §9.2 #1, and §4.9 strategy-supervisor contract row. **Skills sandbox lifecycle decision: option (a)** — pool by `(account_id, skill_id)` in a new `SandboxPool` (SK-PRD-02 scope expansion); must land before Phase 5 default-on. Updated §9.2 #8 and §4.9 Skills contract row. |
