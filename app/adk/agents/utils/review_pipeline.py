"""Review pipeline factory for the KEN-E agentic harness.

Builds a Generator-Critic review loop (§5.1 contract): a LoopAgent containing a
specialist worker and a gemini-2.0-flash reviewer as direct children. The reviewer
calls exit_loop to approve, or writes feedback to session state for the next iteration.

Architecture note: specialist and reviewer must be *direct* children of LoopAgent.
An intermediate SequentialAgent wrapper does not propagate the reviewer's `escalate`
action up to the LoopAgent, so the loop never terminates on approval.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

from google.adk.agents import LlmAgent, LoopAgent
from google.adk.tools import exit_loop

from app.utils.weave_observability import safe_weave_op

logger = logging.getLogger(__name__)

# Hallucinated-approval patterns. Tightened to filter common negation/conditional
# false positives ("not approved", "cannot approve", "would call exit_loop").
# Observability-only: false positives waste log volume but don't change loop behavior.
_APPROVAL_PATTERN = re.compile(
    r"(?<!not\s)(?<!cannot\s)\bapproved\b"
    r"|(?<!not\s)\ball criteria(?:\s+are)?\s+met\b"
    r"|\bcalling\s+exit_loop\b"
    r"|\bexit_loop\s*\(",
    re.IGNORECASE,
)


@safe_weave_op(name="review_loop.hallucinated_approval")
def _emit_hallucination_span(
    reviewer_text: str, iteration: int, output_key_prefix: str
) -> None:
    """Weave span emitted when a hallucinated approval is detected.

    Called by _check_hallucinated_approval() when the final reviewer event
    contains approval-sounding text but actions.escalate is unset/False.
    The decorated function's inputs become the span's attributes in Weave.
    """


@dataclass
class ReviewIteration:
    """One complete specialist+reviewer iteration in a review loop."""

    iteration: int  # 1-based
    specialist_output: str
    reviewer_output: str
    escalate: bool  # True if reviewer called exit_loop on this iteration


_MAX_ITERATIONS_LIMIT = 10
_VALID_PREFIX_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

# Field-propagation policy is pinned against google-adk 1.27.5; see
# TestModelFieldsSnapshot in test_review_pipeline.py — that test fails on ADK
# upgrades and forces re-categorization of any new LlmAgent fields into one of
# the four buckets below.
#
# Structural fields owned by ADK's agent graph; must not be copied to a worker.
_EXCLUDED_WORKER_FIELDS = {"parent_agent", "sub_agents"}
# Fields the factory sets explicitly on the worker; copy from specialist would
# clobber the factory's intended values.
_OVERRIDDEN_WORKER_FIELDS = {"name", "instruction", "tools", "output_key"}
# Fields that must NOT be propagated to the worker: output_schema enables
# structured-output mode in ADK and disables tool use. A worker with
# output_schema would lose its MCP/function tools and could not write a
# free-form text draft for the reviewer's {prefix}_draft template.
_DROPPED_WORKER_FIELDS = {"output_schema"}

_SENTINEL_TOKENS = ("<<<CRITERIA_START>>>", "<<<CRITERIA_END>>>")


def build_review_pipeline(
    specialist: LlmAgent,
    acceptance_criteria: str,
    output_key_prefix: str | None = None,
    max_iterations: int = 3,
    reviewer_model: str = "gemini-2.0-flash",
) -> LoopAgent:
    """Build a Generator-Critic review loop wrapping a specialist agent.

    Args:
        specialist: The specialist `LlmAgent` to wrap. Must have a string
            `instruction`. The specialist is not mutated; this factory
            constructs a new worker `LlmAgent` from the specialist's full
            field set, named `f"{specialist.name}_worker"`.
        acceptance_criteria: Plain-text criteria injected into both the worker
            instruction (so the worker knows what to satisfy) and the reviewer
            instruction (so the reviewer knows what to check). Must be a
            non-empty string and must not contain either sentinel token
            (`<<<CRITERIA_START>>>` or `<<<CRITERIA_END>>>`).
        output_key_prefix: Namespace for session-state keys. The worker writes
            its draft to `f"{output_key_prefix}_draft"` and the reviewer writes
            feedback to `f"{output_key_prefix}_feedback"`. Must be lowercase
            alphanumeric/underscore starting with a letter, max 64 chars.
            Callers MUST choose a unique prefix per concurrent pipeline to avoid
            state collisions. Defaults to `f'{specialist.name}_review'` when
            not provided.
        max_iterations: Maximum review iterations before the loop exits without
            reviewer approval. Must be between 1 and 10 inclusive. Defaults to 3.
        reviewer_model: Model identifier for the reviewer LLM. Defaults to
            `"gemini-2.0-flash"`.

    Returns:
        A `LoopAgent` named `f"{output_key_prefix}_loop"` containing the worker
        and the reviewer as its sub-agents.

    Raises:
        TypeError: If `specialist.instruction` is not a `str`. ADK supports
            callable instructions, but this factory composes the instruction
            string at build time and cannot wrap a callable.
        ValueError: If `specialist.instruction` contains a
            `<<<CRITERIA_START>>>` or `<<<CRITERIA_END>>>` sentinel token,
            which would corrupt the prompt structure; if `acceptance_criteria`
            is not a non-empty string or contains either sentinel token; if
            `output_key_prefix` does not match the required format or cannot
            be auto-derived from `specialist.name`; or if `max_iterations` is
            outside the allowed range.
    """
    if not isinstance(specialist.instruction, str):
        raise TypeError(
            "build_review_pipeline requires specialist.instruction to be a str; "
            f"got {type(specialist.instruction).__name__}. Callable instructions "
            "are not supported by this factory."
        )
    for _token in _SENTINEL_TOKENS:
        if _token in specialist.instruction:
            raise ValueError(
                f"specialist.instruction must not contain the literal {_token!r} sentinel"
            )

    if not isinstance(acceptance_criteria, str) or not acceptance_criteria.strip():
        raise ValueError(
            "acceptance_criteria must be a non-empty string; "
            f"got {type(acceptance_criteria).__name__!r}"
        )
    for _token in _SENTINEL_TOKENS:
        if _token in acceptance_criteria:
            raise ValueError(
                f"acceptance_criteria must not contain the literal {_token!r} sentinel"
            )

    if output_key_prefix is None:
        _candidate = f"{specialist.name}_review".lower()
        if not _VALID_PREFIX_RE.match(_candidate):
            raise ValueError(
                f"Cannot derive a valid output_key_prefix from specialist.name "
                f"{specialist.name!r} (candidate {_candidate!r} is invalid). "
                "Pass output_key_prefix explicitly."
            )
        output_key_prefix = _candidate

    if not _VALID_PREFIX_RE.match(output_key_prefix):
        raise ValueError(
            "output_key_prefix must be lowercase alphanumeric/underscore, "
            f"start with a letter, and be at most 64 chars; got {output_key_prefix!r}"
        )

    if not (1 <= max_iterations <= _MAX_ITERATIONS_LIMIT):
        raise ValueError(
            f"max_iterations must be between 1 and {_MAX_ITERATIONS_LIMIT}; "
            f"got {max_iterations}"
        )

    worker_instruction = (
        f"{specialist.instruction}\n\n"
        "## Acceptance Criteria\n"
        "Your response must satisfy all of the following criteria:\n"
        "<<<CRITERIA_START>>>\n"
        f"{acceptance_criteria}\n"
        "<<<CRITERIA_END>>>\n\n"
        "## Previous Feedback (if any)\n"
        f"{{{output_key_prefix}_feedback?}}"
    )

    # Strip exit_loop from worker tools (attribute-based to survive future
    # wrappers like FunctionTool) so only the reviewer can terminate the loop.
    worker_tools = [
        t
        for t in list(specialist.tools or [])
        if not (
            getattr(t, "name", None) == "exit_loop"
            or getattr(t, "__name__", None) == "exit_loop"
        )
    ]

    # Propagate the specialist's full field set to the worker so behavior-
    # affecting fields (callbacks, generate_content_config, planner, etc.) are
    # preserved. Exclude ADK-managed structural fields and fields this factory
    # overrides explicitly below.
    # Note: before_agent_callback and after_agent_callback are propagated
    # intentionally. Inside a LoopAgent they fire once per iteration (up to
    # max_iterations times per user turn). Specialist authors must design
    # these callbacks to be idempotent.
    worker_kwargs: dict[str, Any] = {}
    for field in LlmAgent.model_fields:
        if (
            field in _EXCLUDED_WORKER_FIELDS
            or field in _OVERRIDDEN_WORKER_FIELDS
            or field in _DROPPED_WORKER_FIELDS
        ):
            continue
        worker_kwargs[field] = getattr(specialist, field)

    worker_kwargs.update(
        {
            "name": f"{specialist.name}_worker",
            "instruction": worker_instruction,
            "tools": worker_tools,
            "output_key": f"{output_key_prefix}_draft",
        }
    )

    specialist_worker = LlmAgent(**worker_kwargs)

    reviewer_instruction = (
        "## Acceptance Criteria\n"
        "Evaluate the following draft against these criteria:\n"
        "<<<CRITERIA_START>>>\n"
        f"{acceptance_criteria}\n"
        "<<<CRITERIA_END>>>\n\n"
        "## Draft to Evaluate\n"
        f"{{{output_key_prefix}_draft}}\n\n"
        "## Instructions\n"
        "Check each criterion above against the draft text. "
        "If criteria pass, invoke the `exit_loop` tool. "
        "Do not write 'calling exit_loop' or any approval text. "
        "If criteria are NOT all met, provide specific feedback on what needs to be improved."
    )

    reviewer = LlmAgent(
        name=f"{output_key_prefix}_reviewer",
        model=reviewer_model,
        instruction=reviewer_instruction,
        include_contents="none",
        tools=[exit_loop],
        output_key=f"{output_key_prefix}_feedback",
    )

    return LoopAgent(
        name=f"{output_key_prefix}_loop",
        sub_agents=[specialist_worker, reviewer],
        max_iterations=max_iterations,
    )


def extract_pipeline_result(
    session_state: dict[str, Any], output_key_prefix: str
) -> dict[str, Any]:
    """Extract the pipeline's terminal result via the §5.2 approval-vs-exhaustion idiom.

    Three outcomes:

    1. Draft key absent — pipeline never produced output (timeout, runner error,
       worker never ran). Returns approved=False with a "no draft" warning. This
       is **not** equivalent to an approved-but-empty draft; an upstream failure
       must not be reported as success.
    2. Draft present, feedback empty (or absent) — reviewer called exit_loop,
       which wipes the reviewer's output_key. Approved.
    3. Draft present, feedback non-empty — max_iterations reached without
       approval; the last reviewer rejection is retained as the warning.

    Args:
        session_state: A dict-like mapping of session state keys to values.
            Typically tool_context.state or the dict returned by invoke_pipeline().
        output_key_prefix: The prefix used when building the review pipeline
            (e.g., "news_review" or "ga_review"). Must match the prefix passed to
            build_review_pipeline().

    Returns:
        {"result": "", "approved": False, "warning": "pipeline produced no draft"}
            when the draft key is absent.
        {"result": draft, "approved": True} when feedback is empty (approved).
        {"result": draft, "approved": False, "warning": feedback} when feedback is
            non-empty (exhausted).
    """
    draft_key = f"{output_key_prefix}_draft"
    feedback_key = f"{output_key_prefix}_feedback"

    if draft_key not in session_state:
        return {
            "result": "",
            "approved": False,
            "warning": "pipeline produced no draft",
        }

    draft = session_state[draft_key]
    feedback = session_state.get(feedback_key, "")
    if feedback == "":
        return {"result": draft, "approved": True}
    return {"result": draft, "approved": False, "warning": feedback}


def get_worker_name(specialist: LlmAgent) -> str:
    """The name `build_review_pipeline()` assigns to the worker child."""
    return f"{specialist.name}_worker"


def get_reviewer_name(output_key_prefix: str) -> str:
    """The name `build_review_pipeline()` assigns to the reviewer child."""
    return f"{output_key_prefix}_reviewer"


def _event_text(event: Any) -> str:
    """Concatenate text parts from an ADK event's content, if any."""
    if not event.content or not event.content.parts:
        return ""
    return "".join(part.text or "" for part in event.content.parts)


def extract_iterations(
    events: list[Any],
    specialist_worker_name: str,
    reviewer_name: str,
    output_key_prefix: str,
) -> list[ReviewIteration]:
    """Synthesize per-iteration records from a flat list of ADK events.

    ADK does not natively delimit LoopAgent iterations — all events inside a
    LoopAgent run share one ``invocation_id`` with ``branch=None``. This helper
    pairs each specialist-final event with the immediately following
    reviewer-final event to reconstruct iteration boundaries.

    Args:
        events: Ordered list of ADK ``Event`` objects from a single LoopAgent
            run. Events from outside the loop are tolerated and ignored.
        specialist_worker_name: ``name`` of the worker LlmAgent (typically
            ``f"{specialist.name}_worker"``).
        reviewer_name: ``name`` of the reviewer LlmAgent (typically
            ``f"{output_key_prefix}_reviewer"``).
        output_key_prefix: Same prefix passed to ``build_review_pipeline``.
            Used to look up ``{prefix}_draft`` and ``{prefix}_feedback`` values
            in event ``actions.state_delta``.

    Returns:
        A list of ``ReviewIteration`` records in iteration order. If the
        runner aborted mid-iteration (specialist-final with no following
        reviewer-final), the trailing record has ``reviewer_output=""`` and
        ``escalate=False``.
    """
    draft_key = f"{output_key_prefix}_draft"
    feedback_key = f"{output_key_prefix}_feedback"

    iterations: list[ReviewIteration] = []
    pending_specialist_output: str | None = None
    iteration_num = 0

    for event in events:
        author = getattr(event, "author", None)
        is_final = False
        is_final_fn = getattr(event, "is_final_response", None)
        if callable(is_final_fn):
            try:
                is_final = bool(is_final_fn())
            except Exception:
                is_final = False

        if not is_final:
            continue

        if author == specialist_worker_name:
            # If we already have a pending specialist output without a
            # matching reviewer-final, the previous iteration was aborted
            # mid-flight; emit it with an empty reviewer record before
            # starting the next iteration.
            if pending_specialist_output is not None:
                iteration_num += 1
                iterations.append(
                    ReviewIteration(
                        iteration=iteration_num,
                        specialist_output=pending_specialist_output,
                        reviewer_output="",
                        escalate=False,
                    )
                )

            specialist_output = ""
            actions = getattr(event, "actions", None)
            state_delta = getattr(actions, "state_delta", None) if actions else None
            if state_delta:
                specialist_output = state_delta.get(draft_key, "") or ""
            if not specialist_output:
                specialist_output = _event_text(event)
            pending_specialist_output = specialist_output

        elif author == reviewer_name:
            if pending_specialist_output is None:
                # Reviewer-final with no prior specialist-final; nothing to
                # pair, skip.
                continue

            reviewer_output = ""
            actions = getattr(event, "actions", None)
            state_delta = getattr(actions, "state_delta", None) if actions else None
            if state_delta:
                reviewer_output = state_delta.get(feedback_key, "") or ""
            if not reviewer_output:
                reviewer_output = _event_text(event)

            escalate = bool(getattr(actions, "escalate", False)) if actions else False

            iteration_num += 1
            iterations.append(
                ReviewIteration(
                    iteration=iteration_num,
                    specialist_output=pending_specialist_output,
                    reviewer_output=reviewer_output,
                    escalate=escalate,
                )
            )
            pending_specialist_output = None

    # Trailing specialist-final with no reviewer-final — runner aborted.
    if pending_specialist_output is not None:
        iteration_num += 1
        iterations.append(
            ReviewIteration(
                iteration=iteration_num,
                specialist_output=pending_specialist_output,
                reviewer_output="",
                escalate=False,
            )
        )

    return iterations


def _check_hallucinated_approval(events: list, output_key_prefix: str) -> None:
    """Check for hallucinated approvals in the final reviewer event.

    After a review pipeline run, inspects the final reviewer event to detect
    the rare failure mode where the reviewer emits approval-sounding text
    (matching 'approved|all criteria|exit_loop') without invoking exit_loop
    (i.e., actions.escalate is unset/False). When detected, emits a warning
    Weave span and a logger.warning for the standard log pipeline.

    This is observability only — loop behavior is unchanged. The missing tool
    call already keeps the loop running normally (escalate unset means the
    LoopAgent continues to the next iteration). We emit telemetry to track
    the real-world rate of this failure mode.

    Args:
        events: The list of ADK Event objects returned by invoke_pipeline().
            May be empty (e.g., on timeout or error).
        output_key_prefix: The output_key_prefix used when building the review
            pipeline (e.g., "news_review" or "ga_review"). Used to identify
            reviewer events by their author name.

    Returns:
        None always. Internal exceptions are caught and logged; observability
        must not break the dispatch.
    """
    try:
        reviewer_name = f"{output_key_prefix}_reviewer"

        # Collect non-partial reviewer events (partial=True events are streaming
        # chunks; we only want final events that represent complete responses).
        reviewer_events = [
            e
            for e in events
            if getattr(e, "author", None) == reviewer_name
            and not getattr(e, "partial", False)
        ]
        if not reviewer_events:
            return

        # PRD §5.2 + AC#11: inspect only the FINAL reviewer event.
        final_event = reviewer_events[-1]
        iteration_count = len(reviewer_events)

        # Extract text from content parts.
        text_parts: list[str] = []
        content = getattr(final_event, "content", None)
        if content:
            for part in getattr(content, "parts", []):
                t = getattr(part, "text", None)
                if t:
                    text_parts.append(t)
        text = " ".join(text_parts)

        if not text:
            return

        if not _APPROVAL_PATTERN.search(text):
            return

        # Check whether exit_loop was actually invoked (escalate=True).
        actions = getattr(final_event, "actions", None)
        escalate_set = bool(actions and getattr(actions, "escalate", False))
        if escalate_set:
            # Real approval — exit_loop was called; not a hallucination.
            return

        # Hallucinated approval detected: pattern match but no escalate.
        _emit_hallucination_span(
            reviewer_text=text[:500],
            iteration=iteration_count,
            output_key_prefix=output_key_prefix,
        )
        logger.warning(
            "[REVIEW-LOOP] Hallucinated approval detected in '%s' reviewer "
            "(iteration %d). Text matched approval pattern but exit_loop was "
            "not invoked. Loop behavior unchanged — continuing normally. "
            "Text snippet: %.200s",
            output_key_prefix,
            iteration_count,
            text,
        )
    except Exception:
        logger.error(
            "[REVIEW-LOOP] _check_hallucinated_approval raised unexpectedly "
            "for prefix '%s'. Swallowing to protect dispatch.",
            output_key_prefix,
            exc_info=True,
        )
