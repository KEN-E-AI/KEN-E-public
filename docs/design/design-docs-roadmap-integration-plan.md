# Plan: Bidirectional Design Docs ↔ Product Roadmap

**Date:** 2026-03-18 (originally 2026-03-11)
**Status:** In Progress — Phase 2 complete, Phases 3–5 pending
**Branch:** `docs/harness-cleanup-design-docs`

## Context

The KEN-E project has well-structured design docs (`docs/`) and a complete Notion roadmap (Releases → Features → User Stories → Sprints), but they were disconnected. A developer could not see which Features/Stories implement a design doc section, and a PM could not see which design doc sections a Feature touches. The process for updating design docs when the roadmap changes was also undefined.

This plan creates bidirectional links and clear workflows to close these gaps.

### Completed Work

As of commit `fc5cb46` (2026-03-18), 86 bidirectional cross-references have been deployed:

- **54 `> **Roadmap:**` blockquotes** in 9 design docs — each links to the relevant Feature heading in `product-roadmap.md` with Feature name and Release.
- **32 `> **Design refs:**` blockquotes** in `product-roadmap.md` — each links back to design doc section headings using native markdown anchors.
- **`docs/product-roadmap.md`** now exists as a markdown file containing the full 6-release roadmap with Features, User Stories, and cross-references.

The format is simpler than originally planned — static links with Feature name + Release, no story counts or progress tracking. All links use native markdown heading anchors (not HTML comment anchors).

### Goals

1. **High-level vision** — Allow a developer or agent to view the product vision, design plans, and final functionality.
2. **Drill into details** — Allow drilling into any architecture section to see reasoning, implementation plan, and relevant Features/User Stories/Sprints.
3. **Current state vs vision** — Understand what's been built vs. what's planned, with progress visibility.

### Current Gaps

- ~~**No link between design docs and product roadmap.**~~ **Resolved** (commit `fc5cb46`). 86 bidirectional cross-references now link design doc sections to Features in `product-roadmap.md` and vice versa.
- **Unclear process for PM-initiated changes.** When the PM decides to create a new feature or modify an existing one, the process for updating the design documents is undefined and error-prone.

---

## Phase 1: Notion Schema Changes (Foundation)

**Goal:** Add the missing relations so design decisions and features can be cross-referenced in Notion.

### 1a. Add missing relations to Design Decisions database — Pending

The Design Decisions database (`a88ce7c8-1ebb-4634-a422-2c1abcd2daf9`) currently only links to Products. Add:

- `Features` — dual relation to Features DB (`1e430fd6-5302-8135-8a27-000b14a69d9d`)
- `Triggering Story` — relation to User Stories DB (`1e430fd6-5302-8124-916f-000b3d2d07c0`)
- `Affected Stories` — relation to User Stories DB

> **Note:** `notion-schema.md` documented these as "needs to be added manually" but they were never created. The `/end-session` skill already tries to set them — they silently fail.

### 1b. ~~Add `Design Doc Sections` property to Features database~~ — Dropped

**Dropped.** Superseded by `> **Design refs:**` blockquotes embedded directly in `product-roadmap.md` under each Feature heading. Feature-to-section lookups now go through `product-roadmap.md` instead of a Notion property.

### 1c. ~~Create Notion views~~ — Dropped

**Dropped.** Can be created ad-hoc when needed. Not worth planning infrastructure around.

### Files to modify
- `.claude/skills/notion-pm-workflow/references/notion-schema.md` — update after Phase 1a Notion changes

---

## Phase 2: Design Doc Conventions (Anchors + Roadmap Blocks)

**Goal:** Add stable cross-references and visible roadmap info to each design doc section.

### 2a. ~~Add stable `<!-- anchor: -->` HTML comments to section headings~~ — Dropped

**Dropped.** 86 cross-references deployed using native markdown heading anchors (commit `fc5cb46`). HTML comment anchors would be redundant — native heading anchors are simpler, render as clickable links on GitHub, and are already depended on by all existing cross-references.

### 2b. ~~Add visible roadmap info blocks under key section headings~~ — Complete

**Complete** (commit `fc5cb46`). Two blockquote conventions deployed:

**In design docs** — `> **Roadmap:**` links to the Feature heading in `product-roadmap.md`:
```markdown
### 4.3 Tool Discovery & Dynamic Tool Selection
> **Roadmap:** [Feature 1.2 — Tool Registry & Dynamic Selection](../product-roadmap.md#feature-12--tool-registry--dynamic-selection-mvp) (Release 1: MVP)
```

**In `product-roadmap.md`** — `> **Design refs:**` links back to design doc section headings:
```markdown
#### Feature 1.2 — Tool Registry & Dynamic Selection (MVP)
> **Design refs:** [Harness §4.3 Tool Discovery](design/../../docs/KEN-E-Agentic-Harness-Design.md#43-tool-discovery--dynamic-tool-selection) | [MCP §5a Tool Filter](design/mcp-architecture.md#5a-tool_filter-architecture)
```

The format is simpler than originally planned — no story counts or progress tracking. Static links with Feature name and Release.

### 2c. Rewrite `design-doc-mapping.md` — Pending (revised scope)

Rewrite `.claude/skills/notion-pm-workflow/references/design-doc-mapping.md`:

- **Remove** the Section Index (stale line ranges that break on every edit)
- **Remove** the Feature-to-Section Mapping (stale feature numbers, superseded by `> **Design refs:**` blockquotes in `product-roadmap.md`)
- **Keep** the Keyword Search Index (still valuable for keyword-based lookups when the Feature context isn't known)
- **Update** keyword index entries to use section heading slugs instead of line ranges
- **Add** a header note pointing to `product-roadmap.md` for feature-to-section lookups

### Files to modify
- `.claude/skills/notion-pm-workflow/references/design-doc-mapping.md` — rewrite per above scope

---

## Phase 3: Workflow Definitions

**Goal:** Define clear processes for both PM-initiated and developer-initiated changes.

### 3a. PM-Initiated Workflow (Feature Creation/Modification)

PMs work entirely in Notion. Developers maintain markdown (design docs + `product-roadmap.md`).

**When PM creates a new Feature:**
1. PM creates Feature with standard properties (Name, Description, Status, Priority, Release)
2. On the next `/start-session` for a story under that Feature, the agent reads `product-roadmap.md` for design refs and suggests relevant design doc sections.

**When PM modifies a Feature requiring design doc updates:**
1. PM adds a comment to the Feature page: "Needs design doc update: [description]"
2. The next `/start-session` for a story under that Feature surfaces this comment prominently.
3. The developer/agent updates the design doc and the cross-reference blockquotes.

**Why no dedicated PM skill:** PMs don't use Claude Code. Their workflow stays Notion-native. Trying to automate PM→docs sync would require webhooks/polling — heavy infrastructure not justified at current team size.

### 3b. Developer-Initiated Workflow (Updated `/end-session` Flow)

Extend the existing design change check in `/end-session`:

1. **After creating a Design Decision:** Set `Features` and `Triggering Story` relations (using the properties from Phase 1a).
2. **After updating a design doc (High/Critical):** Check if `> **Roadmap:**` blocks in affected sections need updating, and check if `> **Design refs:**` in `product-roadmap.md` needs updating.
3. ~~**Story count updates**~~ — Dropped. Story counts go stale immediately, duplicate info already in `product-roadmap.md`, and would require Notion API calls per session.

### 3c. `[PLANNED]` Lifecycle

When `/end-session` runs and the completed story was the last story for a Feature, check if the corresponding design doc sections still have `[PLANNED]` tags. If so, print a reminder:

> "All stories for Feature X.X are complete. Consider collapsing `[PLANNED]` sections in [doc name §section]."

Actual collapse is manual. CLAUDE.md already documents the convention: remove the `[PLANNED]` tag, merge "current" and "planned" subsections/diagrams, update status columns to "Implemented."

---

## Phase 4: Claude Code Skill Updates

### 4a. Update `/start-session` skill

Modify `session-context.md` Step 4 (design doc reading):

1. Read the Feature heading in `product-roadmap.md`, find the `> **Design refs:**` blockquote
2. Parse the heading anchor links to identify relevant design doc sections
3. Read those sections directly using the heading anchors
4. Fall back to keyword index in `design-doc-mapping.md` for keyword-based lookups (when Feature context is missing or `> **Design refs:**` is empty)
5. Check for PM comments on the Feature page containing "Needs design doc update". Surface prominently if found.

### 4b. Update `/end-session` skill

1. Fix Design Decision relation-setting — set `Features` and `Triggering Story` relations (requires Phase 1a Notion changes)
2. Add `[PLANNED]` collapse reminder when all Feature stories complete (per Phase 3c)
3. When design doc sections change, check/update `> **Roadmap:**` and `> **Design refs:**` blockquotes

### 4c. Update reference files

- `.claude/skills/notion-pm-workflow/references/notion-schema.md` — update after Phase 1a Notion changes
- `.claude/skills/notion-pm-workflow/references/design-doc-mapping.md` — rewrite per Phase 2c
- `.claude/skills/notion-pm-workflow/references/design-change-workflow.md` — add steps for maintaining `> **Roadmap:**` and `> **Design refs:**` blockquotes

### Files to modify
- `.claude/skills/start-session/agents/session-context.md`
- `.claude/skills/end-session/SKILL.md`
- `.claude/skills/notion-pm-workflow/references/notion-schema.md`
- `.claude/skills/notion-pm-workflow/references/design-change-workflow.md`
- `.claude/skills/notion-pm-workflow/references/design-doc-mapping.md`

---

## Phase 5: CLAUDE.md & Documentation Updates

### 5a. Update CLAUDE.md "Design Documentation" section

1. Add `product-roadmap.md` to the design docs table
2. Document the `> **Roadmap:**` and `> **Design refs:**` blockquote conventions
3. Document the `[PLANNED]` collapse convention (partially there already)
4. Update "Workflow for New Design Decisions" to include cross-reference blockquote maintenance steps

### Files to modify
- `CLAUDE.md`

---

## Implementation Sequence

| Order | Item | Status | Depends On |
|-------|------|--------|------------|
| — | ~~1b: Features Design Doc Sections property~~ | **Dropped** | — |
| — | ~~1c: Create Notion views~~ | **Dropped** | — |
| — | ~~2a: Add HTML comment anchors~~ | **Dropped** | — |
| — | ~~2b: Add Roadmap blocks to design docs~~ | **Complete** (`fc5cb46`) | — |
| 1 | 1a: Design Decisions relations (manual Notion work) | Pending | — |
| 2 | 2c: Rewrite design-doc-mapping.md (keep keyword index only) | Pending | — |
| 3 | 4c: Update reference files (design-change-workflow.md) | Pending | — |
| 4 | 4a: Update session-context.md Step 4 | Pending | 2c |
| 5 | 4b: Update /end-session skill | Pending | 1 |
| 6 | 5a: Update CLAUDE.md | Pending | — |

Step 1 is manual Notion work (prerequisite). Steps 2–4 can be a single session. Steps 5–6 are a second session after Notion changes are confirmed.

---

## Verification

After implementation:

1. **Cross-reference integrity:** `grep -r '> \*\*Roadmap:\*\*' docs/` returns all roadmap blocks; each links to a valid heading in `product-roadmap.md`. `grep -r '> \*\*Design refs:\*\*' docs/product-roadmap.md` returns all design ref blocks; each links to a valid heading in a design doc.
2. **Notion schema:** Verify Design Decisions DB has `Features`, `Triggering Story`, `Affected Stories` relations
3. **Keyword index:** `design-doc-mapping.md` keyword index uses section heading slugs (not line ranges) and all slugs resolve to actual headings
4. **End-to-end test:** Run `/start-session` on a story under a Feature — verify the session context reads `> **Design refs:**` from `product-roadmap.md` and loads the linked design doc sections
5. **PM workflow test:** Add a "Needs design doc update" comment to a Feature in Notion — verify `/start-session` surfaces it
6. **Design change test:** Run `/end-session` with a design change — verify it creates a Design Decision with `Features` relation set, and checks cross-reference blockquotes for needed updates
