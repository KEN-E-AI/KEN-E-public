# Plan: Bidirectional Design Docs ↔ Product Roadmap

**Date:** 2026-03-11
**Status:** Proposed — awaiting team review
**Branch:** `docs/harness-cleanup-design-docs`

## Context

The KEN-E project has well-structured design docs (`docs/`) and a complete Notion roadmap (Releases → Features → User Stories → Sprints), but they are disconnected. A developer cannot see which Features/Stories implement a design doc section, and a PM cannot see which design doc sections a Feature touches. The process for updating design docs when the roadmap changes is also undefined.

This plan creates bidirectional links and clear workflows to close these gaps.

### Goals

1. **High-level vision** — Allow a developer or agent to view the product vision, design plans, and final functionality.
2. **Drill into details** — Allow drilling into any architecture section to see reasoning, implementation plan, and relevant Features/User Stories/Sprints.
3. **Current state vs vision** — Understand what's been built vs. what's planned, with progress visibility.

### Current Gaps

- **No link between design docs and product roadmap.** It is not possible to see which Features and User Stories have been created for each component in the design documents.
- **Unclear process for PM-initiated changes.** When the PM decides to create a new feature or modify an existing one, the process for updating the design documents is undefined and error-prone.

---

## Phase 1: Notion Schema Changes (Foundation)

**Goal:** Add the missing relations so design decisions, features, and design docs can be cross-referenced in Notion.

### 1a. Add missing relations to Design Decisions database

The Design Decisions database (`a88ce7c8-1ebb-4634-a422-2c1abcd2daf9`) currently only links to Products. Add:

- `Features` — dual relation to Features DB (`1e430fd6-5302-8135-8a27-000b14a69d9d`)
- `Triggering Story` — relation to User Stories DB (`1e430fd6-5302-8124-916f-000b3d2d07c0`)
- `Affected Stories` — relation to User Stories DB

> **Note:** `notion-schema.md` documented these as "needs to be added manually" but they were never created. The `/end-session` skill already tries to set them — they silently fail.

### 1b. Add `Design Doc Sections` property to Features database

Add a `RICH_TEXT` property called `Design Doc Sections` to the Features data source (`1e430fd6-5302-8135-8a27-000b14a69d9d`).

Format uses stable anchor IDs (defined in Phase 2):
```
Primary: harness§4.3-tool-discovery, mcp§5a-tool-filter
Supporting: harness§2.2-component-responsibilities
```

**Why rich text over a relation or multi-select:** There is no "Sections" database in Notion (and creating one is overkill for ~20 features). Section references are stable identifiers into markdown files. Rich text is flexible and doesn't require pre-populating options.

### 1c. Create Notion views

- **Features DB → "Architecture Roadmap" board view** — grouped by Status, showing `Design Doc Sections`, `Priority`, `User Stories` count
- **Design Decisions DB → "Active Decisions" table view** — filtered to Status=Accepted, sorted by Decision Date DESC, showing `Features` and `Impact Level`

### Files to modify
- `.claude/skills/notion-pm-workflow/references/notion-schema.md` — update with new properties, both KEN-E + MER-E database IDs

---

## Phase 2: Design Doc Conventions (Anchors + Roadmap Blocks)

**Goal:** Add stable cross-references and visible roadmap info to each design doc section.

### 2a. Add stable `<!-- anchor: -->` HTML comments to section headings

Every major section gets an invisible but grep-able anchor that survives heading renames and line-number shifts:

```markdown
<!-- anchor: harness-4.3-tool-discovery -->
### 4.3 Tool Discovery & Dynamic Tool Selection
```

**Naming convention:** `{doc-prefix}-{section-number}-{slug}`
- `harness-` for KEN-E-Agentic-Harness-Design.md
- `mcp-` for mcp-architecture.md
- `hierarchy-` for agent-hierarchy.md
- `api-` for api-gateway-multi-channel.md

**Why HTML comments:** Invisible when rendered, stable across heading renames, grep-able by agents, zero impact on human reading experience.

### 2b. Add visible roadmap info blocks under key section headings

Under each section heading that maps to Features, add a visible blockquote:

```markdown
<!-- anchor: harness-4.3-tool-discovery -->
### 4.3 Tool Discovery & Dynamic Tool Selection
> **Roadmap:** Feature 1.2 (Tool Registry) — In Progress | Stories: 2/3 done

Content follows...
```

For `[PLANNED]` sections:
```markdown
## 6. Multi-Channel Support [PLANNED]
> **Roadmap:** Feature 1.5 (Web Channel), Feature 3.5 (Slack Channel) — Planned | Stories: 0/4 done

Content follows...
```

**Format rules:**
- One-liner blockquote starting with `> **Roadmap:**`
- Lists Feature IDs with names in parentheses
- Shows aggregate status and story count
- Only on sections that map to Features (not every heading)

**Why visible blockquote:** Blockquotes render cleanly on GitHub and stand out without disrupting doc flow. A single line keeps it lightweight.

### 2c. Rewrite `design-doc-mapping.md` to use anchor-based references

Rewrite `.claude/skills/notion-pm-workflow/references/design-doc-mapping.md`:
- Replace line ranges with anchor IDs
- Add reverse index (anchor → Feature IDs)
- Keep existing keyword search index (already anchor-agnostic)

### Files to modify
- `docs/KEN-E-Agentic-Harness-Design.md` — add ~60 anchors, ~15 roadmap blocks
- `docs/design/mcp-architecture.md` — add ~15 anchors, ~5 roadmap blocks
- `docs/design/agent-hierarchy.md` — add ~12 anchors, ~4 roadmap blocks
- `docs/design/api-gateway-multi-channel.md` — add ~10 anchors, ~4 roadmap blocks
- `.claude/skills/notion-pm-workflow/references/design-doc-mapping.md` — full rewrite

---

## Phase 3: Workflow Definitions

**Goal:** Define clear processes for both PM-initiated and developer-initiated changes.

### 3a. PM-Initiated Workflow (Feature Creation/Modification)

PMs work entirely in Notion. The bridge to design docs happens through developer sessions.

**When PM creates a new Feature:**
1. PM creates Feature with standard properties (Name, Description, Status, Priority, Release)
2. PM populates `Design Doc Sections` with relevant anchor IDs (if known). If unknown, leave blank.
3. On the next `/start-session` for a story under that Feature, the agent suggests anchors from the keyword index and offers to populate the field.

**When PM modifies a Feature requiring design doc updates:**
1. PM adds a comment to the Feature page: "Needs design doc update: [description]"
2. The next `/start-session` for a story under that Feature surfaces this comment prominently.
3. The developer/agent updates the design doc and the `Design Doc Sections` field.

**Why no dedicated PM skill:** PMs don't use Claude Code. Their workflow stays Notion-native. Trying to automate PM→docs sync would require webhooks/polling — heavy infrastructure not justified at current team size.

### 3b. Developer-Initiated Workflow (Updated `/end-session` Flow)

Extend the existing design change check in `/end-session`:

**After creating a Design Decision:** Set `Features` and `Triggering Story` relations (using the new properties from Phase 1).

**After updating a design doc (High/Critical):** Update the `> **Roadmap:**` blockquotes in affected sections, and update `Design Doc Sections` on the Feature page if sections changed.

**When a story is marked Done:** Check if this moves any `> **Roadmap:**` block forward:
- Find parent Feature → read `Design Doc Sections` → update story counts
- If all stories done, flag section for `[PLANNED]` collapse (don't auto-collapse — present to developer for confirmation)

### 3c. `[PLANNED]` Lifecycle

A section progresses through these states via the `> **Roadmap:**` block:

```
[PLANNED] + "Stories: 0/N done"     → Planned, no work started
[PLANNED] + "Stories: K/N done"     → Partially implemented
(no tag)  + "Stories: N/N done"     → Fully implemented, [PLANNED] removed
```

Collapsing `[PLANNED]` means: remove the tag, merge "current" and "planned" subsections/diagrams, update status to "Implemented" in any tables.

---

## Phase 4: Claude Code Skill Updates

### 4a. Update `/start-session` skill

Modify `.claude/skills/start-session/SKILL.md`:

1. **Context gathering:** Read the Feature's `Design Doc Sections` property from Notion. If empty, suggest anchors from `design-doc-mapping.md` keyword index.
2. **Context gathering:** Read `> **Roadmap:**` blocks from referenced design doc sections to surface implementation status:
   ```
   ### Design Document Sections
   Primary: harness§4.3-tool-discovery (In Progress: 2/3 stories done)
   Supporting: mcp§5a-tool-filter (Planned: 0/2 stories done)
   ```
3. **Context gathering:** Check for PM comments on the Feature page containing "Needs design doc update". Surface prominently if found.
4. **Plan creation:** If any referenced sections have `[PLANNED]` status, note that the doc may need updating after implementation.

### 4b. Update `/end-session` skill

Modify `.claude/skills/end-session/SKILL.md`:

1. **Design change check:** Set `Features`, `Triggering Story`, `Affected Stories` relations on Design Decision records.
2. **Design change check (High/Critical):** Update `> **Roadmap:**` blocks after doc edits. Update Feature's `Design Doc Sections` in Notion.
3. **New step — Roadmap sync:** When story marked Done, update story counts in `> **Roadmap:**` blocks. Flag sections ready for `[PLANNED]` collapse.
4. **Database reference table:** Include both KEN-E and MER-E database IDs.

### 4c. Update reference files

- `.claude/skills/notion-pm-workflow/references/notion-schema.md` — add new properties, both DB sets
- `.claude/skills/notion-pm-workflow/references/design-change-workflow.md` — add Feature relation steps, roadmap block updates
- `.claude/skills/notion-pm-workflow/references/design-doc-mapping.md` — full rewrite (anchor-based, see 2c)

### Files to modify
- `.claude/skills/start-session/SKILL.md`
- `.claude/skills/end-session/SKILL.md`
- `.claude/skills/notion-pm-workflow/references/notion-schema.md`
- `.claude/skills/notion-pm-workflow/references/design-change-workflow.md`
- `.claude/skills/notion-pm-workflow/references/design-doc-mapping.md`

---

## Phase 5: CLAUDE.md & Documentation Updates

### 5a. Update CLAUDE.md "Design Documentation" section

1. Add mention of `<!-- anchor: -->` convention and naming scheme
2. Add mention of `> **Roadmap:**` blocks and the `[PLANNED]` lifecycle
3. Update "Workflow for New Design Decisions" to include Feature/Story relation steps and roadmap block updates
4. Add new subsection "Linking Design Docs to Roadmap" explaining conventions
5. Update design docs table to add anchor prefix column
6. Add note disambiguating KEN-E vs MER-E database sets, referencing `notion-schema.md`

### Files to modify
- `CLAUDE.md`

---

## Implementation Sequence

| Order | Item | Depends On | Complexity |
|-------|------|------------|------------|
| 1 | 1a: Design Decisions relations | — | Small |
| 2 | 1b: Features `Design Doc Sections` property | — | Small |
| 3 | 2a: Add anchors to all design docs | — | Medium |
| 4 | 2b: Add `> **Roadmap:**` blocks to design docs | 2a, 1b | Medium |
| 5 | 2c: Rewrite design-doc-mapping.md | 2a | Medium |
| 6 | 4c: Update reference files (notion-schema, design-change-workflow) | 1a, 1b | Small |
| 7 | 4a: Update /start-session | 2b, 4c | Medium |
| 8 | 4b: Update /end-session | 2b, 4c | Medium-Large |
| 9 | 5a: Update CLAUDE.md | 2a, 2b | Small |
| 10 | 1c: Create Notion views | 1a, 1b | Small |
| 11 | Backfill: Populate `Design Doc Sections` on existing Features | 2a | Incremental |
| 12 | Backfill: Set `Features` relations on existing Design Decisions | 1a | One-time |

Steps 1-2 are manual Notion work (prerequisite). Steps 3-6 can be a single session. Steps 7-10 are a second session. Steps 11-12 are incremental.

---

## Verification

After implementation:

1. **Anchor integrity:** `grep -r '<!-- anchor:' docs/` should return all anchors; each should match an entry in `design-doc-mapping.md`
2. **Roadmap block format:** `grep -r '> \*\*Roadmap:\*\*' docs/` should return all blocks; each should reference valid Feature IDs
3. **Notion schema:** Verify Design Decisions DB has `Features`, `Triggering Story`, `Affected Stories` relations; Features DB has `Design Doc Sections` property
4. **End-to-end test:** Run `/start-session` on a story under a Feature with populated `Design Doc Sections` — verify the session context shows design doc status and story progress
5. **PM workflow test:** Add a "Needs design doc update" comment to a Feature in Notion — verify `/start-session` surfaces it
6. **Design change test:** Run `/end-session` with a design change — verify it creates a Design Decision with `Features` relation set, and updates `> **Roadmap:**` blocks
