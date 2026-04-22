# Figma Make — Work-Loss Bug Report

## Summary
In a long Figma Make session building a React + Tailwind prototype, significant implementation work has been silently lost **multiple times** across version restores and conversation resumption. Each recovery requires reconstructing ~100–200 lines of code from the raw conversation transcript. This report documents the observed pattern so the Figma Make team can investigate.

## Environment
- Product: **Figma Make** (Claude Code harness)
- Primary working directory: `/workspaces/default/code`
- Session ID: `86dd3f3e-3f76-4401-8b16-934af9fb8adc`
- Transcript: `sessions/86dd3f3e-3f76-4401-8b16-934af9fb8adc/claude/projects/-workspaces-default-code/0cbed7e0-b751-4e17-af46-675810961d4b.jsonl`
- Primary file affected: `src/app/pages/CalendarPage.tsx`
- Project type: React + Tailwind v4 prototype, non-standard Vite setup (no `index.html`, entrypoint is auto-generated)

## Observed Pattern

The loss cycle repeats:

1. Assistant implements a feature (panels, wizard fields, recurring-schedule UI) and verifies it.
2. User continues the session — possibly across conversation compaction, possibly after invoking a restore.
3. On the next turn, the feature is **missing from disk**, even though the in-conversation summary / todo list says it was completed.
4. Import statements that reference the now-missing code produce runtime errors (e.g. `SyntaxError: The requested module does not provide an export named 'getCampaignsForObjective'`).
5. The assistant reconstructs the work from the jsonl transcript — and the loss recurs on the next restore.

## Concrete Loss Events in This Session

### Loss #1 — Calendar page panels + Repeat section
- **What was lost**: Three panel components wired into `CalendarPage.tsx` (`UnscheduledTasksPanel`, `ProjectsInRangePanel`, `MoveToProjectDialog`), plus a Repeat (recurring-schedule) section in `ActivityForm`, plus a `visibleActivities` useMemo that expands recurring tasks via `computeNextRun`.
- **Size**: ~200 lines of wiring across imports, state, handlers, JSX mounts, and form UI.
- **Files**: The component files (`UnscheduledTasksPanel.tsx`, `ProjectsInRangePanel.tsx`, `MoveToProjectDialog.tsx`) were NOT deleted — only their **imports, JSX mounts, and supporting state in `CalendarPage.tsx`** disappeared.
- **Discovery**: User quote: *"NOOOO!!! You've deleted our work again! Investigate why all of the panels that we spent the last 4 hours creating have been removed from the Calendar page..."*
- **Resolution**: Reconstructed from transcript (~206 lines).

### Loss #2 — Field-cleanup refactor (after Loss #1 was reconstructed)
- **What was lost**: A data-model cleanup that removed `objective` and `expected_direction` from `CalendarActivity`, made `campaign_id` nullable, renamed `getCampaignsForObjective` → `getCampaignsByObjective`, and rewrote `ActivityForm`'s Campaign selector (~120 lines of edits across 6 files).
- **Symptom**: `SyntaxError: The requested module '/src/app/data/calendarData.ts' does not provide an export named 'getCampaignsForObjective'` — `calendarData.ts` had been cleaned up (export renamed), but `CalendarPage.tsx` was restored to a pre-cleanup state that still imported the old name.
- **Resolution**: Re-applied cleanup to `CalendarPage.tsx`.

### Loss #4 — Both losses recurred together immediately after this report was written
- **What was lost**: Same as Loss #2 (field cleanup) + Loss #3 (panel wiring), simultaneously, on the very next user turn after this bug report was created.
- **Symptom**: Identical `getCampaignsForObjective` SyntaxError as Loss #2, plus zero references to the panel imports. File length dropped from 2805 → 2616 lines.
- **Significance**: The loss recurred while the user was actively documenting the bug. This is strong evidence the cycle is mechanical (a restore or compaction step) rather than user-triggered.
- **Resolution**: Re-applied both sets of edits in one batch.

### Loss #3 — Panels lost AGAIN after Loss #2 was reconstructed
- **What was lost**: The same panel wiring from Loss #1 disappeared a second time, at the same point that Loss #2's cleanup got reverted.
- **Symptom**: Zero references to `UnscheduledTasksPanel`, `ProjectsInRangePanel`, `MoveToProjectDialog`, `useStandaloneTasks`, `describeSchedule`, or `computeNextRun` in `CalendarPage.tsx`, despite the assistant summary claiming the reconstruction from Loss #1 was complete.
- **Resolution**: Reconstructed a second time from transcript; saved a durable backup at `src/app/pages/_panel_reconstruction.txt` to insure against Loss #N.

## Key Observation: The summary–reality gap

The most telling detail is that the assistant's **post-compaction conversation summary** described features as "implemented and verified," but the file on disk **did not contain them**. Possibilities:

1. **Restores are silently rolling back deltas** that the summary was generated against, and the post-restore state is not reconciled with the running conversation context.
2. **Conversation compaction is referencing transcript state rather than disk state** when generating summaries, so the summary reflects what was written *during the conversation*, not what survives a restore.
3. **Edits are being applied to a versioned snapshot** that later gets superseded without the assistant being informed.

Either way, the assistant believes features are present (because the transcript says so) while the user sees broken imports (because disk says otherwise). This breaks the fundamental trust contract of the tool.

## Reproduction Signal (without a full repro)

Look at `CalendarPage.tsx` across transcript checkpoints vs. disk checkpoints in this session. The panel wiring was written at least **twice** via Edit tool calls to the same file (jsonl line ranges roughly 2275–2341, then again after the user said "yes, re-reconstruct"). Disk state at various points shows only **one** of those two versions — which means at least one Edit's effect did not persist past a restore.

## Impact
- Multi-hour work losses, now recurring.
- User explicitly raised escalating to public commentary about Figma Make reliability.
- Forced defensive workarounds (saving backups as plain-text files inside the project) because the version system cannot be trusted.

## What Would Help
1. **Root-cause the silent loss.** Even if it's rare, the fact that the summary asserts work is present while disk disagrees is a data-integrity issue, not a UX issue.
2. **Surface restore events to the assistant.** If a restore happens, the assistant should be notified so it can reconcile conversation state vs. disk state before making new edits — otherwise it keeps making decisions off a stale model.
3. **Durable per-feature backups.** Consider a built-in "checkpoint" primitive so long-running sessions aren't one restore away from losing hours of work.
4. **A diff between "what the summary claims" and "what's on disk"** at conversation resume — the gap is the bug.

## Artifacts in the Project (available for inspection)
- `src/app/pages/_panel_reconstruction.txt` — literal transcript-extracted code blocks used to restore Loss #1 and #3
- Full session transcript at path above

---
*Generated during active session on 2026-04-22.*
