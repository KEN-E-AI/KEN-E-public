"""Review pipeline factory for the KEN-E agentic harness.

Builds a Generator-Critic review loop (§5.1 contract): a LoopAgent containing a
specialist worker and a gemini-2.5-pro reviewer as direct children. The reviewer
calls exit_loop to approve, or writes feedback to session state for the next iteration.

Architecture note: specialist and reviewer must be *direct* children of LoopAgent.
An intermediate SequentialAgent wrapper does not propagate the reviewer's `escalate`
action up to the LoopAgent, so the loop never terminates on approval.
"""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from google.adk.agents import LlmAgent, LoopAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import ToolContext
from google.adk.tools import exit_loop as _adk_exit_loop

from app.utils.weave_observability import safe_weave_op

logger = logging.getLogger(__name__)

# Default reviewer model for the Generator-Critic review loop.
# Configurable per-specialist via ``MergedAgentConfig.reviewer_model``
# (AH-92 / AH-PRD-09); callers that omit the parameter continue to get this.
DEFAULT_REVIEWER_MODEL: str = "gemini-2.5-pro"

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

# Field-propagation policy is pinned against google-adk 2.0.0; see
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


def _strip_criteria_sentinels(text: str) -> str:
    """Remove sentinel tokens from a rendered instruction string.

    Called defensively inside the callable-instruction wrapper to guard against
    the unlikely case where the factory's callable returns text that already
    contains the sentinel tokens (which would corrupt the prompt structure).
    Logs a warning on hit so ops can investigate the source; never raises.
    """
    stripped = text
    hit = False
    for token in _SENTINEL_TOKENS:
        if token in stripped:
            stripped = stripped.replace(token, "")
            hit = True
    if hit:
        logger.warning(
            "[REVIEW-LOOP] Callable instruction rendered sentinel token(s); "
            "tokens stripped to preserve prompt structure. Investigate the "
            "callable instruction provider — sentinel tokens must not appear "
            "in the base instruction text."
        )
    return stripped


def _compose_worker_instruction(
    base: str | Callable[..., Any],
    acceptance_criteria: str,
    output_key_prefix: str,
) -> str | Callable[[ReadonlyContext], str]:
    """Compose the worker instruction from a base (str or callable) and criteria.

    String path: returns the fully composed string immediately (same as the
    pre-AH-90 behaviour; sentinel check runs at build time).

    Callable path: returns a closure that, when invoked per turn by ADK,
    calls the original callable with the live ReadonlyContext, strips any
    sentinel tokens from the rendered output (defensive; logs.warning on hit),
    then appends the acceptance criteria and previous feedback.  The closure
    preserves the factory's per-turn org-context injection and live-config
    re-read supplied by _make_factory_instruction_provider in builder.py.

    Feedback handling differs by path because ADK only runs
    ``inject_session_state`` (which resolves ``{key?}`` templates) on *string*
    instructions; for callable instructions it sets ``bypass_state_injection=
    True`` and skips substitution entirely (see
    google.adk.flows.llm_flows.instructions._process_agent_instruction).  So:

    * String path embeds the ``{prefix_feedback?}`` template token and relies
      on ADK to substitute the reviewer's feedback on each iteration.
    * Callable path resolves ``{prefix}_feedback`` from ``context.state``
      inside the closure — if it left the template token in place, ADK would
      render it literally and the worker would never see the reviewer's
      feedback, silently breaking the Generator-Critic revision loop.

    The caller (build_review_pipeline) is responsible for validating that
    acceptance_criteria is a non-empty string free of sentinel tokens before
    calling this helper.
    """
    feedback_key = f"{output_key_prefix}_feedback"
    # Everything up to (and including) the "Previous Feedback" header is shared
    # by both paths; only how the feedback value itself is filled in differs.
    criteria_block = (
        "\n\n"
        "## Drafting Rules\n"
        "Your draft must be a clean, standalone, user-facing answer. "
        "You must not reference, acknowledge, quote, or argue with the reviewer "
        "or these acceptance criteria in your draft. "
        "Address feedback by changing the answer itself — never by adding "
        "meta-commentary that explains, justifies, or argues against the feedback. "
        "If a criterion does not apply to this answer (for example, a 'provide the "
        "formula' criterion when the value is a direct platform metric, not a derived "
        "calculation), silently omit that element. Do not justify its absence in prose.\n\n"
        "## Acceptance Criteria\n"
        "Your response must satisfy all of the following criteria:\n"
        "<<<CRITERIA_START>>>\n"
        f"{acceptance_criteria}\n"
        "<<<CRITERIA_END>>>\n\n"
        "## Previous Feedback (if any)\n"
    )

    if isinstance(base, str):
        # ADK substitutes {prefix_feedback?} via inject_session_state because
        # string instructions have bypass_state_injection=False.
        return base + criteria_block + f"{{{feedback_key}?}}"

    # Callable path — wrap the original provider.
    original_callable = base

    def _worker_instruction_provider(context: ReadonlyContext) -> str:
        rendered = original_callable(context)
        # ADK's instruction callable type allows Awaitable[str]; in practice
        # the factory always returns a plain str, but guard defensively.
        if not isinstance(rendered, str):  # pragma: no cover
            rendered = str(rendered)
        rendered = _strip_criteria_sentinels(rendered)
        # ADK bypasses inject_session_state for callable instructions, so we
        # must resolve the reviewer's feedback from live state ourselves. An
        # absent key renders empty — matching the {prefix_feedback?} optional
        # template semantics of the string path on iteration 1.
        feedback = context.state.get(feedback_key, "")
        if not isinstance(feedback, str):  # pragma: no cover
            feedback = str(feedback)
        return rendered + criteria_block + feedback

    return _worker_instruction_provider


def _make_review_exit_loop(feedback_key: str) -> Callable[[ToolContext], None]:
    """Build the reviewer's loop-exit tool for one pipeline.

    Behaves like ADK's built-in ``exit_loop`` (delegates to it, so the
    ``escalate`` / ``skip_summarization`` semantics that end the ``LoopAgent``
    are preserved) **and** explicitly writes ``""`` to the reviewer's feedback
    key on approval.

    Why the explicit write: ADK <= 1.27 overwrote an agent's ``output_key`` to
    ``""`` on a tool-only turn (no model text), so the reviewer's ``exit_loop``
    approval cleared ``{prefix}_feedback`` as a side effect — which
    ``extract_pipeline_result`` (and the tracing layer) read as "approved".
    ADK 1.34+ sets ``skip_summarization`` on exit and no longer writes
    ``output_key`` on a tool-only turn, so a stale rejection in
    ``{prefix}_feedback`` would survive and an approved draft would be misread
    as rejected. Clearing the key here restores the approval invariant
    deterministically, independent of ADK version.
    """

    def exit_loop(tool_context: ToolContext) -> None:
        """Exits the review loop on approval.

        Call this only when the draft satisfies every acceptance criterion.
        """
        _adk_exit_loop(tool_context)
        tool_context.state[feedback_key] = ""

    return exit_loop


def build_review_pipeline(
    specialist: LlmAgent,
    acceptance_criteria: str,
    output_key_prefix: str | None = None,
    max_iterations: int = 3,
    reviewer_model: str = DEFAULT_REVIEWER_MODEL,
) -> LoopAgent:
    """Build a Generator-Critic review loop wrapping a specialist agent.

    Args:
        specialist: The specialist `LlmAgent` to wrap. Its `instruction` may
            be either a plain `str` or a `Callable[[ReadonlyContext], str]`
            (the factory callable produced by `builder._make_factory_instruction_provider`).
            The specialist is not mutated; this factory constructs a new worker
            `LlmAgent` from the specialist's full field set, named
            `f"{specialist.name}_worker"`. The worker's instruction is composed
            from the specialist's instruction plus the acceptance-criteria and
            previous-feedback sections; for callable instructions this is done
            inside a wrapping closure so per-turn org-context injection and
            live-config re-reads (supplied by the factory's callable) are
            preserved on every review iteration, and the reviewer's feedback is
            resolved from session state directly (ADK skips template injection
            for callable instructions).
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
            `"gemini-2.5-pro"`.

    Returns:
        A `LoopAgent` named `f"{output_key_prefix}_loop"` containing the worker
        and the reviewer as its sub-agents.

    Raises:
        TypeError: If `specialist.instruction` is neither a `str` nor a
            `Callable[[ReadonlyContext], str]` (e.g., `None`, `int`, list).
        ValueError: If `specialist.instruction` is a `str` that contains a
            `<<<CRITERIA_START>>>` or `<<<CRITERIA_END>>>` sentinel token
            (cannot validate callable instructions at build time — sentinel
            stripping happens at runtime inside the wrapper closure); if
            `acceptance_criteria` is not a non-empty string or contains either
            sentinel token; if `output_key_prefix` does not match the required
            format or cannot be auto-derived from `specialist.name`; or if
            `max_iterations` is outside the allowed range.
    """
    if not isinstance(specialist.instruction, str) and not callable(specialist.instruction):
        raise TypeError(
            "build_review_pipeline requires specialist.instruction to be a str "
            "or Callable[[ReadonlyContext], str]; "
            f"got {type(specialist.instruction).__name__}."
        )

    # Sentinel-token check runs only for string instructions; callable
    # instructions cannot be introspected at build time — the defensive runtime
    # strip in _compose_worker_instruction handles any leakage.
    if isinstance(specialist.instruction, str):
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

    worker_instruction = _compose_worker_instruction(
        specialist.instruction, acceptance_criteria, output_key_prefix
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
        "If criteria are NOT all met, provide specific feedback on what needs to be improved. "
        "When applying a 'provide the formula' or 'show the calculation' criterion, "
        "note that this applies only to derived metrics (metrics computed from other "
        "values, e.g. CTR = clicks / impressions, CPC = spend / clicks, "
        "ROAS = revenue / spend). Direct platform metrics reported as raw counts or "
        "aggregates by the platform itself (e.g. Google Analytics 'Total active users', "
        "'Sessions', 'New users') have no formula; their absence is not a defect and "
        "must not be flagged as missing."
    )

    reviewer = LlmAgent(
        name=f"{output_key_prefix}_reviewer",
        model=reviewer_model,
        instruction=reviewer_instruction,
        include_contents="none",
        tools=[_make_review_exit_loop(f"{output_key_prefix}_feedback")],
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
       whose per-pipeline tool clears the reviewer's feedback key on approval
       (see ``_make_review_exit_loop``; ADK 1.34+ no longer auto-clears
       ``output_key`` on a tool-only turn). Approved.
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


def is_reviewer_author(author: str | None) -> bool:
    """Return True iff *author* names a review-loop reviewer sub-agent.

    Reviewers are constructed in ``build_review_pipeline()`` at line 382 as
    ``name=f"{output_key_prefix}_reviewer"``.  Any ``author`` value that ends
    with ``"_reviewer"`` (with a non-empty prefix) is treated as a reviewer.
    The predicate is intentionally conservative: ``"reviewer"`` (no prefix) and
    ``"_reviewer"`` (empty prefix) both return ``False``; ``None`` and non-str
    values also return ``False``.

    Use this helper in the chat-assembly layer to suppress reviewer-authored
    text from the user-visible response (CH-68).  Keep the reviewer events
    flowing through the upstream accumulator and event stream — this predicate
    gates display only.
    """
    if not isinstance(author, str):
        return False
    # Require at least one character before "_reviewer" so that the bare string
    # "_reviewer" is not treated as a reviewer.
    suffix = "_reviewer"
    return author.endswith(suffix) and len(author) > len(suffix)


def is_worker_author(author: str | None) -> bool:
    """Return True iff *author* names a review-loop worker sub-agent.

    Workers are constructed in ``build_review_pipeline()`` as
    ``name=f"{specialist.name}_worker"``.  Any ``author`` value that ends
    with ``"_worker"`` (with a non-empty prefix) is treated as a worker.
    The predicate is intentionally conservative: ``"worker"`` (no prefix) and
    ``"_worker"`` (empty prefix) both return ``False``; ``None`` and non-str
    values also return ``False``.

    Use this helper in the chat-assembly layer to buffer worker-authored drafts
    and flush only the final approved draft per review loop (CH-69).  The
    accumulator still receives every chunk — this predicate gates display only.
    """
    if not isinstance(author, str):
        return False
    # Require at least one character before "_worker" so that the bare string
    # "_worker" is not treated as a worker.
    suffix = "_worker"
    return author.endswith(suffix) and len(author) > len(suffix)


def worker_author_for_reviewer(reviewer_author: str | None) -> str | None:
    """Derive the paired worker author name from a reviewer author name.

    Exploits the naming convention:
        reviewer name  →  ``f"{output_key_prefix}_reviewer"``
        worker name    →  ``f"{specialist.name}_worker"``
    where ``output_key_prefix`` defaults to ``f"{specialist.name}_review"``.

    Stripping strategy:
      1. Strip the trailing ``_reviewer`` suffix.
      2. If the remainder ends with ``_review``, strip that too.
      3. Append ``_worker`` to obtain the paired worker name.

    Returns ``None`` for non-reviewer inputs or when the stripping would
    produce an empty stem (fail-safe: no buffer is dropped on a pairing miss,
    so the behaviour collapses to the pre-CH-69 state, not a new regression).

    Examples::

        worker_author_for_reviewer("ga_review_reviewer")   → "ga_worker"
        worker_author_for_reviewer("custom_reviewer")      → "custom_worker"
        worker_author_for_reviewer("ga_worker")            → None
        worker_author_for_reviewer(None)                   → None
    """
    if not is_reviewer_author(reviewer_author):
        return None
    # reviewer_author is a non-empty str ending in "_reviewer" (guaranteed by
    # is_reviewer_author above).
    stem = reviewer_author[: -len("_reviewer")]  # type: ignore[index]
    # Strip the optional trailing "_review" (default output_key_prefix convention).
    if stem.endswith("_review"):
        stem = stem[: -len("_review")]
    if not stem:
        return None
    return f"{stem}_worker"


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
