# KEN-E Notion Database Schema Reference

## Database IDs

| Database | Database ID | Data Source ID |
|----------|-------------|----------------|
| Releases | `1c130fd653028078b55ecfef294a0c5c` | `1c130fd6-5302-8078-b55e-cfef294a0c5c` |
| Features | `1ba30fd6530280f98ff2f9b91bf8d588` | `1ba30fd6-5302-8093-877f-000b545e5e3f` |
| User Stories | `1ba30fd6530280c8be86fbe0b85f09ca` | `1ba30fd6-5302-8000-9407-000b4fe01ba7` |
| Sprints | `1ba30fd653028072b0edcd90ee8748be` | `1ba30fd6-5302-80ed-9373-000bee60c1b9` |
| Session Logs | `d83fc5bae1db403ea1294a87ea71dff0` | `9a4b21b6-36fe-46b4-980d-2628261411e3` |

## Database Relationships

```
Releases (1) ────> (many) Features
Features (1) ────> (many) User Stories
Features (many) <───> (many) Sprints
User Stories (many) <───> (many) Sprints
Session Logs (many) ───> (1) User Story
```

---

## 1. Releases Database

| Property | Type | Valid Values |
|----------|------|--------------|
| Name | title | e.g., "1.0 - MVP", "2.0 - The Report Builder" |
| Description | rich_text | - |
| Release Date | date | ISO-8601 format |
| Features | relation | Links to Features |

---

## 2. Features Database

| Property | Type | Valid Values |
|----------|------|--------------|
| Name | title | e.g., "1.1. Create Strategy Docs" |
| Description | rich_text | - |
| Status | select | `In development`, `Planned`, `Backlog` |
| Priority | select | `🔴 High`, (empty = normal) |
| User Stories | relation | Links to User Stories |
| Sprints | relation | Links to Sprints |
| Owner | person | - |
| Release Date | date | ISO-8601 format |
| Releases | relation | Links to Releases |

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

---

## 4. Sprints Database

| Property | Type | Valid Values |
|----------|------|--------------|
| Sprint Name | title | e.g., "Sprint 1" |
| Sprint Number | number | - |
| Start Date | date | ISO-8601 format |
| End Date | date | ISO-8601 format |
| Status | select | `In progress` |
| User Stories | relation | Links to User Stories |
| Sprint Goal | rich_text | - |
| Velocity (Story Points) | number | - |
| Team Members | person | - |
| Retrospective Notes | rich_text | - |

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
| Status | select | `In Progress`, `Completed`, `Blocked` |
| Repository | rich_text | GitHub repository being worked on |

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
    data_source_id: "9a4b21b6-36fe-46b4-980d-2628261411e3"
  pages:
    - properties:
        Name: "Session - [Story Title] - [Date]"
        date:Session Date:start: "2025-01-15"
        date:Session Date:is_datetime: 1
        Plan: "1. [First task]\n2. [Second task]"
        Status: "In Progress"
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
