# ADK Upstream Bug Tracker

This document tracks open upstream bugs in `google/adk-python` that KEN-E depends on
for correctness or billing accuracy. Each row names the trigger condition that signals
downstream action is needed — check this doc monthly (see Monitoring section).

**Next-action owner:** SCRUM Master monthly sweep.

---

## Tracked Issues

| Issue URL | Title (summary) | Filed | ADK versions watched | Last checked | Trigger condition | Status |
|---|---|---|---|---|---|---|
| TBD — pending PO submission (**back-fill URL here and in `docs/spike-adk-mixed-turn-fc-drop.md` header once PO submits**) | Mixed-turn FC drop: regular-tool FR discarded when model emits regular FC + task FC in same turn → session poisoning | 2026-06-10 (draft ready) | 2.0.x → next minor | 2026-06-10 | Release notes mention `_llm_agent_wrapper` / mixed-turn handling; re-run repro in `docs/spike-adk-mixed-turn-fc-drop.md` to confirm fix, then file `AH-Nxx: Upgrade ADK to <version> + re-verify mixed-turn FC handling`. Recommendation: **keep** `repair_orphaned_function_calls_before_model` as a permanent safety net regardless of upstream fix (see `app/adk/agents/agent_factory/content_repair.py` + AH-164 DoD §3). | **Open — draft ready, awaiting PO submission** |
| [google/adk-python#3984](https://github.com/google/adk-python/issues/3984) | `AgentTool.run_async` discards all inner-stream events (inner `Runner` consumes them privately); `usage_metadata`, tool calls, model chunks all lost from outer stream | — (pre-existing) | 2.0.x / 2.1.x (confirmed OPEN — `AgentTool.run_async` private inner `Runner` still present in 2.0.0 and 2.1.0; see spike-adk2-supervisor-orchestration.md §Q1 + Q3) | 2026-06-01 (spike-adk2-supervisor-orchestration.md) | `AgentTool.run_async` emits inner events natively to the outer stream → re-evaluate `app/adk/agents/agent_tool_billing.py` (the `_BILLING_SINK` ContextVar bridge), and the `AgentTool` isolation established in AH-PRD-15. If fixed, `capture_agent_tool_usage` + `drain_turn_billing` may become redundant; assess before removing. | **Open — workaround in place (AH-PRD-15 isolation + billing bridge)** |

---

## Monitoring

### Mixed-turn FC drop (`repair_orphaned_function_calls_before_model`)

The WARNING logged by `content_repair.py` when the callback fires:

```
Cloud Logging filter (staging or prod):
  resource.type="aiplatform.googleapis.com/ReasoningEngine"
  AND jsonPayload.message:"Padded synthetic function responses"
```

Structured extras on each WARNING log entry:
- `padded_names` — list of regular-tool FC names that were orphaned
- `content_index` — position of the model turn in the outgoing request history

**Periodic-check cadence:** Monthly. On each check, note the frequency and update the
`Last checked` column above.

**Phase 3b trigger threshold:** > 1 % of supervisor-orchestrated turns over any rolling
7-day window in staging or prod. If the WARNING fires above this threshold despite the
`SUPERVISOR_INSTRUCTION_FRAGMENT` HARD RULE being in place, file
`AH-Nxy: Explore executing dropped regular FCs at wrapper boundary` (assessed as
fragile — requires reaching into ADK internals; the ticket is investigative, not
committed). The 1 % threshold can be tuned here if production telemetry shows a
different natural noise floor.

> **Note:** The log field names (`padded_names`, `content_index`) are the canonical
> locator — match `jsonPayload.padded_names` / `jsonPayload.content_index` in the
> `logger.warning(...)` call in `content_repair.py` (search for the message string
> `"Padded synthetic function responses"`). If those extras are ever renamed,
> update the filter above in the same PR.

### AgentTool inner-stream drop (#3984)

No active WARNING log for this — the `_BILLING_SINK` bridge is silent on normal
operation. Monitor via the billing pipeline: if leaf-agent tokens stop appearing in
the `TurnDelta` reported by `drain_turn_billing`, the isolation bridge may be broken.
The relevant test suite:
`app/adk/agents/tests/test_agent_tool_billing_integration.py::test_leaf_usage_propagates_through_agenttool_inner_runner`.
