# CLAUDE.md - ADK Agent System

This file provides guidance for working with the KEN-E ADK agent system. For general project guidelines and best practices, refer to the [root CLAUDE.md](../CLAUDE.md).

## Scope

ADK agent system — agent definitions, dispatch handlers, tools, callbacks, and MCP configuration. Deeper system-reference docs live in [`app/adk/README.md`](adk/README.md) and [`app/adk/DEPLOYMENT_GUIDE.md`](adk/DEPLOYMENT_GUIDE.md).

---

## Artifact handling

Every agent tool that saves an artifact **MUST** call:

```python
chat.artifacts.register_artifact(tool_context, filename, content, created_by_tool="<tool_name>")
```

implemented at `api/src/kene_api/chat/artifacts.py` (ships with CH-PRD-05).

**Never call raw `tool_context.save_artifact(...)` directly.** ADK saves the blob correctly, but it does not write the Firestore metadata row that the chat UI's `ArtifactsPanel` and the side-table `artifact_count` field both depend on. The wrapper saves both in one call.

When CH-PRD-05 ships, a CI lint rule at `api/scripts/lint/check_artifact_register.py` (wired into `make lint`) will scan for raw `.save_artifact(` calls and **fail the build** if any are found outside `api/src/kene_api/chat/artifacts.py` (the only entry in the allow-list).

See [Chat component README §7.5](../docs/design/components/chat/README.md#75-artifact-save-wrapper-contract) for the authoritative wrapper contract, and `CH-PRD-05` §5.2 for the wrapper body implementation.

> **Complementary convention:** `app/adk/agents/strategy_agent/ARTIFACT_CONVENTIONS.md` covers a separate concern — file-prefix naming for uploaded vs. generated strategy artifacts. That convention is unaffected by the register-artifact rule above.

---

## Billing / Chat / MER-E parity merge gates

These CI-resident tests guard the token-billing and event-propagation contracts for the supervisor-orchestration paths (AH-PRD-05). **All four must stay green before any AH-PRD-05 implementation PR merges to main.**

| Test | File | What it guards |
|---|---|---|
| `TestSupervisorTaskModeBillingParity` (AH-147 / AH-PRD-05 §7 AC-5, probe-1 port) | `app/adk/agents/agent_factory/tests/test_chat_billing_parity.py` | Per-task specialist tokens reach `SessionTurnAccumulator` and `extract_billable_tokens` identically to the `transfer_to_agent` baseline; `_TaskAgentTool` injection guard (silent-no-op trap). |
| `TestSupervisorFanOutEventBillingParity` (AH-147 / AH-PRD-05 §7 AC-2, probe-4 port) | `app/adk/agents/agent_factory/tests/test_chat_billing_parity.py` | Fan-out branches (`ctx.run_node` + `asyncio.gather`) each carry `usage_metadata` in the outer event stream; total billable == 2× CH-10 baseline. |
| `test_isolated_agent_tool_end_to_end_billing.py` (AH-147 / AH-PRD-05 §7 AC-3) | `app/adk/agents/tests/` | Full chat-callback pipeline: `chat_before_agent_callback` → isolated `AgentTool` leaf → `capture_agent_tool_usage` → `drain_turn_billing` → `_build_turn_delta` → leaf tokens in the final `TurnDelta` with no double-count. |
| `test_compound_fan_out_billing.py` (AH-147 / AH-PRD-05 §7 AC-4) | `app/adk/agents/tests/` | Compound fan-out: two parallel `ctx.run_node` branches each with an isolated `AgentTool` leaf accumulate leaf tokens **additively** in the `_BILLING_SINK` under a single outer `invocation_id` (no clobber across `asyncio.gather`-copied contexts). |

Earlier merge gates still in force (listed here for a single canonical view):

| Test | File | AH ticket |
|---|---|---|
| `TestChatParity` / `TestBillingParity` | `test_chat_billing_parity.py` | AH-110 / AH-PRD-09 |
| `TestAgentGoogleSearchTaskModeParity` | `test_chat_billing_parity.py` | AH-117 / AH-PRD-15 |
| `TestMultiTaskChatBillingParity` | `test_chat_billing_parity.py` | AH-129 / AH-PRD-14 |

Run all gates together:

```bash
cd app && uv run pytest \
  adk/agents/agent_factory/tests/test_chat_billing_parity.py \
  adk/agents/tests/test_isolated_agent_tool_end_to_end_billing.py \
  adk/agents/tests/test_compound_fan_out_billing.py \
  -v
```
