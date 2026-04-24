# CH-PRD-05 — Todo Lists & Artifacts

**Status:** Not started
**Owner team:** Chat component team (full-stack + ADK)
**Blocked by:** [CH-PRD-02](./CH-PRD-02-chat-page-shell-and-sidebar.md) (page shell mount point)
**Parallel with:** CH-PRD-03, CH-PRD-04
**Blocks:** none
**Estimated effort:** 4 days full-stack + ADK

---

## 1. Context

Two in-session surfaces ship together because they share two design patterns: (a) both are agent-authored and read-only to the user, and (b) both require a lightweight API wrapper that every tool must use so the UI sees the results.

**Todo lists** let an agent track multi-step work that spans user turns. In a single session the agent may create several lists (e.g., "Research phase", "Asset collection", "Q3 Calendar build"). Each list has a title, an `is_current` flag, and a set of items with `completed` bools. Lists live in `session.state["todo_lists"]` as a dict keyed by `list_id`. Two new ADK tools — `set_todo_list` and `update_todo_list` — let agents manipulate the state; the UI reads it via a thin endpoint.

**Artifacts** are documents created during a session. ADK's `GcsArtifactService` already stores blobs, but it surfaces no `created_at` or `tool_name` metadata. To fix that, every agent tool that creates an artifact calls `chat.artifacts.register_artifact(...)` — a two-line wrapper that saves the ADK blob AND writes a Firestore metadata row capturing provenance (`created_by_tool=<tool_name>`, `created_at=now()`, etc.). A CI lint rule blocks raw `context.save_artifact(...)` calls outside the wrapper so artifacts never fall off the UI.

**Two reconciliation jobs** also land here — one for GCS blobs that have no metadata row (orphan blobs from raw-save bypasses), and one for **ADK sessions whose side-table is tombstoned or missing**. The latter is the safety net that catches CH-PRD-04's delete-cleanup task failures.

Landing these together closes the two figma status-view surfaces that CH-PRD-04 reserved. The validation checkpoint is that an agent that creates a todo list or saves an artifact sees both surface in the UI within one polling interval, with correct provenance.

**Creator-type latency.** The v1 data model supports only agent-created artifacts (`created_by_tool` populated). The `ChatArtifactIndex` shape has no separate `creator` field. When a future user-upload UI ships, `created_by_tool = None` is the implicit signal for user-uploaded; no schema migration needed.

## 2. Scope

### In scope

- **`session.state["todo_lists"]` convention** — dict-of-dicts keyed by `list_id`. Each value matches the `TodoList` Pydantic shape (CH-PRD-01). Max 20 lists per session, max 50 items per list (enforced by the tool helpers). Documented in `docs/KEN-E-System-Architecture.md` §3.6.
- **Two ADK tools** — `set_todo_list(list_id, title, items, is_current=False)` creates/replaces a list; `update_todo_list(list_id, item_id, completed)` flips a single checkbox (optional `text` to rename an item). Registered in the Agent Factory (AH-PRD-02) or hardcoded root if not shipped.
- **`chat/todos.py`** — `list_todo_lists(session_id)` reads `session.state["todo_lists"]` via `VertexAiSessionService.get_session`; server-side Pydantic validation drops malformed entries.
- **`GET /api/v1/chat/conversations/{id}/todos`** — returns `list[TodoList]` ordered by `is_current=True` first then `created_at DESC`.
- **`chat/artifacts.py`** — `register_artifact(tool_context, filename, content, created_by_tool) → ChatArtifactIndex` wrapping `context.save_artifact(...)` + writing `ChatArtifactIndex` row to `accounts/{account_id}/chat_sessions/{session_id}/artifacts/{artifact_id}`. Deterministic `artifact_id = sha256(session_id|filename|version)[:32]`. **No `creator` parameter in v1.** When future user-upload UI ships, `created_by_tool=None` signals a user upload.
- **`list_artifacts(session_id)`** — reads the Firestore subcollection; signed GCS URLs generated on-demand in the endpoint (10-min TTL for in-app listing; CH-PRD-04's export uses 24-hour TTL separately).
- **`GET /api/v1/chat/conversations/{id}/artifacts`** — returns `list[ChatArtifactIndex]` + per-row signed URL.
- **Lint rule** `api/scripts/lint/check_artifact_register.py` — grep-based CI check. Any file outside `api/src/kene_api/chat/artifacts.py` that contains `context.save_artifact(` or `.save_artifact(` with `artifact_service` in scope fails the build. Documented escape hatch via allow-list; initial allow-list is empty except the wrapper itself.
- **Migration of existing callsite** — `app/adk/agents/strategy_agent/artifact_utils.py` is modified to call the wrapper. Existing uploaded-strategy prefix + naming is preserved.
- **`TodoListsPanel.tsx`** — read-only renderer. Mounts in CH-PRD-04's status view. Caption: "Tracks long tasks to ensure details are preserved during compaction." Collapsible per list; disabled checkboxes; line-through + muted color for completed items; "Current / Previous" distinction via `is_current` flag.
- **`ArtifactsPanel.tsx`** — read-only renderer. File-type icons (PDF, spreadsheet, image, code, text, generic); filename + file size; **all artifacts render with a "KEN-E" badge showing the `created_by_tool` name on hover** (v1 has no user-upload path). Click → open signed URL in new tab. Mounts in CH-PRD-04's status view.
- **Tool convention docs** — add a short section to `app/CLAUDE.md`: "Agent tools that save an artifact MUST call `chat.artifacts.register_artifact` — see `api/src/kene_api/chat/artifacts.py`."
- **GCS orphan-blob reconciliation job** (daily, pager-alert on drift >0) — query GCS for blobs matching `gs://artifacts-bucket/{app_name}/*/*/*/*` that have no matching `ChatArtifactIndex` row → alert ops. Report-only; recovery is manual.
- **ADK-session orphan reconciliation job** (daily) — the safety net for CH-PRD-04's delete-cleanup task. Compares `list_sessions` output vs. `chat_sessions` side-table rows:
  - **Tombstoned orphan** — side-table row has `deleted_at` set but ADK session still exists → delete the ADK session + its GCS artifacts.
  - **Missing orphan** — ADK session exists but no side-table row at all → page ops (should never happen; indicates a side-table-write failure).
  
  Auto-cleanup on tombstoned orphans only. Missing orphans are always manual review.
- **Rate limits** — none on `/todos` or `/artifacts` (pure reads; low cost).
- **Telemetry** — Weave spans `chat.todos.list`, `chat.todos.tool_call` (for `set_todo_list` + `update_todo_list`), `chat.artifact.registered`, `chat.artifact.list`, `chat.orphan_scan.gcs`, `chat.orphan_scan.adk_session`.

### Out of scope

- User-editable todo-list checkboxes — agent-owned per [`../README.md`](../README.md) §7.6.
- User upload UI for artifacts — latent. The data model supports it via `created_by_tool=None` in v2, but no upload affordance ships in v1.
- Artifact inline preview (PDF viewer, image gallery) — click-out-to-signed-URL in v1.
- Artifact search within a session.
- Orphan auto-adopt / auto-delete for GCS blobs — reconciliation is report-only.
- Artifact diffing across versions.
- Cross-session artifact reuse — agent-initiated via `load_artifact(filename)` reads in-scope only.

## 3. Dependencies

| Component | Dependency | Reference |
|-----------|------------|-----------|
| **[CH-PRD-01](./CH-PRD-01-session-metadata-substrate.md)** | `ChatArtifactIndex` shape (no `creator` field), `TodoList` + `TodoItem` shapes, Firestore subcollection registered in DM-PRD-00 registry. | This PRD package |
| **[CH-PRD-02](./CH-PRD-02-chat-page-shell-and-sidebar.md)** | Page shell mount point; `lib/chatApi.ts` extended. | This PRD package |
| **[CH-PRD-04](./CH-PRD-04-session-status-view.md)** | `SessionStatusView.tsx` reserves slots for `TodoListsPanel` + `ArtifactsPanel`. The ADK-session orphan scan is the safety net for CH-PRD-04's delete-cleanup task. If CH-PRD-04 hasn't shipped, the endpoints + backend still ship behind a flag. | This PRD package |
| **[AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md)** | **Soft.** Agent Factory is where the two todo-list tools are registered. If unshipped, register against the hardcoded root with a TODO. | `../../agentic-harness/README.md` |
| **[BL-PRD-05](../../billing/projects/BL-PRD-05-failure-modes-permissions.md)** (soft) | Rate-limit substrate if needed for future write-side tools. Not required for v1 read endpoints. | `../../billing/README.md` |
| **ADK `GcsArtifactService`** | Blob storage. The wrapper sits on top. | Google ADK Python |
| **ADK `VertexAiSessionService`** | `get_session(id).state` read for todo lists; `list_sessions` for the orphan scan. | Google ADK Python |
| Existing `app/adk/agents/strategy_agent/artifact_utils.py` | Current raw `save_artifact_to_service` callsite. Migrated to the wrapper in the same PR. | `app/adk/agents/strategy_agent/artifact_utils.py` |
| **[FF-PRD-01](../../feature-flags/projects/FF-PRD-01-data-model-evaluation-api-backend-sdk.md)**, **[FF-PRD-03](../../feature-flags/projects/FF-PRD-03-frontend-sdk-e2e.md)** | `chat_v2_enabled` (master). No per-feature flag — todos + artifacts are non-optional once Chat is on. | `../../feature-flags/README.md` |

## 4. Data contract

### 4.1 Todo list shapes (ADK state + API)

```python
# session.state["todo_lists"] — dict-of-dicts, keyed by list_id
{
    "list_001": {
        "list_id": "list_001",
        "title": "Current: Q3 Calendar Build",
        "is_current": True,
        "created_at": "2026-04-01T10:00:00Z",
        "items": [
            {
                "item_id": "item_001",
                "text": "Finalize email dates",
                "completed": True,
                "completed_at": "2026-04-01T10:30:00Z",
            },
            {
                "item_id": "item_002",
                "text": "Schedule LinkedIn ads",
                "completed": False,
                "completed_at": None,
            },
        ],
    },
    "list_002": {
        "list_id": "list_002",
        "title": "Previous: Research Phase",
        "is_current": False,
        ...
    },
}
```

Validation on the read path — malformed entries (missing required keys, wrong types) are dropped with a warning log, not returned to the client. Max-size enforcement on the write path (via tool helpers) — 20 lists per session, 50 items per list. Exceeding returns a tool-error the agent can recover from.

### 4.2 Artifact metadata

Per CH-PRD-01 §4.1 — `ChatArtifactIndex`. Key fields:

- `artifact_id` — deterministic: `sha256(session_id|filename|version)[:32]`.
- `created_by_tool` — tool name (e.g., `"build_channel_report"`) when agent-created. `None` is reserved for future user uploads (no UI emits this in v1).
- `gcs_path` — populated from ADK's path convention: `gs://{bucket}/{app_name}/{user_id}/{session_id}/{filename}/{version}`.

**No `creator` field.** The presence or absence of `created_by_tool` is the provenance signal.

### 4.3 Endpoint response shapes

```python
# GET /conversations/{id}/todos
class ListTodosResponse(BaseModel):
    todo_lists: list[TodoList]   # sorted: is_current=True first, then created_at DESC

# GET /conversations/{id}/artifacts
class ListArtifactsResponseItem(BaseModel):
    artifact_index: ChatArtifactIndex
    signed_url: str              # 10-min TTL (CH-PRD-04's export uses 24-hour TTL separately)
    signed_url_expires_at: datetime

class ListArtifactsResponse(BaseModel):
    items: list[ListArtifactsResponseItem]
```

### 4.4 Tool signatures

```python
# Registered as ADK FunctionTools
async def set_todo_list(
    tool_context: ToolContext,
    list_id: str,
    title: str,
    items: list[dict],           # each: {item_id, text, completed=False, completed_at=None}
    is_current: bool = False,
) -> str:
    """Create or replace a todo list in the session.

    Use this when you start a new multi-step task. If `is_current=True`, any
    other list previously marked current will be cleared to False.
    """

async def update_todo_list(
    tool_context: ToolContext,
    list_id: str,
    item_id: str,
    completed: bool,
    text: str | None = None,     # optional rename
) -> str:
    """Check or uncheck an item in an existing todo list.

    Only flips one item at a time.
    """
```

Both tools write to `tool_context.state["todo_lists"]` via ADK's state mechanism — no direct Firestore write. Persistence is automatic through the session service.

## 5. Implementation outline

### 5.1 File inventory

| Action | File |
|--------|------|
| Create | `api/src/kene_api/chat/todos.py` — `list_todo_lists(session_id)`, validation helpers |
| Create | `api/src/kene_api/chat/artifacts.py` — `register_artifact(...)`, `list_artifacts(session_id)` |
| Modify | `api/src/kene_api/routers/chat.py` — `/todos` + `/artifacts` endpoints |
| Modify | `api/src/kene_api/chat/side_table.py` — `artifact_count` increment on registration |
| Create | `app/adk/tools/todo_list_tools.py` — `set_todo_list`, `update_todo_list` `FunctionTool`s |
| Modify | `app/adk/agents/<factory or root>/__init__.py` — register the two tools on the root agent (via AH-PRD-02 if shipped, hardcoded otherwise) |
| Modify | `app/adk/agents/strategy_agent/artifact_utils.py` — replace raw `save_artifact_to_service` with `chat.artifacts.register_artifact` |
| Create | `api/scripts/lint/check_artifact_register.py` — CI lint |
| Modify | `Makefile` or CI config — add `check_artifact_register` to `make lint` |
| Create | `frontend/src/components/chat/TodoListsPanel.tsx` |
| Create | `frontend/src/components/chat/ArtifactsPanel.tsx` |
| Modify | `frontend/src/components/chat/SessionStatusView.tsx` — mount both panels in the slots CH-PRD-04 reserved |
| Modify | `frontend/src/lib/chatApi.ts` — `listTodoLists`, `listArtifacts` typed wrappers |
| Modify | `docs/KEN-E-System-Architecture.md` §3.6 — add `todo_lists` row to the session-state table |
| Modify | `app/CLAUDE.md` (or equivalent ADK docs) — section on the artifact-register convention |
| Create | `api/scripts/chat_artifact_orphan_scan.py` — daily GCS-blob reconciliation |
| Create | `api/scripts/chat_adk_session_orphan_scan.py` — daily ADK-session reconciliation (safety net for CH-PRD-04 delete) |
| Modify | `deployment/terraform/cloud_scheduler.tf` — add both orphan-scan schedules |
| Create | `api/tests/unit/chat/test_todos_service.py` |
| Create | `api/tests/unit/chat/test_todos_validation.py` |
| Create | `api/tests/unit/chat/test_artifacts_service.py` |
| Create | `api/tests/unit/chat/test_artifact_id_determinism.py` |
| Create | `api/tests/integration/chat/test_register_artifact_writes_both.py` |
| Create | `api/tests/integration/chat/test_artifact_lint_rule.py` |
| Create | `api/tests/integration/chat/test_todos_end_to_end.py` |
| Create | `api/tests/integration/chat/test_adk_session_orphan_scan.py` |
| Create | `frontend/src/components/chat/__tests__/TodoListsPanel.spec.tsx` |
| Create | `frontend/src/components/chat/__tests__/ArtifactsPanel.spec.tsx` |
| Create | `frontend/tests/e2e/chat-todos-and-artifacts.spec.ts` |

### 5.2 `register_artifact` — wrapper body

```python
# api/src/kene_api/chat/artifacts.py
async def register_artifact(
    tool_context: ToolContext,
    filename: str,
    content: Part,                        # ADK content Part
    created_by_tool: str,                  # required in v1 (agent-created only)
) -> ChatArtifactIndex:
    """Save an artifact blob via ADK AND write the metadata index row.

    Every agent tool that creates an artifact MUST use this wrapper.
    A CI lint rule blocks raw `context.save_artifact(...)` calls.

    v1: only agents create artifacts (created_by_tool is required).
    v2: user uploads will pass created_by_tool=None; the shape already supports that.
    """
    # Step 1: save via ADK (returns version)
    version = await tool_context.save_artifact(filename, content)

    # Step 2: derive metadata
    session_id = tool_context.session_id
    account_id = tool_context.state["account_id"]
    artifact_id = hashlib.sha256(
        f"{session_id}|{filename}|{version}".encode()
    ).hexdigest()[:32]
    gcs_path = build_gcs_path(
        app_name=tool_context.app_name,
        user_id=tool_context.user_id,
        session_id=session_id,
        filename=filename,
        version=version,
    )

    index = ChatArtifactIndex(
        artifact_id=artifact_id,
        session_id=session_id,
        filename=filename,
        mime_type=content.inline_data.mime_type,
        size_bytes=len(content.inline_data.data or b""),
        version=version,
        gcs_path=gcs_path,
        created_by_tool=created_by_tool,
        created_at=datetime.now(tz=UTC),
    )

    # Step 3: write Firestore metadata row + side-table increment (atomic via batch)
    await firestore_batch([
        ("set", f"accounts/{account_id}/chat_sessions/{session_id}/artifacts/{artifact_id}", index.dict()),
        ("update", f"accounts/{account_id}/chat_sessions/{session_id}", {
            "artifact_count": Increment(1),
            "updated_at": now_utc(),
        }),
    ])

    return index
```

Idempotent: if the metadata row already exists (determined by `artifact_id`), the `set` is a no-op (Firestore dedup via doc id).

### 5.3 Lint rule

```python
# api/scripts/lint/check_artifact_register.py
"""
CI lint: every call to `save_artifact` in the repo must come from
`api/src/kene_api/chat/artifacts.py` (the wrapper).
"""
import re, sys
from pathlib import Path

ALLOWLIST = {"api/src/kene_api/chat/artifacts.py"}
PATTERN = re.compile(r"\b(context|tool_context|artifact_service)\.save_artifact\b")

violations = []
for p in Path(".").rglob("*.py"):
    rel = str(p)
    if any(rel.endswith(a) for a in ALLOWLIST):
        continue
    if rel.startswith(("test", "api/tests/")):
        continue    # tests may legitimately exercise both paths
    for i, line in enumerate(p.read_text().splitlines(), start=1):
        if PATTERN.search(line):
            violations.append((rel, i, line.strip()))

if violations:
    print("FAIL: raw save_artifact calls detected:")
    for v in violations:
        print(f"  {v[0]}:{v[1]}  {v[2]}")
    print("\nUse chat.artifacts.register_artifact() instead.")
    sys.exit(1)
```

Wired into `make lint` (Makefile target); runs on every PR.

### 5.4 Todo-list tool — flow

```python
# app/adk/tools/todo_list_tools.py
async def set_todo_list(
    tool_context: ToolContext,
    list_id: str,
    title: str,
    items: list[dict],
    is_current: bool = False,
) -> str:
    existing = tool_context.state.get("todo_lists", {})
    if list_id not in existing and len(existing) >= 20:
        return "ERROR: session has 20 todo lists already; archive or remove one."
    if len(items) > 50:
        return "ERROR: todo list capped at 50 items."

    normalized = [
        {
            "item_id": item.get("item_id", f"item_{i:03d}"),
            "text": item["text"],
            "completed": bool(item.get("completed", False)),
            "completed_at": item.get("completed_at"),
        }
        for i, item in enumerate(items)
    ]

    if is_current:
        for other_id, other_list in existing.items():
            if other_id != list_id and other_list.get("is_current"):
                other_list["is_current"] = False

    existing[list_id] = {
        "list_id": list_id,
        "title": title,
        "is_current": is_current,
        "created_at": datetime.now(tz=UTC).isoformat(),
        "items": normalized,
    }
    tool_context.state["todo_lists"] = existing
    return f"Todo list '{title}' set with {len(normalized)} items."
```

`update_todo_list` follows the same pattern: reads state, locates the item, flips `completed`, stamps `completed_at`, writes back.

### 5.5 `TodoListsPanel.tsx` — render spec

Port from `docs/figma-export/src/app/components/SessionSettings.tsx` todo-list section:

- **Card header:** "To Do Lists" title + `CheckCircle2` icon + caption "Tracks long tasks to ensure details are preserved during compaction."
- **List items (sorted):** current-marked list first, then rest by `created_at DESC`.
- **Collapsible:** chevron toggles items visible. Expanded by default if `is_current=true`.
- **Item row:** disabled `Checkbox` (visual only; never interactive) + text. Completed items: line-through + muted color. Incomplete items: normal color.
- **Progress fraction:** "2/6" in the list header.
- **Current badge:** blue "Active" pill on the current list's header.

### 5.6 `ArtifactsPanel.tsx` — render spec

Port from `docs/figma-export/src/app/components/SessionSettings.tsx` documents section, scoped to v1 (agent-created artifacts only):

- **Card header:** "Documents" title + `FileText` icon + count badge.
- **Rows:** file-type icon (colored by mime type) + filename (truncate) + size (e.g., "2.4 MB") + **"KEN-E" badge with `Bot` icon** (all v1 artifacts are agent-created). Hover tooltip shows the `created_by_tool` name + date: "Created by `build_channel_report` on 2026-04-02".
- **Click:** opens the `signed_url` in a new tab.
- **Empty state:** "No documents yet. KEN-E will attach any files it creates during the session."

When v2 ships the user-upload UI, a second badge variant ("Uploaded") will be introduced keyed off `created_by_tool === null` — but the v1 ports only the agent variant.

### 5.7 Orphan reconciliation jobs (two)

**GCS blob orphans — `chat_artifact_orphan_scan.py`** (Cloud Run scheduled, daily 04:00 UTC):

```python
async def scan_for_gcs_blob_orphans():
    # List GCS blobs under the artifacts bucket
    blobs = await gcs.list_blobs(prefix=f"{ADK_APP_NAME}/")
    orphans = []
    for blob in blobs:
        parsed = parse_gcs_path(blob.path)
        if not parsed:
            continue
        artifact_id = hashlib.sha256(
            f"{parsed.session_id}|{parsed.filename}|{parsed.version}".encode()
        ).hexdigest()[:32]
        exists = await firestore.get_document(
            f"accounts/{parsed.account_id}/chat_sessions/{parsed.session_id}/artifacts/{artifact_id}"
        )
        if not exists:
            orphans.append(blob.path)
    if orphans:
        await slack_alert(
            channel="#chat-ops",
            message=f"{len(orphans)} orphan GCS blobs detected. Review with ops.",
            details=orphans[:20],
        )
```

Report-only in v1. Ops reviews the list and manually adopts or deletes.

**ADK-session orphans — `chat_adk_session_orphan_scan.py`** (Cloud Run scheduled, daily 04:30 UTC). **The safety net for CH-PRD-04's delete-cleanup task failures.**

```python
async def scan_for_adk_session_orphans():
    """Two cases:
       - TOMBSTONED ORPHAN: chat_sessions.deleted_at set, but ADK session still exists
         → auto-delete the ADK session + its GCS artifacts (CH-PRD-04 delete cleanup failed).
       - MISSING ORPHAN: ADK session exists with no side-table row at all
         → page ops (should not happen; indicates a side-table-write bug).
    """
    tombstoned_to_clean = []
    missing_orphans = []

    # Iterate every account's users
    for account_id in await iterate_accounts():
        for user_id in await iterate_users_in_account(account_id):
            adk_sessions = await adk_session_service.list_sessions(
                app_name="ken_e_chatbot", user_id=user_id,
            )
            for s in adk_sessions:
                meta = await firestore.get_document(
                    f"accounts/{account_id}/chat_sessions/{s.id}"
                )
                if meta is None:
                    missing_orphans.append((account_id, user_id, s.id))
                    continue
                if meta.get("deleted_at") is not None:
                    # Side-table is tombstoned but ADK still has it — CH-PRD-04 cleanup failed
                    deleted_age = now_utc() - meta["deleted_at"]
                    if deleted_age > timedelta(hours=1):
                        # Grace period: don't race with an in-flight cleanup task
                        tombstoned_to_clean.append((account_id, user_id, s.id))

    # Auto-clean tombstoned orphans
    for account_id, user_id, session_id in tombstoned_to_clean:
        await adk_session_service.delete_session(
            app_name="ken_e_chatbot", session_id=session_id,
        )
        artifacts = await artifact_index.list(session_id)
        for a in artifacts:
            await gcs.delete_blob(a.gcs_path)
        # Delete the metadata subcollection + the side-table row itself
        await firestore.delete_collection_group(
            parent=f"accounts/{account_id}/chat_sessions/{session_id}/artifacts",
        )
        await firestore.delete_document(
            f"accounts/{account_id}/chat_sessions/{session_id}",
        )

    # Page ops for missing orphans (no auto-cleanup; needs investigation)
    if missing_orphans:
        await pagerduty_alert(
            severity="warning",
            message=f"{len(missing_orphans)} ADK sessions exist without side-table rows. "
                    "Likely a side-table-write bug. Needs investigation.",
            details=missing_orphans[:10],
        )

    # Telemetry
    await emit_weave_metric("chat.orphan_scan.adk_session", {
        "tombstoned_cleaned": len(tombstoned_to_clean),
        "missing_orphans": len(missing_orphans),
    })
```

1-hour grace period before auto-cleaning tombstoned orphans — avoids racing CH-PRD-04's normal delete-cleanup task.

## 6. API contract

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/chat/conversations/{id}/todos` | Returns `ListTodosResponse`. Ownership-gated 404. |
| `GET` | `/api/v1/chat/conversations/{id}/artifacts` | Returns `ListArtifactsResponse` with 10-min signed URLs. |

No new write endpoints — todo lists and artifacts are written by agent tools via ADK's state / artifact service APIs, not by user-initiated HTTP requests.

## 7. Acceptance criteria

1. **Tool `set_todo_list` works** — calling the tool writes `session.state["todo_lists"][list_id]` with the expected shape; `GET /todos` returns it within one poll.
2. **Tool `update_todo_list` works** — flips `completed` + stamps `completed_at`; state reflects.
3. **Only one list `is_current=true`** — unit test: set list B as current when list A was current → list A's `is_current` flips to false.
4. **Size caps** — 21st list returns tool error; 51st item returns tool error. Tool is recoverable (agent can continue).
5. **Malformed state drops safely** — seed `session.state["todo_lists"]["bad"] = {"nope": 1}`; `GET /todos` returns empty list with a warning log, no 500.
6. **`TodoListsPanel.tsx` renders** — current list first with "Active" pill; expanded by default; disabled checkboxes; line-through on completed; progress fraction correct.
7. **`register_artifact` writes both** — integration test calls the wrapper from a fake tool; GCS blob exists; Firestore index row exists with correct `created_by_tool`, `artifact_id`, `gcs_path`. **No `creator` field on the row.**
8. **`register_artifact` requires `created_by_tool`** — calling without the arg in v1 raises TypeError. Documents that future user-upload path will pass `None` explicitly.
9. **Idempotent registration** — calling `register_artifact` with the same `(session_id, filename, version)` twice leaves one metadata row (deterministic `artifact_id` dedups).
10. **Lint rule blocks raw `save_artifact`** — a test PR adding `context.save_artifact("foo.pdf", part)` in `api/src/kene_api/some_new_file.py` fails `make lint`.
11. **Existing strategy agent migrated** — `app/adk/agents/strategy_agent/artifact_utils.py` now calls the wrapper; existing strategy flow regression-tested.
12. **`ArtifactsPanel.tsx` renders** — file-type icons correct; **all artifacts render with a "KEN-E" badge** (no Uploaded vs KEN-E distinction in v1); hover tooltip shows tool name; click opens signed URL.
13. **`artifact_count` increments** — `chat_sessions.artifact_count` advances by 1 for each registration.
14. **GCS orphan scan** — seed a GCS blob without a metadata row; run scan; Slack alert fires with that blob path.
15. **ADK-session orphan scan (tombstoned)** — seed a side-table row with `deleted_at` set > 1 hour ago but ADK session still exists; run scan; ADK session is deleted + GCS artifacts are deleted + side-table row is deleted + Weave metric fires.
16. **ADK-session orphan scan (missing)** — seed an ADK session with no side-table row; run scan; PagerDuty alert fires; no auto-cleanup.
17. **ADK-session orphan scan grace period** — seed a side-table row with `deleted_at` set 10 minutes ago; run scan; session is NOT cleaned up (within 1-hour grace).
18. **System architecture doc updated** — §3.6 session-state table includes `todo_lists` row.
19. **Tool convention documented** — `app/CLAUDE.md` has a paragraph pointing to the wrapper.

## 8. Test plan

### Unit (backend)
- `list_todo_lists` validation drops malformed entries.
- `list_todo_lists` sort — `is_current=True` first, then `created_at DESC`.
- `register_artifact` determinism — same inputs → same `artifact_id`.
- `register_artifact` idempotency — second call is a no-op at the doc level.
- `register_artifact` updates side-table `artifact_count`.
- `register_artifact` signature: `created_by_tool` is required (v1).
- GCS path parsing — correctly extracts `session_id`, `filename`, `version`.

### Unit (frontend)
- `TodoListsPanel.spec.tsx` — renders given mock data; disabled checkbox; Current badge; progress fraction; expand/collapse.
- `ArtifactsPanel.spec.tsx` — renders given mock data; all render with KEN-E badge; tool name in tooltip; click opens new tab; empty state.

### Unit (ADK)
- `set_todo_list` creates state correctly.
- `set_todo_list` unsets prior current when new list is current.
- `set_todo_list` size cap.
- `update_todo_list` flips item.

### Integration
- End-to-end todo: agent calls `set_todo_list` via ADK runner → `GET /todos` returns; agent calls `update_todo_list` → updated item reflects.
- End-to-end artifact: agent calls a tool using `register_artifact` → GCS blob + metadata row exist → `GET /artifacts` returns with signed URL → signed URL downloads the blob.
- Lint rule regression: add a deliberate violation → `make lint` fails with clear message.
- Strategy agent migration: existing strategy flow still produces the same artifacts, now with metadata rows.
- GCS orphan scan: seed an orphan; scan fires alert; no data mutation.
- ADK-session orphan scan:
  - Tombstoned > 1h → cleanup fires.
  - Tombstoned < 1h → cleanup skipped (grace window).
  - Missing side-table row → PagerDuty alert fires, no cleanup.

### E2E (Playwright)
- Seed a session where the agent creates 2 todo lists + 3 artifacts → open status view → both panels populated correctly.

## 9. Risks & open questions

| Risk | Mitigation |
|------|------------|
| Agent writes malformed `todo_lists` dict that breaks the renderer | Server-side Pydantic validation on read in `/todos` endpoint; malformed entries dropped with warning log. Tool helpers normalize on write. |
| Tool hits size cap mid-task → agent can't add more items | Returns recoverable tool error; agent can prune or archive old lists. |
| Agent forgets to call `register_artifact` and uses raw `save_artifact` | CI lint catches in PR; existing callsites migrated in CH-PRD-05. Runtime reconciliation catches anything the lint misses. |
| Agent calls `register_artifact` but Firestore write fails after GCS save | Logged + retried with exponential backoff (3 attempts); on final failure, orphan reconciliation catches it. Blob stays in GCS (no silent data loss). |
| Signed URL exposes the artifact to anyone with the URL | 10-min TTL for in-app listing; 24-hour TTL on CH-PRD-04's export (deliberate UX tradeoff). Authorization gate before signing (session ownership). Acceptable for v1. |
| Orphan scan gets slow with millions of blobs / sessions | Parallelize per-account prefixes; bounded runtime. If scan exceeds 30 min, page ops and split the iteration. |
| Todo-list state grows large on very active sessions | 20-list × 50-item cap (100 × item-size bytes) stays well under Firestore 1 MB doc budget via `session.state`. |
| Two agent tools try to update the same todo-list item concurrently | ADK state writes are last-writer-wins at the session-service level. Tool helpers are designed for sequential use by a single agent turn. |
| ADK-session orphan scan race: cleanup fires while CH-PRD-04's cleanup task is running | 1-hour grace period before auto-cleanup. Concurrent calls to `delete_session` on the same ID are idempotent in ADK. |
| ADK-session orphan scan finds a "missing orphan" (ADK session, no side-table) | Pager alert; manual investigation. Likely cause: side-table-write bug on creation path or DM-PRD-05 deletion-sweep race. Not auto-cleaned. |

### Open questions
- **Q:** Should the UI surface the todo list in the message stream as well as the status view? → **Proposal:** status view only in v1. Future enhancement if users don't notice progress.
- **Q:** Should `set_todo_list` with an existing `list_id` fully replace items, or merge? → **Proposal:** fully replace — simpler mental model. Use `update_todo_list` per item for merges.
- **Q:** Is there a use case for programmatic artifact lookup by tool name? → **Deferred.** If demand arises, add `?created_by_tool=` query param to `GET /artifacts`.
- **Q:** Should the ADK-session orphan scan also handle sessions that ADK `list_sessions` misses due to Issue #3154? → **Proposal:** the scan treats "no result from `list_sessions`" as ground truth. If the ADK bug returns incomplete lists, we'd under-clean (safer than over-clean). CH-PRD-01's back-fill guard + the periodic scan combined reduce the risk.

## 10. Reference

- Component plan: [`../implementation-plan.md`](../implementation-plan.md)
- Component README: [`../README.md`](../README.md)
- Upstream: [CH-PRD-01](./CH-PRD-01-session-metadata-substrate.md), [CH-PRD-02](./CH-PRD-02-chat-page-shell-and-sidebar.md)
- Mounts into: [CH-PRD-04](./CH-PRD-04-session-status-view.md) — `SessionStatusView` reserves the slots; depends on CH-PRD-05's ADK-session orphan scan as safety net
- Integration: [AH-PRD-02](../../agentic-harness/projects/AH-PRD-02-agent-factory.md) (tool registration)
- Figma: `docs/figma-export/src/app/components/SessionSettings.tsx` — documents + todo lists sections (user-upload variant not ported in v1)
- Existing code: [`app/adk/agents/strategy_agent/artifact_utils.py`](../../../../app/adk/agents/strategy_agent/artifact_utils.py) (migrated)
- ADK docs: [`ArtifactService`](https://google.github.io/adk-docs/artifacts/), [`session.state`](https://google.github.io/adk-docs/sessions/state/)
- CLAUDE.md rules in scope: C-4, C-5, C-7, C-9; PY-1, PY-2, PY-5, PY-7; T-1, T-3, T-4, T-5; G-1
