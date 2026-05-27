"""ADK callbacks for the Chat component side-table integration.

Stamps last_agent_started_at on before_agent_callback and flushes a full
per-turn delta (tokens, tool calls, message count) on after_agent_callback.
Root-agent-only: specialist sub-agents return None immediately.

CH-PRD-01 §5.1 (ADK callback wiring), §7 AC-6, AC-19.
"""

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import requests
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token as _google_id_token

from shared.structured_logging import get_structured_logger

if TYPE_CHECKING:
    from google.adk.agents.callback_context import CallbackContext
    from google.genai import types

logger = get_structured_logger(__name__)

# (connect_timeout, read_timeout) — keeps connect bounded while allowing
# the Cloud Run endpoint a realistic read budget on cold-start turns.
_REQUEST_TIMEOUT = (2.0, 5.0)

# Resolve the Billing-owned token-accounting helper once at import time.
# `shared/` is bundled into both the API container (via api/Dockerfile) and
# the Agent Engine deployment (via extra_packages in deploy_ken_e.py /
# deploy_with_sys_version.py), so this import works in all runtime contexts.
# Falls back gracefully: token counters zero-fill rather than blocking turns.
try:
    from shared.token_accounting import (
        extract_billable_tokens as _extract_billable_tokens,
    )
except ImportError:
    logger.error(
        "token_accounting module not found; token counters will be zero-filled",
        extra={"error_id": "CHAT_TOKEN_ACCOUNTING_MISSING"},
    )
    _extract_billable_tokens = None  # type: ignore[assignment]

# Resolve TurnDelta — same fallback pattern as token_accounting above.
try:
    from shared.turn_delta import TurnDelta
except ImportError:
    logger.error(
        "turn_delta module not found; _build_turn_delta will fall back to dict",
        extra={"error_id": "CHAT_TURN_DELTA_MISSING"},
    )
    TurnDelta = None  # type: ignore[assignment,misc]


def _mint_oidc_token(audience: str) -> str:
    """Fetch a short-lived Google OIDC token for the given audience."""
    return _google_id_token.fetch_id_token(GoogleRequest(), audience)


def _post_side_table_update(
    session_id: str,
    account_id: str,
    delta: dict[str, Any],
    idempotency_key: str,
) -> None:
    """Dispatch side-table POST fire-and-forget in a background daemon thread.

    ADK runs sync callbacks on the agent runtime's event loop; a blocking
    requests.post here would stall every chat turn. Dispatching to a daemon
    thread returns control to the event loop immediately.
    Failure is swallowed-and-logged inside _post_side_table_update_sync.
    """
    thread = threading.Thread(
        target=_post_side_table_update_sync,
        args=(session_id, account_id, delta, idempotency_key),
        daemon=True,
    )
    thread.start()


def _post_side_table_update_sync(
    session_id: str,
    account_id: str,
    delta: dict[str, Any],
    idempotency_key: str,
) -> None:
    """POST delta to the internal side-table update endpoint (blocking).

    Called from a background daemon thread by _post_side_table_update.
    Non-blocking on failure: all exceptions are caught and logged.
    """
    api_url = os.getenv("CHAT_INTERNAL_API_URL", "").rstrip("/")
    audience = os.getenv("CHAT_INTERNAL_API_AUDIENCE", "") or api_url
    if not api_url:
        logger.warning("CHAT_INTERNAL_API_URL not set; side-table update skipped")
        return

    endpoint = f"{api_url}/api/v1/internal/chat/side-table/update"
    try:
        token = _mint_oidc_token(audience)
        resp = requests.post(
            endpoint,
            json={
                "session_id": session_id,
                "account_id": account_id,
                "delta": delta,
                "idempotency_key": idempotency_key,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=_REQUEST_TIMEOUT,
        )
        if resp.status_code == 409:
            # 409 is expected for duplicate idempotency keys; not a warning.
            logger.debug(
                "Side-table update duplicate (idempotent): session=%r key=%r",
                session_id,
                idempotency_key,
            )
        elif 400 <= resp.status_code < 500:
            logger.warning(
                "Side-table update rejected (4xx=%d) for session=%r: %s",
                resp.status_code,
                session_id,
                resp.text[:200],
                extra={
                    "error_id": "CHAT_SIDE_TABLE_CLIENT_ERROR",
                    "session_id": session_id,
                },
            )
        elif resp.status_code >= 500:
            logger.error(
                "Side-table update server error (5xx=%d) for session=%r: %s",
                resp.status_code,
                session_id,
                resp.text[:200],
                extra={
                    "error_id": "CHAT_SIDE_TABLE_SERVER_ERROR",
                    "session_id": session_id,
                },
            )
    except Exception as exc:
        logger.warning(
            "Side-table update failed (non-blocking): %s",
            exc,
            extra={
                "error_id": "CHAT_SIDE_TABLE_NETWORK_ERROR",
                "session_id": session_id,
            },
        )


def _isoformat_sentinel(dt: datetime) -> dict[str, str]:
    """Return the {"_isoformat": "..."} wire sentinel for a datetime value.

    The internal endpoint's inline sentinel reconstruction converts this back to a
    datetime object before calling Firestore, ensuring TIMESTAMP type storage.
    """
    return {"_isoformat": dt.isoformat()}


def _build_turn_delta(events: list[Any], now: datetime) -> TurnDelta:
    """Build a typed TurnDelta from this turn's ADK events.

    Returns a TurnDelta whose .to_wire_dict() produces the HTTP wire format
    and whose .to_firestore_delta() produces Firestore-native types.

    Mirrors SessionTurnAccumulator.build_delta() but outputs a typed model
    instead of an untyped dict.
    """
    input_tokens = 0
    output_tokens = 0
    reasoning_tokens = 0
    tool_call_count = 0
    message_count = 0
    final_text = ""
    _token_extract_errors = 0

    for event in events:
        if _extract_billable_tokens is not None:
            try:
                counts = _extract_billable_tokens(event)
                input_tokens += counts.input
                output_tokens += counts.output
                reasoning_tokens += counts.reasoning
            except Exception as _tok_err:
                _token_extract_errors += 1
                logger.debug("Token extraction failed for event: %s", _tok_err)

        # Count function calls using the real ADK Event API.
        _get_fn_calls = getattr(event, "get_function_calls", None)
        if callable(_get_fn_calls):
            tool_call_count += len(_get_fn_calls() or [])

        if getattr(event, "author", None) in ("user", "model"):
            message_count += 1

        # Extract final-response text using the real ADK Event API.
        _is_final = getattr(event, "is_final_response", None)
        if callable(_is_final) and _is_final():
            _content = getattr(event, "content", None)
            if _content is not None:
                _parts = getattr(_content, "parts", None) or []
                final_text = "".join(
                    getattr(_p, "text", None) or ""
                    for _p in _parts
                    if getattr(_p, "text", None)
                )

    if _token_extract_errors:
        logger.warning(
            "Token extraction failed for %d event(s) in this turn; counts may be under-reported",
            _token_extract_errors,
        )

    turn_tokens = input_tokens + output_tokens + reasoning_tokens

    return TurnDelta(
        last_agent_stopped_at=now,
        updated_at=now,
        last_agent_message_at=now,
        input_tokens_increment=input_tokens,
        output_tokens_increment=output_tokens,
        reasoning_tokens_increment=reasoning_tokens,
        tool_call_count=tool_call_count,
        message_count=message_count,
        current_context_tokens=turn_tokens,
        last_message_preview=final_text[:160],
    )


def chat_before_agent_callback(
    callback_context: CallbackContext,
) -> types.Content | None:
    """Stamp last_agent_started_at on the side-table. Root-only.

    Returns None so the agent proceeds normally.
    """
    try:
        invocation_context = getattr(callback_context, "_invocation_context", None)
        if invocation_context is None:
            return None

        # Root-only guard (AC-19)
        agent = getattr(invocation_context, "agent", None)
        if agent is not None and getattr(agent, "parent_agent", None) is not None:
            return None

        session_id = _extract_session_id(invocation_context)
        if not session_id or session_id.startswith("pending_"):
            return None

        state = _extract_state(callback_context)
        account_id = state.get("account_id", "")
        if not account_id:
            return None

        invocation_id = getattr(invocation_context, "invocation_id", None)
        if invocation_id is None:
            logger.warning(
                "chat_before_agent_callback: invocation_id is None; idempotency key will be non-stable"
            )
            invocation_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        now_sentinel = _isoformat_sentinel(now)

        _post_side_table_update(
            session_id=session_id,
            account_id=account_id,
            delta={
                "last_agent_started_at": now_sentinel,
                "updated_at": now_sentinel,
            },
            idempotency_key=f"{session_id}:before-agent:{invocation_id}",
        )
    except Exception:
        logger.warning(
            "chat_before_agent_callback failed (non-blocking)", exc_info=True
        )
    return None


def chat_after_agent_callback(
    callback_context: CallbackContext,
) -> types.Content | None:
    """Flush full per-turn delta to the side-table. Root-only.

    Gathers events for this invocation from session.events, builds the delta
    via _build_turn_delta, and POSTs it to the internal side-table endpoint.

    Returns None so the agent proceeds normally.
    """
    try:
        invocation_context = getattr(callback_context, "_invocation_context", None)
        if invocation_context is None:
            return None

        # Root-only guard (AC-19)
        agent = getattr(invocation_context, "agent", None)
        if agent is not None and getattr(agent, "parent_agent", None) is not None:
            return None

        session_id = _extract_session_id(invocation_context)
        if not session_id or session_id.startswith("pending_"):
            return None

        state = _extract_state(callback_context)
        account_id = state.get("account_id", "")
        if not account_id:
            return None

        invocation_id = getattr(invocation_context, "invocation_id", None)
        events = _gather_turn_events(invocation_context, invocation_id)

        now = datetime.now(timezone.utc)
        delta = _build_turn_delta(events, now)

        turn_id = invocation_id or str(uuid.uuid4())
        # Shared per-turn key: the /completions finally block flushes partial
        # token counts under the SAME key on a cancelled stream, so whichever
        # site lands first wins and the other is a 409 no-op — no double-count
        # of token increments (CH-PRD-01 §7 AC-8).
        _post_side_table_update(
            session_id=session_id,
            account_id=account_id,
            delta=delta.to_wire_dict(),
            idempotency_key=f"{session_id}:turn:{turn_id}",
        )
    except Exception:
        logger.warning("chat_after_agent_callback failed (non-blocking)", exc_info=True)
    return None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_session_id(invocation_context: Any) -> str:
    """Extract session_id from the ADK invocation context."""
    try:
        session = getattr(invocation_context, "session", None)
        if session is not None:
            sid = getattr(session, "id", None)
            if sid:
                return str(sid)
    except Exception:
        pass
    return ""


def _extract_state(callback_context: Any) -> dict[str, Any]:
    """Safely extract the session state dict from a callback context."""
    try:
        if hasattr(callback_context, "state") and hasattr(
            callback_context.state, "get"
        ):
            return callback_context.state  # type: ignore[return-value]
    except Exception:
        pass
    return {}


def _gather_turn_events(
    invocation_context: Any, invocation_id: str | None
) -> list[Any]:
    """Return events belonging to this invocation from session.events."""
    try:
        session = getattr(invocation_context, "session", None)
        if session is None or invocation_id is None:
            return []
        all_events = getattr(session, "events", None) or []
        return [
            e for e in all_events if getattr(e, "invocation_id", None) == invocation_id
        ]
    except Exception as exc:
        logger.debug("Could not gather turn events: %s", exc)
        return []
