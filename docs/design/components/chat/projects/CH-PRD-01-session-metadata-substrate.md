# CH-PRD-01 — Session Metadata Substrate

**Status:** Not started
**Owner team:** Chat component team (backend + ADK)
**Blocked by:** [DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md) (Shape B convention + registry), [DM-PRD-05](../../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md) (`recursive_delete` covers `chat_sessions/*`), [FF-PRD-01](../../feature-flags/projects/FF-PRD-01-data-model-evaluation-api-backend-sdk.md) (backend feature-flag SDK)
**Parallel with:** none — substrate gates every sibling PRD
**Blocks:** CH-PRD-02, CH-PRD-03, CH-PRD-04, CH-PRD-05
**Estimated effort:** 5 days backend + ADK

---

## 1. Context

Chat is KEN-E's conversational surface — the `/chat` page, sidebar, status view, categories, todo lists, artifacts. Every user-facing feature reads from a Firestore side-table that mirrors ADK sessions plus product fields (title, category, summary cache, search text, token aggregates, activity timestamps, artifact metadata). See [`../implementation-plan.md`](../implementation-plan.md) for the full component design.

This project lays the substrate. It introduces the `chat_sessions` Shape B subcollection, the `chat_artifacts` nested subcollection, the Pydantic shapes and services, the ADK callbacks that keep the side-table fresh (real ADK primitive names are verified in a Day-1 spike), the model context-window registry used for the context meter, the 30-day window lift, and the one-shot back-fill that mirrors every existing ADK session into a minimal side-table row. No user-visible surface ships here — the `/chat` page arrives in CH-PRD-02. The validation checkpoint is that callbacks actually fire on the hot path, token counters move with the conversation, and the back-fill produces a row per historical session without disturbing the existing chat UX.

Landing the substrate first lets CH-PRD-02 build the sidebar against real data and CH-PRD-03 / 04 / 05 build features on a known contract.

**Cost display is deliberately out of scope.** KEN-E's user-facing cost is driven by subscription-level pricing, not per-model token costs — so a meaningful per-session cost estimate would require session → org → subscription → price lookups that are owned by Billing. Chat shows token counts only; cost stays with Billing.

## 2. Scope

### In scope

- **Pydantic models** for `ChatSessionMetadata`, `ChatArtifactIndex`, `ChatCategoryDefinition`, `TodoItem`, `TodoList`, `ChatStatusDetail`, `ModelContextWindowEntry` (shapes in §4).
- **Firestore layout** — new subcollection `accounts/{account_id}/chat_sessions/{session_id}` (Shape B) + nested `chat_sessions/{session_id}/artifacts/{artifact_id}`. Per-user `users/{user_id}/chat_categories/{category_id}` collection (shape registered here; CH-PRD-03 implements CRUD). Composite indexes per §4.3. DM-PRD-00 registry entries, DM-PRD-05 sweep inclusion.
- **Firestore security rules** — enforce `resource.data.user_id == request.auth.uid` on every `chat_sessions/*` read and write, and `request.auth.uid == userId` on `users/{userId}/chat_categories/*`. Rules file: `firestore.rules` additions. Unit-tested with the Firestore emulator.
- **`ChatSessionSideTableService`** (`api/src/kene_api/chat/side_table.py`) — `create(session_id, user_id, account_id, organization_id, model_id)`, `get(session_id)`, `list_for_user(user_id, account_id, cursor?, category_id?, query?)`, `update_from_delta(session_id, delta)`, `tombstone(session_id)`. Single write path into the side-table.
- **ADK callbacks** (`app/adk/agents/chat_callbacks.py`) — registered on the root runner via the Agent Factory (AH-PRD-02) or hardcoded root fallback. Two top-level callbacks:
  - `before_agent_callback` → stamps `last_agent_started_at = now()` on the side-table.
  - `after_agent_callback` → flushes the per-invocation accumulator, stamps `last_agent_stopped_at = now()`, writes all token / tool-call / compaction-summary deltas in one Firestore update.
  
  **Per-event work** happens inside the completion endpoint's event loop (`async for event in runner.run_async(...)`). The endpoint maintains a `SessionTurnAccumulator` and calls `.add_event(event)` as events stream. At end-of-turn the accumulator posts a single delta to the side-table via the internal endpoint — this is the handoff that `after_agent_callback` also covers for ADK-native invocation paths.

  **Pre-implementation spike:** Day 1 of CH-PRD-01 is a spike to confirm ADK callback signatures against the deployed ADK version (`before_agent_callback` / `after_agent_callback` are the public names I expect; per-event callbacks may not be first-class). The spike output is a short `docs/spike-adk-chat-callbacks.md` with confirmed signatures + an "if the expected callbacks don't exist, here is the fallback" section. Findings feed §5.2.
- **Events-based `is_agent_running` derivation** (no in-process sweeper). Instead of a boolean field, the side-table stores `last_agent_started_at` and `last_agent_stopped_at`. `is_agent_running` is *derived at read time*:
  ```
  is_agent_running = (
      last_agent_started_at is not None
      AND (last_agent_stopped_at is None OR last_agent_started_at > last_agent_stopped_at)
      AND (now() - last_agent_started_at) < STUCK_THRESHOLD  # 10 minutes
  )
  ```
  Self-expiring; a crashed invocation naturally becomes "not running" after the threshold without any sweeper. No in-process sweeper; no Cloud Run cron job. Simpler and more reliable.
- **SSE cancellation / exception handling** — the completion endpoint's `finally` / exception handlers call the same accumulator-flush code path as `after_agent_callback`, so even a user-cancelled stream records `last_agent_stopped_at` and flushes partial token counts. Tested explicitly.
- **Model context-window registry** (`api/src/kene_api/chat/context_windows.py`) — dict keyed by model id → `ModelContextWindowEntry(context_window_max)`. Much simpler than the original pricing registry. CI test (`test_context_window_registry_covers_deployed_models.py`) asserts every `model=` referenced in `app/adk/agents/*` is registered.
- **Multi-agent model handling** — the side-table snapshots the **root agent's** `model_id` and `context_window_max` at session creation. The context meter uses those for its denominator. Specialists that use different models still contribute to `current_context_tokens` (their `event.usage_metadata` is counted), but the bar is always rendered against the root's max window. Documented caveat in the status view copy: "Context usage is measured against the root model's window." No cost math — see Out of scope.
- **`current_context_tokens` post-compaction baseline** — on compaction event, after writing the summary, `current_context_tokens` is recomputed by summing `event.usage_metadata.total_token_count` across the events in the post-compaction active window (summary event + overlap invocation + last 10 retained events). Correct math, not "reset to 0."
- **`message_count` increment rule** — `message_count += 1` on every event where `event.author` is `"user"` or `"model"`. System and tool events are excluded.
- **Token-accounting helper** (owned by **Billing**, not Chat) — `extract_billable_tokens(event) → BillableTokenCounts(input, output, reasoning)` lives at `app/adk/token_accounting.py`. Billing's BL-PRD-02 is the authoritative owner. If Billing hasn't shipped when CH-PRD-01 starts, Chat authors the helper **under Billing's namespace**, with Billing as the PR reviewer and future maintainer — not under Chat ownership. Chat is a consumer in perpetuity. Token definition: input + output + reasoning, cached-input excluded — invariant shared with Billing.
- **30-day window** — lift `RECOVERY_WINDOW_DAYS` from 7 to 30 in `app/adk/session/recovery.py`. Mirror constant in `api/src/kene_api/chat/search.py` (used by CH-PRD-02's list endpoint). Callers validated via grep audit.
- **Back-fill migration** (`api/scripts/migrate_chat_side_table_backfill.py`) — iterates every ADK session via `list_sessions(app_name="ken_e_chatbot", user_id=...)` for every user in the org, writes a minimal `ChatSessionMetadata` row for each session that lacks one. Idempotent. `--dry-run` mode. Reports `{processed, created, already_present, errored}`. **Pre-work spike** measures actual `list_sessions` return shape on a realistic dev session count (known ADK Issue #3154 causes empty `user_id` on returned Session objects in some versions — the back-fill reads `user_id` from the enclosing iteration loop, never trusts the `Session.user_id` field).
- **Internal endpoint** `POST /api/v1/internal/chat/side-table/update` (OIDC) — the HTTP bridge from ADK-deployment callbacks to the API's side-table service. Idempotent on a request-body hash. Handler lives in `api/src/kene_api/chat/side_table_handlers.py` (NOT a Python module named `hooks.py` — see §5.1).
- **Creation path hook** — the existing `POST /api/v1/chat/conversations` is extended to write the side-table row after ADK session creation. The pending-session pattern is preserved: the side-table write happens inside `resolve_pending_session` once the real ADK ID is known.
- **`GET /api/v1/chat/conversations` base extension** — cursor pagination signature + 30-day window filter added to the signature here; CH-PRD-02 fully wires the frontend against it.
- **Weave spans** — `chat.session.created`, `chat.session.updated_from_event`, `chat.side_table.list`, `chat.back_fill`, `chat.adk_callback.invoked`. Cardinality bound by `session_id_hash` + `user_id_hash`.
- **Feature flags** — register `chat_v2_enabled` (master), `chat_status_detail_enabled`, `chat_categories_enabled`. Default off in dev; CH-PRD-02..05 flip their respective flags as they ship. **Note:** `chat_manual_compaction_enabled` is NOT registered — manual Compact-now is scoped out of v1 (see CH-PRD-04 §2).

### Out of scope

- **Cost display (per-session dollar amount).** Subscription-level pricing is Billing's concern; Chat shows token counts only. No `cost_usd_cents` field, no pricing registry, no cost formatter.
- **Manual compaction trigger / Compact-now button.** Deferred beyond v1; ADK's automatic compaction continues to run.
- **"Permissions Approved" figma card.** Not rendered in v1 — no placeholder, no flag, no data contract. Future PRD brings it in.
- **"Loaded Tools" figma card is replaced** by a new Authentication Status card in CH-PRD-04 §5.6. No CH-PRD-01 data contract changes — the card reads account-level integration state from IN-PRD-03's existing `platform_connections` collection; no Chat-owned storage.
- **In-process stale-flag sweeper.** Replaced by the events-based derivation above.
- Sidebar UI, page route, search input — CH-PRD-02.
- Category CRUD endpoints + UI — CH-PRD-03.
- Status view UI, status-detail composite endpoint, export, delete two-phase — CH-PRD-04.
- Todo list agent tools, artifact `register_artifact` wrapper + lint rule — CH-PRD-05.
- Removing the existing Redis 24h cache — retained as a speed-up; side-table is authoritative.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md)** | Shape B convention + `_migrate_shape_b/resources.py` registry. `chat_sessions` + nested `artifacts` registered here. | `../../data-management/README.md` |
| **[DM-PRD-05](../../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md)** | `recursive_delete` on account deletion cleans `chat_sessions/*` and sub-`artifacts/*`. `users/{user_id}/chat_categories/*` cleans on user deletion (first user-scoped subcollection). | `../../data-management/README.md` |
| **[FF-PRD-01](../../feature-flags/projects/FF-PRD-01-data-model-evaluation-api-backend-sdk.md)** | Backend feature-flag SDK. Three Chat flags registered here. | `../../feature-flags/README.md` |
| **[AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md)** | **Soft.** Agent Factory is the idiomatic callback-registration site. If unshipped, register against current hardcoded root + TODO. | `../../agentic-harness/README.md` |
| **[BL-PRD-02](../../billing/projects/BL-PRD-02-token-meter-monthly-enforcement.md)** | **Peer — Billing owns `extract_billable_tokens`.** Chat consumes. If Billing hasn't shipped, Chat lands the helper under Billing's namespace with Billing as reviewer + maintainer. Same token definition (input + output + reasoning, cached-input excluded) per Billing README §7.4. | `../../billing/README.md` §7.4 |
| **[BL-PRD-05](../../billing/projects/BL-PRD-05-failure-modes-permissions.md)** | **Soft — rate-limit substrate.** Billing introduces a Firestore-backed sliding-window limiter. Chat endpoints that need rate limits (CH-PRD-02..05) reuse this substrate when available. If BL-PRD-05 has not shipped when a Chat rate-limited endpoint ships, that Chat endpoint ships a minimal in-process limiter with a TODO to migrate. | `../../billing/README.md` |
| ADK `VertexAiSessionService` | `create_session`, `get_session`, `list_sessions(app_name, user_id)`, `delete_session`. Used by side-table creation, status-detail reads, back-fill. | Google ADK Python v1.16+ |
| Existing `api/src/kene_api/routers/chat.py` | The 9 existing endpoints. CH-PRD-01 adds the side-table write path to `POST /conversations` and extends `GET /conversations` signature. | `api/src/kene_api/routers/chat.py` |
| Existing Redis metadata cache | Preserved as a speed-up. Side-table is authoritative. | `api/src/kene_api/cache.py` |
| Existing `app/adk/session/recovery.py` | `RECOVERY_WINDOW_DAYS` constant lifted 7 → 30 here. Other code paths using the window are grep-audited. | `app/adk/session/recovery.py` |
| OIDC internal-endpoint auth | Reused from Integrations for the side-table-update bridge. | `api/src/kene_api/auth/` |
| Firebase Auth / Firestore security rules | Per-user-per-account enforcement lives here. | `firestore.rules` |

## 4. Data contract

### 4.1 Pydantic shapes

```python
class ChatSessionMetadata(BaseModel):
    session_id: str                          # ADK session id; also Firestore doc id
    user_id: str
    account_id: str
    organization_id: str
    adk_app_name: str                        # always "ken_e_chatbot"
    title: str | None = None                 # max 120 chars; set via PUT
    category_id: str | None = None           # FK to users/{user_id}/chat_categories/*
    latest_summary: str | None = None        # from ADK compaction events
    summary_updated_at: datetime | None = None
    compaction_count: int = 0
    search_text: str = ""                    # casefold(title + " " + category_name + " " + latest_summary)
    created_at: datetime
    updated_at: datetime                     # stamped on every event callback
    first_message_at: datetime | None = None
    last_user_message_at: datetime | None = None
    last_agent_message_at: datetime | None = None
    last_viewed_at: datetime | None = None   # set by POST /mark-read
    # Agent-running state — derived at read time from these two timestamps
    last_agent_started_at: datetime | None = None    # set by before_agent_callback
    last_agent_stopped_at: datetime | None = None    # set by after_agent_callback (or exception / cancellation)
    # Token aggregates (cumulative across compactions; for display only)
    input_tokens_total: int = 0
    output_tokens_total: int = 0
    reasoning_tokens_total: int = 0
    # Context window meter
    current_context_tokens: int = 0          # recomputed on compaction to match the active window
    context_window_max: int                  # snapshotted from root-agent's model at creation
    model_id: str                            # root-agent model at creation
    # Activity-summary counts
    tool_call_count: int = 0
    artifact_count: int = 0
    message_count: int = 0                   # +1 per event with author=="user" or author=="model"
    # Sidebar preview
    last_message_preview: str | None = None  # truncated to 160 chars
    # Lifecycle
    deleted_at: datetime | None = None       # two-phase tombstone

class ChatArtifactIndex(BaseModel):
    artifact_id: str                         # deterministic: sha256(session_id|filename|version)[:32]
    session_id: str
    filename: str
    mime_type: str
    size_bytes: int
    version: int                             # ADK artifact version (0..N)
    gcs_path: str                            # gs://{bucket}/{app_name}/{user_id}/{session_id}/{filename}/{version}
    created_by_tool: str | None = None       # agent tool name if agent-created; None means user-uploaded (latent for v1 — no user-upload surface yet)
    created_at: datetime

class ChatCategoryDefinition(BaseModel):
    category_id: str
    user_id: str
    name: str                                # 1..64 chars; stripped
    name_casefold: str                       # dedup key: name.strip().casefold()
    created_at: datetime
    updated_at: datetime

class TodoItem(BaseModel):
    item_id: str
    text: str
    completed: bool
    completed_at: datetime | None = None

class TodoList(BaseModel):
    list_id: str
    title: str
    is_current: bool
    created_at: datetime
    items: list[TodoItem]

class ChatStatusDetail(BaseModel):
    """Composite response shape for GET /conversations/{id}/status-detail."""
    metadata: ChatSessionMetadata
    artifacts: list[ChatArtifactIndex]
    todo_lists: list[TodoList]
    # Derived at the server
    is_agent_running: bool                   # derived from started_at / stopped_at / STUCK_THRESHOLD
    context_usage_percent: float             # current_context_tokens / context_window_max
    duration_seconds: int                    # last_agent_message_at - created_at
    activity_summary: str                    # "12 tool calls • 2 compactions • 3 artifacts"
    total_tokens: int                        # input + output + reasoning

class ModelContextWindowEntry(BaseModel):
    model_id: str
    context_window_max: int                  # tokens

class BillableTokenCounts(BaseModel):
    """Shared with Billing. Lives at app/adk/token_accounting.py (Billing owns)."""
    input: int
    output: int
    reasoning: int
    @property
    def total_billable(self) -> int:
        return self.input + self.output + self.reasoning
```

### 4.2 Firestore layout (Shape B + user-scoped)

| Path | Purpose |
|---|---|
| `accounts/{account_id}/chat_sessions/{session_id}` | Side-table row |
| `accounts/{account_id}/chat_sessions/{session_id}/artifacts/{artifact_id}` | Artifact metadata (written by CH-PRD-05; collection registered here) |
| `users/{user_id}/chat_categories/{category_id}` | Per-user categories (collection registered here; CRUD in CH-PRD-03) |

### 4.3 Composite indexes (Terraform)

Four indexes cover every query combination the sidebar and status view emit:

```hcl
# 1. Default sidebar query (no category filter): user_id + deleted_at + updated_at
resource "google_firestore_index" "chat_sessions_user_live_updated" {
  collection_group = "chat_sessions"
  fields { field_path = "user_id";    order = "ASCENDING" }
  fields { field_path = "deleted_at"; order = "ASCENDING" }
  fields { field_path = "updated_at"; order = "DESCENDING" }
}

# 2. Category-filtered sidebar query: user_id + category_id + deleted_at + updated_at
resource "google_firestore_index" "chat_sessions_user_category_live_updated" {
  collection_group = "chat_sessions"
  fields { field_path = "user_id";     order = "ASCENDING" }
  fields { field_path = "category_id"; order = "ASCENDING" }
  fields { field_path = "deleted_at";  order = "ASCENDING" }
  fields { field_path = "updated_at";  order = "DESCENDING" }
}

# 3. Chat artifacts: per-session listing
resource "google_firestore_index" "chat_artifacts_session_created" {
  collection_group = "artifacts"
  fields { field_path = "session_id"; order = "ASCENDING" }
  fields { field_path = "created_at"; order = "DESCENDING" }
}

# 4. Per-user categories: dedup + sort
resource "google_firestore_index" "chat_categories_user_name" {
  collection_group = "chat_categories"
  fields { field_path = "user_id";       order = "ASCENDING" }
  fields { field_path = "name_casefold"; order = "ASCENDING" }
}
```

Both sidebar indexes (#1 and #2) include `deleted_at` so tombstone exclusion is index-covered. Validated with `firebase emulators:start --only firestore` against the real query shapes during CH-PRD-01 implementation.

### 4.4 Model context-window registry

```python
MODEL_CONTEXT_WINDOW_REGISTRY: dict[str, ModelContextWindowEntry] = {
    "gemini-2.0-flash": ModelContextWindowEntry(
        model_id="gemini-2.0-flash",
        context_window_max=128_000,
    ),
    "gemini-2.5-flash": ModelContextWindowEntry(...),
    "gemini-2.5-pro": ModelContextWindowEntry(...),
    # every model id referenced from app/adk/agents/ must have an entry
}
```

The CI coverage test walks `app/adk/agents/**/*.py` for `model=` kwargs and asserts each found id is a key. Adding a model without registering the context window fails the build.

### 4.5 Firestore security rules

Added to `firestore.rules`:

```
match /accounts/{accountId}/chat_sessions/{sessionId} {
  allow read: if request.auth != null
              && resource.data.user_id == request.auth.uid;
  allow write: if request.auth != null
               && request.auth.token.account_id == accountId
               && request.resource.data.user_id == request.auth.uid;

  match /artifacts/{artifactId} {
    allow read: if request.auth != null
                && get(/databases/$(database)/documents/accounts/$(accountId)/chat_sessions/$(sessionId)).data.user_id == request.auth.uid;
    // No direct write — artifacts go through the server-side register_artifact wrapper (CH-PRD-05).
    allow write: if false;
  }
}

match /users/{userId}/chat_categories/{categoryId} {
  allow read, write: if request.auth != null
                    && request.auth.uid == userId;
}
```

Enforcement belt-and-braces: the API layer additionally checks ownership server-side, so a Firestore-rules gap doesn't leak data on the API path. Unit-tested with the Firestore emulator.

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create | `api/src/kene_api/models/chat.py` — all Pydantic shapes |
| Create | `api/src/kene_api/chat/__init__.py` |
| Create | `api/src/kene_api/chat/side_table.py` — `ChatSessionSideTableService` |
| Create | `api/src/kene_api/chat/side_table_handlers.py` — HTTP handlers for the internal update endpoint (NOT called "hooks") |
| Create | `api/src/kene_api/chat/context_windows.py` — `MODEL_CONTEXT_WINDOW_REGISTRY`, `get_model_context_window(model_id)` |
| Create | `api/src/kene_api/chat/search.py` — `list_sessions(user_id, account_id, cursor?, category_id?, query?)` |
| Create | `api/src/kene_api/chat/accumulator.py` — `SessionTurnAccumulator` (per-turn in-memory delta) |
| Create | `app/adk/token_accounting.py` — `extract_billable_tokens(event)`, `BillableTokenCounts`. **Billing-owned.** |
| Create | `app/adk/agents/chat_callbacks.py` — `before_agent_callback`, `after_agent_callback`. **Only file that fires the ADK callbacks.** Posts to the internal update endpoint. |
| Modify | `api/src/kene_api/routers/chat.py` — extend `POST /conversations` to write the side-table row; extend `GET /conversations` signature for cursor + filters; add completion-endpoint accumulator flush on cancellation / exception; add `POST /internal/chat/side-table/update` handler. |
| Modify | `app/adk/session/recovery.py` — `RECOVERY_WINDOW_DAYS = 30` |
| Modify | `deployment/terraform/firestore.tf` — 4 composite indexes from §4.3 |
| Modify | `firestore.rules` — add the security-rules blocks from §4.5 |
| Create | `api/scripts/migrate_chat_side_table_backfill.py` — one-shot back-fill |
| Create | `api/scripts/lint/check_context_window_registry_coverage.py` — CI lint |
| Create | `docs/spike-adk-chat-callbacks.md` — Day-1 spike output (confirmed ADK callback signatures + fallback plan) |
| Create | `api/tests/unit/chat/test_side_table.py`, `test_accumulator.py`, `test_context_windows.py`, `test_search.py`, `test_token_accounting.py`, `test_token_accounting_parity.py`, `test_is_agent_running_derivation.py`, `test_message_count_rule.py`, `test_post_compaction_baseline.py` |
| Create | `api/tests/integration/chat/test_session_creation_writes_side_table.py`, `test_callback_writes_counters.py`, `test_backfill.py`, `test_30_day_window.py`, `test_internal_side_table_update_oidc.py`, `test_sse_cancellation_flushes_accumulator.py`, `test_firestore_security_rules.py` |

### 5.2 Callback wiring — detail

**Day-1 spike deliverable.** Confirmed ADK callback names before any implementation begins. The names below are the expected public names (`before_agent_callback`, `after_agent_callback`) — if the spike finds different names, the spike doc is updated and this PRD file is amended in a one-line commit before implementation starts.

```
# app/adk/agents/chat_callbacks.py

@before_agent_callback
def on_agent_start(invocation_context):
    session_id = invocation_context.session.id
    post_side_table_update(session_id, {
        "last_agent_started_at": now(),
        "updated_at": now(),
    })

@after_agent_callback
def on_agent_stop(invocation_context):
    session_id = invocation_context.session.id
    # The accumulator was built by the completion endpoint iterating events;
    # at after_agent_callback time, we also flush anything we observed.
    accumulator = get_accumulator(session_id)
    post_side_table_update(session_id, accumulator.build_delta())


# api/src/kene_api/chat/accumulator.py

class SessionTurnAccumulator:
    def __init__(self):
        self.input = 0
        self.output = 0
        self.reasoning = 0
        self.tool_call_count = 0
        self.message_count_delta = 0
        self.latest_summary: str | None = None
        self.compaction_count_delta = 0
        self.post_compaction_context_tokens: int | None = None   # set on compaction event
        self.final_text: str = ""

    def add_event(self, event):
        if event.usage_metadata:
            counts = extract_billable_tokens(event)     # Billing-owned helper
            self.input += counts.input
            self.output += counts.output
            self.reasoning += counts.reasoning
        if event.type == "tool_call":
            self.tool_call_count += 1
        if event.author in ("user", "model"):
            self.message_count_delta += 1
        if event.type == "compaction_summary":
            self.latest_summary = event.content
            self.compaction_count_delta += 1
            # Post-compaction baseline: sum usage_metadata across the active event window
            self.post_compaction_context_tokens = compute_post_compaction_window_tokens(event)
        if event.is_final_text:
            self.final_text = event.text

    def build_delta(self) -> dict:
        delta = {
            "last_agent_stopped_at": now(),
            "updated_at": now(),
            "last_agent_message_at": now(),
            "input_tokens_total":     Increment(self.input),
            "output_tokens_total":    Increment(self.output),
            "reasoning_tokens_total": Increment(self.reasoning),
            "tool_call_count":        Increment(self.tool_call_count),
            "message_count":          Increment(self.message_count_delta),
            "last_message_preview":   truncate(self.final_text, 160),
        }
        if self.post_compaction_context_tokens is not None:
            delta["current_context_tokens"] = self.post_compaction_context_tokens
            delta["latest_summary"] = self.latest_summary
            delta["summary_updated_at"] = now()
            delta["compaction_count"] = Increment(self.compaction_count_delta)
            delta["search_text"] = casefold(title + " " + category_name + " " + self.latest_summary)
        else:
            delta["current_context_tokens"] = Increment(self.input + self.output + self.reasoning)
        return delta
```

**Per-event work** happens inside the completion endpoint's event loop:
```python
# api/src/kene_api/routers/chat.py — in the /completions handler
try:
    accumulator = SessionTurnAccumulator()
    async for event in runner.run_async(...):
        accumulator.add_event(event)
        yield format_sse(event)
except (asyncio.CancelledError, Exception):
    # SSE cancellation or any agent-side failure: still flush what we've accumulated
    # and stamp last_agent_stopped_at. This is the same code path after_agent_callback runs.
    raise
finally:
    await post_side_table_update(session_id, accumulator.build_delta())
```

The `finally` block ensures `last_agent_stopped_at` and partial counters are always recorded — even if the agent crashes mid-stream or the user clicks Stop. No stuck state, no sweeper.

**Batch-coalesce:** one Firestore `update` per turn (on `finally` / `after_agent_callback`). Writes never block the stream.

**Failure semantics:** callback errors are logged + metered but never block the agent. Side-table write failures are retried by the Firestore client (idempotent on request-body hash at the internal endpoint).

### 5.3 Back-fill migration

```text
migrate_chat_side_table_backfill(--dry-run?, --account-id?):
  1. Day-1 spike measures the shape of VertexAiSessionService.list_sessions on dev:
     - Does it paginate? Known ADK Issue #3154 can return empty user_id — confirm.
     - Worst-case per-user session count for planning memory bounds.
  2. If --account-id: scope to one account; else: iterate all accounts.
  3. For each account, list distinct user_ids from accounts/{account_id}/users/*.
  4. For each (account_id, user_id) pair: call list_sessions(app_name, user_id). Use the user_id from
     the iteration — NEVER trust the Session.user_id field returned by the ADK (Issue #3154 bug).
  5. For each ADK session returned:
     a. If accounts/{account_id}/chat_sessions/{session_id} exists → skip.
     b. Read session.state for account_id validation. Skip (with warning log) if state.account_id != account_id.
     c. Write a minimal ChatSessionMetadata row:
        - created_at = session.create_time
        - updated_at = session.update_time
        - last_agent_started_at / last_agent_stopped_at = None (unknown for historical sessions)
        - message_count = count of user/model events in session.events
        - last_message_preview = preview from the last non-internal event
        - title = session.state.get("conversation_name") or None
        - context_window_max = lookup in MODEL_CONTEXT_WINDOW_REGISTRY for the root model
        - deleted_at = None
  6. Report {processed, created, already_present, errored}. Idempotent.
```

**Dry-run** mode prints the planned writes without touching Firestore. Run against dev → staging → prod.

### 5.4 Token-accounting helper — owned by Billing

```python
# app/adk/token_accounting.py
# OWNER: Billing (BL-PRD-02). Chat consumes. Changes require Billing review.

def extract_billable_tokens(event) -> BillableTokenCounts:
    """Extract billable tokens from an ADK event.

    Token definition (invariant, shared with Billing):
      - input: event.usage_metadata.prompt_token_count - cached_input_tokens
      - output: event.usage_metadata.candidates_token_count
      - reasoning: event.usage_metadata.thoughts_token_count (0 for non-reasoning models)

    Cached input tokens are EXCLUDED (KEN-E margin, not customer cost).
    """
    if not event.usage_metadata:
        return BillableTokenCounts(input=0, output=0, reasoning=0)
    cached = getattr(event.usage_metadata, "cached_content_token_count", 0) or 0
    return BillableTokenCounts(
        input=max(0, event.usage_metadata.prompt_token_count - cached),
        output=event.usage_metadata.candidates_token_count or 0,
        reasoning=getattr(event.usage_metadata, "thoughts_token_count", 0) or 0,
    )
```

Billing's BL-PRD-02 meter calls `extract_billable_tokens(event).total_billable`. Chat's accumulator sums the three fields separately so the status view can show Input / Output / Total.

**Ownership protocol:**
- If BL-PRD-02 has already shipped: Chat imports and uses. Done.
- If BL-PRD-02 has not shipped: Chat lands the helper at the documented path **with Billing as PR reviewer and future maintainer**. The Chat author notes in the PR description: "This lands in Billing's namespace; ownership transfers on BL-PRD-02 merge. No changes to this file without Billing review."

`test_token_accounting_parity.py` constructs a synthetic event and asserts the helper's output matches a hardcoded expected `BillableTokenCounts`. Billing and Chat both include this test (symlinked or copied with CI assertion of identity).

### 5.5 30-day window — grep audit

1. Grep `RECOVERY_WINDOW_DAYS` — only `app/adk/session/recovery.py` defines it.
2. Grep `7` near `days` or `timedelta` in `api/src/kene_api/routers/chat.py` — any orphan 7-day constants become 30.
3. Grep `created_at >= ` and `updated_at >= ` in chat-related code to confirm no hardcoded `-7` offsets.
4. Add a module-level constant `CHAT_LIST_WINDOW_DAYS = 30` in `api/src/kene_api/chat/search.py` and import across the component.

### 5.6 Feature flag registration

```python
FEATURE_FLAGS_REGISTRY_ADDITIONS = {
    "chat_v2_enabled": {"default": False, "description": "Master kill switch for the Chat component (sidebar, status view, categories, todos, artifacts)."},
    "chat_status_detail_enabled": {"default": False, "description": "Gates the session status view endpoint + Session Status toggle button."},
    "chat_categories_enabled": {"default": False, "description": "Gates category CRUD + sidebar filter + status-view assign dropdown."},
}
```

No `chat_manual_compaction_enabled` (feature scoped out of v1). No `chat_permissions_and_tools_ui_enabled` (feature scoped out of v1).

## 6. API contract

### Extended

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/chat/conversations` | Existing. After ADK session creation, write a `ChatSessionMetadata` row. Returns the existing `ConversationInfo` shape (unchanged; side-table fields surfaced in future endpoints). |
| `GET` | `/api/v1/chat/conversations?cursor=&category_id=&query=&limit=` | Existing. Signature extended. Default `limit=20`, max `limit=100`. Returns `{items: ConversationInfo[], next_cursor: str \| null}`. `items[]` adds `last_agent_started_at`, `last_agent_stopped_at`, `last_viewed_at`. CH-PRD-02 wires the frontend. |
| `GET` | `/api/v1/chat/sessions/recoverable` | Existing. 30-day window lift. |

### New

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/internal/chat/side-table/update` | OIDC. Body `{session_id, delta: {field_path: value \| Increment(n)}, idempotency_key}`. Idempotent on `idempotency_key` with 24h TTL. The ADK-deployment bridge and completion-endpoint `finally` both post here. |

Auth gates:
- `chat_v2_enabled=false` → all new endpoints return 404.
- Firestore security rules enforce per-user-per-account ownership on every direct-Firestore read (belt-and-braces with API-layer checks).

## 7. Acceptance criteria

1. **Pydantic shapes land** in `api/src/kene_api/models/chat.py` per §4.1 — no `cost_usd_cents`, no `ModelPricingEntry`, no `creator` on artifacts, and `last_agent_started_at` / `last_agent_stopped_at` replacing `is_agent_running`.
2. **Firestore layout + 4 composite indexes** provisioned via Terraform (§4.3). DM-PRD-00 registry lists `chat_sessions` + nested `artifacts` + user-scoped `chat_categories`.
3. **Firestore security rules** from §4.5 land; emulator test asserts cross-user reads return PERMISSION_DENIED; cross-account writes return PERMISSION_DENIED; artifact writes from the client are disallowed.
4. **Day-1 ADK callback spike** completes; `docs/spike-adk-chat-callbacks.md` records confirmed signatures. PRD §5.2 amended if the spike finds different names.
5. **`ChatSessionSideTableService` lands** — create / get / list_for_user / update_from_delta / tombstone work against the real Firestore client. Uses `firestore.Increment` for counter fields.
6. **Callbacks fire on the hot path.** Unit test constructs a fake agent invocation; the accumulator aggregates correctly; one `update` call hits Firestore per turn (not per event).
7. **`is_agent_running` is derived** at read time from timestamps. No persistent boolean field; no in-process sweeper. Test asserts that a 15-minute-old `last_agent_started_at` with no `last_agent_stopped_at` returns `is_agent_running=false`.
8. **SSE cancellation / exception flushes the accumulator.** Integration test cancels a streaming response mid-flight → side-table records `last_agent_stopped_at` + the partial token counts.
9. **`message_count` rule** — unit test constructs events with authors `user`, `model`, `system`, `tool` in a mixed sequence; asserts `message_count` increments only on `user`/`model`.
10. **Post-compaction `current_context_tokens` baseline** — unit test constructs a fake compaction event + active window; asserts `current_context_tokens` equals the sum of `usage_metadata.total_token_count` across the retained events (NOT zero).
11. **Model context-window registry + CI coverage** — every `model=` kwarg found in `app/adk/agents/**/*.py` is a key in `MODEL_CONTEXT_WINDOW_REGISTRY`. Lint test fails on a deliberately-unregistered model.
12. **Shared token-accounting helper** — `extract_billable_tokens` lands at `app/adk/token_accounting.py` under Billing ownership. Parity test passes: identical output on a fixed fixture (symlinked / duplicated between chat and billing test dirs; CI asserts identical).
13. **30-day window** — `RECOVERY_WINDOW_DAYS = 30` in `session/recovery.py`; `CHAT_LIST_WINDOW_DAYS = 30` in `chat/search.py`. Grep audit confirms no other 7-day chat window exists.
14. **Creation path** — `POST /api/v1/chat/conversations` writes a side-table row after the ADK session commits. The pending-session pattern still works.
15. **Back-fill** — `migrate_chat_side_table_backfill.py --dry-run` reports zero divergence after a real run on a seed dataset; real run is idempotent. User-id is read from the iteration loop, not from `Session.user_id` (ADK Issue #3154 guard).
16. **Internal side-table-update endpoint** — OIDC-authed; rejects unauthenticated requests with 401; applies deltas correctly; idempotent on `idempotency_key`.
17. **Feature flags** — three flags registered; `chat_v2_enabled=false` keeps new endpoints returning 404; existing endpoints always functional. `chat_manual_compaction_enabled` is NOT registered (Compact-now is out of v1).
18. **No user-visible change** from CH-PRD-01 alone beyond the window-lift. The `/chat` frontend is unchanged; session creation + history still works; sidebar is not yet wired.

## 8. Test plan

### Unit
- `ChatSessionMetadata` Pydantic validation (title ≤120 chars; message_count ≥0; `search_text` autocomputed with `casefold()`).
- `ChatSessionSideTableService.update_from_delta` applies field-paths and `Increment(...)` correctly.
- `SessionTurnAccumulator` aggregation (token counts, tool-call counts, compaction summaries, message_count rule).
- `extract_billable_tokens` correctness (cached-input excluded; reasoning counted; missing fields default to 0).
- `compute_post_compaction_window_tokens` — given a compaction event + retained events, produces the right sum.
- `is_agent_running` derivation — table-driven tests across 6 states (never-started, running-fresh, running-stuck, stopped-before-start, stopped-after-start, both-null).
- Context-window registry coverage lint on a synthetic `agents/foo.py` with an unknown model id — lint fails.
- `search_text` recomputation — matches `casefold()` of concatenated fields invariant.
- 30-day window cutoff — list query excludes a row with `updated_at = now() - 31d`.

### Integration
- Session creation E2E: `POST /conversations` → ADK session exists → side-table row exists with expected fields.
- Callback E2E: construct a fake invocation → `before_agent_callback` stamps started_at → accumulator adds events → `finally` flushes → Firestore shows correct cumulative counters and `last_agent_stopped_at`.
- SSE cancellation E2E: start a streaming completion → cancel mid-stream → `last_agent_stopped_at` set + partial token counts persisted.
- Back-fill against a seed dataset: 100 ADK sessions → 100 side-table rows; re-run idempotent.
- Internal endpoint `POST /internal/chat/side-table/update` with OIDC — 200 on valid; 401 without token; idempotent on `idempotency_key`.
- Parity test — Chat and Billing both import `extract_billable_tokens` and produce identical output on a shared fixture (CI asserts).
- Firestore security rules — user A cannot read user B's `chat_sessions`; anyone authenticated against account A cannot read/write another account's docs; client-side artifact writes fail.

### Manual verification
- Dev-env: run `setup_local_dev.sh`, create a session via the existing `POST /conversations`, inspect Firestore console, confirm `chat_sessions/{session_id}` exists with default values. Send a message via `/completions`, confirm token counters increment + timestamps stamp correctly.
- Staging: run `migrate_chat_side_table_backfill.py --dry-run` against the real dataset; confirm count matches `list_sessions` across users; run for real; confirm idempotency.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Day-1 ADK callback spike finds different names or no per-event callbacks at all | Spike is the gating first task. If names differ, §5.2 is amended before implementation. Per-event updates are already handled by the completion endpoint's event loop (not a callback), so the fallback is already in the design. |
| Callbacks fire on the hot path with unbounded latency (Firestore slow) | Fire-and-forget writes from the callback; one `update` per turn (batch-coalesce); log + meter callback latency; alert on p95 > 1s. |
| SSE cancellation doesn't fire `after_agent_callback` | `finally` block in the completion endpoint is the authoritative flush site — runs regardless of ADK callback behavior. |
| Token definition drifts from Billing | Shared `extract_billable_tokens` under Billing ownership + parity test on every PR. Divergence fails CI. |
| Multi-agent session: cost estimate would be wrong | Cost display removed from v1 (not Chat's concern). Context meter uses root-agent's window as a documented approximation. |
| Post-compaction context baseline: edge cases around event ordering | `compute_post_compaction_window_tokens` is a pure function with unit tests covering empty window, summary-only, summary + overlap + retained events, oversized summary. Failure mode is that the meter briefly shows a non-zero starting value post-compact — acceptable vs. the old "reset to 0" bug. |
| ADK `list_sessions` has known Issue #3154 returning empty `user_id` | Back-fill reads `user_id` from the iteration loop; never trusts the `Session.user_id` field. Tested with a fake session fixture that simulates the bug. |
| ADK `list_sessions` is unpaginated → OOM on large tenants | Day-1 spike measures actual behavior on dev. If unpaginated, back-fill iterates at the user level (naturally chunked). Worst-case bounded by product usage. |
| Firestore composite index build takes >30min on first deploy | Scheduled during a maintenance window; the side-table is unused at the read path until CH-PRD-02, so no user impact. |
| `search_text` grows unbounded on long-summary sessions | Truncate `latest_summary` to first 2 KB before concatenating into `search_text`; Firestore doc size stays under 1 MB. |
| Context-window registry CI coverage breaks on a deliberate model rollout | A PR that adds a new model ALSO adds the context-window entry — same PR. Test fails locally before commit. |
| User has `account_id` in URL that differs from `session.state["account_id"]` on back-fill | Back-fill reads `session.state` for ground truth; skips the session with a warning rather than writing to the wrong account. |
| Redis cache falls out of sync with side-table | Cache is a speed-up; side-table is authoritative. Cache TTL (24h) bounds drift. Documented. |

### Open questions
- **Q:** Does `event.usage_metadata.cached_content_token_count` populate reliably across Gemini model versions? → **Proposal:** default to 0 when field missing; unit test covers both branches. Validate against production traces in week 1.
- **Q:** What is the right `STUCK_THRESHOLD` for `is_agent_running` derivation (10 min in the proposal)? → **Proposal:** 10 min covers p99 agent response time comfortably. Revisit if users report stuck "working…" indicators; adjustable via config.
- **Q:** Where should `extract_billable_tokens` actually live in repo layout if Billing hasn't defined the namespace yet? → **Proposal:** `app/adk/token_accounting.py` in Billing's `BL-PRD-02` Pydantic module layout. If that layout hasn't settled, a stub commit lands alongside this PRD's PR to reserve the path.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Component README: [`../README.md`](../README.md)
- Upstream: [DM-PRD-00](../../data-management/projects/DM-PRD-00-migration-foundation.md), [DM-PRD-05](../../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md), [FF-PRD-01](../../feature-flags/projects/FF-PRD-01-data-model-evaluation-api-backend-sdk.md)
- Downstream: [CH-PRD-02](./CH-PRD-02-chat-page-shell-and-sidebar.md), [CH-PRD-03](./CH-PRD-03-session-categories.md), [CH-PRD-04](./CH-PRD-04-session-status-view.md), [CH-PRD-05](./CH-PRD-05-todo-lists-and-artifacts.md)
- Peer (Billing): [BL-PRD-02](../../billing/projects/BL-PRD-02-token-meter-monthly-enforcement.md) — owns `extract_billable_tokens`. Rate-limit substrate: [BL-PRD-05](../../billing/projects/BL-PRD-05-failure-modes-permissions.md).
- ADK docs: [`VertexAiSessionService`](https://google.github.io/adk-docs/sessions/), [`EventsCompactionConfig`](https://google.github.io/adk-docs/context/compaction/), [agent callbacks](https://google.github.io/adk-docs/agents/)
- ADK known issue: [Issue #3154 — `list_sessions` returns empty `user_id`](https://github.com/google/adk-python/issues/3154)
- Existing code: [`api/src/kene_api/routers/chat.py`](../../../../api/src/kene_api/routers/chat.py), [`app/adk/session/recovery.py`](../../../../app/adk/session/recovery.py)
- CLAUDE.md rules in scope: PY-1, PY-2, PY-5, PY-7; D-1, D-2, D-5; C-2, C-4; T-1, T-3, T-4, T-5
