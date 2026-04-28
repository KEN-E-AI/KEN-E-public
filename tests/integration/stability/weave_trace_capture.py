"""In-memory Weave span capture for Sprint 6 trace-compliance validation.

**Approach:** monkey-patch
``weave.trace.context.call_context.push_call`` at fixture entry. KEN-E
creates parent spans via ``client.create_call(...)`` (see
``app/adk/tracking/callbacks.py``), which in turn pushes the resulting
``Call`` onto the weave call stack. Intercepting ``push_call`` gives us
every span (root + children) without touching the wandb HTTP exporter.

**Why this approach over the HTTP-exporter route:** weave is pinned
narrowly (``>=0.51.0,<0.51.57``) so monkey-patching internals is safe
for Sprint 6. Intercepting the exporter would require serialising the
graph and reasoning about flush timing — much more code, no realism gain
for the questions the harness is asking ("does each span carry the
required metadata?").

**Compatibility:** captured spans are flat dicts whose key set matches
the trace fixtures under ``app/adk/tracking/tests/fixtures/*.json`` —
every dict can be fed straight into
``app.adk.tracking.compliance.validate_trace_compliance``.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from types import TracebackType
from typing import Any


class TraceCapture:
    """Context manager that records every weave Call pushed onto the stack."""

    def __init__(self) -> None:
        self._traces: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._original_push: Callable[..., Any] | None = None
        self._call_context_module: Any = None

    def __enter__(self) -> TraceCapture:
        # Imported lazily so non-trace harness paths don't pay the weave
        # import cost or fail when weave is partially configured.
        from weave.trace.context import call_context

        self._call_context_module = call_context
        self._original_push = call_context.push_call

        def _patched_push_call(call: Any) -> Any:
            try:
                self._record(call)
            except Exception:
                # Capture must never break the workload — swallow extraction
                # failures and let the original push proceed.
                pass
            assert self._original_push is not None
            return self._original_push(call)

        call_context.push_call = _patched_push_call  # type: ignore[assignment]
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._original_push is not None and self._call_context_module is not None:
            self._call_context_module.push_call = self._original_push
        self._original_push = None
        self._call_context_module = None

    @property
    def traces(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._traces)

    def clear(self) -> None:
        with self._lock:
            self._traces.clear()

    def _record(self, call: Any) -> None:
        attrs = getattr(call, "attributes", None) or {}
        flat: dict[str, Any] = dict(attrs)
        # Provide trace identity hints alongside metadata so downstream
        # consumers can deduplicate or correlate without re-parsing the Call.
        for src, dst in (
            ("op_name", "_weave_op_name"),
            ("trace_id", "_weave_trace_id"),
            ("id", "_weave_call_id"),
        ):
            value = getattr(call, src, None)
            if value is not None:
                flat[dst] = value
        with self._lock:
            self._traces.append(flat)


def replay_through_compliance(captures: list[dict[str, Any]]) -> list[Any]:
    """Run each captured trace through ``validate_trace_compliance``.

    Returns a list of ``TraceComplianceResult`` instances — one per input
    capture. Strips the ``_weave_*`` identity hints before validating so
    they don't appear as spurious "unknown field" warnings.
    """
    from app.adk.tracking.compliance import validate_trace_compliance

    results = []
    for trace in captures:
        cleaned = {k: v for k, v in trace.items() if not k.startswith("_weave_")}
        results.append(validate_trace_compliance(cleaned))
    return results
