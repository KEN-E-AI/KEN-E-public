# Notion Database Schema Reference

## Database IDs

| Database | Database ID | Data Source ID |
|----------|-------------|----------------|
| Products | `2f230fd6530280ed8638d08cce017c37` | `2f230fd6-5302-8022-9267-000b5519fb1f` |
| Releases | `1c130fd653028078b55ecfef294a0c5c` | `1c130fd6-5302-80b9-9ea5-000b8b9b655f` |
| Features | `1ba30fd6530280f98ff2f9b91bf8d588` | `1ba30fd6-5302-8093-877f-000b545e5e3f` |
| User Stories | `1ba30fd6530280c8be86fbe0b85f09ca` | `1ba30fd6-5302-8000-9407-000b4fe01ba7` |
| Sprints | `1ba30fd653028072b0edcd90ee8748be` | `1ba30fd6-5302-80ed-9373-000bee60c1b9` |
| Session Logs | `2f230fd653028074aaffd8bed7b3d32b` | `2f230fd6-5302-80b3-a026-000be20a8517` |
| Design Decisions | `0b49b51c9ea04b1e9e828531512844fb` | `a88ce7c8-1ebb-4634-a422-2c1abcd2daf9` |

## Database Relationships

```
Products (1) ────> (many) Releases, Features, User Stories, Sprints, Session Logs, Design Decisions
Releases (1) ────> (many) Features
Features (1) ────> (many) User Stories
Features (many) <───> (many) Sprints
User Stories (many) <───> (many) Sprints
User Stories (many) <───> (many) User Stories [Dependencies - self-referential]
User Stories (many) <───> (many) Design Decisions [Affected by decisions]
Session Logs (many) ───> (1) User Story
Design Decisions (1) ───> (1) User Story [Triggering story]
Design Decisions (1) ────> (many) User Stories [Affected stories]
Design Decisions (1) ────> (many) Features [Affected features]
```

---

## 0. Products Database

| Property | Type | Valid Values |
|----------|------|--------------|
| Name | title | "KEN-E", "MER-E" |
| Description | rich_text | Product description |
| Status | status | `Not started`, `Planning`, `In development`, `Live` |
| Owner | person | Product lead |
| Repository | rich_text | Primary GitHub repo |

---

## 1. Releases Database

| Property | Type | Valid Values |
|----------|------|--------------|
| Name | title | e.g., "1.0 - MVP", "2.0 - The Report Builder" |
| Description | rich_text | - |
| Release Date | date | ISO-8601 format |
| Features | relation | Links to Features |
| Products | relation | Links to Products (KEN-E or MER-E) |

---

## 2. Features Database

| Property | Type | Valid Values |
|----------|------|--------------|
| Name | title | e.g., "1.1. Create Strategy Docs" |
| Description | rich_text | - |
| Status | status | `Backlog`, `Planned`, `In development`, `Live` |
| Priority | select | `🟢 Low`, `🟡 Medium`, `🔴 High` |
| User Stories | relation | Links to User Stories |
| Sprints | relation | Links to Sprints |
| Owner | person | - |
| Release Date | rollup | Rolled up from Releases |
| Target Release | date | ISO-8601 format |
| Feature Details | rich_text | Additional feature details |
| Creation Date | created_time | Auto-set on creation |
| Releases | relation | Links to Releases |
| Products | relation | Links to Products (KEN-E or MER-E) |

---

## 3. User Stories Database

| Property | Type | Valid Values |
|----------|------|--------------|
| Title | title | e.g., "1.1.1 - Automated Strategy Generation" |
| User Story | rich_text | "As a [persona], I want [action], So that [benefit]" |
| Status | status | `Backlog`, `In progress`, `Ready for test`, `Blocked`, `Done` |
| Priority | select | `🟢 Low`, `🟡 Medium`, `🔴 High` |
| Story Points | number | - |
| Assigned To | person | - |
| Acceptance Criteria | rich_text | Given/When/Then format |
| Definition of Done | rich_text | Verification checklist |
| Features | relation | Links to parent Feature |
| Sprints | relation | Links to Sprint(s) |
| Repository | select | GitHub repository name |
| Products | relation | Links to Products (KEN-E or MER-E) |
| Dependencies | relation | Links to User Stories this story depends on (self-referential) |
| Blocked By | relation | Links to User Stories blocking this story (self-referential) |
| Design Decisions | relation | Links to Design Decisions affecting this story |

---

## 4. Sprints Database

| Property | Type | Valid Values |
|----------|------|--------------|
| Sprint Name | title | e.g., "Sprint 1" |
| Sprint Number | number | - |
| Start Date | date | ISO-8601 format |
| End Date | date | ISO-8601 format |
| Status | status | `Planning`, `In progress`, `Completed`, `Retrospective` |
| User Stories | relation | Links to User Stories |
| Sprint Goal | rich_text | - |
| Velocity (Story Points) | number | - |
| Team Members | rollup | Rolled up from User Stories |
| SCRUM Team | select | `Customer Success`, `User Interface`, `DevOps`, `Core AI`, `Business Intelligence`, `Data Warehouse` |
| Retrospective Notes | rich_text | - |
| Products | relation | Links to Products (KEN-E or MER-E) |

---

## 5. Session Logs Database

| Property | Type | Valid Values |
|----------|------|--------------|
| Name | title | Session identifier |
| Session Date | date | ISO-8601 datetime |
| Developer | person | - |
| User Story | relation | Links to User Story being worked on |
| Plan | rich_text | What was planned for this session |
| Work Completed | rich_text | What was actually completed |
| Next Steps | rich_text | Actionable items for next session |
| Blockers | rich_text | Any blockers or open questions |
| Status | status | `Not started`, `In progress`, `Blocked`, `Completed` |
| Repository | rich_text | GitHub repository being worked on |
| Products | relation | Links to Products (KEN-E or MER-E) |

---

## 6. Design Decisions Database

Track architectural and design decisions made during development.

| Property | Type | Valid Values |
|----------|------|--------------|
| Title | title | Brief description of the decision |
| Decision Date | date | ISO-8601 format |
| Context | rich_text | Why this decision was needed |
| Decision | rich_text | What was decided |
| Alternatives Considered | rich_text | Other options that were rejected |
| Consequences | rich_text | Impact on the system |
| Status | select | `Proposed`, `Accepted`, `Superseded`, `Deprecated` |
| Impact Level | select | `Low`, `Medium`, `High`, `Critical` |
**Note:** The following relation properties are not yet in the Notion schema and need to be added manually:
- Triggering Story → User Story where this decision was made
- Affected Stories → User Stories impacted by this decision
- Affected Features → Features impacted by this decision
- Products → Links to Products (KEN-E or MER-E)

---

## MCP Tool Operations

### Search for a User Story

```
notion-search:
  query: "1.1.1" (or story title)
  query_type: "internal"
```

### Fetch Story Details

```
notion-fetch:
  id: "[page_id or URL]"
```

### Update Story Status

```
notion-update-page:
  data:
    page_id: "[User Story page ID]"
    command: "update_properties"
    properties:
      Status: "In progress"  # or "Ready for test", "Blocked", "Done"
```

### Create Session Log

```
notion-create-pages:
  parent:
    data_source_id: "2f230fd6-5302-80b3-a026-000be20a8517"
  pages:
    - properties:
        Name: "Session - [Story Title] - [Date]"
        date:Session Date:start: "2025-01-15"
        date:Session Date:is_datetime: 1
        Plan: "1. [First task]\n2. [Second task]"
        Status: "In progress"
        Repository: "[repo-name]"
```

### Update Session Log

```
notion-update-page:
  data:
    page_id: "[Session Log page ID]"
    command: "update_properties"
    properties:
      Work Completed: "- Completed X\n- Completed Y"
      Next Steps: "- Do A\n- Do B"
      Status: "Completed"
```

### Create New User Story

```
notion-create-pages:
  parent:
    data_source_id: "1ba30fd6-5302-8000-9407-000b4fe01ba7"
  pages:
    - properties:
        Title: "1.X.X - [Story Name]"
        User Story: "As a [persona], I want [action], So that [benefit]."
        Status: "Backlog"
        Acceptance Criteria: "1. Given [context], When [action], Then [result]."
        Definition of Done: "• Verify that..."
        Repository: "[repo-name]"
```

### Add Comment to Story

```
notion-create-comment:
  parent:
    page_id: "[User Story page ID]"
  rich_text:
    - type: "text"
      text:
        content: "Session completed. Ready for testing."
```

### Add Testing Notes to Story

```
notion-update-page:
  data:
    page_id: "[User Story page ID]"
    command: "insert_content_after"
    selection_with_ellipsis: "Definition of Done..."
    new_str: "\n\n## Testing Notes\n- [Note 1]\n- [Note 2]"
```

### Create Design Decision

```
notion-create-pages:
  parent:
    data_source_id: "a88ce7c8-1ebb-4634-a422-2c1abcd2daf9"
  pages:
    - properties:
        Title: "[Brief decision title]"
        date:Decision Date:start: "[YYYY-MM-DD]"
        date:Decision Date:is_datetime: 0
        Context: "[Why this decision was needed]"
        Decision: "[What was decided]"
        Alternatives Considered: "[Other options]"
        Consequences: "[Impact on the system]"
        Status: "Accepted"
        Impact Level: "[Low/Medium/High/Critical]"
      content: |
        ## Decision Record

        ### Context
        [Detailed context]

        ### Decision
        [The decision]

        ### Rationale
        [Why this over alternatives]

        ### Consequences
        [Impacts]
```

**Note:** After creating the decision, add relation properties manually in Notion:
- Triggering Story → link to the User Story where decision was made
- Affected Stories → link to impacted User Stories
- Affected Features → link to impacted Features
- Product → link to MER-E or KEN-E

### Link Design Decision to Affected Stories

After creating the decision, update each affected story:

```
notion-update-page:
  data:
    page_id: "[Affected Story page ID]"
    command: "update_properties"
    properties:
      Design Decisions: "[Decision Page URL]"
```

### Add Design Change Comment to Story

```
notion-create-comment:
  parent:
    page_id: "[Affected Story page ID]"
  rich_text:
    - type: "text"
      text:
        content: "⚠️ DESIGN CHANGE: This story is affected by [Decision Title].\n\nSee: [Decision URL]\n\nImpact: [How this story needs to change]"
```

---

## Data Validation Rules

1. **Status values must match exactly** (case-sensitive)
2. **Priority uses emoji prefix:** `🟢 Low`, `🟡 Medium`, `🔴 High`
3. **Dates use ISO-8601 format:** `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`
4. **Date properties require expanded format:**
   - `date:Session Date:start`: The date value
   - `date:Session Date:end`: Optional end date for ranges
   - `date:Session Date:is_datetime`: 1 for datetime, 0 for date only
5. **Relations use page IDs**, not names
6. **Title/Name properties are required** for all new pages
