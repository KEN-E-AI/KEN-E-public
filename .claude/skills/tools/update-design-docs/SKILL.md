# Tool SKILL: Update Design Docs

## Purpose

Ensures that changes to architecture and design documents propagate across two surfaces: other documents in the `docs/` directory, AND Linear issues that reference the changed documents in their "Design References" sections. When a document is modified, renamed, restructured, or deleted, both downstream docs and Linear issues must be updated to maintain consistency.

**Invoked by:** Product Assistant operation SKILL (`operations/product-assistant`, Flow 3: Design Doc Update) or Feature Planning flow (Flow 1, Step 5a)

## Algorithm

### Step 1 — Scan All Documents

Read all files in the `docs/` directory (and subdirectories). For each file, extract:
- File path
- Document title (first `#` heading)
- All cross-references: links to other docs, mentions of other component names, references to shared concepts (API endpoints, data models, config keys, etc.)

Supported file types: `.md`, `.txt`, `.pdf` (extract text), `.html`

The propagation paths for each doc differ by type — see Step 3's classification table to determine which downstream sections to update for the changed file.

### Step 2 — Build Dependency Map

Construct a directed graph of document dependencies:
- **Node:** Each document in `docs/`
- **Edge:** Document A → Document B if Document A contains a reference to Document B (link, filename mention, or shared concept reference)

The graph represents "A depends on B" — meaning if B changes, A may need to be updated.

**Reference detection patterns:**
- Explicit links: `[text](path/to/doc.md)` or `see docs/filename.md`
- Filename mentions: Any occurrence of another doc's filename (with or without path)
- Shared concept references: Terms defined in one doc and used in others (e.g., a data model name defined in `data-model.md` and referenced in `api-spec.md`)
- Section references: "See Section X of {document}" or "As described in {document}"

### Step 3 — Identify Impact

Given the primary document being modified:

1. **Classify the document type** — this determines which propagation paths to run:

   | Document Pattern | Type | Extra Propagation |
   |------------------|------|-------------------|
   | `docs/{Repo}-System-Architecture.md` | System architecture (Level 1) | Standard Step 5 only — these docs are referenced from many places but rarely have direct issue Design References |
   | `docs/design/components/{component}/README.md` | Component README (Level 2) | Run "Component README Propagation" (R1–R3) below in addition to Step 5 |
   | `docs/design/components/{component}/projects/{PRD-ID}*.md` | Project PRD (Level 3) | Run "PRD-Specific Propagation" (P1–P4) below in addition to Step 5 |
   | Other (`docs/design-guidelines.md`, `docs/data-visualization.md`, etc.) | Cross-cutting reference | Standard Step 5 only |

2. Read the change (diff between old and new content, or the PO's description of the change)
3. Traverse the dependency graph to find all documents that reference the primary document
4. For each downstream document, use Claude API reasoning to determine:
   - **Does this document need to change?** (not every reference requires an update — some are stable cross-references that don't depend on the specific content that changed)
   - **What specifically needs to change?** (which sections, which references, which values)

### Step 4 — Apply Updates

For each downstream document that needs changes:

1. Read the full document content
2. Apply the necessary updates:
   - Update cross-references if names, paths, or section headings changed
   - Update descriptions if the referenced concept's definition changed
   - Update examples if the referenced API or data model changed
   - Add notes if the change introduces a new constraint or deprecation
3. Preserve the document's existing style, formatting, and tone

### Step 5 — Propagate to Linear Issues

After updating downstream docs, propagate changes to Linear issues that reference the modified documents in their "Design References" sections.

#### 5a — Identify Affected Issues

For each document that was modified, renamed, or deleted (including the primary document and all downstream docs updated in Step 4), search for Linear issues that reference it.

**Search strategy:**
1. Extract the filename and path components from each changed doc. The canonical layout is `docs/design/components/{component}/...` (per `CLAUDE.md` §Context Loading Sequence). Examples:
   - `docs/design/components/automations/projects/A-PRD-01-data-model-and-api.md`
   - `docs/design/components/performance/README.md`
   - `docs/FUN-E-System-Architecture.md` (Level 1, repo-root)
2. Query the Linear API to find issues whose descriptions contain those filenames. Use the `list_issues` operation filtered by Team, then search description text for matches.
3. Also search for section-level references using the `§` pattern (e.g., `docs/design/components/...: §Section Name`)
4. **Legacy paths:** Some older issues may use the deprecated `docs/components/{component}/...` form (no `design/` segment). Search both patterns and propose a path-update propagation when the legacy form is found.

**Design References format in issue templates:**
All three issue templates (Feature, User Story, Bug Report) use the same canonical format:
```
## Design References
- docs/design/components/[component]/[doc-name]: §[section]
- docs/design/components/[component]/projects/[PRD-ID]-[slug].md: §[section]
- docs/[Repo-Name]-System-Architecture.md: §[section]
```

The PRD file (Level 3 context per `CLAUDE.md` §Context Loading Sequence) should appear as a Design Reference on every issue belonging to a Linear Project named `<PRD-ID>: <PRD title>` — this is the source-of-truth pointer to the spec the issue derives from.

#### 5b — Classify Changes per Issue

For each affected issue, determine what type of update is needed:

| Change Type | Issue Impact | Action |
|-------------|-------------|--------|
| **Doc renamed or moved** | File path in Design References is now stale | Update the path/filename in the reference |
| **Section heading renamed** | `§` reference points to a section that no longer exists | Update the section name in the reference |
| **Section removed** | `§` reference points to content that was deleted | Remove the reference and add a note: `[Removed — see {replacement} or contact PO]` |
| **Section moved to different doc** | `§` reference is in the wrong document | Update both the doc path and section name |
| **Content changed (same path/heading)** | Reference is still valid, but the referenced content has changed | No update to the reference itself, but post a comment on the issue noting the change (see 5d) |
| **New doc created** | Existing issues may benefit from referencing the new doc | Do NOT auto-add references — flag for PO review (see 5d) |
| **PRD §7 AC modified** (highest impact — see "PRD-Specific Propagation" below) | Child issues are 1:1 with PRD §7 ACs; modifying an AC potentially invalidates the matching issue's ACs | Block auto-edits. Post a notification comment on every issue mapped to the changed AC (resolve via PRD-ID prefix on the parent Linear Project) AND @mention the issue's PO. Require PO confirmation before any propagation. |
| **PRD §7 AC added** | New AC with no matching child issue means project coverage gap | Notify PO that a new issue is needed. Do NOT auto-create — let the product-assistant Flow 2 / roadmap update flow create the matching issue. |
| **PRD §7 AC removed** | Existing child issue is now orphaned (delivers an AC that no longer exists) | Notify PO. Do NOT auto-cancel the issue — the PO decides whether to cancel, repurpose, or revert the AC removal. |

#### 5c — Update Issue Descriptions

For issues that need description changes (renamed paths, renamed sections, removed sections):

1. Read the full issue description via the Linear API
2. Locate the `## Design References` section
3. Apply the targeted update — only modify the specific reference line(s) that changed
4. Preserve all other content in the description exactly as-is
5. Update the issue via the Linear API

**Critical:** Never modify content outside the `## Design References` section. The rest of the issue description (User Story, Acceptance Criteria, Context, Implementation Notes) is authored by the PO and must not be touched.

#### 5d — Post Notification Comments

For issues where the Design References remain valid but the underlying content changed, OR where new docs may be relevant, post an informational comment:

```markdown
**Product Assistant — Design Reference Update**

The following design documents referenced by this issue have been updated:

| Reference | Change |
|-----------|--------|
| `docs/{filename}: §{section}` | {brief description of what changed} |

**Action needed:** {None — references are still valid / PO should review whether AC or Implementation Notes need adjustment based on the doc changes}

---
_Agent: {component}-product-assistant | Timestamp: {ISO 8601}_
```

This comment alerts the PO that referenced content has changed without silently modifying the issue's substance.

## PRD-Specific Propagation

PRDs (`docs/design/components/{component}/projects/{PRD-ID}*.md`) have a special place in the dependency graph: each PRD maps **1:1 to a Linear Project**, and each Linear Project's child issues are 1:1 with the PRD's §7 acceptance criteria. A change to a PRD therefore has Linear-side effects that go beyond the standard "find issues that reference this file" search.

When the changed document is a PRD, run the following propagation logic in addition to the standard Step 5:

### P1 — Identify the Linear Project from the PRD-ID

Extract the `<PRD-ID>` prefix from the PRD filename (e.g., `A-PRD-01` from `A-PRD-01-data-model-and-api.md`). Query Linear for the Project whose name starts with `<PRD-ID>:`:

```graphql
query ProjectByPrdId {
  projects(filter: { name: { startsWith: "A-PRD-01:" } }) {
    nodes { id name issues { nodes { id identifier description state { name } } } }
  }
}
```

If no matching Project exists, log a warning — the PRD may have been authored before the Linear Project was created. Continue with the standard Step 5 propagation.

### P2 — Sync the Project Description

The Linear Project description is a one-paragraph summary that points to the PRD (per `CLAUDE.md` §Linear Issue Structure). It is NOT a copy of the PRD content. If the PRD's overview / scope changed materially, the Project description summary may now be stale.

Compare the current Project description against the PRD's overview / scope sections. If they have drifted, propose an updated Project description and ask the PO to confirm before applying. Do NOT auto-edit the Project description without confirmation — it may have been hand-tuned with project-level context not present in the PRD.

### P3 — §7 Acceptance Criteria Diff

Diff the PRD's §7 Acceptance Criteria section between old and new content. For each AC:

| Diff Result | Action |
|-------------|--------|
| Unchanged | No-op |
| Modified (same number, changed wording) | Find the matching child issue (by AC text similarity ≥ 0.7); post a notification comment AND @mention the issue's PO. **Block auto-editing the issue's description** — the PO must confirm whether the issue's AC should also change. |
| Added (new AC number) | Post a notification on the Linear Project @mentioning the PO that a new child issue is needed to cover the new AC. The product-assistant roadmap update flow handles actual issue creation. |
| Removed (AC number deleted) | Find the orphaned child issue (the one delivering this AC); post a notification @mentioning the PO. **Do NOT auto-cancel the issue** — the PO decides next steps. |
| Renumbered (same content, different number) | No-op for issue content; if any issue description text references "AC-X" by number, update those references after PO confirmation |

### P4 — Cross-Reference with `audit-project-coverage`

After applying the §7 AC diff, call `linear-sprint-ops` operation 19 (`audit-project-coverage`) on the Linear Project to confirm coverage is still complete. Report any gaps in the change summary (Step 6).

---

## Component README Propagation

Component READMEs (`docs/design/components/{component}/README.md`) sit one level above PRDs in the dependency hierarchy. A change to a component README potentially affects:

- **Every PRD under `projects/`** for that component (PRDs inherit conventions, key abstractions, and API contracts from the README)
- **Every Linear Project mapped to those PRDs**
- **Every child issue across those Linear Projects** (transitively)

When the changed document is a component README, run this fan-out check in addition to the standard Step 5:

### R1 — Enumerate Affected PRDs

```bash
ls docs/design/components/{component}/projects/*.md
```

For each PRD, evaluate whether the README change requires the PRD to be updated. Common patterns:

| README Change | PRD Impact |
|---------------|------------|
| Key directory or file path changed | PRDs that named the old path need updating |
| API contract / schema reference changed | PRDs that depend on the contract need re-checking |
| New convention introduced | PRDs authored before the convention may be inconsistent — flag (don't auto-edit) |
| Cross-component dependency added/removed | PRDs that referenced the old dependency model need updating |

If a PRD needs updating, recurse — the PRD update will trigger PRD-Specific Propagation (above) for any §7 AC effects.

### R2 — Notify PRD-Owning POs

A README change typically affects multiple Linear Projects, each with its own PO (Project Lead). Resolve the distinct set of POs across affected PRDs (similar to `resolve-pos-for-cycle` from `linear-sprint-ops`) and post a single consolidated notification on each affected Project @mentioning that Project's PO.

### R3 — Issue-Level Notification (Bulk-Sensitive)

A component README is referenced as a Design Reference by potentially DOZENS of issues. To avoid notification spam:

- If fewer than 10 issues reference the README directly: post per-issue notification comments per Step 5d
- If 10+ issues reference it: post a single consolidated comment on each affected Linear Project (NOT each issue), and rely on the per-Project @mention to surface the change. Include the issue count in the consolidated comment.

This is the threshold rule from "High Issue Volume" in Edge Cases below, applied specifically to README changes (which always have high fan-out).

---

### Step 6 — Generate Change Summary

Output the complete list of changes across both surfaces:

```markdown
### Change Summary

**Primary document:** `docs/{filename}`
**Change type:** {new content / modification / removal}

**Downstream documents updated:**

| Document | Section | Change |
|----------|---------|--------|
| `docs/{file_1}` | {section heading} | {brief description of change} |
| `docs/{file_2}` | {section heading} | {brief description of change} |

**Downstream documents reviewed but unchanged:**
- `docs/{file_3}` — references {primary doc} but the change does not affect the referenced content

**Linear issues updated:**

| Issue | Reference Changed | Update |
|-------|-------------------|--------|
| {ISSUE_ID}: {title} | `docs/{old_path}` → `docs/{new_path}` | Path updated in Design References |
| {ISSUE_ID}: {title} | `§{old_section}` → `§{new_section}` | Section reference updated |

**Linear issues notified (content change, references still valid):**
- {ISSUE_ID}: {title} — comment posted noting content change in `docs/{filename}`

**Files modified:** {count}
**Files reviewed:** {count}
**Issues updated:** {count}
**Issues notified:** {count}
```

## Consistency Rules

When propagating changes, enforce these consistency rules across BOTH docs and Linear issues:

### Naming Consistency
If a component, feature, or concept is renamed in the primary document, ALL references to the old name must be updated across all downstream documents AND all Linear issue Design References that use the old name.

### Schema Consistency
If a data model, API endpoint, or configuration key is modified in the primary document, ALL documents that describe or reference that schema must be updated. Linear issues referencing changed schemas should receive notification comments.

### Version Consistency
If a version number, dependency version, or tech stack version is updated, ALL documents that reference that version must be updated.

### Cross-Reference Integrity
If a section heading changes (which changes its anchor link), ALL documents that link to that section must have their links updated, AND all Linear issue `§` references to that section heading must be updated.

### Linear Issue Boundary
Only the `## Design References` section of an issue description may be modified programmatically. All other sections (User Story, Acceptance Criteria, Context, Implementation Notes, Description, etc.) are PO-authored content — never modify them. If a doc change has implications for those sections, post a notification comment instead.

## Edge Cases

### Circular References
If Document A references Document B and Document B references Document A, process each document exactly once. Use a visited set to prevent infinite traversal.

### External References
References to external URLs, APIs, or documents outside the `docs/` directory are noted but not modified. Only internal documents are updated.

### New Documents
If the change involves creating a new document, add it to the dependency map and check if existing documents should reference it.

### Document Deletion
If the change involves removing a document, identify all documents that reference it and update or remove those references. Flag any broken links. Also find all Linear issues with Design References pointing to the deleted doc and update those references (replace with the successor doc, or mark as removed).

### Completed Issues
When searching Linear for affected issues, include issues in ALL statuses — including "Done" and "Cancelled." Even completed issues should have accurate Design References for future audits and re-use. However, do NOT post notification comments on "Done" or "Cancelled" issues (the PO does not need to be alerted about closed work).

### High Issue Volume
If a doc change affects more than 20 Linear issues, batch the updates and include a summary count in the change report rather than listing every issue individually. Post a single consolidated Linear project update instead of per-issue comments (Linear Asks surfaces this in the team's Slack channel).

## Output

The tool returns:
1. The list of files modified (with full paths)
2. The diff for each modified file
3. The list of Linear issues updated (identifier + title + what changed)
4. The list of Linear issues notified (identifier + title + comment posted)
5. The change summary (formatted as in Step 6)

The calling SKILL (Product Assistant) is responsible for committing the file changes, reporting results to the PO in the terminal, and posting summaries to Linear where appropriate.
