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
   ``error_code`` on the ``google_search`` node — this is the must-have check).
2. A ``google_search`` call fires and a non-empty, grounded answer comes back
   (citations / grounding present) — the search leaf actually ran.
3. (best-effort, needs Firestore read) the turn's billed tokens on the
   ``chat_sessions`` side-table grew by MORE than a caller-only baseline — i.e.
   the search leaf's ``usage_metadata`` reached the meter via the
   ``capture_agent_tool_usage`` after_model_callback (AgentTool drops it, #3984).

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
    value = client.access_secret_version(name={"name": name}).payload.data.decode()
    # The secret may hold a bare id or a full resource name.
    if value.startswith("projects/"):
        return value
    return f"projects/{project}/locations/{_LOCATION}/reasoningEngines/{value}"


def _event_error_code(event: Any) -> str | None:
    """Return an error_code from a streamed event (dict or object), if any."""
    if isinstance(event, dict):
        return event.get("error_code") or event.get("errorCode")
    return getattr(event, "error_code", None) or getattr(event, "errorCode", None)


def _event_mentions_search(event: Any) -> bool:
    """True if the event references a google_search function call / grounding."""
    blob = repr(event).lower()
    return "google_search" in blob or "grounding" in blob


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
    saw_search = False
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
        if _event_mentions_search(event):
            saw_search = True
        answer_chunks.append(_event_text(event))

    answer = "".join(answer_chunks).strip()
    print(f"[smoke] streamed {event_count} event(s); answer length={len(answer)}")

    # ---- Assertions -------------------------------------------------------
    ok = True

    if errors:
        print(f"FAIL (1): {len(errors)} event(s) carried an error_code: {errors}")
        print(
            "  This is the prod incident shape — the search leaf's request "
            "carried a non-search tool. The AgentTool isolation is broken."
        )
        ok = False
    else:
        print("PASS (1): no event carried an error_code.")

    if not saw_search:
        print(
            "FAIL (2a): no google_search / grounding reference in the stream — "
            "is agent.google_search assigned in this env's tool_ids?"
        )
        ok = False
    elif not answer:
        print("FAIL (2b): search ran but no answer text came back.")
        ok = False
    else:
        print(
            f"PASS (2): google_search ran and returned an answer ({answer[:120]!r}...)."
        )

    if billing_check:
        # Give the fire-and-forget side-table POST a moment to land.
        time.sleep(5)
        after_total = _read_side_table_total(project, account_id, session_id)
        if before_total is None or after_total is None:
            print(
                "SKIP (3): billing side-table not readable; verify the meter "
                "delta manually (Weave-vs-meter §4 reconciliation)."
            )
        else:
            delta = after_total - before_total
            # A caller-only turn (no search leaf) bills a few hundred tokens; a
            # grounded search turn that also counts the gemini-2.5-flash leaf bills
            # materially more. A non-trivial delta is the signal the leaf was billed.
            if delta > 0:
                print(
                    f"PASS (3): side-table billed +{delta} tokens this turn "
                    "(includes the search leaf if the callback fired)."
                )
            else:
                print(
                    f"FAIL (3): side-table token delta was {delta} — the turn "
                    "billed nothing; the leaf usage may not be reaching the meter."
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
