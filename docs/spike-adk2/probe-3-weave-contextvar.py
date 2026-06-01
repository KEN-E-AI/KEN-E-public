"""Probe Q3 — Does asyncio.run on a worker thread preserve Weave contextvar call-stack?

Run with (from repo root):
    .venv-adk2/bin/python docs/spike-adk2/probe-3-weave-contextvar.py

Findings:
    - Python's ThreadPoolExecutor.submit() does NOT propagate contextvars to
      worker threads by default (tested on Python 3.12.3, 3.13.x).
    - asyncio.run() starts a fresh event loop with no contextvar inheritance.
    - KEN-E's _build_specialist pool uses asyncio.run() in a worker thread for
      MCP pool checkout (timeout enforcement only, not agent execution).
    - Impact: Weave spans from MCP pool checkout (in the worker thread) will
      ORPHAN from the parent agent's Weave trace. This is an EXISTING issue
      on ADK 1.34.1 too (not introduced by 2.0).
    - ADK 2.0 agent execution happens in the main event loop (not worker threads),
      so the main Weave trace topology is UNAFFECTED.
    - Fix (if needed for MCP spans): pass `ctx.run(asyncio.run, coro)` pattern
      to propagate context into the worker thread.
"""

import asyncio
import concurrent.futures
import contextvars

print("=== Probe Q3: Weave contextvar propagation through asyncio.run on worker thread ===\n")

# Simulate Weave's contextvar behavior
weave_call_stack = contextvars.ContextVar("weave_call_stack", default=None)


async def check_contextvar_in_worker_async():
    """Async function run via asyncio.run() in a worker thread."""
    return weave_call_stack.get()


def worker_bare():
    """Worker thread using bare asyncio.run() — no context copy."""
    return asyncio.run(check_contextvar_in_worker_async())


def worker_with_ctx(ctx):
    """Worker thread using ctx.run() to propagate context."""
    return ctx.run(asyncio.run, check_contextvar_in_worker_async())


# Set the contextvar in main thread
weave_call_stack.set("parent_agent_span")

print("Main thread contextvar: 'parent_agent_span'")
print()

# Test bare asyncio.run in worker
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
    result_bare = ex.submit(worker_bare).result()
print(f"Worker (bare asyncio.run) saw: {result_bare!r}")
assert result_bare is None, f"Expected None (contextvar NOT propagated), got {result_bare!r}"
print("=> Contextvar NOT propagated (orphaned) ❌")

# Test with explicit ctx.run
ctx = contextvars.copy_context()
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
    result_ctx = ex.submit(worker_with_ctx, ctx).result()
print(f"\nWorker (ctx.run + asyncio.run) saw: {result_ctx!r}")
assert result_ctx == "parent_agent_span", f"Expected propagation, got {result_ctx!r}"
print("=> Contextvar propagated via ctx.run ✅")

print()
print("--- Scope Assessment ---")
print("KEN-E _build_specialist uses asyncio.run in get_pool_checkout_executor().submit(_runner)")
print("  -> MCP pool checkout spans ORPHAN from parent Weave trace (existing bug on 1.34.1 too)")
print("  -> Impact: limited to MCP toolset construction, NOT main agent LLM calls")
print("  -> Agent execution (LLM calls, tool dispatch) runs in the main event loop — NOT affected")
print("  -> Fix: wrap asyncio.run with ctx.run in _build_specialist (one-line change if needed)")
print()
print("ADK 2.0 change: NodeRunner events flow through ic._event_queue in the MAIN event loop,")
print("  so no worker-thread contextvar issue exists for sub-agent event propagation in 2.0.")

print("\n=== Q3 VERDICT ===")
print("asyncio.run on worker thread: Weave contextvars ORPHANED.")
print("Scope: MCP pool checkout only. Main agent LLM invocations unaffected (main event loop).")
print("This is an EXISTING issue on ADK 1.34.1 too — not a 2.0 regression.")
print("Fix available (ctx.run wrapper) if MCP checkout span fidelity is required.")
