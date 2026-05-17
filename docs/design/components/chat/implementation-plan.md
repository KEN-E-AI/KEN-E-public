# Chat — Implementation Plan

**Status:** Draft — 2026-04-24 (revised post-qreview)
**Owner:** Chat component team (TBD)
**Proposed PRD prefix:** `CH-PRD-NN`
**Backend session service:** Google ADK `VertexAiSessionService` (app_name = `ken_e_chatbot`)

---

## 1. What Chat is

Chat is KEN-E's **conversational surface** — the `/chat` page, the session history sidebar, the session status view, the per-user category system, the metadata substrate that mirrors ADK sessions into Firestore, and every ADK hook that keeps the substrate fresh. It replaces and extends the minimal `/chat` experience that UI-PRD-02 was originally scoped to deliver, folding in eleven user-facing features that the pre-component UI does not support.

Six facts shape the design:

1. **Sessions are per-user-per-account.** A session is uniquely identified by `(user_id, account_id, adk_session_id)`; the sidebar lists only the authenticated user's sessions for the currently selected account. This matches how the existing `/api/v1/chat/completions` code path already scopes its state. Firestore security rules enforce this server-side.
2. **ADK is the source of truth for conversation events; Firestore is the source of truth for product metadata.** ADK's `VertexAiSessionService` has no pagination, no sorting, no title, no search, and sparse artifact metadata. Rather than fight those gaps, Chat mirrors every session into a Firestore `chat_sessions/*` side-table with the product fields the UI needs (title, category, summary cache, search text, activity timestamps, token aggregates, artifact metadata index). Read paths hit the side-table; write paths touch both, with ADK callbacks + the completion endpoint's event-loop accumulator as the one-way flow from ADK to Firestore.
3. **The compaction summary and todo lists are agent-authored and read-only to the user.** The summary is extracted from ADK's compaction events. Todo lists live in `session.state["todo_lists"]` as a dict-of-lists and are updated exclusively by agent tools. The UI renders these without edit affordances — no merge conflicts, no save buttons.
4. **`is_agent_running` is a derived field, not a persistent boolean.** Computed from `last_agent_started_at`, `last_agent_stopped_at`, and a 10-minute stuck threshold. No in-process sweeper, no Cloud Run cron. A crashed invocation becomes "not running" automatically at read time.
5. **Multi-session concurrency is first-class.** A user can interleave sessions across tabs and watch the sidebar flip dots from active to needs-review to idle as state changes. Server-authoritative timestamps + 5–10s polling + `mark-read` endpoint is the whole mechanism.
6. **Token counts — but not cost — are surfaced in Chat.** Subscription-level pricing is Billing's concern; adding per-session cost would require session → org → subscription → rate lookups that are deliberately out of scope. Chat and Billing share the same `extract_billable_tokens(event)` helper (Billing-owned) with the same token definition (input + output + reasoning; cached-input excluded); Chat aggregates for display, Billing aggregates for enforcement. Same source, different consumers.
7. **Auto-title is once-per-session and billable.** After the first assistant response completes, CH-PRD-04 fires a fire-and-forget `gemini-2.5-flash` call (3–6 word title from the first user message + first assistant response). The generator: re-reads the side-table before writing (race-safe with manual edits); stamps `auto_title_attempted_at` on every outcome (success, failure, suppression) so it never retries; bills tokens through the same BL-PRD-02 meter agent calls use; degrades gracefully if Gemini fails (leaves title null, no retry). Manual title edits via PUT `/conversations/{id}` set `auto_title_attempted_at` synchronously to suppress in-flight generation. Gated by `chat_auto_title_enabled` (default `true`; ops kill switch).

**Scoped out of v1** (following the qreview pass on 2026-04-24):
- **Per-session cost display** — subscription-level pricing complexity deferred.
- **Manual Compact-now button** — ADK auto-compaction still runs; manual trigger returns in a future PRD if the ADK API stabilizes.
- **"Permissions Approved" figma card** — not rendered at all (no placeholder, no mock data, no flag). Future PRD brings this in when it becomes a real feature.
- **"Loaded Tools" figma card is replaced** by a new **Authentication Status** card (CH-PRD-04 §5.6) showing account-level integration state. Ships read-only in v1 via IN-PRD-03's data; per-row Check Status button is enabled once IN-PRD-07 ships (soft dep; flag-gated).

## 2. What exists today (before Chat)

The backend plumbing is further along than the frontend. A `/api/v1/chat/*` FastAPI router ships today with 9 endpoints backed by `VertexAiSessionService`. Frontend has `services/chatService.ts` as a typed API client but no chat page, no sidebar, no status view, and no session-list UI.

| Upstream | What it gives us |
|---|---|
| **Existing `/api/v1/chat/*`** | 9 endpoints: `completions`, `conversations` POST/GET, `conversations/{id}` PUT/DELETE, `conversations/{id}/history`, `sessions/recoverable`, `sessions/{id}/recover`, `cache/invalidate/{account_id}`. Uses `VertexAiSessionService` with `app_name="ken_e_chatbot"`. Redis 24-hour metadata cache. 7-day recovery window. Pending-session pattern for deferred ADK creation. |
| **ADK `VertexAiSessionService`** | Session CRUD, event stream, `session.state` KV store, `list_sessions(app_name, user_id)` (no pagination, no sort, and Issue #3154 returns empty `user_id` on some versions). |
| **ADK `EventsCompactionConfig`** | Already configured in `app/adk/deploy_ken_e.py` per `docs/KEN-E-System-Architecture.md` §3.5 — `gemini-2.5-flash` summarizer every 5 invocations or >50K tokens, 1-invocation overlap, last 10 events kept raw. Automatic, not manual. |
| **ADK `GcsArtifactService`** | Artifact blob storage. Filename + MIME native; no `created_at` or tool-name metadata. |
| **ADK callback API** | `before_agent_callback` / `after_agent_callback` at the invocation level (plus `before_model_callback` / `after_model_callback` / `before_tool_callback` / `after_tool_callback` at finer grains). Chat uses the agent-level pair. **Day-1 spike in CH-PRD-01 confirms exact signatures** before implementation begins. |
| **`docs/figma-export/`** | Complete React prototype of the target UX. `SessionsSidebar`, `SessionSettings`, `ChatInterface`, `ChatPage`, mock data. All 11 user-facing features are designed; three figma elements are deliberately not ported in v1 (summary editability, Compact-now button, Permissions Approved card, cost line). The figma's "Loaded Tools" card is replaced by a new Authentication Status card — see CH-PRD-04 §5.6. |
| **DM-PRD-00** (Migration Foundation) | Shape B convention + `_migrate_shape_b/resources.py` registry for new subcollections. |
| **DM-PRD-05** (Deletion Sweep) | `recursive_delete` covers `chat_sessions` and its artifact subcollection on account deletion; user deletion covers `chat_categories`. |
| **UI-PRD-01** (Design System Foundation) | `LayoutC`, Tailwind tokens, shadcn primitives, `TopNav`, `AccountSwitcher`, text-size preference. |
| **FF-PRD-01 + FF-PRD-03** | Backend + frontend SDKs for the three Chat flags (master + status-detail + categories; manual-compaction flag NOT needed — feature out of v1). |
| **BL-PRD-02** (Billing meter — not required to ship before Chat) | Owns `extract_billable_tokens(event)` at `app/adk/token_accounting.py`. Chat consumes. |
| **BL-PRD-05** (Billing rate limits — soft) | Firestore sliding-window limiter used by Chat's rate-limited endpoints when available; fallback is in-process. |
| **W&B Weave tracing** (existing) | Token counts already instrumented on LLM spans. Same definition as Chat + Billing will use. |
| **Firebase Auth + Firestore security rules** | Chat adds rules to enforce per-user-per-account access; API-layer checks are belt-and-braces. |

**What is missing** — everything user-facing that CH-PRD-02 onward delivers. No chat page, no sidebar, no status view, no categories, no todo-list state convention, no context-window meter, no artifact metadata index, no export. The backend substrate (`chat_sessions/*` side-table) also does not exist today — CH-PRD-01 introduces it.

## 3. Data model

### 3.1 Pydantic shapes

```python
class ChatSessionMetadata(BaseModel):
    """The Firestore side-table row. One per ADK session."""
    session_id: str                          # ADK session id; also the doc id
    user_id: str
    account_id: str
    organization_id: str
    adk_app_name: str                        # "ken_e_chatbot"
    # User-owned fields
    title: str | None                        # editable; max 120 chars
    category_id: str | None                  # FK to users/{user_id}/chat_categories/*
    # Compaction-derived (read-only to user)
    latest_summary: str | None
    summary_updated_at: datetime | None
    compaction_count: int                    # 0..N
    # Search
    search_text: str                         # casefold(title + " " + category.name + " " + latest_summary)
    # Activity timestamps
    created_at: datetime
    updated_at: datetime                     # stamped on every end-of-turn flush
    first_message_at: datetime | None
    last_user_message_at: datetime | None
    last_agent_message_at: datetime | None
    last_viewed_at: datetime | None          # set by POST /mark-read
    # Agent-running state — derived at read time from these two timestamps
    last_agent_started_at: datetime | None   # set by before_agent_callback
    last_agent_stopped_at: datetime | None   # set by after_agent_callback or the completion endpoint's finally block
    # Token aggregates (cumulative across compactions; for display only)
    input_tokens_total: int
    output_tokens_total: int
    reasoning_tokens_total: int
    # Context window meter
    current_context_tokens: int              # recomputed on compaction to the post-compaction window sum
    context_window_max: int                  # snapshotted from root-agent's model at creation
    model_id: str                            # root-agent model at creation
    # Activity-summary counts
    tool_call_count: int
    artifact_count: int
    message_count: int                       # +1 per event with author in ("user", "model")
    # Sidebar preview
    last_message_preview: str | None         # truncated to 160 chars
    # Lifecycle
    deleted_at: datetime | None              # two-phase tombstone

class ChatCategoryDefinition(BaseModel):
    category_id: str
    user_id: str
    name: str                                # max 64 chars
    name_casefold: str                       # dedup key: name.strip().casefold() — Unicode-safe
    created_at: datetime
    updated_at: datetime

class ChatArtifactIndex(BaseModel):
    artifact_id: str                         # deterministic: sha256(session_id|filename|version)[:32]
    session_id: str
    filename: str
    mime_type: str
    size_bytes: int
    version: int                             # ADK artifact version (0..N)
    gcs_path: str                            # gs://{bucket}/{app_name}/{user_id}/{session_id}/{filename}/{version}
    created_by_tool: str | None              # agent tool name in v1; None reserved for future user uploads
    created_at: datetime

class TodoItem(BaseModel):
    item_id: str
    text: str
    completed: bool
    completed_at: datetime | None

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
    # Derived server-side — NO cost field
    is_agent_running: bool                   # derived from started_at / stopped_at / 10-min threshold
    context_usage_percent: float             # current_context_tokens / context_window_max
    duration_seconds: int                    # last_agent_message_at - created_at
    activity_summary: str                    # "12 tool calls • 2 compactions • 3 artifacts"
    total_tokens: int                        # input + output + reasoning
```

**No `cost_usd_cents` field.** **No `ModelPricingEntry`.** **No `creator` field on artifacts** (use `created_by_tool=None` for future user uploads). **No persistent `is_agent_running` boolean** (derived at read time).

### 3.2 Firestore layout (Shape B + user-scoped)

| Path | Purpose |
|---|---|
| `accounts/{account_id}/chat_sessions/{session_id}` | Side-table row. One per ADK session. |
| `accounts/{account_id}/chat_sessions/{session_id}/artifacts/{artifact_id}` | Artifact metadata index. |
| `users/{user_id}/chat_categories/{category_id}` | Per-user categories. One of five user-scoped subcollections in the codebase (alongside `notification_status` and `preferences` per `firestore_notification_repository.py`, and `notifications` and `security` per `routers/users.py`). Registered in DM-PRD-05's `USER_SUBCOLLECTIONS` so the user-deletion sweep covers it. — see README §7.2. |

**Four composite indexes** (CH-PRD-01 §4.3) — two sidebar variants (with/without category filter; both include `deleted_at` for index-covered tombstone exclusion), artifact listing, category dedup. Firestore security rules (`firestore.rules`) enforce per-user-per-account access; API-layer checks are belt-and-braces.

### 3.3 `session.state` extension — `todo_lists`

A new session-state key is introduced:

```python
session.state["todo_lists"] = {
    "<list_id>": {
        "list_id": str,
        "title": str,
        "is_current": bool,
        "created_at": str,               # ISO 8601
        "items": [
            {"item_id": str, "text": str, "completed": bool, "completed_at": str | None}
        ]
    }
}
```

Dict-of-lists (not list-of-lists) so a new todo list can be added without rewriting prior lists — agent tools append via dict-set. Max 20 lists per session; max 50 items per list. The `docs/KEN-E-System-Architecture.md` §3.6 session-state table is updated to include `todo_lists`.

### 3.4 Model context-window registry

```python
MODEL_CONTEXT_WINDOW_REGISTRY: dict[str, ModelContextWindowEntry] = {
    "gemini-2.0-flash": ModelContextWindowEntry(
        model_id="gemini-2.0-flash",
        context_window_max=128_000,
    ),
    "gemini-2.5-flash": ModelContextWindowEntry(...),
    "gemini-2.5-pro": ModelContextWindowEntry(...),
    # ...
}
```

**Only context-window sizes.** No pricing, no cost math. The registry powers the context-bar denominator on the status view and nothing else. A CI test (`test_context_window_registry_covers_deployed_models.py`) asserts every model id referenced from `app/adk/agents/*` is registered. Adding a model without registering a context window fails the build.

### 3.5 Execution model

- **Deployment target:** colocated with the main API. ADK callbacks run inside the Vertex AI Agent Engine deployment (`app/adk/`); the callbacks and the completion endpoint's `finally` block both POST the per-turn delta to the API's internal `/internal/chat/side-table/update` endpoint.
- **Callbacks:** `before_agent_callback` stamps `last_agent_started_at`. `after_agent_callback` (or the endpoint's `finally` block on cancellation / exception) flushes the per-turn accumulator and stamps `last_agent_stopped_at`. Exact callback signatures confirmed via Day-1 spike in CH-PRD-01; `docs/spike-adk-chat-callbacks.md` records the findings.
- **Per-turn accumulator:** the completion endpoint iterates `async for event in runner.run_async(...)`, feeding each event into a `SessionTurnAccumulator`. At end-of-turn, one Firestore `update` is issued with all deltas (token Increments, tool-call count, compaction summary if applicable, `message_count` +1 per `user`/`model` event). Batch-coalesced — writes never block the stream.
- **Post-compaction baseline:** when a compaction event arrives, `current_context_tokens` is recomputed as the sum of `usage_metadata.total_token_count` across the post-compaction active window (summary + overlap + last 10 retained events). Not "reset to 0" — the old naive reset would misleadingly show 0% immediately after compaction.
- **Events-based `is_agent_running`:** derived at read time from `last_agent_started_at > (last_agent_stopped_at OR epoch) AND (now - last_agent_started_at) < 10 min`. Self-expiring — a crashed invocation times out naturally. **No sweeper, no cron, no stuck state.**
- **SSE cancellation handling:** the completion endpoint's `finally` block always fires the accumulator flush + stamps `last_agent_stopped_at`, so even a user-cancelled stream records partial progress.
- **Sidebar polling:** 5–10s interval when visible; pauses on `visibilitychange` hidden. Infinite-scroll cursor batches 20 per page.
- **Observability:** Weave spans `chat.session.created`, `chat.session.updated_from_event`, `chat.side_table.list`, `chat.mark_read`, `chat.export`, `chat.delete`, `chat.artifact.registered`, `chat.orphan_scan.gcs`, `chat.orphan_scan.adk_session`. Cardinality bound by `session_id_hash` + `user_id_hash`.

## 4. API surface

### User-facing (session management + status + categories)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/chat/completions` | **Existing.** Extended with the per-turn accumulator + `finally`-block flush. Request/response unchanged. |
| `POST` | `/api/v1/chat/conversations` | **Existing.** Creates ADK session + side-table row. `conversation_name` → initial `title`. |
| `GET` | `/api/v1/chat/conversations?cursor=&category_id=&query=` | **Extended.** Cursor pagination, 30-day window, filters. Default limit 20, max 100. |
| `PUT` | `/api/v1/chat/conversations/{id}` | **Existing.** Body `{title}` (was `conversation_name`). Recomputes casefold `search_text`. |
| `DELETE` | `/api/v1/chat/conversations/{id}` | **Existing, extended.** Two-phase tombstone. Failures caught by CH-PRD-05's ADK-session orphan scan. |
| `GET` | `/api/v1/chat/conversations/{id}/history` | **Existing.** No change. |
| `GET` | `/api/v1/chat/conversations/{id}/status-detail` | **NEW.** Composite read. |
| `POST` | `/api/v1/chat/conversations/{id}/mark-read` | **NEW.** Sets `last_viewed_at = now()`. Rate-limited 60/min/session. |
| `GET` | `/api/v1/chat/conversations/{id}/export?format=markdown` | **NEW.** Streams markdown with 24-hour signed artifact URLs via `yaml.safe_dump`. Rate-limited 10/hour/session. |
| `PUT` | `/api/v1/chat/conversations/{id}/category` | **NEW.** Body `{category_id: str \| null}`. |
| `GET` | `/api/v1/chat/conversations/{id}/artifacts` | **NEW.** Metadata rows + 10-min signed GCS URLs. |
| `GET` | `/api/v1/chat/conversations/{id}/todos` | **NEW.** `session.state["todo_lists"]`. |
| `GET` | `/api/v1/chat/categories` | **NEW.** List user's categories. |
| `POST` | `/api/v1/chat/categories` | **NEW.** Body `{name}`. 64-char cap; casefold dedup. Rate-limit 20/hour/user. |
| `DELETE` | `/api/v1/chat/categories/{id}` | **NEW.** Bulk-clears `category_id` on affected sessions. Rate-limit 20/hour/user. |
| `GET` | `/api/v1/chat/sessions/recoverable` | **Existing, 30-day window.** Retained for the existing recovery UI. |
| `POST` | `/api/v1/chat/sessions/{id}/recover` | **Existing.** No change. |

**No `/compact` endpoint** (Compact-now out of v1).

### Internal

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/internal/chat/side-table/update` | OIDC. Body `{session_id, delta, idempotency_key}`. Idempotent on request-body hash. |

## 5. Interaction with existing + concurrent components

### 5.1 UI

Chat owns the `/chat` route and mounts inside UI-PRD-01's `LayoutC`. The top-nav `AccountSwitcher` remains the account source; Chat reads the selected account and passes it into every API call. Text-size preference from UI-PRD-01 is honored by `ChatInterface`. No UI PRD ships chat-specific components other than what Chat itself delivers — see §5.3 for the UI-PRD-02 scope adjustment.

### 5.2 Agentic Harness

Chat registers two ADK callbacks on the root runner: `before_agent_callback` (stamps `last_agent_started_at`) and `after_agent_callback` (flushes the per-turn accumulator, stamps `last_agent_stopped_at`). Per-event updates live in the completion endpoint's `async for event in runner.run_async(...)` loop, feeding a `SessionTurnAccumulator` that calls `.add_event(event)` per event. At end-of-turn, one Firestore `update` is issued. The completion endpoint's `finally` block ensures cancellation / exception still flushes the accumulator — no stuck state. The Agent Factory (AH-PRD-02) is the idiomatic registration site; if AH-PRD-02 hasn't shipped, CH-PRD-01 registers against the current hardcoded root path with a TODO.

### 5.3 UI-PRD-02 (coordination — scope adjustment complete)

UI-PRD-02's scope has been adjusted in `PROJECT-PLANNER.md`, `docs/design/components/ui/README.md`, and `docs/design/components/ui/projects/UI-PRD-02-core-shell-pages.md`. The `/chat` page, `ChatInterface`, `ThinkingBlock`, and `SessionsSidebar` are no longer in UI-PRD-02; CH-PRD-02 owns them end-to-end. UI-PRD-02 is now responsible for redesigning Authentication / AcceptInvitation / OrganizationSettings / AccountSettings / UserSettings onto the new shell, deleting legacy `Home.tsx`, and registering `/` as `<Navigate to="/chat" replace />`. Both PRDs land in Release 1 and must coordinate the `App.tsx` route registration (UI-PRD-02 lands the redirect; CH-PRD-02 lands the destination behind `chat_v2_enabled`).

### 5.4 Billing

Chat's per-session token aggregates are a display cache; Billing's per-org counters are the enforcement truth. Both consume `event.usage_metadata` via the shared `extract_billable_tokens(event)` helper in `app/adk/token_accounting.py`, **owned by Billing** per BL-PRD-02. If Billing has shipped first, Chat imports and uses. If Chat ships first, Chat lands the helper at the documented path **in Billing's namespace with Billing as PR reviewer and future maintainer**. A CI parity test asserts both consumers produce identical output on a fixed fixture.

**Chat does NOT implement cost display.** KEN-E's user-facing cost is determined by subscription level, not per-model token pricing; a meaningful per-session dollar amount would require session → org → subscription → rate lookups that are Billing's concern. Chat shows token counts only.

Chat reads `useOrgStatus` (owned by Billing) to render the chat-input disabled state when the org is `inactive_*`. No API coupling — UI composition only.

### 5.5 Billing — rate limit substrate (BL-PRD-05, soft)

Rate-limited Chat endpoints (`/mark-read`, `/categories`, `/category`, `/export`) use Billing's Firestore-backed sliding-window limiter when available. If BL-PRD-05 hasn't shipped when a Chat endpoint lands, the endpoint ships a minimal in-process limiter with a TODO to migrate. One-line swap once BL-PRD-05 merges.

### 5.6 Knowledge Graph (KG-PRD-04)

KG-PRD-04's daily idle-session sweep reads ADK sessions via `list_sessions`. It is extended to also read `chat_sessions.deleted_at` and skip tombstoned sessions. One if-statement; no data-model change. Chat does not own the sweep — KG-PRD-04 does — but the Chat team writes the integration line as part of CH-PRD-04 (delete endpoint) acceptance.

### 5.7 Automations

`PlanRun` sessions (owned by Automations) use a different ADK `app_name` and do not appear in the Chat sidebar. Documented as an explicit exclusion in the component README §3.2.

### 5.8 Notifications

No new notification categories from Chat in v1.

### 5.9 Feature Flags

- `chat_v2_enabled` — master kill switch. `false` → new endpoints return 404; route falls back.
- `chat_status_detail_enabled` — gates the status view (CH-PRD-04). When false, the Session Status button is hidden.
- `chat_categories_enabled` — gates CH-PRD-03. When false, category dropdowns are hidden.

**No `chat_manual_compaction_enabled`** (Compact-now out of v1). **No placeholder-card flag for Permissions Approved** (not rendered at all). **Auth Status card inherits `integrations_connection_test_enabled`** from IN-PRD-07 — no Chat-owned flag. All three existing flags are targeted-rollout-capable.

## 6. Phasing

Five PRDs. Proposed prefix: `CH-PRD-NN`.

### CH-PRD-01 — Session metadata substrate (5 days, backend + ADK)

**Delivers:** Day-1 ADK callback spike; `ChatSessionMetadata` (no cost field; started/stopped timestamps instead of boolean), `ChatArtifactIndex` (no creator field), `TodoItem`, `TodoList`, `ChatStatusDetail`, `ModelContextWindowEntry` Pydantic shapes; Shape B Firestore layout + 4 composite indexes; Firestore security rules enforcing per-user-per-account access; `ChatSessionSideTableService` with create/get/list/update_from_delta/tombstone; `chat_callbacks.py` with `before_agent_callback` + `after_agent_callback`; `SessionTurnAccumulator`; `chat/context_windows.py` registry + CI coverage test; `extract_billable_tokens` helper at `app/adk/token_accounting.py` (Billing-owned); 30-day `RECOVERY_WINDOW_DAYS` lift + `CHAT_LIST_WINDOW_DAYS = 30`; `migrate_chat_side_table_backfill.py` one-shot (guards against ADK Issue #3154); `POST /internal/chat/side-table/update` OIDC bridge; SSE cancellation / exception `finally` flush; three feature flags registered; post-compaction context baseline algorithm; `message_count` rule; public-facing side-table-integrated endpoints (`POST /conversations` creates side-table row; `GET /conversations` cursor-paginated signature).

**Exit criteria:** Day-1 spike complete; every ADK session a user has created maps to a side-table row after back-fill; callbacks fire on the hot path; SSE cancellation flushes the accumulator; `is_agent_running` derivation returns correctly across 6 state combinations; the `extract_billable_tokens` helper has one caller (Chat) and passes parity tests with Billing; 30-day window lift observed in both recovery and list endpoints.

**Blocked by:** DM-PRD-00, DM-PRD-05, FF-PRD-01.

**Blocks:** CH-PRD-02, CH-PRD-03, CH-PRD-04, CH-PRD-05.

### CH-PRD-02 — Chat page shell & sidebar (5 days, frontend + thin backend)

**Delivers:** `frontend/src/pages/Chat.tsx`; `frontend/src/components/chat/SessionsSidebar.tsx` (port + wire); `ChatInterface.tsx` (port + wire); `SessionStatusDot.tsx`; `useChatSessions` TanStack infinite query with 5–10s polling; `mark-read` wiring via IntersectionObserver on the latest agent message; search (casefold substring against `search_text`); `/api/v1/chat/conversations` extension with cursor + category filter + query param; `POST /mark-read` endpoint; `/chat` route registered with `chat_v2_enabled` flag; **follow-up PR to delete `frontend/src/services/chatService.ts`**; load-test gate (1000 concurrent sidebar polls, p95 <100ms).

**Exit criteria:** user can open `/chat`, see 30-day session history, search + filter, scroll to load more, and the sidebar dots flip active → needs-review → idle; chatService.ts gone after the follow-up; load-test p95 <100ms.

**Blocked by:** CH-PRD-01, UI-PRD-01, FF-PRD-03.

**Blocks:** CH-PRD-03, CH-PRD-04, CH-PRD-05.

### CH-PRD-03 — Session categories (3 days, full-stack)

**Delivers:** `users/{user_id}/chat_categories/*` collection + composite index; `ChatCategoryDefinition` model (with `name_casefold` dedup); `chat/categories.py` service; four new endpoints (`GET /categories`, `POST /categories`, `DELETE /categories/{id}`, `PUT /conversations/{id}/category`); `CategoriesDropdown.tsx` (shared component with inline "+ New" + trash-icon delete + confirm popover); sidebar category filter wiring; status-view assign dropdown wiring (mount point reserved by CH-PRD-04); rate limits via BL-PRD-05 substrate or in-process fallback.

**Exit criteria:** user can create, assign, and delete categories; deleting a category silently clears `category_id` on every affected session without orphaning; sidebar filter narrows results correctly; dedup on casefold name works (Turkish dotted-i handled correctly).

**Blocked by:** CH-PRD-02.

**Parallel with:** CH-PRD-04, CH-PRD-05.

### CH-PRD-04 — Session status view (~6 days, full-stack — base 4 days + ~1 day for the Authentication Status card + ~1 day for auto-title generation)

**Delivers:** `SessionStatusView.tsx` (port + scope-adjusted — **no Compact-now, no Permissions Approved card, no cost line**); **`AuthStatusCard.tsx` (§5.6)** replacing the figma's Loaded Tools card — pure frontend composition over IN-PRD-03's `useConnections(accountId)` with four per-row states and deep-links to `/settings/integrations/{connection_id}`; ships **read-only** (soft dep on IN-PRD-07 — the per-row Check Status button turns on once IN-PRD-07's flag + hook + `last_tested_at` field land); "Session Status" header toggle button; `status-detail` composite endpoint; `TokenUsagePanel.tsx` (context bar + 3-card token grid — no cost); `chat/export.py` markdown-export streamer using `yaml.safe_dump` with 24-hour signed artifact URLs; **once-per-session auto-title generation in `chat/auto_title.py` using `gemini-2.5-flash` (§5.7) — fired async after the first assistant response, billable through BL-PRD-02, suppressed by manual edits, gated by `chat_auto_title_enabled`**; PUT title endpoint with casefold search_text recomputation **+ synchronous `auto_title_attempted_at` stamp**; DELETE two-phase tombstone with async Cloud Run cleanup; summary figma deviation fix (read-only); rate limits via BL-PRD-05.

**Exit criteria:** user can open the status view for any session and see every field populated; visual regression asserts absence of Compact-now button + Permissions card + cost line AND presence of the Authentication Status card; Auth Status card renders all four row states correctly against a seeded account (one connected, one expired, one not-connected); Delete tombstones the session and sidebar refreshes; Export downloads a valid markdown transcript with `yaml.safe_dump` front-matter + 24-hour artifact links; first-turn auto-title populates within 10s on the happy path, leaves title null + stamps `auto_title_attempted_at` on Gemini failure, never retries, and is suppressed by a manual title edit racing the generator.

**Blocked by:** CH-PRD-02.

**Parallel with:** CH-PRD-03, CH-PRD-05.

### CH-PRD-05 — Todo lists + artifacts (4 days, full-stack + ADK)

**Delivers:** `set_todo_list` + `update_todo_list` agent tools with dict-of-lists state convention; `todo_lists` addition to `docs/KEN-E-System-Architecture.md` §3.6; `TodoListsPanel.tsx` (read-only renderer); `chat/artifacts.py` `register_artifact(tool_context, filename, content, created_by_tool)` wrapper (**no `creator` parameter**); migration of `strategy_agent/artifact_utils.py`; CI lint (`check_artifact_register.py`); `ArtifactsPanel.tsx` (all artifacts render with "KEN-E" badge in v1 since no user-upload path); `GET /todos` + `/artifacts` endpoints; daily GCS-blob orphan scan; **daily ADK-session orphan scan — safety net for CH-PRD-04 delete-cleanup failures** (auto-cleans tombstoned orphans >1h old; pages ops on missing orphans).

**Exit criteria:** agent tool → state → UI loop works; every artifact saved via wrapper shows with correct `created_by_tool` provenance; lint rule blocks raw `save_artifact` calls; both orphan scans run correctly with Weave telemetry and Slack/PagerDuty alerts on drift.

**Blocked by:** CH-PRD-02.

**Parallel with:** CH-PRD-03, CH-PRD-04.

## 7. Non-goals

- **Per-session cost display.** Subscription-level pricing complexity deferred. Chat shows token counts only; Billing is the sole owner of cost display at any level.
- **Manual Compact-now button.** Deferred beyond v1. ADK's automatic compaction still runs. Will return as a future PRD once the ADK manual-compaction API stabilizes.
- **"Permissions Approved" status-view card.** Not rendered at all in v1. No placeholder, no mock data, no flag. Future PRD wires it when it becomes a real feature.
- **"Loaded Tools" status-view card is replaced** by a new Authentication Status card (CH-PRD-04 §5.6). The figma's generic "tool-loading status" concept is re-framed as "account-level integration auth status" — the data users actually want to see before engaging an agent with a platform-dependent task.
- **User-writable summary.** Agent-authored. Users who want to override should set a session title instead.
- **User-writable todo lists.** Agents own the checkboxes.
- **Session sharing between users.** Always scoped to one `(user_id, account_id)`.
- **Multi-format export.** Markdown only in v1. PDF / JSON deferred.
- **Bulk operations.** No multi-select delete, no multi-select category assign, no bulk export.
- **Archive vs delete.** Delete is the only destructive action. The 30-day window already hides stale sessions.
- **Session-search full-text ranking.** Casefold substring match on `search_text` only. No TF-IDF, no fuzzy, no Algolia.
- **Session pinning.**
- **Real-time sidebar updates via SSE / websocket.** v1 uses 5–10s polling.
- **Cross-session todo rollup.**
- **Per-category color or icon customization.**
- **Quick actions from the sidebar** (rename, delete, change category in a right-click menu). All mutations happen in the status view.

## 8. Dependency graph

```
DM-PRD-00 (Shape B + registry)    ─┐
DM-PRD-05 (recursive_delete)      ─┤
FF-PRD-01 (backend feature flags) ─┤
UI-PRD-01 (design system)         ─┤
FF-PRD-03 (frontend feature flags)─┤
                                    │
                                    ▼
                          ┌───────────────────┐
                          │    CH-PRD-01      │  Session metadata substrate
                          │                   │  side-table, callbacks, accumulator,
                          │                   │  events-based status, security rules
                          └─────────┬─────────┘
                                    │
                                    ▼
                          ┌───────────────────┐
                          │    CH-PRD-02      │  /chat page + sidebar
                          │                   │  status dots + mark-read + load test
                          └─────────┬─────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                ▼                   ▼                   ▼
      ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
      │    CH-PRD-03      │ │    CH-PRD-04      │ │    CH-PRD-05      │
      │ Categories        │ │ Status view       │ │ Todos + artifacts │
      │                   │ │ (no compact, no   │ │ (no creator field,│
      │                   │ │ placeholders,     │ │ + 2 orphan scans) │
      │                   │ │ no cost)          │ │                   │
      └───────────────────┘ └───────────────────┘ └───────────────────┘

Soft peers: BL-PRD-02 (extract_billable_tokens, Billing-owned)
            BL-PRD-05 (rate-limit substrate)
```

## 9. Risks

| Risk | Mitigation |
|---|---|
| Day-1 ADK callback spike finds different names or missing primitives | Spike is the gating first task. §5.2 of CH-PRD-01 amended before implementation. Per-event updates via event-loop accumulator are the fallback already in the design. |
| SSE cancellation doesn't fire `after_agent_callback` | The completion endpoint's `finally` block always fires the accumulator flush — authoritative regardless of ADK callback behavior. |
| Side-table diverges from ADK ground truth | Daily reconciliation via CH-PRD-05's two orphan scans (GCS blobs + ADK sessions vs side-table) catches drift within 24h. |
| Firestore write amplification (many event increments per turn) | One `update` per turn via accumulator batch-coalesce. Tested. |
| ADK upgrade changes event shape → callback silently breaks | Integration test + parity test asserts the helper produces expected output on every PR. |
| Search `search_text` denormalization drifts after compaction | Accumulator rewrites `search_text` on the same turn the summary changes. Unit-tested invariant. |
| 5–10s polling scales poorly (>1000 sessions) | 30-day window caps active size; cursor pagination caps batch size. CH-PRD-02 load-test gates at p95 <100ms. Polling pauses when hidden. |
| Delete cleanup task fails silently | CH-PRD-05's nightly ADK-session orphan scan catches it within 24h. |
| ADK-session orphan scan finds missing side-table rows | Pager alert (indicates side-table-write bug); no auto-cleanup. |
| Category delete on a session the user is currently viewing | Client invalidates the status-view query on any category mutation; rehydrates with `category_id=null`. |
| Agent writes malformed `todo_lists` dict | Pydantic validation on read drops malformed entries with warning log. Tool helpers normalize on write. |
| Artifact blob exists in GCS but no Firestore index row (raw save_artifact bypass) | CI lint rule + nightly GCS orphan scan; orphans reported to ops. |
| Token-definition drift between Chat and Billing | Shared `extract_billable_tokens` under Billing ownership + CI parity test. Divergence fails build. |
| Export endpoint leaks a signed GCS URL | Authorization check (session owner); 24-hour TTL on export URLs is a deliberate UX tradeoff (links usable hours after download); `artifact_links_valid_until` surfaced in front-matter. |
| `App.tsx` route registration race between UI-PRD-02 and CH-PRD-02 | Both ship in Release 1; coordinate landing order at PR review. UI-PRD-02 lands `/` redirect; CH-PRD-02 lands `/chat` destination behind `chat_v2_enabled`. The flag-gated fallback (CH-PRD-02 §2.1) handles the ordering gap if they merge out of order. |
| ADK `list_sessions` Issue #3154 returns empty `user_id` | Back-fill reads `user_id` from iteration loop, never trusts `Session.user_id`. ADK-session orphan scan uses same guard. |
| 30-day window cutoff hides an active session | `updated_at` is rolling on every event; opening/editing bumps it. |
| Post-compaction context baseline miscomputes | Unit-tested pure function; worst case is transient display oddity (much better than naive reset-to-0). |

## 10. Open questions

Decisions that need a product / ops call before or during implementation.

1. ~~**UI-PRD-02 scope adjustment** (§5.3).~~ **Resolved** — UI-PRD-02 scope adjustment is complete in `PROJECT-PLANNER.md`, `docs/design/components/ui/README.md`, and `docs/design/components/ui/projects/UI-PRD-02-core-shell-pages.md`. UI-PRD-02 owns the `/` → `/chat` redirect; CH-PRD-02 owns `/chat`.
2. **Artifact user-upload surface timing.** v1 has no user-upload UI; `created_by_tool=None` is latent. Is there a v2 PRD already scheduled to surface user uploads? → If not, the latent shape stays; if yes, schedule it.
3. **Export format in v2.** Markdown v1 is settled. JSON / PDF demand should be driven by data.
4. **`STUCK_THRESHOLD` for `is_agent_running` derivation.** 10 min is the proposal; revisit if users report stuck "working…" indicators.
5. **Compact-now return.** Is there a target quarter to bring it back? Depends on ADK API evolution.
6. **"Permissions Approved" card return.** Will come back when the real feature ships. Separate PRD.
7. **Multi-currency token display.** Not for v1. If it ever matters, coordinate with Billing.

## 11. Success criteria

- User can open `/chat`, see 30-day session history in the sidebar, search across name + category + summary, filter by category, and load older sessions via infinite scroll — all within 1 second of initial page load on a warm cache.
- Status dots correctly reflect session state: **Active** transitions to **Needs Review** within 2s of the agent's final event; **Needs Review** transitions to **Idle** within 2s of the user scrolling the latest message into view.
- Status view displays every in-scope figma field (name, category, summary, todo lists, artifacts, tokens, context, activity summary, duration, export, delete) with real data + the new Authentication Status card with account-level integration state. Compact-now, Permissions Approved, and cost line do NOT appear.
- Delete is instant from the user's perspective (<200ms UI); async cleanup completes within 5 minutes or is caught by CH-PRD-05's ADK-session orphan scan within 24 hours.
- Export generates a valid markdown file with `yaml.safe_dump` front-matter (hostile-character-safe) within 10s for sessions under 50 events; artifact URLs valid for 24 hours.
- Token aggregates match Billing's per-session projection within 0.5% at month-end reconciliation.
- Zero divergence between Chat's `extract_billable_tokens` result and Billing's (asserted by CI).
- Artifact provenance (`created_by_tool`) is correct on 100% of test agent-tool artifacts (lint rule + runtime test).
- Firestore security rules reject cross-user reads on `chat_sessions/*` (asserted by emulator test).
- Sidebar list endpoint p95 <100ms at 1000 concurrent polls (asserted by CH-PRD-02 load test).
- All five PRDs shippable in four sprints.
