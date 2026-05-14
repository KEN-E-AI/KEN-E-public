# AH-PRD-07 — Unify Strategy-Agent Construction with the Agent Factory

**Status:** Proposed (skeleton — needs scoping pass before sprint planning)
**Owner team:** Core AI / Agent Platform (backend)
**Blocked by:** [AH-PRD-06](./AH-PRD-06-tool-mapping.md) PR-A (the `tool_ids` / `mcp_servers` contract this PRD's agents must honour)
**Parallel with:** Any other backend work that touches `app/adk/agents/strategy_agent/`
**Blocks:** Per-agent tool selection actually taking effect for `marketing_researcher`, `marketing_formatter`, and any future strategy-agent specialist; the natural completion of the AH-PRD-06 user-facing contract
**Estimated effort:** TBD — depends on how much of the `strategy_agent` orchestrator can be migrated vs. how much needs to stay on the SDK-direct path

---

## 1. Context

KEN-E has **two parallel agent-construction code paths** today:

1. **`app/adk/agents/agent_factory/` (AH-PRD-02 + AH-PRD-06 path).** `build_hierarchy` reads every doc from `agent_configs/`, merges in any per-account overlay, validates against the `MergedAgentConfig` model (which declares `mcp_servers` and `tool_ids`), and constructs each `LlmAgent` via `build_agent`. This is the canonical path the AH-PRD-06 tool picker writes through.
2. **`app/adk/agents/strategy_agent/config_loader.py` (legacy path).** `create_agent_from_firestore_config` reads the same Firestore docs but filters fields down to ADK's `LlmAgentConfig` allowed keys before validation (`config_loader.py:148-149`). `tool_ids` and `mcp_servers` aren't in that allow-list, so they're stripped. The resulting agent has no tools; callers then mutate `agent.tools = [...]` in `marketing_agents.py` to attach a hand-coded toolset (today: just `google_search_agent` wrapped in `AgentTool`).

Agents that flow through path #2 today: `marketing_researcher` and `marketing_formatter`, both invoked by `strategy_agent/orchestrator.py`. Any future specialist added under `strategy_agent/` inherits the same limitation.

This PRD bridges the gap so all specialists honour the AH-PRD-06 contract regardless of which subsystem invokes them, and so the tool picker's per-agent selections actually shape runtime behaviour for the strategy-agent specialists.

Surfaced during AH-PRD-06 implementation review — see AH-PRD-06 §2 "Known limitations after PR-A/B/C ship."

## 2. Scope

> _TBD — needs a scoping pass against the strategy-agent orchestrator before sprint planning. The two plausible shapes:_
>
> - **Option A — Replace.** Route `marketing_researcher` / `marketing_formatter` construction through `agent_factory.build_hierarchy`. Strategy orchestrator pulls the constructed agents from a shared registry instead of calling `create_marketing_researcher` directly. Smaller surface but requires `build_hierarchy` to handle agents that need post-construction mutations (e.g., `output_schema`, sub-agent wiring).
> - **Option B — Bridge.** Keep `strategy_agent/config_loader.py` as a thin shim, but teach it to honour `tool_ids` + `mcp_servers` by delegating tool resolution to `agent_factory.roster.resolve_specialist_roster` and toolset construction to `agent_factory.mcp.build_toolset_for_doc`. Larger code surface; preserves the orchestrator's current control flow.
>
> Option A is the cleaner long-term shape; Option B is the lower-risk first step. A small spike to confirm `build_hierarchy` can absorb the `output_schema` and `sub_agents` mutations the strategy_agent path performs would settle this.

### In scope (placeholder)

- Migrate `marketing_researcher` and `marketing_formatter` to honour the AH-PRD-06 `tool_ids` and `mcp_servers` contract.
- Preserve current production behaviour: `google_search_agent` continues to be available; the marketing-formatter output schema continues to be enforced.
- Update or replace `strategy_agent/config_loader.py` so any future specialist added there inherits the contract automatically.
- Migration story for existing production agent docs: do their stored `mcp_servers` / `tool_ids` need backfilling so they don't end up with zero tools post-migration?

### Out of scope (placeholder)

- The strategy-agent **orchestrator** itself (`orchestrator.py`'s multi-step flow control) — this PRD is about agent construction, not orchestration.
- New tools for `marketing_researcher` (e.g., GA, Ads). Adding those is what the picker is for; this PRD just makes the picker's selections take effect.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[AH-PRD-06](./AH-PRD-06-tool-mapping.md)** | The `tool_ids` / `mcp_servers` contract this PRD's agents must read and honour. AH-PRD-06's PR-A defined the contract; PR-C wired default function tools through the factory; this PRD extends both to strategy-agent specialists. | `./AH-PRD-06-tool-mapping.md` |
| **[AH-PRD-02](./AH-PRD-02-agent-factory.md)** | `agent_factory.build_hierarchy` / `build_agent` / `resolve_specialist_roster` — the construction primitives this PRD reuses (or replaces the strategy-agent loader with). | `./AH-PRD-02-agent-factory.md` |
| **[AH-PRD-04](./AH-PRD-04-data-visualization.md)** | `create_visualization()` is a default-global function tool. Once strategy-agent specialists go through the factory, they inherit it — relevant for marketing-research outputs that should include charts. Soft dependency: AH-PRD-04 reaches strategy-agent specialists for free, no extra wiring. | `./AH-PRD-04-data-visualization.md` |
| Existing `strategy_agent/marketing_agents.py` | Hand-wired tool attachments (`agent.tools = [AgentTool(...)]`) need to move into the factory path or be expressed as Firestore-doc fields the factory consumes. | `app/adk/agents/strategy_agent/marketing_agents.py` |

## 4. Data contract

No new Firestore fields are expected. The strategy-agent agent docs already carry `mcp_servers` and (post-AH-PRD-06) `tool_ids`; this PRD makes them load-bearing for the strategy-agent path.

> _TBD — confirm by reading the current Firestore docs for `marketing_researcher` / `marketing_formatter` and listing what each currently carries vs. what the factory needs._

## 5. Implementation outline

> _TBD — depends on Option A vs Option B in §2. Rough sketch for Option B (the lower-risk first step):_
>
> 1. Extract tool resolution from `strategy_agent/config_loader.py` into a helper that calls `agent_factory.roster.resolve_specialist_roster`. Inputs: the full Firestore doc (not the `LlmAgentConfig`-filtered subset). Outputs: the same list of `BaseTool` instances the factory produces.
> 2. After `Agent.from_config()` returns in `create_agent_from_firestore_config`, set `agent.tools = factory_tools + caller_supplied_tools` (e.g., `google_search_agent`). Hand-wired callers continue to work; selection-driven tools layer on top.
> 3. Decide what "caller-supplied tools" means long-term. Either keep them as a per-call kwarg (Option B) or migrate the orchestrator to express them as Firestore-doc fields (toward Option A).
> 4. Update tests to verify the strategy-agent path now respects a non-null `tool_ids` and a non-empty `mcp_servers`.

## 6. API contract

No new API endpoints. AH-PRD-06 already exposes the contract (`GET /api/v1/accounts/{account_id}/tools`, plus `tool_ids` on the agent-config CRUD endpoints). This PRD changes *what happens server-side when those tools are saved*, not the wire shape.

## 7. Acceptance criteria

> _TBD — first pass:_
>
> 1. **Strategy-agent specialists honour `tool_ids`.** Given a `marketing_researcher` doc with `tool_ids = ["function.create_visualization"]`, the constructed agent's `tools` list contains exactly that tool (plus any hand-wired survivors, see AC #3).
> 2. **Strategy-agent specialists honour `mcp_servers`.** Given a `marketing_researcher` doc with `mcp_servers = ["google_analytics_mcp"]` and `tool_ids = None`, the constructed agent has every catalogued GA tool wired (matching the factory path's behaviour exactly).
> 3. **Pre-PRD hand-wired tools continue to work.** `google_search_agent` is still attached to `marketing_researcher` after migration. The exact mechanism (Firestore-doc field vs. kwarg) is a §5 implementation detail; the user-visible behaviour is preserved.
> 4. **Picker UI round-trip.** Saving `tool_ids` for `marketing_researcher` through the `/workflows/agents` picker (post-AH-PRD-06) actually changes the tool list of the agent that handles the next request.
> 5. **AH-PRD-04 inheritance.** `marketing_researcher` and `marketing_formatter` constructed via the unified path inherit `create_visualization` automatically (per AH-PRD-06 §4 default-roster semantics).
> 6. **No regression on the orchestrator.** The marketing-research → marketing-formatter handoff produces the same `MarketingResearchReport` output before and after the migration.

## 8. Test plan

> _TBD — outline:_
>
> - Unit: factory-path tool resolution helper, given a strategy-agent Firestore doc, returns the expected tool list for representative `tool_ids` / `mcp_servers` shapes.
> - Integration: construct `marketing_researcher` and `marketing_formatter` via the unified path against a seeded Firestore; assert `agent.tools` matches expectations for null / empty / set `tool_ids`.
> - E2E: existing marketing-research orchestrator tests in `strategy_agent/tests/` continue to pass.
> - Regression: drive an end-to-end marketing-research query through the deployed agent and verify the output schema is unchanged.

## 9. Risks & open questions

> _TBD — first pass:_
>
> | Risk | Mitigation |
> |---|---|
> | `Agent.from_config()` (ADK SDK) rejects unknown fields under `extra='forbid'`, which is why `strategy_agent/config_loader.py` strips fields today. | The factory path doesn't use `Agent.from_config` — it builds via `build_agent` and constructs `LlmAgent` directly. The migration is to drop `from_config` for these agents, not to teach it new fields. |
> | Post-construction mutations the strategy-agent path performs (`agent.output_schema = ...`, `agent.tools = [...]`) may not all have equivalents in `build_agent`. | A spike to enumerate every mutation and map it to factory equivalents is the first concrete step before sprint planning. |
> | Stored production docs for `marketing_researcher` / `marketing_formatter` may have empty `mcp_servers` / `tool_ids` because the old loader never read them — naive migration could land them with zero tools. | Pre-migration backfill: write each agent's current hand-coded tool set into its Firestore doc as `tool_ids` / `mcp_servers` so the unified path reproduces today's behaviour exactly. |
>
> **Open questions:**
>
> - Which option in §2 (Replace vs. Bridge) does the team prefer? Answer drives PR sequencing and risk profile.
> - Are there other call sites that bypass `agent_factory.build_hierarchy` (beyond `strategy_agent`)? A grep audit before sprint planning would catch any siblings that need the same treatment.
> - Does the `orchestrator.py` `agent_metadata_cache` (referenced in the grep for `marketing_researcher`) assume the legacy construction path's metadata shape? May need updating in parallel.

## 10. Reference

- Upstream: [AH-PRD-06 §2 Known limitations](./AH-PRD-06-tool-mapping.md#known-limitations-after-pr-abc-ship)
- Affected code:
  - `app/adk/agents/strategy_agent/config_loader.py` — the field-stripping loader
  - `app/adk/agents/strategy_agent/marketing_agents.py` — hand-wired tool attachments
  - `app/adk/agents/strategy_agent/orchestrator.py` — caller of the construction helpers
  - `app/adk/agents/agent_factory/hierarchy.py` / `builder.py` / `roster.py` — the factory primitives this PRD reuses
- Architecture: `docs/KEN-E-System-Architecture.md` §2.5 (Tool-assignment & routing model)
