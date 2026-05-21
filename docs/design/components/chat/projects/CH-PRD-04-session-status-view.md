# CH-PRD-04 — Session Status View

**Status:** Not started
**Owner team:** Chat component team (full-stack)
**Blocked by:** [CH-PRD-02](./CH-PRD-02-chat-page-shell-and-sidebar.md) (page shell + toggle button mount point); [IN-PRD-03](../../integrations/projects/IN-PRD-03-connection-management-ui.md) (Integrations `GET /connections` endpoint + `useConnections(accountId)` hook + typed `ConnectionCardView` / `PlatformConnectionPublic` types — the data source for the Authentication Status card)
**Parallel with:** CH-PRD-03, CH-PRD-05
**Soft dep:** [IN-PRD-07](../../integrations/projects/IN-PRD-07-on-demand-connection-test.md) — if shipped at CH-PRD-04 ship time, the Authentication Status card's per-row "Check Status" button + last-checked timestamp + state-reactive CTAs are enabled behind `integrations_connection_test_enabled`; if not, the card ships **read-only** (status dot + badge derived from `PlatformConnection.status` only) and the interactive upgrade lands as part of IN-PRD-07's frontend scope without requiring a CH-PRD-04 re-release.
**Blocks:** none
**Estimated effort:** 5 days full-stack (4 from the base scope + ~1 day for the Authentication Status card's read-only implementation + graceful-degradation branches)

---

## 1. Context

The session status view is the side panel a user opens to inspect a session's identity, history, and usage. It surfaces: editable title, category assignment (dropdown from CH-PRD-03), model-generated summary (read-only), documents list (CH-PRD-05), todo lists (CH-PRD-05), token usage (input / output / total), context-window usage (% bar with Healthy/Moderate/Near-limit badge), last-activity + duration, and an activity summary ("12 tool calls • 2 compactions • 3 artifacts"). Below these cards sit two action buttons: **Export** and **Delete**.

The page-level `Session Status` button (mounted in CH-PRD-02) toggles between chat and status view. CH-PRD-04 delivers the toggle's destination plus the composite `GET /status-detail` endpoint that feeds it in one round-trip, plus two backend actions (export, delete two-phase).

Two figma deviations are resolved here: **summary is read-only** (figma's "You can edit this summary" copy is replaced with "Auto-generated during compaction" and the textarea becomes a read-only text block), and **multi-session concurrency via status dots** is handled in CH-PRD-02 (CH-PRD-04 does not own the dots; only the status view).

The figma's original "Loaded Tools" card is **replaced** by a new **Authentication Status** card that lists account-level integrations with a colored status dot, platform name, last-checked timestamp, and — when IN-PRD-07 has shipped — a per-row "Check Status" button. The card is read-only in its initial ship; IN-PRD-07's frontend scope upgrades it to interactive without requiring a CH-PRD-04 re-release. Scoping is deliberately account-wide (not per-session) because `PlatformConnection`s are account-scoped — the same list surfaces across every session, with a "Account-wide connection status" subtitle making the scoping explicit.

Three figma elements remain **explicitly out of scope** for v1:
- **"Compact now" button** — manual compaction is deferred. ADK's automatic compaction continues to run.
- **"Permissions Approved" card** — not rendered at all (no placeholder, no mock data, no flag).
- **"Cost" line** — per-session cost requires subscription-level pricing lookups that are owned by Billing; Chat shows token counts only.

Landing the status view completes the "see everything about a session" surface the user spec described. The validation checkpoint is that opening the status view on any session returns every field populated correctly within 500ms p95, and the two action buttons (Export, Delete) each work end-to-end.

## 2. Scope

### In scope

- **`frontend/src/components/chat/SessionStatusView.tsx`** — port + scope-adjusted version of `docs/figma-export/src/app/components/SessionSettings.tsx`. Card grid: Title card + Category card + Summary card + Documents card + Todo Lists card + Context & Token Usage card + Activity card + **Authentication Status card (new; §5.6)**. Action buttons row: Export, Delete. **No Compact-now button.** **No Permissions Approved card.** **No Cost line.**
- **`GET /api/v1/chat/conversations/{id}/status-detail`** — composite endpoint returning `ChatStatusDetail` (metadata + artifacts + todo_lists + derived fields: `is_agent_running`, `context_usage_percent`, `duration_seconds`, `activity_summary`, `total_tokens`). One round-trip per open.
- **`GET /api/v1/chat/conversations/{id}/export?format=markdown`** — streams a markdown transcript. YAML front-matter (serialized via `yaml.safe_dump` for hostile-character safety) with metadata; message log body. Embedded artifact signed URLs use a **24-hour TTL** (extended from the 10-minute TTL used for in-app artifact listing) so that exports are usable hours after download.
- **`DELETE /api/v1/chat/conversations/{id}`** extension — two-phase tombstone (synchronous side-table `deleted_at=now()`; async ADK + GCS + artifact cleanup via Cloud Run background task). Cleanup task retries up to 3× with exponential backoff; on permanent failure, pages ops. The orphaned ADK session is later caught by the nightly ADK-session orphan scan owned by CH-PRD-05.
- **`PUT /api/v1/chat/conversations/{id}`** extension — title-only edit. Body `{title}`. Updates side-table + recomputes `search_text` (using `casefold()`). Existing endpoint is re-shaped (was `conversation_name` field — now `title`).
- **`TokenUsagePanel.tsx`** — renders: context bar + badge (Healthy <60%, Moderate 60–80%, Near-limit >80%), 3-card token grid (Input / Output / Total). **No cost line.**
- **`SummaryCard.tsx`** — read-only. "Auto-generated during compaction" caption + summary text or placeholder "No summary yet. KEN-E compacts long sessions automatically."
- **`TitleCard.tsx`** — editable `Input` + debounced save (500ms after last keystroke).
- **Auto-title generation** — once per session, after the first assistant response completes, generate a 3–6 word session title via `gemini-2.5-flash` and write it to `chat_sessions.title` (only if the user hasn't already set one). Implementation in `api/src/kene_api/chat/auto_title.py` (§5.7); fired from CH-PRD-01's completion-endpoint `finally` block when the per-turn flush detects `message_count == 2 AND title is None AND auto_title_attempted_at is None`. Fire-and-forget background task — does not block the streaming response. Tokens consumed pass through `extract_billable_tokens` (BL-PRD-02) and increment the org's monthly meter. Manual title edits (PUT `/conversations/{id}`) suppress auto-title by setting `auto_title_attempted_at` synchronously; once set, the field never resets, so auto-title runs at most once per session regardless of outcome (success / failure / suppressed). Gated by `chat_auto_title_enabled` (default `true`; provides ops a kill switch for prompt-quality regressions).
- **`ActivityCard.tsx`** — last-activity, duration, activity summary lines.
- **`AuthStatusCard.tsx`** — account-level integration auth status. Header: "Authentication Status" + aggregate count badge (e.g. "6/8 connected"). Per-platform row: colored status dot + platform display name + "Last Checked" timestamp (from `PlatformConnection.last_tested_at` when IN-PRD-07 ships; falls back to `connected_at` otherwise) + state-dependent right-side CTA. Row click deep-links to `/settings/integrations/{connection_id}` (or `/settings/integrations` for not-connected platforms). Data source: the existing `useConnections(accountId)` hook from IN-PRD-03 — no new backend endpoint. Four rendered states: **Authenticated** (green dot + "Authenticated" badge), **Needs re-auth** (red dot + "Reconnect" CTA; covers `status ∈ {expired, revoked, error}` or definitive IN-PRD-07 failure), **Transient error** (amber dot + "Retry" button; only when IN-PRD-07 is present and the last test was `is_transient=true`), **Not connected** (grey dot + "Connect" CTA). The "Check Status" button is gated by `integrations_connection_test_enabled` — hidden in the read-only ship, visible and functional once IN-PRD-07 ships. Subtitle reads "Account-wide connection status" to make the scope explicit.
- **`useChatSession.ts`** — TanStack `useQuery` hook consuming `/status-detail`. Polls every 10s while the status view is open (so tokens + activity counts update during an in-flight response); pauses on `visibilitychange` hidden.
- **`chat/export.py`** — `export_session_as_markdown(session_id) → StreamingResponse`. YAML front-matter via `yaml.safe_dump(front_matter_dict)`; transcript body streamed event-by-event; inline artifact links with 24h signed URLs.
- **Delete two-phase** — `DELETE /conversations/{id}` sets `deleted_at=now()` synchronously; fire-and-forget Cloud Run task calls `VertexAiSessionService.delete_session` + iterates artifact GCS blobs + deletes Firestore rows.
- **Rate limits** — Export is rate-limited 10/hour/session (prevents abuse of signed-URL generation). Uses Billing's BL-PRD-05 sliding-window limiter when available; minimal in-process fallback otherwise.
- **Telemetry** — Weave spans `chat.status_detail.read`, `chat.export`, `chat.delete`, `chat.title.updated`.
- **Feature flag gating** — status view gated by `chat_status_detail_enabled`; when off, the toggle button in the page header is hidden.

### Out of scope

- **Compact now button / manual compaction.** Deferred beyond v1. ADK's automatic compaction still runs.
- **Permissions Approved card.** Not rendered at all in v1; no placeholder, no mock data, no flag. Future PRD delivers when permission approval becomes a real feature.
- **Per-session cost display.** Subscription-level pricing is Billing's concern; adding session-level cost requires lookups Chat intentionally doesn't own.
- **Per-session filtering of the Authentication Status card.** v1 shows all account-level integrations (same list across every session). Filtering to "platforms this agent actually used in this session" would require new session-side tracking and is deferred.
- **"Check all" aggregate button on the Authentication Status card.** Per-row Check Status only; users click one platform at a time. The 60s cache from IN-PRD-07 already bounds cost on repeat clicks.
- Agent-tool registration for `set_todo_list` / `update_todo_list` — CH-PRD-05.
- Artifacts panel rendering (icons, badges, list) — CH-PRD-05 ships `ArtifactsPanel.tsx` which `SessionStatusView` mounts. CH-PRD-04 reserves the slot.
- Todo lists rendering — CH-PRD-05 ships `TodoListsPanel.tsx`. CH-PRD-04 reserves the slot.
- Category dropdown — CH-PRD-03 ships `CategoriesDropdown.tsx`; CH-PRD-04 mounts it.
- ADK-session orphan scan — CH-PRD-05 owns the daily reconciliation (CH-PRD-04's delete path relies on it to catch cleanup-task failures).
- User-facing summary editing — non-goal per [`../implementation-plan.md`](../implementation-plan.md) §7.
- PDF / JSON export — markdown only in v1.
- Multi-session batch actions.
- Real-time push of tokens — 10s polling only in v1.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[CH-PRD-01](./CH-PRD-01-session-metadata-substrate.md)** | Side-table + callbacks + context-window registry + `ChatStatusDetail` shape. Every field in the status view comes from here. | This PRD package |
| **[CH-PRD-02](./CH-PRD-02-chat-page-shell-and-sidebar.md)** | Page shell + toggle button mount point. `SessionStatusView` renders inside the page's right pane when toggled. | This PRD package |
| **[CH-PRD-03](./CH-PRD-03-session-categories.md)** (soft) | `CategoriesDropdown variant="assign"` — CH-PRD-04 mounts; if CH-PRD-03 hasn't shipped, a read-only category label renders instead. | This PRD package |
| **[CH-PRD-05](./CH-PRD-05-todo-lists-and-artifacts.md)** (soft + integration) | `TodoListsPanel.tsx`, `ArtifactsPanel.tsx` — CH-PRD-04 reserves slots. The ADK-session orphan scan owned by CH-PRD-05 is the final safety net when the CH-PRD-04 delete cleanup task fails. If CH-PRD-05 hasn't shipped, the cards render "Coming soon" placeholders + a manual scan script is available for ops. | This PRD package |
| **[IN-PRD-03](../../integrations/projects/IN-PRD-03-connection-management-ui.md)** (hard) | `GET /api/v1/integrations/{account_id}/connections` + `useConnections(accountId)` TanStack Query hook + `ConnectionCardView` / `PlatformConnectionPublic` types. The Authentication Status card is a pure frontend composition over this endpoint; no new backend endpoint is required from Chat. | [`../../integrations/README.md`](../../integrations/README.md) |
| **[IN-PRD-07](../../integrations/projects/IN-PRD-07-on-demand-connection-test.md)** (soft) | `POST /connections/{id}/test` + `useTestConnectionMutation` hook + `ConnectionTestResult` type + `PlatformConnection.last_tested_at` field + `integrations_connection_test_enabled` flag. Optional at CH-PRD-04 ship time: if present, the Auth Status card renders the per-row "Check Status" button and reacts to test results; if absent, the card ships read-only and IN-PRD-07's frontend scope adds the button later. | [`../../integrations/projects/IN-PRD-07-on-demand-connection-test.md`](../../integrations/projects/IN-PRD-07-on-demand-connection-test.md) |
| **[BL-PRD-02](../../billing/projects/BL-PRD-02-token-meter-monthly-enforcement.md)** (soft) | **For auto-title generation** — the `gemini-2.5-flash` call passes through `extract_billable_tokens(event)` and increments the org's monthly token meter. Same shared helper Chat already uses for per-turn aggregation (CH-PRD-01); no new contract. | `../../billing/README.md` §7.4 |
| **[BL-PRD-05](../../billing/projects/BL-PRD-05-failure-modes-permissions.md)** (soft) | Rate-limit substrate for the export endpoint. Fallback: minimal in-process limiter. | `../../billing/README.md` |
| Existing `DELETE /conversations/{id}` | Base endpoint; CH-PRD-04 adds the side-table tombstone + async cleanup. | `api/src/kene_api/routers/chat.py` |
| GCS signed URLs | 10-minute TTL for in-app listing; 24-hour TTL for export-embedded links. | GCP |
| **[FF-PRD-01](../../feature-flags/projects/FF-PRD-01-data-model-evaluation-api.md)**, **[FF-PRD-03](../../feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md)** | `chat_status_detail_enabled` flag (gates the status view). `integrations_connection_test_enabled` flag (inherited from IN-PRD-07; gates the Check Status button and state-reactive CTAs on the Auth Status card). `chat_auto_title_enabled` flag (default `true`; ops kill switch for the auto-title generator). | `../../feature-flags/README.md` |

## 4. Data contract

### 4.1 Composite response shape

```python
# api/src/kene_api/models/chat.py — ChatStatusDetail defined in CH-PRD-01

# Derived fields computed server-side:
#   is_agent_running      = derived from last_agent_started_at / last_agent_stopped_at / STUCK_THRESHOLD
#   context_usage_percent = current_context_tokens / context_window_max
#   duration_seconds      = (last_agent_message_at or updated_at) - created_at
#   activity_summary      = f"{tool_call_count} tool calls • {compaction_count} compactions • {artifact_count} artifacts"
#   total_tokens          = input_tokens_total + output_tokens_total + reasoning_tokens_total
```

The server computes derived fields so client-side math + locale don't diverge.

### 4.2 Export response

```
GET /conversations/{id}/export?format=markdown
Content-Type: text/markdown; charset=utf-8
Content-Disposition: attachment; filename="session-{id}-{date}.md"
```

**Front-matter** is serialized via `yaml.safe_dump(front_matter_dict, default_flow_style=False)` so hostile characters in title, category, or summary never break the YAML:

```
---
title: "Building Q3 calendar"
session_id: "abc123"
category: "Campaign Planning"
created_at: "2026-04-01T10:00:00Z"
last_activity: "2026-04-10T15:30:00Z"
duration: "34 minutes"
model: "gemini-2.0-flash"
tokens:
  input: 84320
  output: 42150
  reasoning: 0
  total: 126470
compactions: 2
artifact_links_valid_until: "2026-04-11T15:30:00Z"
---

# Session transcript

## You (2026-04-01 10:00)
Can you help me build a Q3 marketing calendar?

## KEN-E (2026-04-01 10:00)
I can help with that...

### Tool call: search_kb("Q2 performance data")
Returned: ...

## Artifacts
- [Q3 Campaign Brief.pdf](<24-hour signed GCS URL>) — 2026-04-01
- [Channel Performance Report.xlsx](<24-hour signed GCS URL>) — 2026-04-02
```

The `artifact_links_valid_until` field surfaces the 24-hour expiry so a reader opening the file later knows to re-export if links have expired.

### 4.3 Delete response

```python
class DeleteSessionResponse(BaseModel):
    session_id: str
    deleted_at: datetime
    async_cleanup_task_id: str        # the Cloud Run task handle; surfaced for debugging
```

Response returns after the side-table write (synchronous). ADK + GCS cleanup happens asynchronously; failures are caught by CH-PRD-05's nightly ADK-session orphan scan.

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create | `frontend/src/components/chat/SessionStatusView.tsx` |
| Create | `frontend/src/components/chat/TitleCard.tsx` |
| Create | `frontend/src/components/chat/SummaryCard.tsx` |
| Create | `frontend/src/components/chat/TokenUsagePanel.tsx` (no cost line) |
| Create | `frontend/src/components/chat/ActivityCard.tsx` |
| Create | `frontend/src/components/chat/AuthStatusCard.tsx` |
| Create | `frontend/src/hooks/useChatSession.ts` |
| Modify | `frontend/src/pages/Chat.tsx` (from CH-PRD-02) — toggle button renders the status view |
| Modify | `frontend/src/lib/chatApi.ts` — wrappers for status-detail, export, delete (extend), put-title. **Also:** ship a no-op stub `useTestConnectionMutation` hook here (returns `{ mutate: noop, mutateAsync: async () => null, isPending: false, data: undefined }`) so `AuthStatusCard.tsx` has a stable import to build against even before IN-PRD-07 ships. IN-PRD-07's frontend scope replaces the stub's body with a one-line re-export from `frontend/src/app/lib/api/integrations.ts`. The component-side call site never changes. |
| Create | `api/src/kene_api/chat/status_detail.py` — `get_status_detail(session_id) → ChatStatusDetail` |
| Create | `api/src/kene_api/chat/export.py` — `export_session_as_markdown(session_id)` using `yaml.safe_dump` |
| Create | `api/src/kene_api/chat/auto_title.py` — `generate_session_title(session_id, user_id)` async generator using `gemini-2.5-flash`. See §5.7. |
| Modify | `api/src/kene_api/routers/chat.py` — 4 endpoints: `/status-detail`, `/export`, `DELETE` extended, `PUT` title (PUT also stamps `auto_title_attempted_at = now()` synchronously to suppress auto-title when the user beats it). |
| Modify | `api/src/kene_api/chat/side_table.py` — `tombstone(session_id)` fleshed out (creates Cloud Run task); add `update_from_delta` callsite that sets `auto_title_attempted_at` on PUT-title. |
| Modify | `api/src/kene_api/chat/accumulator.py` (from CH-PRD-01) — at end of `build_delta()`, hook a check: if `message_count == 2 AND title is None AND auto_title_attempted_at is None` after applying the delta, return a side-channel "should_fire_auto_title" signal that the completion endpoint's `finally` reads; if true, fire-and-forget `generate_session_title(...)`. |
| Modify | `api/src/kene_api/routers/chat.py` (completion endpoint, from CH-PRD-01) — `finally` block reads the accumulator's auto-title signal and fires the background task. |
| Create | `api/src/kene_api/chat/cleanup_task.py` — Cloud Run background handler for async ADK + GCS delete |
| Modify | `deployment/terraform/cloud_run.tf` — optional: separate cleanup worker (or piggy-back on existing job runner) |
| Create | `api/tests/unit/chat/test_status_detail.py` |
| Create | `api/tests/unit/chat/test_export_markdown.py` |
| Create | `api/tests/unit/chat/test_export_yaml_safe.py` |
| Create | `api/tests/unit/chat/test_auto_title.py` — happy path; race with manual edit; flag-off skip; failure path leaves title null + `auto_title_attempted_at` set; second turn does not retry. |
| Create | `api/tests/integration/chat/test_delete_two_phase.py` |
| Create | `api/tests/integration/chat/test_auto_title_billing_meter.py` — assert tokens consumed by `gemini-2.5-flash` flow through `extract_billable_tokens` and increment the org's BL-PRD-02 meter. |
| Create | `frontend/src/components/chat/__tests__/SessionStatusView.spec.tsx` |
| Create | `frontend/src/components/chat/__tests__/TokenUsagePanel.spec.tsx` |
| Create | `frontend/src/components/chat/__tests__/AuthStatusCard.spec.tsx` |
| Create | `frontend/tests/e2e/chat-status-view.spec.ts` |

**Not created / not modified (explicitly):**
- No `api/src/kene_api/chat/compaction.py` (Compact-now is out of v1).
- No `frontend/src/components/chat/PlaceholderCard.tsx` for a Permissions placeholder (the Permissions Approved figma card is not rendered at all).
- No new backend endpoint for the Auth Status card — consumes `GET /integrations/{account_id}/connections` (IN-PRD-03) and `POST /connections/{id}/test` (IN-PRD-07) directly from the frontend.

### 5.2 Status view layout

Port from `docs/figma-export/src/app/components/SessionSettings.tsx` with the following deviations:

- **Summary card:** replace the editable `Textarea` with a read-only text block. Caption reads "Auto-generated during compaction" (drop "You can edit this summary"). Empty state: "No summary yet. KEN-E compacts long sessions automatically."
- **Activity card (new, derived from fields):** one line each for "Last activity: 2h ago"; "Duration: 34 minutes"; "Activity: 12 tool calls • 2 compactions • 3 artifacts created".
- **Action row (simplified):** two buttons below all cards — **Export transcript** and **Delete session**. Delete opens a confirm dialog ("Delete this session? This cannot be undone. All artifacts will be removed from storage."). Compact-now button does not exist.
- **Token Usage Panel:** context bar + badge, 3-card token grid (Input / Output / Total). No cost line, no cost math anywhere in the component.
- **Permissions Approved:** not rendered. Its slot is empty space; copy from the figma is not ported.
- **Authentication Status:** rendered per §5.6. Replaces the figma's "Loaded Tools" card (the rename reflects that the rendered content is account-level integration auth state, not per-session tool loading). Figma reference: `SessionSettings.tsx` lines ~526–586.

### 5.3 `/status-detail` composite read

```python
async def get_status_detail(session_id: str, user_id: str) -> ChatStatusDetail:
    meta = await side_table.get(session_id)
    if meta is None or meta.user_id != user_id or meta.deleted_at:
        raise HTTPException(404)

    # Artifacts subcollection read (owned by CH-PRD-05 but surfaced here)
    artifacts = await artifact_index.list(session_id)

    # Todo lists from session.state (owned by CH-PRD-05)
    todo_lists = await todos.list(session_id)

    # is_agent_running derived (no persistent boolean field; see CH-PRD-01 §5.2)
    now = datetime.now(tz=UTC)
    STUCK_THRESHOLD = timedelta(minutes=10)
    is_agent_running = (
        meta.last_agent_started_at is not None
        and (meta.last_agent_stopped_at is None
             or meta.last_agent_started_at > meta.last_agent_stopped_at)
        and (now - meta.last_agent_started_at) < STUCK_THRESHOLD
    )

    total_tokens = meta.input_tokens_total + meta.output_tokens_total + meta.reasoning_tokens_total

    return ChatStatusDetail(
        metadata=meta,
        artifacts=artifacts,
        todo_lists=todo_lists,
        is_agent_running=is_agent_running,
        context_usage_percent=round(meta.current_context_tokens / max(meta.context_window_max, 1), 4),
        duration_seconds=int((
            (meta.last_agent_message_at or meta.updated_at) - meta.created_at
        ).total_seconds()),
        activity_summary=f"{meta.tool_call_count} tool calls • {meta.compaction_count} compactions • {meta.artifact_count} artifacts",
        total_tokens=total_tokens,
    )
```

If CH-PRD-05 hasn't shipped: `artifact_index.list(session_id) → []`; `todos.list(session_id) → []`. Status view renders empty-state cards.

### 5.4 Export flow

```python
import yaml

async def export_session_as_markdown(session_id: str, user_id: str) -> StreamingResponse:
    meta = await side_table.get(session_id)
    if meta is None or meta.user_id != user_id:
        raise HTTPException(404)

    events = await adk_session_service.get_session_events(session_id)
    artifacts = await artifact_index.list(session_id)

    expires_at = datetime.now(tz=UTC) + timedelta(hours=24)

    async def generate():
        front_matter = {
            "title": meta.title or "Untitled session",
            "session_id": meta.session_id,
            "category": meta.category_name,  # resolved on-the-fly; None if uncategorized
            "created_at": meta.created_at.isoformat(),
            "last_activity": (meta.last_agent_message_at or meta.updated_at).isoformat(),
            "duration": humanize_duration(meta.last_agent_message_at - meta.created_at),
            "model": meta.model_id,
            "tokens": {
                "input": meta.input_tokens_total,
                "output": meta.output_tokens_total,
                "reasoning": meta.reasoning_tokens_total,
                "total": meta.input_tokens_total + meta.output_tokens_total + meta.reasoning_tokens_total,
            },
            "compactions": meta.compaction_count,
            "artifact_links_valid_until": expires_at.isoformat(),
        }
        yield "---\n"
        yield yaml.safe_dump(front_matter, default_flow_style=False, sort_keys=False)
        yield "---\n\n# Session transcript\n\n"
        async for ev in events:
            yield format_event_as_markdown(ev)
        if artifacts:
            yield "\n## Artifacts\n\n"
            for a in artifacts:
                signed_url = gcs.generate_signed_url(a.gcs_path, ttl_seconds=86400)  # 24 hours
                yield f"- [{a.filename}]"
                yield f"({signed_url}) — {a.created_at:%Y-%m-%d}\n"

    return StreamingResponse(
        generate(),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="session-{session_id}.md"'},
    )
```

**Why `yaml.safe_dump` matters:** titles like `"Q3: \"Grand\" plan"` or summaries containing `---` would break a hand-templated front-matter. `safe_dump` handles escaping uniformly.

**Rate limit:** 10/hour/session via Billing's BL-PRD-05 limiter (fallback: in-process limiter if BL-PRD-05 hasn't shipped).

### 5.5 Delete two-phase

```python
async def delete_session(session_id: str, user_id: str) -> DeleteSessionResponse:
    meta = await side_table.get(session_id)
    if meta is None or meta.user_id != user_id:
        raise HTTPException(404)

    # Phase 1: synchronous tombstone
    await side_table.update_from_delta(session_id, {
        "deleted_at": now_utc(),
        "updated_at": now_utc(),
    })

    # Phase 2: async cleanup
    task_id = await cloud_run_tasks.enqueue(
        "chat_cleanup_task",
        payload={"session_id": session_id, "user_id": user_id, "account_id": meta.account_id},
    )
    return DeleteSessionResponse(
        session_id=session_id,
        deleted_at=now_utc(),
        async_cleanup_task_id=task_id,
    )

# cleanup_task.py (Cloud Run job handler)
async def chat_cleanup_task(payload: dict):
    session_id = payload["session_id"]
    account_id = payload["account_id"]
    # 1. ADK session delete
    await adk_session_service.delete_session(app_name="ken_e_chatbot", session_id=session_id)
    # 2. Artifact index + GCS blobs
    artifacts = await artifact_index.list(session_id)
    for a in artifacts:
        await gcs.delete_blob(a.gcs_path)
    await firestore.delete_collection_group(
        parent=f"accounts/{account_id}/chat_sessions/{session_id}/artifacts",
    )
    # 3. Finally, delete the side-table row
    await firestore.delete_document(f"accounts/{account_id}/chat_sessions/{session_id}")
```

**Failure handling:** 3 retries with exponential backoff. On permanent failure, ops is paged. The ADK session that didn't delete is caught the next day by CH-PRD-05's ADK-session orphan scan (which compares `list_sessions` against side-table rows and deletes ADK sessions whose side-table is tombstoned or missing).

### 5.6 Authentication Status card

A read-only surface in v1; upgraded to interactive when IN-PRD-07 ships. Pure frontend composition — no new backend endpoint.

**Data sources (composition, not aggregation):**

```text
AuthStatusCard(accountId):
  connections = useConnections(accountId)                      // IN-PRD-03 hook
  testMutation = useTestConnectionMutation()                   // stubbed on CH-PRD-04 ship;
                                                               // real implementation after IN-PRD-07
  testFlagEnabled = useFeatureFlag("integrations_connection_test_enabled")

  for each platform in connections:
     render <PlatformRow
        platform={platform}
        onCheckStatus={testFlagEnabled ? () => testMutation.mutate(...) : undefined}
     />
```

**`useTestConnectionMutation` import seam** — CH-PRD-04 ships a no-op stub of this hook in `frontend/src/lib/chatApi.ts` (see §5.1) so `AuthStatusCard.tsx` has a stable import that compiles regardless of whether IN-PRD-07 has landed. The stub's shape exactly matches the real hook IN-PRD-07 ships in `frontend/src/app/lib/api/integrations.ts` — same return fields (`mutate`, `mutateAsync`, `isPending`, `data`), same argument signature. When `integrations_connection_test_enabled=false` the mutation is never invoked, so the stub being a no-op is safe. When IN-PRD-07 ships, its frontend scope replaces the stub body with a one-line re-export; no change to the component's call site. This is the same graceful-degradation seam pattern CH-PRD-04 already uses for `CategoriesDropdown` (CH-PRD-03 soft dep) and `TodoListsPanel` / `ArtifactsPanel` (CH-PRD-05 soft deps).

**Row-state derivation** (pure function of `PlatformConnection` + last `ConnectionTestResult`):

| Inputs | Rendered state |
|---|---|
| No connection row for this platform | **Not connected** — grey dot + "Connect" CTA → deep-link `/settings/integrations` |
| `status=connected`, no test result (or test `ok=true`) | **Authenticated** — green dot + "Authenticated" badge |
| `status=connected`, last test `is_transient=true` | **Transient error** — amber dot + "Retry" button (IN-PRD-07's cache does not extend on transient, so retry re-probes) |
| `status=connected`, last test definitive failure (`auth_failed` / `scope_missing`) | **Needs re-auth** — red dot + "Reconnect" CTA → deep-link `/settings/integrations/{connection_id}` |
| `status ∈ {expired, revoked, error}` | **Needs re-auth** — red dot + "Reconnect" CTA → deep-link `/settings/integrations/{connection_id}` |
| `no_probe_configured` last-test result | **Authenticated** fallback — we still trust `status=connected`; no live-test available but the connection exists. The per-row Check Status button is rendered **disabled** (not hidden) with tooltip text "Live verification not available for this platform" — preserves visual consistency across rows. |

When IN-PRD-07 is **not yet shipped**: the "Check Status" button is not rendered (flag off). Rows still render with the four states; the derivation simply never sees a test result. "Last Checked" row uses `connected_at` as the fallback timestamp label — copy reads "Connected: {date}" instead of "Last Checked: {date}" to avoid implying a live probe ran.

When IN-PRD-07 **is shipped**: the "Check Status" button appears on every connected-status row, calls `useTestConnectionMutation`, shows a 1.2s spinner, updates the row state + "Last Checked: {date}" on return. Two clicks within 60s hit the cache (per IN-PRD-07 §5.2) — visible as "cached (verified Ns ago)" tooltip on the badge. No new rate limits added by Chat; IN-PRD-07's cache is the rate limit.

**Row-click (not on button)**: deep-links to `/settings/integrations/{connection_id}` for existing connections, or `/settings/integrations` for not-connected platforms. Accessibility: the card lists rows with `role="button"` where the row is clickable; CTA buttons have their own accessible labels and stop click propagation.

**Aggregate count in the header**: `"{connected_count}/{total_enabled_platforms} connected"` where `connected_count = connections.filter(c => c.status === "connected").length` and `total_enabled_platforms = connections.length` (the IN-PRD-03 endpoint already filters to platforms whose per-platform feature flags are on). When `connected_count === 0 && total_enabled_platforms === 0`, the card renders an empty state with "No integrations available for this account" + link to `/settings/integrations` for the setup flow.

**Feature-flag degradation**:

| `chat_status_detail_enabled` | `integrations_connection_test_enabled` | Card behavior |
|---|---|---|
| off | any | Whole status view hidden (existing behavior) |
| on | off | Card renders; Check Status button hidden; row states derive from `status` only; "Connected: {date}" label |
| on | on | Card renders; Check Status button visible; row states react to live test results; "Last Checked: {date}" label |

### 5.7 Auto-title generation

Once-per-session, after the first assistant response completes. Asynchronous (no impact on streaming UX), billable through the org's monthly meter, suppressed by manual title edits, and never retried after the first attempt regardless of outcome.

**Trigger condition.** CH-PRD-01's `SessionTurnAccumulator.build_delta()` includes the `message_count` increment for the just-completed turn. After the side-table update lands, the completion endpoint's `finally` block re-reads the resulting metadata and checks:

```text
should_fire_auto_title = (
    message_count == 2                       # first user message + first assistant response
    AND title is None                        # user has not set one
    AND auto_title_attempted_at is None      # we have not already tried
    AND chat_auto_title_enabled              # ops kill switch
)
```

If true, the endpoint fires `asyncio.create_task(generate_session_title(session_id, user_id))` and continues. The streaming response has already finished by the time `finally` runs; the user sees no latency.

**Generator (`api/src/kene_api/chat/auto_title.py`):**

```python
AUTO_TITLE_PROMPT = """Generate a concise 3-6 word title that captures
what this conversation is about. Return ONLY the title text — no quotes,
no punctuation at the end, no leading/trailing whitespace.

User message: {user_msg}
Assistant response: {assistant_msg}"""

async def generate_session_title(session_id: str, user_id: str) -> None:
    # Re-read in case user beat us to it (race-safe).
    meta = await side_table.get(session_id)
    if meta is None or meta.title is not None or meta.auto_title_attempted_at is not None:
        return
    if not feature_flags.is_enabled("chat_auto_title_enabled"):
        return

    events = await adk_session_service.get_session_events(session_id)
    user_msg = first_user_text(events)[:500]            # truncate to bound prompt cost
    assistant_msg = first_assistant_text(events)[:500]

    try:
        resp = await gemini_client.generate(
            model="gemini-2.5-flash",
            prompt=AUTO_TITLE_PROMPT.format(user_msg=user_msg, assistant_msg=assistant_msg),
            max_output_tokens=30,
            temperature=0.2,
        )
        # Bill the call against the org's BL-PRD-02 meter (same path as agent calls).
        billing.meter_increment(meta.organization_id, extract_billable_tokens(resp))
        title = resp.text.strip()[:120]
    except (GeminiError, asyncio.TimeoutError, ValueError) as e:
        log.warning("auto_title_failed", session_id=session_id, error=str(e))
        title = None  # leave title null; do not retry

    # Re-read again before write (race with manual edit).
    meta = await side_table.get(session_id)
    if meta is None or meta.title is not None:
        # User beat us to it. Stamp auto_title_attempted_at so we don't retry.
        await side_table.update_from_delta(session_id, {"auto_title_attempted_at": now_utc()})
        return

    delta = {"auto_title_attempted_at": now_utc()}
    if title:  # success path
        delta["title"] = title
        delta["search_text"] = casefold_search_text(meta, override_title=title)
    await side_table.update_from_delta(session_id, delta)
```

**Manual-edit suppression.** `PUT /conversations/{id}` (title-edit) is extended in this PRD to set `auto_title_attempted_at = now()` in the same Firestore update as the title write. This means: if a user types a title within the first ~2 seconds of the first agent reply (before the auto-title call lands), the suppression race is resolved synchronously by the user write; the in-flight auto-title generator's final re-read sees the user title and skips the title overwrite, only stamping `auto_title_attempted_at` (which is a no-op since the user already set it).

**Billing.** The Gemini call's `usage_metadata` is extracted via the shared `extract_billable_tokens(event)` helper (per CH-PRD-01 §5.4 — Billing-owned, in `shared/token_accounting.py`) and incremented against the org via `billing.meter_increment`. Same code path as agent calls; no duplicate metering. `test_auto_title_billing_meter.py` integration test asserts the meter advances.

**Failure semantics.** Any failure (Gemini API error, timeout, malformed response, empty string, post-strip 0-length) → log warning, leave title null, stamp `auto_title_attempted_at` to prevent retry. The user sees "Untitled session" until they edit. Acceptable v1 behavior; not worth a retry queue.

**Cost-of-feature ceiling.** With `gemini-2.5-flash` at ~30 output tokens × ~250 input tokens per call, average cost is well under $0.001 per session. At 100K sessions/month, that's <$100 — bounded and tracked through BL-PRD-02 like any other agent call.

## 6. API contract

### Extended

| Method | Path | Purpose |
|---|---|---|
| `PUT` | `/api/v1/chat/conversations/{id}` | Body `{title}` (renamed from `conversation_name`). Updates side-table + `search_text` (casefold) + sets `auto_title_attempted_at = now()` synchronously to suppress an in-flight auto-title call. |
| `DELETE` | `/api/v1/chat/conversations/{id}` | Two-phase tombstone. Returns 200 after side-table write; async ADK + GCS cleanup. |

### New

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/chat/conversations/{id}/status-detail` | Composite read. Gated by `chat_status_detail_enabled`. |
| `GET` | `/api/v1/chat/conversations/{id}/export?format=markdown` | Markdown transcript stream with 24-hour artifact URLs. `format=markdown` only in v1. Rate-limited 10/hour/session. |

**No `POST /conversations/{id}/compact` endpoint** (scoped out of v1).

**No new endpoint for the Authentication Status card.** The card is a pure frontend composition over `GET /api/v1/integrations/{account_id}/connections` (IN-PRD-03) and `POST /api/v1/integrations/{account_id}/connections/{connection_id}/test` (IN-PRD-07). The `account_id` passed to `useConnections` is the active account from the chat session's context (same account the session was created under, resolved via `useAccountContext()`).

Auth on all: authenticated user + session ownership. 404 on mismatch.

## 7. Acceptance criteria

1. **Status view renders** — user clicks Session Status in the page header, status view loads within 500ms p95 populated with real data for every card. **No Compact-now button, no Permissions Approved card, no cost line. The Authentication Status card renders per §5.6.**
2. **Title edit** — typing in the title `Input` debounces 500ms, fires `PUT /conversations/{id}`, sidebar row reflects on next poll. `search_text` re-derived via `casefold()`.
3. **Summary read-only** — caption reads "Auto-generated during compaction"; no edit affordance; empty state for sessions that haven't been compacted.
4. **Category dropdown** — mounts `CategoriesDropdown variant="assign"` from CH-PRD-03 (if shipped); read-only category label otherwise.
5. **Tokens + context** — all numbers populated from `ChatStatusDetail`; context bar + badge reflects %; total tokens = input + output + reasoning. No cost number rendered.
6. **Activity card** — "Last activity", "Duration", "Activity summary" lines render correctly.
7. **Export** — clicking the button streams a markdown file; front-matter serialized via `yaml.safe_dump` (hostile-character test: title `"Q3: \"Grand\" plan"` round-trips without breaking YAML); artifact links are signed GCS URLs with **24-hour TTL**; `artifact_links_valid_until` timestamp present in front-matter.
8. **Export rate limit** — 11th request in an hour returns 429.
9. **Delete** — confirm dialog; on confirm, `DELETE /conversations/{id}` fires; the sidebar removes the row immediately; the async cleanup task completes within 5 minutes; ADK session + GCS blobs + Firestore rows all cleaned. If the cleanup task fails, CH-PRD-05's nightly orphan scan catches the ADK session within 24 hours.
10. **Deleted session is gone** — `GET /status-detail` on a tombstoned session returns 404.
11. **No Permissions card** — visual regression test asserts the rendered component does NOT contain the figma "Permissions Approved" placeholder copy.
12. **No Compact-now button** — the action row renders exactly Export + Delete; automated test asserts no button with the "Compact now" or "Compact session" label exists.
13. **Polling** — while status view is open and agent is running, tokens + activity values update within 10s of each event. Polling pauses on `visibilitychange` hidden.
14. **Title rename affects sidebar search** — rename "Q2 planning" → "Q3 planning"; sidebar search for "Q3" now finds the session.
15. **Auth Status card — base rendering** — card renders with one row per integration returned by `GET /integrations/{account_id}/connections`. Aggregate header badge reads `"{connected}/{total} connected"` with numbers matching the rendered rows. Empty-account state ("No integrations available for this account") shows when the endpoint returns an empty list.
16. **Auth Status card — four row states** — with test fixtures covering (i) `status=connected` + ok test, (ii) `status=expired`, (iii) `status=connected` + transient test, (iv) no connection for a platform: all four rows render correct dot color (green / red / amber / grey), badge / CTA copy, and accessible labels. Visual regression test snapshots each state.
17. **Auth Status card — row click deep-link** — clicking a connected-status row (not on its button) navigates to `/settings/integrations/{connection_id}`; clicking a not-connected-status row navigates to `/settings/integrations`.
18. **Auth Status card — read-only mode (IN-PRD-07 not shipped)** — with `integrations_connection_test_enabled=false`, the Check Status button is NOT rendered on any row; row states derive from `PlatformConnection.status` only; timestamp label reads `"Connected: {date}"`. Automated test asserts no button labeled "Check Status" exists.
19. **Auth Status card — interactive mode (IN-PRD-07 shipped)** — with `integrations_connection_test_enabled=true`, every connected-status row renders a "Check Status" button; clicking it fires the IN-PRD-07 test mutation and updates the row's state + "Last Checked" timestamp within one render pass. Two clicks within 60s: second click shows cached-hit badge copy ("cached (verified Ns ago)"); network-request mock asserts exactly one HTTP call.
20. **Auth Status card — definitive failure flips row** — with the IN-PRD-07 endpoint mocked to return `ok=false, error.code=auth_failed`, clicking Check Status transitions the row to red + "Reconnect" CTA; deep-link target is `/settings/integrations/{connection_id}`. (Side-effect: IN-PRD-07's `mark_expired` runs; a subsequent `useConnections` refetch shows `status=expired` — asserted in the integration test.)
21. **Auth Status card — transient failure does not degrade** — with the endpoint mocked to return `ok=false, error.is_transient=true`, the row shows amber + "Retry"; clicking Retry re-probes (IN-PRD-07's cache does not extend on transient); connection `status` stays `connected`.
22. **Auth Status card — no probe configured** — for a platform whose `PlatformDefinition.health_check_endpoint` is null, last-test result `code="no_probe_configured"` does NOT degrade the row — it renders "Authenticated" based on `status=connected`. The Check Status button on that row is rendered **disabled** (not hidden) with tooltip text "Live verification not available for this platform"; the button's disabled state is detectable via `aria-disabled="true"` + the standard disabled attribute.
23. **Auth Status card — loading state** — while `useConnections` is pending (initial fetch or refetch after an invalidation), the card renders a skeleton with N rows where N = (a) the count of rows cached by TanStack Query from a prior fetch if available, (b) otherwise 3 skeleton rows as a neutral default. Header badge reads "Loading…" during the pending state. The skeleton uses the same row height as real rows to prevent layout shift when data arrives.
24. **Auth Status card — accessibility** — (a) each platform row has `role="button"` + `aria-label` summarizing `"{platform_display_name} — {state_label}"` (e.g. `"Google Ads — Authenticated"`, `"Mailchimp — Needs re-auth"`); (b) inner CTA buttons (Check Status / Reconnect / Retry / Connect) have their own accessible labels and stop-propagation on click so the row-click deep-link doesn't also fire; (c) keyboard navigation: Tab moves focus across rows, Enter on a focused row triggers the row-click deep-link, Tab-then-Enter on an inner button triggers its action; (d) the card region is `aria-live="polite"` so state changes after a Check Status call are announced to screen readers; (e) color is never the only cue — every state pairs the dot color with a text badge. Verified by an axe-core assertion in the component spec.
25. **Auto-title — happy path.** Send the first user message → first assistant response completes → within 10 seconds the side-table row's `title` is populated by `gemini-2.5-flash` with a 3–6 word title; `auto_title_attempted_at` is non-null; the sidebar reflects the title on its next poll. `search_text` is recomputed using the new title.
26. **Auto-title — manual edit beats auto-title.** Send the first user message → before the assistant response completes (or within ~1s after), the user PUTs a manual title via `PUT /conversations/{id}`. The PUT sets `auto_title_attempted_at` synchronously. The auto-title generator's final re-read sees a non-null title, skips the title write, and stamps `auto_title_attempted_at` (idempotent — already set). End state: user's manual title preserved; only one `auto_title_attempted_at` write.
27. **Auto-title — billing meter.** Integration test asserts the `gemini-2.5-flash` call's tokens flow through `extract_billable_tokens(event)` and increment the org's BL-PRD-02 monthly meter. Verifies the `usage_records` row has the right `organization_id` and tokens >0.
28. **Auto-title — flag off.** With `chat_auto_title_enabled=false`, no Gemini call fires; `auto_title_attempted_at` stays null; sessions retain `title=null` until the user edits. Asserted by network-mock count == 0.
29. **Auto-title — failure path.** Mock the Gemini client to raise `GeminiError` (or return empty string) → the generator catches, leaves `title=null`, sets `auto_title_attempted_at=now()`. Second turn does NOT retry (precondition `auto_title_attempted_at is None` fails). Asserted by network-mock count == 1 across 5 subsequent turns.
30. **Auto-title — idempotency.** Even if the trigger fires twice (e.g. duplicate side-table flush), the generator's first re-read finds `auto_title_attempted_at` non-null on the second invocation and returns immediately. Asserted by network-mock count == 1 when the trigger is invoked twice in rapid succession.

## 8. Test plan

### Unit (backend)
- `get_status_detail` composite assembly — correct derived fields; `is_agent_running` derivation matches table-driven fixture from CH-PRD-01.
- `export_session_as_markdown` — front-matter contains all required fields; `artifact_links_valid_until` is 24 hours out.
- `test_export_yaml_safe.py` — title with `"`, summary with `---`, category with `:` all round-trip through `yaml.safe_dump` + `yaml.safe_load` unchanged.
- `delete_session` — side-table tombstones; cleanup task enqueued; second DELETE is a no-op.
- `test_title_update_recomputes_search_text_with_casefold` — rename operation produces `casefold()`-normalized `search_text`.

### Unit (frontend)
- `SessionStatusView.spec.tsx` — renders every card with mock data; **asserts Permissions Approved + Compact-now + Cost are NOT rendered; asserts Authentication Status card IS rendered with a header labeled "Authentication Status".**
- `AuthStatusCard.spec.tsx` — per-state rendering (Authenticated / Needs re-auth / Transient / Not connected / no-probe fallback with **disabled Check Status button + tooltip**); aggregate count derivation; row-click deep-link behavior via mocked router; flag-off hides Check Status button while keeping the card; flag-on wires `useTestConnectionMutation` and shows cached-hit copy on repeat click; **loading state** (skeleton with N rows from cached count, or 3 as default; header badge reads "Loading…"; no layout shift when data arrives); **accessibility** via `axe.run()` on the rendered tree (expect no violations), plus explicit assertions on `role="button"` + `aria-label` on rows, `aria-disabled` on the disabled no-probe Check Status button, `aria-live="polite"` on the card region, and keyboard-nav behavior (Tab → row focus; Enter → deep-link; Tab-then-Enter → inner button action).
- `TokenUsagePanel.spec.tsx` — context bar + badge transitions at 60% / 80%; token numbers formatted with commas; no dollar-amount DOM node.
- `TitleCard.spec.tsx` — debounced save fires once per 500ms; optimistic update.
- `useChatSession.ts` — polling active when status view open; stops when closed.

### Integration
- `/status-detail` composite read — one round-trip; 500ms p95 on warm cache.
- Export E2E — seed a 20-event session; GET export; open downloaded file; parse YAML front-matter; assert every field correct.
- Delete two-phase — tombstone within 200ms; sidebar excludes within 1 poll; cleanup task completes within 5 min (CI can fast-forward).
- Delete with cleanup-task failure — simulate cleanup failure; assert nightly orphan scan (CH-PRD-05) would catch it in the next-day window (or tested directly).
- Auth Status card against a seeded account: one `connected` Google, one `expired` Meta, one not-connected Mailchimp — open the status view and assert the card shows three rows in the correct states with the correct CTAs, aggregate reads `"1/2 connected"` (Mailchimp not included in `total_enabled_platforms` when its per-platform flag is off, or `"1/3"` when on; pick one based on feature-flag fixture).
- Auth Status flag-off integration: `integrations_connection_test_enabled=false` → Check Status button absent across all rows; `useTestConnectionMutation` is not called on any interaction.

### E2E (Playwright)
- Open status view; edit title; close; reopen — title persists.
- Click Export; confirm download; open file; verify front-matter fields + 24-hour signed URL timestamp.
- Click Delete → confirm → session gone from sidebar.
- Assert Compact-now / Permissions / Cost are not in the DOM; assert the Authentication Status card IS in the DOM.
- Seed one connected integration in the Playwright fixture; open status view; assert the Auth Status row renders with the green "Authenticated" state; if IN-PRD-07 is enabled in the test env, click Check Status and assert the row updates.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Delete cleanup task fails silently → orphaned ADK session | CH-PRD-05's nightly ADK-session orphan scan catches ADK sessions whose side-table is tombstoned or missing. No permanent orphans. |
| 24-hour signed URL on export leaks an artifact if the exported file is shared | 24h TTL is a deliberate tradeoff between UX (links usable hours later) and security. Documented in front-matter (`artifact_links_valid_until`). If a stricter policy is needed later, per-org config can shorten TTL. |
| Title debounce races with sidebar poll | Optimistic update on the sidebar row on debounce commit; server response confirms. Stale row cleared on next poll. |
| Export for a very large session (500+ events) blows request timeout | Streaming response — chunks flush as events are read. Per-event render cost is bounded. |
| `current_context_tokens` becomes negative after an odd event order | Floor-at-0 on the update side in CH-PRD-01; compaction reset is the recomputed baseline (not `Increment`). Unit-tested there. |
| Summary card grows unbounded (huge transcript) | ADK compaction already bounds summary length; side-table truncates at 2 KB for `search_text` concatenation. Display-side has a "Show more" affordance if >400 chars. |
| Users ask where the Compact-now button went | Figma export is a design prototype, not a shipped-feature contract. Release notes call out the deferred feature. Auto-compaction still runs invisibly. |
| BL-PRD-05 rate limiter not available when CH-PRD-04 ships | In-process fallback limiter ships with CH-PRD-04; one-line swap when BL-PRD-05 merges. |
| Account-level integrations surfaced inside a per-session panel is confusing — the same list appears across every session | Card subtitle reads "Account-wide connection status"; row-click deep-links to `/settings/integrations` which is the canonical management surface. Not a novel pattern — the Context & Token Usage card is also per-session while the integrations it depends on are account-level. |
| IN-PRD-07 slips past CH-PRD-04 ship | Card ships read-only behind the soft-dep branch (no Check Status button, `"Connected: {date}"` timestamp label). IN-PRD-07's frontend scope explicitly includes the extension to turn the button on. No CH-PRD-04 re-release required — the flag flip does it. |
| Check Status button gives the impression of a per-session preflight | Button label is "Check Status" (not "Preflight"); result updates the shared account-level state, not anything session-scoped. Documented in the card's help tooltip if added later. |
| Auto-title produces inappropriate or hallucinated content (e.g. for sessions in unusual languages, prompt-injection-flavored first messages, or low-context exchanges) | Max 30 output tokens + temperature 0.2 + post-strip-and-truncate to 120 chars + `chat_auto_title_enabled` ops kill switch. Qualitative review on a stratified sample (10 sessions × 5 demographic buckets) during the first 2 weeks of rollout; if quality is unacceptable, flip flag off, re-tune prompt, re-enable. Runtime safety: if the model returns empty/whitespace-only, treat as failure (leave `title=null`). |
| Race between async auto-title generation and user manual edit | Two re-reads of `meta.title` inside `generate_session_title` (once before the LLM call, once before the side-table write); manual PUT also sets `auto_title_attempted_at` synchronously to suppress an in-flight call. Final-write check guarantees the user's title wins regardless of timing. AC #26 covers this. |
| `gemini-2.5-flash` not in `MODEL_CONTEXT_WINDOW_REGISTRY` | The model is registered at CH-PRD-01 ship time as part of the registry's coverage of every model referenced in `app/adk/agents/**/*.py`. CH-PRD-04 expands the registry's coverage spec to also include any model referenced from `app/adk/` more broadly (auto-title doesn't live under `agents/` but still must be registered). CI lint catches a missing entry. |
| Cost of auto-title at high session volume balloons | Bounded by design: 30 max output tokens × ~250 input tokens × `gemini-2.5-flash` rates → <$0.001/session. At 100K sessions/month: <$100. Tracked in Billing's existing per-org meter. If volume grows beyond plan, the kill switch is the immediate lever. |

### Open questions
- **Q:** Is 10 exports/hour/session too restrictive for power users? → **Proposal:** start there; revisit based on observed abuse patterns. Easy to loosen via config.
- **Q:** Should the Export filename include the session title (slugified) or just the session id? → **Proposal:** `session-{date}-{first-6-chars-of-title-slug-or-id}.md`. Human-friendly; unique enough.
- **Q:** What happens to the status view if the user deletes a session another user somehow had open (shouldn't happen, but)? → Ownership check on every endpoint returns 404. Front-end detects 404 and navigates back to `/chat`.
- **Q:** Should the Auth Status card filter to platforms with a connection (hiding not-connected platforms), or show every enabled platform including disconnected ones? → **Proposal:** show every enabled platform (what `GET /integrations/{account_id}/connections` already returns — per IN-PRD-03 §6 the endpoint surfaces all platforms with per-platform flag on, including not-connected ones). Matches the figma mock's "8 integrations with 6 connected" framing and makes onboarding next-steps visible without leaving the chat.
- **Q:** Does the Auth Status card need to refetch when the chat status view is reopened, or is stale account data acceptable for 60s? → **Proposal:** `useConnections` already uses TanStack Query defaults (refetch on window focus + 60s staleTime). No special Chat-specific refetch logic needed.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Component README: [`../README.md`](../README.md)
- Upstream: [CH-PRD-01](./CH-PRD-01-session-metadata-substrate.md), [CH-PRD-02](./CH-PRD-02-chat-page-shell-and-sidebar.md)
- Mounts from: [CH-PRD-03](./CH-PRD-03-session-categories.md), [CH-PRD-05](./CH-PRD-05-todo-lists-and-artifacts.md)
- ADK-session orphan scan (safety net for delete failures): [CH-PRD-05](./CH-PRD-05-todo-lists-and-artifacts.md)
- Rate-limit substrate: [BL-PRD-05](../../billing/projects/BL-PRD-05-failure-modes-permissions.md)
- Auth Status card data source + deep-link target: [IN-PRD-03](../../integrations/projects/IN-PRD-03-connection-management-ui.md)
- Auth Status card interactive upgrade (soft dep): [IN-PRD-07](../../integrations/projects/IN-PRD-07-on-demand-connection-test.md)
- Figma: `docs/figma-export/src/app/components/SessionSettings.tsx` (with scope deviations noted in §2; Auth Status card at lines ~526–586)
- PyYAML `safe_dump`: https://pyyaml.org/wiki/PyYAMLDocumentation
- CLAUDE.md rules in scope: C-4, C-5, C-6, C-7; PY-1, PY-2, PY-3, PY-5; T-1, T-2, T-3, T-4, T-5; G-1, G-2, G-3
