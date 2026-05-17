# CH-PRD-03 — Session Categories

**Status:** Not started
**Owner team:** Chat component team (full-stack)
**Blocked by:** [CH-PRD-02](./CH-PRD-02-chat-page-shell-and-sidebar.md) (page shell + sidebar + filter dropdown stub)
**Parallel with:** CH-PRD-04, CH-PRD-05
**Blocks:** none
**Estimated effort:** 3 days full-stack

---

## 1. Context

Categories are user-defined labels the user applies to sessions to organize their history. Each user creates their own categories — not shared between users. Categories default to no category (Uncategorized); the user can create a category via a "+ New" button and assign any session to it via a dropdown. The same dropdown surfaces a trash icon per category for deletion; deleting a category silently re-assigns every session carrying that category back to Uncategorized.

Two dropdowns surface categories: the sidebar filter dropdown (CH-PRD-02 shipped the stub) narrows the sidebar to sessions in a chosen category, and the status-view assign dropdown (CH-PRD-04 ships the surface; CH-PRD-03 ships the dropdown component it consumes) assigns the currently-open session to a category. Both dropdowns share one component (`CategoriesDropdown.tsx`) with slot props for the two use-cases.

Landing categories lets users scale past a flat 30-day sidebar — the common case of "just show me my Q3 campaign sessions." The validation checkpoint is that a user can create, assign, and delete categories without the sidebar losing integrity, and the bulk-clear on delete never orphans a `category_id` FK.

## 2. Scope

### In scope

- **`users/{user_id}/chat_categories/{category_id}` collection** — shape registered in CH-PRD-01; CH-PRD-03 delivers the write-path + reads. One of five user-scoped subcollections in the codebase (alongside `users/{user_id}/notification_status/*` and `users/{user_id}/preferences/notifications` per `firestore_notification_repository.py`, and `users/{user_id}/notifications/settings` and `users/{user_id}/security/settings` per `routers/users.py`); registered with DM-PRD-05's `USER_SUBCOLLECTIONS` registry so the user-deletion sweep covers it. Convention documented in [`../README.md`](../README.md) §7.2.
- **`ChatCategoryDefinition` Pydantic shape** — fields per CH-PRD-01 §4.1 (`category_id`, `user_id`, `name`, `name_casefold`, `created_at`, `updated_at`). Name 1–64 chars; stripped; case-insensitive dedup via `name_casefold`.
- **`ChatCategoryService`** (`api/src/kene_api/chat/categories.py`) — `list_categories(user_id)`, `create_category(user_id, name)`, `delete_category(user_id, category_id)` (with transactional bulk-clear), `assign_category(session_id, category_id | None)`.
- **Four API endpoints:** `GET /categories`, `POST /categories`, `DELETE /categories/{id}`, `PUT /conversations/{id}/category`.
- **`CategoriesDropdown.tsx`** (shared) — shadcn `DropdownMenu` variant with inline "+ New" creation flow, trash-icon per category, "Uncategorized" option, section headers if needed. Two slot props: `variant="filter"` (selection mode; "All sessions" option first) vs `variant="assign"` (selection + inline assign on click). Used in CH-PRD-02's sidebar filter (replaces the temporary `Select`) and CH-PRD-04's status-view assign.
- **`useChatCategories.ts`** TanStack hook — list + create mutation + delete mutation + assign mutation. Invalidates `["chat-sessions", ...]` on any mutation so the sidebar reflects new counts + clearings.
- **Bulk-clear on delete** — Firestore transaction: (a) query sessions where `user_id==me AND category_id==deleted_id`, (b) clear `category_id` on each, (c) delete the category doc. Batched at 400 writes per transaction; iterates with an idempotency marker if > 400 sessions affected.
- **Search-text reconciliation on delete/assign** — when a session's `category_id` changes, its `search_text` must be recomputed (category name becomes part of `search_text` per CH-PRD-01). The PUT endpoint and delete bulk-clear both update `search_text` in the same write.
- **Sidebar count invalidation** — deleting a category removes the option from the filter dropdown within 1s; affected sessions reappear under "All sessions" with no `category_id`.
- **Status-view assign dropdown wiring** — the dropdown is delivered here but mounts inside CH-PRD-04's status view. CH-PRD-03 ships a placeholder mount point if CH-PRD-04 hasn't shipped (behind a flag); CH-PRD-04 replaces the placeholder.
- **Feature flag gating** — entire feature gated by `chat_categories_enabled`. When off, the filter dropdown in CH-PRD-02 renders "All sessions" only; the status-view dropdown is hidden.
- **Rate limits** — `POST /categories` 20/hour/user; `DELETE /categories/{id}` 20/hour/user; `PUT /conversations/{id}/category` 60/minute/session.
- **Weave spans** — `chat.category.created`, `chat.category.deleted`, `chat.category.assigned`, `chat.category.bulk_clear`.

### Out of scope

- Per-category color or icon customization — name-only in v1.
- Pre-defined / seeded categories — users start with an empty list (except "Uncategorized" which is implicit).
- Shared team categories — per-user only.
- Category reordering (drag-to-reorder) — alphabetical sort in v1.
- Nested / hierarchical categories — flat in v1.
- Migrating categories across user accounts — categories stay attached to the user id they were created under.
- Analytics "most used category" — deferred.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[CH-PRD-01](./CH-PRD-01-session-metadata-substrate.md)** | `ChatCategoryDefinition` shape; Firestore collection registered in DM-PRD-00 registry; composite index. | This PRD package |
| **[CH-PRD-02](./CH-PRD-02-chat-page-shell-and-sidebar.md)** | Sidebar filter dropdown stub replaced by `CategoriesDropdown.tsx`. `useChatSessions` query key includes `category_id` so mutations invalidate cleanly. | This PRD package |
| **[DM-PRD-05](../../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md)** | User-deletion sweep cleans `users/{user_id}/chat_categories/*` via the `USER_SUBCOLLECTIONS` registry (`recursive_delete(users/{user_id})` reaps the subcollection). CH-PRD-03 adds `chat_categories` to that registry, which also covers `notification_status`, `preferences`, `notifications`, and `security`. | `../../data-management/README.md` |
| **[FF-PRD-01](../../feature-flags/projects/FF-PRD-01-data-model-evaluation-api.md)**, **[FF-PRD-03](../../feature-flags/projects/FF-PRD-03-frontend-sdk-and-e2e.md)** | `chat_categories_enabled` flag — registered by CH-PRD-01, gated here. | `../../feature-flags/README.md` |
| **[BL-PRD-05](../../billing/projects/BL-PRD-05-failure-modes-permissions.md)** | **Soft.** Firestore-backed sliding-window rate-limit substrate for `POST /categories` (20/hour/user), `DELETE /categories/{id}` (20/hour/user), `PUT /conversations/{id}/category` (60/min/session). Fallback: in-process limiter while BL-PRD-05 is pending. | `../../billing/README.md` |
| Firestore transactions | `transaction.set/update/delete` for the atomic bulk-clear + delete path. | Firestore Python SDK |
| Existing `services/chatService.ts` / `lib/chatApi.ts` | Typed wrappers added here for the four endpoints. | `frontend/src/lib/chatApi.ts` |

## 4. Data contract

### 4.1 Pydantic + TypeScript shapes

```python
# api/src/kene_api/models/chat.py — already in CH-PRD-01
class ChatCategoryDefinition(BaseModel):
    category_id: str
    user_id: str
    name: str                 # 1..64 chars; stripped
    name_casefold: str           # derived: name.strip().lower()
    created_at: datetime
    updated_at: datetime

class CreateCategoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)

class AssignCategoryRequest(BaseModel):
    category_id: str | None   # None → set to Uncategorized
```

```typescript
// frontend/src/lib/chatApi.ts
export type ChatCategoryId = Brand<string, "ChatCategoryId">;

export interface ChatCategory {
  category_id: ChatCategoryId;
  name: string;
  created_at: string;
  updated_at: string;
}
```

### 4.2 Dedup invariant

`name_casefold = name.strip().casefold()` (Unicode-safe case folding — handles Turkish dotted-i, German ß, Greek sigma variants correctly). `POST /categories` with a name that collides on `name_casefold` with an existing user-owned category returns 409 with `{error: "category_exists", existing_category_id}`. Case-variants are treated as the same category.

### 4.3 Bulk-clear transaction shape

```python
async def delete_category(user_id: str, category_id: str) -> DeleteCategoryResult:
    # Phase 1: query all affected sessions
    affected = await firestore.collection_group("chat_sessions") \
        .where("user_id", "==", user_id) \
        .where("category_id", "==", category_id) \
        .get()

    # Phase 2: batched transactions of 400 at a time
    for batch in chunked(affected, size=400):
        async with firestore.transaction() as tx:
            for session_doc in batch:
                new_search_text = recompute_search_text(
                    session_doc, category_name=None,
                )
                tx.update(session_doc.reference, {
                    "category_id": None,
                    "search_text": new_search_text,
                    "updated_at": now_utc(),
                })
            # Delete the category doc in the LAST transaction only
            if batch is last:
                tx.delete(category_ref(user_id, category_id))

    return DeleteCategoryResult(
        category_id=category_id,
        sessions_reassigned=len(affected),
    )
```

**Idempotency:** the category doc is deleted in the last transaction. If the overall operation is retried (e.g. after a partial failure), (a) already-cleared sessions are no-ops, (b) the category doc delete either succeeds (idempotent) or the doc is already gone (no-op).

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create | `api/src/kene_api/chat/categories.py` — `ChatCategoryService` |
| Modify | `api/src/kene_api/routers/chat.py` — add 4 endpoints |
| Modify | `api/src/kene_api/chat/side_table.py` — expose `recompute_search_text(doc, category_name)` helper |
| Modify | `deployment/terraform/firestore.tf` — `chat_categories` composite index (already shipped in CH-PRD-01; verify) |
| Create | `frontend/src/components/chat/CategoriesDropdown.tsx` |
| Create | `frontend/src/hooks/useChatCategories.ts` |
| Modify | `frontend/src/lib/chatApi.ts` — 4 typed wrappers |
| Modify | `frontend/src/components/chat/SessionsSidebar.tsx` — swap the temporary `Select` for `CategoriesDropdown variant="filter"` |
| Create | `frontend/src/components/chat/__tests__/CategoriesDropdown.spec.tsx` |
| Create | `frontend/src/hooks/__tests__/useChatCategories.spec.ts` |
| Create | `api/tests/unit/chat/test_categories_service.py` |
| Create | `api/tests/unit/chat/test_categories_dedup.py` |
| Create | `api/tests/integration/chat/test_category_bulk_clear_transactional.py` |
| Create | `api/tests/integration/chat/test_category_user_isolation.py` |
| Create | `frontend/tests/e2e/chat-categories.spec.ts` |

### 5.2 `CategoriesDropdown` — layout detail

Port + generalize from `docs/figma-export/src/app/components/SessionSettings.tsx`'s inline category UI:

- **Trigger:** shadcn `DropdownMenuTrigger` with a `ChevronDown` icon. Shows current selection label (e.g. "Uncategorized", "Campaign Planning") or "All sessions" in filter variant.
- **Menu structure (top → bottom):**
  1. In `variant="filter"`: "All sessions" option (sentinel for `category_id=null` in the query).
  2. "Uncategorized" option (applies `category_id=null`).
  3. Separator.
  4. One row per user category: category name (left, click to select) + trash icon (right, click to delete). Rows sorted alphabetically by name.
  5. Separator.
  6. "+ New category" button opening an inline form.
- **Inline create form:** `Input` (placeholder "New category name…") + "Add" button + "X" close. Enter submits. On success: mutation fires, category is added to the menu, optionally auto-selected if `variant="assign"`. Duplicate-name error shows a toast with the existing category name.
- **Inline delete:** clicking the trash icon opens a confirm popover ("Delete 'X'? Sessions will return to Uncategorized."). On confirm: mutation fires, category disappears from the menu, sidebar re-queries.
- **Keyboard navigation:** up/down arrows navigate; Enter selects; "+" key on focus jumps to the create input.

### 5.3 Hook — `useChatCategories`

```typescript
export function useChatCategories() {
  const queryClient = useQueryClient();
  const { enabled } = useFeatureFlag("chat_categories_enabled");

  const list = useQuery({
    queryKey: ["chat-categories"],
    queryFn: listChatCategories,
    enabled,
    staleTime: 60_000,
  });

  const create = useMutation({
    mutationFn: createChatCategory,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat-categories"] }),
  });

  const remove = useMutation({
    mutationFn: deleteChatCategory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-categories"] });
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] }); // category_id cleared on many rows
    },
  });

  const assign = useMutation({
    mutationFn: assignSessionCategory,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat-sessions"] }),
  });

  return { list, create, remove, assign };
}
```

### 5.4 Backend — endpoints

```python
@router.get("/categories", response_model=list[ChatCategory])
async def list_categories(user: User = Depends(auth)):
    if not is_enabled("chat_categories_enabled"):
        raise HTTPException(404)
    return await category_service.list_categories(user.id)

@router.post("/categories", response_model=ChatCategory)
async def create_category(body: CreateCategoryRequest, user: User = Depends(auth)):
    if not is_enabled("chat_categories_enabled"):
        raise HTTPException(404)
    try:
        return await category_service.create_category(user.id, body.name)
    except CategoryExistsError as e:
        raise HTTPException(409, detail={"error": "category_exists", "existing_category_id": e.existing_id})

@router.delete("/categories/{category_id}")
async def delete_category(category_id: str, user: User = Depends(auth)):
    if not is_enabled("chat_categories_enabled"):
        raise HTTPException(404)
    result = await category_service.delete_category(user.id, category_id)
    return {"sessions_reassigned": result.sessions_reassigned}

@router.put("/conversations/{session_id}/category")
async def set_category(
    session_id: str,
    body: AssignCategoryRequest,
    user: User = Depends(auth),
):
    if not is_enabled("chat_categories_enabled"):
        raise HTTPException(404)
    # Validate ownership + category_id (if provided) exists for this user
    await category_service.assign_category(
        user_id=user.id, session_id=session_id, category_id=body.category_id,
    )
    return {"status": "ok"}
```

Ownership check: `assign_category` verifies `session.user_id == user.id` and (if `category_id` non-null) the category belongs to `user.id`. 403 otherwise.

## 6. API contract

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/chat/categories` | List the user's categories. 404 if flag off. |
| `POST` | `/api/v1/chat/categories` | Body `{name}`. 409 on dedup collision. Rate-limit 20/hour/user. |
| `DELETE` | `/api/v1/chat/categories/{category_id}` | Bulk-clears affected sessions; returns `{sessions_reassigned}`. Rate-limit 20/hour/user. |
| `PUT` | `/api/v1/chat/conversations/{session_id}/category` | Body `{category_id: str \| null}`. Recomputes `search_text`. Rate-limit 60/min/session. |

Auth: all require authenticated user. Ownership enforced server-side. Schemas in `api/src/kene_api/models/chat.py`; typed wrappers in `frontend/src/lib/chatApi.ts`.

## 7. Acceptance criteria

1. **Create** — `POST /categories` with name "Q3 Campaigns" creates a row at `users/{me}/chat_categories/{id}` with the expected shape; appears in `GET /categories`.
2. **Create dedup** — second `POST /categories` with "q3 campaigns" returns 409 + `existing_category_id`.
3. **Assign** — `PUT /conversations/{id}/category` with a valid `category_id` updates the session's `category_id` + `search_text`; sidebar row reflects on next poll.
4. **Unassign** — `PUT /conversations/{id}/category` with `category_id=null` clears; sidebar row shows no category label.
5. **Delete** — `DELETE /categories/{id}` removes the category AND clears `category_id` on every affected session; `sessions_reassigned` count matches. Transactional — partial-failure never orphans rows.
6. **Filter** — selecting a category in the sidebar filter dropdown narrows the sidebar to matching sessions; "All sessions" clears.
7. **Search + filter combo** — searching "Q3" within a selected category only matches sessions that are both in that category AND whose `search_text` contains "q3". Confirmed by integration test.
8. **Trash icon in filter dropdown** — clicking trash on a category deletes it, then the dropdown closes, then the sidebar repopulates without that category's sessions disappearing (they just lose their label).
9. **Trash icon in status-view dropdown** — same UX, same endpoint. CH-PRD-04 wires the mount.
10. **User isolation** — user A's categories are invisible to user B. Integration test with two users asserts 404 on cross-user read and no leakage via `list_categories`.
11. **Flag off** — with `chat_categories_enabled=false`: `GET /categories` 404; category filter hidden from sidebar; existing `category_id` values preserved in rows but not rendered.
12. **DM-PRD-05 sweep** — `delete_user_data(user_id)` cleans `users/{user_id}/chat_categories/*` via the `USER_SUBCOLLECTIONS` registry. Integration test seeds a user with 5 categories + 10 categorized sessions, runs the user-deletion endpoint, confirms categories are gone (sessions are also deleted as part of the same sweep since the user owned them).
13. **Bulk-clear at scale** — delete a category with 800 affected sessions → completes in 2 transactions; all sessions clear correctly; no orphans.
14. **Dropdown keyboard navigation** — arrow keys navigate options; Enter selects; accessible via screen-reader (aria-labels present).

## 8. Test plan

### Unit (backend)
- `ChatCategoryService.create_category` happy path — name stripped, `name_casefold` derived, dedup check.
- `ChatCategoryService.create_category` dedup collision — raises `CategoryExistsError`.
- `ChatCategoryService.delete_category` batching — 401 affected sessions → 2 transactions.
- `ChatCategoryService.assign_category` ownership — 403 when `session.user_id != user.id`; 403 when `category` belongs to another user.
- `recompute_search_text` — includes category name when `category_id` present; excludes when null.

### Unit (frontend)
- `CategoriesDropdown.spec.tsx` — renders variant="filter" with "All sessions"; variant="assign" without.
- Inline create form: submits on Enter; shows duplicate error; closes on cancel.
- Trash-icon flow: opens confirm; confirm fires mutation; dropdown refreshes.
- `useChatCategories` mutations invalidate the correct query keys.

### Integration
- Bulk-clear transactional integrity: seed 800 sessions under a category; DELETE; assert all clear + category gone.
- User isolation: user A creates "alpha"; user B's `list_categories` does not include it; user B `PUT /conversations/{id}/category = alpha_id` returns 403.
- Flag off: `GET /categories` returns 404; sidebar renders without category filter.
- DM-PRD-05 cleanup: user deletion sweep removes the collection.

### E2E (Playwright)
- Create, assign to a session, filter sidebar, delete, see session return under "All sessions" with no label.
- Delete a category while the status view is open on a session carrying that category — status view refreshes with `category_id=null`.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Concurrent delete + assign on the same category → lost write | Transactional delete reads the session list inside the transaction (no external query); if a concurrent PUT inserts a new assignment, the transaction reads it and clears it in the same commit. Last-writer-wins semantics acceptable. |
| Delete on a category with >10k affected sessions → runtime cost | Batching at 400/tx keeps individual transactions bounded; total elapsed time = ceil(N/400) × tx-duration. For 10k sessions that's 25 transactions ≈ 30 seconds. Documented as acceptable for v1; v2 could move to a background job. |
| Trash-icon accidental click | Confirm popover required. Tested via E2E. |
| Search text drifts after a rename (future feature) | Rename is out of scope in v1; if added, the rename endpoint must also update `search_text` on every affected session (same pattern as delete's bulk-clear). Documented. |
| Filter dropdown gets long on users with 50+ categories | Scroll within the dropdown; no truncation. If UX gets unwieldy, add grouping (deferred). |
| User renames a category (future) and two old categories collide on `name_casefold` | Rename is out of scope in v1. Future rename endpoint does the same dedup check. |

### Open questions
- **Q:** Should deleting a category require confirming in the status-view dropdown AND again in the confirm popover, or just one confirm? → **Proposal:** one confirm popover only, consistent with both dropdowns.
- **Q:** Does "assign to Uncategorized" show as a selectable option in the dropdown, or is it the implicit "none selected" state? → **Proposal:** explicit "Uncategorized" option; simpler mental model.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Component README: [`../README.md`](../README.md)
- Upstream: [CH-PRD-01](./CH-PRD-01-session-metadata-substrate.md), [CH-PRD-02](./CH-PRD-02-chat-page-shell-and-sidebar.md)
- Downstream: none (sibling [CH-PRD-04](./CH-PRD-04-session-status-view.md) mounts the assign variant of this dropdown)
- Integration: [DM-PRD-05](../../data-management/projects/DM-PRD-05-deletion-sweep-rewrite.md) (user-deletion sweep)
- Figma: `docs/figma-export/src/app/components/SessionSettings.tsx` — inline category UI on the status view
- CLAUDE.md rules in scope: C-5 (branded types); T-1, T-2, T-3; G-2, G-3
