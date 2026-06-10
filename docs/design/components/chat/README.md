# Chat — Product Requirements Document

> **Linear Team:** [KEN-E] Chat
> **Last Updated:** 2026-04-24
> **Status:** Draft — substrate designed, 5 PRDs scoped, not yet implemented
> **Backend session service:** Google ADK `VertexAiSessionService` (app_name = `ken_e_chatbot`)

## 1. Overview

The Chat component is KEN-E's **conversational surface**. It owns the `/chat` page, the session history sidebar, the session status view, the per-user category system, the session metadata substrate that mirrors ADK sessions into Firestore for pagination / search / listing, the once-per-session auto-title generator (`gemini-2.5-flash`, fired after the first assistant response, billable through BL-PRD-02), and every ADK hook that feeds the substrate (token counters, compaction summaries, tool-call counts, artifact provenance). No other component renders chat messages, lists sessions, writes to `accounts/{account_id}/chat_sessions/*`, maintains the per-user `chat_categories` collection, or reads `session.state["todo_lists"]` for the UI.

Six facts shape the design. **Sessions are per-user-per-account** — every session is scoped to exactly one `(user_id, account_id)` tuple, matching how the existing `/api/v1/chat/completions` code path already scopes its state; the sidebar lists only that user's sessions for the currently selected account. Firestore security rules enforce this server-side. **ADK is the source of truth for conversation events**, but ADK's `VertexAiSessionService` has no native pagination, no sorting, no full-text search, no session title, and sparse artifact metadata — so a **Firestore `chat_sessions` side-table** mirrors every ADK session and adds the product fields (title, category, summary cache, search text, activity timestamps, token aggregates, artifact index). **State denormalization happens in ADK callbacks + the completion endpoint's event loop**, not on the read path — `before_agent_callback` / `after_agent_callback` stamp start/stop timestamps + flush per-turn token counters, keeping the hot-read sidebar fast. **`is_agent_running` is a derived field**, not a persistent boolean — computed at read time from `last_agent_started_at`, `last_agent_stopped_at`, and a 10-minute stuck-threshold; no in-process sweeper is needed. **Multi-session concurrency is a first-class capability** — a user can send messages in session A, switch to session B, and see session A transition from active to needs-review without reloading; the sidebar polls a lightweight status endpoint. **"Read-only" on the user's side, for summary and todo lists** — the compaction summary and todo-list checkboxes are agent-authored state; the user views but does not edit them, so there is no merge conflict between user writes and agent state updates.

**Scoped out of v1 (scope from the user on 2026-04-24 qreview):** per-session cost display (subscription-level pricing is Billing's concern — Chat shows token counts only), manual Compact-now button (ADK auto-compaction still runs), and the "Permissions Approved" figma card (not rendered at all; future PRD when it becomes a real feature). The figma's "Loaded Tools" card is **replaced** by a new **Authentication Status** card (CH-PRD-04 §5.6) that lists account-level integrations with state-dependent CTAs; ships read-only in v1 using IN-PRD-03's `/connections` data, and the per-row Check Status button is enabled once IN-PRD-07 ships (soft dep; flag-gated).

A developer reading only this section should understand: this component owns the `chat_sessions/*`, `chat_categories/*` (per-user), and the session-scoped `artifacts/*` subcollection. It owns the `/api/v1/chat/*` user-facing surface in full — the existing endpoints plus new additions for categories, artifacts, todos, status detail, mark-read, and export. It owns the production `/chat` page, the expandable `SessionsSidebar`, the `SessionStatusView`, and every hook that feeds them. It ships across **5 project PRDs (CH-PRD-01 → CH-PRD-05)** and is required by the UI shell (the `/chat` route mounts here), Billing (reads `is_agent_running` derived-field for the inactive banner's "finish current turn" affordance), Knowledge Graph (KG-PRD-04's session-end sweep respects `deleted_at`), and the Agentic Harness (every LLM-consuming turn emits ADK callbacks that Chat subscribes to + the completion endpoint iterates the event stream into a per-turn accumulator).

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Session creation                                                            │
│    POST /api/v1/chat/conversations (existing endpoint, extended)            │
│      → VertexAiSessionService.create_session(app_name, user_id, state={..}) │
│      → write chat_sessions/{session_id} side-table doc (title=null,         │
│          category_id=null, tokens=0, last_agent_started_at=null, ...)       │
│      → write_audit(event="chat_session_created") [soft dep on DM-PRD-07]    │
└─────────────────────────────────────────────────────────────────────────────┘

                            Per-turn event flow (hot path)

┌─────────────────────────────────────────────────────────────────────────────┐
│  Agentic Harness LLM call                                                   │
│    1. before_agent_callback → side_table.last_agent_started_at = now()      │
│    2. completion endpoint iterates `async for event in runner.run_async()`: │
│         accumulator.add_event(event)                                        │
│         - if event.usage_metadata:                                          │
│             accumulator += extract_billable_tokens(event)                   │
│             (shared helper owned by Billing BL-PRD-02)                      │
│         - if event.type == "tool_call": tool_call_count += 1                │
│         - if event.author in ("user", "model"): message_count += 1          │
│         - if event.type == "compaction_summary":                            │
│             accumulator.latest_summary = event.content                      │
│             accumulator.post_compaction_context_tokens =                    │
│                 sum(e.usage_metadata.total_token_count for e in             │
│                     post_compaction_window)                                 │
│         yield format_sse(event)                                             │
│    3. finally / after_agent_callback (whichever fires first):               │
│         one Firestore update with accumulator.build_delta():                │
│         last_agent_stopped_at = now()                                       │
│         input_tokens_total += Increment                                     │
│         output_tokens_total += Increment                                    │
│         reasoning_tokens_total += Increment                                 │
│         current_context_tokens = accumulator.post_compaction_context_tokens │
│           if compaction happened, else Increment(turn_tokens)               │
│         latest_summary / summary_updated_at / compaction_count if applicable│
│         search_text = casefold(title + category_name + latest_summary)     │
└─────────────────────────────────────────────────────────────────────────────┘

                              Sidebar status polling

┌────────────────┐   GET /api/v1/chat/conversations?cursor=...   ┌────────────┐
│ SessionsSidebar├──────────────────────────────────────────────►│  Chat API  │
│ (infinite      │ sorted by updated_at DESC, 30-day window      │            │
│  scroll, 5–10s │ filtered by category / search text            │ returns:   │
│  poll on       │                                               │ {items[],  │
│  visible page) │                                               │  next_cursor}  │
│                │◄──────────────────────────────────────────────┤            │
│                │  items include last_agent_started_at,         │            │
│                │  last_agent_stopped_at, last_viewed_at →      │            │
│                │  client derives active / needs-review / idle  │            │
└────────────────┴───────────────────────────────────────────────┴────────────┘

                              User opens a session

┌─────────────────────────────────────────────────────────────────────────────┐
│  Route to /chat?session={id}                                                 │
│    1. GET /api/v1/chat/conversations/{id}/history     (existing, unchanged) │
│    2. GET /api/v1/chat/conversations/{id}/status-detail  (NEW: composite)   │
│         returns metadata, artifacts[], todo_lists[], and server-derived     │
│         fields: is_agent_running, context_usage_percent, duration_seconds,  │
│         activity_summary, total_tokens                                      │
│    3. POST /api/v1/chat/conversations/{id}/mark-read   (NEW: side-effect)   │
│         sets last_viewed_at = now() → sidebar indicator flips to idle        │
└─────────────────────────────────────────────────────────────────────────────┘

                              Status-view actions

┌─────────────────────────────────────────────────────────┐
│  Edit title  → PUT /conversations/{id}                  │  updates title + casefold(search_text)
│  Set cat.    → PUT /conversations/{id}/category         │  updates category_id + casefold(search_text)
│  Export      → GET /conversations/{id}/export           │  streams markdown; 24h signed URLs for artifacts
│  Delete      → DELETE /conversations/{id}                │  tombstones side-table (deleted_at=now);
│                                                         │  async Cloud Run cleanup of ADK + GCS;
│                                                         │  failures caught by CH-PRD-05 orphan scan
└─────────────────────────────────────────────────────────┘

(No Compact-now button — deferred from v1.
 No cost display — subscription-level pricing is Billing's concern.
 No Permissions Approved card — not rendered at all.
 Authentication Status card — renders account-level integration status;
 read-only until IN-PRD-07's Check Status button is enabled.)

                              Categories (per user)

┌─────────────────────────────────────────────────────────────────────────────┐
│  Sidebar filter dropdown / Status-view assign dropdown                       │
│    GET  /api/v1/chat/categories                     list user's categories   │
│    POST /api/v1/chat/categories                     create (+ New); dedup   │
│                                                     on casefold(name)        │
│    DELETE /api/v1/chat/categories/{id}              delete (trash icon);    │
│                                                     bulk re-assign every     │
│                                                     affected session to      │
│                                                     category_id=null         │
└─────────────────────────────────────────────────────────────────────────────┘

              Daily reconciliation (CH-PRD-05) — staging + prod
              (dev is local-only; run on demand via the CLI)

┌─────────────────────────────────────────────────────────────────────────────┐
│  04:00 UTC — GCS blob orphan scan: alert on blobs without metadata rows     │
│  04:30 UTC — ADK-session orphan scan: safety net for delete cleanup        │
│    - tombstoned side-table + live ADK session (> 1h) → auto-delete ADK     │
│    - live ADK session + missing side-table → page ops                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Key Directories

| Path | Purpose |
|------|---------|
| `api/src/kene_api/models/chat.py` | `ChatSessionMetadata`, `ChatSessionSummary`, `ChatCategoryDefinition`, `ChatArtifactIndex`, `ChatStatusDetail`, `TodoList`, `TodoItem` Pydantic shapes. (CH-PRD-01) |
| `api/src/kene_api/chat/__init__.py` | Package entry. |
| `api/src/kene_api/chat/side_table.py` | `ChatSessionSideTableService` — `create`, `get`, `list_for_user`, `update_from_delta`, `tombstone`. The single write path into the side-table. (CH-PRD-01) |
| `api/src/kene_api/chat/side_table_handlers.py` | HTTP handlers for the internal `POST /internal/chat/side-table/update` endpoint that ADK-deployment callbacks post to. (CH-PRD-01) |
| `api/src/kene_api/chat/accumulator.py` | `SessionTurnAccumulator` — in-memory per-turn delta built by the completion-endpoint event loop, flushed in a `finally` / `after_agent_callback`. (CH-PRD-01) |
| `api/src/kene_api/chat/context_windows.py` | Model → `context_window_max` registry (used for the context meter only; **no pricing**, no cost math). Source of truth for the context-bar denominator. (CH-PRD-01) |
| `api/src/kene_api/chat/export.py` | `export_session_as_markdown(session_id)` — pulls events, renders a transcript with YAML front-matter via `yaml.safe_dump`, 24-hour signed GCS URLs for artifacts. (CH-PRD-04) |
| `api/src/kene_api/chat/cleanup_task.py` | Cloud Run background task for async ADK + GCS cleanup after delete. Failures caught by CH-PRD-05's ADK-session orphan scan. (CH-PRD-04) |
| `api/src/kene_api/chat/categories.py` | `list_categories(user_id)`, `create_category(user_id, name)` (casefold dedup), `delete_category(user_id, category_id)` (transactional bulk-clear). (CH-PRD-03) |
| `api/src/kene_api/chat/artifacts.py` | `register_artifact(tool_context, filename, content, created_by_tool)`, `list_artifacts(session_id)`. Sibling of ADK's `ArtifactService` — writes the metadata row, not the blob. (CH-PRD-05) |
| `api/src/kene_api/chat/todos.py` | `list_todo_lists(session_id)` — reads `session.state["todo_lists"]` from ADK via the session service; no writes (agent-owned). (CH-PRD-05) |
| `api/src/kene_api/chat/search.py` | `list_sessions(user_id, account_id, cursor, category_id?, query?)` — Firestore cursor pagination + server-side casefold substring search against denormalized `search_text`. (CH-PRD-02) |
| `api/src/kene_api/routers/chat.py` | **Extended** — all new endpoints added alongside the existing 9. (CH-PRD-01..05) |
| `app/adk/agents/chat_callbacks.py` | **The only file that fires ADK callbacks.** `before_agent_callback` stamps `last_agent_started_at`; `after_agent_callback` flushes the accumulator via HTTP POST to the internal side-table-update endpoint. (CH-PRD-01) |
| `shared/token_accounting.py` | `extract_billable_tokens(event) → BillableTokenCounts`. **Billing-owned** (per BL-PRD-02); Chat consumes. Lives in the `shared/` package so both the API container and the Agent Engine deployment import it without sys.path trickery. (CH-PRD-01 lands the helper under Billing's namespace if BL-PRD-02 hasn't shipped.) |
| `app/adk/session/recovery.py` | **Modified** — `RECOVERY_WINDOW_DAYS = 30` (lifted from 7). (CH-PRD-01) |
| `app/adk/tools/todo_list_tools.py` | `set_todo_list`, `update_todo_list` ADK `FunctionTool`s. (CH-PRD-05) |
| `api/scripts/migrate_chat_side_table_backfill.py` | One-shot back-fill — walks every ADK session via `list_sessions` and writes a minimal side-table row so existing sessions show up in the sidebar. Idempotent. Guards against ADK Issue #3154 by reading `user_id` from the iteration loop, not `Session.user_id`. (CH-PRD-01) |
| `api/src/kene_api/chat/artifact_orphan_scan.py` | Daily GCS-blob orphan scan (report-only). Invoked by the `chat-artifact-orphan-scan` Cloud Scheduler job via the `/api/v1/internal/chat/orphan-scan/gcs` endpoint; runnable directly via `python -m kene_api.chat.artifact_orphan_scan`. (CH-PRD-05) |
| `api/src/kene_api/chat/adk_session_orphan_scan.py` | Daily ADK-session orphan scan — safety net for CH-PRD-04 delete-cleanup failures. Auto-deletes tombstoned orphans > 1h old; pages ops on missing orphans. Invoked by the `chat-adk-session-orphan-scan` Cloud Scheduler job via the `/api/v1/internal/chat/orphan-scan/adk-session` endpoint; runnable directly via `python -m kene_api.chat.adk_session_orphan_scan`. (CH-PRD-05) |
| `api/scripts/lint/check_artifact_register.py` | CI lint blocking raw `save_artifact()` calls outside the wrapper. (CH-PRD-05) |
| `api/scripts/lint/check_context_window_registry_coverage.py` | CI lint asserting every deployed model has a context-window registry entry. (CH-PRD-01) |
| `deployment/firestore.rules` | **New** — security rules gate `chat_sessions/*` reads on `resource.data.user_id == request.auth.uid` and `chat_categories/*` on `request.auth.uid == userId`; artifact subcollection reads are gated by parent-session ownership. `chat_sessions/*` and `artifacts/*` are server-write-only (`allow write: if false`). Deployed by `deployment/terraform/firestore_rules.tf`. (CH-PRD-01) |
| `frontend/src/pages/Chat.tsx` | Top-level route component. Owns route state (`?session=`), sidebar collapse state, `SessionStatusView` toggle. (CH-PRD-02) |
| `frontend/src/components/chat/SessionsSidebar.tsx` | Port of `docs/figma-export/src/app/components/SessionsSidebar.tsx`; production wiring to `/api/v1/chat/conversations` with infinite scroll + search + category filter + status dots. (CH-PRD-02) |
| `frontend/src/components/chat/SessionStatusDot.tsx` | 3-state (active / needs-review / idle) dot with tooltip. Used in sidebar and page header. (CH-PRD-02) |
| `frontend/src/components/chat/ChatInterface.tsx` | Port of `docs/figma-export/src/app/components/ChatInterface.tsx`; message list, input, artifact blocks, thinking blocks. Fires `mark-read` on latest-message visibility. (CH-PRD-02) |
| `frontend/src/components/chat/SessionStatusView.tsx` | Port + scope-adjusted version of `docs/figma-export/src/app/components/SessionSettings.tsx`; session details panel. **No Compact-now button. No Permissions Approved card. No cost line. Authentication Status card replaces the figma's Loaded Tools card (see `AuthStatusCard.tsx`).** (CH-PRD-04) |
| `frontend/src/components/chat/AuthStatusCard.tsx` | Account-level integration auth status on the session status view. Data from IN-PRD-03's `useConnections(accountId)`; per-row "Check Status" button flag-gated on `integrations_connection_test_enabled` (powered by IN-PRD-07 when shipped). Four states: Authenticated / Needs re-auth / Transient / Not connected. Row-click deep-links to `/settings/integrations/{connection_id}`. (CH-PRD-04 §5.6) |
| `frontend/src/components/chat/CategoriesDropdown.tsx` | Shared dropdown with inline "+ New" create + trash-icon delete per category. Used in sidebar filter and in status-view assign. (CH-PRD-03) |
| `frontend/src/components/chat/TodoListsPanel.tsx` | Read-only renderer for `todo_lists` from the status-detail payload; collapsible list, progress fraction, Current / Previous distinction. (CH-PRD-05) |
| `frontend/src/components/chat/ArtifactsPanel.tsx` | File-type icons + "KEN-E" badge (all v1 artifacts are agent-created) with tool name on hover. (CH-PRD-05) |
| `frontend/src/components/chat/TokenUsagePanel.tsx` | Context bar + 3-card token grid (Input / Output / Total) + activity-summary line. **No cost line.** (CH-PRD-04) |
| `frontend/src/components/chat/TitleCard.tsx`, `SummaryCard.tsx`, `ActivityCard.tsx` | Individual status-view cards. (CH-PRD-04) |
| `frontend/src/hooks/useChatSessions.ts` | TanStack Query infinite-query hook for the sidebar. 5–10s polling window on the active page. (CH-PRD-02) |
| `frontend/src/hooks/useChatSession.ts` | TanStack Query hook for the `/status-detail` endpoint. (CH-PRD-04) |
| `frontend/src/hooks/useChatCategories.ts` | Mutation-aware hook for category list + create + delete. (CH-PRD-03) |
| `frontend/src/lib/chatApi.ts` | **Extended** — typed wrappers for every new endpoint. (CH-PRD-02..05) |
| `frontend/src/services/chatService.ts` | **Deleted in a CH-PRD-02 follow-up PR** once all callers migrate to `lib/chatApi.ts`. No indefinite shim. |

### 2.2 Data Flow

1. **Session creation (CH-PRD-01).** `POST /api/v1/chat/conversations` stays the existing endpoint. It already creates an ADK session via `VertexAiSessionService.create_session`. After the ADK call, the extended handler writes a `ChatSessionMetadata` doc to `accounts/{account_id}/chat_sessions/{session_id}` with `title=null`, `category_id=null`, `tokens_*=0`, `last_agent_started_at=null`, `last_viewed_at=now()`. The existing pending-session pattern (`pending_*` IDs) is preserved.
2. **Per-turn meter + denormalization (CH-PRD-01).** Before the agent runs, `before_agent_callback` stamps `last_agent_started_at`. As events stream back, the completion endpoint's event loop iterates `async for event in runner.run_async(...)` and feeds each event into a `SessionTurnAccumulator` (in-memory per-turn delta). At end-of-turn — either via the `finally` block (SSE cancellation / exception) or via `after_agent_callback` — the accumulator's `build_delta()` output posts as one Firestore update. Token counts, tool-call counts, compaction summaries, and `message_count` (+1 per `user`/`model` event, excluding `system`/`tool`) all batch-coalesce into a single write. `current_context_tokens` recomputes correctly on compaction (sum of `usage_metadata` across the post-compaction event window), not a naive reset to 0.
3. **Events-based `is_agent_running`.** No persistent boolean field. No in-process sweeper. The status is **derived at read time** from the timestamps: `last_agent_started_at is not null AND (last_agent_stopped_at is null OR last_agent_started_at > last_agent_stopped_at) AND (now - last_agent_started_at) < 10 min`. A crashed invocation becomes naturally "not running" after 10 minutes.
4. **SSE cancellation / exception handling.** The completion endpoint's `finally` block always fires the accumulator flush — so even a user-cancelled stream records `last_agent_stopped_at` and persists partial token counts. Stuck state is impossible by construction.
5. **Sidebar list + status polling (CH-PRD-02).** `GET /api/v1/chat/conversations` is extended to paginate by `updated_at DESC` with a Firestore cursor token, filter by `account_id` (always), `category_id` (optional), the 30-day `updated_at >= now()-30d` window, and `query` (casefold substring against `search_text`). Response items include the three timestamps so the client derives active / needs-review / idle locally. The sidebar polls every 5–10s while the tab is visible.
6. **Session-detail assembly (CH-PRD-04).** `GET /api/v1/chat/conversations/{id}/status-detail` is one composite read returning the metadata doc + the artifact list + the `todo_lists` state snapshot + server-derived fields (`is_agent_running`, `context_usage_percent`, `duration_seconds`, `activity_summary`, `total_tokens`).
7. **Mark-as-read (CH-PRD-02).** On the client, when the latest agent message becomes visible in the message list (IntersectionObserver), fire `POST /api/v1/chat/conversations/{id}/mark-read`. Server sets `last_viewed_at=now()`. The next sidebar poll sees `last_agent_message_at <= last_viewed_at` and the indicator flips to idle.
8. **Category CRUD (CH-PRD-03).** Categories live under `users/{user_id}/chat_categories/{category_id}` (user-scoped). `POST /categories` creates with trimmed + dedup-by-casefold name; `DELETE /categories/{id}` runs transactions that clear `category_id` on every affected session (batched at 400 writes per transaction) then deletes the category doc.
9. **Search-text reconciliation.** `search_text` is `casefold(title + " " + category_name + " " + latest_summary)` — Unicode-safe case folding. Rewritten by the accumulator on every turn (summary might have changed) and on every title / category change.
10. **Export (CH-PRD-04).** `GET /conversations/{id}/export?format=markdown` streams a markdown transcript — YAML front-matter via `yaml.safe_dump` (hostile-character safe) with title, category, duration, tokens, then message log with tool-call inlines and artifact references. **24-hour TTL on signed GCS URLs embedded in the export** (longer than the 10-minute TTL used for in-app listing, because exports are read later). `artifact_links_valid_until` timestamp surfaces in the front-matter.
11. **Delete (CH-PRD-04).** `DELETE /conversations/{id}` is a two-phase tombstone: (a) set `deleted_at=now()` on the side-table (hides from sidebar immediately); (b) Cloud Run background task calls `VertexAiSessionService.delete_session`, iterates GCS blobs, and cleans Firestore. **Cleanup-task failures are caught by CH-PRD-05's nightly ADK-session orphan scan.**
12. **Artifact registration (CH-PRD-05).** Every agent tool that needs to save an artifact calls `chat.artifacts.register_artifact(...)` which wraps `context.save_artifact(...)` — the wrapper writes both the ADK blob and the Firestore metadata row with `created_by_tool=<tool_name>`. v1 has no user-upload path; `created_by_tool=None` is reserved for a future upload UI.
13. **Todo list rendering (CH-PRD-05).** The Agent Factory registers `set_todo_list` and `update_todo_list` tools that write into `session.state["todo_lists"][list_id]`. The UI reads via `/status-detail` (server reads `session.state` through `VertexAiSessionService.get_session`). The user never writes — checkboxes are disabled. Shape is a dict keyed by `list_id` so multiple lists co-exist.

### 2.3 API Contracts

Owned endpoints (existing endpoints retained; new endpoints marked NEW):

| Endpoint | Method | Owner | Purpose |
|----------|--------|-------|---------|
| `/api/v1/chat/completions` | POST | CH-PRD-01 (callbacks + event-loop accumulator only) | **Existing.** Extended with `before_agent_callback` / `after_agent_callback` stamping + per-turn accumulator. Request/response shape unchanged. |
| `/api/v1/chat/conversations` | POST | CH-PRD-01 | **Existing.** Creates ADK session + side-table row. `conversation_name` optional (sets initial `title`). |
| `/api/v1/chat/conversations` | GET | CH-PRD-02 | **Extended.** Cursor pagination via `cursor` query param; sorts by `updated_at DESC`; 30-day window; filters by `category_id`, `query`, `account_id`; returns `items[]` + `next_cursor`. |
| `/api/v1/chat/conversations/{id}` | PUT | CH-PRD-04 | **Existing, extended.** Body `{title}`. Updates both the ADK session and the side-table; recomputes `search_text` (casefold). |
| `/api/v1/chat/conversations/{id}` | DELETE | CH-PRD-04 | **Existing, extended.** Two-phase tombstone (side-table `deleted_at` + async cleanup). |
| `/api/v1/chat/conversations/{id}/history` | GET | (existing, unchanged) | Event-stream → message list. No change. |
| `/api/v1/chat/conversations/{id}/status-detail` | GET | CH-PRD-04 | **NEW.** Composite: metadata + artifacts + todo_lists + server-derived fields. |
| `/api/v1/chat/conversations/{id}/mark-read` | POST | CH-PRD-02 | **NEW.** Sets `last_viewed_at = now()`. Idempotent; dedup window 5s server-side. |
| `/api/v1/chat/conversations/{id}/export?format=markdown` | GET | CH-PRD-04 | **NEW.** Streams markdown transcript with 24-hour signed artifact URLs. `format=markdown` only in v1. Rate-limited 10/hour/session. |
| `/api/v1/chat/conversations/{id}/category` | PUT | CH-PRD-03 | **NEW.** Body `{category_id: str \| null}`. Updates side-table + casefold(`search_text`). |
| `/api/v1/chat/conversations/{id}/artifacts` | GET | CH-PRD-05 | **NEW.** Lists artifact metadata rows; resolves signed GCS URLs with 10-min TTL on request. |
| `/api/v1/chat/conversations/{id}/todos` | GET | CH-PRD-05 | **NEW.** Thin wrapper around `VertexAiSessionService.get_session(id).state["todo_lists"]`. |
| `/api/v1/chat/categories` | GET | CH-PRD-03 | **NEW.** Lists the user's categories. |
| `/api/v1/chat/categories` | POST | CH-PRD-03 | **NEW.** Body `{name: str}`. 64-char name cap; dedup on casefold within user. Returns the new category. |
| `/api/v1/chat/categories/{id}` | DELETE | CH-PRD-03 | **NEW.** Deletes + bulk-clears `category_id` on affected sessions. Rate-limited 20/hour/user. |
| `/api/v1/chat/sessions/recoverable` | GET | (existing, modified) | **Existing, window lifted to 30 days.** Retained for the existing recoverable-session picker. |
| `/api/v1/chat/sessions/{id}/recover` | POST | (existing, unchanged) | Existing recovery flow. |
| `/api/v1/internal/chat/side-table/update` | POST | CH-PRD-01 | **NEW internal.** OIDC. Body `{session_id, delta, idempotency_key}`. The bridge from ADK-deployment callbacks and the completion endpoint's `finally` to the side-table service. |

**No `POST /compact` endpoint** — manual Compact-now is out of v1.

Schema source of truth: `api/src/kene_api/models/chat.py` (Pydantic), mirrored in `frontend/src/lib/chatApi.ts`. URL paths use kebab-case (`status-detail`, `mark-read`); Firestore paths use snake_case (`chat_sessions`, `chat_categories`).

### 2.4 Key Abstractions

| Abstraction | Path | Purpose |
|-------------|------|---------|
| `ChatSessionMetadata` | `api/src/kene_api/models/chat.py` | The side-table doc. No `cost_usd_cents` field (cost display is out of scope). `last_agent_started_at` + `last_agent_stopped_at` replace the old `is_agent_running` boolean — running state is derived at read time. |
| `ChatCategoryDefinition` | Same | Per-user. `name_casefold` for Unicode-safe dedup. |
| `ChatArtifactIndex` | Same | One per artifact. `created_by_tool: str \| None` — non-null in v1 (agent-created); `None` reserved for future user uploads. No separate `creator` field. |
| `ChatStatusDetail` | Same | Composite response shape for `/status-detail`. Includes server-derived `is_agent_running`, `context_usage_percent`, `duration_seconds`, `activity_summary`, `total_tokens`. No `cost_usd_display`. |
| `TodoList` + `TodoItem` | Same | Read-only shapes matching the `session.state["todo_lists"]` convention. In the supervisor-orchestration model ([AH-PRD-05](../agentic-harness/projects/AH-PRD-05-multi-step-workflows.md)), `TodoItem` gains supervisor ledger fields: `assignee` (specialist doc_id), `query` (task query), `criteria` (acceptance criteria for the review-loop wrapper), `depends_on` (list of upstream item_ids), `result_key` (session-state key where the specialist writes its output), and a widened `status` enum (`pending` \| `dispatched` \| `awaiting_review` \| `completed` \| `failed`). These fields are **additive and backward-compatible** — the existing `set_todo_list` / `update_todo_list` tool surface is unchanged for users. The supervisor (not the user) writes the new fields. **Implementation note:** the `status` enum is widened from binary to 5-state; consumers using exhaustive pattern matching must handle the three new states (`dispatched`, `awaiting_review`, `failed`) gracefully. |
| `ChatSessionSideTableService.update_from_delta(session_id, delta)` | `api/src/kene_api/chat/side_table.py` | The single hook that applies a delta to the side-table. Uses `firestore.Increment` for token counters. |
| `ChatSessionSideTableService.list_for_user(user_id, account_id, cursor, category_id?, query?)` | Same | Cursor-paginated read. Applies 30-day window. Enforces `user_id` match server-side. |
| `SessionTurnAccumulator` | `api/src/kene_api/chat/accumulator.py` | In-memory per-turn delta: tokens, tool_call_count, message_count (user+model only), latest_summary, post-compaction context baseline. Single Firestore `update` per turn via `build_delta()`. |
| `before_agent_callback` / `after_agent_callback` | `app/adk/agents/chat_callbacks.py` | **The only ADK callback file.** Day-1 spike confirms signatures. Start timestamps + end-of-turn accumulator flush. |
| `extract_billable_tokens(event)` | `shared/token_accounting.py` | **Billing-owned** per BL-PRD-02. Shared helper: input + output + reasoning; cached-input excluded. Chat consumes. |
| `context_windows.get_model_context_window(model_id)` | `api/src/kene_api/chat/context_windows.py` | Registry lookup returning `context_window_max` only — no pricing, no cost math. Used for the context-bar denominator. |
| `chat.artifacts.register_artifact(tool_context, filename, content, created_by_tool)` | `api/src/kene_api/chat/artifacts.py` | The wrapper every agent tool uses to save an artifact. Saves blob + writes metadata row. Enforced by CI lint rule. |
| `useChatSessions` | `frontend/src/hooks/useChatSessions.ts` | TanStack Query `useInfiniteQuery`; poll window 5000ms when visible, stops when hidden. |
| `SessionStatusDot` | `frontend/src/components/chat/SessionStatusDot.tsx` | Pure function of the three timestamp fields + 10-min threshold. Three states, three colors, tooltip. |

## 3. Component Dependencies

### 3.1 Depends On

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[Data Management — DM-PRD-00](../data-management/projects/DM-PRD-00-migration-foundation.md)** | **Hard prerequisite for CH-PRD-01.** Shape B convention + registry for new subcollections. Chat lands `accounts/{account_id}/chat_sessions/*`, `accounts/{account_id}/chat_sessions/{session_id}/artifacts/*`, and adds `users/{user_id}/chat_categories/*` (one of five user-scoped subcollections in the codebase, alongside `notification_status`, `preferences`, `notifications`, and `security`; registered with DM-PRD-05's `USER_SUBCOLLECTIONS` — see §7.2). | [`../data-management/README.md`](../data-management/README.md) §2 |
| **[Data Management — DM-PRD-05](../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md)** | **Hard prerequisite for CH-PRD-04.** `recursive_delete` for chat_sessions + artifacts subcollection on account deletion. User deletion covers `chat_categories`. | [`../data-management/README.md`](../data-management/README.md) deletion section |
| **[Data Management — DM-PRD-07](../data-management/projects/DM-PRD-07-approval-workflow-and-audit.md)** | **Soft.** `write_audit` for chat-session lifecycle events. Optional at v1 — plain structured logging is acceptable if DM-PRD-07 hasn't shipped. | [`../data-management/README.md`](../data-management/README.md) audit section |
| **[UI — UI-PRD-01](../ui/README.md)** | **Hard prerequisite for CH-PRD-02, CH-PRD-04, CH-PRD-05.** Design-system foundation (tokens, shell, Tailwind config, shadcn primitives, `Sidebar`, `TopNav`, `AccountSwitcher`, text-size preference). Every Chat component renders inside `LayoutC`. | [`../ui/README.md`](../ui/README.md) |
| **[UI — UI-PRD-02](../ui/README.md)** | **Coordination.** UI-PRD-02 has been scope-adjusted to auth/settings redesigns only — `/chat` page creation is absorbed by CH-PRD-02. UI-PRD-02 owns the `/` → `/chat` redirect (delete legacy `Home.tsx`); CH-PRD-02 owns the `/chat` destination behind `chat_v2_enabled`. The two PRDs must coordinate `App.tsx` route registration in the same release window. | [`../ui/README.md`](../ui/README.md) |
| **[Feature Flags — FF-PRD-01](../feature-flags/projects/FF-PRD-01-data-model-evaluation-api.md), [FF-PRD-03](../feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md)** | **Hard prerequisite.** Three flags: `chat_v2_enabled` (master kill switch — reverts UI to pre-component state), `chat_status_detail_enabled` (gates the status view separately), `chat_categories_enabled` (gates CH-PRD-03 surface). **No `chat_manual_compaction_enabled`** (Compact-now out of v1). **No placeholder-cards flag** (Permissions / Tools UIs out of v1). | [`../feature-flags/README.md`](../feature-flags/README.md) |
| **[Agentic Harness — AH-PRD-02](../agentic-harness/projects/AH-PRD-02-agent-factory.md)** | **Soft.** The Agent Factory is where Chat registers its two ADK callbacks (`before_agent_callback`, `after_agent_callback`) + the two todo-list tools. If AH-PRD-02 hasn't shipped, Chat registers against the current hardcoded root path with a TODO comment referencing AH-PRD-02's landing. | [`../agentic-harness/README.md`](../agentic-harness/README.md) |
| **[Billing — BL-PRD-02](../billing/projects/BL-PRD-02-token-meter-monthly-enforcement.md)** | **Peer — Billing owns `extract_billable_tokens`.** Chat consumes. Token-definition parity (input + output + reasoning, excluding cached-input) is preserved via the shared helper + CI parity test. If Billing hasn't shipped when Chat starts, Chat lands the helper under Billing's namespace with Billing as reviewer + future maintainer. **Chat does NOT implement cost display — Billing owns pricing entirely.** | [`../billing/README.md`](../billing/README.md) §7.4 |
| **[Billing — BL-PRD-05](../billing/projects/BL-PRD-05-failure-modes-permissions.md)** | **Soft — rate-limit substrate.** Billing introduces a Firestore-backed sliding-window limiter used by Chat's rate-limited endpoints (`/mark-read`, `/categories`, `/category`, `/export`). If BL-PRD-05 hasn't shipped when a Chat endpoint ships, that endpoint ships a minimal in-process limiter with a TODO to migrate. | [`../billing/README.md`](../billing/README.md) |
| **ADK `VertexAiSessionService`** (existing) | Session CRUD, event stream, `session.state` read/write, `list_sessions(app_name, user_id)`. `app_name="ken_e_chatbot"`. See `app/adk/session/recovery.py`. | Google ADK Python v1.16+ |
| **ADK callback API** (existing) | `before_agent_callback`, `after_agent_callback`. **Day-1 spike** in CH-PRD-01 confirms exact signatures before implementation. | Google ADK Python |
| **ADK `EventsCompactionConfig`** (existing) | Automatic compaction is configured in `app/adk/deploy_ken_e.py` (see `docs/KEN-E-System-Architecture.md` §3.5). Manual Compact-now is deliberately scoped out of v1. | Google ADK Python v1.16+ |
| **ADK `GcsArtifactService`** (existing) | Artifact blob storage. Chat adds a metadata sibling — does NOT replace. | Google ADK Python |
| Existing `/api/v1/chat/*` surface (9 endpoints) | Base surface that CH-PRD-01..05 extend. | `api/src/kene_api/routers/chat.py` |
| Redis metadata cache (existing, 24h TTL) | Preserved as a speed-up; the side-table is authoritative. | `api/src/kene_api/cache.py` |

### 3.2 Depended On By

| Component | Dependency |
|-----------|------------|
| **[UI](../ui/README.md)** | The `/chat` route is mounted by the UI shell; the route component is owned by Chat. Chat components render inside `LayoutC`. |
| **[Knowledge Graph — KG-PRD-04](../knowledge-graph/projects/KG-PRD-04-session-end-automation.md)** | The daily idle-session sweep queries ADK sessions, not the Chat side-table — but it respects `chat_sessions.deleted_at` via a thin read. If a session is tombstoned, the sweep skips it. |
| **[Billing — BL-PRD-04](../billing/projects/BL-PRD-04-subscription-settings-ui-integration.md)** | The inactive banner sits in `LayoutC` above Chat; chat input disabled state is rendered by `ChatInterface` reading `useOrgStatus`. No API coupling — UI composition only. |
| **[Agentic Harness](../agentic-harness/README.md)** | Registers two callbacks into the runner (`before_agent_callback`, `after_agent_callback`) + two todo-list tools. Agent specialists that use `save_artifact` MUST call `chat.artifacts.register_artifact` instead of the raw ADK method, or their artifacts won't surface in the UI (§7.5). |
| **[Agentic Harness — AH-PRD-04](../agentic-harness/projects/AH-PRD-04-data-visualization.md)** | Modifies `frontend/src/components/chat/ChatInterface.tsx` (CH-PRD-02-owned) to thread `response.artifacts` into message render and delegate to a Vega-Lite chart block. Pure additive coupling — CH-PRD-02 ships the component first in R1; AH-PRD-04 lands the artifact-rendering extension in R1. No backend coupling. |
| **[Automations](../automations/README.md)** | `PlanRun` sessions use a separate ADK `app_name` (not `ken_e_chatbot`); they do NOT appear in the Chat sidebar. Documented exclusion to prevent confusion. |

## 4. Design System References

| Document | Sections | When to Read |
|----------|----------|--------------|
| `docs/figma-export/src/app/components/SessionsSidebar.tsx` | Entire file | **Design contract for CH-PRD-02.** 384px expanded / 64px collapsed; status dots; search + category-filter layout; session-item three-line layout. |
| `docs/figma-export/src/app/components/SessionSettings.tsx` | Entire file, **with four deliberate deviations for v1**: summary is read-only (figma's "You can edit this summary" copy dropped); **no Compact-now button**; **no Permissions Approved card**; **no cost line in the token-usage card**; the figma's **"Loaded Tools" card is replaced by a new Authentication Status card** rendering account-level integration state with four per-row states and state-dependent CTAs (see CH-PRD-04 §5.6 and `AuthStatusCard.tsx` lines ~526–586 of the figma file for the visual template). | **Design contract for CH-PRD-04** with the noted deviations. |
| `docs/figma-export/src/app/components/ChatInterface.tsx` | Entire file | **Design contract for CH-PRD-02.** Message list, input, artifact blocks, thinking blocks. |
| `docs/figma-export/src/app/pages/ChatPage.tsx` | Entire file | **Design contract for CH-PRD-02.** Page orchestration; toggle between chat and status view via header button. |
| `docs/figma-export/src/app/data/mockData.ts` | `AISession`, `sessionCategories`, `mockDocuments`, `mockTodoLists` | Reference for field shapes. (`mockPermissions` + `mockTools` deliberately unused in v1.) |
| `frontend/CLAUDE.md` | CSS architecture, shadcn/ui component library, branded types, TanStack Query patterns, IntersectionObserver usage | Before adding any React component under `frontend/src/components/chat/`. |
| UI-PRD-01's shell + `LayoutC` | `Sidebar`, `TopNav`, `BackgroundEffects` | Chat mounts inside `LayoutC`. The Chat sidebar is a secondary sidebar — the primary UI sidebar is separate. |

## 5. Project Index

The component's work is split across **5 feature PRDs (CH-PRD-01..05)** plus **1 tooling PRD (CH-PRD-06 — Documentation Link Integrity)** under [`projects/`](./projects/). CH-PRD-01 is the strict substrate prerequisite. After CH-PRD-01, CH-PRD-02 (page + sidebar) blocks CH-PRD-03 / 04 / 05 because the page route is the container for all three. CH-PRD-03 (categories), CH-PRD-04 (status view), CH-PRD-05 (todos + artifacts) can run in parallel. CH-PRD-06 is orthogonal — a small CI/tooling effort bundled under Chat for ownership convenience, not a chat-feature dependency; it can ship in any order relative to CH-PRD-01..05.

### 5.1 Dependency graph

```
DM-PRD-00 (Shape B + registry)  ─┐
DM-PRD-05 (deletion sweep)      ─┤
FF-PRD-01 + FF-PRD-03           ─┤
UI-PRD-01 (design system)       ─┤
                                  │
                                  ▼
                          ┌───────────────────┐
                          │    CH-PRD-01      │  Session metadata substrate
                          │                   │  side-table, callbacks, accumulator,
                          │                   │  events-based status, 30-day window,
                          │                   │  backfill, security rules
                          └─────────┬─────────┘
                                    │
                                    ▼
                          ┌───────────────────┐
                          │    CH-PRD-02      │  Chat page shell + sidebar
                          │                   │  /chat route, search,
                          │                   │  infinite scroll, status dots
                          └─────────┬─────────┘
                                    │
                ┌───────────────────┼───────────────────┐
                ▼                   ▼                   ▼
      ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
      │    CH-PRD-03      │ │    CH-PRD-04      │ │    CH-PRD-05      │
      │ Session           │ │ Session status    │ │ Todo lists +      │
      │ categories        │ │ view (name,       │ │ artifacts         │
      │ (per-user CRUD,   │ │ summary, tokens,  │ │ (state schema,    │
      │ trash delete,     │ │ context, activity,│ │ provenance,       │
      │ filter, assign)   │ │ export, delete)   │ │ renderers, orphan │
      │                   │ │                   │ │ scans)            │
      └───────────────────┘ └───────────────────┘ └───────────────────┘

(Tooling PRD — separate from the feature dependency chain above; no chat-feature deps)

                                ┌───────────────────┐
                                │    CH-PRD-06      │  Documentation link
                                │                   │  integrity & CI
                                │                   │  enforcement (lychee
                                │                   │  config + CI gate +
                                │                   │  G-4 in CLAUDE.md)
                                └───────────────────┘
```

### 5.2 Projects

| # | Project PRD | Owner team | Blocked by | Parallel with | Est. |
|---|-------------|------------|------------|---------------|------|
| 01 | [Session Metadata Substrate](./projects/CH-PRD-01-session-metadata-substrate.md) | Chat / Backend + ADK | DM-PRD-00, DM-PRD-05, FF-PRD-01 | — | 5 days |
| 02 | [Chat Page Shell & Sidebar](./projects/CH-PRD-02-chat-page-shell-and-sidebar.md) | Chat / Frontend + Backend (thin) | CH-PRD-01, UI-PRD-01, FF-PRD-03 | — | 5 days |
| 03 | [Session Categories](./projects/CH-PRD-03-session-categories.md) | Chat / Full-stack | CH-PRD-02 | CH-PRD-04, CH-PRD-05 | 3 days |
| 04 | [Session Status View](./projects/CH-PRD-04-session-status-view.md) | Chat / Full-stack | CH-PRD-02 | CH-PRD-03, CH-PRD-05 | 4 days |
| 05 | [Todo Lists + Artifacts](./projects/CH-PRD-05-todo-lists-and-artifacts.md) | Chat / Full-stack + ADK | CH-PRD-02 | CH-PRD-03, CH-PRD-04 | 4 days |
| 06 | [Documentation Link Integrity](./projects/CH-PRD-06-documentation-link-integrity.md) | Chat / Tooling | — (PR #241 merge is the trigger event, not a strict blocker) | any | 0.5 day |

**Total: 21 days for the 5 feature PRDs (CH-PRD-01..05) + 0.5 day for CH-PRD-06 tooling** across 4 sprints (down from 22 after Compact-now, cost, and placeholder cards were scoped out of CH-PRD-04). CH-PRD-06 is partially shipped (`lychee.toml` + G-4 in CLAUDE.md exist; pr_checks.yaml CI step pending).

### 5.3 Cross-PRD coordination points

Four touchpoints need conscious coordination:

- **UI-PRD-02 scope adjustment (CH-PRD-02).** UI-PRD-02's PROJECT-PLANNER row, README description, and the project PRD itself have been scope-adjusted to drop the `/chat` page. CH-PRD-02 absorbs `/chat` page creation, including the port of `ChatInterface` + `ThinkingBlock` components. Coordination at landing: UI-PRD-02 lands the `/` → `/chat` redirect; CH-PRD-02 lands the `/chat` destination behind `chat_v2_enabled`.
- **ADK callback registration site + Day-1 spike (CH-PRD-01 ↔ AH-PRD-02).** Chat needs two callbacks: `before_agent_callback`, `after_agent_callback`. The Agent Factory (AH-PRD-02) is the idiomatic registration site. If AH-PRD-02 hasn't shipped, CH-PRD-01 registers callbacks against the current hardcoded root-agent path. CH-PRD-01 Day 1 also runs a focused ADK spike to verify exact public callback names; findings captured in `docs/spike-adk-chat-callbacks.md`.
- **Artifact tool-convention contract (CH-PRD-05 ↔ every specialist).** CH-PRD-05 introduces `chat.artifacts.register_artifact()` as the canonical artifact-save path for agent tools. Every future specialist that creates an artifact must call this wrapper or its artifacts do not appear in the UI. The existing `app/adk/agents/strategy_agent/artifact_utils.py` is **allow-listed, not migrated** (CH-47, PO-approved Option A) — it is a setup-time input loader for a separate ADK app with no parent `chat_sessions` row; migration would crash strategy runs. A lint rule (`check_artifact_register.py`) scans for raw `save_artifact` calls outside the allow-list and blocks them.
- **Token-definition parity with Billing (CH-PRD-01 ↔ BL-PRD-02).** Both Chat's token aggregation and Billing's meter count input + output + reasoning tokens excluding cached-input discount (per Billing README §7.4). A single helper `extract_billable_tokens(event)` at `shared/token_accounting.py` is **owned by Billing**. If Billing hasn't shipped, Chat authors the helper in Billing's namespace with Billing as reviewer. CI parity test asserts both consumers read the same definition on every PR.

### 5.4 Recommended workflow

1. **Sprint 1:** CH-PRD-01 lands (5 days, backend + ADK). Day 1 is the ADK callback spike. No downstream CH work possible — gate. Coordination with UI team happens here to scope-adjust UI-PRD-02.
2. **Sprint 2:** CH-PRD-02 (5 days, frontend + thin backend). The `/chat` page goes live behind `chat_v2_enabled` flag. Completes end-to-end the existing chat UX with v2 plumbing. Load-test gate at AC #16.
3. **Sprint 3:** CH-PRD-03, CH-PRD-04, CH-PRD-05 in parallel across three dev pairs (3 / 4 / 4 days). Each gated by its own feature flag (`chat_categories_enabled`, `chat_status_detail_enabled`). Each ships independently.
4. **Sprint 4 (capstone):** flag sweep — enable all three Chat flags in dev → staging → prod. Observe for 7 days. Delete `frontend/src/services/chatService.ts` in a follow-up PR. Drop the flags from CLAUDE.md once usage stabilizes.

### 5.x Cross-PRD Coordination: AH-PRD-05 (Supervisor-Orchestration)

The `TodoItem` schema widening described in §2.4 is driven by the supervisor-orchestration model in [AH-PRD-05](../agentic-harness/projects/AH-PRD-05-multi-step-workflows.md). The `set_todo_list` / `update_todo_list` tools are the supervisor coordinator's primary ledger-write mechanism. Chat owns the schema and model definitions; the Harness (AH-PRD-05) is the consumer. Coordinate on any further `TodoItem` field additions before implementing them.

## 6. Global Document References

| Document | Relevant Sections | Why |
|----------|-------------------|-----|
| Root `CLAUDE.md` | §2 While Coding, §3 Testing, §4 Database, §6 Tooling Gates, §7 Git | Branded types (C-5), Pydantic (PY-2), context managers (PY-5), lint gates (G-1..G-3), conventional commits (GH-1). |
| `api/CLAUDE.md` | Firestore access patterns, Redis metadata cache, Secret Manager usage | Before building the side-table service or extending the existing chat router. |
| `frontend/CLAUDE.md` | CSS architecture, shadcn/ui, branded types, TanStack Query, IntersectionObserver | Before building the Sidebar, Status View, or any Chat React component. |
| [`./implementation-plan.md`](./implementation-plan.md) | Entire document, especially §5 (component interactions) and §10 (open questions) | Authoritative source for v1 scope decisions. |
| `docs/KEN-E-System-Architecture.md` | §1.6 (Component Landscape — Chat row), §3.5 (Session Compaction), §3.6 (Session State Management — `todo_lists` added) | Cross-component orientation. |
| `docs/trace-structure-spec.md` | Sections describing LLM-call spans + token attributes | Before implementing the per-turn accumulator in CH-PRD-01. Same provider response Weave records is the source for Chat's token counters. |
| [`../../DESIGN-REVIEW-LOG.md`](../../DESIGN-REVIEW-LOG.md) | Entry dated CH-PRD-05 completion | Rationale for the Firestore side-table + user-scoped categories + read-only summary + events-based status design. (To be authored during CH-PRD-05.) |

## 7. Conventions and Constraints

### 7.1 Session scope is per-user-per-account

Every `chat_sessions/{session_id}` doc carries both `user_id` and `account_id`. The sidebar lists only sessions matching the currently selected account AND the authenticated user. Sessions do not migrate between accounts. Firestore security rules gate reads on `resource.data.user_id == request.auth.uid`; `chat_sessions` is server-write-only (`allow write: if false`) because `ChatSessionSideTableService` is the single write path via the Admin SDK. Account scoping is enforced by the API layer, not the rules — a KEN-E user belongs to many accounts (plus org-admin / super-admin implicit access), which no single-valued Firebase custom claim can represent. Belt-and-braces with API-layer checks so a rules gap doesn't leak data on the API path. Unit-tested against the Firestore emulator. See CH-PRD-01 §4.5.

### 7.2 Categories are per-user, not per-account

Categories live at `users/{user_id}/chat_categories/{category_id}`. This is one of five user-scoped subcollections in the codebase, alongside `users/{user_id}/notification_status` and `users/{user_id}/preferences` (which predate the Shape B migration and live in `firestore_notification_repository.py`) and `users/{user_id}/notifications` and `users/{user_id}/security` (default-settings docs seeded in `routers/users.py`). DM-PRD-05's `delete_user_data(user_id)` orchestrator covers it through the `USER_SUBCOLLECTIONS` registry — `recursive_delete(users/{user_id})` reaps the subcollection on user deletion (distinct from account deletion, which doesn't touch user-scoped state). A category applies across all of the user's accounts — but because sessions are per-account, only sessions matching the current account see the category in the sidebar. Name dedup uses `casefold()` (Unicode-safe) rather than `lower()`.

### 7.3 The side-table never writes to ADK, ADK never reads the side-table

Strict separation. The ADK session is the source of truth for events, state, artifacts. The Firestore side-table is the source of truth for product fields (title, category, summary cache, counters, activity timestamps, artifact metadata index). Flow direction is one-way — ADK → side-table via callbacks + the completion endpoint's event-loop accumulator. On read, the sidebar reads only the side-table; the status view reads the side-table + state for todos (lightweight `get_session`) + event stream for export.

### 7.4 Token-definition parity with Billing

Chat counts input + output + reasoning tokens, excluding the cached-input discount. Identical definition to Billing's meter (`../billing/README.md` §7.4). Both components call the same `extract_billable_tokens(event)` helper — **owned by Billing** — so divergence is impossible by construction. Cached-token savings flow to KEN-E margin and are not surfaced in either the Chat per-session aggregate or the Billing invoice.

### 7.5 Artifact-save wrapper contract

Every agent tool that creates an artifact must call `chat.artifacts.register_artifact(...)` rather than the raw ADK `context.save_artifact(...)`. Artifacts saved via the raw ADK call still persist blobs but do not surface in the Chat UI. A lint rule in CI (`check_artifact_register.py`) fails the build on raw calls outside the wrapper. v1 requires `created_by_tool`; the future user-upload path will pass `None` — the shape already supports it. No separate `creator` field.

### 7.6 Read-only surfaces

Three surfaces are agent-authored and read-only from the user's perspective: **session summary** (written by ADK compaction), **todo-list checkboxes** (updated by agent tools into `session.state["todo_lists"]`), **tool-call / artifact activity counts** (incremented by the per-turn accumulator). The UI renders these with no edit affordances and no save buttons. Attempts to PATCH fields marked read-only return 400. This eliminates merge conflicts between user intent and agent state.

### 7.7 Status indicator mechanics — derived from timestamps

No persistent `is_agent_running` boolean. No in-process sweeper. Three states, derived client-side and by the `/status-detail` endpoint server-side from three side-table fields:

- **Active (teal dot)** — `last_agent_started_at` is set, greater than `last_agent_stopped_at` (or `last_agent_stopped_at` is null), AND `now - last_agent_started_at < 10 min`.
- **Needs Review (coral dot)** — agent has stopped (`last_agent_stopped_at > last_agent_started_at`) AND `last_agent_message_at > last_viewed_at`.
- **Idle (no dot)** — otherwise.

`last_agent_started_at` is set by `before_agent_callback`; `last_agent_stopped_at` + `last_agent_message_at` by `after_agent_callback` or the completion endpoint's `finally` block (so SSE cancellation also records a stop). `last_viewed_at` by `POST /mark-read`. Crash safety: if a completion request dies without firing anything, the 10-minute threshold naturally times out the "active" state at read time. Self-expiring; no sweeper required.

### 7.8 30-day recovery and list windows

Both the sidebar list and the existing `/sessions/recoverable` endpoint use a 30-day `updated_at >= now()-30d` window (lifted from the pre-Chat 7-day window). A user who returns to a 45-day-old session by direct URL can still recover it via `/sessions/{id}/recover`, but it does not appear in the default sidebar list. The constants are `RECOVERY_WINDOW_DAYS = 30` in `app/adk/session/recovery.py` and `CHAT_LIST_WINDOW_DAYS = 30` in `api/src/kene_api/chat/search.py`.

### 7.9 Context meter, not cost meter

Chat displays **token counts** (Input / Output / Total) and **context-window usage %**. Chat does **not** display per-session cost. KEN-E's user-facing cost is determined by subscription level, not per-model token pricing; surfacing a meaningful per-session dollar amount would require subscription → rate lookups that are owned by Billing. Chat ships a `context_windows.py` registry for the context-bar denominator (model id → `context_window_max`) and nothing more — no pricing fields, no `compute_cost_cents`, no `format_cost_cents_to_display`.

### 7.10 Firestore layout (Shape B + user-scoped)

- `accounts/{account_id}/chat_sessions/{session_id}` — Shape B.
- `accounts/{account_id}/chat_sessions/{session_id}/artifacts/{artifact_id}` — Shape B.
- `users/{user_id}/chat_categories/{category_id}` — user-scoped subcollection.

**Four composite indexes** cover every query combination in v1:
1. `(user_id ASC, deleted_at ASC, updated_at DESC)` — default sidebar (no category filter).
2. `(user_id ASC, category_id ASC, deleted_at ASC, updated_at DESC)` — category-filtered sidebar.
3. `(session_id ASC, created_at DESC)` on `artifacts` — per-session listing.
4. `(user_id ASC, name_casefold ASC)` on `chat_categories` — dedup + sort.

DM-PRD-05's `recursive_delete` registry picks up all three paths.

### 7.11 Feature-flag structure

- **Component-level kill switches:** `chat_v2_enabled` (master; reverts `/chat` to the pre-component UX), `chat_status_detail_enabled` (gates the status view), `chat_categories_enabled` (gates categories end-to-end), `chat_auto_title_enabled` (default `true`; ops kill switch for the once-per-session `gemini-2.5-flash` auto-title generator owned by CH-PRD-04 §5.7).
- **No `chat_manual_compaction_enabled`** — manual Compact-now is scoped out of v1. Auto-compaction always runs.
- **No placeholder-card flag for Permissions Approved** — that card is not rendered at all in v1. Future PRD adds real feature + flag.
- **Auth Status card inherits `integrations_connection_test_enabled`** (from IN-PRD-07) — when off, the card ships read-only (no Check Status button, no state-reactive CTAs); when on, the button appears per-row. No Chat-owned flag.
- All four chat-owned flags ship targeted-rollout-capable.
- `chat_v2_enabled=false` defaults ALL new endpoints to 404, not 500. Existing endpoints stay functional.

### 7.12 Auto-title generation contract

Sessions begin with `title=null`. After the **first assistant response completes** (i.e., when the per-turn flush detects `message_count == 2 AND title is None AND auto_title_attempted_at is None AND chat_auto_title_enabled`), the completion endpoint's `finally` block fires a fire-and-forget call to `generate_session_title(session_id, user_id)` (CH-PRD-04 §5.7). The generator:

- uses `gemini-2.5-flash` with max 30 output tokens, temperature 0.2;
- bills tokens through the shared `extract_billable_tokens(event)` helper into the org's BL-PRD-02 monthly meter (no separate metering path);
- never overwrites a title the user has already set — re-reads the side-table both before the LLM call and before the side-table write;
- always stamps `auto_title_attempted_at = now()` on completion (success, failure, or suppression), guaranteeing **at most one Gemini call per session**;
- treats every failure mode (API error, timeout, empty response, oversized input) as "leave title null + stamp attempted" — never retries.

`PUT /conversations/{id}` (manual title edit) sets `auto_title_attempted_at` synchronously to win the race against an in-flight generator call. Manual edits are forever respected; no auto-regeneration is performed even if the user later clears the title to null.

### 7.13 Standard shape for a project PRD in [`projects/`](./projects/)

Every PRD follows the shared 10-section structure used across sibling components:

1. Context — problem this PRD solves
2. Scope — explicit in/out
3. Dependencies — other PRDs, files, services
4. Data contract — Pydantic / TypeScript types owned or consumed
5. Implementation outline — files to create / modify (table)
6. API contract — endpoints (where applicable)
7. Acceptance criteria — what "done" means
8. Test plan — unit / integration / E2E coverage
9. Risks & open questions
10. Reference — links back to sibling PRDs, upstream design docs

### 7.14 SSE multi-author event contract

The `POST /api/v1/chat/completions` (streaming) SSE wire supports multi-author fan-out turns (supervisor model, AH-PRD-05) via an additive author-tagging mechanism. Existing single-author clients that do not handle the new event type continue to work unchanged.

**Wire frames**

| Frame | Format | When emitted |
|---|---|---|
| Author sidecar | `event: author\ndata: <name>\n\n` | Once per author transition (not per text frame). Emitted immediately before the first text frame of a new author. |
| Text frame | `data: <text fragment>\n\n` | Unchanged. Author tracked via the most-recent preceding sidecar. |
| Reasoning frame | `event: reasoning\ndata: {"text":"...","seq":N}\n\n` (single author) or `event: reasoning\ndata: {"text":"...","seq":N,"author":"<name>"}\n\n` (non-default author) | `"author"` key is present only when author ≠ `"model"`. |
| Session frame | `event: session\ndata: {"session_id":"..."}\n\n` | Unchanged. Not author-tagged. |
| Done | `data: [DONE]\n\n` | Unchanged. |

**Default author**

The default author is `"model"` — the ADK root agent's canonical author string, matching `accumulator._is_message_event`. Single-author turns (`author == "model"` throughout) emit **zero** sidecar frames. Their wire bytes are byte-for-byte identical to the pre-author-tagging baseline.

**Parser contract (stateful)**

A compliant parser initializes `currentAuthor = "model"` before the stream starts. Each `event: author` sidecar updates `currentAuthor` to the sidecar's data value (ignoring empty/whitespace-only values). Each subsequent text event carries the current `currentAuthor` value. SSE's guaranteed in-order delivery makes this safe.

```
Initial state:  currentAuthor = "model"
event: author  → data = "specialist_a"   → currentAuthor = "specialist_a"
data: Hello    → text event, author = "specialist_a"
data: World    → text event, author = "specialist_a"
event: author  → data = "specialist_b"   → currentAuthor = "specialist_b"
data: Hi       → text event, author = "specialist_b"
```

**Rendering contract**

One assistant bubble per distinct author seen in a turn. Same-author fragments accumulate in the current bubble. A new bubble is spawned when the incoming event's `author` differs from the in-flight bubble's author. Author labels appear above each bubble whose author ≠ `"model"` (the default single-specialist author produces no label — UI is unchanged for single-author turns).

**Back-compat guarantees**

- Legacy parsers that drop unknown event types (`event: author` → silently dropped) continue to work; they render all fragments as `author = "model"` which is visually correct for current single-specialist turns.
- `ChatResponse` (non-streaming response shape) is **unchanged** — the `author` field exists on the SSE wire only.
- The `"author"` key in the reasoning JSON payload is optional; a `JSON.parse` client that casts to `{ text: string; seq: number }` ignores it.

**Cross-references:** AH-PRD-14 §4 (SSE multi-author event contract), §6 (API contract — author field additive). Implementation: `api/src/kene_api/routers/chat.py` (`_format_sse`, `_stream_completion_sse`); `frontend/src/lib/chatApi.ts` (`StreamEvent`, `streamChatCompletion`).

---

<!-- PRD MAINTENANCE NOTES

Updating this PRD:
- When CH-PRD-05 completes: remove [PLANNED] tags, update Status to "Active," append a Verification section (E2E results + 7-day observation metrics + first-org-on-v2 date) at the end of §7, and cross-link from DESIGN-REVIEW-LOG.
- When a new specialist that creates artifacts ships: verify it calls `chat.artifacts.register_artifact` (§7.5 lint rule enforces).
- When a new LLM model is registered with the Agent Factory: add its entry to `MODEL_CONTEXT_WINDOW_REGISTRY` (§7.10) + assert via the CI coverage test.
- When the ADK callback API changes (upgrade): re-validate `chat_callbacks.py` against the new ADK version + update §7.3 if the event shape changes.
- When a new user-scoped collection lands: point it at the pattern documented in §7.2 + update DM-PRD-05's deletion sweep.
- When cost display becomes a real feature (post-v1): design + Billing coordination needed; add a future CH-PRD scoped to cost surfacing (CH-PRD-06 is taken for the documentation-link-integrity tooling PRD — see [`./projects/CH-PRD-06-documentation-link-integrity.md`](./projects/CH-PRD-06-documentation-link-integrity.md)).
- When manual compaction becomes a real feature (post-v1): add a CH-PRD for the Compact-now button; re-register the feature flag.
- When the "Permissions Approved" card becomes a real feature: new PRD + flag registration + figma re-alignment.
- When IN-PRD-07 ships after CH-PRD-04: the Auth Status card's Check Status button + state-reactive CTAs light up via `integrations_connection_test_enabled`. No CH-PRD-04 re-release — IN-PRD-07's frontend scope includes the extension to `AuthStatusCard.tsx`.

This PRD is read by the Dev Team agent during implementation planning (CLAUDE.md §Context Loading Sequence, Step 1). Keep it concise — every sentence should help a dev write better code or avoid mistakes.
-->
