#!/usr/bin/env python
"""Live-Gemini google_search smoke for a deployed Agent Engine (AH-PRD-15 §7.7 / §8).

THE GATE THE PROD 400 SLIPPED THROUGH. The AC #1-#6 unit/integration suites mock
the LLM, so they cannot catch a real-Gemini ``400 INVALID_ARGUMENT: "Multiple
tools are supported only when they are all search tools."`` This script drives a
REAL web-search turn against a deployed engine and asserts the isolated AgentTool
contract holds end-to-end. **Run it against STAGING and require a PASS before any
prod re-deploy of the chat tree** (AH-121 re-plan, mandatory process fix).

What it asserts
---------------
1. No streamed event carries an ``error_code`` (the prod incident was an
   ``error_code`` on the ``google_search`` node — this is the must-have check, and
   the only one that needs a live model).
2. A ``google_search`` function_call fires and a non-empty answer comes back.
   Grounding metadata is reported when detectable but not hard-required — its wire
   shape through Agent Engine isn't guaranteed, and check (1) is the real grounding
   guard (a non-grounded request wouldn't 400).
3. (needs Firestore read) the leaf's tokens reached the meter: the
   ``chat_sessions`` side-table delta EXCEEDS the caller-visible token usage seen on
   the stream by ~a leaf call. Because AgentTool drops the leaf's usage from the
   stream (#3984), a working capture makes the meter exceed the stream baseline;
   a broken capture makes them equal → this check FAILs. SKIPs (never silently
   PASSes) when the baseline can't be measured. The CI propagation test
   (``test_agent_tool_billing_integration.py``) and the §4 reconciliation are the
   authoritative billing checks; this is the live cross-check.

Prerequisites
-------------
* ``agent.google_search`` must be assigned to the root (or a specialist) in the
  target env's Firestore ``ken_e_chatbot.tool_ids`` — otherwise no search runs.
* ADC for the target project with Vertex AI + (optionally) Firestore read.

Usage
-----
    # Deploy first, then probe staging:
    cd app/adk && uv sync --frozen && uv run python deploy_ken_e.py --env staging
    uv run python -m app.adk.agents.scripts.smoke_google_search_live \\
        --env staging --account-id <prod-test-account> --user-id smoke

    # Pass an explicit engine + skip the billing check:
    uv run python -m app.adk.agents.scripts.smoke_google_search_live \\
        --engine projects/391472102753/locations/us-central1/reasoningEngines/<id> \\
        --no-billing-check

Exit 0 = PASS (safe to consider the cutover gate's live check satisfied for this
env). Non-zero = FAIL — do NOT promote to prod.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any

# Per-env project + secret config (mirrors deploy_ken_e.py blocks).
_ENV_PROJECT = {
    "dev": "ken-e-dev",
    "staging": "ken-e-staging",
    "production": "ken-e-production",
    "prod": "ken-e-production",
}
_LOCATION = "us-central1"
_ENGINE_ID_SECRET = "ken-e-engine-id"
_DEFAULT_QUERY = (
    "Use web search: what did Google announce about Gemini this week? "
    "Cite your sources."
)


def _resolve_engine(env: str, explicit: str | None) -> str:
    """Return the engine resource name — explicit arg wins, else the env secret."""
    if explicit:
        return explicit
    from google.cloud import secretmanager

    project = _ENV_PROJECT[env]
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project}/secrets/{_ENGINE_ID_SECRET}/versions/latest"
    value = client.access_secret_version(request={"name": name}).payload.data.decode()
    # The secret may hold a bare id or a full resource name.
    if value.startswith("projects/"):
        return value
    return f"projects/{project}/locations/{_LOCATION}/reasoningEngines/{value}"


def _event_error_code(event: Any) -> str | None:
    """Return an error_code from a streamed event (dict or object), if any."""
    if isinstance(event, dict):
        return event.get("error_code") or event.get("errorCode")
    return getattr(event, "error_code", None) or getattr(event, "errorCode", None)


def _event_has_search_call(event: Any) -> bool:
    """True if the event carries a function_call to the ``google_search`` AgentTool.

    This is the "the search tool was dispatched" signal — distinct from grounding
    (see :func:`_event_has_grounding`). It does NOT prove grounding ran inside the
    leaf, only that the root/specialist invoked the tool.
    """
    if isinstance(event, dict):
        parts = ((event.get("content") or {}).get("parts")) or []
        for p in parts:
            fc = p.get("function_call") if isinstance(p, dict) else None
            if isinstance(fc, dict) and fc.get("name") == "google_search":
                return True
        return False
    get_fcs = getattr(event, "get_function_calls", None)
    if callable(get_fcs):
        return any(
            getattr(fc, "name", None) == "google_search" for fc in (get_fcs() or [])
        )
    return False


def _event_has_grounding(event: Any) -> bool:
    """True if the event carries grounding metadata (real web grounding ran).

    Looks for ADK/Gemini grounding fields (``grounding_metadata`` /
    ``grounding_chunks`` / ``web_search_queries``). Best-effort across wire shapes;
    a soft signal, since the exact field surfacing through Agent Engine's stream is
    not guaranteed — absence is reported, not failed.
    """
    keys = (
        "grounding_metadata",
        "groundingMetadata",
        "grounding_chunks",
        "web_search_queries",
    )
    if isinstance(event, dict):
        blob = event
        return any(k in str(blob) for k in keys)
    return any(getattr(event, k, None) for k in ("grounding_metadata",)) or any(
        k in repr(event) for k in keys
    )


def _event_usage_total(event: Any) -> int:
    """Sum prompt+candidates+thoughts tokens from an event's usage_metadata.

    This is the CALLER-visible usage (root/specialist) on the outer stream — the
    isolated leaf's usage is dropped from the stream by the AgentTool inner runner
    (#3984), which is why the billing check compares the meter delta to this baseline.
    Returns 0 when no usage is present or the shape is unreadable.
    """
    usage: Any = None
    if isinstance(event, dict):
        usage = event.get("usage_metadata") or event.get("usageMetadata")
    else:
        usage = getattr(event, "usage_metadata", None)
    if usage is None:
        return 0

    def _get(obj: Any, *names: str) -> int:
        for n in names:
            v = obj.get(n) if isinstance(obj, dict) else getattr(obj, n, None)
            if v:
                return int(v)
        return 0

    return (
        _get(usage, "prompt_token_count", "promptTokenCount")
        + _get(usage, "candidates_token_count", "candidatesTokenCount")
        + _get(usage, "thoughts_token_count", "thoughtsTokenCount")
    )


def _event_text(event: Any) -> str:
    """Best-effort extraction of streamed answer text from a wire event."""
    if isinstance(event, dict):
        content = event.get("content") or {}
        parts = content.get("parts") if isinstance(content, dict) else None
        if parts:
            return "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    return ""


def _read_side_table_total(
    project: str, account_id: str, session_id: str
) -> int | None:
    """Return cumulative billed tokens for a session, or None if unreadable."""
    try:
        from google.cloud import firestore

        db = firestore.Client(project=project)
        doc = (
            db.collection("accounts")
            .document(account_id)
            .collection("chat_sessions")
            .document(session_id)
            .get()
        )
        if not doc.exists:
            return None
        d = doc.to_dict() or {}
        return int(
            d.get("input_tokens_total", 0)
            + d.get("output_tokens_total", 0)
            + d.get("reasoning_tokens_total", 0)
        )
    except Exception as exc:  # pragma: no cover - best-effort
        print(f"  (billing check skipped: side-table unreadable: {exc})")
        return None


def run_smoke(
    *,
    env: str,
    engine_name: str,
    account_id: str,
    user_id: str,
    query: str,
    billing_check: bool,
) -> int:
    import vertexai

    project = _ENV_PROJECT[env]
    vertexai.init(project=project, location=_LOCATION)
    print(f"[smoke] env={env} project={project}\n[smoke] engine={engine_name}")

    engine = vertexai.agent_engines.get(engine_name)
    session = engine.create_session(user_id=user_id)
    session_id = session["id"] if isinstance(session, dict) else session.id
    print(f"[smoke] session={session_id}")

    before_total = (
        _read_side_table_total(project, account_id, session_id)
        if billing_check
        else None
    )

    errors: list[str] = []
    saw_search_call = False
    saw_grounding = False
    stream_caller_tokens = 0
    answer_chunks: list[str] = []
    event_count = 0

    print(f"[smoke] query: {query!r}\n[smoke] streaming ...")
    for event in engine.stream_query(
        user_id=user_id,
        session_id=session_id,
        message=query,
    ):
        event_count += 1
        code = _event_error_code(event)
        if code:
            errors.append(str(code))
            print(f"  !! error_code event: {code}: {repr(event)[:300]}")
        if _event_has_search_call(event):
            saw_search_call = True
        if _event_has_grounding(event):
            saw_grounding = True
        stream_caller_tokens += _event_usage_total(event)
        answer_chunks.append(_event_text(event))

    answer = "".join(answer_chunks).strip()
    print(
        f"[smoke] streamed {event_count} event(s); answer length={len(answer)}; "
        f"caller-visible tokens={stream_caller_tokens}; grounding seen={saw_grounding}"
    )

    # ---- Assertions -------------------------------------------------------
    ok = True

    # (1) The real 400 guard — the only check that needs a live model. This is
    # what the prod cutover missed.
    if errors:
        print(f"FAIL (1): {len(errors)} event(s) carried an error_code: {errors}")
        print(
            "  This is the prod incident shape — the search leaf's request "
            "carried a non-search tool. The AgentTool isolation is broken."
        )
        ok = False
    else:
        print("PASS (1): no event carried an error_code.")

    # (2) The search tool was dispatched and an answer came back. Grounding
    # metadata is reported when detectable but not hard-required (its wire shape
    # through Agent Engine is not guaranteed) — check (1) is the real grounding
    # guard since a non-grounded request would not 400 in the first place.
    if not saw_search_call:
        print(
            "FAIL (2a): no google_search function_call in the stream — is "
            "agent.google_search assigned in this env's tool_ids?"
        )
        ok = False
    elif not answer:
        print("FAIL (2b): the search tool ran but no answer text came back.")
        ok = False
    else:
        grounding_note = (
            "grounding metadata present"
            if saw_grounding
            else "grounding metadata NOT detected on the wire (soft — see check 1)"
        )
        print(
            f"PASS (2): google_search dispatched + answer returned ({grounding_note})."
        )

    # (3) Did the LEAF's tokens actually reach the meter? This must be able to FAIL
    # when the capture silently breaks — comparing the meter delta against the
    # caller-visible stream usage is what makes it non-vacuous: the leaf's usage is
    # dropped from the stream (#3984), so a working capture makes the meter EXCEED
    # the caller-visible total by ~a leaf call. SKIP (never silently PASS) when the
    # baseline can't be measured.
    if billing_check:
        # Give the fire-and-forget side-table POST a moment to land.
        time.sleep(5)
        after_total = _read_side_table_total(project, account_id, session_id)
        if before_total is None or after_total is None:
            print(
                "SKIP (3): billing side-table not readable; verify the meter delta "
                "manually (the CI propagation test + Weave-vs-meter §4 reconciliation "
                "are the authoritative billing checks)."
            )
        elif stream_caller_tokens == 0:
            print(
                "SKIP (3): could not read caller-visible usage off the stream, so the "
                "leaf-vs-caller baseline can't be established; rely on §4 reconciliation."
            )
        else:
            meter_delta = after_total - before_total
            leaf_estimate = meter_delta - stream_caller_tokens
            # A gemini-2.5-flash grounded-search leaf call bills well over this floor
            # (instruction + query input + the grounded answer output); the floor only
            # absorbs minor stream-vs-session aggregation noise.
            leaf_floor = 50
            if leaf_estimate >= leaf_floor:
                print(
                    f"PASS (3): meter delta {meter_delta} exceeds caller-visible "
                    f"{stream_caller_tokens} by {leaf_estimate} (~the search leaf) — "
                    "the leaf usage_metadata reached the meter."
                )
            else:
                print(
                    f"FAIL (3): meter delta {meter_delta} vs caller-visible "
                    f"{stream_caller_tokens} → leaf estimate {leaf_estimate} < {leaf_floor}. "
                    "The leaf's tokens are NOT reaching the meter — the #3984 capture "
                    "(after_model_callback / ContextVar) is broken."
                )
                ok = False

    print("\n=== SMOKE RESULT:", "PASS ===" if ok else "FAIL ===")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default="staging", choices=sorted(_ENV_PROJECT))
    parser.add_argument(
        "--engine",
        default=None,
        help="Explicit engine resource name (else read from secret).",
    )
    parser.add_argument(
        "--account-id",
        default="",
        help="Prod-test account for the side-table billing check.",
    )
    parser.add_argument("--user-id", default="ah121-smoke")
    parser.add_argument("--query", default=_DEFAULT_QUERY)
    parser.add_argument(
        "--no-billing-check",
        dest="billing_check",
        action="store_false",
        help="Skip the side-table token-delta check (no Firestore read).",
    )
    args = parser.parse_args(argv)

    if args.billing_check and not args.account_id:
        print("NOTE: --account-id not set; disabling the billing check.")
        args.billing_check = False

    engine_name = _resolve_engine(args.env, args.engine)
    return run_smoke(
        env=args.env,
        engine_name=engine_name,
        account_id=args.account_id,
        user_id=args.user_id,
        query=args.query,
        billing_check=args.billing_check,
    )


if __name__ == "__main__":
    sys.exit(main())
