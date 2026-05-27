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

# NOTE: do NOT add `from __future__ import annotations` here. Generated
# dispatch closures are cloudpickled into the Agent Engine deployment
# artifact; deferred (string) annotations don't survive the round-trip
# (cloudpickle drops `__wrapped__`/`__globals__` for closures), so ADK's
# `typing.get_type_hints()` on the deserialized dispatch fails with
# `NameError: name 'ToolContext' is not defined` when it tries to build
# the function declaration sent to Gemini. Resolving annotations at
# function-definition time (no future import) makes the type objects
# travel with the closure and matches the legacy `dispatch_handlers.py`
# pattern. Verified end-to-end during AH-17 smoke testing.

import copy
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
from app.adk.agents.utils.criteria_utils import (
    MAX_CRITERIA_CHARS,
    sanitise_criteria,
)
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
    set_delegate_attrs,
    set_pipeline_attrs,
)
from app.utils.weave_observability import safe_weave_op
from shared.account_id_utils import validate_account_id

logger = logging.getLogger(__name__)

# Specialist names must be lowercase, start with a letter, and contain only
# letters, digits, and underscores — no longer than 64 characters total.
_VALID_SPECIALIST_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

# Hard cap on specialist description length in the Available Specialists block.
_MAX_DESCRIPTION_CHARS: int = 500


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
            copy.deepcopy(tool_context.state.to_dict()) if tool_context is not None else None
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
                from app.adk.agents.utils.supervisor_utils import (
                    invoke_pipeline,
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
                if not outcome.get("approved"):
                    logger.warning(
                        "[%s-DISPATCH] Review loop exhausted iterations without approval; "
                        "returning last draft.",
                        name.upper(),
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
            return f"Error dispatching to {name}: specialist unavailable"

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
        if not _VALID_SPECIALIST_NAME_RE.fullmatch(name)
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
        raw_desc: str = (getattr(agent, "description", None) or "").strip()
        if not raw_desc:
            description = "(no description provided)"
        else:
            description = sanitise_criteria(raw_desc[:_MAX_DESCRIPTION_CHARS])
            if not description:
                description = "(no description provided)"
        lines.append(f"- **{name}**: {description}")

    return heading + "\n".join(lines)


@safe_weave_op(name="delegate_to_specialist")
def delegate_to_specialist(
    name: str,
    query: str,
    acceptance_criteria: str = "",
    tool_context: ToolContext | None = None,
) -> str:
    """Dispatch a query to a named specialist resolved per-turn from Firestore.

    Single unified dispatch tool for the per-turn dispatch model (AH-PRD-09
    Phase 2). Replaces the N individual ``dispatch_to_<specialist>`` closures
    generated by ``generate_dispatch_functions`` with one entry point that
    delegates resolution and execution to ``specialist_runtime.run``.

    Args:
        name: Specialist Firestore document ID (``^[a-z][a-z0-9_]{0,63}$``).
        query: The query to send to the specialist.
        acceptance_criteria: Optional review-loop acceptance criteria.
        tool_context: ADK ToolContext from the calling root agent.

    Returns:
        The specialist's response string, or an error sentinel string on failure.
    """
    if not _VALID_SPECIALIST_NAME_RE.fullmatch(name):
        return (
            f"[DELEGATE ERROR] Invalid specialist name {name!r}. "
            "Names must match ^[a-z][a-z0-9_]{0,63}$."
        )

    _raw_account_id: str | None = (
        tool_context.state.get("account_id") if tool_context is not None else None
    )
    account_id: str | None
    if _raw_account_id is not None:
        try:
            account_id = validate_account_id(_raw_account_id)
        except ValueError:
            _safe_id = repr(_raw_account_id)[:120]
            logger.warning(
                "[DELEGATE] Invalid account_id %s in session state; proceeding as global.",
                _safe_id,
            )
            account_id = None
    else:
        account_id = None

    # Lazy import: avoids a circular dependency at module-load time since
    # agent_factory/__init__.py imports both dispatch and specialist_runtime.
    from app.adk.agents.agent_factory.specialist_runtime import (
        resolve_agent_with_hit as _resolve_agent_with_hit,
    )
    from app.adk.agents.agent_factory.specialist_runtime import (
        run as _specialist_run,
    )

    # Resolve the agent first to observe the LRU cache hit/miss flag.
    # The config and agent are cached, so the second resolution inside run()
    # costs only a dict lookup.
    cache_hit: bool = False
    try:
        _, cache_hit = _resolve_agent_with_hit(name, account_id)
    except Exception as _pre_resolve_exc:
        logger.warning(
            "[DELEGATE] pre-resolution for cache_hit on %r raised: %s; defaulting to False.",
            name,
            _pre_resolve_exc,
        )  # cache_hit stays False; run() will surface the error if persistent

    result = _specialist_run(
        doc_id=name,
        query=query,
        account_id=account_id,
        acceptance_criteria=acceptance_criteria,
        tool_context=tool_context,
    )
    set_delegate_attrs(specialist_name=name, cache_hit=cache_hit)
    return result
