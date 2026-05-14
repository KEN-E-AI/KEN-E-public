# AH-PRD-08 — Hide Strategy-Pipeline Specialists from the Workflows Picker

**Status:** Proposed
**Owner team:** Core AI / Agent Platform (backend)
**Blocked by:** [AH-PRD-06](./AH-PRD-06-tool-mapping.md) (the picker UI whose contract this PRD is closing)
**Parallel with:** —
**Blocks:** Closing the AH-PRD-06 §2 "Known limitations after PR-A/B/C ship" item for strategy-pipeline specialists
**Estimated effort:** 1 small PR, ≈ 0.5 day. Splits the existing `AUDIT_FIELDS_RESEARCHER` profile, flips the 4 strategy researchers to a new hidden profile, and ships a one-off backfill script.

**Supersedes:** [AH-PRD-07](./AH-PRD-07-unify-strategy-agent-construction.md) (Unify Strategy-Agent Construction with the Agent Factory). The original migration plan has been replaced by hiding these agents from the picker so the AH-PRD-06 UX contract is no longer made for them in the first place. See §1 for the rationale.

---

## 1. Context

AH-PRD-06 shipped per-agent tool mapping end-to-end: the `/workflows/agents` picker writes `tool_ids` to each agent's Firestore doc, and the agent factory honours that selection at construction time. **One gap remained:** eight strategy-pipeline specialists — `business_researcher` / `business_formatter`, `competitive_researcher` / `competitive_formatter`, `marketing_researcher` / `marketing_formatter`, `brand_researcher` / `brand_formatter` — are constructed through a separate legacy loader (`app/adk/agents/strategy_agent/config_loader.py:create_agent_from_firestore_config`) that filters the Firestore doc down to ADK's `LlmAgentConfig` allowed keys before validation, **silently stripping `tool_ids` and `mcp_servers`**. The picker UI persists a tool selection for these agents but the selection has no runtime effect.

AH-PRD-07 originally proposed to bridge this gap by migrating the legacy loader onto the factory path. After a scoping spike, that approach was rejected in favour of a smaller, safer plan grounded in two findings:

1. **These 8 specialists are account-creation-only.** `dispatch_to_strategy` (`app/adk/agents/utils/dispatch_handlers.py:273`) has exactly one non-test caller: `create_strategy_docs_supervisor.py`, whose own instruction line and docstring both state *"ONLY invoked during account creation. You do not handle chat interactions."* It is deployed as a separate Agent Engine app, distinct from the runtime chatbot. Once these agents have done their one job (seeding the knowledge graph + strategy documents during onboarding), they are never re-invoked. Any user-driven tool reconfiguration is therefore strictly cosmetic — even after a hypothetical AH-PRD-07 migration.
2. **The `visible_in_frontend` flag already exists and is wired end-to-end.** `AgentConfig.visible_in_frontend: bool = True` (`api/src/kene_api/models/agent_config_models.py:371`), the backend supports `?visible_in_frontend=true` filtering (`routers/agent_configs.py:771-816`), and the frontend picker already passes that filter on every fetch (`frontend/src/lib/api/agentConfigs.ts:141`). The 4 strategy *formatters* are already hidden today via `AUDIT_FIELDS_FORMATTER` in `app/adk/agents/scripts/_seed_helpers.py:71-80`. Only the 4 *researchers* are currently visible-but-broken; they share `AUDIT_FIELDS_RESEARCHER` (line 54) with the user-facing chatbot / news / GA agents.

Hiding the researchers (to match the formatters) collapses the AH-PRD-07 migration from a multi-PR factory rework with backfill risks into **one profile split + a one-off Firestore backfill of a single boolean**. The user-visible outcome is identical to AH-PRD-07's: picker changes for these agents do not silently lie. The difference is in how that honesty is enforced — by removing the surface rather than by making the surface actually drive runtime behaviour.

## 2. Scope

### In scope

- Split `AUDIT_FIELDS_RESEARCHER` in `app/adk/agents/scripts/_seed_helpers.py` into two profiles:
  - `AUDIT_FIELDS_USER_FACING_RESEARCHER` — unchanged contents (`visible_in_frontend=True`, `available_to_copy=True`). Used by the chatbot, news agent, GA agent, and any future user-facing specialist.
  - `AUDIT_FIELDS_STRATEGY_PIPELINE_RESEARCHER` — new profile (`visible_in_frontend=False`, `available_to_copy=False`, otherwise identical to the user-facing profile). Used exclusively by the 4 strategy-pipeline researchers.
- Update the 4 strategy researcher seed entries (`business_researcher`, `competitive_researcher`, `marketing_researcher`, `brand_researcher` in `app/adk/agents/strategy_agent/scripts/upload_baseline_configs.py` and any equivalent migrate scripts) to reference the new profile.
- Ship a one-off backfill migration (`api/scripts/migrate_strategy_pipeline_visibility.py` or extend `api/scripts/migrate_agent_config_flags.py`) that updates `agent_configs/{business_researcher,competitive_researcher,marketing_researcher,brand_researcher}` in dev / staging / prod Firestore with `visible_in_frontend=False` and `available_to_copy=False`. The 4 formatter docs already carry the correct values and are out of scope for the backfill.
- Update [AH-PRD-06 §2](./AH-PRD-06-tool-mapping.md) "Known limitations after PR-A/B/C ship" — replace the AH-PRD-07-pointing language with a "Resolved by AH-PRD-08" pointer.
- Mark [AH-PRD-07](./AH-PRD-07-unify-strategy-agent-construction.md) as Superseded with a header pointing here. Keep the skeleton in place as a record of the analysed alternative in case the design constraint (strategy specialists are not user-callable at runtime) changes later.
- Update [PROJECT-PLANNER.md](../../PROJECT-PLANNER.md) — replace the AH-PRD-07 row with the AH-PRD-08 row in R1 Foundation.

### Out of scope

- **Migrating any strategy-pipeline specialist onto the factory path.** Deferred indefinitely. Re-open via a new PRD if these agents ever become user-callable at runtime (e.g. a future "Refresh marketing strategy" UX flow).
- **Deleting `strategy_agent/config_loader.py` or `marketing_agents.py`.** Both stay; their behaviour is unchanged. The strategy supervisor continues to call them at account creation, and they continue to construct agents via `Agent.from_config()` + post-construction `agent.tools = [...]` / `agent.output_schema = ...` mutations.
- **AH-PRD-04 `create_visualization` inheritance for strategy specialists.** Since these agents emit structured JSON for knowledge-graph ingestion (not user-facing prose), the missed inheritance is acceptable. If a future requirement adds chart output to strategy results, that follow-up will need to address tool wiring then.
- **Documenting the legacy loader as deprecated.** Light touch only — a comment in `config_loader.py` pointing readers to AH-PRD-08 for context. Promoting the loader to a formal deprecation cycle is out of scope; future strategy-pipeline additions are expected to be rare.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[AH-PRD-06](./AH-PRD-06-tool-mapping.md)** | The picker UI whose `visible_in_frontend=true` filter is the mechanism this PRD relies on. Already shipped — this PRD is purely the closing seam. | `./AH-PRD-06-tool-mapping.md` §2 Known limitations |
| Existing `AUDIT_FIELDS_FORMATTER` profile | `app/adk/agents/scripts/_seed_helpers.py:71-80`. The new `AUDIT_FIELDS_STRATEGY_PIPELINE_RESEARCHER` mirrors its `visible_in_frontend=False` + `available_to_copy=False` discipline. | This component |
| Existing `migrate_agent_config_flags.py` | `api/scripts/migrate_agent_config_flags.py`. Sets the 8 audit flags (including `visible_in_frontend`) on existing agent docs. The new backfill follows the same pattern. | `api/scripts/migrate_agent_config_flags.py` |

## 4. Data contract

No new Firestore fields. This PRD changes the value of `visible_in_frontend` and `available_to_copy` on exactly four existing documents (`business_researcher`, `competitive_researcher`, `marketing_researcher`, `brand_researcher`) and adds a new seed profile constant in source.

| Doc | Before | After |
|-----|--------|-------|
| `agent_configs/business_researcher` | `visible_in_frontend=True, available_to_copy=True` | `visible_in_frontend=False, available_to_copy=False` |
| `agent_configs/competitive_researcher` | `visible_in_frontend=True, available_to_copy=True` | `visible_in_frontend=False, available_to_copy=False` |
| `agent_configs/marketing_researcher` | `visible_in_frontend=True, available_to_copy=True` | `visible_in_frontend=False, available_to_copy=False` |
| `agent_configs/brand_researcher` | `visible_in_frontend=True, available_to_copy=True` | `visible_in_frontend=False, available_to_copy=False` |

The 4 formatter docs already carry the target values (`visible_in_frontend=False, available_to_copy=False`) via `AUDIT_FIELDS_FORMATTER` and are not touched.

## 5. Implementation outline

### 5.1 File inventory

| File | Change |
|------|--------|
| `app/adk/agents/scripts/_seed_helpers.py` | Rename `AUDIT_FIELDS_RESEARCHER` → `AUDIT_FIELDS_USER_FACING_RESEARCHER` (keep the old name as a deprecation alias for one release). Add new `AUDIT_FIELDS_STRATEGY_PIPELINE_RESEARCHER` constant with `visible_in_frontend=False` + `available_to_copy=False`. Update module docstring. |
| `app/adk/agents/strategy_agent/scripts/upload_baseline_configs.py` | Switch the 4 researcher seed entries from `AUDIT_FIELDS_RESEARCHER` to `AUDIT_FIELDS_STRATEGY_PIPELINE_RESEARCHER`. |
| `app/adk/agents/scripts/tests/test_seed_helpers.py` | Add tests for the new profile. Update existing researcher assertions to use the renamed constant. |
| `app/adk/agents/strategy_agent/scripts/tests/test_upload_baseline_configs.py` | Assert the 4 researcher seeds now write `visible_in_frontend=False, available_to_copy=False`. |
| `api/scripts/migrate_strategy_pipeline_visibility.py` *(new)* OR extension of `api/scripts/migrate_agent_config_flags.py` | One-off backfill: update the 4 researcher docs in dev / staging / prod with the new flag values. Dry-run-by-default following the existing migration-script convention. |
| `app/adk/agents/strategy_agent/config_loader.py` | Add a short module-level comment near the field-stripping logic (`line ~148-149`) pointing readers to AH-PRD-08 for the rationale: "Specialists loaded via this path are intentionally not user-configurable; see AH-PRD-08." |
| `docs/design/components/agentic-harness/projects/AH-PRD-06-tool-mapping.md` | §2 "Known limitations" — replace AH-PRD-07-pointing language with an AH-PRD-08-pointing resolution. |
| `docs/design/components/agentic-harness/projects/AH-PRD-07-unify-strategy-agent-construction.md` | Add `**Status:** Superseded by [AH-PRD-08](./AH-PRD-08-hide-strategy-pipeline-specialists.md)` header + one-paragraph rationale at the top of §1. Skeleton kept as a record. |
| `docs/design/components/PROJECT-PLANNER.md` | Replace AH-PRD-07 row with the AH-PRD-08 row in R1 Foundation. |

### 5.2 Profile split

```python
# _seed_helpers.py — after the change

# Default profile for user-facing specialists (chatbot, news, GA, and any
# future runtime-callable researcher). Visible in the Workflows > Agents UI
# and forkable. The AH-PRD-06 tool picker honours selections for these
# agents because they're constructed via the agent factory.
AUDIT_FIELDS_USER_FACING_RESEARCHER: dict[str, Any] = {
    "code_execution_enabled": False,
    "mcp_servers": [],
    "skill_ids": [],
    "sandbox_code_executor_enabled": False,
    "response_schema": None,
    "available_to_copy": True,
    "automatically_available": True,
    "visible_in_frontend": True,
}

# Deprecation alias — remove in the next release after all callers migrate.
AUDIT_FIELDS_RESEARCHER = AUDIT_FIELDS_USER_FACING_RESEARCHER

# Profile for the 4 strategy-pipeline researchers (business / competitive /
# marketing / brand). Hidden from the Workflows > Agents UI and not
# forkable because:
#   1. They are only invoked during account creation, never at runtime
#      (see create_strategy_docs_supervisor.py).
#   2. They are constructed via strategy_agent/config_loader.py, which
#      strips tool_ids / mcp_servers before validation — picker changes
#      have no runtime effect.
# Hiding them at the seed layer means the picker contract isn't made
# for them in the first place. See AH-PRD-08.
AUDIT_FIELDS_STRATEGY_PIPELINE_RESEARCHER: dict[str, Any] = {
    "code_execution_enabled": False,
    "mcp_servers": [],
    "skill_ids": [],
    "sandbox_code_executor_enabled": False,
    "response_schema": None,
    "available_to_copy": False,
    "automatically_available": True,
    "visible_in_frontend": False,
}
```

### 5.3 Backfill script

A standalone migration following the `migrate_agent_config_flags.py` pattern: dry-run by default, requires `--project` for the target environment, idempotent (re-running is a no-op if values are already correct). The script writes only `visible_in_frontend=False` and `available_to_copy=False` on the 4 target docs and logs the before/after of each field. It does **not** touch the seed-script source of truth — the seed-script change in §5.2 is the durable contract for fresh environments; the backfill exists only to bring already-deployed Firestore data in line.

## 6. API contract

No new API endpoints. The existing `GET /api/v1/accounts/{account_id}/agent-configs/?visible_in_frontend=true` filter (`routers/agent_configs.py:771`) already excludes hidden agents from the picker fetch. This PRD changes which agents qualify as "hidden," not how the filter works.

## 7. Acceptance criteria

1. **`AUDIT_FIELDS_STRATEGY_PIPELINE_RESEARCHER` exists** and carries the values shown in §5.2. `AUDIT_FIELDS_RESEARCHER` continues to import / export the user-facing profile for at least one release as a deprecation alias.
2. **The 4 strategy researcher seed scripts use the new profile.** Running `upload_baseline_configs.py` against a fresh Firestore writes `visible_in_frontend=False, available_to_copy=False` on `business_researcher`, `competitive_researcher`, `marketing_researcher`, `brand_researcher`.
3. **The backfill script flips the 4 existing docs.** Running `migrate_strategy_pipeline_visibility.py --project ken-e-dev` against a previously seeded Firestore updates the 4 researcher docs and is idempotent on re-run.
4. **The Workflows picker excludes the 4 researchers.** With the backfill applied, `GET /api/v1/accounts/{id}/agent-configs/?visible_in_frontend=true` returns no `business_researcher` / `competitive_researcher` / `marketing_researcher` / `brand_researcher` entries.
5. **The 4 formatter docs are unchanged.** No visible regression in the formatter behaviour — they were already hidden.
6. **Account-creation strategy generation is unchanged.** End-to-end account-creation smoke test passes; the strategy supervisor still produces the 5 strategy documents.
7. **AH-PRD-06 §2 "Known limitations" no longer points at AH-PRD-07.** The replacement language references AH-PRD-08 and notes the resolution mechanism (visibility hiding).
8. **AH-PRD-07 carries `Status: Superseded`.** The skeleton remains in place; the supersession is one paragraph at the top of §1.
9. **PROJECT-PLANNER.md R1 Foundation lists AH-PRD-08, not AH-PRD-07.**

## 8. Test plan

### Unit

- `test_seed_helpers.py`: assert `AUDIT_FIELDS_STRATEGY_PIPELINE_RESEARCHER["visible_in_frontend"] is False` and `["available_to_copy"] is False`. Assert the user-facing profile is unchanged.
- `test_seed_helpers.py`: assert `AUDIT_FIELDS_RESEARCHER` (deprecation alias) is identical to `AUDIT_FIELDS_USER_FACING_RESEARCHER`.

### Integration

- `test_upload_baseline_configs.py`: extend the existing per-doc tests to assert the 4 researcher seeds now write `visible_in_frontend=False` and `available_to_copy=False`.
- New `test_migrate_strategy_pipeline_visibility.py`: against a Firestore emulator pre-seeded with `visible_in_frontend=True` on the 4 docs, run the migration and assert the resulting field values + idempotent re-run.
- Existing `test_agent_configs_api.py:test_list_visible_in_frontend_filter` already validates the filter mechanism — no change needed.

### E2E / regression

- Account-creation smoke: run the existing end-to-end account-creation test (or stub harness) and verify the 5 strategy documents are still produced. The legacy loader continues to read these docs, so any unintended side effect of changing `visible_in_frontend` would surface here.
- Manual picker check (post-backfill): open `/workflows/agents` in a backfilled environment and confirm the 4 strategy researchers no longer appear in the agent list.

## 9. Risks & open questions

| Risk | Mitigation |
|---|---|
| **Backfill missed in an environment.** A deployed Firestore that wasn't backfilled keeps the 4 researchers visible-but-broken. | The backfill is idempotent and runs per environment. Add a one-line operational note to the runbook for environments coming online before the backfill. |
| **A future requirement re-exposes these agents to runtime user calls** (e.g., "Refresh my marketing strategy" UX). | At that point, both AH-PRD-07's original migration analysis and this PRD's hiding decision need revisiting. AH-PRD-07 is kept as a skeleton specifically for this scenario. |
| **A new strategy-pipeline specialist is added later via the legacy loader** and the author copies the wrong profile (`AUDIT_FIELDS_USER_FACING_RESEARCHER`). | The deprecation comment in `config_loader.py` (§5.1) flags the rationale. Profile names are explicit enough to make the right choice obvious; tests assert the strategy-pipeline researchers use the strategy-pipeline profile. |
| **`AUDIT_FIELDS_RESEARCHER` alias removed too eagerly.** Downstream seed scripts that haven't migrated would lose the import. | Keep the alias for at least one release; remove only after a follow-up grep confirms no remaining importers outside the strategy-pipeline scripts. |

**Open questions:**

- Is there a hidden runtime call site we missed (e.g. a Cloud Function that re-runs `dispatch_to_strategy` for "knowledge refresh")? Spike answered no for current main, but worth a follow-up grep on any future PR that touches `strategy_agent/`. The existence of the legacy loader stays defensible only as long as that answer holds.

## 10. Reference

- Supersedes: [AH-PRD-07 — Unify Strategy-Agent Construction with the Agent Factory](./AH-PRD-07-unify-strategy-agent-construction.md)
- Closes: [AH-PRD-06 §2 Known limitations](./AH-PRD-06-tool-mapping.md#known-limitations-after-pr-abc-ship)
- Affected code:
  - `app/adk/agents/scripts/_seed_helpers.py` — profile split
  - `app/adk/agents/strategy_agent/scripts/upload_baseline_configs.py` — seed switch
  - `app/adk/agents/strategy_agent/config_loader.py` — deprecation comment
  - `api/scripts/migrate_strategy_pipeline_visibility.py` — new backfill
- Architecture: `docs/KEN-E-System-Architecture.md` §2.5 (Tool-assignment & routing model)
