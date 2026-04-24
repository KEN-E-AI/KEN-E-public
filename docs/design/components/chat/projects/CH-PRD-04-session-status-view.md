# CH-PRD-04 — Session Status View

**Status:** Not started
**Owner team:** Chat component team (full-stack)
**Blocked by:** [CH-PRD-02](./CH-PRD-02-chat-page-shell-and-sidebar.md) (page shell + toggle button mount point)
**Parallel with:** CH-PRD-03, CH-PRD-05
**Blocks:** none
**Estimated effort:** 4 days full-stack (reduced from 5 after Compact-now, placeholder cards, and cost were scoped out)

---

## 1. Context

The session status view is the side panel a user opens to inspect a session's identity, history, and usage. It surfaces: editable title, category assignment (dropdown from CH-PRD-03), model-generated summary (read-only), documents list (CH-PRD-05), todo lists (CH-PRD-05), token usage (input / output / total), context-window usage (% bar with Healthy/Moderate/Near-limit badge), last-activity + duration, and an activity summary ("12 tool calls • 2 compactions • 3 artifacts"). Below these cards sit two action buttons: **Export** and **Delete**.

The page-level `Session Status` button (mounted in CH-PRD-02) toggles between chat and status view. CH-PRD-04 delivers the toggle's destination plus the composite `GET /status-detail` endpoint that feeds it in one round-trip, plus two backend actions (export, delete two-phase).

Two figma deviations are resolved here: **summary is read-only** (figma's "You can edit this summary" copy is replaced with "Auto-generated during compaction" and the textarea becomes a read-only text block), and **multi-session concurrency via status dots** is handled in CH-PRD-02 (CH-PRD-04 does not own the dots; only the status view).

Three figma elements are **explicitly out of scope** for v1:
- **"Compact now" button** — manual compaction is deferred. ADK's automatic compaction continues to run.
- **"Permissions Approved" card** — not rendered at all (no placeholder, no mock data, no flag).
- **"Loaded Tools" card** — same.
- **"Cost" line** — per-session cost requires subscription-level pricing lookups that are owned by Billing; Chat shows token counts only.

Landing the status view completes the "see everything about a session" surface the user spec described. The validation checkpoint is that opening the status view on any session returns every field populated correctly within 500ms p95, and the two action buttons (Export, Delete) each work end-to-end.

## 2. Scope

### In scope

- **`frontend/src/components/chat/SessionStatusView.tsx`** — port + scope-adjusted version of `docs/figma-export/src/app/components/SessionSettings.tsx`. Card grid: Title card + Category card + Summary card + Documents card + Todo Lists card + Context & Token Usage card + Activity card. Action buttons row: Export, Delete. **No Compact-now button.** **No Permissions Approved card.** **No Loaded Tools card.** **No Cost line.**
- **`GET /api/v1/chat/conversations/{id}/status-detail`** — composite endpoint returning `ChatStatusDetail` (metadata + artifacts + todo_lists + derived fields: `is_agent_running`, `context_usage_percent`, `duration_seconds`, `activity_summary`, `total_tokens`). One round-trip per open.
- **`GET /api/v1/chat/conversations/{id}/export?format=markdown`** — streams a markdown transcript. YAML front-matter (serialized via `yaml.safe_dump` for hostile-character safety) with metadata; message log body. Embedded artifact signed URLs use a **24-hour TTL** (extended from the 10-minute TTL used for in-app artifact listing) so that exports are usable hours after download.
- **`DELETE /api/v1/chat/conversations/{id}`** extension — two-phase tombstone (synchronous side-table `deleted_at=now()`; async ADK + GCS + artifact cleanup via Cloud Run background task). Cleanup task retries up to 3× with exponential backoff; on permanent failure, pages ops. The orphaned ADK session is later caught by the nightly ADK-session orphan scan owned by CH-PRD-05.
- **`PUT /api/v1/chat/conversations/{id}`** extension — title-only edit. Body `{title}`. Updates side-table + recomputes `search_text` (using `casefold()`). Existing endpoint is re-shaped (was `conversation_name` field — now `title`).
- **`TokenUsagePanel.tsx`** — renders: context bar + badge (Healthy <60%, Moderate 60–80%, Near-limit >80%), 3-card token grid (Input / Output / Total). **No cost line.**
- **`SummaryCard.tsx`** — read-only. "Auto-generated during compaction" caption + summary text or placeholder "No summary yet. KEN-E compacts long sessions automatically."
- **`TitleCard.tsx`** — editable `Input` + debounced save (500ms after last keystroke).
- **`ActivityCard.tsx`** — last-activity, duration, activity summary lines.
- **`useChatSession.ts`** — TanStack `useQuery` hook consuming `/status-detail`. Polls every 10s while the status view is open (so tokens + activity counts update during an in-flight response); pauses on `visibilitychange` hidden.
- **`chat/export.py`** — `export_session_as_markdown(session_id) → StreamingResponse`. YAML front-matter via `yaml.safe_dump(front_matter_dict)`; transcript body streamed event-by-event; inline artifact links with 24h signed URLs.
- **Delete two-phase** — `DELETE /conversations/{id}` sets `deleted_at=now()` synchronously; fire-and-forget Cloud Run task calls `VertexAiSessionService.delete_session` + iterates artifact GCS blobs + deletes Firestore rows.
- **Rate limits** — Export is rate-limited 10/hour/session (prevents abuse of signed-URL generation). Uses Billing's BL-PRD-05 sliding-window limiter when available; minimal in-process fallback otherwise.
- **Telemetry** — Weave spans `chat.status_detail.read`, `chat.export`, `chat.delete`, `chat.title.updated`.
- **Feature flag gating** — status view gated by `chat_status_detail_enabled`; when off, the toggle button in the page header is hidden.

### Out of scope

- **Compact now button / manual compaction.** Deferred beyond v1. ADK's automatic compaction still runs.
- **Permissions Approved card.** Not rendered at all in v1; no placeholder, no mock data, no flag. Future PRD delivers when permission approval becomes a real feature.
- **Loaded Tools card.** Same — not rendered at all. Future PRD delivers when per-session tool loading becomes a real feature.
- **Per-session cost display.** Subscription-level pricing is Billing's concern; adding session-level cost requires lookups Chat intentionally doesn't own.
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
| **[BL-PRD-05](../../billing/projects/BL-PRD-05-failure-modes-permissions.md)** (soft) | Rate-limit substrate for the export endpoint. Fallback: minimal in-process limiter. | `../../billing/README.md` |
| Existing `DELETE /conversations/{id}` | Base endpoint; CH-PRD-04 adds the side-table tombstone + async cleanup. | `api/src/kene_api/routers/chat.py` |
| GCS signed URLs | 10-minute TTL for in-app listing; 24-hour TTL for export-embedded links. | GCP |
| **[FF-PRD-01](../../feature-flags/projects/FF-PRD-01-data-model-evaluation-api-backend-sdk.md)**, **[FF-PRD-03](../../feature-flags/projects/FF-PRD-03-frontend-sdk-e2e.md)** | `chat_status_detail_enabled` flag. | `../../feature-flags/README.md` |

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
| Create | `frontend/src/hooks/useChatSession.ts` |
| Modify | `frontend/src/pages/Chat.tsx` (from CH-PRD-02) — toggle button renders the status view |
| Modify | `frontend/src/lib/chatApi.ts` — wrappers for status-detail, export, delete (extend), put-title |
| Create | `api/src/kene_api/chat/status_detail.py` — `get_status_detail(session_id) → ChatStatusDetail` |
| Create | `api/src/kene_api/chat/export.py` — `export_session_as_markdown(session_id)` using `yaml.safe_dump` |
| Modify | `api/src/kene_api/routers/chat.py` — 4 endpoints: `/status-detail`, `/export`, `DELETE` extended, `PUT` title |
| Modify | `api/src/kene_api/chat/side_table.py` — `tombstone(session_id)` fleshed out (creates Cloud Run task) |
| Create | `api/src/kene_api/chat/cleanup_task.py` — Cloud Run background handler for async ADK + GCS delete |
| Modify | `deployment/terraform/cloud_run.tf` — optional: separate cleanup worker (or piggy-back on existing job runner) |
| Create | `api/tests/unit/chat/test_status_detail.py` |
| Create | `api/tests/unit/chat/test_export_markdown.py` |
| Create | `api/tests/unit/chat/test_export_yaml_safe.py` |
| Create | `api/tests/integration/chat/test_delete_two_phase.py` |
| Create | `frontend/src/components/chat/__tests__/SessionStatusView.spec.tsx` |
| Create | `frontend/src/components/chat/__tests__/TokenUsagePanel.spec.tsx` |
| Create | `frontend/tests/e2e/chat-status-view.spec.ts` |

**Not created / not modified (explicitly):**
- No `api/src/kene_api/chat/compaction.py` (Compact-now is out of v1).
- No `frontend/src/components/chat/PlaceholderCard.tsx` (Permissions + Loaded Tools cards are not rendered).

### 5.2 Status view layout

Port from `docs/figma-export/src/app/components/SessionSettings.tsx` with the following deviations:

- **Summary card:** replace the editable `Textarea` with a read-only text block. Caption reads "Auto-generated during compaction" (drop "You can edit this summary"). Empty state: "No summary yet. KEN-E compacts long sessions automatically."
- **Activity card (new, derived from fields):** one line each for "Last activity: 2h ago"; "Duration: 34 minutes"; "Activity: 12 tool calls • 2 compactions • 3 artifacts created".
- **Action row (simplified):** two buttons below all cards — **Export transcript** and **Delete session**. Delete opens a confirm dialog ("Delete this session? This cannot be undone. All artifacts will be removed from storage."). Compact-now button does not exist.
- **Token Usage Panel:** context bar + badge, 3-card token grid (Input / Output / Total). No cost line, no cost math anywhere in the component.
- **Permissions Approved + Loaded Tools:** the corresponding figma cards are NOT rendered. Their slots are empty space; copy from the figma is not ported.

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
                yield f"- [{a.filename}]({signed_url}) — {a.created_at:%Y-%m-%d}\n"

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

## 6. API contract

### Extended

| Method | Path | Purpose |
|---|---|---|
| `PUT` | `/api/v1/chat/conversations/{id}` | Body `{title}` (renamed from `conversation_name`). Updates side-table + `search_text` (casefold). |
| `DELETE` | `/api/v1/chat/conversations/{id}` | Two-phase tombstone. Returns 200 after side-table write; async ADK + GCS cleanup. |

### New

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/chat/conversations/{id}/status-detail` | Composite read. Gated by `chat_status_detail_enabled`. |
| `GET` | `/api/v1/chat/conversations/{id}/export?format=markdown` | Markdown transcript stream with 24-hour artifact URLs. `format=markdown` only in v1. Rate-limited 10/hour/session. |

**No `POST /conversations/{id}/compact` endpoint** (scoped out of v1).

Auth on all: authenticated user + session ownership. 404 on mismatch.

## 7. Acceptance criteria

1. **Status view renders** — user clicks Session Status in the page header, status view loads within 500ms p95 populated with real data for every card. **No Compact-now button, no Permissions Approved card, no Loaded Tools card, no cost line.**
2. **Title edit** — typing in the title `Input` debounces 500ms, fires `PUT /conversations/{id}`, sidebar row reflects on next poll. `search_text` re-derived via `casefold()`.
3. **Summary read-only** — caption reads "Auto-generated during compaction"; no edit affordance; empty state for sessions that haven't been compacted.
4. **Category dropdown** — mounts `CategoriesDropdown variant="assign"` from CH-PRD-03 (if shipped); read-only category label otherwise.
5. **Tokens + context** — all numbers populated from `ChatStatusDetail`; context bar + badge reflects %; total tokens = input + output + reasoning. No cost number rendered.
6. **Activity card** — "Last activity", "Duration", "Activity summary" lines render correctly.
7. **Export** — clicking the button streams a markdown file; front-matter serialized via `yaml.safe_dump` (hostile-character test: title `"Q3: \"Grand\" plan"` round-trips without breaking YAML); artifact links are signed GCS URLs with **24-hour TTL**; `artifact_links_valid_until` timestamp present in front-matter.
8. **Export rate limit** — 11th request in an hour returns 429.
9. **Delete** — confirm dialog; on confirm, `DELETE /conversations/{id}` fires; the sidebar removes the row immediately; the async cleanup task completes within 5 minutes; ADK session + GCS blobs + Firestore rows all cleaned. If the cleanup task fails, CH-PRD-05's nightly orphan scan catches the ADK session within 24 hours.
10. **Deleted session is gone** — `GET /status-detail` on a tombstoned session returns 404.
11. **No Permissions / Loaded Tools cards** — visual regression test asserts the rendered component does NOT contain the figma placeholder copy for either card.
12. **No Compact-now button** — the action row renders exactly Export + Delete; automated test asserts no button with the "Compact now" or "Compact session" label exists.
13. **Polling** — while status view is open and agent is running, tokens + activity values update within 10s of each event. Polling pauses on `visibilitychange` hidden.
14. **Title rename affects sidebar search** — rename "Q2 planning" → "Q3 planning"; sidebar search for "Q3" now finds the session.

## 8. Test plan

### Unit (backend)
- `get_status_detail` composite assembly — correct derived fields; `is_agent_running` derivation matches table-driven fixture from CH-PRD-01.
- `export_session_as_markdown` — front-matter contains all required fields; `artifact_links_valid_until` is 24 hours out.
- `test_export_yaml_safe.py` — title with `"`, summary with `---`, category with `:` all round-trip through `yaml.safe_dump` + `yaml.safe_load` unchanged.
- `delete_session` — side-table tombstones; cleanup task enqueued; second DELETE is a no-op.
- `test_title_update_recomputes_search_text_with_casefold` — rename operation produces `casefold()`-normalized `search_text`.

### Unit (frontend)
- `SessionStatusView.spec.tsx` — renders every card with mock data; **asserts Permissions Approved + Loaded Tools + Compact-now + Cost are NOT rendered.**
- `TokenUsagePanel.spec.tsx` — context bar + badge transitions at 60% / 80%; token numbers formatted with commas; no dollar-amount DOM node.
- `TitleCard.spec.tsx` — debounced save fires once per 500ms; optimistic update.
- `useChatSession.ts` — polling active when status view open; stops when closed.

### Integration
- `/status-detail` composite read — one round-trip; 500ms p95 on warm cache.
- Export E2E — seed a 20-event session; GET export; open downloaded file; parse YAML front-matter; assert every field correct.
- Delete two-phase — tombstone within 200ms; sidebar excludes within 1 poll; cleanup task completes within 5 min (CI can fast-forward).
- Delete with cleanup-task failure — simulate cleanup failure; assert nightly orphan scan (CH-PRD-05) would catch it in the next-day window (or tested directly).

### E2E (Playwright)
- Open status view; edit title; close; reopen — title persists.
- Click Export; confirm download; open file; verify front-matter fields + 24-hour signed URL timestamp.
- Click Delete → confirm → session gone from sidebar.
- Assert Compact-now / Permissions / Loaded Tools / Cost are not in the DOM.

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

### Open questions
- **Q:** Is 10 exports/hour/session too restrictive for power users? → **Proposal:** start there; revisit based on observed abuse patterns. Easy to loosen via config.
- **Q:** Should the Export filename include the session title (slugified) or just the session id? → **Proposal:** `session-{date}-{first-6-chars-of-title-slug-or-id}.md`. Human-friendly; unique enough.
- **Q:** What happens to the status view if the user deletes a session another user somehow had open (shouldn't happen, but)? → Ownership check on every endpoint returns 404. Front-end detects 404 and navigates back to `/chat`.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Component README: [`../README.md`](../README.md)
- Upstream: [CH-PRD-01](./CH-PRD-01-session-metadata-substrate.md), [CH-PRD-02](./CH-PRD-02-chat-page-shell-and-sidebar.md)
- Mounts from: [CH-PRD-03](./CH-PRD-03-session-categories.md), [CH-PRD-05](./CH-PRD-05-todo-lists-and-artifacts.md)
- ADK-session orphan scan (safety net for delete failures): [CH-PRD-05](./CH-PRD-05-todo-lists-and-artifacts.md)
- Rate-limit substrate: [BL-PRD-05](../../billing/projects/BL-PRD-05-failure-modes-permissions.md)
- Figma: `docs/figma-export/src/app/components/SessionSettings.tsx` (with scope deviations noted in §2)
- PyYAML `safe_dump`: https://pyyaml.org/wiki/PyYAMLDocumentation
- CLAUDE.md rules in scope: C-4, C-5, C-6, C-7; PY-1, PY-2, PY-3, PY-5; T-1, T-2, T-3, T-4, T-5; G-1, G-2, G-3
