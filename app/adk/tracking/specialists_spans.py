"""Weave span callback for the per-turn available-specialist roster (CH-58).

``specialists_span_before_agent_callback`` fires after
``attach_specialists_before_agent_callback`` populates
``session.state["_available_specialists"]`` and emits a one-shot
``specialists.list`` child span nested under the ``ken_e_agent`` root span.

Design:
  - **Empty roster vs missing state key are distinct signals** (per MER-E
    contract, docs/trace-structure-spec.md §16):
    * Key PRESENT (even if ``[]``) → emit span with ``specialist_count: 0``.
    * Key MISSING entirely → skip emission; absence is a degradation signal.
  - Degrade open: every non-recoverable failure (Weave client absent,
    ``create_call`` raised) is caught, logged at WARNING, and the callback
    returns ``None`` so the agent turn is unaffected.
  - Factory stays Weave-free: the data flows via session state, not a direct
    import from the agent_factory layer.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from shared.account_id_utils import validate_account_id
from shared.structured_logging import get_structured_logger

# Lazy import guard — mirrors skill_spans.py:36-42.  builder.py imports
# callbacks (which import specialists_spans) at module top, so a Weave import
# failure would cascade into the entire agent factory becoming unimportable.
_weave_get_client: Callable[[], Any] | None = None
_weave_call_context: Any | None = None
try:
    from weave.trace.api import get_client as _weave_get_client
    from weave.trace.context import call_context as _weave_call_context
except ImportError:  # pragma: no cover
    pass

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext
    from google.genai import types

logger = get_structured_logger(__name__)

# Sentinel used to distinguish a missing state key from an explicitly empty
# list.  A plain ``state.get(key, [])`` collapses both into an empty list,
# making the degradation signal invisible to MER-E.
_MISSING: object = object()


def specialists_span_before_agent_callback(
    callback_context: CallbackContext,
) -> types.Content | None:
    """Emit a ``specialists.list`` Weave child span for the current turn.

    Reads ``_available_specialists`` from session state (written by
    ``attach_specialists_before_agent_callback``).  The span is nested under
    the open ``ken_e_agent`` root span via ``use_stack=True``.

    Empty-vs-missing policy (per docs/trace-structure-spec.md §16):
      - Key PRESENT (even if ``[]``) → emit span; ``specialist_count`` may be 0.
      - Key MISSING → skip emission (degradation signal for MER-E).

    Must be wired AFTER ``attach_specialists_before_agent_callback`` in
    ``additional_before_agent_callbacks`` so the state key is populated before
    this callback reads it.

    Always returns ``None`` — never blocks the agent turn.
    """
    if _weave_get_client is None:
        return None
    client = _weave_get_client()
    if not client:
        return None

    try:
        state: Any = callback_context.state
        specialists = state.get("_available_specialists", _MISSING)

        if specialists is _MISSING:
            # State key absent — capture failed or wiring bypassed.
            # Skip emission so MER-E sees the absence as a degradation signal.
            # Do NOT log a warning here; the absence is a deliberate signal,
            # not an error in this callback.
            return None

        if not isinstance(specialists, list):
            logger.warning(
                "specialists_span: state['_available_specialists'] has unexpected "
                "type %s; skipping span emission",
                type(specialists).__name__,
            )
            return None

        account_id = "unknown"
        try:
            raw_account_id = state.get("account_id")
            if raw_account_id:
                account_id = validate_account_id(str(raw_account_id))
        except (ValueError, Exception):
            logger.debug(
                "specialists_span: could not validate account_id from state; "
                "defaulting to 'unknown'",
                exc_info=True,
            )

        call = client.create_call(
            op="specialists.list",
            inputs={},
            attributes={
                "account_id": account_id,
                "specialist_count": len(specialists),
                "specialists": specialists,  # [{name, description, agent_id}, ...]
            },
            use_stack=True,
        )
        if call is None:
            return None
        try:
            client.finish_call(call, output={"status": "ok"})
        finally:
            if _weave_call_context is not None:
                try:
                    _weave_call_context.pop_call(call.id)
                except Exception:
                    pass

    except Exception:
        logger.warning(
            "specialists_span_before_agent_callback failed (non-blocking)",
            exc_info=True,
        )

    return None
