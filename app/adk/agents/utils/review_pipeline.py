"""Review pipeline factory for the KEN-E agentic harness.

Implements the §5.1 Generator-Critic contract: every specialist delegation is
wrapped in a `LoopAgent` containing a cloned worker (the specialist) and a
reviewer that evaluates the worker's draft against caller-supplied acceptance
criteria. The reviewer either invokes `exit_loop` to escalate out of the loop
or writes feedback into session state for the worker's next iteration.

Design notes:
    * The factory clones the specialist into a fresh `LlmAgent` named
      `<specialist>_worker` so the original specialist remains reusable in
      other contexts and untouched by this wrapping.
    * The reviewer uses `include_contents='none'` so it sees only the rendered
      instruction (the draft via template substitution), not the full chat
      history - this keeps it isolated from prior turns.
    * The caller is responsible for choosing a unique `output_key_prefix` per
      concurrent pipeline; the prefix namespaces both `<prefix>_draft` and
      `<prefix>_feedback` keys in session state.
    * The `LoopAgent` directly contains `[worker, reviewer]` - wrapping these
      in a `SequentialAgent` would swallow the `escalate` signal that
      `exit_loop` emits to terminate the loop.
"""

from google.adk.agents import LlmAgent, LoopAgent
from google.adk.tools import exit_loop


def build_review_pipeline(
    specialist: LlmAgent,
    acceptance_criteria: str,
    output_key_prefix: str = "review",
    max_iterations: int = 3,
    reviewer_model: str = "gemini-2.0-flash",
) -> LoopAgent:
    """Build a Generator-Critic review loop wrapping a specialist agent.

    Args:
        specialist: The specialist `LlmAgent` to wrap. Must have a string
            `instruction`. The specialist is cloned (not mutated) into a worker
            named `f"{specialist.name}_worker"`.
        acceptance_criteria: Plain-text criteria injected into both the worker
            instruction (so the worker knows what to satisfy) and the reviewer
            instruction (so the reviewer knows what to check).
        output_key_prefix: Namespace for session-state keys. The worker writes
            its draft to `f"{output_key_prefix}_draft"` and the reviewer writes
            feedback to `f"{output_key_prefix}_feedback"`. Callers MUST choose a
            unique prefix per concurrent pipeline to avoid state collisions.
        max_iterations: Maximum review iterations before the loop exits without
            reviewer approval. Defaults to 3.
        reviewer_model: Model identifier for the reviewer LLM. Defaults to
            `"gemini-2.0-flash"`.

    Returns:
        A `LoopAgent` named `f"{output_key_prefix}_loop"` containing the cloned
        worker and the reviewer as its sub-agents.

    Raises:
        TypeError: If `specialist.instruction` is not a `str`. ADK supports
            callable instructions, but this factory composes the instruction
            string at build time and cannot wrap a callable.
    """
    if not isinstance(specialist.instruction, str):
        raise TypeError(
            "build_review_pipeline requires specialist.instruction to be a str; "
            f"got {type(specialist.instruction).__name__}. Callable instructions "
            "are not supported by this factory."
        )

    worker_instruction = (
        f"{specialist.instruction}\n\n"
        f"## Acceptance Criteria\n"
        f"Your response must satisfy all of the following criteria:\n"
        f"{acceptance_criteria}\n\n"
        f"## Previous Feedback (if any)\n"
        f"{{{output_key_prefix}_feedback?}}"
    )

    specialist_worker = LlmAgent(
        name=f"{specialist.name}_worker",
        model=specialist.model,
        description=specialist.description,
        instruction=worker_instruction,
        tools=specialist.tools,
        output_key=f"{output_key_prefix}_draft",
    )

    reviewer_instruction = (
        f"## Acceptance Criteria\n"
        f"Evaluate the following draft against these criteria:\n"
        f"{acceptance_criteria}\n\n"
        f"## Draft to Evaluate\n"
        f"{{{output_key_prefix}_draft}}\n\n"
        f"## Instructions\n"
        f"Check each criterion above against the draft text. "
        f"If criteria pass, invoke the `exit_loop` tool. "
        f"Do not write 'calling exit_loop' or any approval text. "
        f"If criteria are NOT all met, provide specific feedback on what needs to be improved."
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
