"""Review pipeline factory for the KEN-E agentic harness.

Builds a Generator-Critic review loop (§5.1 contract): a LoopAgent containing a
specialist worker and a gemini-2.0-flash reviewer as direct children. The reviewer
calls exit_loop to approve, or writes feedback to session state for the next iteration.

Architecture note: specialist and reviewer must be *direct* children of LoopAgent.
An intermediate SequentialAgent wrapper prevents the LoopAgent from correctly
observing the exit_loop termination signal.
"""

import re
from typing import Any

from google.adk.agents import LlmAgent, LoopAgent
from google.adk.tools import exit_loop

_MAX_ITERATIONS_LIMIT = 10
_VALID_PREFIX_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")

# Structural fields owned by ADK's agent graph; must not be copied to a worker.
_EXCLUDED_WORKER_FIELDS = {"parent_agent", "sub_agents"}
# Fields the factory sets explicitly on the worker; copy from specialist would
# clobber the factory's intended values.
_OVERRIDDEN_WORKER_FIELDS = {"name", "instruction", "tools", "output_key"}

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
    worker_kwargs: dict[str, Any] = {}
    for field in LlmAgent.model_fields:
        if field in _EXCLUDED_WORKER_FIELDS or field in _OVERRIDDEN_WORKER_FIELDS:
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
