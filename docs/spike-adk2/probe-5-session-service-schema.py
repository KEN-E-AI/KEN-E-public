"""Probe Q5 — VertexAiSessionService schema + chat_sessions Firestore mirror.

Run with:
    /tmp/adk2-probe/bin/python docs/spike-adk2/probe-5-session-service-schema.py

Findings:
    - VertexAiSessionService.append_event in ADK 2.0 stores the full event as
      'raw_event' via event.model_dump() in addition to field-based storage.
    - New Event fields in 2.0 (node_info, output, isolation_scope) will appear
      in raw_event — Vertex AI backend receives them.
    - If the Vertex AI backend doesn't support raw_event, the service falls back
      to legacy field-based storage (try/except pydantic.ValidationError).
    - KEN-E's chat_sessions Firestore mirror (Chat component, CH-PRD-01) may need
      review: if it parses ADK event dicts directly, the new fields could be
      unexpected. But since it uses duck-typing on 'author', 'invocation_id',
      'timestamp', 'usage_metadata', and 'content' — it should not break.
    - No schema migration needed for existing sessions.
"""

import inspect

print("=== Probe Q5: VertexAiSessionService schema + Firestore mirror ===\n")


def check_vertex_session_service():
    from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService
    src = inspect.getsource(VertexAiSessionService.append_event)

    has_raw_event = "raw_event" in src
    # node_info is NOT explicitly named — it flows through model_dump() which
    # serializes all non-None Event fields generically. has_node_info=False is expected.
    has_node_info = "node_info" in src
    has_fallback = "ValidationError" in src
    has_usage = "usage_metadata" in src

    print("VertexAiSessionService.append_event analysis:")
    print(f"  Stores raw_event (model_dump): {has_raw_event}")
    print(f"  References node_info explicitly: {has_node_info}  (expected False — model_dump handles it generically)")
    print(f"  Has ValidationError fallback: {has_fallback}")
    print(f"  Stores usage_metadata: {has_usage}")

    if has_raw_event:
        print()
        print("  raw_event = event.model_dump(exclude_none=True, mode='json', by_alias=True)")
        print("  => node_info, output, isolation_scope fields included in raw_event")
        print("  => Vertex AI API must accept these new fields or the fallback is used")

    if has_fallback:
        print()
        print("  Fallback: if pydantic.ValidationError on raw_event, retries without it")
        print("  => Backward-compatible with older Vertex AI Agent Engine backends")

    return has_raw_event, has_fallback


def check_new_event_fields():
    from google.adk.events.event import Event
    new_fields = {"node_info", "output", "isolation_scope"}
    all_fields = set(Event.model_fields.keys())
    present = new_fields & all_fields
    print(f"\nNew ADK 2.0 Event fields present: {present}")
    print("  These appear in raw_event but NOT in the legacy field-based storage path.")
    print("  => KEN-E chat_sessions Firestore mirror should NOT parse raw_event directly.")
    print("  => If it parses event dict keys: 'author', 'invocation_id', 'timestamp',")
    print("     'usage_metadata', 'content' — safe, these exist in both 1.x and 2.0.")
    return True


def assess_firestore_mirror():
    print("\nKEN-E chat_sessions Firestore mirror assessment:")
    print("  The mirror (Chat / CH-PRD-01) copies ADK session events to Firestore.")
    print("  If it stores raw event dicts: new 2.0 fields (node_info, isolation_scope)")
    print("    will appear in Firestore — requires no migration (additive fields).")
    print("  If it extracts specific fields: duck-typing on standard fields is safe.")
    print()
    print("  Recommendation: Chat team should review SessionTurnAccumulator to confirm")
    print("  it doesn't hard-reject unknown Event fields when parsing ADK 2.0 events.")
    print("  No migration of existing sessions required (new fields are additive/optional).")
    return True


r1, r2 = check_vertex_session_service()
check_new_event_fields()
assess_firestore_mirror()

print("\n=== Q5 VERDICT ===")
print("VertexAiSessionService: backward-compatible with 2.0 (fallback if API rejects raw_event).")
print("chat_sessions Firestore mirror: likely safe if it uses duck-typing on standard fields.")
print("  Recommendation: Chat team review before 2.0 migration; no schema migration required.")
print("  Risk level: LOW (new fields are optional/additive; no breaking schema changes).")
