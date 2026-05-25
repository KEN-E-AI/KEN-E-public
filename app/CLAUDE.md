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
