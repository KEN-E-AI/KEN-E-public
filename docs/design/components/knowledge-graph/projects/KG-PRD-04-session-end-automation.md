# KG-PRD-04 — Session-End as a System-Triggered Automation

**Status:** Ready for development (after KG-PRDs 1, 2, 3 + Calendar PRDs 1–6 + Automations PRDs 1–7 all merge)
**Owner team:** Agent / ML + Backend (pair)
**Blocked by:** KG-PRDs 1, 2, 3; Calendar PRDs 1–6; Automations PRDs 1–7
**Parallel with:** KG-PRD-05 (same dev can ship both if scheduled)
**Estimated effort:** 5–7 days

---

## 1. Context

Today, anything the user surfaces in chat — a new pricing move, a competitor launch, a stakeholder change — is lost when the conversation ends. The next session starts cold. This PRD delivers the learning loop: a system that reviews completed chat sessions, extracts new facts, and updates the account's Neo4j knowledge base.

Rather than a bespoke Cloud Tasks pipeline, session-end **rides on the Automations platform** (Calendar + Automations PRDs). One seeded system-level `ProjectPlan` (`is_system=true`) with two tasks — `session_reviewer` (LLM) and `session_applier` (deterministic) — represents the workflow. A daily Cloud Scheduler sweeper finds idle sessions and triggers one `PlanRun` per session via the Automations manual-trigger endpoint. The Automations orchestrator, artifact system, HITL halt, and Outputs tab do the heavy lifting.

Destructive changes (deletes, updates to user-written fields) halt as `PlanRun.status="halted_for_human"`, surfacing in the Automation Details Outputs tab for human review. Additive changes (new Observations, new relationships, supersedes within the same session) auto-apply.

## 2. Scope

### In scope
- `api/scripts/seed_session_end_template.py` — one-time Firestore write of the Session-End Review ProjectPlan (`is_system=true`, two tasks, no cron).
- `api/src/kene_api/routers/internal/session_sweeper.py` — new `POST /api/v1/internal/scheduler/process-idle-sessions` endpoint (OIDC auth, same pattern as A-PRD-2 scheduler).
- Cloud Scheduler job (Terraform) firing once daily to hit the sweeper.
- Two ADK agents in `app/adk/agents/session_end_agent/`:
  - `reviewer.py` — LLM agent; reads transcript + KG via KG-PRD-03 tools; emits a `SessionReview` Pydantic payload; saves it as a `TaskArtifact` via A-PRD-3's `attach_task_artifact` tool.
  - `applier.py` — deterministic Python wrapped as an agent task; downloads the artifact, routes each proposed change by autonomy rules, applies via `GraphSyncService` (KG-PRD-02) or halts the task for HITL.
- `review_session(session_id, account_id, transcript) -> SessionReview` as a **pure function** core so the reviewer logic can be invoked from any orchestrator (future-proofing against the Automations platform slipping).
- Embedding generation for created Observations (reuse `EmbeddingGenerator` from strategy agent).
- Registration of the session-end agents with the ADK agent registry so the Automations orchestrator's agent-dispatch path can find them.
- Unit + integration tests including HITL halt / resume cycle.

### Out of scope
- Bespoke Cloud Tasks pipeline (explicitly rejected in favor of Automations).
- `Proposal` node in Neo4j (explicitly rejected — review queue is `PlanRun.status="halted_for_human"`).
- Any change to the ADK session retention window (Vertex AI defaults).
- End-of-turn triggering — only the daily idle sweeper is in scope.
- Cost controls / quota enforcement beyond what the Automations platform already provides.

## 3. Dependencies

> **Revised 2026-04-20** — Consumed Firestore collections (`project_plans`, `plan_runs`, artifact subcollection) follow the Shape B layout (`accounts/{account_id}/{resource}/...`). The PRD itself calls the Automations API and does not touch Firestore paths directly, but integrators should expect Shape B paths when debugging. See [Review 15 in DESIGN-REVIEW-LOG](../../../DESIGN-REVIEW-LOG.md#review-15-multi-tenant-data-model-shape--firestore-subcollections-shape-b--gcs-prefix-g1) for rationale.

**Hard blockers:**
- **KG-PRD-01:** `:KGNode`, constraints, vector index.
- **KG-PRD-02:** `Session` lifecycle (`touch_session`, `close_session`), `Observation` / `create_observation` / `supersede_observation`, provenance stamping.
- **KG-PRD-03:** read tools (`load_context_section`, `load_document`, `search_kb`, `list_observations`) that the reviewer consumes.
- **Calendar PRD-1:** `ProjectPlan`, `PlanTask`, `is_system` field, write-protection for system plans.
- **Calendar PRD-4:** orchestrator DAG dispatch, HITL `Awaiting Approval` semantics.
- **Calendar PRD-6:** Cloud Scheduler Terraform pattern + OIDC auth for internal endpoints.
- **A-PRD-1:** `PlanRun`, `inputs` field, `triggered_by="system"`.
- **A-PRD-2:** manual-trigger endpoint accepting `triggered_by="system"` + `inputs`, prompt template substitution.
- **A-PRD-3:** `TaskArtifact` persistence + `attach_task_artifact` agent tool + signed-URL download.
- **A-PRD-6:** Automation Details Outputs tab + HITL Mark Complete / Revision Requested on `is_system=true` runs.

**External:**
- `AgentEngineClient.get_conversation_history(session_id)` at `api/src/kene_api/routers/chat.py:1291` — transcript access.
- `EmbeddingGenerator` from `app/adk/agents/strategy_agent/embeddings.py`.

## 4. Data contract

### `SessionReview` — artifact payload

```python
class SessionReview(BaseModel):
    session_id: str
    account_id: str
    generated_at: datetime
    summary: str                              # 2–3 sentence LLM-generated session summary
    proposed_changes: list[ProposedChange]
    reviewer_notes: str | None = None         # anything the reviewer wants to flag


class ProposedChange(BaseModel):
    kind: Literal[
        "create_observation",
        "add_relationship",
        "supersede_observation",
        "update_node",
        "delete_node",
    ]
    # Filled based on kind:
    target_node_id: str | None = None          # node being updated/deleted/superseded/related
    node_type: str | None = None               # for create_observation / update_node
    subject: str | None = None                 # for create_observation
    statement: str | None = None               # for create_observation / supersede_observation
    confidence: Literal["high", "medium", "low"] | None = None
    fields: dict | None = None                 # for update_node (field -> new value)
    rel_type: str | None = None                # for add_relationship
    from_node_id: str | None = None            # for add_relationship
    to_node_id: str | None = None              # for add_relationship
    about_node_id: str | None = None           # for create_observation (optional)
    reasoning: str                             # LLM's explanation for the proposal
```

The artifact is saved as `proposal.json` via `attach_task_artifact(filename="proposal.json", content_base64=..., mime_type="application/json")`.

### Seeded ProjectPlan

```python
ProjectPlan(
    plan_id="kg-session-end-review",            # stable, hardcoded — seed script uses this
    account_id="_system",                        # sentinel account for system-owned templates
    title="Session-End Knowledge Graph Review",
    goal="Review a completed chat session and propose KB updates.",
    acceptance_criteria=[
        AcceptanceCriterion(description="Every new fact mentioned in the session is captured as an Observation"),
        AcceptanceCriterion(description="Destructive proposals halt for human review"),
        AcceptanceCriterion(description="Run completes within 3 minutes"),
    ],
    tasks=[
        PlanTask(
            task_id="reviewer",
            title="Review session transcript",
            description="Read the transcript for session {inputs.session_id} (account {inputs.account_id}). "
                        "Ground yourself in the current KB via load_context_section / search_kb / "
                        "list_observations as needed. Emit a SessionReview JSON artifact named "
                        "proposal.json listing every proposed change with reasoning and confidence.",
            assignee_type="agent",
            assignee_name="session_reviewer",
            depends_on=[],
        ),
        PlanTask(
            task_id="applier",
            title="Apply proposed changes",
            description="Download proposal.json from the upstream reviewer task. For each proposed "
                        "change, route by autonomy rules: additive + in-session → apply directly; "
                        "update-to-user-written or delete or cross-session supersede → halt this task "
                        "for human review with a clear revision_comment. Inputs: session {inputs.session_id}, "
                        "account {inputs.account_id}.",
            assignee_type="agent",
            assignee_name="session_applier",
            depends_on=["reviewer"],
        ),
    ],
    save_as_automation=True,
    is_system=True,
    recurrence_cron=None,                       # no schedule; runs are manually triggered
    is_active=True,
)
```

The `_system` account id is a sentinel to hold platform-owned ProjectPlans. Calendar PRD-1's write-protection rules (`is_system=true` → 403 on edit/delete) already protect it; the read endpoints naturally return it when queried with that account id (though users never query for it — the sweeper hardcodes the plan_id).

### Sweeper endpoint

`POST /api/v1/internal/scheduler/process-idle-sessions`

Request (optional `now` for testability):
```json
{"now": "2026-04-20T09:00:00Z"}
```

Response:
```json
{
  "checked_at": "2026-04-20T09:00:00Z",
  "sessions_triggered": [
    {"account_id": "acc_abc", "session_id": "sess_xyz", "run_id": "run_123"}
  ],
  "session_count": 1
}
```

Auth: OIDC with the same service account that runs the A-PRD-2 scheduler tick (Calendar PRD-6 established the auth pattern).

### Cloud Scheduler config

- Schedule: `0 4 * * *` UTC — daily at 04:00 UTC (low-traffic window)
- Target: `POST /api/v1/internal/scheduler/process-idle-sessions`
- Auth: OIDC (same SA as A-PRD-2)
- Retry: 3 attempts, exponential backoff

## 5. Implementation outline

| Action | File |
|---|---|
| Create | `api/scripts/seed_session_end_template.py` |
| Create | `api/src/kene_api/routers/internal/session_sweeper.py` |
| Modify | `api/src/kene_api/main.py` — register internal router |
| Create | `deployment/terraform/cloud_scheduler_session_sweeper.tf` |
| Create | `app/adk/agents/session_end_agent/__init__.py` |
| Create | `app/adk/agents/session_end_agent/reviewer.py` |
| Create | `app/adk/agents/session_end_agent/applier.py` |
| Create | `app/adk/agents/session_end_agent/models.py` — `SessionReview`, `ProposedChange` |
| Create | `app/adk/agents/session_end_agent/prompts.py` — reviewer prompt templates |
| Create | `app/adk/agents/session_end_agent/core.py` — `review_session()` pure function |
| Modify | `app/adk/agents/registry.py` — register `session_reviewer` and `session_applier` agent names for the Automations dispatcher |
| Create | `api/tests/unit/test_session_sweeper.py` |
| Create | `app/adk/agents/session_end_agent/test_applier_routing.py` — autonomy-rule unit tests |
| Create | `app/adk/agents/session_end_agent/test_review_session.py` — `review_session()` pure-function tests with canned transcripts |
| Create | `tests/integration/test_session_end_e2e.py` — full HITL halt + resume cycle |

### Sweeper algorithm

```python
# api/src/kene_api/routers/internal/session_sweeper.py

@router.post("/process-idle-sessions")
async def process_idle_sessions(body: SweeperRequest, _=Depends(oidc_auth)) -> SweeperResponse:
    now = body.now or datetime.now(timezone.utc)
    idle_threshold = now - timedelta(hours=24)

    # 1. Find idle Sessions across all accounts
    query = """
        MATCH (s:Session)
        WHERE s.status = 'active' AND s.last_message_at < $threshold
        RETURN s.session_id AS session_id, s.account_id AS account_id
        LIMIT 500
    """
    rows = await neo4j_service.execute_query(query, {"threshold": idle_threshold})

    triggered = []
    for row in rows:
        session_id = row["session_id"]
        account_id = row["account_id"]
        # 2. Flip status to 'processing' atomically — idempotency guard
        flipped = await graph_sync_service.claim_session_for_processing(session_id)
        if not flipped:
            continue  # another sweeper already claimed it

        # 3. Trigger a run via the Automations manual-trigger endpoint
        try:
            run = await automations_client.trigger_run(
                account_id=SYSTEM_ACCOUNT_ID,        # "_system"
                plan_id="kg-session-end-review",
                body={
                    "triggered_by": "system",
                    "inputs": {
                        "session_id": session_id,
                        "account_id": account_id,
                    },
                },
            )
            triggered.append({
                "account_id": account_id,
                "session_id": session_id,
                "run_id": run.run_id,
            })
        except Exception as e:
            # On trigger failure: revert Session.status to 'active' so next sweep retries
            await graph_sync_service.revert_session_claim(session_id)
            logger.exception(f"Failed to trigger run for session {session_id}: {e}")

    return SweeperResponse(checked_at=now, sessions_triggered=triggered, session_count=len(triggered))
```

Claim method uses an atomic Cypher update:
```cypher
MATCH (s:Session {session_id: $session_id})
WHERE s.status = 'active'
SET s.status = 'processing'
RETURN s.session_id IS NOT NULL AS claimed
```

### `review_session` pure function

```python
# app/adk/agents/session_end_agent/core.py

async def review_session(
    session_id: str,
    account_id: str,
    transcript: list[ChatMessage],
    kb_read_tools: KBReadTools,                   # injected, for testability
    llm_client: LLMClient,                        # injected
) -> SessionReview:
    """Review a completed session and return a structured list of proposed KB changes.

    Pure in the sense that it has no side effects on the KB, the filesystem, or
    any external service beyond the LLM call + injected KB read tools. Safe to
    call from any orchestrator context.
    """
    # 1. Build grounding context: pass the transcript + (optionally) a pre-loaded
    #    context summary from kb_read_tools.load_context_section for relevant domains.
    # 2. Prompt the LLM to produce a SessionReview (structured output via Pydantic).
    # 3. Validate the output; return.
```

The agent wrapper in `reviewer.py` is a thin adapter: it runs inside the Automations dispatch context, extracts `session_id` + `account_id` from `run.inputs`, fetches the transcript via `AgentEngineClient.get_conversation_history()`, calls `review_session`, and calls `attach_task_artifact("proposal.json", ...)`.

### Applier routing rules

```python
# app/adk/agents/session_end_agent/applier.py — core routing

def route_change(
    change: ProposedChange,
    run_session_id: str,
) -> Literal["apply", "halt"]:
    """Return 'apply' if the change is safe to auto-apply, 'halt' for HITL review."""
    if change.kind == "delete_node":
        return "halt"

    if change.kind in ("create_observation", "add_relationship"):
        return "apply"

    if change.kind == "supersede_observation":
        # Safe to apply only if the Observation being superseded was written in THIS session
        existing = fetch_node(change.target_node_id)
        if existing.source_session_id == run_session_id:
            return "apply"
        return "halt"

    if change.kind == "update_node":
        existing = fetch_node(change.target_node_id)
        if existing.last_updated_by_agent == "user":
            # User wrote this; check age
            age = datetime.now(timezone.utc) - existing.last_modified
            if age < timedelta(days=7):
                return "halt"
        return "apply"

    return "halt"  # unknown kind — fail closed
```

Apply path: invoke the appropriate `GraphSyncService` method (with `session_id=run_session_id` so provenance is stamped).

Halt path: the applier agent calls its `update_task_status` tool (provided by the Automations orchestrator) with `status="Awaiting Approval"` and a `revision_comment` that names the pending change and its reasoning. The `PlanRun` flips to `halted_for_human` (per Calendar PRD-4 / A-PRD-4 semantics). User reviews in the Automation Details Outputs tab (A-PRD-6) and either Marks Complete (approve) or Revision Requested (reject).

On approve: the applier task re-runs — but this time the routing is bypassed for the halted change (the human approved it), so it applies directly. Implementation: use a small run-scoped `approved_changes: set[int]` (indexes into `proposed_changes`) stored in the `PlanRun.task_states[applier].completion_notes` or similar — or simpler, re-read the proposal artifact and the current halt state and only apply the specific change that was approved.

Detail: if the reviewer proposed 5 changes and 2 halt, the applier applies 3 immediately, halts with both pending. On approve, the applier resumes and applies both. On Revision Requested with feedback, the applier *re-runs the reviewer task* via a revision-iteration dispatch (Calendar PRD-4's revision loop), capped at 5 iterations.

### Reviewer prompt (structure)

```
You are a knowledge graph curator. Your job is to review a completed chat conversation
and propose updates to the account's knowledge base so the next session is better informed.

Session: {inputs.session_id}
Account: {inputs.account_id}

Current KB snapshot (executive summary):
{kb_context_summary}

Conversation transcript:
{transcript}

Using the read tools (load_context_section, load_document, search_kb, list_observations),
verify what is already known before proposing changes. Propose only facts that are
genuinely new or updated compared to the KB. For each proposed change, include:

  - kind (create_observation / add_relationship / supersede_observation / update_node / delete_node)
  - the required fields for that kind
  - reasoning: a 1-2 sentence justification
  - confidence: high / medium / low

Rules:
  - Prefer Observations for free-form facts ("The CMO mentioned...")
  - Propose delete_node or update_node on canonical strategy nodes only when the conversation
    unambiguously retires or changes something.
  - If unsure, propose an Observation with confidence="low" instead of a destructive change.

Return a SessionReview object.
```

Reviewer uses structured output (Pydantic) — if the model is Gemini/ADK, set `output_schema=SessionReview`. If not, parse + validate the text response.

### Agent registration

In `app/adk/agents/registry.py`:
```python
AGENTS["session_reviewer"] = build_session_reviewer_agent()
AGENTS["session_applier"] = build_session_applier_agent()
```

The Automations task dispatcher (A-PRD-2 / Calendar PRD-4) looks up `assignee_name` against this registry.

### Embeddings for new Observations

After `create_observation` lands, generate the embedding asynchronously (fire-and-forget via a BackgroundTask) so the applier doesn't block. Use the existing `EmbeddingGenerator` with the `RETRIEVAL_DOCUMENT` task. An Observation with `embedding=null` is simply not returned by `search_kb` (per KG-PRD-03) until it catches up.

## 6. API contract

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/internal/scheduler/process-idle-sessions` | OIDC (daily sweeper SA) | Daily tick |

No user-facing endpoints. The Automation Details page (A-PRD-6) is the user's review surface, reached via the Automations List page (filtered to `is_system=false` in normal use; operators reach the system automation via direct URL).

## 7. Acceptance criteria

1. Running `api/scripts/seed_session_end_template.py` creates the `kg-session-end-review` ProjectPlan in Firestore with `is_system=true`, `save_as_automation=true`, the two tasks, and an audit entry. Re-running the script is idempotent.
2. The Session-End Review template does not appear on the Automations List page (A-PRD-5) when a standard user visits `/workflows`.
3. Visiting `/workflows/automations/kg-session-end-review` directly renders the page in read-only mode with the banner, no Run Now / Delete buttons, and the DAG visualization.
4. Given a fixture account with a Session whose `status="active"` and `last_message_at < now - 24h`, calling the sweeper endpoint triggers exactly one `PlanRun` for that session with `triggered_by="system"` and `inputs={"session_id": ..., "account_id": ...}`. The `Session.status` flips to `processing`.
5. The sweeper claims each idle session atomically — two concurrent sweeper ticks trigger exactly one run (not two) per session.
6. A canned transcript where the user says "Our CMO is pivoting us to usage-based pricing next quarter" produces:
   - A `PlanRun` with `status="complete"`
   - A `TaskArtifact` (`proposal.json`) attached to the reviewer task
   - One `Observation` in Neo4j with `subject`-like "pricing model" / "pricing pivot", `statement` containing the quote, `confidence` ∈ {medium, high}, `:OBSERVED_IN` edge to the Session, `valid_from` set, `embedding` populated (within a bounded delay).
7. A canned transcript where the user says "Delete the old Product X, we discontinued it last quarter" produces:
   - `PlanRun.status="halted_for_human"`
   - `proposal.json` saved with a `delete_node` proposed change
   - No Product deleted in Neo4j
   - The applier task in `Awaiting Approval` state with a clear `revision_comment`
   - Deep-linkable via `/workflows/automations/kg-session-end-review?run={run_id}&task=applier` from the notification
8. Marking the applier task Complete via the A-PRD-6 UI applies the halted delete, flips the run to `complete`, and the product is removed from Neo4j.
9. Marking Revision Requested with a comment ("that's not right, the product is still live") re-dispatches the reviewer, which produces a new `proposal.json` and does NOT re-propose the delete. (Verify via a second fixture that's engineered to respond to feedback; at worst, verify the revision round-trip happens and bypass the content check.)
10. Autonomy routing:
    - `create_observation` → auto-applies
    - `add_relationship` (whitelisted rel types) → auto-applies
    - `supersede_observation` of a same-session Observation → auto-applies
    - `update_node` of a field last-updated-by-user within 7 days → halts
    - `update_node` of a field last-updated-by-user > 7 days ago → auto-applies
    - `delete_node` → always halts
    - `supersede_observation` of a cross-session Observation → halts
11. `review_session` (pure function) can be called from a test harness with fixture transcripts + a mocked `kb_read_tools` and returns a valid `SessionReview` — the Automations platform dependency is not required for unit testing.
12. Re-processing an already-processed Session (`status="processed"`) is a no-op — the sweeper skips it.
13. The daily Cloud Scheduler job exists in Terraform, authenticates with OIDC, and is visible in the GCP console.
14. Multi-tenant: two Sessions belonging to different accounts, both idle, both get processed; neither's Observations leak into the other's KB.

## 8. Test plan

**Unit tests:**

- `test_applier_routing.py` — one test per autonomy rule with a mocked `fetch_node`. Covers all 7 cases in criterion #10.
- `test_review_session.py` — `review_session()` with 5 canned transcripts:
  1. Additive only (one new pricing observation)
  2. Destructive (proposed delete)
  3. Update to a user-written field < 7 days old
  4. Cross-session supersede
  5. Mixed (one additive + one destructive)
  Assert structure of returned `SessionReview`; exact content validation is brittle, so check `kind` distribution + presence of key fields.
- `test_session_sweeper.py` — mock Neo4j + Automations client. Idle detection, atomic claim, idempotent re-run (no double fire), failure path reverts claim.
- `test_seed_script.py` — seed script creates the plan once; re-run is no-op; idempotent.

**Integration tests:**

- `test_session_end_e2e.py` — full cycle against live services (Neo4j + Firestore emulator + a stubbed Automations orchestrator or the real one if test environment supports it):
  - Seed account with Session idle > 24h
  - POST to the sweeper endpoint
  - Poll the created PlanRun until terminal
  - Assert additive outcome (Observation in Neo4j)
- `test_session_end_halt_resume.py`:
  - Seed account, trigger a run whose proposal includes a destructive change
  - Assert PlanRun halts; artifact is readable via the Outputs tab endpoint
  - PATCH the applier task Complete
  - Assert the delete lands and the run completes
- `test_session_end_revision.py`:
  - Same setup; PATCH the applier task Revision Requested
  - Assert reviewer re-runs (revision_iteration increments)
- `test_session_end_multi_tenant.py`:
  - Two accounts with idle sessions
  - Sweep triggers runs for both
  - Assert no cross-account writes

**Smoke test (pre-merge):**

- On staging: seed a single test account, have a real chat of 4–5 turns with one clearly new fact, close the conversation, manually trigger the sweeper, verify the Observation appears in Neo4j and in `list_observations()`.

## 9. Risks & open questions

| Risk / question | Mitigation |
|---|---|
| Reviewer hallucinates facts not in the transcript | Structured-output prompt with the transcript quoted verbatim; the applier rejects proposals whose `reasoning` is empty or obviously generic. Confidence-scoring gives the routing layer a hedge. If a real hallucination rate > 5%, add a second-pass critic agent or tune the prompt. |
| Transcript retrieval fails (Vertex AI session aged out > 7 days) | Sweeper runs daily, so a session idle > 24h is still well within the window. Log and skip if retrieval fails; the Session's `status="processing"` will be reverted by a follow-up: if no run completes within 2 hours, a secondary sweeper resets to `active` — or simpler, set `status="failed"` with a reason. Document. |
| Many concurrent idle sessions overwhelm the Automations platform | Sweeper LIMITs to 500 sessions per tick. Measure. If this ever becomes constraining, split into smaller batches or add a rate-limit. |
| Approved halt applies a stale proposal if the KB moved | When the user clicks Complete, the applier re-fetches target nodes before writing. If the target has changed materially (different `last_modified`), the applier halts again with a fresh revision_comment. Document. |
| Embedding generation lag affects downstream `search_kb` | Accepted — an Observation created at time T is semantically searchable at time T+N. Document. |
| `_system` sentinel account accidentally exposed to users | Calendar PRD-1 write-protection + A-PRD-5 list filter + A-PRD-6 read-only mode all gate this. Add an explicit integration test that a non-admin user cannot create, edit, or delete the seeded template. |
| The applier's "re-run to apply approved halts" logic is fragile | Implementation choice: instead of re-reading artifact + halt state, have the applier on revision #2 apply **every** non-halt-eligible change (same routing) — on a second pass, any changes the human approved via Complete are no longer halt-eligible because their routing conditions resolved. Tighter than storing approval state. Validate via the halt-resume integration test. |
| PRD-6 / PRD-5 integration not yet implemented when KG-PRD-4 is ready to test | Mock the Automations orchestrator + UI in tests; gate merge on actual Automations shipping. Phases 1, 2, 3 (KG) can ship first without this. |
| Revision loop eats tokens | Cap at 5 iterations (matches Calendar PRD-4 default). After cap, mark the run `failed` with a reason. |

## 10. Reference

- Parent plan: [`the-purpose-of-neo4j-clever-frost.md`](../../../../../Users/kenwilliams/.claude/plans/the-purpose-of-neo4j-clever-frost.md) §Phase 4.
- KG-PRD-01, 2, 3 (direct dependencies).
- Calendar PRDs 1, 4, 6 + Automations PRDs 1, 2, 3, 4, 6 (platform dependencies — see §3).
- `api/src/kene_api/routers/chat.py:1291` — transcript access.
- `app/adk/agents/strategy_agent/embeddings.py` — embedding reuse.
- CLAUDE.md rules in scope: C-1, C-4; PY-1, PY-2, PY-3, PY-7; T-1, T-3, T-4, T-6.
