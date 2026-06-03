"""Off-state stash for the per-tool Weave attributes context manager.

The before-tool hook (:mod:`app.adk.security.hooks`) opens
``weave.attributes(...)`` — a ``@contextmanager``, i.e. a generator-backed
object — and must keep it alive until the after-tool callback
(:mod:`app.adk.tracking.callbacks`) closes it. That context manager used to be
parked in ADK session ``state`` under ``_trace_attrs_ctx``, but
``AgentTool.run_async`` deep-copies the parent session state into every
agent-as-tool child session, and ``copy.deepcopy`` of a generator raises
``TypeError: cannot pickle 'generator' object`` — which broke every
agent-as-tool call (e.g. ``agent.google_search``).

Session state is meant to be serializable; a live context manager does not
belong there. This module holds those context managers off-state, keyed by the
identity of the per-call ``ToolContext``. ADK constructs one ``ToolContext``
per function call and reuses it across the before/tool/after sequence, so
``id(tool_context)`` is a stable per-call key. Keying per call (rather than the
old single shared-state slot) also fixes a latent bug when tools run in
parallel, where exiting one tool's context would otherwise close another's.

Entries are added by the before-tool hook and removed by the after-tool
callback's ``finally`` block. In ADK 1.27.5 ``after_tool`` fires on the tool's
success path, on the permission-block path (the before-tool callback returns a
deny response; ``after_tool`` runs unconditionally — ``functions.py:541``), and
on plugin-handled tool errors (e.g. ``ReflectAndRetryToolPlugin`` returns an
error response rather than re-raising), so the paired ``pop`` runs in all of
those. The only un-popped case is a tool exception that no ``on_tool_error``
plugin handles → ADK re-raises and skips ``after_tool``; the stranded entry is
then bounded by ``id()`` reuse (a later ``ToolContext`` reusing the id
overwrites it) rather than growing without limit.
"""

from __future__ import annotations

from typing import Any

_pending_trace_contexts: dict[int, Any] = {}


def stash_trace_context(tool_context: Any, attrs_ctx: Any) -> None:
    """Hold *attrs_ctx* alive for the duration of *tool_context*'s tool call."""
    _pending_trace_contexts[id(tool_context)] = attrs_ctx


def pop_trace_context(tool_context: Any) -> Any | None:
    """Remove and return the stashed context manager for *tool_context*, if any."""
    return _pending_trace_contexts.pop(id(tool_context), None)


def clear_trace_contexts() -> None:
    """Close and drop all stashed trace contexts. For test isolation only.

    Exits each stashed ``weave.attributes()`` CM (suppressing weave's
    cross-context ``reset(token)`` error) before emptying the stash. Exiting
    runs the generator's ``finally`` so it is exhausted and won't resurface as a
    ``PytestUnraisableExceptionWarning`` when garbage-collected later. Used by
    the autouse fixture in ``app/adk/conftest.py``.
    """
    for attrs_ctx in list(_pending_trace_contexts.values()):
        try:
            attrs_ctx.__exit__(None, None, None)
        except Exception:
            # Cross-context reset / already-closed CM — expected during teardown.
            pass
    _pending_trace_contexts.clear()
