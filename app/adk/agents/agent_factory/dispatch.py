"""Dynamic dispatch-function factory for the KEN-E agent registry.

Provides two public symbols consumed by the agent factory's build phase:

* ``generate_dispatch_functions`` — given a mapping of specialist name ->
  LlmAgent, returns a matching mapping of name -> callable dispatch function,
  each wrapped with ``@safe_weave_op`` tracing and wired to the review-loop
  pipeline when ``acceptance_criteria`` is supplied by the caller.

* ``assemble_available_specialists_block`` — produces a Markdown ``##
  Available Specialists`` block listing every registered specialist in
  alphabetical order, suitable for injection into a router agent's system
  prompt.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools import ToolContext

from app.adk.agents.utils.agent_retry import (
    DEFAULT_RETRY_CONFIG,
    invoke_agent_with_retry,
)
from app.adk.agents.utils.criteria_utils import MAX_CRITERIA_CHARS, sanitise_criteria
from app.adk.agents.utils.review_pipeline import (
    _check_hallucinated_approval,
    build_review_pipeline,
    extract_iterations,
    extract_pipeline_result,
    get_reviewer_name,
    get_worker_name,
)
from app.adk.agents.utils.review_pipeline_tracing import (
    emit_iteration_span,
    set_pipeline_attrs,
)
from app.adk.agents.utils.supervisor_utils import invoke_pipeline
from app.utils.weave_observability import safe_weave_op

logger = logging.getLogger(__name__)

# Specialist names must be lowercase, start with a letter, and contain only
# letters, digits, and underscores — no longer than 64 characters total.
_VALID_SPECIALIST_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _build_dispatch(name: str, specialist: LlmAgent) -> Callable:
    """Build a single dispatch callable for *specialist* named *name*.

    The returned function:
    - Is decorated with ``@safe_weave_op(name=f"dispatch_to_{name}")`` for
      Weave tracing.
    - Accepts ``(query, acceptance_criteria="", tool_context=None)``.
    - When *acceptance_criteria* is non-empty (after sanitisation and the
      ``MAX_CRITERIA_CHARS`` cap), runs the full review-loop pipeline via
      ``build_review_pipeline`` + ``invoke_pipeline``, emits per-iteration
      Weave spans, and returns the ``result`` string from the pipeline outcome.
    - When *acceptance_criteria* is empty, delegates directly to
      ``invoke_agent_with_retry`` using ``DEFAULT_RETRY_CONFIG``.
    - On any exception: logs the error and returns a plain error string
      (never re-raises) so the router agent receives a graceful degradation
      message instead of an unhandled exception.

    Args:
        name: Validated specialist name (must satisfy ``_VALID_SPECIALIST_NAME_RE``).
        specialist: The ``LlmAgent`` to dispatch to.

    Returns:
        A callable with signature
        ``(query: str, acceptance_criteria: str = "",
           tool_context: ToolContext | None = None) -> str``.
    """
    output_key_prefix = f"{name}_review"

    @safe_weave_op(name=f"dispatch_to_{name}")
    def _dispatch(
        query: str,
        acceptance_criteria: str = "",
        tool_context: ToolContext | None = None,
    ) -> str:
        initial_state: dict[str, Any] | None = (
            dict(tool_context.state) if tool_context is not None else None
        )

        criteria = acceptance_criteria.strip()
        if len(criteria) > MAX_CRITERIA_CHARS:
            logger.warning(
                "[%s-DISPATCH] acceptance_criteria truncated from %d to %d chars",
                name.upper(),
                len(criteria),
                MAX_CRITERIA_CHARS,
            )
            criteria = criteria[:MAX_CRITERIA_CHARS]
        criteria = sanitise_criteria(criteria)

        try:
            if criteria:
                logger.info(
                    "[%s-DISPATCH] Building review pipeline (criteria length=%d).",
                    name.upper(),
                    len(criteria),
                )
                pipeline = build_review_pipeline(
                    specialist=specialist,
                    acceptance_criteria=criteria,
                    output_key_prefix=output_key_prefix,
                )
                _text, final_state, events = invoke_pipeline(
                    pipeline, query, state=initial_state
                )
                _check_hallucinated_approval(events, output_key_prefix)
                outcome = extract_pipeline_result(final_state, output_key_prefix)
                worker_name = get_worker_name(specialist)
                reviewer_name = get_reviewer_name(output_key_prefix)
                iterations = extract_iterations(
                    events, worker_name, reviewer_name, output_key_prefix
                )
                for it in iterations:
                    emit_iteration_span(
                        it.iteration, it.specialist_output, it.reviewer_output
                    )
                set_pipeline_attrs(
                    criteria, final_state, output_key_prefix, len(iterations)
                )
                return outcome["result"]

            logger.info(
                "[%s-DISPATCH] Single-pass dispatch (no acceptance_criteria).",
                name.upper(),
            )
            return invoke_agent_with_retry(
                specialist,
                query,
                state=initial_state,
                retry_config=DEFAULT_RETRY_CONFIG,
            )
        except Exception as e:
            logger.error(
                "[%s-DISPATCH] Error dispatching to specialist: %s",
                name.upper(),
                e,
                exc_info=True,
            )
            return f"Error dispatching to {name}: {e}"

    # Give the function a helpful __name__ for introspection / logging.
    _dispatch.__name__ = f"dispatch_to_{name}"
    return _dispatch


def generate_dispatch_functions(
    specialists: dict[str, LlmAgent],
) -> dict[str, Callable]:
    """Generate a dispatch callable for every specialist in *specialists*.

    Each key in the returned dict matches a key in *specialists*, and each
    value is a callable produced by ``_build_dispatch``.

    Args:
        specialists: Mapping of specialist name -> ``LlmAgent``.  Names must
            satisfy ``^[a-z][a-z0-9_]{0,63}$``; a ``ValueError`` is raised at
            build time for any name that violates this constraint.

    Returns:
        ``dict[str, Callable]`` — one entry per specialist.

    Raises:
        ValueError: If any specialist name does not satisfy the name
            validation regex.
    """
    invalid = [
        name
        for name in specialists
        if not _VALID_SPECIALIST_NAME_RE.match(name)
    ]
    if invalid:
        raise ValueError(
            f"Specialist name(s) {invalid!r} are invalid. "
            "Names must match ^[a-z][a-z0-9_]{0,63}$."
        )

    return {name: _build_dispatch(name, agent) for name, agent in specialists.items()}


def assemble_available_specialists_block(
    specialists: dict[str, LlmAgent],
) -> str:
    """Build a Markdown block listing every registered specialist.

    Returns a string starting with ``"## Available Specialists\\n\\n"`` followed
    by one bullet per specialist in alphabetical order.  Each bullet has the
    form ``"- **{name}**: {description}"``.  When the specialist's description
    is absent or empty, the fallback text ``"(no description provided)"`` is
    used.

    When the registry is empty, the heading is still emitted, followed by a
    single ``"- None registered."`` line.

    Args:
        specialists: Mapping of specialist name -> ``LlmAgent``.

    Returns:
        A Markdown-formatted string ready for injection into a router agent's
        system prompt.
    """
    heading = "## Available Specialists\n\n"

    if not specialists:
        return heading + "- None registered."

    lines: list[str] = []
    for name in sorted(specialists):
        agent = specialists[name]
        description: str = (getattr(agent, "description", None) or "").strip()
        if not description:
            description = "(no description provided)"
        lines.append(f"- **{name}**: {description}")

    return heading + "\n".join(lines)
