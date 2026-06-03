# CH-PRD-02 — Chat Page Shell & Sidebar

**Status:** Not started
**Owner team:** Chat component team (frontend + thin backend)
**Blocked by:** [CH-PRD-01](./CH-PRD-01-session-metadata-substrate.md) (side-table + callbacks + pagination backend), [UI-PRD-01](../../ui/README.md) (design system foundation, `LayoutC`, shell components), [FF-PRD-03](../../feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md) (frontend feature-flag SDK)
**Parallel with:** none — the shell is the container for CH-PRD-03/04/05
**Blocks:** CH-PRD-03, CH-PRD-04, CH-PRD-05
**Estimated effort:** 5 days frontend + 1 day thin backend

---

## 1. Context

The Chat page is the user's primary surface for talking to KEN-E. Today, `frontend/src/` has a typed chat API client (`services/chatService.ts`) but no chat page, no sidebar, no message list, no session-switching UI. CH-PRD-02 delivers the full page and sidebar on top of CH-PRD-01's substrate.

Three things ship here: the `/chat` route with its page shell (toggle between message view and session-status view in CH-PRD-04); the collapsible left sidebar with session list + search + category filter + status dots + infinite scroll; and the wiring that keeps the sidebar honest via 5–10s polling + `mark-read` on message visibility. Session-status view contents (name, summary, tokens, etc.) arrive in CH-PRD-04 — this PRD just delivers the toggle button as a placeholder destination. Categories arrive in CH-PRD-03 — the filter dropdown in this PRD reads categories via `GET /api/v1/chat/categories` if `chat_categories_enabled=true`, otherwise it renders "All sessions" only.

Landing the shell first means CH-PRD-03/04/05 each ship in-place under the `/chat` route. The validation checkpoint is a user can open `/chat`, see their 30-day session history in the sidebar sorted by recency, search by name/category/summary substring, scroll to load more, and switch between sessions without page reloads.

## 2. Scope

### In scope

- **`/chat` route** — registered in the frontend router behind the `chat_v2_enabled` flag. Falls back to a 404 or a "coming soon" placeholder when off.
- **`frontend/src/pages/Chat.tsx`** — top-level page component. Owns `?session=<id>` URL query, sidebar collapse state (persisted to localStorage), view state (message vs status-view). Renders inside UI-PRD-01's `LayoutC`.
- **`frontend/src/components/chat/SessionsSidebar.tsx`** — production port of `docs/figma-export/src/app/components/SessionsSidebar.tsx`. 384px expanded / 64px collapsed. Header: "Sessions" title + active/review counts + "New Session" button + collapse toggle. Search input + category-filter dropdown. Scrollable session list with infinite-scroll sentinel. Collapsed state: 10 stacked icon-only status dots + "+ New" button.
- **`frontend/src/components/chat/ChatInterface.tsx`** — production port of `docs/figma-export/src/app/components/ChatInterface.tsx`. Message list, composer, artifact inline blocks, thinking blocks, text-size preference (from UI-PRD-01). Subscribes to `/completions` SSE stream. Fires `POST /mark-read` via IntersectionObserver on the latest agent message.
- **`frontend/src/components/chat/SessionStatusDot.tsx`** — pure-function component. Takes `(is_agent_running, last_agent_message_at, last_viewed_at) → "active" | "needs-review" | "idle"`. Renders the dot with the correct color + glow; tooltip reads "Agent working", "Unread reply", or no tooltip.
- **`frontend/src/hooks/useChatSessions.ts`** — TanStack `useInfiniteQuery` hook. Polls every 5000ms when `document.visibilityState === "visible"`; pauses when hidden. Query key: `["chat-sessions", account_id, category_id, query]`. Invalidates on message send, on `mark-read`, on visibility change.
- **`frontend/src/lib/chatApi.ts`** — typed API wrappers for every extended / new endpoint this PRD touches. The existing `services/chatService.ts` continues to work; it internally delegates to `lib/chatApi.ts` (migration owned by CH-PRD-02; cleanup in a follow-up).
- **`POST /api/v1/chat/conversations/{id}/mark-read`** endpoint — stamps `last_viewed_at = now()` on the side-table. Idempotent; 5-second dedup to collapse rapid fires. Rate-limited 60/minute/session (via Billing's BL-PRD-05 substrate when available; minimal in-process fallback otherwise).
- **`GET /api/v1/chat/conversations` full wiring** — CH-PRD-01 shipped the signature; CH-PRD-02 wires the server logic behind it (cursor pagination via Firestore `start_after`; 30-day window; category filter; case-insensitive `query` substring against `search_text`).
- **"New Session" flow** — clicks `POST /api/v1/chat/conversations` (existing); optimistic row in the sidebar with a placeholder title ("Untitled session") until the real row lands; navigates to `/chat?session=<id>` once created.
- **Recovery integration** — when the user opens `/chat` with no `?session=`, a lightweight intro lands (empty composer, "Start a new session…" hint). The existing `GET /sessions/recoverable` surface is retained; a small affordance in the sidebar header lets the user re-open a recoverable session not in the main list (rare, since the 30-day window covers the vast majority).
- **Telemetry** — Weave spans `chat.page.render`, `chat.sidebar.poll`, `chat.sidebar.search`, `chat.sidebar.infinite_scroll`, `chat.mark_read`. Page-view event on route mount.
- **Feature flag gating** — entire page + endpoints gated by `chat_v2_enabled`. Category filter additionally gated by `chat_categories_enabled` (dropdown hidden when off).

### Out of scope

- Session status view contents (name edit, summary, tokens panel, etc.) — CH-PRD-04. This PRD ships only the toggle button + an empty placeholder panel.
- Category CRUD (create / delete / trash icons) — CH-PRD-03. This PRD reads categories for the filter dropdown; it does not mutate them.
- Todo list renderer + artifacts panel — CH-PRD-05.
- Compact-now, delete, export buttons — CH-PRD-04.
- User-upload of artifacts — latent per [`../implementation-plan.md`](../implementation-plan.md) §10 Q2.
- Sidebar right-click / quick-action menu — deferred per [`../implementation-plan.md`](../implementation-plan.md) §7.
- Real-time push (SSE / websocket) for sidebar — polling in v1.
- Mobile responsive layout — desktop-first v1; mobile is a follow-up.
- Session pinning — deferred.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[CH-PRD-01](./CH-PRD-01-session-metadata-substrate.md)** | Side-table + callbacks + `GET /conversations` signature + composite indexes. Without this, sidebar has no data to render. | This PRD package |
| **[UI-PRD-01](../../ui/README.md)** | `LayoutC`, `Sidebar` (primary), `TopNav`, `AccountSwitcher`, `BackgroundEffects`, Tailwind tokens, shadcn primitives (`Button`, `Input`, `Select`, `ScrollArea`, `Tooltip`). Text-size preference infrastructure. | `../../ui/README.md` |
| **[FF-PRD-03](../../feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md)** | `useFeatureFlag("chat_v2_enabled")`, `useFeatureFlag("chat_categories_enabled")` hooks. | `../../feature-flags/README.md` |
| **[UI-PRD-02](../../ui/projects/UI-PRD-02-core-shell-pages.md)** (coordination only) | UI-PRD-02 owns the `/` → `/chat` redirect and legacy `Home.tsx` deletion. CH-PRD-02 owns the `/chat` destination. Both PRDs land in Release 1 — coordinate `App.tsx` route registration. The historical scope adjustment (`/chat` page absorption) is complete in UI-PRD-02 and the PROJECT-PLANNER. | [`../../ui/projects/UI-PRD-02-core-shell-pages.md`](../../ui/projects/UI-PRD-02-core-shell-pages.md) |
| Existing `/api/v1/chat/*` surface | The 9 existing endpoints + CH-PRD-01's extensions. | `api/src/kene_api/routers/chat.py` |
| `docs/figma-export/src/app/components/*` | Design contract for every component ported. | `docs/figma-export/` |
| Existing `frontend/src/services/chatService.ts` | Internally delegated to new `lib/chatApi.ts` during the CH-PRD-02 PR; **a follow-up PR (tracked in the CH-PRD-02 exit checklist) deletes `chatService.ts` entirely once callers are migrated.** No indefinite shim. | `frontend/src/services/chatService.ts` |
| **[BL-PRD-05](../../billing/projects/BL-PRD-05-failure-modes-permissions.md)** | **Soft.** Firestore-backed sliding-window rate-limit substrate for `POST /mark-read` (60/min/session). Fallback: in-process limiter while BL-PRD-05 is pending. | `../../billing/README.md` |
| Firestore cursor pagination | `start_after(DocumentSnapshot)`; opaque base64-encoded cursor in API response. | Firestore Python SDK |

## 4. Data contract

### 4.1 Request / response shapes

```typescript
// frontend/src/lib/chatApi.ts — additions / extensions

type ChatSessionId = Brand<string, "ChatSessionId">;
type ChatCategoryId = Brand<string, "ChatCategoryId">;

export interface ChatSessionSidebarItem {
  session_id: ChatSessionId;
  title: string | null;             // null → render "Untitled session"
  category_id: ChatCategoryId | null;
  category_name: string | null;     // denormalized for render; null when no category
  last_message_preview: string | null;
  updated_at: string;               // ISO 8601
  created_at: string;
  is_agent_running: boolean;
  last_agent_message_at: string | null;
  last_viewed_at: string | null;
}

export interface ListChatSessionsRequest {
  cursor?: string | null;
  category_id?: ChatCategoryId;
  query?: string;
  limit?: number;                   // default 20, max 100
}

export interface ListChatSessionsResponse {
  items: ChatSessionSidebarItem[];
  next_cursor: string | null;
}

export interface MarkReadRequest {
  session_id: ChatSessionId;
}
```

### 4.2 Status-dot derivation

```typescript
export function deriveSessionStatus(
  item: Pick<ChatSessionSidebarItem, "is_agent_running" | "last_agent_message_at" | "last_viewed_at">
): "active" | "needs-review" | "idle" {
  if (item.is_agent_running) return "active";
  if (
    item.last_agent_message_at &&
    (!item.last_viewed_at || item.last_agent_message_at > item.last_viewed_at)
  ) return "needs-review";
  return "idle";
}
```

One function, one test file. Every renderer calls this — no ad-hoc logic elsewhere.

### 4.3 Sidebar query-key shape (TanStack)

```typescript
// frontend/src/hooks/useChatSessions.ts
const queryKey = ["chat-sessions", accountId, categoryId ?? "all", query ?? ""] as const;

useInfiniteQuery({
  queryKey,
  queryFn: ({ pageParam }) => listChatSessions({ cursor: pageParam, category_id: categoryId, query }),
  initialPageParam: null,
  getNextPageParam: (last) => last.next_cursor,
  refetchInterval: () => (document.visibilityState === "visible" ? 5000 : false),
  refetchOnWindowFocus: true,
});
```

Cursor is opaque to the client — never parsed.

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create | `frontend/src/pages/Chat.tsx` |
| Create | `frontend/src/components/chat/SessionsSidebar.tsx` |
| Create | `frontend/src/components/chat/ChatInterface.tsx` |
| Create | `frontend/src/components/chat/SessionStatusDot.tsx` |
| Create | `frontend/src/components/chat/ThinkingBlock.tsx` (port) |
| Create | `frontend/src/components/chat/ArtifactBlock.tsx` (port of inline artifact renderer from `ChatInterface`) |
| Create | `frontend/src/hooks/useChatSessions.ts` |
| Create | `frontend/src/hooks/useMarkRead.ts` |
| Create | `frontend/src/lib/chatApi.ts` — typed wrappers (extends existing `chatService.ts`) |
| Modify | `frontend/src/services/chatService.ts` — delegate internally to `lib/chatApi.ts`; preserve external API |
| Modify | `frontend/src/App.tsx` (or equivalent router) — register `/chat` route behind `chat_v2_enabled` |
| Modify | `api/src/kene_api/routers/chat.py` — `GET /conversations` full implementation (cursor + filters); `POST /conversations/{id}/mark-read` endpoint |
| Modify | `api/src/kene_api/chat/search.py` — `list_sessions` method body (CH-PRD-01 shipped signature) |
| Create | `frontend/src/components/chat/__tests__/SessionsSidebar.spec.tsx` |
| Create | `frontend/src/components/chat/__tests__/SessionStatusDot.spec.tsx` |
| Create | `frontend/src/components/chat/__tests__/ChatInterface.spec.tsx` |
| Create | `frontend/src/hooks/__tests__/useChatSessions.spec.ts` |
| Create | `api/tests/unit/chat/test_list_sessions_pagination.py` |
| Create | `api/tests/unit/chat/test_mark_read.py` |
| Create | `api/tests/integration/chat/test_list_sessions_category_filter.py` |
| Create | `api/tests/integration/chat/test_30_day_window_respected.py` |
| Create | `frontend/tests/e2e/chat-sidebar.spec.ts` (Playwright) |

### 5.2 Sidebar layout — specifics

Port from `docs/figma-export/src/app/components/SessionsSidebar.tsx`:

- **Expanded (384px):** header block (title + count line + "New Session" button + collapse chevron), then search input (with Search icon), then category filter (`Select` with Filter icon; first option "All sessions"; subsequent options populated from `GET /categories`), then `ScrollArea` containing session items.
- **Session item layout (3-line):** status dot (left) + name (truncated, bold) + category label (smaller, tertiary) + last-message preview (smaller, tertiary, single-line truncate). Active variant: violet-300 border + accent background. Hover: accent background + violet-300 border (same as active but without active lock).
- **Infinite scroll sentinel:** a hidden `<div ref={loadMoreRef} />` inside `ScrollArea` at the bottom; IntersectionObserver triggers `fetchNextPage()` when intersecting. Rate-limit sentinel fires to 1/sec.
- **Collapsed (64px):** vertical stack of icon-only buttons. First: "+ New session" with Plus icon. Then: first 10 sessions with their status dots as clickable circles (tooltip on hover shows title). "Show more" chevron at bottom re-expands the sidebar.
- **Active / needs-review counts in header:** derived client-side from the first page of results. `activeCount = items.filter(deriveStatus == "active").length`; `needsReviewCount = items.filter(deriveStatus == "needs-review").length`. Updates every poll.

### 5.3 Message view integration (ChatInterface)

Port from `docs/figma-export/src/app/components/ChatInterface.tsx`:

- **Message list:** renders user + assistant messages with avatars + timestamps + reasoning blocks + artifact blocks.
- **Composer:** Textarea + Send button + placeholder text; Enter sends, Shift+Enter newlines; disabled when `useOrgStatus() inactive_*` (reads Billing state).
- **SSE stream:** subscribes to `POST /chat/completions` with `stream=true`; appends events to the message list; shows thinking block when an assistant message is in-flight; stop button cancels.
- **Artifact inline blocks:** render a card for each artifact referenced by the assistant message; clicking opens the artifact (CH-PRD-05 owns the full viewer; v1 can be a no-op click).
- **`mark-read` trigger:** `useMarkRead` hook wraps an IntersectionObserver on the last assistant message's DOM node. When intersecting for >500ms, `POST /mark-read` fires. Client-side dedup: don't fire again within 5s for the same session.

### 5.4 Backend — list endpoint logic

```python
# api/src/kene_api/chat/search.py
async def list_sessions(
    user_id: str,
    account_id: str,
    cursor: str | None = None,
    category_id: str | None = None,
    query: str | None = None,
    limit: int = 20,
) -> tuple[list[ChatSessionSidebarItem], str | None]:
    limit = min(max(limit, 1), 100)
    cutoff = now_utc() - timedelta(days=CHAT_LIST_WINDOW_DAYS)

    q = (
        firestore_client
        .collection_group("chat_sessions")
        .where("user_id", "==", user_id)
        .where("deleted_at", "==", None)          # exclude tombstones
        .where("updated_at", ">=", cutoff)
        .order_by("updated_at", direction="DESCENDING")
    )
    if category_id is not None:
        q = q.where("category_id", "==", category_id)
    if cursor:
        last_snap = decode_cursor(cursor)
        q = q.start_after(last_snap)
    q = q.limit(limit + 1)   # peek one ahead to know if there's a next page

    docs = await q.get()
    has_more = len(docs) > limit
    docs = docs[:limit]

    items = [ChatSessionSidebarItem.from_doc(d) for d in docs]
    # Account-scoping hardening: assert every returned row's account_id matches
    items = [i for i in items if i.account_id == account_id]

    # Server-side substring filter (post-Firestore) for query
    # Rationale: Firestore has no substring index; search_text denormalization + client-affinity
    # keeps results fast while the result set stays small.
    # Note: search_text is stored casefold()-normalized (per CH-PRD-01) so Unicode case-insensitivity
    # works correctly across Turkish/German/Greek/etc. input.
    if query:
        q_casefold = query.casefold()
        items = [i for i in items if q_casefold in i.search_text]

    next_cursor = encode_cursor(docs[-1]) if has_more else None
    return items, next_cursor
```

**Important:** `query` filtering happens **after** the page fetch (post-Firestore), which means a page may return fewer items than `limit` when the query filters most out. The client handles this by continuing to paginate until it has enough items or `next_cursor` is null. For v1 this is acceptable (typical user has <100 matching sessions); a Firestore-side substring search would require an Algolia-like index, deferred.

### 5.5 Mark-read endpoint

```python
@router.post("/conversations/{session_id}/mark-read")
async def mark_read(session_id: str, user: User = Depends(auth)):
    # dedup: if last_viewed_at within 5s, no-op
    meta = await side_table.get(session_id)
    if meta is None or meta.user_id != user.id:
        raise HTTPException(404)
    if meta.last_viewed_at and (now_utc() - meta.last_viewed_at) < timedelta(seconds=5):
        return {"last_viewed_at": meta.last_viewed_at}
    await side_table.update_from_event(session_id, {"last_viewed_at": now_utc()})
    return {"last_viewed_at": now_utc()}
```

Idempotent; returns `{last_viewed_at}` so the client can optimistically set local state.

### 5.6 Route registration

```typescript
// frontend/src/App.tsx
const { enabled: chatEnabled } = useFeatureFlag("chat_v2_enabled");
// ...
{chatEnabled && <Route path="/chat" element={<ChatPage />} />}
```

Off → the route doesn't exist → 404 falls through.

## 6. API contract

### Extended

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/chat/conversations?cursor=&category_id=&query=&limit=` | Full implementation of the signature CH-PRD-01 defined. Cursor pagination; 30-day window; category filter; server-side query substring against `search_text`. Default `limit=20`, max 100. |

### New

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/chat/conversations/{session_id}/mark-read` | Stamps `last_viewed_at = now()`. 5s dedup; rate-limit 60/min/session. Returns `{last_viewed_at}`. |

Auth: both endpoints require authenticated user + session ownership (`session.user_id == auth.user_id`). 404 on mismatch (never leaks existence).

## 7. Acceptance criteria

1. **`/chat` route renders** inside `LayoutC`; gated by `chat_v2_enabled`. Route mount emits `chat.page.render` Weave span.
2. **Sidebar expanded state** shows sessions sorted by `updated_at DESC`, paginated at 20/page, supports infinite scroll via IntersectionObserver sentinel; next page loads within 300ms p95 on warm cache.
3. **Sidebar collapsed state** renders 10 status dots + "+ New" with correct active / needs-review coloring and tooltips.
4. **Search** — typing "q3" in the search input filters the sidebar to sessions whose name, assigned category name, or cached summary contains "q3" (case-insensitive). Debounced 300ms before firing.
5. **Category filter** — select a category → sidebar narrows to that category's sessions. "All sessions" clears the filter. If `chat_categories_enabled=false`, the dropdown is hidden.
6. **Status dots** — `SessionStatusDot.spec.tsx` covers all 8 combinations of `(is_agent_running, last_agent_message_at ? | null, last_viewed_at ? | null)` → correct state.
7. **Mark-read** — sending a message in session A, then switching to session B without reading the reply, keeps session A's dot coral (needs-review). Returning to A and scrolling the latest message into view flips it idle within 3s.
8. **New session** — clicking "New Session" creates the session via `POST /conversations`, optimistically inserts a row, navigates to `/chat?session=<id>`; real row replaces optimistic within 1s.
9. **Polling** — sidebar polls every 10s while tab visible; pauses on `visibilitychange` hidden; resumes on visible within 200ms. (The interval is 10s per the §9 risk-table response to server p95 > 500ms; the original cadence was 5s.)
10. **30-day window** — a session with `updated_at = now() - 31d` does not appear in default sidebar; accessible via direct URL (`/chat?session=<id>`).
11. **Deleted sessions excluded** — tombstoned rows (`deleted_at` set) never appear in the sidebar even if recent.
12. **Porting parity** — `SessionsSidebar.tsx`, `ChatInterface.tsx` render pixel-parity with figma (spot-checked via visual regression test against screenshots).
13. **Text-size preference** honored by `ChatInterface` (from UI-PRD-01).
14. **`useOrgStatus() inactive_*`** disables the composer with the banner copy (Billing integration; no new API).
15. **`services/chatService.ts` migration** — internally delegates to `lib/chatApi.ts` in the CH-PRD-02 PR; a **follow-up PR (tracked on the CH-PRD-02 exit checklist)** deletes `chatService.ts` entirely once all callers are migrated. No indefinite shim.
16. **Load-test gate** — sidebar-list endpoint sustains 1000 concurrent polls (simulating 1000 open tabs × 10 polls/minute) with p95 response time under 100ms. Run via Locust as part of CH-PRD-02's acceptance; failure gates merge.

    > **⚠️ KNOWN-OPEN GAP (tracked in CH-65).** This AC's literal target (1000 polls, p95 < 100ms) has never been met. The staging CI gate was loosened to p90 ≤ 15 000 ms (PR #584 → #592) before any run passed at 100ms, and silently switched from the legacy ADK path to the v2 side-table path when `chat_v2_enabled` went GA — so it no longer tests this threshold on the live path. As of 2026-06-02 the v2 path measures p95 ≈ 20 s under 1000-VU load. The in-process response cache + async read path (CH-53) close the application-side cost; the Cloud Run `min-instances` bump that closes the cold-scale tail is deferred on CH-65 with re-open tripwires. Closing AC #16 = those two + tightening the gate back toward 100ms p95 and confirming it holds on the v2 path.

## 8. Test plan

### Unit (frontend)
- `SessionStatusDot.spec.tsx`: all 8 state combinations.
- `deriveSessionStatus` pure function: table-driven tests.
- `useChatSessions` polling: document-visibility toggles refetch; query-key change invalidates cache.
- `useMarkRead` IntersectionObserver trigger + 5s dedup.
- `SessionsSidebar.spec.tsx`: expanded/collapsed render; search input change invalidates query; category filter change invalidates query; infinite-scroll sentinel fires `fetchNextPage`.
- `ChatInterface.spec.tsx`: SSE stream append; thinking-block visibility; composer-disabled on `inactive_*`; mark-read fires on visibility.

### Unit (backend)
- `list_sessions` pagination — 50-row fixture paginates in 3 pages of 20 + 10 + null cursor.
- `list_sessions` category filter — filter by `category_id` returns only matching rows.
- `list_sessions` query — substring match on `search_text` (lowercase).
- `list_sessions` 30-day cutoff — row at 31d excluded; row at 29d included.
- `list_sessions` deleted exclusion — tombstoned row excluded.
- `mark_read` — updates `last_viewed_at`; 5s dedup returns same timestamp.
- `mark_read` 404 on session the user does not own.

### Integration
- E2E (Playwright): open `/chat`, sidebar loads within 1s, open a session, send a message, watch sidebar dot transition active → needs-review → idle as expected.
- Cross-tab: open 2 tabs of `/chat` — sending a message in tab 1 updates the sidebar in tab 2 within 10s (polling interval).
- 1000-session seed: infinite scroll paginates through without duplicates; memory stays under 50 MB in DevTools.

### Visual regression
- `SessionsSidebar` expanded: figma screenshot comparison.
- `SessionsSidebar` collapsed: figma screenshot comparison.
- `ChatInterface` message variants (user / assistant with artifacts / assistant with reasoning): figma screenshot comparison.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| 5s polling hammers the server at scale | Polls pause when tab hidden; default `limit=20`; 30-day window caps result set. Monitor p95 sidebar fetch latency + raise polling interval to 10s if server p95 > 500ms. |
| `useChatSessions` cache invalidation misses in a race (send-and-switch) | Invalidate query on `mark-read` response + on `/completions` success; optimistic `updated_at=now()` on send. |
| Server-side substring filter returns <limit items per page | Client keeps calling `fetchNextPage` until it has enough to display OR `next_cursor` is null. Documented in `useChatSessions` hook comments. |
| IntersectionObserver double-fires on fast scroll | Rate-limit sentinel fires to 1/sec in the hook; idempotent backend pagination makes duplicate fetch safe. |
| Composer disabled-state logic diverges from Billing's banner | Both read `useOrgStatus`; shared. CH-PRD-02 does not duplicate the logic — imports the same hook. |
| Figma port deviates in subtle ways (spacing, hover) | Visual regression tests + design review gate on PR. |
| Ported `ChatInterface` breaks existing `/completions` behavior | Preserve existing `services/chatService.ts` external contract; new `lib/chatApi.ts` layered underneath; both tested. |
| "New Session" optimistic row persists as ghost if create fails | On create error, remove the optimistic row + show a toast. |

### Open questions
- **Q:** Should sidebar row click open the session AND mark it read, or only open it (and wait for the user's IntersectionObserver to fire mark-read)? → **Proposal:** only open; IntersectionObserver handles mark-read once the latest message is visible. Simpler logic, consistent with "the user has actually seen the reply" semantics.
- **Q:** Should the search input debounce be 300ms or 500ms? → **Proposal:** 300ms; low enough to feel snappy, high enough to avoid thrashing.
- **Q:** When the user switches accounts (via TopNav), should the sidebar instantly clear or animate? → **Proposal:** instant clear — clean mental model, consistent with how other pages behave on account switch.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Component README: [`../README.md`](../README.md)
- Upstream: [CH-PRD-01](./CH-PRD-01-session-metadata-substrate.md), [UI-PRD-01](../../ui/README.md), [FF-PRD-03](../../feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md)
- Downstream: [CH-PRD-03](./CH-PRD-03-session-categories.md), [CH-PRD-04](./CH-PRD-04-session-status-view.md), [CH-PRD-05](./CH-PRD-05-todo-lists-and-artifacts.md)
- Figma: `docs/figma-export/src/app/components/SessionsSidebar.tsx`, `ChatInterface.tsx`, `ChatPage.tsx`
- Existing code: `frontend/src/services/chatService.ts`, `api/src/kene_api/routers/chat.py`
- CLAUDE.md rules in scope: C-5 (branded types), C-6 (`import type`), C-8 (type over interface); T-1, T-2, T-5; G-2, G-3
