"""Weave tracing helpers for review-loop dispatch wrappers.

Provides three helpers consumed by dispatch_handlers.py and specialist
after_agent_callbacks after each review-pipeline run:

* ``emit_iteration_span`` — creates one Weave child span per review iteration,
  grouping the specialist and reviewer outputs together.
* ``set_pipeline_attrs`` — writes the four AH-PRD-01 §7 AC#9 pipeline-level
  attributes (acceptance_criteria, exit_reason, total_iterations,
  output_key_prefix) onto the surrounding dispatch span's summary dict via
  ``weave.get_current_call()``.
* ``set_specialist_span_attrs`` — writes six AH-35 specialist sub-agent span
  attributes (specialist_name, agent_kind, exit_reason, total_iterations,
  output_key_prefix, cache_hit) onto the specialist sub-agent span's summary
  dict via ``weave.get_current_call()``.  Called from an after_agent_callback.

Both helpers degrade to no-ops when the Weave SDK is not installed or is
uninitialized, mirroring the ``safe_weave_op`` pattern in weave_observability.py.
All Weave-touching paths are wrapped in try/except so a Weave outage never
propagates to the caller.

AH-8 (defensive observability) will add a sibling ``emit_hallucinated_approval_span``
helper to this module.
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import weave as _weave

    WEAVE_AVAILABLE = True
except ImportError:
    _weave = None  # type: ignore[assignment]
    WEAVE_AVAILABLE = False

logger = logging.getLogger(__name__)

# Maximum bytes for specialist/reviewer output captured in a synthesized span.
# Tighter than the 100 KB cap in callbacks.py because iteration spans are
# emitted at max_iterations x dispatch_count density.
_MAX_OUTPUT_BYTES = 4096


def _truncate_output(text: str) -> Any:
    """Truncate ``text`` to ``_MAX_OUTPUT_BYTES`` bytes and return a summary dict
    when truncation occurs; return the original string when it fits.

    Matches the shape used by ``truncate_large_output()`` in adk_callbacks so
    MER-E consumers see a consistent sentinel format.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= _MAX_OUTPUT_BYTES:
        return text
    preview = encoded[:_MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
    return {
        "_truncated": True,
        "size_bytes": len(encoded),
        "preview": preview,
    }


def emit_iteration_span(
    iteration: int,
    specialist_output: str,
    reviewer_output: str,
) -> None:
    """Emit a synthetic Weave child span for one review-loop iteration.

    Must be called from inside a function already wrapped by ``@safe_weave_op``
    (the dispatch handler) so that Weave's call-stack context is active.  The
    ``@_weave.op`` decorator on the inner helper creates a child span under the
    current dispatch call.

    When ``WEAVE_AVAILABLE`` is False or Weave is not initialized, this is a
    no-op.  All exceptions are caught and logged at DEBUG level so a tracing
    failure never breaks a dispatch.

    Args:
        iteration: 1-based iteration index.
        specialist_output: Draft text (or structured output) written by the
            specialist worker in this iteration.  Truncated to
            ``_MAX_OUTPUT_BYTES`` bytes before being written to the span summary.
        reviewer_output: Feedback written by the reviewer in this iteration.
            Empty string on the approval turn.  Truncated similarly.
    """
    if not WEAVE_AVAILABLE or _weave is None:
        return
    try:
        _emit_iteration_span_inner(iteration, specialist_output, reviewer_output)
    except Exception as exc:
        logger.warning(
            "emit_iteration_span: Weave child span failed — tracing data lost: %s", exc
        )


if WEAVE_AVAILABLE and _weave is not None:

    @_weave.op(name="review_loop_iteration")
    def _emit_iteration_span_inner(
        iteration: int,
        specialist_output: str,
        reviewer_output: str,
    ) -> None:
        try:
            call = _weave.get_current_call()
            if call and hasattr(call, "summary"):
                call.summary["iteration"] = iteration
                call.summary["specialist_output"] = _truncate_output(specialist_output)
                call.summary["reviewer_output"] = _truncate_output(reviewer_output)
        except Exception as exc:
            logger.warning(
                "_emit_iteration_span_inner: summary write failed — tracing data lost: %s",
                exc,
            )
else:

    def _emit_iteration_span_inner(  # type: ignore[misc]
        iteration: int,
        specialist_output: str,
        reviewer_output: str,
    ) -> None:
        pass


def set_pipeline_attrs(
    criteria: str,
    final_state: dict[str, Any],
    prefix: str,
    total_iterations: int,
) -> None:
    """Write AH-PRD-01 §7 AC#9 pipeline-level attributes onto the surrounding
    dispatch span's summary via ``weave.get_current_call()``.

    Must be called from inside a ``@safe_weave_op``-decorated dispatch function
    so that the call is the dispatch span, not a sub-span.

    ``exit_reason`` is computed from the §5.2 idiom:
    ``final_state[f"{prefix}_feedback"] == ""`` → ``"approved"``; non-empty →
    ``"max_iterations"``.

    When ``WEAVE_AVAILABLE`` is False or Weave is not initialized, this is a
    no-op.  All exceptions are caught and logged at DEBUG level.

    Args:
        criteria: The acceptance_criteria string passed to the dispatch handler.
        final_state: The final session state dict returned by
            ``invoke_pipeline()``.
        prefix: The ``output_key_prefix`` used for the review pipeline.
        total_iterations: Total number of complete review iterations
            (specialist-final + reviewer-final pairs).
    """
    if not WEAVE_AVAILABLE or _weave is None:
        return
    try:
        feedback = final_state.get(f"{prefix}_feedback", "")
        exit_reason = "approved" if feedback == "" else "max_iterations"

        call = _weave.get_current_call()
        if call and hasattr(call, "summary"):
            call.summary["acceptance_criteria"] = criteria
            call.summary["exit_reason"] = exit_reason
            call.summary["total_iterations"] = total_iterations
            call.summary["output_key_prefix"] = prefix
    except Exception as exc:
        logger.warning(
            "set_pipeline_attrs: summary write failed — tracing data lost: %s", exc
        )


def set_specialist_span_attrs(
    specialist_name: str,
    criteria: str,
    final_state: dict[str, Any],
    prefix: str,
    total_iterations: int,
    cache_hit: bool,
    agent_kind: str = "loop_pipeline",
) -> None:
    """Write AH-35 specialist sub-agent span attributes onto the current Weave
    call's summary dict via ``weave.get_current_call()``.

    Intended to be called from an ``after_agent_callback`` attached to the
    specialist sub-agent so that ``weave.get_current_call()`` resolves to the
    specialist's own span, not the surrounding dispatch span.

    The review-loop attributes ``exit_reason``, ``total_iterations`` and
    ``output_key_prefix`` are written ONLY for ``agent_kind == "loop_pipeline"``
    — a single-pass specialist runs no reviewer, so an ``exit_reason`` would be
    meaningless (it would always read ``"approved"`` off an empty ``prefix``).
    ``specialist_name``, ``agent_kind`` and ``cache_hit`` are written for every
    kind.

    ``exit_reason`` is computed from the §5.2 idiom (same as
    ``set_pipeline_attrs``):
    ``final_state[f"{prefix}_feedback"] == ""`` → ``"approved"``; non-empty →
    ``"max_iterations"``.

    Valid ``agent_kind`` values:
    - ``"loop_pipeline"`` — specialist runs inside a review loop (default).
    - ``"single_pass"`` — specialist runs without a reviewer (single pass).

    When ``WEAVE_AVAILABLE`` is False or Weave is not initialized, this is a
    no-op.  All exceptions are caught and logged at WARNING level so a Weave
    outage never propagates to the caller.

    Args:
        specialist_name: The name of the specialist agent (e.g.
            ``"news_specialist"``).
        criteria: The acceptance_criteria string passed to the dispatch handler.
        final_state: The final session state dict returned by
            ``invoke_pipeline()``.
        prefix: The ``output_key_prefix`` used for the review pipeline.
        total_iterations: Total number of complete review iterations.
        cache_hit: Whether the specialist result was served from cache.
        agent_kind: Kind of specialist agent — ``"loop_pipeline"`` (default) or
            ``"single_pass"``.
    """
    if not WEAVE_AVAILABLE or _weave is None:
        return
    try:
        call = _weave.get_current_call()
        if call and hasattr(call, "summary"):
            call.summary["specialist_name"] = specialist_name
            call.summary["agent_kind"] = agent_kind
            call.summary["cache_hit"] = cache_hit
            # Review-loop-only attributes: a single-pass specialist has no
            # reviewer, so exit_reason / total_iterations / output_key_prefix
            # would be meaningless (see docstring).
            if agent_kind == "loop_pipeline":
                feedback = final_state.get(f"{prefix}_feedback", "")
                exit_reason = "approved" if feedback == "" else "max_iterations"
                call.summary["exit_reason"] = exit_reason
                call.summary["total_iterations"] = total_iterations
                call.summary["output_key_prefix"] = prefix
    except Exception as exc:
        logger.warning(
            "set_specialist_span_attrs: summary write failed — tracing data lost: %s",
            exc,
        )
